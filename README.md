# AI scientist swarms

Can a swarm discover a better chemical separation plant, and does shared memory help?

Agents design plants that separate a hydrocarbon feed into sellable products. They choose column settings, evaluate designs with ChemSep, and revise their designs using simulator feedback. We compare single agents, swarms, and memory conditions. The current V3 task uses 16 components and supports heat integration.

## [Research report](RESEARCH_REPORT.md)

Our experiments, results, and conclusions, with plots and links to the underlying measurements.

On V3 dev002, our 50-agent island teams reached reward **3.866 with Kimi** and **2.160 with DeepSeek**. **Opus solo reached 5.331** using 74 simulator solves; the Kimi team used 2,496. The report explains the resource tradeoffs and the limitations of these single-run comparisons.

[Read the research report](RESEARCH_REPORT.md) · [Final results dashboard](results/results-so-far/final-study.html) · [All runs and evidence](results/results-so-far/inventory.html)

## Explore the project

- [3D plant visualizer](demo/README.md) — saved plant designs; physical placement is illustrative.
- [Detailed experiment reports](results/README.md)

## Reproduce and inspect

The agent loop proposes, evaluates, and revises designs automatically. Humans set the task, budgets, experiment conditions, and analysis. Saved reports contain scores, design data, and provenance; live simulator runs require Windows and ChemSep. Local playback requires neither model calls nor ChemSep.

Run `python -m pytest` to check the repository tests. See [report instructions](docs/AUTOMATIC_REPORTS.md) for exporting experiments and [aggregate instructions](results/results-so-far/README.md) for refreshing the overview.

## Repository map

| Folder | Purpose |
| --- | --- |
| `sepdesign/`, `agents/` | Simulator environment and agent runners |
| `tasks/`, `configs/` | Benchmark tasks and experiment settings |
| `scripts/`, `tests/` | Run, export and validate experiments |
| `results/` | Published evidence; start with its README |
| `demo/` | 3D plant visualizer |
| `docs/` | Setup, methods and submission notes |

[Development and experiment guide](docs/GETTING_STARTED.md)
