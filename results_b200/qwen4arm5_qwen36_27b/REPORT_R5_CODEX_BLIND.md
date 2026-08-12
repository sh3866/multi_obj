# Qwen4Arm5 — Codex direct blind R5 evaluation

## Result

| Arm | Layout | Spacing | Color/type | Style/finish | Overall | Catastrophic ≤3 | Qwen calls | Mean tokens/task |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SELF | 5.67 | 6.50 | 7.00 | 6.25 | **5.25** | **5/12** | 60 | 107,428 |
| FUSED | 6.83 | 7.00 | 8.08 | 7.50 | **6.50** | 1/12 | 120 | **91,784** |
| AXES | 7.08 | 7.25 | 8.00 | 7.25 | **6.83** | 1/12 | 368 | 155,450 |
| MAD | **7.33** | **7.42** | **8.08** | **7.42** | **7.00** | 2/12 | 607 | 273,159 |

R5 ordering is `MAD > AXES > FUSED > SELF`. External critique is associated with a large descriptive gain over SELF: FUSED +1.25, AXES +1.58, MAD +1.75.

## Per-task overall

| Task | SELF | FUSED | AXES | MAD | Winner |
|---|---:|---:|---:|---:|---|
| ab000001 | 9 | 3 | 4 | 7 | SELF |
| ab000002 | 2 | 4 | 8 | 3 | AXES |
| ab000003 | 3 | 8 | 8 | 7 | FUSED / AXES |
| ab000004 | 9 | 8 | 8 | 3 | SELF |
| ab000005 | 4 | 7 | 7 | 8 | MAD |
| ab000006 | 3 | 8 | 6 | 8 | FUSED / MAD |
| ab000007 | 2 | 5 | 2 | 7 | MAD |
| ab000008 | 7 | 8 | 8 | 9 | MAD |
| ab000009 | 2 | 8 | 8 | 9 | MAD |
| ab000010 | 9 | 7 | 7 | 7 | SELF |
| ab000011 | 7 | 7 | 7 | 8 | MAD |
| ab000012 | 6 | 5 | 9 | 8 | AXES |

## Statistical caution

- Task-blocked Friedman test: χ²=4.943, p=0.176.
- Exact paired sign-flip tests on mean differences: FUSED−SELF p=0.268; AXES−SELF p=0.150; MAD−SELF p=0.147; AXES−FUSED p=0.688; MAD−FUSED p=0.545; MAD−AXES p=0.921.
- At n=12, the observed ordering is descriptive and not conventionally significant. The high task-to-task variance is real: each arm has tasks it wins and tasks it catastrophically loses.

## What happened

SELF failed primarily through content preservation. Five R5 artifacts were catastrophic: absent skill tree, absent dialogue stage, clipped SkiFree title/instructions, empty creature field, and absent chessboard. It can also be excellent (ab000001, ab000004, ab000010 all score 9), so its problem is reliability rather than ceiling.

FUSED greatly reduces catastrophic failures at the lowest measured compute. Its two notable failures are oversized puzzle tokens and an off-canvas skill tree. It is the strongest quality/cost point in this run: 6.50 overall with only 120 total calls, and fewer tokens than SELF because the fused critique constrains subsequent generations.

AXES has the best skill-tree and Spirit-hub outcomes and the same low catastrophic rate as FUSED. Its gain over FUSED is only +0.33 with about 3.1× as many calls, and it still deletes the creature scene on ab000007.

MAD has the highest mean and wins or ties seven tasks against FUSED, but its +0.17 over AXES is negligible relative to variance while using 607 calls and 273K tokens/task. Debate helps on several content-heavy tasks (creature field, chess, puzzle objects), but does not guarantee preservation: it clips the skill tree and collapses the planet-defense UI.

## Interpretation

The strongest supported claim is **external screenshot-grounded critique improves R5 reliability relative to pure self-refinement**. The current data do not establish that debate is better than independent axes. MAD is descriptively first, but AXES is nearly tied at substantially lower cost, and FUSED is the cost-efficient baseline.

For the framework, the important signal is that decomposition does not merely inflate scores: all arms were judged from anonymous images, and structured methods still received severe penalties when required content disappeared. The evaluator discriminated visible completion failures rather than rewarding method complexity.

## Blind protocol and audit

- 48 R5 screenshots were copied under fresh runtime-random codes.
- Codex saw each task brief and its four anonymous screenshots, knowing the four evaluation axes but not the arm mapping.
- Four axes and a separate holistic overall were directly scored 0–10; overall is not an arithmetic average and heavily penalizes missing required content.
- A specific visible-evidence reason was authored for every image.
- All 48 scores were saved and validated before `key.json` was opened.
- `codex_blind/scores_blind.json`: locked pre-unblind scores.
- `codex_blind/scores_unblinded.json`: joined arm results.
- `codex_blind/manifest.json`, `packet/`, `sheets/`: exact anonymous evaluation material.
- `SELF|FUSED|AXES|MAD/problems/<task>/trace.json`: complete critic/debate histories and usage.

Limitations: the judge is variant-blind but knows the experimental methods; only R5 is directly scored here; one generator sample per arm/task; one Codex judge; no human inter-rater agreement yet.
