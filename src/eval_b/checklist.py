"""ArtifactsBench-style checklist judging (layer B, absolute; complements the
pairwise BT primary — see PLAN.md "역할 분담": diagnostics + per-round curves).

The judge sees the instruction, the task's per-item checklist, and up to three
temporal screenshots (t0 load / t1 settled / t2 after interactions), and marks
each item pass/fail. Score = fraction passed. Linear cost per artifact, so this
is the metric used on ALL candidates (quality-vs-token and leniency curves).

Isolation: checklists are layer-B assets — never shown to in-loop critics.
"""

from __future__ import annotations

from typing import List, Optional

from ..infra.parse import extract_json


def checklist_prompt(instruction: str, items: List[str], n_images: int) -> str:
    listed = "\n".join(f"{i+1}. {it}" for i, it in enumerate(items))
    shots = ("three screenshots (right after load / settled / after clicking "
             "controls)" if n_images >= 3 else "a screenshot")
    return f"""You are a strict QA judge. A website/artifact was built for this request:

REQUEST: {instruction}

You see {shots} of the artifact. Judge each checklist item strictly: mark it
passed ONLY if the screenshots clearly support it; when in doubt, fail it.

CHECKLIST:
{listed}

Return JSON only:
{{"passed": [<true|false for item 1>, <item 2>, ...]}}  — exactly {len(items)} booleans."""


async def judge_checklist(instruction: str, items: List[str],
                          image_paths: List[str], judge_c,
                          usage=None) -> Optional[List[bool]]:
    """Returns a pass/fail list aligned to `items`, or None on failure."""
    if not items or not image_paths:
        return None
    raw = await judge_c.generate_vlm(
        checklist_prompt(instruction, items, len(image_paths)),
        image_paths, max_tokens=512, temperature=0.0,
        usage_stats=usage, tag="checklist")
    p = extract_json(raw) or {}
    passed = p.get("passed")
    if not isinstance(passed, list) or not passed:
        return None
    # normalize length defensively (judge may over/under-produce)
    out = [bool(x) for x in passed][: len(items)]
    while len(out) < len(items):
        out.append(False)
    return out
