import json,lzma,hashlib,time,collections
from pathlib import Path
root=Path(r'C:\iterate-hackathon\azure-runtime-v3-kimi-independent-400-20261114-r1')
def read(p,default=None):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return default
def rows(p):
 out=[]
 if p.exists():
  for line in p.read_text().splitlines():
   try:out.append(json.loads(line))
   except ValueError:pass
 return out
cp=list((root/'runs').rglob('config.json'));assert len(cp)==1
run=cp[0].parent;c=read(cp[0]);ev=rows(run/'raw/trajectory.jsonl')
A={a:dict(queries=0,best=0,curve=[],counts=collections.Counter(),best_design={},last=None) for a in c['agents']}
usage={a:rows(run/'raw'/a/'usage.jsonl') for a in A};cursor=collections.Counter();counts=collections.Counter();current={a:{} for a in A};q=0;usd=0.;tin=tout=0;best=0.;curve=[];winner=None;policy=0
for e in ev:
 a=e.get('agent');kind=e['kind'];m=e.get('measured') or {}
 if kind=='policy_outcome':
  i=cursor[a];cursor[a]+=1;policy+=1
  if i<len(usage[a]):
   u=usage[a][i];usd+=u.get('usd') or 0;tin+=u.get('input_tokens') or 0;tout+=u.get('output_tokens') or 0
  x=e.get('context') or {};counts['prompts']+=1;counts['included_memories']+=x.get('included_memories',0);counts['incumbent_included']+=bool(x.get('incumbent_included'))
 if kind=='memory_read':counts['retrieved_findings']+=len(e.get('findings',[]))
 if kind!='submission':continue
 v=A[a];q+=e['distinct_queries']-v['queries'];v['queries']=e['distinct_queries'];d=e.get('design') or {};before=current[a];changed=sum(before.get(k)!=d.get(k) for k in set(before)|set(d));valid=m.get('valid') is True
 flags={'submissions':1,'valid':valid,'invalid':m.get('valid') is False,'rejected':bool(e.get('rejected')),'duplicate':bool(e.get('duplicate_of')),'source_copy':bool(e.get('source_design')),'citations':bool(e.get('evidence_ids')),'topology_change':set(before)!=set(d),'one_node_change':changed==1,'below_own_best':valid and m['reward']<v['best']-1e-9}
 for k,x in flags.items():counts[k]+=int(x);v['counts'][k]+=int(x)
 current[a]=d;v['last']={'reward':m.get('reward'),'valid':m.get('valid'),'round':e['round']}
 point=dict(queries=q,agent_queries=v['queries'],elapsed_s=e['elapsed_s'],usd=usd,input_tokens=tin,output_tokens=tout,round=e['round'],reward=m.get('reward'))
 if valid and m['reward']>v['best']:
  v['best']=m['reward'];v['curve'].append(point);v['best_design']=d
 if valid and m['reward']>best:
  best=m['reward'];curve.append(point);winner={'agent':a,'round':e['round'],'design':d,'measured':{k:m.get(k) for k in ['reward','valid','revenue','tac','sold','validation']}}
for a,v in A.items():
 us=usage[a];v['usage']={k:sum(u.get(k) or 0 for u in us) for k in ['input_tokens','output_tokens','usd']};v['usage'].update(requests=len(us),failed_requests=sum(not u.get('ok',True) for u in us),unknown_cost_requests=sum(u.get('usd') is None for u in us),policy_events=cursor[a]);v['usage_sha256']=hashlib.sha256((run/'raw'/a/'usage.jsonl').read_bytes()).hexdigest()
end=dict(queries=q,elapsed_s=max(e.get('elapsed_s',0) for e in ev),usd=sum(v['usage']['usd'] for v in A.values()),input_tokens=sum(v['usage']['input_tokens'] for v in A.values()),output_tokens=sum(v['usage']['output_tokens'] for v in A.values()),reward=best)
curve.append(end)
sim=read(run/'raw/simulator.json');summary=read(run/'metrics/summary.json')
out=dict(captured_at=time.time(),run=str(run),config=c,status=read(root/'campaign-status.json'),stop=read(root/'early-stop.json'),summary=summary,agents=A,curve=curve,winner=winner,counts=counts,backend_calls=sum(x['backend_call'] for x in sim) if sim is not None else None,cache_hits=sum(x['cache_hit'] for x in sim) if sim is not None else None,backend_evidence_available=sim is not None,source_manifest=read(run/'source-manifest.json'),trajectory_sha256=hashlib.sha256((run/'raw/trajectory.jsonl').read_bytes()).hexdigest(),event_count=len(ev),task=read(root/'tasks/campaign.json'),notes=['Forced termination: summary and service-event files may be absent. Query counts cover logged submissions; an in-flight operation may not be represented. Elapsed time ends at last logged event, not necessarily process termination. Costs include all saved usage records.'])
z=lzma.compress(json.dumps(out,separators=(',',':')).encode());p=root/'independent-partial-evidence.json.xz';p.write_bytes(z);print(json.dumps(dict(path=str(p),bytes=len(z),sha256=hashlib.sha256(z).hexdigest())))
