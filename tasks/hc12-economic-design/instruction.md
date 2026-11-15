# Design an economically useful hydrocarbon separation plant

Starting from an empty flowsheet, maximize annual saleable product revenue minus annualized column cost for the supplied fixed 12-component feed. The harness supplies the exact task JSON, including prices and feed conditions.

Represent the plant as a tree of distillation columns. The root path is ""; its top and bottom outlets are "T" and "B". Subsequent paths append T or B. Each column has n_stages (5–200), reflux_ratio (0.1–30), reboil_ratio (0.1–30), and pressure_drop_fraction (0–0.9). At most 36 columns. Feed stage is fixed at the middle of the column.

Only terminal streams with at least 95 mol% of a component earn that component's revenue. Off-spec streams earn zero; there is no disposal fee or mandatory recovery target. The task's min_recovery_fraction controls negligible-stream handling, not a product recovery requirement. All columns must solve, with physical and material-balance checks passing. An invalid design cannot improve your score. The empty design is valid and earns zero. Prices and cost estimates are fixed benchmark assumptions.

Return a JSON object with `reason` (short explanation) and `edits` (array). Edits apply to your current design:
- {"op":"set","node":"","n_stages":60,"reflux_ratio":4,"reboil_ratio":4,"pressure_drop_fraction":0.1}
- {"op":"sell","node":"T"} removes that column and descendants.
- {"op":"revert"} restores the best valid design evaluated so far.

You receive simulator feedback after each submission. Use this to improve your next attempt. Cached identical column evaluations are free. A changed upstream column can require solving all descendants again. This pilot allows 50 distinct column evaluations, with automatic numerical retries disabled; failed evaluations also consume allowance. The best valid design is automatically retained. Keep exploring while budget remains. Do not merely repeat cached designs.
