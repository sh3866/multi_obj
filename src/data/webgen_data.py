"""Load WebGen-Bench test instructions (data/test.jsonl).

Each record: id (e.g. "000001"), instruction, Category, application_type,
ui_instruct. The WebVoyager harness keys served apps by their 1-based index
(f"{idx+1:06d}"), so we expose both `idx` and `app` to keep our artifacts
aligned with test.jsonl.

Adaptations for the multi_obj pipeline (user decision 2026-07-15):
- COLOR MANDATE STRIPPED: every WebGen instruction ends with a sentence that
  dictates the palette ("Set old lace as the body background and use rosy
  brown for the UI."). That sentence turns the design axis into compliance
  checking and kills the subjective-freedom premise of H1/H2, so it is removed
  (strip_color_mandate). The removal is logged per task via `color_stripped`.
- CHECKLIST FROM ui_instruct: each ui_instruct entry (a functional test case
  with `task` + `expected_result`, written for a browser agent) is flattened
  into one checklist string so the layer-B checklist judge can score it from
  the temporal screenshots. Items requiring true multi-page/DB behavior will
  read as failed — acceptable: identical handicap for every arm.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

def strip_color_mandate(instruction: str) -> tuple:
    """Remove the trailing palette-mandate sentence ("Set old lace as the body
    background and use rosy brown for the UI." — every WebGen task ends with
    one, phrasing varies). Rule: drop the LAST sentence iff it talks about
    styling backgrounds/components/theme colors. Returns (text, stripped?)."""
    parts = re.split(r"(?<=[.!?])\s+", instruction.strip())
    if len(parts) < 2:
        return instruction, False
    last = parts[-1].lower()
    styling = ("background" in last or "theme" in last or
               (("component" in last or "ui element" in last or
                 "the ui" in last or "elements" in last or "layout" in last or
                 "ui block" in last or "buttons" in last or "cards" in last)
                and re.search(r"\b(color|style|styling|apply|assign|use|set|"
                              r"choose|specify|configure|define|design)\b",
                              last)))
    if styling:
        return " ".join(parts[:-1]).rstrip(), True
    return instruction, False


def _checklist_from_ui(ui_instruct) -> List[str]:
    out = []
    for u in ui_instruct or []:
        if isinstance(u, str):
            try:
                u = json.loads(u)
            except Exception:
                out.append(u)
                continue
        if isinstance(u, dict):
            task = str(u.get("task", "")).strip()
            exp = str(u.get("expected_result", "")).strip()
            if task or exp:
                out.append(f"{task} Expected: {exp}" if exp else task)
    return out


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
            instruction, stripped = strip_color_mandate(r["instruction"])
            out.append({
                "idx": idx,
                "app": f"{idx + 1:06d}",
                "id": str(r.get("id", f"{idx+1:06d}")),
                "instruction": instruction,
                "color_stripped": stripped,
                "ui_instruct": r.get("ui_instruct", []),
                "checklist": _checklist_from_ui(r.get("ui_instruct")),
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
