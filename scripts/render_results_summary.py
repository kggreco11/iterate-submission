"""Render the research report and registry; no experiment execution."""
from pathlib import Path
import json,csv,html,re,datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];O=R/'results/results-so-far';A=R/'results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis';H=R/'results/experimental-history-20261115';rows=json.loads((O/'runs.json').read_text())
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','axes.titleweight':'bold','savefig.bbox':'tight'})
colors=['#176b87','#df7c27','#7d5299','#5d8264','#a64c57']
def cr(p):return list(csv.DictReader(p.open()))
def finish(fig,name):
 fig.savefig(O/(name+'.png'),dpi=170);fig.savefig(O/(name+'.svg'));plt.close(fig)
labels={'single_without_past':'Solo / exact','single_with_past':'Solo / Past','swarm_without_past':'Shared five / exact','swarm_with_past':'Shared five / Past','independent_without_past':'Independent five (stopped)'}
# Audited common budget curves, no extrapolation.
cs=cr(A/'curves.csv');ind=cr(A/'independent_curves.csv')
print('independent curve fields',list(ind[0]))
fig,ax=plt.subplots(figsize=(10,5.5))
for i,(cond,label) in enumerate(labels.items()):
 data=[x for x in cs if x['condition']==cond]
 if not data: data=ind
 if data:
  q=[float(x.get('queries',x.get('team_queries',0))) for x in data];v=[float(x.get('reward',x.get('best_reward',0))) for x in data]
  ax.step(q,v,where='post',label=label,color=colors[i],linestyle='--' if i==4 else '-')
ax.axvline(395,color='#999',ls=':',lw=1);ax.set(xlabel='Total charged queries',ylabel='Best valid reward',title='V3 dev_000: endpoint gains cost more queries');ax.legend(loc='lower right',fontsize=9);ax.grid(alpha=.15);finish(fig,'budget-curves')
fig,axs=plt.subplots(1,2,figsize=(12,5))
screen=[r for r in rows if r['experiment']=='v3-screen' and r['state']=='completed'];screen.sort(key=lambda x:x['reward'])
div=json.loads((H/'evidence/swarm-screening/results/swarm-screen-dev002/diversity.json').read_text())['conditions'];names=[r['sharing'] for r in screen]
axs[0].barh(names,[r['reward'] for r in screen],color='#176b87');axs[0].set(xlabel='Best valid reward',title='Observed quality')
axs[1].barh(names,[div[r['run_id'].split('-')[-2]]['final_distinct'] for r in screen],color='#df7c27');axs[1].set(xlabel='Distinct final separation structures',title='Retained alternatives');fig.suptitle('V3 dev_002: ten-agent screen, 500 total-query allocation');fig.tight_layout();finish(fig,'screen-quality-diversity')
fig,ax=plt.subplots(figsize=(10,5.5));gs=cr(A/'grade_sensitivity.csv')
for i,(cond,label) in enumerate(labels.items()):
 d=[x for x in gs if x['condition']==cond]
 if not d and i==4:d=[x for x in gs if 'independent' in x['condition']]
 ax.plot([float(x['threshold_increase_percentage_points']) for x in d],[100*float(x['net_loss_fraction']) for x in d],marker='o',label=label,color=colors[i])
ax.set(xlabel='Qualification threshold increase (percentage points)',ylabel='Modeled net-value loss (%)',title='Fixed-flow regrading exposes nominal-score fragility');ax.legend(fontsize=9);ax.grid(alpha=.15);finish(fig,'grade-risk')
fig,ax=plt.subplots(figsize=(10,5))
for model,color in [('claude-opus-5-5',colors[0]),('kimi-k3.1-pro',colors[1])]:
 d=sorted([x for x in rows if x['experiment']=='v3-first-look' and x['model']==model],key=lambda x:x['task']);ax.plot([x['task'][-3:] for x in d],[x['reward'] for x in d],'o-',label=model,color=color)
