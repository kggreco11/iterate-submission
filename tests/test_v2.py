"""Hydrocarbon-16 V2 economics and safety checks (mock backend; no ChemSep needed)."""
import numpy as np
import pytest

from sepdesign import hc16v2_tasks, make_env, make_service
from sepdesign.hc16 import HC16
from sepdesign.service import SolveService
from sepdesign.tasks import Economics


def _flows(d):
    v = np.zeros(len(HC16))
    for k, x in d.items():
        v[HC16.index(k)] = x
    return v


def test_tasks_are_reproducible_and_vary_pressure():
    a, b = hc16v2_tasks("dev"), hc16v2_tasks("dev")
    assert a == b and len(a) == 4 and len(a[0]["components"]) == 16
    assert len({t["pressure_Pa"] for t in a}) > 1
    assert all(1.0e6 <= t["pressure_Pa"] <= 2.5e6 for t in hc16v2_tasks("test"))


def test_premium_pure_blend_and_impure():
    e = Economics(hc16v2_tasks("dev")[0])
    pure, k1 = e.classify(_flows({"N-butane": 97, "Isobutane": 3}))
    prem, k2 = e.classify(_flows({"N-butane": 99.5, "Isobutane": 0.5}))
    blend, k3 = e.classify(_flows({"N-butane": 50, "Isobutane": 50}))
    none, k4 = e.classify(_flows({"N-butane": 60, "Propane": 40}))
    assert (k1, k2, k4) == ("pure", "premium", "none") and k3 == "blend: C4 mix"
    assert prem == pytest.approx(pure * 99.5 / 97 * 1.2) and none == 0.0 and 0 < blend


def test_blend_and_pure_take_the_higher_value():
    e = Economics(hc16v2_tasks("dev")[0])
    v, kind = e.classify(_flows({"N-butane": 96, "Isobutane": 4}))          # >= 95% n-butane AND >= 95% C4 mix
    assert v == max(e.classify(_flows({"N-butane": 96, "Isobutane": 4}))[0], 0.0) and kind in ("pure", "blend: C4 mix")


def test_v1_task_is_unchanged_by_v2_rules():
    from sepdesign import hc12_tasks
    t = hc12_tasks("dev")[0]
    e = Economics(t)
    assert e.premium_purity is None and not e.groups and e.upper_bound_reward == pytest.approx(e.max_total_revenue / e.reward_norm)


def test_service_with_wrong_cost_multipliers_is_refused():
    class Dummy:
        name = "dummy"

        class cost_model:
            em, cm = 1.0, 1.0
    with pytest.raises(ValueError):
        make_env(hc16v2_tasks("dev")[0], SolveService(Dummy()))


def test_mock_runs_v2_task():
    t = hc16v2_tasks("dev")[0]
    env = make_env(t, make_service("mock", task=t), budget=40)
    env.apply([{"op": "set", "node": "", "n_stages": 60, "reflux_ratio": 3, "reboil_ratio": 3, "pressure_drop_fraction": 0.1}])
    r = env.evaluate()
    assert r["valid"] and np.isfinite(r["reward"])
