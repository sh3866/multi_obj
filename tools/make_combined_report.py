"""One self-contained HTML with a 3-tab selector over the experiments run:
  Exp1  strongen (1-round): weak MoE self-critic vs Opus GOLD critique  [Table A]
  Exp2  cap-10 finals: SELF/FUSED/AXES/MAD best-round, blind Fable
  Exp3  cap-10 per-round trajectory: every round judged blind          [Table B]
Each tab: per-task images (click -> lightbox) + the critique/debate/round
elements used. All scores are the BLIND Fable judgments. Images base64-inlined
(main frame only, to keep size sane)."""
import json, os, base64, html, io
from collections import defaultdict
from PIL import Image

SA = "results/strongen"; SB = "results/strongenall"
REPA = f"{SA}/report"; REPB = f"{SB}/report"; TR = f"{REPB}/traj"
AX = ["functionality", "design", "originality", "craft"]
TASKS = [f"ab{i:06d}" for i in range(1, 13)]
OUT = f"{REPB}/combined_report.html"

_cache = {}
def uri(path, maxw=900):
    if not path or not os.path.exists(path): return ""
    ck = (path, maxw)
    if ck in _cache: return _cache[ck]
    try:
        im = Image.open(path).convert("RGB")
        if im.width > maxw:
            im = im.resize((maxw, round(im.height*maxw/im.width)), Image.LANCZOS)
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=80, optimize=True)
        u = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        u = f"data:image/png;base64,{base64.b64encode(open(path,'rb').read()).decode()}"
    _cache[ck] = u; return u
def ov(d): return sum(d[a] for a in AX) / 4 if d and all(a in d for a in AX) else None
def mean(x): return sum(x)/len(x) if x else None
def col(o):
    if o is None: return "#444"
    return "#2e7d46" if o>=7 else "#5c8a3a" if o>=5.5 else "#8a7a2a" if o>=4 else "#9a5a2a" if o>=2.5 else "#9a3a3a"
def clean_instr(s):
    for b in ["You are a code expert. ","You are a code expert, ","You are a coding expert. ",
              "Please use your professional knowledge to generate accurate and professional responses. ",
              "Make sure the generated code is executable for demonstration. ",
              "Make sure the code you generate is executable for demonstration purposes. "]:
        s = s.replace(b, "")
    return s.strip()
def esc(s): return html.escape(str(s))

P = []
def w(s): P.append(s)

