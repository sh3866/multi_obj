"""Robust extraction of JSON / HTML from LLM responses."""

from __future__ import annotations

import json
import re
from typing import Optional


def extract_json(text: Optional[str]) -> Optional[dict]:
    """Pull the first JSON object out of an LLM response (tolerates ``` fences)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.MULTILINE).strip()
    # try whole string first
    try:
        return json.loads(t)
    except Exception:
        pass
    # fall back to first balanced {...}
    start = t.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except Exception:
                    return None
    return None


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
    return t  # last resort: whatever came back
