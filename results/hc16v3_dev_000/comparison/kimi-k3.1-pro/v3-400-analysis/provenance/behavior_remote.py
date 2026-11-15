"""Read-only behavioral audit of saved trajectories. No experiments are launched."""
import json,hashlib,lzma,statistics,collections,time
from pathlib import Path
B=Path(r'C:\iterate-hackathon'); old=json.loads(lzma.decompress((B/'v3-400-analysis.json.xz').read_bytes()))
def fingerprint(d):return json.dumps(d,sort_keys=True,separators=(',',':'))
def diff(a,b):
 keys=set(a)|set(b); changed=[k for k in keys if a.get(k)!=b.get(k)]
 return dict(nodes=len(changed),added=len(set(b)-set(a)),removed=len(set(a)-set(b)),root=a.get('')!=b.get(''),topology=set(a)!=set(b),parameter_only=bool(changed) and set(a)==set(b),unchanged=not changed)
def stats(v):return dict(n=len(v),median=statistics.median(v) if v else None,mean=statistics.mean(v) if v else None,min=min(v) if v else None,max=max(v) if v else None)
def audit(r):
 root=Path(r['run']);ev=[json.loads(l) for l in (root/'raw/trajectory.jsonl').read_text().splitlines() if l.strip()];c=r['config'];agents=c['agents']; versions={};current={a:{} for a in agents};best={a:0 for a in agents};latest_reward={a:0 for a in agents};team=0;inc=None;inc_round={};count=collections.Counter();byagent={a:collections.Counter() for a in agents};phases={str(i):collections.Counter() for i in range(4)};source_ages=[];edits=[];queries=[];submitted=[];novel_gain=[];copy_gain=[];examples=[];improve=[];rounds=collections.defaultdict(list);sources=collections.Counter();context=collections.Counter();sectionbytes=collections.defaultdict(list);sourceexposure=collections.Counter();includedages=[];memorysources=set();policytime=collections.defaultdict(list);valid_rewards=[]
 for e in ev:
  kind=e['kind'];a=e.get('agent');rd=e.get('round',0)
  if kind=='policy_outcome':
   inc_round.setdefault(rd,inc); policytime[rd].append(e.get('model_s',0));x=e.get('context',{})
   context['prompts']+=1;context['incumbent_present']+=bool(x.get('incumbent_included'));context['memory_empty']+=not x.get('included_memories');context['included_memories']+=x.get('included_memories',0);context['omitted_memories']+=x.get('omitted_memories',0)
   for k,v in x.get('section_bytes',{}).items():sectionbytes[k].append(v)
   for key,rr in x.get('source_rounds',{}).items():
    includedages.append(rd-rr)
    if key in versions:sourceexposure[versions[key].get('agent','unknown')]+=1
  if kind=='memory_read':
   for f in e.get('findings',[]):
    for s in f.get('sources',[]):memorysources.add(s.get('sourceId'))
  if kind=='initial_design':versions[e['id']]=e;inc=e['id'];continue
  if kind!='submission':continue
  design=e['design'];source=versions.get(e.get('source_design'));base=source['design'] if source else current[a];d=diff(base,design);own=diff(current[a],design);m=e.get('measured') or {};valid=m.get('valid') is True;reward=m.get('reward');peer=bool(source and source['agent']!=a);ci=e.get('source_design')==inc_round.get(rd) and bool(source);phase=str(min(3,e['distinct_queries']//100));counts=[count,byagent[a],phases[phase]]
  flags=dict(submissions=True,rejected=bool(e.get('rejected')),valid=valid,invalid=m.get('valid') is False,duplicate=bool(e.get('duplicate_of')),source_copy=bool(source),peer_copy=peer,copy_round_incumbent=ci,copy_unchanged=bool(source) and d['unchanged'],copy_then_edit=bool(source) and not d['unchanged'],no_source=not source,base_unchanged=d['unchanged'],one_node_change=d['nodes']==1,multi_node_change=d['nodes']>=3,topology_change=d['topology'],root_change=d['root'],parameter_only=d['parameter_only'],adds_columns=d['added']>0,removes_columns=d['removed']>0,below_own_best=valid and reward<best[a]-1e-9,below_previous=valid and reward<latest_reward[a]-1e-9,team_improvement=valid and reward>team+1e-9,own_improvement=valid and reward>best[a]+1e-9)
  for k,v in flags.items():
   for target in counts:target[k]+=int(v)
  if source:
   source_ages.append(rd-source.get('round',0));sources[source['agent']]+=1
   if valid and (source.get('measured') or {}).get('valid'):
    delta=reward-source['measured']['reward'];copy_gain.append(delta)
    for target in counts:target['copy_beats_source']+=delta>1e-9;target['copy_worse_than_source']+=delta< -1e-9
  if valid and reward>team+1e-9:
   improve.append(dict(agent=a,round=rd,reward=reward,gain=reward-team,peer_copy=peer,incumbent_copy=ci,changes=d,note=e.get('interpretation','')[:650]));team=reward;inc=e['id']
  if valid:best[a]=max(best[a],reward);latest_reward[a]=reward
  edits.append(d['nodes']);queries.append(e.get('new_queries',0));current[a]=design;versions[e['id']]=e;rounds[rd].append(e)
  submitted.append(dict(round=rd,agent=a,reward=reward,valid=valid,copy=peer,changed_nodes=d['nodes'],topology=d['topology'],queries=e['distinct_queries']))
  if len(examples)<15 and (d['nodes']>=5 or (valid and reward<best[a]-.15)):
   examples.append(dict(agent=a,round=rd,changes=d,source=e.get('source_design'),reward=reward,note=e.get('interpretation','')[:650]))
 pair=[];same_base=[];round_div=[]
 for rd,es in rounds.items():
  ds=[fingerprint(e['design']) for e in es];ss=[e.get('source_design') for e in es if e.get('source_design')];round_div.append(dict(round=rd,agents=len(es),unique_designs=len(set(ds)),unique_sources=len(set(ss)),copying=len(ss)))
  for i,e in enumerate(es):
   for other in es[i+1:]:pair.append(diff(e['design'],other['design'])['nodes']);same_base.append(bool(e.get('source_design') and e.get('source_design')==other.get('source_design')))
 final=[r['summary']['agents'][a]['best_design'] for a in agents];finalpair=[diff(final[i],final[j]) for i in range(len(final)) for j in range(i+1,len(final))]
 positive=[e for e in improve if e['reward']>0]; biggest=sorted(positive,key=lambda e:e['gain'],reverse=True)[:8];last=positive[-5:]
 return dict(condition=c['condition'],run_id=c['run_id'],trajectory_sha256=hashlib.sha256((root/'raw/trajectory.jsonl').read_bytes()).hexdigest(),counts=count,per_agent=byagent,query_quartiles=phases,changed_nodes=stats(edits),new_queries_per_submission=stats(queries),copy_source_age_rounds=stats(source_ages),copy_reward_delta=stats(copy_gain),source_agent_counts=sources,context=context,section_bytes={k:stats(v) for k,v in sectionbytes.items()},source_exposure=sourceexposure,included_source_age=stats(includedages),retrieved_distinct_sources=len(memorysources),published_versions=len(versions)-1,same_round_pair_changed_nodes=stats(pair),same_round_same_source_fraction=statistics.mean(same_base) if same_base else None,round_diversity=round_div,final_pair_diffs=finalpair,final_best_designs={a:d for a,d in zip(agents,final)},improvements=improve,examples=examples,model_round_s=sum(max(v) for v in policytime.values()),ideal_balanced_model_round_s=sum(sum(v)/len(v) for v in policytime.values()),model_agent_s=sum(sum(v) for v in policytime.values()),rounds=len(policytime))
out=dict(captured_at=time.time(),runs=[audit(r) for r in old['runs'] if r['summary']['status']=='all_finished_or_exhausted'])
raw=json.dumps(out,separators=(',',':')).encode();z=lzma.compress(raw);p=B/'v3-behavior.json.xz';p.write_bytes(z);print(json.dumps(dict(path=str(p),bytes=len(z),sha256=hashlib.sha256(z).hexdigest())))
