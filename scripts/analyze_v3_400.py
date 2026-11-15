"""Build the V3 400-query analysis from a hash-verified, read-only VM projection.
Usage: PYTHONPATH=runs/v3-400-analysis/deps .venv/bin/python scripts/analyze_v3_400.py
"""
import argparse,base64,csv,hashlib,html,json,math,sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,default=ROOT/'runs/v3-400-analysis/evidence-corrected.json');parser.add_argument('--out',type=Path);args=parser.parse_args()
data=json.loads(args.data.read_text());task=data['task']
OUT=args.out.resolve() if args.out else ROOT/'results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis';OUT.mkdir(parents=True,exist_ok=True)
(OUT/'plots').mkdir(exist_ok=True)
complete=[r for r in data['runs'] if r['summary']['status']=='all_finished_or_exhausted']
failed=[r for r in data['runs'] if r not in complete]
order=['single_without_past','single_with_past','swarm_without_past','swarm_with_past','independent_without_past']
complete.sort(key=lambda r:order.index(r['config']['condition']) if r['config']['condition'] in order else 99)
assert len({r['config']['condition'] for r in complete})==len(complete)
labels={'single_without_past':'Single · no Past','single_with_past':'Single · Past','swarm_without_past':'Swarm · no Past','swarm_with_past':'Swarm · Past'}
colors=['#0072B2','#56B4E9','#D55E00','#009E73','#CC79A7'];styles=['-','--','-', '--', ':']
feed=np.array(task['feed_flows_mol_s']);prices=np.array(task['prices_usd_per_mol']);seconds=task['annual_operating_hours']*3600
norm=float(max(feed*prices*seconds));ceiling=float(sum(feed*prices*seconds)*task['economics']['premium']['multiplier'])
plt.rcParams.update({'font.size':10,'axes.titlesize':13,'axes.titleweight':'bold','axes.spines.top':False,'axes.spines.right':False,'savefig.dpi':160,'axes.grid':True,'grid.alpha':.18})
figures=[];checks=[];metrics=[];products=[];agent_rows=[];checkpoint_rows=[];first_rows=[];column_rows=[]
def check(name,ok,detail=''):
 checks.append(dict(check=name,passed=bool(ok),detail=detail))
def label(r):return labels.get(r['config']['condition'],r['config']['condition'])
def save(fig,name,title,caption):
 fig.suptitle(title,fontsize=17,fontweight='bold',y=.995)
 fig.tight_layout(rect=[0,.045,1,.965]);fig.text(.015,.012,'HC16 V3 · Kimi · one run per condition · 400 charged queries per agent',fontsize=9,color='#53616b')
 fig.savefig(OUT/'plots'/f'{name}.png',bbox_inches='tight');fig.savefig(OUT/'plots'/f'{name}.svg',bbox_inches='tight')
 figures.append((name,title,caption));pdf.savefig(fig,bbox_inches='tight');plt.close(fig)
def write_csv(name,rows):
 if not rows:return
 fields=list(dict.fromkeys(k for row in rows for k in row))
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def checkpoint(r,x,n):
 pts=[p for p in r['curve'] if p[x]<=n]
 return pts[-1]['reward'] if pts else None

def product_rows(r):
 out=[];m=r['winner']['measured']
 for p in m['sold']:
  f=np.array(p['flows']);total=float(sum(f));kind=p.get('kind','none');idx=[int(np.argmax(f))];threshold=task['required_purity'];target='dominant component'
  if kind.startswith('blend: '):
   group=next(g for g in task['economics']['groups'] if g['name']==kind[7:]);idx=[task['components'].index(c) for c in group['members']];threshold=group['min_fraction'];target=kind[7:]
  elif kind=='premium':threshold=task['economics']['premium']['purity'];target=task['components'][idx[0]]
  else:target=task['components'][idx[0]]
  purity=float(sum(f[idx])/total) if total else None
  recovery=float(sum(f[idx])/sum(feed[idx]))
  out.append(dict(condition=r['config']['condition'],node=p['node'] or 'Feed',kind=kind,target=target,qualifies_for_sale=p['value']>0,flow_mol_s=total,qualifying_moles_mol_s=float(sum(f[idx])),purity=purity,purity_target=threshold,physical_target_recovery=recovery,recovery_target=None,annual_revenue_usd=p['value']))
 return out

