"""
Re-simulate every plant on swarm-study team boards (free: ChemSep only, no model calls) and describe each plant at two levels of abstraction:

  product slate   what the plant sells: a set of labels such as "premium:N-hexane", "pure:Propane", "blend:C4 mix"
  structure       what each column separates: a set of labels "<lightest>..<heaviest> | <light key>/<heavy key>" (+ "+side" / "+2fx" for a side
                  draw or a double effect), where the components counted are those with at least 1% of the column's feed, the light key is the
                  heaviest component sent at least 50% overhead and the heavy key the next counted component (normal boiling point order)

    python scripts/plant_fingerprints.py runs/frameworks/screen-dev002 --task hc16v3_dev_002

Writes <campaign>/fingerprints.jsonl: one line per board record (condition, record id, agent, round, solves, reward, valid, copied, slate,
structure). The re-simulated reward is checked against the board's reward.
"""
import argparse
import glob
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign.service import make_env, make_service  # noqa: E402
from sepdesign.taskset import find_task  # noqa: E402

SHORT = {"Ethane": "C2", "Propylene": "C3=", "Propane": "C3", "Isobutane": "iC4", "N-butane": "nC4", "Isopentane": "iC5", "N-pentane": "nC5",
         "2,2-dimethylbutane": "22DMB", "2-methylpentane": "2MP", "3-methylpentane": "3MP", "N-hexane": "nC6", "Methylcyclopentane": "MCP",
         "Cyclohexane": "CH", "N-heptane": "nC7", "N-octane": "nC8", "N-nonane": "nC9"}


def to_spec(s):
    s = list(s)
    if len(s) > 4 and s[4] is not None:
        s[4] = (int(s[4][0]), s[4][1], float(s[4][2]))
    if len(s) > 5:
        s[5] = tuple(s[5])
    return tuple(s)


def column_label(feed, tops, names, spec):
    feed, tops = np.asarray(feed, float), np.asarray(tops, float)
    sig = [i for i in range(len(feed)) if feed[i] >= 0.01 * feed.sum()]
    if not sig:
        return "empty"
    rec = {i: tops[i] / feed[i] for i in sig}
    up = [i for i in sig if rec[i] >= 0.5]
    lk = max(up) if up else None
    later = [i for i in sig if lk is not None and i > lk]
    hk = min(later) if later else None
    cut = f"{SHORT[names[lk]] if lk is not None else '-'}/{SHORT[names[hk]] if hk is not None else '-'}"
    lab = f"{SHORT[names[sig[0]]]}..{SHORT[names[sig[-1]]]} | {cut}"
    if len(spec) > 4 and spec[4] is not None:
        lab += " +side"
    if len(spec) > 5:
        lab += " +2fx"
    return lab


def analyse(args):
    cond_dir, task_id = args
    code = os.path.basename(cond_dir)
    task = find_task(task_id)
    svc = make_service("chemsep", task=task)
    env = make_env(task, svc, budget=10 ** 7)
    names = task["components"]
    out, seen = [], {}
    for line in open(os.path.join(cond_dir, "board.jsonl")):
        r = json.loads(line)
        key = json.dumps(r["design"], sort_keys=True)
        if key not in seen:
            env.design = {p: to_spec(s) for p, s in r["design"].items()}
            res = env.evaluate()
            slate = sorted({(f"premium:{names[int(np.argmax(s['flows']))]}" if s["kind"] == "premium" else
                             f"blend:{s['kind'].split(':', 1)[-1].strip()}" if str(s["kind"]).startswith("blend") else
                             f"pure:{names[int(np.argmax(s['flows']))]}") for s in res["sold"] if s["value"] > 0})
            struct = sorted(column_label(n["feed"], n["tops"], names, n["spec"]) for p, n in res["nodes"].items() if n.get("status") == "ok")
            seen[key] = (slate, struct, float(res["reward"]), bool(res["valid"]))
        slate, struct, rw, valid = seen[key]
        out.append(dict(condition=code, id=r["id"], agent=r["agent"], team=r.get("team"), round=r["round"], solves=r.get("solves"),
                        reward=r["reward"], valid=r["valid"], resim_reward=rw, copied=r.get("copied"), columns=r["columns"],
                        slate=slate, structure=struct))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign")
    ap.add_argument("--task", default="hc16v3_dev_002")
    ap.add_argument("--conditions", nargs="*", default=None)
    a = ap.parse_args()
    dirs = sorted(d for d in glob.glob(os.path.join(a.campaign, "*")) if os.path.exists(os.path.join(d, "board.jsonl")))
    if a.conditions:
        dirs = [d for d in dirs if os.path.basename(d) in a.conditions]
    with ProcessPoolExecutor(len(dirs)) as ex:
        allrows = [row for rows in ex.map(analyse, [(d, a.task) for d in dirs]) for row in rows]
    with open(os.path.join(a.campaign, "fingerprints.jsonl"), "w") as f:
        for r in allrows:
            f.write(json.dumps(r) + "\n")
    bad = [r for r in allrows if r["valid"] and abs(r["reward"] - r["resim_reward"]) > 1e-3]
    print(len(allrows), "records;", len(bad), "whose re-simulated reward differs from the board by more than 0.001")


if __name__ == "__main__":
    main()
