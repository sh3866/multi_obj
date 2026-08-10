"""Build a clean self-contained HTML report for the strong-generator gold-critic
sub-experiment: per task, r0 + weak(SELF/FUSED/AXES/MAD) + gold(fused/axes/mad),
each with Fable's 0-10 scores shown as overall (f/d/o/c). Click image -> lightbox.
Expand a task to read the gold critiques (goldmad shows the per-axis + debate)."""
import json, os, base64, glob, html

RUN = "results/strongen"
REP = f"{RUN}/report"
AX = ["functionality", "design", "originality", "craft"]
ORDER = [("r0", "r0 (shared)"), ("weak_self", "weak · SELF"), ("weak_fused", "weak · FUSED"),
         ("weak_axes", "weak · AXES"), ("weak_mad", "weak · MAD"),
         ("gold_fused", "GOLD · fused"), ("gold_axes", "GOLD · axes"), ("gold_mad", "GOLD · mad")]
CRIT = {"gold_fused": "_critiques_goldfused", "gold_axes": "_critiques_goldaxes", "gold_mad": "_critiques_goldmad"}

mani = json.load(open(f"{REP}/manifest.json"))
tasks = sorted(mani)

def scores_for(t):
    p = f"{REP}/scores_{t}.json"
    return json.load(open(p)) if os.path.exists(p) else {}

def overall(s):
    return sum(s[a] for a in AX) / 4 if s and all(a in s for a in AX) else None

def datauri(path):
    if not path or not os.path.exists(path):
        return ""
    b = base64.b64encode(open(path, "rb").read()).decode()
    return f"data:image/png;base64,{b}"

def color(o):
    if o is None:
        return "#444"
    # 0->red 5->amber 8+->green
    if o >= 7: return "#2e7d46"
    if o >= 5.5: return "#5c8a3a"
    if o >= 4: return "#8a7a2a"
    if o >= 2.5: return "#9a5a2a"
    return "#9a3a3a"

# ---- aggregate means per variant ----
agg = {k: {a: [] for a in AX + ["overall"]} for k, _ in ORDER}
for t in tasks:
    s = scores_for(t)
    for k, _ in ORDER:
        if k in s and all(a in s[k] for a in AX):
            for a in AX: agg[k][a].append(s[k][a])
            agg[k]["overall"].append(overall(s[k]))
def mean(x): return sum(x)/len(x) if x else 0

rows = []
for k, lab in ORDER:
    o = mean(agg[k]["overall"])
    fa = " · ".join(f"{a[0]}{mean(agg[k][a]):.1f}" for a in AX)
    grp = "gold" if k.startswith("gold") else ("weak" if k.startswith("weak") else "base")
    rows.append((lab, o, fa, len(agg[k]["overall"]), grp))

parts = []
parts.append("""<style>
:root{color-scheme:dark}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#14161c;color:#e6e8ee;margin:0;padding:24px 32px}
h1{font-size:22px;margin:0 0 4px} .sub{color:#8a90a0;font-size:13px;margin-bottom:20px}
table.sum{border-collapse:collapse;margin:0 0 28px;font-size:14px}
table.sum td,table.sum th{padding:7px 14px;border-bottom:1px solid #2a2e38;text-align:left}
table.sum th{color:#9aa0b0;font-weight:600}
.pill{display:inline-block;min-width:44px;text-align:center;padding:2px 8px;border-radius:6px;color:#fff;font-weight:700}
.axmini{color:#aeb4c4;font-size:12px;margin-left:8px}
.grp-gold{color:#ffd479} .grp-weak{color:#9ec7ff}
.task{border:1px solid #262a34;border-radius:10px;margin:0 0 22px;padding:14px 16px;background:#181b22}
.task h2{font-size:15px;margin:0 0 2px} .instr{color:#8a90a0;font-size:12.5px;margin:0 0 12px;line-height:1.4}
.cards{display:flex;gap:10px;flex-wrap:wrap}
.card{width:200px;background:#1e222b;border:1px solid #2a2e38;border-radius:8px;overflow:hidden}
.card.best{border-color:#3a7a4a;box-shadow:0 0 0 1px #3a7a4a}
.card .lab{font-size:11.5px;padding:5px 8px;color:#c6ccdc;border-bottom:1px solid #2a2e38;display:flex;justify-content:space-between;align-items:center}
.card .lab .g{color:#ffd479} .card .lab .w{color:#9ec7ff}
.card img{width:100%;height:120px;object-fit:cover;object-position:top;cursor:zoom-in;display:block;background:#0c0d10}
.card .sc{padding:6px 8px;font-size:12px}
.card .sc b{font-size:15px}
.axg{color:#9aa0b0;font-size:11px;margin-top:2px}
details.crit{margin-top:12px} details.crit summary{cursor:pointer;color:#9aa0b0;font-size:12.5px}
.critbox{margin-top:8px;display:flex;gap:12px;flex-wrap:wrap}
.critcol{flex:1;min-width:280px;background:#12141a;border:1px solid #262a34;border-radius:8px;padding:10px 12px}
.critcol h4{margin:0 0 6px;font-size:12px} .critcol.gf h4{color:#ffb} .critcol.gm h4{color:#ffd479}
.critcol pre{white-space:pre-wrap;font-size:11.5px;line-height:1.45;color:#c2c8d8;margin:0;font-family:inherit}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;align-items:center;justify-content:center;z-index:99;cursor:zoom-out}
#lb img{max-width:96vw;max-height:96vh;box-shadow:0 8px 40px #000}
</style>""")

