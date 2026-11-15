"""
Qualify side draws on the real simulator: random columns with a side draw on the Hydrocarbon-16 V3 dev feeds. Reports the share solved (after the
retry initialisations), how many needed a retry, and the component-balance closure including the side stream. Pass bar: >= 85% solved, closure < 1e-6.

    python scripts/side_draw_qualify.py --per-task 40 --out results/hc16v3-side-draw/qualification.json
"""
import argparse
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign import make_service  # noqa: E402
from sepdesign.taskset import get_tasks  # noqa: E402


def cases(task, k, seed):
    rnd = random.Random(seed)
    out = []
    for _ in range(k):
        n = rnd.randint(40, 120)
        fs = int(round(n / 2))
        stage = rnd.choice([s for s in range(max(2, n // 6), min(n - 1, n - n // 6) + 1) if s != fs])
        out.append({"feed_flows_mol_s": task["feed_flows_mol_s"], "temperature_K": task["temperature_K"], "pressure_Pa": task["pressure_Pa"],
                    "n_stages": n, "reflux_ratio": round(rnd.uniform(2, 15), 2), "reboil_ratio": round(rnd.uniform(2, 15), 2),
                    "pressure_drop_fraction": round(rnd.uniform(0, 0.4), 2),
                    "side_draw": {"stage": stage, "phase": rnd.choice(["liquid", "vapour"]), "fraction": round(rnd.uniform(0.05, 0.4), 3)}})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-task", type=int, default=40)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default="runs/side_draw_qualification.json")
    a = ap.parse_args()
    rows = []
    for t in get_tasks("dev", "hc16v3"):
        svc = make_service("chemsep", task=t)
        cs = cases(t, a.per_task, 2026 + int(t["task_id"][-3:]))
        with ThreadPoolExecutor(a.workers) as ex:
            res = list(ex.map(svc.backend.solve_column, cs))
        for c, r in zip(cs, res):
            row = {"task": t["task_id"], "n": c["n_stages"], "side": c["side_draw"], "ok": bool(r["success"]), "solve_s": r["runtime_s"]}
            if r["success"]:
                row["solved_by"] = r["diagnostics"]["solved_by"]
                row["closure"] = r["diagnostics"]["mass_closure_frac"]
                row["side_share"] = float(np.sum(r["side"]["flows"]) / np.sum(c["feed_flows_mol_s"]))
            rows.append(row)
        ok = [r for r in rows if r["task"] == t["task_id"] and r["ok"]]
        print(t["task_id"], f"{len(ok)}/{a.per_task} solved")
    ok = [r for r in rows if r["ok"]]
    summ = {"columns": len(rows), "solved": len(ok), "solved_share": len(ok) / len(rows), "needed_retry": sum(1 for r in ok if r["solved_by"] != "stock"),
            "max_closure": max(r["closure"] for r in ok), "median_solve_s": float(np.median([r["solve_s"] for r in rows])),
            "max_side_share_error": max(abs(r["side_share"] - r["side"]["fraction"]) for r in ok)}
    print(summ)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump({"summary": summ, "rows": rows}, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
