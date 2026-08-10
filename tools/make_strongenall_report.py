"""Clean self-contained HTML report for the cap-10 strong-generator run
(strongenall): gen = critic = Qwen3.6-35B-A3B, up to 10 rounds from a shared r0,
judge = Fable (independent). Per task: r0 + SELF/FUSED/AXES/MAD finals with Fable
0-10 scores shown as overall (f d o c); click image -> lightbox; expand a task to
read each arm's round-by-round self-critic progression (the multi-round 'debate')."""
import json, os, base64, html

RUN = "results/strongenall"
REP = f"{RUN}/report"
AX = ["functionality", "design", "originality", "craft"]
ARMS = ["r0", "SELF", "FUSED", "AXES", "MAD"]
LAB = {"r0": "r0 (shared)", "SELF": "SELF", "FUSED": "FUSED", "AXES": "AXES", "MAD": "MAD"}
TASKS = ["ab%06d" % i for i in range(1, 13)]

mani = json.load(open(f"{REP}/manifest.json"))

def scores_for(t):
    p = f"{REP}/scores_{t}.json"
    return json.load(open(p)) if os.path.exists(p) else {}

def overall(s):
    return sum(s[a] for a in AX) / 4 if s and all(a in s for a in AX) else None

def card_frame(frames):
    if not frames:
        return None
    return frames[1] if len(frames) >= 2 else frames[0]

def datauri(path):
    if not path or not os.path.exists(path):
        return ""
    b = base64.b64encode(open(path, "rb").read()).decode()
    return f"data:image/png;base64,{b}"

def color(o):
    if o is None: return "#444"
    if o >= 7: return "#2e7d46"
    if o >= 5.5: return "#5c8a3a"
    if o >= 4: return "#8a7a2a"
    if o >= 2.5: return "#9a5a2a"
    return "#9a3a3a"

def trace_hist(arm, t):
    p = f"{RUN}/s0/{arm}/problems/{t}/trace.json"
    if not os.path.exists(p): return [], None
    tr = json.load(open(p))
    return tr.get("history", []), tr.get("final_id")

# ---- aggregate means ----
agg = {a: {x: [] for x in AX + ["overall"]} for a in ARMS}
for t in TASKS:
    s = scores_for(t)
    for a in ARMS:
        if a in s and all(x in s[a] for x in AX):
            for x in AX: agg[a][x].append(s[a][x])
            agg[a]["overall"].append(overall(s[a]))
def mean(x): return sum(x)/len(x) if x else 0
best_arm_overall = max([a for a in ARMS if a != "r0"], key=lambda a: mean(agg[a]["overall"]))

parts = []
parts.append("""<style>
:root{color-scheme:dark}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#14161c;color:#e6e8ee;margin:0;padding:24px 32px}
h1{font-size:22px;margin:0 0 4px} .sub{color:#8a90a0;font-size:13px;margin-bottom:20px;line-height:1.5}
table.sum{border-collapse:collapse;margin:0 0 10px;font-size:14px}
table.sum td,table.sum th{padding:7px 14px;border-bottom:1px solid #2a2e38;text-align:left}
table.sum th{color:#9aa0b0;font-weight:600}
.pill{display:inline-block;min-width:44px;text-align:center;padding:2px 8px;border-radius:6px;color:#fff;font-weight:700}
.axmini{color:#aeb4c4;font-size:12px}
.win{color:#ffd479;font-weight:700}
.note{color:#8a90a0;font-size:12.5px;margin:6px 0 26px;line-height:1.5}
.task{border:1px solid #262a34;border-radius:10px;margin:0 0 22px;padding:14px 16px;background:#181b22}
.task h2{font-size:15px;margin:0 0 2px} .instr{color:#8a90a0;font-size:12.5px;margin:0 0 12px;line-height:1.4}
.cards{display:flex;gap:10px;flex-wrap:wrap}
.card{width:210px;background:#1e222b;border:1px solid #2a2e38;border-radius:8px;overflow:hidden}
.card.best{border-color:#c99a2a;box-shadow:0 0 0 1px #c99a2a}
.card .lab{font-size:11.5px;padding:5px 8px;color:#c6ccdc;border-bottom:1px solid #2a2e38;display:flex;justify-content:space-between;align-items:center}
.card .lab .rnd{color:#7a8090;font-size:10.5px}
.card img{width:100%;height:132px;object-fit:cover;object-position:top;cursor:zoom-in;display:block;background:#0c0d10}
.card .sc{padding:6px 8px;font-size:12px} .card .sc b{font-size:15px}
.axg{color:#9aa0b0;font-size:11px}
details.crit{margin-top:12px} details.crit>summary{cursor:pointer;color:#9aa0b0;font-size:12.5px}
.arms{margin-top:10px;display:flex;flex-direction:column;gap:10px}
.armbox{background:#12141a;border:1px solid #262a34;border-radius:8px;padding:8px 12px}
.armbox h4{margin:0 0 6px;font-size:12px}
.armbox.m h4{color:#ffd479} .armbox.a h4{color:#9ec7ff}
.rnd{font-size:11.5px;line-height:1.45;color:#c2c8d8;border-left:2px solid #2a2e38;padding:2px 0 2px 10px;margin:0 0 6px}
.rnd .rn{color:#8a90a0;font-weight:700;margin-right:6px}
.rnd .cf{color:#c98a6a}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;align-items:center;justify-content:center;z-index:99;cursor:zoom-out}
#lb img{max-width:96vw;max-height:96vh;box-shadow:0 8px 40px #000}
</style>""")

