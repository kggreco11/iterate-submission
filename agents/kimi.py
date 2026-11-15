"""Modal Kimi policy shared by single-agent and swarm runners; no HTTP retries."""
import json
import os
import ssl
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlparse

MODEL = 'kimi-k3.1-pro'
MAX_OUTPUT_TOKENS = 16384
REASONING_EFFORT = 'low'


class ToolResponseError(ValueError):
    def __init__(self, category):
        self.category = category
        self.stop_reason = 'model_response_error: ' + category
        super().__init__(category)


def endpoint_url(value):
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or not parsed.hostname.endswith('.modal.direct'):
        raise ValueError('Expected an HTTPS Modal endpoint')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Endpoint must not contain credentials, query or fragment')
    return value.rstrip('/') + ('' if parsed.path.rstrip('/').endswith('/v1') else '/v1') + '/chat/completions'


def request_body(model, system, user, tools):
    return dict(model=model, messages=[{'role': 'system', 'content': system},
        {'role': 'user', 'content': user}], tools=tools, tool_choice='auto', max_tokens=MAX_OUTPUT_TOKENS,
        reasoning_effort=REASONING_EFFORT)


def select_tool(response):
    try:
        choice = response['choices'][0]
        if choice.get('finish_reason') == 'length':
            raise ToolResponseError('output_limit')
        calls = choice['message'].get('tool_calls') or []
        if len(calls) != 1:
            raise ToolResponseError('missing_tool' if not calls else 'multiple_tools')
        tool = calls[0]['function']
        if tool['name'] not in {'submit_edits', 'finish'}:
            raise ToolResponseError('unknown_tool')
        try:
            args = json.loads(tool['arguments'])
        except (ValueError, TypeError):
            raise ToolResponseError('invalid_tool_json') from None
        if not isinstance(args, dict):
            raise ToolResponseError('invalid_tool_arguments')
        if tool['name'] == 'submit_edits' and (not isinstance(args.get('edits'), list)
                or not all(isinstance(e, dict) for e in args['edits'])):
            raise ToolResponseError('invalid_edits')
        return tool['name'], args
    except (KeyError, IndexError, TypeError, AttributeError):
        raise ToolResponseError('malformed_response') from None


class Kimi:
    def __init__(self, model, ledger):
        from agents.llm_agent import EDIT_SCHEMA, FINISH_SCHEMA
        if model != MODEL:
            raise ValueError('Unsupported Modal model alias')
        self.ledger = ledger
        if sys.platform == 'win32':
            import truststore
            self.ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            self.ssl_context = ssl.create_default_context()
        self.key = os.environ['MODAL_PROXY_TOKEN']
        self.url = endpoint_url(os.environ['KIMI_ENDPOINT_URL'])
        self.model = os.environ['KIMI_MODEL']  # Exact model identifier from /v1/models/dashboard.
        self.tools = [{'type': 'function', 'function': dict(name=name, description=desc, parameters=schema)}
            for name, desc, schema in [('submit_edits', 'Edit the design, then re-simulate.', EDIT_SCHEMA),
                                      ('finish', 'Stop.', FINISH_SCHEMA)]]

    def call(self, system, user, env=None):
        from agents.llm_agent import edit_schema
        self.tools[0]['function']['parameters'] = edit_schema(env)
        request = urllib.request.Request(self.url,
            data=json.dumps(request_body(self.model, system, user, self.tools)).encode(),
            headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json',
                     'Modal-Routing-Affinity-Key': self.ledger.run_id + '-' + self.ledger.agent_id})
        try:
            with urllib.request.urlopen(request, timeout=180, context=self.ssl_context) as stream:
                response = json.load(stream)
        except Exception as exc:
            self.ledger.record(None, None, None, ok=False, error=type(exc).__name__)
            raise RuntimeError('Modal request failed: ' + type(exc).__name__) from None
        if not isinstance(response, dict):
            response = {}
        usage = response.get('usage') or {}
        if not isinstance(usage, dict):
            usage = {}
        parsed, failure = None, None
        try:
            parsed = select_tool(response)
        except ToolResponseError as exc:
            failure = exc
        # Record charged tokens even when the response cannot be executed.
        self.ledger.record(response.get('id'), usage.get('prompt_tokens'), usage.get('completion_tokens'),
            cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens'),
            reasoning=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens'),
            ok=failure is None, error=failure.category if failure else None)
        choices = response.get('choices') or []
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = choice.get('message') or {}
        if not isinstance(message, dict):
            message = {}
        diagnostic = dict(request_id=response.get('id'), request_number=self.ledger.n,
            finish_reason=choice.get('finish_reason'), error=failure.category if failure else None,
            max_output_tokens=MAX_OUTPUT_TOKENS, reasoning_effort=REASONING_EFFORT,
            input_tokens=usage.get('prompt_tokens'), provider_truncation_policy='unreported',
            tool_count=len(message.get('tool_calls') or []),
            completion_tokens=usage.get('completion_tokens'),
            reasoning_tokens=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens'))
        with (Path(self.ledger.dir) / 'response-diagnostics.jsonl').open('a') as f:
            f.write(json.dumps(diagnostic) + '\n')
        if failure:
            raise failure
        return parsed
