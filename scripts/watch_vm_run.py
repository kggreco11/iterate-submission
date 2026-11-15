"""Azure snapshot adapter for watch_run's existing terminal display."""
import os
import base64
import gzip
import fcntl
import time
import re
import json
import subprocess
from pathlib import Path


def fetch(controller):
    controller = Path(controller)
    cache = controller.with_suffix('.snapshot.json')
    with controller.with_suffix('.watch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if cache.exists() and time.time() - cache.stat().st_mtime < 60:
            return json.loads(controller.read_text()), json.loads(cache.read_text())
        config, snapshot = _fetch(controller)
        snapshot['fetched_at'] = time.time()
        cache.write_text(json.dumps(snapshot))
        return config, snapshot


def _fetch(controller):
    config = json.loads(controller.read_text())
    run = config['remote'] + '\\runs\\runtime\\' + config['run_id']
    code = '''import json,gzip,base64,time,statistics
from pathlib import Path
p=Path(RUN)
def read(name):
 try:return json.loads((p/name).read_text())
 except (OSError,ValueError):return {}
def rows(name):
 out=[]
 if (p/name).exists():
  for line in (p/name).read_text().splitlines():
   try:out.append(json.loads(line))
   except ValueError:pass
 return out
turns=rows('turns.jsonl'); usage=rows('usage.jsonl'); sims=rows('simulator.jsonl')
best=0; recent=[]
for row in turns:
 if 'reward' not in row:continue
 if row.get('valid'):best=max(best,row['reward'])
 recent.append(dict(turn=row['turn'],solves=row['solves_used'],valid=row['valid'],reward=row['reward'],best=best))
times=[x['result']['runtime_s'] for x in sims if 'result' in x]
snapshot=dict(status=read('status.json'),summary=read('summary.json'),recent=recent[-8:],submissions=len(recent),requests=len(usage),estimated_usd=sum(x.get('usd') or 0 for x in usage),unknown_cost=sum(x.get('usd') is None for x in usage),input_tokens=sum(x.get('input_tokens') or 0 for x in usage),output_tokens=sum(x.get('output_tokens') or 0 for x in usage),note=(turns[-1].get('note','') if turns else ''),median=statistics.median(times) if times else 0,failed=sum(not x.get('result',{}).get('success',False) for x in sims),age=time.time()-(p/'turns.jsonl').stat().st_mtime if turns else 0,elapsed=(usage[-1].get('elapsed_s',0) if usage else 0))
print('WATCH='+base64.b64encode(gzip.compress(json.dumps(snapshot).encode())).decode())
'''.replace('RUN', repr(run))
    encoded = base64.b64encode(code.encode()).decode()
    ps = "& 'C:\\chemsep-benchmark\\venv\\Scripts\\python.exe' -c \"import base64;exec(base64.b64decode('" + encoded + "'))\""
    response = subprocess.run(['az','vm','run-command','invoke','--resource-group',os.environ['AZURE_RESOURCE_GROUP'],'--name','chemsep-01','--command-id','RunPowerShellScript','--scripts',ps,'-o','json'],capture_output=True,text=True)
    if response.returncode:
        if '(Conflict)' in response.stderr:
            raise RuntimeError('Azure command slot is busy; retrying in 60 seconds. The simulator continues running.')
        match = re.search(r'ERROR: \(([^)]+)\)', response.stderr)
        reason = match.group(1) if match else 'CLI request failed'
        raise RuntimeError('Azure status fetch failed: ' + reason)
    data=json.loads(response.stdout)
    for value in data.get('value',[]):
        for line in value.get('message','').splitlines():
            if line.startswith('WATCH='):
                return config,json.loads(gzip.decompress(base64.b64decode(line[6:])))
    raise RuntimeError('Azure did not return a complete snapshot')


def render(config, data, econ):
    state=data['status'].get('state','unknown')
    recent=data['recent']; last=recent[-1] if recent else {}
    best=last.get('best',0)*econ.reward_norm
    lines=[f"{config['model'].upper()} PILOT  |  {state.upper()}",config['run_id'],'',
        f"Simulator: {last.get('solves',0)}/{config['simulator_budget']}  |  Submissions: {data['submissions']}  |  Model responses: {data['requests']}",
        f"Best valid net objective: ${best/1e6:,.2f}M/year",
        f"Hypothetical ceiling: ${econ.max_total_revenue/1e6:,.2f}M/year  |  Attained: {100*best/econ.max_total_revenue:.1f}%",
        f"Simulator failures: {data['failed']}  |  Median solve: {data['median']:.3f}s",
        f"Latest model response at {data['elapsed']/60:.1f} min  |  Feedback age at fetch: {data['age']:.0f}s",
        ('Estimated model cost: unavailable' if data.get('unknown_cost',1) else f"Estimated model cost: ${data['estimated_usd']:.4f}"),
        f"Tokens: {data['input_tokens']:,} input / {data['output_tokens']:,} output",'',
        'RECENT SUBMISSIONS','Attempt  Solves   Valid   Candidate $M/yr   Best $M/yr']
    for row in recent:
        lines.append(f"{row['turn']:>7}  {row['solves']:>6}   {str(row['valid']):<5}   {row['reward']*econ.reward_norm/1e6:>15,.2f}   {row['best']*econ.reward_norm/1e6:>10,.2f}")
    lines+=['','LATEST AGENT INTENT',data['note']]
    if state in ('complete','failed'):lines+=['','Stop reason: '+data['status'].get('stop_reason',data['status'].get('error_type','unknown'))]
    lines+=['',f"Snapshot age: {max(0,time.time()-data.get('fetched_at',time.time())):.0f}s",'Refresh: ~60–90 seconds including Azure delivery. Ctrl-C closes only this viewer.']
    return '\n'.join(lines),state in ('complete','failed')
