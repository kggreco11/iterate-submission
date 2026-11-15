"""Read compact status for a deployed comparison without inference or simulator calls."""
import argparse
import base64
import json
from pathlib import Path
import sys
import time
import fcntl

sys.path.insert(0,str(Path(__file__).resolve().parent))
from azure_runtime import invoke, PYTHON


def fetch(controller):
    cfg=json.loads(controller.read_text())
    code='''import json
from pathlib import Path
r=Path(REMOTE)
run_id=RUN_ID
def read(p):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return {}
s=r/'runs/runtime'/(run_id+'-single')
turns=[]
if(s/'turns.jsonl').exists():
 for line in(s/'turns.jsonl').read_text().splitlines():
  try:turns.append(json.loads(line))
  except ValueError:pass
out={'pair':read(r/'runs'/run_id/'status.json'),'single':read(s/'status.json'),
 'single_summary':read(s/'summary.json'),'single_report':(s/'report.html').exists(),
 'recent':[{k:t.get(k) for k in ('turn','solves_used','reward','valid','action')} for t in turns[-2:]]}
swarms=list((r/'runs'/TASK/'shared-memory-5/kimi-k3.1-pro').glob('swarm-*'))
if swarms:
 p=max(swarms,key=lambda p:p.stat().st_mtime)
 summary=read(p/'metrics/summary.json')
 out['swarm_path']=str(p)
 out['swarm_report']=(p/'report.html').exists()
 out['swarm_summary']={k:summary.get(k) for k in ('status','wall_s','error','team_distinct_queries','known_llm_usd','unknown_cost_requests')}
 out['agents']={a:{k:v.get(k) for k in ('distinct_queries','best_valid_reward')} for a,v in summary.get('agents',{}).items()}
 if(p/'raw/trajectory.jsonl').exists():
  rows=[]
  for line in(p/'raw/trajectory.jsonl').read_text().splitlines():
   try:rows.append(json.loads(line))
   except ValueError:pass
  out['swarm_recent']=[{k:x.get(k) for k in ('kind','agent','round','distinct_queries','error')} for x in rows[-3:]]
  config=read(p/'config.json')
  progress={a:{'solves':0,'best':0,'requests':0,'usd':0,'unknown':0,'input':0,'output':0,'budget':b} for a,b in zip(config.get('agents',[]),config.get('allocations',[]))}
  recent=[]
  for x in rows:
   if x.get('kind')!='submission':continue
   a=x['agent'];v=progress.setdefault(a,{'solves':0,'best':0})
   v['solves']=x.get('distinct_queries',v['solves'])
   measured=x.get('measured') or {}
   if measured.get('valid'):v['best']=max(v['best'],measured.get('reward',0))
   recent.append(dict(agent=a,round=x.get('round'),solves=v['solves'],valid=measured.get('valid'),reward=measured.get('reward'),best=v['best']))
  for a,v in progress.items():
   u=p/'raw'/a/'usage.jsonl'
   if u.exists():
    for line in u.read_text().splitlines():
     try:entry=json.loads(line)
     except ValueError:continue
     v['requests']+=1;v['usd']+=entry.get('usd') or 0;v['unknown']+=int(entry.get('usd') is None)
     v['input']+=entry.get('input_tokens') or 0;v['output']+=entry.get('output_tokens') or 0
  out['live_agents']=progress
  out['live_recent']=recent[-8:]
  out['live_submissions']=len(recent)
  out['live_event']={k:rows[-1].get(k) for k in ('kind','round','agent','elapsed_s')} if rows else {}
  notes=[x for x in rows if x.get('kind')=='submission']
  out['live_note']=str(notes[-1].get('interpretation',''))[:350] if notes else ''

import gzip,base64
print(base64.b64encode(gzip.compress(json.dumps(out).encode())).decode())
'''.replace('REMOTE',repr(cfg['remote'])).replace('RUN_ID',repr(cfg['run_id'])).replace('TASK',repr(cfg['task']))
    enc=base64.b64encode(code.encode()).decode()
    ps=f"$out = & '{PYTHON}' -c \"import base64;exec(base64.b64decode('{enc}'))\"; Write-Output ('RUNTIME='+$out)"
    import gzip
    result=json.loads(gzip.decompress(base64.b64decode(invoke(ps,controller.with_suffix('.transport.jsonl'),'status',run_id=cfg['run_id']))))
    return result


def snapshot(controller):
    cache=controller.with_suffix('.status.json')
    def cached(note):
        if cache.exists():
            try:
                return {**json.loads(cache.read_text()), 'viewer': {'note':note,
                    'snapshot_age_s':round(time.time()-cache.stat().st_mtime)}}
            except (OSError,ValueError):
                pass
        return {'viewer':{'note':note,'snapshot_available':False}}
    with controller.with_suffix('.status.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return cached('Another viewer is fetching status; showing cached data')
        if cache.exists() and time.time()-cache.stat().st_mtime<60:
            return cached('Shared recent snapshot')
        try:
            result=fetch(controller)
        except (RuntimeError,OSError,ValueError) as exc:
            return cached(str(exc) if isinstance(exc,RuntimeError) else 'Status fetch unavailable')
        temporary=cache.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(result,indent=2))
        temporary.replace(cache)
        return {**result,'viewer':{'note':'Fresh snapshot','snapshot_age_s':0}}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('controller',type=Path)
    ap.add_argument('--watch',action='store_true',help='Refresh every 60 seconds; Ctrl-C stops only the viewer')
    a=ap.parse_args()
    try:
        while True:
            result=snapshot(a.controller.resolve())
            if a.watch and sys.stdout.isatty():
                print('\033[2J\033[H',end='')
            print(json.dumps(result,indent=2),flush=True)
            if not a.watch or (result.get('pair',{}).get('state') in ('complete','failed')
                    and result['viewer']['note'] in ('Fresh snapshot','Shared recent snapshot')):
                break
            time.sleep(60)
    except KeyboardInterrupt:
        print('Viewer closed. The experiment is unaffected.')


if __name__=='__main__':
    main()
