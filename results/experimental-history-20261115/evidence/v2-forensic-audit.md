# past.dev swarm forensic audit

Audit of the completed Kimi V2 r3 comparison, performed November 14, 2026 (Pacific). This investigation used saved evidence, offline reproductions, and the original VM trajectory. It did not launch model or simulator experiments or change production code.

## Finding

The completed run is not a clean test of whether useful shared memory improves search. There are confirmed differences in context construction, excessive prompt size, historical spend limits, and weak retrieval coverage. A lower swarm score alone is not a software bug or proof that memory has no value. The individual mechanisms below must be tested separately before attributing the result.

## Observed outcome

Task: `hc16v2_dev_000`. Single: `v2-kimi-20261114-r3-single`. Swarm: `swarm-a1b45716fe3444679f33125db48b89b7`.

| Metric | Single | Five-agent swarm |
| --- | ---: | ---: |
| Best valid reward | 3.4219250194 | 3.3565963752 |
| Annual net objective | $2.841048495B | $2.786809479B |
| Charged simulator queries | 200 | 454 |
| Configured allowance | 200 | 100 each, 500 total |
| Model requests | 51 | 156 |
| Input tokens | 317,389 | 8,773,113 |
| Mean input tokens per request | 6,223 | 56,238 |
| Maximum input tokens per request | 9,195 | 73,253 |
| Output tokens | 62,487 | 218,085 |
| Estimated model cost | $1.259648 | $19.727076 |
| Wall time | 559.28 seconds | 3,285 seconds |
| Failed model requests | 0 | 0 |

The swarm objective was 1.909% lower. Its input volume was 27.64 times larger, estimated model cost 15.66 times larger, and wall time 5.87 times longer. Model costs exclude past.dev and compute costs and use the historical recorded price estimate.

At the last swarm submission at or below 200 aggregate charged queries, the team had used 199 and reached reward 3.0102739129. This chronological checkpoint is not an independently planned 200-query experiment. At the single's 99-query checkpoint, its reward was 2.9311210165; the strongest 100-query swarm agent exceeded that midpoint. Splitting search into five 100-query paths also limits each path's depth relative to a 200-query single.

## Ranked findings

### 1. Swarm context drops direct history and rejected-edit feedback

`sepdesign/swarm.py:88` calls `_state_text(..., [], None, 0)`. `agents/llm_agent.py:194` passes maintained history, the latest error, and the actual best turn. Kimi sends one system message and one fresh user message per request; there is no provider conversation retaining omitted state.

The offline reproduction uses the real `run_swarm` and `run_agent` callers: submit a note, attempt an invalid edit, then inspect the next prompt. With empty retrieval to isolate the direct feedback path, the single receives its earlier note, the rejection banner, the actual error, and recent turns. The swarm receives none. Its header also labels every best result as occurring at turn zero. In the actual run, past.dev could sometimes return this information indirectly, but there is no guaranteed local feedback channel.

Four real submissions failed provenance validation. Agent 2 repeated that failure in rounds 5 and 6. A fifth rejected submission attempted a child column without its parent. These outcomes are consistent with a poor repair loop; they do not establish how much score the missing feedback cost.

### 2. Recall's 8,000-token budget does not bound the model prompt

`sepdesign/swarm.py:89–92` includes the entire recall response, citation mappings, and then complete simulator records for every retrieved source. Those records contain measured nodes, component arrays, outlets, settings, costs, and provenance. The harness does not allocate a total prompt budget or trim these sections.

The first swarm requests used 1,948 input tokens. After the first retrieval, requests jumped to 44,031–45,157 tokens; the peak was 73,253. Swarm mean input was about nine times the single's mean input.

