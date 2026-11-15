import json
from agents.llm_agent import run_agent
from sepdesign import attach_trace, hc12_tasks, make_env, make_service, save_run
from sepdesign.report import build, collect


def test_persistent_run_generates_report_without_new_solves(tmp_path):
    task=hc12_tasks('dev')[0]
    env=make_env(task,make_service('mock'),budget=8)
    attach_trace(env)
    run_agent(env,task,provider='scripted',out_dir=str(tmp_path),run_id='report-test')
    used=env.solves_used
    folder=tmp_path/'report-test'
    save_run(str(folder/'replay.json'),env,task,'report-test',backend='mock')
    assert (folder/'report.html').exists()
    assert env.solves_used==used
    data=collect(folder)
    assert data['replay']['budget']==8
    assert data['replay']['trace']
    assert data['summary']['status']=='budget_exhausted'
    assert data['turns']
    data['turns'][0]['note']='</script><script>alert(1)</script>'
    html=build(folder,data).read_text()
    assert '</script><script>alert(1)</script>' not in html
    assert 'Flowsheet replay' in html


def test_report_failure_preserves_run_evidence(tmp_path, monkeypatch):
    task=hc12_tasks('dev')[0]
    env=make_env(task,make_service('mock'),budget=1)
    attach_trace(env)
    run_agent(env,task,provider='scripted',out_dir=str(tmp_path),run_id='report-failure')
    def fail(*args, **kwargs):
        raise OSError('report storage unavailable')
    monkeypatch.setattr('sepdesign.report.build',fail)
    folder=tmp_path/'report-failure'
    result=save_run(str(folder/'replay.json'),env,task,'report-failure')
    assert result['solves_used']==1
    assert json.loads((folder/'replay.json').read_text())['solves_used']==1
    assert json.loads((folder/'report_failure.json').read_text())['error_type']=='OSError'
