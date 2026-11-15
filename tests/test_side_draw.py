"""Side draws (Hydrocarbon-16 V3): rules, tree, accounting and the unchanged V2 behaviour. Mock backend, no simulator needed."""
import numpy as np

from sepdesign import make_env, make_service
from sepdesign.env import EditError, make_query, path_key
from sepdesign.hc16 import hc16v2_tasks, hc16v3_tasks, task_hash
from sepdesign.taskset import find_task, get_tasks

SD = {"stage": 20, "phase": "liquid", "fraction": 0.1}


def _col(node, side=None, n=60):
    e = {"op": "set", "node": node, "n_stages": n, "reflux_ratio": 3, "reboil_ratio": 3, "pressure_drop_fraction": 0.1}
    if side:
        e["side_draw"] = side
    return e


def _env(family="hc16v3", budget=200):
    task = get_tasks("dev", family)[0]
    return make_env(task, make_service("mock", task=task), budget=budget)


def test_v3_tasks_are_v2_feeds_with_side_draws():
    a, b = hc16v2_tasks("dev"), hc16v3_tasks("dev")
    assert [t["task_id"] for t in b] == [f"hc16v3_dev_{i:03d}" for i in range(4)]
    for x, y in zip(a, b):
        assert x["feed_flows_mol_s"] == y["feed_flows_mol_s"] and x["prices_usd_per_mol"] == y["prices_usd_per_mol"]
        assert y["levers"]["side_draw"] and "levers" not in x
    assert find_task("hc16v3_dev_002")["task_id"] == "hc16v3_dev_002"
    assert task_hash(hc16v2_tasks("dev")).startswith("66b06e7b6ff1")        # V2 tasks unchanged (hash recorded in docs/TASK_V2.md)


def test_v2_still_rejects_side_draws_and_s_paths():
    env = _env("hc16v2")
    for e in (_col("", SD), _col("S")):
        try:
            env.apply([e])
            assert False
        except EditError:
            pass


def test_query_key_unchanged_without_side_draw():
    q = make_query([1, 2], 300, 1e6, 40, 3, 3, 0.1)
    assert len(q) == 7 and q == make_query([1, 2], 300, 1e6, 40, 3, 3, 0.1, None)
    assert len(make_query([1, 2], 300, 1e6, 40, 3, 3, 0.1, (20, "liquid", 0.1))) == 8
    assert make_query([1, 2], 300, 1e6, 40, 3, 3, 0.1, (20, "liquid", 0.1)) != make_query([1, 2], 300, 1e6, 40, 3, 3, 0.1, (21, "liquid", 0.1))


def test_side_draw_rules():
    env = _env()
    bad = [dict(SD, stage=30), dict(SD, stage=1), dict(SD, stage=60), dict(SD, phase="gas"), dict(SD, fraction=0.9), dict(SD, fraction=0.01), {"stage": 5}]
    for sd in bad:                               # stage 30 is the feed stage of a 60-stage column
        try:
            env.apply([_col("", sd)])
            assert False, sd
        except EditError:
            pass
    assert env.design == {}
    try:
        env.apply([_col("S")])                    # no column on '' yet, and no side draw
        assert False
    except EditError:
        pass
    env.apply([_col("")])
    try:
        env.apply([_col("S")])                    # the parent has no side draw
        assert False
    except EditError:
        pass


def test_tree_flows_and_removal():
    env = _env()
    env.apply([_col("", SD), _col("S", n=40), _col("ST", n=30)])
    r = env.evaluate()
    assert r["valid"], r["validation"]["errors"]
    n = r["nodes"]
    assert set(n) >= {"", "T", "B", "S", "ST", "SB", "STT", "STB"}
    assert np.allclose(np.array(n["T"]["feed"]) + np.array(n["S"]["feed"]) + np.array(n["B"]["feed"]), n[""]["feed"], atol=1e-4)
    assert abs(sum(n["S"]["feed"]) - 0.1 * sum(n[""]["feed"])) < 1e-3
    assert "side draw 10% of feed" in env.render(r)
    sorted_paths = sorted(n, key=path_key)
    assert sorted_paths.index("T") < sorted_paths.index("S") < sorted_paths.index("B")
    env.apply([_col("")])                          # re-setting without a side draw removes it and everything below
    assert list(env.design) == [""]
    r2 = env.evaluate()
    assert r2["valid"] and "S" not in r2["nodes"]


def test_side_draw_changes_the_solve_and_costs_a_solve():
    env = _env()
    env.apply([_col("")])
    env.evaluate()
    used = env.solves_used
    env.apply([_col("", SD)])
    env.evaluate()
    assert env.solves_used == used + 1             # a different side draw is a different column solve
    env.apply([_col("", dict(SD, stage=25))])
    env.evaluate()
    assert env.solves_used == used + 2
    env.apply([_col("", SD)])
    env.evaluate()
    assert env.solves_used == used + 2             # same as before: free


def test_validation_catches_a_broken_side_balance():
    env = _env()
    env.apply([_col("", SD)])
    r = env.evaluate()
    assert r["valid"]
    r["nodes"][""]["column_result"]["side"]["flows"][0] += 5.0
    from sepdesign.validation import validate_result
    assert not validate_result(env.design, r, env.econ, env.bounds, env.max_columns)["eligible"]
