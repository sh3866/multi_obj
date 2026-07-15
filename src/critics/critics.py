"""Axis critics + fused critic (layer A — drive revision only, never evidence)."""

from __future__ import annotations

import asyncio
from typing import List, Optional

from ..config import Axis
from ..infra.client import UsageStats
from ..infra.parse import extract_json
from . import prompts


def _normalize(raw: Optional[dict], axis_key: str) -> dict:
    if not raw:
        return {"axis": axis_key, "score": 3, "critique": "(no parse)",
                "suggestion": "", "parse_ok": False}
    try:
        score = max(1, min(5, int(round(float(raw.get("score", 3))))))
    except Exception:
        score = 3
    return {"axis": raw.get("axis", axis_key), "score": score,
            "critique": str(raw.get("critique", "")),
            "suggestion": str(raw.get("suggestion", "")), "parse_ok": True}


def func_evidence(probe: Optional[dict]) -> str:
    if not probe:
        return ""
    fo = probe.get("func_objective")
    fo_s = f"{fo:.2f}" if isinstance(fo, (int, float)) else "n/a"
    return (f"rendered={probe.get('rendered')}, func_objective={fo_s}, "
            f"clicked={probe.get('n_clicked')}, click_errors={probe.get('click_errors')}, "
            f"page_errors={len(probe.get('page_errors', []))}")


async def axis_critic(axis: Axis, instruction: str, html: str, png: Optional[str],
                      probe: Optional[dict], gen_c, vlm_c, cfg, usage: UsageStats) -> dict:
    use_vision = axis.modality in ("vision", "both") and png is not None
    src = html[:6000] if axis.modality in ("code", "both") else ""
    evidence = func_evidence(probe) if axis.key == "functionality" else ""
    prompt = prompts.critic_prompt(axis.key, axis.description, instruction,
                                   has_image=use_vision, html_excerpt=src,
                                   evidence=evidence)
    if use_vision:
        raw = await vlm_c.generate_vlm(prompt, [png], max_tokens=1024,
                                       temperature=cfg.critic_temperature,
                                       usage_stats=usage, tag=f"crit:{axis.key}")
    else:
        raw = await gen_c.generate(prompt, max_tokens=1024,
                                   temperature=cfg.critic_temperature,
                                   usage_stats=usage, tag=f"crit:{axis.key}")
    return _normalize(extract_json(raw), axis.key)


async def all_axis_critics(axes: List[Axis], instruction: str, html: str,
                           png: Optional[str], probe: Optional[dict],
                           gen_c, vlm_c, cfg, usage: UsageStats) -> List[dict]:
    return await asyncio.gather(*[
        axis_critic(a, instruction, html, png, probe, gen_c, vlm_c, cfg, usage)
        for a in axes])


async def fused_critic(instruction: str, axes: List[Axis], html: str,
                       png: Optional[str], probe: Optional[dict],
                       gen_c, vlm_c, cfg, usage: UsageStats) -> dict:
    use_vision = png is not None
    src = "" if use_vision else html[:6000]
    prompt = prompts.fused_critic_prompt(instruction, [a.key for a in axes],
                                         has_image=use_vision, html_excerpt=src,
                                         evidence=func_evidence(probe))
    if use_vision:
        raw = await vlm_c.generate_vlm(prompt, [png], max_tokens=1024,
                                       temperature=cfg.critic_temperature,
                                       usage_stats=usage, tag="crit:fused")
    else:
        raw = await gen_c.generate(prompt, max_tokens=1024,
                                   temperature=cfg.critic_temperature,
                                   usage_stats=usage, tag="crit:fused")
    return _normalize(extract_json(raw), "overall")
