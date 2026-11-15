import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from scripts.run_vm_agent import main
from sepdesign.runtime import SerialBackend, Timings


def test_persistent_loop_has_no_submission_transport(tmp_path):
    main(['--run-id', 'test', '--backend', 'mock', '--budget', '5', '--out', str(tmp_path)])
    run = tmp_path / 'test'
    report = json.loads((run / 'runtime.json').read_text())
    assert report['submission_transport_s'] == 0
    assert report['solver_retry'] is False
    assert report['service']['solves'] == 5
    assert report['phase_counts']['backend'] == 5
    assert report['phase_counts']['model'] > 0
    assert json.loads((run / 'status.json').read_text())['state'] == 'complete'
    assert len((run / 'simulator.jsonl').read_text().splitlines()) == 5


def test_serial_capacity_and_queue_measurement(tmp_path):
    class Backend:
        name = 'test'
        active = 0
        def solve_column(self, case):
            self.active += 1
            assert self.active == 1
            time.sleep(.03)
            self.active -= 1
            return dict(runtime_s=.03)
    timings = Timings(tmp_path / 'timings.jsonl')
    backend = SerialBackend(Backend(), timings, tmp_path / 'raw.jsonl')
    barrier = threading.Barrier(3)
    def solve(_):
        barrier.wait()
        return backend.solve_column({})
    with ThreadPoolExecutor(3) as pool:
        assert len(list(pool.map(solve, range(3)))) == 3
    assert timings.counts['backend'] == 3
    assert timings.totals['queue'] >= .06


def test_duplicate_run_is_rejected(tmp_path):
    import pytest
    args = ['--run-id', 'test', '--backend', 'mock', '--budget', '1', '--out', str(tmp_path)]
    main(args)
    with pytest.raises(FileExistsError):
        main(args)


def test_failure_marker(tmp_path, monkeypatch):
    import pytest
    def fail(*args, **kwargs):
        raise RuntimeError('sensitive provider error')
    monkeypatch.setattr('scripts.run_vm_agent.make_service', fail)
    with pytest.raises(RuntimeError):
        main(['--run-id', 'failed', '--out', str(tmp_path)])
    text = (tmp_path / 'failed' / 'failure.json').read_text()
    assert 'RuntimeError' in text
    assert 'sensitive' not in text


def test_bundle_contains_source_only():
    import io
    import zipfile
    from scripts.azure_runtime import bundle
    with zipfile.ZipFile(io.BytesIO(bundle())) as z:
        names = z.namelist()
        assert 'scripts/run_vm_agent.py' in names
        assert 'agents/llm_agent.py' in names
        assert 'sepdesign/data/column_pr76.sep.tmpl' in names
        assert 'sepdesign/data/cost_params.json' in names
        assert all(not n.startswith('runs/') and '.env' not in n for n in names)


def test_active_pilot_blocks_control_plane(tmp_path, monkeypatch):
    import pytest
    import sys
    from scripts import azure_runtime
    monkeypatch.setattr(sys, 'argv', ['azure_runtime', 'launch', '--run-id', 'test', '--pilot-dir', str(tmp_path)])
    monkeypatch.setattr(azure_runtime, 'invoke', lambda *args: pytest.fail('must not call Azure'))
    with pytest.raises(SystemExit):
        azure_runtime.main()


def test_response_requires_exact_operation_marker(tmp_path, monkeypatch):
    import re
    import subprocess
    import pytest
    from scripts import azure_runtime
    monkeypatch.setenv('AZURE_RESOURCE_GROUP', 'test-resource-group')
    responses = []
    def fake_run(args, **kwargs):
        assert args[args.index('--resource-group') + 1] == 'test-resource-group'
        script = args[args.index('--scripts') + 1]
        marker = re.search(r'RUNTIME:test:status:[a-f0-9]+=', script).group()
        responses.append(marker)
        return subprocess.CompletedProcess(args, 0, json.dumps({'value':[{'message': marker+'ok'}]}), '')
    monkeypatch.setattr(azure_runtime.subprocess, 'run', fake_run)
    assert azure_runtime.invoke("Write-Output 'RUNTIME=ok'", tmp_path/'log', 'status', run_id='test') == 'ok'
    stale = responses[0]
    monkeypatch.setattr(azure_runtime.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], 0, json.dumps({'value':[{'message':stale+'ok'}]}), ''))
    with pytest.raises(RuntimeError, match='mismatched'):
        azure_runtime.invoke("Write-Output 'RUNTIME=ok'", tmp_path/'log', 'status', run_id='test')


