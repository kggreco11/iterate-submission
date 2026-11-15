# Azure simulator operations

All hackathon orchestration, scripts, and results belong in this iterate-hackathon repository. The existing simulator installation is an external service; do not launch legacy experiment jobs.

For current runs, start with [persistent runtime](../../docs/AZURE_RUNTIME.md), [V2 Kimi protocol](../../docs/V2_KIMI_COMPARISON.md), and [shared-memory orchestration](../../docs/SWARM.md). This directory preserves qualification scripts and earlier standalone Kimi/Opus deployment helpers; they are not the active V2 launcher.

## Existing VM

- Resource group: set `AZURE_RESOURCE_GROUP` to your deployment’s resource group.
- Simulator VM: `chemsep-01` (Windows, Standard_D2as_v4)
- Worker endpoint inside VM: `http://127.0.0.1:5701`
- Existing worker task: `ChemSepPilotWorker`
- Existing installation: `C:\chemsep-benchmark\code`
- `chemsep-llm-01` is not required for the initial simulator check and remains stopped.

## Inspect

```sh
az vm get-instance-view -g "$AZURE_RESOURCE_GROUP" -n chemsep-01 --query 'instanceView.statuses[].displayStatus'
az vm run-command invoke -g "$AZURE_RESOURCE_GROUP" -n chemsep-01 --command-id RunPowerShellScript --scripts @infrastructure/azure/inspect_worker.ps1 --query 'value[].message'
```

Azure Run Command executes in a noninteractive session. Use it for inspection and control; ChemSep itself requires an interactive signed-in Windows session. Do not change login security or expose the localhost worker publicly to bypass this requirement.

## Cost control

VM started with user authorization on 2026-11-14. Running status is not worker readiness. Deallocate when finished:

```sh
az vm deallocate -g "$AZURE_RESOURCE_GROUP" -n chemsep-01
```

Do not record passwords, SAS URLs, or API secrets in scripts or results.

## Full reference replay

`replay_reference.py` runs the 12 upstream actions through the localhost worker and uses the installed upstream `Replayer` for matching queue/economics accounting. It does not instantiate COM or launch old experiments. The exact accounting-module hashes and worker identity are captured with results. `reference_provenance.json` identifies the recorded reference fixture.

`run_full_reference.ps1` deploys this repo's runner and fixture to `C:\iterate-hackathon\reference-replay`. The current run writes `reference-20261114.json` and its raw `.calls.jsonl` trace there. Use a fresh output name for another run; overwriting a trace is refused.

```sh
az vm run-command invoke -g "$AZURE_RESOURCE_GROUP" -n chemsep-01 --command-id RunPowerShellScript --scripts @infrastructure/azure/run_full_reference.ps1 -o json
```

The runner prints a gzip/base64 report for retrieval through Azure Run Command. This is a transport encoding, not a secret. The worker remains localhost-only. No LLM/API calls are part of reference replay.

Set `CHEMSEP_REFERENCE_SOURCE` on the Windows host to the installed reference source directory before running `run_full_reference.ps1`.
