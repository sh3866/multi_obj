# Independent blind GPT judge: unblinded summary

ArtifactsBench original task/checklist protocol with an independent GPT referee; one shared r0 and one revision round; n=12 paired tasks. These are not official Gemini leaderboard scores.

| Condition | Mean | Median | SD | Δ vs r0 | 95% paired bootstrap CI | W/T/L vs r0 | Sign p |
|---|---:|---:|---:|---:|---:|---:|---:|
| r0 | 59.25 | 60.50 | 9.77 | +0.00 | [0.00, 0.00] | 0/12/0 | — |
| SELF | 58.50 | 58.50 | 10.43 | -0.75 | [-2.08, 0.42] | 1/8/3 | 0.6250 |
| FUSED | 58.50 | 58.50 | 10.43 | -0.75 | [-2.08, 0.42] | 1/8/3 | 0.6250 |
| AXES | 58.50 | 58.50 | 10.43 | -0.75 | [-2.08, 0.42] | 1/8/3 | 0.6250 |
| CEN_MAD | 58.50 | 58.50 | 10.43 | -0.75 | [-2.08, 0.42] | 1/8/3 | 0.6250 |
| MAD | 58.50 | 58.50 | 10.43 | -0.75 | [-2.08, 0.42] | 1/8/3 | 0.6250 |

Interpretation: bootstrap intervals and sign tests are descriptive with only 12 tasks; no multiplicity correction was applied. Inspect task-level reasons before drawing causal conclusions.
