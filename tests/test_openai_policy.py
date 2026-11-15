from types import SimpleNamespace as NS
from agents.llm_agent import _OpenAI
from sepdesign.ledger import Ledger


def test_responses_tool_call_and_usage(tmp_path):
    policy = _OpenAI.__new__(_OpenAI)
    policy.model = 'gpt-6.1-sol'
    policy.ledger = Ledger(str(tmp_path), 'test')
    policy.tools = [{'type':'function','function':{'name':'submit_edits','parameters':{'type':'object'}}}]
    def create(**kwargs):
        assert kwargs['reasoning']=={'effort':'low'}
        assert kwargs['parallel_tool_calls'] is False
        assert kwargs['tools'][0]['name']=='submit_edits'
        assert kwargs['store'] is False
        return NS(id='r', usage=NS(input_tokens=100, output_tokens=20,
            input_tokens_details=NS(cached_tokens=50), output_tokens_details=NS(reasoning_tokens=10)),
            output=[NS(type='reasoning'),NS(type='function_call',name='submit_edits',arguments='{"edits": []}')])
    policy.c = NS(responses=NS(create=create))
    assert policy.call('system','user') == ('submit_edits', {'edits':[]})
    assert policy.ledger.tok_in==100 and policy.ledger.tok_out==20
