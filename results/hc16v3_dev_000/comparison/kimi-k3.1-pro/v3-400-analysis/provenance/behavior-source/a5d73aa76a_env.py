"""
DesignEnv: an edit-and-evaluate environment for designing a separation plant as a tree of distillation columns.

A DESIGN maps a path to the settings of a column: {path: (n_stages, reflux_ratio, reboil_ratio, pressure_drop_fraction[, side_draw])}.
Paths name streams: "" is the feed; a column at path p has two outlets, p + "T" (tops, the light fraction) and p + "B" (bottoms), and, in tasks
that allow it (task["levers"]["side_draw"]), an optional third outlet p + "S": a side draw (stage, phase "liquid" or "vapour", fraction of the
column feed) taken from the middle of the column; and, in tasks that allow it (task["levers"]["double_effect"]), a DOUBLE-EFFECT column: the
same split done by two columns at different pressures, the high-pressure column's condenser boiling the low-pressure column's reboiler
(sepdesign/multi_effect.py). Settings tuples are (n, reflux, boil-up, dp) for a plain column, (n, reflux, boil-up, dp, side) with a side draw and
(n, reflux, boil-up, dp, None, (fraction to the HP column, LP pressure drop)) for a double-effect column; use side_of / effect_of to read them.
A stream with no column is SOLD AS IT IS: it earns money only if it is nearly pure (see Economics). So stopping is the default and every
column is an explicit decision.

Evaluating a design solves it from the feed down: each column's feed is the outlet of its parent. The simulator is called through
`column_fn(stream, settings)`; the cost to the agent is the number of DISTINCT column solves it has asked for in this episode (each charged
once, so re-evaluating unchanged columns is free). The episode score is the best design evaluated so far (anytime), so exploring never costs
the agent its best result. When the budget is exhausted, unsolved columns are reported as such and their feeds are sold as they are.

Typical use:
    env = DesignEnv(Economics(task), service.column, solve_budget=120)
    env.apply([{"op": "set", "node": "", "n_stages": 60, "reflux_ratio": 4, "reboil_ratio": 4, "pressure_drop_fraction": 0.1}])
    res = env.evaluate()           # res["reward"], res["nodes"], res["sold"], res["failed"] ...
    env.apply([{"op": "set", "node": "T", ...}, {"op": "sell", "node": "B"}, {"op": "revert"}])
    print(env.render(res)); env.score()
"""
import threading
import time

import numpy as np

from sepdesign.multi_effect import FRACTION_BOUNDS, heat_link
from sepdesign.tasks import action_bounds, cost_config
from sepdesign.validation import validate_result
from sepdesign.column_rules import SIDE_PHASES, SIDE_FRACTION_BOUNDS, optional_settings_errors

PARAM_KEYS = ("n_stages", "reflux_ratio", "reboil_ratio", "pressure_drop_fraction")


class EditError(ValueError):
    pass




def make_query(flows, T, P, n_stages, reflux, reboil, dp, side=None):
    """The hashable identity of a column solve (also the cache key). Without a side draw this is the plain 7-tuple."""
    q = (tuple(round(float(f), 6) for f in flows), round(float(T), 6), round(float(P), 6), int(n_stages), round(float(reflux), 2),
         round(float(reboil), 2), round(float(dp), 2))
    if side is None:
        return q
    return q + ((int(side[0]), str(side[1]), round(float(side[2]), 3)),)


def side_of(spec):
    """The side draw (stage, phase, fraction) of a settings tuple, or None."""
    return spec[4] if len(spec) > 4 else None


def effect_of(spec):
    """The double-effect settings (fraction to the HP column, LP pressure drop fraction) of a settings tuple, or None."""
    return spec[5] if len(spec) > 5 else None


def make_spec(base, side=None, effect=None):
    """Canonical settings tuple: 4 numbers, plus a side draw, plus a double effect (never both)."""
    base = tuple(base[:4])
    if effect is not None:
        return base + (None, tuple(effect))
    if side is not None:
        return base + (tuple(side),)
    return base