for r in data['runs']:
 s=r['summary'];c=r['config'];end=r['curve'][-1]
 check(c['run_id']+' frozen task hash',r['source_manifest'].get('tasks\\campaign.json')==data['runs'][0]['source_manifest'].get('tasks\\campaign.json'))
 check(c['run_id']+' experiment settings',c['task']=='hc16v3_dev_000' and c['model']=='kimi-k3.1-pro' and c['backend']=='chemsep' and all(n==400 for n in c['allocations']) and c['simulator_workers']==1 and c['solver_retries']==0)

 check(c['run_id']+' charged-query total',sum(a['queries'] for a in r['agents'].values())==s['team_distinct_queries'])
 check(c['run_id']+' backend curve mapping',r['backend_curve_verified'],'Sequential service events mapped using measured column executions, including cache calls and budget cleanup; endpoint reconciled.')
 check(c['run_id']+' usage curve mapping',r['usage_curve_verified'],'One saved usage event per policy outcome; parallel round costs counted before submissions.')
 for a,u in r['reconciliation'].items():
  check(c['run_id']+' '+a+' usage reconciliation',all(u['checks'].values()),json.dumps(u['checks']))
 check(c['run_id']+' best reward',math.isclose(end['reward'],max(v['best_valid_reward'] or 0 for v in s['agents'].values()),abs_tol=1e-8))
 check(c['run_id']+' submission outcome accounting',sum(r['counts'].get(k,0) for k in ['valid','invalid','rejected'])==s['submissions'])
 check(c['run_id']+' backend response accounting',r['physical'].get('backend_success',0)+r['physical'].get('backend_failure',0)==s['backend_calls'])
 for axis in ['queries','backend_calls','elapsed_s','input_tokens','output_tokens','usd']:
  vals=[p[axis] for p in r['curve'] if p.get(axis) is not None]
  check(c['run_id']+' monotone '+axis,all(b>=a-1e-8 for a,b in zip(vals,vals[1:])))
 if r not in complete:continue
 m=r['winner']['measured'];reward=m['reward'];counts=r['counts'];us=[u['summed'] for u in r['reconciliation'].values()]
 check(c['run_id']+' plant net objective',math.isclose(m['revenue']-m['tac'],reward*norm,rel_tol=1e-8))
 check(c['run_id']+' winning design eligible',m['valid'] and m.get('validation',{}).get('eligible',False))
 stream_sum=np.sum([p['flows'] for p in m['sold']],axis=0)
 # Reprice each terminal stream independently from the frozen task.
 recomputed_revenue=0.
 for product in m['sold']:
  f=np.array(product['flows']);total=float(sum(f));i=int(np.argmax(f));value=0.
  if total>0 and f[i]/total>=task['required_purity']:
   mult=task['economics']['premium']['multiplier'] if f[i]/total>=task['economics']['premium']['purity'] else 1.
   value=float(f[i]*prices[i]*seconds*mult)
  for group in task['economics']['groups']:
   ix=[task['components'].index(v) for v in group['members']];fg=float(sum(f[ix]))
   if total>0 and fg/total>=group['min_fraction']:value=max(value,fg*group['discount']*float(np.mean(prices[ix]))*seconds)
  recomputed_revenue+=value
 check(c['run_id']+' independent stream repricing',math.isclose(recomputed_revenue,m['revenue'],rel_tol=1e-9))
 check(c['run_id']+' terminal component closure',np.allclose(stream_sum,feed,atol=1e-5,rtol=1e-6),f'max residual {max(abs(stream_sum-feed)):.9g} mol/s')
 q=dict(condition=c['condition'],agents=len(c['agents']),status=s['status'],reward=reward,net_usd_per_year=reward*norm,revenue_usd_per_year=m['revenue'],annualized_cost_usd=m['tac'],ceiling_fraction=reward*norm/ceiling,queries=s['team_distinct_queries'],allocation=sum(c['allocations']),backend_calls=s['backend_calls'],cache_hits=s['cache_hits'],attempts=s['submissions'],valid_attempts=counts['valid'],invalid_attempts=counts['invalid'],rejected_attempts=counts['rejected'],duplicate_designs=counts['duplicate'],wall_minutes=s['wall_s']/60,input_tokens=s['team_input_tokens'],output_tokens=s['team_output_tokens'],model_usd=s['known_llm_usd'],requests=sum(u['requests'] for u in us),failed_requests=sum(u['failed_requests'] for u in us),unknown_cost_requests=s['unknown_cost_requests'],memory_usd=None,simulator_usd=None,design_positions=len(r['winner']['design']),physical_column_units=sum(2 if len(v)>5 and v[5] is not None else 1 for v in r['winner']['design'].values()),side_draw_columns=sum(len(v)>4 and v[4] is not None for v in r['winner']['design'].values()),double_effect_columns=sum(len(v)>5 and v[5] is not None for v in r['winner']['design'].values()),pending_ingestions=s.get('pending_ingestions'),run_id=c['run_id'])
 utilities=capital=heat=saving=exchanger=0.
 for path,node in m['nodes'].items():
  cr=node.get('column_result')
  if not cr:continue
  eff=cr.get('effects');costs=[eff['hp'].get('cost',{}),eff['lp'].get('cost',{})] if eff else [cr.get('cost',{})]
  link=eff.get('link',{}) if eff else {}
  cu=sum(z.get('utilities',0) for z in costs)-link.get('saving_usd',0)
  ca=sum(z.get('capital_annual',0) for z in costs)+link.get('exchanger_usd',0)
  utilities+=cu;capital+=ca;heat+=link.get('heat_MW',0);saving+=link.get('saving_usd',0);exchanger+=link.get('exchanger_usd',0)
  column_rows.append(dict(condition=c['condition'],node=path or 'Feed',annualized_cost_usd=node.get('tac'),utilities_usd=cu,annualized_capital_usd=ca,condenser_MW=abs(cr.get('qc',0))/1e6,reboiler_MW=cr.get('qr',0)/1e6,heat_integrated_MW=link.get('heat_MW',0),heat_savings_usd=link.get('saving_usd',0),exchanger_annualized_usd=link.get('exchanger_usd',0),heat_link_feasible=link.get('feasible'),settings=json.dumps(r['winner']['design'].get(path))))
 q.update(utilities_usd_per_year=utilities,annualized_capital_usd=capital,heat_integrated_MW=heat,heat_utility_savings_usd=saving,heat_exchanger_cost_usd=exchanger)
 check(c['run_id']+' column cost breakdown',math.isclose(utilities+capital,m['tac'],rel_tol=1e-8))
 metrics.append(q);products+=product_rows(r)
 for a,v in r['agents'].items():
  agent_rows.append(dict(condition=c['condition'],agent=a,queries=v['queries'],best_reward=v['best'],final_valid=(v['final'] or {}).get('valid'),final_reward=(v['final'] or {}).get('reward'),final_errors='; '.join(((v['final'] or {}).get('validation') or {}).get('errors',[])),**v['counts'],**r['reconciliation'][a]['summed'],cached_input_tokens=r['reconciliation'][a]['cached_tokens'] if not r['reconciliation'][a]['cached_unknown'] else None,reasoning_tokens=r['reconciliation'][a]['reasoning_tokens'] if not r['reconciliation'][a]['reasoning_unknown'] else None))
 for axis,ns in [('queries',[40,100,200,400,800,1200,1600,2000]),('backend_calls',[40,100,200,400,800,1200]),('elapsed_s',[300,600,1200,1800,2400]),('usd',[1,2,5,10,15])]:
  for n in ns:
   observed=n<=dict(queries=s['team_distinct_queries'],backend_calls=s['backend_calls'],elapsed_s=s['wall_s'],usd=s['known_llm_usd'])[axis]
   checkpoint_rows.append(dict(condition=c['condition'],axis=axis,checkpoint=n,reached=observed,best_reward=checkpoint(r,axis,n) if observed else None,note='No extension beyond observed resource use; agents were told 400 each.'))
 first=r['first_positive']
 first_rows.append(dict(condition=c['condition'],run_status=s['status'],criterion='first simulator-valid positive net objective',reached=first is not None,**(first or {})))

