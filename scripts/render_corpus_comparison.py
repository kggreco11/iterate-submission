from pathlib import Path
import json,html,statistics,hashlib,datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];O=R/'results/results-so-far';ds=json.loads((O/'corpus-campaign.json').read_text());sw=next(x for x in ds if x['config']['condition']=='sharing_immediate');solo=next(x for x in ds if x['config']['condition']=='single_baseline');root=R/sw['evidence_root'];diagnostics=[];ages=[];candidate=admitted=0
admissions=json.loads((O/'corpus-evidence/sharing_immediate/prompt-admission.json').read_text())
for d in admissions:
 diagnostics.append(d);candidate+=d['candidate_instances'];admitted+=d['admitted_instances'];ages+=d['nonincumbent_ages']
s=sw['summary'];a=sw['audit'];m=sw['winner']['measured'];metrics={'prompt_count':len(diagnostics),'candidate_instances':candidate,'admitted_candidate_instances':admitted,'nonincumbent_source_age_median_rounds':statistics.median(ages),'median_prompt_bytes':statistics.median(x['input_bytes'] for x in diagnostics),'prompts_at_least_95pct_capacity':sum(x['input_bytes']>=.95*x['max_input_bytes'] for x in diagnostics),'corpus_keys':sw['corpus_inventory']['keys'],'corpus_observations':sw['corpus_inventory']['observations'],'best_plant_topologies':len({tuple(sorted(x['best_design'])) for x in s['agents'].values()})};(O/'corpus-memory-metrics.json').write_text(json.dumps(metrics,indent=2));print(metrics)
fig,axs=plt.subplots(1,2,figsize=(12,4.5))
for d in [solo,sw]:
 c=d['audit']['best_curve'];xs=[0]+[p['charged_queries'] for p in c]+[d['summary']['team_distinct_queries']];ys=[0]+[max(0,p['best_valid_reward']) for p in c]+[max(x['best_valid_reward'] for x in d['summary']['agents'].values())];axs[0].step(xs,ys,where='post',label=d['config']['condition'])
