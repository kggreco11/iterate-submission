"""Opus adapter over the frozen Sol runtime; same prompt, environment and solve budget."""
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))


def request_body(model, system, user, tools):
    return dict(model=model, max_tokens=6000, system=system, tools=tools,
                tool_choice={'type': 'auto'}, output_config={'effort': 'medium'},
                messages=[{'role': 'user', 'content': user}])


def select_tool(response):
    for block in response.get('content', []):
        if block.get('type') == 'tool_use':
            if block.get('name') not in {'submit_edits', 'finish'}:
                raise ValueError('Unknown tool')
            if not isinstance(block.get('input'), dict):
                raise ValueError('Invalid tool arguments')
            return block['name'], block['input']
    # Never silently mark a truncated/thinking-only response as successful completion.
    raise ValueError('No tool call; stop reason: ' + str(response.get('stop_reason')))


class Opus:
    def __init__(self, model, ledger):
        from agents.llm_agent import EDIT_SCHEMA, FINISH_SCHEMA
        self.model, self.ledger = model, ledger
        self.key = os.environ.get('ANTHROPIC_API_KEY')
        if not self.key:
            raise RuntimeError('Missing ANTHROPIC_API_KEY')
        self.tools = [
            dict(name='submit_edits', description='Edit the design, then re-simulate the plant.', input_schema=EDIT_SCHEMA),
            dict(name='finish', description='Stop: nothing more worth trying.', input_schema=FINISH_SCHEMA)]

    def call(self, system, user, env=None):
        body = request_body(self.model, system, user, self.tools)
        request = urllib.request.Request('https://api.anthropic.com/v1/messages',
            data=json.dumps(body).encode(), headers={'x-api-key': self.key,
            'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=180) as stream:
                response = json.load(stream)
        except Exception as exc:
            # Never persist provider exception text or request headers.
            self.ledger.record(None, None, None, ok=False, error=type(exc).__name__)
            raise RuntimeError('Anthropic request failed: ' + type(exc).__name__) from None
        usage = response.get('usage', {})
        self.ledger.record(response.get('id'), usage.get('input_tokens'), usage.get('output_tokens'),
                           cached=usage.get('cache_read_input_tokens'))
        return select_tool(response)


def main():
    from agents import llm_agent
    import run_vm_agent
    llm_agent._Anthropic = Opus
    run_vm_agent.main()


if __name__ == '__main__':
    main()
