"""Load WebGen-Bench test instructions (data/test.jsonl).

Each record: id (e.g. "000001"), instruction, Category, application_type, ui_instruct.
The WebVoyager harness keys served apps by their 1-based index (f"{idx+1:06d}"),
so we expose both `idx` and `app` to keep our artifacts aligned with test.jsonl.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional


def load_webgen(test_path: str, n: Optional[int] = None,
                task_ids: Optional[List[str]] = None,
                categories: Optional[List[str]] = None) -> List[Dict]:
    out = []
    with open(test_path) as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            cat = r.get("Category") or {}
            out.append({
                "idx": idx,
                "app": f"{idx + 1:06d}",
                "id": str(r.get("id", f"{idx+1:06d}")),
                "instruction": r["instruction"],
                "ui_instruct": r.get("ui_instruct", []),
                "category": (cat.get("primary_category", "") if isinstance(cat, dict)
                             else str(cat)),
            })
    if categories:
        want_cat = {c.strip() for c in categories}
        out = [r for r in out if r["category"] in want_cat]
    if task_ids:
        want = set(task_ids)
        out = [r for r in out if r["id"] in want or r["app"] in want]
    if n is not None:
        out = out[:n]
    return out
