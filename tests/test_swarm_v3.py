"""Regressions from the completed r3 memory audit, through the real runner."""
import json
import time
from pathlib import Path
import pytest

from sepdesign.service import make_service, make_env, SolveService
from sepdesign.swarm import run_swarm
from sepdesign.swarm_memory import LocalMemory, NoMemory, ExactMemory, PastMemory
from sepdesign.swarm_context import compact_record, build_prompt, encoded, MAX_RECORD_BYTES, recall_query


def task():
    return json.loads(Path('tasks/hc12_dev_000.json').read_text())


def edit(node='', **overrides):
    return dict(op='set', node=node, n_stages=50, reflux_ratio=3,
                reboil_ratio=3, pressure_drop_fraction=.04, **overrides)


def test_own_history_and_rejection_survive_empty_external_recall(tmp_path):
    class Empty(LocalMemory):
        def recall(self, *args, **kwargs): return []
    prompts = []
    class Policy:
        def call(self, system, user, env):
            prompts.append(user)
            if len(prompts) == 1:
                return 'submit_edits', {'edits': [edit()], 'note': 'REMEMBER_MY_REASONING'}
            if len(prompts) == 2:
                return 'submit_edits', {'edits': [{'op': 'sell', 'node': 'TTTT'}]}
            return 'finish', {}
    run_swarm(task(), make_service('mock'), Empty(), lambda *a: Policy(),
              tmp_path, n=1, rounds=3, budget=10)
    assert 'Recent turns' in prompts[2]
    assert 'REMEMBER_MY_REASONING' in prompts[2]
    assert 'YOUR LAST EDITS WERE REJECTED' in prompts[2]
    assert 'no column at' in prompts[2]


def test_rejected_citations_are_audited_but_never_published(tmp_path):
    memory = LocalMemory()
    class Policy:
        def call(self, *args):
            return 'submit_edits', {'edits': [], 'evidence_ids': ['INVENTED_ID']}
    root, _ = run_swarm(task(), make_service('mock'), memory, lambda *a: Policy(),
                        tmp_path, n=1, rounds=1)
    rows = [json.loads(x) for x in (root/'raw/trajectory.jsonl').read_text().splitlines()]
    assert any(e['kind'] == 'submission' and e.get('rejected') for e in rows)
    assert memory.records == {}


class SeparatingBackend:
    """Conserve mass and produce a profitable measured root for transfer tests."""
    def solve_column(self, request):
        flows = request['feed_flows_mol_s']
        return dict(success=True, tac_usd_per_year=0, runtime_s=0,
            tops=dict(flows=[flows[0]]+[0.]*(len(flows)-1), T_K=request['temperature_K'], P_Pa=request['pressure_Pa']),
            bottoms=dict(flows=[0.]+flows[1:], T_K=request['temperature_K'], P_Pa=request['pressure_Pa']),
            condenser_duty_W=0, reboiler_duty_W=0)


@pytest.mark.parametrize('memory', [ExactMemory, NoMemory])
def test_incumbent_delivery_and_independent_control(tmp_path, memory):
    seen = {}
    class Policy:
        def __init__(self, agent): self.agent, self.turn = agent, 0
        def call(self, system, user, env):
            self.turn += 1
            if self.turn == 1:
                return 'submit_edits', {'edits': [edit()] if self.agent == 'agent-0' else []}
            seen[self.agent] = user
            return 'finish', {}
    root, summary = run_swarm(task(), SolveService(SeparatingBackend()), memory(),
        lambda a, *rest: Policy(a), tmp_path, n=2, rounds=2, budget=10)
    assert summary['status'] == 'round_limit'
    prompt = json.loads((root/'raw/agent-1/prompts/round-0002.json').read_text())
    if memory is ExactMemory:
        assert 'agent-0-v1' in seen['agent-1']
        assert prompt['diagnostics']['incumbent_included']
    else:
        assert 'agent-0-v1' not in seen['agent-1']
        assert prompt['diagnostics']['source_ids'] == []


