"""Robust extraction of JSON / HTML from LLM responses."""

from __future__ import annotations

import json
import re
from typing import Optional


def _balanced_objects(t: str):
    """Yield every balanced {...} substring (outermost), left to right."""
    depth = start = -1
    for i, ch in enumerate(t):
        if ch == "{":
            if depth <= 0:
                start = i; depth = 1
            else:
                depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start != -1:
                yield t[start:i + 1]; start = -1


def _lenient(obj: str) -> Optional[dict]:
    """Recover fields from almost-JSON (unescaped inner quotes / newlines in
    string values). Anchors string values on the next `"key":` or closing brace,
    so inner quotes are tolerated. Best-effort, only used after strict fails."""
    out: dict = {}
    # numbers / bools / null
    for k, v in re.findall(r'"(\w+)"\s*:\s*(-?\d+(?:\.\d+)?|true|false|null)', obj):
        out[k] = {"true": True, "false": False, "null": None}.get(v, None)
        if out[k] is None and v not in ("null",):
            try: out[k] = float(v) if "." in v else int(v)
            except Exception: pass
    # string values: capture up to the next  ", "key":  or trailing }
    for m in re.finditer(r'"(\w+)"\s*:\s*"(.*?)"\s*(?=,\s*"\w+"\s*:|\}\s*$|\}[^"]*$)',
                         obj, flags=re.DOTALL):
        out[m.group(1)] = m.group(2).replace('\\"', '"').replace("\\n", " ").strip()
    # arrays (shallow, of strings)
    for m in re.finditer(r'"(\w+)"\s*:\s*\[(.*?)\]', obj, flags=re.DOTALL):
        items = re.findall(r'"([^"]*)"', m.group(2))
        out[m.group(1)] = items
    return out or None


def extract_json(text: Optional[str]) -> Optional[dict]:
    """Pull a JSON object out of an LLM response. Tolerates ``` fences, a
    <think> reasoning preamble, trailing prose, and (as a last resort) unescaped
    quotes/newlines inside string values."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.DOTALL | re.IGNORECASE).strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.MULTILINE).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    for cand in _balanced_objects(t):          # strict parse of each balanced obj
        try:
            return json.loads(cand)
        except Exception:
            continue
    for cand in _balanced_objects(t):          # lenient recovery
        d = _lenient(cand)
        if d:
            return d
    return _lenient(t)


def extract_html(text: Optional[str]) -> str:
    """Pull a self-contained HTML document out of an LLM response."""
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"^```(?:html)?\s*|\s*```$", "", t, flags=re.MULTILINE).strip()
    m = re.search(r"<!DOCTYPE html.*?</html>", t, flags=re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(0)
    m = re.search(r"<html.*?</html>", t, flags=re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(0)
    # truncated output (no closing </html>): still drop any prose preamble the
    # model wrote before the document ("Here is the improved HTML... ### ...")
    # — otherwise the commentary renders as visible page text.
    m = re.search(r"<!DOCTYPE\s+html|<html[\s>]", t, flags=re.IGNORECASE)
    if m:
        return t[m.start():]
    return t  # last resort: whatever came back


def validate_complete_html(text: Optional[str]) -> tuple[bool, list[str]]:
    """Reject truncated page artifacts before a browser silently repairs them."""
    html = extract_html(text)
    problems: list[str] = []
    low = html.lower().strip()
    if not re.search(r"<(?:!doctype\s+html|html[\s>])", low):
        problems.append("missing_html_start")
    if not low.endswith("</html>"):
        problems.append("missing_html_end")
    if "<body" not in low or "</body>" not in low:
        problems.append("incomplete_body")
    for tag in ("script", "style"):
        opened = len(re.findall(rf"<{tag}(?:\s|>)", low))
        closed = len(re.findall(rf"</{tag}\s*>", low))
        if opened != closed:
            problems.append(f"unbalanced_{tag}")
    return not problems, problems
