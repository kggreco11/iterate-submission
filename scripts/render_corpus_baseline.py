from pathlib import Path
import json,html,csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path('results/results-so-far');d=next(x for x in json.loads((O/'corpus-campaign.json').read_text()) if x['config']['condition']=='single_baseline');a=d['audit'];s=d['summary'];old=list(csv.DictReader(open('results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/curves.csv')))
fig,ax=plt.subplots(figsize=(10,5))
p=[x for x in old if x['condition']=='single_without_past'];ax.step([float(x['queries']) for x in p],[float(x['reward']) for x in p],where='post',label='Historical solo / compact-v3')
p=a['best_curve'];ax.step([0]+[x['charged_queries'] for x in p]+[395],[0]+[max(0,x['best_valid_reward']) for x in p]+[2.3238008676187856],where='post',label='New solo / corpus-v1');ax.set(xlabel='Charged queries',ylabel='Best valid reward (zero incumbent retained)',title='Same consumed budget; different context protocols');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(O/'corpus-baseline.png',dpi=160)
text='''# Completed corpus baseline

Run swarm-292bd96a0f944b1083b637e2b08633fe finished normally by choosing finish at 395/400 charged queries. This is the first completed condition of the new Kimi campaign; the three sharing conditions are still awaiting completed evidence.

## Performance and economics

Best reward: 2.3238. Modeled annual revenue: $3.290B; annual cost: $1.360B; net value: $1.929B. Runtime: 38.94 minutes. Recorded model cost: $4.7250 across 267 requests, 1,313,117 input tokens and 209,877 output tokens. No failed or unpriced requests were recorded. Charged queries and backend calls both equal 395; 2,736 cached service requests are separate from that count.

Against the historical solo endpoint at the same 395 queries, reward is 4.70% lower and recorded model cost 30.82% lower. Historical solo used $6.8301 and reached 2.4383. Input tokens fell 33.31%; output tokens fell 27.42%. These differences cannot be attributed solely to memory: this is one new search trajectory under compact-v3-corpus-v1, versus the historical compact-v3 protocol.

First positive plant appeared at 45 charged queries, 93.6 seconds and $0.1827 of recorded model usage. It explored 24 distinct column-path sets across all submissions. The winning plant has 13 design positions, including a double-effect specification at BT. Column positions are not physical column-unit counts.

## Behavior

There were 266 submissions: 243 valid, 21 invalid and two rejected. Exact duplicate designs accounted for 98 submissions (36.84%). The audit classifies 79 transitions as structural and 187 as local or unchanged topology; exact duplicates are a subset, not a third disjoint class. No source-design copies were recorded and sharing was disabled. Repeated own designs can be cache hits and need not consume new simulator calls, but still consume model decisions and context.

The audit records 28 best-valid improvements, including early improvements that remain negative. Do not equate that count with 28 improvements above the zero incumbent. Cross-agent diversity, contribution balance, sharing activation and peer-corpus influence are not applicable to this solo condition. Those measurements become informative when the sharing conditions complete.

## Grade sensitivity

At fixed output flows and costs, raising all qualification thresholds by 0.05 percentage points reduces annual net by 1.85%, from $1.929B to $1.894B. This is accounting sensitivity with fallback sale categories, not a probability of physical failure. The old solo loses zero at that increment, while the old shared swarm loses 29.62%.

## Evidence

Eight independent checks pass: submission/validity accounting, best reward, summed charged queries, summed recorded model cost, objective normalization, component closure, and repricing the saved streams back to original revenue. The task used for repricing is the frozen campaign task. Full trajectories remain in the retrieved run folder; compact summaries, audit and source manifest are preserved under corpus-evidence/single_baseline. The full analysis JSON includes the winning measured plant, sensitivity points and trajectory SHA256.

Archive SHA256 provided by the retrieval owner: 656b01a8c857854e63faa851e2360c81658b9fe96beff5beee004c45e34b5fb8. Frozen source bundle SHA256: 7f366b1dbc3a2cb7dc5b26d5222f861572695feb0b3c27a4732e109df346a444. This note is a completed-baseline analysis, not a conclusion about the unfinished campaign.
'''
(O/'corpus-baseline.md').write_text(text)
parts=[]
for p in text.split('\n\n'):
 tag='h1' if p.startswith('# ') else 'h2' if p.startswith('## ') else 'p';parts.append('<'+tag+'>'+html.escape(p.lstrip('# '))+'</'+tag+'>')
(O/'corpus-baseline.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Corpus baseline</title><style>body{max-width:950px;margin:40px auto;padding:0 24px;font:18px/1.65 system-ui;color:#172833}img{width:100%}h2{margin-top:40px}a{color:#076681}</style><a href="index.html">Results so far</a>'+''.join(parts[:4])+'<img alt="New and historical solo reward versus queries" src="corpus-baseline.png">'+''.join(parts[4:])+'<p><a href="corpus-evidence/single_baseline/analysis.json">Evidence and checks</a></p></html>')
