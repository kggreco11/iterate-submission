# Task V3: Hydrocarbon-16 with side draws and double-effect columns (`hc16v3`)

Same feeds, prices, premium grade and blends as V2 (`hc16v2`, same seeds, so V2 and V3 tasks have identical feeds). Three things change:
1. **Side draws**: a column may take a third outlet from the middle of the column.
2. **Double-effect columns**: a split may be done by two columns at different pressures, the high-pressure column's condenser boiling the
   low-pressure column's reboiler (heat integration inside the pair).
3. **Energy price x6** (V2: x2); capital stays x10. Plant cost is then about 30-40% of revenue (V2: 12-15%), so energy saving matters.

Pick it with `--family hc16v3`. V2 and V1 are unchanged. Hashes: dev `91bb77c83ae2`, test `7feb566acd00` (first 12 characters of the SHA-256 of the
sorted JSON). Ceilings are the same as V2 (the ceiling has no cost in it).

## Side draws
A set edit may carry `"side_draw": {"stage": s, "phase": "liquid"|"vapour", "fraction": f}`: fraction f (0.02 to 0.6) of the column feed leaves as a
third stream at stage s (2 to n-1, not the feed stage; stage 1 is the condenser, stage n the reboiler; the feed enters the middle stage). The side
stream is named `p + "S"` and can be sold or fed to a further column. It lies between the tops and the bottoms in volatility, so it can deliver a
middle cut (for example a blend) from one column instead of two, but lighter and heavier components leak into it. Omitting `side_draw` in a later
set edit removes it, and the columns below `pS` with it. A different (stage, phase, fraction) is a different solve.

## Double-effect columns
A set edit may carry `"double_effect": {"fraction": f, "low_pressure_drop_fraction": d}`:

    feed --> share f (0.2-0.8) ---> HP column, valve drop = the column's pressure_drop_fraction  --+--> tops  'T' (both tops mixed)
         --> share 1-f -----------> LP column, valve drop = d (larger, so a lower pressure)        -+--> bottoms 'B' (both bottoms mixed)
                                     HP condenser ==heat==> LP reboiler   if Tc(HP) >= Tr(LP) + 10 K

Both columns have the column's stages, reflux and boil-up. The heat passed is the smaller of the HP condenser duty and the LP reboiler duty; it is
bought once instead of twice, and the saving is priced exactly as the cost model prices those duties (same temperature-dependent prices, same
energy multiplier). A shared exchanger (Douglas area correlation, x the capital multiplier) is added. Mixed outlets are let down to the lower pressure
and their temperature comes from an enthalpy balance (Peng-Robinson). A double effect costs two solves and cannot also have a side draw. The agent is
shown both columns' pressures, temperatures and costs, and the heat passed and its saving, or why no heat can pass.
Code: `sepdesign/multi_effect.py` (the heat link), `DesignEnv._pair_result` (the pair). This is an idealised model: one fixed 10 K approach,
no control or start-up penalties, no pinch analysis. Plant-wide heat integration between unrelated columns is deliberately not included: our test
showed it is bookkeeping ("link whatever the temperatures allow" captures nearly all of it).

### Why it is a decision and not a rule (gate test: `scripts/multi_effect_gate.py`, `results/hc16v3-multi-effect/`)
On the four Opus V2 plants (56 columns) every column was tried as a pair over a grid of feed shares and pressures, with its own stages and ratios,
keeping pairs whose split matches the single column's (within 2 percentage points per component), and compared with **the best single column at any
of the same pressures** (so plain pressure re-tuning is not credited to the double effect).
- **Physics decides most columns.** A pair can only pass heat when the HP column's top is 10 K hotter than the LP column's bottom. Columns that
  split a wide boiling range (top-to-bottom span 20 to 150 K: the first columns, most bottoms columns) never qualify at any pressure the valves allow;
  close splits (span under about 15 K) can. 9 to 10 of 56 columns qualify at every cost level tried.
- **Economics decides the rest.** At energy x2 the qualifying pairs gain 0 to 1.5% of the plant's reward (the gate failed at the V2 price level); at
  x6 they gain 0 to 7% (dev_000 7.3%, dev_001 0%, dev_002 2.7%, dev_003 2.4%), with 0 to 4 columns per plant worth doubling. Capital x20 instead of
  x10 changes little. These are lower bounds: the pair keeps Opus's stages and ratios, the grid is coarse, and the plants were not designed for it.
- **Whole-plant check (real simulator):** turning Opus's dev_000 column `BT` (a C6 split, 15 K span) into a double effect at V3 prices raised the
  plant's reward from 2.611 to 2.855 (+9%). At a slightly smaller pressure drop the gap falls just under 10 K, the link disappears and the pair is
  no better than one column: the edge is sharp, as in a real plant.

So at V3 prices the decision is mixed: most columns should not be doubled, a few should, and which ones depends on the split order chosen (an
agent can arrange close splits into their own columns to make doubling possible).

## Simulator qualification
- **Side draws** (`scripts/side_draw_qualify.py`, `results/hc16v3-side-draw/`): 160 random side-draw columns on the four dev feeds; 83 to 89% solved
  after the alternative initialisations (pass bar 85%: borderline on wide random settings), about 30% needed a retry; component balance including the
  side stream closes to better than 1e-9 of the feed and the side flow equals the request.
- **Double effects**: each effect is an ordinary column solve (same solver and failure behaviour as any column); the pair's outlets balance exactly
  (tests), and on the real simulator a full plant with a pair passes validation.
- Tests: 46 pass (`tests/test_side_draw.py`, `tests/test_double_effect.py` and the earlier ones), on the mock backend.

## Not done
Four Opus V3 first-look runs are saved and published in the canonical report index. The robot baselines do not use side draws or double effects. No comparison of side-draw columns against a second
simulator. The cost model still extrapolates for propylene and n-nonane; the energy and capital multipliers are scenario assumptions, not market data.

Real-backend mixing failures invalidate a pair; only the mock backend may use flow-weighted temperature. Saved-design validation enforces the same optional-feature rules as edits. Tool schemas expose these options only for V3 tasks with the corresponding lever enabled.
