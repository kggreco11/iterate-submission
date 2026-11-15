# Task-configured memory controls

The supplied task configuration sets the charged distinct column queries **per agent** through `experiment.simulator_budget_per_agent`. There is no implicit task family, task version, or experiment budget. For example, a configured allowance of 100 gives the single agent 100 and each five-agent team 500 total, with 100 reserved for each agent. The team objective is its best valid complete plant, never the sum of five plants. Task physics, feed data, and economics come from the supplied task.

| Condition | Agents | Sharing |
| --- | ---: | --- |
| `single_without_past` | 1 | Own state/history and direct own-result packet; no remote memory |
| `single_with_past` | 1 | Identical local baseline plus scoped retrieval of older own experiments |
| `swarm_without_past` | 5 | Own history plus exact team incumbent and latest four measured experiments |
| `swarm_with_past` | 5 | Identical direct team packet plus scoped retrieval of older team experiments |

This is agent count × past.dev availability. At 100 per agent the four allowances are 100, 100, 500, and 500 (1,200 total). The local packet path is identical within each pair. Swarms communicate through compact measured packets between rounds; there is no coordinator LLM or free-form peer chat. Supplied teammate designs can be copied and edited. Single versus swarm measures scaling with five times the total allowance, not equal-total-compute superiority. Independent five-agent search without sharing is not part of this matrix. These are pilot comparisons until repeated.

Agents independently maximize the same objective. **No distinct hypotheses, roles, or search regions are assigned.** Duplicate full-design fingerprints and new query counts are recorded, so redundant work can be assessed without imposing a search strategy.

## Run a plan, then execute deliberately

Add the experiment allowance to the task JSON you choose to run, for example:

```json
"experiment": {"simulator_budget_per_agent": 100}
```

This is a field within the full task object. The repository does not select or create the next experiment's task/configuration for you.

```sh
# Prints the plan only; no credentials, models, simulators, or memory calls.
python scripts/run_controls.py --task /absolute/path/to/task-config.json --provider modal --model kimi-k3.1-pro --backend chemsep

# Run beside the simulator with the existing authorized credentials.
python scripts/run_controls.py --task /absolute/path/to/task-config.json --provider modal --model kimi-k3.1-pro --backend chemsep --execute
```

Use the same command with another provider/model to run its single-agent and team controls. All four conditions use `run_swarm`, the same policy factory, task-specific tool schema, provider settings, prompt assembly, checker, serialized simulator capacity, and cleanup rule. Each constructs a fresh environment, service/cache, reader identities, and run ID. No evidence crosses repetitions or conditions. Condition order rotates across `--repetitions N`. `--budget N` explicitly overrides the per-agent task allowance; `--rounds N` changes the common round ceiling. Dollar thresholds are disabled in this runner; accounting remains enabled. The standalone `run_swarm.py` retains its historical 50-total allowance when no experiment budget or explicit budget is supplied; a task experiment allowance selects equal-per-agent mode by default.

Charged queries count each agent's first distinct query, including failed solves and a first use of a peer's globally cached result. Repeating one's own query is free. Backend calls, shared cache hits, and charged team queries are separate quantities. Agents cannot borrow each other's allocations. A model may finish early, so record both allowance and actual usage.

Campaigns write `runs/controls/controls-<uuid>/plan.json`, a continuously updated `summary.json`, and per-condition reports under `runs/`. They are not automatically mixed into the historical V2 published report archive. The plan includes the exact task hash, budget allocation, model, repetitions, and condition order. The first failed condition stops the campaign and retains partial evidence.

## What changed after the r3 audit

- The historical team published 156 experiments but recalled only 16 source versions; its winning round-24 design was never retrieved. The exact packet now guarantees inclusion of the current team incumbent, even if retrieval is empty or stalled. The empty initial plant is also represented, so a losing experiment cannot be mislabeled as the incumbent.
- The winning raw record contained 54,406 characters, beyond the 8,000-token evidence budget's approximate 32,000-character allowance. Publications now contain at most 6,000 UTF-8 bytes: exact settings, scalar objective/validity, bounded product observations, and a clearly labeled interpretation. Large arrays and full validation results remain in the local raw trajectory.
- The old prompt reached 73,253 input tokens. The new complete input has a 32,000-byte default cap, including tool schemas and a framing reserve. State, local history/error, and incumbent must fit intact; optional records are admitted whole. Overflow aborts before a model request. Token estimates are labeled estimates, not provider tokenizer counts.
- Each agent retains its latest 12 turns, last rejected-edit error, and actual best turn. A provider conversation is not assumed to preserve omitted history.
- Rejected edits are audited locally and never published. Shared records omit nested citation lists and edit payloads. Only citations and exact design versions actually emitted in the current prompt are authorized.
- Retrieval queries describe the current paths, unsold streams, objective, and failed columns. Prompts contain bounded derived text and canonical source measurements, without duplicating full simulator records.
- Each proposal round publishes one scoped batch. Default ingestion checks poll without sleeping; latest results are delivered directly while the remote index catches up. Pending ingestion counts and recall diagnostics are recorded. Use `scripts/run_swarm.py --memory-blocking` for explicit synchronous qualification. A completed search may still have pending remote ingestions; it does not certify those jobs eventually succeeded.
- At an exhausted query budget, both the shared runner and legacy single-agent runner deterministically remove only unsolved branches and re-evaluate the already measured prefix. This uses no new distinct queries. Original proposals and cleanup results remain auditable.

