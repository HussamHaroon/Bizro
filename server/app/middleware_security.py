"""Security headers + per-IP rate limiting (bizro-security baseline).

Pure ASGI middleware wired in server/app/main.py via ``app.add_middleware``.

Headers: four baseline anti-clickjacking / anti-sniffing / privacy headers on
EVERY response (including 429s and errors that flow through this layer).

Rate limiting: in-memory sliding window keyed by client IP (the socket peer,
``scope["client"]`` — not a spoofable header). Two buckets:

- ``POST /webhook/whatsapp``  → RATE_LIMIT_WEBHOOK_PER_HOUR (default 30)/hour.
  This endpoint is PUBLIC and triggers paid-tier AI calls, so it gets the
  strict budget.
- everything else             → RATE_LIMIT_GENERAL_PER_MIN (default 120)/min.

LIMITATIONS (accepted for the demo scale):
- State lives in this process only. Behind multiple workers/instances each
  gets its own budget (effective limit = limit x workers); a deployment that
  outgrows the single-process demo should swap the dict for Redis.
- In-memory counters reset on restart; the sliding window simply reopens.
- On lifespan startup the windows are cleared. For the server that is a
  no-op on a fresh dict; for the test suite (every module builds its own
  ``with TestClient(app)``) it gives each module a fresh budget so tests
  neither trip the limiter nor inherit each other's hits.

Limits are read from the environment PER REQUEST (cheap dict lookup) so ops
can tune them without touching settings code and tests can lower them with
``monkeypatch.setenv``.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import deque

from starlette.datastructures import MutableHeaders

WEBHOOK_PATH = "/webhook/whatsapp"
WEBHOOK_WINDOW_S = 3600
GENERAL_WINDOW_S = 60

# Replace (not append) any same-named upstream header — ours must win.
SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("x-content-type-options", "nosniff"),
    ("x-frame-options", "DENY"),
    ("referrer-policy", "strict-origin-when-cross-origin"),
    ("permissions-policy", "camera=(self), microphone=(self)"),
)

# Sliding-window state: {f"{client_host}|{bucket}": deque[monotonic ts]}.
# Module-level (one app per process — see limitation note above).
_HITS: dict[str, deque[float]] = {}
_PURGE_ABOVE_KEYS = 10_000  # bound memory if many distinct IPs appear


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    try:
        return int(raw) if raw.strip() else default
    except ValueError:
        return default


def reset_rate_limits() -> None:
    """Clear every window. Called on lifespan startup (see module docstring)
    and by tests that need a deterministic budget."""
    _HITS.clear()


def _bucket_for(method: str, path: str) -> tuple[str, int, int]:
    """Returns (bucket name, limit, window seconds) for a request."""
    if method == "POST" and path == WEBHOOK_PATH:
        return "webhook", _env_int("RATE_LIMIT_WEBHOOK_PER_HOUR", 30), WEBHOOK_WINDOW_S
    return "general", _env_int("RATE_LIMIT_GENERAL_PER_MIN", 120), GENERAL_WINDOW_S


def _client_key(scope: dict, bucket: str) -> str:
    client = scope.get("client")
    host = client[0] if client else "unknown"
    return f"{host}|{bucket}"


def _prune_stale(hits: deque[float], window: int, now: float) -> None:
    while hits and hits[0] <= now - window:
        hits.popleft()


def _purge_if_huge() -> None:
    """Drop idle keys when the table grows unbounded (many distinct IPs)."""
    if len(_HITS) <= _PURGE_ABOVE_KEYS:
        return
    now = time.monotonic()
    for key in [k for k, d in _HITS.items() if not d or d[-1] <= now - WEBHOOK_WINDOW_S]:
        del _HITS[key]


async def _send_429(send, retry_after: int) -> None:
    body = json.dumps({"detail": "rate limit exceeded"}).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
        (b"retry-after", str(retry_after).encode("ascii")),
    ]
    headers += [(name.encode("ascii"), value.encode("latin-1")) for name, value in SECURITY_HEADERS]
    await send({"type": "http.response.start", "status": 429, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class SecurityHeadersRateLimitMiddleware:
    """Adds the security headers to every response and enforces the two
    per-IP sliding-window budgets. Pure ASGI: responses stream through
    untouched, we only touch ``http.response.start``."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            # Fresh budgets per app boot (and per test-module TestClient).
            reset_rate_limits()
            await self.app(scope, receive, send)
            return
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        bucket, limit, window = _bucket_for(scope.get("method", "GET"), scope.get("path", ""))
        now = time.monotonic()
        _purge_if_huge()
        hits = _HITS.setdefault(_client_key(scope, bucket), deque())
        _prune_stale(hits, window, now)

        if len(hits) >= limit:
            # Oldest accepted hit must leave the window before a slot frees.
            retry_after = max(1, math.ceil(hits[0] + window - now))
            await _send_429(send, retry_after)
            return
        hits.append(now)

        await self.app(scope, receive, self._wrap_send(send))

    def _wrap_send(self, send):
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS:
                    headers[name] = value
            await send(message)

        return send_with_headers
