# RESULTS.md — experiment inventory and findings

Running log of every experiment that produced *judged* numbers, what it controlled,
and what it actually showed. Raw artifacts live under `results/` (git-ignored, 8+ GB).

**Reading rule:** results are reported as run, including the ones that contradict
each other. Where two runs disagree, the confounds are named explicitly.

---

## 0. Summary of what is and is not established

| Claim | Status |
|---|---|
| An evaluator loop beats a single pass | **Supported** (r0 4.58 → arms 5.3–6.0, cap-10) |
| Axis-decomposed critics beat a fused evaluator | **Weak** — holds in the one run with shared r0 (cap-10), contradicted by three earlier runs without it |
| Debate (MAD) beats independent axis critics | **Not established** — MAD ≈ AXES at the final artifact |
| The gains transfer to *pure* subjective design | **Refuted** — all arms ≈ untouched draft (sideproj) |
| Critique quality is the bottleneck | **Refuted** — a judge-aligned oracle critic plateaus after one round (oracle) |

---

## 1. Arm comparison runs (MAD vs AXES vs FUSED vs SELF vs ZS)

Four runs compare the same arm ladder. **They disagree**, and the main difference
is whether all arms started from a *shared* r0.

| run | n | judge | shared r0 | rounds | result (best → worst) |
|---|---|---|---|---|---|
| `pilotA` | 10 | Qwen2.5-VL-72B | ✗ | — | ZS 5.40 · FUSED 5.36 · SELF 5.15 · AXES 5.02 · **MAD 4.95** |
| `pilotW` | 10 | Qwen2.5-VL-72B | ✗ | — | **MAD 5.38** · ZS 5.14 · SELF 5.00 · FUSED 4.83 · AXES 4.71 |
| `deep15` | 15 | Qwen2.5-VL-72B | ✗ | 15 | FUSED 6.16 · ZS 5.91 · AXES 5.79 · SELF 5.75 · **MAD 5.33** |
| `strongenall` (cap-10) | 12 | blind, held-out | **✓** | 10 | **MAD 5.97 · AXES 5.92** · FUSED 5.35 · SELF 5.34 · r0 4.58 |

### Interpretation

MAD finishes first once, last twice, tied-first once. In `pilotA` and `deep15`,
**ZS — no refinement at all — beats MAD.**

The most likely explanation is the **initial-draft lottery**: without a shared r0,
each arm gets a different starting draft, and that draw moves arm ranking more than
the arm itself does. `PLAN.md` records an observed r0 gap of −0.95 between MAD and
AXES from identical code, which is why shared r0 was introduced.

**Caveat (unresolved confound):** the judge changed at the same time
(Qwen2.5-VL-72B → blind held-out judging). Draft lottery and judge change are
therefore entangled; the current data cannot separate them.

**Status:** the "decomposition helps" claim rests on a **single** controlled run
(n=12). `strongenall2` — the same design re-run after the parser fix (below) — is
generated but **not yet judged**, and is the cheapest way to test reproducibility.

---

## 2. Critic-quality experiment (`strongen`)

Same structure, same shared r0, **one round**; only the critique *text* is swapped
(in-house MoE self-critique → hand-written Opus "gold" critique).

| structure | weak critic | gold critic | Δ |
|---|---|---|---|
| fused | 4.38 | 4.75 | +0.38 |
| **axes** | 4.25 | **5.27** | **+1.02** |
| mad | 4.23 | 4.44 | +0.21 |

Critic quality matters, and it pays off most where the structure can **route it per
axis**. Note the gold critiques were free-form prose while the in-loop critics emit
constrained JSON — part of the gap is format, not just model.

---

## 3. Design-only side experiment (`sideproj`)

All 12 briefs rewritten as **single-screen, design-focused** tasks. Critics emit
**no scores** (pure critique). Arms × axis granularity 2 / 4 / 10, 10 rounds fixed.

| arm | score |
|---|---|
| FUSED-10 / FUSED-2 | 6.42 / 6.41 |
| MAD-10 | 6.25 |
| MAD-2 | 6.00 |
| **r0 (untouched draft)** | **5.96** |
| AXES (all), SELF, MAD-4 | 5.79 – 5.96 |

**Null result.** Every arm sits within ±0.5 of the untouched draft, and r0 ranks
mid-pack. Granularity is not monotone. 18% of finals score < 4.5 — **render
breakage, not taste, dominates the variance.**

