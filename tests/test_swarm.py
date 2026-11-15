import json
import pytest
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sepdesign.env import Stream
from sepdesign.service import SolveService, make_service
from sepdesign.swarm import allocations, run_swarm
from sepdesign.swarm_memory import LocalMemory, PastMemory
from scripts.run_swarm import PlumbingPolicy
from sepdesign.ledger import Ledger


def test_allocations():
    assert allocations(1) == [50]
    assert allocations(3) == [17,17,16]
    assert allocations(3,1) == [16,17,17]
    assert allocations(3,2) == [17,16,17]
    assert allocations(5) == [10]*5
    assert allocations(5,mode='equal-per-agent') == [50]*5


def test_single_flight_and_cached_failure():
    class Backend:
        calls = 0
        def solve_column(self, request):
            self.calls += 1
            time.sleep(.01)
            return {'success': False, 'error': 'no convergence', 'runtime_s': .01}
    backend = Backend()
    service = SolveService(backend)
    stream = Stream([1,2],300,100000)
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: service.column(stream, (50,3,3,.04)), range(8)))
    assert backend.calls == 1
    assert all(not r['ok'] for r in results)
    assert sum(e['cache_hit'] for e in service.events) == 7


def test_two_round_use_and_isolation(tmp_path):
    task = json.loads(Path('tasks/hc12_dev_000.json').read_text())
    def factory(a, directory, run_id):
        return PlumbingPolicy(Ledger(str(directory), run_id, a), a)
    root, summary = run_swarm(task, make_service('mock'), LocalMemory(), factory, tmp_path, n=2, rounds=2)
    assert summary['status'] == 'round_limit'
    events = [json.loads(line) for line in (root/'raw/trajectory.jsonl').read_text().splitlines()]
    copied = next(e for e in events if e['kind']=='submission' and e['agent']=='agent-1' and e['round']==2)
    assert copied['source_design'] in copied['evidence_ids']
    assert copied['design'][''][1] == 4
    assert copied['measured'] is not None
    other = LocalMemory()
    other.start('other', ['outsider'])
    assert other.recall('outsider') == []


def test_past_filters_mixed_and_foreign_sources():
    memory = PastMemory.__new__(PastMemory)
    memory.identities, memory.run_id, memory.sources = {'a':'reader'}, 'run', {'own'}
    memory._request = lambda *args: {'results': [
        {'sources':[{'sourceId':'own'}]}, {'sources':[{'sourceId':'foreign'}]},
        {'sources':[{'sourceId':'own'},{'sourceId':'foreign'}]}]}
    assert memory.recall('a') == [{'sources':[{'sourceId':'own'}]}]


def test_memory_failure_retains_summary(tmp_path):
    class Broken(LocalMemory):
        def barrier(self):
            raise TimeoutError('visibility')
    task = json.loads(Path('tasks/hc12_dev_000.json').read_text())
    root, summary = run_swarm(task, make_service('mock'), Broken(),
        lambda a,d,r: PlumbingPolicy(Ledger(str(d),r,a),a), tmp_path, n=1)
    assert summary['status']=='aborted'
    assert (root/'metrics/summary.json').exists()


def test_failed_distinct_queries_charge_share_and_do_not_borrow():
    from sepdesign.service import make_env
    task = json.loads(Path('tasks/hc12_dev_000.json').read_text())
    class Backend:
        def solve_column(self, request):
            return {'success':False, 'error':'no convergence', 'runtime_s':0}
    service = SolveService(Backend())
    a, b = [make_env(task, service, budget=1) for _ in range(2)]
    edit = dict(op='set', node='', n_stages=50, reflux_ratio=3, reboil_ratio=3, pressure_drop_fraction=.04)
    for env in (a,b):
        env.apply([edit])
        assert not env.evaluate()['valid']
        env.evaluate()
        assert env.solves_used == 1
    assert len(service.log) == 1
    a.apply([{**edit, 'reflux_ratio':4}])
    assert a.evaluate()['unsolved_budget'] == ['']
    assert len(service.log) == 1


def test_reused_cache_rejected(tmp_path):
    import pytest
    service = make_service('mock')
    service.events.append({'cache_hit':False})
    with pytest.raises(ValueError, match='fresh'):
        run_swarm({},service,LocalMemory(),None,tmp_path)


def test_past_failed_ingestion_stops():
    import pytest
    memory = PastMemory.__new__(PastMemory)
    memory.timeout, memory.pending = 1, ['ingestion-id']
    memory._request = lambda *args: {'status':'failed'}
    with pytest.raises(RuntimeError, match='ingestion failed'):
        memory.barrier()


def test_policy_failure_keeps_successful_peer(tmp_path):
    task = json.loads(Path('tasks/hc12_dev_000.json').read_text())
    class Policy:
        def __init__(self, agent, directory, run_id):
            self.agent = agent
            self.ledger = Ledger(str(directory), run_id, agent)
        def call(self, *args):
            self.ledger.record('request', 10, 2)
            if self.agent == 'agent-1':
                raise TimeoutError('provider unavailable')
            return 'submit_edits', {'edits': [], 'note': 'retain this reasoning'}
    service = make_service('mock')
    root, summary = run_swarm(task, service, LocalMemory(), Policy, tmp_path, n=2)
    rows = [json.loads(x) for x in (root/'raw/trajectory.jsonl').read_text().splitlines()]
    outcomes = {r['agent']: r for r in rows if r['kind']=='policy_outcome'}
    assert summary['status'] == 'aborted'
    assert outcomes['agent-0']['response']['note'] == 'retain this reasoning'
    assert outcomes['agent-1']['error'] == 'TimeoutError'
    assert all(r['model_s'] >= 0 and r['round']==1 for r in outcomes.values())
    assert summary['submissions'] == summary['backend_calls'] == 0
    assert all(a['usage']['requests']==1 and a['usage']['reconciled'] for a in summary['agents'].values())


