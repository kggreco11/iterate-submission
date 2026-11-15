"""
Quick end-to-end check of the simulator and environment (about 30 s with ChemSep, instant with the mock).

    python scripts/smoke_test.py                 # ChemSep (must be installed)
    python scripts/smoke_test.py --backend mock
Builds one design by hand, evaluates it, runs a short greedy search, and checks the mass balance and the reward.
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sepdesign import make_env, make_service  # noqa: E402
from sepdesign.taskset import get_tasks  # noqa: E402
from sepdesign import baselines  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None)
    ap.add_argument("--family", default="hc12", choices=["hc12", "hc16v2", "hc16v3"])
    a = ap.parse_args()
    t0 = time.perf_counter()
    task = get_tasks("dev", a.family)[0]
    svc = make_service(a.backend, task=task)
    env = make_env(task, svc, budget=60)
    print(f"backend: {svc.backend_name}; task {task['task_id']}: {len(task['components'])} components, "
          f"upper-bound reward {env.econ.upper_bound_reward:.2f}")
    env.apply([{"op": "set", "node": "", "n_stages": 60, "reflux_ratio": 4.0, "reboil_ratio": 4.0, "pressure_drop_fraction": 0.1}])
    r = env.evaluate()
    root = r["nodes"][""]
    assert root["status"] == "ok", f"the first column did not solve: {root}"
    feed = np.array(root["feed"])
    out = np.array(root["tops"]) + np.array(root["bottoms"])
    assert np.allclose(feed, out, rtol=1e-3, atol=1e-3 * feed.sum()), "mass balance across the first column is off"
    print(env.render(r))
    baselines.first_cut(env)
    baselines.greedy_local(env, passes=1)
    print(f"after first-cut + greedy: best reward {env.score():.3f} with {env.solves_used} solves; solver stats {svc.stats()}")
    assert env.score() is not None and np.isfinite(env.score())
    print(f"OK ({time.perf_counter() - t0:.0f}s)")


if __name__ == "__main__":
    main()
