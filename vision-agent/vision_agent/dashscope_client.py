"""Thin DashScope (Model Studio) client for Qwen-OCR models.

Uses the OpenAI-compatible chat/completions endpoint with Base64 Data-URL
images — the exact calling convention documented for BOTH qwen-vl-ocr and
qwen3.5-ocr (vision-agent/notes.md §2, cites help.aliyun.com API reference).
No SDK dependency: plain `requests`, injectable transport for tests.

MOCK_MODE is handled one layer up (adapters.py), per Orchestrator decision D0-3.
"""

from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Callable

import requests

from vision_agent.config import Settings

MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
}


class DashScopeError(RuntimeError):
    """Base error for DashScope call failures."""


class DashScopeAuthError(DashScopeError):
    pass


class DashScopeRateLimitError(DashScopeError):
    pass


class DashScopeApiError(DashScopeError):
    pass


class ImageError(ValueError):
    """Local image unreadable / unsupported / too large."""


def image_to_data_url(path: str | Path, max_bytes: int) -> str:
    """Read a local image and return a Base64 Data URL.

    Base64 Data URLs are the documented cross-interface way to pass local
    files to both OCR models (notes.md §2 "Calling convention").
    """
    path = Path(path)
    if not path.is_file():
        raise ImageError(f"image file not found: {path}")
    mime = MIME_BY_SUFFIX.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0]
    if not mime or not mime.startswith("image/"):
        raise ImageError(f"unsupported image type {path.suffix!r} (use jpg/png/webp/bmp)")
    size = path.stat().st_size
    if size > max_bytes:
        raise ImageError(f"image is {size / 1e6:.1f} MB, over the {max_bytes / 1e6:.0f} MB limit")
    if size == 0:
        raise ImageError(f"image file is empty: {path}")
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except (OSError, binascii.Error) as exc:  # pragma: no cover - defensive
        raise ImageError(f"could not read image {path}: {exc}") from exc
    return f"data:{mime};base64,{encoded}"


class DashScopeOcrClient:
    """One method that matters: ``chat(model, prompt, image_data_url) -> str``.

    Retries transient failures (429 / 5xx / connection errors) twice with
    linear backoff; auth failures and HTTP 4xx fail fast with a typed error.
    """

    def __init__(
        self,
        settings: Settings,
        transport: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._settings = settings
        # transport(session-post signature) is injectable so tests can assert
        # the exact payload without any network.
        self._transport = transport or self._default_transport
        self._sleep = sleep if sleep is not None else time.sleep

    # ------------------------------------------------------------------ API

    def chat(self, model: str, prompt: str, image_data_url: str) -> str:
        """Send image + prompt to ``model``; return the assistant text.

        Payload follows the documented compatible-mode multimodal shape:
        content = [image_url, text] (notes.md §2).
        """
        if not self._settings.has_api_key:
            raise DashScopeAuthError(
                "DASHSCOPE_API_KEY is not set (real calls forbidden in mock mode) — "
                "see HANDOFF.md ①"
            )
        url = self._settings.dashscope_base_url.rstrip("/") + "/chat/completions"
        body = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        import llm_guard  # free-tier budget guard (repo root; D6-2)

        llm_guard.allow(model)
        last_error: Exception | None = None
        for attempt in range(3):  # 1 try + 2 retries
            try:
                return self._request(url, body)
            except DashScopeAuthError:
                raise
            except (DashScopeRateLimitError, DashScopeApiError) as exc:
                last_error = exc
                if attempt < 2:
                    self._sleep(1.5 * (attempt + 1))
        raise DashScopeApiError(f"DashScope call failed after retries: {last_error}")

    # -------------------------------------------------------------- internals

    def _default_transport(self, url: str, headers: dict[str, str], json_body: dict, timeout: int):
        return requests.post(url, headers=headers, json=json_body, timeout=timeout)

    def _request(self, url: str, body: dict) -> str:
        import llm_guard  # free-tier budget guard (repo root; D6-2)

        headers = {"Authorization": f"Bearer {self._settings.dashscope_api_key}"}
        response = self._transport(
            url=url, headers=headers, json_body=body, timeout=self._settings.ocr_timeout_seconds
        )
        status = getattr(response, "status_code", None)
        payload = self._json_of(response)
        if status == 401:
            raise DashScopeAuthError("DashScope rejected the API key (HTTP 401)")
        if status == 429:
            raise DashScopeRateLimitError(f"rate limited (HTTP 429): {payload}")
        if status is not None and not (200 <= status < 300):
            raise DashScopeApiError(f"HTTP {status}: {payload}")
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DashScopeApiError(f"unexpected DashScope response shape: {payload}") from exc
        # content may be a plain string (usual) or a content-part list.
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        if not isinstance(content, str):
            raise DashScopeApiError(f"non-text content in response: {content!r}")
        llm_guard.record(str(body.get("model", "?")), usage=payload.get("usage"))
        return content

    @staticmethod
    def _json_of(response: Any) -> dict:
        getter = getattr(response, "json", None)
        if callable(getter):
            try:
                data = getter()
            except ValueError:
                data = None
            if isinstance(data, dict):
                return data
        text = getattr(response, "text", "")
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {"raw": text}
        except (ValueError, TypeError):
            return {"raw": text}