ax.set(xlabel='V3 development task',ylabel='Best valid reward',title='First looks: Opus leads on all four observed tasks');ax.legend();ax.grid(alpha=.15);finish(fig,'first-looks')
# Final study endpoints: show resource use alongside quality.
review=json.loads((O/'final-team-review.json').read_text())
final_rows=[r for r in review['rows'] if r['task']=='hc16v3_dev_002']
selected=[]
for model,agents,preset,label in [('claude-opus-5-5',1,'solo','Opus solo'),('kimi-k3.1-pro',50,'ring-5x2-k10','Kimi 50-agent islands'),('kimi-k3.1-pro',10,'open','Kimi 10-agent open'),('kimi-k3.1-pro',1,'solo','Kimi solo'),('deepseek-v4.1-flash',50,'ring-5x2-k10','DeepSeek 50-agent islands'),('deepseek-v4.1-flash',1,'solo','DeepSeek solo')]:
 r=next(r for r in final_rows if r['model']==model and r['agents']==agents and r['preset']==preset)
 selected.append((label,r))
fig,axs=plt.subplots(1,2,figsize=(12,5.5),gridspec_kw={'width_ratios':[1.2,1]},sharey=True)
y=list(range(len(selected)));palette=['#70539c','#176b87','#176b87','#176b87','#d07b28','#d07b28']
axs[0].barh(y,[r['reward'] for _,r in selected],color=palette);axs[1].barh(y,[r['queries'] for _,r in selected],color=palette)
axs[0].set_yticks(y,[label for label,_ in selected]);axs[0].invert_yaxis();axs[0].set(xlabel='Best valid reward',xlim=(0,6.2));axs[1].set(xlabel='Consumed simulator solves',xlim=(0,3000))
for i,(_,r) in enumerate(selected):
 axs[0].text(r['reward']+.07,i,f"{r['reward']:.3f}",va='center',fontsize=10)
 axs[1].text(r['queries']+35,i,f"{r['queries']:,}",va='center',fontsize=10)
fig.suptitle('Final V3 dev002 results: quality and resources');fig.text(.5,.01,'One run per condition; unequal budgets and thinking settings; historical harness limitations apply.',ha='center',fontsize=9);fig.tight_layout(rect=(0,.04,1,.95));finish(fig,'final-teams')
# Markdown remains the source for the master report and analysis.
esc=html.escape
style='''body{margin:0;background:#f5f6f8;color:#172833;font:17px/1.65 system-ui,sans-serif}main{max-width:1050px;margin:auto;padding:40px 28px 80px}h1{font-size:40px;line-height:1.15}h2{font-size:26px;line-height:1.3;margin-top:44px}p{max-width:79ch}a{color:#076681}nav{display:flex;gap:18px;flex-wrap:wrap;border-bottom:1px solid #ccd5dc;padding-bottom:16px}img{width:100%;background:white;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px;background:white}td,th{padding:11px;text-align:left;border-bottom:1px solid #dce2e6;vertical-align:top}th{background:#e8eff3}small,.muted{color:#52636e}section{margin:32px 0}.table{overflow:auto}.cards{display:flex;gap:18px;flex-wrap:wrap}.card{background:white;border:1px solid #dce2e6;padding:18px;flex:1;min-width:180px}.card strong{font-size:30px;display:block}input{padding:12px;font:inherit;width:min(500px,90%);margin:18px 0}code{font-size:14px;overflow-wrap:anywhere}'''
def page(title,body):return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+style+'</style><main><nav><a href="research-report.html">Research report</a><a href="index.html">Overview</a><a href="analysis.html">Full analysis</a><a href="inventory.html">Run inventory</a><a href="README.md">Update guide</a></nav>'+body+'</main></html>'
def report_inline(text, base):
 def replace(m):
  marker,label,target=m.groups()
  url=target if target.startswith(('https://','http://','#')) else __import__('os').path.relpath((base/target).resolve(),O)
  return ('<img src="'+esc(url,quote=True)+'" alt="'+esc(label,quote=True)+'">') if marker else ('<a href="'+esc(url,quote=True)+'">'+esc(label)+'</a>')
 pieces=[];last=0
 for m in re.finditer(r'(!?)\[([^\]]+)\]\(([^)]+)\)',text):
  pieces.append(esc(text[last:m.start()]));pieces.append(replace(m));last=m.end()
 pieces.append(esc(text[last:]));return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',''.join(pieces))
