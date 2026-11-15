import importlib.util
import json
from pathlib import Path
import pytest

from agents import kimi

@pytest.mark.parametrize('base', ['https://inference.us-west.modal.direct', 'https://inference.us-west.modal.direct/v1/'])
def test_endpoint_normalization(base):
    assert kimi.endpoint_url(base) == 'https://inference.us-west.modal.direct/v1/chat/completions'

@pytest.mark.parametrize('base', ['http://test.modal.direct', 'https://modal.direct.evil.test', 'https://secret@test.modal.direct', 'https://test.modal.direct?key=secret'])
def test_credentials_only_go_to_modal(base):
    with pytest.raises(ValueError): kimi.endpoint_url(base)

def test_no_tool_is_not_success():
    with pytest.raises(ValueError):
        kimi.select_tool({'choices':[{'message':{}, 'finish_reason':'length'}]})

def test_parse_tool():
    r={'choices':[{'message':{'tool_calls':[{'function':{'name':'submit_edits','arguments':json.dumps({'edits':[]})}}]}}]}
    assert kimi.select_tool(r) == ('submit_edits', {'edits':[]})


def test_unknown_usage_is_failure_not_successful_spend_stop(tmp_path, monkeypatch):
    from agents import llm_agent
    from sepdesign.service import make_env, make_service
    task=json.loads(Path('tasks/hc16v2_dev_000.json').read_text())
    class Unknown:
        def __init__(self, model, ledger): self.ledger=ledger
        def call(self, *args):
            self.ledger.record(None,None,None,ok=False)
            raise RuntimeError('Transport failure')
    monkeypatch.setattr(llm_agent,'Kimi',Unknown)
    monkeypatch.setattr(llm_agent.time,'sleep',lambda _:None)
    env=make_env(task,make_service('mock',task=task),budget=200)
    result=llm_agent.run_agent(env,task,provider='modal',model='kimi-k3.1-pro',
        max_usd=20,out_dir=str(tmp_path),run_id='unknown')
    assert result['status']=='unknown_usage'
    assert result['requests']==1


def test_kimi_uses_verified_tls_and_records_usage(tmp_path, monkeypatch):
    import io
    import ssl
    from sepdesign.ledger import Ledger
    monkeypatch.setenv('MODAL_PROXY_TOKEN','test-token')
    monkeypatch.setenv('KIMI_ENDPOINT_URL','https://inference.us-west.modal.direct')
    monkeypatch.setenv('KIMI_MODEL','test-model')
    def response(request, timeout, context):
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert timeout == 180
        body=json.loads(request.data)
        assert body['model']=='test-model'
        return io.BytesIO(json.dumps({'id':'test','usage':{'prompt_tokens':100,'completion_tokens':20},
            'choices':[{'message':{'tool_calls':[{'function':{'name':'finish','arguments':'{}'}}]}}]}).encode())
    monkeypatch.setattr(kimi.urllib.request,'urlopen',response)
    ledger=Ledger(str(tmp_path),'run',model='kimi-k3.1-pro')
    assert kimi.Kimi('kimi-k3.1-pro',ledger).call('system','user') == ('finish',{})
    assert ledger.n == 1 and ledger.unknown == 0
    assert ledger.tok_in == 100 and ledger.tok_out == 20


@pytest.mark.parametrize('response,category', [
    ({'choices':[{'finish_reason':'length','message':{'tool_calls':[{'function':{'name':'finish','arguments':'{}'}}]}}]},'output_limit'),
    ({'choices':[{'message':{}}]},'missing_tool'),
    ({'choices':[]},'malformed_response'),
    ({'choices':[{'message':{'tool_calls':[{'function':{'name':'submit_edits','arguments':'{"edits":'}}]}}]},'invalid_tool_json'),
    ({'choices':[{'message':{'tool_calls':[{'function':{'name':'submit_edits','arguments':'{}'}}]}}]},'invalid_edits'),
])
def test_rejects_incomplete_responses(response,category):
    with pytest.raises(kimi.ToolResponseError) as exc:
        kimi.select_tool(response)
    assert exc.value.category == category


def test_truncation_stops_without_paid_retry_and_retains_usage(tmp_path,monkeypatch):
    import io
    from agents import llm_agent
    from sepdesign.service import make_env,make_service
    monkeypatch.setenv('MODAL_PROXY_TOKEN','secret-test-token')
    monkeypatch.setenv('KIMI_ENDPOINT_URL','https://inference.us-west.modal.direct')
    monkeypatch.setenv('KIMI_MODEL','test-model')
    calls=[]
    def response(request,**kw):
        body=json.loads(request.data);calls.append(body)
        assert body['reasoning_effort']=='low' and body['max_tokens']==16384
        return io.BytesIO(json.dumps({'id':'truncated','usage':{'prompt_tokens':100,'completion_tokens':16384},
            'choices':[{'finish_reason':'length','message':{'content':'private text'}}]}).encode())
    monkeypatch.setattr(kimi.urllib.request,'urlopen',response)
    task=json.loads(Path('tasks/hc16v2_dev_000.json').read_text())
    env=make_env(task,make_service('mock',task=task),budget=200)
    result=llm_agent.run_agent(env,task,provider='modal',model=kimi.MODEL,max_usd=20,out_dir=str(tmp_path),run_id='truncated')
    assert result['status']=='model_response_error: output_limit'
    assert len(calls)==result['requests']==result['failed_requests']==1
    assert result['output_tokens']==16384 and result['usd_estimated_total']>0
    assert env.solves_used==0
    log=(tmp_path/'truncated/response-diagnostics.jsonl').read_text()
    assert json.loads(log)['finish_reason']=='length'
    assert 'private text' not in log and 'secret-test-token' not in log