pdf=PdfPages(OUT/'figures.pdf')
# Five resource curves, exact step improvements; no extension beyond observed endpoints.
fig,axes=plt.subplots(2,3,figsize=(16,9))
curve_axes=[('queries','Charged team queries',1),('backend_calls','Actual backend simulator calls',1),('elapsed_s','Elapsed minutes',60),('input_tokens','Input tokens (millions)',1e6),('total_tokens','Input + output tokens (millions)',1e6),('usd','Estimated model spend (USD)',1)]
for ax,(key,title,scale) in zip(axes.flat,curve_axes):
 for i,r in enumerate(complete):
  if key=='backend_calls' and not r['backend_curve_verified']:continue
  if key in ('input_tokens','total_tokens','usd') and not r['usage_curve_verified']:continue
  pts=r['curve'];x=[(p['input_tokens']+p['output_tokens'] if key=='total_tokens' else p[key])/scale for p in pts];y=[p['reward']*norm/1e9 for p in pts]
  ax.step(x,y,where='post',label=label(r),color=colors[i],ls=styles[i],lw=2);ax.plot(x[-1],y[-1],'o',color=colors[i],ms=4)
 ax.set(xlabel=title,ylabel='Best valid net objective ($B/year)',ylim=(0,None));
 if key=='queries':ax.axvline(400,color='#666',ls=':',lw=1);ax.text(415,.03,'400 team queries',fontsize=8,rotation=90,va='bottom')
axes[0,0].legend(fontsize=8)
save(fig,'01_resource_curves','Search quality across six resource measures','Exact best-so-far step curves. Cost is model-only, not total search expense. Endpoint dots mark observed stopping points. Usage includes every agent in a parallel proposal round before any of that round’s submissions.')
# equal budget view and peragent normalization
fig,axes=plt.subplots(1,2,figsize=(13,5.5))
for i,r in enumerate(complete):
 pts=[p for p in r['curve'] if p['queries']<=400]
 stop=min(400,r['summary']['team_distinct_queries']);last=checkpoint(r,'queries',stop)
 axes[0].step([p['queries'] for p in pts]+[stop],[p['reward']*norm/1e9 for p in pts]+[last*norm/1e9],where='post',color=colors[i],ls=styles[i],label=label(r),lw=2)
 axes[1].step([p['queries']/len(r['config']['agents']) for p in r['curve']],[p['reward']*norm/1e9 for p in r['curve']],where='post',color=colors[i],ls=styles[i],label=label(r),lw=2)
axes[0].set(xlabel='Charged team queries',ylabel='Best valid net objective ($B/year)',title='Equal total budget: observed prefix',xlim=(0,400),ylim=(0,None))
axes[1].set(xlabel='Charged team queries / agent count',ylabel='Best valid net objective ($B/year)',title='Equal per-agent allowance: unequal team totals',xlim=(0,400),ylim=(0,None));axes[0].legend(fontsize=8)
save(fig,'02_budget_fairness','Equal-total and equal-per-agent views answer different questions','The left panel uses prefixes of runs told a 400-per-agent horizon, not separately budget-conditioned trials. The right x-axis is average team usage, not the maximum individual agent usage. No 3-agent run exists for this campaign.')
# per-agent curves
fig,axes=plt.subplots(2,2,figsize=(13,9))
for ax,r in zip(axes.flat,complete):
 for j,(a,v) in enumerate(r['agents'].items()):
  pts=v['curve'];ax.step([0]+[p['agent_queries'] for p in pts]+[v['queries']],[0]+[max(0,p['reward'])*norm/1e9 for p in pts]+[max(0,v['best'])*norm/1e9],where='post',label=a,color=colors[j],ls=['-','--',':','-.','-'][j])
 ax.set(title=label(r),xlabel='Agent charged queries',ylabel='Agent best valid net ($B/year)',xlim=(0,400),ylim=(0,2.4));ax.legend(fontsize=8)
save(fig,'03_agent_curves','How individual agents reached the team result','Each agent starts with the benchmark-valid zero-value empty plant, retained as a floor even if early submissions are negative. Agent traces are correlated members of the same run, not independent repetitions or confidence intervals. Team score is the maximum agent score.')
# first positive
fig,axes=plt.subplots(1,5,figsize=(18,5))
for ax,key,title,scale in zip(axes,['queries','backend_calls','attempts','elapsed_s','usd'],['Charged queries','Backend calls','Submission attempts','Elapsed minutes','Estimated model USD'],[1,1,1,60,1]):
 vals=[r['first_positive'][key]/scale if r['first_positive'] else 0 for r in complete]
 ax.bar(range(len(complete)),vals,color=colors[:len(complete)]);ax.set_xticks(range(len(complete)),[label(r).replace(' · ','\n') for r in complete],fontsize=8);ax.set_title(title)
 for j,v in enumerate(vals):ax.text(j,v,f'{v:.2f}',ha='center',va='bottom',fontsize=9)