# ---------------- styles ----------------
w("""<style>
:root{color-scheme:dark}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#12141a;color:#e6e8ee;margin:0;padding:0 0 60px}
header{position:sticky;top:0;z-index:20;background:#0e1016;border-bottom:1px solid #262a34;padding:14px 30px}
h1{font-size:19px;margin:0 0 10px}
nav button{background:#1e222b;color:#c6ccdc;border:1px solid #2a2e38;border-radius:8px;padding:8px 14px;margin-right:8px;font-size:13px;cursor:pointer}
nav button.on{background:#2b4a7a;border-color:#3a6ab0;color:#fff;font-weight:700}
.wrap{padding:22px 30px;max-width:1400px}
h2.sec{font-size:16px;margin:4px 0 2px} .desc{color:#8a90a0;font-size:12.5px;margin:0 0 16px;line-height:1.5}
table.t{border-collapse:collapse;margin:6px 0 20px;font-size:13px}
table.t td,table.t th{padding:6px 12px;border-bottom:1px solid #2a2e38;text-align:left;white-space:nowrap}
table.t th{color:#9aa0b0;font-weight:600}
.pill{display:inline-block;min-width:42px;text-align:center;padding:2px 7px;border-radius:6px;color:#fff;font-weight:700}
.mut{color:#8a90a0;font-size:12px}
.win{color:#ffd479;font-weight:700} .gold{color:#ffd479} .wk{color:#9ec7ff}
.task{border:1px solid #262a34;border-radius:10px;margin:0 0 20px;padding:13px 15px;background:#181b22}
.task h3{font-size:14px;margin:0 0 2px} .instr{color:#9aa0b0;font-size:12px;margin:0 0 10px;line-height:1.5;white-space:pre-wrap;background:#12141a;border:1px solid #232733;border-radius:6px;padding:8px 10px;max-height:240px;overflow:auto}
.cards{display:flex;gap:9px;flex-wrap:wrap}
.card{width:190px;background:#1e222b;border:1px solid #2a2e38;border-radius:8px;overflow:hidden}
.card.best{border-color:#c99a2a;box-shadow:0 0 0 1px #c99a2a}
.card .lab{font-size:11px;padding:4px 7px;color:#c6ccdc;border-bottom:1px solid #2a2e38;display:flex;justify-content:space-between}
.card img{width:100%;height:112px;object-fit:cover;object-position:top;cursor:zoom-in;display:block;background:#0c0d10}
.card .sc{padding:5px 7px;font-size:11.5px} .card .sc b{font-size:14px}
.axg{color:#9aa0b0;font-size:10.5px}
details{margin-top:10px} summary{cursor:pointer;color:#9aa0b0;font-size:12px}
.box{margin-top:8px;display:flex;gap:10px;flex-wrap:wrap}
.colb{flex:1;min-width:260px;background:#12141a;border:1px solid #262a34;border-radius:8px;padding:9px 11px}
.colb h4{margin:0 0 5px;font-size:11.5px} .colb.gm h4{color:#ffd479} .colb.gf h4{color:#ffb}
.colb pre,.rev{white-space:pre-wrap;font-size:11px;line-height:1.45;color:#c2c8d8;margin:0;font-family:inherit}
.deb{font-size:11px;line-height:1.5;color:#c2c8d8}
.deb .ax{color:#9ec7ff;font-weight:700} .deb .cf{color:#c98a6a} .deb .mo{color:#ffd479;font-weight:700}
.film{display:flex;gap:6px;flex-wrap:wrap;align-items:flex-end;margin-top:6px}
.fr{width:96px} .fr img{width:96px;height:64px;object-fit:cover;object-position:top;cursor:zoom-in;border:1px solid #2a2e38;border-radius:4px;display:block}
.fr .rl{font-size:10px;color:#8a90a0;text-align:center;margin-top:1px}
.armrow{margin:8px 0;padding:7px 9px;background:#14161c;border:1px solid #232733;border-radius:7px}
.armrow .an{font-size:12px;font-weight:700;margin-bottom:2px}
.an.SELF{color:#9ec7ff} .an.FUSED{color:#b0d0a0} .an.AXES{color:#e0b0e0} .an.MAD{color:#ffd479}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.93);display:none;align-items:center;justify-content:center;z-index:99;cursor:zoom-out;padding:20px}
.lbwrap{display:flex;flex-direction:column;align-items:center;gap:12px;max-width:96vw;max-height:96vh}
#lb img{max-width:92vw;max-height:78vh;box-shadow:0 8px 40px #000;border-radius:4px}
#lbcap{color:#e6e8ee;font-size:14px;line-height:1.55;max-width:900px;text-align:center;background:#181b22;border:1px solid #2a2e38;padding:11px 16px;border-radius:8px;cursor:default}
section{display:none} section.on{display:block}
</style>""")

w("<header><h1>MAD 웹디자인 실험 — 통합 리포트</h1><nav>"
  "<button id='b1' class='on' onclick=\"show('e1')\">① Gold vs MoE · 1라운드</button>"
  "<button id='b2' onclick=\"show('e2')\">② cap-10 최종</button>"
  "<button id='b3' onclick=\"show('e3')\">③ cap-10 라운드별 궤적</button>"
  "<button id='b4' onclick=\"show('e4')\">④ cap-10 재실행 · 파서수정 · critic 전사</button>"
  "</nav></header>")

# =========================================================== EXP 1
def scores(rep, t):
    p=f"{rep}/scores_{t}.json"; return json.load(open(p)) if os.path.exists(p) else {}
