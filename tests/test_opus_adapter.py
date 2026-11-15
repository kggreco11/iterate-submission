"""Validate Opus API compatibility and failure handling without paid calls."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import io
import json
import pytest

spec = importlib.util.spec_from_file_location('opus_adapter', Path(__file__).resolve().parents[1] / 'infrastructure/azure/opus200/run_opus.py')
opus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(opus)


def test_request_uses_supported_opus_settings():
    body = opus.request_body('claude-opus-5-5', 'system', 'state', [])
    assert body['tool_choice'] == {'type': 'auto'}
    assert body['output_config'] == {'effort': 'medium'}
    assert body['max_tokens'] == 6000
    assert 'thinking' not in body and 'temperature' not in body


def test_thinking_blocks_do_not_hide_tool_call():
    response = {'content': [{'type': 'thinking', 'thinking': ''},
        {'type': 'tool_use', 'name': 'submit_edits', 'input': {'edits': []}}]}
    assert opus.select_tool(response) == ('submit_edits', {'edits': []})


def test_truncated_response_is_not_finish():
    with pytest.raises(ValueError, match='No tool call'):
        opus.select_tool({'stop_reason': 'max_tokens', 'content': []})


def test_usage_recorded_even_when_output_has_no_tool(monkeypatch):
    records = []
    agent = opus.Opus.__new__(opus.Opus)
    agent.model, agent.key, agent.tools = 'claude-opus-5-5', 'test-only', []
    agent.ledger = SimpleNamespace(record=lambda *a, **kw: records.append((a, kw)))
    response = {'id': 'test', 'usage': {'input_tokens': 12, 'output_tokens': 6000},
                'stop_reason': 'max_tokens', 'content': []}
    monkeypatch.setattr(opus.urllib.request, 'urlopen', lambda *a, **kw: io.BytesIO(json.dumps(response).encode()))
    with pytest.raises(ValueError):
        agent.call('system', 'state')
    assert records[0][0] == ('test', 12, 6000)
