import pytest
from sepdesign.swarm_memory import PastMemory


def memory(monkeypatch, blocking=False, status='processing'):
    from sepdesign import swarm_memory
    monkeypatch.setattr(swarm_memory.time, 'monotonic', lambda: 1000)
    value=PastMemory.__new__(PastMemory)
    value.pending=['delayed'];value.pending_since={'delayed':0}
    value.timeout=300;value.blocking=blocking;value.events=[]
    def request(*args):
        value.events.append({'ok':True})
        return {'status':status}
    value._request=request
    return value


def test_nonblocking_delayed_ingestion_remains_pending_and_observable(monkeypatch):
    value=memory(monkeypatch)
    value.barrier()
    assert value.pending==['delayed']
    assert value.events[-1]['visibility_overdue'] is True
    assert value.events[-1]['pending_age_s']==1000


def test_blocking_deadline_still_fails(monkeypatch):
    with pytest.raises(TimeoutError):memory(monkeypatch,blocking=True).barrier()


def test_explicit_ingestion_failure_still_fails(monkeypatch):
    with pytest.raises(RuntimeError):memory(monkeypatch,status='failed').barrier()


def test_delayed_completion_is_removed(monkeypatch):
    value=memory(monkeypatch,status='completed');value.barrier()
    assert not value.pending and not value.pending_since
