# Harbor task layout and the pilot adapter

Task package: `tasks/hc12-economic-design/` contains `task.toml`,
`instruction.md`, `environment/`, and `tests/test.sh`. This follows
[Harbor's task organization](https://github.com/harbor-framework/docs/blob/main/guides/creating-tasks.mdx).
It is not yet a standalone Harbor CLI task: the Windows ChemSep environment
uses the repository's Azure adapter rather than a Harbor environment backend.

## Runners

- `agents/llm_agent.py` and `scripts/run_llm_agent.py`: the project’s general runner,
  now merged into this branch. Use it for environments with direct simulator access.
- `agents/luna_pilot.py` and `scripts/pilot_remote.py`: local Responses API and
  Azure simulator transport for the current pilot. Reuses the general runner's
  dotenv loader and usage ledger. No API key is sent to the VM.
- `sepdesign/ledger.py`: shared usage event format. An unknown model price is not
  evidence of zero spending; check `requests_with_unknown_cost`.

The active pilot launched before this integration and retains its original
source snapshot and event schema. It uses five displayed components per stream,
full conversation history, low reasoning effort, and no solver retries.
the project’s general runner uses six displayed components and recent-turn history.
Do not pool these as identical experimental conditions. Choose one protocol
before running the 1/3/5-agent comparison.

## Artifacts and verification

Each pilot lives under ignored `runs/<run-id>/`: configuration, request/response
records, usage, trajectory, and summary. Simulator-side state and raw calls are
under the same run ID on the VM. Export selected evidence to `results/` for Git.
The task verifier recomputes best-design reward from trusted recorded simulator
outputs; it is not a fresh physical solve. Full validation remains provisional,
particularly energy closure and economic calibration.

## Branch policy

Agent work stays on a dedicated `codex/` branch. Fetch and merge collaborators'
latest main into that branch, run checks, then push that branch. Do not push to
main without a new explicit request. Preserve unrelated local edits.
