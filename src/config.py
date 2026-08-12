"""Experiment configuration (v2 — pre-registered design, see PLAN.md).

Six arms, each isolating one mechanism (H1 axis separation, H2 debate):
  ZS     zero-shot single pass                       (floor anchor)
  BON    best-of-N diverse sampling until budget      (no-loop baseline)
  SELF   self-refine loop, no external evaluator      (SELF->FUSED = external eval)
  FUSED  planner + generator + ONE fused evaluator    (Anthropic harness; FUSED->AXES = H1)
  AXES   per-objective critics, independent, moderator (AXES->MAD = H2)
  MAD    AXES + cross-critique (conflicts) before synthesis

Execution regime (final v2, user decision 2026-07-15): CONSENSUS-STOP —
deployment semantics. Each arm stops the moment its own evaluator declares the
artifact good enough (FUSED: fused score>=4 or no suggestion; AXES/MAD:
moderator good_enough consensus) and THAT artifact is the final output — no
external selector, because a harness-side selector could not be used at
inference time and would therefore not measure the method itself. HARD CAP at
4 rounds: if no consensus by then, the round-4 artifact ships. SELF has no
stop signal by construction (4 refines, last is final); ZS is single-shot.
All intermediate candidates are still preserved (diagnostic curves), and
tokens are logged and REPORTED (cost table) — budget_tokens is only a runaway
safety guard.

Final-artifact selection (identical for all arms, layer-A only): highest
render-probe func_objective, ties broken by latest candidate.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field, asdict
from typing import List, Optional

ARMS = ("ZS", "BON", "SELF", "FUSED", "AXES", "MAD", "DISC")


@dataclass
class Axis:
    key: str
    description: str
    kind: str = "subjective"   # "verifiable" | "subjective"
    modality: str = "vision"   # "vision" | "code" | "both"
    critic_prompt: str = ""    # side design-mode: full critic prompt for this axis


# Main axes = the Anthropic harness rubric (design/originality/craft/functionality),
# one agent per criterion, with the harness blog's FULL criterion definitions
# (user decision 2026-07-15: critics, debaters and the judge all see these).
# Efficiency deliberately EXCLUDED (rewards degenerate pages).
AXES_MAIN: List[Axis] = [
    Axis("functionality",
         "Usability independent of aesthetics: do the requested features "
         "actually work — can users understand what the interface does, find "
         "the primary actions, and complete tasks without guessing? "
         "Interactive elements, forms and navigation must operate without "
         "errors.", kind="verifiable", modality="both"),
    Axis("design",
         "Design quality: does the design feel like a coherent whole rather "
         "than a collection of parts? Strong work means the colors, "
         "typography, layout, imagery, and other details combine to create a "
         "distinct mood and identity.", kind="subjective", modality="vision"),
    Axis("originality",
         "Originality: is there evidence of custom decisions, or is this "
         "template layouts, library defaults, and AI-generated patterns? A "
         "human designer should recognize deliberate creative choices. "
         "Unmodified stock components — or telltale signs of AI generation "
         "like purple gradients over white cards — fail here.",
         kind="subjective", modality="vision"),
    Axis("craft",
         "Craft: technical execution — typography hierarchy, spacing "
         "consistency, color harmony, contrast ratios. This is a competence "
         "check rather than a creativity check; failing means broken "
         "fundamentals.", kind="subjective", modality="vision"),
]

# ablation granularities (axis-count dose-response for H1)
AXES_COARSE: List[Axis] = [
    Axis("functionality", "Requested features actually work, no errors.",
         kind="verifiable", modality="both"),
    Axis("aesthetics", "Overall visual quality: layout, color, typography, "
         "originality, craft.", kind="subjective", modality="vision"),
]
AXES_FINE: List[Axis] = [
    Axis("functionality", "Requested features actually work, no errors.",
         kind="verifiable", modality="both"),
    Axis("layout", "Spatial composition, hierarchy, alignment, spacing, balance.",
         kind="subjective", modality="vision"),
    Axis("color", "Color palette harmony, contrast, theme adherence.",
         kind="subjective", modality="vision"),
    Axis("typography", "Font choice, sizing, rhythm, readability.",
         kind="subjective", modality="vision"),
    Axis("originality", "Distinctive, non-template, memorable.",
         kind="subjective", modality="vision"),
    Axis("craft", "Detail, consistency, finish, no rough edges.",
         kind="subjective", modality="vision"),
]
# literature-grounded alternatives (axis-taxonomy ablation):
# VisAWI facets (Moshagen & Thielsch 2010) — the validated psychometric
# structure of website aesthetics; item semantics embedded in descriptions.
AXES_VISAWI: List[Axis] = [
    Axis("functionality", "Requested features actually work, no errors.",
         kind="verifiable", modality="both"),
    Axis("simplicity", "VisAWI simplicity facet — effortless perception: the "
         "layout appears clear, orderly and homogeneous; everything groups "
         "properly and the structure is easy to grasp at a glance. Items: "
         "'the layout is easy to grasp', 'everything goes together', 'the "
         "site appears well structured'.",
         kind="subjective", modality="vision"),
    Axis("diversity", "VisAWI diversity facet — visual inventiveness and "
         "dynamics: the design is varied, interesting and lively rather than "
         "monotonous or static. Items: 'the layout is pleasantly varied', "
         "'the design is interesting', 'the layout appears dynamic'.",
         kind="subjective", modality="vision"),
    Axis("colorfulness", "VisAWI colorfulness facet — color composition: the "
         "color selection is attractive, the composition harmonious, colors "
         "chosen with skill rather than defaults. Items: 'the color "
         "composition is attractive', 'the colors are appealing', 'the choice "
         "of colors is botched' (reverse).",
         kind="subjective", modality="vision"),
    Axis("craftsmanship", "VisAWI craftsmanship facet — skillful, coherent "
         "integration of all design dimensions with contemporary techniques: "
         "the page appears professionally designed, made with care, nothing "
         "half-done or outdated. Items: 'the layout appears professionally "
         "designed', 'the site is made with care', 'the design is up-to-date'.",
         kind="subjective", modality="vision"),
]
# Lavie & Tractinsky 2004 — the validated 2-factor structure of perceived web
# aesthetics; scale-item adjectives embedded so critics inherit the construct.
AXES_LT: List[Axis] = [
    Axis("functionality", "Requested features actually work, no errors.",
         kind="verifiable", modality="both"),
    Axis("classical", "Classical aesthetics (order and clarity, the dimension "
         "presiding from antiquity): clean, clear, pleasant, symmetrical "
         "design — visual order a viewer finds immediately legible.",
         kind="subjective", modality="vision"),
    Axis("expressive", "Expressive aesthetics (the designer's creativity "
         "breaking conventions): creative, original, fascinating, "
         "sophisticated design with special effects that serve the identity. "
         "Novelty must remain appropriate to the task — novel AND fitting "
         "(the standard definition of creativity), not weird for its own sake.",
         kind="subjective", modality="vision"),
]
# Hassenzahl (AttrakDiff) — pragmatic vs hedonic quality; hedonic split into
# stimulation and identity (perceived independently, both drive attractiveness).
AXES_HEDONIC: List[Axis] = [
    Axis("functionality", "Pragmatic quality: effectiveness and efficiency — "
         "requested features work, users can complete tasks without guessing, "
         "no errors.", kind="verifiable", modality="both"),
    Axis("hedonic_stimulation", "Hedonic quality / stimulation: does the page "
         "feel novel, interesting, exciting — does it stimulate curiosity and "
         "offer something to discover? AttrakDiff items: inventive vs "
         "conventional, captivating vs dull, novel vs ordinary. Novelty must "
         "stay appropriate to the task, not arbitrary.",
         kind="subjective", modality="vision"),
    Axis("hedonic_identity", "Hedonic quality / identity: does the page "
         "communicate a self — a distinct personality, voice and brand the "
         "owner would proudly identify with? AttrakDiff items: stylish vs "
         "tacky, premium vs cheap, integrating vs alienating. A page with no "
         "recognizable identity fails here even if pretty.",
         kind="subjective", modality="vision"),
]
AXIS_SETS = {"main4": AXES_MAIN, "coarse2": AXES_COARSE, "fine6": AXES_FINE,
             "visawi5": AXES_VISAWI, "lt3": AXES_LT, "hedonic3": AXES_HEDONIC}

# Side 'design-first' experiment axis sets (no scoring; each Axis carries its
# full design critic prompt). Only used when design_mode=True.
try:
    from . import side_prompts as _sp
    for _sname, _items in _sp.AXIS_META.items():
        AXIS_SETS[_sname] = [Axis(_k, _name, "subjective", "vision",
                                  critic_prompt=_full)
                             for _k, _name, _persona, _full in _items]
except Exception as _e:  # side prompts optional; never break main import
    import logging as _lg
    _lg.getLogger(__name__).warning("side_prompts not loaded: %s", _e)


@dataclass
class ExperimentConfig:
    arm: str = "MAD"

    # models / servers
    gen_ports: List[int] = field(default_factory=lambda: [8000])
    gen_model: str = "Qwen/Qwen3.6-35B-A3B-FP8"
    # critics must be the SAME tier as the generator (debate quality is bounded
    # by participant capability — 2511.07784); 7B critics would confound H2
    vlm_ports: List[int] = field(default_factory=lambda: [8004])
    vlm_model: str = "Qwen/Qwen2.5-VL-32B-Instruct"

    # iteration regime (user decision 2026-07-15, final v2): CONSENSUS-STOP —
    # obey the evaluator's good_enough (that artifact is the final output),
    # HARD CAP 4 rounds. Tokens are LOGGED and reported as cost, never matched.
    budget_tokens: int = 400_000     # runaway safety guard only; must not bind
    max_rounds_cap: int = 4          # BINDING: hard cap per arm
    # BON draft cap = 5 so BON gets the SAME number of generation calls as the
    # loop arms (initial + 4 revisions = 5); 4 would short BON one generation.
    max_candidates_cap: int = 5      # BINDING: max BON drafts
    early_stop: bool = True          # consensus-stop IS the method's output

    # axes / debate
    axis_set: str = "main4"
    debate_rounds: int = 1           # MAD only; 0 would equal AXES
    # side 'design-first' experiment: no-score design critics, vision SELF,
    # single-page briefs. Reversible — set False to restore main behaviour.
    design_mode: bool = False

    # sampling
    gen_temperature: float = 0.7
    bon_temperature: float = 0.9     # extra diversity for BON drafts
    critic_temperature: float = 0.2
    max_tokens: int = 16384

    # infra
    concurrency: int = 4
    mock: bool = False
    render: bool = True              # in-loop Playwright previews for critics
    viewport: tuple = (1280, 800)

    # shared-r0 paired design (2026-07-16): when set, loop arms load the
    # cached planner spec + initial html from <init_pool>/<app>/ instead of
    # generating their own — removes initial-draw noise from arm comparisons
    # (deep15 showed r0 luck can flip rankings). Empty = classic fresh r0.
    init_pool: str = ""

    # io / data
    output_dir: str = "results/run"
    artifact_root: str = "webgen_out"
    task_source: str = "artifacts"           # "artifacts" (primary) | "webgen"
    webgen_test: str = "external/WebGen-Bench/data/test.jsonl"
    artifacts_json: str = "external/ArtifactsBenchmark/dataset/artifacts_bench.json"
    n_items: Optional[int] = None
    task_ids: Optional[List[str]] = None
    categories: Optional[List[str]] = None   # category filter (or design_forward/low_freedom)
    difficulties: Optional[List[str]] = None # artifacts only: simple|medium|hard

    def axes(self) -> List[Axis]:
        return AXIS_SETS[self.axis_set]

    def subjective_axes(self) -> List[Axis]:
        return [a for a in self.axes() if a.kind == "subjective"]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["axes_resolved"] = [asdict(a) for a in self.axes()]
        return d

    @staticmethod
    def _ports(spec: str) -> List[int]:
        spec = str(spec).strip()
        if ":" in spec:
            lo, hi = spec.split(":"); return list(range(int(lo), int(hi) + 1))
        if "," in spec:
            return [int(x) for x in spec.split(",")]
        return [int(spec)]

    @classmethod
    def from_args(cls, a: argparse.Namespace) -> "ExperimentConfig":
        if a.arm in ("MAD", "DISC") and a.debate_rounds < 1:
            raise ValueError(
                f"{a.arm} with --debate-rounds {a.debate_rounds} would be a "
                "silent duplicate of AXES — debate depth 0 IS the AXES arm; "
                "run --arm AXES instead (pre-registered ablation protocol).")
        return cls(
            arm=a.arm,
            gen_ports=cls._ports(a.gen_ports), gen_model=a.gen_model,
            vlm_ports=cls._ports(a.vlm_ports), vlm_model=a.vlm_model,
            budget_tokens=a.budget_tokens, max_rounds_cap=a.max_rounds_cap,
            max_candidates_cap=a.max_candidates_cap,
            early_stop=not a.no_early_stop,
            axis_set=a.axis_set, debate_rounds=a.debate_rounds,
            design_mode=getattr(a, "design_mode", False),
            gen_temperature=a.gen_temperature, bon_temperature=a.bon_temperature,
            critic_temperature=a.critic_temperature, max_tokens=a.max_tokens,
            concurrency=a.concurrency, mock=a.mock, render=not a.no_render,
            init_pool=a.init_pool,
            output_dir=a.output_dir, artifact_root=a.artifact_root,
            task_source=a.task_source, webgen_test=a.webgen_test,
            artifacts_json=a.artifacts_json, n_items=a.n_items,
            task_ids=(a.task_ids.split(",") if a.task_ids else None),
            categories=(a.categories.split(",") if a.categories else None),
            difficulties=(a.difficulties.split(",") if a.difficulties else None),
        )


def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--arm", default="MAD", choices=list(ARMS))
    p.add_argument("--gen-ports", default="8000")
    p.add_argument("--gen-model", default="Qwen/Qwen3.6-35B-A3B-FP8")
    p.add_argument("--vlm-ports", default="8004")
    p.add_argument("--vlm-model", default="Qwen/Qwen2.5-VL-32B-Instruct")
    p.add_argument("--budget-tokens", type=int, default=400_000)
    p.add_argument("--max-rounds-cap", type=int, default=4)
    p.add_argument("--max-candidates-cap", type=int, default=5,
                   help="BON draft cap; 5 = generation-call parity with loop "
                        "arms (initial + 4 revisions)")
    p.add_argument("--no-early-stop", action="store_true",
                   help="ignore good_enough and always run the full round cap "
                        "(ablation only; default is consensus-stop)")
    p.add_argument("--axis-set", default="main4", choices=list(AXIS_SETS))
    p.add_argument("--design-mode", action="store_true",
                   help="side design-first experiment: no-score design critics, "
                        "vision SELF, design generator prompts (reversible)")
    p.add_argument("--init-pool", default="",
                   help="dir of cached shared r0s (<pool>/<app>/{spec.txt,"
                        "r0.html}); loop arms start from these instead of "
                        "generating their own (paired shared-r0 design)")
    p.add_argument("--debate-rounds", type=int, default=1)
    p.add_argument("--gen-temperature", type=float, default=0.7)
    p.add_argument("--bon-temperature", type=float, default=0.9)
    p.add_argument("--critic-temperature", type=float, default=0.2)
    p.add_argument("--max-tokens", type=int, default=8192)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--mock", action="store_true")
    p.add_argument("--no-render", action="store_true")
    p.add_argument("--task-source", default="artifacts", choices=["artifacts", "webgen"])
    p.add_argument("--webgen-test", default="external/WebGen-Bench/data/test.jsonl")
    p.add_argument("--artifacts-json",
                   default="external/ArtifactsBenchmark/dataset/artifacts_bench.json")
    p.add_argument("--difficulties", default=None,
                   help="artifacts only: comma list of simple,medium,hard")
    p.add_argument("--artifact-root", default="webgen_out")
    p.add_argument("--n-items", type=int, default=None)
    p.add_argument("--task-ids", default=None)
    p.add_argument("--categories", default=None,
                   help="category filter; for artifacts also accepts the "
                        "presets 'design_forward' / 'low_freedom'")
    p.add_argument("--output-dir", default="results/run")
