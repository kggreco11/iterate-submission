"""
Column simulator backend: ChemSep's own column solver (co-col2.exe) run as a console program on a column input file (.sep).

One solve = edit the column file (stages, feed stage, reflux and boil-up ratios, pressure, feed), run the solver in its own scratch folder,
read the products, duties and per-stage profile it writes back, then price the column with sepdesign.cost_model. The valve in front of the
column is a Peng-Robinson isenthalpic flash (sepdesign.thermo) using the same constants as the column. Each call is independent, so many
can run at once (threads or processes): there is no shared state and no desktop session is needed.

A solve that does not converge returns success=False (never a silent wrong answer). ChemSep sometimes pops up an "iteration limit" dialog on
hard designs; the solve is killed after `timeout_s` and reported as not converged.
"""
import os
import re
import shutil
import subprocess
import tempfile
import time

import numpy as np

from sepdesign.chemsep_lib import chemsep_exe
from sepdesign.families import Family

_METHOD = {"m2": "2 Method 2-pass constant H first", "m3": "3 Method 2-pass constant H first", "m4": "4 Method 2-pass ideal K + H first"}


def _num(x):
    return repr(float(x))


def add_side_draw(text, stage, phase, flow_kmol_s):
    """Column input text with one side draw: ChemSep's 'Complex Column' with a [SideStreams] block (total molar flow in kmol/s, phase liquid or vapour).
    The stage counts from the condenser (stage 1)."""
    code = {"vapour": 1, "liquid": 2}[phase]
    t, k1 = re.subn(r"(?m)^1 Operation kind Simple Distillation$", "11 Operation kind Complex Column", text, count=1)
    t, k2 = re.subn(r"0 Sidestream stages\nF=(\d+)\nS=\n", lambda m: f"1 Sidestream stages\nF={m.group(1)}\nS={int(stage)}\n", t, count=1)
    t, k3 = re.subn(r"\n\[Condenser\]\n", f"\n[SideStreams]\n1 Number\n{int(stage)} Stage Sidestream1\n{code} Phase {phase.capitalize()}\n"
                    f"2 Specification Total flow\n{_num(flow_kmol_s)} Value\n\n[Condenser]\n", t, count=1)
    assert k1 == k2 == k3 == 1, "side-draw edit: the column template does not have the expected lines"
    return t


def build_sep(family, case, T_feed_K, variant=None):
    """Column input text for `case` (mol/s feed flows, ratios, stages, pressure drop fraction); the feed is given as temperature and pressure."""
    n = int(case["n_stages"])
    P_col = float(case["pressure_Pa"]) * (1.0 - float(case["pressure_drop_fraction"]))
    t = family.sep_template
    if variant is not None:                       # alternative initialisations differ only in the solver-method line
        t = re.sub(r"(?m)^\d+ Method .*$", _METHOD[variant], t, count=1)
    fs = case.get("feed_stage") or int(round(n / 2))
    t = re.sub(r"(?m)^\d+ Stages$", f"{n} Stages", t, count=1)
    t = re.sub(r"(?m)^\d+ Last stage$", f"{n - 1} Last stage", t, count=1)
    t = re.sub(r"(?m)^\S+ Value Qcondenser$", f"{_num(case['reflux_ratio'])} Value Qcondenser", t, count=1)
    t = re.sub(r"(?m)^\S+ Value Qreboiler$", f"{_num(case['reboil_ratio'])} Value Qreboiler", t, count=1)
    for name in ("Condenser pressure", "Top pressure", "Bottom pressure"):
        t = re.sub(rf"(?m)^\S+ {name}$", f"{_num(P_col)} {name}", t, count=1)
    flows = [f / 1000.0 for f in case["feed_flows_mol_s"]]
    feeds = (f"[Feeds]\n1 Number\n1 Feed state T & p\n{fs} Stage Feed1{{split}}\n{_num(T_feed_K)} Temperature\n{_num(P_col)} Pressure\n"
             f"0 Vapour fraction\n{len(flows)} componentflows\n" + "".join(f"{_num(f)} Component {i + 1} flow\n" for i, f in enumerate(flows)) + "\n")
    t, k = re.subn(r"\[Feeds\].*?(?=\[Condenser\])", lambda m: feeds, t, count=1, flags=re.S)
    assert k == 1, "feeds block not found in the column template"
    sd = case.get("side_draw")
    if sd:
        t = add_side_draw(t, sd["stage"], sd["phase"], float(sd["fraction"]) * sum(flows))
    return t


