# Shared-memory harness

`python scripts/run_swarm.py` runs a two-agent, two-round **scripted mock plumbing test**, with no model API. `--memory past --env-file /absolute/path/to/.env` uses the authorized project key without copying it. Run from the repository root. New controlled experiments use the [task-configured memory controls](MEMORY_CONTROLS.md): four conditions through the same harness, with the per-agent allowance supplied by the task configuration.

For controlled runs select `--agents 1`, `3`, or `5`, `--backend chemsep`, `--memory past`, and explicitly select provider/model. The runner reuses `agents/llm_agent.py` prompts, policies and tool schema, `Ledger`, `DesignEnv`, and its independent checker. Single-agent runs receive the identical memory interface. There is no coordinator model. Each policy owns a complete flowsheet.

## Protocol and conservative defaults

All agents propose concurrently from the previous round's information and their own recent history/error feedback. Each measured result is compacted; rejected edits remain local. Shared conditions receive the exact incumbent and recent results directly. past.dev publishes one batch per round and polls ingestion without sleeping by default; `--memory-blocking` restores synchronous waiting. The pending-job deadline defaults to 300 seconds plus at most one 30-second HTTP request; use `--memory-timeout` to configure it. Observed memory failures abort and preserve artifacts. Pending jobs at search completion are reported, not certified successful. No automatic network/solver/model retries occur. Round limit defaults to 2 for plumbing; explicitly set it for experiments.

Without a task experiment allowance, historical equal-total defaults remain 50; 17/17/16; or 10 each. `--repetition` rotates the smaller three-agent shares. A task field `experiment.simulator_budget_per_agent` selects equal-per-agent mode by default. `--budget N` explicitly sets the total in equal-total mode or each agent's allocation in equal-per-agent mode. The four-control runner always uses equal-per-agent allocations and requires a configured allowance or an explicit override. `--task tasks/hc16v2_dev_000.json` selects V2 economics. Two agents are plumbing only. Exhausted/finished agents stop proposing; evidence remains readable. Shares are never borrowed. A partially evaluated design is invalid. At the cap, deterministic removal of unsolved branches can validate a measured prefix without new queries; both runners audit this cleanup.

Charging is **distinct query per agent**, including failures. A peer's cached query still consumes the requesting agent's share the first time; repeated own queries do not. Team charged queries are the sum of these agent counts, not the global union. Global cache hits and actual backend calls are separate. A fresh service/cache is required for every run; CLI constructs it. One simulator worker protects local ChemSep and makes capacity equal across conditions. Atomic cache lookup/solve fixes duplicate concurrent backend calls; exceptions become cached failed evaluations. Returned results are copied to prevent cache mutation. Models can run concurrently; solver calls are serialized.

Each run gets a UUID audience and unique reader identities. Every write includes the audience. Every new reader must return zero raw prior findings before work starts; failure aborts. Reads subsequently accept only evidence whose **every** source belongs to that run. Starting a new run resets history/cache/environment and uses a new scope; old evidence is retained remotely for audit, not deleted. The project console/key can see older audiences. See [clean-slate behavior and verification](MEMORY_CONTROLS.md#clean-slate-means-scoped-access-not-an-empty-console).

Copying uses `source_design` plus `evidence_ids` and edits. Only versions and citations actually included in the current prompt are eligible, whether delivered directly or retrieved. Exact settings are supplied without full simulator arrays. Invalid provenance or edits are rejected locally and consume no solver budget; rejected citation IDs never enter shared records. Interpretation remains a hypothesis. A 32,000-byte default input cap covers state, history, evidence, schemas, and a framing reserve; every agent prompt and its selection diagnostics are saved.

## Runner integration

`run_swarm(task, service, memory, policy_factory, out, n, rounds, repetition, mode, model)` is backend independent. Supply a fresh `SolveService(backend)`; backend implements `solve_column(request)` returning the existing simulator result contract (see `sepdesign/service.py`). Backend adapters must disable their own retries. CLI ChemSep sets `retry=False` and runs directly beside ChemSep. No VM or Azure transport dependency is introduced.

A policy factory receives `(agent_id, raw_directory, run_id)` and returns a runner-compatible `call(system, user, env)` object. Optional `ledger` uses the existing per-request ledger. `PastMemory` implements `start/publish/barrier/recall`; `LocalMemory` is exclusively a deterministic test double.

Artifacts follow `docs/RUN_ARTIFACTS.md`: `runs/<task>/<condition>/<model>/<run-id>`. Config, manifest, full checked submissions, design provenance, evidence/write/read IDs, per-agent usage, team summary, simulator queue/solver events, model timing and memory request timing are retained even on abort. Raw commands and credentials are not recorded. Memory/compute USD remain explicitly unknown; known LLM totals and unknown request counts are separate. Provider cached/reasoning counts remain in request ledgers.

API spend enforcement is disabled by default, as requested. Usage is always recorded;
unknown dollar costs remain explicitly unknown. Passing `--max-usd` enables an
optional per-agent between-request threshold and requires known model pricing.
This is not a strict billing ceiling. Simulator budgets remain enforced in all
cases. Freeze checker and experiment configuration before reported campaigns.

## past.dev API references inspected

- https://past.dev/docs/memory-api/setup
- https://past.dev/docs/memory-api/access-control
- https://past.dev/docs/memory-api/api-reference
- https://past.dev/docs/memory-api/sending-data

The live probe uses scripted policies and a mock simulator; it verifies memory plumbing, not physical simulator performance or swarm improvement. Agent B must retrieve A's first evidence, copy that version and explicitly revise reflux in round two. A separate run reader must return no accepted evidence. Inspect `raw/trajectory.jsonl` and `metrics/isolation.json`.

## Validation on November 14, 2026

26 deterministic tests passed. The live past.dev test completed in 91.27 seconds: four submissions, four charged distinct queries, three mock backend calls, two cache hits. B cited A v1, copied its design and changed reflux to 4.0; the separate reader returned no original-run sources. Reviewed evidence is in `results/hc12_dev_000/shared-memory-2/scripted/swarm-5fe736c8394b44ceb45fe8e825468f94/`. No model API or real ChemSep calls were made. The live bundle predates the final source-manifest/raw-response instrumentation; its manifest records that gap.


## Failure evidence and runtime integration

The branch incorporates the persistent-runtime changes from main. Every concurrent
policy outcome is persisted as it completes, including agent, round, complete
response or error type, and elapsed model time. A failed policy aborts the round
before any proposal is evaluated, while retaining successful peers' responses.

Backend exceptions are cached as structured infrastructure failures and raised as
`InfrastructureError`, including on cache hits. They abort the swarm with
`infrastructure_error` status; the attempted call, charged query, proposed design,
and raw failure remain in artifacts. Explicit solver nonconvergence remains a
normal invalid design. The runtime regression also verifies partial artifacts
survive this failure classification. Local combined suite: 39 tests passed.


OpenAI policies use the Responses API with low reasoning and one required function
call per proposal. Chat Completions rejected Sol reasoning with function tools in
the first live VM attempt. See the [Responses function-calling interface](https://developers.openai.com/api/docs/guides/function-calling).

`python scripts/check_memory_isolation.py --run RUN_DIRECTORY --env-file ENV_FILE` probes a fresh audience and reader against an existing run, checking both accepted memories and raw source overlap. No model or simulator calls are made.

Each completed or failed run automatically writes `report.html`, linking per-agent reports with replay and product sale grades. Reports never spend additional simulator calls. Kimi uses `--provider modal --model kimi-k3.1-pro` and the existing Modal environment configuration.
