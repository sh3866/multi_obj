"""Shared machinery for all arms: generation calls, candidate tracking with
tokens_at stamps, in-loop previews, and the SHARED final-artifact selector.

Contract (PLAN.md, consensus-stop regime 2026-07-15 v2):
- every arm receives a BudgetedUsage and must stop when usage.exhausted()
- the loop obeys its evaluator's good_enough (consensus-stop); hard cap
  cfg.max_rounds_cap rounds; the artifact at stop time is the final output
- every intermediate artifact is a candidate stamped with tokens_at
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from ..config import ExperimentConfig
from ..infra.client import BudgetedUsage
from ..infra.parse import extract_html, extract_json
from ..infra import render
from ..critics import prompts


class CandidateSet:
    """Ordered candidates; each stamped with cumulative tokens at creation."""

    def __init__(self, usage: BudgetedUsage):
        self.usage = usage
        self.items: List[dict] = []

    def add(self, cid: str, html: str, round_idx: int, note: str = "") -> None:
        if not html:
            return
        self.items.append({"id": cid, "html": html, "round": round_idx,
                           "tokens_at": self.usage.total_tokens, "note": note})

    def last_html(self) -> str:
        return self.items[-1]["html"] if self.items else ""


async def preview(html: str, rdir: str, cfg: ExperimentConfig):
    """In-loop render for critics. Returns (png_path_or_None, probe_or_None)."""
    if not cfg.render or not html:
        return None, None
    os.makedirs(rdir, exist_ok=True)
    png = os.path.join(rdir, "preview.png")
    info = await render.render_and_probe(html, png, viewport=cfg.viewport)
    return (png if info.get("rendered") else None), info


# ---------------------------------------------------------------------------
# Generation calls
# ---------------------------------------------------------------------------

async def gen_initial(instruction: str, spec: str, gen_c, cfg, usage,
                      temperature: Optional[float] = None) -> str:
    if getattr(cfg, "design_mode", False):
        from .. import side_prompts as sp
        prompt = sp.gen_initial_prompt(instruction)
    else:
        prompt = prompts.initial_generation_prompt(instruction, spec)
    raw = await gen_c.generate(
        prompt, max_tokens=cfg.max_tokens,
        temperature=cfg.gen_temperature if temperature is None else temperature,
        usage_stats=usage, tag="gen:init")
    return extract_html(raw)


# chars (~14k tokens at 2.5c/t); with the 32k-context gen server + 16k output
# this leaves headroom (14k prompt-html + ~2k instruction + 16k output < 32k).
# Raised from 20k after pilot attempt-5 showed pages of 30-37k chars hitting
# the cap every self-refine round.
HTML_PROMPT_CAP = 35000

logger = logging.getLogger("arms")


def _capped(prev_html: str, tag: str) -> str:
    """Truncate prev_html for the revision prompt. Truncation silently deletes
    the document tail (the model rewrites 'the full page' from a cut source),
    so every occurrence is logged — check the rate; if it is common, the cap /
    server context must be raised, not ignored."""
    if len(prev_html) > HTML_PROMPT_CAP:
        logger.warning("HTML_PROMPT_CAP truncation [%s]: %d -> %d chars "
                       "(tail dropped from revision context)",
                       tag, len(prev_html), HTML_PROMPT_CAP)
        return prev_html[:HTML_PROMPT_CAP]
    return prev_html


async def gen_revision(instruction: str, prev_html: str, revision_spec: str,
                       gen_c, cfg, usage) -> str:
    if getattr(cfg, "design_mode", False):
        from .. import side_prompts as sp
        prompt = sp.gen_revision_prompt(instruction, _capped(prev_html, "revise"),
                                        revision_spec)
    else:
        prompt = prompts.revision_generation_prompt(
            instruction, _capped(prev_html, "revise"), revision_spec)
    raw = await gen_c.generate(prompt, max_tokens=cfg.max_tokens,
                               temperature=cfg.gen_temperature,
                               usage_stats=usage, tag="gen:revise")
    return extract_html(raw)


async def gen_self_refine(instruction: str, prev_html: str, gen_c, cfg, usage,
                          png: Optional[str] = None, vlm_c=None):
    """Returns (html, good_enough). good_enough=True means the agent declared
    its own work done (consensus-stop signal, mirrors FUSED/AXES/MAD).
    Design-mode: the agent SEES its own render (png via vlm_c) and rebuilds; no
    good_enough (fixed rounds)."""
    if getattr(cfg, "design_mode", False):
        from .. import side_prompts as sp
        prompt = sp.self_refine_prompt(instruction, _capped(prev_html, "self_refine"))
        client = vlm_c if (vlm_c is not None and png) else gen_c
        if client is vlm_c:
            raw = await client.generate_vlm(prompt, [png], max_tokens=cfg.max_tokens,
                                            temperature=cfg.gen_temperature,
                                            usage_stats=usage, tag="gen:self_refine")
        else:
            raw = await client.generate(prompt, max_tokens=cfg.max_tokens,
                                        temperature=cfg.gen_temperature,
                                        usage_stats=usage, tag="gen:self_refine")
        return extract_html(raw), False
    raw = await gen_c.generate(
        prompts.self_refine_prompt(instruction, _capped(prev_html, "self_refine")),
        max_tokens=cfg.max_tokens, temperature=cfg.gen_temperature,
        usage_stats=usage, tag="gen:self_refine")
    if raw and "GOOD_ENOUGH" in raw.strip()[:40] and "<html" not in raw.lower():
        return "", True
    return extract_html(raw), False


def load_init(workdir: str, cfg) -> Optional[dict]:
    """Shared-r0 paired design: load the cached planner spec + initial html
    for this task (app id = workdir basename) from cfg.init_pool. Returns
    {"spec", "html"} or None when the pool is unset/missing this app."""
    if not cfg.init_pool:
        return None
    app = os.path.basename(workdir.rstrip("/"))
    base = os.path.join(cfg.init_pool, app)
    hp, sp = os.path.join(base, "r0.html"), os.path.join(base, "spec.txt")
    if not os.path.exists(hp):
        logger.warning("init_pool set but no cached r0 for %s — falling back "
                       "to fresh generation", app)
        return None
    spec = open(sp).read() if os.path.exists(sp) else ""
    return {"spec": spec, "html": open(hp).read()}


async def run_planner(instruction: str, gen_c, cfg, usage) -> str:
    raw = await gen_c.generate(
        prompts.planner_prompt(instruction, [a.key for a in cfg.axes()]),
        max_tokens=768, temperature=cfg.critic_temperature,
        usage_stats=usage, tag="planner")
    return (extract_json(raw) or {}).get("spec", "")


# ---------------------------------------------------------------------------
# Shared final-artifact selector (identical across arms; layer-A signals only)
# ---------------------------------------------------------------------------

async def probe_and_select(cands: CandidateSet, workdir: str,
                           cfg: ExperimentConfig) -> dict:
    """Render+probe every candidate (screenshot doubles as the layer-B judging
    input), then pick the final: max func_objective, tie-break = latest.
    With --no-render: final = last candidate (mock/smoke only)."""
    cdir = os.path.join(workdir, "candidates")
    os.makedirs(cdir, exist_ok=True)
    for c in cands.items:
        c["html_path"] = os.path.join(cdir, f"{c['id']}.html")
        with open(c["html_path"], "w") as f:
            f.write(c["html"])
        if cfg.render:
            png = os.path.join(cdir, f"{c['id']}.png")
            info = await render.render_and_probe(c["html"], png, viewport=cfg.viewport,
                                                 n_shots=3)
            c["png"] = png if info.get("rendered") else None
            c["pngs"] = info.get("pngs") if info.get("rendered") else None
            c["probe"] = {k: info.get(k) for k in
                          ("rendered", "func_objective", "dom_nodes", "html_bytes",
                           "load_ms", "n_clicked", "click_errors")}
            c["probe"]["n_page_errors"] = len(info.get("page_errors", []))
            c["probe"]["n_console_errors"] = len(info.get("console_errors", []))
        else:
            c["png"], c["probe"] = None, None

    if not cands.items:
        return {"id": None, "html": ""}
    # CONSENSUS-STOP semantics (user decision 2026-07-15 v2): the final output
    # is the artifact the method itself stopped on — the LAST candidate (loops
    # break at good_enough before revising further; hard cap 4 rounds). No
    # harness-side selector: one couldn't be used at inference time, so using
    # one here would measure the harness, not the method. Probe data above is
    # kept for descriptive stats and checklist curves only.
    return cands.items[-1]
