# V3 400-query run configuration

Frozen task and plans from the Kimi V3 dev_000 campaign: 400 charged distinct column queries per agent, 800 rounds, one repetition, no dollar stop, no assigned roles. Kimi uses reasoning `low` and a 16,384-token output allowance. The backend is ChemSep; install its runtime and provider dependencies on the execution host (see [Azure setup](../../infrastructure/azure/README.md)). Supply credentials locally through `.env` or the environment.

`task.json` is the full task used by the 400-query campaign and recovery runs. `plan.json` records the four original conditions: single and five-agent swarm, each with and without past.dev. The single allowances are 400 each; swarm allowances are 2,000 each. The separate `independent-plan.json` records five agents without sharing (2,000 total). Plans are provenance; the runner reads the task and CLI arguments.

From the repository root, print the four-condition plan without making external calls:

```sh
python scripts/run_controls.py --task configs/v3-400/task.json --provider modal --model kimi-k3.1-pro --backend chemsep --rounds 800
```

Add `--execute` to run. This runner fixes the original one/five-agent matrix. For individual conditions and adjustable agent count, use the standalone runner:

```sh
python scripts/run_swarm.py --task configs/v3-400/task.json --provider modal --model kimi-k3.1-pro --backend chemsep --agents 5 --mode equal-per-agent --budget 400 --rounds 800 --memory past
```

Memory modes: `past` includes the direct measured-results packet plus scoped historical retrieval; `exact` supplies the direct packet without past.dev; `none` is the independent control. Use one agent for single-agent conditions. The standalone CLI currently accepts agent counts 1, 2, 3, and 5. Nonblocking memory polling is the default, with delayed ingestion retained for later polling. Each run creates fresh memory scope and simulator/cache state. See [memory controls](../../docs/MEMORY_CONTROLS.md) for accounting and isolation details.

The accompanying source includes the corrected four-condition matrix, optional condition selection, delayed-ingestion handling, and bounded recall queries used by the campaign/recovery setup. Run outputs, machine-specific deployment scripts, and credentials are excluded.

## Five independent single-agent runs

`single-agent-5x-plan.json` specifies five separate repetitions of `single_without_past`: one agent, 400 queries and an 800-round ceiling per run (2,000 queries total). Each repetition gets a fresh environment, simulator service/cache, run ID, and local memory. The `exact` memory mode contains only that single agent's own measured results; there is no past.dev retrieval or evidence shared between repetitions. This differs from the five-agent independent condition above, which uses one shared simulator cache within its run.

Print the saved plan:

```sh
python scripts/run_controls.py --task configs/v3-400/task.json --provider modal --model kimi-k3.1-pro --backend chemsep --rounds 800 --repetitions 5 --condition single_without_past
```

Add `--execute` to run all five sequentially. A failed repetition stops the campaign and retains partial evidence. Early finishes are permitted; 400 is each run's allowance, not guaranteed usage.
