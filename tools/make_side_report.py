"""Standalone HTML report for the SIDE 'design-first' experiment (results/sideproj).

Single-page design-focused briefs, shared r0, 10 rounds fixed (no early stop),
NO-SCORE critics (subjective design is not scalarized). Arms:
  SELF (vision self-refine) + FUSED/AXES/MAD x design2/4/10.
Per task: shared r0 + all arm finals at a glance, then each arm-config's
round-by-round image evolution and (for FUSED/AXES/MAD) the round-by-round
critic transcript — axis critiques -> suggestions, MAD cross-critique rebuttals,
moderator synthesis. This section carries NO judge scores (qualitative only):
the point is how the image evolves and how the critics are composed as the
design axis granularity goes 2 -> 4 -> 10.
Images base64-inlined, downscaled to keep the file usable."""
import json, os, base64, html, io
from PIL import Image

SD = "results/sideproj"
REP = f"{SD}/report"
TASKS = [f"ab{i:06d}" for i in range(1, 13)]
OUT = f"{SD}/side_report.html"

_cache = {}
def uri(path, maxw=320):
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
def esc(s): return html.escape(str(s))
def clean_instr(s):
    for b in ["You are a code expert. ", "You are a code expert, ", "You are a coding expert. ",
              "Please use your professional knowledge to generate accurate and professional responses. ",
              "Make sure the generated code is executable for demonstration. ",
              "Make sure the code you generate is executable for demonstration purposes. "]:
        s = s.replace(b, "")
    return s.strip()
def _real(x):
    """Drop template placeholders ('<...>') and literal ellipsis/empty punts."""
    if x is None: return None
    if isinstance(x, list):
        x = [s for s in x if _real(s)]
        return x or None
    s = str(x).strip()
    if not s or (s.startswith("<") and s.endswith(">")): return None
    if not s.strip(".…-—· "): return None
    return s
def _sug(x):
    if isinstance(x, list): x = " · ".join(str(s) for s in x)
    return _real(x)
BLANK = "<span class='mut' style='font-style:italic'>(크리틱 모델이 이 축을 비워둠 — 리포트 생략 아님)</span>"

def strace(cfg, t):
    p = f"{SD}/s0/{cfg}/problems/{t}/trace.json"
    return json.load(open(p)) if os.path.exists(p) else None
def scands(cfg, t):
    p = f"{SD}/s0/{cfg}/problems/{t}/candidates.json"
    return json.load(open(p)) if os.path.exists(p) else []

AXCOMP = {"design2": "structure · aesthetic",
          "design4": "layout · spacing · color_type · style_orig",
          "design10": "hierarchy · composition · spacing · alignment · color · typography · imagery · mood · originality · finish"}
GR = ["design2", "design4", "design10"]
FAMS = ["FUSED", "AXES", "MAD"]
SIDE_TASKS = [t for t in TASKS if os.path.isdir(f"{SD}/s0/MAD_design4/problems/{t}")]

# blind Fable design scores (single overall 0-10, un-mapped) + means
SSC = json.load(open(f"{REP}/scores_side.json")) if os.path.exists(f"{REP}/scores_side.json") else {}
MEANS = json.load(open(f"{REP}/means_side.json")) if os.path.exists(f"{REP}/means_side.json") else {}
def sc_of(t, cfg): return (SSC.get(t, {}) or {}).get(cfg)
def col(o):
    if o is None: return "#444"
    return "#2e7d46" if o >= 7 else "#5c8a3a" if o >= 5.5 else "#8a7a2a" if o >= 4 else "#9a5a2a" if o >= 2.5 else "#9a3a3a"

P = []
def w(s): P.append(s)

