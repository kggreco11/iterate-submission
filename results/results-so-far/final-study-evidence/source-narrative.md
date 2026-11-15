# Agent teams for separation-plant design: final results (hackathon submission)

## Plain-language summary
We built a benchmark in which AI agents design a distillation plant (a tree of columns separating 16 hydrocarbons) and are scored by a real
column simulator (ChemSep) on profit: product value minus annual plant cost. We then asked whether teams of cheaper agents, organised in different
ways, can match a single strong agent.

- **One strong agent (Opus 5.5) is far ahead of cheaper single agents** on the hardest task version (V3): 2.8 to 5.1 reward against 0.3 to 2.1 for
  Kimi K3.1 Pro alone. The difference is look-ahead: a partly built plant loses money, and Opus keeps building through that "valley" while weaker
  models retreat to an empty plant.
- **Sharing gets teams of weak agents through the valley**: with sharing, every agent reached a profitable plant; without it, 4 of 10.
- **But naive sharing makes the whole team copy one small plant.** In the first screening (Kimi, 10 agents x 50 solves), teams that saw the best plant
  every round collapsed onto one design within 7 to 10 rounds, and no team beat the solo agent. Agents copied whole plants (52% of turns in the broadcast
  team) because they could only see other plants' settings, not what the plants did.
- **We rebuilt the team harness** so agents see other plants in full, keep a private notebook, can graft one branch of another plant, and their
  reasoning is saved; and we tested many organisations: independent, open, islands with periodic exchange, copy only from other lineages, a niche
  (quality-diversity) board, protected strategies, culling the weaker half, and a supervisor who reallocates budget and branches new agents.
