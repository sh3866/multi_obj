"""Combined gallery for the axis-taxonomy ablation: per task, the FOUR
versions' artifacts side by side (V0 = deep15 MAD candidate r8 as the cap-8
counterfactual; visawi5 / lt3 / hedonic3 = axisabl finals), each with its
judge scores. One page: results/axisabl/REPORT.html.

  python make_axisabl_report.py
"""

from __future__ import annotations

import html
import json
import os
from collections import defaultdict

from make_report import thumb_b64  # same thumbnail pipeline as the arm report

AXES = ["functionality", "design", "originality", "craft"]
VERSIONS = [
    ("V0 main4", "results/deep15/judge/scores_qvl72.jsonl",
     lambda app: f"results/deep15/MAD/problems/{app}/candidates/r8.png",
     ("MAD", "r8")),
    ("visawi5", "results/axisabl/visawi5/judge/scores_qvl72.jsonl",
     lambda app: f"results/axisabl/visawi5/MAD/problems/{app}/final_t1.png",
     ("MAD", "final")),
    ("lt3", "results/axisabl/lt3/judge/scores_qvl72.jsonl",
     lambda app: f"results/axisabl/lt3/MAD/problems/{app}/final_t1.png",
     ("MAD", "final")),
    ("hedonic3", "results/axisabl/hedonic3/judge/scores_qvl72.jsonl",
     lambda app: f"results/axisabl/hedonic3/MAD/problems/{app}/final_t1.png",
     ("MAD", "final")),
]
THUMB_W = 420


def load_scores(path, arm, cand):
    out = defaultdict(dict)
    for l in open(path):
        r = json.loads(l)
        if r["arm"] == arm and r["cand_id"] == cand and r["score"] is not None:
            out[r["app"]][r["axis"]] = r["score"]
    return out


def main():
    scores = {name: load_scores(p, arm, cand)
              for name, p, _, (arm, cand) in VERSIONS}
    apps = sorted(scores["V0 main4"])

    # instructions from any set's trace
    instr = {}
    for app in apps:
        tp = f"results/axisabl/lt3/MAD/problems/{app}/trace.json"
        if os.path.exists(tp):
            instr[app] = json.load(open(tp)).get("instruction", "")

    css = """
    body{font-family:-apple-system,'Segoe UI',sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
    .wrap{max-width:1900px;margin:0 auto;padding:24px}
    h1{font-size:20px} h2{font-size:15px;margin:8px 0}
    table{border-collapse:collapse;margin:12px 0}
    td,th{border:1px solid #333;padding:4px 12px;font-size:13px}
    .task{margin:34px 0;border-top:1px solid #333;padding-top:14px}
    .instr{color:#9aa4b2;font-size:13px;max-width:1300px;white-space:pre-wrap}
    .row{display:flex;gap:14px;overflow-x:auto;padding:12px 0}
    .card{flex:0 0 auto;width:WPX px;background:#171a21;border:1px solid #2a2f3a;border-radius:8px;padding:8px}
    .card img{width:100%;border-radius:4px;display:block;background:#fff}
    .card .name{font-weight:700;font-size:14px;margin:6px 0 2px}
    .best .name{color:#7ee787}
    .sc{font-size:12px;color:#9aa4b2}
    .big{font-size:16px;color:#e6e6e6;font-weight:700}
    .missing{height:150px;display:flex;align-items:center;justify-content:center;color:#555;border:1px dashed #333;border-radius:4px}
    """.replace("WPX px", f"{THUMB_W}px")

    parts = [f"<style>{css}</style><div class='wrap'>",
             "<h1>Axis-taxonomy ablation — MAD cap 8, 15 tasks "
             "(V0 = deep15 r8 counterfactual; judge qvl72, fixed 4 criteria)</h1>",
             "<table><tr><th>set</th><th>mean overall</th>"
             + "".join(f"<th>{a}</th>" for a in AXES) + "</tr>"]
    for name in scores:
        f = scores[name]
        mo = sum(v["overall"] for v in f.values()) / len(f)
        parts.append(f"<tr><td>{name}</td><td>{mo:.2f}</td>" +
                     "".join(f"<td>{sum(v[a] for v in f.values())/len(f):.2f}</td>"
                             for a in AXES) + "</tr>")
    parts.append("</table>")

    for app in apps:
        parts.append(f"<div class='task'><h2>{html.escape(app)}</h2>"
                     f"<div class='instr'>{html.escape(instr.get(app, '')[:500])}</div>"
                     "<div class='row'>")
        cards = []
        for name, _, png_fn, _ in VERSIONS:
            s = scores[name].get(app, {})
            cards.append((-(s.get("overall") or -1), name, s, png_fn(app)))
        best = min(c[0] for c in cards)
        for negov, name, s, png in sorted(cards):
            img = thumb_b64(png, THUMB_W) if os.path.exists(png) else None
            body = (f"<img src='{img}' loading='lazy'>" if img
                    else "<div class='missing'>no screenshot</div>")
            det = " · ".join(f"{a[:4]} {s.get(a, '?')}" for a in AXES)
            cls = "card best" if negov == best else "card"
            parts.append(
                f"<div class='{cls}'>{body}<div class='name'>{html.escape(name)}</div>"
                f"<div class='sc'><span class='big'>overall "
                f"{(-negov) if negov <= 0 else '?':.1f}</span> — {det}</div></div>")
        parts.append("</div></div>")
    parts.append("</div>")

    out = "results/axisabl/REPORT.html"
    with open(out, "w") as f:
        f.write("\n".join(parts))
    print(f"wrote {out} ({os.path.getsize(out)//1024} KB, {len(apps)} tasks x 4 sets)")


if __name__ == "__main__":
    main()
