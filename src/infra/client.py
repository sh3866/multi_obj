"""Async vLLM client (round-robin) — text generation + VLM (image) chat.

Reuses the mad/ harness pattern (PortManager round-robin, retries, UsageStats)
and adds generate_vlm() which sends a base64 screenshot alongside the prompt to
an OpenAI-compatible multimodal endpoint (the WebGen-Bench image pattern).

A MockClient with the same interface lets the whole loop run with no servers.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

import aiohttp

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------

@dataclass
class UsageStats:
    n_calls: int = 0
    n_failed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def record(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        self.n_calls += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    def record_failure(self) -> None:
        self.n_failed += 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict:
        return {
            "n_calls": self.n_calls, "n_failed": self.n_failed,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class BudgetedUsage(UsageStats):
    """UsageStats with a hard total-token budget (compute matching across arms).

    Arms must check exhausted() before each further step and stop when True.
    The budget counts prompt+completion tokens of every LLM/VLM call the arm makes.
    """

    def __init__(self, budget_tokens: int):
        super().__init__()
        self.budget_tokens = budget_tokens

    def exhausted(self) -> bool:
        return self.total_tokens >= self.budget_tokens

    def remaining(self) -> int:
        return max(0, self.budget_tokens - self.total_tokens)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["budget_tokens"] = self.budget_tokens
        return d


class PortManager:
    def __init__(self, ports: List[int]):
        assert ports, "At least one port required"
        self.ports = ports
        self._idx = 0
        self._lock = asyncio.Lock()

    async def next_port(self) -> int:
        async with self._lock:
            port = self.ports[self._idx % len(self.ports)]
            self._idx += 1
            return port


# ---------------------------------------------------------------------------

class VLLMClient:
    """Async client for OpenAI-compatible vLLM endpoints (text + vision)."""

    def __init__(self, ports: List[int], model_name: str,
                 concurrency: int = 8, timeout: int = 2400):
        self.port_manager = PortManager(ports)
        self.model_name = model_name
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(concurrency)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=self._semaphore._value)
        self._session = aiohttp.ClientSession(connector=connector)
        return self

    async def __aexit__(self, *_):
        if self._session:
            await self._session.close()

    async def _post(self, payload: dict, usage_stats: Optional[UsageStats],
                    retries: int = 3, tag: str = "") -> Optional[str]:
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        for attempt in range(retries):
            port = await self.port_manager.next_port()
            url = f"http://localhost:{port}/v1/chat/completions"
            try:
                async with self._semaphore:
                    async with self._session.post(url, json=payload, timeout=timeout) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        text = data["choices"][0]["message"]["content"]
                        if usage_stats is not None:
                            u = data.get("usage", {})
                            usage_stats.record(u.get("prompt_tokens", 0),
                                               u.get("completion_tokens", 0))
                        return text
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("[%s] attempt %d/%d failed (port=%d): %s",
                               tag, attempt + 1, retries, port, exc)
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
        if usage_stats is not None:
            usage_stats.record_failure()
        logger.error("[%s] all %d retries exhausted", tag, retries)
        return None

    # serving max-model-len; override per machine via $GEN_CONTEXT_LIMIT
    CONTEXT_LIMIT = int(__import__("os").environ.get("GEN_CONTEXT_LIMIT", 16384))

    async def generate(self, prompt: str, max_tokens: int = 4096,
                       temperature: float = 0.7,
                       usage_stats: Optional[UsageStats] = None,
                       tag: str = "gen") -> Optional[str]:
        # long prompts (full HTML in revision/self-refine) + fixed max_tokens can
        # exceed the server context window -> instant 400; shrink the output
        # request to fit. Dense minified HTML/JS tokenizes at ~2.5 chars/token,
        # so estimate pessimistically (the 3.0 estimate still produced 400s).
        est_prompt_tokens = int(len(prompt) / 2.5)
        fit = max(1024, self.CONTEXT_LIMIT - est_prompt_tokens - 512)
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": min(max_tokens, fit),
            "temperature": temperature,
        }
        # Qwen3.x are reasoning models: disable "thinking" so the completion is
        # clean HTML/JSON instead of a <think> preamble. Harmless no-op for
        # non-reasoning models is NOT guaranteed, so gate on the model name.
        if any(t in self.model_name for t in ("Qwen3", "qwen3")):
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        return await self._post(payload, usage_stats, tag=tag)

    async def generate_vlm(self, prompt: str, image_paths: List[str],
                           max_tokens: int = 2048, temperature: float = 0.2,
                           usage_stats: Optional[UsageStats] = None,
                           tag: str = "vlm") -> Optional[str]:
        """Send prompt + one or more screenshots to a vision endpoint."""
        content = [{"type": "text", "text": prompt}]
        for p in image_paths:
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            })
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        return await self._post(payload, usage_stats, tag=tag)


class APIClient(VLLMClient):
    """OpenAI-compatible remote API endpoint (e.g. Gemini's OpenAI-compat URL).
    Same interface as VLLMClient; used for frontier judge models in eval layer B.
    """

    def __init__(self, base_url: str, api_key: str, model_name: str,
                 concurrency: int = 8, timeout: int = 600):
        super().__init__([0], model_name, concurrency=concurrency, timeout=timeout)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def _post(self, payload: dict, usage_stats: Optional[UsageStats],
                    retries: int = 4, tag: str = "") -> Optional[str]:
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/chat/completions"
        for attempt in range(retries):
            try:
                async with self._semaphore:
                    async with self._session.post(url, json=payload, headers=headers,
                                                  timeout=timeout) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        text = data["choices"][0]["message"]["content"]
                        if usage_stats is not None:
                            u = data.get("usage", {}) or {}
                            usage_stats.record(u.get("prompt_tokens", 0),
                                               u.get("completion_tokens", 0))
                        return text
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("[%s] API attempt %d/%d failed: %s",
                               tag, attempt + 1, retries, exc)
                if attempt < retries - 1:
                    await asyncio.sleep(3 * 2 ** attempt)  # rate-limit friendly
        if usage_stats is not None:
            usage_stats.record_failure()
        return None


# ---------------------------------------------------------------------------
# Mock client — same interface, no servers. Lets the loop be tested offline.
# ---------------------------------------------------------------------------

class MockClient:
    """Offline stand-in. Routes on prompt markers used by critics/prompts.py and
    eval_b/judge.py; deterministic (hash-based) so smoke runs are reproducible."""

    def __init__(self, *_, role: str = "gen", **__):
        self.role = role
        self._n = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    @staticmethod
    def _axis(prompt: str) -> str:
        m = re.search(r"AXIS:\s*(\w+)", prompt)
        return m.group(1) if m else "overall"

    @staticmethod
    def _h(prompt: str, mod: int) -> int:
        import hashlib
        return int(hashlib.md5(prompt.encode()).hexdigest(), 16) % mod

    def _reply(self, prompt: str) -> str:
        # pairwise judge -> forced choice
        if '"winner"' in prompt:
            return json.dumps({"winner": "A" if self._h(prompt, 2) == 0 else "B",
                               "reason": "[mock] deterministic pick"})
        # checklist judge -> per-item booleans
        if '"passed"' in prompt:
            return json.dumps({"passed": [self._h(prompt + str(i), 3) > 0
                                          for i in range(5)]})
        # moderator synthesis -> revision spec (never claims done; budget stops the loop)
        if "good_enough" in prompt and "revision" in prompt:
            return json.dumps({"good_enough": False,
                               "revision": "Increase contrast; tighten spacing.",
                               "conflicts": ["design vs functionality"],
                               "rationale": "[mock] resolved trade-off"})
        # cross-critique (rebuttal with conflicts)
        if "compromise" in prompt:
            return json.dumps({"axis": self._axis(prompt),
                               "conflicts": ["originality trades off"],
                               "accept": ["raise contrast"],
                               "compromise": "raise contrast, keep identity"})
        # orchestrator (DISC axis discovery)
        if '"north_star"' in prompt:
            return json.dumps({"north_star": "[mock] a luminous, tactile arcade "
                               "screen with juicy feedback and confident identity.",
                               "axes": [
                                   {"key": "game_feel", "description": "responsive, juicy interactions"},
                                   {"key": "visual_identity", "description": "distinct, cohesive art direction"},
                                   {"key": "feedback_clarity", "description": "state changes clearly communicated"}]})
        # planner
        if "build spec" in prompt.lower():
            return json.dumps({"spec": "Clean modern single-page build.",
                               "success_criteria": {}})
        # critic / fused critic -> score + suggestion
        if '"score"' in prompt and '"suggestion"' in prompt:
            return json.dumps({"axis": self._axis(prompt),
                               "score": 2 + self._h(prompt, 3),
                               "critique": "[mock] acceptable, minor issues",
                               "suggestion": "improve contrast and alignment"})
        # generator (initial / revise / self-refine) -> self-contained HTML
        return (
            "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Mock</title>"
            "<style>body{font-family:sans-serif;margin:0;background:#0f172a;color:#e2e8f0}"
            ".hero{padding:64px;text-align:center}button{padding:12px 24px;border:0;"
            "border-radius:8px;background:#6366f1;color:white}</style></head>"
            f"<body><div class='hero'><h1>Mock build #{self._n}</h1>"
            "<p>Offline generator output.</p>"
            "<button onclick=\"this.textContent='ok'\">Get started</button></div></body></html>"
        )

    async def generate(self, prompt: str, max_tokens=4096, temperature=0.7,
                       usage_stats=None, tag="gen") -> str:
        self._n += 1
        if usage_stats is not None:
            usage_stats.record(len(prompt) // 4, 160)
        return self._reply(prompt)

    async def generate_vlm(self, prompt: str, image_paths=None, max_tokens=2048,
                           temperature=0.2, usage_stats=None, tag="vlm") -> str:
        self._n += 1
        if usage_stats is not None:
            usage_stats.record(len(prompt) // 4, 100)
        # include image identities in the routing hash so a swapped pair (B,A)
        # can produce a different (order-consistent) mock verdict than (A,B)
        return self._reply(prompt + "|" + "|".join(image_paths or []))


def make_client(ports, model, concurrency, mock: bool, role: str = "gen"):
    if mock:
        return MockClient(role=role)
    return VLLMClient(ports, model, concurrency=concurrency)
