"""Bradley-Terry fitting (Zermelo/MM algorithm) + winrate matrix + paired stats.

No external deps beyond stdlib; exact binomial sign test for pairwise arm
comparisons (paired by task).
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, List, Tuple


def fit_bt(wins: Dict[Tuple[str, str], int], iters: int = 200) -> Dict[str, float]:
    """wins[(i, j)] = number of times i beat j. Returns strengths normalized to
    geometric mean 1 (log-BT scores comparable across fits)."""
    players = sorted({p for pair in wins for p in pair})
    if not players:
        return {}
    p = {x: 1.0 for x in players}
    n_ij = defaultdict(int)
    w_i = defaultdict(int)
    for (i, j), w in wins.items():
        n_ij[(i, j)] += w
        n_ij[(j, i)] += 0
        w_i[i] += w
    for _ in range(iters):
        new = {}
        for i in players:
            denom = 0.0
            for j in players:
                if i == j:
                    continue
                n = n_ij.get((i, j), 0) + n_ij.get((j, i), 0)
                if n:
                    denom += n / (p[i] + p[j])
            new[i] = (w_i[i] / denom) if denom > 0 else p[i]
        # normalize: geometric mean = 1
        gm = math.exp(sum(math.log(max(v, 1e-12)) for v in new.values()) / len(new))
        p = {k: v / gm for k, v in new.items()}
    return p


def winrate_matrix(results: List[dict], arms: List[str],
                   axis: str = "overall") -> Dict[Tuple[str, str], dict]:
    """results: rows {app, arm_a, arm_b, axis, winner_arm}. Returns per ordered
    pair: {wins, total, winrate} aggregated over all votes (both orders)."""
    out = {}
    for a in arms:
        for b in arms:
            if a >= b:
                continue
            rows = [r for r in results if r["axis"] == axis and
                    {r["arm_a"], r["arm_b"]} == {a, b} and r.get("winner_arm")]
            wins_a = sum(1 for r in rows if r["winner_arm"] == a)
            out[(a, b)] = {"wins_a": wins_a, "total": len(rows),
                           "winrate_a": wins_a / len(rows) if rows else None}
    return out


def paired_sign_test(results: List[dict], arm_a: str, arm_b: str,
                     axis: str = "overall") -> dict:
    """Per-task majority vote -> exact two-sided binomial sign test."""
    by_app = defaultdict(list)
    for r in results:
        if r["axis"] == axis and {r["arm_a"], r["arm_b"]} == {arm_a, arm_b} \
                and r.get("winner_arm"):
            by_app[r["app"]].append(r["winner_arm"])
    a_tasks = b_tasks = 0
    for app, winners in by_app.items():
        na = winners.count(arm_a)
        nb = winners.count(arm_b)
        if na > nb:
            a_tasks += 1
        elif nb > na:
            b_tasks += 1
        # per-task ties (split votes) are dropped, standard sign-test practice
    n = a_tasks + b_tasks
    if n == 0:
        return {"n_tasks": 0, "p": None, "a_tasks": 0, "b_tasks": 0}
    k = max(a_tasks, b_tasks)
    p = sum(math.comb(n, x) for x in range(k, n + 1)) / (2 ** n) * 2
    return {"n_tasks": n, "a_tasks": a_tasks, "b_tasks": b_tasks,
            "p": min(1.0, p)}


def bt_from_results(results: List[dict], axis: str = "overall") -> Dict[str, float]:
    wins = defaultdict(int)
    for r in results:
        if r["axis"] != axis or not r.get("winner_arm"):
            continue
        loser = r["arm_b"] if r["winner_arm"] == r["arm_a"] else r["arm_a"]
        wins[(r["winner_arm"], loser)] += 1
    return fit_bt(dict(wins))
