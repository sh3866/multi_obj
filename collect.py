"""Aggregate a run: budget compliance, judge winrates + Bradley-Terry, paired
sign tests for the pre-registered comparisons, the discrimination gate, and the
critic-leniency table. Writes {run_dir}/SUMMARY.md + summary.json.

  python collect.py results/pilot [--axis overall]
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

from src.eval_b.bt import winrate_matrix, paired_sign_test, bt_from_results
from src.infra.io_utils import atomic_write_json, atomic_write_text, read_json

# pre-registered pairwise comparisons (PLAN.md); Holm-Bonferroni applied over these
KEY_COMPARISONS = [
    ("SELF", "FUSED"),   # value of an external evaluator
    ("FUSED", "AXES"),   # H1: axis separation
    ("AXES", "MAD"),     # H2: debate
    ("BON", "MAD"),      # does the whole loop beat compute-matched sampling
]


def load_arm_stats(run_dir):
    stats = {}
    for d in sorted(os.listdir(run_dir)):
        p = os.path.join(run_dir, d, "global_stats.json")
        if os.path.exists(p):
            stats[d] = read_json(p)
    return stats


def load_judges(run_dir):
    """Returns {judge_name: rows} from judge/results_*.jsonl (+ legacy results.jsonl)."""
    jdir = os.path.join(run_dir, "judge")
    out = {}
    if not os.path.isdir(jdir):
        return out
    for fn in sorted(os.listdir(jdir)):
        if not (fn.startswith("results") and fn.endswith(".jsonl")):
            continue
        name = fn[len("results_"):-len(".jsonl")] if fn.startswith("results_") \
            else "default"
        out[name] = [json.loads(l) for l in open(os.path.join(jdir, fn)) if l.strip()]
    return out


def inter_judge_agreement(a_rows, b_rows):
    """% of identical votes on the shared (app, pair, axis, order) keys."""
    key = lambda r: (r["app"], r["arm_a"], r["arm_b"], r["axis"], r["order"])
    a_map = {key(r): r.get("winner_arm") for r in a_rows if r.get("winner_arm")}
    same = total = 0
    for r in b_rows:
        k = key(r)
        if r.get("winner_arm") and k in a_map:
            total += 1
            same += (a_map[k] == r["winner_arm"])
    return (same / total, total) if total else (None, 0)


def load_checklists(run_dir):
    """{judge_name: rows} from judge/checklist_*.jsonl."""
    jdir = os.path.join(run_dir, "judge")
    out = {}
    if not os.path.isdir(jdir):
        return out
    for fn in sorted(os.listdir(jdir)):
        if fn.startswith("checklist_") and fn.endswith(".jsonl"):
            name = fn[len("checklist_"):-len(".jsonl")]
            out[name] = [json.loads(l) for l in open(os.path.join(jdir, fn))
                         if l.strip()]
    return out


def leniency_table(run_dir, arms):
    """Mean in-loop critic score by round (from traces). Rising scores with a
    flat/declining held-out judge -> leniency drift (H2 mechanism analysis)."""
    out = {}
    for arm in arms:
        pdir = os.path.join(run_dir, arm, "problems")
        if not os.path.isdir(pdir):
            continue
        by_round = defaultdict(list)
        for app in os.listdir(pdir):
            tp = os.path.join(pdir, app, "trace.json")
            if not os.path.exists(tp):
                continue
            for h in read_json(tp).get("history", []):
                if "scores" in h:                      # AXES / MAD
                    by_round[h["round"]].extend(h["scores"].values())
                elif "fused_score" in h:               # FUSED
                    by_round[h["round"]].append(h["fused_score"])
        if by_round:
            out[arm] = {r: round(sum(v) / len(v), 3)
                        for r, v in sorted(by_round.items())}
    return out


def holm_bonferroni(pvals):
    """pvals: dict name->p. Returns dict name->adjusted p."""
    items = sorted((p, k) for k, p in pvals.items() if p is not None)
    adj, prev = {}, 0.0
    m = len(items)
    for i, (p, k) in enumerate(items):
        v = min(1.0, max(prev, (m - i) * p))
        adj[k] = v
        prev = v
    for k, p in pvals.items():
        if p is None:
            adj[k] = None
    return adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--axis", default="overall")
    ap.add_argument("--judge", default=None,
                    help="primary judge name (default: first alphabetically)")
    a = ap.parse_args()

    stats = load_arm_stats(a.run_dir)
    arms = sorted(stats)
    judges = load_judges(a.run_dir)
    primary = a.judge if a.judge else (sorted(judges)[0] if judges else None)
    results = judges.get(primary, [])
    lines = [f"# Run summary — {a.run_dir}", ""]
    if judges:
        lines += [f"Judges: {', '.join(sorted(judges))} — primary: **{primary}**", ""]

    # --- budget compliance --------------------------------------------------
    lines += ["## Budget compliance (compute matching)", "",
              "| arm | tasks ok | mean tokens | budget | mean candidates |",
              "|---|---|---|---|---|"]
    for arm in arms:
        s = stats[arm]
        lines.append(f"| {arm} | {s['n_ok']}/{s['n_tasks']} | "
                     f"{s['mean_tokens']:.0f} | {s['budget_tokens']} | "
                     f"{s['mean_candidates']:.1f} |")
    lines.append("")

    # --- functionality probe (layer-A descriptive) ---------------------------
    func_means = {}
    for arm in arms:
        vals = [r.get("final_func") for r in stats[arm]["per_task"]
                if r.get("final_func") is not None]
        if vals:
            func_means[arm] = sum(vals) / len(vals)
    if func_means:
        lines += ["## Final func_objective (probe, descriptive only)", "",
                  "| arm | mean |", "|---|---|"]
        for arm, m in sorted(func_means.items(), key=lambda x: -x[1]):
            lines.append(f"| {arm} | {m:.3f} |")
        lines.append("")

    # --- judge winrates / BT --------------------------------------------------
    summary = {"arms": arms, "axis": a.axis}
    if results:
        wm = winrate_matrix(results, arms, a.axis)
        bt = bt_from_results(results, a.axis)
        lines += [f"## Held-out judge `{primary}` — axis `{a.axis}`", "",
                  "Bradley-Terry strengths (geo-mean 1):", ""]
        for arm, s in sorted(bt.items(), key=lambda x: -x[1]):
            lines.append(f"- **{arm}**: {s:.3f}")
        lines += ["", "| pair | winrate(first) | votes |", "|---|---|---|"]
        for (x, y), d in sorted(wm.items()):
            wr = f"{d['winrate_a']:.2f}" if d["winrate_a"] is not None else "-"
            lines.append(f"| {x} vs {y} | {wr} | {d['total']} |")
        lines.append("")

        pvals = {}
        lines += ["## Pre-registered comparisons (paired sign test)", "",
                  "| comparison | tasks (a/b) | p | p (Holm) |", "|---|---|---|---|"]
        tests = {}
        for x, y in KEY_COMPARISONS:
            if x in arms and y in arms:
                t = paired_sign_test(results, x, y, a.axis)
                tests[f"{x}_vs_{y}"] = t
                pvals[f"{x}_vs_{y}"] = t["p"]
        adj = holm_bonferroni(pvals)
        for name, t in tests.items():
            p = f"{t['p']:.4f}" if t["p"] is not None else "-"
            ph = f"{adj[name]:.4f}" if adj.get(name) is not None else "-"
            lines.append(f"| {name} | {t['a_tasks']}/{t['b_tasks']} | {p} | {ph} |")
        lines.append("")
        summary.update({"bt": bt,
                        "winrates": {f"{x}|{y}": d for (x, y), d in wm.items()},
                        "sign_tests": tests, "holm": adj})

        # --- discrimination gate ---------------------------------------------
        gate = []
        rates = [d["winrate_a"] for d in wm.values() if d["winrate_a"] is not None]
        if rates and all(abs(r - 0.5) < 0.05 for r in rates):
            gate.append("FAIL: all pairwise winrates within 45-55% — judge cannot "
                        "separate arms. Raise task difficulty / artifact scope "
                        "before the main run.")
        if func_means:
            mean_all = sum(func_means.values()) / len(func_means)
            if mean_all > 0.95:
                gate.append("WARN: func_objective near ceiling (>0.95) — "
                            "functionality axis saturated; harder tasks needed.")
            if mean_all < 0.05:
                gate.append("WARN: func_objective near floor — generation broken.")
        if not gate:
            gate.append("PASS: arms are separable and functionality is off "
                        "ceiling/floor.")
        lines += ["## Discrimination gate", ""] + [f"- {g}" for g in gate] + [""]
        summary["gate"] = gate
    else:
        lines += ["_No judge results yet — run run_judge.py first._", ""]

    # --- checklist scores (absolute, diagnostics + curves) --------------------
    checklists = load_checklists(a.run_dir)
    for jn, rows in sorted(checklists.items()):
        finals = [r for r in rows if r["cand_id"] == "final" and r["score"] is not None]
        if not finals:
            continue
        by_arm = defaultdict(list)
        for r in finals:
            by_arm[r["arm"]].append(r["score"])
        lines += [f"## Checklist scores (judge `{jn}`, final artifacts)", "",
                  "| arm | mean score | tasks |", "|---|---|---|"]
        for arm, v in sorted(by_arm.items(), key=lambda x: -sum(x[1]) / len(x[1])):
            lines.append(f"| {arm} | {sum(v)/len(v):.3f} | {len(v)} |")
        lines.append("")
        summary.setdefault("checklist", {})[jn] = {
            arm: sum(v) / len(v) for arm, v in by_arm.items()}

    # --- dual-judge robustness ------------------------------------------------
    if len(judges) > 1:
        from src.eval_b.bt import bt_from_results as _bt
        lines += ["## Dual-judge robustness", ""]
        for jn, rows in sorted(judges.items()):
            bt_j = _bt(rows, a.axis)
            rank = " > ".join(k for k, _ in sorted(bt_j.items(), key=lambda x: -x[1]))
            lines.append(f"- **{jn}** BT ranking: {rank}")
        names = sorted(judges)
        agree_rows = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                agr, n = inter_judge_agreement(judges[names[i]], judges[names[j]])
                if agr is not None:
                    agree_rows.append(f"- {names[i]} vs {names[j]}: "
                                      f"{agr:.1%} agreement on {n} shared votes")
        lines += agree_rows + [""]
        summary["inter_judge"] = agree_rows

    # --- critic leniency (mechanism analysis) --------------------------------
    lt = leniency_table(a.run_dir, arms)
    if lt:
        rounds = sorted({r for v in lt.values() for r in v})
        lines += ["## In-loop critic score by round (leniency trajectory)", "",
                  "| arm | " + " | ".join(f"r{r}" for r in rounds) + " |",
                  "|---|" + "---|" * len(rounds)]
        for arm, v in lt.items():
            lines.append(f"| {arm} | " +
                         " | ".join(str(v.get(r, "")) for r in rounds) + " |")
        lines += ["", "_Rising critic scores with flat held-out judge = leniency "
                  "drift; compare AXES vs MAD slopes (H2 mechanism)._", ""]
        summary["leniency"] = lt

    atomic_write_text(os.path.join(a.run_dir, "SUMMARY.md"), "\n".join(lines))
    atomic_write_json(os.path.join(a.run_dir, "summary.json"), summary)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
