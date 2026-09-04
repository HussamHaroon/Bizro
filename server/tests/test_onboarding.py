"""Onboarding flow — a merchant's first-contact TEXT greeting ("hello", "hi",
"start", "help", or Urdu "ہیلو" / "شروع") must get the two-message Urdu
onboarding sequence stored as regular outbound_messages rows via the same
reply path as every other outbound (dispatch.send_reply), while any other
text must NOT trigger it.

Offline (MOCK_MODE=always) against the throwaway SQLite DB pinned in
conftest.py. Merchants are auto-upserted by the webhook itself (same pattern
as test_fix_block.py), so no manual merchant seeding is needed.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.db import Merchant, OutboundMessage, db_session
from server.app.main import app
from server.app.webhook import ONBOARDING_SEQUENCE_UR


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


# ----------------------------------------------------------------- helpers


def _text_payload(wa_id: str, body: str) -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Onboarding"}, "wa_id": wa_id}],
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


def _outbound_rows(wa_id: str) -> list[OutboundMessage]:
    with db_session() as s:
        m = s.query(Merchant).filter_by(wa_id=wa_id).one_or_none()
        if m is None:
            return []
        return s.query(OutboundMessage).filter_by(merchant_id=m.id).all()


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


# --------------------------------------- happy path: hello + ہیلو


@pytest.mark.parametrize("greeting", ["hello", "ہیلو"])
def test_onboarding_greeting_stores_two_message_sequence(client, greeting):
    wa = _wa("92300")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, greeting))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True, out
    assert out["onboarding"] is True
    assert out["replies"] == list(ONBOARDING_SEQUENCE_UR)

    rows = _outbound_rows(wa)
    assert len(rows) == 2, "onboarding must store exactly two outbound rows"
    stored = [row.body for row in rows]
    assert sorted(stored) == sorted(ONBOARDING_SEQUENCE_UR)
    assert all(row.kind == "onboarding" for row in rows)
    assert all(row.transaction_id is None for row in rows), (
        "onboarding rows are regular outbound messages, not tied to a transaction"
    )
    # regular outbound messages: no mock markers inside the stored bodies
    # (the only mock marker allowed is whatsapp_client's own send-result one)
    for body in stored:
        assert "mock" not in body.lower()
        assert "[mock" not in body.lower()


def test_onboarding_outbound_visible_via_rest_chat_view(client):
    """The stored onboarding rows must surface on the outbound audit/chat
    read side (GET /api/merchants/{id}/outbound)."""
    wa = _wa("92301")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "hello"))
    assert r.status_code == 200, r.text
    mid = r.json()["results"][0]["merchant_id"]
    r = client.get(f"/api/merchants/{mid}/outbound")
    assert r.status_code == 200, r.text
    bodies = [row["body"] for row in r.json()["outbound"]]
    assert sorted(bodies) == sorted(ONBOARDING_SEQUENCE_UR)


# ------------------------------- every trigger word, case-insensitive


@pytest.mark.parametrize(
    "greeting",
    ["hello", "Hello", "HELLO", "hElLo", "hi", "HI", "start", "START",
     "help", "Help", "HELP", "ہیلو", "شروع"],
)
def test_all_trigger_words_route_to_onboarding(client, greeting):
    wa = _wa("92302")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, greeting))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out.get("onboarding") is True, f"{greeting!r} must trigger onboarding"
    rows = _outbound_rows(wa)
    assert len(rows) == 2
    assert sorted(row.body for row in rows) == sorted(ONBOARDING_SEQUENCE_UR)


# ---------------------------------------- negative: normal text, no trigger


@pytest.mark.parametrize("text", ["hello world", "mera naam Ali hai", "کیا حال ہے"])
def test_non_trigger_text_does_not_onboard(client, text):
    wa = _wa("92303")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, text))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out["ok"] is True
    assert not out.get("onboarding"), f"{text!r} must NOT trigger onboarding"
    rows = _outbound_rows(wa)
    assert all(row.kind != "onboarding" for row in rows)
    assert not (set(row.body for row in rows) & set(ONBOARDING_SEQUENCE_UR)), (
        "no onboarding body may be stored for a non-trigger text"
    )


def test_trigger_words_with_surrounding_whitespace_still_match(client):
    """Trailing whitespace/newlines from typing must not break the greeting."""
    wa = _wa("92304")
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "  hello  "))
    assert r.status_code == 200, r.text
    out = r.json()["results"][0]
    assert out.get("onboarding") is True
    assert len(_outbound_rows(wa)) == 2
