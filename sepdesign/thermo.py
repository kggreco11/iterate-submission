"""
Peng-Robinson (1976) thermodynamics in plain numpy: TP flash (negative-flash successive substitution) and the isenthalpic valve.

The column solver needs the state of the feed after the pressure-reducing valve in front of the column. This module computes it with the same
equation of state, constants and binary interaction table as the column itself, so the feed is consistent with the column's thermodynamics.

Model: PR-76 cubic with classical mixing rules and kij; ideal-gas Cp from ChemSep's correlations (equation 16: A + exp(B/T + C + D T + E T^2),
or the polynomial forms 4 and 100, J/kmol/K); ideal-gas reference 298.15 K; PR departure enthalpy; no formation enthalpies.
"""
import numpy as np

R = 8.314462618
T_REF = 298.15
SQ2 = np.sqrt(2.0)
_GL_X, _GL_W = np.polynomial.legendre.leggauss(12)


class PRThermo:
    """spec: names, Tc (K), Pc (Pa), omega, cp = [(equation number, [A..E])], kij matrix (n x n)."""

    def __init__(self, spec):
        self.names = list(spec["names"])
        self.n = len(self.names)
        self.Tc = np.array(spec["Tc"], float)
        self.Pc = np.array(spec["Pc"], float)
        self.omega = np.array(spec["omega"], float)
        self.cp_eq = np.array([e for e, _ in spec["cp"]], int)
        self.cp = np.array([c for _, c in spec["cp"]], float)
        assert set(self.cp_eq) <= {4, 16, 100}, f"unsupported ideal-gas Cp equation numbers {set(self.cp_eq)}"
        self.kij = np.array(spec["kij"], float)
        self.kappa = 0.37464 + 1.54226 * self.omega - 0.26992 * self.omega ** 2
        self.ac = 0.45724 * R ** 2 * self.Tc ** 2 / self.Pc
        self.bi = 0.0778 * R * self.Tc / self.Pc

    # ---- ideal gas -------------------------------------------------------------------------------------------------------
    def h_ig(self, T):
        """Ideal-gas molar enthalpy of each component relative to 298.15 K, J/mol."""
        A, B, C, D, E = (self.cp[:, i][:, None] for i in range(5))
        Ts = 0.5 * (T - T_REF) * _GL_X[None, :] + 0.5 * (T + T_REF)
        e16 = A + np.exp(B / Ts + C + D * Ts + E * Ts ** 2)
        poly = A + B * Ts + C * Ts ** 2 + D * Ts ** 3 + E * Ts ** 4
        cp = np.where((self.cp_eq == 16)[:, None], e16, poly)
        return 0.5 * (T - T_REF) * (cp * _GL_W[None, :]).sum(1) / 1000.0

    # ---- EOS -------------------------------------------------------------------------------------------------------------
    def _a_terms(self, T):
        alpha = (1.0 + self.kappa * (1.0 - np.sqrt(T / self.Tc))) ** 2
        return self.ac * alpha, -self.ac * self.kappa * np.sqrt(alpha) / np.sqrt(T * self.Tc)

    def _mix(self, x, T):
        a, da = self._a_terms(T)
        sa = np.sqrt(np.outer(a, a))
        aij = (1.0 - self.kij) * sa
        daij = (1.0 - self.kij) * (np.outer(da, a) + np.outer(a, da)) / (2.0 * sa)
        ax = aij @ x
        return float(x @ ax), float(x @ daij @ x), ax, float(x @ self.bi)

    @staticmethod
    def _roots(A, B):
        r = np.roots([1.0, -(1.0 - B), A - 3.0 * B * B - 2.0 * B, -(A * B - B * B - B ** 3)])
        r = np.sort(r[np.abs(r.imag) < 1e-9].real)
        return r[r > B + 1e-12]

    def phase(self, x, T, P, vapour):
        """(Z, ln phi_i, H_departure J/mol, number of real roots) for the vapour-like (largest) or liquid-like (smallest) root."""
        a, dadT, ax, b = self._mix(x, T)
        A = a * P / (R * T) ** 2
        B = b * P / (R * T)
        roots = self._roots(A, B)
        if len(roots) == 0:
            roots = np.array([max(1.0, B + 1e-6)])
        Z = roots[-1] if vapour else roots[0]
        L = np.log((Z + (1 + SQ2) * B) / (Z + (1 - SQ2) * B))
        lnphi = self.bi / b * (Z - 1.0) - np.log(Z - B) - A / (2 * SQ2 * B) * (2.0 * ax / a - self.bi / b) * L
        hdep = R * T * (Z - 1.0) + (T * dadT - a) / (2 * SQ2 * b) * L
        return float(Z), lnphi, float(hdep), len(roots)

    # ---- flash -----------------------------------------------------------------------------------------------------------
    @staticmethod
    def _rr_beta(z, K):
        """Rachford-Rice root of the negative flash (beta may fall outside 0..1)."""
        up, dn = K > 1.0, K < 1.0
        lo = float(np.max(1.0 / (1.0 - K[up]))) if up.any() else -1e6
        hi = float(np.min(1.0 / (1.0 - K[dn]))) if dn.any() else 1e6
        span = hi - lo
        a, b = lo + 1e-12 * span, hi - 1e-12 * span
        f = lambda be: float(np.sum(z * (K - 1.0) / (1.0 + be * (K - 1.0))))   # noqa: E731
        for _ in range(200):
            m = 0.5 * (a + b)
            if f(m) > 0:
                a = m
            else:
                b = m
            if b - a < 1e-14:
                break
        return 0.5 * (a + b)

    def flash(self, z, T, P, max_iter=500):
        """TP flash. Returns dict(beta, x, y, H): vapour fraction (0 = liquid, 1 = vapour), phase compositions, enthalpy in J per mol feed."""
        z = np.maximum(np.asarray(z, float), 1e-30)
        z = z / z.sum()
        K = self.Pc / P * np.exp(5.373 * (1.0 + self.omega) * (1.0 - self.Tc / T))
        beta, trivial = None, False
        for _ in range(max_iter):
            if np.max(np.abs(np.log(K))) < 1e-9:
                trivial = True
                break
            beta = self._rr_beta(z, K)
            x = z / (1.0 + beta * (K - 1.0))
            y = K * x
            x, y = np.abs(x) / np.abs(x).sum(), np.abs(y) / np.abs(y).sum()
            _, lnphi_l, _, _ = self.phase(x, T, P, vapour=False)
            _, lnphi_v, _, _ = self.phase(y, T, P, vapour=True)
            Kn = np.exp(lnphi_l - lnphi_v)
            done = np.max(np.abs(np.log(Kn / K))) < 1e-12
            K = Kn
            if done:
                break
        hig = self.h_ig(T)
        if trivial or beta is None or beta <= 0.0 or beta >= 1.0:
            Zl, lnl, hl, nl = self.phase(z, T, P, vapour=False)
            Zv, lnv, hv, nv = self.phase(z, T, P, vapour=True)
            if not trivial and beta is not None and nl > 1:
                vap = beta >= 1.0
            else:
                vap = (Zv > 0.5) if nl == 1 else (float(z @ lnv) < float(z @ lnl))
            return {"beta": 1.0 if vap else 0.0, "x": z, "y": z, "H": float(z @ hig) + (hv if vap else hl)}
        x = z / (1.0 + beta * (K - 1.0))
        y = K * x
        x, y = x / x.sum(), y / y.sum()
        _, _, hl, _ = self.phase(x, T, P, vapour=False)
        _, _, hv, _ = self.phase(y, T, P, vapour=True)
        H = beta * (float(y @ hig) + hv) + (1.0 - beta) * (float(x @ hig) + hl)
        return {"beta": float(beta), "x": x, "y": y, "H": float(H)}

    # ---- adiabatic mixing ---------------------------------------------------------------------------------------------------
    def mix_T(self, streams, P_out, tol=1e-6):
        """Temperature of the adiabatic mix of streams [(flows mol/s, T K, P Pa), ...] at P_out (each stream let down to P_out through a valve
        first). Returns nan if no temperature in range matches the total enthalpy."""
        tot = sum(np.asarray(f, float) for f, _, _ in streams)
        N = float(tot.sum())
        if N <= 0:
            return float("nan")
        H = sum(float(np.sum(f)) * self.flash(np.asarray(f, float) / max(float(np.sum(f)), 1e-30), T, P)["H"] for f, T, P in streams if np.sum(f) > 0)
        z = tot / N
        T0 = sum(float(np.sum(f)) * T for f, T, _ in streams) / N
        g = lambda T: self.flash(z, T, P_out)["H"] * N - H   # noqa: E731
        lo, hi = T0 - 30.0, T0 + 30.0
        glo, ghi = g(lo), g(hi)
        k = 0
        while glo > 0 and k < 6:
            lo -= 40.0
            glo = g(lo)
            k += 1
        k = 0
        while ghi < 0 and k < 6:
            hi += 40.0
            ghi = g(hi)
            k += 1
        if glo > 0 or ghi < 0:
            return float("nan")
        side, mid = 0, 0.5 * (lo + hi)
        for _ in range(80):                              # Illinois regula falsi
            mid = hi - ghi * (hi - lo) / (ghi - glo)
            gm = g(mid)
            if abs(hi - lo) < tol or gm == 0.0:
                return float(mid)
            if gm * ghi > 0:
                hi, ghi = mid, gm
                if side == 1:
                    glo *= 0.5
                side = 1
            else:
                lo, glo = mid, gm
                if side == -1:
                    ghi *= 0.5
                side = -1
        return float(mid)

    # ---- isenthalpic valve -----------------------------------------------------------------------------------------------
    def valve_T(self, flows, T_in, P_in, P_out, tol=1e-6):
        """Outlet temperature of an isenthalpic expansion (enthalpy rises with T at fixed P and composition)."""
        flows = np.asarray(flows, float)
        if P_out >= P_in * (1.0 - 1e-12):
            return float(T_in)
        z = flows / flows.sum()
        H_in = self.flash(z, T_in, P_in)["H"]
        g = lambda T: self.flash(z, T, P_out)["H"] - H_in   # noqa: E731
        lo, hi = T_in - 40.0, T_in + 5.0
        glo, ghi = g(lo), g(hi)
        k = 0
        while glo > 0 and k < 6:
            hi, ghi = lo, glo
            lo -= 60.0
            glo = g(lo)
            k += 1
        if glo > 0 or ghi < 0:
            return float("nan")
        side = 0
        for _ in range(60):                              # Illinois regula falsi
            mid = hi - ghi * (hi - lo) / (ghi - glo)
            gm = g(mid)
            if abs(hi - lo) < tol or gm == 0.0:
                return float(mid)
            if gm * ghi > 0:
                hi, ghi = mid, gm
                if side == 1:
                    glo *= 0.5
                side = 1
            else:
                lo, glo = mid, gm
                if side == -1:
                    ghi *= 0.5
                side = -1
        return float(mid)