w("""<style>
:root{color-scheme:dark}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#12141a;color:#e6e8ee;margin:0;padding:0 0 60px}
header{position:sticky;top:0;z-index:20;background:#0e1016;border-bottom:1px solid #262a34;padding:14px 30px}
h1{font-size:19px;margin:0 0 6px}
.wrap{padding:22px 30px;max-width:1400px}
h2.sec{font-size:16px;margin:4px 0 2px} .desc{color:#8a90a0;font-size:12.5px;margin:0 0 16px;line-height:1.55}
table.t{border-collapse:collapse;margin:6px 0 20px;font-size:13px}
table.t td,table.t th{padding:6px 12px;border-bottom:1px solid #2a2e38;text-align:left}
table.t th{color:#9aa0b0;font-weight:600}
.mut{color:#8a90a0;font-size:12px}
.task{border:1px solid #262a34;border-radius:10px;margin:0 0 20px;padding:13px 15px;background:#181b22}
.task h3{font-size:14px;margin:0 0 2px}
.instr{color:#9aa0b0;font-size:12px;margin:0 0 10px;line-height:1.5;white-space:pre-wrap;background:#12141a;border:1px solid #232733;border-radius:6px;padding:8px 10px;max-height:220px;overflow:auto}
details{margin-top:6px} summary{cursor:pointer;color:#9aa0b0;font-size:12px}
.rev{white-space:pre-wrap;font-size:11px;line-height:1.45;color:#c2c8d8;margin:0;font-family:inherit}
.deb{font-size:11px;line-height:1.5;color:#c2c8d8}
.deb .ax{color:#9ec7ff;font-weight:700} .deb .cf{color:#c98a6a} .deb .mo{color:#ffd479;font-weight:700}
.film{display:flex;gap:6px;flex-wrap:wrap;align-items:flex-end;margin-top:6px}
.fr{width:150px} .fr img{width:150px;height:100px;object-fit:cover;object-position:top;cursor:zoom-in;border:1px solid #2a2e38;border-radius:4px;display:block}
.fr.big{width:150px} .fr.big img{width:150px;height:100px}
.fr .rl{font-size:10px;color:#8a90a0;text-align:center;margin-top:1px}
.armrow{margin:8px 0;padding:7px 9px;background:#14161c;border:1px solid #232733;border-radius:7px}
.armrow .an{font-size:12px;font-weight:700;margin-bottom:2px}
.an.SELF{color:#9ec7ff} .an.FUSED{color:#b0d0a0} .an.AXES{color:#e0b0e0} .an.MAD{color:#ffd479}
.glance{margin:2px 0 6px;padding:8px 9px;background:#101319;border:1px solid #232733;border-radius:7px}
.glance .t{font-size:11.5px;color:#9aa0b0;margin-bottom:2px}
.sc{font-size:11px;font-weight:800;text-align:center;margin-top:1px}
table.sum{border-collapse:collapse;margin:6px 0 14px;font-size:12.5px}
table.sum td,table.sum th{padding:5px 12px;border-bottom:1px solid #2a2e38;text-align:center;white-space:nowrap}
table.sum th{color:#9aa0b0;font-weight:600} table.sum td.lab{text-align:left;font-weight:700}
.pill{display:inline-block;min-width:38px;padding:2px 7px;border-radius:6px;color:#fff;font-weight:800}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.95);display:none;flex-direction:column;align-items:center;justify-content:center;gap:14px;z-index:99;cursor:zoom-out;padding:24px}
#lb img{height:84vh;width:auto;max-width:97vw;object-fit:contain;box-shadow:0 8px 50px #000;border-radius:6px;image-rendering:auto}
#lbcap{color:#e6e8ee;font-size:14px;line-height:1.55;max-width:1000px;text-align:center;background:#181b22;border:1px solid #2a2e38;padding:12px 18px;border-radius:8px;cursor:default}
#lbcap b{color:#ffd479}
nav button{background:#1e222b;color:#c6ccdc;border:1px solid #2a2e38;border-radius:8px;padding:8px 14px;margin-right:8px;font-size:13px;cursor:pointer}
nav button.on{background:#2b4a7a;border-color:#3a6ab0;color:#fff;font-weight:700}
section{display:none} section.on{display:block}
</style>""")

