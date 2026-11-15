# Historical benchmark catalogue

Start at [Results](README.md) for the maintained findings and model-run inventory. This catalogue covers older benchmark evidence, including robot baselines, repriced plants and local polish. Its row count is not a count of independent model experiments.

## The data
| file | what |
|---|---|
| [`all_results.csv`](all_results.csv) / [`all_results.json`](all_results.json) | One row per run (98 rows): version, task, method (agent / robot / polished plant / re-priced plant), model, condition, seed, budget told, solves used, turns, best valid reward, ceiling, share of ceiling, best known, share of best known, best at 40/100/200 solves, estimated model dollars, stop reason, source file, notes |
| [`data/designs.jsonl`](data/designs.jsonl) | The best plant of each agent run: every column's settings (stages, reflux, boil-up, pressure drop, side draw, double effect) and the products sold |

Run `python scripts/sync_reports.py` to generate HTML from saved evidence, then `python scripts/collect_results.py` to rebuild the queryable CSV/JSON. Canonical run IDs deduplicate historical copies; swarm designs retain agent IDs. "Best known" is the best valid reward any row reached on that task; it is a
reference, not a proven optimum. The ceiling (every component sold pure, premium grade where it exists, at zero cost) is unreachable. Kimi and Sol rows
come from canonical report bundles; the five-agent Kimi swarm row is the completed outcome (454 queries, reward 3.356596). No remote branch is needed.
Robot rows are summarised from local run files when available. Existing archived aggregate rows are retained when their raw files are absent, with that evidence limit recorded in `note`.

## Reports by topic
| topic | report | data |
|---|---|---|
| Task V1 (Hydrocarbon-12), simulator | [`docs/SIMULATOR.md`](../docs/SIMULATOR.md), [`docs/TASK_BRIEF.md`](../docs/TASK_BRIEF.md) | [`hc12-qualification/`](hc12-qualification/) |
| Task V2 (Hydrocarbon-16: premium, blends, costs) | [`docs/TASK_V2.md`](../docs/TASK_V2.md) | |
| Task V3 (side draws, double effects, energy x6) | [`docs/TASK_V3.md`](../docs/TASK_V3.md) | [`hc16v3-side-draw/`](hc16v3-side-draw/), [`hc16v3-multi-effect/`](hc16v3-multi-effect/) |
| Robot baselines, V1 | [`robot-baselines-dev/summary.md`](robot-baselines-dev/summary.md) | rows in `all_results.csv` |
| Opus 5.5 on V1 (first look, truncated by credit) | [`opus-5-5-dev-first-look/README.md`](opus-5-5-dev-first-look/README.md) | run, turn and usage logs in that folder; `polish_check.json`, `v2_whatif.json` |
| Opus 5.5 on V2 | [`hc16v2-first-look/README.md`](hc16v2-first-look/README.md) | run, turn and usage logs in `opus-5-5/`; `polish_check.json` |
| Heat integration between columns (bookkeeping, not a decision) | section in the evaluation; [`docs/TASK_V3.md`](../docs/TASK_V3.md) | `hc16v2-first-look/heat_integration.json` (energy x2), `heat_integration_energy_x6.json` |
| Double-effect gate test and cost-level tuning | [`docs/TASK_V3.md`](../docs/TASK_V3.md) | `hc16v3-multi-effect/gate.json`, `gate_summary.txt` |
| Opus 5.5 on V3 | the evaluation, V3 section | run, turn and usage logs in `hc16v3-first-look/opus-5-5/`; `polish_check.json`, `polish_v2plants_at_v3.json`, `polish_summary.txt` |
| Kimi V2 single vs five-agent swarm | [`docs/V2_KIMI_COMPARISON.md`](../docs/V2_KIMI_COMPARISON.md) | Canonical single/swarm bundles linked in [`README.md`](README.md) |
| Swarm harness, shared memory, runtime | [`docs/SWARM.md`](../docs/SWARM.md), [`docs/AZURE_RUNTIME.md`](../docs/AZURE_RUNTIME.md) | [`azure-runtime/`](azure-runtime/), `hc12_dev_000/shared-memory-2/` |

## Scripts that produced the analyses
`scripts/curve_check.py` (is the reward still rising), `scripts/polish_check.py` (local optimality; `--as-family` re-prices a plant on another
version's task), `scripts/heat_integration_potential.py`, `scripts/multi_effect_gate.py`, `scripts/side_draw_qualify.py`, `scripts/v3_usage.py`
(how an agent used side draws and double effects), `scripts/collect_results.py` (this folder's data files).