save(fig,'04_first_positive','Resources to first positive, valid plant','Strict eligibility alone can be satisfied by the initial empty, zero-value plant. This chart therefore uses first valid reward > 0; it is not an invented commercial success threshold. Aborted attempts are retained separately in the report.')
# economics
fig,axes=plt.subplots(1,2,figsize=(13,5))
x=np.arange(len(complete));width=.24
for j,(key,name,col) in enumerate([('revenue_usd_per_year','Revenue','#0072B2'),('annualized_cost_usd','Annualized cost','#D55E00'),('net_usd_per_year','Net objective','#009E73')]):axes[0].bar(x+(j-1)*width,[m[key]/1e9 for m in metrics],width,label=name,color=col)
axes[0].set_xticks(x,[label(r).replace(' · ','\n') for r in complete]);axes[0].set_ylabel('$B/year');axes[0].legend(fontsize=9)
axes[1].bar(x,[m['ceiling_fraction']*100 for m in metrics],color=colors[:len(complete)]);axes[1].set_xticks(x,[label(r).replace(' · ','\n') for r in complete]);axes[1].set(ylabel='Percent of hypothetical ceiling',ylim=(0,100));axes[1].axhline(100,color='#777',ls=':')
save(fig,'05_plant_economics','Winning-plant revenue, cost, and ceiling attainment',f'Perfect separation at premium prices with zero column cost gives a hypothetical ${ceiling/1e9:.3f}B/year ceiling. It is not a feasible design or established optimum.')
# validity and cache
fig,axes=plt.subplots(1,3,figsize=(16,5))
bottom=np.zeros(len(complete))
for key,name,col in [('valid_attempts','Valid','#009E73'),('invalid_attempts','Evaluated invalid','#D55E00'),('rejected_attempts','Rejected edit','#999999')]:
 vals=np.array([m[key] for m in metrics]);axes[0].bar(x,vals,bottom=bottom,label=name,color=col);bottom+=vals
axes[0].legend(fontsize=8);axes[0].set_title('Submission outcomes')
for offset,key,name,col in [(-.18,'queries','Charged queries','#0072B2'),(.18,'backend_calls','Backend executions','#E69F00')]:axes[1].bar(x+offset,[m[key] for m in metrics],.36,label=name,color=col)
axes[1].set_title('Query accounting');axes[1].legend(fontsize=8)
axes[2].bar(x,[r['physical']['backend_failure'] for r in complete],color='#D55E00');axes[2].set_title('Failed backend responses')
for ax in axes:ax.set_xticks(x,[label(r).replace(' · ','\n') for r in complete],fontsize=8)
save(fig,'06_validity_and_queries','Design failures and simulator work are different measurements','Rejected edits do not imply simulator execution. Backend failures may occur within multi-column submissions. Solver retries are configured off; shared-cache hits still consume an agent’s first distinct-query allowance.')
# runtime and tokens
fig,axes=plt.subplots(1,3,figsize=(16,5))
base=np.zeros(len(complete))
for key,name,col in [('model_round_critical_s','Model: round max','#0072B2'),('simulator_s','Simulator service','#E69F00'),('memory_read_s','Memory reads','#009E73'),('memory_write_s','Memory writes','#CC79A7'),('barrier_s','Memory barriers','#56B4E9')]:
 vals=np.array([r['timing'].get(key,0)/60 for r in complete]);axes[0].bar(x,vals,bottom=base,label=name,color=col);base+=vals
residual=np.array([r['summary']['wall_s']/60 for r in complete])-base
axes[0].bar(x,np.maximum(residual,0),bottom=base,label='Other / residual',color='#aaa');axes[0].set_ylabel('Minutes');axes[0].legend(fontsize=7)
axes[1].bar(x,[m['input_tokens']/1e6 for m in metrics],label='Input',color='#0072B2');axes[1].bar(x,[m['output_tokens']/1e6 for m in metrics],bottom=[m['input_tokens']/1e6 for m in metrics],label='Output',color='#E69F00');axes[1].set_ylabel('Million tokens');axes[1].legend(fontsize=8)
axes[2].bar(x,[m['model_usd'] for m in metrics],color=colors[:len(complete)]);axes[2].set_ylabel('Estimated model USD')
for ax in axes:ax.set_xticks(x,[label(r).replace(' · ','\n') for r in complete],fontsize=8)
save(fig,'07_runtime_tokens_cost','Where runtime and model spend went','Timing is an approximate sequential phase decomposition: sum of maximum model duration per synchronized round, service duration, and logged memory time. Concurrent agent-model seconds are not added as wall time. Memory and VM dollar charges are unknown.')
# physical component recovery in sold qualifying products
recovery=[]
for r in complete:
 rec=np.zeros(len(feed))
 for p in r['winner']['measured']['sold']:
  if p['value']<=0:continue
  f=np.array(p['flows']);kind=p['kind']
  if kind.startswith('blend: '):idx=[task['components'].index(c) for c in next(g for g in task['economics']['groups'] if g['name']==kind[7:])['members']]
  else:idx=[int(np.argmax(f))]
  rec[idx]+=f[idx]
 recovery.append(rec/feed*100)
fig,ax=plt.subplots(figsize=(15,5));im=ax.imshow(recovery,vmin=0,vmax=100,cmap='Blues',aspect='auto');ax.set_xticks(range(len(feed)),task['components'],rotation=45,ha='right');ax.set_yticks(x,[label(r) for r in complete])
for i,row in enumerate(recovery):
 for j,v in enumerate(row):ax.text(j,i,f'{v:.0f}',ha='center',va='center',fontsize=8,color='white' if v>60 else '#222')
