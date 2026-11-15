import base64
import gzip
import hashlib
import json
from pathlib import Path
import pytest
from sepdesign.report_archive import publish, publish_swarm
from scripts import finalize_vm_report as exporter


def payload(run='test-run'):
    return dict(summary=dict(run_id=run,model='model',task='task',status='budget_exhausted'),
        replay=dict(task='task',budget=1,solves_used=1,best_reward=0,trace=[],upper_bound_reward=1),
        turns=[],usage=[],status={'state':'complete'},runtime={'phase_seconds':{'model':2},'credential':'private'},
        controller={'secret':'private'})


def test_publish_rebuilds_html_and_index_without_exporting_controller(tmp_path):
    data=payload(); path=publish(data,tmp_path)
    assert path == tmp_path/'results/task/single-agent/model/test-run/index.html'
    assert 'Flowsheet replay' in path.read_text()
    assert 'private' not in (path.parent/'report-data.json').read_text()
    assert json.loads((path.parent/'report-data.json').read_text())['runtime']['phase_seconds']['model']==2
    manifest=json.loads((path.parent/'manifest.json').read_text())
    assert all(hashlib.sha256((path.parent/name).read_bytes()).hexdigest()==digest for name,digest in manifest['sha256'].items())
    assert 'task/single-agent/model/test-run/index.html' in (tmp_path/'results/index.html').read_text()
    path.unlink()
    assert publish(data,tmp_path).exists()
    assert (tmp_path/'results/README.md').read_text().count('| test-run |')==1


def test_unsafe_paths_rejected(tmp_path):
    with pytest.raises(ValueError):publish(payload('../escape'),tmp_path)
    assert not (tmp_path/'escape').exists()