def _section(text, header):
    m = re.search(re.escape(header) + r"[^\n]*\n(.*?)(?=^\[|\Z)", text, re.S | re.M)
    return m.group(1) if m else ""


def _product(text, header, n_comp):
    first, xs = {}, {}
    for line in _section(text, header).splitlines():
        m = re.match(r"\s*(\S+)\s+(.*\S)\s*$", line)
        if not m:
            continue
        try:
            val = float(m.group(1))
        except ValueError:
            continue
        mm = re.match(r"Mole fraction of component\s+(\d+)", m.group(2))
        if mm:
            xs.setdefault(int(mm.group(1)), val)
        else:
            first.setdefault(m.group(2), val)
    if "Flow rate" not in first or len(xs) < n_comp:
        return None
    F = first["Flow rate"] * 1000.0                                  # kmol/s -> mol/s
    return {"flows": [F * xs[i + 1] for i in range(n_comp)], "T_K": first.get("Temperature [K]"), "P_Pa": first.get("Pressure [Pa]")}


def _rows(text, header):
    out = []
    for line in _section(text, header).splitlines():
        t = line.split()
        if len(t) >= 3 and t[0].isdigit():
            try:
                out.append([float(x) for x in t])
            except ValueError:
                pass
    return np.array(out) if out else np.zeros((0, 0))


def parse_profile(text):
    """Per-stage T (K), P (Pa), vapour and liquid flow (kmol/s), vapour and liquid molecular weight and density (kg/m3)."""
    pr, vp, lp = _rows(text, "[Profiles]"), _rows(text, "[Vapour Properties]"), _rows(text, "[Liquid Properties]")
    if not (len(pr) and len(pr) == len(vp) == len(lp)):
        return None
    return {"T": pr[:, 1], "P": pr[:, 2], "V": pr[:, 3], "L": pr[:, 4], "MWv": vp[:, 1], "rhoV": vp[:, 2], "MWl": lp[:, 1], "rhoL": lp[:, 2]}


def _duty(text, header):
    m = re.search(re.escape(header) + r"\s*\n\s*(\S+)\s+Duty", text)
    return float(m.group(1)) if m else None


def failure(error, runtime_s=0.0, diagnostics=None):
    return {"success": False, "tops": None, "bottoms": None, "condenser_duty_W": None, "reboiler_duty_W": None, "tac_usd_per_year": None,
            "runtime_s": runtime_s, "error": error, "diagnostics": diagnostics or {}}


