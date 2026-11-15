"""Archived one-off builder, retained to explain the frozen historical inventory.

This script consumed planning files and local snapshots that are no longer active
inputs. Refresh current results with scripts/build_results_summary.py instead.
"""
raise SystemExit("Archived builder: historical evidence is frozen; use scripts/build_results_summary.py for the maintained inventory.")

from pathlib import Path
import json,csv,hashlib,datetime,shutil
from zoneinfo import ZoneInfo
R=Path(__file__).resolve().parents[2]; W=R/'results/experimental-history-20261115/evidence/source-snapshot'; O=R/'results/experimental-history-20261115'
rows=[]; provenance=[]
def preserve(p,name):
 p=Path(p); b=p.read_bytes(); q=O/'evidence'/name;q.write_bytes(b)
 provenance.append(dict(source=str(p),snapshot=str(q.relative_to(O)),sha256=hashlib.sha256(b).hexdigest()))
 return 'evidence/'+name
def add(**kw): rows.append(kw)
# Completed model experiments only. The credit-interrupted HC12 Opus first look is excluded by user direction.
for root,pattern in [(R,'hc16v2_dev_*/single-agent/*/*/summary.json'),(W,'hc16v3_dev_*/single-agent/*/*/summary.json'),(R,'hc12_dev_000/single-agent/gpt*/*/summary.json')]:
 for p in sorted((root/'results').glob(pattern)):
  s=json.loads(p.read_text());rid=s.get('run_id',p.parent.name);task=s.get('task',p.parts[-5]);model=s.get('model',p.parts[-3]);budget=400 if 'opus' in model else (200 if ('200' in rid or 'v2-kimi' in rid) else 50)
  if any(r.get('run_id')==rid for r in rows):continue
  ev=preserve(p,rid+'-summary.json'); unknown=s.get('requests_with_unknown_cost',0)>0 or s.get('cost_usd','missing') is None
  add(run_id=rid,task=task,model=model,model_identity='recorded API model string; immutable revision not captured' if 'kimi' not in model else 'reporting alias; exact served weight identity not verified',agents=1,sharing='own history; no external shared memory',budget_per_agent=budget,budget_total=budget,status='completed; '+s.get('status',s.get('stop_reason','finished')),queries=s.get('solves_used'),backend_calls='',reward=s.get('best_valid_reward',s.get('best_reward')),net_usd_per_year='',wall_s=s.get('wall_s'),model_usd='' if unknown else s.get('usd_estimated_total'),cost_note='unknown' if unknown else 'historical model estimate; excludes VM and memory',requests=s.get('requests',''),input_tokens=s.get('input_tokens',''),output_tokens=s.get('output_tokens',''),evidence=ev,original_evidence=str(p))
p=R/'results/hc16v2_dev_000/shared-memory-5/kimi-k3.1-pro/swarm-a1b45716fe3444679f33125db48b89b7/summary.json';s=json.loads(p.read_text())
add(run_id=s['run_id'],task='hc16v2_dev_000',model='kimi-k3.1-pro',model_identity='reporting alias; exact served weight identity not verified',agents=5,sharing='Past retrieval; historical V2 feedback/context defects',budget_per_agent=100,budget_total=500,status='completed; all_finished_or_exhausted (three historical dollar stops)',queries=s['team_distinct_queries'],backend_calls=s['backend_calls'],reward=max(a['best_valid_reward'] for a in s['agents'].values()),net_usd_per_year=2786809479,wall_s=s['wall_s'],model_usd=s['known_llm_usd'],cost_note='model estimate only',requests=sum(a['usage']['requests'] for a in s['agents'].values()),input_tokens=s['team_input_tokens'],output_tokens=s['team_output_tokens'],evidence=preserve(p,s['run_id']+'-summary.json'),original_evidence=str(p))
p=W/'runs/v3-campaign-launch/snapshot.json'; ev=preserve(p,'v3-100-campaign-snapshot.json')
for x in json.loads(p.read_text())['summary']['outcomes']:
 add(run_id=x['run'].split('\\')[-1],task='hc16v3_dev_000',model='kimi-k3.1-pro',model_identity='reporting alias; controller model_id is endpoint hostname',agents=x['agents'],sharing=x['memory']+'; local feedback/incumbent protocol V3',budget_per_agent=100,budget_total=x['total_budget'],status='completed; '+x['status'],queries=x['queries'],backend_calls=x['backend_calls'],reward=x['best_valid_reward'],net_usd_per_year='',wall_s=x['wall_s'],model_usd=x['estimated_model_usd'],cost_note='model estimate only; snapshot-level evidence',requests='',input_tokens=x['input_tokens'],output_tokens=x['output_tokens'],evidence=ev,original_evidence=str(p))
