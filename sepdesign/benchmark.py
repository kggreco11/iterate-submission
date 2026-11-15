"""
Benchmark harness: run robots or agents on the tasks under identical rules and summarise.

An ENTRY is either a robot name (first_cut_greedy, random, random_then_greedy) or an agent, written "agent:module:function" where
`function(env, task, seed)` spends the env's solve budget however it likes (see agents/example_agent.py: run_agent). The harness builds the
environment (same task, same solve budget, same simulator), attaches the improvement trace, runs the entry, and saves one run file.

Every run is scored the same way: the best reward found at 40, 120 and 400 solves (the env keeps a best-so-far curve), so one 400-solve run gives
all three comparison points. Deterministic entries (first_cut_greedy) ignore the seed and run once per task.
"""
import csv
import glob
import importlib
import json
import os
import time

import numpy as np

from sepdesign import baselines
from sepdesign.env import attach_trace
from sepdesign.taskset import get_tasks
from sepdesign.runlog import save_run
from sepdesign.service import make_env, make_service

ROBOTS = {"first_cut_greedy": True, "random": False, "random_then_greedy": False}      # name -> deterministic?
POINTS = (40, 120, 400)


def run_robot(name, env, seed):
    if name == "first_cut_greedy":
        baselines.first_cut(env)
        baselines.greedy_local(env, passes=10)
    elif name == "random":
        baselines.random_designs(env, seed=seed)
    elif name == "random_then_greedy":
        baselines.random_then_greedy(env, seed=seed)
    else:
        raise ValueError(f"unknown robot {name!r}")


def run_agent(spec, env, task, seed):
    _, mod, fn = spec.split(":")
    getattr(importlib.import_module(mod), fn)(env, task, seed)


def run_name(entry, task_id, seed, budget):
    safe = entry.replace(":", "_").replace(".", "_")
    return f"{task_id}__{safe}__s{seed}__b{budget}"


def run_one(entry, split, task_idx, seed, budget, backend, out_dir, extra=None):
    """Run one entry on one task and save the run file; returns its path. Skips work if the file already exists (resumable)."""
    task = get_tasks(split)[task_idx]
    path = os.path.join(out_dir, run_name(entry, task["task_id"], seed, budget) + ".json")
    if os.path.exists(path):
        return path
    svc = make_service(backend, task=task)
    env = make_env(task, svc, budget=budget)
    attach_trace(env)
    t0 = time.perf_counter()
    if entry.startswith("agent:"):
        run_agent(entry, env, task, seed)
    else:
        run_robot(entry, env, seed)
    save_run(path, env, task, f"{entry} (seed {seed}, {budget} solves)", backend=svc.backend_name, wall_s=time.perf_counter() - t0,
             extra={"entry": entry, "seed": seed, "split": split, "service": svc.stats(), **(extra or {})})
    return path


def jobs(entries, split, tasks, seeds, budget):
    out = []
    for e in entries:
        det = ROBOTS.get(e, False)
        for t in tasks:
            for s in ([seeds[0]] if det else seeds):
                out.append((e, split, t, s, budget))
    return out


def summarize(out_dir, points=POINTS):
    """Aggregate run files in out_dir: mean best reward at each point per entry (over tasks and seeds), plus per-task means."""
    runs = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(out_dir, "*.json")))]
    runs = [r for r in runs if r.get("entry")]
    table, per_task = {}, {}
    for r in runs:
        row = table.setdefault(r["entry"], {"runs": 0, "wall_s": [], **{f"at_{k}": [] for k in points}, "backend": set()})
        row["runs"] += 1
        row["wall_s"].append(r.get("wall_s", 0.0))
        row["backend"].add(r.get("backend", ""))
        for k in points:
            if k > r["budget"]:                                             # this run never reached k solves: not counted at k
                continue
            v = r["curve"].get(str(k))
            row[f"at_{k}"].append(0.0 if v is None else float(v))           # no valid design yet by k solves counts as 0
        per_task.setdefault((r["entry"], r["task"]), []).append(r["best_reward"] or 0.0)
    lines = ["| entry | runs | " + " | ".join(f"best @ {k}" for k in points) + " | mean wall (s) | backend |", "|---|---|" + "---|" * (len(points) + 2)]
    for e, row in sorted(table.items()):
        cells = [("n/a" if not row[f"at_{k}"] else f"{np.mean(row[f'at_{k}']):.3f}" + (f" +- {np.std(row[f'at_{k}']):.2f}" if len(row[f"at_{k}"]) > 1 else ""))
                 for k in points]
        lines.append(f"| {e} | {row['runs']} | " + " | ".join(cells) + f" | {np.mean(row['wall_s']):.0f} | {','.join(sorted(row['backend']))} |")
    md = "\n".join(lines)
    with open(os.path.join(out_dir, "summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entry", "task", "n_runs", "mean_final_best"])
        for (e, t), v in sorted(per_task.items()):
            w.writerow([e, t, len(v), f"{np.mean(v):.4f}"])
    open(os.path.join(out_dir, "summary.md"), "w").write(md + "\n")
    return md
