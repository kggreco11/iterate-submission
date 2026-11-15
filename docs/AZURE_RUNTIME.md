# Persistent Azure simulator runtime

`run_vm_agent.py` runs the project’s `agents.llm_agent.run_agent` loop beside ChemSep.
The existing `scripts/run_llm_agent.py` remains the general multi-task runner;
this entry point uses the frozen task JSON, disables solver retries, and fixes
simulator capacity to one. It does not implement swarm scheduling or change
prompts, budgets, memory, or checker policy. Existing pilot/viewer files are untouched.

```text
Azure deploy → detached Scheduled Task → run_agent
                                          ├─ model/provider call
                                          ├─ env.evaluate → in-process service/cache
                                          │                 → serial ChemSep backend
                                          └─ usage, turns, replay, raw simulator evidence
Azure status/report/export ← persisted files
```

There is no Azure request per submission. Launch uses a unique SYSTEM Scheduled
Task so the Python loop survives Run Command cleanup without an interactive
Windows desktop. Each run has an isolated source directory and output directory.
Duplicate deployment/launch/run IDs are rejected; failed runs are not resumed
implicitly. The Scheduled Task has a two-hour execution limit. A killed process
or VM outage may leave `status.json` at `running`; inspect Scheduled Task state
before treating it as live. Completed task definitions remain for inspection.

## Reproduce the credential-free benchmark

Use the repository virtual environment locally. Stage new source files before
deployment: the package includes allowlisted **tracked working-tree source**,
not `.env`, local run artifacts, or credentials. The returned SHA-256 identifies
the exact ZIP. Run IDs use only letters, digits, underscores and hyphens.

Set `AZURE_RESOURCE_GROUP` to the resource group for your own deployment.

```bash
python scripts/azure_runtime.py deploy --run-id YOUR_ID --pilot-dir /absolute/path/to/terminal/pilot
python scripts/azure_runtime.py launch --run-id YOUR_ID --budget 12 --pilot-dir /absolute/path/to/terminal/pilot
python scripts/azure_runtime.py status --run-id YOUR_ID --pilot-dir /absolute/path/to/terminal/pilot
python scripts/azure_runtime.py report --run-id YOUR_ID --pilot-dir /absolute/path/to/terminal/pilot
python scripts/azure_runtime.py export --run-id YOUR_ID --pilot-dir /absolute/path/to/terminal/pilot
```

Every command requires a local pilot `summary.json` or `failure.json`. This guard
protects the named frozen pilot; it is not a global lock against other operators.
Coordinate Azure Run Commands and simulator use before launching another run.
Never launch multiple runtimes for a controlled comparison: the serialization
lock is per runtime process, not VM-wide. A future round harness must share one
service/backend rather than launch one process per agent.

Control output is bounded. `report` downloads only the compressed runtime report;
`export` downloads a terminal archive in 2100-byte chunks with size/SHA-256
verification. Full export can be slow because each chunk pays Run Command latency.
Export is outside experiment wall time. Use `report` for routine checks, and
retain full evidence on the VM until export finishes. Deployment is intended for
this small source bundle; large packages should use a separately approved blob
transfer mechanism. Azure failures are not automatically retried.

## Timing interpretation

- `control_plane_s`: host-measured Azure deployment, launch, status or export latency.
- `submission_transport_s`: zero by construction for the in-process evaluator.
- `model`: provider-call wall time (scripted policy computation in free tests).
- `queue`: wait to acquire the single backend worker.
- `backend`: full backend invocation wall time.
- `solver_reported`: backend `runtime_s`, including valve flash, process execution,
  parsing and costing; **not isolated solver CPU time**.
- `evaluation`: entire flowsheet evaluation, including cache lookups and checks.

Evaluation contains backend/queue time; backend contains solver-reported time.
These overlapping fields must not be added together. JSONL events preserve
individual durations and counts. Queue contention is exercised by a local test;
a single sequential agent should show almost zero queue time. Raw backend cases
and results are saved separately from the compact feedback.

## Remaining integration requirements

The Azure launcher intentionally permits only the scripted provider. Paid runs
need an explicit approved VM credential destination/security decision; this code
neither uploads keys nor includes them in Azure payloads. The VM entry point can
use an already provisioned provider environment, but that setup was not exercised.
the project’s existing provider implementations, retry behavior and cost ledger remain
unchanged; validate Luna API compatibility, price coverage and effective spend
caps before paid use (unknown prices currently cannot enforce a dollar cap).

This is transport validation, not the controlled experiment harness. Implement
synchronized 1/3/5-agent rounds, 50 / 17-17-16 / 10-each shares, past.dev write/read
barriers and isolation, cache charging rules, and the agreed accounting/freeze
checks separately. Keep one shared simulator worker across all conditions and
solver retries disabled. No claim about model quality or memory benefits follows
from this benchmark.

Alternatives: a VM HTTP/RPC service could keep credentials on the host but needs
network authentication/exposure decisions and reconnect/idempotency handling.
An SSH tunnel requires SSH provisioning. Blob queues avoid a public endpoint but
add polling/storage dependencies. Co-locating the loop is the smallest change
that removes Run Command latency from every submission; Azure stays the control
plane only.

## Review hardening

Control responses carry a fresh operation UUID plus run ID and action. A caller
requires exactly one matching marker and rejects stale, unrelated or duplicate
responses without echoing remote output. Control logs retain those identifiers.

Runtime terminal status preserves the agent stop reason. Returned API errors
and unknown stop reasons produce `failed` plus failure.json, even if the agent
loop returned normally. Budget, turn-limit, spend-threshold and explicit finish
stops are recorded as completed with their distinct stop reasons.

API spend enforcement is disabled by default at the user's request. Token and
cost logging remain enabled; missing prices stay unknown. If `--max-usd` is
explicitly supplied, paid models require configured pricing. That optional
threshold is checked between calls and can overshoot by one request. Simulator
budgets and turn limits remain enforced independently.
