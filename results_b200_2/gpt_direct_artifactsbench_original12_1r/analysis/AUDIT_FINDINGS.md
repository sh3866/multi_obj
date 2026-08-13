# Audit findings before interpretation

## What is valid

- All 72 candidate packages exist and passed render/integrity checks.
- Each task uses one frozen shared r0 across all five refinement conditions.
- The blind manifest contains anonymous paths and the 72 score records map back cleanly.
- The judge inspected the permitted source and three staged images, and the recorded input hashes match.

## Critical limitation in the completed judge output

The current `independent_gpt_scores_blind.json` is structurally valid but is not sufficiently
candidate-specific for comparing refinement organizations. Within every task, the judge emitted
byte-identical overall reasons and checklist assessments for all five revised candidates. It also
assigned the same score to all five conditions. This happened even where their HTML and image
hashes differ. Therefore the condition-level equality cannot be treated as evidence that the five
methods are truly equivalent.

The score file is retained as an immutable audit artifact, not silently replaced. A valid
method-comparison conclusion requires a new blind judgment pass that explicitly produces
candidate-specific evidence without comparing or revealing conditions.

## Generator-side limitation

The five revised candidates are also highly similar to their shared r0 and to one another.
Character-level similarity to r0 is approximately 0.960–0.994. Many revisions are small,
formulaic additions rather than substantial task-level redesigns. Consequently this one-round
run has low treatment separation: even a stronger judge may find only small differences.

## Descriptive scores only

The current means are r0 59.25 and 58.50 for each of SELF, FUSED, AXES, CEN_MAD, and MAD.
Every revised method has the same paired delta, -0.75, because of the duplicated within-task
judgments. These numbers must not be reported as evidence for or against MAD/AXES organization.

Recommended next action: retain this run for pipeline auditing, then rejudge all 72 candidates
with a fresh independent context requiring unique image/code citations per candidate. If the
rejudged scores still collapse, rerun generation with stronger revision contracts to increase
treatment separation.
