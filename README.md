# multi_obj v2 — MAD for multi-objective optimization of subjective objectives

Does axis-separated multi-agent debate beat compute-matched baselines when the
objectives are subjective and conflicting (design quality, originality, craft vs
functionality)? Testbed: ArtifactsBench (design-forward interactive artifacts:
games / SVG / web apps / simulations), generator Qwen3.6-35B.

- **PLAN.md** — pre-registered design (hypotheses H1/H2/H3, arms, metrics, tests).
  Frozen once the main run starts.
- **RESEARCH_BASELINES.md** — literature survey backing every design choice.

## Arms

ZS · BON · SELF · FUSED (Anthropic-harness fused evaluator) · AXES (per-objective
critics, no debate) · MAD (axis critics + cross-critique). All run to the SAME
total-token budget per task; no early stopping; every intermediate artifact is a
stored candidate stamped with `tokens_at`.

## Pipeline

```
run_generate.py   one arm x N tasks under a token budget (--task-source artifacts)
                  -> results/<tag>/<ARM>/problems/<app>/{candidates/, final*.png, trace.json}
run_judge.py      held-out judge (VL-72B :8100), forced-choice pairwise, both orders
                  -> results/<tag>/judge/results_<judge>.jsonl   (BT primary)
run_checklist.py  ArtifactsBench checklist scoring on temporal screenshots
                  -> results/<tag>/judge/checklist_<judge>.jsonl (diagnostics/curves)
collect.py        budget compliance + BT + sign tests + gate + checklist
                  + leniency + inter-judge agreement -> results/<tag>/SUMMARY.md
```

## Quick start

```bash
# offline smoke (no GPU/servers):
bash scripts/run_smoke.sh

# pilot (see PLAN.md Phase 1):
bash scripts/run_pilot.sh pilot1 10
```

## Evaluation isolation (do not violate)

| layer | signals | used for |
|---|---|---|
| A | VL-32B critics (= generator tier), Playwright probe, UIClip | revision only, never evidence |
| B | held-out VL-72B: pairwise BT + checklist (+ Gemini when key available) | screening; UIClip banned here |
| C | human blind pairwise (Phase 3) | final claims |

## Layout

```
src/infra/      client (vLLM round-robin + BudgetedUsage + mock), render, parse, io
src/data/       artifacts_data (ArtifactsBench, primary), webgen_data/webgen_artifact (legacy)
src/arms/       common (budgeted runner, shared selector) + the 6 frozen arms
src/critics/    prompts, axis/fused critics, debate (iterative cross-critique)
src/signals/    uiclip, design_metrics  (layer A only)
src/eval_b/     judge (pairwise), checklist (ArtifactsBench absolute), bt, pareto
_archive/       v1 code (S0-S14 era); results/_archive_pre_reset/ has ver1-6
```
