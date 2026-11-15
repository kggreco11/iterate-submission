"""
Summarize team runs (sepdesign/teams.py): score, budget, cost, diversity, how ideas moved, and what agents wrote in their notebooks.

    python scripts/summarize_teams.py runs/teams/final-10 runs/teams/final-50 runs/teams/final-solo --out results/final-dev002

Writes <out>/summary.md and <out>/summary.json, and copies each run's summary, config, board, team curve and per-agent notebooks/turns
(prompts and reasoning stay in runs/ because of size).
Diversity: a plant's structure is the set of separations its columns make; families are lineages joined by copying (grafting does not change
family). "Herd" = share of agents whose latest plant has the team's most common structure.
"""
import argparse
import glob
import json
import os
import re
import shutil
from collections import Counter

import numpy as np
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REF = {"Kimi K3.1 Pro solo, 200 solves (V3 dev_002)": 2.13, "Opus 5.5 solo (V3 dev_002)": 5.13, "best known plant (V3 dev_002)": 5.57}


def jac(a, b):
    a, b = set(a), set(b)
    return 0.0 if not a and not b else 1 - len(a & b) / len(a | b)


def analyse_live(d):
    """For a run stopped before it finished: rebuild what the live logs allow (round events, replies, costs, prompts)."""
    cfg = json.load(open(os.path.join(d, "config.json")))
    E = [json.loads(l) for l in open(os.path.join(d, "events.jsonl")) if '"kind": "round"' in l]
    last = E[-1] if E else {"round": 0, "team_best": 0, "team_solves": 0, "usd_real": 0, "usd_logged": 0, "t": 0}
    curve_path = os.path.join(d, "team_curve.json")
    curve = json.load(open(curve_path)) if os.path.exists(curve_path) else []
    at = lambda n: (max([e[1] for e in curve if e[0] <= n] or [0.0]) if curve and n <= last["team_solves"] else None)  # noqa: E731
    copies = grafts = nb_total = nb_refs = req = 0
    off = 0
    agents = sorted(glob.glob(os.path.join(d, "agents", "*")))
    for ag in agents:
        if os.path.exists(os.path.join(ag, "reasoning.jsonl")):
            for l in open(os.path.join(ag, "reasoning.jsonl")):
                rep = json.loads(l).get("reply")
                if rep and isinstance(rep, list) and len(rep) == 2 and isinstance(rep[1], dict):
                    a_ = rep[1]
                    copies += bool(a_.get("copy_from"))
                    grafts += bool(a_.get("graft"))
                    if a_.get("notebook"):
                        nb_total += 1
                        nb_refs += bool(re.search(r"\bR\d+\b|agent-\d|island|teammate|other plant", a_["notebook"], re.I))
        if os.path.exists(os.path.join(ag, "usage.jsonl")):
            req += sum(1 for _ in open(os.path.join(ag, "usage.jsonl")))
        if os.path.exists(os.path.join(ag, "prompts.jsonl")):
            bests = [float(m) for l in open(os.path.join(ag, "prompts.jsonl")) for m in re.findall(r"Best valid reward so far: (-?[\d.]+)", json.loads(l)["user"])]
            off += bool(bests and max(bests) > 0)
    n = sum(cfg.get("islands") or [1])
    return {"run": os.path.basename(d), "preset": cfg["config"]["preset"], "agents": n, "status": f"stopped early at round {last['round']}",
            "team_best": last["team_best"], "best_at": {k: at(int(k)) for k in ("100", "250", "500", "1000")}, "team_solves": last["team_solves"],
            "agents_off_zero": off, "best_columns": None, "copies": copies, "grafts": grafts, "learned_without_copying": None, "evaluations": None,
            "distinct_structures": None, "novelty": None, "final_distinct": None, "families_end": None, "herd_end": None,
            "notebook_entries": nb_total, "notebook_refs_to_others": nb_refs, "usd_real_estimate": last.get("usd_real", 0), "usd_logged": last.get("usd_logged"),
            "requests": req, "wall_min": last["t"] / 60}


