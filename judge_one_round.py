"""Score ONE specific candidate round across the s0 configs (preliminary).
Appends cand_id=<round> rows to scores_<judge>.jsonl per run-dir.

  python judge_one_round.py --round r3 --judge s0prelim --judge-ports 8200
"""
from __future__ import annotations
import argparse, asyncio, json, os
from src.infra.client import make_client, UsageStats
from src.eval_b.judge import judge_scores

CONFIGS = [
    ("results/sharedr0/s0", "SELF"), ("results/sharedr0/s0", "FUSED"),
    ("results/sharedr0/s0", "AXES"), ("results/sharedr0/s0", "MAD"),
    ("results/axisabl2/s0/visawi5", "MAD"),
    ("results/axisabl2/s0/lt3", "MAD"),
    ("results/axisabl2/s0/hedonic3", "MAD"),
]
AXES = ["functionality", "design", "originality", "craft"]


def shots(pdir, app, rnd):
    base = os.path.join(pdir, app, "candidates")
    settled = os.path.join(base, f"{rnd}.png")
    if not os.path.exists(settled):
        return None
    return [settled]


async def main_async(a):
    jc = make_client([int(p) for p in str(a.judge_ports).split(",")],
                     "Qwen/Qwen2.5-VL-72B-Instruct", 8, False, "judge")
    usage = UsageStats()
    sem = asyncio.Semaphore(8)
    async with jc as client:
        for run_dir, arm in CONFIGS:
            pdir = os.path.join(run_dir, arm, "problems")
            if not os.path.isdir(pdir):
                continue
            out = os.path.join(run_dir, "judge", f"scores_{a.judge}.jsonl")
            apps = sorted(os.listdir(pdir))

            async def one(app):
                imgs = shots(pdir, app, a.round)
                if not imgs:
                    return None
                tp = os.path.join(pdir, app, "trace.json")
                instr = json.load(open(tp)).get("instruction", "") if os.path.exists(tp) else ""
                async with sem:
                    sc = await judge_scores(instr, imgs, AXES, client, usage)
                rows = [{"app": app, "arm": arm, "cand_id": a.round, "axis": ax,
                         "score": None if sc is None else sc[ax]} for ax in AXES]
                if sc is not None:
                    rows.append({"app": app, "arm": arm, "cand_id": a.round,
                                 "axis": "overall",
                                 "score": round(sum(sc[ax] for ax in AXES)/len(AXES), 3)})
                return rows

            results = await asyncio.gather(*[one(app) for app in apps])
            with open(out, "a") as f:
                for rows in results:
                    if rows:
                        for r in rows:
                            f.write(json.dumps(r) + "\n")
            n = sum(1 for r in results if r)
            print(f"{run_dir}/{arm}: {n} {a.round} scored")
    print(f"tokens={usage.total_tokens}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--round", required=True)
    p.add_argument("--judge", default="s0prelim")
    p.add_argument("--judge-ports", default="8200")
    asyncio.run(main_async(p.parse_args()))
