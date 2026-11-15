# Experimental history: from a working simulator to shared search

> Historical snapshot. Start with the [research report](../../RESEARCH_REPORT.md) and [report guide](../../docs/REPORT_GUIDE.md) for subsequent findings.

**Research snapshot: November 15, 2026, 11:20 AM Pacific.** This document covers completed plant-design experiments and starts a narrative for discussion. As requested, failed/interrupted attempts and setup tests are excluded from the main experiment inventory. Simulator qualification and deterministic search are background evidence, not additional model experiments.

Read the [current master report](../../RESEARCH_REPORT.md), [full completed-run table](inventory.md), or [machine-readable completed-run inventory](completed-runs.csv). The inventory contains **32 completed model search runs**, deduplicated by run ID: three HC12 runs, six HC16 V2 runs, and twenty-three HC16 V3 runs. This is the count under the completed-only scope, not every invocation made during development. Agent members of a swarm are not separate independent trials.

## How the experimental tracks fit together

The experiments progressed through: task development and baselines → investigation of V2 information delivery → two complementary V3 tracks → measurement of performance and exploration → the next agreed sharing-timing test.

- **Track A:** single agents and five-agent swarms, varying query allowance and additional Past memory on dev_000.
- **Track B:** four Kimi single-agent first looks and eight completed swarm-organization screening conditions, with screening on dev_002.

Read the [current master report](../../RESEARCH_REPORT.md) or [initial screening results](SCREENING.md). The combined CSV contains 32 completed runs. The original readable inventory covers the first 20; the screening inventory covers the additional 12. Different tasks, harnesses, budgets and diversity definitions remain explicit, so results are not pooled into a single ranking.

## What we have learned

The system can turn model proposals into complete separation-plant designs and evaluate their economics with ChemSep. Sharing visibly transfers designs and improvements. It also produces closely related endpoint plants. The evidence does **not** yet show a general swarm advantage or establish that external memory helps or harms search.

In the completed V3 400-per-agent comparison, exact-sharing five-agent search reaches the highest final modeled annual net value, **$2.179B/year**. It uses 1,978 charged queries, compared with 395 for the no-Past single agent at **$2.024B/year**. At the matched 395-query prefix, that single agent leads. Both observations belong in the story. These are modeled benchmark values, excluding feed cost; they are not realized operating profits or validated commercial plant forecasts. [V3 evidence and methods](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/README.md)

## How the problem evolved

| Stage | What changed | Why it matters for interpretation |
|---|---|---|
| Six-component reference | Replayed a pre-existing 12-column plant and checked economics and material closure. | A simulator reference, not an agent trial or the final task. |
| HC12 / V1 | Twelve hydrocarbons; 95% pure products sell; off-spec residuals can have zero value; optimize product revenue minus annualized separation cost. | No requirement to recover every component at a minimum percentage. The empty plant is a valid zero-value baseline. |
| HC16 V2 | Sixteen components, 99% premium grade at 1.2× price, qualifying blends, task-dependent pressure; energy ×2 and capital ×10. | Creates more selling and separation choices. Its objectives cannot be pooled with HC12. |
| HC16 V3 | Same V2 feeds/prices, side draws and double-effect columns, energy ×6 and capital ×10. | Introduces a meaningful heat-integration choice under higher assumed energy costs. Different physics/options/economics from V2. |
| Revised V3 agent harness | Local history/error feedback, guaranteed incumbent and compact exact evidence; optional Past retrieval on top. | Fixes confirmed V2 context defects. V3 “no Past” swarms still communicate. |

The cost multipliers and selling thresholds are benchmark assumptions. Independent energy closure and broader cost calibration remain unverified. A double-effect design position represents two physical columns and consumes two column solves when both are new; design positions, physical equipment, submissions, model requests, charged queries, and backend calls are different units. [HC12 brief](../../docs/TASK_BRIEF.md), [V2 task](../../docs/TASK_V2.md), [V3 task snapshot](evidence/task-v3.md)

The six-component reference reproduced net value of $1.372B/year, but one column missed its initial material-balance tolerance. The later HC12 fixed-first-cut qualification passed its provisional eligibility gate with 12 solves in 3.79 seconds and remained uneconomic. These checks established a usable evaluation path, not optimality. [Reference](../reference-20261114/README.md), [HC12 qualification](../hc12-qualification/README.md)