w("<header><h1>사이드 실험 — 디자인 전용</h1>"
  "<nav style='margin-top:8px'>"
  "<button id='b1' class='on' onclick=\"show('p1')\">① 축 granularity (design2/4/10)</button>"
  "<button id='b2' onclick=\"show('p2')\">② 오라클 골드 크리틱 (상한 실험)</button>"
  "</nav></header>")

w("<section id='p1' class='on'><div class='wrap'>")
w("<div class='mut' style='margin-bottom:14px'>results/sideproj · gen=critic=Qwen3.6-35B-A3B · 크리틱 무점수 · 10라운드 고정 · 정성 비교</div>")
w("<div class='desc'><b>단일 페이지 디자인 집중 브리프</b>로 재작성 · 공유 r0에서 <b>10라운드 고정(no early stop)</b> · "
  "<b>크리틱은 점수 없음</b>(주관적 디자인은 점수화 대상이 아니라는 전제) — 오직 비평·개선지시만, generator가 코드 재생성. "
  "SELF=자기 렌더를 보고 스스로 수정(외부 크리틱 없음, vision) · FUSED=단일 통합 크리틱 · AXES=축별 독립 크리틱→moderator · "
  "MAD=축별+상호반박(토론)→moderator. 각 arm을 <b>디자인 축 granularity 2/4/10</b>로 실행 → 축을 잘게 쪼갤수록 "
  "크리틱 구성·수정 방향이 어떻게 달라지는지 비교. 채점 없음 — 이미지 진화 + 크리틱 구성 정성 비교. 이미지 클릭→확대.</div>")
w("<table class='t'><tr><th>granularity</th><th>축 구성</th></tr>"
  + "".join(f"<tr><td class='an MAD'>{g}</td><td class='mut'>{esc(AXCOMP[g])}</td></tr>" for g in GR)
  + "</table>")

# ---- blind Fable design-score summary ----
if MEANS:
    w("<h2 class='sec' style='margin-top:18px'>최종 산출물 블라인드 디자인 채점 (Fable, 단일 점수 0–10)</h2>")
    w("<div class='desc'>판정자=세계 최고 수준 디자인 디렉터 페르소나. <b>최종 산출물만</b> 익명·순서셔플로 놓고 "
      "'디자인적으로 얼마나 아름답고 완성도 있는가'를 <b>축 평균이 아닌 단일 총체 점수</b>로 판정(시각 위계·레이아웃·여백·정렬·색·타이포·이미지·무드·독창성·완성도 종합). "
      "각 최종 이미지 아래 점수, 클릭하면 확대+판정 근거. 아래는 arm-config별 12태스크 평균.</div>")
    order = sorted([v for v in MEANS if MEANS[v] is not None], key=lambda v: -MEANS[v])
    w("<table class='sum'><tr><th>순위</th><th>arm-config</th><th>평균</th></tr>")
    for i, v in enumerate(order, 1):
        o = MEANS[v]; lab = "r0 (공유 초안)" if v == "r0" else v
        w(f"<tr><td>{i}</td><td class='lab'>{esc(lab)}</td><td><span class='pill' style='background:{col(o)}'>{o:.2f}</span></td></tr>")
    w("</table>")
    # family x granularity matrix
    w("<b class='mut'>계열 × granularity (평균)</b>")
    w("<table class='sum'><tr><th></th><th>design2</th><th>design4</th><th>design10</th></tr>")
    for fam in FAMS:
        cells = "".join(f"<td><span class='pill' style='background:{col(MEANS.get(fam+'_'+g))}'>{MEANS.get(fam+'_'+g):.2f}</span></td>" for g in GR)
        w(f"<tr><td class='lab an {fam}'>{fam}</td>{cells}</tr>")
    w(f"<tr><td class='lab an SELF'>SELF</td><td><span class='pill' style='background:{col(MEANS.get('SELF_design4'))}'>{MEANS.get('SELF_design4'):.2f}</span></td><td class='mut'>—</td><td class='mut'>—</td></tr>")
    w(f"<tr><td class='lab'>r0</td><td colspan='3'><span class='pill' style='background:{col(MEANS.get('r0'))}'>{MEANS.get('r0'):.2f}</span> <span class='mut'>공유 초안 (모든 arm의 출발점)</span></td></tr>")
    w("</table>")
    w("<div class='desc' style='color:#c98a6a'><b>정직한 관찰:</b> 모든 arm이 5.8–6.4에 밀집하고 <b>공유 초안 r0(5.96)이 중간</b>에 위치한다. "
      "즉 같은 체급 크리틱으로 10라운드 리파인해도 이 블라인드 디자인 채점에서 r0를 뚜렷이 넘지 못했고, 일부(SELF·MAD_design4=5.79)는 오히려 r0보다 낮다. "
      "granularity를 늘린 쪽(FUSED_design10 6.42·MAD_design10 6.25)이 소폭 앞서지만 차이는 노이즈 수준. "
      "이는 '주관적 디자인 품질을 같은 모델 크리틱으로 개선하기는 어렵다'는 (예상 가능한) 혼재/거의-null 결과로 읽는 게 맞다.</div>")

