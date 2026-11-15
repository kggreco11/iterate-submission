"""
A small runnable agent loop to copy from. This one is NOT a language-model agent: it proposes random edits to the best design so far. Replace
`propose()` with a model call that reads `env.render(result)` and returns a list of edits (the same dicts `env.apply` takes).

    python agents/example_agent.py --budget 120                 # ChemSep (needs ChemSep installed)
    python agents/example_agent.py --budget 120 --backend mock  # development only
Writes runs/example_agent.json (plays in the demo page: python demo/build_replay.py runs/example_agent.json).
"""
import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign import EditError, attach_trace, baselines, hc12_tasks, make_env, make_service, save_run  # noqa: E402


def propose(env, result, rnd):
    """Edits to try next, given the current result. Here: nudge one column's settings, or add a column on an impure stream."""
    impure = baselines._off_spec_leaves(env, result)
    if impure and rnd.random() < 0.4 and len(env.design) < env.max_columns:
        return [{"op": "set", "node": rnd.choice(impure), "n_stages": rnd.randint(30, 120), "reflux_ratio": rnd.uniform(1, 8),
                 "reboil_ratio": rnd.uniform(1, 8), "pressure_drop_fraction": rnd.uniform(0, 0.3)}]
    path = rnd.choice(sorted(env.design))
    n, rr, rb, dp = env.design[path]
    return [{"op": "set", "node": path, "n_stages": max(5, min(200, int(n * rnd.uniform(0.8, 1.25)))),
             "reflux_ratio": max(0.1, min(30, rr * rnd.uniform(0.8, 1.25))), "reboil_ratio": max(0.1, min(30, rb * rnd.uniform(0.8, 1.25))),
             "pressure_drop_fraction": max(0.0, min(0.9, dp + rnd.uniform(-0.05, 0.05)))}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=120)
    ap.add_argument("--task", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--backend", default=None)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    task = hc12_tasks("dev")[a.task]
    svc = make_service(a.backend)
    env = make_env(task, svc, budget=a.budget)
    attach_trace(env)
    t0 = time.perf_counter()
    result = baselines.first_cut(env)                      # a starting design, then refine
    while env.solves_left > 0:
        env.design = dict(env.best[1])                     # always edit the best design so far
        try:
            env.apply(propose(env, result, rnd))
        except EditError:
            continue
        result = env.evaluate()
    print(f"best reward {env.score():.3f} using {env.solves_used} solves on {task['task_id']} ({svc.backend_name})")
    save_run("runs/example_agent.json", env, task, f"example agent (seed {a.seed})", backend=svc.backend_name, wall_s=time.perf_counter() - t0)


if __name__ == "__main__":
    main()
