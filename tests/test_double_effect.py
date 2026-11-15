"""Double-effect columns (Hydrocarbon-16 V3): rules, budget, accounting, heat link. Mock backend, no simulator needed."""
import numpy as np

from sepdesign import make_env, make_service
from sepdesign.env import EditError, effect_of
from sepdesign.multi_effect import DT_MIN, heat_link
from sepdesign.taskset import get_tasks
from sepdesign.validation import validate_result

DE = {"fraction": 0.5, "low_pressure_drop_fraction": 0.6}


def _col(node, de=None, side=None, dp=0.0):
    e = {"op": "set", "node": node, "n_stages": 60, "reflux_ratio": 3, "reboil_ratio": 3, "pressure_drop_fraction": dp}
    if de:
        e["double_effect"] = de
    if side:
        e["side_draw"] = side
    return e


def _env(family="hc16v3", budget=200):
    task = get_tasks("dev", family)[0]
    return make_env(task, make_service("mock", task=task), budget=budget)


def _raises(env, edits):
    try:
        env.apply(edits)
    except EditError:
        return True
    return False


def test_rules():
    assert _raises(_env("hc16v2"), [_col("", DE)])                                        # not in V2
    env = _env()
    assert _raises(env, [_col("", dict(DE, fraction=0.9))])
    assert _raises(env, [_col("", dict(DE, low_pressure_drop_fraction=0.2), dp=0.3)])     # LP must be at a lower pressure
    assert _raises(env, [_col("", dict(DE, low_pressure_drop_fraction=0.95))])
    assert _raises(env, [_col("", DE, side={"stage": 20, "phase": "liquid", "fraction": 0.1})])
    assert _raises(env, [_col("", {"fraction": 0.5})])
    env.apply([_col("", DE)])
    assert effect_of(env.design[""]) == (0.5, 0.6)


def test_pair_costs_two_solves_and_balances():
    env = _env()
    env.apply([_col("", DE), _col("T")])
    r = env.evaluate()
    assert r["valid"], r["validation"]["errors"]
    assert env.solves_used == 3
    n = r["nodes"][""]
    cr = n["column_result"]
    feed = np.asarray(n["feed"])
    assert np.allclose(np.asarray(cr["tops"]["flows"]) + np.asarray(cr["bottoms"]["flows"]), feed, atol=1e-4)
    hp, lp = cr["effects"]["hp"], cr["effects"]["lp"]
    assert abs(sum(hp["tops"]["flows"]) + sum(hp["bottoms"]["flows"]) - 0.5 * feed.sum()) < 1e-3
    assert lp["tops"]["P"] < hp["tops"]["P"]
    link = cr["effects"]["link"]
    assert abs(cr["tac"] - (hp["tac"] + lp["tac"] - link["saving_usd"] + link["exchanger_usd"])) < 1e-6
    assert "DOUBLE EFFECT" in env.render(r)
    env.evaluate()
    assert env.solves_used == 3                                                            # unchanged pair: free
    env.apply([_col("", dict(DE, fraction=0.4)), _col("T")])
    env.evaluate()
    assert env.solves_used == 6                                                            # both effects and the column below change


def test_validation_rejects_tampered_pair():
    env = _env()
    env.apply([_col("", DE)])
    r = env.evaluate()
    r["nodes"][""]["column_result"]["tops"]["flows"][0] += 3.0
    assert not validate_result(env.design, r, env.econ, env.bounds, env.max_columns)["eligible"]


def test_heat_link_rules():
    def res(qc, qr, Tc, Tr, util=1e9):
        return {"qc": qc, "qr": qr, "cost": {"Tc": Tc, "Tr": Tr, "price_cond": 1.0, "price_reb": 9.0, "utilities": util}}
    hp, lp = res(-50e6, 55e6, 400.0, 420.0), res(-40e6, 45e6, 350.0, 380.0)
    ok = heat_link(hp, lp, 2.0, 10.0)
    assert ok["feasible"] and abs(ok["heat_MW"] - 45.0) < 1e-9 and ok["dT_K"] == 20.0
    assert abs(ok["saving_usd"] - 2.0 * 10.0 * 45e6 * 8000 * 3600 / 1e9) < 1.0
    assert ok["exchanger_usd"] > 0
    no = heat_link(res(-50e6, 55e6, 385.0, 420.0), lp, 2.0, 10.0)                        # 5 K gap < DT_MIN
    assert not no["feasible"] and no["saving_usd"] == 0.0 and DT_MIN == 10.0
    capped = heat_link(hp, res(-40e6, 45e6, 350.0, 380.0, util=1.0), 2.0, 10.0)
    assert capped["saving_usd"] <= 1e9 + 1.0
