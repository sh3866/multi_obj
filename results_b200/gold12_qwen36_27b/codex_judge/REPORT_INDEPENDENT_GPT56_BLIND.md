# Gold12 — independent fresh-context GPT-5.6 blind re-evaluation

## Protocol

A new GPT-5.6 agent with no conversation history could read only the anonymous `manifest.json`, `packet/`, and `sheets/`. It could not read the key, prior scores, reports, or production files and was not told which methods existed. It received the same detailed four specialist personas and holistic completeness-first rubric used for the main four-arm independent evaluation. All 48 scores were saved and validated before variant mapping.

## Independent result

| Variant | Overall | Δ vs r0 | Task W/T/L | Catastrophic ≤3 |
|---|---:|---:|---:|---:|
| r0 | **6.83** | — | — | 0 |
| GOLD-FUSED | **7.13** | **+0.29** | 6/3/3 | 0 |
| GOLD-AXES | **6.96** | **+0.13** | 7/4/1 | 1 |
| GOLD-MAD | **6.46** | **−0.38** | 3/4/5 | 2 |

Exact paired sign-flip p-values versus r0: FUSED 0.582; AXES 0.906; MAD 0.359. None is significant at n=12.

## Revision to the earlier conclusion

The earlier same-Codex blind evaluation scored r0 6.75, FUSED 7.83, AXES 7.42, MAD 6.42. The independent judge agrees strongly at image level (overall Pearson r=0.814, Spearman ρ=0.669, MAE=0.80) and agrees that MAD regresses, but it estimates much smaller one-round gains for FUSED/AXES.

Therefore the defensible conclusion is narrower: a one-round high-quality Gold critique **can** improve individual artifacts and FUSED/AXES have favorable win counts, but this 12-task run does not show a large or statistically reliable mean improvement under an independent judge. The catastrophic ab000001 regressions materially offset gains elsewhere. “Gold provides a clear +1 point average” is not supported after independent re-evaluation.

## Audit files

- `independent_gpt56_scores_blind.json`: independent locked anonymous scores.
- `independent_gpt56_scores_unblinded.json`: mapping joined after lock.
- `manifest.json`, `packet/`, `sheets/`: exact anonymous material.
