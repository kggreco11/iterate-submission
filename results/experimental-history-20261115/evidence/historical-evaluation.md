# Where we stand: all results so far (14 November 2026)

## Plain-language summary
- **Agents beat search by a wide margin on every task version.** Opus reaches 2 to 6 times the reward of the non-agent search robots (far more on
  some V2 tasks) with fewer simulator calls.
- **One Opus run gets close to the best plant that small changes can reach.** A local polish (remove, add or re-tune columns) finds only
  0.6% to 6.6% more on any task, in V1, V2 or V3.
- **But one run is not the best plant that exists (V3).** On two of the four V3 tasks, Opus's *V2* plant, designed for different prices and
  re-priced at V3 prices, beats Opus's own V3 plant by 16% and 8% (both plants polished). So different runs find different layouts, and the gap between them is bigger
  than anything local tuning recovers. That spread is exactly the room a swarm (or several independent runs) could exploit.
- **The new V3 options get used selectively.** Opus kept three double-effect columns in one plant, tried and rejected them in another, and never
  tried them in the other two. It almost never tried side draws.
- **Cheaper models come close on the one task measured.** Kimi K3.1 Pro reached 91% of the best known V2 dev_000 plant using 200 calls and
  $1.26, against Opus's 97% with 106 calls and $2.86. GPT-6.1 Sol reached 74% of the best known V1 dev_000 plant at 200 calls (cost unknown).
- **The completed five-agent Kimi swarm finished 1.91% below the single agent**, using 454 charged queries versus 200 and estimated model cost $19.73 versus $1.26. This is an unequal-budget pair, not a causal test of sharing.

How sure: one run (seed) per task and condition throughout; Kimi and Sol each on one task. These are first looks, not established results.

## The tasks
| version | what it is | cost level (energy, capital) | dev ceilings |
|---|---|---|---|
| V1 `hc12` | 12 hydrocarbons, 95% purity sells | x1, x1 | about 4.7 to 6.9 |
| V2 `hc16v2` | 16 hydrocarbons, 99% premium grade (x1.2), blends at 85%, feed pressure 10-25 bar | x2, x10 | 5.3, 6.6, 9.9, 7.0 |
| V3 `hc16v3` | V2 feeds plus side draws and double-effect (heat-integrated) columns | x6, x10 | same as V2 |

