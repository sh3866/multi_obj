"""REPORT0 full — interactive s0 report.

Level 1: per task, all 7 configs side by side at each config's PEAK round
         (round with the highest judged overall for that task).
Level 2: click a config card -> expands to that config's round-by-round
         evolution: every candidate's screenshot + judge scores, and for
         AXES/MAD the full debate (per-critic critique/score/suggestion,
         cross-critique rebuttals, moderator synthesis) at that round.

Self-contained HTML (screenshots inlined as base64), pure CSS/JS accordion.

  python make_report0_full.py --judge s0full --out results/REPORT0_full.html
"""
from __future__ import annotations
import argparse, base64, html, json, os
from collections import defaultdict
from make_report import thumb_b64

AX = ["functionality", "design", "originality", "craft"]


def configs_for(seed):
    return [
        ("SELF", f"results/sharedr0/{seed}", "SELF"),
        ("FUSED", f"results/sharedr0/{seed}", "FUSED"),
        ("AXES", f"results/sharedr0/{seed}", "AXES"),
        ("MAD·main4", f"results/sharedr0/{seed}", "MAD"),
        ("MAD·visawi5", f"results/axisabl2/{seed}/visawi5", "MAD"),
        ("MAD·lt3", f"results/axisabl2/{seed}/lt3", "MAD"),
        ("MAD·hedonic3", f"results/axisabl2/{seed}/hedonic3", "MAD"),
    ]


def configs_from_rundir(run_dir):
    """Single-experiment mode: one config per arm dir under <run_dir>."""
    order = ["ZS", "SELF", "FUSED", "AXES", "MAD"]
    found = [a for a in order
             if os.path.isdir(os.path.join(run_dir, a, "problems"))]
    return [(a, run_dir, a) for a in found]


CONFIGS = configs_for("s0")   # default; overridden in main() by --seed
THUMB = 300
SMALL = 150


def load_all(run_dir, arm, judge):
    """{app: {cand_id: {axis: score}}} for every judged candidate."""
    p = os.path.join(run_dir, "judge", f"scores_{judge}.jsonl")
    out = defaultdict(lambda: defaultdict(dict))
    if os.path.exists(p):
        for l in open(p):
            if not l.strip():
                continue
            r = json.loads(l)
            if r["arm"] == arm and r.get("score") is not None:
                out[r["app"]][r["cand_id"]][r["axis"]] = r["score"]
    return out


def rounds_of(cand_scores):
    return sorted((c for c in cand_scores if c.startswith("r") and c[1:].isdigit()),
                  key=lambda c: int(c[1:]))


def esc(x):
    return html.escape(str(x))


COLORS = ["#7ee787", "#4a90d9", "#e0a030", "#d98a8a", "#b088d9",
          "#42c8b0", "#d9c98a"]


def curve_svg(cfg_data, apps, labels):
    """Inline SVG: mean judged overall vs round, one line per config."""
    W, H, PL, PB, PT, PR = 920, 380, 46, 34, 20, 150
    curves = {}
    ymin, ymax, xmax = 10, 0, 0
    for label in labels:
        sc = cfg_data[label][0]
        byr = defaultdict(list)
        for app in apps:
            for c, axd in sc.get(app, {}).items():
                if c.startswith("r") and c[1:].isdigit() and "overall" in axd:
                    byr[int(c[1:])].append(axd["overall"])
        pts = [(r, sum(v)/len(v)) for r, v in sorted(byr.items())]
        if not pts:
            continue
        curves[label] = pts
        xmax = max(xmax, max(r for r, _ in pts))
        ymin = min(ymin, min(y for _, y in pts))
        ymax = max(ymax, max(y for _, y in pts))
    ymin, ymax = ymin - 0.2, ymax + 0.2

    def X(r): return PL + (r / max(xmax, 1)) * (W - PL - PR)
    def Y(y): return PT + (1 - (y - ymin) / (ymax - ymin)) * (H - PT - PB)

    s = [f"<svg viewBox='0 0 {W} {H}' style='width:100%;max-width:{W}px;background:#12151b;border:1px solid #2a2f3a;border-radius:8px'>"]
    # y gridlines
    yy = ymin
    while yy <= ymax:
        s.append(f"<line x1='{PL}' y1='{Y(yy):.0f}' x2='{W-PR}' y2='{Y(yy):.0f}' stroke='#252a33'/>")
        s.append(f"<text x='{PL-8}' y='{Y(yy)+3:.0f}' fill='#7a8494' font-size='10' text-anchor='end'>{yy:.1f}</text>")
        yy += 0.5
    # x labels
    for r in range(0, xmax + 1):
        s.append(f"<text x='{X(r):.0f}' y='{H-PB+16}' fill='#7a8494' font-size='10' text-anchor='middle'>r{r}</text>")
    s.append(f"<text x='{(PL+W-PR)/2:.0f}' y='{H-4}' fill='#9aa4b2' font-size='11' text-anchor='middle'>round</text>")
    # lines + legend
    for i, (label, pts) in enumerate(curves.items()):
        col = COLORS[i % len(COLORS)]
        d = " ".join(f"{'M' if j==0 else 'L'}{X(r):.1f},{Y(y):.1f}" for j,(r,y) in enumerate(pts))
        s.append(f"<path d='{d}' fill='none' stroke='{col}' stroke-width='2'/>")
        # peak marker
        pr, pv = max(pts, key=lambda p: p[1])
        s.append(f"<circle cx='{X(pr):.1f}' cy='{Y(pv):.1f}' r='3.5' fill='{col}'/>")
        ly = PT + 6 + i * 17
        s.append(f"<line x1='{W-PR+8}' y1='{ly}' x2='{W-PR+26}' y2='{ly}' stroke='{col}' stroke-width='2'/>")
        s.append(f"<text x='{W-PR+30}' y='{ly+3}' fill='#c8d0dc' font-size='10'>{esc(label)} (pk r{pr})</text>")
    s.append("</svg>")
    return "".join(s)


