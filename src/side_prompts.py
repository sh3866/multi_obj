"""Side 'design-first' experiment prompts (no scoring — subjective critique only).

Loads the editable prompt files under sideproj_subjective/ and assembles the
critic / fused / moderator / debate / generator prompts. Used ONLY when
ExperimentConfig.design_mode is True; main behaviour is untouched otherwise.
Edit the .txt files to change behaviour — this module just wires them in.
"""
from __future__ import annotations
import os
import re
import json
from typing import List

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "sideproj_subjective")


def _r(rel: str) -> str:
    with open(os.path.join(BASE, rel), encoding="utf-8") as f:
        return f.read()


# ---- flat prompt files -----------------------------------------------------
GEN_INITIAL_T = _r("gen_prompts/initial.txt")
GEN_REVISION_T = _r("gen_prompts/revision.txt")
SELF_T = _r("critic_prompts/self.txt")
MODERATOR_T = _r("critic_prompts/moderator.txt")
DEBATE_T = _r("critic_prompts/debate_template.txt")
FUSED_T = {2: _r("critic_prompts/fused/fused2.txt"),
           3: _r("critic_prompts/fused/fused3.txt"),
           4: _r("critic_prompts/fused/fused4.txt"),
           10: _r("critic_prompts/fused/fused10.txt")}

# ---- design axis sets: {set_name: [(key, name, persona, full_prompt), ...]} -
_SETS = {
    "design2": ["structure", "aesthetic"],
    "design4": ["layout", "spacing", "color_type", "style_orig"],
    "design10": ["hierarchy", "composition", "spacing", "alignment", "color",
                 "typography", "imagery", "mood", "originality", "finish"],
    "conflict3": ["spec_fidelity", "unity", "variety"],
}
AXIS_META = {}   # set_name -> list of (key, name, persona, full_prompt)
for _s, _keys in _SETS.items():
    _lst = []
    for _k in _keys:
        _txt = _r(f"critic_prompts/{_s}/{_k}.txt")
        _name = re.search(r"Your ONE job is (.+?):", _txt).group(1)
        _persona = re.search(r"You are (.+?)\. You are among", _txt, re.S).group(1)
        _lst.append((_k, _name, _persona, _txt))
    AXIS_META[_s] = _lst


# ---- assemblers ------------------------------------------------------------
def gen_initial_prompt(instruction: str) -> str:
    return GEN_INITIAL_T.replace("{instruction}", instruction)


def gen_revision_prompt(instruction: str, prev_html: str, spec: str) -> str:
    return (GEN_REVISION_T.replace("{instruction}", instruction)
            .replace("{revision_spec}", spec).replace("{prev_html}", prev_html))


def self_refine_prompt(instruction: str, prev_html: str) -> str:
    return (SELF_T.replace("{instruction}", instruction)
            .replace("{prev_html}", prev_html))


def critic_prompt(axis, instruction: str) -> str:
    """axis carries its full design critic prompt (Axis.critic_prompt)."""
    return axis.critic_prompt.replace("{instruction}", instruction)


def fused_prompt(instruction: str, n_axes: int) -> str:
    t = FUSED_T.get(n_axes) or FUSED_T[4]
    return t.replace("{instruction}", instruction)


def _verdicts_text(verdicts: List[dict]) -> str:
    lines = []
    for v in verdicts:
        lines.append(f"- [{v.get('axis','')}] weaknesses: {v.get('critique','')}\n"
                     f"    suggested: {v.get('suggestion','')}")
    return "\n".join(lines)


def synthesis_prompt(instruction: str, verdicts: List[dict],
                     rebuttals: List[dict]) -> str:
    debate_block = ""
    if rebuttals:
        rb = "\n".join(
            f"- [{r.get('axis','')}] conflicts={r.get('conflicts')} "
            f"compromise=\"{r.get('compromise','')}\"" for r in rebuttals)
        debate_block = f"\n\nCROSS-CRITIQUE (conflicts & compromises):\n{rb}"
    return (MODERATOR_T.replace("{instruction}", instruction)
            .replace("{verdicts}", _verdicts_text(verdicts))
            .replace("{debate_block}", debate_block))


def cross_critique_prompt(axis, own: dict, others: List[dict]) -> str:
    """axis.critic_prompt holds persona+name; extract them for the debate."""
    txt = axis.critic_prompt
    name = re.search(r"Your ONE job is (.+?):", txt).group(1)
    persona = re.search(r"You are (.+?)\. You are among", txt, re.S).group(1)
    own_txt = (f"weaknesses: {own.get('critique','')}\n"
               f"suggested: {own.get('suggestion','')}")
    others_txt = "\n".join(
        f"- [{o.get('axis','')}] {o.get('suggestion','')}" for o in others)
    return (DEBATE_T.replace("{persona}", persona).replace("{axis_name}", name)
            .replace("{key}", axis.key).replace("{own}", own_txt)
            .replace("{others}", others_txt))