Rewards are (product value - plant cost) / (value of the most valuable pure stream in the feed). The ceiling (everything pure, premium grade, at no
cost) is unreachable. Below, "best known" is the best plant any method has produced for that task (an agent, its local polish, or another
version's plant re-priced); it is a reference, not a proven optimum.

## Results by task version

### V1 (Hydrocarbon-12)
| task | Opus 5.5 (solves) | after polish (best known) | Opus share of best known | robots, mean of 3 at 400 solves | other models |
|---|---|---|---|---|---|
| dev_000 | 4.24 (85) | 4.26 | 99% | 1.53 (all tasks) | GPT-6.1 Sol 3.17 at 200 calls (74%) |
| dev_001 | 4.75 (64) | 5.06 | 94% | | |
| dev_002 | 3.38 (67) | 3.54 | 95% | | |
| dev_003 | 3.35 (65) | 3.53 | 95% | | |
The V1 Opus runs were cut short when the account ran out of credit (25 to 32 turns), so they are lower bounds.

### V2 (Hydrocarbon-16)
| task | Opus 5.5 (solves) | after polish (best known) | Opus share | robots, mean at 400 solves | other models |
|---|---|---|---|---|---|
| dev_000 | 3.63 (106) | 3.75 | 97% | 0.45 to 0.95 by robot | Kimi K3.1 Pro single 3.42 at 200 calls, $1.26 (91%); Kimi 5 x 100 swarm 3.36 at 454 team queries, completed (about 90%) |
| dev_001 | 4.63 (113) | 4.72 | 98% | 0.13 to 0.84 | |
| dev_002 | 7.38 (204) | 7.47 | 99% | 0.80 to 1.54 | |
| dev_003 | 5.19 (153) | 5.29 | 98% | 1.89 to 2.99 | |
Opus cost $2.86 to $4.98 per run ($14.41 for four). Its plants sell 27-37% of revenue as blends and earn 10-12% from the premium grade.

### V3 (Hydrocarbon-16 with side draws and double effects, energy x6)
| task | Opus 5.5 (solves, $) | Opus after polish | Opus's V2 plant at V3 prices, after polish | best known | Opus share | V3 options in Opus's best plant |
|---|---|---|---|---|---|---|
| dev_000 | 2.77 (233, $4.18) | 2.83 | 2.72 | 2.83 | 98% | 3 double effects (30, 39, 67 MW of heat passed) |
| dev_001 | 2.85 (153, $4.45) | 3.03 | **3.53** | 3.53 | **81%** | none (1 side draw tried) |
| dev_002 | 5.13 (110, $2.58) | 5.16 | **5.57** | 5.57 | **92%** | none (never tried) |
| dev_003 | 4.44 (284, $4.14) | 4.53 | 4.20 | 4.53 | 98% | none (7 double-effect turns tried, none kept) |
Plant cost is 22-40% of revenue at V3 prices (V2: 12-15%). Opus finished each run itself before the 400-call budget. $15.34 for four runs.

## What the results say about the research questions

**1. Do agents beat search?** Yes, clearly, on every version: Opus at 2 to 6 times the robot score (far more on some V2 tasks), with fewer calls. The robots are not a
competitive bar; "best known" is the right reference.

**2. Is the task saturated?** It depends on what saturated means.
- *Locally, yes:* a single Opus plant is within 1-7% of what small changes reach, on all three versions.
- *Globally, not on V3:* two of four V3 tasks have a better known layout than the one Opus found. Different runs find different
  layouts (after polishing both: +16% on dev_001, +8% on dev_002), and on the hardest version the difference is larger than local tuning recovers. V3 is the first version where this shows up.

**3. Can agents get similar results with fewer calls?** Mostly yes for Opus: on V2 it had 96-100% of its final score by 100 calls on every task.
On V3 it needed more: by 100 calls it had 97%, 45%, 100% and 91% of its final score (dev_001 found its good layout late, between 100 and 150 calls).

**4. Can a weaker model match Opus at the same number of calls?** Only one task measured: Kimi at 200 calls reached 94% of Opus's score with 106
calls, for 44% of the dollars. Sol on V1 reached 75% of Opus's (truncated) score at 200 calls. Not enough for a conclusion; it needs the same
tasks and more seeds.

**5. Do swarms help?** The completed Kimi pair does not show a gain: the single agent reached 3.421925 with 200 queries in 559 seconds, while the five-agent swarm reached 3.356596 with 454 charged queries (409 backend calls) in 3,285 seconds. Model estimates were $1.259648 and $19.727076. One unequal-budget pair does not establish a general architecture advantage; equal-budget runs and a no-sharing best-of-N control are still needed.

## Caveats that apply to everything
- One seed per task and condition: run-to-run variation is unmeasured, and the V3 result suggests it is large.
- Different budget horizons: Opus was told 400 calls and stopped itself (106-284); Kimi had 200; the swarm 5 x 100. Compare at equal calls
  (`scripts/curve_check.py --upto N`) and disclose the horizon.
- "Best known" is not an optimum; the ceiling is unreachable.
- Prices, the premium, the blend discount and the cost multipliers are benchmark assumptions; the cost model is calibrated on six hydrocarbons and
  extrapolates for propylene and n-nonane. No second-simulator check of the 16-component or side-draw columns.
- V1 Opus runs were truncated by credit exhaustion. The V3 robot baseline was stopped after 9 of 28 runs (not reported).

## Spend so far (model APIs, estimated)
Opus: V1 about $4.82, V2 $14.41, V3 $15.34 (about $34.6). Kimi: single $1.26, swarm $19.73 at completion. Sol: unknown (pricing not recorded).
Kimi/Sol ran on the Azure VM. Attributable VM and memory charges are not recorded; model estimates are not total experiment cost.

## What I would do next
1. **Measure run-to-run spread on V3:** 2 more Opus seeds on the four V3 dev tasks (about $30). This says how much a "best of N" or a swarm can gain,
   which is the core of the swarm question.
2. **Run the swarm comparison on V3 with the no-sharing control** at equal total calls: 1 agent, 3 independent agents (best of 3), 3 agents with
   shared memory. the team’s harness already supports the conditions; it needs `hc16v3` task files.
3. **Same-task model comparison:** Kimi (and Sonnet) on the same V3 tasks at the same budget as Opus.
4. Keep test tasks sealed until the protocol is frozen.

Sources: `results/opus-5-5-dev-first-look/`, `results/robot-baselines-dev/`, `results/hc16v2-first-look/`, `results/hc16v3-first-look/`,
`results/hc16v3-multi-effect/`, V2 robots in `runs/v2_bench` (summary in this note), canonical Kimi/Sol bundles under `results/<task>/<condition>/<model>/<run-id>/`. Historical snapshots are not final results.
