# Repository structure audit

## Decision

Use one research entry point: root README → RESEARCH_REPORT.md → linked study reports and source evidence. The former results/INDEX.md is now explicitly a historical benchmark catalogue, and results/index.html links to the maintained HTML instead of carrying a second stale run table. No new project name is introduced.

## What looks redundant

| Area | Why it exists | Action |
| --- | --- | --- |
| `results/results-so-far/` | Cross-study findings and model-run registry | Maintained reader entry point |
| `results/<task>/<condition>/<model>/<run>/` | Individual reports and saved source data | Keep canonical run evidence |
| `results/*-first-look/` | Earlier source exports, including logs and polish | Treat as historical; do not add new runs here |
| `results/experimental-history-20261115/` | Reviewed historical inventory and source snapshots | Keep frozen evidence and inventories; superseded presentation drafts removed |
| `results/all_results.*` and `results/data/` | Benchmark rows including robots, repricing and polish | Keep as benchmark catalogue; not interchangeable with model-run registry |
| `results/*qualification*`, `*reference*`, `*side-draw*`, `*multi-effect*` | Simulator qualification and feature validation | Keep separate from model findings |
| `demo/` and local `sites/` | Visualizer and unfinished presentation work | Video production is in progress |

## Exact-copy audit

Found 61 groups of byte-identical files across results; removing extra copies would save approximately 0.35 MiB. Equal content alone is not proof a path can be deleted: source snapshots have provenance roles and reports have inbound links.

Examples:

- `results/hc16v3-side-draw/qualification.json`; `results/experimental-history-20261115/evidence/side-draw-qualification.json`; `results/experimental-history-20261115/evidence/source-snapshot/results/hc16v3-side-draw/qualification.json`
- `results/all_results.csv`; `results/experimental-history-20261115/evidence/historical-reference-inventory.csv`; `results/experimental-history-20261115/evidence/source-snapshot/results/all_results.csv`
- `results/hc16v3-first-look/polish_v2plants_at_v3.json`; `results/experimental-history-20261115/evidence/v2-plants-at-v3-polish.json`; `results/experimental-history-20261115/evidence/source-snapshot/results/hc16v3-first-look/polish_v2plants_at_v3.json`
- `results/hc16v3-first-look/polish_check.json`; `results/experimental-history-20261115/evidence/v3-polish.json`; `results/experimental-history-20261115/evidence/source-snapshot/results/hc16v3-first-look/polish_check.json`
- `results/hc16v2_dev_000/shared-memory-5/kimi-k3.1-pro/swarm-a1b45716fe3444679f33125db48b89b7/summary.json`; `results/experimental-history-20261115/evidence/swarm-a1b45716fe3444679f33125db48b89b7-summary.json`; `results/results-so-far/evidence/7043dc0af29aeb62ef3d.json`
- `results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/summary.json`; `results/results-so-far/evidence/f7755b94243ab4514ecc.json`
- `results/results-so-far/evidence/fc696f815985f5f30ecf.json`; `results/results-so-far/final-study-evidence/summary.json`
- `results/experimental-history-20261115/evidence/historical-evaluation.md`; `results/experimental-history-20261115/evidence/source-snapshot/docs/EVALUATION_2026-11-14.md`

## Remaining structural cleanup

Physical archive moves should be a separate migration that updates report links, renderer paths, source manifests and external citations together. Stale planning notes, event materials, consolidation status and superseded presentation drafts have been removed; Git history retains them. The current demo brief and submission checklist remain while production and submission are underway. Monitor bookkeeping is local and ignored; it is not research evidence. New reports should follow the canonical task/condition/model/run layout; use the maintained overview for cross-study comparisons.