maniA = json.load(open(f"{REPA}/manifest.json"))
V1 = [("r0","r0 (공유)"),("weak_self","weak·SELF"),("weak_fused","weak·FUSED"),("weak_axes","weak·AXES"),
      ("weak_mad","weak·MAD"),("gold_fused","GOLD·fused"),("gold_axes","GOLD·axes"),("gold_mad","GOLD·mad")]
S1 = {t: scores(REPA, t) for t in TASKS}
agg1 = {k: [] for k,_ in V1}
for t in TASKS:
    for k,_ in V1:
        if k in S1[t] and ov(S1[t][k]) is not None: agg1[k].append(ov(S1[t][k]))

w("<section id='e1' class='on'><div class='wrap'>")
w("<h2 class='sec'>① 강생성기 1라운드 — MoE 자기크리틱(weak) vs Opus GOLD 크리틱</h2>")
w("<div class='desc'>generator=critic=Qwen3.6-35B-A3B · 공유 r0에서 1라운드 · weak=모델 자기평가, GOLD=Opus(3구조) · judge=Fable(블라인드). 점수=4축 평균, 괄호는 (f d o c).</div>")
# Table A: matched-structure
def m(k): return mean(agg1[k])
w("<b>표 A — 같은 구조에서 critic만 MoE→Opus 교체</b>")
w("<table class='t'><tr><th>구조</th><th>MoE(weak)</th><th>Opus(gold)</th><th>Δ</th></tr>")
for name,wk,gd in [("fused","weak_fused","gold_fused"),("axes","weak_axes","gold_axes"),("mad","weak_mad","gold_mad")]:
    a,b=m(wk),m(gd); w(f"<tr><td>{name}</td><td>{a:.2f}</td><td class='gold'>{b:.2f}</td><td>{b-a:+.2f}</td></tr>")
w("</table>")
# blind means all 8
w("<b>블라인드 평균 (8 variant)</b><table class='t'><tr><th>variant</th><th>overall</th><th>per-axis</th></tr>")
for k,lab in V1:
    o=m(k); fa=" ".join(f"{a[0]}{mean([S1[t][k][a] for t in TASKS if k in S1[t]]):.1f}" for a in AX)
    cls="gold" if k.startswith("gold") else ("wk" if k.startswith("weak") else "")
    w(f"<tr><td class='{cls}'>{esc(lab)}</td><td><span class='pill' style='background:{col(o)}'>{o:.2f}</span></td><td class='mut'>{fa}</td></tr>")
