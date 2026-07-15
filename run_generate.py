"""Generate one arm over benchmark instructions under a fixed token budget.
Task sources: ArtifactsBench (primary; --task-source artifacts, default) or
WebGen-Bench (--task-source webgen; also emits WebGen-format artifacts).

Per task, writes under {output_dir}/problems/{app}/:
  candidates/{id}.html + {id}.png   every intermediate artifact (+ probe metrics)
  candidates.json                    index with tokens_at stamps (for token curves)
  trace.json                         per-round history (critic scores -> leniency)
  final.html / final.png             shared-selector pick (max func_objective)
and a WebGen-format artifact under {artifact_root}/{arm}/ for official scoring.

Offline smoke (no servers/GPU/Playwright):
  python run_generate.py --mock --no-render --arm MAD --n-items 2 \
      --budget-tokens 4000 --output-dir results/_smoke/MAD

Live example (primary track):
  python run_generate.py --arm MAD --gen-ports 8000 --vlm-ports 8004 \
      --n-items 50 --categories design_forward --difficulties medium,hard \
      --output-dir results/pilot/MAD
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import time

from src.config import ExperimentConfig, add_common_args
from src.infra.client import make_client, BudgetedUsage
from src.data.webgen_data import load_webgen
from src.data.artifacts_data import load_artifacts
from src.data.webgen_artifact import write_artifact
from src.arms.arms import RUNNERS
from src.arms.common import probe_and_select
from src.infra.io_utils import atomic_write_json, atomic_write_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("generate")


async def run_task(item, gen_c, vlm_c, cfg) -> dict:
    workdir = os.path.join(cfg.output_dir, "problems", item["app"])
    os.makedirs(workdir, exist_ok=True)
    usage = BudgetedUsage(cfg.budget_tokens)
    rec = await RUNNERS[cfg.arm](item["instruction"], workdir, gen_c, vlm_c, cfg, usage)
    cands = rec["candidates"]

    final = await probe_and_select(cands, workdir, cfg)
    atomic_write_text(os.path.join(workdir, "final.html"), final.get("html", ""))
    for src_p, dst in zip(final.get("pngs") or ([final["png"]] if final.get("png") else []),
                          ("final_t0.png", "final.png", "final_t2.png")
                          if len(final.get("pngs") or []) == 3 else ("final.png",)):
        if src_p and os.path.exists(src_p):
            shutil.copyfile(src_p, os.path.join(workdir, dst))

    atomic_write_json(os.path.join(workdir, "candidates.json"),
                      [{k: v for k, v in c.items() if k != "html"}
                       for c in cands.items])
    atomic_write_json(os.path.join(workdir, "trace.json"),
                      {"arm": cfg.arm, "app": item["app"], "id": item["id"],
                       "instruction": item["instruction"],
                       "category": item.get("category", ""),
                       "difficulty": item.get("difficulty", ""),
                       "checklist": item.get("checklist", []),
                       "final_id": final.get("id"),
                       "history": rec["history"], "usage": usage.to_dict(),
                       "extra": rec.get("extra", {})})

    if cfg.task_source == "webgen":  # WebGen official-scoring artifacts
        write_artifact(cfg.arm, item["app"], item["instruction"],
                       final.get("html", ""), cfg.artifact_root)
    log.info("[%s|%s] cands=%d final=%s tokens=%d/%d calls=%d",
             item["app"], cfg.arm, len(cands.items), final.get("id"),
             usage.total_tokens, cfg.budget_tokens, usage.n_calls)
    return {"app": item["app"], "id": item["id"],
            "category": item.get("category", ""),
            "n_candidates": len(cands.items), "final_id": final.get("id"),
            "final_func": (final.get("probe") or {}).get("func_objective"),
            "usage": usage.to_dict()}


async def main_async(cfg: ExperimentConfig):
    if cfg.task_source == "artifacts":
        items = load_artifacts(cfg.artifacts_json, cfg.n_items, cfg.task_ids,
                               cfg.categories, cfg.difficulties)
    else:
        items = load_webgen(cfg.webgen_test, cfg.n_items, cfg.task_ids, cfg.categories)
    log.info("%s: %d tasks, budget=%d tok/task, mock=%s render=%s",
             cfg.arm, len(items), cfg.budget_tokens, cfg.mock, cfg.render)
    os.makedirs(cfg.output_dir, exist_ok=True)
    atomic_write_json(os.path.join(cfg.output_dir, "run_config.json"),
                      {**cfg.to_dict(),
                       "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})

    gen_c = make_client(cfg.gen_ports, cfg.gen_model, cfg.concurrency, cfg.mock, "gen")
    vlm_c = make_client(cfg.vlm_ports, cfg.vlm_model, cfg.concurrency, cfg.mock, "vlm")
    sem = asyncio.Semaphore(cfg.concurrency)

    async with gen_c as g, vlm_c as v:
        async def worker(item):
            async with sem:
                try:
                    return await run_task(item, g, v, cfg)
                except Exception:
                    log.exception("[%s|%s] task failed", item["app"], cfg.arm)
                    return {"app": item["app"], "id": item["id"], "error": True}
        records = await asyncio.gather(*[worker(it) for it in items])

    ok = [r for r in records if not r.get("error")]
    summ = {
        "arm": cfg.arm, "n_tasks": len(records), "n_ok": len(ok),
        "budget_tokens": cfg.budget_tokens,
        "mean_tokens": (sum(r["usage"]["total_tokens"] for r in ok) / len(ok)) if ok else 0,
        "mean_candidates": (sum(r["n_candidates"] for r in ok) / len(ok)) if ok else 0,
        "total_calls": sum(r["usage"]["n_calls"] for r in ok),
        "artifact_dir": os.path.join(cfg.artifact_root, cfg.arm),
        "per_task": records,
    }
    atomic_write_json(os.path.join(cfg.output_dir, "global_stats.json"), summ)
    log.info("DONE %s: ok=%d/%d mean_tokens=%.0f (budget %d) mean_cands=%.1f",
             cfg.arm, len(ok), len(records), summ["mean_tokens"],
             cfg.budget_tokens, summ["mean_candidates"])


def main():
    p = argparse.ArgumentParser()
    add_common_args(p)
    asyncio.run(main_async(ExperimentConfig.from_args(p.parse_args())))


if __name__ == "__main__":
    main()
