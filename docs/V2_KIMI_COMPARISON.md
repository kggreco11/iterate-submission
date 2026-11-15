# First Kimi V2 comparison

> Historical study document. For the current interpretation and ongoing experiments, read the [research report](../RESEARCH_REPORT.md) and [report guide](REPORT_GUIDE.md). Original observations below retain their study-specific limitations.

This describes the historical unequal-budget comparison. New experiments use the [task-configured memory controls](MEMORY_CONTROLS.md), with an explicit per-agent simulator allowance for each of four controls.

Task: `hc16v2_dev_000`. Run the single-agent condition first, then the five-agent shared-memory condition, and review results before extending the campaign.

| Condition | Simulator budget | Model-turn limit | Estimated model spend stop |
|---|---:|---:|---:|
| Single agent | 200 | 400 | Disabled |
| Five agents with past.dev shared memory | 100 each, 500 total | 200 rounds | Disabled |

The simulator limit counts each agent's distinct queries, including failed solves and first use of a peer's cached query. Agents cannot borrow unused allocations. Actual backend calls may be fewer than charged team queries because the service shares a cache. Model spend is measured and reported, not used as a stopping constraint for this comparison. Per-request input/output tokens, requests, failures, unknown usage and estimated model cost remain recorded. Memory and VM charges are not included in the model cost estimate.

The configured Modal endpoint supplies the exact Kimi model ID through `KIMI_MODEL`; the reporting alias is `kimi-k3.1-pro`. Input/output rates are conservatively estimated at $2/$10 per million tokens, ignoring input cache discounts, from https://modal.com/docs/guide/supported-models (2026-11-14). Secrets are loaded from the existing restricted VM files, never packaged with source.

Launch `scripts/run_v2_kimi_pair.py --run-id UNIQUE_ID` on the prepared VM. The launcher runs both conditions sequentially with no repeat campaign. Failure of the single-agent process prevents the swarm from starting. A successful early `finish` or model-turn limit may consume less than the simulator allowance. Each condition constructs a fresh simulator service. The swarm uses a new past.dev audience with run-scoped source filtering.

Single-agent output is under `runs/runtime/<id>-single`; swarm output is under `runs/<task>/shared-memory-5/kimi-k3.1-pro/<swarm-id>`. Reports are generated from saved evidence automatically. The aggregate swarm report links each agent's full replay. Do not compare the five-agent team's best score as if it had the same total simulator budget as the 200-call single agent.

Validation: 64 local tests pass, including existing HC12, persistent runtime, memory isolation, failure accounting, V2 economics, configurable budgets and automatic reports. The isolated Windows deployment passed compilation and a five-call scripted/mock V2 run before paid execution.

## Response-limit fix

The r2 single-agent run stopped after 8 simulator calls: its last three completions each used all 6,000 allowed output tokens, and the old adapter raised generic ValueErrors. The exact provider finish reasons were not retained, so truncation is inferred rather than proven for that historical run.

Kimi now requests explicit `reasoning_effort=low` and a 16,384-token output allowance. The model publisher documents low/high/max and a default of max: https://huggingface.co/moonshotai/Kimi-K3.1-Pro. The comparison now disables dollar thresholds, per the user’s instruction; simulator allowances remain unchanged. This configuration needs a new live validation before claiming the original problem is resolved on Modal.

Responses marked `length` are rejected even if they include parseable arguments. Missing/multiple tools, malformed JSON and invalid edit containers get distinct errors. A response error stops the single-agent loop immediately and prevents the swarm from starting; the swarm also aborts on policy errors. No identical paid parsing retries occur. Charged usage is retained and marked failed. Per-request `response-diagnostics.jsonl` records finish reason, token counts, tool count and configured limits without credentials or response text. Regression validation: 72 tests pass, including a simulated truncated response that charges usage exactly once and uses no simulator calls.

## Local progress viewer

On the macOS/Linux controller (uses POSIX file locks), use:

```sh
.venv/bin/python scripts/watch_swarm_run.py runs/azure-control/v2-kimi-20261114-r3-controller.json
```

The JSON status reader and readable watcher share a 60-second cache and a nonblocking lock. Azure-busy responses retain the last snapshot and display its age. Ctrl-C closes only the viewer; it does not stop the remote experiment. Controller files remain local and are not bundled with demo evidence.
