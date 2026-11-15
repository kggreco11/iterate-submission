# Historical simulator readiness snapshot

This captures the initial qualification stage, not current experiment status. See the [master research report](../../docs/RESEARCH_NARRATIVE.md) and [runtime docs](../../docs/AZURE_RUNTIME.md) for later progress.

Checked 2026-11-14 through Azure CLI, Windows Run Command, and the interactive desktop.

- chemsep-01 is running; chemsepadmin is signed in.
- Started the existing ChemSepPilotWorker task; desktop reports worker ready, source hash af312cef9ed57075.
- Three live config-0 column checks passed: 20, 80, and 160 stages.
- Annualized costs matched recorded values exactly; largest outlet component-flow difference was 1.93e-15 mol/s.
- Component material balances and nonnegative outlet checks passed for all three cases.
- Full results are on the VM at `C:\iterate-hackathon\simulator-check\results.json`; local full-result retrieval is pending.
- Full 12-column replay completed: 12 successful fresh calls in 74.2 s; economics match the recorded reference. Two off-spec terminal streams remain. One column fails the initial strict component-balance tolerance; this is not an unconditional physics pass. See results/reference-20261114/README.md. No agent experiment has run.
- chemsep-llm-01 remains unused.

New check code is in this repository. The running simulator worker and its Python environment still come from the existing `C:\chemsep-benchmark` installation; they have not been migrated. No legacy experiment launcher was run.

The fixtures in reference_cases.json came from the earlier simulator parity-check setup. authors_design_reference.json is a recorded upstream reference fetched from the revise-loop branch, not a result of this project's execution. That upstream reference reports two forced off-spec streams and spec_success=false; acceptance targets must not assume it satisfies every product specification.