def markdown_page(path):
 parts=[]
 for para in path.read_text().split('\n\n'):
  inline=lambda t:report_inline(t,path.parent)
  if para.strip().startswith('<!--'):continue
  heading=re.match(r'^(#{1,4}) (.*)',para,re.S)
  if heading:
   level=len(heading[1]);parts.append(f'<h{level}>'+inline(heading[2])+f'</h{level}>')
  elif para.startswith('|'):
   lines=para.splitlines();head='<tr>'+''.join('<th>'+inline(x.strip())+'</th>' for x in lines[0].strip('|').split('|'))+'</tr>'
   body=''.join('<tr>'+''.join('<td>'+inline(x.strip())+'</td>' for x in line.strip('|').split('|'))+'</tr>' for line in lines[2:])
   parts.append('<div class="table"><table><thead>'+head+'</thead><tbody>'+body+'</tbody></table></div>')
  elif para.strip():parts.append('<p>'+inline(para)+'</p>')
 return ''.join(parts)
(O/'analysis.html').write_text(page('Detailed results analysis',markdown_page(O/'ANALYSIS.md')))
(O/'research-report.html').write_text(page('Research report',markdown_page(R/'RESEARCH_REPORT.md')))
# Preserve old external links while making the new title and location primary.
(O/'narrative.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=research-report.html"><title>Research report</title><a href="research-report.html">Open the research report</a>')

names={'v3-team-snapshot':'Final team-study reports and dev000 references', 'v3-deepseek':'DeepSeek dev_002 final study (new evidence)','v3-corpus':'New Kimi corpus campaign','hc12':'HC12 pilots','v2':'V2 first looks and memory comparison','v3-first-look':'V3 first looks','v3-100':'V3 100-per-agent pilot','v3-400':'V3 400-per-agent comparison','v3-screen':'V3 dev_002 organization screen','adapter-attempts':'DeepSeek adapter attempts'}
def fmt(v,n=2):return '—' if v in ('',None) else f'{float(v):,.{n}f}'
def table(rs):
 body='<div class="table"><table><thead><tr>'+''.join('<th>'+s+'</th>' for s in ['Run / evidence','Condition','Status','Queries / allocation','Reward','Model $'])+'</tr></thead><tbody>'
 for r in rs:
  body+='<tr><td><a href="'+esc(r.get('report',r['evidence']))+'">'+esc(r['run_id'])+'</a><br><small>'+esc(r['task']+' · '+r['model'])+'</small></td><td>'+esc(r['sharing'])+'<br><small>'+fmt(r['agents'],0)+' agents</small></td><td>'+esc('partial (round limit)' if r['status']=='round_limit' else r['state'])+'</td><td>'+('≥' if r.get('queries_lower_bound') else '')+fmt(r['queries'],0)+' / '+fmt(r['budget_total'],0)+'</td><td>'+fmt(r['reward'],4)+'</td><td>'+fmt(r['model_usd'])+'</td></tr>'
 return body+'</tbody></table></div>'
inv='<h1>All identified model runs</h1><p>One row per run ID. Agent members and duplicate artifact paths are not repeats. Missing values mean unknown. Costs are saved model estimates; errors may have unpriced requests.</p><input aria-label="Filter runs" id="filter" placeholder="Filter by model, task, condition, or run ID">'
for g,title in names.items():
 rs=[r for r in rows if r['experiment']==g];inv+='<section><h2>'+title+'</h2>'+table(rs)+'</section>'
 pagebody='<h1>'+title+'</h1>'+table(rs)+'<p><a href="analysis.html">Interpretation and comparison limits</a></p>'
 if g=='v3-corpus':pagebody+='<p><a href="corpus-comparison.html">Completed corpus campaign diagnostic</a></p>'
 if g=='v3-400':pagebody+='<img src="budget-curves.png" alt="Best valid reward versus total charged queries"><img src="grade-risk.png" alt="Net loss versus qualification threshold increase"><p><a href="../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/behavior.html">Detailed behavior audit</a> · <a href="../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/independent.html">Independent control</a></p>'
 if g=='v3-screen':pagebody+='<img src="screen-quality-diversity.png" alt="Quality and retained structures by screening condition">'
 if g=='v3-first-look':pagebody+='<img src="first-looks.png" alt="Opus and Kimi first-look rewards by task">'
 (O/(g+'.html')).write_text(page(title,pagebody))
