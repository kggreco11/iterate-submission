"""
MockBackend: a cheap stand-in for the ChemSep backend so agents and tooling can be developed on any machine (no ChemSep, no Windows).

It is NOT a simulator of real distillation: it splits the feed along the volatility order with a sharpness that grows with stages and reflux,
and prices the column with a made-up formula of similar size. Never report results from it; every run file records which backend produced it.
"""
import time

import numpy as np

from sepdesign.hc12 import TB_K
from sepdesign.hc16 import COMPONENT_DATA


class MockBackend:
    name = "mock"

    def __init__(self, tb=None, names=None):
        if tb is None and names is not None and all(n in COMPONENT_DATA for n in names):
            tb = [COMPONENT_DATA[n][0] for n in names]
        self.tb = np.asarray(TB_K if tb is None else tb, float)

    def solve_column(self, case):
        t0 = time.perf_counter()
        z = np.asarray(case["feed_flows_mol_s"], float)
        n, rr, rb, dp = int(case["n_stages"]), float(case["reflux_ratio"]), float(case["reboil_ratio"]), float(case["pressure_drop_fraction"])
        if rr * rb > 600.0:                                           # mimic the occasional non-converging extreme design
            return {"success": False, "error": "mock: extreme design did not converge", "runtime_s": time.perf_counter() - t0, "diagnostics": {}}
        F = z.sum()
        d = rb / (rr + 1.0 + rb)                                      # distillate fraction from the reflux and boil-up ratios
        mid = (np.cumsum(z) - 0.5 * z) / F                            # position of each component along the feed, light to heavy
        k = 2.0 * np.sqrt(n) * np.log1p(min(rr, rb)) + 1.0            # sharpness of the split
        lo, hi = -2.0, 2.0
        for _ in range(60):                                           # shift so the distillate amount matches d
            sh = 0.5 * (lo + hi)
            r = 1.0 / (1.0 + np.exp(-k * (d - mid + sh)))
            if float(r @ z) / F > d:
                hi = sh
            else:
                lo = sh
        top = r * z
        bot = z - top
        P_col = float(case["pressure_Pa"]) * (1.0 - dp)
        side, sd = None, case.get("side_draw")
        if sd:                                                        # toy side draw: a middle cut taken from both outlets around the split point
            w = np.exp(-(((mid - d) / 0.18) ** 2)) * z
            w = w / max(w.sum(), 1e-12)
            amount = min(float(sd["fraction"]) * F, 0.95 * F)
            sflow = np.minimum(w * amount, 0.9 * z)
            frac_top = np.divide(top, z, out=np.zeros_like(z), where=z > 0)
            top, bot = top - sflow * frac_top, bot - sflow * (1.0 - frac_top)
            side = sflow
        V = rb * bot.sum()
        qr, qc = V * 2.5e4, -(rr + 1.0) * top.sum() * 2.5e4
        util = 4.0 * (qr + abs(qc)) * 8000 * 3600 / 1e9 / 2.0
        cap = 3.0e3 * n * np.sqrt(max(V, 1.0))
        tac = util + cap
        pf = (max(P_col, 1e4) / 101325.0) ** 0.07                     # toy: boiling temperatures rise with pressure
        tt = pf * (float(self.tb[top > 1e-9][-1]) if (top > 1e-9).any() else float(self.tb[0]))
        tb_ = pf * (float(self.tb[bot > 1e-9][-1]) if (bot > 1e-9).any() else float(self.tb[-1]))
        out = {"success": True, "tac_usd_per_year": float(tac), "condenser_duty_W": float(qc), "reboiler_duty_W": float(qr),
               "tops": {"flows": top.tolist(), "T_K": tt, "P_Pa": P_col}, "bottoms": {"flows": bot.tolist(), "T_K": tb_, "P_Pa": P_col},
               "cost": {"tac": float(tac), "utilities": float(util), "capital": float(cap * 3.0), "capital_annual": float(cap), "price_cond": 2.0,
                        "price_reb": 2.0, "Tc": tt, "Tr": tb_, "E_c_GJ": abs(qc) * 8000 * 3600 / 1e9, "E_r_GJ": qr * 8000 * 3600 / 1e9},
               "runtime_s": time.perf_counter() - t0, "error": None, "diagnostics": {"engine": "mock"}}
        if side is not None:
            ts = float(self.tb[side > 1e-9].mean()) if (side > 1e-9).any() else tt
            out["side"] = {"flows": side.tolist(), "T_K": ts, "P_Pa": P_col}
        return out
