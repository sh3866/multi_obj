"""Layer-B held-out pairwise judge (evidence, NOT optimization signal).

Isolation rules (PLAN.md):
- the judge model must differ from every in-loop model (generator, critics)
- UIClip is layer-A (used inside arms), so it is permanently excluded here
- forced choice, no tie option; every pair is judged in BOTH orders

The judge sees two screenshots labeled A and B plus the original instruction,
and picks a winner on one axis ("overall" or a named subjective axis).
"""

from __future__ import annotations

from typing import Optional

from ..infra.parse import extract_json

JUDGE_AXES = {
    "overall": "overall quality: does it fulfil the request with a functional, "
               "well-designed, original, polished result",
    "design": "design quality: coherence, mood, identity; layout harmony, color, "
              "typography, spacing",
    "originality": "originality: custom decisions vs template look; distinctive, "
                   "memorable, no generic AI-slop patterns",
    "craft": "craft: detail, consistency, finish; polished states, no rough edges",
}


def pairwise_prompt(instruction: str, axis: str) -> str:
    crit = JUDGE_AXES[axis]
    return f"""You are an expert web design judge. Two different websites (A = first
image, B = second image) were built for the same request:

REQUEST: {instruction}

Compare them ONLY on this criterion: {crit}.

You MUST pick a winner — no ties. If the difference is subtle, still decide.

Return JSON only:
{{"winner": "A" or "B", "reason": "<one sentence>"}}"""


async def judge_pair(instruction: str, png_a: str, png_b: str, axis: str,
                     judge_c, usage=None) -> Optional[str]:
    """Returns 'A' | 'B' | None (parse/transport failure)."""
    raw = await judge_c.generate_vlm(pairwise_prompt(instruction, axis),
                                     [png_a, png_b], max_tokens=256,
                                     temperature=0.0, usage_stats=usage,
                                     tag=f"judge:{axis}")
    p = extract_json(raw) or {}
    w = str(p.get("winner", "")).strip().upper()
    return w if w in ("A", "B") else None
