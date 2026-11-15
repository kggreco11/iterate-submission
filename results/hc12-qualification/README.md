# HC12 live backend qualification

November 14, 2026. Fixed task `hc12_dev_000`; real direct ChemSep console solver, not the mock backend. This is a bounded fixed first-cut run, not an agent comparison.

| Measurement | Result |
| --- | --- |
| Actual column solves | 12 |
| Failed solves / retry rescues | 0 / 0 |
| Execution wall time | 3.787 s (excluding Azure delivery) |
| Median solve | 0.299 s |
| Final design eligibility | Passed provisional gate |
| Maximum raw column component residual | 8.03e-8 mol/s |
| Maximum outlet/rounded-child discrepancy | 4.84e-7 mol/s |
| Overall component residual | 5.68e-14 mol/s |
| Final normalized economic score | -0.063313 |
| Final annual net objective | $-48,881,690.37 |
| Best valid score, including empty baseline | 0 |

The fixed first-cut plant is physically admissible under the provisional checks but loses money under the benchmark economics. Keeping the empty design as best is expected behavior. No claim is made that this is a good search baseline or that a profitable design was found in this run.

The checker includes raw component balances, stream continuity, finite/nonnegative flows and costs, positive states, complete topology, and recomputed economic accounting. Tolerances remain provisional (1e-5 mol/s absolute plus 1e-6 relative). Energy closure is not independently verified. Running the calibrated cost model successfully does not independently validate its accuracy for the heavier components.

The console solver was found at `C:\Users\chemsepadmin\Desktop\bin\co-col2.exe`. Set `CHEMSEP_DIR` explicitly to its parent installation directory. It ran from Azure's noninteractive session without the old worker.

The runner used a 12-column cap and 24-query ceiling solely for qualification. The main task retains its 36-column cap. No LLM or memory API was used.

Artifacts: `summary.json`, `report.json` and `calls.json` (all 12 raw simulator calls). Script: `scripts/qualify_hc12.py`. Regression checks: 17 local tests passed after integrating current main.
