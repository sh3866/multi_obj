"""Grounded computational design metrics from a rendered screenshot (no LLM).

HCI-validated low-level aesthetics (Miniukovich & Oulasvirta; Hasler-Susstrunk;
Rosenholtz). Each raw metric is mapped to a goodness in [0,1] so it can be a
Pareto axis (higher = better). Inverted-U metrics (clutter, colourfulness,
whitespace, colour count) peak inside a target band; monotone ones (symmetry,
balance) just increase. Everything is computed from the full-page PNG.

Returns a dict of goodness scores keyed by axis name.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _load(png_path, max_side=1024):
    im = Image.open(png_path).convert("RGB")
    if max(im.size) > max_side:
        s = max_side / max(im.size)
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))))
    return np.asarray(im, dtype=np.float64)          # H x W x 3, 0..255


def _band(x, lo, hi, w):
    """goodness=1 inside [lo,hi], decaying to 0 over absolute width `w` outside."""
    if x < lo:
        return max(0.0, 1.0 - (lo - x) / w)
    if x > hi:
        return max(0.0, 1.0 - (x - hi) / w)
    return 1.0


def _lower(x, good, bad):
    """monotone 'lower is better': 1 at x<=good, 0 at x>=bad."""
    if x <= good:
        return 1.0
    if x >= bad:
        return 0.0
    return (bad - x) / (bad - good)


def colourfulness(a):
    """Hasler & Susstrunk (2003): M = std(rg,yb) + 0.3*mean(rg,yb). Typical 0..150."""
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    rg = R - G
    yb = 0.5 * (R + G) - B
    std = np.sqrt(rg.var() + yb.var())
    mean = np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)
    return std + 0.3 * mean


def clutter(a):
    """Edge density (Sobel magnitude > thresh fraction). Higher = more cluttered."""
    g = a.mean(axis=2)
    gx = np.abs(np.diff(g, axis=1, prepend=g[:, :1]))
    gy = np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    mag = np.hypot(gx, gy)
    return float((mag > 24).mean())                  # fraction of edge pixels


def whitespace(a):
    """Fraction of pixels close to the dominant (background) colour."""
    flat = (a // 24 * 24).reshape(-1, 3)
    cols, counts = np.unique(flat, axis=0, return_counts=True)
    bg = cols[counts.argmax()]
    d = np.abs(a - bg).sum(axis=2)
    return float((d < 40).mean())


def colour_count(a):
    """Number of distinct quantised colours (palette size)."""
    q = (a // 32 * 32).reshape(-1, 3)
    return int(np.unique(q, axis=0).shape[0])


def symmetry(a):
    """Left-right pixel symmetry (1 = perfectly mirror-symmetric)."""
    g = a.mean(axis=2)
    mirror = g[:, ::-1]
    diff = np.abs(g - mirror).mean() / 255.0
    return float(1.0 - diff)


def balance(a):
    """Visual-mass balance: how centred the 'ink' (non-background) is. 1 = centred."""
    g = 255.0 - a.mean(axis=2)                        # ink = darker/coloured
    g = np.clip(g - g.min(), 0, None)
    tot = g.sum() + 1e-9
    ys, xs = np.mgrid[0:g.shape[0], 0:g.shape[1]]
    cx = (g * xs).sum() / tot / g.shape[1]
    cy = (g * ys).sum() / tot / g.shape[0]
    off = np.hypot(cx - 0.5, cy - 0.5) / 0.707        # 0 centred .. 1 corner
    return float(1.0 - off)


def raw_metrics(png_path) -> dict:
    """Raw computational-aesthetics values (no thresholds). Normalization is done
    data-driven by the scorer across the per-problem candidate pool.
    Directions (from HCI literature): cleanliness=lower clutter better;
    whitespace/colourfulness = inverted-U (middle best); balance/symmetry = higher better."""
    try:
        a = _load(png_path)
    except Exception:
        return {}
    return {"clutter": clutter(a), "whitespace": whitespace(a),
            "colourfulness": colourfulness(a), "balance": balance(a),
            "symmetry": symmetry(a)}

# direction of each raw metric: "low"=lower better, "mid"=inverted-U, "high"=higher better
METRIC_DIR = {"clutter": "low", "whitespace": "mid", "colourfulness": "mid",
              "balance": "high", "symmetry": "high"}


def design_goodness(png_path) -> dict:
    """All grounded design axes as goodness in [0,1] (higher=better)."""
    try:
        a = _load(png_path)
    except Exception:
        return {}
    raw_clutter = clutter(a)
    raw_ws = whitespace(a)
    raw_cf = colourfulness(a)
    raw_cc = colour_count(a)
    return {
        "cleanliness": round(_lower(raw_clutter, 0.02, 0.10), 4),   # low edge-clutter is cleaner
        "whitespace":  round(_band(raw_ws, 0.25, 0.60, 0.45), 4),   # airy but not empty (inverted-U)
        "colorfulness":round(_band(raw_cf, 14.0, 45.0, 30.0), 4),   # colourful, not garish (inverted-U)
        "balance":     round(balance(a), 4),                        # centred visual mass (monotone)
        "symmetry":    round(symmetry(a), 4),                       # mirror symmetry (monotone)
        "_raw": {"clutter": round(raw_clutter, 4), "whitespace": round(raw_ws, 4),
                 "colourfulness": round(raw_cf, 2), "colour_count": raw_cc},
    }


if __name__ == "__main__":
    import sys, json
    print(json.dumps(design_goodness(sys.argv[1]), indent=2))
