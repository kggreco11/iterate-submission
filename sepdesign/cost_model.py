"""
Annual cost of a column, computed from what the solver reports (per-stage vapour and liquid flows, densities, temperatures; duties).

  diameter   largest over stages of  sqrt(4 Qv / (pi f u_flood)),  Qv = V MWv / rhoV,  u_flood = Csb sqrt((rhoL - rhoV) / rhoV),  f = 0.8
  height     0.6 m per stage + 4 m
  capital    shell 101.9 D^1.066 H^0.802 (2.18 + Fc)   trays 4.7 D^1.55 H Fc   exchangers 101.3 A^0.65 (2.29 + Fc)
             (Douglas, Conceptual Design of Chemical Processes, 1988: D, H in ft, A in ft2, x M&S/280, Fc = 1 carbon steel);
             condenser and reboiler areas A = Q / (U dT)
  utilities  condenser duty x price_c(T condenser) + reboiler duty x price_r(T reboiler), per GJ at 8,000 h/yr; the price curves are piecewise
             linear in temperature (refrigeration is expensive for cold condensers, steam price rises with reboiler temperature)
  TAC        utilities + capital scale x capital / 3 years

The two price curves and the capital scale are fitted (data/cost_params.json) to ChemSep's own Total Annual Cost for 4,014 six-hydrocarbon
designs; scored on inlet groups it never saw, the model's median error is 11.5%, its 90th percentile 50%, and it orders designs like ChemSep
98.4% of the time (see docs/COST_MODEL.md). It is a calibrated textbook model, not ChemSep's own number, and for heavier components and hotter
bottoms it extrapolates: the reboiler price is held non-decreasing above 340 K for that reason.
"""
import json
import os

import numpy as np

HOURS = 8000.0
MS = 1800.0 / 280.0
FT = 3.280839895
M2_TO_FT2 = FT * FT
DEFAULTS = {"payback": 3.0, "Csb": 0.09, "flood_frac": 0.8, "tray_spacing": 0.6, "head": 4.0, "U_hx": 850.0, "T_hot": 520.0, "T_cw": 311.0,
            "min_dT_c": 8.0, "min_dT_r": 15.0}
PARAMS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cost_params.json")


def features(res, p=None):
    """Size the column and its exchangers from a solve result (needs res['profile'], res['qc'], res['qr'])."""
    p = {**DEFAULTS, **(p or {})}
    pr = res["profile"]
    n = len(pr["T"])
    sl = slice(1, max(n - 1, 2))                                  # exclude the condenser and reboiler stages
    rhoV, rhoL = np.maximum(pr["rhoV"][sl], 1e-6), np.maximum(pr["rhoL"][sl], 1.0)
    qv = pr["V"][sl] * pr["MWv"][sl] / rhoV                      # kmol/s * kg/kmol / (kg/m3) = m3/s
    uf = p["Csb"] * np.sqrt(np.maximum(rhoL - rhoV, 1.0) / rhoV)
    D = float(max(np.sqrt(4.0 * (qv / (p["flood_frac"] * uf)).max() / np.pi), 0.5))
    H = p["tray_spacing"] * (n - 1) + p["head"]
    Qc, Qr = abs(res["qc"]), abs(res["qr"])
    Tc, Tr = float(pr["T"][0]), float(pr["T"][-1])
    A_c = Qc / (p["U_hx"] * max(Tc - p["T_cw"], p["min_dT_c"]))
    A_r = Qr / (p["U_hx"] * max(p["T_hot"] - Tr, p["min_dT_r"]))
    Dft, Hft = D * FT, H * FT
    shell = MS * 101.9 * Dft ** 1.066 * Hft ** 0.802 * (2.18 + 1.0)
    trays = MS * 4.7 * Dft ** 1.55 * Hft * 1.0
    hx = MS * 101.3 * ((A_c * M2_TO_FT2) ** 0.65 + (A_r * M2_TO_FT2) ** 0.65) * (2.29 + 1.0)
    return {"Tc": Tc, "Tr": Tr, "D_m": D, "H_m": H, "A_c_m2": A_c, "A_r_m2": A_r, "capital_shell": shell, "capital_trays": trays, "capital_hx": hx,
            "capital": shell + trays + hx, "E_r_GJ": Qr * HOURS * 3600.0 / 1e9, "E_c_GJ": Qc * HOURS * 3600.0 / 1e9}


class CostModel:
    """Callable (res, case) -> {'tac': $/yr, 'capital': $, 'utilities': $/yr, ...}."""

    def __init__(self, params=None, fitted=None, energy_multiplier=1.0, capital_multiplier=1.0):
        self.p = {**DEFAULTS, **(params or {})}
        self.f = fitted or json.load(open(PARAMS_FILE))
        self.em, self.cm = float(energy_multiplier), float(capital_multiplier)    # scenario scaling of the energy and capital parts of the cost

    @property
    def signature(self):
        return f"E{self.em:g}:C{self.cm:g}"

    def __call__(self, res, case=None):
        f = features(res, self.p)
        pc = float(np.interp(f["Tc"], self.f["cond_knots"], self.f["cond_price_per_GJ"]))
        pr = float(np.interp(f["Tr"], self.f["reb_knots"], self.f["reb_price_per_GJ"]))
        util = self.em * (pc * f["E_c_GJ"] + pr * f["E_r_GJ"])
        cap = self.cm * self.f["capital_scale"] * f["capital"]
        return {"tac": float(util + cap / self.p["payback"]), "capital": float(cap), "utilities": float(util), "price_cond": pc, "price_reb": pr, **f}
