"""Axis critics + fused critic (layer A — drive revision only, never evidence)."""

from __future__ import annotations

import asyncio
import re
from typing import List, Optional

from ..config import Axis
from ..infra.client import UsageStats
from ..infra.parse import extract_json
from . import prompts


def _salvage_text(raw: str) -> str:
    """When JSON never materialized (reasoning got truncated BEFORE the JSON),
    the raw completion is still the model's actual critique — in prose. Keep it
    rather than discarding to "(no parse)": strip <think> tags and any dangling
    partial JSON, and return the prose (its conclusion, near the end)."""
    if not raw:
        return ""
    t = re.sub(r"</?think>", " ", raw, flags=re.IGNORECASE)
    t = re.sub(r"\{[^{}]*$", " ", t)          # drop a partial JSON fragment at the tail
    t = re.sub(r"\s+", " ", t).strip()
    return t[-600:] if len(t) > 600 else t


def _normalize(raw: Optional[dict], axis_key: str, raw_text: str = "") -> dict:
    if not raw:
        salv = _salvage_text(raw_text or "")
        if len(salv) >= 40:                   # usable prose critique survived
            return {"axis": axis_key, "score": 3, "critique": salv,
                    "suggestion": "", "parse_ok": False, "salvaged": True,
                    "raw": (raw_text or "")[:300]}
        # nothing usable came back at all
        return {"axis": axis_key, "score": 3, "critique": "(no parse)",
                "suggestion": "", "parse_ok": False, "raw": (raw_text or "")[:300]}
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
    out = (f"rendered={probe.get('rendered')}, func_objective={fo_s}, "
           f"page_errors={len(probe.get('page_errors', []))}")
    # verbatim error texts: counts alone let critics say "add features" while
    # the real problem is e.g. a blocked CDN script (pilot blank-final cause)
    errs = ([str(e)[:200] for e in probe.get("page_errors", [])[:3]] +
            [str(e)[:200] for e in probe.get("console_errors", [])[:2]])
    if errs:
        out += "\nerror_messages: " + " | ".join(errs)
    return out


def _pick_suggestion(d: dict) -> str:
    return str(d.get("suggestion", d.get("suggestions", "")))


def _valid_design_verdict(d: Optional[dict]) -> bool:
    if not isinstance(d, dict):
        return False
    critique = str(d.get("critique", "")).strip()
    suggestion = _pick_suggestion(d).strip()
    joined = critique + suggestion
    return (len(critique) >= 20 and len(suggestion) >= 20
            and not ("<" in joined and ">" in joined))


_DESIGN_JSON_RETRY = ("\n\nYour previous response was invalid. Return ONLY one JSON object with "
                      "non-empty string fields \"critique\" and \"suggestion\". No reasoning or placeholders.")


async def axis_critic(axis: Axis, instruction: str, html: str, png: Optional[str],
                      probe: Optional[dict], gen_c, vlm_c, cfg, usage: UsageStats) -> dict:
    # ---- side design-mode: no score, vision critic, own full prompt ----
    if getattr(cfg, "design_mode", False) and getattr(axis, "critic_prompt", ""):
        from .. import side_prompts as sp
        prompt = sp.critic_prompt(axis, instruction)
        raw = await vlm_c.generate_vlm(prompt, [png] if png else [], max_tokens=4096,
                                       temperature=cfg.critic_temperature,
                                       usage_stats=usage, tag=f"crit:{axis.key}", think=False)
        d = extract_json(raw)
        retry_raw = ""
        if not _valid_design_verdict(d):
            retry_raw = await vlm_c.generate_vlm(
                prompt + _DESIGN_JSON_RETRY, [png] if png else [], max_tokens=1536,
                temperature=cfg.critic_temperature, usage_stats=usage,
                tag=f"crit:{axis.key}:retry", think=False) or ""
            d2 = extract_json(retry_raw)
            if _valid_design_verdict(d2):
                d = d2
        valid = _valid_design_verdict(d)
        d = d or {}
        salv = _salvage_text(raw or "")
        return {"axis": axis.key, "score": 3, "parse_ok": bool(d),
                "critique": str(d.get("critique", salv if not d else "")),
                "suggestion": _pick_suggestion(d), "contract_ok": valid,
                "runtime_prompt": prompt, "raw_response": raw or "",
                "retry_raw_response": retry_raw}
    use_vision = axis.modality in ("vision", "both") and png is not None
    src = html[:6000] if axis.modality in ("code", "both") else ""
    evidence = func_evidence(probe) if axis.key == "functionality" else ""
    prompt = prompts.critic_prompt(axis.key, axis.description, instruction,
                                   has_image=use_vision, html_excerpt=src,
                                   evidence=evidence)
    async def _ask(pr: str, mt: int, think):
        if use_vision:
            return await vlm_c.generate_vlm(pr, [png], max_tokens=mt,
                                            temperature=cfg.critic_temperature,
                                            usage_stats=usage, tag=f"crit:{axis.key}",
                                            think=think)
        return await gen_c.generate(pr, max_tokens=mt,
                                    temperature=cfg.critic_temperature,
                                    usage_stats=usage, tag=f"crit:{axis.key}",
                                    think=bool(think))
    raw = await _ask(prompt, 4096, None)          # 1st: full reasoning (best quality)
    parsed = extract_json(raw)
    if parsed is None:                            # reasoning overran budget / truncated
        raw2 = await _ask(prompt + "\n\nRespond with ONLY the JSON object — no "
                          "analysis, no <think>, no preamble.", 1536, False)
        parsed = extract_json(raw2)
        if parsed is None:
            raw = raw2                            # keep the concise attempt for audit
    return _normalize(parsed, axis.key, raw or "")


