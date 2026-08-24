# Qwen3.8 30-task / 3-repeat / 5-round run

Status: **generation complete; strict structural audit passed**

- Model: `Qwen/Qwen3.8-27B`
- Repeats: 3 independent shared-r0 repeats
- Tasks: 30
- Arms: `SELF`, `FUSED`, `AXES`, `CEN_MAD`, `MAD`
- Rounds: r0 through r5
- Generator context/output: 65,536 / 32,768 tokens
- Design critic output: 16,384 tokens; concise failure-only retries: 4,096 tokens
- Completed trajectories: 450 / 450
- Complete HTML candidates: 2,700 / 2,700
- Rendered PNG candidates: 2,700 / 2,700 at 1280x800

## Final audit

`audit/full_audit_final.json` passed with zero structural issues. It verifies:

- every expected repeat/arm/task trajectory exists exactly once;
- all r0-r5 HTML and PNG files exist;
- every HTML has closing body/html tags;
- every PNG is valid and exactly 1280x800;
- every candidate reports `rendered=true`;
- each final HTML/PNG is byte-identical to its r5 candidate;
- r0 is shared across arms within a repeat and distinct across repeats;
- primary design critics used 16K, failure-only retries used 4K, and generators used at most 32K;
- two length-terminated generation attempts were rejected and immediately recovered by successful `attempt2` calls.

Final audit SHA-256:

`99e5d2497f14c8dec44be2ba9f20881504964c3ae285899e13a33155e9b05a91`

## Preserved quality diagnostics

The audit records 650 non-structural warnings: 605 candidate page-error observations, 43 console-error observations, and 2 rejected/truncated attempts that were successfully retried. Page/console errors are defects in the model-produced JavaScript while the pages still render; they are intentionally preserved as experimental outcomes rather than repaired after generation, which would bias the comparison.

## Recovery note

Eight missing trajectories from the regular run were regenerated and installed. A false contract rejection was fixed: concrete recommendations mentioning HTML tags such as `<section>` had previously been mistaken for template placeholders. Failure-only critic retries were also extended so a malformed critic response does not discard an otherwise valid multi-round trajectory. Normal successful calls and the experimental personas/arms were unchanged.
