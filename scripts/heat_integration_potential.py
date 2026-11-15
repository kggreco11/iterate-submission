"""
How much could heat integration add to a finished plant? (needs the simulator, no API calls)

Heat integration: the condenser of column A (heat rejected at the condenser temperature) supplies the reboiler of column B (heat needed at the reboiler
temperature) when Tc(A) - Tr(B) >= dT_min. The plant then buys less steam and less cooling:
    saving = transferred heat x (condenser price at Tc(A) + reboiler price at Tr(B)) x energy multiplier,   minus a new exchanger (Douglas area cost).
Temperatures are the tops and bottoms product temperatures of each solved column (the condenser and reboiler stage temperatures), duties are the solver's.
This is an idealised accounting of heat matching on solved columns: no pinch analysis, no steam levels, no control or start-up penalties.

Three numbers per plant:
  A. FIXED PRESSURES: best heat matching for the plant exactly as the agent built it (what a "link everything feasible" rule would give).
  B. PRESSURE RE-TUNE: coordinate search over each column's pressure drop (real re-solves), scoring each candidate with its best heat matching.
     This is the part that is not a bookkeeping rule: pressures change condenser/reboiler temperatures and the products.
  C. For reference, the same search without integration (pressure re-tune alone), so the integration gain is not confused with plain tuning.

    python scripts/heat_integration_potential.py runs/v2_opus/*.json --out results/hc16v2-first-look/heat_integration.json
"""
import argparse
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign import make_env, make_service  # noqa: E402
from sepdesign.cost_model import CostModel, HOURS, MS, M2_TO_FT2  # noqa: E402
from sepdesign.taskset import find_task  # noqa: E402
from sepdesign.tasks import cost_config  # noqa: E402

DT_MIN = 10.0
U_HX = 850.0
DP_GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)


def column_table(res):
    """[(path, Qc W, Tc K, Qr W, Tr K)] for every solved column of an evaluation result."""
    rows = []
    for p, n in res["nodes"].items():
        if n.get("status") != "ok":
            continue
        cr = n["column_result"]
        rows.append((p, abs(cr["qc"]), float(cr["tops"]["T"]), abs(cr["qr"]), float(cr["bottoms"]["T"])))
    return rows


def best_matching(rows, cm, dt_min=DT_MIN):
    """Greedy heat matching (largest $/W first): returns net saving $/yr and the list of links. A lower bound on the best matching."""
    f, cmod = cm.f, cm
    pc = {p: float(np.interp(Tc, f["cond_knots"], f["cond_price_per_GJ"])) for p, Qc, Tc, Qr, Tr in rows}
    pr = {p: float(np.interp(Tr, f["reb_knots"], f["reb_price_per_GJ"])) for p, Qc, Tc, Qr, Tr in rows}
    left_c = {p: Qc for p, Qc, Tc, Qr, Tr in rows}
    left_r = {p: Qr for p, Qc, Tc, Qr, Tr in rows}
    T_c = {p: Tc for p, Qc, Tc, Qr, Tr in rows}
    T_r = {p: Tr for p, Qc, Tc, Qr, Tr in rows}
    pairs = [(pc[a] + pr[b], a, b) for a in left_c for b in left_r if a != b and T_c[a] - T_r[b] >= dt_min]
    pairs.sort(reverse=True)
    total, links = 0.0, []
    for w, a, b in pairs:
        q = min(left_c[a], left_r[b])
        if q <= 1e3:
            continue
        gj = q * HOURS * 3600.0 / 1e9
        util = cmod.em * w * gj
        area = q / (U_HX * (T_c[a] - T_r[b]))
        capex = cmod.cm * f["capital_scale"] * MS * 101.3 * (area * M2_TO_FT2) ** 0.65 * (2.29 + 1.0) / cmod.p["payback"]
        if util - capex <= 0:
            continue
        left_c[a] -= q
        left_r[b] -= q
        total += util - capex
        links.append({"from_condenser": a or "feed", "to_reboiler": b or "feed", "MW": q / 1e6, "dT_K": T_c[a] - T_r[b], "saving_musd": (util - capex) / 1e6})
    return total, links


def integrated_reward(res, cm, norm):
    if not res["valid"]:
        return -1e18, 0.0, []
    s, links = best_matching(column_table(res), cm)
    return (res["revenue"] - res["tac"] + s) / norm, s, links


