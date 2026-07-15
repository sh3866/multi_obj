"""Debate primitives (MAD arm): iterative cross-critique + moderator synthesis.

cross_critique receives the PREVIOUS round's rebuttals so multiple debate rounds
actually iterate (each critic responds to the others' positions) instead of
recomputing round 1 — the v1 bug where debate_rounds>1 was a no-op is fixed here.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from ..config import Axis
from ..infra.client import UsageStats
from ..infra.parse import extract_json
from . import prompts


async def cross_critique(axes: List[Axis], verdicts: List[dict],
                         prior_rebuttals: Optional[List[dict]],
                         gen_c, cfg, usage: UsageStats) -> List[dict]:
    by_key = {v["axis"]: v for v in verdicts}

    async def one(axis: Axis) -> dict:
        own = by_key.get(axis.key, {"score": 3, "suggestion": ""})
        others = [v for v in verdicts if v["axis"] != axis.key]
        prompt = prompts.cross_critique_prompt(axis.key, axis.description, own,
                                               others, prior_rebuttals or [])
        raw = await gen_c.generate(prompt, max_tokens=1024,
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
    prompt = prompts.synthesis_prompt(instruction, verdicts, rebuttals or [])
    raw = await gen_c.generate(prompt, max_tokens=1024,
                               temperature=cfg.critic_temperature,
                               usage_stats=usage, tag="synthesis")
    p = extract_json(raw) or {}
    return {"good_enough": bool(p.get("good_enough", False)),
            "revision": str(p.get("revision", "")),
            "conflicts": p.get("conflicts", []),
            "rationale": str(p.get("rationale", ""))}
