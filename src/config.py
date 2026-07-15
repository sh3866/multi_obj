"""Experiment configuration (v2 — pre-registered design, see PLAN.md).

Six arms, each isolating one mechanism (H1 axis separation, H2 debate):
  ZS     zero-shot single pass                       (floor anchor)
  BON    best-of-N diverse sampling until budget      (no-loop baseline)
  SELF   self-refine loop, no external evaluator      (SELF->FUSED = external eval)
  FUSED  planner + generator + ONE fused evaluator    (Anthropic harness; FUSED->AXES = H1)
  AXES   per-objective critics, independent, moderator (AXES->MAD = H2)
  MAD    AXES + cross-critique (conflicts) before synthesis

Execution regime (2026-07-15): fixed 4-iteration cap per arm with self-judged
early stop; tokens logged (not matched). Candidates keep `tokens_at`+round stamps
so round-fixed / token-cut / consensus-stop views are all recoverable post hoc.

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


# Main axes = the Anthropic harness rubric (design/originality/craft/functionality),
# one agent per criterion. Efficiency deliberately EXCLUDED (rewards degenerate pages).
AXES_MAIN: List[Axis] = [
    Axis("functionality", "Do the requested features actually work: interactive "
         "elements, forms, navigation operate without errors.",
         kind="verifiable", modality="both"),
    Axis("design", "Design quality: coherence, mood, identity; layout harmony, "
         "color, typography, spacing.", kind="subjective", modality="vision"),
    Axis("originality", "Originality: custom decisions vs template look; "
         "distinctive, memorable, no AI-slop patterns.",
         kind="subjective", modality="vision"),
    Axis("craft", "Craft: detail, consistency, finish; no rough edges, "
         "polished states and edge cases.", kind="subjective", modality="vision"),
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
    Axis("simplicity", "Effortless perception: clear, orderly, homogeneous "
         "layout that groups well and is easy to grasp.",
         kind="subjective", modality="vision"),
    Axis("diversity", "Inventive, dynamic layout: visually rich, varied, "
         "interesting rather than monotonous.",
         kind="subjective", modality="vision"),
    Axis("colorfulness", "Color choice and composition: attractive, harmonious, "
         "well-composed palette.", kind="subjective", modality="vision"),
    Axis("craftsmanship", "Skillful, modern execution: professionally made "
         "with appropriate contemporary techniques, nothing half-done.",
         kind="subjective", modality="vision"),
]
# Lavie & Tractinsky 2004 — minimal validated 2-factor aesthetics structure
AXES_LT: List[Axis] = [
    Axis("functionality", "Requested features actually work, no errors.",
         kind="verifiable", modality="both"),
    Axis("classical", "Classical aesthetics: clean, clear, orderly, symmetrical, "
         "pleasant design.", kind="subjective", modality="vision"),
    Axis("expressive", "Expressive aesthetics: original, sophisticated, "
         "fascinating, creative design.", kind="subjective", modality="vision"),
]
AXIS_SETS = {"main4": AXES_MAIN, "coarse2": AXES_COARSE, "fine6": AXES_FINE,
             "visawi5": AXES_VISAWI, "lt3": AXES_LT}


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

    # iteration regime (user decision 2026-07-15): FIXED 4-ROUND CAP for every
    # arm (BON=4 drafts, SELF=4 refines, FUSED/AXES/MAD=4 critique rounds) with
    # self-judged early stop allowed. Tokens are LOGGED and reported (three-view
    # reporting: round-fixed / token-cut / consensus-stop) but no longer matched.
    budget_tokens: int = 400_000     # non-binding safety ceiling
    max_rounds_cap: int = 4          # BINDING: max iterations per arm
    max_candidates_cap: int = 4      # BINDING: max BON drafts
    early_stop: bool = True          # obey good_enough / high fused score

    # axes / debate
    axis_set: str = "main4"
    debate_rounds: int = 1           # MAD only; 0 would equal AXES

    # sampling
    gen_temperature: float = 0.7
    bon_temperature: float = 0.9     # extra diversity for BON drafts
    critic_temperature: float = 0.2
    max_tokens: int = 8192

    # infra
    concurrency: int = 4
    mock: bool = False
    render: bool = True              # in-loop Playwright previews for critics
    viewport: tuple = (1280, 800)

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
        return cls(
            arm=a.arm,
            gen_ports=cls._ports(a.gen_ports), gen_model=a.gen_model,
            vlm_ports=cls._ports(a.vlm_ports), vlm_model=a.vlm_model,
            budget_tokens=a.budget_tokens, max_rounds_cap=a.max_rounds_cap,
            max_candidates_cap=a.max_candidates_cap,
            early_stop=not a.no_early_stop,
            axis_set=a.axis_set, debate_rounds=a.debate_rounds,
            gen_temperature=a.gen_temperature, bon_temperature=a.bon_temperature,
            critic_temperature=a.critic_temperature, max_tokens=a.max_tokens,
            concurrency=a.concurrency, mock=a.mock, render=not a.no_render,
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
    p.add_argument("--max-candidates-cap", type=int, default=4)
    p.add_argument("--no-early-stop", action="store_true")
    p.add_argument("--axis-set", default="main4", choices=list(AXIS_SETS))
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
