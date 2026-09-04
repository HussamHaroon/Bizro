"""One-tap polite udhar reminder — POST /api/merchants/{id}/transactions/{tx}/reminder-draft.

Offline suite (bizro-testability): the model call is a monkeypatched
httpx.post — no network, no real key. LLM_GUARD_OFF=1 keeps the fake calls out
of the free-tier ledger (data/openrouter-usage.json), and llm_guard.allow/
record are additionally spied so the budget-guard wiring is observable.

Covers: happy path (draft returned verbatim, env-driven model + base URL +
key, prompt carries shop + purchase + untrusted-data guard, allow/record
called), 502 on AI failure (network error, non-200, empty output — the honest
failure the dashboard offers retry on), and the eligibility guards (409 for
non-udhar / rejected / settled customers, 404 wrong merchant, 400 bad uuid,
'me' sentinel).

Everything runs offline (MOCK_MODE=always) against the throwaway SQLite DB
pinned in conftest.py — never main's bizro.db.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from server.app.db import Merchant, db_session
from server.app.main import app

DRAFT = (
    "احمد بھائی، اداب! پچھلے ہفتے کھانے کا تیل 2500 روپے کا لیا تھا، "
    "جب آسان ہو بھجوا دیں۔ ہمیشہ کی طرح شکریہ! — Bismillah Karyana Store"
)


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    from server.app.db import init_db

    init_db()
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


@pytest.fixture(autouse=True)
def _live_env(monkeypatch):
    """Point the draft call at a fake OpenRouter and silence the free-tier
    ledger; the transport itself is replaced per-test."""
    monkeypatch.setenv("LLM_GUARD_OFF", "1")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-or-test")
    monkeypatch.setenv("DASHSCOPE_BASE_URL", "https://fake.openrouter.example/api/v1")
    monkeypatch.setenv("MODEL_REASONING", "minimax/minimax-test:free")


# ----------------------------------------------------------------- helpers


def _new_merchant(name: str = "Bismillah Karyana Store") -> uuid.UUID:
    with db_session() as s:
        m = Merchant(wa_id=f"92400{uuid.uuid4().hex[:8]}", display_name=name)
        s.add(m)
        s.commit()
        return m.id


def _seed_tx(
    merchant_id,
    kind: str = "udhar_given",
    amount: float = 2500.0,
    name: str = "احمد",
    status: str = "confirmed",
    description: str = "کھانے کا تیل 5 لیٹر",
) -> str:
    from server.app import dispatch as disp

    with db_session() as s:
        tx = disp.persist_transaction(
            s,
            s.get(Merchant, merchant_id),
            {
                "kind": kind,
                "amount_pkr": float(amount),
                "occurred_at": "2026-08-18T11:00:00+00:00",
                "counterparty": {"name": name, "phone": None},
                "description": description,
                "source": {"type": "manual", "media_id": None, "model": None,
                           "confidence": 0.95, "raw_output": {}},
                "status": status,
            },
            None,
        )
        return str(tx.id)


def _fake_model(content: str = DRAFT, status_code: int = 200):
    """Fake chat/completions transport; returns (post, calls)."""
    calls: list[dict] = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json})

        class R:
            text = "model exploded" if status_code != 200 else ""

            def __init__(self):
                self.status_code = status_code

            def json(self):
                return {
                    "choices": [{"message": {"content": content}}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 40},
                }

        return R()

    return fake_post, calls


def _post_draft(client: TestClient, merchant_id, tx_id: str):
    return client.post(f"/api/merchants/{merchant_id}/transactions/{tx_id}/reminder-draft")


# ============================== happy path ==============================


def test_reminder_draft_returns_the_model_draft(client, monkeypatch):
    mid = _new_merchant()
    tx_id = _seed_tx(mid)

    fake_post, calls = _fake_model()
    monkeypatch.setattr(httpx, "post", fake_post)

    allowed: list[str] = []
    recorded: list[str] = []
    import llm_guard

    monkeypatch.setattr(llm_guard, "allow", lambda model: allowed.append(model))
    monkeypatch.setattr(llm_guard, "record",
                        lambda model, usage=None: recorded.append(model))

    r = _post_draft(client, mid, tx_id)
    assert r.status_code == 200, r.text
    body = r.json()
    # Exact contract: the draft (cleaned, not re-worded), customer, amount.
    assert body == {"reminder": DRAFT, "customer": "احمد", "amount_pkr": 2500.0}

    # One OpenRouter-shaped call, env-driven: model from MODEL_REASONING.
    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == "https://fake.openrouter.example/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-or-test"
    assert call["json"]["model"] == "minimax/minimax-test:free"
    system, user = (m["content"] for m in call["json"]["messages"])
    assert "Bismillah Karyana Store" in system, "sign-off shop name in the system prompt"
    assert "NEVER threaten" in system
    assert "کھانے کا تیل" in user, "what they bought rides in the user payload"
    assert "UNTRUSTED" in user, "model-extracted strings are marked as data (bizro-security)"
    assert "2500" in user
    # Free-tier budget guard actually wired (D6-2).
    assert allowed == ["minimax/minimax-test:free"]
    assert recorded == ["minimax/minimax-test:free"]


def test_reminder_draft_me_sentinel_and_long_output_clamped(client, monkeypatch):
    """'me' resolves like every merchant route (D1-2); a runaway draft is cut
    back to a whole sentence instead of a mid-word stump."""
    r = client.get("/api/merchants")
    first = r.json()[0]
    tx_id = _seed_tx(uuid.UUID(first["id"]))

    runaway = "شکریہ۔ " * 200  # 1400 chars, sentence marks throughout
    fake_post, _ = _fake_model(content=runaway)
    monkeypatch.setattr(httpx, "post", fake_post)

    r = _post_draft(client, "me", tx_id)
    assert r.status_code == 200, r.text
    draft = r.json()["reminder"]
    assert len(draft) <= 600
    assert draft.endswith("۔"), "clamped at a sentence boundary, not mid-word"


# ============================== 502 AI-failure paths ==============================
# Drafts are never faked (D0-3): every model-side failure is an honest 502.


def test_reminder_draft_network_error_is_502_with_retry_hint(client, monkeypatch):
    mid = _new_merchant()
    tx_id = _seed_tx(mid)

    def down(url, headers=None, json=None, timeout=None):
        raise httpx.ConnectError("no route to host")

    monkeypatch.setattr(httpx, "post", down)
    r = _post_draft(client, mid, tx_id)
    assert r.status_code == 502
    assert "retry" in r.json()["detail"]


def test_reminder_draft_model_error_status_is_502(client, monkeypatch):
    mid = _new_merchant()
    tx_id = _seed_tx(mid)
    fake_post, _ = _fake_model(status_code=429)  # free-tier rate limit
    monkeypatch.setattr(httpx, "post", fake_post)
    r = _post_draft(client, mid, tx_id)
    assert r.status_code == 502
    assert "429" in r.json()["detail"]


def test_reminder_draft_empty_output_is_502(client, monkeypatch):
    mid = _new_merchant()
    tx_id = _seed_tx(mid)
    fake_post, _ = _fake_model(content="   ")
    monkeypatch.setattr(httpx, "post", fake_post)
    r = _post_draft(client, mid, tx_id)
    assert r.status_code == 502


def test_reminder_draft_missing_key_is_502_not_a_fake(client, monkeypatch):
    """No key (MOCK_MODE=always dev box) → 502, never a templated draft posing
    as AI output."""
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    mid = _new_merchant()
    tx_id = _seed_tx(mid)
    r = _post_draft(client, mid, tx_id)
    assert r.status_code == 502
    assert "DASHSCOPE_API_KEY" in r.json()["detail"]


# ============================== eligibility guards ==============================


def test_reminder_draft_rejects_non_udhar_kind(client, monkeypatch):
    mid = _new_merchant()
    tx_id = _seed_tx(mid, kind="sale", amount=900)
    monkeypatch.setattr(httpx, "post", _fake_model()[0])
    r = _post_draft(client, mid, tx_id)
    assert r.status_code == 409
    assert "udhar_given" in r.json()["detail"]


def test_reminder_draft_rejects_rejected_entry(client):
    mid = _new_merchant()
    tx_id = _seed_tx(mid, status="rejected")
    r = _post_draft(client, mid, tx_id)
    assert r.status_code == 409


def test_reminder_draft_rejects_settled_customer(client):
    """outstanding = Σ(given) − Σ(settlement) ≤ 0 → nothing to remind (§3)."""
    mid = _new_merchant()
    given = _seed_tx(mid, amount=1000)
    _seed_tx(mid, kind="udhar_settlement", amount=1000)
    r = _post_draft(client, mid, given)
    assert r.status_code == 409
    assert "settled" in r.json()["detail"]


def test_reminder_draft_partial_settlement_still_remindable(client, monkeypatch):
    mid = _new_merchant()
    given = _seed_tx(mid, amount=1000)
    _seed_tx(mid, kind="udhar_settlement", amount=400)  # 600 still outstanding
    fake_post, _ = _fake_model()
    monkeypatch.setattr(httpx, "post", fake_post)
    r = _post_draft(client, mid, given)
    assert r.status_code == 200
    assert r.json()["amount_pkr"] == 1000.0


def test_reminder_draft_id_handling(client, monkeypatch):
    mid = _new_merchant()
    tx_id = _seed_tx(mid)
    other_mid = _new_merchant()
    monkeypatch.setattr(httpx, "post", _fake_model()[0])

    assert _post_draft(client, mid, str(uuid.uuid4())).status_code == 404
    assert _post_draft(client, other_mid, tx_id).status_code == 404, \
        "another merchant's tx id must not leak existence"
    r = client.post(f"/api/merchants/{mid}/transactions/not-a-uuid/reminder-draft")
    assert r.status_code == 400