V2 qualification records 1,200 simulator solves, with 24 nonconvergences. The preserved V3 side-draw dataset records **133/160 solved (83.125%)**, 47 needing retry; use that exact saved result rather than the broader 83–89% wording in the task note. Qualification retries are not the later Kimi campaign retry policy. A double-effect grid on 56 existing Opus V2 columns motivated the energy ×6 scenario; it is simulator-led task development, not a model win. [Side-draw source](evidence/side-draw-qualification.json), [V3 gate description](evidence/task-v3.md)

## Completed experiments, in sequence

### 1. HC12 pilots and persistent runtime

| Completed run | Announced query ceiling | Charged queries | Best valid reward | Wall time | Model cost |
|---|---:|---:|---:|---:|---|
| Luna pilot | 50 | 50 | 0.7750 | 20.1 min | Unknown |
| Sol pilot | 50 | 50 | 3.3784 | 33.8 min | Unknown |
| Sol persistent run | 200 | 200 | 3.1705 | 19.7 min | Unknown |

These use recorded model strings `gpt-6-luna` and `gpt-6.1-sol`. The two pilots used the earlier Azure transport; the 200-query Sol run executed beside ChemSep. The Luna transport measurement found roughly 32.2 seconds of overhead per submission; moving the loop removed per-submission Azure transport. That explains an infrastructure improvement, not a controlled model-performance speedup. The 50-query Sol run's higher result than the separate 200-query run is a useful reminder that more allowance does not guarantee a better independent trajectory. These are different runs, not successive prefixes of one search. [Pilot/runtime evidence](../azure-runtime/README.md), [run IDs and ledgers](inventory.md)

The original HC12 Opus first-look results are outside this completed-only inventory because the provider account ran out of credit. Their archive remains available as background, without using them as completed experimental results. [Historical first-look record](../opus-5-5-dev-first-look/README.md)

### 2. HC16 V2 first looks and the Kimi comparison

Four completed Opus runs used `claude-opus-5-5`, one per development task, each told a 400-query ceiling. They finished themselves at 106, 113, 204 and 153 queries, with rewards 3.6292, 4.6312, 7.3802 and 5.1934. Recorded model estimates total **$14.406788**. Simulator-only local polishing improved the four outcomes by about 1.2–3.2%; this is extra search on saved plants and is not four more model runs. [V2 first look](../hc16v2-first-look/README.md)

| Completed Kimi V2 condition | Allowance | Queries / backend calls | Best reward | Modeled net/year | Model estimate | Wall time |
|---|---|---:|---:|---:|---:|---:|
| Single | 200 | 200 / not extracted here | 3.4219 | $2.841B | $1.26 | 9.3 min |
| Five-agent Past swarm | 100 each / 500 total | 454 / 409 | 3.3566 | $2.787B | $19.73 | 54.8 min |

The swarm finished 1.91% below the single with more total queries and much greater model spend. Three agents ended under historical dollar thresholds, leaving 46 queries unused. The later protocol document describes disabled thresholds; the actual saved ledgers take precedence for this historical run. [V2 audit](../../docs/SWARM_MEMORY_AUDIT.md)

The subsequent audit changed the hypothesis. The V2 swarm lacked guaranteed direct local history and rejection feedback. It published 156 experiments but retrieved only 16 distinct source versions; the winning round-24 design was never retrieved. Its mean input request was about nine times the single's, and memory processing occupied 73% of wall time. This is evidence of a deficient information path, not evidence that shared memory intrinsically reduces performance. V3 restored the local feedback and incumbent guarantees; these old defects should not be used to explain V3 outcomes. [Preserved audit](evidence/v2-forensic-audit.md)

### 3. HC16 V3 Opus and simulator reference work

| Task | Completed Opus reward | Queries / announced ceiling | Model estimate | Reward after local polish | V2 plant repriced at V3, then polished |
|---|---:|---:|---:|---:|---:|
| dev_000 | 2.7669 | 233 / 400 | $4.18 | 2.8320 | 2.7201 |
| dev_001 | 2.8531 | 153 / 400 | $4.45 | 3.03* | 3.53* |
| dev_002 | 5.1323 | 110 / 400 | $2.58 | 5.16* | 5.57* |
| dev_003 | 4.4425 | 284 / 400 | $4.14 | 4.53* | 4.20* |

*Rounded historical evaluation values. Exact source tables are retained in [local-polish evidence](evidence/v3-polish.json) and [repriced V2 plant evidence](evidence/v2-plants-at-v3-polish.json). The four completed model runs cost an estimated **$15.338304** and all finished early. Their summaries are linked individually in the [inventory](inventory.md).