p=R/'results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/metrics.csv';metrics=list(csv.DictReader(p.open()));preserve(p,'v3-400-metrics.csv')
for x in metrics:
 add(run_id=x['run_id'],task='hc16v3_dev_000',model='kimi-k3.1-pro',model_identity='reporting alias; immutable served revision not verified',agents=int(x['agents']),sharing=x['condition'],budget_per_agent=400,budget_total=int(x['allocation']),status='completed; '+x['status'],queries=int(x['queries']),backend_calls=int(x['backend_calls']),reward=float(x['reward']),net_usd_per_year=float(x['net_usd_per_year']),wall_s=float(x['wall_minutes'])*60,model_usd=float(x['model_usd']),cost_note='model estimate only; excludes recovery attempts',requests=int(x['requests']),input_tokens=int(x['input_tokens']),output_tokens=int(x['output_tokens']),evidence='../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/report-data.json',original_evidence=str(p))
# Snapshot changing status and relevant configuration, never alter controllers.
for rel,name in [('runs/v3-independent-400-prep/snapshot.json','independent-snapshot.json'),('runs/v3-independent-400-prep/controller.json','independent-controller.json'),('runs/v3-screening-400-prep/plan.json','next-campaign-plan.json'),('runs/v3-screening-400-prep/validation.json','next-campaign-offline-validation.json'),('runs/v3-campaign-launch/plan.json','v3-100-plan.json')]:
 preserve(W/rel,name)
for rel,name in [('docs/EVALUATION_2026-11-14.md','historical-evaluation.md'),('docs/TASK_V3.md','task-v3.md'),('results/all_results.csv','historical-reference-inventory.csv'),('results/hc16v3-side-draw/qualification.json','side-draw-qualification.json'),('results/hc16v3-first-look/polish_check.json','v3-polish.json'),('results/hc16v3-first-look/polish_v2plants_at_v3.json','v2-plants-at-v3-polish.json')]: preserve(W/rel,name)
for rel,name in [('workplan.md','historical-workplan.md'),('docs/SWARM_MEMORY_AUDIT.md','v2-forensic-audit.md')]:preserve(R/rel,name)
cols=['run_id','task','model','model_identity','agents','sharing','budget_per_agent','budget_total','status','queries','backend_calls','reward','net_usd_per_year','wall_s','model_usd','cost_note','requests','input_tokens','output_tokens','evidence','original_evidence']
with (O/'completed-runs.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader();writer.writerows(rows)
# Separate non-model reference inventory; source aggregate has no formal run IDs for many records.
hist=list(csv.DictReader((W/'results/all_results.csv').open()));refs=[x for x in hist if x['method']!='agent']
with (O/'simulator-reference-inventory.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(hist[0]));writer.writeheader();writer.writerows(refs)
assert len({r['run_id'] for r in rows})==len(rows)
assert all(int(r['queries']) <= int(r['budget_total']) for r in rows)
assert len(rows)==20,len(rows)
assert sum(int(x['queries']) for x in metrics)==4736
assert abs(sum(float(x['model_usd']) for x in metrics)-48.190418)<1e-8
assert sum(x['total_budget'] for x in json.loads((O/'evidence/next-campaign-plan.json').read_text())['trials'])==12400
now=datetime.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(timespec='seconds')
(O/'provenance.json').write_text(json.dumps(dict(compiled_at=now,primary_checkout=str(R),implementation_worktree=str(W),sources=provenance,policy='Main inventory includes completed plant-design model experiments only. Setup checks, failed/interrupted attempts, running control, and future campaign excluded. Historical evidence snapshots may retain excluded records for audit.'),indent=2))
# Readable full run table, with links to dedicated evidence.
t=['# Completed experiment inventory','',f'Compiled {now}. 20 completed plant-design model runs; per-agent budgets are announced ceilings, not necessarily consumed. Paid infrastructure checks and failed/interrupted attempts are excluded. Empty CSV values mean unknown or not independently extracted, never zero.','', '| Run / evidence | Task | Model | Agents / sharing | Budget each / total | Used / backend | Best reward | Model $ | Wall min |','|---|---|---|---|---:|---:|---:|---:|---:|']
for r in rows:
 def fmt(x,n=4):return 'unknown' if x in ('',None) else f'{float(x):.{n}f}'
 t.append(f"| [{r['run_id']}]({r['evidence']}) | {r['task']} | {r['model']} | {r['agents']} / {r['sharing']} | {r['budget_per_agent']} / {r['budget_total']} | {r['queries']} / {r['backend_calls'] or 'unknown'} | {fmt(r['reward'])} | {fmt(r['model_usd'],2)} | {fmt(float(r['wall_s'])/60,1)} |")
(O/'inventory.md').write_text('\n'.join(t)+'\n')
print(now,'completed runs',len(rows),'reference rows',len(refs))
