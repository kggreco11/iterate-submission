"""
How distinct are the plants a team explores, across agents and over time? Reads <campaign>/fingerprints.jsonl (scripts/plant_fingerprints.py).

Distance between two plants = Jaccard distance between their label sets (1 - |A and B| / |A or B|), at two levels: STRUCTURE (what each column
separates) and SLATE (what the plant sells). 0 = the same plant idea, 1 = nothing in common.

Per condition:
  explored        distinct structures / slates evaluated by the whole team
  novelty         share of evaluations whose structure no teammate had evaluated before (the rest re-test an idea the team already had)
  final_distinct  distinct structures among the agents' best plants
  final_spread    mean pairwise structure distance between the agents' best plants
  spread_by_round mean pairwise structure distance between the agents' CURRENT plants after each round (1.0 = all different, 0 = all identical)
  herd_by_round   share of agents whose current structure is the team's most common one
  families        independent lineages alive at the end (an agent that copies a record joins the copied agent's lineage)
Also a 2-D map of every distinct structure (classical multidimensional scaling of the structure distances, all conditions together).

    python scripts/plant_diversity.py runs/frameworks/screen-dev002 --out results/swarm-screen-dev002/diversity.json
"""
import argparse
import itertools
import json
import os
from collections import Counter, defaultdict

import numpy as np


def jac(a, b):
    a, b = set(a), set(b)
    return 0.0 if not a and not b else 1.0 - len(a & b) / len(a | b)


def mean_pairwise(sets):
    pairs = list(itertools.combinations(sets, 2))
    return float(np.mean([jac(x, y) for x, y in pairs])) if pairs else 0.0


def analyse(rows):
    rows = sorted(rows, key=lambda r: (r["round"], r["id"]))
    agents = sorted({r["agent"] for r in rows}, key=lambda a: int(a.split("-")[1]))
    seen, novel = set(), 0
    current, best, family = {}, {}, {a: a for a in agents}
    by_id = {r["id"]: r for r in rows}
    spread, herd, fams = [], [], []
    rounds = sorted({r["round"] for r in rows})
    by_round = defaultdict(list)
    for r in rows:
        by_round[r["round"]].append(r)
    per_agent_struct = defaultdict(set)
    for rd in rounds:
        for r in by_round[rd]:
            key = tuple(r["structure"])
            if key not in seen:
                novel += 1
                seen.add(key)
            per_agent_struct[r["agent"]].add(key)
            if r.get("copied") and r["copied"] in by_id:
                family[r["agent"]] = family[by_id[r["copied"]]["agent"]]
            current[r["agent"]] = r
            if r["valid"] and (r["agent"] not in best or r["reward"] > best[r["agent"]]["reward"]):
                best[r["agent"]] = r
        cur = [tuple(current[a]["structure"]) for a in agents if a in current]
        spread.append(round(mean_pairwise(cur), 4))
        herd.append(round(Counter(cur).most_common(1)[0][1] / len(cur), 4) if cur else 0.0)
        fams.append(len({family[a] for a in agents}))
    finals = [best[a] for a in agents if a in best and best[a]["reward"] > 0]
    team_best = max((r for r in rows if r["valid"]), key=lambda r: r["reward"], default=None)
    return {"agents": len(agents), "records": len(rows), "valid": sum(r["valid"] for r in rows),
            "explored_structures": len({tuple(r["structure"]) for r in rows}), "explored_slates": len({tuple(r["slate"]) for r in rows}),
            "novelty": novel / len(rows), "per_agent_structures": float(np.mean([len(v) for v in per_agent_struct.values()])),
            "copies": sum(1 for r in rows if r.get("copied")),
            "final_distinct": len({tuple(r["structure"]) for r in finals}), "final_slates": len({tuple(r["slate"]) for r in finals}),
            "final_spread": mean_pairwise([r["structure"] for r in finals]), "final_slate_spread": mean_pairwise([r["slate"] for r in finals]),
            "families_end": fams[-1] if fams else None, "rounds": rounds, "spread_by_round": spread, "herd_by_round": herd, "families_by_round": fams,
            "team_best": team_best["reward"] if team_best else 0.0,
            "team_best_structure": team_best["structure"] if team_best else [], "team_best_slate": team_best["slate"] if team_best else [],
            "agent_bests": [{"agent": r["agent"], "reward": r["reward"], "structure": r["structure"], "slate": r["slate"]} for r in finals]}


def mds(keys, dim=2):
    n = len(keys)
    D = np.array([[jac(a, b) for b in keys] for a in keys]) ** 2
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ D @ J
    w, v = np.linalg.eigh(B)
    idx = np.argsort(w)[::-1][:dim]
    return v[:, idx] * np.sqrt(np.maximum(w[idx], 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaign")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(os.path.join(a.campaign, "fingerprints.jsonl"))]
    by_c = defaultdict(list)
    for r in rows:
        by_c[r["condition"]].append(r)
    res = {c: analyse(rs) for c, rs in sorted(by_c.items())}
    keys = sorted({tuple(r["structure"]) for r in rows})
    xy = mds(keys)
    pos = {k: (round(float(x), 4), round(float(y), 4)) for k, (x, y) in zip(keys, xy)}
    points = [{"c": r["condition"], "a": r["agent"], "r": r["round"], "w": round(r["reward"], 3), "v": r["valid"], "xy": pos[tuple(r["structure"])],
               "n": len(r["structure"])} for r in rows]
    out = {"conditions": res, "points": points}
    print("cond | agents | evaluations | distinct structures | novelty | per-agent structures | copies | best plants: distinct / spread | "
          "families at end | herd at end | team best")
    for c, m in res.items():
        print(f"{c} | {m['agents']} | {m['records']} | {m['explored_structures']} | {m['novelty']:.2f} | {m['per_agent_structures']:.1f} | {m['copies']} | "
              f"{m['final_distinct']} / {m['final_spread']:.2f} | {m['families_end']} | {m['herd_by_round'][-1]:.2f} | {m['team_best']:.2f}")
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(out, open(a.out, "w"))


if __name__ == "__main__":
    main()
