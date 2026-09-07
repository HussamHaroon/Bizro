"""Supplier verification handshake (schema.md §10) — endpoint contract tests.

The handshake is the one anti-fabrication anchor outside the merchant's
control: the DISTRIBUTOR confirms the purchase. These tests verify the
endpoint extracts the supplier phone (receipt_meta first, customer record
fallback), logs the request on the audit trail, and degrades politely when
no phone exists. Delivery is mock-safe in the test env.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.app.main import app
from server.app.db import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def _mk_photo_tx(phone: str | None, meta_phone: str | None = None):
    """Insert a merchant + a photo transaction with the given provenance."""
    from datetime import datetime, timezone

    from server.app.db import Customer, Merchant, OutboundMessage, Transaction, db_session

    with db_session() as s:
        m = Merchant(
            id=uuid.uuid4(), wa_id=f"92{uuid.uuid4().hex[:10]}",
            display_name="Forensics Store", created_at=datetime.now(timezone.utc),
        )
        s.add(m)
        s.flush()  # merchant row must exist before the customer FK
        cust = Customer(
            id=uuid.uuid4(), merchant_id=m.id, name="Al-Madina Distributors",
            phone=phone, created_at=datetime.now(timezone.utc),
        )
        s.add(cust)
        tx = Transaction(
            id=uuid.uuid4(), merchant_id=m.id, customer_id=cust.id,
            kind="expense", amount_pkr=2560.0, currency="PKR",
            description="Supplier purchase", item_lines=[],
            occurred_at=datetime.now(timezone.utc),
            source_type="photo",
            source_model="qwen-vl-ocr", confidence=0.9,
            raw_model_output={
                "receipt_meta": {
                    "bill_number": "4401",
                    "supplier_phone": meta_phone,
                    "exif_present": False,
                }
            },
            flag="none", status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        s.add(tx)
        s.commit()
        return str(m.id), str(tx.id), str(cust.id)


def test_verify_supplier_uses_receipt_meta_phone(client):
    _, tx_id, _ = _mk_photo_tx(phone="0421112222", meta_phone="03004567890")
    r = client.post(f"/api/transactions/{tx_id}/verify-supplier")
    assert r.status_code == 200
    body = r.json()
    assert body["queued"] is True
    assert body["to_last4"] == "7890"  # receipt_meta wins over customer record


def test_verify_supplier_falls_back_to_customer_phone(client):
    _, tx_id, _ = _mk_photo_tx(phone="0421112222", meta_phone=None)
    r = client.post(f"/api/transactions/{tx_id}/verify-supplier")
    assert r.status_code == 200
    assert r.json()["to_last4"] == "2222"


def test_verify_supplier_without_any_phone_is_422(client):
    _, tx_id, _ = _mk_photo_tx(phone=None, meta_phone=None)
    r = client.post(f"/api/transactions/{tx_id}/verify-supplier")
    assert r.status_code == 422
    assert "supplier phone" in r.json()["detail"]


def test_verify_supplier_request_is_on_audit_trail(client):
    from server.app.db import OutboundMessage, db_session

    _, tx_id, _ = _mk_photo_tx(phone="03001234567", meta_phone="03001234567")
    client.post(f"/api/transactions/{tx_id}/verify-supplier")
    with db_session() as s:
        rows = (
            s.query(OutboundMessage)
            .filter(
                OutboundMessage.transaction_id == uuid.UUID(tx_id),
                OutboundMessage.kind == "supplier_verification_request",
            )
            .all()
        )
    assert len(rows) == 1
    assert "Verification: did you sell" in rows[0].body
    assert "YES or NO" in rows[0].body
