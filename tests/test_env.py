"""Environment tests on the mock backend (no ChemSep needed). Run: python -m pytest -q"""
import numpy as np
import pytest

from sepdesign import EditError, attach_trace, hc12_tasks, make_env, make_service
from sepdesign import baselines

COL = {"op": "set", "node": "", "n_stages": 50, "reflux_ratio": 3, "reboil_ratio": 3, "pressure_drop_fraction": 0.1}


@pytest.fixture()
def env():
    return make_env(hc12_tasks("dev")[0], make_service("mock"), budget=60)


def test_edits_are_validated(env):
    with pytest.raises(EditError):
        env.apply([{**COL, "node": "T"}])                      # no parent column
    with pytest.raises(EditError):
        env.apply([{**COL, "n_stages": 4000}])                 # out of range
    assert env.validate([{"op": "revert"}])                    # nothing to revert to yet
    assert env.design == {}


def test_budget_counts_distinct_solves(env):
    env.apply([COL])
    env.evaluate()
    used = env.solves_used
    env.evaluate()                                              # unchanged design: free
    assert env.solves_used == used == 1


def test_mass_balance_and_reward(env):
    env.apply([COL])
    r = env.evaluate()
    n = r["nodes"][""]
    assert np.allclose(np.array(n["tops"]) + np.array(n["bottoms"]), n["feed"], rtol=1e-6)
    assert np.isfinite(r["reward"]) and r["reward"] < env.econ.upper_bound_reward


def test_baselines_improve_and_trace(env):
    attach_trace(env)
    baselines.first_cut(env)
    first = env.score()
    baselines.greedy_local(env, passes=1)
    assert env.score() >= first
    assert env.trace and env.trace[-1]["reward"] == pytest.approx(env.score())
    assert env.solves_used <= env.solve_budget


def test_revert_and_sell(env):
    env.apply([COL])
    env.evaluate()
    env.apply([{**COL, "node": "T", "n_stages": 40}])
    env.apply([{"op": "sell", "node": "T"}])
    assert "T" not in env.design
    env.apply([{"op": "revert"}])
    assert set(env.design) == {""}


def test_failed_column_design_is_invalid(env):
    env.apply([{**COL, "reflux_ratio": 30, "reboil_ratio": 30}])      # the mock fails extreme designs, like the real solver sometimes does
    r = env.evaluate()
    assert r["failed"] == [""] and not r["valid"]
    assert env.score() is None and env.best is None                  # a failed column never counts as the best design
    assert "NOT VALID" in env.render(r)
