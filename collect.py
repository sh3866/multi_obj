"""Aggregate a run: token cost, ABSOLUTE judge scores (primary, per-axis),
paired sign tests for the pre-registered comparisons, the discrimination gate,
checklist scores, dual-judge robustness, and the critic-leniency table.
Writes {run_dir}/SUMMARY.md + summary.json.

  python collect.py results/pilot [--judge qvl72] [--axis overall]

Evaluation mode (user decision 2026-07-15): absolute 0-10 scoring
(scores_<judge>.jsonl from run_judge.py) — no pairwise/BT. The paired sign
test compares the two arms' scores task by task (ties dropped).
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict

from src.infra.io_utils import atomic_write_json, atomic_write_text, read_json

# pre-registered pairwise comparisons (PLAN.md); Holm-Bonferroni applied over these
KEY_COMPARISONS = [
    ("SELF", "FUSED"),   # value of an external evaluator
    ("FUSED", "AXES"),   # H1: axis separation
    ("AXES", "MAD"),     # H2: debate
    # ("BON", "MAD") removed with the BON arm (user decision 2026-07-15)
]


def load_arm_stats(run_dir):
    stats = {}
    for d in sorted(os.listdir(run_dir)):
        p = os.path.join(run_dir, d, "global_stats.json")
        if os.path.exists(p):
            stats[d] = read_json(p)
    return stats


def _load_jsonl_by_prefix(run_dir, prefix):
    """{name: rows} from judge/<prefix>_*.jsonl."""
    jdir = os.path.join(run_dir, "judge")
    out = {}
    if not os.path.isdir(jdir):
        return out
    for fn in sorted(os.listdir(jdir)):
        if fn.startswith(prefix + "_") and fn.endswith(".jsonl"):
            name = fn[len(prefix) + 1:-len(".jsonl")]
            out[name] = [json.loads(l) for l in open(os.path.join(jdir, fn))
                         if l.strip()]
    return out


def load_scores(run_dir):
    return _load_jsonl_by_prefix(run_dir, "scores")


def load_checklists(run_dir):
    return _load_jsonl_by_prefix(run_dir, "checklist")


def score_map(rows, axis, view="probe_max"):
    """{(app, arm): score} for one selection view's final artifacts on one axis.
    Views: probe_max (shared layer-A selector) | consensus (method's own stop)."""
    return {(r["app"], r["arm"]): r["score"] for r in rows
            if r["axis"] == axis and r.get("view", "probe_max") == view
            and r.get("score") is not None}


def sign_test_scores(rows, arm_a, arm_b, axis, view="probe_max"):
    """Task-paired sign test on absolute scores: count tasks where a>b vs b>a
    (ties dropped, standard practice) -> exact two-sided binomial."""
    sm = score_map(rows, axis, view)
    apps = {app for (app, arm) in sm if arm == arm_a} & \
           {app for (app, arm) in sm if arm == arm_b}
    a_tasks = b_tasks = 0
    for app in apps:
        da = sm[(app, arm_a)] - sm[(app, arm_b)]
        if da > 0:
            a_tasks += 1
        elif da < 0:
            b_tasks += 1
    n = a_tasks + b_tasks
    if n == 0:
        return {"n_tasks": 0, "p": None, "a_tasks": 0, "b_tasks": 0}
    k = max(a_tasks, b_tasks)
    p = sum(math.comb(n, x) for x in range(k, n + 1)) / (2 ** n) * 2
    return {"n_tasks": n, "a_tasks": a_tasks, "b_tasks": b_tasks,
            "p": min(1.0, p)}


def mean_scores_by_arm(rows, view="probe_max"):
    """{arm: {axis: mean}} over one selection view's final artifacts."""
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r.get("view", "probe_max") == view and r.get("score") is not None:
            acc[r["arm"]][r["axis"]].append(r["score"])
    return {arm: {ax: sum(v) / len(v) for ax, v in per.items() if v}
            for arm, per in acc.items()}


def inter_judge_agreement(a_rows, b_rows, axis):
    """Across the two judges: fraction of same-direction task-level arm-pair
    orderings (both judges scored the same app for both arms, neither tied)."""
    sa, sb = score_map(a_rows, axis), score_map(b_rows, axis)  # probe_max view
    apps = defaultdict(set)
    for (app, arm) in set(sa) & set(sb):
        apps[app].add(arm)
    same = total = 0
    for app, arms in apps.items():
        arms = sorted(arms)
        for i in range(len(arms)):
            for j in range(i + 1, len(arms)):
                da = sa[(app, arms[i])] - sa[(app, arms[j])]
                db = sb[(app, arms[i])] - sb[(app, arms[j])]
                if da == 0 or db == 0:
                    continue
                total += 1
                same += (da > 0) == (db > 0)
    return (same / total, total) if total else (None, 0)


def leniency_table(run_dir, arms, excl=frozenset()):
    """Mean in-loop critic score by round (from traces). Rising scores with a
    flat/declining held-out judge -> leniency drift (H2 mechanism analysis).
    SUBJECTIVE AXES ONLY: functionality is anchored to probe evidence and
    barely drifts, so mixing it in would dilute the drift slope. (FUSED's
    single fused score cannot be decomposed — reported as-is.)"""
    out = {}
    for arm in arms:
        pdir = os.path.join(run_dir, arm, "problems")
        if not os.path.isdir(pdir):
            continue
        by_round = defaultdict(list)
        for app in os.listdir(pdir):
            if app in excl:
                continue
            tp = os.path.join(pdir, app, "trace.json")
            if not os.path.exists(tp):
                continue
            for h in read_json(tp).get("history", []):
                if "scores" in h:                      # AXES / MAD
                    by_round[h["round"]].extend(
                        v for k, v in h["scores"].items()
                        if k != "functionality")
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
    ap.add_argument("--axis", default="overall",
                    help="primary axis for the pre-registered tests")
    ap.add_argument("--judge", default=None,
                    help="primary judge name (default: first alphabetically)")
    ap.add_argument("--view", default="probe_max",
                    choices=["probe_max", "consensus"],
                    help="which final-selection view the pre-registered tests "
                         "use (both are judged; see View comparison section)")
    ap.add_argument("--exclude-tasks", default="",
                    help="comma list of app ids dropped from ALL tables "
                         "(listwise, keeps pairing fair). Use for tasks that "
                         "are unsatisfiable in the sandbox or produced a "
                         "blank final in any arm.")
    a = ap.parse_args()

    excl = {t.strip() for t in a.exclude_tasks.split(",") if t.strip()}

    stats = load_arm_stats(a.run_dir)
    for s in stats.values():
        keep = [r for r in s.get("per_task", []) if r.get("app") not in excl]
        drop_n = len(s.get("per_task", [])) - len(keep)
        if drop_n:
            s["per_task"] = keep
            s["n_tasks"] -= drop_n
            s["n_ok"] = min(s["n_ok"], s["n_tasks"])
            if keep:
                s["mean_tokens"] = sum(r["usage"]["total_tokens"]
                                       for r in keep) / len(keep)
                s["mean_candidates"] = sum(r["n_candidates"]
                                           for r in keep) / len(keep)
    arms = sorted(stats)
    judges = load_scores(a.run_dir)
    # SUMMARY tables/tests are over FINAL artifacts only — with run_judge
    # --all-candidates the file also holds per-round rows (curve analysis)
    judges = {j: [r for r in rows
                  if r.get("cand_id", "final") == "final"
                  and r.get("app") not in excl]
              for j, rows in judges.items()}
    primary = a.judge if a.judge else (sorted(judges)[0] if judges else None)
    rows = judges.get(primary, [])
    lines = [f"# Run summary — {a.run_dir}", ""]
    if judges:
        lines += [f"Judges: {', '.join(sorted(judges))} — primary: **{primary}** "
                  f"(absolute 0-10 scoring)", ""]

    # --- token cost (reported, not matched) -----------------------------------
    lines += ["## Token cost per arm (reported only — max-performance regime, "
              "no matching)", "",
              "| arm | tasks ok | mean tokens | safety cap | mean candidates |",
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

    # --- absolute judge scores (PRIMARY) --------------------------------------
    summary = {"arms": arms, "axis": a.axis, "mode": "absolute"}
    if rows:
        means = mean_scores_by_arm(rows, a.view)
        axes_present = sorted({r["axis"] for r in rows})
        lines += [f"## Held-out judge `{primary}` — absolute scores (0-10, "
                  "final artifacts = consensus-stop outputs)", "",
                  "| arm | " + " | ".join(axes_present) + " |",
                  "|---|" + "---|" * len(axes_present)]
        order = sorted(means, key=lambda m: -(means[m].get(a.axis, 0)))
        for arm in order:
            lines.append("| " + arm + " | " +
                         " | ".join(f"{means[arm].get(ax, float('nan')):.2f}"
                                    for ax in axes_present) + " |")
        lines.append("")
        summary["means"] = means
        other = "consensus" if a.view == "probe_max" else "probe_max"
        om = mean_scores_by_arm(rows, other)
        if om:
            lines += [f"## View comparison — mean `{a.axis}` "
                      "(probe_max = shared selector | consensus = method's own stop)",
                      "", "| arm | probe_max | consensus |", "|---|---|---|"]
            pm = mean_scores_by_arm(rows, "probe_max")
            cm = mean_scores_by_arm(rows, "consensus")
            for arm in sorted(set(pm) | set(cm),
                              key=lambda x: -(pm.get(x, {}).get(a.axis, 0))):
                p = pm.get(arm, {}).get(a.axis)
                c = cm.get(arm, {}).get(a.axis)
                lines.append(f"| {arm} | {p:.2f} |" if c is None else
                             f"| {arm} | {p:.2f} | {c:.2f} |")
            lines.append("")
            summary["view_comparison"] = {
                "probe_max": {k: v.get(a.axis) for k, v in pm.items()},
                "consensus": {k: v.get(a.axis) for k, v in cm.items()}}

        pvals, tests = {}, {}
        lines += [f"## Pre-registered comparisons (paired sign test on "
                  f"per-task `{a.axis}` scores)", "",
                  "| comparison | tasks (a/b) | p | p (Holm) |", "|---|---|---|---|"]
        for x, y in KEY_COMPARISONS:
            if x in arms and y in arms:
                t = sign_test_scores(rows, x, y, a.axis, a.view)
                tests[f"{x}_vs_{y}"] = t
                pvals[f"{x}_vs_{y}"] = t["p"]
        adj = holm_bonferroni(pvals)
        for name, t in tests.items():
            p = f"{t['p']:.4f}" if t["p"] is not None else "-"
            ph = f"{adj[name]:.4f}" if adj.get(name) is not None else "-"
            lines.append(f"| {name} | {t['a_tasks']}/{t['b_tasks']} | {p} | {ph} |")
        lines.append("")
        summary.update({"sign_tests": tests, "holm": adj})

        # --- discrimination gate ----------------------------------------------
        gate = []
        splits = [t["a_tasks"] / t["n_tasks"] for t in tests.values()
                  if t["n_tasks"] > 0]
        if splits and all(abs(s - 0.5) < 0.05 for s in splits):
            gate.append("FAIL: every pre-registered comparison splits 45-55% — "
                        "the judge cannot separate arms on absolute scores. "
                        "Raise task difficulty/scope or fall back to pairwise "
                        "judging (artifacts are preserved) before the main run.")
        n_ties = sum(1 for t in tests.values() if t["n_tasks"] == 0)
        if n_ties:
            gate.append(f"WARN: {n_ties} comparison(s) had zero decided tasks "
                        "(all score ties) — absolute scale may be too coarse; "
                        "consider pairwise fallback.")
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
        lines += ["_No judge scores yet — run run_judge.py first._", ""]

    # --- checklist scores (absolute, diagnostics + curves) --------------------
    checklists = load_checklists(a.run_dir)
    if excl:
        checklists = {j: [r for r in rows if r.get("app") not in excl]
                      for j, rows in checklists.items()}
    for jn, cl_rows in sorted(checklists.items()):
        finals = [r for r in cl_rows
                  if r["cand_id"] == "final" and r["score"] is not None]
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
        lines += ["## Dual-judge robustness", ""]
        for jn, jr in sorted(judges.items()):
            m = mean_scores_by_arm(jr)
            rank = " > ".join(k for k, _ in
                              sorted(m.items(),
                                     key=lambda x: -x[1].get(a.axis, 0)))
            lines.append(f"- **{jn}** mean-{a.axis} ranking: {rank}")
        names = sorted(judges)
        agree_rows = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                agr, n = inter_judge_agreement(judges[names[i]],
                                               judges[names[j]], a.axis)
                if agr is not None:
                    agree_rows.append(f"- {names[i]} vs {names[j]}: "
                                      f"{agr:.1%} same-direction on {n} "
                                      "task-level arm pairs")
        lines += agree_rows + [""]
        summary["inter_judge"] = agree_rows

    # --- critic leniency (mechanism analysis) --------------------------------
    lt = leniency_table(a.run_dir, arms, excl)
    if lt:
        rounds = sorted({r for v in lt.values() for r in v})
        lines += ["## In-loop critic score by round (leniency trajectory, "
                  "subjective axes only)", "",
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
