"""Layer-B ABSOLUTE judging over the final artifacts of several arms.

Primary evaluation (user decision 2026-07-15): ArtifactsBench-style absolute
scoring — the held-out judge sees ONE artifact (temporal screenshot series) and
scores it 0-10 on each requested axis. Linear cost: one call per (arm, task).
Appends rows to {run_dir}/judge/scores_{judge_name}.jsonl:
  {app, arm, cand_id: "final", axis, score}

Pairwise forced choice (Arena-style) was demoted to optional post-hoc — all
artifacts are preserved, so it can be run later without regeneration if
absolute scores fail to separate the arms (src/eval_b/judge.py:judge_pair).

The judge model MUST be held out (different from the generator and the in-loop
critic VLM) and ABOVE both in capability (PLAN.md ladder: critic 32B = generator
tier < judge VL-72B/Gemini < human). Dual-judge: run once per judge with a
distinct --judge-name.

Offline smoke:
  python run_judge.py --run-dir results/_smoke --mock

Live:
  # open judge (self-hosted VL-72B):
  python run_judge.py --run-dir results/pilot --judge-name qvl72 \
      --judge-ports 8100 --judge-model Qwen/Qwen2.5-VL-72B-Instruct
  # frontier judge (Gemini via OpenAI-compat API; needs $GEMINI_API_KEY):
  python run_judge.py --run-dir results/pilot --judge-name gemini \
      --judge-base-url https://generativelanguage.googleapis.com/v1beta/openai \
      --judge-model gemini-2.5-pro
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os

from src.infra.client import make_client, APIClient, UsageStats
from src.eval_b.judge import judge_scores, JUDGE_AXES
from src.infra.io_utils import atomic_write_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("judge")


def discover_arms(run_dir: str) -> list:
    return sorted(d for d in os.listdir(run_dir)
                  if os.path.isdir(os.path.join(run_dir, d, "problems")))


def final_visual(run_dir: str, arm: str, app: str, mock: bool) -> list | None:
    """Temporal screenshot series [t0, settled, t2] when available, else the
    single settled shot. Judges see dynamic behavior, not one static frame."""
    base = os.path.join(run_dir, arm, "problems", app)
    png = os.path.join(base, "final_t1.png")
    if os.path.exists(png):
        series = [os.path.join(base, "final_t0.png"), png,
                  os.path.join(base, "final_t2.png")]
        return series if all(os.path.exists(p) for p in series) else [png]
    if mock:  # mock judge only hashes the path; html file is a fine stand-in
        html = os.path.join(base, "final.html")
        return [html] if os.path.exists(html) else None
    return None


def candidate_visuals(run_dir: str, arm: str, app: str) -> list:
    """[(cand_id, [pngs])] for every stored candidate (quality-vs-round curve;
    deep-loop ablation). Candidate shots: r{k}_t0.png / r{k}.png / r{k}_t2.png."""
    cdir = os.path.join(run_dir, arm, "problems", app, "candidates")
    out = []
    if not os.path.isdir(cdir):
        return out
    for fn in sorted(os.listdir(cdir)):
        if fn.endswith(".png") and "_t" not in fn:
            cid = fn[:-4]
            settled = os.path.join(cdir, fn)
            series = [os.path.join(cdir, f"{cid}_t0.png"), settled,
                      os.path.join(cdir, f"{cid}_t2.png")]
            out.append((cid, series if all(os.path.exists(p) for p in series)
                        else [settled]))
    return out




async def main_async(a):
    arms = a.arms.split(",") if a.arms else discover_arms(a.run_dir)
    axes = a.axes.split(",")
    for ax in axes:
        assert ax in JUDGE_AXES, f"unknown judge axis {ax}"

    # every (arm, app) with a final visual; the final IS the artifact the
    # method stopped on (consensus-stop regime) — one judgment each.
    work = []
    for arm in arms:
        pdir = os.path.join(a.run_dir, arm, "problems")
        for app in sorted(os.listdir(pdir) if os.path.isdir(pdir) else []):
            pngs = final_visual(a.run_dir, arm, app, a.mock)
            if not pngs:
                continue
            tp = os.path.join(pdir, app, "trace.json")
            instr = (json.load(open(tp)).get("instruction", "")
                     if os.path.exists(tp) else "")
            work.append((arm, app, instr, "final", pngs))
            if a.all_candidates:
                for cid, cpngs in candidate_visuals(a.run_dir, arm, app):
                    work.append((arm, app, instr, cid, cpngs))
    log.info("arms=%s axes=%s artifacts=%d (1 call each)", arms, axes, len(work))

    jdir = os.path.join(a.run_dir, "judge")
    os.makedirs(jdir, exist_ok=True)
    out_path = os.path.join(jdir, f"scores_{a.judge_name}.jsonl")
    if os.path.exists(out_path):  # don't mix scores from a previous judging run
        os.replace(out_path, out_path + ".bak")
    usage = UsageStats()
    if a.judge_base_url:  # frontier API judge (e.g. Gemini OpenAI-compat)
        key = os.environ.get(a.judge_api_key_env, "")
        assert key, f"set ${a.judge_api_key_env} for the API judge"
        judge_c = APIClient(a.judge_base_url, key, a.judge_model, a.concurrency)
    else:
        judge_c = make_client(
            [int(p) for p in str(a.judge_ports).split(",")],
            a.judge_model, a.concurrency, a.mock, "judge")
    sem = asyncio.Semaphore(a.concurrency)
    write_lock = asyncio.Lock()

    async with judge_c as jc:
        async def one(arm, app, instruction, cand_id, pngs):
            async with sem:
                scores = await judge_scores(instruction, pngs, axes, jc, usage)
            rows = [{"app": app, "arm": arm, "cand_id": cand_id,
                     "axis": ax, "score": None if scores is None else scores[ax]}
                    for ax in axes]
            # overall = plain mean of the four judged criteria (computed, not
            # judged — user decision 2026-07-15)
            rows.append({"app": app, "arm": arm, "cand_id": cand_id,
                         "axis": "overall",
                         "score": None if scores is None else
                         round(sum(scores[ax] for ax in axes) / len(axes), 3)})
            async with write_lock:
                with open(out_path, "a") as f:
                    for r in rows:
                        f.write(json.dumps(r) + "\n")
            return scores is not None

        oks = await asyncio.gather(*[one(*w) for w in work])

    n_null = sum(1 for ok in oks if not ok)
    atomic_write_json(os.path.join(jdir, f"judge_meta_{a.judge_name}.json"),
                      {"judge_name": a.judge_name, "mode": "absolute",
                       "arms": arms, "axes": axes, "n_artifacts": len(work),
                       "n_null": n_null, "judge_model": a.judge_model,
                       "mock": a.mock, "usage": usage.to_dict()})
    log.info("DONE: %d artifacts scored (%d null) -> %s",
             len(work), n_null, out_path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True,
                   help="dir containing one subdir per arm (results/<tag>)")
    p.add_argument("--arms", default=None, help="comma list; default: auto-detect")
    p.add_argument("--axes", default="functionality,design,originality,craft",
                   help=f"comma list from {list(JUDGE_AXES)}; 'overall' is "
                        "always appended as their plain mean (computed)")
    p.add_argument("--judge-name", default="qvl72",
                   help="tag for output file (scores_<name>.jsonl); use a "
                        "distinct name per judge for the dual-judge protocol")
    p.add_argument("--judge-ports", default="8100")
    p.add_argument("--judge-model", default="Qwen/Qwen2.5-VL-72B-Instruct")
    p.add_argument("--judge-base-url", default=None,
                   help="OpenAI-compatible API base URL for a frontier judge, "
                        "e.g. https://generativelanguage.googleapis.com/v1beta/openai")
    p.add_argument("--judge-api-key-env", default="GEMINI_API_KEY")
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--all-candidates", action="store_true",
                   help="also score every stored candidate (quality-vs-round "
                        "curves, deep-loop ablation); finals still get "
                        "cand_id='final' rows so collect.py works unchanged")
    p.add_argument("--mock", action="store_true")
    a = p.parse_args()
    asyncio.run(main_async(a))


if __name__ == "__main__":
    main()
