# 30-task same-task-grouped blind evaluation

## Protocol

- 30 single-page tasks, three independent stochastic repeats.
- Within each repeat, all arms share the same r0.
- Conditions: SELF, FUSED, AXES, CEN_MAD, MAD; rounds r1–r5.
- Each task's 78 images (3 r0 + 5 conditions × 5 rounds × 3 repeats) were shuffled and judged together.
- The blind judge saw the common brief and anonymous images, but no task ID, condition, repeat, round, HTML, critique, or generation history.
- Scores are integer 0–100 for four intent4 axes plus an independently judged overall score.
- 2,340/2,340 screenshots were directly inspected. All score schemas, IDs, order, image hashes, and 30 instantiated runtime prompts passed validation.

## Final-round mean scores

| Condition | Brief | Clarity | Craft | Expressiveness | Overall |
|---|---:|---:|---:|---:|---:|
| R0 | 69.49 | 68.16 | 68.68 | 68.21 | 68.06 |
| SELF r5 | 71.00 | 69.13 | 70.13 | 69.42 | **69.09** |
| FUSED r5 | 69.48 | 67.92 | 68.44 | 68.47 | 67.51 |
| AXES r5 | 68.93 | 66.87 | 67.83 | 67.52 | 67.09 |
| CEN_MAD r5 | 68.82 | 67.56 | 68.51 | 67.29 | 66.79 |
| MAD r5 | 67.43 | 65.94 | 66.59 | 66.19 | 65.99 |

Paired against the exact same task/repeat r0, SELF r5 improved by +1.03 overall on average (48 wins, 8 ties, 34 losses). FUSED was -0.54 (39/5/46), AXES -0.97 (47/4/39), CEN_MAD -1.27 (40/5/45), and MAD -2.07 (42/5/43).

## Trajectory result

The best round was not consistently r5. Overall means by round were:

- SELF: 67.31, 68.73, **69.33**, 68.54, 69.09.
- FUSED: 67.71, 69.27, 68.42, **69.73**, 67.51.
- AXES: 67.59, 66.44, **69.24**, 67.71, 67.09.
- CEN_MAD: 67.70, 66.82, **68.53**, 65.73, 66.79.
- MAD: 67.97, 67.91, **68.13**, 68.01, 65.99.

The grouped evaluation therefore indicates over-refinement after a useful intermediate round, especially for FUSED and the multi-critic conditions. FUSED r4 was the strongest aggregate condition/round (69.73), while forcing every method to r5 materially understated its best observed performance. MAD's r5 decline was the largest.

## Audit files

- `manifest.json`: blind grouped packet (no condition labels).
- `JUDGE_GROUP_PROMPT_TEMPLATE.txt` and `runtime_prompts/TG01.txt`–`TG30.txt`: exact judge instructions.
- `independent_scores_grouped_blind.json`: 2,340 blind judgments with reasons.
- `blind_validation.json`: combined blind validation.
- `key.json`: separately stored identity mapping.
- `unblinded_scores.json` / `.csv`: unblinded item-level scores.
- `analysis_condition_round.json` / `.csv`: condition-by-round means.
- `analysis_condition_round_repeat.json`: repeat-level means.
- `analysis_final_summary.json`: r0 and r5 summary.
