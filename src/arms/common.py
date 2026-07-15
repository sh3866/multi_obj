"""Shared machinery for all arms: generation calls, candidate tracking with
tokens_at stamps, in-loop previews, and the SHARED final-artifact selector.

Compute-matching contract (PLAN.md):
- every arm receives a BudgetedUsage and must stop when usage.exhausted()
- no early stopping on "good enough" — critic verdicts are logged, not obeyed
- every intermediate artifact is a candidate stamped with tokens_at
"""

from __future__ import annotations

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
    raw = await gen_c.generate(
        prompts.initial_generation_prompt(instruction, spec),
        max_tokens=cfg.max_tokens,
        temperature=cfg.gen_temperature if temperature is None else temperature,
        usage_stats=usage, tag="gen:init")
    return extract_html(raw)


HTML_PROMPT_CAP = 20000   # chars (~8k tokens at 2.5c/t); fits 16k-context servers


async def gen_revision(instruction: str, prev_html: str, revision_spec: str,
                       gen_c, cfg, usage) -> str:
    raw = await gen_c.generate(
        prompts.revision_generation_prompt(instruction,
                                           prev_html[:HTML_PROMPT_CAP],
                                           revision_spec),
        max_tokens=cfg.max_tokens, temperature=cfg.gen_temperature,
        usage_stats=usage, tag="gen:revise")
    return extract_html(raw)


async def gen_self_refine(instruction: str, prev_html: str, gen_c, cfg, usage) -> str:
    raw = await gen_c.generate(
        prompts.self_refine_prompt(instruction, prev_html[:HTML_PROMPT_CAP]),
        max_tokens=cfg.max_tokens, temperature=cfg.gen_temperature,
        usage_stats=usage, tag="gen:self_refine")
    return extract_html(raw)


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
        else:
            c["png"], c["probe"] = None, None

    if not cands.items:
        return {"id": None, "html": ""}
    if cfg.render:
        best = max(cands.items,
                   key=lambda c: ((c["probe"] or {}).get("func_objective") or 0.0,
                                  cands.items.index(c)))
    else:
        best = cands.items[-1]
    return best
