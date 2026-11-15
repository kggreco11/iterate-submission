"""
Double-effect columns: one split done by two columns at different pressures, the high-pressure column's condenser boiling the low-pressure column's
reboiler.

    feed --> splitter --(fraction f)-----> HP column (valve drop dp)        --+--> tops  (both tops mixed)
                     --(fraction 1-f)---> LP column (valve drop dp_low > dp) -+--> bottoms (both bottoms mixed)
                                 HP condenser heat ==> LP reboiler, if Tc(HP) - Tr(LP) >= DT_MIN

Both columns have the column's stages, reflux and boil-up. The heat passed is min(HP condenser duty, LP reboiler duty); it saves that much cooling
at the HP condenser and that much heating at the LP reboiler, priced exactly as the cost model prices them (same temperature-dependent prices, same
energy multiplier). The shared exchanger is costed with the cost model's exchanger correlation (Douglas, area = Q / (U dT)), times the capital
multiplier, and is added to the pair's capital; the two columns' own condenser and reboiler areas are left as sized (a conservative simplification).
Mixed outlets are let down to the lower pressure; their temperature comes from an adiabatic (enthalpy) balance.

This is an idealised model of heat integration: no control or start-up penalties, one fixed minimum approach temperature, no pinch analysis.
"""
import json
import os

from sepdesign.cost_model import HOURS, MS, M2_TO_FT2, PARAMS_FILE

DT_MIN = 10.0                 # K, minimum temperature difference across the shared condenser-reboiler
U_HX = 850.0                  # W/m2/K, as the cost model's exchangers
FRACTION_BOUNDS = (0.2, 0.8)  # share of the feed sent to the high-pressure column
_FITTED = None


def _fitted():
    global _FITTED
    if _FITTED is None:
        _FITTED = json.load(open(PARAMS_FILE))
    return _FITTED


def heat_link(hp, lp, energy_multiplier, capital_multiplier):
    """Heat passed from the HP condenser to the LP reboiler, and its value. hp, lp: column results with 'qc', 'qr' and 'cost' (Tc, Tr, prices).
    Returns a dict with feasible, dT_K, heat_MW, saving_usd (utilities saved per year), exchanger_usd (annual capital of the shared exchanger)."""
    ch, cl = hp.get("cost"), lp.get("cost")
    if not ch or not cl:
        return {"feasible": False, "dT_K": None, "heat_MW": 0.0, "saving_usd": 0.0, "exchanger_usd": 0.0, "why": "no cost breakdown"}
    dT = float(ch["Tc"] - cl["Tr"])
    if dT < DT_MIN:
        return {"feasible": False, "dT_K": dT, "heat_MW": 0.0, "saving_usd": 0.0, "exchanger_usd": 0.0,
                "why": f"HP condenser {ch['Tc']:.0f} K is not at least {DT_MIN:.0f} K hotter than LP reboiler {cl['Tr']:.0f} K"}
    q = min(abs(float(hp["qc"])), abs(float(lp["qr"])))
    gj = q * HOURS * 3600.0 / 1e9
    saving = float(energy_multiplier) * (ch["price_cond"] + cl["price_reb"]) * gj
    saving = min(saving, float(ch.get("utilities", saving)) + float(cl.get("utilities", saving)))     # never more than the two columns pay
    area = q / (U_HX * dT)
    f = _fitted()
    exchanger = float(capital_multiplier) * f["capital_scale"] * MS * 101.3 * (area * M2_TO_FT2) ** 0.65 * (2.29 + 1.0) / 3.0
    return {"feasible": True, "dT_K": dT, "heat_MW": q / 1e6, "saving_usd": saving, "exchanger_usd": exchanger, "why": ""}
