# Iterative Gold × 10 — independent fresh-context GPT-5.6 blind re-evaluation

## Protocol

All 44 screenshots were copied under fresh random codes, with both task method and R0–R10 chronology hidden. A new GPT-5.6 agent with no conversation history could read only the anonymous manifest, packet and sheets. It received the same detailed four personas and completeness-first rubric used in the main experiment. Scores were locked and validated before round mapping.

## Independent trajectory

| Round | R0 | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Mean | 5.50 | 5.78 | 7.35 | 6.58 | 7.90 | 5.45 | 5.43 | 6.60 | 7.13 | **7.95** | 7.30 |

Best shared checkpoint is R9=7.95; final R10=7.30; best-per-task mean=8.08. The mean across all revision rounds is 6.75, +1.25 over R0. Six of 40 revisions are catastrophic (overall ≤3).

## Per-task trajectory

| Task | R0 | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | Best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ab000002 | 3.0 | 2.5 | 7.3 | 2.5 | 8.0 | 2.5 | 2.5 | 5.0 | 4.9 | 8.0 | 8.1 | R10 |
| ab000007 | 4.5 | 5.6 | 7.6 | 7.9 | 7.8 | 3.0 | 3.0 | 5.6 | 7.6 | 7.6 | 5.0 | R3 |
| ab000010 | 7.0 | 7.4 | 7.4 | 8.4 | 8.4 | 8.7 | 8.6 | 8.2 | 8.4 | 8.6 | 8.5 | R5 |
| ab000012 | 7.5 | 7.6 | 7.1 | 7.5 | 7.4 | 7.6 | 7.6 | 7.6 | 7.6 | 7.6 | 7.6 | R1 |

## Agreement and interpretation

The earlier same-Codex trajectory scores and independent scores agree strongly (Pearson r=0.861, Spearman ρ=0.649, MAE=0.91). Both detect the same central pattern: large attainable improvement, non-monotonic collapse at R5–R6, recovery later, and stable high quality for the simpler sphere/spirit tasks.

This independently supports iterative Gold as an oracle-guided search or checkpoint-selection process, not as a monotonic ten-step optimizer. The practical algorithm should preserve the best checkpoint and roll back regressions. It does not support blindly shipping the final round, and it does not isolate Gold's causal effect from repeated generation without a control arm.

## Audit files

- `independent_blind/independent_gpt56_scores_blind.json`: locked anonymous scores.
- `independent_blind/independent_gpt56_scores_unblinded.json`: round mapping joined after lock.
- `independent_blind/manifest.json`, `packet/`, `sheets/`: exact anonymous material.
