"""GET /api/merchants/{id}/insights — offline, deterministic, throwaway SQLite
per conftest.py. Covers qa/reviews/2026-09-07-insights-findings.md §d:

- empty merchant → exactly three empty lists (never invented, never an error)
- demand best-day/best-window correctness from seeded item_lines (PKT dayparts)
- restock ranking includes a low-stock item (CONSUMES compute_inventory — no
  duplicated stock math) and ranks by recent weekly demand
- price pct math: first-half vs second-half medians → exact pct + direction
- unknown merchant → 404 (invalid id → 400), 'me' sentinel resolves

Rows are seeded RELATIVE TO NOW on specific PKT weekdays so they stay inside
the endpoint's rolling 90-day window forever — fixed calendar dates would
silently fall out of the window as the demo clock moves.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server.app.db import Merchant, db_session
from server.app.main import app

PKT = timezone(timedelta(hours=5))


@pytest.fixture(scope="module", autouse=True)
def _db_ready():
    from server.app.db import init_db

    init_db()
    yield


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # lifespan runs init_db
        yield c


def _new_merchant(name: str) -> str:
    with db_session() as s:
        m = Merchant(wa_id=f"insights-{uuid.uuid4().hex[:8]}", display_name=name)
        s.add(m)
        s.commit()
        return str(m.id)


def _seed_tx(
    merchant_id: str,
    kind: str,
    amount: float,
    occurred_at: str,
    item_lines: list[dict] | None = None,
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
                "status": "confirmed",
            },
            None,
        )


def _pkt_iso(target_dow: int, hour_pkt: int, weeks_back: int = 0) -> str:
    """ISO instant at `hour_pkt` PKT on the most recent `target_dow` weekday
    (optionally `weeks_back` whole weeks earlier), always strictly in the past
    and therefore inside the endpoint's rolling 90-day window."""
    now_p = datetime.now(PKT)
    d = now_p - timedelta(days=(now_p.weekday() - target_dow) % 7, weeks=weeks_back)
    cand = d.replace(hour=hour_pkt, minute=0, second=0, microsecond=0)
    if cand >= now_p:  # same-day future hour — drop a week
        cand -= timedelta(weeks=1)
    return cand.isoformat()


def _get_insights(client: TestClient, merchant_id: str) -> dict:
    r = client.get(f"/api/merchants/{merchant_id}/insights")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"demand_timing", "restock_now", "price_trends"}, body
    return body


def test_empty_merchant_returns_exactly_three_empty_lists(client):
    mid = _new_merchant("Insights Empty Store")
    body = _get_insights(client, mid)
    assert body == {"demand_timing": [], "restock_now": [], "price_trends": []}


def test_demand_best_day_and_window_from_seeded_lines(client):
    mid = _new_merchant("Insights Demand Store")
    # chai patti: Saturday 18:30 PKT ×3 sales (6 units, evening), Saturday
    # 10:00 PKT (2 units, morning), Monday 09:00 PKT (1 unit, morning).
    for _ in range(3):
        _seed_tx(mid, "sale", 700, _pkt_iso(5, 18, 1),
                 [{"item": "chai patti", "qty": 2, "unit": "packet"}])
    _seed_tx(mid, "sale", 700, _pkt_iso(5, 10, 1),
             [{"item": "chai patti", "qty": 2, "unit": "packet"}])
    _seed_tx(mid, "sale", 350, _pkt_iso(0, 9, 1),
             [{"item": "chai patti", "qty": 1, "unit": "packet"}])
    # a money-only settlement with lines must NOT feed demand (schema.md §1)
    _seed_tx(mid, "udhar_settlement", 900, _pkt_iso(2, 12, 1),
             [{"item": "chai patti", "qty": 99, "unit": "packet"}])

    body = _get_insights(client, mid)
    rows = body["demand_timing"]
    assert rows, "seeded demand must produce at least one row"
    chai = next(r for r in rows if r["item"] == "chai patti")
    assert chai["best_day"] == "Saturday"
    assert chai["best_window"] == "evening"  # 6 evening units beat 3 morning
    assert chai["weekly_units"] > 0
    assert chai["note"].startswith("Based on your last ")


