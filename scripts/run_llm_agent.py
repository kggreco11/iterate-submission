"""
Run the language-model agent on dev tasks (one independent run per task and seed, in parallel) with per-request token and dollar accounting.

    python scripts/run_llm_agent.py --provider scripted --tasks 0 --budget 60              # free dry run of the loop (no API)
    python scripts/run_llm_agent.py --provider anthropic --model claude-opus-5-5 --tasks 0 1 2 3 --budget 400 --max-usd 15

The API key is read from the environment or a local .env file in the repo root (ANTHROPIC_API_KEY / OPENAI_API_KEY); .env is git-ignored. Outputs:
runs/llm/<run_id>/{usage.jsonl, summary.json, turns.jsonl} and runs/llm/<run_id>.json (the run file for the replay page and benchmark summary).
Each run stops at the solve budget, the turn cap, or the per-run spend cap, whichever comes first, and records why.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agents"))


def _one(a):
    from llm_agent import load_dotenv, run_agent
    from sepdesign import attach_trace, make_env, make_service, save_run
    from sepdesign.taskset import get_tasks
    load_dotenv()
    split, ti, seed, budget, provider, model, max_turns, max_usd, out, backend = a
    task = get_tasks(split)[ti]
    svc = make_service(backend, task=task)
    env = make_env(task, svc, budget=budget)
    attach_trace(env)
    t0 = time.perf_counter()
    summ = run_agent(env, task, seed, provider=provider, model=model, max_turns=max_turns, max_usd=max_usd, out_dir=out)
    path = os.path.join(out, summ["run_id"] + ".json")
    save_run(path, env, task, f"{model if provider != 'scripted' else 'scripted'} (seed {seed}, {budget} solves)", backend=svc.backend_name,
             wall_s=time.perf_counter() - t0, extra={"entry": f"llm:{provider}:{model}", "seed": seed, "split": split, "llm": summ, "service": svc.stats()})
    return summ


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="anthropic", choices=["anthropic", "openai", "scripted", "modal"], help="modal = Kimi on a Modal endpoint (agents/kimi.py; use --model kimi-k3.1-pro)")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--family", default="hc12", choices=["hc12", "hc16v2", "hc16v3"], help="task family (workers inherit it through $TASK_FAMILY)")
    ap.add_argument("--tasks", nargs="*", type=int, default=[0])
    ap.add_argument("--seeds", nargs="*", type=int, default=[0])
    ap.add_argument("--budget", type=int, default=400)
    ap.add_argument("--max-turns", type=int, default=80)
    ap.add_argument("--max-usd", type=float, default=None, help="Optional estimated API spend threshold; disabled by default")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--backend", default=None)
    ap.add_argument("--out", default="runs/llm")
    a = ap.parse_args()
    os.environ["TASK_FAMILY"] = a.family
    if a.split == "test":
        print("NOTE: test split. Run the test tasks once, with every setting frozen.")
    jobs = [(a.split, t, s, a.budget, a.provider, a.model, a.max_turns, a.max_usd, a.out, a.backend) for t in a.tasks for s in a.seeds]
    print(f"{len(jobs)} run(s): {a.provider}/{a.model}, budget {a.budget} solves, max {a.max_turns} turns, API spend threshold {a.max_usd if a.max_usd is not None else 'disabled'}")
    total = 0.0
    with ProcessPoolExecutor(min(a.workers, len(jobs))) as ex:
        for f in as_completed([ex.submit(_one, j) for j in jobs]):
            try:
                s = f.result()
            except Exception as e:  # noqa: BLE001
                print("RUN FAILED:", type(e).__name__, str(e)[:200])
                continue
            total += s["usd_estimated_total"]
            print(f"{s['task']} seed {s['seed']}: best valid reward {s['best_valid_reward']}, {s['solves_used']} solves, {s['turns']} turns, "
                  f"{s['requests']} requests, {s['input_tokens']} in / {s['output_tokens']} out tokens, ~${s['usd_estimated_total']:.2f}, stopped: {s['status']}")
    print(f"total estimated spend ${total:.2f}")


if __name__ == "__main__":
    main()
