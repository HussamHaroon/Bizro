"""Two-factor customer confirmation tests (schema.md §13) — the demo showpiece.

The story under test: merchant records an entry naming a customer with a phone
→ the CUSTOMER's WhatsApp gets a ping → the customer's own YES/NO reply flips
or rejects that entry → the shopkeeper is alerted on NO. Merchant messages are
never mistaken for customer confirmations, and customer pings never break the
shopkeeper flow.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.app.db import Customer, Merchant, Transaction, db_session, init_db
from server.app.main import app


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def _wa(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def _mk_merchant_with_customer(phone: str | None):
    from server.app.ledger import seal_transaction

    with db_session() as s:
        m = Merchant(
            id=uuid.uuid4(), wa_id=_wa("97"), display_name="Two-Factor Store",
            created_at=datetime.now(timezone.utc),
        )
        s.add(m)
        s.flush()
        cust = Customer(
            id=uuid.uuid4(), merchant_id=m.id, name="Ahmad",
            phone=phone, created_at=datetime.now(timezone.utc),
        )
        s.add(cust)
        s.flush()
        tx = Transaction(
            id=uuid.uuid4(), merchant_id=m.id, customer_id=cust.id,
            kind="udhar_given", amount_pkr=5000.0, currency="PKR",
            description="udhar", item_lines=[],
            occurred_at=datetime.now(timezone.utc), source_type="manual",
            flag="none", status="pending",
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        seal_transaction(tx, None)
        s.add(tx)
        s.commit()
        return str(m.id), str(tx.id), cust.phone


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


def _txs(mid):
    with db_session() as s:
        rows = s.query(Transaction).filter(
            Transaction.merchant_id == uuid.UUID(mid)).all()
        return [(str(t.id), t.status, t.trust_tier, float(t.amount_pkr)) for t in rows]


def test_customer_ping_sent_when_phone_on_file(client):
    # merchant sends a udhar note via the text path. The mock pipeline returns
    # counterparty احمد carrying the phone the merchant "spoke" — persist
    # creates a NEW customer row from that counterparty (the spoken Urdu name
    # never ilike-matches the seeded Latin "Ahmad" row), and THE NEW ROW gets
    # the ping: whoever the merchant named is pinged at the number they spoke.
    mid, _, _ = _mk_merchant_with_customer("923001112233")
    r = client.post("/webhook/whatsapp", json=_text_payload(_wa("97m"), "Ahmad ko panch hazar ka udhar diya"))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert out["ok"] is True
    pings = [p for p in out.get("customer_pings", []) if p.get("pinged")]
    assert pings, "customer with phone must be pinged"
    ping = pings[0]
    assert "PKR 5,000" in ping["body"]
    assert "Reply YES" in ping["body"]
    # evidence: WHICH customer row received the ping
    assert ping["customer"] == "احمد"
    assert ping["to"] == "923001112233"
    with db_session() as s:
        # the text came from a fresh wa_id → the webhook upserted a NEW merchant;
        # the counterparty row (and the ping) belong to THAT merchant
        rows = (
            s.query(Customer)
            .filter(Customer.merchant_id == uuid.UUID(out["merchant_id"]))
            .all()
        )
        by_name = {c.name: c.phone for c in rows}
        # exactly one row: created from the spoken counterparty + spoken phone
        assert by_name == {"احمد": "923001112233"}
        tx = s.get(Transaction, uuid.UUID(ping["transaction_id"]))
        cust = s.get(Customer, tx.customer_id)
        assert (cust.name, cust.phone) == ("احمد", "923001112233"), (
            "the ping targets the counterparty row built from the spoken phone, "
            "not any pre-seeded ledger customer"
        )


def test_no_ping_without_phone(client, monkeypatch):
    # counterparty WITHOUT a phone: the sale_with_items mock returns Bilal with
    # phone=None — a pingeable kind (sale), skipped exactly at the phone check
    # → zero pings. (clean_udhar now carries a spoken phone by design — it is
    # the §13 demo scenario — so the no-phone case pins its own scenario.)
    monkeypatch.setenv("MOCK_SCENARIO", "sale_with_items")
    mid, _, _ = _mk_merchant_with_customer(None)
    # text from the merchant's own wa_id is needed — use a fresh merchant text flow
    with db_session() as s:
        m = s.get(Merchant, uuid.UUID(mid))
        wa = m.wa_id
    r = client.post("/webhook/whatsapp", json=_text_payload(wa, "Bilal ne pandrah sau ka saman cash liya"))
    assert r.status_code == 200
    assert r.json()["results"][0].get("customer_pings", []) == []


def test_customer_yes_confirms_and_upgrades_tier(client):
    mid, tx_id, phone = _mk_merchant_with_customer("923005556666")
    r = client.post("/webhook/whatsapp", json=_text_payload(phone, "YES"))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert out["customer_reply"] == "yes" and out["confirmed"] is True
    rows = _txs(mid)
    assert rows[0][1] == "confirmed"
    assert rows[0][2] == "customer_confirmed"
    # §12 integration: the report/corroboration path consumes the upgraded
    # customer_confirmed tier without error (demo proof: YES → report still runs).
    rp = client.get(f"/api/merchants/{mid}/report/preview")
    assert rp.status_code == 200, rp.text
    report = rp.json().get("report")
    assert isinstance(report, dict)
    assert isinstance(report.get("trust"), dict), (
        "the corroboration block must run over the ledger that now carries a "
        "customer_confirmed entry"
    )


def test_customer_no_flags_and_alerts_shopkeeper(client):
    mid, tx_id, phone = _mk_merchant_with_customer("923007778888")
    r = client.post("/webhook/whatsapp", json=_text_payload(phone, "NO ghalat hai"))
    assert r.status_code == 200
    out = r.json()["results"][0]
    assert out["confirmed"] is False
    rows = _txs(mid)
    assert rows[0][1] == "pending"  # stays for the shopkeeper to correct
    assert rows[0][2] in (None, "self_reported")
    assert any("incorrect" in (r_ or "") for r_ in [out["reply"]]) or "incorrect" in out["reply"]


def test_customer_confirmation_never_parses_as_transaction(client):
    mid, _, phone = _mk_merchant_with_customer("923009990000")
    before = len(_txs(mid))
    client.post("/webhook/whatsapp", json=_text_payload(phone, "yes"))
    assert len(_txs(mid)) == before, "a bare YES must never create an entry"


def test_merchant_wa_id_is_never_treated_as_customer(client):
    mid, _, _ = _mk_merchant_with_customer("923001112233")
    with db_session() as s:
        wa = s.get(Merchant, uuid.UUID(mid)).wa_id
    out = client.post("/webhook/whatsapp", json=_text_payload(wa, "yes")).json()["results"][0]
    assert out.get("customer_reply") is None, "merchant's own YES must go down the normal path"


def test_customer_with_no_pending_gets_polite_reply(client):
    # dedicated merchant + customer pair with NO transactions at all
    with db_session() as s:
        m = Merchant(
            id=uuid.uuid4(), wa_id=_wa("99"), display_name="Empty Store",
            created_at=datetime.now(timezone.utc),
        )
        s.add(m)
        s.flush()
        s.add(Customer(
            id=uuid.uuid4(), merchant_id=m.id, name="Nasir",
            phone="923004443333", created_at=datetime.now(timezone.utc),
        ))
        s.commit()
    out = client.post("/webhook/whatsapp", json=_text_payload("923004443333", "YES")).json()["results"][0]
    assert out["applied"] is False
    assert "Nothing is waiting" in out["reply"]