def test_large_raw_experiment_is_compacted_and_citations_do_not_recur():
    raw = dict(id='run-agent-0-v24', agent='agent-0', round=24, design={'': [50,3,3,.04]},
        measured=dict(valid=True, reward=3.5, revenue=100, tac=10,
            nodes={'huge': 'x'*100000}), evidence_ids=['UNSUPPORTED'],
        evidence_sources={'UNSUPPORTED': []}, edits=[{'bad': 'UNSUPPORTED'}], rejected=None)
    projected = compact_record(raw)
    assert len(encoded(projected).encode()) <= MAX_RECORD_BYTES
    assert projected['design'] == raw['design'] and projected['measured']['reward'] == 3.5
    assert 'UNSUPPORTED' not in encoded(projected) and 'huge' not in encoded(projected)


def test_prompt_budget_preserves_incumbent_and_drops_large_optional_memory():
    env = make_env(task(), make_service('mock'), budget=10)
    env.evaluate()
    record = compact_record(dict(id='known', agent='agent-0', round=24, design={'': [50,3,3,.04]},
        measured=dict(valid=True, reward=3.5), rejected=None))
    findings = [dict(id='mem-'+str(i), sources=[{'sourceId': 'known'}], content='x'*2000) for i in range(100)]
    system, user, allowed, versions, stats = build_prompt(task(), env, 25, [], None, 24,
        findings, {'known': record}, max_input_bytes=12000)
    assert stats['input_bytes'] <= 12000
    assert stats['incumbent_included'] and 'known' in versions
    assert stats['omitted_memories'] > 0
    assert len([k for k in allowed if k.startswith('mem-')]) == stats['included_memories']


def test_input_overflow_stops_before_provider(tmp_path):
    calls = []
    class Policy:
        def call(self, *args): calls.append(1); return 'finish', {}
    root, summary = run_swarm(task(), make_service('mock'), NoMemory(), lambda *a: Policy(),
        tmp_path, n=1, rounds=1, max_input_bytes=100)
    assert summary['status'] == 'aborted'
    assert not calls and summary['backend_calls'] == 0


def test_recall_query_contains_actual_stream_chemistry_and_failed_settings():
    env = make_env(task(), make_service('mock'), budget=10)
    env.evaluate()
    env.design = {'B': (50, 3, 3, .04)}
    env.last['failed'] = ['B']
    query = recall_query(env, 'current-run')
    assert 'major_components' in query and any(name in query for name in env.names)
    assert '(50, 3, 3, 0.04)' in query and 'current-run' in query


@pytest.mark.parametrize('dirty', [False, True])
def test_past_checks_raw_clean_slate_before_ingestion(dirty):
    memory = PastMemory.__new__(PastMemory)
    calls = []
    def request(method, path, body=None):
        calls.append((method, path, body))
        return {'results': [{'id': 'old-project-visible', 'sources': [{'sourceId': 'old'}]}] if dirty else []}
    memory._request = request
    if dirty:
        with pytest.raises(RuntimeError, match='Clean-slate'):
            memory.start('fresh', ['a', 'b'])
        assert memory.clean_slate['raw_findings'] == 2
    else:
        memory.start('fresh', ['a', 'b'])
        assert memory.clean_slate['verified']
        with pytest.raises(ValueError, match='new PastMemory'):
            memory.start('fresh-again', ['a'])
    assert all(path != 'ingest' for _, path, _ in calls)
    assert calls[0][2]['identities'] == ['fresh-a', 'fresh-b']


def test_clean_slate_failure_stops_before_policy_or_simulator(tmp_path):
    memory = PastMemory.__new__(PastMemory)
    memory._request = lambda *a: {'results': [{'sources': [{'sourceId': 'foreign'}]}]}
    called = []
    root, summary = run_swarm(task(), make_service('mock'), memory,
        lambda *a: called.append(1), tmp_path, n=1, rounds=1)
    assert summary['status'] == 'aborted' and not called
    assert summary['backend_calls'] == 0
    assert not json.loads((root/'metrics/isolation.json').read_text())['verified']


def test_nonblocking_ingestion_keeps_pending_and_never_sleeps(monkeypatch):
    memory = PastMemory.__new__(PastMemory)
    memory.pending, memory.pending_since = ['job'], {'job': time.monotonic()}
    memory.timeout, memory.blocking = 300, False
    states = iter(['processing', 'completed'])
    memory._request = lambda *a: {'status': next(states)}
    monkeypatch.setattr('sepdesign.swarm_memory.time.sleep', lambda *a: pytest.fail('must not wait'))
    memory.barrier()
    assert memory.pending == ['job']
    memory.barrier()
    assert memory.pending == []


