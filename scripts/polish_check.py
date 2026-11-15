"""
Local-optimality check of a finished design (needs the simulator, no API calls).

Takes the best design of a run file and asks the simulator three questions:
  1. PRUNE: does removing any column (and everything below it) raise the reward? (Removal re-uses solved results: nearly free.)
  2. ADD: for each stream that is sold but not pure, does a new column (best of a small grid of settings) raise the reward?
  3. TUNE: does greedy tuning of the settings of the pruned / extended design raise it further?
It reports the reward after each step, the per-column marginal value, and the value still sitting in impure streams versus the cost of the best
column found for it. If nothing improves the design, it is locally optimal under these moves; that is evidence, not proof, of being near-best.

    python scripts/polish_check.py runs/llm_opus/*.json --out results/opus-5-5-dev-first-look/polish_check.json
"""
import argparse
import itertools
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign import baselines, make_env, make_service  # noqa: E402
from sepdesign.env import make_spec  # noqa: E402
from sepdesign.taskset import find_task  # noqa: E402

GRID = list(itertools.product((60, 120), (3.0, 8.0, 20.0), (3.0, 8.0, 20.0), (0.0,)))      # stages, reflux, boil-up, pressure drop


def load_design(run):
    cols = run["trace"][-1]["columns"]
    out = {}
    for p, c in cols.items():
        side = (int(c["side"]["stage"]), c["side"]["phase"], round(c["side"]["fraction"], 3)) if "side" in c else None
        eff = (round(c["double_effect"]["fraction"], 2), round(c["double_effect"]["low_pressure_drop_fraction"], 2)) if "double_effect" in c else None
        out[p] = make_spec((int(c["n_stages"]), round(c["reflux"], 2), round(c["reboil"], 2), round(c["dp"], 2)), side, eff)
    return out


def impure_leaves(env, res):
    out = []
    for p, n in res["nodes"].items():
        if n["status"] == "sold" and n["value"] <= 0 and p not in env.design:
            fl = np.asarray(n["feed"], float)
            if not env.econ.negligible(fl):
                out.append((p, float(fl @ env.econ.prices * env.econ.seconds)))
    return out