axs[0].set(xlabel='Team-total charged queries',ylabel='Best valid reward',title='Immediate sharing remains in a low-value region');axs[0].legend(fontsize=8)
d=a['diversity_by_round'];axs[1].plot([x['round'] for x in d],[x['distinct_column_path_sets'] for x in d],label='Current topologies');axs[1].plot([x['round'] for x in d],[x['distinct_exact_designs'] for x in d],label='Current exact designs');axs[1].set(xlabel='Round',ylabel='Distinct current plants',title='Settings differ even as structure converges');axs[1].legend(fontsize=8)
fig.tight_layout();fig.savefig(O/'corpus-comparison.png',dpi=170);fig.savefig(O/'corpus-comparison.svg')
matched=max(p['best_valid_reward'] for p in a['best_curve'] if p['charged_queries']<=395)
text=f'''# Immediate sharing: completed comparison

## Main finding

The new five-agent immediate-sharing swarm finished normally at 1,990/2,000 charged queries, reward 0.52089 and $24.24 recorded model spend. The solo baseline reached 2.32380 at 395 queries and $4.73. The swarm's endpoint is 77.58% lower despite about five times the queries and 5.13 times the model spend. At the matched 395-query cutoff, the swarm reached {matched:.6f}, 83.05% below the completed solo endpoint.

This is a bad observed outcome for immediate sharing under this configuration, not proof that sharing generally hurts. The earlier shared swarm scored 2.6249 with another context protocol. One search path per condition cannot separate stochastic basin choice from policy effects.

## Why the reward is low

The winning swarm plant has only four column positions, annual revenue $735.4M, annual cost $302.9M, and net value $432.5M. The solo winner has 13 positions, revenue $3.290B, cost $1.360B, and net $1.929B. The swarm saves roughly $1.057B in cost but gives up $2.554B in revenue. The low score is an economic outcome of a small plant, not a reward-normalization discrepancy: saved streams, revenue, costs, objective and material closure reconcile.

The swarm reached its first positive plant at 67 team queries; solo did so at 45. All five swarm agents contributed best-valid improvements (26, 11, 10, 15 and 10 respectively). Improvement counts include early negative best-valid records. Collaboration did generate improvements, but largely within a low-value plant family.

## Copying and exploration

611 of 763 submissions explicitly selected a source design: 80.08%. Of these, 484 submissions selected a peer source (63.43% of all submissions), and 127 selected an own-agent source. Source IDs were attributed against the submitting agent. 189 submissions (24.77%) were exact duplicates. There were 559 valid, 185 invalid, and 19 rejected submissions. Invalid attempts were 24.25%, compared with 7.89% in solo.

Across all proposals, 33 column-path sets were explored. All five final best plants share one topology. Final current plants have two topologies and five exact settings, so current-state diversity and best-plant diversity must not be conflated. Structural changes occurred in 205 transitions; 558 retained the topology. Exact duplicates overlap those categories. This is not a complete absence of exploration, but the retained solutions are highly concentrated.

1,308 backend calls underlie 1,990 charged queries. The query-work audit also records 1,444 requests for evidence previously measured by peers and 474 own previously measured requests. Those service-request categories are not additional charged-query budgets. Cached reuse can reduce physical work while agents still spend their decision budgets following the same designs.

## Did the corpus actually become visible?

The saved corpus contains {metrics['corpus_keys']} deduplicated keys and {metrics['corpus_observations']} observations. These are implementation-level groupings, not verified independent scientific lessons. The corpus is serialized into the shared findings section; the empty external memory-request log does not mean the corpus was invisible.

Across {metrics['prompt_count']} saved prompts, {admitted:,} of {candidate:,} candidate-source instances were admitted ({admitted/candidate:.1%}). This counts repeated opportunities, not unique memories. Median prompt size was {metrics['median_prompt_bytes']:,.0f} bytes; {metrics['prompts_at_least_95pct_capacity']} prompts were at least 95% of the 32,000-byte allowance. Median age of admitted non-incumbent sources was {metrics['nonincumbent_source_age_median_rounds']:.0f} rounds. The latest incumbent is a separate mandatory source. A growing corpus therefore did not guarantee fresh or diverse evidence in each prompt.

The frozen candidate selector confirms a concrete mechanism: it rotates through insertion-ordered finding groups and observations, takes each observation’s first support ID, and stops at 20 candidates. It does not rank by recency, value improvement or relevance. The prompt builder then admits candidates in that order until the byte cap prevents inclusion. Thus old examples are an expected consequence of the implemented selection rule, rather than evidence that the corpus was absent. This is an implementation limitation; the effect on the final score remains unproven.

These measurements support checking admission and ranking alongside corpus size. They do not prove that stale evidence caused the low score. A causal account would require a controlled counterfactual; none was run here.

## Configuration and grade checks

Both new conditions use the same frozen campaign source, Kimi model alias, V3 dev_000 task, disabled solver retries, serialized simulator, 400 queries per agent, and compact-v3-corpus-v1 context protocol. Agent count, sharing, memory provider and total budget differ as designed. Immutable served model weights are not identified by the alias. The old compact-v3 results are historical references.

The swarm winner has no fixed-flow revenue loss for threshold shifts from 0 through 0.5 percentage points, unlike the much more profitable solo winner. This reflects qualification headroom in this small plant; it does not rescue its poor nominal economics or establish physical robustness.

## Campaign status and evidence

The team stopped the delayed-sharing conditions because of the time limit. The campaign crossed into delay25 before the stop reached it; that attempt is user-stopped and its full archive is preserved separately. Its 15 saved submissions record at least 20 charged queries; no sharing activation was observed. No final service summary exists, so backend calls and in-flight work are not reconstructed. Delay50 is cancelled and confirmed unstarted. Neither is a completed delayed-sharing comparison. No additional run or retry is authorized.

The full raw archive remains in the retrieved evidence folder. Eight accounting and physical-consistency checks pass for each completed condition. Compact source/config/summary/audit snapshots and winning measured outputs are in corpus-evidence. Prompt admission metrics are in corpus-memory-metrics.json. The completed swarm archive SHA256 is 35353c3b26c7425991851f7cb76d1cb4d24f3ce6c067b7fb9e944756a109e4d3.
'''
(O/'corpus-comparison.md').write_text(text);parts=[]
for p in text.split('\n\n'):
 tag='h1' if p.startswith('# ') else 'h2' if p.startswith('## ') else 'p';parts.append('<'+tag+'>'+html.escape(p.lstrip('# '))+'</'+tag+'>')
(O/'corpus-comparison.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Kimi corpus comparison</title><style>body{max-width:1000px;margin:40px auto;padding:0 24px;font:18px/1.65 system-ui;color:#172833}img{width:100%}h2{margin-top:40px}a{color:#076681}</style><a href="index.html">Results so far</a>'+''.join(parts[:4])+'<img src="corpus-comparison.png" alt="Matched budget performance and current-design diversity">'+''.join(parts[4:])+'</html>')
