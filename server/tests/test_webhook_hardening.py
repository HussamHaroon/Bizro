"""Webhook + boot hardening tests (§11): prod fail-closed, async ack mode,
trust-tier surface, cancel-command hook."""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.app.main import app
from server.app.config import Settings, _enforce_production_baseline
from server.app.db import Merchant, Transaction, db_session, init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _text_payload(wa_id: str, body: str) -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "T"}, "wa_id": wa_id}],
                    "messages": [{
                        "from": wa_id, "id": f"wamid.{uuid.uuid4().hex}",
                        "timestamp": "1755798180", "type": "text",
                        "text": {"body": body},
                    }],
                },
                "field": "messages",
            }],
        }],
    }


# --- prod fail-closed boot ----------------------------------------------------

def test_production_without_secrets_refuses_to_boot():
    s = Settings(
        env="production", whatsapp_app_secret="", whatsapp_verify_token="bizro-verify",
        dashscope_api_key="", mock_mode="auto",
    )
    with pytest.raises(RuntimeError) as exc:
        _enforce_production_baseline(s)
    assert "WHATSAPP_APP_SECRET" in str(exc.value)
    assert "WHATSAPP_VERIFY_TOKEN" in str(exc.value)


def test_production_with_secrets_boots():
    s = Settings(
        env="production", whatsapp_app_secret="real-secret",
        whatsapp_verify_token="custom-token", dashscope_api_key="sk-real",
    )
    _enforce_production_baseline(s)  # no raise


def test_dev_mode_never_guards():
    s = Settings(env="dev", whatsapp_app_secret="", whatsapp_verify_token="bizro-verify")
    _enforce_production_baseline(s)  # no raise


# --- trust tier surface ---------------------------------------------------------

