import fcntl
import json
from scripts import check_v2_pair as viewer


def test_busy_azure_retains_stale_snapshot(tmp_path,monkeypatch):
    p=tmp_path/'controller.json'
    p.with_suffix('.status.json').write_text(json.dumps({'pair':{'state':'swarm_running'}}))
    import os,time
    os.utime(p.with_suffix('.status.json'),(time.time()-120,)*2)
    def busy(_):raise RuntimeError('Azure control slot is busy')
    monkeypatch.setattr(viewer,'fetch',busy)
    result=viewer.snapshot(p)
    assert result['pair']['state']=='swarm_running'
    assert result['viewer']['snapshot_age_s']>=120
    assert 'busy' in result['viewer']['note']


def test_viewers_share_cache_and_do_not_fetch_concurrently(tmp_path,monkeypatch):
    p=tmp_path/'controller.json'
    calls=[]
    monkeypatch.setattr(viewer,'fetch',lambda _:calls.append(1) or {'pair':{'state':'swarm_running'}})
    with p.with_suffix('.status.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        assert viewer.snapshot(p)['viewer']['snapshot_available'] is False
        assert not calls
    assert viewer.snapshot(p)['viewer']['note']=='Fresh snapshot'
    assert viewer.snapshot(p)['viewer']['note']=='Shared recent snapshot'
    assert calls==[1]
