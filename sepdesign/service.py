"""
SolveService: one simulator backend + a thread-safe cache of column results + a log of real solves. Plug `service.column` into DesignEnv.

    svc = make_service()                 # backend from $SIM_BACKEND: "chemsep" (default, needs ChemSep) or "mock" (development only)
    env = make_env(task, svc, budget=120)

Safe to share between threads and agents: identical columns are solved once. `svc.backend_name` records which backend produced results.
"""
import os
import threading
import time
from copy import deepcopy

import numpy as np

from sepdesign.env import DesignEnv, make_query
from sepdesign.tasks import Economics, cost_config


class InfrastructureError(RuntimeError):
    """Backend execution failed, rather than returning solver nonconvergence."""


class SolveService:
    def __init__(self, backend):
        self.backend = backend
        self.backend_name = getattr(backend, "name", "backend")
        cm = getattr(backend, "cost_model", None)
        self.cost_config = (getattr(cm, "em", 1.0), getattr(cm, "cm", 1.0)) if cm is not None else None     # None: backend without a cost model
        self.cache, self.log = {}, []
        self.lock = threading.Lock()
        self.call_lock = threading.Lock()
        self.events = []
        self.raw_responses = []

    def column(self, stream, action):
        """column_fn for DesignEnv: (stream, settings) -> {"ok", "tac", "tops", "bottoms", ...}."""
        # Conservative single worker: cache lookup and solve are one critical section.
        # This also protects local backends that cannot safely overlap calls.
        queued = time.monotonic()
        with self.call_lock:
            start = time.monotonic()
            q = make_query(stream.flows, stream.T, stream.P, *action)
            hit = q in self.cache
            try:
                out = self.cache[q] if hit else self._column_uncached(q)
                if out.get('error_category') == 'infrastructure':
                    raise InfrastructureError(out['error'])
                return deepcopy(out)
            finally:
                self.events.append({'cache_hit': hit, 'backend_call': not hit,
                                    'queue_s': start - queued, 'solver_s': time.monotonic() - start})

    def _column_uncached(self, q):
        flows, T, P, n, rr, rb, dp = q[:7]
        case = {"feed_flows_mol_s": list(flows), "temperature_K": T, "pressure_Pa": P, "n_stages": n, "reflux_ratio": rr, "reboil_ratio": rb,
                "pressure_drop_fraction": dp}
        if len(q) > 7:                                   # side draw (Hydrocarbon-16 V3)
            case["side_draw"] = {"stage": q[7][0], "phase": q[7][1], "fraction": q[7][2]}
        start = time.monotonic()
        try:
            res = self.backend.solve_column(case)
        except Exception as exc:
            res = {'success': False, 'error': type(exc).__name__, 'error_category': 'infrastructure', 'runtime_s': time.monotonic()-start}
        self.raw_responses.append(deepcopy(res))
        if res["success"] and res.get("tac_usd_per_year") is not None and np.isfinite(res["tac_usd_per_year"]) and res["tac_usd_per_year"] >= 0:
            out = {"ok": True, "tac": res["tac_usd_per_year"] if res["tac_usd_per_year"] is not None else 0.0,
                   "tops": {"flows": res["tops"]["flows"], "T": res["tops"]["T_K"], "P": res["tops"]["P_Pa"]},
                   "bottoms": {"flows": res["bottoms"]["flows"], "T": res["bottoms"]["T_K"], "P": res["bottoms"]["P_Pa"]},
                   "qc": res["condenser_duty_W"], "qr": res["reboiler_duty_W"], "solve_s": res["runtime_s"]}
            if res.get("cost") is not None:
                out["cost"] = res["cost"]
            if res.get("side") is not None:
                out["side"] = {"flows": res["side"]["flows"], "T": res["side"]["T_K"], "P": res["side"]["P_Pa"]}
        else:
            out = {"ok": False, "error": res.get("error") or "solve failed or missing/invalid annualized cost", "solve_s": res["runtime_s"]}
        if res.get('error_category') == 'infrastructure':
            out['error_category'] = 'infrastructure'
        with self.lock:
            self.cache[q] = out
            self.log.append((res["runtime_s"], bool(out["ok"]), (res.get("diagnostics") or {}).get("solved_by")))
        return out

    def mix(self, streams):
        """(T, P) of the adiabatic mix of [(flows, T, P), ...] at the lowest pressure, with the backend's thermodynamics when it has them."""
        P = min(float(p) for _, _, p in streams)
        thermo = getattr(getattr(self.backend, "family", None), "thermo", None)
        if thermo is not None:
            T = thermo.mix_T(streams, P)
            if not np.isfinite(T) or T <= 0:
                raise ValueError('Adiabatic mixing did not produce a valid temperature')
            return float(T), P
        if self.backend_name != 'mock':
            raise ValueError('Thermodynamic mixing is unavailable for this backend')
        N = sum(float(np.sum(f)) for f, _, _ in streams)
        return sum(float(np.sum(f)) * float(t) for f, t, _ in streams) / max(N, 1e-12), P

    def stats(self):
        if not self.log:
            return {"solves": 0, "backend": self.backend_name}
        t = np.array([x[0] for x in self.log])
        return {"backend": self.backend_name, "solves": len(self.log), "failed": int(sum(1 for x in self.log if not x[1])),
                "median_s": float(np.median(t)), "mean_s": float(t.mean()),
                "retry_rescued": int(sum(1 for x in self.log if x[1] and x[2] not in (None, "stock")))}


def make_service(kind=None, names=None, task=None, **kw):
    """kind: 'chemsep' (default) or 'mock'; $SIM_BACKEND overrides the default.
    task: if given, the components and the cost multipliers (energy, capital) are taken from it. Pass task= for any task with an "economics" block
    (Hydrocarbon-16 V2); make_env refuses a service whose cost multipliers differ from the task's. names: component names (default: Hydrocarbon-12)."""
    from sepdesign.hc12 import HC12
    kind = (kind or os.environ.get("SIM_BACKEND") or "chemsep").lower()
    names = names or (list(task["components"]) if task is not None else None)
    em, cm = cost_config(task) if task is not None else (1.0, 1.0)
    if kind == "mock":
        from sepdesign.mock_backend import MockBackend
        svc = SolveService(MockBackend(names=names))
        svc.cost_config = None
        return svc
    if kind == "chemsep":
        from sepdesign.chemsep_backend import ChemSepBackend
        from sepdesign.cost_model import CostModel
        from sepdesign.families import pr_family
        return SolveService(ChemSepBackend(pr_family(names or HC12), cost_model=CostModel(energy_multiplier=em, capital_multiplier=cm), **kw))
    raise ValueError(f"unknown simulator backend {kind!r} (use 'chemsep' or 'mock')")


def make_env(task, service, budget=120, max_columns=None):
    need = cost_config(task)
    have = getattr(service, "cost_config", None)
    if have is not None and tuple(have) != need:
        raise ValueError(f"the simulator service uses cost multipliers (energy, capital) = {tuple(have)} but task {task['task_id']} requires {need}: "
                         "build the service with make_service(..., task=task)")
    return DesignEnv(Economics(task), service.column, solve_budget=budget, max_columns=max_columns, names=list(task["components"]),
                     mix_fn=getattr(service, "mix", None))
