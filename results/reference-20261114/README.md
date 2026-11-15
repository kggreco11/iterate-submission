# Live 12-column reference replay

Executed 2026-11-14 on chemsep-01. This is a simulator reference check, not an agent experiment.

- **Execution:** 12 fresh column calls, zero cache hits, 74.2 seconds including worker description and accounting; Azure command delivery adds overhead.
- **Economics:** annual revenue $1,488.053M; annualized cost $116.419M; net $1,371.634M under the upstream benchmark assumptions.
- **Reference agreement:** 12 successful columns, no unresolved streams; annualized cost matches exactly and revenue differs by less than $0.000001/year.
- **Specification:** two terminal streams remain below the existing 95% purity cutoff; upstream spec_success is false.
- **Physics:** all columns converged. Eleven of twelve pass the initial component balance check (absolute 1e-6 mol/s + relative 1e-7 of component inlet). The column fed by stream 6 fails; do not label this an unconditional physics pass.
- **Overall closure:** maximum absolute component residual 3.5e-05 mol/s, using the upstream six-decimal stream rounding.
- **Limit:** energy balance is not independently verified; heat duties alone do not provide inlet/outlet enthalpy closure.

The flagged residuals are isopentane (2.56e-5 mol/s; 0.31 ppm of its inlet) and n-pentane (1.38e-6 mol/s; 0.50 ppm), both in the column fed by stream 6. All raw outlet flows are finite and nonnegative. These small residuals need an explicit numerical-tolerance decision; they do not demonstrate a gross conservation failure.

## Product outcomes

Recovery below counts a component only in on-spec terminal streams where it is the dominant component. Purity range describes those individual product streams, not a blended product.

| Component | On-spec product purity | Component recovery |
| --- | --- | --- |
| Ethane | No dedicated product | 0.00% |
| Propane | 98.492–98.492% | 98.36% |
| Isobutane | 97.296–100.000% | 96.64% |
| N-butane | 99.996–100.000% | 92.31% |
| Isopentane | 98.423–99.934% | 75.88% |
| N-pentane | 99.985–99.993% | 97.86% |

Ethane remains in other streams; 0% dedicated-product recovery does not mean its mass disappeared.

## Off-spec outlets

| Stream | Main component | Purity | Flow (mol/s) |
| --- | --- | --- | --- |
| 21 | Isopentane | 92.490% | 89.367 |
| 24 | Isobutane | 61.976% | 64.575 |

The upstream stream-limit rule terminates these outlets. Treating them as residual streams versus requiring further separation is an explicit design-brief decision.

## Historical implications for the experiment

These notes predate the frozen HC12 economic brief. That brief subsequently chose no recovery minima and allowed zero-value residuals; the proposed five-product brief below was not adopted.

- Keep this as a reproducible economic reference, not a feasible example of recovering all six components as pure products.
- A five-product brief with ethane allowed as an impurity/residual is a candidate, not yet an agreed requirement.
- Freeze recovery thresholds and residual-stream rules before evaluation; reference isopentane recovery is about 75.9%.
- Investigate and justify numerical tolerances before freezing the checker. Do not silently relax them to make the reference pass.

## Flowsheet

```mermaid
flowchart TD
  S1["Stream 1"] --> C1["Column 1: 121 stages; RR 5.2; RB 7.6; dP 0.0"]
  C1 -->|tops| S2
  C1 -->|bottoms| S3
  S2["Stream 2"] --> C2["Column 2: 72 stages; RR 6.1; RB 7.0; dP 0.01"]
  C2 -->|tops| S4
  C2 -->|bottoms| S5
  S3["Stream 3"] --> C3["Column 3: 58 stages; RR 4.9; RB 9.1; dP 0.26"]
  C3 -->|tops| S6
  C3 -->|bottoms| S7
  S6["Stream 6"] --> C4["Column 4: 95 stages; RR 6.2; RB 8.1; dP 0.55"]
  C4 -->|tops| S8
  C4 -->|bottoms| S9
  S7["Stream 7"] --> C5["Column 5: 86 stages; RR 9.9; RB 8.6; dP 0.89"]
  C5 -->|tops| S10
  C5 -->|bottoms| S11
  S8["Stream 8"] --> C6["Column 6: 120 stages; RR 7.1; RB 7.6; dP 0.52"]
  C6 -->|tops| S12
  C6 -->|bottoms| S13
  S9["Stream 9"] --> C7["Column 7: 73 stages; RR 5.9; RB 6.3; dP 0.52"]
  C7 -->|tops| S14
  C7 -->|bottoms| S15
  S11["Stream 11"] --> C8["Column 8: 89 stages; RR 9.6; RB 9.5; dP 0.12"]
  C8 -->|tops| S16
  C8 -->|bottoms| S17
  S12["Stream 12"] --> C9["Column 9: 114 stages; RR 5.3; RB 5.9; dP 0.38"]
  C9 -->|tops| S18
  C9 -->|bottoms| S19
  S15["Stream 15"] --> C10["Column 10: 95 stages; RR 9.3; RB 6.8; dP 0.45"]
  C10 -->|tops| S20
  C10 -->|bottoms| S21
  S16["Stream 16"] --> C11["Column 11: 101 stages; RR 9.5; RB 9.7; dP 0.35"]
  C11 -->|tops| S22
  C11 -->|bottoms| S23
  S19["Stream 19"] --> C12["Column 12: 153 stages; RR 4.3; RB 8.3; dP 0.27"]
  C12 -->|tops| S24
  C12 -->|bottoms| S25
  S4["Stream 4: Propane, 98.49%"]
  S5["Stream 5: Isobutane, 97.30%"]
  S10["Stream 10: Isopentane, 99.93%"]
  S13["Stream 13: N-butane, 100.00%"]
  S14["Stream 14: N-butane, 100.00%"]
  S17["Stream 17: N-pentane, 99.98%"]
  S18["Stream 18: Isobutane, 100.00%"]
  S20["Stream 20: N-butane, 100.00%"]
  S21["Stream 21: Isopentane, 92.49%"]
  S22["Stream 22: Isopentane, 98.42%"]
  S23["Stream 23: N-pentane, 99.99%"]
  S24["Stream 24: Isobutane, 61.98%"]
  S25["Stream 25: N-butane, 100.00%"]
```

Machine-readable data: report.json; raw column trace: reference.calls.jsonl; independent check results: validation.json. Scripts: infrastructure/azure/replay_reference.py and summarize_reference.py. Simulator service and accounting library are still dependencies of the existing Windows installation; their fingerprints are recorded in report.json.
