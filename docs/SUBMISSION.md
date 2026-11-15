# Submission — iterate-hackathon

## Entry

- **Track:** AI scientist swarms. Organizers approved the chemical plant domain change (team confirmation, November 15).
- **Optional challenges:** not selected.
- **Repository:** the repository containing this submission
- **Video:** We are preparing the final two-minute video. Insert its YouTube, Drive, or Loom URL when ready.
- **Deadline:** Sunday, November 15, 14:30 PT.

## Short description

iterate-hackathon studies how AI scientist swarms search for better chemical separation plants. Agents propose designs, test them with ChemSep, and revise them from simulation feedback. On V3 dev002, our 50-agent island configurations reached reward 3.866 with Kimi and 2.160 with DeepSeek. Opus solo reached 5.331 using 74 simulator solves, compared with 2,496 for the Kimi team. Our experiments trace the tradeoffs between design quality, resources and diversity, with saved plant designs and logs behind every reported outcome. The [research report](../RESEARCH_REPORT.md) presents the final results and their limitations.

## Judging evidence

Each criterion carries 20%.

| Criterion | Evidence to show | Limit to state |
| --- | --- | --- |
| Research rigour | Single/swarm comparison, Past ablation, matched-query curves, separate organization screen | One run per condition; task and harness differences prevent pooling results |
| Novelty | Chemical plant search with explicit design sharing; relationship between sharing, diversity and quality | Position as an experimental contribution; novelty beyond existing literature has not been established |
| Results | Final dev002 endpoints: Kimi team 3.866, DeepSeek team 2.160, Opus solo 5.331; actual 3D plant playback | Unequal budgets and thinking settings; historical harness defects; playback is recorded evidence |
| Autonomy and self-improvement | Agents repeatedly propose, evaluate and revise designs using feedback | Humans define tasks, budgets, conditions and analysis; no demonstrated autonomous redesign of the research process |
| Interpretability and reproducibility | Saved designs, score traces, provenance, report builders and tests | Full real simulation requires Windows/ChemSep; failed and stopped runs remain explicitly labeled in the inventory |

Sources: [maintained analysis](../results/results-so-far/ANALYSIS.md), [V3 comparison](../results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/index.html), [run inventory](../results/results-so-far/inventory.html).

## Two-minute video

Use the [current demo content brief](DEMO_CONTENT_BRIEF.md), derived from the [research report](../RESEARCH_REPORT.md). The completed five-agent content follow-up is retained in the diagnostic appendix; its underperformance and unresolved cause are supporting findings, not the video headline.

## Three-minute pitch and live demo

- **0:00–0:30:** State the research question and explain the economic design objective.
- **0:30–1:30:** Open the 3D player; scrub through the saved evolution and inspect the final plants.
- **1:30–2:20:** Show final dev002 quality and resource use; explain earlier memory and diversity findings.
- **2:20–3:00:** Show traceability, state limitations, and describe the next controlled test.

Use the [3D visualizer setup](../demo/README.md) to prepare a saved-run demonstration. Validate the presentation machine before the pitch. A saved replay should be described as recorded evidence; fresh optimization requires the Windows/ChemSep runtime.

Round 1 permits 3 minutes of pitch plus 2 minutes of Q&A. Finals at 16:30 allow 3 minutes including the live demo, with no Q&A. Challenge winner demos are 2 minutes; awards are at 18:00.

## Remaining submission checks

- Upload the final MP4 and insert its YouTube, Drive, or Loom URL.
- Verify judges can access the repository and video.
- Select any optional challenges and submit the entry by 14:30.
- Rehearse the 3-minute pitch with the actual presentation machine.