for t in SIDE_TASKS:
    tr0 = strace("MAD_design4", t)
    instr = clean_instr(tr0["instruction"]) if tr0 else t
    r0png = f"{SD}/s0/MAD_design4/problems/{t}/candidates/r0.png"
    w(f"<div class='task'><h3>{t}</h3><div class='instr'>{esc(instr)}</div>")
    # at-a-glance: shared r0 + all finals, with blind design score + reason
    def final_card(cfg, lab, path):
        if not os.path.exists(path): return
        d = sc_of(t, cfg) or {}
        o = d.get("score"); reason = esc(d.get("reason", ""))
        cap = (f"<b>{lab} · {o:.1f}/10</b> — {reason}" if o is not None else esc(lab))
        scline = (f"<div class='sc' style='color:{col(o)}'>{o:.1f}</div>" if o is not None else "")
        w(f"<div class='fr big'><img src='{uri(path,1100)}' data-cap=\"{cap}\" onclick='LB(this)'>"
          f"<div class='rl'>{esc(lab)}</div>{scline}</div>")
    w("<div class='glance'><div class='t'>한눈에 보기 — r0(공유) + 각 arm 최종 · 클릭→확대+판정근거</div><div class='film'>")
    final_card("r0", "r0 (공유)", r0png)
    for cfg, lab in [("SELF_design4", "SELF")] + [(f"{fam}_{g}", f"{fam[:1]}·{g[6:]}") for fam in FAMS for g in GR]:
        final_card(cfg, lab, f"{SD}/s0/{cfg}/problems/{t}/final_t1.png")
    w("</div></div>")

    def strip_and_transcript(cfg, title, kind):
        cl = scands(cfg, t); tr = strace(cfg, t)
        if not tr: return
        hist = {e.get("round"): e for e in tr.get("history", [])}
        w(f"<div class='armrow'><div class='an {kind}'>{esc(title)}</div><div class='film'>")
        for c in cl:
            rid = c.get("id"); pth = c.get("png") or f"{SD}/s0/{cfg}/problems/{t}/candidates/{rid}.png"
            u = uri(pth, 720)
            cap = esc(f"{title} · {rid}")
            img = (f"<img src='{u}' data-cap=\"{cap}\" onclick='LB(this)'>" if u else "<div style='width:96px;height:64px;background:#0c0d10'></div>")
            w(f"<div class='fr'>{img}<div class='rl'>{esc(rid)}</div></div>")
        w("</div>")
        if kind == "SELF":
            w("<div class='rev mut' style='margin-top:4px'>vision self-refine — 자기 렌더를 보고 스스로 수정, 외부 크리틱 없음</div>")
        else:
            w("<details><summary>▸ 라운드별 크리틱 전사 (점수 없음)</summary>")
            if kind == "FUSED" and not any(_real((hist.get(r) or {}).get("critique")) for r in hist):
                w("<div class='rev mut' style='margin:2px 0 4px'>※ 이 실행의 FUSED 로그는 요약 제안(≤160자)만 저장됨 — "
                  "arms.py 수정 후 재실행 시 AXES/MAD처럼 전체 비평이 표시됩니다.</div>")
            for r in sorted(hist):
                e = hist[r]
                w(f"<div class='deb' style='margin:6px 0;border-top:1px solid #232733;padding-top:5px'><b>round {r}</b>")
                if kind == "FUSED":
                    cr = _real(e.get("critique")); sg = _sug(e.get("suggestion"))
                    if cr:
                        w(f"<div><span class='ax'>[fused critic]</span> {esc(cr)}" + (f" <i>→ {esc(sg)}</i>" if sg else "") + "</div>")
                    else:
                        w(f"<div><span class='ax'>[fused critic]</span> " + (f"<i>→ {esc(sg)}</i>" if sg else BLANK) + "</div>")
                else:
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
                        w(f"<div><span class='mo'>[moderator]</span> " + (esc(rat) + " " if rat else "") + (f"→ {esc(rev)}" if rev else "") + "</div>")
                w("</div>")
            w("</details>")
        w("</div>")

    strip_and_transcript("SELF_design4", "SELF · design4 (vision 자기수정)", "SELF")
    for fam in FAMS:
        for g in GR:
            strip_and_transcript(f"{fam}_{g}", f"{fam} · {g}  ({AXCOMP[g]})", fam)
    w("</div>")