async def all_axis_critics(axes: List[Axis], instruction: str, html: str,
                           png: Optional[str], probe: Optional[dict],
                           gen_c, vlm_c, cfg, usage: UsageStats) -> List[dict]:
    return await asyncio.gather(*[
        axis_critic(a, instruction, html, png, probe, gen_c, vlm_c, cfg, usage)
        for a in axes])


async def fused_critic(instruction: str, axes: List[Axis], html: str,
                       png: Optional[str], probe: Optional[dict],
                       gen_c, vlm_c, cfg, usage: UsageStats) -> dict:
    # ---- side design-mode: single integrated design critic, no score ----
    if getattr(cfg, "design_mode", False):
        from .. import side_prompts as sp
        prompt = sp.fused_prompt(instruction, len(axes))
        raw = await vlm_c.generate_vlm(prompt, [png] if png else [], max_tokens=4096,
                                       temperature=cfg.critic_temperature,
                                       usage_stats=usage, tag="crit:fused")
        d = extract_json(raw)
        retry_raw = ""
        if not _valid_design_verdict(d):
            retry_raw = await vlm_c.generate_vlm(
                prompt + _DESIGN_JSON_RETRY,
                [png] if png else [], max_tokens=1536, temperature=cfg.critic_temperature,
                usage_stats=usage, tag="crit:fused:retry", think=False) or ""
            d2 = extract_json(retry_raw)
            if _valid_design_verdict(d2):
                d = d2
        valid = _valid_design_verdict(d)
        d = d or {}
        salv = _salvage_text(raw or "")
        return {"axis": "overall", "score": 3, "parse_ok": bool(d), "good_enough": False,
                "critique": str(d.get("critique", salv if not d else "")),
                "suggestion": _pick_suggestion(d), "contract_ok": valid,
                "runtime_prompt": prompt, "raw_response": raw or "",
                "retry_raw_response": retry_raw}
    use_vision = png is not None
    src = "" if use_vision else html[:6000]
    prompt = prompts.fused_critic_prompt(instruction, axes,
                                         has_image=use_vision, html_excerpt=src,
                                         evidence=func_evidence(probe))
    async def _ask(pr: str, mt: int, think):
        if use_vision:
            return await vlm_c.generate_vlm(pr, [png], max_tokens=mt,
                                            temperature=cfg.critic_temperature,
                                            usage_stats=usage, tag="crit:fused",
                                            think=think)
        return await gen_c.generate(pr, max_tokens=mt,
                                    temperature=cfg.critic_temperature,
                                    usage_stats=usage, tag="crit:fused",
                                    think=bool(think))
    raw = await _ask(prompt, 4096, None)
    parsed = extract_json(raw)
    if parsed is None:
        raw2 = await _ask(prompt + "\n\nRespond with ONLY the JSON object — no "
                          "analysis, no <think>, no preamble.", 1536, False)
        parsed = extract_json(raw2)
        if parsed is None:
            raw = raw2
    out = _normalize(parsed, "overall", raw or "")
    # explicit stop declaration (2026-07-15: replaces the score>=4 threshold —
    # matches the blog's iterate-until-satisfied and the other arms' contract)
    out["good_enough"] = bool((parsed or {}).get("good_enough", False))
    return out
