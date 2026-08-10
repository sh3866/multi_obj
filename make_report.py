"""Visual results gallery: per task, every arm's FINAL rendered screenshot side
by side with its judge scores. Self-contained HTML (thumbnails embedded base64)
— open results/<tag>/REPORT.html in any browser.

  python make_report.py results/pilot1 [--judge qvl72] [--thumb-width 460]

Layout per task: instruction header, then one card per arm:
  [screenshot thumbnail]  overall X.X | design X design/orig/craft | checklist NN%
Cards are ordered by overall score (best first). A mean-score table tops the page.
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import os
from collections import defaultdict

ARM_ORDER = ["ZS", "BON", "SELF", "FUSED", "AXES", "MAD", "DISC"]


def load_scores(run_dir, judge):
    """{(app, arm): {axis: score}} for finals + judge name actually used."""
    jdir = os.path.join(run_dir, "judge")
    names = sorted(fn[len("scores_"):-len(".jsonl")]
                   for fn in (os.listdir(jdir) if os.path.isdir(jdir) else [])
                   if fn.startswith("scores_") and fn.endswith(".jsonl"))
    name = judge if judge else (names[0] if names else None)
    out = defaultdict(dict)
    if name:
        for l in open(os.path.join(jdir, f"scores_{name}.jsonl")):
            if not l.strip():
                continue
            r = json.loads(l)
            if r.get("cand_id", "final") == "final" and r.get("score") is not None:
                out[(r["app"], r["arm"])][r["axis"]] = r["score"]
    return out, name


def load_r0_overall(run_dir, judge):
    """{(app, arm): r0 overall} — present when run_judge ran --all-candidates.
    Lets the header table show each arm's improvement over its own start."""
    jdir = os.path.join(run_dir, "judge")
    p = os.path.join(jdir, f"scores_{judge}.jsonl") if judge else None
    out = {}
    if p and os.path.exists(p):
        for l in open(p):
            if not l.strip():
                continue
            r = json.loads(l)
            if (r.get("cand_id") == "r0" and r["axis"] == "overall"
                    and r.get("score") is not None):
                out[(r["app"], r["arm"])] = r["score"]
    return out


def load_mean_tokens(run_dir):
    """{arm: mean tokens/task} from each arm's global_stats.json."""
    out = {}
    for d in sorted(os.listdir(run_dir)):
        p = os.path.join(run_dir, d, "global_stats.json")
        if os.path.exists(p):
            out[d] = json.load(open(p)).get("mean_tokens")
    return out


def load_checklist(run_dir, judge):
    """{(app, arm): fraction} for finals."""
    jdir = os.path.join(run_dir, "judge")
    p = os.path.join(jdir, f"checklist_{judge}.jsonl") if judge else None
    out = {}
    if p and os.path.exists(p):
        for l in open(p):
            if not l.strip():
                continue
            r = json.loads(l)
            if r.get("cand_id") == "final" and r.get("score") is not None:
                out[(r["app"], r["arm"])] = r["score"]
    return out