parts.append("<h1>Strong Generator — weak vs GOLD critic</h1>")
parts.append('<div class="sub">generator = critic = Qwen3.6-35B-A3B · 1 round from a shared r0 · '
             'weak critic = the model itself · GOLD critic = Opus (3 structures) · judge = Fable (independent). '
             'Score = mean of 4 axes; per-axis in parens.</div>')

# summary table
parts.append('<table class="sum"><tr><th>variant</th><th>overall (mean)</th><th>per-axis</th><th>n</th></tr>')
for lab, o, fa, n, grp in rows:
    cls = "grp-gold" if grp == "gold" else ("grp-weak" if grp == "weak" else "")
    parts.append(f'<tr><td class="{cls}">{html.escape(lab)}</td>'
                 f'<td><span class="pill" style="background:{color(o)}">{o:.2f}</span></td>'
                 f'<td class="axmini">{fa}</td><td>{n}</td></tr>')
parts.append("</table>")

# per-task
for t in tasks:
    s = scores_for(t)
    instr = mani[t]["instruction"]
    for b in ["You are a code expert. ", "You are a code expert, ", "You are a coding expert. ",
              "Please use your professional knowledge to generate accurate and professional responses. ",
              "Make sure the generated code is executable for demonstration. ",
              "Make sure the code you generate is executable for demonstration purposes. "]:
        instr = instr.replace(b, "")
    # best overall this task
    best = None; bo = -1
    for k, _ in ORDER:
        o = overall(s.get(k, {}))
        if o is not None and o > bo: bo, best = o, k
    parts.append('<div class="task">')
    parts.append(f'<h2>{t}</h2><div class="instr">{html.escape(instr.strip()[:220])}</div>')
    parts.append('<div class="cards">')
    for k, lab in ORDER:
        sk = s.get(k, {}); o = overall(sk)
        uri = datauri(mani[t]["artifacts"].get(k))
        labcls = "g" if k.startswith("gold") else ("w" if k.startswith("weak") else "")
        bestcls = " best" if k == best else ""
        oc = color(o)
        axtxt = " ".join(f"{a[0]}{sk[a]}" for a in AX) if o is not None else "—"
        ostr = f"{o:.2f}" if o is not None else "—"
        img = f'<img src="{uri}" onclick="LB(this.src)">' if uri else '<div style="height:120px;background:#0c0d10"></div>'
        parts.append(f'<div class="card{bestcls}"><div class="lab"><span class="{labcls}">{html.escape(lab)}</span></div>'
                     f'{img}<div class="sc" style="color:{oc}"><b>{ostr}</b> '
                     f'<span class="axg">({axtxt})</span></div></div>')
    parts.append('</div>')
    # gold critiques / debate
    parts.append('<details class="crit"><summary>▸ GOLD critiques &amp; MAD debate</summary><div class="critbox">')
    for k, cdir in CRIT.items():
        p = f"{RUN}/{cdir}/{t}.txt"
        txt = open(p).read() if os.path.exists(p) else "(none)"
        cls = "gm" if k == "gold_mad" else "gf"
        parts.append(f'<div class="critcol {cls}"><h4>{k.replace("gold_","GOLD ")}</h4><pre>{html.escape(txt)}</pre></div>')
    parts.append('</div></details>')
    parts.append('</div>')

parts.append('<div id="lb" onclick="this.style.display=\'none\'"><img id="lbimg"></div>')
parts.append('<script>function LB(s){document.getElementById("lbimg").src=s;document.getElementById("lb").style.display="flex";}</script>')

os.makedirs(REP, exist_ok=True)
open(f"{REP}/report.html", "w").write("<!doctype html><meta charset=utf-8><title>Strong Generator: weak vs GOLD</title>" + "".join(parts))
print(f"wrote {REP}/report.html")
# quick console summary
print("\nvariant means:")
for lab, o, fa, n, grp in rows:
    print(f"  {lab:16} {o:.2f}  ({fa})  n={n}")
