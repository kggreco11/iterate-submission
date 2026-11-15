"""Replay the upstream 12-column reference via the existing localhost worker.

The existing upstream installation supplies episode accounting; this repo owns
orchestration and artifacts. No direct COM calls or legacy jobs are launched.
"""
import argparse
import base64
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import urllib.request


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--upstream', required=True)
    p.add_argument('--reference', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, a.upstream)
    from btx.replay import Replayer, summarize
    from btx.task import Economics, make_task
    from btx.backends import to_legacy
    from btx.column_service import make_query

    def request(path, body=None):
        req = urllib.request.Request('http://127.0.0.1:5701' + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=330) as response:
            return json.load(response)

    ref = json.loads(a.reference.read_text())
    started = time.time()
    health = request('/health')
    desc = request('/describe', {'config': 0})
    cfg = desc['config_args']
    task = make_task('hackathon-config0-reference', desc['feed_flows_mol_s'],
        prices=cfg[1], purity=cfg[3] if len(cfg) > 3 else .95,
        temperature=desc['temperature_K'], pressure=desc['pressure_Pa'],
        fail_penalty=cfg[2], components=desc['components'], flowsheet='cfg0')
    calls = []
    a.out.parent.mkdir(parents=True, exist_ok=True)
    trace = a.out.with_suffix('.calls.jsonl')

    def solve(stream, action):
        flows, temp, pressure, n, rr, rb, dp = make_query(stream.flows, stream.T, stream.P, *action)
        case = dict(components=desc['components'], feed_flows_mol_s=list(flows),
            temperature_K=temp, pressure_Pa=pressure, n_stages=n,
            reflux_ratio=rr, reboil_ratio=rb, pressure_drop_fraction=dp, feed_stage=None)
        t = time.time()
        result = request('/solve', dict(config=0, case=case, request_id=f'hackathon-reference-{len(calls)+1}'))['result']
        record = dict(stream=stream.number, case=case, result=result, wall_s=time.time()-t)
        with trace.open('a') as f:
            f.write(json.dumps(record)+'\n')
        calls.append(record)
        if not result['success']:
            raise RuntimeError(f'Reference column failed on stream {stream.number}; preserved trace')
        return to_legacy(result)

    if trace.exists():
        raise RuntimeError('Use a new output path to avoid mixing runs')
    econ = Economics(task)
    rp = Replayer(econ, solve)
    for sid, *action in ref['actions']:
        if rp.done or rp.queue[0].number != sid:
            raise RuntimeError(f'Reference topology diverged before stream {sid}')
        rp.step(tuple(action))
    summary = summarize(rp)
    outlets = []
    recovered = [0.] * len(task['components'])
    total_out = [0.] * len(recovered)
    for stream, disposition in rp.finals:
        flows = stream.flows.tolist()
        total = sum(flows)
        dominant = max(range(len(flows)), key=flows.__getitem__)
        purity = flows[dominant]/total if total else 0.
        if disposition == 'product_on_spec':
            recovered[dominant] += flows[dominant]
        total_out = [x+y for x,y in zip(total_out, flows)]
        outlets.append(dict(stream=stream.number, disposition=disposition,
            flows_mol_s=flows, total_mol_s=total, dominant_component=task['components'][dominant],
            purity=purity, temperature_K=stream.T, pressure_Pa=stream.P))
    balance = [out-feed for out,feed in zip(total_out, task['feed_flows_mol_s'])]
    column_checks = []
    for c in calls:
        r = c['result']
        diffs = [t+b-f for t,b,f in zip(r['tops']['flows'],r['bottoms']['flows'],c['case']['feed_flows_mol_s'])]
        column_checks.append(dict(stream=c['stream'], max_balance_error_mol_s=max(map(abs,diffs)),
            passed=all(math.isfinite(d) and abs(d)<=1e-6+1e-7*abs(f) for d,f in zip(diffs,c['case']['feed_flows_mol_s']))))
    report = dict(task=task, worker=health, summary=summary, expected_summary=ref['summary'],
        outlets=outlets, component_recovery_to_own_on_spec_product=[r/f if f else None for r,f in zip(recovered,task['feed_flows_mol_s'])],
        overall_component_residual_mol_s=balance, column_balance_checks=column_checks,
        actual_simulator_calls=len(calls), cache_hits=0, wall_s=time.time()-started,
        source_sha256={name:hashlib.sha256((Path(a.upstream)/name).read_bytes()).hexdigest()
            for name in ['btx/replay.py','btx/task.py','btx/backends.py']},
        reference_sha256=hashlib.sha256(a.reference.read_bytes()).hexdigest())
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    encoded=base64.b64encode(gzip.compress(json.dumps(report,separators=(',',':')).encode())).decode()
    print('REPORT_GZIP_BASE64='+encoded, flush=True)

if __name__ == '__main__':
    main()
