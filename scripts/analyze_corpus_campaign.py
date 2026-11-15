"""Analyze retrieved corpus-campaign conditions offline; preserve historical reports."""
from pathlib import Path
import json,hashlib,math,csv,html
R=Path(__file__).resolve().parents[1];O=R/'results/results-so-far';B=R/'runs/v3-screening-400-prep/kimi-five-r1/retrieved';T=json.loads((R/'results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/report-data.json').read_text())['task'];sec=T['annual_operating_hours']*3600
if not B.exists():
 raise SystemExit("Retrieved raw campaign archives are required; preserved corpus-campaign.json was not changed.")
results=[]
for root in sorted(B.glob('*/run')):
 T=json.loads((root.parent/'campaign/tasks/campaign.json').read_text());sec=T['annual_operating_hours']*3600
 if not (root/'metrics/summary.json').exists():continue
 c=json.loads((root/'config.json').read_text());s=json.loads((root/'metrics/summary.json').read_text());a=json.loads((root/'metrics/screening-audit.json').read_text());events=[json.loads(l) for l in (root/'raw/trajectory.jsonl').read_text().splitlines()];subs=[e for e in events if e['kind']=='submission'];valid=[e for e in subs if (e.get('measured') or {}).get('valid') and not e.get('rejected')];win=max(valid,key=lambda e:e['measured']['reward']);m=win['measured'];net=m['revenue']-m['tac']
 def revenue(delta):
  totalvalue=0
  for p in m['sold']:
   f=p['flows'];total=sum(f);i=max(range(len(f)),key=lambda k:f[k]);v=0
   if total and f[i]/total>=T['required_purity']+delta:v=f[i]*T['prices_usd_per_mol'][i]*sec*(T['economics']['premium']['multiplier'] if f[i]/total>=T['economics']['premium']['purity']+delta else 1)
   for g in T['economics']['groups']:
    ix=[T['components'].index(z) for z in g['members']];fg=sum(f[i] for i in ix)
    if total and fg/total>=g['min_fraction']+delta:v=max(v,fg*g['discount']*sum(T['prices_usd_per_mol'][i] for i in ix)/len(ix)*sec)
   totalvalue+=v
  return totalvalue
 checks={'submission_count':len(subs)==s['submissions'],'validity_counts':sum(a['attempts'].values())==len(subs),'best_reward':math.isclose(m['reward'],max(v['best_valid_reward'] for v in s['agents'].values())),'query_sum':sum(v['distinct_queries'] for v in s['agents'].values())==s['team_distinct_queries'],'cost_sum':math.isclose(sum(v['usage']['usd_estimated_total'] for v in s['agents'].values()),s['known_llm_usd']),'reprice_original':math.isclose(revenue(0),m['revenue'],rel_tol=1e-9),'objective':math.isclose(net,m['reward']*max(f*p*sec for f,p in zip(T['feed_flows_mol_s'],T['prices_usd_per_mol'])),rel_tol=1e-9),'component_closure':all(abs(sum(p['flows'][i] for p in m['sold'])-f)<=max(1e-5,abs(f)*1e-6) for i,f in enumerate(T['feed_flows_mol_s']))}
 assert all(checks.values()),checks
 dest=O/'corpus-evidence'/c['condition'];dest.mkdir(parents=True,exist_ok=True)
 for file in ['config.json','metrics/summary.json','metrics/screening-audit.json','source-manifest.json']:(dest/Path(file).name).write_bytes((root/file).read_bytes())
 data=dict(config=c,summary=s,audit=a,winner=win,checks=checks,trajectory_sha256=hashlib.sha256((root/'raw/trajectory.jsonl').read_bytes()).hexdigest(),evidence_root=str(root.relative_to(R)),annual_net=net,sensitivity=[dict(threshold_pp=pp,net= revenue(pp/100)-m['tac'],loss_fraction=(m['revenue']-revenue(pp/100))/net) for pp in [0,.01,.05,.1,.25,.5]],distinct_attempt_topologies=len({tuple(sorted(e['design'])) for e in subs}),explicit_source_submissions=sum(bool(e.get('source_design')) for e in subs),peer_source_submissions=sum(bool(e.get('source_design')) and ('-'+e['agent']+'-') not in e['source_design'] for e in subs),own_source_submissions=sum(bool(e.get('source_design')) and ('-'+e['agent']+'-') in e['source_design'] for e in subs))
 corpus=json.loads((root/'raw/corpus.json').read_text());data['corpus_inventory']={'keys':len(corpus),'observations':sum(len(g['observations']) for g in corpus.values()),'sha256':hashlib.sha256((root/'raw/corpus.json').read_bytes()).hexdigest()}
 (dest/'analysis.json').write_text(json.dumps(data,indent=2));results.append(data)
(O/'corpus-campaign.json').write_text(json.dumps(results,indent=2));print([(d['config']['condition'],d['annual_net'],d['sensitivity'][2],d['distinct_attempt_topologies'],d['peer_source_submissions']) for d in results])
