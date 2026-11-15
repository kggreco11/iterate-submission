"""
Task specification and economics.

A task fixes the problem: components, feed flows (mol/s), feed temperature and pressure, product prices ($/mol), required purity.
A stream is worth money only if it is nearly pure:

    value(stream)  = max(flow) x price[dominant component] x seconds per year     if max(flow) / sum(flow) >= purity, else 0
    reward         = (sum of product values - sum of column annual costs) / reward_norm
    reward_norm    = max over components of (feed flow x price x seconds per year)    (the most valuable pure stream in the feed)

A task may carry an optional "economics" block (Hydrocarbon-16 V2 uses it); tasks without it behave exactly as above:
    "premium": {"purity": 0.99, "multiplier": 1.2}     a stream at >= that purity of one component sells at multiplier x the price
    "groups":  [{"name", "members": [components], "min_fraction": 0.95, "discount": 0.85}]
               a stream whose members together make up >= min_fraction of its moles sells as a blend: (member moles) x discount x (mean member
               price); a stream that qualifies both as a pure product and as a blend sells at the higher value
    "cost":    {"energy_multiplier", "capital_multiplier"}   scale the energy and capital parts of every column's annual cost (see cost_model)
"""
import numpy as np

DEFAULT_ACTION_BOUNDS = {"n_stages": (5, 200), "reflux_ratio": (0.1, 10.0), "reboil_ratio": (0.1, 10.0), "pressure_drop_fraction": (0.0, 0.9)}


def make_task(task_id, components, feed_flows, prices, purity=0.95, temperature=298.15, pressure=101325.0, hours=8000.0, stream_limit=None,
              action_bounds=None, meta=None, economics=None, levers=None):
    feed = [round(float(f), 6) for f in feed_flows]
    assert len(components) == len(feed) == len(prices), "one feed flow and one price per component"
    task = {"task_id": task_id, "components": list(components), "feed_flows_mol_s": feed, "temperature_K": float(temperature),
            "pressure_Pa": float(pressure), "prices_usd_per_mol": [float(p) for p in prices], "required_purity": float(purity),
            "annual_operating_hours": float(hours), "stream_limit": int(stream_limit) if stream_limit else 3 * len(feed),
            "min_recovery_fraction": 0.01, "action_bounds": action_bounds or {}, "meta": meta or {}}
    if economics:
        task["economics"] = economics
    if levers:                                  # optional extra decisions, e.g. {"side_draw": true} (Hydrocarbon-16 V3)
        task["levers"] = dict(levers)
    return task


def action_bounds(task):
    """(low, high) per column setting: defaults, overridden by the task's optional 'action_bounds'."""
    out = dict(DEFAULT_ACTION_BOUNDS)
    for k, v in (task.get("action_bounds") or {}).items():
        assert k in out, f"unknown setting {k!r}"
        lo, hi = float(v[0]), float(v[1])
        assert lo < hi
        out[k] = (lo, hi)
    return out


def cost_config(task):
    """(energy multiplier, capital multiplier) the task requires of the simulator's cost model."""
    c = (task.get("economics") or {}).get("cost") or {}
    return float(c.get("energy_multiplier", 1.0)), float(c.get("capital_multiplier", 1.0))


def simulator_budget(task, override=None, required=False):
    """Read an optional per-agent experiment allowance; CLI overrides are explicit."""
    settings = task.get('experiment') or {}
    if not isinstance(settings, dict):
        raise ValueError('Task experiment configuration must be an object')
    value = override if override is not None else settings.get('simulator_budget_per_agent')
    if value is None:
        if required:
            raise ValueError('Set task experiment.simulator_budget_per_agent or supply --budget')
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError('simulator_budget_per_agent must be a positive integer')
    return value