def test_export_renders_locally_and_reuses_verified_download(tmp_path,monkeypatch):
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    p=tmp_path/'controller.json'
    p.write_text(json.dumps(dict(task='task',model='model',run_id='test-run',remote='C:\\runtime')))
    blob=gzip.compress(json.dumps(payload()).encode())
    calls=[]
    def remote(code):
        calls.append(code)
        if 'payload=gzip.compress' in code:
            return json.dumps({'size':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
        return base64.b64encode(blob).decode()
    monkeypatch.setattr(exporter,'remote',remote)
    report=exporter.finalize(p)
    assert report.exists() and 'results' in report.parts
    assert all('build(run' not in code and 'report.py).write' not in code for code in calls)
    report.unlink()
    count=len(calls)
    assert exporter.finalize(p).exists()
    assert len(calls)==count


def test_failed_export_checksum_does_not_publish(tmp_path,monkeypatch):
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    p=tmp_path/'controller.json';p.write_text(json.dumps(dict(task='task',model='model',run_id='test-run',remote='C:\\runtime')))
    responses=iter([json.dumps({'size':3,'sha256':'incorrect'}),base64.b64encode(b'bad').decode()])
    monkeypatch.setattr(exporter,'remote',lambda _:next(responses))
    with pytest.raises(RuntimeError,match='checksum'):exporter.finalize(p)
    assert not (tmp_path/'results').exists()


def test_swarm_bundle_links_each_agent_and_does_not_duplicate_trials(tmp_path):
    summary=dict(run_id='team',status='round_limit',team_distinct_queries=2,backend_calls=1,
        agents={'agent-0':dict(distinct_queries=1,best_valid_reward=0),'agent-1':dict(distinct_queries=1,best_valid_reward=0)})
    data=dict(summary=summary,config={'task':'task','model':'model'},agents={a:payload(a) for a in summary['agents']})
    report=publish_swarm(data,tmp_path)
    for a in summary['agents']:
        assert (report.parent/'agents'/a/'index.html').exists()
        assert f'agents/{a}/index.html' in report.read_text()
    assert len(list((tmp_path/'results').glob('*/*/*/*/manifest.json')))==1


def test_terminal_build_automatically_archives_but_running_snapshot_does_not(tmp_path,monkeypatch):
    from sepdesign import report
    monkeypatch.setattr(report,'__file__',str(tmp_path/'sepdesign/report.py'))
    run=tmp_path/'runs/runtime/test-run'
    data=payload();data['status']={'state':'running'}
    report.build(run,data)
    assert not (tmp_path/'results').exists()
    data['status']={'state':'complete'}
    report.build(run,data)
    assert (tmp_path/'results/task/single-agent/model/test-run/index.html').exists()


def test_swarm_export_renders_all_agent_pages_locally(tmp_path,monkeypatch):
    monkeypatch.setattr(exporter,'ROOT',tmp_path)
    p=tmp_path/'controller.json';p.write_text(json.dumps(dict(task='task',run_id='pair',remote='C:\\runtime')))
    summary=dict(run_id='team',status='round_limit',team_distinct_queries=1,backend_calls=1,
        agents={'agent-0':dict(distinct_queries=1,best_valid_reward=0)})
    data=dict(summary=summary,config={'task':'task','model':'model'},agents={'agent-0':payload()})
    blob=gzip.compress(json.dumps(data).encode())
    responses=iter([json.dumps({'size':len(blob),'sha256':hashlib.sha256(blob).hexdigest()}),base64.b64encode(blob).decode()])
    monkeypatch.setattr(exporter,'remote',lambda _:next(responses))
    report=exporter.finalize_swarm(p)
    assert (report.parent/'agents/agent-0/index.html').exists()
    assert exporter.finalize_swarm(p)==report


def test_comparison_uses_best_agent_and_survives_refresh(tmp_path):
    from sepdesign.swarm_report import single_metrics
    single=payload();single['replay'].update(best_reward=3,reward_norm=100,wall_s=60)
    summary=dict(run_id='team',status='complete',team_distinct_queries=2,backend_calls=2,wall_s=120,
        agents={'agent-0':dict(distinct_queries=1,best_valid_reward=2),
                'agent-1':dict(distinct_queries=1,best_valid_reward=1)})
    data=dict(summary=summary,config={'task':'task','model':'model'},agents={a:payload(a) for a in summary['agents']})
    for d in data['agents'].values():d['replay']['reward_norm']=100
    data['comparison']={'single':single_metrics(single)}
    report=publish_swarm(data,tmp_path)
    assert '33.33% lower than' in report.read_text()  # max=2, not the summed score of 3
    del data['comparison']
    publish_swarm(data,tmp_path)
    assert '33.33% lower than' in report.read_text()
    data['comparison']={'single':{**single_metrics(single),'task':'different'}}
    before=report.read_bytes()
    with pytest.raises(ValueError,match='must match'):publish_swarm(data,tmp_path)
    assert report.read_bytes()==before


def test_zero_baseline_and_fresh_clone_regeneration(tmp_path):
    from sepdesign.swarm_report import single_metrics
    from scripts.sync_reports import migrate
    single=payload();single['replay'].update(reward_norm=100,wall_s=60)
    single_report=publish(single,tmp_path)
    summary=dict(run_id='team',status='complete',team_distinct_queries=1,backend_calls=1,wall_s=120,
        agents={'agent-0':dict(distinct_queries=1,best_valid_reward=2)})
    agent=payload();agent['replay']['reward_norm']=100
    data=dict(summary=summary,config={'task':'task','model':'model'},agents={'agent-0':agent},
        comparison={'single':single_metrics(single)})
    report=publish_swarm(data,tmp_path)
    assert 'baseline reward is zero' in report.read_text()
    report.unlink();single_report.unlink()
    migrate(tmp_path)
    assert single_report.exists()
    assert 'baseline reward is zero' in report.read_text()


@pytest.mark.parametrize('single_state,swarm_state', [('running','complete'),('complete','running'),('failed','complete')])
def test_comparison_rejects_unfinished_or_failed_inputs(tmp_path,single_state,swarm_state):
    from scripts.compare_reports import compare
    single=payload();single['status']['state']=single_state
    swarm={'summary':{'status':swarm_state}}
    a=tmp_path/'single.json';b=tmp_path/'swarm.json'
    a.write_text(json.dumps(single));b.write_text(json.dumps(swarm))
    with pytest.raises(ValueError,match='requires completed'):compare(a,b,tmp_path)
    assert not (tmp_path/'results').exists()


def test_comparison_bundle_is_indexed_without_single_run_regeneration(tmp_path):
    from scripts.sync_reports import migrate
    folder = tmp_path/'results/task/comparison/model/analysis'
    folder.mkdir(parents=True)
    manifest = dict(schema='v3-analysis-bundle-v1', run_id='analysis', task='task',
                    condition='comparison', model='model', status='includes early-stopped control')
    (folder/'manifest.json').write_text(json.dumps(manifest))
    (folder/'report-data.json').write_text(json.dumps({'runs': [], 'independent_partial': {}}))
    (folder/'index.html').write_text('Preserved comparison report')
    migrate(tmp_path)
    assert (folder/'index.html').read_text() == 'Preserved comparison report'
    assert 'includes early-stopped control' in (tmp_path/'results/README.md').read_text()
    assert 'task/comparison/model/analysis/index.html' in (tmp_path/'results/index.html').read_text()
