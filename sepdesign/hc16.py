"""
Hydrocarbon-16 V2: sixteen light hydrocarbons, richer economics, expensive plant. A separate task family from Hydrocarbon-12 (which is unchanged).

What differs from Hydrocarbon-12:
  * 16 components: the twelve of Hydrocarbon-12 plus propylene (5.6 K from propane: the classic hard C3 split), 3-methylpentane (3 K from
    2-methylpentane), cyclohexane and n-nonane. A sharp-split sequence of 16 products can be ordered in 9,694,845 ways (58,786 for 12).
  * Premium grade: a stream at >= 99% of one component sells at 1.2x that component's price (>= 95% sells at the base price).
  * Blends: a stream that is >= 95% made of the members of a blend (for example isobutane + n-butane) sells as that blend at 85% of the members'
    mean price, without separating the members. A stream that qualifies both as a pure product and as a blend sells at the higher value.
  * Cost: the annualised cost of every column uses energy prices x2 and capital cost x10 relative to the calibrated cost model.
  * Feed pressure varies by task (10 to 25 bar); the feed temperature is 400 K.

Boiling points (K): ethane 184.6, propylene 225.5, propane 231.0, isobutane 261.3, n-butane 272.7, isopentane 301.0, n-pentane 309.2,
2,2-dimethylbutane 322.9, 2-methylpentane 333.4, 3-methylpentane 336.4, n-hexane 341.9, methylcyclopentane 345.0, cyclohexane 353.9,
n-heptane 371.6, n-octane 398.8, n-nonane 424.0.
"""
import hashlib
import json

import numpy as np

from sepdesign.tasks import make_task

# name (as in ChemSep's library) -> (normal boiling point K, molecular weight g/mol); the list is in boiling-point order
COMPONENT_DATA = {
    "Ethane": (184.55, 30.07), "Propylene": (225.45, 42.081), "Propane": (231.02, 44.097), "Isobutane": (261.34, 58.123),
    "N-butane": (272.66, 58.123), "Isopentane": (300.99, 72.15), "N-pentane": (309.22, 72.15), "2,2-dimethylbutane": (322.87, 86.177),
    "2-methylpentane": (333.40, 86.177), "3-methylpentane": (336.40, 86.177), "N-hexane": (341.88, 86.177), "Methylcyclopentane": (344.98, 84.161),
    "Cyclohexane": (353.93, 84.161), "N-heptane": (371.57, 100.2), "N-octane": (398.82, 114.23), "N-nonane": (423.97, 128.259)}
HC16 = list(COMPONENT_DATA)
TB16 = np.array([COMPONENT_DATA[c][0] for c in HC16])
MW16 = np.array([COMPONENT_DATA[c][1] for c in HC16])
BASE_X = np.array([.02, .05, .10, .07, .10, .09, .08, .03, .07, .05, .08, .03, .04, .08, .06, .05])
PRICE_KG = np.array([0.125, 0.40, 0.204, 0.272, 0.249, 0.545, 0.545, 0.62, 0.55, 0.55, 0.50, 0.58, 0.60, 0.50, 0.48, 0.45])     # $/kg
FEED_TOTAL_MOL_S = 3300.0
FEED_T = 400.0
P_RANGE_BAR = (10.0, 25.0)
ACTION_BOUNDS = {"reflux_ratio": [0.1, 30.0], "reboil_ratio": [0.1, 30.0]}
ECONOMICS = {
    "premium": {"purity": 0.99, "multiplier": 1.2},
    "groups": [
        {"name": "C3 mix", "members": ["Propylene", "Propane"], "min_fraction": 0.95, "discount": 0.85},
        {"name": "C4 mix", "members": ["Isobutane", "N-butane"], "min_fraction": 0.95, "discount": 0.85},
        {"name": "C5 mix", "members": ["Isopentane", "N-pentane"], "min_fraction": 0.95, "discount": 0.85},
        {"name": "C6 paraffin mix", "members": ["2,2-dimethylbutane", "2-methylpentane", "3-methylpentane", "N-hexane"], "min_fraction": 0.95, "discount": 0.85},
        {"name": "C6 naphthene mix", "members": ["Methylcyclopentane", "Cyclohexane"], "min_fraction": 0.95, "discount": 0.85}],
    "cost": {"energy_multiplier": 2.0, "capital_multiplier": 10.0}}
N_TASKS = {"dev": 4, "test": 12}
SEEDS = {"dev": 1601, "test": 1602}


def hc16v2_tasks(split="dev"):
    """Tasks of a split: composition ~ Dirichlet around BASE_X (concentration 60), prices x lognormal (sigma 0.15), feed pressure uniform 10-25 bar."""
    rng = np.random.default_rng(SEEDS[split])
    out = []
    for i in range(N_TASKS[split]):
        x = np.maximum(rng.dirichlet(BASE_X * 60.0), 0.004)
        x = x / x.sum()
        px = PRICE_KG * np.exp(rng.normal(0.0, 0.15, len(x)))
        p_bar = float(np.round(rng.uniform(*P_RANGE_BAR) * 2) / 2)
        out.append(make_task(f"hc16v2_{split}_{i:03d}", HC16, list(FEED_TOTAL_MOL_S * x), list(px * MW16 / 1000.0), purity=0.95, temperature=FEED_T,
                             pressure=p_bar * 1e5, action_bounds=ACTION_BOUNDS, economics=ECONOMICS, meta={"family": "hc16v2", "split": split}))
    return out


V3_COST = {"energy_multiplier": 6.0, "capital_multiplier": 10.0}     # V3: energy x6 (V2: x2) so heat saving matters; see docs/TASK_V3.md


def hc16v3_tasks(split="dev"):
    """Hydrocarbon-16 V3: the same feeds, prices and economics as V2 (same seeds), plus side draws (a third outlet from the middle of a column)
    and double-effect columns (one split by two columns at different pressures, heat-integrated), at a higher energy price (V3_COST)."""
    out = []
    for t in hc16v2_tasks(split):
        t = json.loads(json.dumps(t))
        t["task_id"] = t["task_id"].replace("hc16v2", "hc16v3")
        t["meta"]["family"] = "hc16v3"
        t["levers"] = {"side_draw": True, "double_effect": True}
        t["economics"]["cost"] = dict(V3_COST)
        out.append(t)
    return out


def task_hash(tasks):
    return hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest()
