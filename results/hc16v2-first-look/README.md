# Opus 5.5 on Hydrocarbon-16 V2 dev tasks (first look)

One run per dev task, seed 0, `claude-opus-5-5`, solve budget told to the agent: 400. Each agent ended its own run ("finish") before using it.
Backend: ChemSep (real simulator). Run files, turn logs (`turns.jsonl`) and token/dollar logs (`usage.jsonl`) are in `opus-5-5/`.

| task | solves used | turns | best reward (share of ceiling) | cost | net profit $B/yr |
|---|---|---|---|---|---|
| dev_000 | 106 | 58 | 3.63 (68%) | $2.86 | 3.01 |
| dev_001 | 113 | 66 | 4.63 (70%) | $2.88 | 2.43 |
| dev_002 | 204 | 93 | 7.38 (75%) | $4.98 | 3.24 |
| dev_003 | 153 | 85 | 5.19 (74%) | $3.69 | 3.01 |

## Is the reward still rising? (`python scripts/curve_check.py <dir> --upto 200`)
Gain of the best valid reward over the last 50 solves: +0.59, +0.16, +0.03, +0.19. Three runs were still creeping up when the agent stopped; dev_002 had plateaued.
"Still rising" means at least 3% of the best over the last 50 solves.

## Local-optimality check (`polish_check.json`; `python scripts/polish_check.py`)
Prune / add a column on an impure stream / re-tune settings (about 290 extra solves each): +3.2%, +1.9%, +1.2%, +1.9% (about $40-100M/yr on $2.4-3.2B).
No column was worth removing. This says small local changes do not help much; it does not rule out a different layout being much better.

## How Opus used the new rules
About 10-12% of revenue comes from the premium-grade bonus and roughly 27-37% from blend sales (blends estimated as sold streams under 95% pure with value).
Plants have 11-18 columns; column cost is 12-15% of revenue.

## Caveats
Single seed per task. Ceilings are unreachable upper bounds (every component pure at premium grade for free). The cost model extrapolates for propylene and
n-nonane. Robot baselines on V2 are not included here yet.
