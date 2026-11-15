"""Build one figure per reported experiment from published measurements, offline.

Requires matplotlib. Updates only marked figure sections in RESEARCH_REPORT.md.
"""
from pathlib import Path
import csv, json, re, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];O=R/'results/results-so-far';F=R/'results/research-figures';F.mkdir(exist_ok=True)
A=R/'results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis'
rows=json.loads((O/'runs.json').read_text());review=json.loads((O/'final-team-review.json').read_text());teams={x['run_id']:x for x in review['rows']}
curves=list(csv.DictReader((A/'curves.csv').open()))+list(csv.DictReader((A/'independent_curves.csv').open()))
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','figure.facecolor':'white'})
modelnames={'claude-opus-5-5':'Opus','kimi-k3.1-pro':'Kimi','deepseek-v4.1-flash':'DeepSeek','gpt-6.1-sol':'Sol','gpt-6-luna':'Luna'}
conditions={'single_without_past':'Solo, exact results','single_with_past':'Solo, Past retrieval','swarm_without_past':'Five agents, exact sharing','swarm_with_past':'Five agents, Past retrieval','independent_without_past':'Five independent agents','single_baseline':'Solo, compact experiment library','sharing_immediate':'Five agents, immediate library sharing'}
keep=lambda r:r['state']=='completed' or r['status']=='round_limit' or r['sharing']=='independent_without_past' or (r['experiment']=='v3-screen' and r['sharing']=='solo')
selected=[r for r in rows if keep(r)];blocks={};records=[]
for r in selected:
 rid=r['run_id'];group=r['experiment'];source=(O/r['evidence']).resolve();d=json.loads(source.read_text());curve=[];agents={};extra='';q=float(r['queries']);reward=float(r['reward']);alloc=float(r['budget_total']);model=modelnames.get(r['model'],r['model']);task=r['task'].split('_dev_')[-1];label=conditions.get(r['sharing'],r['sharing'].removeprefix('team-'))
 if rid in teams:
  tr=teams[rid];source=R/tr['report'].replace('index.html','report-data.json');d=json.loads(source.read_text());s=d['summary'];curve=[(float(x[0]),float(x[1])) for x in d['team_curve']];agents=s['agents'];label=f"{tr['agents']} agents, {tr['preset']}" if tr['agents']>1 else 'Solo'
  if task=='000':group='stopping';label='Required continuation' if q>100 else 'Free stopping'
  else:group='final-'+model.lower()
  first=s.get('team_first_positive_at_team_solves');extra=(f"The first positive plant appeared at {first:,} total solves. " if first is not None else 'No positive-scoring plant was found. ')
  extra+=f"{s.get('agents_off_zero',0)} of {tr['agents']} agents found positive plants. The best design used {s.get('best_columns',0)} column positions."
 elif group=='v3-400':
  curve=[(float(x['queries']),float(x['reward'])) for x in curves if x['condition']==r['sharing']];source=A/('independent_curves.csv' if r['state']=='stopped' else 'curves.csv')
  extra='The curve uses total charged queries across the team, so it can be compared at the same query cutoff as solo. The larger allocation is not an equal-budget control.' if r['agents']>1 else 'This single-agent condition supplies the baseline for separating extra retrieval from the exact results already supplied in each prompt.'
 elif group=='v3-corpus':
  source=O/'corpus-evidence'/r['sharing']/'screening-audit.json';a=json.loads(source.read_text());curve=[(float(x['charged_queries']),max(0,float(x['best_valid_reward']))) for x in a['best_curve']];s=json.loads((source.parent/'summary.json').read_text());agents=s['agents'];extra='The shared-library configuration is a separate experiment from the earlier memory controls. Its result should not be treated as a repeat under identical settings.'
 elif group=='v3-screen':
  agents=d.get('agents',{});extra='This screening condition had a total allocation of 500 queries. The comparison varies how designs and advice are exchanged, while the final score alone does not measure how many alternatives survived.'
 elif group=='v3-100':
  label='Five agents, exact sharing' if r['agents']>1 else ('Solo, Past retrieval' if r['sharing'].startswith('past') else 'Solo, exact results');extra='This pilot preceded the longer memory experiment. Its outcome is a separate search trajectory, not an earlier checkpoint of the later 400-query run.'
 elif group=='v2':
  label='Five-agent memory swarm' if r['agents']>1 else 'Solo';extra='V2 has different economics and design choices from V3. Compare this score within the task; it is not part of the final V3 leaderboard.'
 else:
  label='Solo';extra='This is an initial single-agent reference. Model settings and consumed budgets differ between runs, so the result does not isolate model quality from search depth.'
 title=f'{model}: {label} — task {task}'
 if group=='hc12':title=f'{model}: {int(alloc)}-query pilot — HC12'
 status='Completed' if r['state']=='completed' else ('Partial: round limit' if r['status']=='round_limit' else 'Stopped early')
 ymax=8 if group=='v2' else (6 if group.startswith('final') or group=='v3-first-look' else 4)
 fig,axs=plt.subplots(1,2,figsize=(10.5,3.8),gridspec_kw={'width_ratios':[1.35,1]})
 if curve:
  assert all(x<=q+1e-6 for x,y in curve),(rid,'curve exceeds consumed budget')
  assert math.isclose(max(y for x,y in curve),reward,abs_tol=1e-7),(rid,'endpoint mismatch')
  curve=[(0.,0.)]+curve+[(q,reward)]
  axs[0].step([x for x,y in curve],[y for x,y in curve],where='post',color='#176b87',linewidth=2)
  axs[0].plot(q,reward,'o',color='#176b87');axs[0].set(xlabel='Total simulator queries charged',ylabel='Best reward (including empty design)',xlim=(0,alloc),ylim=(-.05,ymax));axs[0].set_title('Search progress')
 else:
  axs[0].barh(['Best observed'],[reward],color='#176b87');axs[0].set(xlabel='Reward',xlim=(0,ymax));axs[0].text(reward+.06,0,f'{reward:.3f}',va='center');axs[0].set_title('Observed endpoint')
 vals=sorted([float(a['best_valid_reward']) for a in agents.values() if isinstance(a,dict) and a.get('best_valid_reward') is not None],reverse=True)
 if len(vals)>1:
  axs[1].bar(range(1,len(vals)+1),vals,color='#d18532');axs[1].set(xlabel='Agent rank by final best score',ylabel='Best reward',ylim=(min(0,min(vals)-.1),ymax));axs[1].set_title('Results across agents')
 else:
  axs[1].barh(['Allocated','Used'],[alloc,q],color=['#dbe2e8','#d18532']);axs[1].set(xlabel='Simulator queries',xlim=(0,alloc*1.15));axs[1].set_title('Resources')
  for i,v in enumerate([alloc,q]):axs[1].text(v+alloc*.02,i,f'{int(v):,}',va='center')
 fig.suptitle(title,fontsize=12);fig.tight_layout(rect=(0,.06,1,.92));fig.text(.5,.025,f'{status}  |  Reward {reward:.4f}  |  {int(q):,} / {int(alloc):,} queries',ha='center',fontsize=10)
 filename=rid+'.png';fig.savefig(F/filename,dpi=130);plt.close(fig)
 cost='not recorded' if r.get('model_usd') is None else f"${r['model_usd']:.2f}"
 caption='Best-so-far values are shown only through the observed query count; the line is not extended into the unused allocation.' if curve else 'Only the measured endpoint is plotted here; this summary does not establish the path taken to reach it.'
 text=f"### {title}\n\n**{status}.** Best reward **{reward:.4f}**, using **{int(q):,} of {int(alloc):,}** allocated queries. Estimated model cost: **{cost}**.\n\n{extra}\n\n![{title}: reward {reward:.3f} after {int(q)} queries](results/research-figures/{filename})\n\n{caption} [Measurements for this run]({source.relative_to(R)}). Run ID: `{rid}`.\n"
 blocks.setdefault(group,[]).append(text)
 records.append(dict(run_id=rid,group=group,plot='results/research-figures/'+filename,source=str(source.relative_to(R)),reward=reward,queries=q,allocation=alloc,curve=curve,agent_best_rewards=vals,status=status))
report=R/'RESEARCH_REPORT.md';text=report.read_text()
for group,sections in blocks.items():
 start=f'<!-- experiments:{group} -->';end=f'<!-- /experiments:{group} -->'
 assert start in text,group
 text=re.sub(re.escape(start)+r'.*?'+re.escape(end),lambda m:start+'\n\n'+'\n'.join(sections)+'\n'+end,text,flags=re.S)
report.write_text(text);(F/'data.json').write_text(json.dumps(records,indent=2)+'\n')
print(f'Wrote {len(records)} experiment figures; {sum(bool(r["curve"]) for r in records)} use measured search curves.')
