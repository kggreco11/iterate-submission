"""Read-only run inventory. Refresh Git refs separately; never launches or polls experiments."""
from pathlib import Path
import csv, json, subprocess, hashlib, datetime, re, os, argparse
R=Path(__file__).resolve().parents[1]; O=R/'results/results-so-far'; H=R/'results/experimental-history-20261115'; A=R/'results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis'
O.mkdir(exist_ok=True); (O/'evidence').mkdir(exist_ok=True)
def git(*args): return subprocess.check_output(['git',*args],cwd=R,text=True).strip()
def read(p): return json.loads(p.read_text())
def csvread(p):return list(csv.DictReader(p.open()))
def save(name,d): (O/name).write_text(json.dumps(d,indent=2)+'\n')
def num(v):return None if v in ('',None) else float(v)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--refs-from',type=Path,help='Use the immutable refs in a saved provenance JSON instead of current remote tips')
args=parser.parse_args()
pinned_refs=read(args.refs_from)['refs'] if args.refs_from else None
rows={}; sources=[]; exclusions=[]; conflicts=[]; aliases={}; refs={}
def capture(b,source):
 sha=hashlib.sha256(b).hexdigest(); dest='evidence/'+sha[:20]+'.json'; (O/dest).write_bytes(b);sources.append(dict(source=source,path=dest,sha256=sha));return dest
def add(r,source,overwrite=False):
 rid=r['run_id'];aliases.setdefault(rid,[]).append(source)
 if rid in rows and not overwrite:
  old=rows[rid]
  if old.get('queries') is not None and r.get('queries') is not None and float(old['queries'])!=float(r['queries']):conflicts.append(dict(run_id=rid,field='queries',retained=old['queries'],other=r['queries'],source=source))
  return
 rows[rid]=r
# Reviewed historical records, with original evidence preserved.
for r in csvread(H/'completed-runs.csv'):
 r['evidence']=os.path.relpath((H/r['evidence']).resolve(),O)
 for k in ['agents','budget_total','queries','backend_calls','reward','model_usd','wall_s','net_usd_per_year','requests','input_tokens','output_tokens']:r[k]=num(r.get(k))
 r['state']='completed';add(r,r['original_evidence'])
def parse(s,p,source,ev):
 if '/agents/' in p or '/raw/agent-' in p:
  exclusions.append(dict(source=source,reason='agent member summary; requires parent-run reconciliation'));return
 if not isinstance(s,dict) or not s.get('run_id'):exclusions.append(dict(source=source,reason='not a run summary'));return
 if any(t in p.lower() for t in ['scripted','smoke','qualification','azure-runtime','integration']):exclusions.append(dict(source=source,reason='infrastructure / qualification / scripted'));return
 task=s.get('task') or next((x for x in p.split('/') if re.fullmatch(r'hc\d+(?:v\d+)?_dev_\d+',x)),None)
 if not task:exclusions.append(dict(source=source,reason='task not identifiable'));return
 if not any(k in s for k in ['best_valid_reward','team_best','team_distinct_queries']):exclusions.append(dict(source=source,reason='unrecognized experiment schema'));return
 ag=s.get('agents',{}); n=len(ag) if isinstance(ag,(dict,list)) else ag
 n=n or s.get('workers') or 1;model=s.get('model') or ('kimi-k3.1-pro' if 'swarm-screen' in p else next((x for x in p.split('/') if x.startswith(('gpt-','claude-','kimi-','opus-','deepseek-'))),'unknown'))
 status=s.get('status','unknown');completed=status in ['all_done','all_finished_or_exhausted','budget_exhausted','finished','completed','complete','done','budget']
 q=s.get('team_solves',s.get('team_distinct_queries',s.get('solves_used')))
 reward=s.get('team_best',s.get('best_valid_reward'))
 if reward is None and isinstance(ag,dict):reward=max((a.get('best_valid_reward',0) for a in ag.values()),default=0)
 cost=s.get('usd',s.get('known_llm_usd',s.get('usd_estimated_total')))
 r=dict(run_id=s['run_id'],task=task,model=model,agents=n,sharing=s.get('name','single-agent' if n==1 else 'shared-memory'),budget_per_agent='',budget_total=s.get('team_budget'),status=status,state='completed' if completed else 'failed_or_partial',queries=q,backend_calls=s.get('backend_calls'),reward=reward,model_usd=cost,wall_s=s.get('wall_s'),net_usd_per_year=None,evidence=ev,cost_note='saved estimate; unknown-cost requests: '+str(s.get('requests_with_unknown_cost',s.get('unknown_cost_requests',0))),original_evidence=source)
 add(r,source)
