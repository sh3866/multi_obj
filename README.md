# multi_obj — Multi-agent critique for subjective, multi-objective artifact quality

**Question.** An LLM generator in a loop with an evaluator produces steadily better
artifacts (web pages, UIs, games). But the evaluator is usually *one agent giving one
verdict*, while artifact quality is **several objectives that trade off against each
other** — functionality, layout, spacing, colour/typography, originality, craft.

> Does giving each objective its own critic — and letting the critics argue —
> produce a better final artifact than one fused evaluator?

Multi-agent debate (MAD) is almost exclusively evaluated on **reasoning** tasks with
verifiable answers, and even there its advantage over a well-prompted single agent is
contested. This project points it at the opposite setting: **subjective quality with
no answer key**, which today is handled by training-time preference learning (RLHF).

Testbed: ArtifactsBench (design-forward interactive artifacts). Generator:
Qwen3.6-35B-A3B, self-hosted on vLLM.

## Documents

| file | contents |
|---|---|
| **[RESULTS.md](RESULTS.md)** | every judged experiment, what it controlled, and what it showed — including contradictions |
| [PLAN.md](PLAN.md) | pre-registered design (hypotheses, arms, metrics, tests), frozen before the main run |
| [RESEARCH_BASELINES.md](RESEARCH_BASELINES.md) | literature survey behind each design choice |
| [HANDOFF.md](HANDOFF.md) | operational state / how to resume |

## Arms

Everything is held fixed except **the structure of the evaluator**.

| arm | evaluator | isolates |
|---|---|---|
| `ZS` | none (single pass) | floor anchor |
| `SELF` | generator critiques its own work | value of *any* external evaluator |
| `FUSED` | one fused critic (the harness baseline) | H1 control |
| `AXES` | one critic per objective → moderator | **H1**: does decomposition help? |
| `MAD` | AXES + cross-critique debate → moderator | **H2**: does arguing help? |
| `DISC` | orchestrator discovers the axes, then debates | exploratory |

Critics emit **critique only**; the generator rewrites the code.

## Controls

- **Shared r0** — all arms start from the *same* initial draft (common random
  numbers). Without this the initial-draft lottery dominates arm ranking; see
  [RESULTS.md §1](RESULTS.md).
- **Budget-matched** — equal total token budget per task, not equal rounds.
- **Consensus-stop** — each arm stops when *its own* evaluator declares the work
  good enough, so evaluator leniency becomes measurable.
- **Blind, held-out judging** — the judge is never an in-loop model; variants are
  anonymised to codes, shuffled, given neutral paths, and un-mapped only after
  scoring.

## Pipeline

```
make_r0_pool.py    one shared initial draft per task
                   -> results/<tag>/r0_pool/<seed>/<app>/r0.html

run_generate.py    one arm x N tasks under a token budget
                   -> results/<tag>/<seed>/<ARM>/problems/<app>/
                        candidates/  final_t{0,1,2}.png  trace.json

run_judge.py       held-out judge, absolute 0-10 per axis on a temporal
                   screenshot series (load / settled / after-click)
                   -> results/<tag>/judge/scores_<judge>.jsonl

run_checklist.py   ArtifactsBench checklist scoring (diagnostics)
collect.py         budget compliance, sign tests, discrimination gate
```

Rendering is headless Chromium via Playwright and runs on CPU
(`tools/oracle_render.py` is a one-file example).

## Reports

Self-contained HTML reports (images inlined) are built by:

```
tools/make_combined_report.py    main experiments, 4 tabs
tools/make_side_report.py        design-only side study + oracle ceiling study
```

They are written under `results/` and are **not** tracked by git.

## Repository layout

```
src/            arms, critics, debate, evaluation, infra (vLLM client, render, parse)
tools/          report builders, blind un-mapping, diagnostics
cluster/        Slurm sbatch scripts (H200 / A100, vLLM serving)
sideproj_subjective/   design-only briefs and critic prompt set
slides/         lab-meeting decks
results/        all run artifacts — git-ignored (8+ GB)
```

## Status

An evaluator loop clearly beats a single pass. Whether **decomposition and debate**
beat a fused evaluator is supported by exactly one controlled run and contradicted by
three earlier, less-controlled ones. On *pure* design tasks the effect disappears
entirely, and an oracle critic aligned with the judge lifts quality for one round and
then plateaus — which points at the generator's ability to absorb long revision
instructions without regression, rather than at critique quality.

See [RESULTS.md](RESULTS.md) for the numbers and the open items.
