# Development and experiment guide

## Quick start (Windows machine with ChemSep)

1. Install **ChemSep LITE** (free, https://www.chemsep.org). The default install location is found automatically; otherwise set `CHEMSEP_DIR`
   to the folder that contains `bin\co-col2.exe` and `pcd\`.
2. Python 3.10+ and numpy:
   ```
   pip install -r requirements.txt
   ```
3. Check everything works (about 20 seconds):
   ```
   python scripts/smoke_test.py
   ```
4. Run a baseline (400 solves is about 3 minutes) and look at the plant it builds:
   ```
   python scripts/run_baselines.py --robot random_then_greedy --task 0 --budget 400
   python demo/build_replay.py runs/*.json
   ```
   then open `demo/plant_replay.html` in a browser.

**No ChemSep on your machine** (for example a Mac): everything except the real simulator runs with `--backend mock` or `SIM_BACKEND=mock`.
The mock is a toy stand-in for developing agents and tooling. Never report numbers from it; run files record which backend produced them.

## For agent authors

```python
from sepdesign import hc12_tasks, make_service, make_env, attach_trace, save_run

svc = make_service()                       # ChemSep by default; make_service("mock") for development. Share one service between agents.
task = hc12_tasks("dev")[0]                # 4 dev tasks and 12 test tasks (hc12_tasks("test")); use the test tasks only for final results
env = make_env(task, svc, budget=120)      # budget = number of DISTINCT column solves this agent may use
attach_trace(env)                          # optional: records every improvement for the replay page

env.apply([{"op": "set", "node": "", "n_stages": 60, "reflux_ratio": 4, "reboil_ratio": 4, "pressure_drop_fraction": 0.1}])
res = env.evaluate()                       # solves the whole design from the feed down
print(env.render(res))                     # compact text view of the plant, good for a language-model prompt
env.apply([{"op": "set", "node": "T", ...}, {"op": "sell", "node": "B"}, {"op": "revert"}])
env.score()                                # reward of the best design evaluated so far
save_run("runs/my_agent.json", env, task, "my agent", backend=svc.backend_name)
```

- **Design tree.** Paths name streams: `""` is the feed; a column at path `p` has outlets `p+"T"` (tops, light) and `p+"B"` (bottoms, heavy). A stream
  with no column is sold as it is, and is worth money only if it is at least 95% pure. A column can only be added below an existing column.
- **Settings per column:** `n_stages` (5 to 200), `reflux_ratio` and `reboil_ratio` (0.1 to 30), `pressure_drop_fraction` (0 to 0.9: how much the pressure
  is dropped by a valve before the column).
- **Reward** = (value of pure products - annual cost of all columns) / (value of the single most valuable pure stream in the feed). The unreachable
  ceiling (sell every component pure at no cost) is `env.econ.upper_bound_reward` (about 4.7 on the dev tasks).
- **Budget** counts distinct column solves per environment; re-evaluating an unchanged column is free. `env.evaluate_batch(designs, workers=8)` evaluates
  several candidate designs in parallel. A shared `SolveService` caches solves across agents, so agents trying the same column pay nothing extra on the
  machine, but each agent's own budget still counts it.
- **Failures.** A column that does not converge is reported with status `failed` and its feed is sold as it is. ChemSep sometimes opens an
  "iteration limit" dialog on hard designs; the solve is stopped after 20 seconds and counted as failed. (You can click Cancel.)
- **Speed.** A solve takes about 0.3 to 0.8 seconds; use threads (the solves are independent processes) to run many at once.
- `agents/example_agent.py` is a small runnable loop to copy from. Run files written by `save_run` play in the demo page.

## Language-model agent (single agent, with token and dollar accounting)

`agents/llm_agent.py` runs a single agent with an Anthropic or OpenAI model. Put the key in a local `.env` in the repo root (`ANTHROPIC_API_KEY=...`;
the file is git-ignored) and run:

```
python scripts/run_llm_agent.py --provider scripted --tasks 0 --budget 60        # free dry run, no API
python scripts/run_llm_agent.py --provider anthropic --model claude-opus-5-5 --tasks 0 1 2 3 --budget 400 --max-usd 15
```

Every request is logged to `runs/llm/<run_id>/usage.jsonl` (tokens, estimated dollars) with a `summary.json` and the turn-by-turn `turns.jsonl`; the run
file plays in the demo page. Each run stops at the solve budget, the turn cap or the per-run dollar cap and records which. The OpenAI path has been exercised in live Sol pilots and a three-agent shared-memory run. See the [master research report](../RESEARCH_REPORT.md) for current evidence and limitations.

## Task families

- `hc12` (default): Hydrocarbon-12, 12 components, 95% pure products. Unchanged.
- `hc16v2`: **Hydrocarbon-16 V2**, 16 components (adds propylene, 3-methylpentane, cyclohexane, n-nonane), a 1.2x premium grade at 99% purity,
  blended products, feed pressure 10 to 25 bar by task, and energy x2 / capital x10 plant costs. See `docs/TASK_V2.md`.

- `hc16v3`: **Hydrocarbon-16 V3**, the V2 feeds plus side draws (a third outlet from the middle of a column) and double-effect columns (one
  split done by two heat-integrated columns at different pressures), at energy x6 / capital x10. See `docs/TASK_V3.md`.

Pick the family with `--family hc16v2` (scripts) or `get_tasks("dev", "hc16v2")`, and build the simulator from the task so its cost level matches:
`task = hc16v2_tasks("dev")[0]; svc = make_service(task=task); env = make_env(task, svc)`. `make_env` refuses a service with the wrong cost level.

## Layout

```
sepdesign/   simulator wrapper, thermodynamics, cost model, environment, baselines, tasks
scripts/     smoke_test.py, run_baselines.py
agents/      example_agent.py
demo/        plant-replay page (build_replay.py + template)
tests/       environment tests (run on the mock backend)
docs/        SIMULATOR.md: what the simulator computes and how far to trust it
```

## Built with

- **ChemSep** (Harry Kooijman and Ross Taylor; free LITE edition) for the column solver, the pure-component library and the Peng-Robinson
  interaction parameters from its DECHEMA table. ChemSep is not redistributed here: install it separately and respect its license.
- **numpy** for the flash and valve calculations, the cost model and the environment.
- Peng-Robinson equation of state; Douglas, *Conceptual Design of Chemical Processes* (1988) for the sizing and capital correlations.

See the [submission checklist](SUBMISSION.md) for delivery requirements.

## Demo and evidence

Open [3D site assembly](../demo/plant_v2.html) or [schematic replay](../demo/plant_3d.html). Both work offline. [Demo instructions](../demo/README.md) include rebuild commands using the checked-in [evidence bundle](../results/progress-20261114/README.md).

For new experiments, use the [task-configured memory controls](../docs/MEMORY_CONTROLS.md): single, independent, exact-sharing, and past.dev conditions, with the per-agent simulator allowance supplied by the task configuration. Physics and economics come from the explicitly supplied task. The [historical Kimi comparison](../docs/V2_KIMI_COMPARISON.md) and [runtime instructions](../docs/AZURE_RUNTIME.md) remain available.
