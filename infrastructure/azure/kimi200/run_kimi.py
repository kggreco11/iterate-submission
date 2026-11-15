"""Modal Kimi adapter for the frozen Sol 200-solve runtime."""
import json
import os
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
MODEL = 'kimi-k3.1-pro'


def endpoint_url(value):
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.modal.direct'):
        raise ValueError('Expected an HTTPS Modal endpoint')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Endpoint must not contain credentials, query or fragment')
    return value.rstrip('/') + ('' if parsed.path.rstrip('/').endswith('/v1') else '/v1') + '/chat/completions'


def request_body(model, system, user, tools):
    return dict(model=model, messages=[{'role': 'system', 'content': system},
        {'role': 'user', 'content': user}], tools=tools, tool_choice='auto', max_tokens=6000)


def select_tool(response):
    calls = response['choices'][0]['message'].get('tool_calls') or []
    if not calls:
        raise ValueError('No tool call: ' + str(response['choices'][0].get('finish_reason')))
    tool = calls[0]['function']
    if tool['name'] not in {'submit_edits', 'finish'}:
        raise ValueError('Unknown tool')
    args = json.loads(tool['arguments'])
    if not isinstance(args, dict):
        raise ValueError('Tool arguments must be an object')
    return tool['name'], args


class Kimi:
    def __init__(self, model, ledger):
        from agents.llm_agent import EDIT_SCHEMA, FINISH_SCHEMA
        self.ledger = ledger
        self.key = os.environ['MODAL_PROXY_TOKEN']
        self.url = endpoint_url(os.environ['KIMI_ENDPOINT_URL'])
        self.model = os.environ['KIMI_MODEL']  # Exact model identifier from /v1/models/dashboard.
        self.tools = [{'type': 'function', 'function': dict(name=name, description=desc, parameters=schema)}
            for name, desc, schema in [('submit_edits', 'Edit the design, then re-simulate.', EDIT_SCHEMA),
                                      ('finish', 'Stop.', FINISH_SCHEMA)]]

    def call(self, system, user, env=None):
        request = urllib.request.Request(self.url,
            data=json.dumps(request_body(self.model, system, user, self.tools)).encode(),
            headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json',
                     'Modal-Routing-Affinity-Key': self.ledger.run_id})
        try:
            with urllib.request.urlopen(request, timeout=180) as stream:
                response = json.load(stream)
        except Exception as exc:
            self.ledger.record(None, None, None, ok=False, error=type(exc).__name__)
            raise RuntimeError('Modal request failed: ' + type(exc).__name__) from None
        usage = response.get('usage', {})
        # Uncached rates give a conservative estimate. Do not label this as billed cost.
        self.ledger.record(response.get('id'), usage.get('prompt_tokens'), usage.get('completion_tokens'),
            cached=usage.get('prompt_tokens_details', {}).get('cached_tokens'),
            reasoning=usage.get('completion_tokens_details', {}).get('reasoning_tokens'))
        return select_tool(response)


def main():
    from agents import llm_agent
    import run_vm_agent
    from sepdesign import ledger
    ledger.PRICES[MODEL] = (2.0, 10.0)
    ledger.PRICE_SOURCE = 'https://modal.com/docs/guide/supported-models; checked 2026-11-14; uncached estimate'
    llm_agent._OpenAI = Kimi
    run_vm_agent.main()


if __name__ == '__main__':
    main()