fig.colorbar(im,ax=ax,label='Percent of feed component recovered as qualifying product')
save(fig,'08_component_recovery','Physical recovery into qualifying products','Counts a component only when it is the priced pure/premium component or a member of the sold blend; impurities are excluded. No overall component recovery target is specified. The task’s 1% negligible-stream cutoff is not a required recovery target.')
# purity and flow per winning plant
fig,axes=plt.subplots(2,2,figsize=(14,10))
for ax,r in zip(axes.flat,complete):
 ps=[p for p in products if p['condition']==r['config']['condition']];xx=np.arange(len(ps))
 ax.bar(xx,[p['purity']*100 if p['purity'] is not None else 0 for p in ps],color=['#009E73' if p['qualifies_for_sale'] else '#999' for p in ps]);ax.scatter(xx,[p['purity_target']*100 for p in ps],marker='_',s=180,color='black',label='Grade purity threshold');ax.set_xticks(xx,[p['node']+'\n'+('sale' if p['qualifies_for_sale'] else 'unpaid') for p in ps],fontsize=8);ax.set(ylim=(0,105),ylabel='Purity / blend membership (%)',title=label(r));ax.legend(fontsize=8)
save(fig,'09_product_purity','Purity against the applicable product grade','Green streams qualify for sale; gray streams are unpaid. Premium target is 99%; base pure and blend thresholds are 95%. For unpaid streams the chart shows dominant-component purity versus the 95% pure-product threshold. Stream flow and recovery are in products.csv and the tables below.')
fig,axes=plt.subplots(2,2,figsize=(14,9))
for ax,r in zip(axes.flat,complete):
 ps=[p for p in products if p['condition']==r['config']['condition']];xx=np.arange(len(ps));ax.bar(xx,[p['flow_mol_s'] for p in ps],color=['#009E73' if p['qualifies_for_sale'] else '#999' for p in ps]);ax.set_xticks(xx,[p['node'] for p in ps]);ax.set(title=label(r),ylabel='Terminal stream flow (mol/s)')
save(fig,'10_product_flows','Where the feed leaves each winning plant','Terminal flow includes all species in the stream. Qualifying product moles, physical recovery, and grade are separately tabulated; flow targets are not specified by this task.')
# memory evidence
fig,axes=plt.subplots(1,3,figsize=(16,5))
for ax,key,title in zip(axes,['cited','peer_copies','duplicate'],['Submissions citing evidence','Copies of peer designs','Duplicate full designs']):
 vals=[sum(v['counts'].get(key,0) for v in r['agents'].values()) for r in complete];ax.bar(x,vals,color=colors[:len(complete)]);ax.set_xticks(x,[label(r).replace(' · ','\n') for r in complete],fontsize=8);ax.set_title(title)
save(fig,'11_memory_behavior','Observed sharing behavior, not causal attribution','No-Past swarms still share exact peer packets and incumbents. Peer copying is linked through saved source-design IDs; citations alone do not prove useful adoption. Duplicate designs may include intentional restoration of a prior best design.')
fig,axes=plt.subplots(1,2,figsize=(12,5))
for ax,r in zip(axes,[r for r in complete if len(r['agents'])>1]):
 names=list(r['agents']);matrix=np.zeros((len(names),len(names)))
 for edge,count in r['peer_copies'].items():
  src,dst=edge.split(' -> ');matrix[names.index(src),names.index(dst)]=count
 im=ax.imshow(matrix,cmap='Blues',vmin=0);ax.set_xticks(range(len(names)),names,rotation=30);ax.set_yticks(range(len(names)),names);ax.set(xlabel='Copying agent',ylabel='Source agent',title=label(r))
 for i in range(len(names)):
  for j in range(len(names)):ax.text(j,i,int(matrix[i,j]),ha='center',va='center',color='white' if matrix[i,j]>matrix.max()*.6 else '#222')
 fig.colorbar(im,ax=ax,label='Peer-design copies')
save(fig,'12_peer_copy_network','Which agents supplied the designs peers copied','Counts explicit source-design references to another agent. This measures observed provenance, not whether copying improved outcomes.')
# levers
fig,axes=plt.subplots(1,2,figsize=(12,5))
for ax,key,title in zip(axes,['side_draw','double_effect'],['Side-draw attempts','Double-effect attempts']):
 vals=[sum(v['counts'].get(key+'_attempts',0) for v in r['agents'].values()) for r in complete];valid=[sum(v['counts'].get(key+'_valid',0) for v in r['agents'].values()) for r in complete];ax.bar(x,vals,color='#bbb',label='All proposals');ax.bar(x,valid,color='#0072B2',label='Valid proposals');ax.set_xticks(x,[label(r).replace(' · ','\n') for r in complete],fontsize=8);ax.set_title(title);ax.legend(fontsize=8)