def analyse(d):
    if not os.path.exists(os.path.join(d, "summary.json")):
        return analyse_live(d)
    s = json.load(open(os.path.join(d, "summary.json")))
    B = [json.loads(l) for l in open(os.path.join(d, "board.jsonl"))] if os.path.exists(os.path.join(d, "board.jsonl")) else []
    seen, novel = set(), 0
    for r in B:
        k = tuple(r.get("structure", []))
        novel += k not in seen
        seen.add(k)
    latest, best = {}, {}
    for r in B:
        latest[r["agent"]] = r
        if r["valid"] and r["reward"] > 0 and (r["agent"] not in best or r["reward"] > best[r["agent"]]["reward"]):
            best[r["agent"]] = r
    fin = [tuple(r["structure"]) for r in best.values()]
    cur = [tuple(r["structure"]) for r in latest.values()]
    herd = Counter(cur).most_common(1)[0][1] / len(cur) if cur else 0
    fams = len({r["family"] for r in latest.values()}) if latest else 0
    nb_refs = nb_total = 0
    for f in glob.glob(os.path.join(d, "agents", "*", "turns.jsonl")):
        for l in open(f):
            t = json.loads(l)
            if t.get("notebook"):
                nb_total += 1
                nb_refs += bool(re.search(r"\bR\d+\b|agent-\d|island|teammate|other plant", t["notebook"], re.I))
    shown = [r for r in B if r.get("shown")]
    learned = 0                                  # changed structure toward a shown plant without copying or grafting
    for r in shown:
        if r.get("copied") or r.get("graft"):
            continue
        others = [x for x in B if x["id"] in r["shown"]]
        prev = [x for x in B if x["agent"] == r["agent"] and int(x["id"][1:]) < int(r["id"][1:])]
        if others and prev:
            before = min(jac(prev[-1]["structure"], o["structure"]) for o in others)
            after = min(jac(r["structure"], o["structure"]) for o in others)
            learned += after < before - 1e-9
    spend = s.get("usd_cached_price_estimate", 0.0)
    return {"run": os.path.basename(d), "preset": s["preset"], "agents": s["workers"], "status": s["status"], "team_best": s["team_best"],
            "best_at": {k: v if int(k) <= s["team_solves"] else None for k, v in s["best_at"].items()}, "team_solves": s["team_solves"], "agents_off_zero": s["agents_off_zero"], "best_columns": s["best_columns"],
            "copies": s["copies"], "grafts": s["grafts"], "learned_without_copying": learned, "evaluations": len(B),
            "distinct_structures": len(seen), "novelty": novel / max(len(B), 1), "final_distinct": len(set(fin)),
            "families_end": fams, "herd_end": herd, "notebook_entries": nb_total, "notebook_refs_to_others": nb_refs,
            "usd_real_estimate": spend, "usd_logged": s.get("usd_logged"), "requests": s["requests"], "wall_min": s["wall_s"] / 60}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("campaigns", nargs="+")
    ap.add_argument("--out", default="results/final-dev002")
    a = ap.parse_args()
    dirs = sorted(d for c in a.campaigns for d in glob.glob(os.path.join(c, "*", "*")) if os.path.exists(os.path.join(d, "config.json")))
    rows = []
    from sepdesign.team_report import payload, publish_team
    for d in dirs:
        data = payload(d)
        row = analyse(d)
        row.update(model=data['config']['model'], run_id=data['config']['run_id'])
        rows.append(row)
        publish_team(data)
    rows.sort(key=lambda r: -r["team_best"])
    os.makedirs(a.out, exist_ok=True)
    for d in dirs:
        cfg = json.load(open(os.path.join(d, "config.json")))
        from sepdesign.report_archive import segment
        dst = os.path.join(a.out, segment(cfg['model']), segment(cfg['run_id']))
        os.makedirs(dst, exist_ok=True)
        for f in ("summary.json", "config.json", "board.jsonl", "team_curve.json", "events.jsonl"):
            if os.path.exists(os.path.join(d, f)):
                shutil.copy(os.path.join(d, f), dst)
        for ag in glob.glob(os.path.join(d, "agents", "*")):
            os.makedirs(os.path.join(dst, "agents", os.path.basename(ag)), exist_ok=True)
            for f in ("turns.jsonl", "summary.json", "usage.jsonl"):
                if os.path.exists(os.path.join(ag, f)):
                    shutil.copy(os.path.join(ag, f), os.path.join(dst, "agents", os.path.basename(ag)))
    json.dump(rows, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
    lines = ["| run | model | status | agents | team best | best at 100 / 250 / 500 / 1000 team solves | team solves | agents off zero | best plant columns | copies | grafts | moved toward a seen plant without copying | distinct plant structures | new to team | distinct final plants | families at end | herd at end | notebook entries citing others | $ (cached-price estimate) | minutes |",
             "|" + "---|" * 20]
    for r in rows:
        b = {k: ("-" if v is None else f"{float(v):.2f}") for k, v in r["best_at"].items()}
        f = lambda v, fmt="{}": "-" if v is None else fmt.format(v)  # noqa: E731
        lines.append(f"| {r['run']} | {r['model']} | {r['status']} | {r['agents']} | **{r['team_best']:.2f}** | {b['100']} / {b['250']} / {b['500']} / {b['1000']} | {r['team_solves']} | "
                     f"{r['agents_off_zero']}/{r['agents']} | {f(r['best_columns'])} | {r['copies']} | {r['grafts']} | {f(r['learned_without_copying'])} | "
                     f"{f(r['distinct_structures'])} | {f(None if r['novelty'] is None else 100 * r['novelty'], '{:.0f}%')} | {f(r['final_distinct'])} | {f(r['families_end'])} | "
                     f"{f(None if r['herd_end'] is None else 100 * r['herd_end'], '{:.0f}%')} | {r['notebook_refs_to_others']}/{r['notebook_entries']} | "
                     f"{r['usd_real_estimate']:.2f} | {r['wall_min']:.0f} |")
    lines.append("")
    lines.append("References on the same task: " + "; ".join(f"{k} {v}" for k, v in REF.items()) + ".")
    open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