w("</table>")
# per task
for t in TASKS:
    s=S1[t]; instr=clean_instr(maniA[t]["instruction"])
    best=None;bo=-1
    for k,_ in V1:
        if k=="r0": continue
        o=ov(s.get(k,{}))
        if o is not None and o>bo: bo,best=o,k
    w(f"<div class='task'><h3>{t}</h3><div class='instr'>{esc(instr)}</div><div class='cards'>")
    for k,lab in V1:
        sk=s.get(k,{}); o=ov(sk); u=uri(maniA[t]["artifacts"].get(k))
        ax=" ".join(f"{a[0]}{sk[a]}" for a in AX) if o is not None else "—"
        bc=" best" if k==best else ""
        reason = esc(sk.get("reason", ""))
        img=(f"<img src='{u}' data-reason=\"{reason}\" onclick='LB(this)'>" if u
             else "<div style='height:112px;background:#0c0d10'></div>")
        os_=f"{o:.2f}" if o is not None else "—"
        rlab = " <span class='axg'>· 클릭→의견</span>" if reason else ""
        w(f"<div class='card{bc}'><div class='lab'><span>{esc(lab)}</span></div>{img}"
          f"<div class='sc' style='color:{col(o)}'><b>{os_}</b> <span class='axg'>({ax})</span>{rlab}</div></div>")
    w("</div>")
    # gold critiques + MAD debate
    w("<details><summary>▸ GOLD 크리틱 &amp; MAD 4자 토론</summary><div class='box'>")
    for k,cdir in [("gold_fused","_critiques_goldfused"),("gold_axes","_critiques_goldaxes"),("gold_mad","_critiques_goldmad")]:
        p=f"{SA}/{cdir}/{t}.txt"; txt=open(p).read() if os.path.exists(p) else "(none)"
        cls="gm" if k=="gold_mad" else "gf"
        w(f"<div class='colb {cls}'><h4>{k.replace('gold_','GOLD ')}</h4><pre>{esc(txt)}</pre></div>")
    w("</div>")
    dp=f"{SA}/_debate_goldmad/{t}.json"
    if os.path.exists(dp):
        d=json.load(open(dp))
        w("<div class='deb' style='margin-top:8px'><b class='mo'>MAD 토론 전사</b>")
        for v in d.get("verdicts",[]):
            w(f"<div><span class='ax'>[{esc(v.get('axis'))}]</span> {esc(v.get('critique',''))} <i>→ {esc(v.get('suggestion',''))}</i></div>")
        for r in d.get("debate",[]):
            cf=r.get("conflicts") or []
            if cf: w(f"<div><span class='cf'>⇄ [{esc(r.get('axis'))}]</span> {esc('; '.join(cf))} — {esc(r.get('compromise',''))}</div>")
        mo=d.get("moderator",{})
        if mo: w(f"<div><span class='mo'>[moderator]</span> {esc(mo.get('rationale',''))} → {esc(mo.get('revision',''))}</div>")
        w("</div>")
    w("</details></div>")
w("</div></section>")

# =========================================================== EXP 2
maniB = json.load(open(f"{REPB}/manifest.json"))
ARMS=["r0","SELF","FUSED","AXES","MAD"]
S2={t: scores(REPB,t) for t in TASKS}
def trace(arm,t):
    p=f"{SB}/s0/{arm}/problems/{t}/trace.json"; return json.load(open(p)) if os.path.exists(p) else None
def revlog(arm,t):
    tr=trace(arm,t)
    if not tr: return []
    out=[]
    for e in tr.get("history",[]):
        rev=(e.get("revision") or "").strip()
        if rev: out.append((e.get("round"), rev))
    return out
agg2={a:[] for a in ARMS}
for t in TASKS:
    for a in ARMS:
        if a in S2[t] and ov(S2[t][a]) is not None: agg2[a].append(ov(S2[t][a]))
w("<section id='e2'><div class='wrap'>")
w("<h2 class='sec'>② cap-10 최종본 — 각 arm의 best 라운드 (블라인드 Fable)</h2>")
w("<div class='desc'>gen=critic=Qwen3.6-35B-A3B · 공유 r0에서 최대 10라운드 · 각 arm이 자기 best 라운드 선택 · judge=Fable(블라인드). 펼치면 라운드별 self-critique(revision 로그) = 이 실험의 'debate'.</div>")
w("<table class='t'><tr><th>arm</th><th>overall</th><th>per-axis</th></tr>")
for a in ARMS:
    o=mean(agg2[a]); fa=" ".join(f"{x[0]}{mean([S2[t][a][x] for t in TASKS if a in S2[t]]):.1f}" for x in AX)
    w(f"<tr><td>{a}</td><td><span class='pill' style='background:{col(o)}'>{o:.2f}</span></td><td class='mut'>{fa}</td></tr>")
