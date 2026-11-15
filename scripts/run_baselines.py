"""
Run a non-agent baseline on a task and save a run file (with the plant-replay trace).

    python scripts/run_baselines.py --robot random_then_greedy --task 0 --budget 400
    python scripts/run_baselines.py --robot first_cut_greedy --backend mock --budget 100      # no ChemSep needed (development only)
Robots: first_cut_greedy, random, random_then_greedy. Output: runs/<task>_<robot>_s<seed>_b<budget>.json
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign import attach_trace, make_env, make_service, save_run  # noqa: E402
from sepdesign.taskset import get_tasks  # noqa: E402
from sepdesign import baselines  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--robot", default="random_then_greedy", choices=["first_cut_greedy", "random", "random_then_greedy"])
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--family", default="hc12", choices=["hc12", "hc16v2", "hc16v3"])
    ap.add_argument("--task", type=int, default=0)
    ap.add_argument("--budget", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--backend", default=None, help="chemsep (default) or mock")
    ap.add_argument("--out", default="runs")
    a = ap.parse_args()
    task = get_tasks(a.split, a.family)[a.task]
    svc = make_service(a.backend, task=task)
    env = make_env(task, svc, budget=a.budget)
    attach_trace(env)
    t0 = time.perf_counter()
    if a.robot == "first_cut_greedy":
        baselines.first_cut(env)
        baselines.greedy_local(env, passes=10)
    elif a.robot == "random":
        baselines.random_designs(env, seed=a.seed)
    else:
        baselines.random_then_greedy(env, seed=a.seed)
    dt = time.perf_counter() - t0
    path = os.path.join(a.out, f"{task['task_id']}_{a.robot}_s{a.seed}_b{a.budget}.json")
    out = save_run(path, env, task, f"{a.robot} (seed {a.seed}, {a.budget} solves)", backend=svc.backend_name, wall_s=dt,
                   extra={"robot": a.robot, "seed": a.seed, "service": svc.stats()})
    print(f"{task['task_id']} {a.robot} backend={svc.backend_name}: best reward {out['best_reward']:.3f} "
          f"(upper bound {out['upper_bound_reward']:.2f}) in {out['solves_used']} solves, {dt:.0f}s -> {path}")


if __name__ == "__main__":
    main()
