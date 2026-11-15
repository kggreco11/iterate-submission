"""
Run agent-team presets (sepdesign/teams.py) on one task, each with a fresh simulator service and cache, optionally in parallel and for several models.

    python scripts/run_teams.py --backend mock --provider scripted --presets solo independent open ring-5x2-k10 --budget 20     # free plumbing test
    python scripts/run_teams.py --task hc16v3_dev_002 --presets solo --model deepseek-v4.1-flash --budget 100                  # one cheap model check
    python scripts/run_teams.py --task hc16v3_dev_002 --presets open ring-5x2-k10 cull --model kimi-k3.1-pro --parallel 3

Outputs: runs/teams/<campaign>/<model>/<preset>/ (config, summary, board with full plant views, events, team curve, per-agent prompts, reasoning,
turns with notebooks, usage) and runs/teams/<campaign>/campaign.json.
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
from sepdesign.service import make_service  # noqa: E402
from sepdesign.taskset import find_task  # noqa: E402
from sepdesign.teams import PRESETS, config, finish_fraction, run_team  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="hc16v3_dev_002")
    ap.add_argument("--presets", nargs="+", default=["solo"])
    ap.add_argument("--models", nargs="+", default=["kimi-k3.1-pro"])
    ap.add_argument("--budget", type=int, default=None, help="solves per agent (default: the preset's)")
    ap.add_argument("--agents", type=int, default=None, help="team size (scales presets with one island or all-singleton islands)")
    ap.add_argument("--islands", default=None, help="island sizes, e.g. 3x10 (10 islands of 3) or 4,4,2")
    ap.add_argument("--efforts", nargs="+", default=["low"], help="reasoning effort(s) of the model, e.g. low high xhigh")
    ap.add_argument("--seeds", nargs="+", type=int, default=None, help="repeat each job with these seeds")
    ap.add_argument("--plan", action="store_true", help="require a short written plan with every edit")
    ap.add_argument("--min-finish", type=finish_fraction, default=None, help="refuse finish until this fraction (0 to 1) of the agent's budget is used, e.g. 0.8")
    ap.add_argument("--unsold-info", action="store_true", help="show each unsold stream's distance from a sellable spec and its value if sold")
    ap.add_argument("--think-budget", type=int, default=None, help="cap thinking at N tokens per turn (think step, then an act step with no thinking)")
    ap.add_argument("--think-every", type=int, default=None, help="think (at --efforts) only every Nth turn; other turns use no thinking")
    ap.add_argument("--think-when-stuck", type=int, default=None, help="also think when the agent has not improved for N turns")
    ap.add_argument("--tag", default="", help="suffix for the run folder")
    ap.add_argument("--max-rounds", type=int, default=250)
    ap.add_argument("--backend", default="chemsep", choices=["chemsep", "mock"])
    ap.add_argument("--provider", default="modal", choices=["modal", "anthropic", "scripted"])
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    load_dotenv()
    unknown = [p for p in a.presets if p not in PRESETS]
    if unknown:
        ap.error(f"unknown presets {unknown}; choose from {sorted(PRESETS)}")
    task = find_task(a.task)
    camp = a.out or os.path.join("runs", "teams", time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4])
    os.makedirs(camp, exist_ok=True)
    json.dump(vars(a) | {"campaign": camp}, open(os.path.join(camp, "plan.json"), "w"), indent=1)
    seeds = a.seeds or [a.seed]
    jobs = [(m, p, e, sd) for m in a.models for p in a.presets for e in a.efforts for sd in seeds]
    print("campaign", camp, "| task", a.task, "| jobs", jobs, flush=True)

    def one(job):
        model, preset, effort, sd = job
        cfg = config(preset, agents=a.agents, islands=a.islands, budget=a.budget, effort=effort, plan=a.plan or None,
                     think_every=a.think_every, think_when_stuck=a.think_when_stuck, think_budget=a.think_budget, unsold_info=a.unsold_info or None, min_finish=a.min_finish)
        svc = make_service(a.backend, task=task)
        tag = f"{preset}-{effort}" + (f"-cap{a.think_budget}" if a.think_budget else "") + (f"-minfinish{a.min_finish}" if a.min_finish else "") + f"{a.tag}" + (f"-s{sd}" if len(seeds) > 1 else "")
        s = run_team(cfg, task, svc, os.path.join(camp, model, tag), model=model, provider=a.provider, seed=sd, max_rounds=a.max_rounds,
                     log=lambda m: print(m, flush=True))
        s["tag"] = tag
        return s
    with ThreadPoolExecutor(max(1, a.parallel)) as ex:
        res = list(ex.map(one, jobs))
    rows = [{k: s[k] for k in ("model", "tag", "preset", "status", "team_best", "best_at", "team_solves", "agents_off_zero", "workers", "best_columns", "copies",
                               "grafts", "distinct_structures", "usd_cached_price_estimate", "usd_logged", "requests", "wall_s")} for s in res]
    json.dump(rows, open(os.path.join(camp, "campaign.json"), "w"), indent=1)
    print("\nmodel | run | status | team best | at 100 / 250 / 500 / 1000 | team solves | off zero | best columns | copies | grafts | structures | $ real | $ logged | requests | min")
    for r in rows:
        b = r["best_at"]
        print(f"{r['model']} | {r['tag']} | {r['status'][:25]} | {r['team_best']:.3f} | {b[100]:.2f} / {b[250]:.2f} / {b[500]:.2f} / {b[1000]:.2f} | {r['team_solves']} | "
              f"{r['agents_off_zero']}/{r['workers']} | {r['best_columns']} | {r['copies']} | {r['grafts']} | {r['distinct_structures']} | "
              f"{r['usd_cached_price_estimate']:.2f} | {r['usd_logged']:.2f} | {r['requests']} | {r['wall_s'] / 60:.1f}")


if __name__ == "__main__":
    main()