Different starting layouts mattered: on two tasks, repriced and polished V2 plants exceeded polished V3 plants by more than further local tuning typically achieved. This supports investigating alternative search paths. It does not estimate run-to-run variance, because the starting tasks/economics and histories differed. The dev_000 Opus winner retained three double effects; other V3 runs used these levers little or not at all. [Historical evaluation](evidence/historical-evaluation.md)

Background deterministic work includes 28 HC12 robot records, 28 V2 robot records, nine saved rows from an incomplete V3 robot campaign, and 16 local-polish/repricing records. These **81 reference rows are not 81 model experiments**. Some raw robot files were absent even before the recent worktree removal; the aggregate CSV preserves that limitation. HC12 robots used an earlier validity gate; V3 robots do not explore the new side-draw/double-effect actions. Avoid the broad claim that agents generally beat competitive search. [Separate reference inventory](simulator-reference-inventory.csv)

### 4. V3 Kimi at 100 queries per agent

These are actual separately budgeted experiments, not the 100-query prefixes of later 400-query runs.

| Completed condition | Agents | Allowance each / total | Used / backend | Best reward | Model estimate |
|---|---:|---:|---:|---:|---:|
| Single, no Past | 1 | 100 / 100 | 100 / 100 | 0.4255 | $1.33 |
| Single, Past | 1 | 100 / 100 | 100 / 100 | 0.6060 | $1.82 |
| Exact-sharing swarm, no Past | 5 | 100 / 500 | 488 / 309 | 2.0698 | $5.78 |

Three completed cells: **688 charged queries**, **509 backend calls**, **$8.922294** estimated model spend. The fourth cell has no completed outcome and is excluded. The campaign was not a completed four-cell matrix. This snapshot supports a different single/Past ordering at the smaller horizon, but one run per cell and intervening recovery changes prevent a general budget-by-memory conclusion. [Preserved observed snapshot](evidence/v3-100-campaign-snapshot.json)

### 5. V3 Kimi at 400 queries per agent

| Completed condition | Agents | Queries / ceiling | Backend calls | Best net/year | Model estimate | Wall min |
|---|---:|---:|---:|---:|---:|---:|
| Single, no Past | 1 | 395 / 400 | 395 | $2.024B | $6.83 | 39.4 |
| Single, Past | 1 | 400 / 400 | 400 | $1.146B | $5.96 | 33.4 |
| Exact-sharing swarm, no Past | 5 | 1,978 / 2,000 | 1,212 | $2.179B | $19.81 | 48.0 |
| Exact-sharing swarm, Past | 5 | 1,963 / 2,000 | 1,148 | $2.039B | $15.59 | 39.2 |

Four completed runs total **4,736 charged queries**, **3,155 backend calls**, and **$48.190418** estimated model spend. Past memory and VM costs are not included. The widely quoted **$53.695638** figure includes additional recovery-attempt spending; it is not the cost of these four completed runs alone. Recovery handling also changed deployed memory adapter code, limiting causal interpretation of the four-condition comparison. Those attempts are outside this results inventory. [Metrics](evidence/v3-400-metrics.csv), [full analysis](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/index.html)

At **395 cumulative charged queries**, no-Past single reward is 2.4383 versus 2.1029 for the exact-sharing swarm: the swarm is 13.76% lower at that observed prefix. At their unequal endpoints it is 7.65% higher, using 5.01× the queries and 2.90× model spend. These prefixes inherit a 400-per-agent announced horizon and are not separately budget-conditioned experiments.

Past finishes lower in each matched agent-count pair: 43.40% lower for the single and 6.46% lower for the swarm. That is a descriptive result of these runs, not proof of a negative memory effect. V3 retrieval faced local prompt admission limits and ongoing ingestion: roughly 78% and 86% of candidate memory instances were omitted from single/swarm prompts, with 75 and 26 ingestion jobs pending at completion. These percentages count repeated candidate instances, not unique memories. [Behavior analysis](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/behavior-analysis.md)

## What the trajectories add

Explicit peer-design selection occurs in 67.9% of no-Past swarm submissions and 67.6% of Past submissions. Round-start incumbent selection occurs in 76.3% and 78.7%. Most copies are followed by edits. All five agents contribute team improvements; 58/87 and 56/79 positive team-improvement events have explicit peer ancestry. Copying can therefore be productive, although ancestry is not a counterfactual estimate of benefit.

Within each swarm, all five final retained plants share the same set of 17 column positions, with different settings. The two swarms themselves converge to different plant families. The no-Past winner has four double effects, 21 physical columns and about 92 MW of modeled heat transfer; the Past winner has 17 physical columns and no double effects. The net-value difference reflects costs as well as revenue, not merely product purity.

