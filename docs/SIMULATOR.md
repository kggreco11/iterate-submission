# What the simulator computes, and how far to trust it

## One column solve
1. **Valve.** The feed's pressure is dropped by a valve (isenthalpic flash, Peng-Robinson 76 with ChemSep's constants and interaction table,
   `sepdesign/thermo.py`) to get the feed temperature and phase.
2. **Column.** ChemSep's solver (`co-col2.exe`, ChemSep LITE) solves an equilibrium-stage column: material, equilibrium, summation and heat
   balances on every stage at once (Newton's method), Peng-Robinson K-values and enthalpies, total condenser, partial reboiler, constant pressure,
   feed on the middle stage. It reports the two product streams, the duties and the per-stage vapour and liquid flows.
3. **Cost.** `sepdesign/cost_model.py` sizes the column from the stage flows (diameter, height), costs it with Douglas correlations, and adds
   utilities from temperature-dependent price curves.
4. If the solver stops at its iteration limit, three alternative initialisations are tried before the solve is reported as failed.

## Trust, with numbers
- **Separation (flows, duties):** this is ChemSep's own solver; nothing is approximated here except the valve in front of it. For the feed
  state, the flash agrees with ChemSep's own flash of the same feed (vapour fraction and enthalpy to four significant figures on the test feed).
- **Cost:** a calibrated textbook model, not ChemSep's own annual-cost number (ChemSep computes that in a separate sizing step that is not part of the
  solver). Fitted to ChemSep's annual cost on 4,014 six-hydrocarbon designs and scored on inlet groups it never saw: median error 11.5%, 90th
  percentile 50%, and it orders pairs of designs the same way as ChemSep 98.4% of the time (32.9% with no cost at all). For the 12-hydrocarbon set it
  extrapolates to heavier components and hotter bottoms (up to about 480 K); the reboiler price is held non-decreasing above 340 K for that reason.
  Absolute dollar figures should be read as "about right", rankings as reliable.
- **Failures.** A few percent of random designs do not converge; the retry methods rescue some. Extreme designs (very high reflux with very many
  stages) fail most often.
- **Not covered:** one column type, equilibrium stages with 100% efficiency, constant pressure inside the column, feed always on the middle stage.
  The hydrocarbons are treated with an equation of state only (no activity-coefficient models), which suits this mixture.

## Environment variables
`CHEMSEP_DIR` (ChemSep install folder, if not found automatically), `SIM_BACKEND` (`chemsep` default, or `mock`).