w("</table>")
for t in TASKS:
    s=S2[t]; instr=clean_instr(maniB[t]["instruction"])
    best=None;bo=-1
    for a in ARMS:
        if a=="r0": continue
        o=ov(s.get(a,{}))
        if o is not None and o>bo: bo,best=o,a
    w(f"<div class='task'><h3>{t}</h3><div class='instr'>{esc(instr)}</div><div class='cards'>")
    for a in ARMS:
        sk=s.get(a,{}); o=ov(sk)
        fr=maniB[t]["artifacts"].get(a,[]); u=uri(fr[1] if len(fr)>1 else (fr[0] if fr else None))
        ax=" ".join(f"{x[0]}{sk[x]}" for x in AX) if o is not None else "—"
        bc=" best" if a==best else ""; rr=maniB[t].get("final_round",{}).get(a,"") if a!="r0" else ""
        img=f"<img src='{u}' onclick='LB(this)'>" if u else "<div style='height:112px;background:#0c0d10'></div>"
        os_=f"{o:.2f}" if o is not None else "—"
        w(f"<div class='card{bc}'><div class='lab'><span>{a}</span><span class='mut'>{rr}</span></div>{img}"
          f"<div class='sc' style='color:{col(o)}'><b>{os_}</b> <span class='axg'>({ax})</span></div></div>")
    w("</div>")
    w("<details><summary>▸ 라운드별 self-critique (각 arm이 매 라운드 낸 수정 지시)</summary>")
    for a in ["SELF","FUSED","AXES","MAD"]:
        rl=revlog(a,t)
        w(f"<div class='armrow'><div class='an {a}'>{a} · {len(rl)} 라운드</div>")
        for rn,rev in rl: w(f"<div class='rev'><b>r{rn}:</b> {esc(rev[:300])}</div>")
        if not rl: w("<div class='rev mut'>(조기정지 — 수정 없음)</div>")
        w("</div>")
    w("</details></div>")
w("</div></section>")

# =========================================================== EXP 3
key=json.load(open(f"{TR}/traj_key.json"))
# (arm,task)-> {round: {overall, axis dict}}
traj=defaultdict(dict)
for cid,meta in key.items():
    sp=f"{TR}/traj_scores_{cid}.json"
    if not os.path.exists(sp): continue
    arm,task=meta["cell"].split("__"); sc=json.load(open(sp))
    for code,rnd in meta["code2round"].items():
        if code in sc: traj[(arm,task)][int(rnd)]=sc[code]
# paired 6-task table
def full_curve(arm,t):
    d=traj.get((arm,t),{})
    if not d: return None
    full={};last=None
    for r in range(11):
        if r in d: last=ov(d[r])
        full[r]=last
    return full
ARMS3=["SELF","FUSED","AXES","MAD"]
paired=[t for t in TASKS if all((a,t) in traj for a in ARMS3)]
w("<section id='e3'><div class='wrap'>")
w("<h2 class='sec'>③ cap-10 라운드별 궤적 — 모든 중간 라운드를 블라인드 채점</h2>")
w("<div class='desc'>각 라운드 산출물을 익명·순서셔플로 Fable가 절대채점(뒤 라운드=더 좋다 편향 제거). 조기정지 arm은 정지 후 carry-forward. 아래 표 B는 4-arm 모두 채점된 공통 태스크 페어링.</div>")
if paired:
    w(f"<b>표 B — 라운드별 평균 overall (공통 {len(paired)}개 태스크: {', '.join(paired)})</b>")
    w("<table class='t'><tr><th>arm</th>"+"".join(f"<th>r{r}</th>" for r in range(11))+"<th>peak</th><th>Δ</th></tr>")
    for a in ARMS3:
        vals=[mean([full_curve(a,t)[r] for t in paired]) for r in range(11)]
        pk=max(range(11),key=lambda r:vals[r])
        w(f"<tr><td class='an {a}' style='padding-left:12px'>{a}</td>"
          +"".join(f"<td style='color:{col(v)}'>{v:.2f}</td>" for v in vals)
          +f"<td>r{pk}</td><td>{vals[10]-vals[0]:+.2f}</td></tr>")
    w("</table>")
    w("<div class='desc'>SELF·FUSED는 일찍(r3~6) 피크 후 정체/하락, AXES·MAD(구조화·토론)는 라운드를 살려 크게 개선(+1.5). AXES는 빨리, MAD는 늦게까지.</div>")