Best-so-far plots hide the unsuccessful search: 56.1% and 48.2% of all swarm submissions were valid but below the submitting agent's retained best. The harness retains the best but does not enforce strictly greedy candidate acceptance. Past was not uniformly more conservative: its multi-position and root-setting changes were more frequent on the recorded definitions. “Shared-incumbent local search” is a reasonable behavioral interpretation; “five identical agents doing nothing but copying” is not supported. [Counts, definitions and caveats](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/behavior-analysis.md)

Economic margins also matter. Repricing the saved fixed flows and costs with selling-grade thresholds raised by **0.05 percentage points** lowers no-Past swarm net by about **29.6%**, versus about **20%** for the Past swarm. The no-Past plant has several valuable blend streams very close to 95%. This is offline threshold sensitivity with fallback sales categories, **not** a new physical simulation, operational failure probability, or robustness certification. [Repricing table](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/grade_sensitivity.csv)

## Current work and the next agreed experiment

The five-agent independent Kimi control, `v3-kimi-independent-400-20261114-r1`, was still progressing in the last locally observed snapshot, **11:14:33 AM Pacific**: 1,555/2,000 charged queries; best reward 2.2344; no terminal summary. It uses own histories and no cross-agent evidence, while retaining a shared deterministic simulator cache with per-agent first-use charging. Its partial score is not a completed result. The later disappearance of its local worktree means this document does not certify its current live state. No additional VM poller was started. [Observed status](evidence/independent-snapshot.json)

The next agreed campaign replaces the earlier Kimi variants:

| Condition | Agents | Sharing begins | Maximum charged queries |
|---|---:|---|---:|
| Single baseline | 1 | Not applicable | 400 |
| Immediate sharing | 10 | From the start | 4,000 |
| Delayed sharing 25% | 10 | After 100 queries per agent | 4,000 |
| Delayed sharing 50% | 10 | After 200 queries per agent | 4,000 |

**12,400 maximum queries; one run per condition; no Past.** Model: Modal `deepseek-ai/DeepSeek-V4.1-Flash`, verified by the preparation chat's models API and tiny completion response. Shared records are to be consolidated deterministically into distinct evidence-backed findings while retaining raw observations, contradictions and exact designs. Existing local state/history, copying permission and sharing frequency remain; no additional branch restrictions or separate memory service.

Preparation passed the full 12,400-query **mock** validation (zero model or ChemSep calls). A separate authenticated smoke completion used 302 input / 60 output tokens and zero simulator queries. Neither is a completed plant-design experiment. **No campaign launch or durable queue registration was confirmed.** The preparation chat reported that the worktree disappeared while it was freezing the bundle and is recovering before registration. The intended guard remains successful completion of the existing independent control and idle experiment processes. This document does not operate that queue.

Changing model, team size and shared evidence together makes the new campaign an exploratory configuration comparison. The old five-agent Kimi independent control supplies historical context, not a matched ten-agent DeepSeek never-sharing arm. Earlier 12/10/8-run repeat proposals and the four-run Kimi version were superseded, not executed results.

## Provenance and boundaries

The main checkout guide and report index were read, along with archived summaries, manifests, the V2 audit, V3 metric/behavior exports, implementation-worktree source/config records and three relevant chats. Sources are linked per claim; [provenance.json](provenance.json) hashes copied evidence. Model costs use historical recorded estimates, not current list prices or invoices. Unknown Sol/Luna dollars remain unknown, despite some ledgers containing a zero known-cost subtotal. No all-project dollar total is claimed.

The implementation worktree disappeared around 11:17 AM during this research. Tracked V3 sources were recovered **read-only** from Git commit `7c0d5087b2d7d4ad6e30103274042a3d8dfea69e`. Selected previously observed ignored status/config fields were transcribed into explicitly labeled snapshots; they are not represented as byte-identical exports. [Recovery provenance](evidence/source-recovery.json) identifies this distinction. No experiments, source branch or controller were modified or restored.

Chat provenance: analysis/decisions `01a1e039-6aa9-73e3-a072-0b694cd769e0`; prior campaign `01a1dd3a-fb9b-7782-95b8-edd868d8fd73`; current preparation `01a1e090-6f99-7f63-bb94-a1b343a21247`. The last preparation-chat read confirmed endpoint validation and the workspace blocker, but no launch. No messages were sent to those chats.

Historical workplans and evaluation notes contain outdated status and stronger interpretations. They are evidence of project progression, not automatically the current conclusion. Reports, demo replays, recovered exports, per-agent swarm views and re-rendered comparisons do not add independent trials. The replay visualizations show saved improvements; they are not the full attempt record or a live plant.
