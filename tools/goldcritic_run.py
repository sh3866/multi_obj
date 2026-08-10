"""Gold-critic single-step test (2026-07-16).

Reuses art32b's SHARED r0. For each task, waits for a hand-written gold critique
(critic = Opus, written offline by looking at r0.png), then has the SAME
generator (Qwen3-VL-32B) revise r0 using that critique -> r1_gold.

Weak baseline (r1_weak = VL-32B critic's revision of the same r0) already lives
in results/art32b. So this is a paired single-variable comparison: identical r0,
critique text is the only difference. Judge (Fable) scores r0 / r1_weak / r1_gold
later -> tests whether a stronger critic causally raises the judged score.
"""
from __future__ import annotations
import argparse, asyncio, glob, json, os, time
from types import SimpleNamespace

from src.infra.client import make_client, BudgetedUsage
from src.infra.render import render_and_probe
from src.arms.common import gen_revision

OUT = "results/goldcritic"
# variant -> critique dir. Each produces r1_{variant}.{html,png}.
VARIANTS = {"gold": "_critiques", "goldmad": "_critiques_mad"}


async def one_unit(task, variant, gen_c, cfg, usage):
    d = f"{OUT}/{task}"
    critique_f = f"{OUT}/{VARIANTS[variant]}/{task}.txt"
    r0_html = open(f"{d}/r0.html").read()
    instruction = open(f"{d}/instruction.txt").read()
    critique = open(critique_f).read().strip()
    print(f"[{task}/{variant}] revising r0 ({len(critique)} chars)...", flush=True)
    html = await gen_revision(instruction, r0_html, critique, gen_c, cfg, usage)
    open(f"{d}/r1_{variant}.html", "w").write(html)
    info = await render_and_probe(html, f"{d}/r1_{variant}.png", n_shots=3)
    json.dump({"task": task, "variant": variant, "critique_chars": len(critique),
               "bytes": len(html.encode()), "probe": info},
              open(f"{d}/r1_{variant}_meta.json", "w"), indent=1)
    ok = info.get("rendered")
    print(f"[{task}/{variant}] DONE rendered={ok} func={info.get('func_objective')}", flush=True)
    return (task, variant), ok


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-ports", default="8000")
    ap.add_argument("--gen-model", required=True)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--wait-min", type=int, default=60,
                    help="max minutes to wait for critique files to appear")
    args = ap.parse_args()

    tasks = sorted(os.path.basename(os.path.dirname(p))
                   for p in glob.glob(f"{OUT}/*/r0.html"))
    units = [(t, v) for t in tasks for v in VARIANTS]
    print(f"tasks={len(tasks)} variants={list(VARIANTS)} units={len(units)}", flush=True)

    ports = [int(p) for p in args.gen_ports.split(",")]
    gen_c = make_client(ports, args.gen_model, args.concurrency, False, "gen")
    cfg = SimpleNamespace(max_tokens=args.max_tokens, gen_temperature=0.7)
    usage = BudgetedUsage(10_000_000)

    done, deadline = set(), time.time() + args.wait_min * 60
    while len(done) < len(units) and time.time() < deadline:
        ready = [(t, v) for (t, v) in units if (t, v) not in done
                 and os.path.exists(f"{OUT}/{VARIANTS[v]}/{t}.txt")]
        if not ready:
            await asyncio.sleep(15); continue
        results = await asyncio.gather(
            *(one_unit(t, v, gen_c, cfg, usage) for (t, v) in ready),
            return_exceptions=True)
        for r in results:
            if isinstance(r, tuple):
                done.add(r[0])
            else:
                print(f"ERROR: {r}", flush=True)
        left = [u for u in units if u not in done]
        print(f"progress {len(done)}/{len(units)}; waiting on: {left[:6]}...", flush=True)
    print(f"FINISHED {len(done)}/{len(units)}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
