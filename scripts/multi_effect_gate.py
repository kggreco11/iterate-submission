"""
Gate test for multi-effect (double-effect) columns, on finished plants (needs the simulator, no API calls).

A double-effect column replaces one column by two that do the same split: the feed is divided, a fraction f goes to a HIGH-pressure column and the rest
to a LOW-pressure column (the pressure can only be dropped, by each column's valve). The high-pressure column condenses hotter, so its condenser can
boil the low-pressure column's reboiler if Tc(HP) - Tr(LP) >= 10 K: that heat is bought once and used twice. The price is a second shell.

For every column of each plant this script tries the pair on the column's own feed and settings (same stages, reflux and boil-up), over a grid of
feed fractions and the two pressure drops, and keeps the best pair whose products match the single column's (every component holding at least 1%
of the feed goes overhead in the same proportion within 2 percentage points, so the plant downstream is essentially unchanged). It reports the
saving of the best pair, and then re-prices every candidate under other energy and capital multipliers (the cost model's energy and capital parts
scale linearly), so the cost levels can be tuned until the pair pays on some columns and not on others.

    python scripts/multi_effect_gate.py runs/v2_opus/*.json --out results/hc16v3-multi-effect/gate.json
"""
import argparse
import glob
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign import make_env, make_service  # noqa: E402
from sepdesign.cost_model import HOURS, MS, M2_TO_FT2, CostModel  # noqa: E402
from sepdesign.env import Stream  # noqa: E402
from sepdesign.taskset import find_task  # noqa: E402
from sepdesign.tasks import cost_config  # noqa: E402

DT_MIN = 10.0
U_HX = 850.0
FRACTIONS = (0.4, 0.5, 0.6)
DP_STEPS = (0.15, 0.3, 0.45, 0.6)
MAX_SPLIT_DEV = 0.02
GRID_EM = (2, 4, 6, 10)
GRID_CM = (5, 10, 20, 40)


def link_value(hp, lp, em, cm, f):
    """(utility saving $/yr at energy multiplier em, link exchanger annual capital at capital multiplier cm, heat MW, dT) for HP condenser -> LP reboiler."""
    ch, cl = hp["cost"], lp["cost"]
    dT = ch["Tc"] - cl["Tr"]
    if dT < DT_MIN:
        return 0.0, 0.0, 0.0, dT
    q = min(abs(hp["qc"]), abs(lp["qr"]))
    gj = q * HOURS * 3600.0 / 1e9
    saving = em * (ch["price_cond"] + cl["price_reb"]) * gj
    area = q / (U_HX * dT)
    hx = cm * f["capital_scale"] * MS * 101.3 * (area * M2_TO_FT2) ** 0.65 * (2.29 + 1.0) / 3.0
    return saving, hx, q / 1e6, dT


def analyse(path, workers=4):
    run = json.load(open(path))
    task = find_task(run["task"])
    em0, cm0 = cost_config(task)
    fitted = CostModel().f
    svc = make_service("chemsep", task=task)
    env = make_env(task, svc, budget=10 ** 6)
    design = {p: (int(c["n_stages"]), round(c["reflux"], 2), round(c["reboil"], 2), round(c["dp"], 2)) for p, c in run["trace"][-1]["columns"].items()}
    env.design = dict(design)
    base = env.evaluate()
    norm = env.econ.reward_norm
    jobs, meta, sjobs, smeta = [], [], [], []
    for p, spec in design.items():
        node = base["nodes"].get(p)
        if not node or node.get("status") != "ok" or not node["column_result"].get("cost"):
            continue
        feed = np.asarray(node["feed"], float)
        n, rr, rb, dp = spec
        dps = {dp, 0.0} | {round(x + s_, 2) for x in (dp, 0.0) for s_ in DP_STEPS if x + s_ <= 0.9}
        for d in sorted(dps):                        # the single column at every pressure a pair uses (fair comparison)
            smeta.append((p, d))
            sjobs.append((Stream(feed, node["T"], node["P"]), (n, rr, rb, d)))
        for fr in FRACTIONS:
            for dph in sorted({dp, 0.0}):
                dpls = [round(dph + s, 2) for s in DP_STEPS if dph + s <= 0.9]
                for dpl in dpls:
                    meta.append((p, fr, dph, dpl))
                    jobs.append(((Stream(feed * fr, node["T"], node["P"]), (n, rr, rb, dph)), (Stream(feed * (1 - fr), node["T"], node["P"]), (n, rr, rb, dpl))))
    flat = [j for pair in jobs for j in pair]
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(lambda a: svc.column(*a), flat))
        sres = list(ex.map(lambda a: svc.column(*a), sjobs))
    cols = {}
    for k, (p, fr, dph, dpl) in enumerate(meta):
        hp, lp = res[2 * k], res[2 * k + 1]
        node = base["nodes"][p]
        single = node["column_result"]
        feed = np.asarray(node["feed"], float)
        c = cols.setdefault(p, {"path": p or "feed", "span_K": single["cost"]["Tr"] - single["cost"]["Tc"], "Tc": single["cost"]["Tc"], "Tr": single["cost"]["Tr"],
                                "single": {"util": single["cost"]["utilities"], "cap": single["cost"]["capital_annual"], "tac": single["tac"],
                                           "Qr_MW": abs(single["qr"]) / 1e6}, "candidates": []})
        if not (hp["ok"] and lp["ok"] and hp.get("cost") and lp.get("cost")):
            c["candidates"].append({"f": fr, "dp_hp": dph, "dp_lp": dpl, "ok": False})
            continue
        top_s = np.asarray(single["tops"]["flows"], float)
        top_p = np.asarray(hp["tops"]["flows"], float) + np.asarray(lp["tops"]["flows"], float)
        big = feed >= 0.01 * feed.sum()
        dev = float(np.max(np.abs(top_p[big] / feed[big] - top_s[big] / feed[big]))) if big.any() else 0.0
        saving, hx, mw, dT = link_value(hp, lp, em0, cm0, fitted)
        c["candidates"].append({"f": fr, "dp_hp": dph, "dp_lp": dpl, "ok": True, "split_dev": dev, "dT": dT, "link_MW": mw,
                                "util": hp["cost"]["utilities"] + lp["cost"]["utilities"], "cap": hp["cost"]["capital_annual"] + lp["cost"]["capital_annual"],
                                "saving": saving, "hx": hx})
    for (p, d), r in zip(smeta, sres):
        if p not in cols or not (r["ok"] and r.get("cost")):
            continue
        node = base["nodes"][p]
        feed = np.asarray(node["feed"], float)
        single = node["column_result"]
        big = feed >= 0.01 * feed.sum()
        dev = float(np.max(np.abs(np.asarray(r["tops"]["flows"])[big] / feed[big] - np.asarray(single["tops"]["flows"])[big] / feed[big]))) if big.any() else 0.0
        cols[p].setdefault("singles", []).append({"dp": d, "split_dev": dev, "util": r["cost"]["utilities"], "cap": r["cost"]["capital_annual"]})
    return {"task": run["task"], "norm": norm, "em0": em0, "cm0": cm0, "opus_reward": base["reward"], "columns": list(cols.values())}