@pytest.mark.parametrize('single', [False, True])
def test_batch_every_point_is_scoped_and_small(single):
    memory = PastMemory.__new__(PastMemory)
    memory._request = lambda *a: {'results': []}
    memory.start('fresh', ['a', 'b'])
    requests = []
    def request(method, path, body):
        requests.append((path, body))
        return {'ingestionId': 'batch', 'items': [{'sourceId': p['id']} for p in body['items']]}
    memory._request = request
    records = [compact_record(dict(id='v'+str(i), agent=a, round=1, design={},
        measured=dict(valid=True, reward=i), rejected=None)) for i, a in enumerate(['a','b'])]
    if single:
        assert memory.publish(records[0]) == 'batch'
        records = records[:1]
    else:
        assert memory.publish_batch(records) == ['batch', 'batch']
    path, body = requests[0]
    assert path == 'ingest/batch' and len(body['items']) == len(records)
    assert all(p['audience'] == 'fresh' for p in body['items'])
    assert memory.sources == {r['id'] for r in records} and memory.pending == ['batch']


def test_free_cleanup_at_cap_is_measured_and_audited(tmp_path):
    class Policy:
        def call(self, *args): return 'submit_edits', {'edits': [edit(), edit('B')]}
    root, summary = run_swarm(task(), SolveService(SeparatingBackend()), ExactMemory(),
        lambda *a: Policy(), tmp_path, n=1, rounds=2, budget=1)
    assert summary['team_distinct_queries'] == summary['backend_calls'] == 1
    assert summary['agents']['agent-0']['best_valid_reward'] > 0
    rows = [json.loads(x) for x in (root/'raw/trajectory.jsonl').read_text().splitlines()]
    cleanup = next(e for e in rows if e['kind'] == 'budget_cleanup')
    assert cleanup['original_result']['unsolved_budget'] == ['B']
    assert cleanup['new_queries'] == 0
    assert cleanup['measured']['valid'] and cleanup['design'] == {'': [50,3.0,3.0,.04]}


@pytest.mark.parametrize('feature', ['side_draw', 'double_effect'])
def test_v3_optional_settings_survive_compaction_and_exact_copy(tmp_path, feature):
    from sepdesign.taskset import get_tasks
    from agents.llm_agent import edit_schema, FINISH_SCHEMA
    v3 = get_tasks('dev', 'hc16v3')[0]
    class Policy:
        def __init__(self, agent): self.agent, self.turn = agent, 0
        def call(self, system, user, env):
            self.turn += 1
            if self.turn == 1:
                settings = edit()
                settings[feature] = ({'stage': 15, 'phase': 'liquid', 'fraction': .1} if feature == 'side_draw'
                    else {'fraction': .5, 'low_pressure_drop_fraction': .6})
                return 'submit_edits', {'edits': [settings] if self.agent == 'agent-0' else []}
            if self.agent == 'agent-0': return 'finish', {}
            versions = json.loads(user.split('Retrieved complete design versions:\n')[1])
            source = next(k for k in versions if k.endswith('-agent-0-v1'))
            return 'submit_edits', {'source_design': source, 'evidence_ids': [source], 'edits': []}
    root, summary = run_swarm(v3, make_service('mock', task=v3), ExactMemory(),
        lambda a, *rest: Policy(a), tmp_path, n=2, rounds=2, budget=10)
    assert summary['status'] == 'round_limit'
    rows = [json.loads(x) for x in (root/'raw/trajectory.jsonl').read_text().splitlines()]
    copy = next(e for e in rows if e['kind'] == 'submission' and e['agent'] == 'agent-1' and e['round'] == 2)
    assert copy['measured']['valid'] and copy['rejected'] is None
    assert len(copy['design']['']) == (5 if feature == 'side_draw' else 6)
    prompt = json.loads((root/'raw/agent-1/prompts/round-0002.json').read_text())
    env = make_env(v3, make_service('mock', task=v3))
    assert prompt['diagnostics']['tool_schema_bytes'] == len(encoded([edit_schema(env), FINISH_SCHEMA]).encode())
