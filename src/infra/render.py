"""Render an HTML string to a screenshot + active verification, via Playwright
(the chromium downloaded by `playwright install chromium`).

The only system lib chromium was missing on this box is libasound.so.2, supplied
by conda `alsa-lib`; set LD_LIBRARY_PATH so the browser finds it (see _ensure_ld).
Same interface throughout: render_and_probe(html, out_png, ...) -> dict with the
screenshot path, console/page errors, click probes, and efficiency metrics.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Make chromium find libasound.so.2 (conda alsa-lib) at launch.
_CONDA_LIB = "/data_seoul/sunghyun/anaconda3/lib"
if os.path.isdir(_CONDA_LIB) and _CONDA_LIB not in os.environ.get("LD_LIBRARY_PATH", ""):
    os.environ["LD_LIBRARY_PATH"] = _CONDA_LIB + ":" + os.environ.get("LD_LIBRARY_PATH", "")

_PLAYWRIGHT_OK: Optional[bool] = None


def playwright_available() -> bool:
    global _PLAYWRIGHT_OK
    if _PLAYWRIGHT_OK is None:
        try:
            import playwright.async_api  # noqa: F401
            _PLAYWRIGHT_OK = True
        except Exception:
            _PLAYWRIGHT_OK = False
    return _PLAYWRIGHT_OK


_PROBE_JS = """
() => {
  const q = (s) => Array.from(document.querySelectorAll(s));
  return {
    n_buttons: q('button').length,
    n_links: q('a[href]').length,
    n_inputs: q('input, textarea, select').length,
    n_forms: q('form').length,
    n_clickable: q('button, a[href], [onclick], [role=button], input[type=submit], input[type=button]').length,
    dom_nodes: document.getElementsByTagName('*').length,
    title: document.title || '',
    body_len: (document.body ? document.body.innerText.length : 0),
  };
}
"""


def _score(rendered, page_errors, console_errors, struct):
    if not rendered:
        return 0.0
    s = 1.0
    if page_errors:
        s -= 0.4
    if console_errors:
        s -= 0.2
    if struct.get("body_len", 0) < 30:
        s -= 0.2
    return max(0.0, min(1.0, s))


async def render_and_probe(html: str, out_png: str,
                           viewport: Tuple[int, int] = (1280, 800),
                           full_page: bool = True, settle_ms: int = 500, n_shots: int = 1) -> dict:
    """Render one settled screenshot (t1) and collect passive load diagnostics.

    n_shots remains only for call-site compatibility; t0/t2 are no longer
    captured or stored in new experiments.
    """
    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    info = {"rendered": False, "png": out_png, "pngs": [out_png],
            "console_errors": [], "page_errors": [],
            "structure": {}, "func_objective": 0.0,
            "html_bytes": len(html.encode("utf-8")), "dom_nodes": None, "load_ms": None}
    if not playwright_available():
        logger.warning("Playwright unavailable — skipping render.")
        info["error"] = "playwright_unavailable"
        return info

    base, ext = os.path.splitext(out_png)
    from playwright.async_api import async_playwright
    try:
        async with async_playwright() as p:
            browser_env = {k: v for k, v in os.environ.items()
                           if k not in {"DISPLAY", "WAYLAND_DISPLAY"}}
            browser = await p.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                      "--disable-software-rasterizer"],
                env=browser_env)
            page = await browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            page.on("console", lambda m: (
                info["console_errors"].append(m.text) if m.type == "error" else None))
            page.on("pageerror", lambda e: info["page_errors"].append(str(e)))
            t0 = time.perf_counter()
            await page.set_content(html, wait_until="networkidle")
            info["load_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            await page.wait_for_timeout(settle_ms)
            await page.screenshot(path=out_png, full_page=full_page, timeout=120000)
            info["rendered"] = True
            try:
                info["structure"] = await page.evaluate(_PROBE_JS)
                info["dom_nodes"] = info["structure"].get("dom_nodes")
            except Exception as exc:
                info["structure"] = {"probe_error": str(exc)}
            await browser.close()
        info["func_objective"] = _score(info["rendered"], info["page_errors"],
                                        info["console_errors"], info["structure"])
    except Exception as exc:
        logger.error("Render failed: %s", exc)
        info["error"] = str(exc)
    return info