def thumb_b64(png_path, width):
    """Base64 JPEG thumbnail; falls back to raw PNG bytes if PIL unavailable."""
    try:
        from PIL import Image
        im = Image.open(png_path).convert("RGB")
        h = max(1, round(im.height * width / im.width))
        im = im.resize((width, min(h, width * 3)))  # cap very tall full-page shots
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        try:
            return ("data:image/png;base64," +
                    base64.b64encode(open(png_path, "rb").read()).decode())
        except Exception:
            return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--judge", default=None)
    ap.add_argument("--thumb-width", type=int, default=460)
    ap.add_argument("--exclude-tasks", default="",
                    help="comma list of app ids left out of the gallery "
                         "(same listwise exclusion as collect.py)")
    a = ap.parse_args()

    excl = {t.strip() for t in a.exclude_tasks.split(",") if t.strip()}
    scores, judge = load_scores(a.run_dir, a.judge)
    checks = load_checklist(a.run_dir, judge)
    arms = [d for d in ARM_ORDER
            if os.path.isdir(os.path.join(a.run_dir, d, "problems"))]
    apps = sorted({app for arm in arms
                   for app in os.listdir(os.path.join(a.run_dir, arm, "problems"))}
                  - excl)

    # instructions from any arm's trace
    instr = {}
    for app in apps:
        for arm in arms:
            tp = os.path.join(a.run_dir, arm, "problems", app, "trace.json")
            if os.path.exists(tp):
                t = json.load(open(tp))
                instr[app] = t.get("instruction", "")
                break

    # arm means for the header table (excluded tasks dropped here too —
    # the gallery below already skips them; the two must agree)
    r0s = load_r0_overall(a.run_dir, judge)
    tokens = load_mean_tokens(a.run_dir)
    means, deltas, n_excl = defaultdict(list), defaultdict(list), defaultdict(int)
    for (app, arm), s in scores.items():
        if "overall" in s:
            if app in excl:
                n_excl[arm] += 1
            else:
                means[arm].append(s["overall"])
                if (app, arm) in r0s:
                    deltas[arm].append(s["overall"] - r0s[(app, arm)])
    mean_rows = sorted(((arm, sum(v) / len(v), len(v)) for arm, v in means.items()),
                       key=lambda x: -x[1])

    css = """
    body{font-family:-apple-system,'Segoe UI',sans-serif;margin:0;background:#0f1115;color:#e6e6e6}
    .wrap{max-width:1700px;margin:0 auto;padding:24px}
    h1{font-size:20px} h2{font-size:15px;margin:8px 0}
    table{border-collapse:collapse;margin:12px 0}
    td,th{border:1px solid #333;padding:4px 12px;font-size:13px}
    .task{margin:34px 0;border-top:1px solid #333;padding-top:14px}
    .instr{color:#9aa4b2;font-size:13px;max-width:1200px;white-space:pre-wrap}
    .row{display:flex;gap:14px;overflow-x:auto;padding:12px 0}
    .card{flex:0 0 auto;width:VARWpx;background:#171a21;border:1px solid #2a2f3a;border-radius:8px;padding:8px}
    .card img{width:100%;border-radius:4px;display:block;background:#fff}
    .card .name{font-weight:700;font-size:14px;margin:6px 0 2px}
    .best .name{color:#7ee787}
    .sc{font-size:12px;color:#9aa4b2}
    .big{font-size:16px;color:#e6e6e6;font-weight:700}
    .missing{height:160px;display:flex;align-items:center;justify-content:center;color:#555;border:1px dashed #333;border-radius:4px}
    """.replace("VARW", str(a.thumb_width))

    parts = [f"<style>{css}</style><div class='wrap'>",
             f"<h1>{html.escape(a.run_dir)} — final artifacts & judge scores "
             f"(judge: {html.escape(str(judge))})</h1>",
             "<table><tr><th>arm</th><th>mean overall</th><th>&Delta; vs r0</th>"
             "<th>mean tokens</th><th>tasks</th><th>excluded</th></tr>"]
    for arm, m, n in mean_rows:
        d = deltas.get(arm)
        d_s = f"{sum(d)/len(d):+.2f}" if d else "–"
        t = tokens.get(arm)
        t_s = f"{t/1000:.0f}k" if t else "–"
        parts.append(f"<tr><td>{arm}</td><td>{m:.2f}</td><td>{d_s}</td>"
                     f"<td>{t_s}</td><td>{n}</td>"
                     f"<td>{n_excl.get(arm, 0)}</td></tr>")
    parts.append("</table>")
    if excl:
        parts.append(f"<div class='sc'>excluded tasks (blank final in some arm "
                     f"or unsatisfiable in the offline sandbox): "
                     f"{html.escape(', '.join(sorted(excl)))}</div>")

    for app in apps:
        parts.append(f"<div class='task'><h2>{html.escape(app)}</h2>"
                     f"<div class='instr'>{html.escape(instr.get(app, '')[:600])}</div>"
                     "<div class='row'>")
        cards = []
        for arm in arms:
            s = scores.get((app, arm), {})
            cards.append((-(s.get("overall") or -1), arm, s))
        for i, (_, arm, s) in enumerate(sorted(cards)):
            png = os.path.join(a.run_dir, arm, "problems", app, "final_t1.png")
            img = thumb_b64(png, a.thumb_width) if os.path.exists(png) else None
            body = (f"<img src='{img}' loading='lazy'>" if img
                    else "<div class='missing'>no render</div>")
            ov = s.get("overall")
            axis = " · ".join(f"{k[:4]} {s[k]:.0f}" for k in
                              ("functionality", "design", "originality", "craft") if k in s)
            ck = checks.get((app, arm))
            ck_s = f" · checklist {ck:.0%}" if ck is not None else ""
            parts.append(
                f"<div class='card{' best' if i == 0 and ov is not None else ''}'>"
                f"{body}<div class='name'>{arm}</div>"
                f"<div class='sc'><span class='big'>"
                f"{('overall %.1f' % ov) if ov is not None else 'unscored'}</span>"
                f"{(' — ' + axis) if axis else ''}{ck_s}</div></div>")
        parts.append("</div></div>")
    parts.append("</div>")

    out = os.path.join(a.run_dir, "REPORT.html")
    with open(out, "w") as f:
        f.write("<!doctype html><meta charset='utf-8'>"
                f"<title>{html.escape(os.path.basename(a.run_dir))} report</title>"
                + "".join(parts))
    print(f"wrote {out} ({os.path.getsize(out)//1024} KB, "
          f"{len(apps)} tasks x {len(arms)} arms)")


if __name__ == "__main__":
    main()
