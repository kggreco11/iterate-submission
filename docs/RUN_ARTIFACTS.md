# Run artifacts

Local experiments use a predictable hierarchy:

```text
runs/
  README.md                           generated index
  hc12_dev_000/
    single-agent/
      gpt-6-luna/
        <run-id>/
          config.json                 task, model and budget settings
          source-manifest.json        source hashes, when captured
          manifest.json               status, original location, evidence gaps
          raw/                        requests, responses and trajectory
          metrics/                    summary and estimated pricing
          reports/index.html          shareable, self-contained report
```

A run ID identifies one independent trial. The condition will distinguish
single-agent, shared-memory-3, shared-memory-5 and any no-sharing controls.
Never mix mock tests, simulator qualification and agent experiments in aggregate metrics.

The current pilot still writes to its original flat directory. Run
`python scripts/organize_run.py runs/luna-pilot-20261114T211810Z`
to refresh its organized snapshot without moving files beneath the active process.
Future Luna pilots write under the hierarchy directly, in `raw/`; pass that raw
directory to the same organizer. The source path in manifest.json remains
authoritative while a run is active. A finished run may have stopped at a time
or request limit: consult metrics/summary.json for the stop reason and solves used.

`runs/` is Git-ignored working storage. Completed publishable reports are generated automatically by the current completion/export paths under `results/<task>/<condition>/<model>/<run-id>/index.html`, with summary, report-data and hash manifest. The manual copy step is superseded by `scripts/sync_reports.py`; see [report generation and sync](AUTOMATIC_REPORTS.md). Both `results/README.md` and `results/index.html` are regenerated. Raw simulator evidence not exported remains explicitly unverified; never copy credentials or command payloads.

Existing `results/hc12-qualification/` is a simulator qualification, and
`results/reference-20261114/` is the older six-component reference work. They
retain their paths to preserve existing links. `runs/integration-smoke/` is a
scripted mock harness check, not a Luna result.

## Standard experiment report

Every completed pilot report includes the light-mode metrics dashboard, ideal
zero-cost/perfect-separation economic ceiling, and per-submission flowsheet
replay. Replay provides play/pause, previous/next and arrow-key navigation, a
submission slider, best-design shortcut, clickable equipment/stream details,
and synchronized candidate/best economics, validity and call counts. Show
unobserved or budget-incomplete branches explicitly. Do not call this a P&ID:
these artifacts contain process topology, not instrumentation specifications.

`agents/luna_pilot.py --model gpt-6.1-sol` runs the same 50-evaluation pilot
protocol as Luna and automatically builds the organized report when finished.
The model is the intended experimental change; prompt, low reasoning effort,
output-token cap, retry policy and initial state stay the same. Both pilots
use the original Azure transport, so timing includes that overhead. Fresh
memory-enabled controlled runs will use the new shared harness/runtime.
