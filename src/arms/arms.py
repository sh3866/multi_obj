"""The six pre-registered arms. FROZEN once the main run starts (PLAN.md).

Every arm has the same signature and contract:
    async run(instruction, workdir, gen_c, vlm_c, cfg, usage) -> {
        "candidates": CandidateSet, "history": [...], "extra": {...}}
- usage is a BudgetedUsage; the arm stops when usage.exhausted()
- CONSENSUS-STOP regime (2026-07-15 v2): the loop breaks the moment its own
  evaluator declares good_enough (that artifact is the final output; hard cap
  cfg.max_rounds_cap). Verdicts are logged in history for leniency analysis.
"""

from __future__ import annotations

import os

from ..critics import critics, debate
from . import common


async def run_zs(instruction, workdir, gen_c, vlm_c, cfg, usage):
    """Floor anchor: one pass, no refinement (does not consume full budget)."""
    cands = common.CandidateSet(usage)
    html = await common.gen_initial(instruction, "", gen_c, cfg, usage)
    cands.add("r0", html, 0, "one_pass")
    return {"candidates": cands, "history": [{"round": 0, "action": "one_pass"}],
            "extra": {}}


async def run_bon(instruction, workdir, gen_c, vlm_c, cfg, usage):
    """Best-of-N diverse sampling: keep drafting until the budget is spent.
    N is emergent from the budget — automatic compute matching."""
    cands = common.CandidateSet(usage)
    history = []
    k, step_cost = 0, None
    while not usage.exhausted() and k < cfg.max_candidates_cap:
        if step_cost and usage.remaining() < 0.6 * step_cost:
            break  # not enough left for another full draft — avoid overshoot
        t0 = usage.total_tokens
        html = await common.gen_initial(instruction, "", gen_c, cfg, usage,
                                        temperature=cfg.bon_temperature)
        step_cost = usage.total_tokens - t0
        cands.add(f"d{k}", html, k, "draft")
        history.append({"round": k, "action": "draft",
                        "tokens": usage.total_tokens})
        k += 1
    return {"candidates": cands, "history": history, "extra": {"n_drafts": k}}


async def run_self(instruction, workdir, gen_c, vlm_c, cfg, usage):
    """Self-refine: generator critiques and revises its own work. No external
    evaluator of any kind (isolates the value of external feedback)."""
    cands = common.CandidateSet(usage)
    history = []
    init = common.load_init(workdir, cfg)   # shared-r0 paired design
    html = (init["html"] if init else
            await common.gen_initial(instruction, "", gen_c, cfg, usage))
    cands.add("r0", html, 0, "initial(shared)" if init else "initial")
    history.append({"round": 0, "action": "initial", "shared_r0": bool(init),
                    "tokens": usage.total_tokens})
    r, step_cost = 1, None
    while not usage.exhausted() and r <= cfg.max_rounds_cap:
        if step_cost and usage.remaining() < 0.6 * step_cost:
            break
        t0 = usage.total_tokens
        png = None
        if getattr(cfg, "design_mode", False):
            png, _ = await common.preview(
                html, os.path.join(workdir, f"round_{r:02d}"), cfg)
        new_html, good = await common.gen_self_refine(instruction, html,
                                                      gen_c, cfg, usage,
                                                      png=png, vlm_c=vlm_c)
        step_cost = usage.total_tokens - t0
        if cfg.early_stop and good:
            history.append({"round": r, "action": "good_enough_stop",
                            "good_enough_flag": True,
                            "tokens": usage.total_tokens})
            break  # agent declared its own work done (consensus-stop)
        html = new_html or html
        cands.add(f"r{r}", html, r, "self_refine")
        history.append({"round": r, "action": "self_refine",
                        "tokens": usage.total_tokens})
        r += 1
    return {"candidates": cands, "history": history, "extra": {}}


