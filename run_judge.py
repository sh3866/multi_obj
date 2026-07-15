"""Layer-B pairwise judging over the final artifacts of several arms.

For every task present in ALL arms, every unordered arm pair is judged in BOTH
presentation orders (position-bias control) on each requested axis.
Appends rows to {run_dir}/judge/results.jsonl:
  {app, axis, arm_a, arm_b, order, winner_pos, winner_arm}

The judge model MUST be held out (different from the generator and the in-loop
critic VLM) and ABOVE both in capability (PLAN.md ladder: critic 32B = generator
tier < judge VL-72B/Gemini < human). Dual-judge protocol per ArtifactsBench.

Offline smoke:
  python run_judge.py --run-dir results/_smoke --mock

Live (dual-judge protocol, ArtifactsBench-style):
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
import itertools
import json
import logging
import os

from src.infra.client import make_client, APIClient, UsageStats
from src.eval_b.judge import judge_pair, JUDGE_AXES
from src.infra.io_utils import atomic_write_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("judge")


def discover_arms(run_dir: str) -> list:
    return sorted(d for d in os.listdir(run_dir)
                  if os.path.isdir(os.path.join(run_dir, d, "problems")))


def final_visual(run_dir: str, arm: str, app: str, mock: bool) -> str | None:
    base = os.path.join(run_dir, arm, "problems", app)
    png = os.path.join(base, "final.png")
    if os.path.exists(png):
        return png
    if mock:  # mock judge only hashes the path; html file is a fine stand-in
        html = os.path.join(base, "final.html")
        return html if os.path.exists(html) else None
    return None


async def main_async(a):
    arms = a.arms.split(",") if a.arms else discover_arms(a.run_dir)
    axes = a.axes.split(",")
    for ax in axes:
        assert ax in JUDGE_AXES, f"unknown judge axis {ax}"
    # tasks with a final visual in every arm
    apps = None
    for arm in arms:
        pdir = os.path.join(a.run_dir, arm, "problems")
        have = {app for app in (os.listdir(pdir) if os.path.isdir(pdir) else [])
                if final_visual(a.run_dir, arm, app, a.mock)}
        apps = have if apps is None else (apps & have)
    apps = sorted(apps or [])
    # instructions from traces (task-source agnostic)
    items = {}
    for app in apps:
        for arm in arms:
            tp = os.path.join(a.run_dir, arm, "problems", app, "trace.json")
            if os.path.exists(tp):
                items[app] = {"instruction": json.load(open(tp)).get("instruction", "")}
                break
    log.info("arms=%s axes=%s tasks=%d pairs/task=%d x2 orders",
             arms, axes, len(apps), len(list(itertools.combinations(arms, 2))))

    jdir = os.path.join(a.run_dir, "judge")
    os.makedirs(jdir, exist_ok=True)
    out_path = os.path.join(jdir, f"results_{a.judge_name}.jsonl")
    if os.path.exists(out_path):  # don't mix votes from a previous judging run
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
        async def one(app, arm_x, arm_y, axis, order):
            # order 0: x shown as A; order 1: y shown as A
            first, second = (arm_x, arm_y) if order == 0 else (arm_y, arm_x)
            pa = final_visual(a.run_dir, first, app, a.mock)
            pb = final_visual(a.run_dir, second, app, a.mock)
            instruction = items.get(app, {}).get("instruction", "")
            async with sem:
                w = await judge_pair(instruction, pa, pb, axis, jc, usage)
            winner_arm = None if w is None else (first if w == "A" else second)
            row = {"app": app, "axis": axis, "arm_a": arm_x, "arm_b": arm_y,
                   "order": order, "winner_pos": w, "winner_arm": winner_arm}
            async with write_lock:
                with open(out_path, "a") as f:
                    f.write(json.dumps(row) + "\n")
            return row

        jobs = [one(app, x, y, axis, order)
                for app in apps
                for (x, y) in itertools.combinations(arms, 2)
                for axis in axes
                for order in (0, 1)]
        rows = await asyncio.gather(*jobs)

    n_null = sum(1 for r in rows if r["winner_pos"] is None)
    atomic_write_json(os.path.join(jdir, f"judge_meta_{a.judge_name}.json"),
                      {"judge_name": a.judge_name, "arms": arms, "axes": axes,
                       "n_tasks": len(apps), "n_votes": len(rows),
                       "n_null": n_null, "judge_model": a.judge_model,
                       "mock": a.mock, "usage": usage.to_dict()})
    log.info("DONE: %d votes (%d null) -> %s", len(rows), n_null, out_path)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True,
                   help="dir containing one subdir per arm (results/<tag>)")
    p.add_argument("--arms", default=None, help="comma list; default: auto-detect")
    p.add_argument("--axes", default="overall",
                   help=f"comma list from {list(JUDGE_AXES)}")
    p.add_argument("--judge-name", default="qvl72",
                   help="tag for output file (results_<name>.jsonl); use a "
                        "distinct name per judge for the dual-judge protocol")
    p.add_argument("--judge-ports", default="8100")
    p.add_argument("--judge-model", default="Qwen/Qwen2.5-VL-72B-Instruct")
    p.add_argument("--judge-base-url", default=None,
                   help="OpenAI-compatible API base URL for a frontier judge, "
                        "e.g. https://generativelanguage.googleapis.com/v1beta/openai")
    p.add_argument("--judge-api-key-env", default="GEMINI_API_KEY")
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--mock", action="store_true")
    a = p.parse_args()
    asyncio.run(main_async(a))


if __name__ == "__main__":
    main()