---

## 4. Oracle ceiling experiment (`oracle`)

Question: if the critic is *perfectly aligned with the judge*, how high can the loop
go? Generator = Haiku 4.5. Critic = Opus, given the judge's own 4 axes, the same
0–10 anchors, and asked to describe "what a 10/10 looks like for this brief"
(no scores). 6 tasks × 3 rounds, **96 blind per-axis judgments**.

Bias control: nothing is scored during the loop; afterwards r0–r3 are anonymised
and shuffled, and each image is scored by an **independent fresh sub-agent** that
sees one image and one axis only. The critic and the judge never share memory.

### Trajectory

| | r0 | r1 | r2 | r3 |
|---|---|---|---|---|
| mean | 5.00 | **5.77** | 5.21 | 5.10 |

| axis | r0 | r1 | r2 | r3 | Δ |
|---|---|---|---|---|---|
| layout | 5.08 | 6.00 | 5.33 | 5.17 | +0.08 |
| **spacing** | 5.82 | 5.58 | 4.65 | **4.50** | **−1.32** |
| color_type | 4.92 | 6.05 | 5.78 | 5.88 | +0.97 |
| style_orig | 4.17 | 5.47 | 5.08 | 4.87 | +0.70 |

Round 1 improves 5/6 tasks (**+0.78**). Rounds 2–3 do not (r1→r2: 2/6, −0.56).
4/6 tasks peak at r1. **Net gain +0.11.** Ceiling ≈ 7; never near 9–10.

### Why it collapses — it is not "too much content"

HTML grew 1.5–2.5× in *every* task, with opposite outcomes
(`ab000005` grew 2.4× and gained +2.50; `ab000006` grew 2.5× and lost −2.00).
Size is not predictive. Task *type* is:

| layout style | tasks | outcome |
|---|---|---|
| flow layout (dashboards, HUD panels) | ab2, ab3, ab4 | all improved and held (+0.58 … +0.95) |
| single SVG scene | ab5 | +2.50, kept climbing |
| **absolutely-positioned graphics** (game board, sprites) | ab1, ab6 | **both collapsed (−2.00)** |

Judge evidence for the failures: *"the skier sprite sits directly on top of the
SKIFREE wordmark, burying the K and half the I"* (ab6 r3);
*"everything below the header fails, board clipped"* (ab1 r3).

Elements placed by absolute coordinates **collide and clip** as the critique asks
for more; flow/grid layouts re-flow gracefully instead.

Also: starting quality correlates negatively with gain (r = −0.63) — the worst
draft (2.75) improved the most (+2.50).

**Caveat:** n = 6, single run; the type pattern rests on 3 vs 2 tasks. Suggestive,
not established. And since critic and judge share a rubric by construction, part of
any gain is Goodhart — memory bias was blocked, criterion alignment was intentional.

---

## 5. Infrastructure finding: the silent parser bug

`generate_vlm()` never disabled the VLM's thinking preamble while `max_tokens` was
1024, so axis critiques were truncated before their JSON closed: **86% of axis
critiques were silently dropped** as "(no parse)" and the arms ran on almost no
signal.

Fix: keep thinking on, raise `max_tokens` to 4096, harden `extract_json`
(strip `<think>`, multiple candidates, lenient field recovery), retry with thinking
off, salvage prose when JSON never appears. **After the fix: 960/960 parsed (100%).**

Separately, ~13% of parsed axis critiques contain a literal `"..."` — the critic
model *chose* to skip that axis. This is a model-quality issue, not a parse failure,
and is one reason per-axis independent calls were adopted in the side experiment.

---

## 6. Open items

1. **Judge `strongenall2`** (generated, unjudged) — same design as cap-10 with the
   parser fixed. Highest-value next step: it is the only direct reproducibility
   check on the one result that supports the main claim.
2. Disentangle **shared-r0** from **judge change** — re-judge the pilots blind, or
   re-run one pilot with shared r0.
3. Test whether a **regression-aware critic** ("preserve what already works; do not
   introduce collisions or clipping") removes the post-r1 collapse. If it does, the
   diagnosis moves from "generator can't execute" to "critic can't see regressions".
4. Move from absolute scores (which cluster at 5.8–6.4) to **pairwise** comparison
   for subjective design.
