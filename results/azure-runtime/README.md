# Azure persistent-runtime validation — November 14, 2026

A detached Windows Scheduled Task ran the existing scripted agent loop against
the fixed hc12 task and real ChemSep backend. Twelve submissions / twelve solves
completed in **3.671 seconds**, with one simulator worker and retries disabled.
All 12 backend solves succeeded; the best economic reward stayed at the empty
baseline. This validates transport, not agent performance.

| Measurement | Seconds |
|---|---:|
| Persistent loop wall time | 3.6712 |
| All evaluations (12) | 3.6165 |
| Backend total | 3.5682 |
| Mean backend-reported solve | 0.2973 |
| Scripted provider computation (12 calls) | 0.0070 |
| Queue total | 0.0000144 |
| Azure transport per submission | 0 (in-process) |

These measurements overlap: evaluation contains queue/backend, and backend
contains backend-reported solve time. The latter includes valve flash, solver
process execution, parsing and costing; it is not pure solver CPU time. Model
API latency was not measured: **no paid calls or credential transfer occurred**.
The inherited ledger labels the scripted run's configured model as gpt-6-luna
and its prices unknown; the provider field is `scripted`, with zero tokens.

The completed Luna pilot's 33 submissions spent 1,078.184 seconds in Azure round
trips, including 15.583 seconds of VM evaluation: **32.200 seconds overhead per
submission**. See `pilot-transport-baseline.json`. Different policies/designs
mean this is a transport comparison, not an experimental performance comparison.

See `runtime.json` for machine-readable counts/totals, `provenance.json` for the
source archive hash and VM path, and `transport.jsonl` for control-plane timings.
The initial package missed data assets and failed before evaluation; the corrected
package includes template/cost files and a regression test. Existing pilot and
viewer files were not modified. The VM remains running.

Local validation: **24 tests passed**, including queue contention/serialization,
loop accounting, source packaging, pilot-terminal guard, duplicate-run rejection,
and failure markers. [Runtime instructions](../../docs/AZURE_RUNTIME.md) describe
launch, status, report, export, timing semantics, and remaining paid-model and
synchronized-round integration requirements.

Full export passed size and SHA-256 verification (see provenance). The `evidence/`
files contain all eight exported artifacts; only CRLF line endings were normalized
to LF for Git. The original verified ZIP remains in the local run directory.
