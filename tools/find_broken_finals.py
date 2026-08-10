"""Mechanical listwise-exclusion rule (user decision 2026-07-15).

A task is excluded from ALL summary tables when ANY arm's final artifact is
broken, where broken :=
  (a) visually blank — every temporal screenshot (final_t0/t1/t2.png) has
      pixel std < 3 (uniform screen; catches blank pages and bare spinners), OR
  (b) judged dead — the held-out judge gave overall == 0.

Prints the comma-separated app-id list (empty output = nothing excluded), so
pipelines can do:
  EXCL=$(python tools/find_broken_finals.py results/<tag> --judge qvl72)
  python collect.py results/<tag> --judge qvl72 --exclude-tasks "$EXCL"

Keeping the rule mechanical (no eyeballing) makes it pre-registrable for the
main run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

BLANK_STD = 3.0


def is_blank(base: str) -> bool:
    stds = []
    for t in (0, 1, 2):
        p = os.path.join(base, f"final_t{t}.png")
        if os.path.exists(p):
            a = np.asarray(Image.open(p).convert("L"), dtype=np.float32)
            stds.append(float(a.std()))
    return bool(stds) and max(stds) < BLANK_STD


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--judge", default="qvl72")
    a = ap.parse_args()

    broken = set()
    arms = [d for d in sorted(os.listdir(a.run_dir))
            if os.path.isdir(os.path.join(a.run_dir, d, "problems"))]
    for arm in arms:
        pdir = os.path.join(a.run_dir, arm, "problems")
        for app in sorted(os.listdir(pdir)):
            if is_blank(os.path.join(pdir, app)):
                broken.add(app)
                print(f"# blank final: {app}/{arm}", file=sys.stderr)

    spath = os.path.join(a.run_dir, "judge", f"scores_{a.judge}.jsonl")
    if os.path.exists(spath):
        for l in open(spath):
            if not l.strip():
                continue
            r = json.loads(l)
            if (r.get("cand_id", "final") == "final" and r["axis"] == "overall"
                    and r.get("score") == 0.0):
                if r["app"] not in broken:
                    print(f"# judge overall==0: {r['app']}/{r['arm']}",
                          file=sys.stderr)
                broken.add(r["app"])

    print(",".join(sorted(broken)))


if __name__ == "__main__":
    main()
