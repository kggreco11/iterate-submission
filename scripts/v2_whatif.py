"""
What-if analysis for task V2 on existing designs (needs the simulator, no API calls).

For each finished design it reports:
  COST  how plant cost splits into energy (variable) and capital (fixed, annualised); and, as energy and capital prices are scaled, how many columns
        stop paying for themselves and how much pruning them would gain.
  PREMIUM  what share of product value comes from streams at >=99% purity (which a premium-grade price would reward) and how pure the products are.
  GROUPS   how many unsold impure streams would qualify as a blended product (C4 mix, C5 mix, C6 mix) and what they would be worth.

    python scripts/v2_whatif.py runs/llm_opus/*.json --out results/opus-5-5-dev-first-look/v2_whatif.json
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign import hc12_tasks  # noqa: E402
from sepdesign.chemsep_backend import ChemSepBackend  # noqa: E402
from sepdesign.cost_model import CostModel, features  # noqa: E402
from sepdesign.env import DesignEnv  # noqa: E402
from sepdesign.families import pr_family  # noqa: E402
from sepdesign.hc12 import HC12  # noqa: E402
from sepdesign.service import SolveService  # noqa: E402
from sepdesign.tasks import Economics  # noqa: E402

SCENARIOS = [("base", 1, 1), ("energy only", 1, 0), ("capital only", 0, 1), ("energy x2", 2, 1), ("capital x2", 1, 2), ("both x2", 2, 2), ("both x3", 3, 3),
             ("both x5", 5, 5), ("both x10", 10, 10), ("both x20", 20, 20)]
GROUPS = {"C4 mix": ["Isobutane", "N-butane"], "C5 mix": ["Isopentane", "N-pentane"],
          "C6 mix": ["2,2-dimethylbutane", "2-methylpentane", "N-hexane", "Methylcyclopentane"]}
GROUP_DISCOUNT = 0.85            # blend sells at 85% of the members' mean price (illustrative)


class ScaledCost(CostModel):
    def __init__(self, me, mc):
        super().__init__()
        self.me, self.mc = me, mc

    def __call__(self, res, case=None):
        f = features(res, self.p)
        pc = float(np.interp(f["Tc"], self.f["cond_knots"], self.f["cond_price_per_GJ"]))
        pr = float(np.interp(f["Tr"], self.f["reb_knots"], self.f["reb_price_per_GJ"]))
        util = self.me * (pc * f["E_c_GJ"] + pr * f["E_r_GJ"])
        cap = self.mc * self.f["capital_scale"] * f["capital"] / self.p["payback"]
        return {"tac": float(util + cap)}


def load_design(run):
    return {p: (int(c["n_stages"]), round(c["reflux"], 2), round(c["reboil"], 2), round(c["dp"], 2)) for p, c in run["trace"][-1]["columns"].items()}


def analyse(path):
    run = json.load(open(path))
    task = next(t for t in hc12_tasks("dev") if t["task_id"] == run["task"])
    econ = Economics(task)
    design = load_design(run)
    fam = pr_family(HC12)
    out = {"task": run["task"], "columns": len(design), "scenarios": {}}
    for name, me, mc in SCENARIOS:
        svc = SolveService(ChemSepBackend(fam, cost_model=ScaledCost(me, mc)))
        env = DesignEnv(econ, svc.column, solve_budget=3000, names=HC12)
        env.design = dict(design)
        base = env.evaluate()
        cur = dict(design)
        cur_r = base
        unprofitable = None
        while True:
            cs = [(p, {q: s for q, s in cur.items() if not q.startswith(p)}) for p in cur]
            if not cs:                                   # every column already pruned
                unprofitable = len(design) if unprofitable is None else unprofitable
                break
            rs = env.evaluate_batch([d for _, d in cs], workers=4)
            gains = [(r["reward"] - cur_r["reward"]) if r["valid"] else -1e18 for r in rs]
            if unprofitable is None:
                unprofitable = int(sum(1 for g in gains if g > 1e-4))
            j = int(np.argmax(gains))
            if gains[j] > 1e-4:
                cur, cur_r = cs[j][1], rs[j]
            else:
                break
        out["scenarios"][name] = {"base_net_usd": base["revenue"] - base["tac"], "revenue_usd": base["revenue"], "cost_usd": base["tac"],
                                  "reward": base["reward"], "columns_not_paying_for_themselves": unprofitable,
                                  "gain_from_pruning_usd": (cur_r["reward"] - base["reward"]) * econ.reward_norm, "columns_after_pruning": len(cur)}
    # premium grade: purity of what is sold (value-weighted), from the final trace snapshot
    prods = [p for p in run["trace"][-1]["products"] if p["value"] > 0]
    tot = sum(p["value"] for p in prods)
    out["premium"] = {"value_share_at_ge_99": sum(p["value"] for p in prods if p["purity"] >= 0.99) / tot,
                      "value_share_at_ge_995": sum(p["value"] for p in prods if p["purity"] >= 0.995) / tot,
                      "purity_quartiles": [float(np.percentile([p["purity"] for p in prods], q)) for q in (0, 25, 50, 75, 100)], "products": len(prods)}
    # groups: unsold impure streams that would qualify as a blended product
    sold_nodes = {p["node"] for p in prods}
    prices = dict(zip(HC12, task["prices_usd_per_mol"]))
    final = svc.cache  # last scenario cache is irrelevant; recompute from the base scenario's result instead
    env = DesignEnv(econ, SolveService(ChemSepBackend(fam, cost_model=ScaledCost(1, 1))).column, solve_budget=3000, names=HC12)
    env.design = dict(design)
    res = env.evaluate()
    qual = []
    for s in res["sold"]:
        if s["value"] > 0:
            continue
        fl = np.asarray(s["flows"], float)
        tot_f = fl.sum()
        if tot_f <= 0 or econ.negligible(fl):
            continue
        for g, members in GROUPS.items():
            idx = [HC12.index(m) for m in members]
            if fl[idx].sum() / tot_f >= 0.95:
                gp = GROUP_DISCOUNT * float(np.mean([prices[m] for m in members]))
                qual.append({"stream": s["node"], "group": g, "flow_mol_s": float(fl[idx].sum()), "value_musd": float(fl[idx].sum() * gp * econ.seconds / 1e6)})
    out["groups"] = {"qualifying_unsold_streams": qual, "total_value_musd": sum(q["value_musd"] for q in qual), "unsold_impure_streams": sum(
        1 for s in res["sold"] if s["value"] <= 0 and not econ.negligible(np.asarray(s["flows"], float)))}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", default="runs/v2_whatif.json")
    a = ap.parse_args()
    paths = [p for p in a.runs if p.endswith(".json")]
    with ProcessPoolExecutor(min(4, len(paths))) as ex:
        results = sorted(ex.map(analyse, paths), key=lambda r: r["task"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(results, open(a.out, "w"), indent=1)
    for r in results:
        s0 = r["scenarios"]["base"]
        print(f"\n{r['task']} ({r['columns']} columns): revenue ${s0['revenue_usd'] / 1e9:.2f}B, cost ${s0['cost_usd'] / 1e6:.0f}M ({100 * s0['cost_usd'] / s0['revenue_usd']:.0f}% of revenue)")
        e, c = r["scenarios"]["energy only"]["cost_usd"], r["scenarios"]["capital only"]["cost_usd"]
        print(f"  cost split: energy ${e / 1e6:.0f}M ({100 * e / (e + c):.0f}%), capital (annualised) ${c / 1e6:.0f}M ({100 * c / (e + c):.0f}%)")
        print("  scenario        net $B/yr   cost $M   columns not paying   gain from pruning $M/yr")
        for name, _, _ in SCENARIOS[3:]:
            s = r["scenarios"][name]
            print(f"  {name:<14} {s['base_net_usd'] / 1e9:8.2f} {s['cost_usd'] / 1e6:9.0f} {s['columns_not_paying_for_themselves']:>12} {s['gain_from_pruning_usd'] / 1e6:>22.0f}")
        p = r["premium"]
        print(f"  premium: {100 * p['value_share_at_ge_99']:.0f}% of product value is at >=99% purity ({100 * p['value_share_at_ge_995']:.0f}% at >=99.5%); purity min/median/max "
              f"{p['purity_quartiles'][0]:.3f}/{p['purity_quartiles'][2]:.3f}/{p['purity_quartiles'][4]:.3f} over {p['products']} products")
        g = r["groups"]
        print(f"  groups: {len(g['qualifying_unsold_streams'])} of {g['unsold_impure_streams']} unsold impure streams would qualify as a blend, worth ${g['total_value_musd']:.0f}M/yr: "
              f"{[(q['group'], round(q['value_musd'])) for q in g['qualifying_unsold_streams']]}")


if __name__ == "__main__":
    main()