def test_returned_api_error_is_failed(tmp_path, monkeypatch):
    monkeypatch.setattr('scripts.run_vm_agent.run_agent', lambda *a, **kw: {'status':'api_error: TimeoutError'})
    main(['--run-id','api-failure','--backend','mock','--out',str(tmp_path)])
    status=json.loads((tmp_path/'api-failure/status.json').read_text())
    assert status['state']=='failed'
    assert status['stop_reason']=='api_error: TimeoutError'
    assert (tmp_path/'api-failure/failure.json').exists()


def test_unknown_paid_price_stops_before_backend_or_provider(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setattr('scripts.run_vm_agent.make_service', lambda *a, **kw: pytest.fail('must fail before backend'))
    with pytest.raises(ValueError, match='known model pricing'):
        main(['--run-id','unknown-price','--provider','openai','--model','unpriced-model','--max-usd','1','--out',str(tmp_path)])
    assert json.loads((tmp_path/'unknown-price/status.json').read_text())['state']=='failed'


def test_unpriced_model_allowed_without_spend_enforcement(tmp_path, monkeypatch):
    seen = {}
    def fake_agent(*args, **kwargs):
        seen.update(kwargs)
        return {'status': 'finished'}
    monkeypatch.setattr('scripts.run_vm_agent.run_agent', fake_agent)
    main(['--run-id','no-cap','--backend','mock','--provider','openai','--model','unpriced-model','--out',str(tmp_path)])
    assert seen['max_usd'] is None
    assert json.loads((tmp_path/'no-cap/status.json').read_text())['state']=='complete'


def test_backend_exception_preserves_partial_evidence(tmp_path, monkeypatch):
    import pytest
    from sepdesign.mock_backend import MockBackend
    original=MockBackend.solve_column
    count=0
    def fail_second(self, case):
        nonlocal count
        count+=1
        if count==2: raise ConnectionError('original failure')
        return original(self, case)
    monkeypatch.setattr(MockBackend,'solve_column',fail_second)
    from sepdesign.service import InfrastructureError
    with pytest.raises(InfrastructureError,match='ConnectionError'):
        main(['--run-id','partial','--backend','mock','--budget','5','--out',str(tmp_path)])
    run=tmp_path/'partial'
    usage=[json.loads(x) for x in (run/'usage.jsonl').read_text().splitlines()]
    summary=json.loads((run/'summary.json').read_text())
    assert len(usage)==summary['requests']==2
    assert summary['input_tokens']==sum(x['input_tokens'] for x in usage)
    assert summary['output_tokens']==sum(x['output_tokens'] for x in usage)
    assert json.loads((run/'status.json').read_text())['state']=='failed'
    assert json.loads((run/'replay.json').read_text())['partial']
    assert json.loads((run/'runtime.json').read_text())['service']['solves']==2
    attempts=[json.loads(x) for x in (run/'turns.jsonl').read_text().splitlines()]
    assert attempts[-1]['action']=='failed' and attempts[-1]['design']
    assert len((run/'simulator.jsonl').read_text().splitlines())==2


def test_vm_v2_task_and_report(tmp_path):
    main(['--run-id','v2','--backend','mock','--budget','5','--out',str(tmp_path),
          '--task','tasks/hc16v2_dev_000.json'])
    run = tmp_path/'v2'
    replay = json.loads((run/'replay.json').read_text())
    assert replay['task'] == 'hc16v2_dev_000'
    assert len(replay['components']) == 16
    assert replay['budget'] == replay['solves_used'] == 5
    assert (run/'report.html').exists()
    assert all('kind' in p for t in replay['trace'] for p in t['products'])