# per-task filmstrips
for t in TASKS:
    have=[a for a in ARMS3 if (a,t) in traj]
    if not have: continue
    instr=clean_instr(maniB[t]["instruction"])
    w(f"<div class='task'><h3>{t}</h3><div class='instr'>{esc(instr)}</div>")
    for a in have:
        d=traj[(a,t)]; rounds=sorted(d)
        w(f"<div class='armrow'><div class='an {a}'>{a} — 라운드별 (블라인드 점수)</div><div class='film'>")
        for r in rounds:
            o=ov(d[r]); pth=f"{SB}/s0/{a}/problems/{t}/candidates/r{r}.png"; u=uri(pth)
            img=f"<img src='{u}' onclick='LB(this)'>" if u else "<div style='width:96px;height:64px;background:#0c0d10'></div>"
            w(f"<div class='fr'>{img}<div class='rl' style='color:{col(o)}'>r{r}: {o:.1f}</div></div>")
        w("</div>")
        rl=revlog(a,t)
        if rl:
            w("<details><summary>revision 로그</summary>")
            for rn,rev in rl: w(f"<div class='rev'><b>r{rn}:</b> {esc(rev[:260])}</div>")
            w("</details>")
        w("</div>")
    w("</div>")
w("</div></section>")

# =========================================================== EXP 4 (cap-10 재실행, 파서수정본)
SC = "results/strongenall2"
def trace4(arm, t):
    p = f"{SC}/s0/{arm}/problems/{t}/trace.json"
    return json.load(open(p)) if os.path.exists(p) else None
def cands4(arm, t):
    p = f"{SC}/s0/{arm}/problems/{t}/candidates.json"
    return json.load(open(p)) if os.path.exists(p) else []
def _real(x):
    """Drop template-placeholder echoes ('<axis + why...>') AND the literal
    ellipsis / empty values the critic model sometimes emits when it punts on a
    field. Returns None so callers can render an explicit 'left blank' marker
    instead of a bare '...' that reads like report truncation."""
    if x is None: return None
    if isinstance(x, list):
        x = [s for s in x if _real(s)]
        return x or None
    s = str(x).strip()
    if not s or (s.startswith("<") and s.endswith(">")): return None
    if not s.strip(".…-—· "): return None  # only ellipsis/dashes/dots
    return s
BLANK = "<span class='mut' style='font-style:italic'>(크리틱 모델이 이 축을 비워둠 — 리포트 생략 아님)</span>"
ARMS4 = ["SELF", "FUSED", "AXES", "MAD"]
TASKS4 = [t for t in TASKS if os.path.isdir(f"{SC}/s0/MAD/problems/{t}")]

w("<section id='e4'><div class='wrap'>")
w("<h2 class='sec'>④ cap-10 재실행 (파서 수정본) — critic 구성 &amp; 이미지 진화 (점수 비움)</h2>")
w("<div class='desc'>gen=critic=Qwen3.6-35B-A3B · 공유 r0에서 최대 10라운드 · "
  "<b>VLM 파서 버그 수정 후</b> 재실행 → axis 크리틱이 정상 파싱(기존 86% '(no parse)' 해소). "
  "이 섹션은 <b>채점하지 않음</b> — 목적은 매 라운드 이미지가 어떻게 바뀌고 그 사이 크리틱이 무엇을 지적했는지를 보는 것. "
  "SELF=외부 크리틱 없음(자기수정) · FUSED=단일 통합 크리틱 · AXES=축별 독립 크리틱→moderator · "
  "MAD=축별+상호반박(토론)→moderator. 이미지 클릭→확대.</div>")