def best_single(col, em, cm, em0, cm0):
    """Cheapest single column (any of the tried pressures, Opus's own included) whose split matches Opus's column."""
    s = col["single"]
    best = s["util"] * em / em0 + s["cap"] * cm / cm0
    for c in col.get("singles", []):
        if c["split_dev"] <= MAX_SPLIT_DEV:
            best = min(best, c["util"] * em / em0 + c["cap"] * cm / cm0)
    return best


def best_pair(col, em, cm, em0, cm0):
    """Best net saving ($/yr) of a pair over the single column at multipliers (em, cm), among candidates matching the single column's split."""
    single = best_single(col, em, cm, em0, cm0)
    best = None
    for c in col["candidates"]:
        if not c.get("ok") or c["split_dev"] > MAX_SPLIT_DEV:
            continue
        pair = (c["util"] - c["saving"]) * em / em0 + (c["cap"] + c["hx"]) * cm / cm0
        net = single - pair
        if best is None or net > best[0]:
            best = (net, c)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="runs/multi_effect_gate.json")
    a = ap.parse_args()
    paths = sorted(p for x in a.runs for p in glob.glob(x) if p.endswith(".json"))
    plants = [analyse(p, a.workers) for p in paths]
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(plants, open(a.out, "w"), indent=1)
    for pl in plants:
        em0, cm0 = pl["em0"], pl["cm0"]
        print(f"\n{pl['task']}: Opus {pl['opus_reward']:.3f}, reward normaliser ${pl['norm'] / 1e6:.0f}M/yr  (current cost level: energy x{em0:g}, capital x{cm0:g})")
        print("  column | Tc-Tr span K | reboiler MW | feasible pairs (heat flows, split kept) | best net saving $M/yr | best pair")
        tot = 0.0
        for col in sorted(pl["columns"], key=lambda c: c["span_K"]):
            okc = [c for c in col["candidates"] if c.get("ok") and c["split_dev"] <= MAX_SPLIT_DEV and c["link_MW"] > 0]
            b = best_pair(col, em0, cm0, em0, cm0)
            net = b[0] if b else float("nan")
            if b and net > 0:
                tot += net
            desc = f"f={b[1]['f']}, dp {b[1]['dp_hp']}/{b[1]['dp_lp']}, dT {b[1]['dT']:.0f} K, link {b[1]['link_MW']:.0f} MW" if b else "-"
            print(f"  {col['path']:<6} | {col['span_K']:5.0f} | {col['single']['Qr_MW']:5.0f} | {len(okc):2d} | {net / 1e6:+7.1f} | {desc}")
        print("  (net saving = best single column at any tried pressure minus the best pair: pressure re-tuning alone is not credited)")
        print(f"  total over columns where the pair pays: ${tot / 1e6:.0f}M/yr = {tot / pl['norm']:+.3f} reward ({100 * tot / pl['norm'] / pl['opus_reward']:.1f}% of Opus)")
    print("\nShare of columns (all plants) where the best pair beats the best single column (any tried pressure) by more than 1% of its cost, by cost level:")
    print("energy x \\ capital x | " + " | ".join(f"x{c}" for c in GRID_CM))
    for em in GRID_EM:
        row = []
        for cm in GRID_CM:
            yes = tot_c = 0
            for pl in plants:
                for col in pl["columns"]:
                    tot_c += 1
                    b = best_pair(col, em, cm, pl["em0"], pl["cm0"])
                    single = best_single(col, em, cm, pl["em0"], pl["cm0"])
                    yes += bool(b and b[0] > 0.01 * single)
            row.append(f"{yes}/{tot_c}")
        print(f"x{em} | " + " | ".join(row))


if __name__ == "__main__":
    main()