def coordinate_search(env, design, cm, norm, integrate, passes=2):
    """Greedy search over each column's pressure drop. Returns (best score, best design)."""
    def score(d):
        env.design = dict(d)
        r = env.evaluate()
        if not r["valid"]:
            return -1e18
        return integrated_reward(r, cm, norm)[0] if integrate else r["reward"]
    cur_d, cur = dict(design), score(design)
    for _ in range(passes):
        moved = False
        for p in sorted(cur_d, key=lambda q: (len(q), q)):
            for dp in DP_GRID:
                s = cur_d[p]
                if abs(s[3] - dp) < 1e-9:
                    continue
                cand = dict(cur_d)
                cand[p] = (s[0], s[1], s[2], dp)
                v = score(cand)
                if v > cur + 1e-4:
                    cur, cur_d, moved = v, cand, True
        if not moved:
            break
    return cur, cur_d


def analyse(path, backend=None, energy_mult=None):
    run = json.load(open(path))
    task = json.loads(json.dumps(find_task(run["task"])))
    if energy_mult is not None:                      # what-if: a different energy price level (the plant itself is unchanged)
        task.setdefault("economics", {}).setdefault("cost", {})["energy_multiplier"] = float(energy_mult)
    svc = make_service(backend, task=task)
    em, cmult = cost_config(task)
    cm = CostModel(energy_multiplier=em, capital_multiplier=cmult)
    env = make_env(task, svc, budget=100000)
    norm = env.econ.reward_norm
    design = {p: (int(c["n_stages"]), round(c["reflux"], 2), round(c["reboil"], 2), round(c["dp"], 2)) for p, c in run["trace"][-1]["columns"].items()}
    env.design = dict(design)
    base = env.evaluate()
    rows = column_table(base)
    gross_c = sum(r[1] for r in rows) / 1e6
    gross_r = sum(r[3] for r in rows) / 1e6
    A, links = best_matching(rows, cm)
    out = {"task": run["task"], "opus_reward": base["reward"], "columns": len(design), "total_condenser_MW": gross_c, "total_reboiler_MW": gross_r,
           "A_fixed_pressure": {"saving_musd": A / 1e6, "reward_gain": A / norm, "links": links},
           "temperatures": {(p or "feed"): {"Tc": Tc, "Tr": Tr, "Qc_MW": Qc / 1e6, "Qr_MW": Qr / 1e6} for p, Qc, Tc, Qr, Tr in rows}}
    s_plain, d_plain = coordinate_search(env, design, cm, norm, integrate=False)
    out["C_pressure_retune_only"] = {"reward": s_plain, "gain": s_plain - base["reward"]}
    env.design = dict(d_plain)
    s_int, d_int = coordinate_search(env, design, cm, norm, integrate=True)
    env.design = dict(d_int)
    r_int = env.evaluate()
    sc, saving, links_b = integrated_reward(r_int, cm, norm)
    out["B_pressure_retune_with_integration"] = {"reward": sc, "gain_over_opus": sc - base["reward"], "gain_over_plain_retune": sc - s_plain, "saving_musd": saving / 1e6,
                                                "links": links_b, "pressure_drops": {(p or "feed"): d_int[p][3] for p in d_int}}
    out["solves_used"] = env.solves_used
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--backend", default=None)
    ap.add_argument("--energy-mult", type=float, default=None, help="override the energy price multiplier (default: the task's, 2)")
    ap.add_argument("--out", default="runs/heat_integration.json")
    a = ap.parse_args()
    paths = [p for x in a.runs for p in glob.glob(x) if p.endswith(".json")]
    results = []
    for p in paths:
        r = analyse(p, a.backend, a.energy_mult)
        results.append(r)
        A, B, C = r["A_fixed_pressure"], r["B_pressure_retune_with_integration"], r["C_pressure_retune_only"]
        print(f"\n{r['task']}: Opus {r['opus_reward']:.3f}, {r['columns']} columns, condensers {r['total_condenser_MW']:.0f} MW, reboilers {r['total_reboiler_MW']:.0f} MW")
        print(f"  A. link at the plant's own pressures:  {A['reward_gain']:+.3f} (${A['saving_musd']:.0f}M/yr), {len(A['links'])} links")
        print(f"  C. pressure re-tune alone:             {C['gain']:+.3f}")
        print(f"  B. re-tune pressures + link:           {B['gain_over_opus']:+.3f} over Opus ({B['gain_over_plain_retune']:+.3f} over plain re-tune), ${B['saving_musd']:.0f}M/yr from {len(B['links'])} links")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(results, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
