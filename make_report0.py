"""REPORT0 — preliminary s0-only gallery across all 7 configs (single seed,
finals only). sharedr0's 4 arms (main4 axes) + axisabl2's 3 literature panels
(MAD). All started from the SAME shared r0, so directly comparable.

  python make_report0.py --judge s0prelim
"""

from __future__ import annotations

import argparse
import html
import json
import os
from collections import defaultdict

from make_report import thumb_b64

AXES = ["functionality", "design", "originality", "craft"]
# (label, run_dir, arm-subdir, final png template)
CONFIGS = [
    ("SELF (main4)",  "results/sharedr0/s0", "SELF"),
    ("FUSED (main4)", "results/sharedr0/s0", "FUSED"),
    ("AXES (main4)",  "results/sharedr0/s0", "AXES"),
    ("MAD (main4)",   "results/sharedr0/s0", "MAD"),
    ("MAD / visawi5",   "results/axisabl2/s0/visawi5", "MAD"),
    ("MAD / lt3",       "results/axisabl2/s0/lt3", "MAD"),
    ("MAD / hedonic3",  "results/axisabl2/s0/hedonic3", "MAD"),
]
THUMB_W = 360


def load(run_dir, arm, judge, cand="final"):
    """{app: {axis: score}} for the chosen candidate round + {app: r0 overall}."""
    p = os.path.join(run_dir, "judge", f"scores_{judge}.jsonl")
    fin, r0 = defaultdict(dict), {}
    if not os.path.exists(p):
        return fin, r0
    for l in open(p):
        if not l.strip():
            continue
        r = json.loads(l)
        if r["arm"] != arm or r.get("score") is None:
            continue
        if r["cand_id"] == cand:
            fin[r["app"]][r["axis"]] = r["score"]
        elif r["cand_id"] == "r0" and r["axis"] == "overall":
            r0[r["app"]] = r["score"]
    return fin, r0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default="s0prelim")
    ap.add_argument("--cand", default="final",
                    help="candidate round to show (final | r3 | ...)")
    ap.add_argument("--out", default="results/REPORT0.html")
    a = ap.parse_args()

    png_name = "final_t1.png" if a.cand == "final" else f"candidates/{a.cand}.png"
    data = {}      # label -> (fin, r0, png_dir)
    for label, run_dir, arm in CONFIGS:
        fin, r0 = load(run_dir, arm, a.judge, a.cand)
        data[label] = (fin, r0, os.path.join(run_dir, arm, "problems"))
    apps = sorted({app for (fin, _, _) in data.values() for app in fin})

    # header table: mean overall / delta-r0 / tokens
    def mean_tokens(run_dir, arm):
        p = os.path.join(run_dir, arm, "global_stats.json")
        return json.load(open(p)).get("mean_tokens") if os.path.exists(p) else None

    rows = []
    for label, run_dir, arm in CONFIGS:
        fin, r0, _ = data[label]
        ov = [fin[x]["overall"] for x in fin if "overall" in fin[x]]
        dl = [fin[x]["overall"] - r0[x] for x in fin if "overall" in fin[x] and x in r0]
        t = mean_tokens(run_dir, arm)
        rows.append((label, sum(ov)/len(ov) if ov else 0,
                     sum(dl)/len(dl) if dl else None, t, len(ov)))
    rows.sort(key=lambda r: -r[1])

    css = """
    body{font-family:-apple-system,'Segoe UI',sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
    .wrap{max-width:2200px;margin:0 auto;padding:24px}
    h1{font-size:20px} h2{font-size:15px;margin:8px 0}
    table{border-collapse:collapse;margin:12px 0}
    td,th{border:1px solid #333;padding:4px 12px;font-size:13px}
    .task{margin:30px 0;border-top:1px solid #333;padding-top:12px}
    .instr{color:#9aa4b2;font-size:12px;max-width:1400px;white-space:pre-wrap}
    .row{display:flex;gap:12px;overflow-x:auto;padding:10px 0}
    .card{flex:0 0 auto;width:WPXpx;background:#171a21;border:1px solid #2a2f3a;border-radius:8px;padding:7px}
    .card img{width:100%;border-radius:4px;display:block;background:#fff}
    .card .name{font-weight:700;font-size:13px;margin:5px 0 2px}
    .best .name{color:#7ee787}
    .sc{font-size:11px;color:#9aa4b2}.big{font-size:15px;color:#e6e6e6;font-weight:700}
    .missing{height:130px;display:flex;align-items:center;justify-content:center;color:#555;border:1px dashed #333;border-radius:4px}
    """.replace("WPX", str(THUMB_W))

    P = ["<meta charset='utf-8'>",
         f"<style>{css}</style><div class='wrap'>",
         "<h1>REPORT0 &mdash; s0 preliminary (single seed, finals only, judge "
         f"{html.escape(a.judge)}). Shared r0 across all configs.</h1>",
         "<table><tr><th>config</th><th>mean overall</th><th>&Delta; vs r0</th>"
         "<th>mean tokens</th><th>n</th></tr>"]
    for label, mo, dl, t, n in rows:
        P.append(f"<tr><td>{html.escape(label)}</td><td>{mo:.2f}</td>"
                 f"<td>{('%+.2f'%dl) if dl is not None else '–'}</td>"
                 f"<td>{('%.0fk'%(t/1000)) if t else '–'}</td><td>{n}</td></tr>")
    P.append("</table>")

    instr = {}
    for app in apps:
        for _, run_dir, arm in CONFIGS:
            tp = os.path.join(run_dir, arm, "problems", app, "trace.json")
            if os.path.exists(tp):
                instr[app] = json.load(open(tp)).get("instruction", "")
                break

    for app in apps:
        P.append(f"<div class='task'><h2>{html.escape(app)}</h2>"
                 f"<div class='instr'>{html.escape(instr.get(app, '')[:420])}</div>"
                 "<div class='row'>")
        cards = []
        for label, _, _ in [(c[0], c[1], c[2]) for c in CONFIGS]:
            fin, _, pdir = data[label]
            s = fin.get(app, {})
            png = os.path.join(pdir, app, png_name)
            cards.append((-(s.get("overall") or -1), label, s, png))
        best = min(c[0] for c in cards)
        for negov, label, s, png in sorted(cards):
            img = thumb_b64(png, THUMB_W) if os.path.exists(png) else None
            body = f"<img src='{img}' loading='lazy'>" if img else "<div class='missing'>n/a</div>"
            det = " · ".join(f"{ax[:4]} {s.get(ax,'?')}" for ax in AXES)
            cls = "card best" if negov == best else "card"
            ov = f"{-negov:.1f}" if negov <= 0 else "?"
            P.append(f"<div class='{cls}'>{body}<div class='name'>{html.escape(label)}</div>"
                     f"<div class='sc'><span class='big'>overall {ov}</span> — {det}</div></div>")
        P.append("</div></div>")
    P.append("</div>")

    with open(a.out, "w") as f:
        f.write("\n".join(P))
    print(f"wrote {a.out} ({os.path.getsize(a.out)//1024} KB, "
          f"{len(apps)} tasks x {len(CONFIGS)} configs, cand={a.cand})")


if __name__ == "__main__":
    main()
