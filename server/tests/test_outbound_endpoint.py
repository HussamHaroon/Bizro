"""GET /api/merchants/{id}/outbound — the simulator-chat + audit read side of
outbound_messages (schema.md §2).

Offline (MOCK_MODE=always), throwaway SQLite per conftest.py. Covers: the
{count, outbound} envelope, newest-first ordering, the §7.1 buttons round-trip
through the payload JSON column, the limit clamp, 'me' resolution, and the
404 for an unknown merchant id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server.app.db import Merchant, OutboundMessage, db_session
from server.app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def _seed_merchant(wa_id: str, display_name: str) -> str:
    with db_session() as s:
        m = Merchant(wa_id=wa_id, display_name=display_name)
        s.add(m)
        s.commit()
        return str(m.id)


def _insert_outbound(merchant_id: str, body: str, kind: str, minutes_ago: int,
                     buttons: list | None = None) -> str:
    with db_session() as s:
        row = OutboundMessage(
            merchant_id=uuid.UUID(merchant_id),
            kind=kind,
            body=body,
            payload={"buttons": buttons} if buttons is not None else None,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        )
        s.add(row)
        s.commit()
        return str(row.id)


def _cleanup_merchant(merchant_id: str) -> None:
    """Bulk-delete the outbound rows FIRST, then the merchant — one flush
    emits the parent DELETE before independent child rows (no relationship()
    between the mappers), which trips the FK constraint."""
    with db_session() as s:
        mid = uuid.UUID(merchant_id)
        s.query(OutboundMessage).filter_by(merchant_id=mid).delete()
        s.commit()
        m = s.get(Merchant, mid)
        if m is not None:
            s.delete(m)
            s.commit()


CONFIRM_BUTTONS = [
    {"type": "reply", "reply": {"id": "confirm", "title": "درست ہے"}},
    {"type": "reply", "reply": {"id": "correct", "title": "بدلیں"}},
]


def test_outbound_lists_merchant_messages_newest_first_with_buttons(client):
    wa = _wa("92410")
    mid = _seed_merchant(wa, "Outbound E2E")
    old_id = _insert_outbound(mid, "پہلا جواب", "clarification", minutes_ago=10)
    new_id = _insert_outbound(
        mid,
        "احمد کو 5000 روپے ادھر دیے۔ کیا یہ درست ہے؟",
        "confirmation_text",
        minutes_ago=1,
        buttons=CONFIRM_BUTTONS,
    )

    r = client.get(f"/api/merchants/{mid}/outbound")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) >= {"count", "outbound"}
    assert body["count"] == len(body["outbound"]) == 2

    rows = body["outbound"]
    assert [row["id"] for row in rows] == [new_id, old_id], "newest-first"

    newest = rows[0]
    for field in ("id", "transaction_id", "kind", "body", "buttons", "created_at"):
        assert field in newest, f"outbound row missing {field}"
    assert newest["kind"] == "confirmation_text"
    assert newest["body"].startswith("احمد کو 5000")
    assert newest["buttons"] == CONFIRM_BUTTONS, "§7.1 buttons must round-trip"
    assert newest["transaction_id"] is None
    assert rows[1]["buttons"] is None
    assert rows[1]["body"] == "پہلا جواب"

    _cleanup_merchant(mid)


def test_outbound_limit_and_me_resolution(client):
    wa = _wa("92411")
    mid = _seed_merchant(wa, "Outbound Limit")
    for i in range(3):
        _insert_outbound(mid, f"msg-{i}", "confirmation_text", minutes_ago=i)

    r = client.get(f"/api/merchants/{mid}/outbound?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert [row["body"] for row in body["outbound"]] == ["msg-0", "msg-1"]

    # 'me' (single-merchant demo resolution, D1-2) = the FIRST merchant by
    # created_at — the same row GET /api/merchants lists first. Whatever the
    # shared test DB's history, outbound('me') must 200 and, when 'me' IS our
    # seeded merchant, return exactly the same rows as the explicit id.
    first = client.get("/api/merchants").json()[0]["id"]
    assert client.get("/api/merchants/me/outbound").status_code == 200
    if first == mid:
        assert client.get("/api/merchants/me/outbound?limit=100").json() == \
            client.get(f"/api/merchants/{mid}/outbound?limit=100").json()

    _cleanup_merchant(mid)


def test_outbound_unknown_merchant_404_and_bad_uuid_400(client):
    assert client.get(f"/api/merchants/{uuid.uuid4()}/outbound").status_code == 404
    assert client.get("/api/merchants/not-a-uuid/outbound").status_code == 400


def test_outbound_limit_is_validated(client):
    r = client.get("/api/merchants/me/outbound?limit=0")
    assert r.status_code == 422
    r = client.get("/api/merchants/me/outbound?limit=500")
    assert r.status_code == 422
