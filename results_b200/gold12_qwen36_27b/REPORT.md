# Gold-critic validation on 12 single-page briefs

## Question

Can a directly observed, high-quality critique cause Qwen3.6-27B to produce an artifact that a judge rates above the exact same shared r0? Can the ArtifactsBench-style evaluation detect that reliably?

## Frozen setup

- 12 manually rewritten single-screen design briefs.
- One local `Qwen/Qwen3.6-27B` vLLM (`:8000`) for r0, revision, and automated judging; no external API.
- One shared r0 per task; exactly one revision round.
- Gold critique authored by Codex after direct inspection of each 1280×800 r0 render; no score was shown or optimized during critique.
- Variants: holistic GOLD-FUSED, four-axis GOLD-AXES, conflict-resolved GOLD-MAD.
- Judge images copied under opaque hashes. Absolute scoring used one image; pairwise used a single left/right composite in both orders.

## Result 1 — absolute ArtifactsBench-style score

| variant | requirement | layout | color/type | identity/craft | overall | Δ overall vs r0 |
|---|---:|---:|---:|---:|---:|---:|
| r0 | 7.33 | 8.33 | 8.33 | 7.92 | **7.42** | +0.00 |
| gold_fused | 9.33 | 9.33 | 9.08 | 8.83 | **8.75** | +1.33 |
| gold_axes | 8.33 | 8.75 | 8.83 | 8.50 | **8.25** | +0.83 |
| gold_mad | 7.08 | 8.75 | 8.25 | 7.92 | **6.92** | -0.50 |

Absolute scoring says GOLD-FUSED and GOLD-AXES improve substantially, while GOLD-MAD regresses. Per-task overall signs:

- `gold_fused`: positive 6, negative 2, tied 4; mean Δ +1.33.
- `gold_axes`: positive 6, negative 1, tied 5; mean Δ +0.83.
- `gold_mad`: positive 2, negative 4, tied 6; mean Δ -0.50.

## Result 2 — blind forced-choice, both presentation orders

| variant vs r0 | gold votes / 24 | r0 votes / 24 | consistent gold wins | consistent r0 wins | order-split tasks |
|---|---:|---:|---:|---:|---:|
| gold_fused | 18 | 6 | 7 | 1 | 4 |
| gold_axes | 18 | 6 | 7 | 1 | 4 |
| gold_mad | 7 | 17 | 2 | 7 | 3 |

GOLD-FUSED and GOLD-AXES each produce seven order-consistent task wins versus one loss, with four unresolved order splits. Dropping split tasks gives a two-sided sign-test p≈0.070; the direction is meaningful but n=12 is not enough for p<0.05. Treating the two orders as independent votes would give an anti-conservative result and is not used.

GOLD-MAD is clearly worse in this run: two consistent wins, seven consistent losses, three splits.

## Judge reliability audit

- The judge selected the second-position image 47/72 times (65.3%; exact two-sided binomial p=0.0128). This is a significant position bias.
- 11/36 task×variant comparisons changed winner when order was reversed.
- Absolute scoring correctly caught major visible failures: the oversized Cub in AXES task 1 (2/10), absent skill tree in task 2 (4/10), missing wet mess in MAD task 5 (4/10), empty play field in MAD task 7 (3/10), and missing puzzle objects in MAD task 11 (0/10).
- But absolute scores strongly cluster at 9–10 for otherwise distinct outputs, so they detect gross failures better than subtle preference.
- The same model generated and judged. Blinding prevents label leakage but not same-model aesthetic bias. These numbers validate the pipeline only as a local sanity check, not as independent evidence.

## Direct execution audit (not an independent outcome)

I re-opened the rendered 4-way comparison after generation to determine whether Qwen actually followed each gold instruction and whether it introduced regressions:

| task | fused | axes | mad | visible note |
|---|---|---|---|---|
| ab000001 | regressed | severe regression | roughly neutral | AXES makes Cub/star enormous; FUSED simplifies connector content. |
| ab000002 | improved | improved | failed | FUSED/AXES restore a centered tree; MAD still leaves the centerpiece absent. |
| ab000003 | improved | improved | roughly neutral | FUSED/AXES improve the character stage; MAD becomes too dark. |
| ab000004 | roughly neutral | roughly neutral | roughly neutral | Already-strong r0; revisions mostly restyle the same console. |
| ab000005 | improved | improved | regressed | FUSED/AXES improve mop/wetness; MAD loses a convincing spill. |
| ab000006 | improved | improved | improved | All revisions reveal the skier and integrate the menu better. |
| ab000007 | slightly improved | slightly improved | regressed | Player/net remains weak; MAD makes the field almost empty. |
| ab000008 | improved | improved | regressed | FUSED/AXES fix CTA hierarchy; MAD flattens the strong perspective scene. |
| ab000009 | roughly neutral | roughly neutral | roughly neutral | Piece consistency improves somewhat; layouts remain similar. |
| ab000010 | improved | improved | improved | All variants satisfy multicolor better; AXES has the strongest sphere depth. |
| ab000011 | improved | improved | severe regression | FUSED/AXES clarify objects; MAD removes required objects/legend. |
| ab000012 | improved | improved | improved | All develop the central summoning seal and bespoke identity. |

## Conclusion

**Yes: a good visual critique can produce a real, judge-detectable improvement with Qwen3.6-27B.** The strongest evidence is not merely the absolute-score increase: GOLD-FUSED and GOLD-AXES each beat the exact same r0 on seven tasks in both presentation orders, and the visible fixes correspond to the critique (restored skill tree, visible skier, multicolor sphere, clearer puzzle objects, stronger summoning seal).

**No: improvement is not guaranteed, and 'gold MAD' is not automatically gold execution.** Qwen occasionally over-applies or drops requirements. The conflict-resolved MAD instructions produced several catastrophic regressions, so the bottleneck includes the revision operator, not only critic quality.

**ArtifactsBench-style evaluation is partially trustworthy.** Its rubric detects large requirement/layout failures well. Absolute 0–10 scoring has a severe ceiling, while this local Qwen pairwise judge has statistically significant second-position bias. A defensible main experiment needs both-order presentation, task-level aggregation, and a genuinely held-out judge or human subset.

## Audit trail

- `tasks/<task>/r0/`: exact initial prompt, raw Qwen response, HTML, screenshot and render metadata.
- `tasks/<task>/gold/README.md`: direct observation, four axis critiques, MAD trade-off, and all exact revision instructions.
- `tasks/<task>/variants/<variant>/`: exact revision prompt, raw response, HTML, screenshot and render metadata.
- `judge/blind_key.json`: anonymous-code mapping, isolated from judge inputs.
- `judge/absolute_audit.json`, `judge/pairwise_audit.json`: every judge prompt, raw response, parse and winner.
- `review/all_compare.jpg`: all r0/FUSED/AXES/MAD renders in task rows.
- `protocol/*.json`: models, parameters, token use and completion status.
