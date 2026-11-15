"""Integrate the user-stopped independent control without rewriting historical evidence."""
import json,csv,hashlib,html,itertools,math,re
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
R=Path(__file__).resolve().parents[1];O=R/'results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis'
E=json.loads((R/'runs/v3-independent-analysis/evidence.json').read_text());D=json.loads((O/'report-data.json').read_text());T=D['task'];sec=T['annual_operating_hours']*3600;norm=max(f*p*sec for f,p in zip(T['feed_flows_mol_s'],T['prices_usd_per_mol']));end=E['curve'][-1];m=E['winner']['measured'];agents=E['agents'];condition='independent_without_past'
checks=[]
def check(n,v):checks.append({'check':n,'passed':bool(v)})
check('user-stopped status',E['status']['state']=='user_stopped');check('charged counts reconcile',sum(a['queries'] for a in agents.values())==end['queries']);check('per-agent allowance',all(a['queries']<=400 for a in agents.values()));check('best of five',abs(max(a['best'] for a in agents.values())-end['reward'])<1e-10);check('winning plant objective',math.isclose(m['revenue']-m['tac'],norm*m['reward'],rel_tol=1e-9));check('winning plant valid',m['valid']);check('no source copying',E['counts'].get('source_copy',0)==0);check('no citations',E['counts'].get('citations',0)==0);check('no retrieved findings',E['counts'].get('retrieved_findings',0)==0);check('no included shared memory',E['counts'].get('included_memories',0)==0)
for axis in ['queries','elapsed_s','usd','input_tokens','output_tokens']:
 vals=[p[axis] for p in E['curve']];check('monotone '+axis,all(b>=a-1e-8 for a,b in zip(vals,vals[1:])))