w("</div></section>")

# ============================================================ PAGE 2 — ORACLE
OR = "results/oracle"
ORAX = ["layout", "spacing", "color_type", "style_orig"]
ORND = ["r0", "r1", "r2", "r3"]
AXLAB = {"layout": "Layout & Hierarchy", "spacing": "Spacing, Alignment & Balance",
         "color_type": "Color & Typography", "style_orig": "Style, Originality & Finish"}
try:
    ORS = json.load(open(f"{OR}/report/scores_final.json"))
except Exception:
    ORS = {}
ORTASKS = sorted(ORS)

def omean(vals): return sum(vals) / len(vals) if vals else 0.0
def rmean(t, r): return omean([ORS[t][r][a]["score"] for a in ORAX if a in ORS[t].get(r, {})])
def ocol(s):
    return ("#2e7d46" if s >= 7 else "#5c8a3a" if s >= 6 else "#8a7a2a" if s >= 5
            else "#9a5a2a" if s >= 4 else "#9a3a3a")

w("<section id='p2'><div class='wrap'>")
w("<div class='mut' style='margin-bottom:14px'>results/oracle · generator=Haiku 4.5 · "
  "critic=Opus (판정 루브릭 정렬) · judge=Opus 축별 전문가, 블라인드·무기억</div>")
w("<div class='desc'><b>질문:</b> 판정자와 <b>완전히 정렬된 최고 품질 크리틱</b>(오라클)을 주면 점수가 실제로 오르는가, "
  "어디까지 오르는가? 이건 실용적 방법 비교가 아니라 <b>상한선(skyline) 측정</b>입니다 — 정답을 그냥 알려줬을 때의 천장.<br><br>"
  "<b>설계:</b> Haiku가 r0 생성 → 매 라운드 Opus 오라클 크리틱(진단 + <i>이 브리프의 10/10은 이런 모습</i> + 지시, "
  "<b>점수는 안 매김</b>) → Haiku 재생성 → 총 3라운드. 크리틱은 매 라운드 <b>새 컨텍스트</b>(무기억, 현재 화면만 봄).<br>"
  "<b>편향 차단:</b> 루프 중에는 채점하지 않고, 끝난 뒤 r0~r3를 <b>익명·셔플</b>해 이미지 1장씩 "
  "<b>독립 서브에이전트</b>가 자기 축만 채점(라운드·arm 정보 없음). 판정자는 크리틱을 볼 수 없음. "
  "총 <b>96개 판정</b>(6태스크 × 4라운드 × 4축).</div>")