class ChemSepBackend:
    name = "chemsep"

    def __init__(self, family: Family, cost_model=None, retry=True, timeout_s=20.0, work_root=None, below_normal=True, chemsep_dir=None):
        self.exe = chemsep_exe(chemsep_dir)
        if not self.exe:
            raise FileNotFoundError("ChemSep's co-col2.exe not found: install ChemSep LITE (chemsep.org) or set CHEMSEP_DIR")
        self.family = family
        self.cost_model = cost_model
        self.variants = (None, "m3", "m4", "m2") if retry else (None,)
        self.timeout_s = timeout_s
        self.below_normal = below_normal
        self.work_root = work_root or os.path.join(tempfile.gettempdir(), "sepdesign_work")
        os.makedirs(self.work_root, exist_ok=True)

    def _run(self, case, T_feed, variant):
        d = tempfile.mkdtemp(prefix="c_", dir=self.work_root)
        try:
            with open(os.path.join(d, "c.sep"), "w", encoding="latin-1", newline="") as f:
                f.write(build_sep(self.family, case, T_feed, variant))
            kw = {}
            if os.name == "nt":
                kw["creationflags"] = (0x00004000 if self.below_normal else 0) | 0x08000000     # below-normal priority, no console window
            try:
                p = subprocess.run([self.exe, "c.sep"], cwd=d, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=self.timeout_s,
                                   errors="replace", **kw)
            except subprocess.TimeoutExpired:
                return None, {"timeout": True}
            out = p.stdout + p.stderr
            m = re.search(r"Convergence obtained in\s+(\d+)\s+iterations", out)
            diag = {"n_iter": int(m.group(1)) if m else None}
            if not m or "Convergence not obtained" in out:
                diag["unconverged"] = True
                return None, diag
            txt = open(os.path.join(d, "c.sep"), encoding="latin-1").read()
            nc = len(case["feed_flows_mol_s"])
            tops, bots = _product(txt, "[Top product]", nc), _product(txt, "[Bottom product]", nc)
            side = _product(txt, "[Side stream 1 from stage", nc) if case.get("side_draw") else None
            if case.get("side_draw") and side is None:
                diag["parse_error"] = True
                return None, diag
            qc, qr = _duty(txt, "[Condenser Heat Duty]"), _duty(txt, "[Reboiler Heat Duty]")
            if tops is None or bots is None or qc is None or qr is None:
                diag["parse_error"] = True
                return None, diag
            return {"tops": tops, "bottoms": bots, "side": side, "qc": qc, "qr": qr, "profile": parse_profile(txt)}, diag
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def solve_column(self, case):
        t0 = time.perf_counter()
        P_in = float(case["pressure_Pa"])
        P_col = P_in * (1.0 - float(case["pressure_drop_fraction"]))
        try:
            T_feed = self.family.thermo.valve_T(case["feed_flows_mol_s"], float(case["temperature_K"]), P_in, P_col)
        except Exception as ex:  # noqa: BLE001
            return failure(f"valve flash failed: {type(ex).__name__}: {ex}", time.perf_counter() - t0)
        if not np.isfinite(T_feed):
            return failure("valve flash did not converge", time.perf_counter() - t0)
        tried = []
        for variant in self.variants:
            res, diag = self._run(case, T_feed, variant)
            tried.append({"variant": variant or "stock", **diag})
            if res is not None:
                feed = float(np.sum(case["feed_flows_mol_s"]))
                closure = abs(sum(res["tops"]["flows"]) + sum(res["bottoms"]["flows"]) + (sum(res["side"]["flows"]) if res.get("side") else 0.0) - feed) / feed
                cost = self.cost_model(res, case) if (self.cost_model is not None and res.get("profile") is not None) else None
                tac = cost["tac"] if cost else None
                breakdown = None
                if cost:                                  # the parts of the annual cost (multi-effect pairs need them)
                    breakdown = {k: float(cost[k]) for k in ("tac", "utilities", "capital", "price_cond", "price_reb", "Tc", "Tr", "E_c_GJ", "E_r_GJ")}
                    breakdown["capital_annual"] = float(cost["tac"] - cost["utilities"])
                return {"success": True, "tac_usd_per_year": tac, "condenser_duty_W": res["qc"], "reboiler_duty_W": res["qr"], "tops": res["tops"],
                        "bottoms": res["bottoms"], "side": res.get("side"), "cost": breakdown, "runtime_s": time.perf_counter() - t0, "error": None,
                        "diagnostics": {"engine": "chemsep", "T_feed_K": T_feed, "solved_by": variant or "stock", "attempts": tried,
                                        "mass_closure_frac": closure}}
        return failure("column did not converge (stock method and three alternative initialisations)", time.perf_counter() - t0,
                       {"engine": "chemsep", "T_feed_K": T_feed, "attempts": tried})
