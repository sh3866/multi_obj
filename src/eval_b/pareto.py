"""Pareto archive (Component D) + hypervolume.

A candidate carries a per-axis score vector (higher = better on every axis). The
archive keeps only non-dominated candidates (no convergence to one). The final
output is the front; its quality is measured by dominated hypervolume.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional


def dominates(a: Dict[str, float], b: Dict[str, float], axes: List[str]) -> bool:
    """a dominates b: >= on all axes and > on at least one."""
    ge_all = all(a.get(k, 0) >= b.get(k, 0) for k in axes)
    gt_any = any(a.get(k, 0) > b.get(k, 0) for k in axes)
    return ge_all and gt_any


class ParetoArchive:
    def __init__(self, axes: List[str], cap: int = 8):
        self.axes = axes
        self.cap = cap
        self.items: List[dict] = []   # each: {"id","scores",...payload}

    def add(self, item: dict) -> bool:
        """Insert if non-dominated. Returns True if it entered the front."""
        s = item["scores"]
        # dominated by an existing member -> reject
        for m in self.items:
            if dominates(m["scores"], s, self.axes):
                return False
        # remove members this one dominates
        self.items = [m for m in self.items if not dominates(s, m["scores"], self.axes)]
        self.items.append(item)
        # cap: drop the lowest-sum member if over capacity
        if len(self.items) > self.cap:
            self.items.sort(key=lambda m: sum(m["scores"].get(k, 0) for k in self.axes),
                            reverse=True)
            self.items = self.items[: self.cap]
        return True

    def best(self) -> Optional[dict]:
        if not self.items:
            return None
        return max(self.items,
                   key=lambda m: sum(m["scores"].get(k, 0) for k in self.axes))

    def front(self) -> List[dict]:
        return list(self.items)


def hypervolume_mc(points: List[Dict[str, float]], axes: List[str],
                   ref: Optional[Dict[str, float]] = None,
                   hi: float = 1.0, n: int = 200000, seed: int = 0) -> float:
    """Monte-Carlo dominated hypervolume in [ref, hi]^d (scores assumed normalized)."""
    if not points:
        return 0.0
    ref = ref or {k: 0.0 for k in axes}
    rng = random.Random(seed)
    d = len(axes)
    box = 1.0
    for k in axes:
        box *= (hi - ref[k])
    hits = 0
    for _ in range(n):
        p = {k: ref[k] + (hi - ref[k]) * rng.random() for k in axes}
        for q in points:
            if all(q.get(k, 0) >= p[k] for k in axes):
                hits += 1
                break
    return box * hits / n