- **Final run (this document's main table):** DeepSeek V4.1 Flash with a capped thinking budget, ten 10-agent organisations plus a 50-agent island
  team and a solo agent, on the same task. See the table below for results and caveats.

## The task
V3 (`hc16v3`, `docs/TASK_V3.md`): 16 hydrocarbons, products sold pure (95%), premium (99%, x1.2) or as blends; energy x6 and capital x10 cost level;
side draws and double-effect (heat-integrated) columns available. Score = (product value - annual plant cost) / value of the most valuable pure stream.
All team results below are on dev task `hc16v3_dev_002`. References on that task: Kimi K3.1 Pro solo 2.13 (200 solves), Opus 5.5 solo 5.13,
best known plant 5.57.

## Earlier results this builds on
- `docs/EVALUATION_2026-11-14.md`: V1/V2/V3 single-agent and robot results (Opus 81-98% of best known on V3).
- `results/swarm-screen-dev002/`: first screening of nine Kimi organisations (10 x 50 solves): best team 2.55 (broadcast), solo 2.66 at 256 solves.
- Plant-diversity analysis (`scripts/plant_diversity.py`): sharing teams collapsed to one structure and one lineage; islands-then-merge kept 5 distinct
  final plants. F3 islands with 100 solves per agent: 2.55 (best plant still 4 columns).
- `docs/SWARM_NEXT_ROUND.md`: literature (Lazer and Friedman 2007; island-model evolutionary algorithms; FunSearch/AlphaEvolve; MAST; LLM conformity
  studies) and the design of the organisations tested here.

## Final run setup
| setting | value |
|---|---|
| model | DeepSeek V4.1 Flash on Modal (shared endpoint) |
| thinking | capped at 1,500 tokens per turn: a think step (low effort, stopped at the cap), then an act step that must call the tool. DeepSeek ignores stated length limits, so the cap is enforced by the harness |
| what agents see | own plant in full; up to 4 other plants in the same full detail (streams, separations, costs, sales); a private notebook rewritten every turn |
| how ideas move | copy a shown plant, graft one branch, or write own edits (organisation-dependent) |
| budget | 50 distinct column solves per agent (10-agent teams 500; 50-agent team 2,500); solo 200 |
| simulator | ChemSep, real; shared cache; failures retried with alternative initialisations |
| concurrency | Modal accepts at most 16 simultaneous requests per model (measured); the runs share 15 |

Organisations (`sepdesign/teams.py` presets): independent; open (everyone sees the island's best and latest plants); open-nocopy (graft or write,
no whole-plant copies); ring-5x2-k10 (5 islands of 2, the next island's best every 10 rounds); ring-3isl-k10 (3 islands of 3/3/4); other-family
(copy only from other lineages, shown the most different plant); niche (best plant of each kind); strategies (5 strategies x 2 agents, sharing within a
strategy); cull (weaker half stopped every 10 rounds, solves moved to the stronger half); managed (a supervisor reallocates solves or branches agents
every 10 rounds); 50 agents in 10 islands of 5 exchanging every 10 rounds.

## Results
Snapshot taken while some runs were still in progress (status column says so); regenerate with `scripts/summarize_teams.py`. Kimi rows use the fixed setup (unsold-stream values, plan line); the Opus row is a reference rerun in the same setup.

| run | agents | team best | best at 100 / 250 / 500 / 1000 team solves | team solves | agents off zero | best plant columns | copies | grafts | moved toward a seen plant without copying | distinct plant structures | new to team | distinct final plants | families at end | herd at end | notebook entries citing others | $ (cached-price estimate) | minutes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ring-5x2-k10-low-cap1500_50agents | 50 | **1.57** | 0.00 / 0.00 / 0.00 / 1.22 | 1510 | 15/50 | - | 47 | 0 | - | - | - | - | - | - | 781/1322 | 6.60 | 61 |
| independent-low | 10 | **1.43** | 0.00 / 1.43 / 1.43 / 1.43 | 244 | 5/10 | - | 0 | 0 | - | - | - | - | - | - | 18/130 | 1.56 | 17 |
| cull-low | 10 | **1.32** | 0.00 / 0.00 / 1.32 / 1.32 | 310 | 2/10 | - | 0 | 0 | - | - | - | - | - | - | 17/116 | 1.70 | 18 |
| open-low | 10 | **0.75** | 0.00 / 0.75 / 0.75 / 0.75 | 162 | 9/10 | - | 17 | 0 | - | - | - | - | - | - | 40/60 | 1.02 | 18 |
| solo-low | 1 | **0.18** | 0.18 / 0.18 / 0.18 / 0.18 | 72 | 1/1 | - | 0 | 0 | - | - | - | - | - | - | 0/30 | 0.42 | 18 |
| ring-5x2-k10-low | 10 | **0.14** | 0.00 / 0.14 / 0.14 / 0.14 | 132 | 1/10 | - | 0 | 0 | - | - | - | - | - | - | 7/40 | 0.68 | 18 |
| cull-low-cap1500 | 10 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 188 | 0/10 | - | 0 | 0 | - | - | - | - | - | - | 81/203 | 0.78 | 61 |
| independent-low-cap1500 | 10 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 348 | 0/10 | - | 0 | 0 | - | - | - | - | - | - | 86/387 | 1.47 | 60 |
| managed-low-cap1500 | 9 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 278 | 0/9 | - | 0 | 0 | - | - | - | - | - | - | 91/253 | 1.00 | 60 |
| niche-low-cap1500 | 10 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 443 | 0/10 | - | 2 | 0 | - | - | - | - | - | - | 80/350 | 1.44 | 61 |
| open-low-cap1500 | 10 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 329 | 0/10 | - | 3 | 0 | - | - | - | - | - | - | 217/359 | 1.62 | 59 |
| open-nocopy-low-cap1500 | 10 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 409 | 0/10 | - | 0 | 1 | - | - | - | - | - | - | 190/349 | 1.64 | 60 |
| other-family-low-cap1500 | 10 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 365 | 0/10 | - | 3 | 0 | - | - | - | - | - | - | 257/391 | 1.78 | 60 |
| ring-3isl-k10-low-cap1500 | 10 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 346 | 0/10 | - | 7 | 0 | - | - | - | - | - | - | 157/300 | 1.40 | 60 |
| ring-5x2-k10-low-cap1500 | 10 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 327 | 0/10 | - | 4 | 0 | - | - | - | - | - | - | 150/313 | 1.45 | 60 |
| strategies-low-cap1500 | 10 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 389 | 0/10 | - | 3 | 0 | - | - | - | - | - | - | 169/360 | 1.74 | 60 |
| solo-low-cap1500 | 1 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 184 | 0/1 | 0 | 0 | 0 | 0 | 50 | 26% | 0 | 1 | 100% | 15/194 | 0.81 | 32 |
| ring-5x2-k10-low_50agents | 50 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 304 | 0/50 | - | 1 | 0 | - | - | - | - | - | - | 17/107 | 1.45 | 18 |
| solo-low | 1 | **0.00** | 0.00 / 0.00 / 0.00 / 0.00 | 4 | 0/1 | - | 0 | 0 | - | - | - | - | - | - | 0/2 | 0.10 | 1 |

References on the same task: Kimi K3.1 Pro solo, 200 solves (V3 dev_002) 2.13; Opus 5.5 solo (V3 dev_002) 5.13; best known plant (V3 dev_002) 5.57.


## What we learned
- With DeepSeek (capped thinking), only the 50-agent island team reached a profitable plant; every 10-agent team and the solo agent stayed at 0 within 500/200 solves. Scale plus occasional exchange let one agent cross the money-losing stage and spread its plant.
- DeepSeek alone failed by retreating: it kept 1-column plants, removed or reverted 84 times, and spent its effort cutting cost instead of adding the columns that would unlock revenue.
- Kimi teams with the fixes reached positive plants faster (see table).
- Infrastructure: Modal allows 16 concurrent requests per model; synchronous rounds wait for the slowest agent, so very large teams are slow.
- Opus refused prompts that called the notebook 'private'; transparent wording fixed it.

## Caveats
- One seed per organisation; differences of about 0.2 reward may be noise.
- One task (V3 dev_002); test tasks were not used.
- DeepSeek's thinking is capped at 1,500 tokens; Kimi and Opus ran without caps; model comparisons mix model and thinking budget.
- Cost estimates use Modal's listed prices including the cached-input discount; check against the Modal bill.
- The cost model is calibrated on six hydrocarbons and extrapolates; prices and multipliers are benchmark assumptions.

## Reproduce
```
python scripts/run_teams.py --task hc16v3_dev_002 --models deepseek-v4.1-flash --presets independent open open-nocopy ring-5x2-k10 ring-3isl-k10 other-family niche strategies cull managed --think-budget 1500 --budget 50 --parallel 10
python scripts/run_teams.py --task hc16v3_dev_002 --models deepseek-v4.1-flash --presets ring-5x2-k10 --islands 5x10 --think-budget 1500 --budget 50
python scripts/run_teams.py --task hc16v3_dev_002 --models deepseek-v4.1-flash --presets solo --think-budget 1500 --budget 200
python scripts/summarize_teams.py runs/teams/final-10 runs/teams/final-50 runs/teams/final-solo --out results/final-dev002
```
Needs ChemSep LITE and a Modal proxy token (`MODAL_PROXY_TOKEN` in `.env`).
