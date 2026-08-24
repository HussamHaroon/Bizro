"""Thin DashScope / Alibaba Cloud Model Studio client (OpenAI-compatible mode).

Single choke-point for every server-side model call (SKILL.md hard rule).
Env-driven via config.Settings. MOCK_MODE=auto with no DASHSCOPE_API_KEY returns
clearly-labeled synthetic responses — every mock payload carries "mock": true
and never mimics real model output.

Model IDs live in config (MODEL_* envs); see server/docs/model-notes.md for the
live-docs research behind the defaults and any drift found.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .config import get_settings


class DashScopeError(RuntimeError):
    pass


class MockModeError(DashScopeError):
    """MOCK_MODE=never was set but no API key exists — refuse to fake it."""


def is_live() -> bool:
    return get_settings().dashscope_is_live()


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def chat_completion(
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    response_format_json: bool = False,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """POST {base}/chat/completions (OpenAI-compatible). Returns the parsed JSON.

    In mock mode returns a synthetic envelope clearly marked "mock": true.
    """
    s = get_settings()
    if not s.dashscope_is_live():
        if s.mock_mode == "never":
            raise MockModeError(
                "MOCK_MODE=never but DASHSCOPE_API_KEY is not set — refusing to mock."
            )
        return _mock_chat_completion(model, messages)

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format_json:
        body["response_format"] = {"type": "json_object"}

    resp = httpx.post(
        f"{s.dashscope_base_url.rstrip('/')}/chat/completions",
        headers=_headers(s.dashscope_api_key),
        json=body,
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise DashScopeError(
            f"DashScope chat/completions HTTP {resp.status_code}: {resp.text[:500]}"
        )
    return resp.json()


def list_models(timeout: float = 30.0) -> dict[str, Any]:
    """GET {base}/models — used by scripts/verify_key.py to check reachability."""
    s = get_settings()
    if not s.dashscope_is_live():
        if s.mock_mode == "never":
            raise MockModeError(
                "MOCK_MODE=never but DASHSCOPE_API_KEY is not set — refusing to mock."
            )
        return {
            "mock": True,
            "note": (
                "MOCK response — no DASHSCOPE_API_KEY configured. This is NOT a real "
                "model list. Set DASHSCOPE_API_KEY (HANDOFF.md ①) for live output."
            ),
            "data": [],
        }

    resp = httpx.get(
        f"{s.dashscope_base_url.rstrip('/')}/models",
        headers=_headers(s.dashscope_api_key),
        timeout=timeout,
    )
    if resp.status_code != 200:
        raise DashScopeError(
            f"DashScope /models HTTP {resp.status_code}: {resp.text[:500]}"
        )
    return resp.json()


def probe_model(model: str, timeout: float = 30.0) -> bool:
    """Minimal chat/completions reachability probe — used as a fallback when
    GET /models is unavailable on a regional endpoint (server/docs/model-notes.md
    §1: /models is not documented on the compat page)."""
    s = get_settings()
    if not s.dashscope_is_live():
        return False
    resp = httpx.post(
        f"{s.dashscope_base_url.rstrip('/')}/chat/completions",
        headers=_headers(s.dashscope_api_key),
        json={
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        },
        timeout=timeout,
    )
    # 200 = reachable; 404/400 model-not-found style errors are the signal we
    # care about; 429 (quota) still proves the model id resolved.
    return resp.status_code in (200, 429)


def _mock_chat_completion(model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Clearly-labeled synthetic completion. The 'content' is a stub string that
    a caller must NOT treat as a parsed model answer — pipelines are expected to
    validate/retry on real calls; in mock mode the server's fallback pipelines
    (dispatch.py) generate the synthetic transaction data themselves and mark it."""
    return {
        "mock": True,
        "note": (
            "MOCK response — clearly synthetic, not real model output. "
            "Set DASHSCOPE_API_KEY (HANDOFF.md ①) for live calls."
        ),
        "id": f"mock-{int(time.time())}",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {"mock": True, "model": model, "messages_in": len(messages)},
                        ensure_ascii=False,
                    ),
                },
                "finish_reason": "mock",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
