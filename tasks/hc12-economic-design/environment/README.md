# Execution environment

This task adopts Harbor's task/instruction/environment/tests organization. It is currently run by the repository's adapter, not the Harbor CLI: the existing licensed Windows ChemSep console installation is accessed through Azure Run Command. No Docker image or Harbor environment plugin is claimed.

- Agent: local Python, OpenAI Responses API; key stays local.
- Simulator: existing Windows Azure VM; Python/numpy, ChemSep console executable.
- Source: this repository's sepdesign package, deployed as a source snapshot.
- Task data: ../hc12_dev_000.json relative to this task directory.
- Isolation: unique per-run state/cache/results; no earlier solutions supplied to agent.
- Verifier: trusted harness validates simulator outputs and writes logs/verifier/reward.json.
- Agent only emits JSON edits, with no access to verifier code or reward files.

Azure command delivery adds substantial latency. Record it separately; this transport is a pilot mechanism, not a fair swarm speed benchmark. Past.dev integration is not included in this initial single-agent plumbing pilot; the agent retains its own transcript.

`tests/test.sh` replays the recorded best design through the independent validator,
using the harness-owned simulator cache and refusing any missing evidence. It
writes reward.json and validation.json. This checks recorded evidence; it does
not perform an additional fresh simulator replay or verify energy closure.

Pilot limits: 50 distinct evaluations, no automatic solver retries, 60 model
requests, 2,500 maximum output tokens per request, one-hour loop deadline.
Dollar spend is unknown until a verified price is supplied; token and request
limits are the current spending safeguards. A request or Azure evaluation in
flight may finish after the loop deadline. API failures stop the pilot and are
saved; there are no automatic model retries.
