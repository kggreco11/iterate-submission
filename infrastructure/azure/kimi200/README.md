# Kimi K3.1 Pro: 200-solve run

Uses a separate source-only copy of the completed Sol runtime on chemsep-01.
Same hc12_dev_000 task, prompt, environment, validation, serial solver, seed 0,
fresh empty plant/cache, and solver retries disabled. Budget: 200 distinct
column solves, at most 400 agent turns. These are not 200 model requests.

Kimi settings: Modal shared endpoint, provider-default reasoning, automatic tool
selection, 6,000 output tokens/request. Estimated spend cutoff: $20 (checked
between calls, so one call can overshoot). Estimate uses uncached rates of $2/M
input and $10/M output. Cached input is logged but not discounted in this
conservative estimate. Actual model reasoning and token usage may differ from Sol.

Live access verified: an authenticated Kimi request returned a valid ping tool call.
The credential was provisioned using an ephemeral VM RSA key; only encrypted
credential bytes traversed Azure Run Command. VM file access is restricted to
SYSTEM and administrators. Hackathon credit coverage remains unverified.

## Provision and launch

In the Modal workspace, create a shared endpoint for `moonshotai/Kimi-K3.1-Pro`.
Use its request example or Models API to obtain the exact model identifier.
Provision these machine variables on the Windows VM, or put them in
`C:\iterate-hackathon\secrets\kimi-200\modal.env` restricted to SYSTEM and administrators:

```
MODAL_PROXY_TOKEN=<combined proxy token ID.secret>
KIMI_ENDPOINT_URL=https://inference.us-west.modal.direct
KIMI_MODEL=<endpoint hostname returned by Modal>
```

Never paste credentials into chat or Azure Run Command scripts. The launcher
reads credentials only on the VM and does not print them.

From the repository root:

```bash
.venv/bin/python scripts/setup_kimi_200.py prepare
.venv/bin/python scripts/setup_kimi_200.py launch
.venv/bin/python scripts/watch_run.py runs/azure-control/kimi-200-20261114-controller.json --vm
```

Prepare refuses an existing destination; skip it after successful preparation.
Launch refuses existing run/task IDs. Dispatch is not proof of inference: verify
model response and simulator progress in the watcher. Remote results are under
`C:\iterate-hackathon\azure-runtime-kimi-200-20261114\runs\runtime\kimi-200-20261114`.
The Scheduled Task has a two-hour limit; a forced timeout may leave no final summary.

Sources checked 2026-11-14:
- https://modal.com/library/moonshot/kimi-k3-1-pro
- https://modal.com/docs/guide/endpoint-integrations
