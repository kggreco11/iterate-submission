# Initial swarm screening

## What was missing

The initial screening study contains **12 additional completed experiments**: four Kimi V3 single-agent first looks and eight multi-agent screening conditions. They were missing from the original 20-run inventory. The combined CSV now contains **32 verified completed runs**. Interrupted runs remain excluded.

## The swarm screening

Task: **HC16 V3 dev_002**. Model alias: **Kimi K3.1 Pro**. Each condition has 500 total allocated queries and ten model agents/roles. Most use ten solvers with 50 each; the critic condition allocates 500 across seven solvers, and the supervisor condition across nine workers.

| Configuration | Best reward | Queries used | Distinct final structures* |
|---|---:|---:|---:|
| [C1: independent](evidence/swarm-screening/results/swarm-screen-dev002/C1/summary.json) | 2.428 | 484 | 4 |
| [F1: broadcast](evidence/swarm-screening/results/swarm-screen-dev002/F1/summary.json) | 2.552 | 500 | 1 |
| [F2: lessons](evidence/swarm-screening/results/swarm-screen-dev002/F2/summary.json) | 0.715 | 499 | 3 |
| [F3: islands](evidence/swarm-screening/results/swarm-screen-dev002/F3/summary.json) | 2.436 | 499 | 5 |
| [F4: strategies](evidence/swarm-screening/results/swarm-screen-dev002/F4/summary.json) | 0.921 | 499 | 1 |
| [F5: teams](evidence/swarm-screening/results/swarm-screen-dev002/F5/summary.json) | 1.463 | 500 | 1 |
| [F6: roles](evidence/swarm-screening/results/swarm-screen-dev002/F6/summary.json) | 0.717 | 500 | 3 |
| [F7: supervisor](evidence/swarm-screening/results/swarm-screen-dev002/F7/summary.json) | 1.312 | 500 | 1 |

*Distinct process structures among recorded agent-best plants, using a separation-based fingerprint. This is not an exact-settings count or the column-path metric used in our five-agent analysis.

## The useful finding

**Broadcast sharing produced the best completed screening result, but converged on one process structure.** Independent search retained four final structures; delayed sharing retained five, with a slightly lower best score than broadcast. In this screening, all ten broadcast agents achieved a positive result versus four of ten independent agents.

This adds direct evidence for the exploration-versus-sharing question. It does not establish a general ranking: one seed per condition, no completed matched solo control in this screening, and different structures do not necessarily mean better engineering.

## Other completed work

Four Kimi single-agent V3 runs had 200-query ceilings, using 195, 195, 200 and 190 queries on dev_000 through dev_003. Rewards were **0.522, 0.270, 2.132 and 0.910**. These are distinct from our later V3 control runs. [Run IDs and source summaries](screening-completed-runs.csv)

The earlier studies include the V2/V3 task development, Opus first looks, simulator qualification, and local-polish studies already covered in the history. They are not counted again here.

## Follow-up work: keep status separate

The round-two note reports a completed **F3-100** follow-up at about 876 queries and reward 2.55, but I did not find a corresponding saved run summary/config in this branch. It is document-reported, not added to the 32 artifact-verified runs.

Six new configurations—ring islands, copying other design families, a board retaining different solution types, protected strategies, culling, and a managed portfolio—have implementation and a plan. Their completed results were not found in the inspected branch. The proposed 1,000-query solo control and larger scaling runs are not counted as results. [Round-two study plan](evidence/swarm-screening/docs/SWARM_NEXT_ROUND.md)

## How this fits our story

These experiments make the narrative stronger: **sharing can spread success while reducing diversity; delaying sharing can preserve alternatives, but did not win this screening.**

Keep this study separate from our dev_000 five-agent campaign: different task, budgets, prompts/harness, roles and simulator retry settings. The saved configurations enable ChemSep alternative initializations; our 400-query campaign recorded retries disabled. Do not compare raw rewards across the two task instances.

## Evidence

Read-only inspection of local Git remote-tracking branch `origin/feature/swarm-runner`, commit `aebae133dba191d7ba66a64db78d48633ab4776b`. This is the available repository snapshot, not a claim that the remote was freshly synchronized. Selected source files are copied with hashes in the [manifest](evidence/swarm-screening/manifest.json). No experiment was run or modified.
