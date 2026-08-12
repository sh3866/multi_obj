# Design4 12-task experiment — audited results

## Executive conclusion

The completed experiment provides **directional but not statistically conclusive evidence** for MAD. At round 5, MAD has the highest raw overall mean (**76.67**) across 12 tasks, followed by FUSED (**75.00**), AXES (**73.67**), and SELF (**73.25**). MAD also has the best mean on every judge axis at round 5. However, task-level paired confidence intervals overlap zero and all exact sign-flip tests are nonsignificant at 0.05. With only 12 tasks and one judgment per artifact, this is a promising effect estimate, not a proven win.

The matched 4-task table places the independently created Gold trajectory on the same blind scale. Across all six rounds, Gold averages **77.96 overall**, above MAD **73.67**, FUSED **71.54**, SELF **69.25**, and AXES **69.21**. At round 5, Gold is **79.25**, MAD **76.00**, AXES **74.00**, SELF **71.75**, and FUSED **71.25**. Gold peaks at round 4 (**83.75**) and then drops, so even expert critique does not guarantee monotonic improvement.

## Protocol

- Tasks: the 12 modified ArtifactsBench single-page briefs in sideproj_subjective/tasks.jsonl.
- Methods: SELF, FUSED, AXES, MAD.
- Generator and Qwen critics: Qwen/Qwen3.6-27B served by two vLLM endpoints.
- Shared initial artifacts: each method starts from the same cached r0 HTML per task.
- Refinement: five revision rounds, retaining r0 through r5.
- Main artifacts: 12 × 4 × 6 = **288** screenshots.
- Calibration/comparison anchors: 4 tasks × 6 rounds = **24 Gold** screenshots.
- Blind pool: all **312** images globally shuffled and relabeled K001–K312.
- Judge: three independent GPT-5.6 visual judges, 104 random images each. Judges were restricted to one anonymous manifest, the brief, the image, and the exact shared rubric. They did not access key.json, methods, rounds, HTML, traces, critiques, or previous scores.
- Scores: integer 0–100 for Layout & Hierarchy, Spacing/Alignment/Balance, Color & Typography, Style/Originality/Finish, and an independently assigned holistic Overall score. Overall is not an arithmetic average.
- Every instantiated judge prompt and every axis-specific reason is saved.

## Integrity result

The generation audit is PASS_WITH_DOCUMENTED_AUDIT_LIMITATION:

- 48/48 task-method traces present.
- 288/288 candidate HTML files complete.
- 288/288 PNGs readable at exactly 1280×800.
- 1,147 API calls represented; zero API failures.
- Two generation attempts ended with finish_reason=length; both were rejected and successfully retried.
- AXES: 240 critic and 60 moderator contracts passed.
- MAD: 240 critic, 240 rebuttal, and 60 moderator contracts passed.
- Five original FUSED task trajectories contained literal ... placeholder critiques that the old nonempty-string validator had accepted. The validator was strengthened, and tasks 2, 3, 4, 7, and 8 were regenerated in full from the same shared r0. All 25 replacement critic outputs passed validation and preserve exact runtime prompts/raw responses.
- The other 35 legacy FUSED rounds preserve full parsed critique and suggestion but predate exact runtime-prompt/raw-response persistence. This is recorded as an auditability limitation, not represented as verbatim raw data.

## Main 12-task results

### Round-5 endpoint

| Method | Overall | Layout | Spacing | Color/type | Style/finish |
|---|---:|---:|---:|---:|---:|
| MAD | **76.67** | **76.92** | **75.83** | **80.58** | **77.83** |
| FUSED | 75.00 | 74.25 | 74.92 | 78.75 | 76.42 |
| AXES | 73.67 | 74.25 | 72.92 | 78.83 | 75.50 |
| SELF | 73.25 | 72.92 | 73.08 | 79.08 | 74.33 |

### Overall trajectory

| Method | r0 | r1 | r2 | r3 | r4 | r5 |
|---|---:|---:|---:|---:|---:|---:|
| SELF | 75.58 | 72.00 | 73.58 | 72.33 | 70.33 | 73.25 |
| FUSED | 73.83 | 67.83 | 73.00 | 72.08 | 74.92 | 75.00 |
| AXES | 74.92 | 69.75 | 75.75 | 74.92 | 72.67 | 73.67 |
| MAD | 71.92 | **78.17** | 75.92 | 76.08 | 73.25 | **76.67** |

Although r0 HTML is shared within each task, it was rendered and judged independently for each arm. The 3.67-point spread among arm r0 means therefore estimates animation/render timing plus judge-assignment noise, not a treatment difference. Using the per-task mean of all four observed r0s as a common reference gives r5 changes of SELF −0.81, FUSED +0.94, AXES −0.40, and MAD +2.60. Their 95% task-bootstrap intervals all include zero.

### Task-level inference