save(fig,'13_v3_levers','How often agents tried the V3 design options','An attempt means the submitted design contains the option, including unchanged options carried forward. It does not count distinct innovations. Winning-design option counts are in the metrics table.')
# failure overhead
allrows=complete+failed;fig,ax=plt.subplots(figsize=(12,5));vals=[r['summary']['known_llm_usd'] for r in allrows];names=[label(r)+('\nABORTED' if r in failed else '\ncompleted') for r in allrows];ax.bar(range(len(vals)),vals,color=[colors[complete.index(r)] if r in complete else '#999' for r in allrows]);ax.set_xticks(range(len(vals)),names,fontsize=8);ax.set_ylabel('Estimated model USD')
save(fig,'14_failed_attempt_cost','Keep recovery overhead in the campaign ledger','Aborted attempts are excluded from completed-condition performance rankings but included in operational spend. The earlier 100-query campaign and any independent control are outside this ledger.')
fig,axes=plt.subplots(1,2,figsize=(13,5))
axes[0].bar(x,[m['utilities_usd_per_year']/1e9 for m in metrics],label='Utilities, after heat savings',color='#D55E00')
axes[0].bar(x,[m['annualized_capital_usd']/1e9 for m in metrics],bottom=[m['utilities_usd_per_year']/1e9 for m in metrics],label='Annualized capital incl. exchanger',color='#0072B2');axes[0].set_ylabel('Annual plant cost ($B/year)');axes[0].legend(fontsize=8)
axes[1].bar(x,[m['heat_integrated_MW'] for m in metrics],color=colors[:len(complete)]);axes[1].set_ylabel('Heat transferred by double effects (MW)')
for ax in axes:ax.set_xticks(x,[label(r).replace(' · ','\n') for r in complete],fontsize=8)
save(fig,'15_cost_and_heat','Utility costs and heat integration in the winning plants','Uses the saved cost-model breakdown. Double-effect utility savings are subtracted once and exchanger annualized cost is added once. These heat links do not constitute independent whole-plant energy-balance verification.')
fig,axes=plt.subplots(2,2,figsize=(13,8))
for ax,r in zip(axes.flat,complete):
 names=list(r['agents']);xx=np.arange(len(names));best=[r['agents'][a]['best']*norm/1e9 for a in names];final=[((r['agents'][a]['final'] or {}).get('reward') or 0)*norm/1e9 for a in names]
 ax.bar(xx-.18,best,.36,label='Best valid retained',color='#0072B2');ax.bar(xx+.18,final,.36,label='Last submitted objective',color='#999')
 for j,a in enumerate(names):
  if (r['agents'][a]['final'] or {}).get('valid') is False:ax.plot(j+.18,final[j],marker='x',color='#D55E00',ms=10,mew=2)
 ax.set_xticks(xx,names);ax.set(title=label(r),ylabel='Annual objective ($B/year)');ax.legend(fontsize=8)
save(fig,'16_best_vs_last','Best retained designs and final submissions can differ','An orange cross marks an invalid last submission; its displayed objective is ineligible. The experiment score uses the best valid design retained during search, never an invalid last attempt.')
pdf.close()

# Topology plots: exact winning-design nodes; text tables retain full settings.
with PdfPages(OUT/'winning_plants.pdf') as treepdf:
 for r in complete:
  m=r['winner']['measured'];nodes=m['nodes'];leaves=sorted(p for p in nodes if p not in r['winner']['design']);positions={p:i for i,p in enumerate(leaves)}
  for p in sorted(nodes,key=len,reverse=True):
   children=[q for q in nodes if len(q)==len(p)+1 and q.startswith(p)]
   if children:positions[p]=sum(positions[q] for q in children)/len(children)
  fig,ax=plt.subplots(figsize=(max(11,len(leaves)*1.5),7))
  for p,n in nodes.items():
   xx=positions[p];yy=-len(p)
   if p:ax.plot([positions[p[:-1]],xx],[-len(p)+1,yy],color='#9caeb9',zorder=0)
   column=p in r['winner']['design'];box=dict(boxstyle='round,pad=.4',fc='#e5f1f8' if column else '#e5f3ec',ec='#527483')
   if column:
    spec=r['winner']['design'][p];txt=f'{p or "Feed column"}\n{spec[0]} stages\nRR {spec[1]:g} · RB {spec[2]:g}'
    if len(spec)>5 and spec[5] is not None:txt+='\nDouble effect'
    elif len(spec)>4 and spec[4] is not None:txt+='\nSide draw'
   else:
    kind=n.get('kind','terminal')
    if kind in ('pure','premium'):kind+=' '+task['components'][int(np.argmax(n['feed']))]
    txt=f'{p or "Feed"}\n{kind}\n${n.get("value",0)/1e6:.1f}M/yr'
   ax.text(xx,yy,txt,ha='center',va='center',fontsize=8,bbox=box)
  ax.set(xlim=(-.8,max(positions.values())+.8),ylim=(-max(map(len,nodes))-.7,.7));ax.axis('off');fig.suptitle(label(r)+' — best valid process topology',fontsize=16);fig.tight_layout();name='plant_'+r['config']['condition'];fig.savefig(OUT/'plots'/f'{name}.png',dpi=160,bbox_inches='tight');treepdf.savefig(fig,bbox_inches='tight');plt.close(fig);figures.append((name,label(r)+' winning plant','Process topology, not a P&ID. Exact column settings and saved measured streams are included in report-data.json.'))

source_changes=[]
base=complete[0]['source_manifest']
for r in complete[1:]:
 for path in sorted(set(base)|set(r['source_manifest'])):
  if base.get(path)!=r['source_manifest'].get(path):source_changes.append(dict(condition=r['config']['condition'],file=path,baseline_sha256=base.get(path),condition_sha256=r['source_manifest'].get(path)))
write_csv('source_changes.csv',source_changes)
qualification_rows=[]
for r in data['runs']:
 p=r['curve'][0]
 qualification_rows.append(dict(condition=r['config']['condition'],run_id=r['config']['run_id'],run_status=r['summary']['status'],criterion='first benchmark-valid including empty initial plant',reached=p['reward'] is not None,**p))
 p=r['first_positive']
 qualification_rows.append(dict(condition=r['config']['condition'],run_id=r['config']['run_id'],run_status=r['summary']['status'],criterion='first positive valid objective',reached=p is not None,**(p or {})))
write_csv('qualification.csv',qualification_rows)

write_csv('columns.csv',column_rows);write_csv('metrics.csv',metrics);write_csv('agents.csv',agent_rows);write_csv('products.csv',products);write_csv('checkpoints.csv',checkpoint_rows);write_csv('first_positive.csv',first_rows)
write_csv('curves.csv',[dict(condition=r['config']['condition'],**p) for r in complete for p in r['curve']])
write_csv('validation.csv',checks)
(OUT/'report-data.json').write_text(json.dumps(data,indent=1)+'\n');(OUT/'summary.json').write_text(json.dumps(dict(metrics=metrics,validation=checks),indent=2)+'\n')