past.dev documents that `maxTokens` counts content and excerpts, excluding JSON structure and metadata; whole documents that do not fit are omitted. Appending complete source records is outside that service budget. Thus `maxTokens=8000` is not an 8,000-token limit on what Kimi receives. See the [past.dev recall contract](https://past.dev/docs/memory-api/api-reference).

### 3. Retrieval occurred, but coverage of the experimental record was poor

The original VM trajectory confirms 156 publications and 156 nonempty accepted retrievals. However, the union of retrieved source versions contains only 16 of the 156 published experiments. All 16 source IDs match actual submitted version IDs, so there is no observed source/version-ID mismatch.

**The team's winning design, found by agent 3 in round 24, was never retrieved by any agent.** After round 4, the current team incumbent was absent from every retrieval: it was present in the first 20 reads and missing in all remaining 136. The only source versions from after round 4 that ever appeared were agent 2's rejected round-5 submission and agent 4's rejected round-20 submission. Thus no later successfully evaluated experiment entered the retrieved source set.

At round 30, agent 0's first three returned documents were raw source JSON from agent 2 round 1 (reward -0.1022), agent 0 round 2, and agent 4 round 2 (reward -0.2189). The response still emphasized early experiments while omitting the winning round-24 design. Its serialized memory section was 49,641 characters, followed by another 53,680 characters of complete source records, before the agent's current-state text.

Published records ranged from 1,466 to 59,058 characters, with median 31,466.5. **75 of 156 records exceeded 32,000 characters. The winning record contained 54,406 characters**, about 13,602 tokens under the service's documented estimate of four characters per token. Consequently, that raw source document cannot fit the configured 8,000-token recall budget. The API omits whole documents that do not fit. Smaller derived memories could still have carried its conclusions, but none of the accepted retrieved documents attributed evidence to that source. This confirms an incompatible raw-source size and recall budget; ranking and memory extraction remain additional possible causes of the missing derived evidence.

The adapter asks the same generic run-wide query for every agent and every round. It does not include the agent's current design, proposed question, failed column, desired tradeoff, or best-so-far objective. It offers no guaranteed channel for the latest results or team incumbent. Since copying is permitted only from the current retrieval, omitted designs are also unavailable as exact cloning targets.

This is a confirmed retrieval-coverage failure. Whether the service omitted particular sources because of ranking, document size, extraction, or the evidence budget requires source-specific inspection; a successful HTTP response and a nonempty result do not establish useful recall.

### 4. Historical spend limits stopped three agents early

Agents 0, 2, and 4 stopped at 94, 83, and 77 charged queries, leaving 46 calls unused. Their stop notes were `spend threshold or unknown usage`; all usage costs were known. The archived run used $4 per swarm agent, while the single had $20 and reached its simulator cap first. Later launcher changes do not alter this historical run.

The large prompts therefore have an observed resource consequence: they consume the spend allowance while comparatively few simulator experiments are made. The exact lost score cannot be inferred without another run.

### 5. The orchestration encourages early shared ancestry without assigning exploration

All agents receive the same initial design task and prompt; the harness assigns no distinct hypotheses, search regions, or experiments. There is no coordinator or experiment reservation mechanism.

There were 14 explicit source-design selections, 13 from another agent. All occurred in rounds 2–5. Four agents copied agent 2's round-2 design in round 3, and four selected agent 0's round-3 design in each of rounds 4 and 5. All five final best designs differ, but their root, `B`, and `BB` settings agree.

This supports early convergence on a common design family. It does not prove that all later exploration was duplicated, and 128 cited submissions do not by themselves prove useful transfer of new evidence.

### 6. Synchronous memory processing dominates runtime

Recorded publication, barrier, and recall time totals 2,398.272 seconds, 73.0% of the 3,285-second run. Ingestion barriers account for 2,305.2 seconds. The run made 1,591 past.dev HTTP requests, all recorded successful, including 1,122 processing-status polls and 156 completed-status polls.

Each round waits for every publication to finish ingestion before recalling and proceeding. This explains much of the elapsed-time penalty. There was no wall-clock stop in this comparison, so waiting alone does not establish why the final objective was lower.

### 7. Rejected submissions recirculate invalid citation IDs

The full trajectory permits checking invalid IDs against the actual prior retrieval and the complete-record section. In agent 2's first provenance rejection, round 5, one cited ID was absent from its prompt and had never been returned to that agent. The harness then published the rejected submission, including that unsupported ID in `evidence_ids`.

In the next three provenance rejections (agent 2 round 6; agent 4 rounds 11 and 20), the same unsupported ID was present inside retrieved content and the appended source records, while remaining absent from the allowed citation mapping. Agents were therefore exposed to an ID they could see but could not validly cite. The first unsupported citation was a model mistake; the subsequent recirculation is a workflow defect. Retaining rejected attempts for audit is useful, but invalid nested citation IDs should not re-enter the decision prompt as apparent evidence. Missing direct rejection feedback compounds this problem.

## Suspicions checked and limits

| Potential error | Result |
| --- | --- |
| Memory never published or read | Contradicted: 156 writes and 156 nonempty accepted reads. |
| Wrong source IDs prevent cloning | No observed source/version mismatch. Four provenance mistakes occurred; three reused an unsupported ID echoed inside previously rejected records. |
| Cross-run contamination | UUID audiences, reader identities, and all-source filtering are implemented; historical isolation probe exists. Full rejected raw recall results were not retained, so the cost of filtering cannot be reconstructed. |
| Hard model/context overflow | No failed requests or recorded overflow in this completed run. Exact prompts and server truncation policy were not archived, so silent provider truncation cannot be ruled out. |
| Output-token exhaustion | No positive evidence here: maximum output 3,624 versus configured allowance 16,384; zero failed requests. Earlier r2 output-limit failures are a different run. |
| Lost reasoning/context between calls | Confirmed omission in swarm caller; reproduced offline. |
| Irrelevant or stale retrieval | Winning source never retrieved; no later successfully evaluated source after round 4 appeared. Its raw size exceeds the evidence budget. Derived-memory selection remains unresolved. |
| Score accidentally summed across plants | Team report uses maximum valid agent reward. Objective conversion agrees with saved normalization. |
| Last bad design overwrote the best | Contradicted by saved best-of-run evidence. Agent 3 ends below its own best, but its earlier best remains the team score. |
| Budget cap prevents free cleanup | Reproduced in both harnesses: removing an unsolved child can validate a solved prefix without another solve. The two swarm agents reaching 100 ended on valid submissions, so this is not supported as their terminal failure here. |
| Simulator/caching orchestration | Shared simulator calls are serialized; cache results are copied and per-agent first-use charging is explicit. Relevant existing tests pass. A physical simulator requalification was outside this audit. |
| Controlled statistical comparison | Absent: one task and one run per condition, different harnesses and individual search depth, plus historical spend limits. |

## Changes warranted before another paid comparison

1. Restore each agent's local recent history, last rejection/error, and true best turn independently of external retrieval.
2. Guarantee a compact exact packet containing the team's incumbent, recent experiments, relevant failures, settings, objectives, and provenance. Keep large raw simulator arrays in the audit store. Retrieval should add task-specific evidence to that packet. Quarantine unsupported IDs in rejected attempts so they cannot be recirculated as citable evidence.
3. Allocate the complete prompt budget across state, history, memory, and exact candidate designs. Record section sizes, token estimates, source IDs, prompt hashes, recall budget usage, filtering counts, and source freshness. Preserve enough sanitized input to reproduce what each agent saw.
4. Make retrieval queries depend on the current search question. Test whether a just-published improvement and a known failure are actually retrievable; test exact copying of the retrieved design. Investigate large-source omission before raising recall limits.
5. Give agents distinct experiments or hypotheses and record duplicate-query avoidance. Early copying should not erase all exploration diversity.
6. Compare one agent and five agents through the same harness and feedback path. Separate independent five-agent search, exact shared evidence, and past.dev retrieval as ablations. Specify equal total solve budgets and a separate equal-per-agent scaling comparison. Avoid unintended dollar stops; report cost and time separately.
7. Use repeated tasks/runs before claiming a general memory benefit or lack of benefit. No paid campaign was launched during this audit.

## Reproduction and evidence

From the repository root:

```sh
python runs/memory-audit/reproduce_context.py
python -m pytest -q tests/test_swarm.py tests/test_kimi_adapter.py tests/test_llm_runner.py tests/test_env.py
```

The reproduction asserts the context difference, incorrect best-turn label, and free-cleanup edge. The selected existing suite passed: **38 tests in 0.64 seconds**. Passing these existing tests does not refute the newly reproduced context omission.

- [Derived run statistics and trajectory anchors](../runs/memory-audit/run-evidence.json)
- [Original VM inventory and source hashes](../runs/memory-audit/vm-inventory.json)
- [VM-derived memory coverage, freshness, and examples](../runs/memory-audit/report-data.json)
- [Raw-source size and invalid-citation probes](../runs/memory-audit/source-probe.json)
- [Offline real-caller reproduction](../runs/memory-audit/reproduce_context.py)
- [Single report](../results/hc16v2_dev_000/single-agent/kimi-k3.1-pro/v2-kimi-20261114-r3-single/index.html)
- [Swarm dashboard and agent replays](../results/hc16v2_dev_000/shared-memory-5/kimi-k3.1-pro/swarm-a1b45716fe3444679f33125db48b89b7/index.html)

The original VM trajectory SHA-256 is `e9f8865a4b8b7fdfa64248cb7438a30d63fcf40677902c0acb806f8651c947c7`. The deployed `swarm.py`, `swarm_memory.py`, `kimi.py`, and `llm_agent.py` hashes match this checkout's audited files. Audit outputs under `runs/` are local, Git-ignored working artifacts. The public report bundles omit full recalled prose, model request bodies, and some raw terminal state; those omissions are stated rather than treated as evidence of absence.