| Contrast | Mean difference | 95% task bootstrap CI | Exact sign-flip p |
|---|---:|---:|---:|
| MAD r5 − its observed r0 | +4.75 | [−1.17, 10.75] | 0.178 |
| MAD r5 − shared-r0 reference | +2.60 | [−3.48, 8.23] | 0.419 |
| MAD r5 − SELF r5 | +3.42 | [−0.83, 8.67] | 0.246 |
| MAD r5 − AXES r5 | +3.00 | [−0.42, 6.42] | 0.154 |
| MAD r5 − FUSED r5 | +1.67 | [−2.75, 7.33] | 0.679 |

None reaches conventional statistical significance.

## Matched 4-task comparison including Gold

All-round means use 24 artifacts per method (4 tasks × 6 rounds):

| Method | Overall | Layout | Spacing | Color/type | Style/finish |
|---|---:|---:|---:|---:|---:|
| GOLD | **77.96** | **77.46** | **76.83** | **82.17** | **78.50** |
| MAD | 73.67 | 72.79 | 71.38 | 80.79 | 75.08 |
| FUSED | 71.54 | 71.21 | 72.00 | 77.88 | 74.17 |
| SELF | 69.25 | 68.38 | 68.50 | 78.25 | 71.75 |
| AXES | 69.21 | 68.67 | 68.83 | 78.13 | 71.96 |

Gold trajectory: **68.50 → 75.75 → 79.00 → 81.50 → 83.75 → 79.25**. The strong r0-to-r4 rise demonstrates that high-quality critique can cause large visible improvement on these tasks, while the r5 regression demonstrates the need for candidate selection or stopping rather than blindly taking the last round.

## Representative MAD conflict-resolution case

For task 7, MAD improved from r2 **45** to r3 **76** (+31). The four critics disagreed about strict alignment versus visual-weight distribution, negative space versus atmospheric richness, and clustering versus scattering creatures. The moderator selected explicit compromises:

- align the top UI but center the bottom action to form a balanced triangular composition;
- retain negative space while adding only subtle noise and radial glow;
- keep creatures scattered, but unify them into one bioluminescent family.

The blind judge independently described r2 as a “sparse collection mockup” with weak grouping and missing gameplay imagery. For r3 it identified a central luminous focal creature, controlled empty space, a rich nocturnal palette, and bespoke rendering, while still noting the missing player/net. This is a genuine example where recorded cross-axis conflict resolution aligns with a large blind visual improvement. It is compelling qualitative evidence, but one case does not establish the average causal effect.

## Gold-based judge centering

The three judge parts' Gold overall means were 78.33 (n=6), 74.67 (n=9), and 81.00 (n=9), versus a pooled Gold mean of 77.96. Raw scores remain the primary results. A transparent sensitivity table additionally applies additive Gold centering per criterion (raw − judge Gold mean + pooled Gold mean, clipped to 0–100). This changes all-round main overall means only modestly: SELF 72.33, FUSED 73.08, AXES 73.84, MAD 75.14, preserving the ranking.

This centering is only a sensitivity check: Gold images were distributed rather than replicated across all judges, so judge effects are partly confounded with which Gold task/rounds each judge received.

## Interpretation

The evidence supports three claims:

1. Gold critique is meaningfully actionable: it produces a large aggregate improvement through r4 and scores above all Qwen-driven methods on matched tasks.
2. MAD is the most promising Qwen-driven method in this run: it leads the round-5 mean, leads every round-5 axis, and contains at least one clear conflict-resolution success.
3. Iteration is unstable: every method exhibits large stepwise regressions, and the best candidate often occurs before r5. A selection/stopping mechanism is likely more important than simply increasing rounds.

What this experiment does **not** prove is that MAD is statistically superior. The effective sample size for method comparison is 12 tasks, there is one judge observation per image, and trajectories mix genuine visual change with judge/render noise. A stronger follow-up would replicate each anonymous image across all judges (or at least a balanced subset), pre-register a best-of-trajectory selector, and expand task count.

## Files

- INTEGRITY_AUDIT.json: generation and transcript audit.
- trajectory_blind_gold_calibrated/JUDGE_PROMPT_TEMPLATE.txt: exact shared judge template.
- trajectory_blind_gold_calibrated/runtime_prompts/: all 312 exact instantiated prompts.
- trajectory_blind_gold_calibrated/independent_gpt56_scores_blind.json: locked anonymous judgments.
- trajectory_blind_gold_calibrated/independent_gpt56_scores_unblinded.json: raw unblinded results.
- trajectory_blind_gold_calibrated/scores_unblinded_with_gold_centering.json: sensitivity scores.
- trajectory_blind_gold_calibrated/tables/: CSV/JSON summaries, trajectories, pairwise tests, and ranked round transitions.
- SELF,FUSED,AXES,MAD/problems/task/: candidate HTML/PNG, trace, and final artifact.
