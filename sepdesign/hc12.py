"""
Hydrocarbon-12: twelve light hydrocarbons (ethane to n-octane) to be separated into pure products by a tree of distillation columns.

Boiling points (K): ethane 184.6, propane 231.0, isobutane 261.3, n-butane 272.7, isopentane 301.0, n-pentane 309.2, 2,2-dimethylbutane 322.9,
2-methylpentane 333.4, n-hexane 341.9, methylcyclopentane 345.0, n-heptane 371.6, n-octane 398.8. Several neighbours are close boilers
(isobutane/n-butane 11 K, isopentane/n-pentane 8 K, 2-methylpentane/n-hexane 8 K, n-hexane/methylcyclopentane 3 K), which makes the
separations expensive. A sharp-split sequence of 12 products can be ordered in 58,786 ways, before choosing stages, reflux, boil-up and pressure
for each of the 11 or more columns.

A task is a feed (about 3.3 kmol/s at 400 K and 17.6 bar, composition and prices varying by task), a 95% purity requirement, and the reward
(product value minus annual column cost) / (value of the single most valuable pure stream in the feed).
"""
import hashlib
import json

import numpy as np

from sepdesign.tasks import make_task

HC12 = ["Ethane", "Propane", "Isobutane", "N-butane", "Isopentane", "N-pentane", "2,2-dimethylbutane", "2-methylpentane", "N-hexane",
        "Methylcyclopentane", "N-heptane", "N-octane"]
TB_K = np.array([184.55, 231.02, 261.34, 272.66, 300.99, 309.22, 322.87, 333.40, 341.88, 344.98, 371.57, 398.82])
MW = np.array([30.07, 44.097, 58.123, 58.123, 72.15, 72.15, 86.177, 86.177, 86.177, 84.161, 100.2, 114.23])
BASE_X = np.array([.02, .12, .08, .12, .10, .10, .03, .09, .10, .04, .12, .08])
PRICE_KG = np.array([0.125, 0.204, 0.272, 0.249, 0.545, 0.545, 0.62, 0.55, 0.50, 0.58, 0.50, 0.48])      # $/kg
FEED_TOTAL_MOL_S = 3300.0
FEED_T, FEED_P = 400.0, 17.6e5
ACTION_BOUNDS = {"reflux_ratio": [0.1, 30.0], "reboil_ratio": [0.1, 30.0]}
N_TASKS = {"dev": 4, "test": 12}
SEEDS = {"dev": 1201, "test": 1202}


def hc12_tasks(split="dev"):
    """The tasks of a split: feed composition ~ Dirichlet around BASE_X (concentration 60), prices x lognormal (sigma 0.15) per component."""
    rng = np.random.default_rng(SEEDS[split])
    out = []
    for i in range(N_TASKS[split]):
        x = np.maximum(rng.dirichlet(BASE_X * 60.0), 0.004)
        x = x / x.sum()
        px = PRICE_KG * np.exp(rng.normal(0.0, 0.15, len(x)))
        out.append(make_task(f"hc12_{split}_{i:03d}", HC12, list(FEED_TOTAL_MOL_S * x), list(px * MW / 1000.0), purity=0.95, temperature=FEED_T,
                             pressure=FEED_P, action_bounds=ACTION_BOUNDS, meta={"family": "hc12", "split": split}))
    return out


def task_hash(tasks):
    return hashlib.sha256(json.dumps(tasks, sort_keys=True).encode()).hexdigest()