class Economics:
    def __init__(self, task):
        self.task = task
        comps = list(task["components"])
        self.prices = np.array(task["prices_usd_per_mol"], dtype=float)
        self.purity = float(task["required_purity"])
        self.seconds = float(task["annual_operating_hours"]) * 3600.0
        self.feed = np.array(task["feed_flows_mol_s"], dtype=float)
        self.T0, self.P0 = float(task["temperature_K"]), float(task["pressure_Pa"])
        self.min_recovery = self.feed * float(task["min_recovery_fraction"])
        self.stream_limit = int(task["stream_limit"])
        self.n = len(self.feed)
        ec = task.get("economics") or {}
        prem = ec.get("premium")
        self.premium_purity = float(prem["purity"]) if prem else None
        self.premium_mult = float(prem["multiplier"]) if prem else 1.0
        self.groups = []                                              # (name, member indices, min fraction, price $/mol)
        for g in ec.get("groups") or []:
            idx = np.array([comps.index(m) for m in g["members"]])
            self.groups.append((g["name"], idx, float(g.get("min_fraction", self.purity)), float(g["discount"]) * float(self.prices[idx].mean())))
        single = self.feed * self.prices * self.seconds          # value of each component sold pure (base grade)
        self.reward_norm = float(single.max())
        self.max_total_revenue = float(single.sum()) * self.premium_mult      # ceiling: every component pure and in the premium grade

    @property
    def upper_bound_reward(self):
        """Reward if every component were sold pure (premium grade where offered) at no cost: an unreachable ceiling, not a target."""
        return self.max_total_revenue / self.reward_norm

    def classify(self, flows):
        """(value $/yr, kind) of a stream sold as it is. kind: 'premium', 'pure', 'blend: <name>' or 'none'."""
        flows = np.asarray(flows, dtype=float)
        s = flows.sum()
        if s <= 0:
            return 0.0, "none"
        best, kind = 0.0, "none"
        i = int(np.argmax(flows))
        x = flows[i] / s
        if x >= self.purity:
            mult = self.premium_mult if (self.premium_purity is not None and x >= self.premium_purity) else 1.0
            best, kind = float(flows[i] * self.prices[i] * self.seconds * mult), ("premium" if mult > 1.0 else "pure")
        for name, idx, minf, price in self.groups:
            f = float(flows[idx].sum())
            if f / s >= minf and f * price * self.seconds > best:
                best, kind = f * price * self.seconds, f"blend: {name}"
        return best, kind

    def stream_value(self, flows):
        return self.classify(flows)[0]

    def negligible(self, flows):
        flows = np.asarray(flows, dtype=float)
        return bool(flows.max() <= self.min_recovery[int(flows.argmax())])

    def describe_rules(self):
        """Plain-language statement of how streams are valued (for the agent's brief)."""
        lines = [f"A stream earns money only if one component makes up at least {self.purity:.0%} of its moles; then it is worth (flow of that "
                 f"component) x (its price) x {self.seconds / 3600:.0f} hours/year. Impure streams are worth nothing."]
        if self.premium_purity is not None:
            lines.append(f"PREMIUM GRADE: if that component makes up at least {self.premium_purity:.0%} of the stream, it sells at {self.premium_mult:g} times its price.")
        if self.groups:
            lines.append("BLENDS: a stream made up at least 95% of the members of a blend sells as that blend, without separating the members, "
                         "at a discount to the members' average price. Blends: " + "; ".join(
                             f"{n} = {' + '.join(self.task['components'][i] for i in idx)} (sells at {price / float(self.prices[idx].mean()):.0%} of their mean price)"
                             for n, idx, _, price in self.groups) + ". A stream that qualifies as both a pure product and a blend sells at the higher value.")
        em, cm = cost_config(self.task)
        if (em, cm) != (1.0, 1.0):
            lines.append("COST LEVEL: this is an expensive-plant scenario (energy and equipment costs are well above the usual level), so extra columns "
                         "and tall, high-reflux columns cost a lot.")
        return "\n".join(lines)
