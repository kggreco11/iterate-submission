# Design eligibility

`sepdesign.validation.validate_result` is a separate checker called before a candidate can replace `DesignEnv.best`. All conditions use the same checker. `render()` exposes rejection reasons to agents; economic reward remains visible even when a design is ineligible.

The checker verifies complete tree coverage, bounds, actually solved columns, finite/nonnegative component flows and annualized costs, finite heat duties, positive temperatures/pressures, feed identity, stream continuity, component balances and independently recomputed revenue/cost/reward. It rejects failed, budget-skipped and negligible-feed-skipped columns. Explicitly remove an unnecessary column and reevaluate rather than claiming it ran.

The service rejects missing/invalid costs instead of converting them to zero. The greedy baseline can only accept eligible improvements. Empty designs are valid and worth zero for the fixed HC12 feed.

## Provisional numerical policy

Component-flow comparisons use `absolute tolerance 1e-5 mol/s + relative tolerance 1e-6`. These tolerances are explicit defaults pending live qualification, not a claim of metrology accuracy. Raw column outputs are retained alongside rounded environment streams. Do not silently relax tolerances after viewing a comparison result.

State continuity uses relative 1e-6 and absolute 1e-5 in K or Pa. Economics comparisons use relative 1e-6 and absolute 1e-5 in their recorded units.

**Energy closure is not independently verified.** Finite duties and converged solver output do not provide inlet/outlet enthalpy closure. The gate reports `energy_balance_verified: false` and the benchmark must disclose this limitation. Nor does this gate validate the calibration accuracy of the annualized cost model.

## Checks and live runner

```sh
python -m pytest -q
python scripts/qualify_hc12.py
```

The second command requires Windows with ChemSep and uses the fixed task JSON. Set `CHEMSEP_DIR` to the installed directory if automatic discovery fails. It performs a bounded first-cut exploration (24 distinct queries maximum; 12-column cap for this qualification run only), writes raw calls and a report beneath `results/hc12-qualification`, and records source/task hashes. It does not call an LLM. A qualification run is not a reported agent comparison, and this first-cut cap does not replace the task's 36-column limit.