def analyse(args):
    path, backend, as_family = args
    run = json.load(open(path))
    tid = run["task"] if not as_family else as_family + "_" + "_".join(run["task"].split("_")[1:])    # re-price a plant on another family's task
    task = find_task(tid)
    svc = make_service(backend, task=task)
    env = make_env(task, svc, budget=2500)
    norm = env.econ.reward_norm
    design = load_design(run)
    env.design = dict(design)
    base = env.evaluate()
    out = {"task": tid, "source_run": os.path.basename(path), "opus_reported_best": run["best_reward"], "base_reward": base["reward"], "base_valid": base["valid"],
           "norm_usd": norm, "columns": len(design), "steps": []}
    # 1. marginal value of each column (remove it and everything below it)
    marg = []
    cands = [(p, {q: s for q, s in design.items() if not q.startswith(p)}) for p in sorted(design, key=lambda p: (len(p), p))]
    res = env.evaluate_batch([d for _, d in cands], workers=4)
    for (p, d), r in zip(cands, res):
        marg.append({"path": p, "subtree_columns": len(design) - len(d), "reward_if_removed": r["reward"], "delta": r["reward"] - base["reward"],
                     "valid": r["valid"], "column_cost_musd": base["nodes"][p].get("tac", 0.0) / 1e6})
    out["marginal"] = sorted(marg, key=lambda m: -m["delta"])
    # 2. greedy prune: keep removing the column whose removal helps most, while it helps
    cur, cur_r = dict(design), base
    while True:
        cs = [(p, {q: s for q, s in cur.items() if not q.startswith(p)}) for p in cur if p]
        cs.append(("", {}))
        rs = env.evaluate_batch([d for _, d in cs], workers=4)
        j = int(np.argmax([r["reward"] if r["valid"] else -1e18 for r in rs]))
        if rs[j]["valid"] and rs[j]["reward"] > cur_r["reward"] + 1e-4:
            cur, cur_r = cs[j][1], rs[j]
        else:
            break
    out["steps"].append({"step": "prune", "reward": cur_r["reward"], "columns": len(cur)})
    # 3. add: best new column on each impure stream, repeated while it helps
    adds = []
    for _ in range(3):
        env.design = dict(cur)
        r0 = env.evaluate()
        leaves = impure_leaves(env, r0)
        if not leaves:
            break
        trials = [(p, g, {**cur, p: g}) for p, _ in leaves for g in GRID]
        rs = env.evaluate_batch([d for _, _, d in trials], workers=4)
        best, bj = r0["reward"], None
        for j, r in enumerate(rs):
            if r["valid"] and r["reward"] > best + 1e-4:
                best, bj = r["reward"], j
        adds.append({"impure_streams": [{"path": p, "unrealised_value_musd": v / 1e6} for p, v in leaves], "best_gain": best - r0["reward"],
                     "best_move": None if bj is None else {"path": trials[bj][0], "settings": trials[bj][1]}})
        if bj is None:
            break
        cur = trials[bj][2]
    out["adds"] = adds
    env.design = dict(cur)
    r_add = env.evaluate()
    out["steps"].append({"step": "add", "reward": r_add["reward"], "columns": len(cur)})
    # 4. tune settings by greedy hill climbing (200 more solves)
    env.solve_budget = env.solves_used + 200
    baselines.greedy_local(env, passes=2)
    out["steps"].append({"step": "tune", "reward": env.score(), "columns": len(env.best[1]) if env.best else None})
    out["final_reward"] = max(s["reward"] for s in out["steps"])
    out["improvement_vs_opus"] = out["final_reward"] - base["reward"]
    out["solves_used"] = env.solves_used
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--backend", default=None)
    ap.add_argument("--out", default="runs/polish_check.json")
    ap.add_argument("--as-family", default=None, help="score each plant on the same-numbered task of this family (e.g. hc16v3: same feed, V3 prices)")
    a = ap.parse_args()
    paths = [p for p in a.runs if p.endswith(".json")]
    with ProcessPoolExecutor(min(4, len(paths))) as ex:
        results = list(ex.map(analyse, [(p, a.backend, a.as_family) for p in paths]))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(results, open(a.out, "w"), indent=1)
    for r in sorted(results, key=lambda r: r["task"]):
        print(f"\n{r['task']}: Opus best {r['opus_reported_best']:.3f} (re-simulated {r['base_reward']:.3f}, {r['columns']} columns)")
        wasteful = [m for m in r["marginal"] if m["delta"] > 1e-4]
        print(f"  columns whose removal RAISES the reward: {len(wasteful)}", [(m['path'] or 'feed', round(m['delta'], 3)) for m in wasteful[:5]])
        print("  least valuable columns (reward change if removed):", [(m['path'] or 'feed', round(m['delta'], 3), f"${m['column_cost_musd']:.0f}M") for m in r["marginal"][:4]])
        for s in r["steps"]:
            print(f"  after {s['step']:<5}: reward {s['reward']:.3f} ({s['reward'] - r['base_reward']:+.3f}), {s['columns']} columns")
        a0 = r["adds"][0] if r["adds"] else None
        if a0:
            tot = sum(x["unrealised_value_musd"] for x in a0["impure_streams"])
            print(f"  impure streams left: {len(a0['impure_streams'])}, total value if they were pure products: ${tot:.0f}M/yr; best single new column raised reward by {a0['best_gain']:+.3f}")
        print(f"  final {r['final_reward']:.3f}: improvement over Opus {r['improvement_vs_opus']:+.3f} reward = ${r['improvement_vs_opus'] * r['norm_usd'] / 1e6:+.0f}M/yr ({r['solves_used']} solves)")


if __name__ == "__main__":
    main()
