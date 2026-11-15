# V3 400-query analysis

[Open the full plotted report](index.html) · [Metric figures PDF](figures.pdf) · [Plant topologies PDF](winning_plants.pdf)

- Single Past vs no Past: final reward -43.40%; model spend -12.67%. One completed run per condition; memory-handling recovery patches limit causal interpretation.
- Swarm Past vs no Past: final reward -6.46%; model spend -21.32%. One completed run per condition; memory-handling recovery patches limit causal interpretation.
- Single · no Past at 395 observed charged queries: reward 2.4383, net $2.024B/year. Final: $2.024B/year.
- Single · Past at 400 observed charged queries: reward 1.3800, net $1.146B/year. Final: $1.146B/year.
- Swarm · no Past at 400 observed charged queries: reward 2.1971, net $1.824B/year. Final: $2.179B/year.
- Swarm · Past at 400 observed charged queries: reward 2.0449, net $1.698B/year. Final: $2.039B/year.
- At the same observed 395-query cap, no-Past single reward is 2.4383 versus swarm 2.1029 (-13.76%). At their unequal endpoints, the swarm is +7.65% higher, using 5.01× charged queries and 2.90× model spend.
- The no-Past swarm’s net gain over the single comes from a $171.6M/year reduction in annualized cost, with revenue changing by $-16.7M/year. This is an accounting decomposition, not an intervention on plant topology.
- Past swarm leads the no-Past swarm at 200 team queries (1.8134 vs 1.1766), but trails by 400 (2.0449 vs 2.1971). Its early lead does not persist to the endpoint.
- The ranking depends on the resource: at $5 of model spend, the no-Past single leads (2.3680 vs 2.2421); at 10 elapsed minutes, the no-Past swarm leads (2.2421 vs 1.8673).
- Single · Past: 77.9% of candidate memory instances were omitted from prompts under the context budget; logged reads/writes/barriers account for 6.2 minutes (18.7% of wall time). Counts are repeated instances across prompts, not unique facts.
- Swarm · no Past: 436 explicit peer-design copies; final per-agent best rewards span 2.622220–2.624930. 1/5 agents ended on an invalid submitted design, while retaining earlier valid best designs.
- Swarm · Past: 304 explicit peer-design copies; final per-agent best rewards span 2.454490–2.455338. 1/5 agents ended on an invalid submitted design, while retaining earlier valid best designs.
- Swarm · Past: 86.1% of candidate memory instances were omitted from prompts under the context budget; logged reads/writes/barriers account for 4.8 minutes (12.3% of wall time). Counts are repeated instances across prompts, not unique facts.
- The Past single’s winning plant has zero physical recovery into priced qualifying products for: 2,2-dimethylbutane, 2-methylpentane, 3-methylpentane, N-hexane, Methylcyclopentane, Cyclohexane. Those components remain in terminal flows but do not qualify as the priced species or blend members. This helps explain its revenue shortfall despite lower plant cost.

## Evidence limitations

- All four completed conditions use the same HC16 V3 task and Kimi alias with 400 charged distinct queries per agent; five-agent totals are 2,000. One simulator worker and zero configured solver retries. Exact provider model ID is not inferred from the alias.
- Without Past is an exact-sharing condition, not a no-sharing baseline. The independent control has no completed result in this evidence. Shared agents are not independent samples.
- The completed cells came from multiple deployments after memory-handling failures. Source manifests are included to make the changed code auditable. This is a recovered exploratory comparison, not an unchanged-source randomized trial.
- Model USD uses the recorded uncached estimate: $2 per million input tokens and $10 per million output tokens, with source/date in each ledger summary. Cached/reasoning tokens are not added again. These estimates are not invoices; memory and VM costs are unknown.
- Curves use exact best-improvement events plus observed run endpoints. Flat intervals imply no better valid submission. Prefixes inherit the 400-per-agent announced horizon. Curves are not extrapolated after a run stops.
- Model costs are attributed in logged policy-outcome order; all concurrent proposals finish before submission evaluation. Simulator-call mapping uses the number of column executions present in each measured result, including both double-effect legs and budget cleanup; it is validated against service-event count and backend totals. A failed mapping suppresses that curve.
- Saved simulator validity checks cover convergence, complete evaluated topology, bounds, finite/nonnegative streams, component closure and economic accounting. Tolerances are provisional. Independent energy-balance validation is explicitly absent.
- Cache hits count all simulator-service lookups, including revisits to queries already paid by the same agent. Cache hits therefore do not equal charged queries minus backend calls. Both counts are retained rather than collapsed into one efficiency measure.
- The task values qualifying pure/premium products and blends. It does not require all components to be recovered at a minimum percentage. Revenue/ideal revenue is an economic ratio and is never used here as physical recovery.
- This export is a compact evidence projection of trajectories, summaries, winner streams, and usage reconciliation. Raw provider requests, credentials, and full raw simulator responses stay on the VM. Every-candidate replay is not included.

## Rebuild

`PYTHONPATH=runs/v3-400-analysis/deps .venv/bin/python scripts/analyze_v3_400.py --data results/hc16v3_dev_000/comparison/kimi-k3.1-pro/v3-400-analysis/report-data.json`

Validation: 122/122 checks passed.

## Behavioral investigation

[Swarm behavior, product grades, and next experiments](behavior.html) · [Markdown](behavior-analysis.md)

## Independent control update

The user-stopped independent control is now analyzed separately from completed runs. [Updated five-condition comparison](independent.html) · [Analysis and caveats](independent-analysis.md). The original findings above remain a historical four-condition analysis.
