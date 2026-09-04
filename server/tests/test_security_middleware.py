"""Security middleware (server/app/middleware_security.py).

Covers:
- the four security headers on every response (checked on GET /health and
  on a rate-limited 429);
- the per-IP sliding-window limits: POST /webhook/whatsapp over its hourly
  budget → 429 + Retry-After + {"detail": "rate limit exceeded"}; the
  general bucket behaves the same (checked with a lowered env limit);
- the 31-POSTs-→-429 scenario from the security baseline, made fast by
  lowering RATE_LIMIT_WEBHOOK_PER_HOUR via monkeypatch (limits are read
  per request so no app reload is needed).

Offline (MOCK_MODE=always, throwaway SQLite per conftest.py). The middleware
clears its windows on lifespan startup, so this module's budget is fresh and
it leaves nothing behind for other modules.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.app.main import app
from server.app.middleware_security import reset_rate_limits

SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(self), microphone=(self)",
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db + clears limiter windows
        yield c


@pytest.fixture(autouse=True)
def _fresh_windows():
    """Order-independent tests: a clean budget per test, nothing leaked."""
    reset_rate_limits()
    yield
    reset_rate_limits()


def test_security_headers_on_every_response(client):
    r = client.get("/health")
    assert r.status_code == 200, r.text
    for name, expected in SECURITY_HEADERS.items():
        assert r.headers.get(name) == expected, f"missing/incorrect {name}"


def test_webhook_429_has_retry_after_json_body_and_headers(client, monkeypatch):
    """31st POST to the public webhook (limit lowered to 5 for speed) must be
    a 429 carrying Retry-After, the JSON detail, and the security headers."""
    monkeypatch.setenv("RATE_LIMIT_WEBHOOK_PER_HOUR", "5")

    statuses = [client.post("/webhook/whatsapp", json={}).status_code for _ in range(31)]

    assert statuses[:5] == [200] * 5, "under the limit every request is served"
    assert statuses.count(429) == 26, "every request over the limit is rejected"

    r = client.post("/webhook/whatsapp", json={})
    assert r.status_code == 429
    assert "retry-after" in r.headers, "client must be told when to come back"
    assert int(r.headers["retry-after"]) >= 1
    assert r.json() == {"detail": "rate limit exceeded"}
    for name, expected in SECURITY_HEADERS.items():
        assert r.headers.get(name) == expected, f"429 must also carry {name}"


def test_general_bucket_limits_non_webhook_traffic(client, monkeypatch):
    """Everything that is not a webhook POST shares the general per-minute
    budget — here lowered to 3 so the 4th /health call is rejected."""
    monkeypatch.setenv("RATE_LIMIT_GENERAL_PER_MIN", "3")

    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
    r = client.get("/health")
    assert r.status_code == 429
    assert "retry-after" in r.headers
    assert r.json() == {"detail": "rate limit exceeded"}


def test_webhook_and_general_buckets_are_independent(client, monkeypatch):
    """Exhausting the webhook hourly budget does not touch the general
    budget (and vice versa) — they are separate windows."""
    monkeypatch.setenv("RATE_LIMIT_WEBHOOK_PER_HOUR", "1")

    assert client.post("/webhook/whatsapp", json={}).status_code == 200
    assert client.post("/webhook/whatsapp", json={}).status_code == 429
    # general bucket untouched by the webhook hits
    assert client.get("/health").status_code == 200