def debate_html(trace_hist, rnd_idx):
    """Render the debate block for a given round index, if present."""
    for h in trace_hist:
        if h.get("round") == rnd_idx and "debate" in h:
            d = h["debate"]
            parts = ["<div class='debate'>"]
            parts.append("<div class='dh'>Critics</div>")
            for ax, c in d.get("critiques", {}).items():
                parts.append(
                    f"<div class='crit'><b>{esc(ax)}</b> "
                    f"<span class='sc2'>score {esc(c.get('score','?'))}</span><br>"
                    f"<i>{esc(c.get('critique',''))}</i><br>"
                    f"<span class='sug'>&rarr; {esc(c.get('suggestion',''))}</span></div>")
            if d.get("rebuttals"):
                parts.append("<div class='dh'>Cross-critique (debate)</div>")
                for rb in d["rebuttals"]:
                    conf = rb.get("conflicts") or []
                    acc = rb.get("accept") or []
                    comp = rb.get("compromise", "")
                    parts.append(
                        f"<div class='reb'><b>{esc(rb.get('axis','?'))}</b> rebuts:<br>"
                        + (f"<span class='cf'>conflicts:</span> {esc(' | '.join(map(str,conf)))}<br>" if conf else "")
                        + (f"<span class='ac'>accepts:</span> {esc(' | '.join(map(str,acc)))}<br>" if acc else "")
                        + (f"<span class='cp'>compromise:</span> {esc(comp)}" if comp else "")
                        + "</div>")
            syn = d.get("synthesis", {})
            parts.append("<div class='dh'>Moderator</div>")
            parts.append(
                f"<div class='syn'>good_enough={esc(syn.get('good_enough'))}<br>"
                f"<b>rationale:</b> {esc(syn.get('rationale',''))}<br>"
                f"<b>revision:</b> {esc(syn.get('revision',''))[:400]}</div>")
            parts.append("</div>")
            return "".join(parts)
    return ""


