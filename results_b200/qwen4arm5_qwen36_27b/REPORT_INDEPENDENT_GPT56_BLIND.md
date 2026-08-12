# Independent fresh-context GPT-5.6 blind evaluation

## Independence protocol

A new GPT-5.6 agent was started with no conversation history. It was allowed to read only `codex_blind/manifest.json`, `packet/`, and `sheets/`. It was explicitly forbidden from opening the arm key, prior scores, or any other repository files. It was told neither the production methods nor their names.

The judge received detailed specialist personas for Layout & Hierarchy, Spacing/Alignment/Balance, Color & Typography, and Style/Originality/Finish. It directly scored a separate holistic overall and wrote one visible-evidence reason per image. All 48 scores were saved and validated against the anonymous manifest before the arm key was joined.

## Independent result

| Arm | Layout | Spacing | Color/type | Style/finish | Overall | Catastrophic ≤3 |
|---|---:|---:|---:|---:|---:|---:|
| SELF | 5.33 | 5.67 | 5.67 | 5.92 | **5.17** | **5/12** |
| FUSED | 6.83 | 7.00 | 7.42 | **7.67** | **6.50** | 1/12 |
| AXES | **7.25** | **7.33** | **7.58** | 7.50 | **6.92** | 1/12 |
| MAD | 7.08 | 6.92 | **7.58** | 7.42 | **6.83** | 2/12 |

Independent ordering: `AXES 6.92 > MAD 6.83 > FUSED 6.50 > SELF 5.17`.

## Agreement with the original method-blind Codex scoring

| Measure | Original Codex | Fresh GPT-5.6 |
|---|---:|---:|
| SELF | 5.25 | 5.17 |
| FUSED | 6.50 | 6.50 |
| AXES | 6.83 | 6.92 |
| MAD | 7.00 | 6.83 |

The two judges reproduce the same substantive structure. Their two-judge descriptive averages are SELF 5.21, FUSED 6.50, AXES 6.88, MAD 6.92. AXES and MAD are effectively tied; both exceed FUSED descriptively, and every external-critic arm exceeds SELF.

- Overall image-level Pearson r=0.874, Spearman ρ=0.768, MAE=0.67 points.
- Catastrophic/non-catastrophic agreement: 46/48 images; each judge identified nine catastrophic images and agreed on eight.
- Axis Pearson correlations: Layout 0.953; Spacing 0.917; Color/type 0.854; Style/finish 0.917.

This high agreement is important because the second judge knew nothing about the experimental methods and never saw the first judge's scores.

## Statistical caution

The independent judge's Friedman test is χ²=5.010, p=0.171. Exact paired sign-flip tests: FUSED−SELF p=0.185; AXES−SELF p=0.086; MAD−SELF p=0.147; AXES−FUSED p=0.594; MAD−FUSED p=0.742; MAD−AXES p=1.000. With 12 tasks, no arm difference is conventionally significant; the replicated ordering is strong descriptive evidence, not a definitive population claim.

## Conclusion

The independent rerun strengthens the earlier conclusion and slightly changes the top rank. It confirms that SELF is much less reliable, FUSED is a strong low-cost baseline, and structured multi-critic methods are descriptively best. It does **not** support a claim that MAD debate beats AXES: the fresh judge ranks AXES first, the original judge ranks MAD first, and their difference is negligible under both.

## Audit files

- `codex_blind/independent_gpt56_scores_blind.json`: independent scores locked before key access.
- `codex_blind/independent_gpt56_scores_unblinded.json`: post-lock arm join.
- `codex_blind/manifest.json`, `packet/`, `sheets/`: evaluated anonymous material.
