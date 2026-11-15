# Real Sol / ChemSep five-call runtime smoke test

November 14, 2026. GPT-6.1 Sol, Responses API, low reasoning, 5 simulator calls,
no API spend cap, one persistent Python process beside ChemSep on the Azure VM.

- Completed: 5 model requests, 5 actual simulator calls, budget exhausted normally.
- Wall time: 31.765 seconds; model time 28.897 seconds; evaluation 1.876 seconds.
- Per-submission Azure transport: zero. Deployment, installation, Scheduled Task
  dispatch, and result retrieval are outside the run wall time.
- One solver nonconvergence, counted as a failed design evaluation; zero model errors.
- Input/output tokens: 8,265 / 969. Dollar estimate remains unknown in this ledger.
- Best normalized valid reward: 1.4038167718. This short run is infrastructure
  validation, not a matched performance comparison with the legacy pilots.

The earlier Luna pilot incurred approximately 32.2 seconds of Azure overhead per
submission (see ../pilot-transport-baseline.json). This test confirms removal of
that per-submission cost; it does not establish a matched end-to-end speedup ratio.

The initial attempt failed before any solves because Chat Completions rejected
Sol reasoning with function tools. The successful retry uses Responses. Both
attempts remain on the VM. Dependency installation also required a PowerShell
native-stderr handling fix; startup time is not included in the timing above.

Evidence: runtime.json is the retrieved VM runtime/status document. Full raw
artifacts remain under:
`C:\iterate-hackathon\azure-runtime-sol-fast-five-20261114\runs\runtime\sol-fast-five-r2-20261114`.
The deployed source is the merged runtime source plus agents/llm_agent.py from
commit 52b34cf (Responses client). This bundle does not contain all raw artifacts.
