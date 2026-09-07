"""Language-switch commands: "tell me in english" / "urdu me batao" are meta
requests, never transactions (regression: they used to fall into the free-text
parser, which answered "how much was it?").

Covered here (offline, deterministic — conftest pins MOCK_MODE=always):
(a) the matcher accepts whole-message commands in both languages and REJECTS
    messages that merely contain the word (a real entry must still parse);
(b) switching with a live draft persists the preference and re-renders the
    pending confirmation in the requested language, buttons attached;
(c) switching without a pending entry answers with the plain ack;
(d) a message containing "english" but not being a command still parses."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.db import (
    Merchant,
    MerchantSettings,
    OutboundMessage,
    Transaction,
    db_session,
)
from server.app.lang import SWITCH_ACK_PAIR, language_switch_request
from server.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _text_payload(wa_id: str, body: str) -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Lang Test"}, "wa_id": wa_id}],
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


def _post(client, wa: str, body: str) -> dict:
    body_json = client.post("/webhook/whatsapp", json=_text_payload(wa, body)).json()
    return body_json["results"][0]


def _settings_lang(wa: str) -> str | None:
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa).one_or_none()
        if m is None:
            return None
        row = s.query(MerchantSettings).filter_by(merchant_id=m.id).one_or_none()
        return row.language if row else None


# ------------------------------------------------- (a) matcher unit checks


def test_switch_matcher_accepts_commands():
    assert language_switch_request("tell me in english") == "en"
    assert language_switch_request("Tell me in English.") == "en"
    assert language_switch_request("in english") == "en"
    assert language_switch_request("English please") == "en"
    assert language_switch_request("reply in english") == "en"
    assert language_switch_request("urdu") == "ur"
    assert language_switch_request("urdu me batao") == "ur"
    assert language_switch_request("اردو") == "ur"
    assert language_switch_request("انگریزی میں") == "en"


def test_switch_matcher_rejects_non_commands():
    assert language_switch_request("") is None
    assert language_switch_request("english book sold for 500") is None
    assert language_switch_request("Ahmad ko udhar diya") is None
    assert language_switch_request("what is english") is None
    assert language_switch_request("500") is None


# ------------------------------- (b) switch with a live draft re-renders it


def test_switch_to_english_resends_pending_confirmation(client, monkeypatch):
    monkeypatch.setenv("MOCK_SCENARIO", "clean_udhar")
    wa = _wa("92500")
    _post(client, wa, "Ahmad ko panch hazar ka udhar diya")
    r = _post(client, wa, "tell me in english")
    assert r["ok"] is True and r["language_switch"] == "en"
    assert "credit to" in r["reply"]  # English confirmation re-render
    assert r["sent"], "delivery result present"
    assert _settings_lang(wa) == "en"
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa).one()
        tx = (
            s.query(Transaction)
            .filter_by(merchant_id=m.id, status="pending")
            .order_by(Transaction.created_at.desc())
            .first()
        )
        assert tx is not None
        sent_row = (
            s.query(OutboundMessage)
            .filter_by(merchant_id=m.id, transaction_id=tx.id, kind="confirmation_text")
            .order_by(OutboundMessage.created_at.desc())
            .first()
        )
        assert sent_row is not None and sent_row.body == r["reply"]
        assert sent_row.payload and sent_row.payload.get("buttons")


def test_switch_to_urdu_resends_pending_confirmation(client, monkeypatch):
    monkeypatch.setenv("MOCK_SCENARIO", "clean_udhar")
    wa = _wa("92501")
    _post(client, wa, "Ahmad ko panch hazar ka udhar diya")
    r = _post(client, wa, "urdu me batao")
    assert r["ok"] is True and r["language_switch"] == "ur"
    assert "کیا یہ درست ہے؟" in r["reply"]
    assert _settings_lang(wa) == "ur"


# ------------------------------------------- (c) switch without a draft → ack


def test_switch_without_pending_gives_ack(client):
    wa = _wa("92502")
    r = _post(client, wa, "tell me in english")
    assert r["language_switch"] == "en"
    assert r["reply"] == SWITCH_ACK_PAIR[1]
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa).one()
        assert s.query(Transaction).filter_by(merchant_id=m.id).count() == 0


# ----------------- (d) message containing the word still parses as a tx


def test_message_containing_english_still_parses(client, monkeypatch):
    monkeypatch.setenv("MOCK_SCENARIO", "clean_udhar")
    wa = _wa("92503")
    r = _post(client, wa, "english wali kitab 500 ki bech di")
    assert "language_switch" not in r
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa).one()
        assert s.query(Transaction).filter_by(merchant_id=m.id).count() == 1
