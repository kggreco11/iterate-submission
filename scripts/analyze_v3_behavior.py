"""Offline diagnostics for the V3 report. Uses saved evidence only."""
import csv,json,hashlib,itertools
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis'
D=json.loads((OUT/'report-data.json').read_text());T=D['task'];sec=T['annual_operating_hours']*3600
order=['single_without_past','single_with_past','swarm_without_past','swarm_with_past']
runs=sorted([r for r in D['runs'] if r['summary']['status']=='all_finished_or_exhausted'],key=lambda r:order.index(r['config']['condition']))
labels=['1 agent · No Past','1 agent · Past','5 agents · No Past','5 agents · Past'];colors=['#0072B2','#56B4E9','#D55E00','#009E73']
plt.rcParams.update({'font.size':12,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.16})
def save(fig,name):
 fig.tight_layout();fig.savefig(OUT/'plots'/f'{name}.png',dpi=180,bbox_inches='tight');fig.savefig(OUT/'plots'/f'{name}.svg',bbox_inches='tight');plt.close(fig)
def csvwrite(name,rows):
 with (OUT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def reprice(m,delta):
 total=0
 for p in m['sold']:
  f=p['flows'];flow=sum(f);i=max(range(len(f)),key=lambda k:f[k]);value=0
  if flow and f[i]/flow>=T['required_purity']+delta:
   mult=T['economics']['premium']['multiplier'] if f[i]/flow>=T['economics']['premium']['purity']+delta else 1
   value=f[i]*T['prices_usd_per_mol'][i]*sec*mult
  for g in T['economics']['groups']:
   ix=[T['components'].index(c) for c in g['members']];fg=sum(f[i] for i in ix)
   if flow and fg/flow>=g['min_fraction']+delta:value=max(value,fg*g['discount']*sum(T['prices_usd_per_mol'][i] for i in ix)/len(ix)*sec)
  total+=value
 return total
rows=[];fig,ax=plt.subplots(figsize=(10,5.8))
for r,label,color in zip(runs,labels,colors):
 m=r['winner']['measured'];assert abs(reprice(m,0)-m['revenue'])<.01
 xs=np.linspace(0,.5,501);ys=[(reprice(m,float(x)/100)-m['tac'])/1e9 for x in xs]
 ax.plot(xs,ys,label=label,color=color,lw=2.5,ls='--' if r['config']['condition'].endswith('_with_past') else '-')
 for pp in [0,.01,.05,.1,.25,.5]:
  rev=reprice(m,pp/100);rows.append(dict(condition=r['config']['condition'],threshold_increase_percentage_points=pp,annual_net_usd=rev-m['tac'],annual_revenue_loss_usd=m['revenue']-rev,net_loss_fraction=(m['revenue']-rev)/(m['revenue']-m['tac'])))
ax.axvline(.05,color='#6b7780',ls=':',lw=1.3);ax.set(xlabel='Increase in all grade thresholds (percentage points)',ylabel='Annual net value ($B/year)',title='Thin grade margins can reverse the ranking',ylim=(0,2.4),xlim=(0,.5));ax.legend(fontsize=10,loc='lower left');fig.text(.11,-.02,'Offline repricing of fixed saved flows and costs; not a physical perturbation or a new simulation.',fontsize=10,color='#536573');save(fig,'17_grade_sensitivity');csvwrite('grade_sensitivity.csv',rows)
# Exact endpoint design distances: numeric settings and outlet topology, not reward alone.
fig,axes=plt.subplots(1,2,figsize=(11,5));distance_rows=[]
for ax,r in zip(axes,runs[2:]):
 agents=list(r['summary']['agents']);ds=[r['summary']['agents'][a]['best_design'] for a in agents];mat=np.zeros((len(ds),len(ds)),dtype=int)
 for i,d in enumerate(ds):
  for j,e in enumerate(ds):
   mat[i,j]=sum(d.get(k)!=e.get(k) for k in set(d)|set(e))
   if i<j:distance_rows.append(dict(condition=r['config']['condition'],agent_a=agents[i],agent_b=agents[j],changed_node_settings=int(mat[i,j]),same_topology=set(d)==set(e)))
 ax.imshow(mat,vmin=0,vmax=8,cmap='Blues');ax.set_xticks(range(5),range(5));ax.set_yticks(range(5),range(5));ax.set(xlabel='Agent',ylabel='Agent',title='No Past' if r['config']['condition'].endswith('without_past') else 'Past');ax.grid(False)
 for i in range(5):
  for j in range(5):ax.text(j,i,str(mat[i,j]),ha='center',va='center',color='white' if mat[i,j]>4 else '#182b3b')
fig.suptitle('Every agent keeps the same 17-position topology within its swarm\nCells count positions with different settings',fontsize=15);save(fig,'18_final_design_distance');csvwrite('final_design_distance.csv',distance_rows)
# Saturation is retrospective, not an independently run low-budget experiment.
rows=[]
for r in runs:
 final=r['curve'][-1]['reward']
 for fraction in [.9,.95,.99]:
  p=next(p for p in r['curve'] if p['reward']>=fraction*final)
  rows.append(dict(condition=r['config']['condition'],fraction_of_observed_final=fraction,queries=p['queries'],elapsed_minutes=p['elapsed_s']/60,model_usd=p['usd']))
csvwrite('search_saturation.csv',rows)
behavior=OUT/'behavior-data.json'
if behavior.exists():
 B=json.loads(behavior.read_text());by={r['condition']:r for r in B['runs']};rows=[]
 for key in order:
  r=by[key];n=r['counts']['submissions'];rows.append(dict(condition=key,submissions=n,**{k:r['counts'][k]/n for k in ['peer_copy','source_copy','copy_round_incumbent','duplicate','one_node_change','topology_change','below_own_best','multi_node_change']}))
 csvwrite('behavior_rates.csv',rows)
 fig,axes=plt.subplots(1,2,figsize=(11,5.3))
 for ax,key in zip(axes,order[2:]):
  r=by[key];ph=r['query_quartiles'];x=np.arange(4)
  for field,title,color in [('copy_round_incumbent','Copies round-start incumbent','#0072B2'),('one_node_change','Changes one node from base','#D55E00'),('topology_change','Changes column topology','#009E73')]:
   ax.plot(x,[100*ph[str(i)][field]/ph[str(i)]['submissions'] for i in x],marker='o',label=title,color=color,lw=2)
  ax.set_xticks(x,['0–99','100–199','200–299','300–400']);ax.set(xlabel='Agent’s consumed query budget',ylabel='% of submissions',ylim=(0,105),title='No Past' if key.endswith('without_past') else 'Past')
 fig.legend(*axes[0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.5,-.02),ncol=3,fontsize=10);fig.suptitle('How search behavior changes through the budget',fontsize=15);save(fig,'19_behavior_by_budget')
# Publish code and refresh the bundle checksums.
(OUT/'provenance'/'analyze_v3_behavior.py').write_bytes(Path(__file__).read_bytes())
p=OUT/'manifest.json';m=json.loads(p.read_text());m['sha256']={str(f.relative_to(OUT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in OUT.rglob('*') if f.is_file() and f.name!='manifest.json'};p.write_text(json.dumps(m,indent=2)+'\n')
print('Behavior/grade diagnostics written to',OUT)
