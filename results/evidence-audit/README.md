# Evidence audit

The audit found **two missing inventory values and inconsistent numeric types**, now corrected. It found no malformed JSON, failing source hashes, inconsistent available endpoint rewards, or credential-pattern matches in the audited snapshot. It also exposes material evidence gaps: published summaries are not a substitute for missing raw traces.

This is the supporting audit for the [master research report](../../RESEARCH_REPORT.md), not another results narrative.

## Exact scope

Audited source: main at `9735141383c988ac5650642233dc1fded50fa57c`, after the submission-document cleanup. The [machine-readable manifest](manifest.json) lists every file, SHA-256, line count, record schema, applied checks and finding location.

| Coverage | Count / treatment |
|---|---|
| Tracked files | 1,129, each hashed |
| UTF-8 text | 1,092 files; 747,263 physical lines scanned for specific credential formats |
| JSONL | All 318 files; all 19,411 nonblank records parsed and recursively visited |
| JSON | All 434 files parsed; nested traces, turns, usage, events and curves traversed |
| CSV | All 29 files checked for row width; 3,586 recognized numeric fields parsed |
| Explicit transport payload | One gzip/base64 report decoded and recursively checked |
| Structured records including embedded exports | 36,147 occurrences; duplicates are not independent experiments |
| Aggregate comparisons | 373 applicable comparisons of available query, reward, usage or inventory values; 15 further comparisons unavailable because values are absent |
| Published source hashes | All 241 locally resolvable manifest entries match |
| Binary files | 37 hashed only; images/PDFs are not semantically audited |

The checks detect malformed/truncated JSON, duplicate keys, nonfinite values, invalid counter types, missing schema fields, changed identities within usage streams, cumulative request/cost discrepancies, decreasing counters, summary/record disagreements, missing sources and checkpoints beyond the observed budget. Null-cost requests remain unknown, not free. Canonical team identities are checked against the inventory.

**This is exhaustive automated coverage of the saved files, not a claim that a person independently interpreted every sentence or validated every scientific decision.** Text-only checks are credential-pattern scans. Prompts, notes and HTML/JavaScript are not executed; their scientific meaning is not mechanically established. There are no tracked `.log` files in this snapshot; saved logs principally use JSONL. Ignored live runs, remote VMs, Git history, billing-provider records and unpublished source files are outside scope. ChemSep was not rerun.

## Corrections made

- The completed capped DeepSeek solo on dev002 had a **200-query allocation** and **$0.80798472 cached-price model-cost estimate** in its canonical export, but both were missing from the inventory. Its result remains **zero reward at 184 consumed queries**. This does not change the research conclusion.
- The inventory builder now lets a canonical team export supply its full configuration and summary, instead of retaining incomplete metadata from the first generic snapshot encountered. Costs are explicitly estimates, not billed totals.
- Ninety-six historical CSV-derived request/token fields were strings or empty strings in the JSON inventory. The builder now emits numeric values or null.
- A generic status named `stop` no longer counts as successful completion without a more specific completion status.
- `--refs-from` permits a refresh from the immutable commits recorded in existing provenance. This audit does not silently import a newly advanced branch.

Experiment measurements are unchanged. Identifying text and paths were removed for publication, including in historical records; hashes in file manifests were updated for those published copies. The older checks described here refer to the recorded development revision.

## Evidence gaps and historical findings

- **Seventeen of the eighteen canonical team snapshots lack plant-submission records.** Their events and usage can be inspected, but full plant evolution cannot be reconstructed. Only the capped DeepSeek solo has published board/turn records in this group.
- Some extracted V3 reports retain raw trajectory, simulator or usage hashes without publishing blobs matching those hashes. We can check the available exported curves and saved reconciliation arithmetic; we cannot independently recompute those exports from absent raw streams. The manifest identifies each reference.
- Many team-agent usage files lack adjacent agent summaries. Their available per-request sequences are checked, but an absent endpoint cannot be reconciled. Unknown request costs and missing provider request IDs are recorded as coverage limitations. Counts include repeated raw/embedded exports.
- **Fifteen historical checkpoint fields across eleven files exceed the observed query count.** These are carried-forward endpoint values, not observations at those budgets. Keep these source snapshots intact; use the corrected current narrative and observed checkpoints.
- **Twelve repeated request-ID occurrences belong to scripted qualification records.** They are not evidence of duplicate provider billing or a failure of the scientific runs.
- A [separate whole-tree Markdown/HTML navigation check](legacy-links.json) during cleanup found **23 pre-existing unresolved local targets**, principally links inside frozen historical snapshots or links to omitted historical files. The audit does not rewrite those hashed source documents. The earlier 290-link validation covered selected active report pages, not every historical page.
- There are 857 nonempty `error`/`errors` fields across JSON occurrences. This is a structural count, not 857 distinct failed experiments: copies, nested payloads and provider errors can repeat. Failed/incomplete runs remain separate from completed comparisons.

These gaps prevent certifying every claimed inference from raw data. They do not overturn the available completed dev000 endpoint comparison or justify treating provisional organization results as completed experiments.

## Reproduce

From the repository root, with Python 3 and Git; no model or simulator calls:

```bash
python3 scripts/audit_evidence.py --revision 9735141383c988ac5650642233dc1fded50fa57c --output /tmp/evidence-audit.json
python3 scripts/build_results_summary.py --refs-from results/results-so-far/provenance.json
python3 -m pytest tests/test_evidence_audit.py -q
```

The committed manifest describes the **pre-correction main snapshot**, so its two missing inventory values and 96 numeric-type warnings remain visible as the before evidence. Rerunning against the correction commit verifies their resolution. The script exits nonzero for structural/hash errors; warnings and missing-source coverage remain in the manifest and must be read.

During this audit, `origin/feature/swarm-runner` advanced to `9d2e0082495c31305d9893176f50b95da8eda07d` with newer final-results claims. Those changes are **outside this main-snapshot audit** and have not been promoted into the narrative or inventory here. They need their own reconciliation before use in the demo.