# Scan every fetched remote branch, newest first, and local canonical results. No raw prompts copied.
refnames=list(pinned_refs) if pinned_refs is not None else git('for-each-ref','--sort=-committerdate','--format=%(refname:short)','refs/remotes/origin').splitlines()
seen_blobs=set()
for ref in refnames:
 if ref=='origin':continue
 sha=pinned_refs[ref] if pinned_refs is not None else git('rev-parse',ref);refs[ref]=sha
 for line in git('ls-tree','-r',sha,'results').splitlines():
  meta,p=line.split('\t',1)
  if not p.endswith('/summary.json'):continue
  blob=meta.split()[2]
  if blob in seen_blobs:continue
  seen_blobs.add(blob); b=subprocess.check_output(['git','cat-file','blob',blob],cwd=R); source=f'git:{sha}:{p}'
  try:s=json.loads(b)
  except ValueError:exclusions.append(dict(source=source,reason='invalid JSON'));continue
  parse(s,p,source,capture(b,source))
for p in sorted((R/'results').glob('**/summary.json')):
 if any(x in p.parts for x in ['results-so-far','experimental-history-20261115','comparison']):continue
 b=p.read_bytes();source=str(p.relative_to(R));parse(json.loads(b),source,source,capture(b,source))
# Canonical team exports carry identity in report-data config, not the compact summary.
for p in (R/'results').glob('hc16v3_dev_*/team-*/*/*/report-data.json'):
 d=read(p)
 if d.get('schema')!='team-report-v1':continue
 c=d['config'];s=d['summary'];budgets=c.get('budgets',{});n=len(budgets) or c.get('config',{}).get('n',1)
 ev=capture(json.dumps({'config':c,'summary':s}).encode(),str(p.relative_to(R)))
 normalized=dict(s,run_id=c['run_id'],task=c['task'],model=c['model'],agents=n,team_budget=sum(budgets.values()),usd=s.get('usd_cached_price_estimate',s.get('usd')))
 # Canonical export binds this summary to its configuration; replace generic
 # snapshots so first-seen incomplete metadata cannot suppress budget or cost.
 rows.pop(c['run_id'],None)
 parse(normalized,str(p.relative_to(R)),str(p.relative_to(R)),ev)
 r=rows[c['run_id']];r.update(cost_note='cached-price estimate from canonical report; not provider billing',sharing=p.parts[-4],budget_per_agent=c.get('config',{}).get('budget'),report=os.path.relpath(p.with_name('index.html'),O),experiment_source='team-report-v1')
# Preserve the exported failure summary when the local ignored transport is absent.
archived=O/'adapter-failure.json'
if archived.exists():
 r=read(archived);add(r,'saved adapter failure evidence')

# Campaign attempts from audited V3 report, including recoveries that completed inventory excludes.
report=read(A/'report-data.json')
for x in report['runs']:
 s=x['summary'];c=x['config'];ev=capture(json.dumps({'config':c,'summary':s}).encode(),str(A.relative_to(R)/'report-data.json'))
 parse(dict(s,task=c['task'],model=c['model']),f"results/{c['task']}/campaign/summary.json",str((A/'report-data.json').relative_to(R)),ev)
 r=rows[c['run_id']];r['budget_total']=sum(c['allocations']);r['budget_per_agent']=c['budget'];r['sharing']=c['condition']
# Independent control has no final backend summary: use audited trajectory metrics, never fill unknown backend count.
for m in csvread(A/'metrics.csv'):
 if m['status']!='user_stopped':continue
 r=dict(run_id=m['run_id'],task='hc16v3_dev_000',model='kimi-k3.1-pro',agents=5,sharing='independent_without_past',budget_total=2000,budget_per_agent=400,status='user_stopped',state='stopped',queries=num(m['queries']),backend_calls=None,reward=num(m['reward']),model_usd=num(m['model_usd']),wall_s=num(m['wall_minutes'])*60,net_usd_per_year=num(m['net_usd_per_year']),evidence=os.path.relpath(A/'independent-evidence.json',O),cost_note='saved usage at forced stop; backend count unavailable')
 add(r,str((A/'metrics.csv').relative_to(R)),True)
# DeepSeek first failure, extracted from saved Azure transport; no remote access.
f=R/'runs/v3-screening-400-prep/original-failure-status.json'
if f.exists():
 msg=read(f)['value'][0]['message'];d=json.JSONDecoder().raw_decode(msg.split('STATUS_BEGIN\n')[1])[0]
 for x in d['outcomes']:
  s=dict(x['summary'],task='hc16v3_dev_000',model='deepseek-v4.1-flash');ev=capture(json.dumps(s).encode(),str(f.relative_to(R)));parse(s,'results/hc16v3_dev_000/campaign/summary.json',str(f.relative_to(R)),ev);rows[s['run_id']].update(budget_total=x['total_budget'],budget_per_agent=400,sharing=x['condition'])