def test_backend_outage_aborts_and_retains_accounting(tmp_path):
    from sepdesign.service import InfrastructureError
    import pytest
    class Backend:
        def solve_column(self, request):
            raise ConnectionError('outage')
    task = json.loads(Path('tasks/hc12_dev_000.json').read_text())
    service = SolveService(Backend())
    root, summary = run_swarm(task, service, LocalMemory(),
        lambda a,d,r: PlumbingPolicy(Ledger(str(d),r,a),a), tmp_path, n=1)
    assert summary['status']=='infrastructure_error'
    assert summary['backend_calls']==summary['team_distinct_queries']==1
    rows = [json.loads(x) for x in (root/'raw/trajectory.jsonl').read_text().splitlines()]
    failed = next(r for r in rows if r['kind']=='evaluation_failure')
    assert failed['agent']=='agent-0' and failed['design']
    assert failed['error_category']=='infrastructure'
    assert service.raw_responses[0]['error_category']=='infrastructure'
    # Replaying the cached failure must stay an infrastructure error, without a retry.
    q = next(iter(service.cache))
    flows, temp, pressure, *action = q
    with pytest.raises(InfrastructureError, match='ConnectionError'):
        service.column(Stream(flows,temp,pressure), action)
    assert len(service.log)==1 and service.events[-1]['cache_hit']


def test_memory_transport_failure_is_logged(monkeypatch):
    import urllib.error
    import ssl
    import pytest
    memory = PastMemory.__new__(PastMemory)
    memory.events, memory.key, memory.request_timeout = [], 'fake', 1
    memory.ssl_context = ssl.create_default_context()
    def fail(*args, **kwargs):
        assert kwargs['context'].verify_mode == ssl.CERT_REQUIRED
        raise urllib.error.URLError('certificate validation failed')
    monkeypatch.setattr('urllib.request.urlopen', fail)
    with pytest.raises(urllib.error.URLError):
        memory._request('POST','recall',{})
    assert memory.events[0]['ok'] is False
    assert memory.events[0]['error_type']=='URLError'


@pytest.mark.parametrize('valid_citation', [True, False])
def test_retrieved_memory_id_citation_is_valid_but_foreign_id_is_not(tmp_path, valid_citation):
    task = json.loads(Path('tasks/hc12_dev_000.json').read_text())
    class Memory(LocalMemory):
        def recall(self, agent, query=None):
            rows = super().recall(agent, query)
            for row in rows: row['id']='memory-'+row['id']
            return rows
    class Policy(PlumbingPolicy):
        def call(self, system, user, env=None):
            name, args = super().call(system, user, env)
            if self.turn==2 and self.agent=='agent-1':
                args['evidence_ids']=['memory-'+args['source_design'] if valid_citation else 'foreign-id']
            return name,args
    root,summary = run_swarm(task,make_service('mock'),Memory(),
        lambda a,d,r:Policy(Ledger(str(d),r,a),a),tmp_path,n=2,rounds=2)
    rows=[json.loads(x) for x in (root/'raw/trajectory.jsonl').read_text().splitlines()]
    copied=next(r for r in rows if r['kind']=='submission' and r['agent']=='agent-1' and r['round']==2)
    if valid_citation:
        assert copied['rejected'] is None
        assert copied['evidence_sources'][copied['evidence_ids'][0]] == [copied['source_design']]
    else:
        assert 'not retrieved' in copied['rejected']
        assert copied['measured'] is None


def test_v2_five_agents_have_independent_hundred_call_budgets(tmp_path):
    task = json.loads(Path('tasks/hc16v2_dev_000.json').read_text())
    observed = []
    class Policy:
        def call(self, system, user, env):
            assert 'BLENDS' in system and 'PREMIUM' in system
            assert len(env.names) == 16
            observed.append(env.solve_budget)
            return 'finish', {}
    root, result = run_swarm(task, make_service('mock', task=task), LocalMemory(),
        lambda *args: Policy(), tmp_path, n=5, rounds=2, mode='equal-per-agent', budget=100)
    assert observed == [100]*5
    assert json.loads((root/'config.json').read_text())['allocations'] == [100]*5
    assert (root/'report.html').exists()
    assert all((root/'raw'/f'agent-{i}'/'report.html').exists() for i in range(5))
    assert not (root/'report_failure.json').exists()


def test_custom_budget_allocations():
    assert allocations(5,mode='equal-per-agent',budget=100) == [100]*5
    assert allocations(3,mode='equal-total',budget=100) == [34,33,33]
    for invalid in (0,-1,1.2,True):
        with pytest.raises(ValueError): allocations(5,budget=invalid)
