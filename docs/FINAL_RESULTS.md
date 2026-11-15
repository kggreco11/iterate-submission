# Final results: agent teams on V3 dev002

[Read the master research report](../RESEARCH_REPORT.md) for the complete experiment sequence and plots.

## Main observations

- The 50-agent island configurations achieved the best team endpoints for both tested team models: Kimi 3.866 and DeepSeek 2.160.
- All four Kimi ten-agent conditions exceeded the Kimi solo endpoint of 1.754. They had 500 allocated solves versus 200 for solo.
- Kimi open sharing reached 2.954 and retained one best separation structure. The 50-agent run reached 3.866 with 16 retained best structures and a 13-column-position winner.
- Opus solo reached 5.331 in 74 solves. The best Kimi team reached about 73% of that reward using about 34 times as many solves. This does not establish a query-efficiency advantage for swarms.

## Task and setup

Agents design a plant separating 16 hydrocarbons, using ChemSep evaluations. They choose column connectivity and operating settings, including side draws and double-effect options. Reward is simulated annualized product revenue minus annual plant cost, normalized by a task-specific reference stream value. It is not realized profit.

All rows in the following table use hc16v3_dev_002. Agents receive full own/peer plant views, per-agent notebooks and copy/graft/edit tools according to their configuration. Teams use 50 distinct column solves per agent; solo runs allocate 200. The managed run actually starts nine workers and allocates 450 solves. DeepSeek uses a 1,500-token think-then-act cap; Kimi and Opus are uncapped in these runs. Solver failures can retry alternative initializations, unlike the dev000 memory-control harness.

## Final observed results

There are 19 uniquely identified dev002 runs: 17 all_done and two round_limit outcomes. all_done means the runner finished under its stopping rules, not that every allocated solve was consumed. The two round-limit outcomes are partial and remain labeled. Model costs are cached-price estimates, not invoices.

| Model | Configuration | Agents | Reward | Solves / allocation | Status | Model cost estimate | Evidence |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- |
| claude-opus-5-5 | solo | 1 | 5.3313 | 74 / 200 | all_done | $2.12 | [Run](../results/hc16v3_dev_002/team-solo/claude-opus-5-5/hc16v3_dev_002-solo-c5cb4e8e/index.html) |
| kimi-k3.1-pro | ring-5x2-k10 | 50 | 3.8660 | 2496 / 2500 | all_done | $23.28 | [Run](../results/hc16v3_dev_002/team-ring-5x2-k10/kimi-k3.1-pro/hc16v3_dev_002-ring-5x2-k10-761c0ffe/index.html) |
| kimi-k3.1-pro | open | 10 | 2.9537 | 499 / 500 | all_done | $6.35 | [Run](../results/hc16v3_dev_002/team-open/kimi-k3.1-pro/hc16v3_dev_002-open-41ad914b/index.html) |
| kimi-k3.1-pro | cull | 10 | 2.4483 | 497 / 500 | all_done | $3.06 | [Run](../results/hc16v3_dev_002/team-cull/kimi-k3.1-pro/hc16v3_dev_002-cull-db97bd5c/index.html) |
| kimi-k3.1-pro | independent | 10 | 2.2686 | 492 / 500 | all_done | $3.55 | [Run](../results/hc16v3_dev_002/team-independent/kimi-k3.1-pro/hc16v3_dev_002-independent-683a1314/index.html) |
| kimi-k3.1-pro | ring-5x2-k10 | 10 | 2.2295 | 498 / 500 | all_done | $4.19 | [Run](../results/hc16v3_dev_002/team-ring-5x2-k10/kimi-k3.1-pro/hc16v3_dev_002-ring-5x2-k10-f29cf5a2/index.html) |
| deepseek-v4.1-flash | ring-5x2-k10 | 50 | 2.1601 | 2349 / 2500 | all_done | $11.96 | [Run](../results/hc16v3_dev_002/team-ring-5x2-k10/deepseek-v4.1-flash/hc16v3_dev_002-ring-5x2-k10-78e50fff/index.html) |
| kimi-k3.1-pro | solo | 1 | 1.7539 | 196 / 200 | all_done | $1.38 | [Run](../results/hc16v3_dev_002/team-solo/kimi-k3.1-pro/hc16v3_dev_002-solo-feca83f5/index.html) |
| deepseek-v4.1-flash | open | 10 | 0.8391 | 464 / 500 | all_done | $2.67 | [Run](../results/hc16v3_dev_002/team-open/deepseek-v4.1-flash/hc16v3_dev_002-open-5f533da2/index.html) |
| deepseek-v4.1-flash | independent | 10 | 0.6602 | 493 / 500 | all_done | $2.27 | [Run](../results/hc16v3_dev_002/team-independent/deepseek-v4.1-flash/hc16v3_dev_002-independent-3631e4b1/index.html) |
| deepseek-v4.1-flash | cull | 10 | 0.0000 | 299 / 500 | round_limit | $1.37 | [Run](../results/hc16v3_dev_002/team-cull/deepseek-v4.1-flash/hc16v3_dev_002-cull-2433e454/index.html) |
| deepseek-v4.1-flash | managed | 9 | 0.0000 | 407 / 450 | round_limit | $1.70 | [Run](../results/hc16v3_dev_002/team-managed/deepseek-v4.1-flash/hc16v3_dev_002-managed-f226c55c/index.html) |
| deepseek-v4.1-flash | niche | 10 | 0.0000 | 480 / 500 | all_done | $1.63 | [Run](../results/hc16v3_dev_002/team-niche/deepseek-v4.1-flash/hc16v3_dev_002-niche-20940918/index.html) |
| deepseek-v4.1-flash | open-nocopy | 10 | 0.0000 | 484 / 500 | all_done | $2.08 | [Run](../results/hc16v3_dev_002/team-open-nocopy/deepseek-v4.1-flash/hc16v3_dev_002-open-nocopy-c2285eb2/index.html) |
| deepseek-v4.1-flash | other-family | 10 | 0.0000 | 473 / 500 | all_done | $2.44 | [Run](../results/hc16v3_dev_002/team-other-family/deepseek-v4.1-flash/hc16v3_dev_002-other-family-ec12d65d/index.html) |
| deepseek-v4.1-flash | ring-3isl-k10 | 10 | 0.0000 | 454 / 500 | all_done | $2.12 | [Run](../results/hc16v3_dev_002/team-ring-3isl-k10/deepseek-v4.1-flash/hc16v3_dev_002-ring-3isl-k10-9d054776/index.html) |
| deepseek-v4.1-flash | ring-5x2-k10 | 10 | 0.0000 | 483 / 500 | all_done | $2.40 | [Run](../results/hc16v3_dev_002/team-ring-5x2-k10/deepseek-v4.1-flash/hc16v3_dev_002-ring-5x2-k10-90279e64/index.html) |
| deepseek-v4.1-flash | solo | 1 | 0.0000 | 184 / 200 | all_done | $0.81 | [Run](../results/hc16v3_dev_002/team-solo/deepseek-v4.1-flash/hc16v3_dev_002-solo-a3c6b51b/index.html) |
| deepseek-v4.1-flash | strategies | 10 | 0.0000 | 458 / 500 | all_done | $2.19 | [Run](../results/hc16v3_dev_002/team-strategies/deepseek-v4.1-flash/hc16v3_dev_002-strategies-8574f67c/index.html) |

