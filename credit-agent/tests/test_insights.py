"""Merchant insights (credit_agent.insights) — offline, deterministic.

Covers the metric definitions in qa/reviews/2026-09-07-insights-findings.md:

- demand timing: best day + best window from sale + udhar_given item_lines,
  PKT dayparts (morning <12, afternoon 12-17, evening >=17), the UTC→PKT day
  edge, rejected rows excluded, below-threshold items dropped
- restock: consumes inventory flags (never re-derived here), ranked by recent
  weekly demand, ok-stock items absent
- price trends: first-half vs second-half medians → exact pct math, direction
  words, too-few-observations items excluded
- empty ledger → exactly the three empty lists, never invented
- generate_report integration: report["insights"] rides the payload AND the
  persisted credit_reports row; an empty merchant persists the empty shape
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.insights import compute_insights

SAT = datetime(2026, 8, 1)       # a Saturday (weekday 5)
SAT_1830_PKT = datetime(2026, 8, 1, 13, 30)   # naive UTC → 18:30 PKT (evening)
SAT_1000_PKT = datetime(2026, 8, 1, 5, 0)     # → 10:00 PKT (morning)
MON = datetime(2026, 7, 27)      # the Monday before (weekday 0)
MON_0900_PKT = datetime(2026, 7, 27, 4, 0)    # → 09:00 PKT (morning)
assert SAT.weekday() == 5 and MON.weekday() == 0


def _tx(kind, item_lines, occurred_at, status="confirmed", amount_pkr=100.0):
    return SimpleNamespace(
        kind=kind,
        item_lines=item_lines,
        occurred_at=occurred_at,
        status=status,
        amount_pkr=amount_pkr,
    )


def _line(item, qty, unit="packet", unit_price=None):
    return {"item": item, "qty": qty, "unit": unit, "unit_price": unit_price}


# --- demand timing -------------------------------------------------------------


def test_demand_best_day_best_window_and_weekly_rate():
    txs = [
        # chai patti: Saturday evening 4 units, Saturday morning 2, Monday 1
        _tx("sale", [_line("chai patti", 2)], SAT_1830_PKT),
        _tx("udhar_given", [_line("Chai PATTI", 2)], SAT_1830_PKT),  # merges via _norm_item
        _tx("sale", [_line("chai patti", 2)], SAT_1000_PKT),
        _tx("sale", [_line("chai patti", 1)], MON_0900_PKT),
        # dal: 3 units, all Saturday evening → second in the list
        _tx("sale", [_line("dal", 3, unit="kg")], SAT_1830_PKT),
        # cheeni: 2 units — below DEMAND_MIN_UNITS, a "best day" would be noise
        _tx("sale", [_line("cheeni", 2, unit="kg")], SAT_1830_PKT),
        # rejected rows never count
        _tx("sale", [_line("chai patti", 50)], SAT_1830_PKT, status="rejected"),
    ]
    out = compute_insights(txs)
    assert [d["item"] for d in out["demand_timing"]] == ["chai patti", "dal"]
    chai = out["demand_timing"][0]
    assert chai["best_day"] == "Saturday"
    assert chai["best_window"] == "evening"
    # span Mon 27 → Sat 1 inclusive = 6 days; 7 units × 7 / 6 = 8.2
    assert chai["weekly_units"] == 8.2
    assert chai["note"] == "Based on your last 6 days"
    assert out["demand_timing"][1]["best_day"] == "Saturday"
    # exactly the three keys — the shape is stable, empty or not
    assert set(out) == {"demand_timing", "restock_now", "price_trends"}


def test_demand_pkt_day_edge_utc_evening_is_next_pkt_morning():
    # 20:00 UTC Saturday = 01:00 PKT SUNDAY → Sunday morning, not Saturday evening
    txs = [_tx("sale", [_line("ghee 1kg", 5)], datetime(2026, 8, 1, 20, 0))]
    out = compute_insights(txs)
    row = out["demand_timing"][0]
    assert row["best_day"] == "Sunday"
    assert row["best_window"] == "morning"


def test_demand_afternoon_boundary_12_and_17():
    # hour 12 PKT → afternoon; hour 17 PKT → evening (>= 17)
    txs = [
        _tx("sale", [_line("cheeni", 2, unit="kg")], datetime(2026, 8, 1, 7, 0)),   # 12:00 PKT
        _tx("sale", [_line("cheeni", 3, unit="kg")], datetime(2026, 8, 1, 12, 0)),  # 17:00 PKT
    ]
    out = compute_insights(txs)
    row = out["demand_timing"][0]
    assert row["best_window"] == "evening"  # 3 units evening beats 2 afternoon


def test_demand_and_price_ignore_lineless_kinds():
    # udhar_settlement is money-only (schema.md §1) — lines must not count
    txs = [_tx("udhar_settlement", [_line("chai patti", 9)], SAT_1830_PKT)]
    out = compute_insights(txs)
    assert out["demand_timing"] == []


# --- restock -------------------------------------------------------------------


def _restock_fixture():
    inventory_items = [
        {"item": "sugar 1kg", "unit": "kg", "bought": 18.0, "sold": 20.0,
         "in_stock": -2.0, "flag": "negative"},
        {"item": "atta 10kg bag", "unit": "bag", "bought": 20.0, "sold": 18.0,
         "in_stock": 2.0, "flag": "low"},
        {"item": "dal masoor 1kg", "unit": "kg", "bought": 100.0, "sold": 10.0,
         "in_stock": 90.0, "flag": "ok"},
    ]
    # window 2026-05-03 → 2026-08-01 (91 days → 4.0 weeks); recent 28-day
    # cutoff = 2026-07-04: sugar sells 8 units inside it, atta none.
    txs = [
        _tx("sale", [], datetime(2026, 5, 3, 10, 0)),                    # widens the span only
        _tx("sale", [_line("sugar 1kg", 2, unit="kg")], datetime(2026, 7, 20, 10, 0)),
        _tx("sale", [_line("sugar 1kg", 6, unit="kg")], datetime(2026, 8, 1, 10, 0)),
        _tx("udhar_settlement", [_line("sugar 1kg", 50, unit="kg")], datetime(2026, 7, 25, 10, 0)),
    ]
    return txs, inventory_items


def test_restock_ranks_flagged_items_by_recent_weekly_demand():
    txs, inventory_items = _restock_fixture()
    out = compute_insights(txs, inventory_items=inventory_items)
    rows = out["restock_now"]
    assert [r["item"] for r in rows] == ["sugar 1kg", "atta 10kg bag"]  # ok-stock absent
    sugar = rows[0]
    assert sugar["in_stock"] == -2.0 and sugar["flag"] == "negative"
    assert sugar["weekly_demand"] == 2.0        # 8 recent units / 4.0 weeks
    assert rows[1]["weekly_demand"] == 0.0      # no recent lines → ranked last, still shown
    assert rows[1]["in_stock"] == 2.0
    # the money-only settlement line above must NOT have inflated demand


def test_restock_empty_without_inventory_items():
    txs, _ = _restock_fixture()
    # no inventory items passed (server package unreachable) → honest [], and
    # demand/price still compute from the same txs
    out = compute_insights(txs)
    assert out["restock_now"] == []
    assert set(out) == {"demand_timing", "restock_now", "price_trends"}


# --- price trends --------------------------------------------------------------


def _price_fixture():
    def e(day, price, item, qty=1):
        return _tx("expense", [_line(item, qty, unit="tin", unit_price=price)],
                   datetime(2026, 6, 1) + timedelta(days=day), amount_pkr=price * qty)

    return [
        e(0, 1000, "cooking oil 5l"), e(9, 1000, "cooking oil 5l"),
        e(44, 1080, "cooking oil 5l"), e(49, 1080, "cooking oil 5l"),
        e(4, 500, "dal masoor 1kg"), e(11, 500, "dal masoor 1kg"),
        e(39, 400, "dal masoor 1kg"), e(47, 400, "dal masoor 1kg"),
        # flat: 180 → 181 is +0.6%, inside the ±1% noise band → "flat"
        e(0, 180, "cheeni"), e(4, 180, "cheeni"), e(30, 181, "cheeni"), e(34, 181, "cheeni"),
        # one observation only → not a trend, excluded
        e(0, 620, "chai patti 950g"),
        # no usable unit_price → excluded
        _tx("expense", [_line("besan", 2, unit="kg")], datetime(2026, 6, 2)),
        # another single-observation item → excluded
        e(49, 1080, "ghee 1kg"),
    ]


def test_price_trends_median_math_direction_and_ranking():
    out = compute_insights(_price_fixture())
    rows = out["price_trends"]
    assert [r["item"] for r in rows] == ["dal masoor 1kg", "cooking oil 5l", "cheeni"]
    dal, oil, cheeni = rows
    assert (dal["first_median"], dal["second_median"], dal["pct_change"], dal["direction"]) == (
        500.0, 400.0, -20.0, "down")
    assert (oil["first_median"], oil["second_median"], oil["pct_change"], oil["direction"]) == (
        1000.0, 1080.0, 8.0, "up")
    assert cheeni["direction"] == "flat" and cheeni["pct_change"] == 0.6
    assert dal["unit"] == "tin"
    assert all(r["note"].startswith("Based on your last ") for r in rows)


def test_rejected_expense_rows_do_not_skew_prices():
    txs = _price_fixture()[:-1]  # drop the trailing decoy, add a rejected outlier
    txs.append(_tx("expense", [_line("cooking oil 5l", 1, unit="tin", unit_price=5000)],
                   datetime(2026, 7, 28), status="rejected"))
    oil = [r for r in compute_insights(txs)["price_trends"] if r["item"] == "cooking oil 5l"][0]
    assert oil["second_median"] == 1080.0 and oil["pct_change"] == 8.0


# --- empty / degenerate ledgers -------------------------------------------------


def test_empty_ledger_returns_exactly_three_empty_lists():
    assert compute_insights([]) == {"demand_timing": [], "restock_now": [], "price_trends": []}


def test_all_rejected_ledger_returns_three_empty_lists():
    txs = [_tx("sale", [_line("chai patti", 9)], SAT_1830_PKT, status="rejected")]
    assert compute_insights(txs) == {"demand_timing": [], "restock_now": [], "price_trends": []}


# --- generate_report integration ------------------------------------------------


def _seed_db(tmp_path):
    """Two merchants on a throwaway mirror DB: one with item_lines history,
    one empty — generate_report must carry insights for both shapes."""
    from sqlalchemy import create_engine

    from credit_agent.db_view import Base, Merchant, Transaction, get_sessionmaker

    db_url = f"sqlite:///{(tmp_path / 'insights_report.db').as_posix()}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = get_sessionmaker(db_url)
    with Session() as s:
        m = Merchant(id=uuid.uuid4(), wa_id="923000001111", display_name="Insights Report Store")
        s.add(m)
        s.flush()
        rows = [
            # restock: chai patti bought 10, sold 9 → in_stock 1 → low
            Transaction(id=uuid.uuid4(), merchant_id=m.id, kind="expense",
                        amount_pkr=3500.0, item_lines=[_line("chai patti", 10, unit_price=1000.0)],
                        occurred_at=datetime(2026, 6, 1, 6, 0), source_type="photo", status="confirmed"),
            Transaction(id=uuid.uuid4(), merchant_id=m.id, kind="sale",
                        amount_pkr=900.0, item_lines=[_line("chai patti", 4, unit_price=250.0)],
                        occurred_at=SAT_1830_PKT, source_type="voice", status="confirmed"),
            Transaction(id=uuid.uuid4(), merchant_id=m.id, kind="sale",
                        amount_pkr=900.0, item_lines=[_line("chai patti", 4, unit_price=250.0)],
                        occurred_at=SAT_1830_PKT + timedelta(days=7), source_type="voice",
                        status="confirmed"),
            Transaction(id=uuid.uuid4(), merchant_id=m.id, kind="sale",
                        amount_pkr=250.0, item_lines=[_line("chai patti", 1, unit_price=250.0)],
                        occurred_at=MON_0900_PKT + timedelta(days=7), source_type="voice",
                        status="confirmed"),
            # price: cooking oil 1000 → 1080
            Transaction(id=uuid.uuid4(), merchant_id=m.id, kind="expense",
                        amount_pkr=1000.0, item_lines=[_line("cooking oil 5l", 1, unit="tin", unit_price=1000.0)],
                        occurred_at=datetime(2026, 6, 1, 7, 0), source_type="photo", status="confirmed"),
            Transaction(id=uuid.uuid4(), merchant_id=m.id, kind="expense",
                        amount_pkr=1000.0, item_lines=[_line("cooking oil 5l", 1, unit="tin", unit_price=1000.0)],
                        occurred_at=datetime(2026, 6, 10, 7, 0), source_type="photo", status="confirmed"),
            Transaction(id=uuid.uuid4(), merchant_id=m.id, kind="expense",
                        amount_pkr=1080.0, item_lines=[_line("cooking oil 5l", 1, unit="tin", unit_price=1080.0)],
                        occurred_at=datetime(2026, 7, 15, 7, 0), source_type="photo", status="confirmed"),
            Transaction(id=uuid.uuid4(), merchant_id=m.id, kind="expense",
                        amount_pkr=1080.0, item_lines=[_line("cooking oil 5l", 1, unit="tin", unit_price=1080.0)],
                        occurred_at=datetime(2026, 7, 20, 7, 0), source_type="photo", status="confirmed"),
        ]
        s.add_all(rows)
        empty = Merchant(id=uuid.uuid4(), wa_id="923000002222", display_name="Empty Insights Store")
        s.add(empty)
        s.commit()
        return db_url, str(m.id), str(empty.id)


def test_generate_report_carries_insights_and_persists_them(tmp_path):
    from sqlalchemy import select

    from credit_agent.db_view import CreditReport, get_sessionmaker
    from credit_agent.report import generate_report

    db_url, mid, empty_mid = _seed_db(tmp_path)
    report = generate_report(mid, period="all", db_url=db_url)

    insights = report["insights"]
    assert set(insights) == {"demand_timing", "restock_now", "price_trends"}
    chai = [d for d in insights["demand_timing"] if d["item"] == "chai patti"]
    assert chai and chai[0]["best_day"] == "Saturday"
    # restock CONSUMES compute_inventory through the same session: chai patti
    # bought 10 − sold 9 → in_stock 1 → low flag → ranked into restock_now
    restock = {r["item"]: r for r in insights["restock_now"]}
    assert "chai patti" in restock
    assert restock["chai patti"]["in_stock"] == 1.0
    assert restock["chai patti"]["weekly_demand"] > 0
    oil = [p for p in insights["price_trends"] if p["item"] == "cooking oil 5l"]
    assert oil and oil[0]["direction"] == "up" and oil[0]["pct_change"] == 8.0

    # the PERSISTED row carries the same block (report_json rides to readers)
    Session = get_sessionmaker(db_url)
    with Session() as s:
        row = s.scalars(
            select(CreditReport).where(CreditReport.merchant_id == uuid.UUID(mid))
            .order_by(CreditReport.created_at.desc())
        ).first()
        assert row is not None
        assert row.report_json["insights"] == insights


def test_generate_report_empty_merchant_persists_empty_insights(tmp_path):
    from credit_agent.report import generate_report

    db_url, _mid, empty_mid = _seed_db(tmp_path)
    report = generate_report(empty_mid, period="all", db_url=db_url)
    assert report["insights"] == {"demand_timing": [], "restock_now": [], "price_trends": []}
