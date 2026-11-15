# Opus 5.5 / 200-solve comparison

Prepared for comparison with `sol-200-20261114`. The reference completed with 200 distinct column solves and 208 model requests. The budget is **not** 200 model requests or 200 design submissions.

- Task: `hc12_dev_000`; fresh empty plant and cache; seed 0.
- Provider/model: Anthropic / `claude-opus-5-5`.
- Budget: 200 distinct simulator column solves; at most 400 agent turns.
- Same VM-local runner, task data, system prompt, compact state/history, validation, economics, serial simulator and disabled solver retries as Sol.
- Separate deployment: `C:\iterate-hackathon\azure-runtime-opus-200-20261114`.
- Sol source: `C:\iterate-hackathon\azure-runtime-sol-fast-five-20261114`.
- Source hashes are recorded in the controller JSON and remote `source-hashes.json`.
- Opus settings: automatic tool selection, medium effort, 6,000 total output tokens including thinking. Sol used its provider defaults. Equal simulator budget does not imply equal token usage, reasoning effort or cost.
- Two-hour Scheduled Task limit, matching Sol. No dollar threshold, matching Sol; ledger uses the existing $4/M input and $20/M output estimate. A wall timeout may interrupt before a terminal summary is written.

## Current readiness

No paid request was made during setup. Credential presence was checked without reading values: neither the project environment nor the VM machine variable nor the dedicated credential file had an Anthropic key. Live authentication and model/tool compatibility remain unverified until credentials are provisioned.

The adapter uses Python's standard-library HTTP client; no Anthropic SDK installation is required. It omits unsupported forced tool choice and records output usage even for a truncated/no-tool response. It follows the original runner's independent compact-state requests rather than replaying a multi-turn Anthropic tool transcript.

## Launch after provisioning the credential

Through the VM's secure administrative session, set `ANTHROPIC_API_KEY` as a machine environment variable, or put an `ANTHROPIC_API_KEY=...` line in `C:\iterate-hackathon\secrets\opus-200\anthropic.env` with access limited to SYSTEM and administrators. The launcher never carries credentials through Azure Run Command. Do not paste keys into chat, command arguments, or source files.

From the repository root:

```bash
.venv/bin/python scripts/setup_opus_200.py launch
.venv/bin/python scripts/watch_run.py runs/azure-control/opus-200-20261114-controller.json --vm
```

Preparation has a separate `prepare` action and refuses an existing destination. Launch refuses an existing run or Scheduled Task. A successful launch response confirms dispatch only; use the watcher to confirm a model response and simulator progress.

Run artifacts live under the deployment's `runs\runtime\opus-200-20261114`. The original Sol run is retained intact.

API requirements: https://platform.claude.com/docs/en/models/opus-5-5/migration-guide
Model pricing: https://platform.claude.com/docs/en/models/opus-5-5/overview
