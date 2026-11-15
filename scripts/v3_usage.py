"""
How did an agent use the V3 options? Reads language-model run folders (turns.jsonl) and run files (best design).

    python scripts/v3_usage.py runs/v3_opus

Per run: best valid reward and share of ceiling, solves and turns used, how many turns tried a side draw or a double effect, how many of those
evaluations were valid, and how many side draws / double effects (with heat passed) are in the best plant, plus the plant's revenue and cost.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign.taskset import find_task  # noqa: E402
from sepdesign.tasks import Economics  # noqa: E402


def main(d):
    print("task | best (share of ceiling) | solves | turns | turns trying side draw / double effect | in best plant: side draws / double effects "
          "(heat MW) | columns | revenue $B | cost $M (% of revenue) | stopped | $")
    for run_dir in sorted(glob.glob(os.path.join(d, "*/"))):
        rid = os.path.basename(run_dir.rstrip("/\\"))
        turns = [json.loads(l) for l in open(os.path.join(run_dir, "turns.jsonl"))] if os.path.exists(os.path.join(run_dir, "turns.jsonl")) else []
        sd = sum(1 for t in turns if any("side_draw" in e and e["side_draw"] for e in t.get("edits") or []))
        de = sum(1 for t in turns if any("double_effect" in e and e["double_effect"] for e in t.get("edits") or []))
        summ = json.load(open(os.path.join(run_dir, "summary.json"))) if os.path.exists(os.path.join(run_dir, "summary.json")) else {}
        rf = os.path.join(d, rid + ".json")
        task = find_task("_".join(rid.split("_")[:3]))
        ceil = Economics(task).upper_bound_reward
        if os.path.exists(rf):
            r = json.load(open(rf))
            s = r["trace"][-1] if r.get("trace") else None
            best = r["best_reward"] or 0.0
        else:
            s, best = None, max([t["reward"] for t in turns if t.get("valid")] or [0.0])
        if s:
            cols = s["columns"]
            nsd = sum(1 for c in cols.values() if "side" in c)
            des = [c["double_effect"] for c in cols.values() if "double_effect" in c]
            heat = ", ".join("%.0f" % x["heat_MW"] for x in des) or "-"
            plant = f"{nsd} / {len(des)} ({heat}) |{len(cols)} | {s['revenue'] / 1e9:.2f} | {s['tac'] / 1e6:.0f} ({100 * s['tac'] / s['revenue']:.0f}%)"
        else:
            plant = "- | - | - | -"
        print(f"{task['task_id']} | {best:.2f} ({100 * best / ceil:.0f}%) | {summ.get('solves_used', max([t.get('solves_used', 0) for t in turns] or [0]))} | {len(turns)} | "
              f"{sd} / {de} | {plant} | {summ.get('status', 'running')} | {summ.get('usd_estimated_total', float('nan')):.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "runs/v3_opus")
