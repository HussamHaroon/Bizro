"""Ledger integrity chain tests (schema.md §11).

The property under test: every row is sealed at insert; the chain detects
(amended rows, vanished rows) without ever rewriting a hash. Edits/deletes
leave HONEST breaks instead of silent rewrites.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from server.app.main import app
from server.app.db import Merchant, Transaction, init_db
from server.app.ledger import chain_tail, verify_chain
from server.app.db import db_session


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def _mk_merchant_and_txs(n: int = 3):
    with db_session() as s:
        m = Merchant(
            id=uuid.uuid4(), wa_id=f"92{uuid.uuid4().hex[:10]}",
            display_name="Chain Store", created_at=datetime.now(timezone.utc),
        )
        s.add(m)
        s.flush()
        from server.app.ledger import seal_transaction

        rows = []
        prev = None
        for i in range(n):
            from server.app.ledger import seal_transaction as _seal

            tx = Transaction(
                id=uuid.uuid4(), merchant_id=m.id, kind="sale",
                amount_pkr=1000.0 + i, currency="PKR", description=f"sale {i}",
                item_lines=[], occurred_at=datetime.now(timezone.utc),
                source_type="voice", confidence=0.9, flag="none", status="confirmed",
                created_at=datetime.now(timezone.utc) + timedelta(seconds=i),
                updated_at=datetime.now(timezone.utc),
            )
            seal_transaction(tx, prev)
            s.add(tx)
            prev = tx.entry_hash
            rows.append(tx)
        s.commit()
        return str(m.id), [str(t.id) for t in rows]


def test_chain_seals_on_insert_and_verifies_clean(client):
    mid, _ = _mk_merchant_and_txs(3)
    r = client.get(f"/api/merchants/{mid}/ledger/verify")
    assert r.status_code == 200
    out = r.json()
    assert out["valid"] is True
    assert out["checked"] == 3
    assert out["amended_after_sealing"] == []
    assert out["broken_at"] is None


def test_chain_links_each_row_to_previous(client):
    mid, tx_ids = _mk_merchant_and_txs(4)
    with db_session() as s:
        rows = (
            s.query(Transaction)
            .filter(Transaction.merchant_id == uuid.UUID(mid))
            .order_by(Transaction.created_at)
            .all()
        )
        assert rows[0].prev_entry_hash is None  # genesis row
        for prev_row, row in zip(rows, rows[1:]):
            assert row.prev_entry_hash == prev_row.entry_hash


def test_edit_is_detected_as_amended_not_hidden(client):
    mid, tx_ids = _mk_merchant_and_txs(3)
    # mutate a sealed row's amount BEHIND the API (simulating any later change)
    with db_session() as s:
        tx = s.get(Transaction, uuid.UUID(tx_ids[1]))
        tx.amount_pkr = 99999.0
        s.commit()
    out = client.get(f"/api/merchants/{mid}/ledger/verify").json()
    assert out["valid"] is False
    assert tx_ids[1] in out["amended_after_sealing"]


def test_delete_breaks_the_chain_at_the_right_point(client):
    mid, tx_ids = _mk_merchant_and_txs(4)
    with db_session() as s:
        s.query(Transaction).filter(Transaction.id == uuid.UUID(tx_ids[2])).delete()
        s.commit()
    out = client.get(f"/api/merchants/{mid}/ledger/verify").json()
    assert out["valid"] is False
    assert out["broken_at"] == tx_ids[3], "successor of the deleted row is where the gap shows"


def test_chain_tails_are_per_merchant(client):
    mid_a, _ = _mk_merchant_and_txs(2)
    mid_b, _ = _mk_merchant_and_txs(2)
    with db_session() as s:
        tail_a = chain_tail(s, uuid.UUID(mid_a))
        tail_b = chain_tail(s, uuid.UUID(mid_b))
    assert tail_a and tail_b and tail_a != tail_b


def test_backfill_is_idempotent(client):
    from server.app.db import _backfill_ledger_chain

    mid, tx_ids = _mk_merchant_and_txs(2)
    with db_session() as s:
        before = s.get(Transaction, uuid.UUID(tx_ids[0])).entry_hash
    _backfill_ledger_chain()  # unsealed-set is empty → no-op
    with db_session() as s:
        after = s.get(Transaction, uuid.UUID(tx_ids[0])).entry_hash
    assert before == after, "re-running the backfill must never re-seal"


def test_verify_endpoint_rejects_unknown_merchant(client):
    r = client.get(f"/api/merchants/{uuid.uuid4()}/ledger/verify")
    assert r.status_code == 404
