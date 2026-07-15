"""Prompt templates — generation, critics, debate, moderator (layer A only).

These prompts drive REVISION inside the arms. They are never used for evidence:
layer-B judging has its own prompts in eval_b/judge.py and its own held-out model.

Critic scores are 1-5 with anchors. They are logged per round (leniency analysis)
but never used for early stopping — arms run until token budget exhaustion.
"""

from __future__ import annotations

import json
from typing import List

SCALE = "Score 1-5: 1=Poor, 2=Below Average, 3=Average, 4=Good, 5=Excellent."

ANCHORS = {
    "functionality": "1=controls dead / JS errors; 3=renders, some features missing; "
                     "5=all requested features present and operable, no errors.",
    "design": "1=cluttered, no hierarchy; 3=usable but generic; 5=clear hierarchy, "
              "harmonious color, refined typography.",
    "originality": "1=bare template / AI-slop look; 3=conventional; "
                   "5=distinctive, memorable, custom decisions.",
    "craft": "1=rough, inconsistent; 3=acceptable; 5=polished, consistent, finished.",
    "aesthetics": "1=ugly and cluttered; 3=generic; 5=beautiful, distinctive, polished.",
    "layout": "1=broken/overlapping; 3=plain grid; 5=balanced, hierarchical, rhythmic.",
    "color": "1=clashing; 3=safe but flat; 5=harmonious palette with clear accents.",
    "typography": "1=default fonts, poor sizing; 3=readable; 5=refined scale and rhythm.",
    # VisAWI facet anchors (Moshagen & Thielsch 2010)
    "simplicity": "1=cluttered, hard to parse; 3=mostly orderly; 5=everything "
                  "groups cleanly, effortless to grasp.",
    "diversity": "1=monotonous, static; 3=some variation; 5=inventive, dynamic, "
                 "visually rich.",
    "colorfulness": "1=jarring or drab colors; 3=safe; 5=attractive, harmonious, "
                    "well-composed palette.",
    "craftsmanship": "1=amateurish, half-done; 3=competent; 5=professionally "
                     "executed with modern techniques.",
    # Lavie & Tractinsky 2004 anchors
    "classical": "1=messy, unclear; 3=acceptable order; 5=clean, clear, "
                 "symmetrical, pleasant.",
    "expressive": "1=generic template; 3=conventional; 5=original, sophisticated, "
                  "fascinating, creative.",
}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def initial_generation_prompt(instruction: str, spec: str = "") -> str:
    spec_block = f"\n\nAGREED BUILD SPEC:\n{spec}" if spec else ""
    return f"""You are a senior front-end engineer. Build a website for this request:

REQUEST:
{instruction}{spec_block}

Requirements:
- Output ONE self-contained HTML document (inline CSS and JS, no external files or
  network requests). It must render standalone in a browser.
- Implement the requested interactive features so they actually work (client-side
  state, e.g. localStorage, where persistence is asked for).
- Aim for a modern, distinctive, polished design with a clear identity — a page
  that looks like a template is a failure.

Return ONLY the HTML, starting with <!DOCTYPE html>. No prose, no markdown fences."""


def revision_generation_prompt(instruction: str, prev_html: str, revision_spec: str) -> str:
    return f"""You are a senior front-end engineer revising a website.

ORIGINAL REQUEST:
{instruction}

AGREED REVISION SPEC (apply these; keep what already works):
{revision_spec}

CURRENT HTML:
{prev_html}

Return ONLY the full revised self-contained HTML, starting with <!DOCTYPE html>.
No prose, no markdown fences."""


def self_refine_prompt(instruction: str, prev_html: str) -> str:
    """SELF arm: the single agent critiques and revises its own work."""
    return f"""You built this website for the request below. Critique your own work, then
improve it: fix anything broken and make it more functional and visually polished.

REQUEST:
{instruction}

CURRENT HTML:
{prev_html}

Return ONLY the full improved self-contained HTML, starting with <!DOCTYPE html>."""


def planner_prompt(instruction: str, axis_keys: List[str]) -> str:
    return f"""You are a product planner. Expand this request into a concise build spec
and per-axis success criteria.

REQUEST:
{instruction}

Axes: {', '.join(axis_keys)}

Return JSON:
{{"spec": "<3-6 sentence build spec>",
  "success_criteria": {{ {", ".join(f'"{k}": "<criterion>"' for k in axis_keys)} }} }}"""


def orchestrator_prompt(instruction: str) -> str:
    """DISC arm: one agent imagines the ideal artifact (north star) and decides
    which quality factors this SPECIFIC task should be decomposed into."""
    return f"""You are the design director. A team of specialist critics will iteratively
review a web artifact built for this request:

REQUEST:
{instruction}

First, vividly imagine the IDEAL, exceptionally well-designed result for this
specific request (the north star). Then decide which 3-5 quality factors this
particular task's success decomposes into — the factors along which the ideal
differs most from a mediocre attempt. Factors must be visually judgeable from a
screenshot, mutually distinct, and specific to THIS task (e.g. for a game:
game-feel, visual identity, feedback clarity — not generic boilerplate).
Do NOT include functionality; a dedicated functionality critic always exists.

Return JSON only:
{{"north_star": "<4-6 sentence vivid description of the ideal result>",
  "axes": [{{"key": "<snake_case_name>", "description": "<one sentence: what this
factor cares about and what excellence looks like here>"}}, ...]}}"""


