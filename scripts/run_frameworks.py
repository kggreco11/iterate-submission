"""
Run swarm-study conditions (sepdesign/frameworks.py) on one task, each with a fresh simulator service and cache, optionally in parallel.

    python scripts/run_frameworks.py --backend mock --provider scripted --codes C0 C1 F1 F2 F3 F4 F5 F6 F7 --team-budget 60     # free plumbing test
    python scripts/run_frameworks.py --task hc16v3_dev_002 --codes C0 C1 F1 F2 F3 F4 F5 F6 F7 --team-budget 500 --parallel 9    # paid (Kimi on Modal)

Outputs: runs/frameworks/<campaign>/<code>/ (config, summary, board, events, team curve, per-agent usage/turns) and runs/frameworks/<campaign>/campaign.json.
"""
import argparse
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.llm_agent import load_dotenv  # noqa: E402
from sepdesign.frameworks import CONDITIONS, run_condition  # noqa: E402
from sepdesign.service import make_service  # noqa: E402
from sepdesign.taskset import find_task  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="hc16v3_dev_002")
    ap.add_argument("--codes", nargs="+", default=list(CONDITIONS))
    ap.add_argument("--team-budget", type=int, default=500)
    ap.add_argument("--max-rounds", type=int, default=150)
    ap.add_argument("--backend", default="chemsep", choices=["chemsep", "mock"])
    ap.add_argument("--provider", default="modal", choices=["modal", "scripted"])
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    load_dotenv()
    task = find_task(a.task)
    camp = a.out or os.path.join("runs", "frameworks", time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4])
    os.makedirs(camp, exist_ok=True)
    json.dump(vars(a) | {"campaign": camp}, open(os.path.join(camp, "plan.json"), "w"), indent=1)
    print("campaign", camp, "| task", a.task, "| conditions", a.codes, "| team budget", a.team_budget, "| backend", a.backend, "| provider", a.provider, flush=True)

    def one(code):
        svc = make_service(a.backend, task=task)
        return run_condition(code, task, svc, os.path.join(camp, code), team_budget=a.team_budget, max_rounds=a.max_rounds, provider=a.provider,
                             seed=a.seed, log=lambda m: print(m, flush=True))
    with ThreadPoolExecutor(max(1, a.parallel)) as ex:
        results = list(ex.map(one, a.codes))
    rows = []
    for s in results:
        rows.append({k: s[k] for k in ("code", "name", "status", "team_best", "team_solves", "best_at", "team_first_positive_at_team_solves",
                                       "agents_off_zero", "solving_agents", "copies", "usd", "requests", "wall_s")})
    json.dump(rows, open(os.path.join(camp, "campaign.json"), "w"), indent=1)
    print("\ncode | name | status | team best | at 100 / 250 / 500 team solves | team solves | team first positive at | agents off zero | copies | $ | requests | min")
    for r in rows:
        b = r["best_at"]
        print(f"{r['code']} | {r['name']} | {r['status'][:30]} | {r['team_best']:.3f} | {b[100]:.2f} / {b[250]:.2f} / {b[500]:.2f} | {r['team_solves']} | "
              f"{r['team_first_positive_at_team_solves']} | {r['agents_off_zero']}/{r['solving_agents']} | {r['copies']} | {r['usd']:.2f} | {r['requests']} | {r['wall_s'] / 60:.1f}")


if __name__ == "__main__":
    main()