parts.append("<h1>Strong Generator — cap-10 rounds (weak self-critic)</h1>")
parts.append('<div class="sub">generator = critic = Qwen3.6-35B-A3B · up to <b>10 rounds</b> from a shared r0 · '
             'each arm selects its own best round · judge = <b>Fable</b> (independent). '
             'Score = mean of 4 axes; per-axis (f d o c) in parens. 3 frames/artifact (t0/t1/t2) so JS-drawn content is visible.</div>')

# summary table
parts.append('<table class="sum"><tr><th>arm</th><th>overall</th><th>func</th><th>design</th><th>orig</th><th>craft</th><th>Δ vs r0</th><th>wins</th></tr>')
# wins per arm
wins = {a: 0 for a in ARMS if a != "r0"}
for t in TASKS:
    s = scores_for(t)
    cand = [a for a in ARMS if a != "r0" and overall(s.get(a, {})) is not None]
    if cand:
        wins[max(cand, key=lambda a: overall(s[a]))] += 1
r0m = mean(agg["r0"]["overall"])
for a in ARMS:
    o = mean(agg[a]["overall"])
    d = "" if a == "r0" else f"{o-r0m:+.2f}"
    w = "" if a == "r0" else str(wins[a])
    labcls = "win" if a == best_arm_overall else ""
    parts.append(f'<tr><td class="{labcls}">{LAB[a]}</td>'
                 f'<td><span class="pill" style="background:{color(o)}">{o:.2f}</span></td>'
                 + "".join(f'<td class="axmini">{mean(agg[a][x]):.2f}</td>' for x in AX)
                 + f'<td class="axmini">{d}</td><td class="axmini">{w}</td></tr>')
parts.append("</table>")
parts.append('<div class="note">MAD & AXES (structured critique) separate clearly from SELF/FUSED at 10 rounds — '
             'SELF/FUSED often converge back to r0 (no improvement), while MAD almost never stops and gains the most. '
             'Click any image to zoom; expand a task to read each arm’s round-by-round self-critique.</div>')

# per task
for t in TASKS:
    s = scores_for(t)
    instr = mani[t]["instruction"]
    for b in ["You are a code expert. ", "You are a code expert, ", "You are a coding expert. ",
              "Please use your professional knowledge to generate accurate and professional responses. ",
              "Make sure the generated code is executable for demonstration. ",
              "Make sure the code you generate is executable for demonstration purposes. "]:
        instr = instr.replace(b, "")
    best = None; bo = -1
    for a in ARMS:
        if a == "r0": continue
        o = overall(s.get(a, {}))
        if o is not None and o > bo: bo, best = o, a
    parts.append('<div class="task">')
    parts.append(f'<h2>{t}</h2><div class="instr">{html.escape(instr.strip()[:220])}</div>')
    parts.append('<div class="cards">')
    for a in ARMS:
        sa = s.get(a, {}); o = overall(sa)
        uri = datauri(card_frame(mani[t]["artifacts"].get(a, [])))
        rnd = mani[t]["final_round"].get(a, "") if a != "r0" else ""
        bestcls = " best" if a == best else ""
        oc = color(o)
        axtxt = " ".join(f"{x[0]}{sa[x]}" for x in AX) if o is not None else "—"
        ostr = f"{o:.2f}" if o is not None else "—"
        img = f'<img src="{uri}" onclick="LB(this.src)">' if uri else '<div style="height:132px;background:#0c0d10"></div>'
        parts.append(f'<div class="card{bestcls}"><div class="lab"><span>{LAB[a]}</span><span class="rnd">{rnd}</span></div>'
                     f'{img}<div class="sc" style="color:{oc}"><b>{ostr}</b> '
                     f'<span class="axg">({axtxt})</span></div></div>')
    parts.append('</div>')
    # round-by-round progression per arm
    parts.append('<details class="crit"><summary>▸ round-by-round self-critique (how each arm evolved)</summary><div class="arms">')
    for a in ["MAD", "AXES", "FUSED", "SELF"]:
        hist, fid = trace_hist(a, t)
        cls = "m" if a == "MAD" else ("a" if a == "AXES" else "")
        parts.append(f'<div class="armbox {cls}"><h4>{a} · {len(hist)} rounds (final {fid})</h4>')
        if not hist:
            parts.append('<div class="rnd">(no history)</div>')
        for e in hist:
            rn = e.get("round", "?")
            rev = (e.get("revision") or "").strip()
            if not rev:
                continue
            rev = html.escape(rev[:340])
            confs = e.get("conflicts") or []
            cf = ""
            if confs and isinstance(confs, list) and confs[0] and "Missing data" not in confs[0] and "cannot resolve" not in confs[0].lower():
                cf = f' <span class="cf">⇄ {html.escape(str(confs[0])[:160])}</span>'
            parts.append(f'<div class="rnd"><span class="rn">r{rn}</span>{rev}{cf}</div>')
        parts.append('</div>')
    parts.append('</div></details>')
    parts.append('</div>')

parts.append('<div id="lb" onclick="this.style.display=\'none\'"><img id="lbimg"></div>')
parts.append('<script>function LB(s){document.getElementById("lbimg").src=s;document.getElementById("lb").style.display="flex";}</script>')

os.makedirs(REP, exist_ok=True)
out = f"{REP}/report.html"
open(out, "w").write("<!doctype html><meta charset=utf-8><title>Strong Generator: cap-10</title>" + "".join(parts))
sz = os.path.getsize(out) / 1e6
print(f"wrote {out}  ({sz:.1f} MB)")
print("\narm means (overall):")
for a in ARMS:
    print(f"  {a:6} {mean(agg[a]['overall']):.2f}")
print("wins:", wins)
