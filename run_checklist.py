"""Layer-B checklist scoring (ArtifactsBench protocol) over a run's artifacts.

Scores the FINAL artifact of every arm x task by default; --all-candidates also
scores every intermediate candidate (for quality-vs-token / leniency curves).
Writes {run_dir}/judge/checklist_{judge_name}.jsonl:
  {app, arm, cand_id, n_items, n_passed, score}

Same held-out judge rules as run_judge.py. Offline smoke:
  python run_checklist.py --run-dir results/_smoke --mock
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os

from src.infra.client import make_client, APIClient, UsageStats
from src.eval_b.checklist import judge_checklist
from src.infra.io_utils import atomic_write_json, read_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("checklist")


def discover_arms(run_dir):
    return sorted(d for d in os.listdir(run_dir)
                  if os.path.isdir(os.path.join(run_dir, d, "problems")))


def final_images(base: str, mock: bool):
    seq = [os.path.join(base, n) for n in ("final_t0.png", "final.png", "final_t2.png")]
    seq = [p for p in seq if os.path.exists(p)]
    if seq:
        return seq
    if mock:
        h = os.path.join(base, "final.html")
        return [h] if os.path.exists(h) else []
    return []


def candidate_images(base: str, cand: dict, mock: bool):
    pngs = [p for p in (cand.get("pngs") or []) if p and os.path.exists(p)]
    if pngs:
        return pngs
    if cand.get("png") and os.path.exists(cand["png"]):
        return [cand["png"]]
    if mock and cand.get("html_path") and os.path.exists(cand["html_path"]):
        return [cand["html_path"]]
    return []


async def main_async(a):
    arms = a.arms.split(",") if a.arms else discover_arms(a.run_dir)
    jdir = os.path.join(a.run_dir, "judge")
    os.makedirs(jdir, exist_ok=True)
    out_path = os.path.join(jdir, f"checklist_{a.judge_name}.jsonl")
    if os.path.exists(out_path):
        os.replace(out_path, out_path + ".bak")

    # work items
    jobs_spec = []
    for arm in arms:
        pdir = os.path.join(a.run_dir, arm, "problems")
        for app in sorted(os.listdir(pdir) if os.path.isdir(pdir) else []):
            base = os.path.join(pdir, app)
            tp = os.path.join(base, "trace.json")
            if not os.path.exists(tp):
                continue
            tr = read_json(tp)
            items = tr.get("checklist") or []
            if not items:
                continue
            instr = tr.get("instruction", "")
            imgs = final_images(base, a.mock)
            if imgs:
                jobs_spec.append((app, arm, "final", instr, items, imgs))
            if a.all_candidates:
                cj = os.path.join(base, "candidates.json")
                if os.path.exists(cj):
                    for c in read_json(cj):
                        ci = candidate_images(base, c, a.mock)
                        if ci and c.get("id") != tr.get("final_id"):
                            jobs_spec.append((app, arm, c["id"], instr, items, ci))
    log.info("arms=%s -> %d checklist judgments", arms, len(jobs_spec))

    usage = UsageStats()
    if a.judge_base_url:
        key = os.environ.get(a.judge_api_key_env, "")
        assert key, f"set ${a.judge_api_key_env} for the API judge"
        judge_c = APIClient(a.judge_base_url, key, a.judge_model, a.concurrency)
    else:
        judge_c = make_client([int(p) for p in str(a.judge_ports).split(",")],
                              a.judge_model, a.concurrency, a.mock, "judge")
    sem = asyncio.Semaphore(a.concurrency)
    lock = asyncio.Lock()

    async with judge_c as jc:
        async def one(app, arm, cid, instr, items, imgs):
            async with sem:
                passed = await judge_checklist(instr, items, imgs, jc, usage)
            row = {"app": app, "arm": arm, "cand_id": cid, "n_items": len(items),
                   "n_passed": sum(passed) if passed else None,
                   "score": (sum(passed) / len(items)) if passed else None}
            async with lock:
                with open(out_path, "a") as f:
                    f.write(json.dumps(row) + "\n")
            return row

        rows = await asyncio.gather(*[one(*spec) for spec in jobs_spec])

    n_null = sum(1 for r in rows if r["score"] is None)
    atomic_write_json(os.path.join(jdir, f"checklist_meta_{a.judge_name}.json"),
                      {"judge_name": a.judge_name, "arms": arms,
                       "n_judgments": len(rows), "n_null": n_null,
                       "all_candidates": a.all_candidates,
                       "judge_model": a.judge_model, "mock": a.mock,
                       "usage": usage.to_dict()})
    log.info("DONE: %d judgments (%d null) -> %s", len(rows), n_null, out_path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--arms", default=None)
    p.add_argument("--all-candidates", action="store_true",
                   help="also score intermediate candidates (curves)")
    p.add_argument("--judge-name", default="qvl72")
    p.add_argument("--judge-ports", default="8100")
    p.add_argument("--judge-model", default="Qwen/Qwen2.5-VL-72B-Instruct")
    p.add_argument("--judge-base-url", default=None)
    p.add_argument("--judge-api-key-env", default="GEMINI_API_KEY")
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--mock", action="store_true")
    a = p.parse_args()
    asyncio.run(main_async(a))


if __name__ == "__main__":
    main()
