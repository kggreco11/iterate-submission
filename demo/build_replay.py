"""
Build demo/plant_replay.html from run files that contain a "trace" (scripts/run_baselines.py, or any agent run saved with sepdesign.save_run).

    python demo/build_replay.py runs/hc12_dev_000_random_then_greedy_s0_b400.json runs/hc12_dev_000_first_cut_greedy_s0_b400.json
Each run is one entry in the page's drop-down; runs on the same task are drawn together on the score curve.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main(paths):
    runs = []
    for p in paths:
        d = json.load(open(p))
        if not d.get("trace"):
            print("skip (no trace):", p)
            continue
        runs.append({"label": d.get("label") or os.path.basename(p), "task": d["task"], "components": d["components"],
                     "upper_bound": d["upper_bound_reward"], "trace": d["trace"]})
    html = open(os.path.join(HERE, "plant_replay_template.html"), encoding="utf-8").read().replace("/*DATA*/[]", json.dumps(runs))
    out = os.path.join(HERE, "plant_replay.html")
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out}: {len(runs)} run(s), {sum(len(r['trace']) for r in runs)} snapshots")


if __name__ == "__main__":
    main(sys.argv[1:])