# --- 표 1: 태스크별 궤적
w("<b>표 1 — 태스크별 라운드 궤적 (4축 평균)</b>")
w("<table class='t'><tr><th>task</th>" + "".join(f"<th>{r}</th>" for r in ORND)
  + "<th>Δ(r3−r0)</th><th>best</th></tr>")
tot = {r: [] for r in ORND}
for t in ORTASKS:
    ms = [rmean(t, r) for r in ORND]
    for r, m in zip(ORND, ms): tot[r].append(m)
    bi = max(range(4), key=lambda i: ms[i])
    d = ms[3] - ms[0]
    w(f"<tr><td>{t}</td>"
      + "".join(f"<td style='color:{ocol(m)};font-weight:{700 if i==bi else 400}'>{m:.2f}</td>"
                for i, m in enumerate(ms))
      + f"<td style='color:{'#7ec97e' if d>0 else '#c97e7e'}'>{d:+.2f}</td>"
      + f"<td class='mut'>{ORND[bi]}</td></tr>")
ov = [omean(tot[r]) for r in ORND]
bi = max(range(4), key=lambda i: ov[i])
w("<tr style='border-top:2px solid #3a3f4c'><td><b>전체평균</b></td>"
  + "".join(f"<td style='color:{ocol(m)};font-weight:{700 if i==bi else 400}'><b>{m:.2f}</b></td>"
            for i, m in enumerate(ov))
  + f"<td><b>{ov[3]-ov[0]:+.2f}</b></td><td class='mut'>{ORND[bi]}</td></tr></table>")

# --- 표 2: 축별
w("<b>표 2 — 축별 라운드 평균 (6 태스크)</b>")
w("<table class='t'><tr><th>axis</th>" + "".join(f"<th>{r}</th>" for r in ORND) + "<th>Δ</th></tr>")
for a in ORAX:
    v = [omean([ORS[t][r][a]["score"] for t in ORTASKS]) for r in ORND]
    d = v[3] - v[0]
    w(f"<tr><td>{esc(AXLAB[a])}</td>"
      + "".join(f"<td style='color:{ocol(x)}'>{x:.2f}</td>" for x in v)
      + f"<td style='color:{'#7ec97e' if d>0 else '#c97e7e'}'><b>{d:+.2f}</b></td></tr>")
w("</table>")

w("<div class='desc' style='border-left:3px solid #c9a22a;padding-left:10px'>"
  "<b>결과:</b> 1라운드는 확실히 오릅니다(<b>+0.77</b>, 6개 중 5개 개선). 그러나 2·3라운드에서 다시 내려가 "
  "<b>6개 중 4개가 r1에서 최고점</b>이고 최종 순증은 <b>+0.11(사실상 0)</b>. 천장은 6.2~7.3이었고 9~10 근처엔 못 갔습니다.<br>"
  "무너지는 주범은 <b>spacing(−1.32)</b> — 크리틱이 요구한 요소를 계속 더하다 화면이 붐비고 결국 깨집니다"
  "(ab000001 r3: 보드 잘림·푸터 소멸로 layout 2.0). 96셀 중 <b>18개(19%)</b>가 4점 미만.<br><br>"
  "<b>해석:</b> 판정 기준을 완벽히 정렬한 오라클 크리틱으로도 만점 근처는 불가능했고, 한 번 오른 뒤 정체·붕괴합니다. "
  "즉 병목은 <b>크리틱 품질이 아니라</b> 긴 지시를 누적 반영하며 레이아웃을 깨뜨리는 <b>생성기의 실행력</b>과, "
  "축 간 트레이드오프를 해소하지 못하는 <b>반복 구조</b>입니다. "
  "<span class='mut'>(주의: 크리틱=판정자가 같은 기준을 공유하므로 상승분에는 Goodhart 성분이 있습니다. "
  "기억 편향은 차단했지만 기준 정렬은 설계상 의도된 것입니다.)</span></div>")