## Interpretation limits

There is one run per condition. Model, thinking allowance, team size, search depth and total budget differ. Larger-budget endpoints do not prove better efficiency, and these runs cannot rank policies by expected performance.

These experiments predate corrections to ring-migration selection, other-family selection and managed budget transfers. Intended migrants could be omitted from prompts; budget transfers could strand solves. The labels describe intended configurations, not verified treatment fidelity. The final scores, plant records and observed diversity are usable evidence, but an exchange-policy explanation requires a controlled rerun. Full peer visibility and model look-ahead are hypotheses for the differences, not isolated causes.

The earlier b54ec03 export was an incomplete snapshot with ambiguous solo-low labels and missing plants. The new model/run-ID bundles resolve those identities and provide final boards, turns, events and usage. Current canonical reports have been refreshed from those sources. The [historical snapshot](../results/results-so-far/final-study-evidence/reviewed-snapshot.json) and [pinned historical audit](../results/evidence-audit/README.md) retain the earlier limitations; they do not describe the new dataset.

## Separate dev000 stopping experiment

Two Opus reference runs use hc16v3_dev_000 and are excluded from the dev002 table and headline plot.

- [Free stopping](../results/hc16v3_dev_000/team-solo/claude-opus-5-5/hc16v3_dev_000-solo-f9b1e6f5/index.html): reward 2.1884, 52 / 200 solves, $1.08 estimated model cost.
- [Forced continuation](../results/hc16v3_dev_000/team-solo/claude-opus-5-5/hc16v3_dev_000-solo-59f2cf1e/index.html): reward 2.7258, 160 / 200 solves, $4.28 estimated model cost.

The forced run refused finish requests until 80% of the allocation was used and logged ten refusals. It already had a different trajectory at the earlier run's stopping budget. Continued search found a better endpoint in this run; this is not a controlled continuation of the same plant and does not isolate stopping as the cause of the difference.

## Verify the evidence

[Run IDs, source hashes and reconciliation checks](../results/results-so-far/final-team-review.json) cover 21 raw runs: 19 dev002 and two dev000 references, totaling 9,255 plant records and 17,481 usage records. Board maxima, agent solve totals, curve endpoints, observed checkpoints, request counts and logged-cost sums reconcile. This validates the saved arithmetic, not the physical model independently.

Offline refresh, with repository dependencies installed:

```bash
python scripts/reconcile_final_teams.py
python scripts/build_results_summary.py --refs-from results/results-so-far/provenance.json
python scripts/render_results_summary.py
```

These commands do not run models or ChemSep. Full experiment execution requires the configured simulator and provider access; see the task and runner documentation.