def _mix_weighted(streams):
    """Fallback mixer: flow-weighted temperature at the lowest pressure (used when the backend has no thermodynamics, e.g. the mock)."""
    P = min(p for _, _, p in streams)
    N = sum(float(np.sum(f)) for f, _, _ in streams)
    return sum(float(np.sum(f)) * T for f, T, _ in streams) / max(N, 1e-12), P


class Stream:
    __slots__ = ("flows", "T", "P")

    def __init__(self, flows, T, P):
        self.flows = np.round(np.asarray(flows, dtype=float), 6)
        self.T, self.P = float(T), float(P)


def _valid_path(p):
    return isinstance(p, str) and set(p) <= {"T", "B", "S"}


def path_key(p):
    """Sort key: shorter paths first, then tops, side draws, bottoms."""
    return (len(p), p.replace("T", "0").replace("S", "1").replace("B", "2"))


class DesignEnv:
    def __init__(self, econ, column_fn, solve_budget=120, max_columns=None, names=None, mix_fn=None):
        self.econ = econ
        self.column_fn = column_fn
        self.mix_fn = mix_fn or _mix_weighted
        self.solve_budget = int(solve_budget)
        self.max_columns = int(max_columns) if max_columns else int(econ.stream_limit)
        self.names = list(names) if names else list(econ.task["components"])
        self.bounds = action_bounds(econ.task)
        self.side_draw_allowed = bool((econ.task.get("levers") or {}).get("side_draw"))
        self.double_effect_allowed = bool((econ.task.get("levers") or {}).get("double_effect"))
        self.energy_multiplier, self.capital_multiplier = cost_config(econ.task)
        self._lock = threading.Lock()
        self.reset()

    # ------------------------------------------------------------------ state
    def reset(self):
        self.design = {}
        self.paid = set()
        self.best = None                 # (reward, design copy, result)
        self.curve = []                  # (solves_used, reward, best_reward) after every evaluation
        self.last = None
        self.n_evals = 0
        return self

    @property
    def solves_used(self):
        return len(self.paid)

    @property
    def solves_left(self):
        return self.solve_budget - len(self.paid)

    # ------------------------------------------------------------------ editing
    def _check_params(self, spec):
        out = []
        for k in PARAM_KEYS:
            if k not in spec:
                raise EditError(f"missing {k}")
            lo, hi = self.bounds[k]
            v = float(spec[k])
            if not (lo <= v <= hi):
                raise EditError(f"{k}={v} outside [{lo}, {hi}]")
            out.append(int(round(v)) if k == "n_stages" else round(v, 2))
        side_t = effect_t = None
        side = spec.get("side_draw")
        if side:
            if not self.side_draw_allowed:
                raise EditError("this task has no side draws (side_draw is not available)")
            try:
                stage, phase, frac = int(side["stage"]), str(side["phase"]).lower(), float(side["fraction"])
            except (KeyError, TypeError, ValueError):
                raise EditError('side_draw must be {"stage": int, "phase": "liquid"|"vapour", "fraction": number}')
            n, fs = out[0], int(round(out[0] / 2))
            if phase not in SIDE_PHASES:
                raise EditError(f"side_draw phase must be 'liquid' or 'vapour', not {phase!r}")
            if not 2 <= stage <= n - 1:
                raise EditError(f"side_draw stage {stage} outside 2..{n - 1} for a {n}-stage column (stage 1 is the condenser, stage {n} the reboiler)")
            if stage == fs:
                raise EditError(f"side_draw stage {stage} is the feed stage; choose another stage")
            lo, hi = SIDE_FRACTION_BOUNDS
            if not lo <= frac <= hi:
                raise EditError(f"side_draw fraction {frac} outside [{lo}, {hi}] (fraction of the column feed taken as the side stream)")
            side_t = (stage, phase, round(frac, 3))
        eff = spec.get("double_effect")
        if eff:
            if not self.double_effect_allowed:
                raise EditError("this task has no double-effect columns (double_effect is not available)")
            if side_t is not None:
                raise EditError("a column cannot have both a side draw and a double effect")
            try:
                f, dpl = float(eff["fraction"]), float(eff["low_pressure_drop_fraction"])
            except (KeyError, TypeError, ValueError):
                raise EditError('double_effect must be {"fraction": number, "low_pressure_drop_fraction": number}')
            lo, hi = FRACTION_BOUNDS
            if not lo <= f <= hi:
                raise EditError(f"double_effect fraction {f} outside [{lo}, {hi}] (share of the feed sent to the high-pressure column)")
            dp_hi = self.bounds["pressure_drop_fraction"][1]
            if not out[3] + 0.01 <= dpl <= dp_hi:
                raise EditError(f"double_effect low_pressure_drop_fraction {dpl} must be above the column's pressure_drop_fraction {out[3]} "
                                f"(the low-pressure column runs at a lower pressure) and at most {dp_hi}")
            effect_t = (round(f, 2), round(dpl, 2))
        result = make_spec(out, side_t, effect_t)
        errors = optional_settings_errors(result, self.econ.task, self.bounds)
        if errors:
            raise EditError('; '.join(errors))
        return result

    def _applied(self, edits):
        new = dict(self.design)
        for e in edits:
            op = e.get("op")
            if op == "revert":
                if self.best is None:
                    raise EditError("nothing to revert to: no design has been evaluated yet")
                new = dict(self.best[1])
                continue
            node = e.get("node", "")
            if not _valid_path(node):
                raise EditError(f"bad node {node!r}: use '' for the feed and a string of T/B{'/S' if self.side_draw_allowed else ''} for outlets (e.g. 'TB')")
            if op == "set":
                if node != "" and node[:-1] not in new:
                    raise EditError(f"cannot put a column on {node!r}: its parent {node[:-1]!r} has no column")
                spec = self._check_params(e)
                if node.endswith("S") and side_of(new[node[:-1]]) is None:
                    raise EditError(f"cannot put a column on {node!r}: column {node[:-1]!r} has no side draw (set one on it first)")
                new[node] = spec
                if side_of(spec) is None:                  # the column has no side draw (any more): the columns below its side outlet go
                    for p in [p for p in new if p.startswith(node + "S")]:
                        del new[p]
            elif op == "sell":
                if node not in new:
                    raise EditError(f"no column at {node!r} to remove")
                for p in [p for p in new if p.startswith(node)]:
                    del new[p]
            else:
                raise EditError(f"unknown op {op!r}")
        if len(new) > self.max_columns:
            raise EditError(f"design would have {len(new)} columns; the cap is {self.max_columns}")
        return new

    def validate(self, edits):
        """List of error strings (empty if the edits are valid). Does not change the design."""
        try:
            self._applied(edits)
            return []
        except EditError as ex:
            return [str(ex)]

    def apply(self, edits):
        """Apply edits atomically (all or none). Forms:
             {"op": "set",  "node": path, "n_stages":.., "reflux_ratio":.., "reboil_ratio":.., "pressure_drop_fraction":..}
             {"op": "sell", "node": path}     remove the column at path and everything below it
             {"op": "revert"}                 go back to the best design evaluated so far
           A column can only be set at "" or below an existing column. Raises EditError (design unchanged) on any problem."""
        self.design = self._applied(edits)
        return self

    def preview(self, edits):
        return self._applied(edits)

    # ------------------------------------------------------------------ evaluation
    def _solve_design(self, design):
        """Solve `design` from the feed down. Thread-safe (budget accounting is under a lock); does not touch self.design / best / curve."""
        e = self.econ
        nodes, sold = {}, []
        total = {"revenue": 0.0, "tac": 0.0}

        def sell(path, s, why):
            v, kind = e.classify(s.flows)
            total["revenue"] += v
            nodes[path]["kind"] = kind
            sold.append({"node": path, "value": v, "why": why, "flows": s.flows.tolist(), "kind": kind})
            return v

        def walk(path, s):
            spec = design.get(path)
            info = {"node": path, "feed": s.flows.tolist(), "T": s.T, "P": s.P}
            nodes[path] = info
            if spec is None:
                info["status"], info["value"] = "sold", sell(path, s, "no column")
                return
            if e.negligible(s.flows):
                info["status"], info["value"] = "negligible_feed", sell(path, s, "negligible flow, column skipped")
                return
            side_spec, eff = side_of(spec), effect_of(spec)
            if eff is not None:                        # double effect: two columns on a split feed
                hp_s = Stream(s.flows * eff[0], s.T, s.P)
                lp_s = Stream(s.flows - hp_s.flows, s.T, s.P)
                calls = [(hp_s, tuple(spec[:4])), (lp_s, tuple(spec[:3]) + (eff[1],))]
            else:
                calls = [(s, tuple(spec[:4]) + ((side_spec,) if side_spec is not None else ()))]
            qs = {make_query(st.flows, st.T, st.P, *a) for st, a in calls}
            with self._lock:
                new_q = qs - self.paid
                over = bool(new_q) and len(self.paid) + len(new_q) > self.solve_budget
                if not over:
                    self.paid.update(new_q)
            if over:
                info["status"], info["value"] = "not_solved_budget", sell(path, s, "solve budget exhausted")
                return
            info["spec"] = spec
            if eff is not None:
                rh, rl = self.column_fn(*calls[0]), self.column_fn(*calls[1])
                res = self._pair_result(rh, rl, eff)
            else:
                res = self.column_fn(*calls[0])
            info["column_result"] = res
            if not res["ok"]:
                info["status"], info["error"] = "failed", res.get("error")
                info["value"] = sell(path, s, "solve failed")
                return
            info["status"], info["tac"] = "ok", float(res["tac"])
            total["tac"] += float(res["tac"])
            tops = Stream(res["tops"]["flows"], res["tops"]["T"], res["tops"]["P"])
            bots = Stream(res["bottoms"]["flows"], res["bottoms"]["T"], res["bottoms"]["P"])
            info["tops"], info["bottoms"] = tops.flows.tolist(), bots.flows.tolist()
            walk(path + "T", tops)
            if side_spec is not None:
                sd = res.get("side")
                if sd is None:
                    info["status"], info["error"] = "failed", "the simulator returned no side stream"
                    info["value"] = sell(path, s, "solve failed")
                    return
                side = Stream(sd["flows"], sd["T"], sd["P"])
                info["side"] = side.flows.tolist()
                walk(path + "S", side)
            walk(path + "B", bots)

        walk("", Stream(e.feed, e.T0, e.P0))
        reward = (total["revenue"] - total["tac"]) / e.reward_norm
        failed = [p for p, n in nodes.items() if n["status"] == "failed"]
        unsolved = [p for p, n in nodes.items() if n["status"] == "not_solved_budget"]
        # A design is VALID only if every column in it solved. A failed column's feed is sold as it is, which can score well, so such a design
        # is shown to the agent but never counts as the best design, the score, or the best-so-far curve.
        return {"reward": reward, "revenue": total["revenue"], "tac": total["tac"], "columns": len(design),
                "recovery": total["revenue"] / e.max_total_revenue if e.max_total_revenue else 0.0, "nodes": nodes, "sold": sold,
                "solves_used": self.solves_used, "solves_left": self.solves_left, "failed": failed, "unsolved_budget": unsolved,
                "valid": not failed and not unsolved}

    def _pair_result(self, rh, rl, eff):
        """Combine the two columns of a double effect into one column result (mixed outlets, net cost, external duties)."""
        effects = {"fraction": eff[0], "low_pressure_drop_fraction": eff[1], "hp": rh, "lp": rl}
        if not (rh.get("ok") and rl.get("ok")):
            which = "high-pressure" if not rh.get("ok") else "low-pressure"
            return {"ok": False, "error": f"the {which} column of the double effect failed: " + str((rh if not rh.get("ok") else rl).get("error")),
                    "effects": effects}
        link = heat_link(rh, rl, self.energy_multiplier, self.capital_multiplier)
        effects["link"] = link
        out = {"ok": True, "effects": effects}
        for key in ("tops", "bottoms"):
            parts = [(np.asarray(r[key]["flows"], float), float(r[key]["T"]), float(r[key]["P"])) for r in (rh, rl)]
            try:
                T, P = self.mix_fn(parts)
                if not np.isfinite(T) or T <= 0 or not np.isfinite(P) or P <= 0:
                    raise ValueError('Nonfinite or nonpositive mixed state')
            except Exception as exc:
                return {'ok': False, 'error': 'Adiabatic mixing failed: ' + type(exc).__name__, 'effects': effects}
            out[key] = {"flows": (parts[0][0] + parts[1][0]).tolist(), "T": float(T), "P": float(P)}
        q = link["heat_MW"] * 1e6
        out["tac"] = float(rh["tac"]) + float(rl["tac"]) - link["saving_usd"] + link["exchanger_usd"]
        out["qc"] = float(rh["qc"]) + float(rl["qc"]) + (q if float(rh["qc"]) < 0 else -q)      # condenser duty bought from utilities
        out["qr"] = float(rh["qr"]) + float(rl["qr"]) - q                                         # reboiler duty bought from utilities
        return out

    def _record(self, design, result):
        self.n_evals += 1
        result["validation"] = validate_result(design, result, self.econ, self.bounds, self.max_columns)
        result["valid"] = result["validation"]["eligible"]
        if result["valid"] and (self.best is None or result["reward"] > self.best[0]):
            self.best = (result["reward"], dict(design), result)
        self.curve.append((self.solves_used, result["reward"], self.best[0] if self.best else None))

    def evaluate(self):
        """Solve the current design. Columns beyond the solve budget are reported 'not solved (budget)' and their feeds sold as they are."""
        result = self._solve_design(self.design)
        self._record(self.design, result)
        self.last = result
        return result

    def cleanup_unsolved(self):
        """At the hard cap, sell only unmeasured branches; preserve all solved settings.

        This deterministic finalization cannot spend another distinct solve. The
        caller retains the original incomplete proposal in its audit trajectory.
        """
        if self.solves_left != 0 or not self.last or not self.last['unsolved_budget']:
            return self.last
        self.apply([{'op': 'sell', 'node': p} for p in self.last['unsolved_budget']])
        return self.evaluate()

    def evaluate_batch(self, designs, workers=8):
        """Evaluate several candidate designs concurrently (budget is charged for the union of distinct solves, so candidates that share
        columns share their cost). self.design / self.last are unchanged; returns result dicts in input order."""
        from concurrent.futures import ThreadPoolExecutor
        designs = [dict(d) for d in designs]
        with ThreadPoolExecutor(max_workers=max(1, min(workers, len(designs)))) as ex:
            results = list(ex.map(self._solve_design, designs))
        for d, r in zip(designs, results):
            r["solves_used"], r["solves_left"] = self.solves_used, self.solves_left
            self._record(d, r)
        return results

    def step(self, edits):
        """apply + evaluate. On an invalid edit the design is unchanged and no solve is charged."""
        self.apply(edits)
        return self.evaluate()

    # ------------------------------------------------------------------ outcome
    def score(self):
        """Reward of the best fully-evaluated design (None if nothing has been evaluated)."""
        return None if self.best is None else self.best[0]

    def best_so_far_at(self, solves):
        """Best reward reached using at most `solves` distinct solves (for budget-matched comparisons)."""
        b = None
        for used, _, best in self.curve:
            if used <= solves and best is not None:
                b = best
        return b

    # ------------------------------------------------------------------ text view for language-model agents
    def render(self, result=None, top=3):
        """Compact text description of a result: the tree, each column's settings and cost, each stream's main components, and what sold."""
        r = result or self.last
        if r is None:
            return "No design evaluated yet."
        lines = [f"reward {r['reward']:.3f} | revenue ${r['revenue'] / 1e6:.1f}M/yr | column cost ${r['tac'] / 1e6:.1f}M/yr | "
                 f"{r['columns']} columns | solves used {r['solves_used']}/{self.solve_budget}"
                 + ("" if r["valid"] else f" | NOT VALID: {len(r['failed'])} column(s) failed, {len(r['unsolved_budget'])} unsolved; does not count")]
        if "validation" in r and not r["valid"]:
            lines.append("Validation: " + "; ".join(r["validation"]["errors"][:5]))
        for path in sorted(r["nodes"], key=path_key):
            n = r["nodes"][path]
            fl = np.asarray(n["feed"], float)
            idx = np.argsort(-fl)[:top]
            mix = ", ".join(f"{self.names[i]} {fl[i] / max(fl.sum(), 1e-12):.0%}" for i in idx if fl[i] > 0)
            tag = f"[{path or 'feed'}] {fl.sum():.0f} mol/s ({mix})"
            if n["status"] == "ok":
                s = n["spec"]
                sdr, eff = side_of(s), effect_of(s)
                sd = f", side draw {sdr[2]:.0%} of feed ({sdr[1]}, stage {sdr[0]}) -> '{path}S'" if sdr is not None else ""
                if eff is not None:
                    ef = n["column_result"]["effects"]
                    lk = ef["link"]
                    hp, lp = ef["hp"], ef["lp"]
                    link_txt = (f"HP condenser ({hp['cost']['Tc']:.0f} K) heats LP reboiler ({lp['cost']['Tr']:.0f} K): {lk['heat_MW']:.0f} MW, saves "
                                f"${lk['saving_usd'] / 1e6:.1f}M/yr, shared exchanger ${lk['exchanger_usd'] / 1e6:.1f}M/yr" if lk["feasible"]
                                else f"NO heat link: {lk['why']}")
                    sd = (f", DOUBLE EFFECT {eff[0]:.0%} of feed to HP column (dp {s[3]}, {hp['tops']['P'] / 1e5:.1f} bar, cost ${hp['tac'] / 1e6:.1f}M/yr), "
                          f"rest to LP column (dp {eff[1]}, {lp['tops']['P'] / 1e5:.1f} bar, cost ${lp['tac'] / 1e6:.1f}M/yr); {link_txt}")
                lines.append(f"{tag} -> column {s[0]} stages, reflux {s[1]}, boil-up {s[2]}, dp {s[3]}{sd}, cost ${n['tac'] / 1e6:.1f}M/yr")
            elif n["status"] == "sold":
                lines.append(f"{tag} -> sold for ${n['value'] / 1e6:.1f}M/yr" + (f" ({n['kind']})" if n.get("kind") in ("premium",) or str(n.get("kind", "")).startswith("blend") else "")
                         + ("" if n["value"] > 0 else " (not pure enough: worth 0)"))
            else:
                lines.append(f"{tag} -> {n['status']}" + (f": {n.get('error')}" if n.get("error") else ""))
        return "\n".join(lines)


