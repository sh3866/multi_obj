"""Debate primitives (MAD arm): iterative cross-critique + moderator synthesis.

cross_critique receives the PREVIOUS round's rebuttals so multiple debate rounds
actually iterate (each critic responds to the others' positions) instead of
recomputing round 1 — the v1 bug where debate_rounds>1 was a no-op is fixed here.

Grounding (2026-07-15 fix): rebuttals are written by the SAME VLM that produced
the verdicts, with the screenshot attached — the debaters argue about the
artifact, not about each other's one-line summaries. The functionality critic
additionally gets the render-probe evidence. Text-only fallback (gen_c) only
when there is no render (mock / --no-render smoke runs).
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from ..config import Axis
from ..infra.client import UsageStats
from ..infra.parse import extract_json
from . import prompts
from .critics import func_evidence


async def cross_critique(axes: List[Axis], verdicts: List[dict],
                         prior_rebuttals: Optional[List[dict]],
                         gen_c, cfg, usage: UsageStats,
                         vlm_c=None, png: Optional[str] = None,
                         probe: Optional[dict] = None) -> List[dict]:
    by_key = {v["axis"]: v for v in verdicts}
    use_vision = png is not None and vlm_c is not None

    async def one(axis: Axis) -> dict:
        own = by_key.get(axis.key, {"score": 3, "suggestion": ""})
        others = [v for v in verdicts if v["axis"] != axis.key]
        if getattr(cfg, "design_mode", False) and getattr(axis, "critic_prompt", ""):
            from .. import side_prompts as sp
            prompt = sp.cross_critique_prompt(axis, own, others)
        else:
            evidence = func_evidence(probe) if axis.key == "functionality" else ""
            prompt = prompts.cross_critique_prompt(axis.key, axis.description, own,
                                                   others, prior_rebuttals or [],
                                                   has_image=use_vision,
                                                   evidence=evidence)
        if use_vision:
            raw = await vlm_c.generate_vlm(prompt, [png], max_tokens=4096,
                                           temperature=cfg.critic_temperature,
                                           usage_stats=usage, tag=f"rebut:{axis.key}")
        else:
            raw = await gen_c.generate(prompt, max_tokens=4096,
                                       temperature=cfg.critic_temperature,
                                       usage_stats=usage, tag=f"rebut:{axis.key}")
        p = extract_json(raw) or {}
        p.setdefault("axis", axis.key)
        p.setdefault("conflicts", [])
        return p

    return await asyncio.gather(*[one(a) for a in axes])


async def synthesize(instruction: str, verdicts: List[dict],
                     rebuttals: Optional[List[dict]], gen_c, cfg,
                     usage: UsageStats) -> dict:
    if getattr(cfg, "design_mode", False):
        from .. import side_prompts as sp
        prompt = sp.synthesis_prompt(instruction, verdicts, rebuttals or [])
    else:
        prompt = prompts.synthesis_prompt(instruction, verdicts, rebuttals or [])
    raw = await gen_c.generate(prompt, max_tokens=4096,
                               temperature=cfg.critic_temperature,
                               usage_stats=usage, tag="synthesis")
    p = extract_json(raw) or {}
    return {"good_enough": bool(p.get("good_enough", False)),
            "revision": str(p.get("revision", "")),
            "conflicts": p.get("conflicts", []),
            "rationale": str(p.get("rationale", ""))}