def _mk_pending_tx():
    with db_session() as s:
        m = Merchant(
            id=uuid.uuid4(), wa_id=_wa("93"), display_name="Tier Store",
            created_at=datetime.now(timezone.utc),
        )
        s.add(m)
        s.flush()
        from server.app.ledger import seal_transaction

        tx = Transaction(
            id=uuid.uuid4(), merchant_id=m.id, kind="sale", amount_pkr=500.0,
            currency="PKR", description="t", item_lines=[],
            occurred_at=datetime.now(timezone.utc), source_type="manual",
            flag="none", status="pending",
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        seal_transaction(tx, None)  # realistic: production rows are sealed at insert
        s.add(tx)
        s.commit()
        return str(m.id), str(tx.id)


def test_wire_exposes_trust_tier_default_self_reported(client):
    mid, tx_id = _mk_pending_tx()
    r = client.get(f"/api/merchants/{mid}/transactions")
    assert r.status_code == 200
    rows = r.json() if isinstance(r.json(), list) else r.json().get("transactions", [])
    row = next(t for t in rows if t["id"] == tx_id)
    assert row["trust_tier"] == "self_reported"
    assert "entry_hash" in row  # §11 chain fields ride the wire


def test_patch_upgrades_trust_tier(client):
    _, tx_id = _mk_pending_tx()
    r = client.patch(
        f"/api/transactions/{tx_id}", json={"trust_tier": "customer_confirmed"}
    )
    assert r.status_code == 200
    assert r.json()["trust_tier"] == "customer_confirmed"
    # tier changes never touch the sealed hash (attestation, not ledger content)
    assert r.json()["entry_hash"] is not None


def test_verify_supplier_sets_third_party(client, monkeypatch):
    """The supplier handshake upgrades the expense row's tier."""
    with db_session() as s:
        m = Merchant(
            id=uuid.uuid4(), wa_id=_wa("94"), display_name="Sup Store",
            created_at=datetime.now(timezone.utc),
        )
        s.add(m)
        s.flush()
        from server.app.ledger import seal_transaction

        tx = Transaction(
            id=uuid.uuid4(), merchant_id=m.id, kind="expense", amount_pkr=2560.0,
            currency="PKR", description="Supplier purchase", item_lines=[],
            occurred_at=datetime.now(timezone.utc), source_type="photo",
            confidence=0.9, flag="none", status="pending",
            raw_model_output={"receipt_meta": {"supplier_phone": "03004567890"}},
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        seal_transaction(tx, None)
        s.add(tx)
        s.commit()
        mid, tx_id = str(m.id), str(tx.id)
    r = client.post(f"/api/transactions/{tx_id}/verify-supplier")
    assert r.status_code == 200
    row = client.get(f"/api/merchants/{mid}/transactions").json()
    rows = row if isinstance(row, list) else row.get("transactions", [])
    assert next(t for t in rows if t["id"] == tx_id)["trust_tier"] == "third_party"


# --- async webhook mode -----------------------------------------------------------

def test_async_mode_acks_then_processes(client, monkeypatch):
    monkeypatch.setenv("WEBHOOK_PROCESSING", "async")
    from server.app.config import get_settings

    get_settings.cache_clear()
    try:
        wa = _wa("95")
        r = client.post("/webhook/whatsapp", json=_text_payload(wa, "Ahmad ko 100 ka udhar"))
        assert r.status_code == 200
        assert r.json() == {"received": True}, "async must ack immediately"
        # TestClient runs BackgroundTasks synchronously post-response: the row
        # must exist by the time the call returns.
        with db_session() as s:
            n = (
                s.query(Transaction)
                .filter(Transaction.merchant_id == s.query(Merchant)
                        .filter(Merchant.wa_id == wa).one().id)
                .count()
            )
        assert n == 1, "ack-immediately must not lose the message"
    finally:
        get_settings.cache_clear()


# --- cancel-command hook -----------------------------------------------------------

def _fake_corrections(cancel_words: set[str]):
    mod = ModuleType("voice_agent.corrections")
    mod.is_cancel_command = lambda text: (text or "").strip().lower() in cancel_words
    mod.CANCEL_CONFIRMATION_REPLIES = {
        "en": "Done. Your last entry is cancelled.",
        "ur": "ہو گیا۔ آخری اندراج کینسل ہو گیا۔",
    }
    return mod


def test_cancel_command_rejects_latest_pending(client, monkeypatch):
    fake = _fake_corrections({"cancel last"})
    monkeypatch.setitem(sys.modules, "voice_agent.corrections", fake)
    wa = _wa("96")
    # seed one pending entry via the normal flow
    client.post("/webhook/whatsapp", json=_text_payload(wa, "Ahmad ko panch sau ka udhar diya"))
    with db_session() as s:
        mid = s.query(Merchant).filter(Merchant.wa_id == wa).one().id
        pending = (
            s.query(Transaction)
            .filter(Transaction.merchant_id == mid, Transaction.status == "pending")
            .count()
        )
    assert pending == 1
    # the cancel command itself must not create a transaction
    out = client.post("/webhook/whatsapp", json=_text_payload(wa, "cancel last")).json()["results"][0]
    assert out["ok"] is True and out["cancelled"] is True
    with db_session() as s:
        txs = s.query(Transaction).filter(Transaction.merchant_id == mid).all()
        assert len(txs) == 1, "cancel command must not parse as a transaction"
        assert txs[0].status == "rejected"


def test_cancel_with_nothing_pending_replies_not_crashes(client, monkeypatch):
    fake = _fake_corrections({"cancel last"})
    monkeypatch.setitem(sys.modules, "voice_agent.corrections", fake)
    wa = _wa("97")
    out = client.post("/webhook/whatsapp", json=_text_payload(wa, "cancel last")).json()["results"][0]
    assert out["ok"] is True and out["cancelled"] is False
    assert out["reply"]


def test_cancel_hook_inert_without_helper(client, monkeypatch):
    monkeypatch.setitem(sys.modules, "voice_agent.corrections", None)  # ImportError path
    wa = _wa("98")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "cancel last"))
    assert r.status_code == 200
    out = r.json()["results"][0]
    # without the helper, the text goes down the normal parse path (clarify)
    assert out.get("cancelled") is None
