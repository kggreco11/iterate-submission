# Task brief: 12-component economic flowsheet design

## Objective

Design a complete distillation-column tree maximizing **annual saleable-product revenue minus total annualized column cost**. All conditions solve the same fixed task. No component has a mandatory minimum recovery; agents choose which separations justify their costs.

## Fixed task and scoring

- Task: `hc12_dev_000`, snapshotted in [tasks/hc12_dev_000.json](../tasks/hc12_dev_000.json). Use this file, rather than regenerating the feed during experiments.
- Feed: 3300.000001 mol/s, 400 K, 1,760,000 Pa; 8,000 operating hours/year.
- A terminal stream earns revenue when its dominant component reaches **95% mole purity**. Revenue credits only that component's molar flow times its fixed price and annual operating seconds.
- Below 95% purity, the stream is an allowed residual with zero revenue. No disposal charge or mixed-product salvage value in this initial benchmark. Report residual flows so that this simplification remains visible.
- Subtract the sum of column annualized equipment/operating costs from the selected backend. Do not add a separate utility charge already included in that cost.
- Prices are fixed benchmark coefficients, not verified market quotations. Feed procurement is excluded because feed is identical across conditions; report “net product revenue minus annualized separation cost,” not accounting profit.
- Normalized score = annual net objective / $772,068,382.078961. Keep dollar components visible.
- Empty-design/do-nothing baseline: **$0/year**, zero calls, zero columns. It is valid and can beat an uneconomic plant.
- Pure-product/no-cost revenue ceiling: $3,656,746,188.98/year. This is an ideal upper bound, not an achievable design.

| Component | Feed (mol/s) | Price ($/mol) |
| --- | --- | --- |
| Ethane | 128.271138 | 0.00438441 |
| Propane | 355.233439 | 0.00862570 |
| Isobutane | 206.916885 | 0.01405534 |
| N-butane | 298.696659 | 0.01729156 |
| Isopentane | 513.118390 | 0.04437269 |
| N-pentane | 278.625168 | 0.03353319 |
| 2,2-dimethylbutane | 77.570139 | 0.06148213 |
| 2-methylpentane | 365.858994 | 0.05118710 |
| N-hexane | 145.130140 | 0.05077347 |
| Methylcyclopentane | 190.001068 | 0.05467201 |
| N-heptane | 369.095829 | 0.04090563 |
| N-octane | 371.482152 | 0.07216479 |

## Design space and starting conditions

Start each agent from the same **empty design**. Permit column-tree edits, evaluation, and revision. No prescribed topology or number of products. Initial bounds follow the current environment: 5–200 stages, reflux and reboil ratios 0.1–30, pressure-drop fraction 0–0.9, and at most 36 columns. The code's `stream_limit` maps to a column cap in this environment; it is not a 36-product requirement.

Recycles, heat integration, alternative unit operations, and blended-product economics are outside this first brief. The backend's supported column/thermodynamic assumptions are documented in [SIMULATOR.md](SIMULATOR.md).

## Validity gate — required before reported comparisons

An economic score is eligible only when:

1. Every included column is actually evaluated and converges. Failed, budget-skipped, or negligible-feed-skipped columns cannot be silently counted as a completed plant. Remove a redundant column explicitly and reevaluate if appropriate.
2. Feed/outlet vectors have the expected 12 components; flows, temperatures, pressures, duties and costs exposed by the backend are finite and physically admissible. Equipment settings satisfy the fixed bounds.
3. Per-column and overall component balances pass a documented, justified numerical tolerance. Preserve raw unrounded outputs for checks; report any rounding separately.
4. All streams terminate as saleable products or explicitly reported residuals; no undeclared mass disappears.

**Gate implementation and numerical tolerances are not yet frozen.** Validate the direct ChemSep backend on this task first. The six-component worker check does not qualify the new backend, heavier components, or calibrated cost model. Energy closure must be checked if sufficient enthalpy data are available; otherwise label it unverified rather than equating convergence with independent energy validation.

The independent `sepdesign.validation` checker now gates `DesignEnv._record`: failed, skipped, incomplete or numerically invalid designs cannot replace the best eligible result. Missing/nonfinite annualized costs are rejected. Provisional component-balance tolerances are 1e-5 mol/s absolute + 1e-6 relative; these are explicit engineering defaults, not yet a solver qualification result. Energy closure remains unverified.

## Comparison and outputs

Use the agreed 1/3/5-agent shared-memory protocol, both equal-team-total and equal-per-agent budget comparisons, and independent repetitions. Keep model/tools/task/evaluator fixed. Count all team work, retries, cache behavior and memory costs. This was the initial proposed protocol, not a claim that every cell or repetition was run. See the [memory-control protocol](MEMORY_CONTROLS.md) and [master research report](../RESEARCH_REPORT.md) for the implemented conditions and observed evidence.

Primary plots: best valid economic objective against calls, elapsed time, and search spend. Secondary outputs: product purity/recovery/flow, residual flow, convergence and invalid-submission rates. Report time/calls to first **positive valid economic improvement over the empty baseline**, since an empty valid design exists at time zero. Any higher target must be declared before comparison runs.

## Readiness and next actions

- [x] Choose one development task, snapshot inputs/prices, and compute the empty-design baseline.
- [x] Specify economic scoring, residual treatment, and starting design.
- [x] Exercise the real direct ChemSep backend and cost calculation on the fixed feed; 12 columns passed the provisional gate. See [qualification](../results/hc12-qualification/README.md). Cost-model calibration accuracy is not independently validated by this run.
- [x] Implement the independent eligibility checker with adversarial tests.
- [ ] Qualify and freeze numerical tolerances on live backend evidence.
- [x] Run a valid nonempty first-cut baseline; it was uneconomic, so the empty baseline remains best.
- [ ] Run one single-agent pilot, then select numeric budgets, rounds, model caps, and repeat count.

Task file SHA-256: `63a8fb92e72484d1124b1e8ebac238324af1143f465db8afa91da97e523c7e6f`.

The 12-component direction and economic objective are user-approved. The concrete task, 95% pricing cutoff, zero-value residual convention, empty start, and inherited bounds are implementation defaults chosen from the existing code for this first brief; document any revisions before freezing the experiment.
