"""
Is the best reward still rising? Reads the turn logs of language-model agent runs (works on runs still in progress).

    python scripts/curve_check.py runs/v2_opus --upto 200

For each run: best valid reward at 25, 50, 100, 150, 200 solves, the gain over the last 50 and 100 solves, how many solves since the last improvement,
and the share of the ceiling reached. "Rising" means the best improved by at least 3% over the last 50 solves. The best is floored at 0 (the empty design).
Only turns up to --upto solves are used, so a run that went further is read at that checkpoint.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign.taskset import find_task  # noqa: E402
from sepdesign.tasks import Economics  # noqa: E402

POINTS = (25, 50, 100, 150, 200)


def curve(turns, upto=None):
    """[(solves_used, best valid reward so far)] after each evaluated turn, floored at 0."""
    best, out = 0.0, []
    for t in turns:
        if t.get("action") != "edit":
            continue
        if upto is not None and t["solves_used"] > upto:
            break
        if t.get("valid") and t["reward"] > best:
            best = t["reward"]
        out.append((t["solves_used"], best))
    return out


def best_at(c, s):
    b = 0.0
    for used, best in c:
        if used <= s:
            b = best
    return b


def analyse(run_dir, upto):
    tp = os.path.join(run_dir, "turns.jsonl")
    turns = [json.loads(l) for l in open(tp)] if os.path.exists(tp) else []
    task_id = "_".join(os.path.basename(run_dir.rstrip("/\\")).split("_")[:3])
    ceiling = Economics(find_task(task_id)).upper_bound_reward
    c = curve(turns, upto)
    if not c:
        return {"task": task_id, "solves": 0}
    S = c[-1][0]
    cur = c[-1][1]
    last_imp = max((used for i, (used, b) in enumerate(c) if i == 0 or b > c[i - 1][1]), default=0)
    g50 = cur - best_at(c, S - 50)
    g100 = cur - best_at(c, S - 100)
    return {"task": task_id, "solves": S, "turns": len(turns), "best": cur, "ceiling": ceiling, "share": cur / ceiling,
            "at": {p: best_at(c, p) for p in POINTS if p <= S}, "gain_last50": g50, "gain_last100": g100, "since_improvement": S - last_imp,
            "rising": g50 >= 0.03 * max(cur, 1e-9)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--upto", type=int, default=None, help="read each run only up to this many solves")
    a = ap.parse_args()
    rows = [analyse(d, a.upto) for d in sorted(glob.glob(os.path.join(a.dir, "*/")))]
    print("task | solves | best (share of ceiling) | best at " + " / ".join(map(str, POINTS)) + " | gain last 50 | gain last 100 | solves since last improvement | verdict")
    for r in rows:
        if not r["solves"]:
            print(r["task"], "| no evaluated turns yet")
            continue
        at = " / ".join(f"{r['at'][p]:.2f}" if p in r["at"] else "-" for p in POINTS)
        print(f"{r['task']} | {r['solves']} | {r['best']:.2f} ({100 * r['share']:.0f}%) | {at} | {r['gain_last50']:+.2f} | {r['gain_last100']:+.2f} | "
              f"{r['since_improvement']} | {'still rising' if r['rising'] else 'flattening'}")


if __name__ == "__main__":
    main()
