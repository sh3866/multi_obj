# Codex direct blind evaluation

## Protocol

- 12 tasks × 4 variants = 48 screenshots.
- Fresh random codes hid the variant mapping within each task.
- Codex saw the brief, four anonymous screenshots, and all evaluation axes, but not the mapping.
- All scores and visible-evidence reasons were saved before unblinding.
- Two copied-code typos were corrected against the manifest before unblinding; both matches were unique within their task and no variant mapping was used.
- Axes: Layout & Hierarchy; Spacing, Alignment & Balance; Color & Typography; Style, Originality & Finish. Overall also penalizes missing required content and visibly broken output.

## Aggregate scores (0–10)

| Variant | Layout | Spacing | Color/type | Style/finish | Overall | Δ vs r0 | Task W/T/L vs r0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| r0 | 7.00 | 7.08 | 7.75 | 7.17 | 6.75 | — | — |
| GOLD-FUSED | 8.25 | 8.08 | 8.17 | 8.00 | **7.83** | **+1.08** | **7 / 4 / 1** |
| GOLD-AXES | 7.67 | 7.42 | 8.00 | 7.75 | **7.42** | **+0.67** | **8 / 2 / 2** |
| GOLD-MAD | 6.83 | 7.08 | 7.50 | 7.00 | **6.42** | **−0.33** | **3 / 4 / 5** |

Two-sided exact sign tests after dropping ties are not conventionally significant at n=12: FUSED p≈0.070, AXES p≈0.109, MAD p≈0.727. These are descriptive pilot results, not a powered benchmark claim.

## Per-task overall scores

| Task | r0 | FUSED | AXES | MAD |
|---|---:|---:|---:|---:|
| ab000001 | 8 | 5 | 2 | 8 |
| ab000002 | 5 | 9 | 9 | 3 |
| ab000003 | 7 | 8 | 8 | 7 |
| ab000004 | 9 | 9 | 9 | 8 |
| ab000005 | 6 | 8 | 8 | 6 |
| ab000006 | 6 | 8 | 9 | 8 |
| ab000007 | 5 | 5 | 5 | 3 |
| ab000008 | 8 | 8 | 9 | 6 |
| ab000009 | 8 | 8 | 7 | 8 |
| ab000010 | 6 | 9 | 7 | 8 |
| ab000011 | 6 | 8 | 7 | 3 |
| ab000012 | 7 | 9 | 9 | 9 |

## Interpretation

The central sanity check passes: a useful gold critique can produce materially higher blind visual scores from the same generator. FUSED is strongest, improving the mean by 1.08 and beating r0 on 7 tasks with one loss. AXES also improves the mean and wins most non-tied comparisons.

The result is not “any gold critique helps.” MAD is slightly worse than r0 and produces three severe incomplete outputs (ab000002, ab000007, ab000011). FUSED and AXES also catastrophically regress on ab000001 by damaging or obscuring the requested puzzle board. The evaluator detected these failures rather than rewarding the mere presence of a gold label.

This supports ArtifactsBench as a useful visible-output sanity check and FUSED/AXES as meaningful critique conditions in this pilot. It does not establish a fully independent benchmark: the same Codex authored the critiques and later judged anonymous outputs, and only 12 tasks, one generator, and one generation per condition were tested. The next credible confirmation is a separately initialized judge or human raters, multiple seeds, and a preregistered aggregation rule.

## Audit artifacts

- `manifest.json`: anonymous task/codes
- `scores_codex_blind.json`: scores fixed before unblinding
- `key.json`: hidden code-to-variant mapping
- `scores_unblinded.json`: joined result
- `packet/` and `sheets/`: exact judged images
