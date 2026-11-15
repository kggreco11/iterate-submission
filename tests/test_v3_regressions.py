"""Regression coverage for PR10's task boundaries and saved evidence workflow."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from sepdesign import make_env, make_service
from sepdesign.taskset import get_tasks
from agents.llm_agent import edit_schema, EDIT_SCHEMA


def env_for(family):
    task=get_tasks('dev',family)[0]
    service=make_service('mock',task=task)
    return make_env(task,service),service


def test_tool_schema_changes_do_not_leak_between_task_families():
    v3,_=env_for('hc16v3');v2,_=env_for('hc16v2');v1,_=env_for('hc12')
    def props(env):return edit_schema(env)['properties']['edits']['items']['properties']
    assert {'side_draw','double_effect'} <= props(v3).keys()
    for e in (v2,v1,None):
        assert edit_schema(e)==EDIT_SCHEMA
        assert not {'side_draw','double_effect'} & props(e).keys()
    props(v3)['side_draw']['properties'].clear()
    assert props(v3)['side_draw']['properties']  # deep copies protect future requests


@pytest.mark.parametrize('spec',[(60,3,3,0,None,(.5,.6)),(60,3,3,0,(20,'liquid',.1))])
def test_saved_v2_design_cannot_use_v3_features(spec):
    env,_=env_for('hc16v2');env.design={'':spec}
    assert not env.evaluate()['valid']
    assert env.best is None


@pytest.mark.parametrize('spec',[(60,3,3,0,(30,'liquid',.1)),(60,3,3,0,(20,'liquid',.7)),
                                  (60,3,3,0,None,(.1,.6))])
def test_saved_v3_design_obeys_optional_bounds(spec):
    env,_=env_for('hc16v3');env.design={'':spec}
    assert not env.evaluate()['valid']


@pytest.mark.parametrize('mode',['nan','raises','missing'])
def test_failed_real_thermodynamics_invalidates_pair(mode):
    env,service=env_for('hc16v3')
    def mix(*args):
        if mode=='raises':raise ValueError('flash failed')
        return float('nan')
    service.backend_name='chemsep'
    if mode!='missing':service.backend.family=SimpleNamespace(thermo=SimpleNamespace(mix_T=mix))
    env.design={'':(60,3,3,0,None,(.5,.6))}
    result=env.evaluate()
    assert not result['valid'] and result['failed']==['']
    assert 'Adiabatic mixing failed' in result['nodes']['']['error']
    assert env.best is None


def test_timing_wrapper_keeps_thermodynamics(tmp_path):
    from sepdesign.runtime import SerialBackend
    from sepdesign.service import SolveService
    thermo=SimpleNamespace(mix_T=lambda streams,p:275.)
    backend=SimpleNamespace(name='chemsep',family=SimpleNamespace(thermo=thermo),cost_model=None)
    wrapped=SerialBackend(backend,None,tmp_path/'evidence.jsonl')
    assert SolveService(wrapped).mix([([1],300,100000),([1],400,90000)])==(275.,90000.)


def test_canonical_collector_has_completed_swarm_and_all_agent_designs():
    from scripts.collect_results import canonical_rows
    designs=[];rows=canonical_rows(designs)
    swarm=next(r for r in rows if r['condition']=='shared-memory-5' and r['model']=='kimi-k3.1-pro')
    assert swarm['solves_used']==454
    assert swarm['reward']==pytest.approx(3.356596375168566)
    assert swarm['status']=='all_finished_or_exhausted'
    assert len([d for d in designs if d['run_id']==swarm['run_id']])==5


def test_v3_html_discovery_without_local_runs(tmp_path):
    from scripts.sync_reports import migrate
    folder=tmp_path/'results/hc16v3-first-look/opus-5-5';folder.mkdir(parents=True)
    run='test-v3';logs=folder/run;logs.mkdir()
    replay=dict(task='hc16v3_dev_000',trace=[],solves_used=1,budget=1,best_reward=0,upper_bound_reward=1)
    (folder/(run+'.json')).write_text(json.dumps(replay))
    (logs/'summary.json').write_text(json.dumps(dict(run_id=run,task=replay['task'],model='opus',status='finish')))
    migrate(tmp_path)
    assert (tmp_path/'results/hc16v3_dev_000/single-agent/opus/test-v3/index.html').exists()


@pytest.mark.parametrize('provider',['anthropic','openai','kimi'])
def test_actual_adapter_request_switches_schema_per_task(provider,tmp_path,monkeypatch):
    import io
    from agents import llm_agent,kimi
    calls=[]
    ledger=SimpleNamespace(record=lambda *a,**k:None,run_id='test',agent_id='agent',n=1,dir=tmp_path)
    if provider=='anthropic':
        policy=llm_agent._Anthropic.__new__(llm_agent._Anthropic)
        response=SimpleNamespace(id='r',usage=SimpleNamespace(input_tokens=1,output_tokens=1),content=[SimpleNamespace(type='tool_use',name='finish',input={})])
        def create(**kwargs):calls.append(kwargs['tools'][0]['input_schema']);return response
        policy.c=SimpleNamespace(messages=SimpleNamespace(create=create));policy.tools=[{'input_schema':EDIT_SCHEMA}]
    elif provider=='openai':
        policy=llm_agent._OpenAI.__new__(llm_agent._OpenAI)
        response=SimpleNamespace(id='r',usage=SimpleNamespace(input_tokens=1,output_tokens=1),output=[SimpleNamespace(type='function_call',name='finish',arguments='{}')])
        def create(**kwargs):calls.append(kwargs['tools'][0]['parameters']);return response
        policy.c=SimpleNamespace(responses=SimpleNamespace(create=create));policy.tools=[{'function':{'name':'submit_edits','parameters':EDIT_SCHEMA}}]
    else:
        policy=kimi.Kimi.__new__(kimi.Kimi)
        policy.url='https://test.modal.direct/v1/chat/completions';policy.key='test-only';policy.ssl_context=None
        policy.tools=[{'type':'function','function':{'name':'submit_edits','parameters':EDIT_SCHEMA}}]
        def urlopen(req,**kwargs):
            calls.append(json.loads(req.data)['tools'][0]['function']['parameters'])
            return io.BytesIO(json.dumps({'choices':[{'finish_reason':'tool_calls','message':{'tool_calls':[{'function':{'name':'finish','arguments':'{}'}}]}}], 'usage':{'prompt_tokens':1,'completion_tokens':1}}).encode())
        monkeypatch.setattr(kimi.urllib.request,'urlopen',urlopen)
    policy.ledger=ledger;policy.model='test-model'
    for family in ['hc16v3','hc16v2','hc12']:
        policy.call('system','state',env_for(family)[0])
    options=lambda schema:schema['properties']['edits']['items']['properties']
    assert 'side_draw' in options(calls[0]) and 'double_effect' in options(calls[0])
    assert calls[1]==calls[2]==EDIT_SCHEMA