def table(rows,fields=None):
 if not rows:return '<p>No observations.</p>'
 fields=fields or list(rows[0]);out='<div class="table"><table><thead><tr>'+''.join('<th>'+html.escape(k.replace('_',' '))+'</th>' for k in fields)+'</tr></thead><tbody>'
 for row in rows:
  def val(v):return 'Unknown / not specified' if v is None else f'{v:,.4f}' if isinstance(v,float) else str(v)
  out+='<tr>'+''.join('<td>'+html.escape(val(row.get(k)))+'</td>' for k in fields)+'</tr>'
 return out+'</tbody></table></div>'
coverage=[
 ('Best economics vs queries / actual calls / time / search cost','Figures 01–02; curves.csv','Complete for model-cost estimates; full search cost unknown'),
 ('Input/output tokens and cost reconciliation','Figure 07; validation.csv; report-data.json','Request-event totals checked against per-agent summaries on VM; raw ledger SHA-256 retained'),
 ('First qualifying resources','Figure 04; first_positive.csv','First positive valid plant; empty initial plant already valid at zero cost'),
 ('Final validity / physical checks','Figure 06; report-data.json','Winner eligibility and component closure checked; final submissions separately tabulated; energy balance unverified'),
 ('Product purity / physical recovery / flow vs targets','Figures 08–10; products.csv','Purity targets available; no plant recovery or product flow targets specified'),
 ('1/3/5-agent comparison','Figures 02–03','1 and 5 available; 3-agent and independent-five results unavailable'),
 ('Per-agent sharing / citations / reuse','Figures 11–12; agents.csv','Observed provenance only; no causal memory claim'),
 ('V3 levers / plant economics / topology','Figures 05, 13 and winning plant figures','Best plant evidence exported; replay of every candidate not exported'),
 ('Reliability across independent repetitions','Figure 14; aborted attempt table','One completed run per condition; no confidence intervals or success-frequency estimate'),
 ('Memory / VM / simulator dollars','metrics.csv','Unknown; do not treat missing charges as zero'),
 ]
by={r['config']['condition']:r for r in complete}
insights=[]
for key in ['single','swarm']:
 if key+'_without_past' not in by or key+'_with_past' not in by:continue
 a,b=by[key+'_without_past'],by[key+'_with_past'];ra,rb=a['curve'][-1]['reward'],b['curve'][-1]['reward']
 insights.append(f'{key.capitalize()} Past vs no Past: final reward {(rb/ra-1)*100:+.2f}%; model spend {(b["summary"]["known_llm_usd"]/a["summary"]["known_llm_usd"]-1)*100:+.2f}%. One completed run per condition; memory-handling recovery patches limit causal interpretation.')
for r in complete:
 q=checkpoint(r,'queries',min(400,r['summary']['team_distinct_queries']));insights.append(f'{label(r)} at {min(400,r["summary"]["team_distinct_queries"])} observed charged queries: reward {q:.4f}, net ${q*norm/1e9:.3f}B/year. Final: ${r["curve"][-1]["reward"]*norm/1e9:.3f}B/year.')
if 'single_without_past' in by and 'swarm_without_past' in by:
 single,swarm=by['single_without_past'],by['swarm_without_past']
 budget=min(single['summary']['team_distinct_queries'],swarm['summary']['team_distinct_queries'],400)
 sv,wv=checkpoint(single,'queries',budget),checkpoint(swarm,'queries',budget)
 insights.append(f'At the same observed {budget}-query cap, no-Past single reward is {sv:.4f} versus swarm {wv:.4f} ({(wv/sv-1)*100:+.2f}%). At their unequal endpoints, the swarm is {(swarm["curve"][-1]["reward"]/single["curve"][-1]["reward"]-1)*100:+.2f}% higher, using {swarm["summary"]["team_distinct_queries"]/single["summary"]["team_distinct_queries"]:.2f}× charged queries and {swarm["summary"]["known_llm_usd"]/single["summary"]["known_llm_usd"]:.2f}× model spend.')
 a,b=single['winner']['measured'],swarm['winner']['measured']
 insights.append(f'The no-Past swarm’s net gain over the single comes from a ${ (a["tac"]-b["tac"])/1e6:.1f}M/year reduction in annualized cost, with revenue changing by ${(b["revenue"]-a["revenue"])/1e6:+.1f}M/year. This is an accounting decomposition, not an intervention on plant topology.')
if 'swarm_without_past' in by and 'swarm_with_past' in by:
 a,b=by['swarm_without_past'],by['swarm_with_past']
 insights.append(f'Past swarm leads the no-Past swarm at 200 team queries ({checkpoint(b,"queries",200):.4f} vs {checkpoint(a,"queries",200):.4f}), but trails by 400 ({checkpoint(b,"queries",400):.4f} vs {checkpoint(a,"queries",400):.4f}). Its early lead does not persist to the endpoint.')
if 'single_without_past' in by and 'swarm_without_past' in by:
 a,b=by['single_without_past'],by['swarm_without_past']
 insights.append(f'The ranking depends on the resource: at $5 of model spend, the no-Past single leads ({checkpoint(a,"usd",5):.4f} vs {checkpoint(b,"usd",5):.4f}); at 10 elapsed minutes, the no-Past swarm leads ({checkpoint(b,"elapsed_s",600):.4f} vs {checkpoint(a,"elapsed_s",600):.4f}).')
for r in complete:
 vals=[v['best'] for v in r['agents'].values() if v['best'] is not None]
 if len(vals)>1:
  copies=sum(v['counts'].get('peer_copies',0) for v in r['agents'].values());invalid_last=sum((v['final'] or {}).get('valid') is False for v in r['agents'].values())
  insights.append(f'{label(r)}: {copies} explicit peer-design copies; final per-agent best rewards span {min(vals):.6f}–{max(vals):.6f}. {invalid_last}/{len(vals)} agents ended on an invalid submitted design, while retaining earlier valid best designs.')
 if r['config']['condition'].endswith('_with_past'):
  mem=r['memory'];offered=mem.get('included_memories',0)+mem.get('omitted_memories',0)
  memory_s=sum(r['timing'].get(k,0) for k in ['memory_read_s','memory_write_s','barrier_s'])
  insights.append(f'{label(r)}: {100*mem.get("omitted_memories",0)/offered if offered else 0:.1f}% of candidate memory instances were omitted from prompts under the context budget; logged reads/writes/barriers account for {memory_s/60:.1f} minutes ({100*memory_s/r["summary"]["wall_s"]:.1f}% of wall time). Counts are repeated instances across prompts, not unique facts.')
