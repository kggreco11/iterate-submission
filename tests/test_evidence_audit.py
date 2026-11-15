"""The audit must expose damaged evidence, not silently accept it or crash."""
import importlib.util
import json
from pathlib import Path
import subprocess

SPEC = importlib.util.spec_from_file_location('audit_evidence', Path(__file__).parents[1]/'scripts/audit_evidence.py')
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


def run_audit(tmp_path, monkeypatch, files):
    for path,data in files.items():
        dest=tmp_path/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(data)
    for args in [('init','-q'),('add','.'),('-c','user.name=Audit test','-c','user.email=audit@example.invalid','commit','-qm','fixture')]:
        subprocess.run(['git',*args],cwd=tmp_path,check=True)
    monkeypatch.setattr(audit_module,'ROOT',tmp_path)
    return audit_module.audit()


def usage(**updates):
    row=dict(run_id='run',agent_id='agent-0',model='model',provider='provider',request_id='req',ok=True,input_tokens=3,output_tokens=2,usd=0.1,cumulative_usd=0.1,cumulative_requests=1)
    return dict(row,**updates)


def test_valid_usage_reconciles_and_counts_every_line(tmp_path,monkeypatch):
    rows=[usage(),usage(request_id='req2',cumulative_usd=0.2,cumulative_requests=2)]
    result=run_audit(tmp_path,monkeypatch,{'results/run/usage.jsonl':'\n'.join(map(json.dumps,rows))+'\n','results/run/summary.json':json.dumps(dict(run_id='run',agent_id='agent-0',model='model',provider='provider',input_tokens=6,output_tokens=4,requests=2,usd_estimated_total=0.2))})
    assert result['findings']==[]
    assert result['totals']['jsonl_records']==2
    assert result['checks']['aggregate_comparisons']==4


def test_malformed_records_and_duplicate_keys_are_reported(tmp_path,monkeypatch):
    result=run_audit(tmp_path,monkeypatch,{'results/run/usage.jsonl':'null\n{broken\n'+json.dumps(usage(input_tokens='bad'))+'\n','results/run/summary.json':'{"requests":1,"requests":2}'})
    codes={f['code'] for f in result['findings']}
    assert {'invalid_json','record_type','duplicate_json_key','metric_type'} <= codes
    assert result['finding_counts']['error']>=3


def test_usage_mismatch_and_precise_line_location(tmp_path,monkeypatch):
    result=run_audit(tmp_path,monkeypatch,{'results/run/usage.jsonl':'\n'+json.dumps(usage(cumulative_usd=1))+'\n','results/run/summary.json':json.dumps(dict(requests=2,usd_estimated_total=1))})
    mismatch=next(f for f in result['findings'] if f['code']=='usage_cost_cumulative')
    assert mismatch['location']=='line:2'
    assert any(f['code']=='aggregate_mismatch' for f in result['findings'])


def test_projected_usage_and_unobserved_checkpoints(tmp_path,monkeypatch):
    report={'usage':[dict(elapsed_s=1,input_tokens=3,output_tokens=2,usd=.1,usd_label='estimate')]}
    result=run_audit(tmp_path,monkeypatch,{'results/report-data.json':json.dumps(report),'results/run/summary.json':json.dumps(dict(team_solves=4,best_at={'10':2}))})
    assert not result['finding_counts'].get('error')
    assert any(f['code']=='unobserved_checkpoint' for f in result['findings'])
    assert any(f['code']=='request_id_unavailable' for f in result['findings'])


def test_bad_summary_shapes_do_not_abort_scan(tmp_path,monkeypatch):
    result=run_audit(tmp_path,monkeypatch,{'results/run/usage.jsonl':json.dumps(usage(input_tokens='bad'))+'\n','results/run/summary.json':json.dumps(dict(input_tokens=3,agents={'agent-0':None},best_at=['bad'])),'results/run/config.json':'[]'})
    codes={f['code'] for f in result['findings']}
    assert {'metric_type','checkpoint_schema','config_schema'} <= codes


def test_published_team_inventory_matches_canonical_evidence():
    root=Path(__file__).parents[1]
    inventory={r['run_id']:r for r in json.loads((root/'results/results-so-far/runs.json').read_text())}
    reports=list((root/'results/hc16v3_dev_002').glob('team-*/*/*/report-data.json'))
    assert reports
    for path in reports:
        report=json.loads(path.read_text());config=report['config'];summary=report['summary']
        row=inventory[config['run_id']]
        assert row['budget_total']==sum(config['budgets'].values())
        assert row['agents']==len(config['budgets'])
        assert row['model_usd']==summary.get('usd_cached_price_estimate',summary.get('usd'))
        assert row['queries']==summary['team_solves']
        assert row['reward']==summary['team_best']


def test_malformed_embedded_exports_and_unhashable_request_id(tmp_path,monkeypatch):
    result=run_audit(tmp_path,monkeypatch,{
        'results/usage.jsonl':json.dumps(usage(request_id=['bad']))+'\n',
        'results/extract.json':json.dumps({'summary':{},'agents':{'a':None},'reconciliation':{}}),
        'results/team.json':json.dumps({'schema':'team-report-v1'}),
        'results/team-budgets.json':json.dumps({'schema':'team-report-v1','config':{'run_id':'x','budgets':{'a':'bad'}},'summary':{}}),
    })
    codes={f['code'] for f in result['findings']}
    assert {'request_id_type','export_schema','canonical_report_schema'} <= codes
    assert result['totals']['jsonl_records']==1
