# GPT-direct one-round user-study experiment

This directory contains the complete 12-task, shared-initialization experiment run on 2026-08-13.

## Conditions

- `r0`: one shared initial artifact per task
- `SELF`: self-refinement from the shared r0
- `FUSED`: one holistic critic, then revision
- `AXES`: four independent axis critiques concatenated verbatim, no moderator
- `CEN_MAD`: four independent axis critiques synthesized by a central moderator
- `MAD`: four independent critics, persona-separated cross-rebuttals, then central moderation

The four axes are Brief & Intent Alignment, Clarity & Information Hierarchy, Visual System & Craft, and Expressiveness & Distinctiveness. All revisions are exactly one round. All screenshots are 1280x800 viewport captures.

## Layout

- `protocol/`: experiment config and exact role prompt templates
- `tasks/<task>/r0/`: shared initial HTML, screenshot, generator prompt, notes, and hashes
- `tasks/<task>/shared_axis_critiques/`: four independent critiques and runtime prompts
- `tasks/<task>/<condition>/`: condition-specific critique/debate/moderation, revised HTML, screenshot, exact generator prompt, notes, and hashes
- `blind/`: shuffled images, public manifest, separately stored key, judge template, exact runtime prompts, raw blind scores, and validation
- `analysis/`: unblinded scores and aggregate statistics

## Judge audit

`independent_scores_blind.json` is retained as the first judge pass, but it is superseded. An audit found that its overall reasons were exactly duplicated across all six same-task images even where the screenshots differed materially.

The accepted result is `independent_scores_blind_v2.json`. It was produced without access to `key.json`, condition names, task directories, HTML, critiques, or previous scores. The judge inspected original-resolution images and performed a same-brief visual audit while blind to condition. `judge_v2_validation.json` verifies 72 unique records, exact schemas, score ranges, hashes, runtime prompts, and zero duplicated reasons within each same-brief group.

Use `analysis/scores_unblinded_v2.json` and `analysis/summary_v2.json` for analysis. The unsuffixed analysis files correspond to the superseded first pass and remain only as an audit trail.

## Reproduce aggregation

```bash
python tools/analyze_gpt_direct_userstudy.py \
  results_b200/gpt_direct_intent4_1r_userstudy \
  --suffix v2
```

The overall score is the judge's independent holistic score, not the arithmetic mean of the four axes.
