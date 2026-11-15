# Workplan: single agent vs shared-memory swarms

Updated November 14, 2026 (completed Kimi pair; locally generated report bundles). The original task is the [12-component economic brief](docs/TASK_BRIEF.md); the active comparison now uses **hc16v2_dev_000** from merged [PR #7](https://github.com). This is the working decision record and execution plan for `iterate-hackathon`.

## Current status and changes to the original plan

Reviewed the five other chats associated with this folder: **Refine hackathon engineering concept**, **Run GPT-6.1 Sol for 200 calls**, **Add an evolving 3D plant demo**, **Estimate Modal swarm experiment cost**, and **Set up past.dev**. Status below reconciles their latest outcomes with saved artifacts and the merged integration PR; historical chat statements are superseded by later evidence.

| Workstream | Verified progress | Remaining work |
| --- | --- | --- |
| Simulator and checker | Real ChemSep qualification, independent eligibility scoring, persistent Windows VM runtime, and live model runs exist. V2 adds 16 components, premium/blend grades and explicit cost multipliers. | Freeze numerical acceptance policy; disclose missing independent energy closure and cost calibration. V2 multipliers are scenario assumptions. |
| Single-agent pilots | Luna/Sol pilots and the Sol 200-call run are saved. Sol 200 completed 208 model requests in 1,185 seconds, best valid reward 3.17045; all 208 requests have unknown dollar pricing. | Finish comparable resource accounting; unknown dollars are not zero. |
| Shared memory and orchestration | Two-agent/two-round past.dev integration and isolation checks passed. Live three-agent Sol run completed five rounds: 15 submissions, 17 charged queries / 13 backend calls, 12 submissions citing evidence, two peer-design copies, zero rejected submissions or memory errors. All three usage ledgers reconcile. | Audit equivalent single-agent memory access for any controlled comparison; retain evidence of actual reuse. |
| Completed Kimi V2 pair | Single: 200 queries, reward 3.421925, 559 seconds, estimated model cost $1.259648. Five-agent swarm: 454/500 charged queries, 409 backend calls, best reward 3.356596 (agent-3), 3,285 seconds, estimated model cost $19.727076; all five usage ledgers reconcile. | Analyze memory reuse and a team-query checkpoint from full trajectory evidence. This unequal-budget, one-repetition pair does not establish a causal memory or architecture advantage. |
| Reports and demo | Automatic single-agent reports and flowsheet replay exist; merged V2 integration adds aggregate/per-agent swarm reports. Sol-based 3D V1 and realistic site-assembly V2 are built, with offline packaging and replay controls. | Completed Kimi report bundles include the single replay, swarm comparison and all five agent replays under `results/`. Finish the presentation narrative. 3D demo shows saved best improvements, not every attempt or live simulator updates. |
| Repository delivery | Swarm harness merged in PR #3; V2/Kimi integration merged in PR #7 (26b755d). | Cleanup branch codex/repository-cleanup now starts from merged main (26b755d), carries the newer viewer fixes, and packages the unique demo/infrastructure evidence. Review and merge the cleanup PR before submission; original worktrees and a recovery stash are retained. |
| Sponsors | Modal authentication and Kimi tool calling work; past.dev is exercised in live swarms. | Exa project-loop use and event/track eligibility remain unverified. The earlier standalone Modal trial was cancelled after three requests; the later V2 pair is a separate run. |

**Active experiment supersedes the original first-run schedule:** Kimi on HC16 V2, one agent with 200 calls followed by five agents with 100 calls each (500 total). This is an exploratory unequal-budget pair, not completion of the original equal-50-call 1/3/5-agent experiment. Compare best team design, never the sum of five independent plant objectives. If trajectories permit, include a 200-team-query swarm checkpoint and disclose the different announced budget horizons. HC12 and HC16 results must remain separate.

Evidence: [Sol 200 saved report data](runs/hc12_dev_000/single-agent/gpt-6.1-sol/sol-200-20261114/report-data.json), [three-agent live summary](runs/azure-control/swarm-three-five-status.json), [isolation probe](runs/azure-control/live-isolation.json), [Kimi pair cached status](runs/azure-control/v2-kimi-20261114-r3-controller.status.json), [demo documentation](demo/README.md), and [merged V2 comparison protocol](https://github.com). The [curated evidence bundle](results/progress-20261114/README.md) preserves these snapshots and rebuildable demo input in Git; original run links remain local and may be git-ignored. Cached status is a dated observation, not a completion claim.

## Research question

How well do **1, 3, and 5 agents** solve the same chemical-engineering design problem, and how does performance change with simulator budget, elapsed time, and search cost?

The project compares agent organization. It is **not autoresearch, model training, or a self-improvement project**. A swarm losing to a single agent is a valid result. The deliverable must show objective plots and checkable simulator evidence, not subjective ratings.

## Original agreed protocol (retained for the controlled comparison)

| Area | Agreed decision |
| --- | --- |
| Domain | Use this repo’s 12-component hydrocarbon problem. Validate the simulator backend and cost model before comparing agents. |
| Starting case | User approved the 12-component task family. Use the fixed hc12_dev_000 snapshot in tasks/hc12_dev_000.json. |
| Task | Design a complete column-tree flowsheet and revise its topology and column settings. Agents choose the topology and number of columns within the task bounds. |
| Scope | One identical engineering brief for all conditions, with independent repeat runs where affordable. Broader task generalization is not established by one case. |
| Primary conditions | 1, 3, and 5 agents. Each agent designs a complete flowsheet. Initial swarms use parallel exploration with shared memory, not subsystem division of labor or a coordinator. |
| Sharing | Use synchronized rounds: one complete-design submission per agent, publish measured results and interpretations to past.dev, then read peers’ findings before the next round. Separate simulator facts from hypotheses. |
| Design reuse | Agents may copy and modify peers’ complete designs. Log the source agent, design version, and resulting edits. |
| Single-agent memory | Give the single agent the same memory tool for its own history. Reset memory between independent runs; share only within the current team run. |
| Efficiency comparison | First comparison: **50 simulator calls total per team**, with equal shares: 1 agent gets 50; 3 agents get 17/17/16; 5 agents get 10 each. Rotate the 16-call allocation across independent 3-agent repetitions. |
| Call accounting | A call is a distinct column evaluation, including failed evaluations, not a whole-flowsheet submission. Disable automatic solver retries to match the Luna pilot; separately log submissions, cache hits, and actual backend invocations. |
| Scaling comparison | Later experiment: 50 calls per agent, giving 50/150/250 team totals. Keep this separate from the first equal-total-budget comparison and report additional resources. |
| Budget curves | Plot performance over cumulative budget, rather than only at one ceiling. Run the single agent to larger matching totals where feasible. |
| Optional control | Independent parallel agents without sharing. Useful, but not required for the first experiment. |
| Evaluation | Maximize annual product revenue minus annualized separation cost among physically valid complete designs. No mandatory per-component recovery. Purity determines product value, not global pass/fail. Agents cannot change the checker. |
| Evidence | Retain failed attempts, raw simulator outputs, final flowsheets, costs, timings, and run-to-run variation. Keep search expense separate from plant economics. |
| Workspace | All new project code, configuration, orchestration, plans, and results belong in this repo. |
| Later extensions | HC16 V2 has now been integrated and exercised; keep its task assumptions and results separate from HC12. |
| Documentation | Keep summaries short. In Notion, use toggles or subpages linked from the to-do table. |

**Interpretation clause:** without the no-sharing parallel control, we can conclude that the overall swarm performs better or worse, but cannot attribute the difference specifically to shared memory. A single-agent baseline does not isolate the effect of sharing.

## Agreed round protocol

1. Each agent proposes or revises a complete flowsheet through the same design interface.
2. Submit for simulator evaluation; retain the design version, edits, results, and failures.
3. Write findings to past.dev, distinguishing measured evidence from interpretation.
4. At the round boundary, read other agents’ findings and choose the next attempt.
5. Continue within the team budget. The evaluator selects the best qualifying submission.

Each active agent gets one complete-design submission per synchronized round. Enforce the allocations above; no agent may silently consume a peer’s share. The orchestrator enforces the round barrier and budget without an extra coordinator LLM. The implemented harness has run-scoped memory, ingestion timeouts and no borrowing of unused allocations; a peer-cache hit is charged on each agent’s first distinct query. Confirm the saved configuration and exhausted-agent behavior when freezing a controlled experiment.

### Memory integration test and controlled baseline

Completed: a small **two-agent, two-round integration test** in a unique memory space, plus isolation checks. The retained acceptance criteria are: Agent A publishes a simulator finding; agent B retrieves it and explicitly uses it in its next proposal. Log writes, reads, cited evidence, and design provenance. Check that a separate run cannot retrieve the finding. This is a plumbing test, not evidence of a performance benefit.

The current GPT-6 Luna pilot uses its own conversation history rather than past.dev. Treat it as preliminary evidence. Run fresh **1-, 3-, and 5-agent conditions through the same memory-enabled harness**, with the single agent using the same tools for its own history. Reset memory between independent runs.

## Measurements

| Dimension | What to record |
| --- | --- |
| Completion | Whether the complete design meets every frozen requirement; report specific failed requirements. |
| Physical validity | Solver convergence, component/material closure, finite/nonnegative streams, equipment bounds, and energy residuals where exposed. State unverified checks. |
| Product performance | Per-product purity, component recovery into qualifying product streams, and flow. Do not substitute revenue recovery for physical recovery. |
| Plant economics | Annual product revenue, total annualized cost, and their difference under fixed benchmark assumptions. Rank economics among qualifying designs. |
| Search resources | Submission attempts, distinct column queries, actual simulator calls, cache hits, retries, LLM tokens/spend, attributable simulator compute cost, and wall time. |
| Reliability | Success frequency, failures, and variation across independent runs. Separate infrastructure outages from invalid designs. |

Required plots:

- Best qualifying design economics versus cumulative simulator calls, wall time, and search cost.
- Calls/attempts/time/cost to first qualifying design; retain unsuccessful runs explicitly.
- Final validity and per-product purity/recovery/flow against targets.
- 1/3/5-agent curves with equal-total and equal-per-agent checkpoints identified.

A submission can require several column solves. Attempts, unique queries, and actual calls are distinct counts. Subscription availability is not evidence that model usage has zero cost; record usage and the valuation method.

## Required per-run token and dollar accounting

- Record request-level usage with run ID, agent ID, request ID, provider/model, timestamp, input/output tokens, cached-input tokens, and reasoning tokens where exposed. Preserve provider definitions: cached/reasoning counts may be subsets, not extra tokens to add again.
- Record billed USD when available. Otherwise label estimated USD and preserve pricing source/date, rates, and calculation method. Missing usage/cost is unknown, never zero; distinguish actual charges, credit-covered usage, and subscription-based estimates.
- Aggregate every agent's calls, retries and failed attempts into team-run totals; retain per-agent breakdowns and cumulative checkpoints.
- Break out LLM, memory/search tools, and simulator/compute dollars. Sum attributable search expense separately from the plant's annualized economic objective; state any allocation method for shared infrastructure.
- Persist request-level usage events plus a per-run summary, even for failed/aborted runs. Reconcile event totals against the summary before comparing conditions. Plot performance versus cumulative tokens and USD alongside simulator calls and elapsed time.
- [x] Implement request-level token/model-cost logging in single-agent and swarm runners; live three-agent ledgers reconcile and Kimi single-agent usage is saved.
- [x] Verify final five-agent model-usage reconciliation and publish the completed single/swarm HTML comparison.
- [ ] Complete full search-dollar accounting. Sol pricing, memory and attributable simulator/VM costs remain unknown where not measured; model estimates alone are not the full ledger.

## Fairness and experiment freeze

- Hold model/version, engineering information, starting design, tool access, physics, economics, simulator version, retry policy, and checks constant.
- Separate setup and architecture tuning from reported experiments. Freeze prompts, protocol, and budgets before comparison runs.
- Specify shared-cache accounting and reset rules. Prevent cross-run memory leakage.
- Keep simulator worker capacity comparable when interpreting wall-clock gains; report queue time and concurrency limits.
- Set model-spend safety caps and report actual total spend. Equal simulator calls do not imply equal LLM cost.
- If checkpoints are read from longer runs, disclose the budget horizon agents were told. Use separately budget-conditioned runs if needed.
- Do not claim a baseline is a global optimum or that a single case establishes broad swarm superiority.

## Original HC12 implementation and qualification

The original implementation contains `sepdesign/`, a design environment, baselines, an example agent, and a replay demo. The following describes the original **12-component family**; the active HC16 V2 extension is recorded above.

See [TASK_BRIEF.md](docs/TASK_BRIEF.md) for the fixed feed and prices, design bounds, empty start, 95% saleability rule, and zero-value residual convention. These concrete defaults are documented separately from the user's high-level decisions. No per-product recovery minima are imposed. The empty design earns $0/year, so measure time to a positive valid economic improvement rather than time to any valid design.

A bounded live 12-component first-cut run completed with 12 successful solves in 3.79 seconds and passed the provisional independent gate. The plant was uneconomic, so the empty baseline remained best. See [qualification results](results/hc12-qualification/README.md). Independent energy closure and cost-model calibration accuracy remain unverified; tolerances are not yet frozen.

## Additional results already in main

- [Opus V2 first look](results/hc16v2-first-look/README.md): four dev tasks, one seed each, real ChemSep, 400-call announced ceilings with early agent finishes; local-polish checks included. Useful context, not matched Kimi/swarm conditions.
- [Opus HC12 first look](results/opus-5-5-dev-first-look/README.md) and [robot baselines](results/robot-baselines-dev/summary.md) are already packaged. Do not mix HC12 and HC16 curves.
- [V2 task notes](docs/TASK_V2.md) report 1,200 qualification solves. Their statement that agent runs have not been run is historical and superseded by the Opus first-look bundle and current Kimi pair.

## Work checklist

### Completed implementation and demonstrated plumbing

- [x] Define and snapshot the original HC12 economic brief.
- [x] Exercise real ChemSep and implement independent best-valid scoring; failed/skipped columns and missing costs cannot become best.
- [x] Build and execute single-agent pilots with saved submissions, usage, timing, failures and replay artifacts.
- [x] Deploy the persistent VM model loop beside ChemSep.
- [x] Complete the two-agent/two-round past.dev integration and separate-run isolation probe.
- [x] Implement configurable 1/3/5-agent synchronized shared-memory orchestration.
- [x] Validate the combined live-model + past.dev + ChemSep path with the completed three-agent/five-round Sol run.
- [x] Demonstrate cross-agent writes, reads, citations and peer-design copying.
- [x] Integrate HC16 V2, Modal Kimi, configurable budgets and automatic per-agent/team reports (PR #7 merged).
- [x] Complete the Kimi V2 200-call single-agent condition.
- [x] Build offline 3D replay V1 and site-assembly V2 from the completed Sol run.

### Submission-critical delivery steps, in order

- [ ] Let the already-launched five-agent Kimi run reach a terminal state; inspect stop/failure reasons and reconcile all five ledgers.
- [ ] Export the Kimi single-agent report, swarm overview and all five agent replays; save a linked comparison with best valid net objective, ceiling fraction, calls, wall time, tokens, estimated model dollars and memory-use evidence.
- [ ] Include a 200 cumulative team-query checkpoint if supported; explicitly retain the 200-vs-500 budget caveat and distinguish backend calls from charged queries.
- [x] Reconcile this checkout with merged main, carry viewer fixes forward, and package demo sources, reproducible commands and selected evidence.
- [ ] Review and merge the repository-cleanup PR; keep final-run provenance distinct from packaging provenance.
- [ ] Freeze checker tolerances and document energy/cost-model limitations before treating results as a controlled benchmark.
- [ ] Confirm equivalent memory tools for the single-agent baseline, frozen prompts/model/version, repeat count and resource accounting before a controlled campaign.
- [ ] Finish cross-condition plots, final flowsheets and concise limitations; existing report/replay infrastructure is complete, final comparison delivery is not.
- [ ] Prepare the reproducible demo/submission and confirm track eligibility and organizer deadlines. Working deadline remains Sunday November 15, 2:00 PM PT pending confirmation of conflicting event notes.

### Optional follow-up experiments (not required to package the current demo)


- [ ] Original fresh 1/3/5-agent equal-50-call conditions with equivalent memory access and frozen settings. The Kimi pair does not satisfy this comparison.
- [ ] Separate 50-calls-per-agent scaling experiment, independent repeats and a no-sharing control. These require a new execution decision; repository cleanup launches no runs.

## Open decisions — not yet locked

1. Justified material/energy tolerances and complete eligibility checks after backend validation.
2. Decide whether a controlled equal-budget campaign remains in scope after the Kimi V2 pair. Its model/task/budget choices are now explicit; repeat count and a comparable single-agent memory condition remain unresolved.
3. Freeze the implemented orchestration policy for reported comparisons: synchronized barriers, run-scoped memory, no borrowing unused allocations, and charging each agent for first use of a distinct query even on shared-cache hits. Verify final run configuration and failure accounting in the evidence bundle.
4. Confirm Track 3 eligibility for engineering, or choose an eligible alternative; the supplied detailed track brief focuses on computational biology.
5. Whether to run the optional no-sharing parallel control and any additional task cases after the first experiment works.

## Available resources and sponsor work

Confirmed by the team: **$250 Modal credits, Devin Max, Exa, and past.dev**. Modal Kimi and past.dev authentication have been exercised. Full provider billing, credit coverage and attributable memory/VM costs remain to reconcile.

- **past.dev:** intended shared-memory layer. Demonstrate multiple writers/readers and one agent using another’s findings. Do not claim a memory benefit without supporting evidence.
- **Exa:** use for relevant engineering/documentation evidence in the main project loop if entering its challenge; expose the same capability across conditions and log use.
- **Modal:** Kimi inference is working through its endpoint; ChemSep remains on the Azure Windows VM. Reconcile grant coverage and actual charges separately.
- Event details and sponsor requirements were collected separately in the local `RESOURCES.md`; confirm eligibility/deadlines with organizers rather than treating working notes as authoritative.

## Project documents

- [Task brief](docs/TASK_BRIEF.md)
- [Fixed task inputs](tasks/hc12_dev_000.json)
- [Simulator documentation](docs/SIMULATOR.md)

This plan records decisions from the team discussion. Items explicitly marked open or optional must not be treated as settled requirements.
