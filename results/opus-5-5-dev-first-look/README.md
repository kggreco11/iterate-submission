# Opus 5.5 first look on the four dev tasks

November 14, 2026. Single agent (no memory tool, no other agents), seed 0, real ChemSep backend, solve budget 400, turn cap 150, $12 cap per run.
The prompt gives the feed, boiling points, prices, rules, settings, objective and budget; it contains no baseline or reference score.
**Every run was cut off early because the Anthropic account ran out of credit (about $4.82 of usage), at 25 to 32 turns. These are lower bounds, not
converged results.** Per-request token and dollar logs, turn logs and run files are in the subfolders.

| task | Opus best valid reward | solves used | share of ceiling | product value vs max | plant cost ($M/yr) | columns | robot mean @ 400 solves (random + greedy) |
|---|---|---|---|---|---|---|---|
| hc12_dev_000 | 4.24 | 85 | 89% | 97% | 281 | 16 | 1.53 |
| hc12_dev_001 | 4.75 | 64 | 78% | 86% | 270 | 15 | 1.23 |
| hc12_dev_002 | 3.38 | 67 | 69% | 77% | 306 | 13 | 1.51 |
| hc12_dev_003 | 3.35 | 65 | 73% | 81% | 259 | 16 | 1.82 |

Opus best at 40 / 120 solves: dev_000 3.69 / 4.24, dev_001 1.49 / 4.75, dev_002 1.90 / 3.38, dev_003 2.46 / 3.35. The robots reach 0.47 at 40 and 0.76 at
120 solves. Estimated Opus spend ~$1.2 per run (about 110k to 160k input and 33k to 38k output tokens), at $4 / $20 per million tokens (team model
configuration; estimates, not invoices).

## Reading it
- Opus reaches 2.2x to 3.9x the robot score using 64 to 85 of its 400 solves. The robots are not the right bar for agents at these budgets.
- "Ceiling" is the reward if every component were sold pure at zero cost; it is unreachable. The plants here recover 77% to 97% of the maximum product value.
  On dev_000 (97% of value, 16 columns) there is little headroom left; on dev_001 to dev_003 there is, but part of it may not be worth its cost.
- The designs look like engineering, not a cost-model exploit: 13 to 16 columns (the robots use about 34), median 80 to 120 stages, mid-range reflux and
  boil-up, extreme settings only on the most expensive columns (up to $84M/yr for the hardest split).

## Caveats
One seed per task; runs truncated by credit exhaustion; the cost model is calibrated on six hydrocarbons and extrapolates for heavier components; the
robot baselines (`results/robot-baselines-dev`) came from an earlier revision of the validity gate; the prompt supplies boiling points, so this measures
an agent with engineering knowledge, not a blind search. Single-case results do not establish that agents beat search in general.
