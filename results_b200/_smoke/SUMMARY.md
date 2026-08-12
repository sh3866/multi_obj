# Run summary — results/_smoke

Judges: qvl72 — primary: **qvl72**

## Budget compliance (compute matching)

| arm | tasks ok | mean tokens | budget | mean candidates |
|---|---|---|---|---|
| AXES | 3/3 | 11733 | 12000 | 3.7 |
| BON | 3/3 | 2523 | 12000 | 4.0 |
| FUSED | 3/3 | 3605 | 12000 | 2.3 |
| MAD | 3/3 | 10231 | 12000 | 2.7 |
| SELF | 3/3 | 3268 | 12000 | 5.0 |
| ZS | 3/3 | 631 | 12000 | 1.0 |

## Held-out judge `qvl72` — axis `overall`

Bradley-Terry strengths (geo-mean 1):

- **MAD**: 1.405
- **BON**: 1.119
- **AXES**: 1.000
- **SELF**: 1.000
- **ZS**: 0.894
- **FUSED**: 0.712

| pair | winrate(first) | votes |
|---|---|---|
| AXES vs BON | 0.50 | 6 |
| AXES vs FUSED | 0.67 | 6 |
| AXES vs MAD | 0.50 | 6 |
| AXES vs SELF | 0.50 | 6 |
| AXES vs ZS | 0.33 | 6 |
| BON vs FUSED | 0.67 | 6 |
| BON vs MAD | 0.17 | 6 |
| BON vs SELF | 0.50 | 6 |
| BON vs ZS | 0.83 | 6 |
| FUSED vs MAD | 0.33 | 6 |
| FUSED vs SELF | 0.50 | 6 |
| FUSED vs ZS | 0.50 | 6 |
| MAD vs SELF | 0.50 | 6 |
| MAD vs ZS | 0.50 | 6 |
| SELF vs ZS | 0.50 | 6 |

## Pre-registered comparisons (paired sign test)

| comparison | tasks (a/b) | p | p (Holm) |
|---|---|---|---|
| SELF_vs_FUSED | 1/1 | 1.0000 | 1.0000 |
| FUSED_vs_AXES | 0/1 | 1.0000 | 1.0000 |
| AXES_vs_MAD | 0/0 | - | - |
| BON_vs_MAD | 0/2 | 0.5000 | 1.0000 |

## Discrimination gate

- PASS: arms are separable and functionality is off ceiling/floor.

## Checklist scores (judge `qvl72`, final artifacts)

| arm | mean score | tasks |
|---|---|---|
| BON | 0.433 | 3 |
| ZS | 0.400 | 3 |
| FUSED | 0.367 | 3 |
| MAD | 0.367 | 3 |
| AXES | 0.333 | 3 |
| SELF | 0.333 | 3 |

## In-loop critic score by round (leniency trajectory)

| arm | r0 | r1 | r2 | r3 |
|---|---|---|---|---|
| AXES | 2.5 | 2.75 | 2.625 |  |
| FUSED | 3.0 | 3.0 | 2.0 | 4.0 |
| MAD | 2.5 | 2.625 |  |  |

_Rising critic scores with flat held-out judge = leniency drift; compare AXES vs MAD slopes (H2 mechanism)._
