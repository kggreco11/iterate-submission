"""Equal per-agent budget, same-harness controls and campaign isolation."""
import json
from pathlib import Path
import pytest

from sepdesign.experiments import control_plan, run_controls
from sepdesign.service import make_service
from sepdesign.swarm_memory import ExactMemory, NoMemory
from scripts.smoke_controls import SmokePolicy, StalledPast


def task():
    value = json.loads(Path('tasks/hc16v2_dev_000.json').read_text())
    value['experiment'] = {'simulator_budget_per_agent': 100}
    return value


def test_configured_controls_have_100_per_agent_queries_and_no_assigned_roles():
    plan = control_plan(task(), 'same-model')
    assert [e['condition'] for e in plan['trials']] == ['single_without_past','single_with_past','swarm_without_past','swarm_with_past']
    assert [e['total_budget'] for e in plan['trials']] == [100,100,500,500]
    assert all(sum(e['allocations']) == e['total_budget'] for e in plan['trials'])
    assert all(e['budget_per_agent'] == 100 for e in plan['trials'])
    assert plan['trials'][0]['allocations'] == [100]
    assert all(e['allocations'] == [100]*5 for e in plan['trials'][2:])
    assert plan['spend_threshold'] is None and plan['assigned_hypotheses'] is False
    assert len({tuple(e['condition'] for e in control_plan(task(), 'm', repetitions=4)['trials'][i:i+4])
                for i in range(0,16,4)}) == 4


def test_full_control_campaign_respects_budget_and_fresh_cache(tmp_path):
    services = []
    def service():
        value = make_service('mock', task=task())
        services.append(value)
        return value
    memories = []
    def memory(kind):
        value = {'none': NoMemory, 'exact': ExactMemory, 'past': StalledPast}[kind]()
        memories.append(value)
        return value
    root, outcomes = run_controls(task(), service, SmokePolicy, tmp_path,
        memory_factory=memory, rounds=101, model='smoke')
    assert [o['queries'] for o in outcomes] == [100,100,500,500]
    assert len(services) == len({id(s) for s in services}) == 4
    assert len({m.run_id for m in memories}) == 5  # includes preflight
    assert all(2 <= len(m.run_id) <= 40 for m in memories)
    assert json.loads((root/'summary.json').read_text())['state'] == 'complete'
    for outcome in outcomes:
        config = json.loads((root/outcome['run']/'config.json').read_text())
        assert config['mode'] == 'equal-per-agent'
        assert config['allocations'] == [100]*outcome['agents']
        assert config['context_protocol'] == 'compact-v3'
        assert config['model'] == 'smoke'


def test_dirty_project_preflight_prevents_any_control_spend(tmp_path):
    class Dirty:
        def start(self, *args): raise RuntimeError('Clean-slate check failed')
    with pytest.raises(RuntimeError, match='Clean-slate'):
        run_controls(task(), lambda: pytest.fail('no simulator should be constructed'),
            lambda *a: pytest.fail('no policy should be constructed'), tmp_path,
            memory_factory=lambda kind: Dirty())
    summary = json.loads(next(tmp_path.glob('*/summary.json')).read_text())
    assert summary['state'] == 'failed' and summary['outcomes'] == []


def test_cli_plans_only_the_supplied_task_without_credentials(tmp_path, monkeypatch):
    from scripts import run_controls as runner
    path = tmp_path/'chosen-task.json'
    path.write_text(json.dumps(task()))
    monkeypatch.setattr(runner, 'load_dotenv', lambda *a: pytest.fail('planning needs no credentials'))
    monkeypatch.setattr(runner, 'run_controls', lambda *a, **k: pytest.fail('planning must not execute'))
    plan = runner.main(['--task', str(path)])
    assert plan['budget'] == 100 and len(plan['trials']) == 4
    assert plan['task'] == task()['task_id']


def test_control_runner_never_selects_an_implicit_task():
    from scripts.run_controls import main
    with pytest.raises(SystemExit):
        main([])


def test_control_budget_is_configuration_or_explicit_override():
    value = task()
    value['experiment']['simulator_budget_per_agent'] = 17
    plan = control_plan(value, 'model')
    assert plan['trials'][0]['allocations'] == [17]
    assert plan['trials'][2]['allocations'] == [17]*5
    assert control_plan(value, 'model', budget=23)['trials'][2]['allocations'] == [23]*5
    value.pop('experiment')
    with pytest.raises(ValueError, match='experiment.simulator_budget_per_agent'):
        control_plan(value, 'model')


def test_standalone_runner_reads_task_budget_and_preserves_legacy_default(tmp_path):
    from sepdesign.swarm import run_swarm
    class Policy:
        def call(self, *args): return 'finish', {}
    value = task()
    value['experiment']['simulator_budget_per_agent'] = 17
    for configured in (True, False):
        if not configured: value.pop('experiment')
        root, _ = run_swarm(value, make_service('mock', task=value), NoMemory(),
            lambda *a: Policy(), tmp_path, n=5, rounds=1)
        config = json.loads((root/'config.json').read_text())
        assert config['allocations'] == ([17]*5 if configured else [10]*5)


def test_pairs_preserve_local_sharing_and_off_condition_skips_remote(tmp_path):
    from sepdesign.experiments import CONDITIONS, memory_for
    assert [(n, memory_for(k).sharing) for _, n, k in CONDITIONS if k != 'past'] == [(1, True), (5, True)]
    calls = []
    def memory(kind):
        calls.append(kind)
        assert kind == 'exact'
        return ExactMemory()
    value = task()
    value['experiment']['simulator_budget_per_agent'] = 2
    root, outcomes = run_controls(value, lambda: make_service('mock', task=value),
        SmokePolicy, tmp_path, memory_factory=memory, rounds=3,
        conditions=['swarm_without_past'])
    assert calls == ['exact']
    assert outcomes[0]['queries'] == 10
    assert not (root/'memory-preflight.json').exists()
