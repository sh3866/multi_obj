# Qwen3.8 grouped-blind evaluation

## Protocol

- Source run: `intent4_qwen38_27b_30task_3seed_5r`
- 30 same-task groups, 78 anonymous candidates per group, 2,340 total images
- Each group contains three shared r0 candidates and r1–r5 from five arms across three repeats
- Candidates were shuffled within task; judges could compare only candidates answering the same brief
- Four intent4 dimensions were scored independently from 0–100, plus a separate holistic `overall` score
- Every image has five visible-evidence reasons containing a strength and a limitation
- Judges were blind to arm, repeat, round, source HTML, critiques, and prior scores

The initial judgments are preserved in `v1_initial/`. A stricter audit found reused reason text across different PNG hashes in 18 groups, so those groups were directly re-inspected and replaced. In the final v2 result, all 11,700 reasons are at least 40 characters and there are zero exact reason duplicates across different image hashes within any task and dimension.

## Final r5 scores

| Condition | Overall | Brief & intent | Clarity & hierarchy | Visual system & craft | Expressiveness |
|---|---:|---:|---:|---:|---:|
| FUSED | 74.6889 | 73.9889 | 75.8111 | 77.3444 | 75.2444 |
| CEN_MAD | 73.8111 | 73.1222 | 75.1444 | 76.1222 | 74.4556 |
| SELF | 73.7222 | 72.3556 | 75.4556 | 76.7556 | 73.9222 |
| AXES | 72.3333 | 71.0889 | 73.8111 | 75.4889 | 72.9444 |
| MAD | 71.3556 | 70.0000 | 73.3889 | 74.8889 | 72.4222 |
| Shared r0 | 70.0000 | 68.1778 | 72.4111 | 73.9778 | 71.0333 |

Each row has 90 observations (30 tasks × 3 repeats). Overall is independently judged, not the mean of the four dimensions.

## Paired r5 change from the matching shared r0

| Condition | Mean overall delta | Improved | Tied | Declined | Repeat deltas (0 / 1 / 2) |
|---|---:|---:|---:|---:|---:|
| FUSED | +4.6889 | 39 | 16 | 35 | +6.0667 / −1.4333 / +9.4333 |
| CEN_MAD | +3.8111 | 46 | 14 | 30 | +2.8667 / −0.1000 / +8.6667 |
| SELF | +3.7222 | 43 | 21 | 26 | +4.8667 / +4.6333 / +1.6667 |
| AXES | +2.3333 | 38 | 12 | 40 | +3.7000 / −1.5000 / +4.8000 |
| MAD | +1.3556 | 47 | 12 | 31 | +4.0000 / −1.0000 / +1.0667 |

These are paired by task and repeat, so every r5 candidate is compared with the exact shared r0 from which that trajectory began.

## Round trajectory

| Condition | r1 | r2 | r3 | r4 | r5 | Best round |
|---|---:|---:|---:|---:|---:|---:|
| SELF | 73.2444 | 74.7333 | 74.1111 | 73.3000 | 73.7222 | r2 |
| FUSED | 69.4444 | 73.6889 | 72.5444 | 74.6556 | 74.6889 | r5 |
| AXES | 71.7667 | 71.5000 | 71.1000 | 71.3333 | 72.3333 | r5 |
| CEN_MAD | 75.0444 | 73.5889 | 72.8444 | 72.8333 | 73.8111 | r1 |
| MAD | 70.6667 | 71.8889 | 70.1333 | 71.7667 | 71.3556 | r2 |

## Interpretation

- At r5, FUSED is highest overall and has the largest mean paired gain over r0. Its gain is not uniform: 39 trajectories improved and 35 declined, and repeat 1 was negative.
- CEN_MAD is second at r5 and improves more individual trajectories than FUSED, but its best aggregate result occurs immediately at r1. Additional rounds erode much of that early gain before a partial r5 recovery.
- SELF is close to CEN_MAD at r5 and is the only arm with positive mean paired gains in all three repeats. Its aggregate peak is r2, not r5.
- AXES produces a modest positive average gain but more declines than improvements. Simply concatenating all four critiques without arbitration is less reliable here than a fused critic or centralized synthesis.
- MAD has the smallest mean gain despite the largest number of individually improved trajectories. This means its improvements tend to be small while some regressions are large enough to suppress the mean.
- Five rounds are not universally beneficial. Only FUSED and AXES peak at r5; SELF and MAD peak at r2, while CEN_MAD peaks at r1.
- Repeat-level variation is large. The ranking should therefore be treated as descriptive evidence from these three repeats rather than a stable population estimate or a significance claim.

## Authoritative files

- `independent_scores_grouped_blind.json`: final manifest-ordered blind judgments
- `blind_validation.json`: global validation and score hash
- `runtime_prompts/TG01.txt` … `TG30.txt`: saved instantiated judge prompts
- `analysis_condition_round.json/.csv`: arm × round means
- `analysis_condition_round_repeat.json`: repeat-specific means
- `analysis_final_summary.json`: shared r0 and r5 summary
- `analysis_paired_r0.json/.csv`: paired r5-minus-r0 analysis
- `unblinded_scores.json/.csv`: identity mapping applied only after blind validation