# --- 태스크별 이미지 궤적 + 판정 근거
for t in ORTASKS:
    bp = f"{OR}/run/{t}/brief.txt"
    instr = clean_instr(open(bp).read()) if os.path.exists(bp) else t
    w(f"<div class='task'><h3>{t}</h3><div class='instr'>{esc(instr)}</div>")
    ms = [rmean(t, r) for r in ORND]
    w("<div class='glance'><div class='t'>라운드 궤적 — 클릭하면 확대 + 축별 판정 근거</div><div class='film'>")
    for r, m in zip(ORND, ms):
        p = f"{OR}/run/{t}/{r}.png"
        parts = []
        for a in ORAX:
            d = ORS[t][r].get(a, {})
            parts.append(f"<b>{esc(AXLAB[a])} · {d.get('score','—')}/10</b> — {esc(d.get('reason',''))}")
        cap = esc(f"{t} · {r} · 평균 {m:.2f}") + "<br><br>" + "<br><br>".join(parts)
        cap = cap.replace('"', "&quot;")
        w(f"<div class='fr big'><img src='{uri(p,1100)}' data-cap=\"{cap}\" onclick='LB(this)'>"
          f"<div class='rl' style='color:{ocol(m)}'><b>{r}</b> · {m:.2f}</div></div>")
    w("</div></div>")
    # 축별 점수 표
    w("<table class='t' style='margin:8px 0 4px'><tr><th>axis</th>"
      + "".join(f"<th>{r}</th>" for r in ORND) + "</tr>")
    for a in ORAX:
        w(f"<tr><td class='mut'>{esc(AXLAB[a])}</td>"
          + "".join(f"<td style='color:{ocol(ORS[t][r][a]['score'])}'>{ORS[t][r][a]['score']:.1f}</td>"
                    for r in ORND) + "</tr>")
    w("</table>")
    # 골드 크리틱 전문
    w("<details><summary>▸ 오라클 골드 크리틱 전문 (라운드별)</summary>")
    for r in ORND[:3]:
        cf = f"{OR}/run/{t}/critique_{r}.md"
        if os.path.exists(cf):
            w(f"<div class='armrow'><div class='an MAD'>{r} 화면에 대한 골드 크리틱 → {ORND[ORND.index(r)+1]} 생성에 투입</div>"
              f"<pre style='white-space:pre-wrap;font-size:10.5px;line-height:1.5;color:#c2c8d8;"
              f"max-height:420px;overflow:auto;margin:6px 0 0'>{esc(open(cf).read())}</pre></div>")
    w("</details></div>")
w("</div></section>")

w("<div id='lb' onclick=\"this.style.display='none'\"><img id='lbi'><div id='lbcap' onclick='event.stopPropagation()'></div></div>")
w("<script>function LB(el){document.getElementById('lbi').src=el.src;"
  "var c=document.getElementById('lbcap');var cap=el.getAttribute('data-cap')||'';"
  "c.innerHTML=cap;c.style.display=cap?'block':'none';"
  "document.getElementById('lb').style.display='flex';}"
  "function show(id){for(const s of document.querySelectorAll('section'))s.classList.toggle('on',s.id==id);"
  "document.getElementById('b1').classList.toggle('on',id=='p1');"
  "document.getElementById('b2').classList.toggle('on',id=='p2');window.scrollTo(0,0);}</script>")

open(OUT, "w").write("<!doctype html><meta charset=utf-8><title>사이드 실험 — 디자인 전용</title>" + "".join(P))
print(f"wrote {OUT}  ({os.path.getsize(OUT)/1e6:.1f} MB)  images={len(_cache)}")