def test_restock_includes_low_stock_item_ranked_by_recent_demand(client):
    mid = _new_merchant("Insights Restock Store")
    # sugar: bought 10, sold 6+6 → in_stock −2 negative; 12 recent units
    _seed_tx(mid, "expense", 1000, _pkt_iso(1, 10, 2),
             [{"item": "sugar 1kg", "qty": 10, "unit": "kg", "unit_price": 100}])
    _seed_tx(mid, "sale", 600, _pkt_iso(3, 12),
             [{"item": "sugar 1kg", "qty": 6, "unit": "kg"}])
    _seed_tx(mid, "udhar_given", 600, _pkt_iso(4, 15),
             [{"item": "sugar 1kg", "qty": 6, "unit": "kg"}])
    # chai patti: bought 10, sold 9 → in_stock 1 ≤ max(2, 1) → low; 9 recent units
    _seed_tx(mid, "expense", 3500, _pkt_iso(1, 11, 2),
             [{"item": "chai patti", "qty": 10, "unit": "packet", "unit_price": 350}])
    _seed_tx(mid, "sale", 3150, _pkt_iso(3, 14),
             [{"item": "chai patti", "qty": 9, "unit": "packet"}])
    # dal: healthy stock (90 of 100) → must NOT appear in restock_now
    _seed_tx(mid, "expense", 1000, _pkt_iso(1, 10, 2),
             [{"item": "dal masoor 1kg", "qty": 100, "unit": "kg", "unit_price": 10}])
    _seed_tx(mid, "sale", 100, _pkt_iso(3, 12),
             [{"item": "dal masoor 1kg", "qty": 10, "unit": "kg"}])

    body = _get_insights(client, mid)
    rows = body["restock_now"]
    names = [r["item"] for r in rows]
    assert "sugar 1kg" in names and "chai patti" in names
    assert "dal masoor 1kg" not in names
    sugar = next(r for r in rows if r["item"] == "sugar 1kg")
    chai = next(r for r in rows if r["item"] == "chai patti")
    assert sugar["in_stock"] == -2.0 and chai["in_stock"] == 1.0
    # ranked by recent weekly demand: 12 units beats 9 regardless of flag order
    assert names.index("sugar 1kg") < names.index("chai patti")
    assert sugar["weekly_demand"] > chai["weekly_demand"] > 0


def test_price_trends_pct_math_and_direction(client):
    mid = _new_merchant("Insights Price Store")
    # cooking oil 5L: 2 old receipts @1000, 2 recent @1080 → +8.0% up
    for weeks in (11, 10):
        _seed_tx(mid, "expense", 1000, _pkt_iso(5, 10, weeks),
                 [{"item": "cooking oil 5l", "qty": 1, "unit": "tin", "unit_price": 1000}])
    for weeks in (1, 0):
        _seed_tx(mid, "expense", 1080, _pkt_iso(0, 12, weeks),
                 [{"item": "cooking oil 5l", "qty": 1, "unit": "tin", "unit_price": 1080}])
    # dal masoor 1kg: 500 → 400 → −20.0% down (bigger move → listed first)
    for weeks in (11, 10):
        _seed_tx(mid, "expense", 500, _pkt_iso(5, 11, weeks),
                 [{"item": "dal masoor 1kg", "qty": 1, "unit": "kg", "unit_price": 500}])
    for weeks in (1, 0):
        _seed_tx(mid, "expense", 400, _pkt_iso(0, 13, weeks),
                 [{"item": "dal masoor 1kg", "qty": 1, "unit": "kg", "unit_price": 400}])
    # a single receipt is not a trend — absent
    _seed_tx(mid, "expense", 620, _pkt_iso(2, 10, 1),
             [{"item": "chai patti 950g", "qty": 1, "unit": "packet", "unit_price": 620}])

    body = _get_insights(client, mid)
    rows = body["price_trends"]
    by_item = {r["item"]: r for r in rows}
    assert "chai patti 950g" not in by_item
    dal = by_item["dal masoor 1kg"]
    oil = by_item["cooking oil 5l"]
    assert (dal["first_median"], dal["second_median"], dal["pct_change"], dal["direction"]) == (
        500.0, 400.0, -20.0, "down")
    assert (oil["first_median"], oil["second_median"], oil["pct_change"], oil["direction"]) == (
        1000.0, 1080.0, 8.0, "up")
    assert abs(dal["pct_change"]) > abs(oil["pct_change"])
    assert rows.index(dal) < rows.index(oil)


def test_unknown_merchant_404_and_bad_id_400(client):
    r = client.get(f"/api/merchants/{uuid.uuid4()}/insights")
    assert r.status_code == 404
    r = client.get("/api/merchants/not-a-uuid/insights")
    assert r.status_code == 400


def test_me_sentinel_resolves(client):
    r = client.get("/api/merchants/me/insights")
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"demand_timing", "restock_now", "price_trends"}