async def run_fused(instruction, workdir, gen_c, vlm_c, cfg, usage):
    """The Anthropic-harness loop: planner + generator + ONE fused evaluator."""
    cands = common.CandidateSet(usage)
    history = []
    init = common.load_init(workdir, cfg)   # shared-r0 paired design
    if init:
        spec, html = init["spec"], init["html"]
    else:
        spec = await common.run_planner(instruction, gen_c, cfg, usage)
        html = await common.gen_initial(instruction, spec, gen_c, cfg, usage)
    cands.add("r0", html, 0, "initial(shared)" if init else "initial")
    r, round_cost = 0, None
    while not usage.exhausted() and r < cfg.max_rounds_cap:
        if round_cost and usage.remaining() < 0.6 * round_cost:
            break
        t0 = usage.total_tokens
        png, probe = await common.preview(html, os.path.join(workdir, f"round_{r:02d}"), cfg)
        v = await critics.fused_critic(instruction, cfg.axes(), html, png, probe,
                                       gen_c, vlm_c, cfg, usage)
        history.append({"round": r, "fused_score": v["score"],
                        "good_enough_flag": v.get("good_enough", False),
                        # store the FULL fused critique + suggestion (parity with
                        # AXES/MAD debate.critiques) — was truncated to [:160]
                        # with no critique, which cut FUSED transcripts in reports
                        "critique": v.get("critique", ""),
                        "suggestion": v.get("suggestion", ""),
                        "tokens": usage.total_tokens})
        if cfg.early_stop and v.get("good_enough"):
            break  # evaluator declared done (explicit, replaces score>=4)
        if usage.exhausted():
            break
        revision = v["suggestion"] or ("Keep improving: polish design, originality "
                                       "and craft; harden the requested features.")
        html = await common.gen_revision(instruction, html, revision,
                                         gen_c, cfg, usage) or html
        r += 1
        cands.add(f"r{r}", html, r, "revision")
        round_cost = usage.total_tokens - t0
    return {"candidates": cands, "history": history, "extra": {"spec": spec}}


async def _critic_loop(instruction, workdir, gen_c, vlm_c, cfg, usage,
                       use_debate: bool, axes=None, spec=None, extra=None):
    """Shared loop for AXES (use_debate=False), MAD (use_debate=True) and DISC
    (use_debate=True + discovered axes/spec). Only the evaluator block differs."""
    cands = common.CandidateSet(usage)
    history = []
    axes = axes or cfg.axes()
    init = common.load_init(workdir, cfg)   # shared-r0 paired design
    if init:
        spec, html = (spec if spec is not None else init["spec"]), init["html"]
    else:
        if spec is None:
            spec = await common.run_planner(instruction, gen_c, cfg, usage)
        html = await common.gen_initial(instruction, spec, gen_c, cfg, usage)
    cands.add("r0", html, 0, "initial(shared)" if init else "initial")
    r, round_cost = 0, None
    while not usage.exhausted() and r < cfg.max_rounds_cap:
        if round_cost and usage.remaining() < 0.6 * round_cost:
            break
        t0 = usage.total_tokens
        png, probe = await common.preview(html, os.path.join(workdir, f"round_{r:02d}"), cfg)
        verdicts = await critics.all_axis_critics(axes, instruction, html, png,
                                                  probe, gen_c, vlm_c, cfg, usage)
        invalid_verdicts = [v.get("axis") for v in verdicts if not v.get("contract_ok", True)]
        if invalid_verdicts:
            raise RuntimeError(f"critic output contract failed after retry: {invalid_verdicts}")
        rebuttals = []
        if use_debate and not usage.exhausted():
            for _ in range(cfg.debate_rounds):
                rebuttals = await debate.cross_critique(axes, verdicts, rebuttals,
                                                        gen_c, cfg, usage,
                                                        vlm_c=vlm_c, png=png,
                                                        probe=probe)
                invalid_rebuttals = [v.get("axis") for v in rebuttals if not v.get("contract_ok", True)]
                if invalid_rebuttals:
                    raise RuntimeError(f"rebuttal output contract failed after retry: {invalid_rebuttals}")
                if usage.exhausted():
                    break
        if usage.exhausted():
            history.append({"round": r,
                            "scores": {v["axis"]: v["score"] for v in verdicts},
                            "stopped": "budget", "tokens": usage.total_tokens})
            break
        synth = await debate.synthesize(instruction, verdicts, rebuttals,
                                        gen_c, cfg, usage, vlm_c=vlm_c, png=png)
        if not synth.get("contract_ok", True):
            raise RuntimeError("moderator output contract failed after retry")
        history.append({"round": r,
                        "scores": {v["axis"]: v["score"] for v in verdicts},
                        "suggestions": {v["axis"]: v["suggestion"][:120]
                                        for v in verdicts},
                        "conflicts": synth.get("conflicts", []),
                        "good_enough_flag": synth["good_enough"],
                        "revision": synth["revision"][:160],
                        # FULL debate transcript (2026-07-15): critiques, the
                        # cross-critique rebuttals (the actual debate) and the
                        # moderator's complete output — for qualitative
                        # analysis; summaries above stay for compact reading.
                        "debate": {
                            "critiques": {v["axis"]: {
                                "score": v.get("score"),
                                "critique": v.get("critique", ""),
                                "suggestion": v.get("suggestion", ""),
                                "contract_ok": v.get("contract_ok"),
                                "runtime_prompt": v.get("runtime_prompt", ""),
                                "raw_response": v.get("raw_response", ""),
                                "retry_raw_response": v.get("retry_raw_response", "")}
                                for v in verdicts},
                            "rebuttals": rebuttals,
                            "synthesis": synth},
                        "tokens": usage.total_tokens})
        if cfg.early_stop and synth["good_enough"]:
            break  # critics reached consensus (self stop, logged above)
        if usage.exhausted():
            break
        revision = synth["revision"] or ("Keep improving: polish design, "
                                         "originality and craft; harden features.")
        html = await common.gen_revision(instruction, html, revision,
                                         gen_c, cfg, usage) or html
        r += 1
        cands.add(f"r{r}", html, r, "revision")
        round_cost = usage.total_tokens - t0
    out_extra = {"spec": spec}
    if extra:
        out_extra.update(extra)
    return {"candidates": cands, "history": history, "extra": out_extra}


