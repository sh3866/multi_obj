"""Generate a shared-r0 pool for the paired design: per task, ONE planner spec
+ ONE initial html that every loop arm will start from.

  python make_r0_pool.py --out r0_pool/s0 \
      --gen-ports 8000,8001 --task-ids "$(cat deep_task_ids.txt)" --n-items 15

Writes <out>/<app>/{spec.txt,r0.html}. Run once per seed (s0/s1/s2) — seeds
differ only through sampling (temperature 0.7), matching fresh-r0 statistics.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os

from src.config import ExperimentConfig, add_common_args
from src.data.artifacts_data import load_artifacts
from src.data.webgen_data import load_webgen
from src.arms import common
from src.infra.client import make_client, UsageStats
from src.infra.io_utils import atomic_write_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("r0pool")


async def main_async(a):
    cfg = ExperimentConfig.from_args(a)
    if cfg.task_source == "webgen":
        items = load_webgen(cfg.webgen_test, cfg.n_items, cfg.task_ids,
                            cfg.categories)
    else:
        items = load_artifacts(cfg.artifacts_json, cfg.n_items, cfg.task_ids,
                               cfg.categories, cfg.difficulties)
    gen_c = make_client(cfg.gen_ports, cfg.gen_model, cfg.concurrency,
                        cfg.mock, "gen")
    usage = UsageStats()
    sem = asyncio.Semaphore(cfg.concurrency)

    async with gen_c as gc:
        async def one(item):
            async with sem:
                spec = await common.run_planner(item["instruction"], gc, cfg, usage)
                html = await common.gen_initial(item["instruction"], spec,
                                                gc, cfg, usage)
            d = os.path.join(a.out, item["app"])
            os.makedirs(d, exist_ok=True)
            atomic_write_text(os.path.join(d, "spec.txt"), spec or "")
            atomic_write_text(os.path.join(d, "r0.html"), html or "")
            log.info("[%s] spec=%d chars, r0=%d chars",
                     item["app"], len(spec or ""), len(html or ""))
            return bool(html)

        oks = await asyncio.gather(*[one(it) for it in items])
    log.info("DONE r0 pool %s: %d/%d ok, tokens=%d",
             a.out, sum(oks), len(items), usage.total_tokens)


def main():
    p = argparse.ArgumentParser()
    add_common_args(p)
    p.add_argument("--out", required=True, help="pool dir (one per seed)")
    a = p.parse_args()
    asyncio.run(main_async(a))


if __name__ == "__main__":
    main()