# ---------------------------------------------------------------------------
# Critics
# ---------------------------------------------------------------------------

def critic_prompt(axis_key: str, axis_desc: str, instruction: str,
                  has_image: bool, html_excerpt: str = "", evidence: str = "") -> str:
    seeing = "the attached screenshot of" if has_image else "the HTML source of"
    code_block = f"\n\nHTML SOURCE:\n{html_excerpt}" if html_excerpt else ""
    ev_block = (f"\n\nOBJECTIVE EVIDENCE (from running the page; trust over looks):\n{evidence}"
                if evidence else "")
    anchor = ANCHORS.get(axis_key, "")
    return f"""You are a specialist critic evaluating ONLY one axis; ignore all others.

AXIS: {axis_key}
WHAT THIS AXIS CARES ABOUT: {axis_desc}

You are judging {seeing} a website built for this request:
REQUEST: {instruction}{code_block}{ev_block}

{SCALE}
ANCHORS — {anchor}
Judge ONLY {axis_key}. Be specific and critical; do not praise mediocre work.

Return JSON only:
{{"axis": "{axis_key}", "score": <1-5 int>, "critique": "<2-3 concrete sentences>",
  "suggestion": "<one concrete change that most improves THIS axis>"}}"""


def fused_critic_prompt(instruction: str, axis_keys: List[str], has_image: bool,
                        html_excerpt: str = "", evidence: str = "") -> str:
    """FUSED arm — single evaluator judging all criteria at once (blog harness)."""
    seeing = "the attached screenshot of" if has_image else "the HTML source of"
    code_block = f"\n\nHTML SOURCE:\n{html_excerpt}" if html_excerpt else ""
    ev_block = f"\n\nOBJECTIVE EVIDENCE:\n{evidence}" if evidence else ""
    return f"""You are an expert web evaluator. Judge OVERALL quality across these criteria
together: {', '.join(axis_keys)}.

REQUEST: {instruction}
You are judging {seeing} the site.{code_block}{ev_block}

{SCALE}
Return JSON only:
{{"score": <1-5 int>, "critique": "<3-4 sentences covering the criteria>",
  "suggestion": "<the single most important change to make next>"}}"""


# ---------------------------------------------------------------------------
# Debate (MAD only): iterative cross-critique + moderator synthesis
# ---------------------------------------------------------------------------

def cross_critique_prompt(axis_key: str, axis_desc: str, own: dict,
                          others: List[dict], prior_rebuttals: List[dict]) -> str:
    others_txt = "\n".join(
        f"- [{o.get('axis')}] score={o.get('score')}: {o.get('suggestion','')}"
        for o in others)
    prior_block = ""
    if prior_rebuttals:
        pr = "\n".join(
            f"- [{r.get('axis')}] conflicts={r.get('conflicts')} "
            f"compromise=\"{r.get('compromise','')}\"" for r in prior_rebuttals
            if r.get("axis") != axis_key)
        prior_block = f"\n\nPREVIOUS DEBATE ROUND (respond to these positions):\n{pr}"

    return f"""You are the '{axis_key}' critic ({axis_desc}).
Your verdict: score={own.get('score')}, suggestion="{own.get('suggestion','')}".

Other axis critics suggested:
{others_txt}{prior_block}

Which of their suggestions CONFLICT with {axis_key} (a real trade-off — improving
their axis would hurt yours)? Name the conflicts, then give a compromise you accept.
Do not soften your standards to be agreeable; defend your axis.

Return JSON only:
{{"axis": "{axis_key}", "conflicts": ["<axis + why it trades off>"],
  "accept": ["<suggestion you support>"],
  "compromise": "<a change that improves overall without sacrificing {axis_key}>"}}"""


def synthesis_prompt(instruction: str, verdicts: List[dict],
                     rebuttals: List[dict]) -> str:
    """Moderator: verdicts (+debate, if any) -> ONE concrete revision spec.
    Used by both AXES (rebuttals=[]) and MAD (rebuttals from cross-critique)."""
    v = json.dumps(verdicts, ensure_ascii=False)
    r = json.dumps(rebuttals or [], ensure_ascii=False)
    debate_block = f"\nCROSS-CRITIQUE / CONFLICTS: {r}" if rebuttals else ""
    return f"""You are the moderator. Synthesize the critics' verdicts into ONE concrete
revision spec that resolves the biggest trade-offs (do NOT just concatenate all
suggestions; pick what is jointly coherent). Weigh all axes equally.

REQUEST: {instruction}
PER-AXIS VERDICTS (1-5): {v}{debate_block}

Return JSON only:
{{"good_enough": <true|false — informational only, work continues regardless>,
  "revision": "<concrete actionable changes for the generator>",
  "conflicts": ["<the key trade-offs you resolved>"],
  "rationale": "<how you weighed them>"}}"""
