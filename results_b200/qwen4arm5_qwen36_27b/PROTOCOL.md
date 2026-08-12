# Qwen4Arm5 frozen protocol

- Tasks: the 12 fixed briefs in `sideproj_subjective/tasks.jsonl`.
- Shared start: exact original r0 HTML from `results/gold12_qwen36_27b`; all arms branch from the same artifact per task.
- Arms: SELF, FUSED_design4, AXES_design4, MAD_design4.
- Model: `Qwen/Qwen3.6-27B` for both generator and every critic/moderator/debater.
- Endpoint: one local vLLM (`:8000`) for all calls.
- Exactly five revisions; early-stop disabled.
- Generator temperature 0.7; critic temperature 0.2; viewport 1280×800; offline self-contained HTML.
- SELF: one Qwen VLM sees screenshot + current HTML and directly regenerates.
- FUSED: one holistic design4 Qwen VLM critic sees screenshot; its revision goes to Qwen generator.
- AXES: four independent design4 Qwen VLM critics see the same screenshot; Qwen moderator synthesizes one revision.
- MAD: the same four independent critics, then four screenshot-grounded cross-critiques, then Qwen moderator synthesis.
- Primary outcome: Codex direct blind scores of R5, randomized within task with hidden arm mapping.
- Secondary outcomes: direct blind scores across R1–R5, requirement-failure rate, regressions, best round, and token/call cost.
- Codex does not author or alter any critique or artifact in this experiment.
- Natural method compute is retained (not token-matched); quality and cost are reported together.