if 'single_with_past' in by:
 idx=complete.index(by['single_with_past'])
 unpaid=[task['components'][j] for j,v in enumerate(recovery[idx]) if v<1e-6 and task['components'][j]!='Ethane']
 if unpaid:insights.append('The Past single’s winning plant has zero physical recovery into priced qualifying products for: '+', '.join(unpaid)+'. Those components remain in terminal flows but do not qualify as the priced species or blend members. This helps explain its revenue shortfall despite lower plant cost.')
failedchecks=[c for c in checks if not c['passed']]
notes=[
 'All four completed conditions use the same HC16 V3 task and Kimi alias with 400 charged distinct queries per agent; five-agent totals are 2,000. One simulator worker and zero configured solver retries. Exact provider model ID is not inferred from the alias.',
 'Without Past is an exact-sharing condition, not a no-sharing baseline. The independent control has no completed result in this evidence. Shared agents are not independent samples.',
 'The completed cells came from multiple deployments after memory-handling failures. Source manifests are included to make the changed code auditable. This is a recovered exploratory comparison, not an unchanged-source randomized trial.',
 'Model USD uses the recorded uncached estimate: $2 per million input tokens and $10 per million output tokens, with source/date in each ledger summary. Cached/reasoning tokens are not added again. These estimates are not invoices; memory and VM costs are unknown.',
 'Curves use exact best-improvement events plus observed run endpoints. Flat intervals imply no better valid submission. Prefixes inherit the 400-per-agent announced horizon. Curves are not extrapolated after a run stops.',
 'Model costs are attributed in logged policy-outcome order; all concurrent proposals finish before submission evaluation. Simulator-call mapping uses the number of column executions present in each measured result, including both double-effect legs and budget cleanup; it is validated against service-event count and backend totals. A failed mapping suppresses that curve.',
 'Saved simulator validity checks cover convergence, complete evaluated topology, bounds, finite/nonnegative streams, component closure and economic accounting. Tolerances are provisional. Independent energy-balance validation is explicitly absent.',
 'Cache hits count all simulator-service lookups, including revisits to queries already paid by the same agent. Cache hits therefore do not equal charged queries minus backend calls. Both counts are retained rather than collapsed into one efficiency measure.',
 'The task values qualifying pure/premium products and blends. It does not require all components to be recovered at a minimum percentage. Revenue/ideal revenue is an economic ratio and is never used here as physical recovery.',
 'This export is a compact evidence projection of trajectories, summaries, winner streams, and usage reconciliation. Raw provider requests, credentials, and full raw simulator responses stay on the VM. Every-candidate replay is not included.',
 ]
from v3_report_html import render_report
body=render_report(out=OUT,data=data,complete=complete,metrics=metrics,figures=figures,insights=insights,notes=notes,coverage=coverage,checks=checks,table=table,norm=norm,detail_tables=[
 ('All run metrics',table(metrics)),
 ('Winning plant equipment and cost breakdown',table(column_rows)),
 ('Winning plant products',table(products)),
 ('First valid and first positive outcomes',table(qualification_rows,['condition','run_status','criterion','reached','queries','backend_calls','attempts','elapsed_s','usd','reward'])),
 ('Every agent and final submission validity',table(agent_rows)),
 ('Source changes',table(source_changes)),
 ('Memory diagnostics',table([dict(condition=r['config']['condition'],**r['memory'],pending_ingestions=r['summary'].get('pending_ingestions')) for r in complete])),
 ('Aborted attempts',table([dict(condition=r['config']['condition'],status=r['summary']['status'],error=r['summary'].get('error'),queries=r['summary']['team_distinct_queries'],model_usd=r['summary']['known_llm_usd']) for r in failed])),
])
(OUT/'index.html').write_text(body)
md=['# V3 400-query analysis','', '[Open the full plotted report](index.html) · [Metric figures PDF](figures.pdf) · [Plant topologies PDF](winning_plants.pdf)','',*['- '+s for s in insights],'','## Evidence limitations','',*['- '+s for s in notes],'','## Rebuild','', '`PYTHONPATH=runs/v3-400-analysis/deps .venv/bin/python scripts/analyze_v3_400.py --data '+str(OUT.relative_to(ROOT)/'report-data.json')+'`','',f'Validation: {len(checks)-len(failedchecks)}/{len(checks)} checks passed.']
if (OUT/'behavior.html').exists():md.extend(['','## Behavioral investigation','','[Swarm behavior, product grades, and next experiments](behavior.html) · [Markdown](behavior-analysis.md)'])
(OUT/'README.md').write_text('\n'.join(md)+'\n')
for source_name in ['analyze_v3_400.py','v3_report_html.py']:
 (OUT/'provenance').mkdir(exist_ok=True)
 (OUT/'provenance'/source_name).write_bytes((ROOT/'scripts'/source_name).read_bytes())
manifest=dict(schema='v3-analysis-bundle-v1',run_id='v3-400-analysis',task=task['task_id'],condition='comparison',model='kimi-k3.1-pro',status='analysis complete; missing experimental controls',report='index.html',evidence='Compact saved trajectory projection; source manifests and raw-ledger hashes retained',sha256={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json'})
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(report=str(OUT/'index.html'),figures=len(figures),checks=len(checks),failed=failedchecks),indent=2))