# Retrieved and audited corpus campaign, separate from historical compact-v3 conditions.
corpus=O/'corpus-campaign.json'
if corpus.exists():
 for x in read(corpus):
  c=x['config'];s=x['summary'];ev='corpus-evidence/'+c['condition']+'/summary.json'
  parse(dict(s,task=c['task'],model=c['model']),f"results/{c['task']}/corpus/summary.json",x['evidence_root'],ev)
  rows[c['run_id']].update(budget_total=sum(c['allocations']),budget_per_agent=c['budget'],sharing=c['condition'],net_usd_per_year=x['annual_net'],context_protocol=c['context_protocol'])
# Preserve user-stopped delayed evidence even in a clean checkout without raw downloads.
partial=O/'corpus-partial.json'
if partial.exists():
 e=read(partial);c=e['config']
 add(dict(run_id=c['run_id'],task=c['task'],model=c['model'],agents=len(c['agents']),sharing=c['condition'],context_protocol=c['context_protocol'],budget_total=sum(c['allocations']),budget_per_agent=c['budget'],state='stopped',status=e['status'],queries=e['logged_queries_lower_bound'],queries_lower_bound=True,backend_calls=None,reward=None,model_usd=e['recorded_model_usd'],wall_s=None,net_usd_per_year=None,cost_note='saved usage only; queries lower bound after forced stop; no final reward asserted',evidence='corpus-partial.json'),'saved partial campaign evidence')
# Keep snapshot without known run identity out of run counts, but show progress and snapshot time.
p=R/'runs/v3-screening-400-prep/remote-status.json';progress=read(p) if p.exists() else None
if progress:save('current-campaign-snapshot.json',progress)
def group(r):
 t=r['task'];s=r['sharing'];rid=r['run_id']
 if r.get('context_protocol')=='compact-v3-corpus-v1':return 'v3-corpus'
 if t.startswith('hc12'):return 'hc12'
 if t.startswith('hc16v2'):return 'v2'
 if re.search(r'-[CF]\d-',rid):return 'v3-screen'
 if r.get('experiment_source')=='team-report-v1':return 'v3-team-snapshot'
 if 'deepseek' in r['model']:return 'v3-deepseek' if r['task'].endswith('002') else 'adapter-attempts'
 if s=='independent_without_past' or s in ['single_without_past','single_with_past','swarm_without_past','swarm_with_past']:return 'v3-400'
 if r.get('budget_total') in [100,500] and t.endswith('000'):return 'v3-100'
 return 'v3-first-look'
for r in rows.values():r['experiment']=group(r)
ordered=sorted(rows.values(),key=lambda r:(r['experiment'],r['task'],r['run_id']))
fields=['experiment','run_id','task','model','agents','sharing','state','status','budget_per_agent','budget_total','queries','queries_lower_bound','backend_calls','reward','net_usd_per_year','model_usd','wall_s','cost_note','evidence']
with (O/'runs.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(ordered)
save('runs.json',ordered);save('provenance.json',dict(compiled_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),refs=refs,sources=sources,aliases=aliases,policy='Snapshot of fetched refs and local saved evidence. No remote experiment polling. Raw source runs remain unchanged.'))
save('coverage.json',dict(exclusions=exclusions,conflicts=conflicts,unverified=['F3-100 follow-up: document-reported, no run summary found','Final dev002 runs predate migration and managed-budget fixes; two round-limit outcomes remain partial' + '; final raw sources reconciled by scripts/reconcile_final_teams.py','DeepSeek dev_000 second attempt: controller exists; final run summary not located'],reference_inventory='../experimental-history-20261115/simulator-reference-inventory.csv'))
checks=[]
def check(label,ok):checks.append(dict(check=label,passed=bool(ok)))
check('unique run IDs',len(ordered)==len(set(r['run_id'] for r in ordered)))
check('all evidence links resolve',all((O/r['evidence']).exists() for r in ordered))
check('known queries within known allocation',all(r.get('budget_total') is None or r.get('queries') is None or float(r['queries'])<=float(r['budget_total']) for r in ordered))
check('independent remains stopped',rows['swarm-3c4ef43770314f2d96d51757b37f47c7']['state']=='stopped')
check('source snapshot hashes',all(hashlib.sha256((O/s['path']).read_bytes()).hexdigest()==s['sha256'] for s in sources))
save('validation.json',checks)
print(json.dumps(dict(runs=len(ordered),states={s:sum(r['state']==s for r in ordered) for s in set(r['state'] for r in ordered)},conflicts=len(conflicts),checks=checks),indent=2))