for a,v in agents.items():check(a+' saved usage covers policy outcomes',v['usage']['requests']>=v['usage']['policy_events'])
def write(name,rows):
 fields=list(dict.fromkeys(k for row in rows for k in row))
 with (O/name).open('w',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def append(name,rows):
 old=list(csv.DictReader((O/name).open())) if (O/name).exists() else []
 write(name,[r for r in old if r.get('condition')!=condition]+rows)
def reprice(delta):
 revenue=0
 for p in m['sold']:
  f=p['flows'];total=sum(f);i=max(range(len(f)),key=lambda k:f[k]);v=0
  if total and f[i]/total>=T['required_purity']+delta:v=f[i]*T['prices_usd_per_mol'][i]*sec*(T['economics']['premium']['multiplier'] if f[i]/total>=T['economics']['premium']['purity']+delta else 1)
  for g in T['economics']['groups']:
   ix=[T['components'].index(c) for c in g['members']];fg=sum(f[i] for i in ix)
   if total and fg/total>=g['min_fraction']+delta:v=max(v,fg*g['discount']*sum(T['prices_usd_per_mol'][i] for i in ix)/len(ix)*sec)
  revenue+=v
 return revenue
check('saved streams reprice to revenue',math.isclose(reprice(0),m['revenue'],rel_tol=1e-9))
check('component closure',all(abs(sum(p['flows'][i] for p in m['sold'])-f)<max(1e-5,abs(f)*1e-6) for i,f in enumerate(T['feed_flows_mol_s'])))
row=dict(condition=condition,status='user_stopped',agents=5,reward=end['reward'],queries=end['queries'],allocation=2000,backend_calls=E['backend_calls'],cache_hits=E['cache_hits'],net_usd_per_year=norm*end['reward'],revenue_usd_per_year=m['revenue'],annualized_cost_usd=m['tac'],wall_minutes=end['elapsed_s']/60,model_usd=end['usd'],input_tokens=end['input_tokens'],output_tokens=end['output_tokens'],attempts=E['counts']['submissions'],valid_attempts=E['counts']['valid'],invalid_attempts=E['counts']['invalid'],rejected_attempts=E['counts']['rejected'],run_id=E['config']['run_id'],measurement_note='Logged partial endpoint; backend missing if final service export absent')
append('metrics.csv',[row]);append('agent_metrics.csv',[dict(condition=condition,agent=a,queries=v['queries'],best_reward=v['best'],final_valid=(v['last'] or {}).get('valid'),final_reward=(v['last'] or {}).get('reward'),status='user_stopped_run',**v['usage']) for a,v in agents.items()])
write('independent_curves.csv',[dict(condition=condition,**p) for p in E['curve']]);append('grade_sensitivity.csv',[dict(condition=condition,threshold_increase_percentage_points=pp,annual_net_usd=reprice(pp/100)-m['tac'],annual_revenue_loss_usd=m['revenue']-reprice(pp/100),net_loss_fraction=(m['revenue']-reprice(pp/100))/(m['revenue']-m['tac'])) for pp in [0,.01,.05,.1,.25,.5]])
pairs=[]
for (a,v),(b,w) in itertools.combinations(agents.items(),2):
 d=v['best_design'];e=w['best_design'];pairs.append(dict(condition=condition,agent_a=a,agent_b=b,changed_node_settings=sum(d.get(k)!=e.get(k) for k in set(d)|set(e)),same_topology=set(d)==set(e)))
append('final_design_distance.csv',pairs)
append('behavior_rates.csv',[dict(condition=condition,submissions=E['counts']['submissions'],**{k:E['counts'].get(k,0)/E['counts']['submissions'] for k in ['source_copy','duplicate','one_node_change','topology_change','below_own_best']},status='user_stopped')])
complete=[r for r in D['runs'] if r['summary']['status']=='all_finished_or_exhausted'];labels={'single_without_past':'Single / no Past','single_with_past':'Single / Past','swarm_without_past':'Shared swarm / no Past','swarm_with_past':'Shared swarm / Past'}
series=[(labels[r['config']['condition']],r['curve']) for r in complete]+[('Independent five / early stop',E['curve'])]
with PdfPages(O/'independent_comparison.pdf') as pdf:
 fig,axs=plt.subplots(2,2,figsize=(12,9))
 for ax,(axis,title,scale) in zip(axs.flat,[('queries','Charged team queries',1),('elapsed_s','Elapsed minutes',60),('usd','Estimated model USD',1),('input_tokens','Input tokens (millions)',1e6)]):
  for name,points in series:ax.step([p[axis]/scale for p in points],[p['reward']*norm/1e9 for p in points],where='post',label=name)
  ax.set(xlabel=title,ylabel='Best modeled annual net ($B)');ax.grid(alpha=.2)
 axs[0,0].legend(fontsize=7);fig.suptitle('Observed V3 trajectories — independent control stopped by user');fig.tight_layout();fig.savefig(O/'plots/independent_comparison.png',dpi=160);pdf.savefig(fig);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,5))
 for a,v in agents.items():ax.step([p['agent_queries'] for p in v['curve']],[p['reward'] for p in v['curve']],where='post',label=a)
 ax.set(xlabel='Own charged queries',ylabel='Best valid reward',title='Independent agents: no extension beyond observed improvements');ax.legend();fig.tight_layout();fig.savefig(O/'plots/independent_agents.png',dpi=160);pdf.savefig(fig);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,5));xs=[i/1000 for i in range(501)];ax.plot(xs,[(reprice(x/100)-m['tac'])/1e9 for x in xs]);ax.set(xlabel='Grade threshold increase (percentage points)',ylabel='Annual net ($B)',title='Independent winner: fixed-flow repricing, not physical robustness');fig.tight_layout();fig.savefig(O/'plots/independent_grade.png',dpi=160);pdf.savefig(fig);plt.close(fig)
