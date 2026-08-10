"""Layer-B held-out judge (evidence, NOT optimization signal).

PRIMARY MODE (user decision 2026-07-15): ABSOLUTE per-axis scoring (0-10),
ArtifactsBench-style — one artifact at a time, no cross-arm comparison.
judge_pair (pairwise forced choice, Arena-style) is kept below for optional
post-hoc use if absolute scores fail to separate the arms; artifacts are all
preserved, so pairwise can be added later without regeneration.

Isolation rules (PLAN.md):
- the judge model must differ from every in-loop model (generator, critics)
- UIClip is layer-A (used inside arms), so it is permanently excluded here

The judge sees each artifact as a TEMPORAL SERIES of screenshots (t0 right
after load / t1 settled / t2 after clicking controls) so dynamic behavior —
games, simulations, animations — is visible, matching what the checklist judge
sees. Falls back to a single settled shot when the series is unavailable.
"""

from __future__ import annotations

from typing import List, Optional

from ..infra.parse import extract_json

# The four harness-blog criteria, verbatim definitions (user decision
# 2026-07-15). The judge scores THESE FOUR; "overall" is NOT judged — it is
# computed post hoc as the plain mean of the four (see run_judge.py).
JUDGE_AXES = {
    "functionality": "usability independent of aesthetics: can users understand "
                     "what the interface does, find primary actions, and "
                     "complete tasks without guessing? (use the after-click "
                     "screenshot: did the controls actually respond?)",
    "design": "design quality: does the design feel like a coherent whole "
              "rather than a collection of parts? Strong work means colors, "
              "typography, layout, imagery combine into a distinct mood and "
              "identity",
    "originality": "originality: evidence of custom decisions vs template "
                   "layouts, library defaults, and AI-generated patterns; a "
                   "human designer should recognize deliberate creative "
                   "choices — unmodified stock components or telltale AI "
                   "signs (purple gradients over white cards) fail",
    "craft": "craft: technical execution — typography hierarchy, spacing "
             "consistency, color harmony, contrast ratios; a competence "
             "check, failing means broken fundamentals",
}


def absolute_prompt(instruction: str, axes: List[str], n_imgs: int) -> str:
    crits = "\n".join(f"- {a}: {JUDGE_AXES[a]}" for a in axes)
    series = ("The images show the artifact right after load / settled / after "
              "clicking its controls — use the changes across them to judge "
              "dynamic behavior, not just the static look."
              if n_imgs >= 3 else "You see a settled screenshot of the artifact.")
    return f"""You are a strict expert judge of web artifacts. One artifact was built for
this request:

REQUEST: {instruction}

{series}

Score the artifact on EACH criterion independently, 0-10:
{crits}
0-2 = broken/unacceptable, 3-4 = poor, 5-6 = mediocre, 7-8 = good, 9-10 =
exceptional (rare — reserve for truly outstanding work). Be harsh; do not
cluster scores at 7. Use the full scale.

Return JSON only:
{{"scores": {{ {", ".join(f'"{a}": <0-10 int>' for a in axes)} }},
  "reason": "<one sentence overall>"}}"""


async def judge_scores(instruction: str, pngs: List[str], axes: List[str],
                       judge_c, usage=None) -> Optional[dict]:
    """ABSOLUTE scoring (primary). Returns {axis: float 0-10} or None."""
    raw = await judge_c.generate_vlm(
        absolute_prompt(instruction, axes, len(pngs)), list(pngs),
        max_tokens=384, temperature=0.0, usage_stats=usage, tag="judge:abs")
    p = extract_json(raw) or {}
    s = p.get("scores")
    if not isinstance(s, dict):
        return None
    out = {}
    for a in axes:
        try:
            out[a] = max(0.0, min(10.0, float(s[a])))
        except (KeyError, TypeError, ValueError):
            return None
    return out


def pairwise_prompt(instruction: str, axis: str, n_a: int, n_b: int) -> str:
    crit = JUDGE_AXES[axis]
    series = ("right after load / settled / after clicking its controls"
              if max(n_a, n_b) >= 3 else "settled")
    return f"""You are an expert web design judge. Two different websites were built for
the same request:

REQUEST: {instruction}

Website A = the first {n_a} image(s); Website B = the next {n_b} image(s).
Each website's images show it {series} — use the changes across a website's
images to judge its dynamic behavior, not just its static look.

Compare them ONLY on this criterion: {crit}.

You MUST pick a winner — no ties. If the difference is subtle, still decide.

Return JSON only:
{{"winner": "A" or "B", "reason": "<one sentence>"}}"""


async def judge_pair(instruction: str, pngs_a: List[str], pngs_b: List[str],
                     axis: str, judge_c, usage=None) -> Optional[str]:
    """pngs_*: temporal screenshot series (1 or 3 images) per side.
    Returns 'A' | 'B' | None (parse/transport failure)."""
    raw = await judge_c.generate_vlm(
        pairwise_prompt(instruction, axis, len(pngs_a), len(pngs_b)),
        list(pngs_a) + list(pngs_b), max_tokens=256,
        temperature=0.0, usage_stats=usage, tag=f"judge:{axis}")
    p = extract_json(raw) or {}
    w = str(p.get("winner", "")).strip().upper()
    return w if w in ("A", "B") else None