def main():
    global CONFIGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="s0", help="s0 | s1 | s2")
    ap.add_argument("--judge", default="qvl72")
    ap.add_argument("--run-dir", default=None,
                    help="single-experiment mode: build arm-comparison report "
                         "for this dir (e.g. results/art32b/s0)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.run_dir:
        CONFIGS = configs_from_rundir(a.run_dir)
        if a.out is None:
            a.out = os.path.join(a.run_dir, "REPORT_full.html")
    else:
        CONFIGS = configs_for(a.seed)
        if a.out is None:
            a.out = f"results/REPORT_{a.seed}_full.html"

    # load judged scores + traces per config
    cfg_data = {}
    for label, rd, arm in CONFIGS:
        scores = load_all(rd, arm, a.judge)
        pdir = os.path.join(rd, arm, "problems")
        cfg_data[label] = (scores, pdir, arm)
    apps = sorted({app for (sc, _, _) in cfg_data.values() for app in sc})

    # peak round per (config, app)
    def peak(label, app):
        sc = cfg_data[label][0].get(app, {})
        best, br = -1, None
        for c in rounds_of(sc):
            o = sc[c].get("overall", -1)
            if o > best:
                best, br = o, c
        return br, best

    css = """
    body{font-family:-apple-system,'Segoe UI',sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
    .wrap{max-width:2300px;margin:0 auto;padding:24px}
    h1{font-size:20px} h2{font-size:15px;margin:10px 0 4px}
    table{border-collapse:collapse;margin:12px 0}
    td,th{border:1px solid #333;padding:4px 12px;font-size:13px}
    .task{margin:26px 0;border-top:1px solid #333;padding-top:12px}
    .instr{color:#9aa4b2;font-size:12px;max-width:1500px;white-space:pre-wrap;margin-bottom:8px}
    .row{display:flex;gap:12px;overflow-x:auto;padding:6px 0}
    .card{flex:0 0 auto;width:WPXpx;background:#171a21;border:1px solid #2a2f3a;border-radius:8px;padding:7px;cursor:pointer}
    .card:hover{border-color:#4a90d9}
    .card img{width:100%;border-radius:4px;display:block;background:#fff}
    .card .name{font-weight:700;font-size:13px;margin:5px 0 2px}
    .best .name{color:#7ee787}
    .sc{font-size:11px;color:#9aa4b2}.big{font-size:15px;color:#e6e6e6;font-weight:700}
    .peak{font-size:10px;color:#e0a030}
    .detail{display:none;background:#12151b;border:1px solid #2a2f3a;border-radius:8px;margin:8px 0;padding:12px}
    .detail.open{display:block}
    .evorow{display:flex;gap:10px;overflow-x:auto;padding:6px 0;align-items:flex-start}
    .evo{flex:0 0 auto;width:SPXpx}
    .evo img{width:100%;border-radius:4px;background:#fff;display:block}
    .evo.pk{outline:2px solid #e0a030}
    .evo .rl{font-size:11px;font-weight:700;margin-top:3px}
    .evo .rs{font-size:10px;color:#9aa4b2}
    .debate{font-size:11px;color:#c8d0dc;margin-top:6px;border-top:1px dashed #333;padding-top:6px}
    .dh{font-weight:700;color:#7aa7d9;margin:6px 0 2px;font-size:11px}
    .crit,.reb,.syn{margin:3px 0;padding:4px 6px;background:#1a1e26;border-radius:4px}
    .sc2{color:#e0a030}.sug{color:#7ee787}.cf{color:#d98a8a}.ac{color:#8ad9a0}.cp{color:#d9c98a}
    .close{float:right;color:#888;cursor:pointer;font-size:12px}
    """.replace("WPX", str(THUMB)).replace("SPX", str(SMALL))

    js = """
    function tog(id){var e=document.getElementById(id);
      document.querySelectorAll('.detail.open').forEach(function(d){if(d.id!=id)d.classList.remove('open');});
      e.classList.toggle('open'); if(e.classList.contains('open'))e.scrollIntoView({behavior:'smooth',block:'nearest'});}
    function lb(src){var o=document.getElementById('lbox');
      o.querySelector('img').src=src; o.style.display='flex';}
    document.addEventListener('keydown',function(e){if(e.key=='Escape')
      document.getElementById('lbox').style.display='none';});
    """
    lbcss = ("#lbox{display:none;position:fixed;inset:0;z-index:999;"
             "background:rgba(0,0,0,.9);align-items:center;justify-content:center;"
             "cursor:zoom-out}"
             "#lbox img{max-width:96vw;max-height:96vh;box-shadow:0 0 40px #000}")

    P = ["<meta charset='utf-8'>",
         f"<style>{css}\n{lbcss}</style><script>{js}</script>",
         # lightbox overlay: click anywhere (or Esc) to dismiss
         "<div id='lbox' onclick=\"this.style.display='none'\"><img src=''></div>",
         "<div class='wrap'>",
         f"<h1>REPORT0 full &mdash; s0, judge {esc(a.judge)}. Cards show each "
         "config at its PEAK round; click a card for round-by-round evolution "
         "+ debate.</h1>"]

    # quality-vs-round curves — all configs overlaid
    P.append("<h2>Quality vs round &mdash; mean judged overall (all configs, "
             "peak marked)</h2>")
    P.append(curve_svg(cfg_data, apps, [c[0] for c in CONFIGS]))

    # header ranking table: mean of per-task peak overall
    P.append("<table><tr><th>config</th><th>mean peak overall</th>"
             "<th>mean peak round</th><th>mean final overall</th></tr>")
    hdr = []
    for label, _, _ in CONFIGS:
        pk = [peak(label, app) for app in apps]
        pov = [b for (_, b) in pk if b >= 0]
        prd = [int(r[1:]) for (r, b) in pk if r]
        sc = cfg_data[label][0]
        fov = []
        for app in apps:
            rs = rounds_of(sc.get(app, {}))
            if rs:
                fov.append(sc[app][rs[-1]].get("overall", 0))
        hdr.append((label, sum(pov)/len(pov) if pov else 0,
                    sum(prd)/len(prd) if prd else 0,
                    sum(fov)/len(fov) if fov else 0))
    for label, pov, prd, fov in sorted(hdr, key=lambda x: -x[1]):
        P.append(f"<tr><td>{esc(label)}</td><td>{pov:.2f}</td>"
                 f"<td>{prd:.1f}</td><td>{fov:.2f}</td></tr>")
    P.append("</table>")

    # instructions
    instr = {}
    for app in apps:
        for _, rd, arm in CONFIGS:
            tp = os.path.join(rd, arm, "problems", app, "trace.json")
            if os.path.exists(tp):
                instr[app] = json.load(open(tp)).get("instruction", "")
                break

    for app in apps:
        P.append(f"<div class='task'><h2>{esc(app)}</h2>"
                 f"<div class='instr'>{esc(instr.get(app,'')[:380])}</div>"
                 "<div class='row'>")
        cards = []
        for label, rd, arm in CONFIGS:
            sc = cfg_data[label][0].get(app, {})
            rs = rounds_of(sc)
            fr = rs[-1] if rs else None          # final (shipped) round
            fov = sc[fr].get("overall", -1) if fr else -1
            br, bov = peak(label, app)            # peak round for annotation
            cards.append((-(fov if fov >= 0 else -1), label, rd, arm, fr, fov, br, bov))
        best = min(c[0] for c in cards)
        for negov, label, rd, arm, fr, fov, br, bov in sorted(cards):
            pdir = cfg_data[label][1]
            # card shows the FINAL (shipped) artifact; peak annotated alongside
            png = os.path.join(pdir, app, "candidates", f"{fr}.png") if fr else None
            img = thumb_b64(png, THUMB) if png and os.path.exists(png) else None
            s = cfg_data[label][0].get(app, {}).get(fr, {}) if fr else {}
            det = " · ".join(f"{ax[:4]} {s.get(ax,'?')}" for ax in AX)
            did = f"d_{app}_{label}".replace("·", "").replace(" ", "")
            body = f"<img src='{img}'>" if img else "<div class='sc'>n/a</div>"
            cls = "card best" if negov == best else "card"
            pk_note = (f"<span class='peak'>peak {bov:.1f}@{esc(br)}</span>"
                       if br and bov > fov + 0.05 else "")
            P.append(
                f"<div class='{cls}' onclick=\"tog('{did}')\">{body}"
                f"<div class='name'>{esc(label)}</div>"
                f"<div class='sc'><span class='big'>final {(-negov):.1f}</span> "
                f"<span class='peak'>@{esc(fr)}</span> {pk_note}<br>{det}</div></div>")

        # detail panels (evolution + debate) — one per config, below the row
        P.append("</div>")
        for label, rd, arm in CONFIGS:
            did = f"d_{app}_{label}".replace("·", "").replace(" ", "")
            pdir = cfg_data[label][1]
            sc = cfg_data[label][0].get(app, {})
            br, _ = peak(label, app)
            tp = os.path.join(pdir, app, "trace.json")
            hist = json.load(open(tp)).get("history", []) if os.path.exists(tp) else []
            P.append(f"<div class='detail' id='{did}'>"
                     f"<span class='close' onclick=\"tog('{did}')\">close ✕</span>"
                     f"<b>{esc(label)}</b> — round-by-round on {esc(app)}"
                     "<div class='evorow'>")
            for c in rounds_of(sc):
                png = os.path.join(pdir, app, "candidates", f"{c}.png")
                img = thumb_b64(png, SMALL) if os.path.exists(png) else None
                o = sc[c].get("overall", "?")
                d2 = " ".join(f"{ax[:1]}{sc[c].get(ax,'?')}" for ax in AX)
                pk = " pk" if c == br else ""
                # thumbnail is a compressed JPEG; clicking opens the ORIGINAL
                # png full-resolution in a lightbox (path relative to results/).
                # link the original relative to the report's own location
                href = os.path.relpath(png, os.path.dirname(os.path.abspath(a.out)))
                body = (f"<img src='{img}' onclick=\"lb('{href}')\" "
                        f"style='cursor:zoom-in'>" if img
                        else "<div class='rs'>n/a</div>")
                P.append(f"<div class='evo{pk}'>{body}"
                         f"<div class='rl'>{esc(c)} · {o}</div>"
                         f"<div class='rs'>{d2}</div></div>")
            P.append("</div>")
            # debate transcript per round (AXES/MAD only)
            if arm in ("AXES", "MAD"):
                for c in rounds_of(sc):
                    dbg = debate_html(hist, int(c[1:]))
                    if dbg:
                        P.append(f"<details><summary style='cursor:pointer;font-size:12px;"
                                 f"color:#7aa7d9'>debate @ {esc(c)}</summary>{dbg}</details>")
            P.append("</div>")
        P.append("</div>")
    P.append("</div>")

    with open(a.out, "w") as f:
        f.write("\n".join(P))
    print(f"wrote {a.out} ({os.path.getsize(a.out)//1024} KB, {len(apps)} tasks)")


if __name__ == "__main__":
    main()