# Grade margins and physical component recovery from saved terminal flows.
products=[];recovery=[0.0]*len(T['components'])
for product in m['sold']:
 f=product['flows'];total=sum(f);kind=product.get('kind','none');ix=[max(range(len(f)),key=lambda i:f[i])];threshold=T['required_purity']
 if kind.startswith('blend: '):
  g=next(g for g in T['economics']['groups'] if g['name']==kind[7:]);ix=[T['components'].index(c) for c in g['members']];threshold=g['min_fraction']
 elif kind=='premium':threshold=T['economics']['premium']['purity']
 purity=sum(f[i] for i in ix)/total if total else 0
 if product['value']>0:
  for i in ix:recovery[i]+=f[i]
 products.append(dict(condition=condition,node=product['node'] or 'Feed',kind=kind,annual_revenue_usd=product['value'],purity=purity,threshold=threshold,headroom_percentage_points=(purity-threshold)*100,qualifies=product['value']>0))
write('independent_products.csv',products)
write('independent_component_recovery.csv',[dict(component=c,feed_mol_s=f,qualifying_product_mol_s=recovery[i],physical_qualifying_recovery=recovery[i]/f if f else None) for i,(c,f) in enumerate(zip(T['components'],T['feed_flows_mol_s']))])
first=next((p for p in E['curve'] if p['reward']>0),None)
write('independent_first_positive.csv',[dict(status='user_stopped',**first)] if first else [dict(status='user_stopped',reached=False)])
matched=[]
for cap in [200,395,400,800,1200,1600]:
 for name,points in series:
  eligible=[p for p in points if p['queries']<=cap]
  if eligible and points[-1]['queries']>=cap:matched.append(dict(condition=name,query_cap=cap,best_reward=eligible[-1]['reward']))
write('independent_matched_queries.csv',matched)
D['independent_partial']=E;(O/'report-data.json').write_text(json.dumps(D,indent=1)+'\n');(O/'independent-evidence.json').write_text(json.dumps(E,indent=2)+'\n');(O/'independent-validation.json').write_text(json.dumps(checks,indent=2))
summary=O/'summary.json';s=json.loads(summary.read_text());s['independent_partial_metrics']=row;s['independent_partial_validation']=checks;summary.write_text(json.dumps(s,indent=2))
B=json.loads((O/'behavior-data.json').read_text());B['independent_partial']={'counts':E['counts'],'agents':agents,'final_pair_diffs':pairs,'status':'user_stopped'};(O/'behavior-data.json').write_text(json.dumps(B,indent=2))
net=norm*end['reward'];lines=['# Independent five-agent control — early-stopped analysis','',f"Run `{E['config']['run_id']}`. Status **user_stopped**. The requested cutoff was 19:39:30 UTC; the confirmed direct stop is recorded in the evidence. This is not a completed 2,000-query result.",'',f"Logged charged queries: **{end['queries']}/2000**. Best valid reward: **{end['reward']:.6f}**. Best modeled annual net: **${net/1e9:.3f}B/year**. Saved model cost: **${end['usd']:.2f}**. Last logged elapsed time: **{end['elapsed_s']/60:.1f} minutes**.",'',f"Backend calls: **{E['backend_calls'] if E['backend_calls'] is not None else 'unavailable'}**. Charged queries are not backend calls. Forced termination may leave an in-flight operation outside saved submission counts.",'','| Agent | Logged queries | Best reward |','|---|---:|---:|']
lines += [f"| {a} | {v['queries']} | {v['best']:.6f} |" for a,v in agents.items()]
lines+=['','## Comparison and behavior','']
for r in complete:
 val=r['curve'][-1]['reward'];lines.append(f"- Versus {labels[r['config']['condition']]} endpoint ({val:.6f}), the independent best is {(end['reward']/val-1)*100:+.2f}%. Resource use and stopping rules differ; this is descriptive, not a causal estimate.")
