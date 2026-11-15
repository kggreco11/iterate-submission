"""
Task families. Hydrocarbon-12 (hc12) is the original task set; Hydrocarbon-16 V2 (hc16v2) adds components, premium grade, blends and an expensive-plant
cost level (sepdesign/hc16.py). Scripts pick the family with --family or $TASK_FAMILY (default hc12).
"""
import os

from sepdesign.hc12 import hc12_tasks
from sepdesign.hc16 import hc16v2_tasks, hc16v3_tasks

FAMILIES = {"hc12": hc12_tasks, "hc16v2": hc16v2_tasks, "hc16v3": hc16v3_tasks}


def get_tasks(split="dev", family=None):
    family = family or os.environ.get("TASK_FAMILY", "hc12")
    if family not in FAMILIES:
        raise ValueError(f"unknown task family {family!r}; choose from {sorted(FAMILIES)}")
    return FAMILIES[family](split)


def find_task(task_id):
    """The task with this id (the id starts with its family and split: 'hc16v2_dev_001')."""
    family, split = task_id.split("_")[0], task_id.split("_")[1]
    return next(t for t in FAMILIES[family](split) if t["task_id"] == task_id)