## Clean slate means scoped access, not an empty console

past.dev retains records from older runs in the project, and the project console can show those records. A project key has broader access than a reader identity. A new experiment uses a new UUID audience with new reader identities; every published point explicitly names that audience. The adapter accepts a recalled document only if **every** supporting source belongs to the current run. Mixed and foreign sources cannot enter a prompt.

When any selected condition uses past.dev, before any control starts the campaign probes a fresh audience for prior findings. At the actual past.dev condition's startup, it probes every new reader again before constructing policies or spending simulator queries. A nonempty **raw** result aborts; an empty result obtained only after filtering is insufficient. `memory-preflight.json`, `metrics/clean-slate.json`, and `raw/memory-requests.json` retain the outcome. These are query-based checks plus scope/source enforcement, not proof that the entire project contains no stored records.

If the preflight fails, inspect project-visible data or supply a dedicated experiment project key. Do not delete or reclassify historical memory as part of a run. This implementation does not purge the project or reuse audiences.

`scripts/check_memory_isolation.py --run RUN_DIRECTORY --env-file ENV_FILE` queries a fresh outsider about a prior run and writes a uniquely named probe artifact. It never overwrites the original startup result.

## Smoke tests and evidence

```sh
python -m pytest -q
python scripts/smoke_controls.py --task /absolute/path/to/task-config.json
python scripts/smoke_controls.py --task /absolute/path/to/task-config.json --live-past --env-file /absolute/path/to/authorized.env
```

The offline smoke reads the supplied task allowance and runs all four conditions with deliberately empty historical retrieval. A 100-per-agent fixture exercises 100, 100, 500, and 500 charged queries respectively. It makes no model API or ChemSep calls. The past.dev cells are explicitly labeled an offline stand-in in this smoke, not a measurement of service performance. Regression tests independently verify profitable incumbent delivery, missing-feedback repair, compact oversized records, citation quarantine, prompt overflow before provider calls, asynchronous polling, per-point batch scoping, free cleanup, and task-enabled optional design settings.

The optional live probe creates a named smoke audience, publishes one compact canary, waits for indexing, confirms a reader in that audience sees it, and confirms a fresh audience cannot retrieve it even with a targeted query. It makes live past.dev calls and retains that canary for audit. No model or ChemSep API is used. It validates access isolation and new ingestion, not search improvement or provider attention quality.

Sanitized smoke results are in [the smoke evidence](../results/swarm-memory-smoke-20261114/summary.json). Full prompts, exact source IDs, section sizes, prompt hashes, incumbent inclusion, source rounds, filtering counts, and provider usage are retained in local run artifacts. These allow examination of what an agent was sent. They do not establish whether a provider silently truncates internally; Kimi diagnostics mark that policy as unreported.

Use repeated `--condition NAME` options to select a subset. A standalone `single_without_past` or `swarm_without_past` execution needs no past.dev credentials and performs no remote preflight. All four cells remain the default. Historical smoke evidence linked above predates this corrected matrix.

### Delayed asynchronous visibility

In nonblocking mode, a pending ingestion older than the visibility timeout remains pending and is polled on later barriers. Memory request events record `pending_age_s` and `visibility_overdue`; delayed data is never represented as completed or available. Explicit ingestion failures still abort. Blocking mode retains its deadline. Report pending/overdue ingestion alongside actual retrieval usage when interpreting memory controls.

Recall queries keep their original content while within 768 UTF-8 bytes. Larger queries use bounded chemistry, failed-setting, and path sections to avoid provider query-length errors. This changes only retrieval query construction; returned evidence still passes the same run-scoped source checks.