async def run_axes(instruction, workdir, gen_c, vlm_c, cfg, usage):
    """Per-objective critics, INDEPENDENT (no cross-talk) -> moderator. H1 arm."""
    return await _critic_loop(instruction, workdir, gen_c, vlm_c, cfg, usage,
                              use_debate=False)


async def run_mad(instruction, workdir, gen_c, vlm_c, cfg, usage):
    """AXES + iterative cross-critique (debate) before synthesis. H2 arm."""
    return await _critic_loop(instruction, workdir, gen_c, vlm_c, cfg, usage,
                              use_debate=True)


async def run_disc(instruction, workdir, gen_c, vlm_c, cfg, usage):
    """DISC: orchestrator imagines the ideal result (north star) and DISCOVERS
    the task-specific factor decomposition; those factors become the debating
    critics (MAD machinery). Functionality critic is always appended as anchor."""
    from ..config import Axis, AXES_MAIN
    from ..critics import prompts as P
    from ..infra.parse import extract_json
    raw = await gen_c.generate(P.orchestrator_prompt(instruction), max_tokens=1024,
                               temperature=cfg.critic_temperature,
                               usage_stats=usage, tag="orchestrator")
    p = extract_json(raw) or {}
    disc = [Axis(str(a.get("key", f"factor{i}"))[:40],
                 str(a.get("description", "")))
            for i, a in enumerate(p.get("axes", [])[:5]) if a.get("key")]
    if not disc:  # orchestrator failed -> fall back to fixed subjective axes
        disc = [a for a in AXES_MAIN if a.kind == "subjective"]
    axes = [AXES_MAIN[0]] + disc          # functionality anchor + discovered
    north = str(p.get("north_star", ""))
    return await _critic_loop(instruction, workdir, gen_c, vlm_c, cfg, usage,
                              use_debate=True, axes=axes, spec=north,
                              extra={"north_star": north,
                                     "discovered_axes": [
                                         {"key": a.key, "description": a.description}
                                         for a in disc]})


RUNNERS = {"ZS": run_zs, "BON": run_bon, "SELF": run_self,
           "FUSED": run_fused, "AXES": run_axes, "MAD": run_mad,
           "DISC": run_disc}
