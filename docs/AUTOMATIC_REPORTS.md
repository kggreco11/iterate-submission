# Report generation and sync

## One home for reports

Open [results/index.html](../results/index.html) locally, or browse [results/README.md](../results/README.md) on GitHub.

```text
results/<task>/<condition>/<model>/<run-id>/
  index.html          self-contained report
  report-data.json    portable inputs to regenerate modern reports
  summary.json        measured outcomes and stop reason
  manifest.json       identity, evidence limits and SHA-256 hashes
  agents/             individual replays for a swarm, when applicable
```

`results/` is tracked in Git. `runs/` is ignored and contains active logs, credentials-adjacent controller files, download chunks and recovery caches. Do not commit all of `runs/`. Legacy pilot bundles retain their existing self-contained HTML and summary when a modern report-data payload does not exist; the manifest says so.

## Where HTML is generated

The simulator and model loop run on the Windows VM. A completion report there is a backup, not the local deliverable. The local sync command downloads saved JSON, checks its transport SHA-256, renders HTML **on this machine**, writes a bundle under `results/`, and regenerates both indexes. Export does not run models, consume simulator calls, overwrite simulator source, or require HTML generation on the VM.

## Commands

Refresh reports already downloaded or saved in this checkout:

```sh
.venv/bin/python scripts/sync_reports.py
```

Download and render a completed single-agent run:

```sh
.venv/bin/python scripts/sync_reports.py --controller runs/azure-control/v2-kimi-20261114-r3-single-controller.json
```

Download the completed swarm and render its overview and all agent reports:

```sh
.venv/bin/python scripts/sync_reports.py --swarm-controller runs/azure-control/v2-kimi-20261114-r3-controller.json
```

The swarm export requires a terminal pair status and one swarm in the isolated deployment. An unfinished run is not a completed report. A saved payload can be rendered using `--data path/to/report-data.json` without contacting Azure.

Azure Run Command has one control slot and small response limits. Downloads are chunked and resumable; competing watchers can delay them. Repeating the command after a completed export rebuilds locally from cached data. A hash failure prevents publication. Controller commands run on the local macOS/Linux machine and require Azure CLI authentication; the local download lock uses POSIX file locking.

## Automatic versus explicit steps

- New terminal single-agent runs built beneath this checkout's `runs/` publish a canonical results bundle through the report builder. New swarms publish a team bundle with agent replays; the legacy organizer publishes completed pilot snapshots.
- The current `watch_run.py --vm` calls the finalizer on completion and now returns the canonical `results/` path. A watcher running an older worktree's code must be restarted with this checkout to use the updated exporter.
- A remote process cannot write into your Mac checkout by itself. Keep a local watcher running or run the sync command. Existing remote deployments are not changed by editing this checkout.
- Report generation does not automatically commit or push. Review the generated bundle, then sync it deliberately:

```sh
git add results/
git commit -m "Publish completed experiment reports"
git push
```

The current branch is the push destination; use the repository's PR workflow to merge into main. GitHub displays HTML source rather than running it. Clone/download and open `results/index.html` locally; static hosting is a separate setup.

## Evidence rules

Keep failed runs labeled, retain the run identity, and never sum independent agent plant objectives. Publishing report data is not proof that every raw simulator trace was exported. Do not include API keys, controller payloads, credential files or full raw request logs in report bundles. Missing model/VM/memory cost remains unknown. Historical qualification evidence stays in its existing results directories and is not mixed into the agent-report index.

## Compare completed single-agent and swarm runs

The swarm landing page includes each agent's replay, the best team objective, query accounting and model cost. To add an explicit single-agent comparator, use saved payloads:

```sh
.venv/bin/python scripts/compare_reports.py \
  --single results/<task>/single-agent/<model>/<single-run>/report-data.json \
  --swarm results/<task>/shared-memory-5/<model>/<swarm-run>/report-data.json
```

This regenerates the swarm HTML locally and records the comparator's identity and payload hash. Refreshing the same swarm preserves that comparison. Task, model and reward normalization must match. Compare the best agent design, not the sum of objectives; always show allocated and consumed budgets, elapsed time and estimated model cost. Unequal-budget, single-repetition outcomes cannot establish a general architecture or memory advantage. Memory and VM charges are excluded when unavailable. Commit the complete changed bundle, including its manifest and source data.

## Team runner v2

`python scripts/sync_reports.py` also discovers `runs/teams/<campaign>/<model>/<preset>/config.json` and publishes portable team evidence under `results/<task>/team-<preset>/<model>/<run-id>/`. Each bundle includes HTML, queryable source JSON, a summary, and hashes. Incomplete snapshots and missing historical plant records are labeled explicitly; these reports display saved plant views rather than inventing simulator trajectories. Regenerate from committed source JSON without the VM. Run `python scripts/collect_results.py` afterward to refresh the combined CSV/JSON and saved designs.

`python scripts/summarize_teams.py <campaign> ... --out <snapshot-directory>` publishes the same bundles and exports raw snapshots under `<snapshot-directory>/<model>/<run-id>/`, so presets shared across models cannot overwrite each other. The team runner saves board records as evaluations complete and checkpoints turns and curves each round. Reusing a run destination is rejected.
