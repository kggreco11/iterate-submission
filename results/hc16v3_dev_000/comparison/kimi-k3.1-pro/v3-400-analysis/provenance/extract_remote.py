"""Read saved results only. Export compact sufficient statistics and exact improvement events."""
import json, hashlib, lzma, time
from pathlib import Path
from collections import Counter, defaultdict
BASE=Path(r'C:\iterate-hackathon')
def read(p,default=None):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return default

def rows(p):
 if not p.exists():return []
 return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def export_run(run, task):
 c=read(run/'config.json');s=read(run/'metrics/summary.json')
 ev=rows(run/'raw/trajectory.jsonl'); sim=read(run/'raw/simulator.json',[])
 usage={a:rows(run/'raw'/a/'usage.jsonl') for a in c['agents']}
 agents={a:dict(queries=0,best=None,curve=[],counts=Counter(),first_positive=None,final=None) for a in c['agents']}
 totals=Counter();memory=Counter();reject=Counter();invalid=Counter();versions={};improvements=[];curve=[];first=None;winner=None;best=None
 cursor=Counter();used=0;back=0;attempts=0;tin=tout=0;usd=0.;unknown=0;simpos=0;timing=Counter();round_model=defaultdict(list);source_copies=Counter();cited_sources=Counter()
 for e in ev:
  kind=e['kind'];a=e.get('agent');m=e.get('measured') or {};v=agents.get(a)
  if kind=='policy_outcome':
   i=cursor[a];u=usage[a][i] if i<len(usage[a]) else {};cursor[a]+=1
   tin+=u.get('input_tokens') or 0;tout+=u.get('output_tokens') or 0;usd+=u.get('usd') or 0;unknown+=int(u.get('usd') is None)
   round_model[e['round']].append(e.get('model_s',0));timing['model_agent_s']+=e.get('model_s',0)
   x=e.get('context') or {};memory['prompts']+=1
   for k in ['included_memories','omitted_memories']:memory[k]+=x.get(k,0)
   memory['empty_prompts']+=int(not x.get('included_memories'));memory['incumbent_missing']+=int(not x.get('incumbent_included'))
  if kind in ('memory_write','memory_read','barrier'):
   timing[kind+'_s']+=e.get('memory_s',0);memory[kind]+=1
  if kind=='memory_read':
   for k in ['raw_findings','accepted_findings','filtered_findings']:memory[k]+=(e.get('diagnostics') or {}).get(k,0)
  if kind not in ('submission','initial_design'):continue
  if kind=='submission':
   attempts+=1;v['counts']['attempts']+=1;delta=e['distinct_queries']-v['queries'];v['queries']=e['distinct_queries'];used+=delta
   batch=sim[simpos:simpos+delta];back+=sum(x['backend_call'] for x in batch);simpos+=delta
   for key,val in [('rejected',bool(e.get('rejected'))),('valid',m.get('valid') is True),('invalid',m.get('valid') is False),('duplicate',bool(e.get('duplicate_of'))),('cited',bool(e.get('evidence_ids')))]:
    v['counts'][key]+=int(val);totals[key]+=int(val)
   if e.get('rejected'):reject[e['rejected']]+=1
   for error in (m.get('validation') or {}).get('errors',[]):invalid[str(error)]+=1
   source=e.get('source_design');src=versions.get(source)
   if source:
    v['counts']['copies']+=1
    if src and src!=a:v['counts']['peer_copies']+=1;source_copies[src+' -> '+a]+=1
   for id in e.get('evidence_ids',[]):
    for source_id in (e.get('evidence_sources') or {}).get(id,[]):
     sa=versions.get(source_id)
     if sa and sa!=a:cited_sources[sa+' -> '+a]+=1
   for lever in ['side_draw','double_effect']:
    idx=4 if lever=='side_draw' else 5
    enabled=any((d.get(lever) if isinstance(d,dict) else (d[idx] if len(d)>idx else None)) for d in (e.get('design') or {}).values())
    v['counts'][lever+'_attempts']+=int(enabled);v['counts'][lever+'_valid']+=int(enabled and m.get('valid') is True)
   v['final']={k:m.get(k) for k in ['valid','reward','validation','failed','unsolved_budget']}
  versions[e.get('id')]=a
  point=dict(queries=used,backend_calls=back,attempts=attempts,elapsed_s=round(e['elapsed_s'],6),input_tokens=tin,output_tokens=tout,usd=usd if not unknown else None,round=e.get('round',0),agent=a,agent_queries=v['queries'] if v else 0)
  if m.get('valid'):
   reward=m['reward']
   if v is not None and (v['best'] is None or reward>v['best']):
    v['best']=reward;v['curve'].append(dict(point,reward=reward))
   if reward>0 and first is None:first=dict(point,reward=reward)
   if reward>0 and v is not None and v['first_positive'] is None:v['first_positive']=dict(point,reward=reward)
   if best is None or reward>best:
    best=reward;curve.append(dict(point,reward=reward));winner={k:e.get(k) for k in ['id','agent','round','design','measured','source_design','evidence_ids']}
    improvements.append(dict(point,reward=reward,note=str(e.get('interpretation',''))[:350]))
 reconciliation={}
 for a,us in usage.items():
  summed=dict(requests=len(us),input_tokens=sum(u.get('input_tokens') or 0 for u in us),output_tokens=sum(u.get('output_tokens') or 0 for u in us),usd_estimated_total=sum(u.get('usd') or 0 for u in us),failed_requests=sum(not u.get('ok',True) for u in us),requests_with_unknown_cost=sum(u.get('usd') is None for u in us))
  reported=s['agents'][a].get('usage') or {}
  checks={k:abs(summed[k]-reported[k])<1e-7 for k in summed if k in reported}
  reconciliation[a]=dict(summed=summed,checks=checks,policy_events=cursor[a],usage_sha256=digest(run/'raw'/a/'usage.jsonl'),price_source=reported.get('price_source'),unknown_input=sum(u.get('input_tokens') is None for u in us),unknown_output=sum(u.get('output_tokens') is None for u in us),cached_tokens=sum(u.get('cached_input_tokens') or 0 for u in us),cached_unknown=sum(u.get('cached_input_tokens') is None for u in us),reasoning_tokens=sum(u.get('reasoning_tokens') or 0 for u in us),reasoning_unknown=sum(u.get('reasoning_tokens') is None for u in us))
 end=dict(queries=s['team_distinct_queries'],backend_calls=s['backend_calls'],attempts=s['submissions'],elapsed_s=s['wall_s'],input_tokens=s['team_input_tokens'],output_tokens=s['team_output_tokens'],usd=s['known_llm_usd'] if s['unknown_cost_requests']==0 else None,reward=best,round=max(e.get('round',0) for e in ev))
 curve.append(end)
 timing['model_round_critical_s']=sum(max(v) for v in round_model.values());timing['simulator_s']=sum(x['solver_s'] for x in sim);timing['queue_s']=sum(x['queue_s'] for x in sim)
 raw=read(run/'raw/simulator-responses.json',[])
 physical=Counter()
 for r in raw:
  physical['backend_success']+=int(bool(r.get('success')))
  physical['backend_failure']+=int(not r.get('success'))
  physical['infrastructure_error']+=int(r.get('error_category')=='infrastructure')
  for k,v in (r.get('diagnostics') or {}).items():
   if isinstance(v,bool):physical[k+'_true']+=v;physical[k+'_observed']+=1
 return dict(config=c,summary=s,agents=agents,curve=curve,first_positive=first,winner=winner,improvements=improvements,memory=memory,timing=timing,counts=totals,rejections=reject,invalid_reasons=invalid,peer_copies=source_copies,peer_citations=cited_sources,reconciliation=reconciliation,physical=physical,source_manifest=read(run/'source-manifest.json',{}),trajectory_sha256=digest(run/'raw/trajectory.jsonl'),simulator_sha256=digest(run/'raw/simulator.json'),backend_curve_verified=simpos==len(sim) and back==s['backend_calls'] and used==s['team_distinct_queries'],usage_curve_verified=all(cursor[a]==len(usage[a]) for a in usage),run=str(run))

out=dict(captured_at=time.time(),runs=[],campaigns=[])
for deployment in sorted(BASE.glob('*v3*400*')):
 for camp in (deployment/'runs/controls').glob('controls-*'):
  out['campaigns'].append(dict(deployment=deployment.name,status=read(camp/'summary.json')))
  task=read(deployment/'tasks/campaign.json')
  if task:out['task']=task
  for cp in (camp/'runs').rglob('config.json'):
   c=read(cp)
   if c and c.get('allocations') and all(n==400 for n in c['allocations']) and (cp.parent/'metrics/summary.json').exists():out['runs'].append(export_run(cp.parent,task))
raw=json.dumps(out,separators=(',',':')).encode();packed=lzma.compress(raw)
p=BASE/'v3-400-analysis.json.xz';p.write_bytes(packed)
print(json.dumps(dict(bytes=len(packed),sha256=hashlib.sha256(packed).hexdigest(),runs=len(out['runs']),path=str(p))))
