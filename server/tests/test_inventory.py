"""Derived inventory endpoint (GET /api/merchants/{id}/inventory) — offline,
deterministic, throwaway SQLite per conftest.py. Covers the inventory findings
doc's plan (server/app/INVENTORY_FINDINGS.md §e):

- empty merchant → empty items (never null, never an error)
- bought/sold math: expense = goods IN; sale + udhar_given = goods OUT;
  udhar_settlement = money-only, never counted; rejected rows excluded
- negative stock flagged (disclosure framing — §9 stock_coherence sibling)
- low-stock threshold: in_stock ≤ max(2, 10% of bought)
- case/whitespace-insensitive item merging via credit_agent._norm_item
- unknown merchant → 404 (invalid id → 400), 'me' sentinel resolves
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from server.app.db import Merchant, db_session
from server.app.main import app


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    from server.app.db import init_db

    init_db()
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


def _new_merchant(wa: str) -> str:
    with db_session() as s:
        m = Merchant(wa_id=wa, display_name="Inventory Test Store")
        s.add(m)
        s.commit()
        return str(m.id)


def _seed_tx(
    merchant_id: str,
    kind: str,
    amount: float,
    occurred_at: str,
    item_lines: list[dict] | None = None,
    status: str = "confirmed",
) -> None:
    """Seed through the PRODUCTION persist path (validation + sealing) so the
    rows are byte-identical to webhook-created ones."""
    from server.app import dispatch as disp

    with db_session() as s:
        disp.persist_transaction(
            s,
            s.get(Merchant, uuid.UUID(merchant_id)),
            {
                "kind": kind,
                "amount_pkr": float(amount),
                "occurred_at": occurred_at,
                "item_lines": item_lines or [],
                "source": {
                    "type": "manual",
                    "media_id": None,
                    "model": None,
                    "confidence": 0.95,
                    "raw_output": {},
                },
                "status": status,
            },
            None,
        )


def _get_inventory(client: TestClient, merchant_id: str) -> dict:
    r = client.get(f"/api/merchants/{merchant_id}/inventory")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"merchant_id", "items", "note"}, body
    assert body["note"], "note must always carry the honest derivation disclosure"
    return body


def _item(body: dict, name: str) -> dict:
    matches = [i for i in body["items"] if i["item"] == name]
    assert len(matches) == 1, (name, body["items"])
    return matches[0]


def test_empty_merchant_returns_empty_items(client):
    mid = _new_merchant(f"inv-empty-{uuid.uuid4().hex[:8]}")
    body = _get_inventory(client, mid)
    assert body["merchant_id"] == mid
    assert body["items"] == []


def test_bought_sold_math_and_money_only_udhar_settlement(client):
    mid = _new_merchant(f"inv-math-{uuid.uuid4().hex[:8]}")
    lines = [{"item": "chai patti", "qty": 10, "unit": "packet",
              "unit_price": 350, "line_total": 3500}]
    _seed_tx(mid, "expense", 3500, "2026-08-01T10:00:00+05:00", lines)          # goods IN 10
    _seed_tx(mid, "sale", 1050, "2026-08-02T10:00:00+05:00", [
        {"item": "chai patti", "qty": 3, "unit": "packet"}])                    # goods OUT 3
    _seed_tx(mid, "udhar_given", 700, "2026-08-03T10:00:00+05:00", [
        {"item": "chai patti", "qty": 2, "unit": "packet"}])                    # goods OUT 2
    # udhar_settlement is MONEY-only (schema.md §1): its lines must NOT subtract.
    _seed_tx(mid, "udhar_settlement", 700, "2026-08-04T10:00:00+05:00", [
        {"item": "chai patti", "qty": 99, "unit": "packet"}])
    # rejected rows never count (same exclusion as udhar radar / credit agent).
    _seed_tx(mid, "sale", 999, "2026-08-05T10:00:00+05:00", [
        {"item": "chai patti", "qty": 50, "unit": "packet"}], status="rejected")

    row = _item(_get_inventory(client, mid), "chai patti")
    assert row["bought"] == 10.0
    assert row["sold"] == 5.0
    assert row["in_stock"] == 5.0
    assert row["unit"] == "packet"
    assert row["flag"] == "ok"


def test_negative_stock_is_flagged_not_hidden(client):
    mid = _new_merchant(f"inv-neg-{uuid.uuid4().hex[:8]}")
    _seed_tx(mid, "expense", 1000, "2026-08-01T10:00:00+05:00", [
        {"item": "sugar 1kg", "qty": 10, "unit": "kg"}])
    _seed_tx(mid, "sale", 600, "2026-08-02T10:00:00+05:00", [
        {"item": "sugar 1kg", "qty": 6, "unit": "kg"}])
    _seed_tx(mid, "udhar_given", 600, "2026-08-03T10:00:00+05:00", [
        {"item": "sugar 1kg", "qty": 6, "unit": "kg"}])

    body = _get_inventory(client, mid)
    row = _item(body, "sugar 1kg")
    assert row["in_stock"] == -2.0
    assert row["flag"] == "negative"
    # Urgency order: the negative item sorts before healthy items.
    assert body["items"][0]["item"] == "sugar 1kg"


def test_low_stock_threshold_floor_and_share(client):
    mid = _new_merchant(f"inv-low-{uuid.uuid4().hex[:8]}")
    # in_stock 2, bought 20 → max(2, 10%·20 = 2) → exactly at threshold → low.
    _seed_tx(mid, "expense", 2000, "2026-08-01T10:00:00+05:00", [
        {"item": "atta 10kg bag", "qty": 20, "unit": "bag"}])
    _seed_tx(mid, "sale", 1800, "2026-08-02T10:00:00+05:00", [
        {"item": "atta 10kg bag", "qty": 18, "unit": "bag"}])
    # in_stock 90, bought 100 → 10% share (10) < 90 → ok.
    _seed_tx(mid, "expense", 900, "2026-08-01T10:00:00+05:00", [
        {"item": "dal masoor 1kg", "qty": 100, "unit": "kg"}])
    _seed_tx(mid, "sale", 90, "2026-08-02T10:00:00+05:00", [
        {"item": "dal masoor 1kg", "qty": 10, "unit": "kg"}])
    # Bought-4 item down to in_stock 2: the floor (2) catches what the 10%
    # share (0.4) would miss — small stockholders still get the warning.
    _seed_tx(mid, "expense", 400, "2026-08-01T10:00:00+05:00", [
        {"item": "tapal chai 200g", "qty": 4, "unit": "packet"}])
    _seed_tx(mid, "sale", 200, "2026-08-02T10:00:00+05:00", [
        {"item": "tapal chai 200g", "qty": 2, "unit": "packet"}])

    body = _get_inventory(client, mid)
    assert _item(body, "atta 10kg bag")["flag"] == "low"
    assert _item(body, "dal masoor 1kg")["flag"] == "ok"
    assert _item(body, "tapal chai 200g")["flag"] == "low"


def test_case_and_whitespace_insensitive_merging(client):
    mid = _new_merchant(f"inv-norm-{uuid.uuid4().hex[:8]}")
    _seed_tx(mid, "expense", 5000, "2026-08-01T10:00:00+05:00", [
        {"item": "  BASMATI   rice 5kg bag ", "qty": 6, "unit": "bag"}])
    _seed_tx(mid, "expense", 2000, "2026-08-02T10:00:00+05:00", [
        {"item": "Basmati Rice 5kg bag", "qty": 4, "unit": "bag"}])
    _seed_tx(mid, "sale", 1000, "2026-08-03T10:00:00+05:00", [
        {"item": "basmati rice 5kg BAG", "qty": 5, "unit": "bag"}])

    body = _get_inventory(client, mid)
    assert len(body["items"]) == 1, body["items"]
    row = body["items"][0]
    assert row["bought"] == 10.0
    assert row["sold"] == 5.0
    assert row["in_stock"] == 5.0


def test_lines_without_usable_qty_are_skipped(client):
    mid = _new_merchant(f"inv-noqty-{uuid.uuid4().hex[:8]}")
    _seed_tx(mid, "expense", 100, "2026-08-01T10:00:00+05:00", [
        {"item": "ghee tin", "qty": None, "unit": "tin"},
        {"item": "ghee tin", "qty": 0, "unit": "tin"},
        {"item": "ghee tin", "qty": 3, "unit": "tin"},
    ])
    row = _item(_get_inventory(client, mid), "ghee tin")
    assert row["bought"] == 3.0


def test_unknown_merchant_404_and_bad_id_400(client):
    r = client.get(f"/api/merchants/{uuid.uuid4()}/inventory")
    assert r.status_code == 404
    r = client.get("/api/merchants/not-a-uuid/inventory")
    assert r.status_code == 400


def test_me_sentinel_resolves(client):
    # 'me' → first merchant (ruling D1-2). Any seeded merchant satisfies it.
    r = client.get("/api/merchants/me/inventory")
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"merchant_id", "items", "note"}
