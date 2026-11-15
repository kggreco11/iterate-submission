# Results so far — maintained aggregate

Open [the overview](index.html), [full analysis](analysis.html), or [searchable run inventory](inventory.html). The editable narrative is [ANALYSIS.md](ANALYSIS.md). Machine-readable exports are [runs.csv](runs.csv) and [runs.json](runs.json).

## Organization

- Experiment pages: HC12 pilots, V2, V3 first looks, V3 100-per-agent, V3 400-per-agent, dev_002 organization screen, adapter attempts.
- Four charts, exported as PNG and SVG: budget curves, screening quality/diversity, grade sensitivity, and model first looks.
- `evidence/`: content-addressed summary snapshots only. Original reports, trajectories, and prompts remain where they were.
- `provenance.json`: scanned commit IDs, source hashes, and duplicate run aliases.
- `coverage.json`: excluded/unrecognized schemas, conflicting counts, and document-only claims requiring evidence.
- `validation.json`: inventory and evidence checks.
- `current-campaign-snapshot.json`: saved progress, not a live feed; its capture time governs freshness.
- `monitor-state.json` (local, Git-ignored): automation bookkeeping, excluded from published evidence. Preserve an existing local copy when updating this checkout.

## Refresh

From the repository root:

```sh
git fetch origin
python3 scripts/analyze_corpus_campaign.py
python3 scripts/build_results_summary.py
PYTHONPATH=runs/v3-400-analysis/deps .venv/bin/python scripts/render_results_summary.py
```

The inventory builder uses Python's standard library. Rendering requires Matplotlib; the command above uses the plotting environment already present in this checkout. Neither command launches, stops, or polls experiments.

Add new standardized run summaries under `results/<task>/<condition>/<model>/<run-id>/summary.json`, or commit them to an origin branch and fetch it. The scanner reads available remote-branch result summaries plus local result summaries, and incorporates the reviewed historical CSV and audited campaign reports. Recognized single/swarm schemas enter the registry; inspect `coverage.json` for anything unrecognized. Ad hoc remote-only logs and summaries stored solely under ignored `runs/` are not automatically harvested. Promote their evidence or add an explicit adapter first.

After rebuilding, check new run statuses, task/model/config identity, budgets, unknown costs, and duplicate conflicts. Review the narrative and chart labels against the new evidence; prose is deliberately not automatically rewritten. Historical rows remain the reviewed baseline, so changed versions of an existing run need explicit reconciliation rather than silently replacing the prior record. The current-campaign adapter is specific to the saved Kimi campaign snapshot and should be updated when its completed summaries arrive.

Do not rerun the old historical inventory builder as an update mechanism: it contains assertions and assumptions tied to its original 20-run snapshot. This master builder reads that preserved historical inventory without modifying it.

## Interpretation

Separate completed, stopped, and failed/partial results. Do not treat an error as a zero-quality design if a valid partial plant exists. Unknown cost is not zero; recorded spend excludes VM and memory and may omit failed request costs. The known-dollar totals are lower-bound recorded estimates, not an invoice.

Compare within task, budget convention, retry policy, and harness version. A 400-per-agent five-agent swarm has 2,000 total allocated charged queries. Agent members are not repeats. Charged queries, backend calls, and cache hits are distinct counters. No statistical confidence interval is justified by one run per condition.

## Existing deep dives

- [V3 comparison](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/index.html)
- [Behavior audit](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/behavior.html)
- [Independent control](../hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/independent.html)
- [Historical narrative](../experimental-history-20261115/README.md)
- [Simulator / robot / polish inventory](../experimental-history-20261115/simulator-reference-inventory.csv)

The master corrects the earlier behavior report’s common-budget label: shared no-Past reward is 2.1029 at 395 queries; 2.1971 is the 400-query checkpoint. The archived report is retained as evidence of the earlier analysis.

New corpus baseline: [analysis](corpus-baseline.html), [evidence](corpus-campaign.json). Retrieved conditions are analyzed offline by `scripts/analyze_corpus_campaign.py` before rebuilding the master.


## Completed corpus campaign

[Diagnostic comparison](corpus-comparison.html) covers completed solo/immediate sharing and the cancelled delayed conditions. The report deliberately separates a verified admission-selection limitation from an unproven causal explanation. Portable prompt-admission rows and hashed source/config/task snapshots are in `corpus-evidence/`; `corpus-partial.json` retains the stopped delay25 lower-bound accounting without inventing a final summary.

Run `python3 scripts/render_corpus_comparison.py` with Matplotlib installed to regenerate the diagnostic from committed compact evidence. `scripts/analyze_corpus_campaign.py` requires the original retrieved raw archives; it exits without overwriting results if those are absent. Current historical registry refs should be pinned when rebuilding for review, so unrelated branch updates are not silently promoted.
