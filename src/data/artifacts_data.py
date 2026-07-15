"""Load ArtifactsBench queries (dataset/artifacts_bench.json).

Each record (per the released dataset): index, question, checklist (list of
per-task criteria strings), class (category), difficulty (simple|medium|hard).
We expose the same item shape as webgen_data.load_webgen so run_generate is
task-source agnostic; `checklist` rides along for layer-B checklist scoring.

Design-forward category subset (PLAN.md): the primary pool draws from
categories with high design freedom; a small low-freedom contrast set is kept
for the headroom dose-response analysis.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

# resolved against the dataset's `class` values (e.g. "Game Development-Puzzle",
# "Simulation & Modeling-Physics Simulation") by substring, case-insensitive
DESIGN_FORWARD = ["game", "svg", "web", "simulation", "multimedia", "visualization"]
LOW_FREEDOM = ["management", "utility"]


def _match(cat: str, needles: List[str]) -> bool:
    c = (cat or "").lower()
    return any(n in c for n in needles)


def load_artifacts(path: str, n: Optional[int] = None,
                   task_ids: Optional[List[str]] = None,
                   categories: Optional[List[str]] = None,
                   difficulties: Optional[List[str]] = None) -> List[Dict]:
    with open(path) as f:
        text = f.read().strip()
    try:                       # JSON array
        raw = json.loads(text)
    except json.JSONDecodeError:  # JSONL (the released format)
        raw = [json.loads(l) for l in text.splitlines() if l.strip()]
    out = []
    for r in raw:
        idx = r.get("index")
        # checklist items ship as {id, title, description}; judges see the title
        cl = [c["title"] if isinstance(c, dict) else str(c)
              for c in (r.get("checklist") or [])]
        out.append({
            "idx": idx,
            "app": f"ab{int(idx):06d}" if str(idx).isdigit() else f"ab_{idx}",
            "id": str(idx),
            "instruction": r.get("question", ""),
            "category": r.get("class", ""),
            "difficulty": str(r.get("difficulty", "")).lower(),  # easy|medium|hard
            "checklist": cl,
        })
    if categories:
        if categories == ["design_forward"]:
            out = [r for r in out if _match(r["category"], DESIGN_FORWARD)]
        elif categories == ["low_freedom"]:
            out = [r for r in out if _match(r["category"], LOW_FREEDOM)]
        else:
            want = [c.strip().lower() for c in categories]
            out = [r for r in out if _match(r["category"], want)]
    if difficulties:
        want_d = {d.strip().lower() for d in difficulties}
        out = [r for r in out if r["difficulty"] in want_d]
    if task_ids:
        want_t = set(task_ids)
        out = [r for r in out if r["id"] in want_t or r["app"] in want_t]
    if n is not None:
        out = out[:n]
    return out
