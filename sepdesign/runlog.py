"""
Run files: one JSON per run, in the format the plant-replay page (demo/build_replay.py) reads. Agents should write the same fields.

  {"label", "task", "components", "upper_bound_reward", "backend", "budget", "solves_used", "best_reward", "wall_s", "curve", "trace": [...], ...}
`trace` comes from sepdesign.env.attach_trace(env): one snapshot per improvement of the best design.
"""
import json
import os

CHECKPOINTS = (20, 40, 80, 120, 200, 300, 400, 600, 800, 1200)


def save_run(path, env, task, label, backend="", wall_s=0.0, extra=None):
    out = {"label": label, "task": task["task_id"], "components": list(task["components"]), "upper_bound_reward": env.econ.upper_bound_reward,
           "reward_norm": env.econ.reward_norm, "backend": backend, "budget": env.solve_budget, "solves_used": env.solves_used, "best_reward": env.score(), "wall_s": wall_s,
           "curve": {str(k): env.best_so_far_at(k) for k in CHECKPOINTS if k <= env.solve_budget}, "trace": getattr(env, "trace", []), **(extra or {})}
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    json.dump(out, open(path, "w"), indent=1)
    # Persistent agent runs have a usage summary and submission history.
    folder = os.path.dirname(os.path.abspath(path))
    if os.path.exists(os.path.join(folder, "summary.json")) and os.path.exists(os.path.join(folder, "turns.jsonl")):
        try:
            from sepdesign.report import build
            build(folder)
        except Exception as exc:
            with open(os.path.join(folder, "report_failure.json"), "w") as failure:
                json.dump({"error_type": type(exc).__name__}, failure)
    return out