def attach_trace(env, names=None):
    """Record a snapshot each time the best design improves (solves used, wall time, reward, revenue, cost, columns, products). The list is also
    kept on env.trace; sepdesign.runlog.save_run writes it out for the plant-replay page."""
    names = list(names or env.names)
    trace = []
    orig = env._record
    t0 = time.perf_counter()

    def rec(design, result):
        before = env.best[0] if env.best else None
        orig(design, result)
        if env.best is not None and (before is None or env.best[0] > before):
            products = []
            for s in result["sold"]:
                fl = np.asarray(s["flows"], float)
                tot = float(fl.sum())
                if tot <= 0:
                    continue
                k = int(np.argmax(fl))
                products.append({"node": s["node"], "component": names[k], "kind": s.get("kind", "none"), "purity": float(fl[k] / tot), "value": float(s["value"]),
                                 "flow_mol_s": tot})
            cols = {p: {"n_stages": int(v[0]), "reflux": float(v[1]), "reboil": float(v[2]), "dp": float(v[3]),
                        "tac": float(result["nodes"][p].get("tac", 0.0)),
                        **({"side": {"stage": int(v[4][0]), "phase": v[4][1], "fraction": float(v[4][2])}} if side_of(v) is not None else {}),
                        **({"double_effect": {"fraction": float(v[5][0]), "low_pressure_drop_fraction": float(v[5][1]),
                                              "heat_MW": float(result["nodes"][p]["column_result"]["effects"]["link"]["heat_MW"])}}
                           if effect_of(v) is not None and result["nodes"][p].get("status") == "ok" else {})}
                    for p, v in design.items() if p in result["nodes"]}
            trace.append({"solves": env.solves_used, "wall_s": time.perf_counter() - t0, "reward": float(result["reward"]),
                          "revenue": float(result["revenue"]), "tac": float(result["tac"]), "columns": cols, "products": products})

    env._record = rec
    env.trace = trace
    return trace
