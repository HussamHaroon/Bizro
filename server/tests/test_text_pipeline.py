"""KILL-fix regression suite: typed WhatsApp TEXT messages must reach the ledger.

Before this block, POSTed text returned 200 but (a) was never parsed into a
transaction and (b) the reply went out via a bare whatsapp_client.send_text with
NO outbound_messages row — so the dashboard simulator (which renders replies by
polling GET /api/merchants/{id}/outbound) could never show a reply to a typed
message.

Covered here (bizro-testability: offline, deterministic, mock model — the
MOCK_MODE=always env pinned in conftest.py fakes the network call):
(a) a typed transaction creates a Transaction with source_type "text" AND an
    outbound row carrying the confirmation (visible on the simulator endpoint);
(b) the onboarding trigger still stores its two onboarding outbound rows;
(c) a garbage string stores a clarify outbound row and creates NO transaction;
(d) the confirm word "1" still confirms a pending tx (regression);
plus: contract-validation failure → clarify copy, model outage → busy copy
(never mixed up), and the server fallback for a missing voice-agent package.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.db import Merchant, OutboundMessage, Transaction, db_session
from server.app.main import app
from server.app.webhook import (
    MODEL_OUTAGE_REPLY_UR,
    ONBOARDING_SEQUENCE_UR,
    TEXT_PARSE_MISS_REPLY_UR,
)

TEXT_PIPELINE_KEY = "voice_agent.pipeline.process_transcript"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


# ----------------------------------------------------------------- helpers


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _text_payload(wa_id: str, body: str) -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Text Test"}, "wa_id": wa_id}],
                    "messages": [{
                        "from": wa_id,
                        "id": f"wamid.{uuid.uuid4().hex}",
                        "timestamp": "1755798180",
                        "type": "text",
                        "text": {"body": body},
                    }],
                },
                "field": "messages",
            }],
        }],
    }


def _merchant_id(wa: str) -> uuid.UUID | None:
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa).one_or_none()
        return m.id if m else None


def _outbound_rows(wa: str) -> list[OutboundMessage]:
    mid = _merchant_id(wa)
    if mid is None:
        return []
    with db_session() as s:
        return s.query(OutboundMessage).filter_by(merchant_id=mid).all()


def _transactions(wa: str) -> list[Transaction]:
    mid = _merchant_id(wa)
    if mid is None:
        return []
    with db_session() as s:
        return s.query(Transaction).filter_by(merchant_id=mid).all()


# ------------------------------------- (a) typed text → ledger + audit row


def test_text_transaction_persists_with_source_type_text(client, monkeypatch):
    monkeypatch.setenv("MOCK_SCENARIO", "clean_udhar")
    wa = _wa("92500")
    body = "Ahmad ko panch hazar ka udhar diya"
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, body))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True, out
    assert out["transaction_id"], "typed text must create a ledger entry"
    assert out["status"] == "pending"

    txs = _transactions(wa)
    assert len(txs) == 1
    tx = txs[0]
    assert tx.source_type == "text"
    assert tx.kind == "udhar_given"
    assert float(tx.amount_pkr) == 5000
    assert tx.source_media_id is None, "text messages have no media row"
    # the typed message itself is kept in the audit raw_output
    assert tx.raw_model_output.get("typed_text") == body

    # the confirmation must exist as an outbound row (simulator renders it)
    rows = _outbound_rows(wa)
    assert len(rows) == 1
    assert rows[0].kind == "confirmation_text"
    assert rows[0].transaction_id == tx.id
    assert rows[0].body == out["confirmation_ur"]
    assert "5000" in rows[0].body and "Is this correct?" in rows[0].body


def test_text_confirmation_visible_via_simulator_outbound_endpoint(client, monkeypatch):
    """The dashboard simulator polls GET /api/merchants/{id}/outbound — the
    confirmation for a typed message MUST show up there (the KILL defect)."""
    monkeypatch.setenv("MOCK_SCENARIO", "clean_udhar")
    wa = _wa("92501")
    r = client.post(
        "/webhook/whatsapp", json=_text_payload(wa, "Bilal ko do hazar udhar diya")
    )
    out = r.json()["results"][0]
    mid = out["merchant_id"]
    r2 = client.get(f"/api/merchants/{mid}/outbound")
    assert r2.status_code == 200, r2.text
    bodies = [row["body"] for row in r2.json()["outbound"]]
    assert out["confirmation_ur"] in bodies


# ------------------------------------------- (b) onboarding trigger intact


def test_onboarding_trigger_still_stores_onboarding_rows(client):
    wa = _wa("92502")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "hello"))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True and out["onboarding"] is True
    assert _transactions(wa) == [], "a greeting must not create a ledger entry"
    rows = _outbound_rows(wa)
    assert len(rows) == 2
    assert sorted(row.body for row in rows) == sorted(ONBOARDING_SEQUENCE_UR)
    assert all(row.kind == "onboarding" for row in rows)


# --------------------------------------- (c) garbage → clarify row, no tx


def test_garbage_text_stores_clarify_row_and_creates_no_transaction(client, monkeypatch):
    monkeypatch.setenv("MOCK_SCENARIO", "garbage_audio")
    wa = _wa("92503")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "asdfqwer !!! zzz"))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True, out
    assert out.get("rejected") is True and out.get("persisted") is False
    assert out["reply"] == TEXT_PARSE_MISS_REPLY_UR
    assert _transactions(wa) == [], "a parse miss must persist NOTHING"
    rows = _outbound_rows(wa)
    assert len(rows) == 1
    assert rows[0].body == TEXT_PARSE_MISS_REPLY_UR
    assert rows[0].kind == "clarification"
    assert rows[0].transaction_id is None


def test_non_transaction_text_gets_clarify_not_busy_copy(client, monkeypatch):
    """Honest failure classes: a readable-but-not-a-transaction message is a
    parse miss (clarify copy) — never the model-outage busy message."""
    monkeypatch.setenv("MOCK_SCENARIO", "unclear_kind")
    wa = _wa("92504")
    r = client.post(
        "/webhook/whatsapp", json=_text_payload(wa, "pichle mahine ka hisaab dikha")
    )
    out = r.json()["results"][0]
    assert out["ok"] is True and out.get("persisted") is False
    assert out["reply"] == TEXT_PARSE_MISS_REPLY_UR
    assert out["reply"] != MODEL_OUTAGE_REPLY_UR
    assert _transactions(wa) == []


# ------------------------------- validation failure → clarify, nothing stored


def test_contract_validation_failure_stores_clarify_row(client, monkeypatch):
    """A pipeline result violating the contract (absurd amount, §6.10) must not
    reach the ledger; the merchant gets the clarify copy with an audit row."""
    from server.app import dispatch as disp

    def absurd_pipeline(text, merchant, occurred_at):
        return {
            "kind": "sale",
            "amount_pkr": 100_000_000,  # over the 1-crore bound
            "occurred_at": occurred_at,
            "source": {"type": "text", "media_id": None, "model": None,
                       "confidence": 0.9, "raw_output": {"transcript": text}},
            "flag": "none",
            "status": "pending",
            "confirmation_ur": "Got it. 100000000 rupees cash sale. Is this correct?",
        }

    monkeypatch.setitem(disp._pipeline_cache, TEXT_PIPELINE_KEY, absurd_pipeline)
    wa = _wa("92505")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "sab bech diya"))
    out = r.json()["results"][0]
    assert out["ok"] is True and out.get("persisted") is False
    assert out["reply"] == TEXT_PARSE_MISS_REPLY_UR
    assert _transactions(wa) == []
    assert [row.body for row in _outbound_rows(wa)] == [TEXT_PARSE_MISS_REPLY_UR]


# --------------------------------- genuine outage → busy copy (and only then)


def test_model_outage_gets_busy_reply_with_audit_row(client, monkeypatch):
    from server.app import dispatch as disp

    def outage_pipeline(text, merchant, occurred_at):
        raise TimeoutError("model call timed out")

    monkeypatch.setitem(disp._pipeline_cache, TEXT_PIPELINE_KEY, outage_pipeline)
    wa = _wa("92506")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "Ahmad ko 500 diya"))
    out = r.json()["results"][0]
    assert out["ok"] is False and out["error"] == "model_outage"
    assert out["reply"] == MODEL_OUTAGE_REPLY_UR
    assert _transactions(wa) == [], "an outage must persist NOTHING"
    rows = _outbound_rows(wa)
    assert len(rows) == 1 and rows[0].body == MODEL_OUTAGE_REPLY_UR


# ---------------------------------------- (d) confirm-word regression: "1"


def test_confirm_word_1_still_confirms_pending_text_tx(client, monkeypatch):
    monkeypatch.setenv("MOCK_SCENARIO", "clean_udhar")
    wa = _wa("92507")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "Ahmad ko udhar diya"))
    tx_id = r.json()["results"][0]["transaction_id"]

    r2 = client.post("/webhook/whatsapp", json=_text_payload(wa, "1"))
    assert r2.status_code == 200, r2.text
    out2 = r2.json()["results"][0]
    assert out2["ok"] is True and out2["type"] == "text"

    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(tx_id)).status == "confirmed"
    # the confirm answer itself must also be stored (simulator renders it)
    bodies = [row.body for row in _outbound_rows(wa)]
    assert out2["reply"] in bodies


def test_reject_word_0_still_rejects_and_stores_reply(client, monkeypatch):
    monkeypatch.setenv("MOCK_SCENARIO", "clean_udhar")
    wa = _wa("92508")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "Ahmad ko udhar diya"))
    tx_id = r.json()["results"][0]["transaction_id"]
    out2 = client.post("/webhook/whatsapp", json=_text_payload(wa, "0")).json()["results"][0]
    with db_session() as s:
        assert s.get(Transaction, uuid.UUID(tx_id)).status == "rejected"
    assert any(row.body == out2["reply"] for row in _outbound_rows(wa))


def test_confirm_word_with_no_pending_tx_stores_polite_row(client):
    """'1' with nothing pending: polite reply, and — unlike before — it gets an
    outbound row, so the simulator can render it."""
    wa = _wa("92509")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "1"))
    out = r.json()["results"][0]
    assert out["ok"] is True
    assert "pending" in out["reply"]
    rows = _outbound_rows(wa)
    assert len(rows) == 1 and rows[0].body == out["reply"]


# ----------------------- server fallback when voice-agent package is missing


def test_dispatch_fallback_labels_mock_text_source(client, monkeypatch):
    from server.app import dispatch as disp
    from datetime import datetime, timezone

    monkeypatch.setitem(disp._pipeline_cache, TEXT_PIPELINE_KEY, None)
    wa = _wa("92510")
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name="Fallback Ctx")
        s.add(m)
        s.commit()
        mid = m.id
        data = disp.process_transcript(
            "Ahmad ko panch hazar diya", m, datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
        )
    assert data["source"]["type"] == "text"
    assert data["source"]["raw_output"]["mock"] is True
    assert data["source"]["confidence"] < 0.75  # stays pending, never auto-confirmed
    # and it persists through the normal path
    with db_session() as s:
        tx = disp.persist_transaction(s, s.get(Merchant, mid), data, None)
        assert tx.status == "pending"
        assert tx.source_type == "text"