inv+='''<script>document.querySelector('#filter').addEventListener('input',e=>{let q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script>''';(O/'inventory.html').write_text(page('Run inventory',inv))
progress=json.loads((O/'current-campaign-snapshot.json').read_text());stamp=datetime.datetime.fromtimestamp(progress['captured_epoch'],datetime.timezone.utc).isoformat();p=next((x for x in progress['agents'] if x['condition']=='single_baseline'),progress['agents'][0])
completed=[r for r in rows if r['state']=='completed']
body='<h1>Experiment results</h1><p><a href="research-report.html">Start here: research report, final results and evidence</a></p><p>Single agents, swarms and memory in chemical plant design. <a href="analysis.html">Read the findings</a> · <a href="inventory.html">Inspect the evidence</a>.</p>'
body+='<h2>Final V3 dev002 results</h2><p>The 50-agent island configurations reached the best team endpoints: Kimi 3.866 at 2,496 solves and DeepSeek 2.160 at 2,349. Opus solo reached 5.331 at 74 solves. These are single-run endpoints with unequal budgets and model thinking settings; historical harness defects limit claims about exchange policies. <a href="final-study.html">Final results and evidence</a>.</p><img src="final-teams.png" alt="Final dev002 reward and consumed solves">'
body+='<h2>Earlier memory comparison</h2><p>On dev000, the sharing swarm reached 7.65% higher simulated annualized net value than solo using roughly five times the queries; solo led at equal queries. Extra Past retrieval did not improve endpoints in that matrix. <a href="v3-400.html">Memory-control evidence</a>.</p>'
body+='<h2>Studies</h2><ul>'+''.join('<li><a href="'+g+'.html">'+title+'</a></li>' for g,title in names.items())+'</ul>'
body+='<h2>Evidence coverage</h2><p>'+str(len(completed))+' completed runs with identifiable summaries; '+str(len(rows)-len(completed))+' stopped or partial registry entries. Final exports supersede earlier snapshots for the same run IDs. <a href="runs.csv">Download registry</a> · <a href="provenance.json">Source commits</a>.</p>'
body+='<p>The corpus campaign ended with completed solo and immediate-sharing conditions; delay25 is user-stopped partial and delay50 never started. <a href="corpus-comparison.html">Diagnostic appendix</a>. This result is retained in the full record without an architecture-wide conclusion.</p>'
body+='<p>Saved corpus campaign snapshot captured '+esc(stamp)+'. <a href="corpus-comparison.html">Completed campaign diagnostic</a>. This page does not report live experiment status.</p>'
body+='<p><a href="../INDEX.md">Historical benchmark catalogue</a> · <a href="../experimental-history-20261115/README.md">Historical research narrative</a></p>'
fb='<h1>Final V3 dev002 team study</h1><p>19 uniquely identified runs: 17 all_done and two round-limit outcomes. Budgets and model thinking settings differ. These runs predate migration-selection and managed-budget fixes; organization labels describe intended treatments.</p><img src="final-teams.png" alt="Final dev002 rewards and consumed solves">'
fb+=table(sorted([r for r in rows if r.get('experiment_source')=='team-report-v1' and r['task']=='hc16v3_dev_002'],key=lambda r:-r['reward']))
fb+='<p><a href="../../docs/FINAL_RESULTS.md">Setup and interpretation limits</a> · <a href="final-team-review.json">Raw-source hashes and reconciliation</a> · <a href="final-study-evidence/reviewed-snapshot.json">Earlier incomplete snapshot</a></p>'
fb+='<h2>Separate dev000 references</h2><p>Excluded from the dev002 leaderboard. Forced continuation and free stopping are different runs; their difference is not an isolated causal effect.</p>'+table([r for r in rows if r.get('experiment_source')=='team-report-v1' and r['task']=='hc16v3_dev_000'])
(O/'final-study.html').write_text(page('Final V3 dev002 results',fb))
(O/'index.html').write_text(page('Results so far',body))
print('Rendered',len(rows),'runs and five charts')
