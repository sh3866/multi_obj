# Iterative Gold × 10 — four-task ceiling study

## Protocol

- Generator: `Qwen/Qwen3.6-27B`, one local vLLM endpoint, temperature 0.7.
- Tasks: ab000002, ab000007, ab000010, ab000012.
- R0 is the original shared artifact. Each R1–R10 revises the immediately previous HTML.
- After every render, Codex directly inspected the new screenshot and authored a fresh English Gold critique.
- Every critique, full prompt, raw response, HTML, screenshot and render probe is retained.
- Scores below are post-hoc trajectory scores by the same Codex, not an independent blind judge. They are suitable for diagnosing the path, not for an unbiased benchmark estimate.

## Round means

| Round | R0 | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Mean | 5.75 | 6.75 | 7.50 | 6.50 | 8.50 | 6.00 | 5.75 | 6.75 | 6.50 | 7.75 | 7.00 |

Peak mean is **R4 = 8.50**; final R10 mean is **7.00**, versus **R0 = 5.75**. Best-of-trajectory mean is **8.75**.

## Per-task scores

| Task | R0 | R1 | R2 | R3 | R4 | R5 | R6 | R7 | R8 | R9 | R10 | Best |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ab000002 | 5 | 3 | 7 | 3 | 9 | 3 | 3 | 5 | 3 | 7 | 7 | R4 (9) |
| ab000007 | 5 | 8 | 8 | 6 | 8 | 3 | 3 | 5 | 6 | 7 | 4 | R1 (8) |
| ab000010 | 6 | 7 | 6 | 8 | 8 | 9 | 8 | 8 | 8 | 8 | 8 | R5 (9) |
| ab000012 | 7 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | 9 | R1 (9) |

## Findings

1. **Gold has a real ceiling effect.** Every task exceeds its R0 at least once; best-of-trajectory rises from mean 5.75 to 8.75.
2. **More rounds are not monotonically better.** The mean peaks at R4, collapses at R5–R6, recovers at R9, then falls at R10.
3. **The main bottleneck is preservation, not diagnosis.** Qwen repeatedly deletes already-correct complex structures even when the critique explicitly says to preserve them. ab000002 loses its tree multiple times; ab000007 loses its whole scene at R5–R6.
4. **Simple/stable artifacts benefit most reliably.** ab000010 reaches multicolor compliance at R3 and stays strong; ab000012 improves at R1 and remains at 9 through R10.
5. **Complex DOM recovery is possible but brittle.** Explicit static HTML/CSS/SVG instructions recover the broken tasks, but later full-document regeneration can erase them again.

Across 40 revisions, 29/40 score above their own R0, but there are 7/40 catastrophic rounds (overall ≤3). Average over all revision rounds is 6.90, +1.15 over R0; selecting the final round gives only +1.25.

## Interpretation

Iterative Gold is meaningful as an **oracle-guided search**: it can find substantially better artifacts and repair visible failures. It is not a safe “apply ten times” optimization algorithm when each step asks the generator to emit a complete replacement HTML document. The evidence favors render → critique → constrained patch/edit → render, plus checkpointing and rollback to the best prior round, rather than unconditional full regeneration for ten rounds.

## Audit paths

- `tasks/<task>/r00..r10/critique.txt` (R1–R10)
- `tasks/<task>/r00..r10/prompt.txt`
- `tasks/<task>/r00..r10/raw_response.txt`
- `tasks/<task>/r00..r10/artifact.html`
- `tasks/<task>/r00..r10/screenshot.png`
- `tasks/<task>/r00..r10/meta.json`
- `<task>_trajectory.jpg`
- `trajectory_scores.json`