lines += [f"- Saved submissions: {E['counts']['submissions']}; valid {E['counts']['valid']}, invalid {E['counts']['invalid']}, rejected {E['counts']['rejected']}.",f"- Source-copy submissions: {E['counts'].get('source_copy',0)}; citation-bearing submissions: {E['counts'].get('citations',0)}; retrieved findings: {E['counts'].get('retrieved_findings',0)}.",f"- Best-design topology matches in {sum(p['same_topology'] for p in pairs)}/{len(pairs)} agent pairs. Different settings/topologies are measured separately from reward.",f"- Increasing all grade thresholds by 0.05 percentage points reduces saved winner net by {(m['revenue']-reprice(.0005))/net*100:.2f}%. This is fixed-flow repricing with fallback sale categories, not a new simulation.",'','## Evidence and limits','','The original four completed runs and two failed attempts are preserved. This control is stored separately as `independent_partial` in report-data.json, preventing it from being classified as a completed or failed infrastructure trial. The shared swarms have a 2,000-query allowance; the single agents have 400. Matched-query CSVs compare observed prefixes only. One run per condition cannot establish statistical reliability.','',f"Validation: {sum(c['passed'] for c in checks)}/{len(checks)} checks passed. Usage covers saved records; any unmatched in-flight call is not silently reconstructed.",'','[Combined figures](independent_comparison.pdf) · [Evidence](independent-evidence.json) · [Matched queries](independent_matched_queries.csv) · [Validation](independent-validation.json)']
text='\n'.join(lines)+'\n';(O/'independent-analysis.md').write_text(text)
def render_md(text):
 parts=[];table=False
 for line in text.splitlines():
  if line.startswith('|'):
   if set(line.replace('|','').replace(':','').replace('-','').strip())==set():continue
   if not table:parts.append('<table>');table=True
   parts.append('<tr>'+''.join('<td>'+html.escape(c.strip())+'</td>' for c in line.strip('|').split('|'))+'</tr>');continue
  if table:parts.append('</table>');table=False
  line=html.escape(line)
  line=re.sub(r'\*\*(.*?)\*\*',r'<strong>\1</strong>',line)
  line=re.sub(r'\[([^]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',line)
  if line.startswith('## '):parts.append('<h2>'+line[3:]+'</h2>')
  elif line.startswith('# '):parts.append('<h1>'+line[2:]+'</h1>')
  elif line:parts.append('<p>'+line+'</p>')
 if table:parts.append('</table>')
 return ''.join(parts)
page='<html><head><meta charset="utf-8"><title>Independent control — V3 comparison</title><style>body{max-width:1100px;margin:40px auto;font:17px system-ui;line-height:1.55}td{padding:8px 18px;border-bottom:1px solid #ddd}img{width:100%}</style></head><body><a href="index.html">Back to V3 analysis</a>'+render_md(text)+''+''.join('<img src="plots/'+n+'.png">' for n in ['independent_comparison','independent_agents','independent_grade'])+'</body></html>'
(O/'independent.html').write_text(page)
for name in ['README.md','behavior-analysis.md']:
 p=O/name;original=p.read_text();marker='\n## Independent control update\n';original=original.split(marker)[0];p.write_text(original+marker+'\nThe user-stopped independent control is now analyzed separately from completed runs. [Updated five-condition comparison](independent.html) · [Analysis and caveats](independent-analysis.md). The original findings above remain a historical four-condition analysis.\n')
for name in ['index.html','behavior.html']:
 p=O/name;s=p.read_text();banner='<aside id="independent-update" style="padding:18px;background:#e8f3f5"><strong>Update: independent control stopped by user.</strong> <a href="independent.html">View five-condition curves, partial results, and caveats</a>.</aside>'
 if 'id="independent-update"' not in s:s=s.replace('<body>','<body>'+banner,1)
 p.write_text(s)
(O/'provenance/analyze_v3_independent.py').write_bytes(Path(__file__).read_bytes());(O/'provenance/extract_independent_partial.py').write_bytes((R/'runs/v3-independent-analysis/extract.py').read_bytes())
p=O/'manifest.json';manifest=json.loads(p.read_text());manifest['status']='Four completed conditions plus user-stopped independent control';manifest['sha256']={str(f.relative_to(O)):hashlib.sha256(f.read_bytes()).hexdigest() for f in O.rglob('*') if f.is_file() and f.name!='manifest.json'};p.write_text(json.dumps(manifest,indent=2))
print(json.dumps({'metrics':row,'validation':checks,'report':str(O/'independent.html')},indent=2))
assert all(c['passed'] for c in checks)