for t in TASKS4:
    tr_any = trace4("MAD", t) or trace4("AXES", t) or trace4("SELF", t)
    instr = clean_instr(tr_any["instruction"]) if tr_any else t
    w(f"<div class='task'><h3>{t}</h3><div class='instr'>{esc(instr)}</div>")
    for a in ARMS4:
        tr = trace4(a, t)
        if not tr: continue
        cl = cands4(a, t)
        hist = {e.get("round"): e for e in tr.get("history", [])}
        # filmstrip — round images only, NO scores
        w(f"<div class='armrow'><div class='an {a}'>{a} — 라운드별 이미지 (점수 없음, {len(cl)}장)</div><div class='film'>")
        for c in cl:
            rid = c.get("id")
            pth = c.get("png") or f"{SC}/s0/{a}/problems/{t}/candidates/{rid}.png"
            u = uri(pth)
            img = (f"<img src='{u}' onclick='LB(this)'>" if u
                   else "<div style='width:96px;height:64px;background:#0c0d10'></div>")
            w(f"<div class='fr'>{img}<div class='rl'>{esc(rid)}</div></div>")
        w("</div>")
        # per-round critic transcript
        w("<details><summary>▸ 라운드별 크리틱 전사 (이 arm이 매 라운드 무엇을 지적했나)</summary>")
        for r in sorted(hist):
            e = hist[r]
            w(f"<div class='deb' style='margin:6px 0;border-top:1px solid #232733;padding-top:5px'><b>round {r}</b>")
            if a == "SELF":
                w(f"<div class='rev mut'>자기수정(외부 크리틱 없음) · action={esc(e.get('action',''))}</div>")
            elif a == "FUSED":
                sg = _real(e.get("suggestion"))
                w(f"<div><span class='ax'>[fused critic]</span> "
                  + (f"<i>→ {esc(sg)}</i>" if sg else BLANK) + "</div>")
            else:  # AXES / MAD
                db = e.get("debate", {}) or {}
                for ax, v in (db.get("critiques") or {}).items():
                    crit = _real(v.get("critique")); sug = _real(v.get("suggestion"))
                    body = (esc(crit) + (f" <i>→ {esc(sug)}</i>" if sug else "")) if crit else BLANK
                    w(f"<div><span class='ax'>[{esc(ax)}]</span> {body}</div>")
                for rb in (db.get("rebuttals") or []):
                    if not isinstance(rb, dict): continue
                    comp = _real(rb.get("compromise")); cf = _real(rb.get("conflicts"))
                    if comp or cf:
                        seg = f"<span class='cf'>⇄ [{esc(rb.get('axis',''))}]</span> "
                        if cf: seg += esc("; ".join(cf)) + " "
                        if comp: seg += f"— {esc(comp)}"
                        w(f"<div>{seg}</div>")
                syn = db.get("synthesis", {}) or {}
                rat = _real(syn.get("rationale")); rev = _real(syn.get("revision"))
                if rat or rev:
                    w(f"<div><span class='mo'>[moderator]</span> "
                      + (esc(rat) + " " if rat else "") + (f"→ {esc(rev)}" if rev else "") + "</div>")
            w("</div>")
        w("</details></div>")
    w("</div>")
w("</div></section>")

w("<div id='lb' onclick=\"this.style.display='none'\"><div class='lbwrap'><img id='lbi'><div id='lbcap'></div></div></div>")
w("<script>"
  "function show(id){for(const s of document.querySelectorAll('section'))s.classList.toggle('on',s.id==id);"
  "document.getElementById('b1').classList.toggle('on',id=='e1');"
  "document.getElementById('b2').classList.toggle('on',id=='e2');"
  "document.getElementById('b3').classList.toggle('on',id=='e3');"
  "document.getElementById('b4').classList.toggle('on',id=='e4');window.scrollTo(0,0);}"
  "function LB(el){var s=el.src||el;var r=(el.getAttribute?el.getAttribute('data-reason'):'')||'';"
  "document.getElementById('lbi').src=s;var c=document.getElementById('lbcap');"
  "c.textContent=r;c.style.display=r?'block':'none';document.getElementById('lb').style.display='flex';}"
  "</script>")

open(OUT,"w").write("<!doctype html><meta charset=utf-8><title>MAD 통합 리포트</title>"+"".join(P))
print(f"wrote {OUT}  ({os.path.getsize(OUT)/1e6:.1f} MB)  images={len(_cache)}")
