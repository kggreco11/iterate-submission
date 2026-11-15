"""
Run robots and/or agents on the dev tasks (several seeds, in parallel processes) and print a summary table.

    python scripts/run_benchmark.py --entries first_cut_greedy random random_then_greedy --tasks 0 1 2 3 --seeds 0 1 2 --budget 400 --workers 6
    python scripts/run_benchmark.py --entries agent:agents.example_agent:run_agent --budget 120 --backend mock
    python scripts/run_benchmark.py --summarize runs/bench                      # just re-summarise existing run files

An entry is a robot (first_cut_greedy, random, random_then_greedy) or "agent:module:function" with function(env, task, seed). Runs are resumable
(a finished run file is skipped). Every run solves independently with its own cache; budgets are per run. Output: runs/bench/*.json,
summary.md, summary.csv.
"""
import argparse
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign.benchmark import jobs, run_one, summarize  # noqa: E402


def _work(args):
    entry, split, task, seed, budget, backend, out = args
    try:
        return run_one(entry, split, task, seed, budget, backend, out), None
    except Exception as ex:  # noqa: BLE001
        return None, f"{entry} task {task} seed {seed}: {type(ex).__name__}: {ex}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entries", nargs="*", default=["first_cut_greedy", "random", "random_then_greedy"])
    ap.add_argument("--split", default="dev", choices=["dev", "test"])
    ap.add_argument("--family", default="hc12", choices=["hc12", "hc16v2", "hc16v3"], help="task family (workers inherit it through $TASK_FAMILY)")
    ap.add_argument("--tasks", nargs="*", type=int, default=[0, 1, 2, 3])
    ap.add_argument("--seeds", nargs="*", type=int, default=[0, 1, 2])
    ap.add_argument("--budget", type=int, default=400)
    ap.add_argument("--workers", type=int, default=4, help="parallel runs (each run uses one solver process at a time)")
    ap.add_argument("--backend", default=None)
    ap.add_argument("--out", default="runs/bench")
    ap.add_argument("--summarize", default=None, help="only summarise this folder")
    a = ap.parse_args()
    if a.summarize:
        print(summarize(a.summarize))
        return
    os.environ["TASK_FAMILY"] = a.family
    if a.split == "test":
        print("NOTE: test split. Run the test tasks once, with every setting frozen.")
    work = [(e, a.split, t, s, a.budget, a.backend, a.out) for (e, _, t, s, _) in jobs(a.entries, a.split, a.tasks, a.seeds, a.budget)]
    print(f"{len(work)} runs, {a.workers} at a time, budget {a.budget} solves each")
    t0 = time.perf_counter()
    errors = []
    with ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(_work, w) for w in work]
        for i, f in enumerate(as_completed(futs), 1):
            path, err = f.result()
            if err:
                errors.append(err)
                print("ERROR", err, flush=True)
            else:
                print(f"[{i}/{len(work)}] {os.path.basename(path)} ({time.perf_counter() - t0:.0f}s)", flush=True)
    print(summarize(a.out))
    if errors:
        print(f"{len(errors)} run(s) failed:", *errors, sep="\n  ")


if __name__ == "__main__":
    main()
