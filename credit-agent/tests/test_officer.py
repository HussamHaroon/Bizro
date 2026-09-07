"""Officer completeness metrics tests (schema.md §12).

Offline, deterministic. The four desk-check questions a karyana lender asks:
how old is the money owed (FIFO aging), how much credit came back (collection
rate), is one debtor too big (concentration), is the ledger still being kept
(weekly entries + activity drop). Frozen `now` makes ages exact.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.db_view import Base, Customer, Merchant, get_sessionmaker
from credit_agent.officer import compute_officer_metrics
from credit_agent.render import render_report_html
from credit_agent.report import generate_report

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def _cust(name="Ahmad"):
    return SimpleNamespace(name=name)


def _tx(kind="sale", amount=1000.0, days_ago=10, customer=None, status="confirmed"):
    return SimpleNamespace(
        kind=kind, amount_pkr=amount, status=status, customer_id=customer,
        occurred_at=NOW - timedelta(days=days_ago),
    )


# --- 1. receivables aging (FIFO per customer) ---------------------------------


def test_aging_buckets_from_occurred_at_vs_period_end():
    c1, c2 = uuid.uuid4(), uuid.uuid4()
    txs = [
        _tx("udhar_given", 1000.0, days_ago=10, customer=c1),   # 0-30
        _tx("udhar_given", 2000.0, days_ago=45, customer=c1),   # 31-60
        _tx("udhar_given", 3000.0, days_ago=75, customer=c2),   # 61-90
        _tx("udhar_given", 4000.0, days_ago=120, customer=c2),  # 90+
    ]
    out = compute_officer_metrics(txs, {c1: _cust("Ahmad"), c2: _cust("Bilal")}, NOW)
    buckets = {b["bucket"]: b for b in out["aging"]["buckets"]}
    assert buckets["0-30"]["total"] == 1000.0
    assert buckets["31-60"]["total"] == 2000.0
    assert buckets["61-90"]["total"] == 3000.0
    assert buckets["90+"]["total"] == 4000.0
    assert out["aging"]["total_outstanding"] == 10000.0
    assert {c["name"] for c in buckets["90+"]["customers"]} == {"Bilal"}


def test_settlements_pay_down_oldest_entry_first():
    c1 = uuid.uuid4()
    txs = [
        _tx("udhar_given", 1000.0, days_ago=100, customer=c1),  # fully settled
        _tx("udhar_given", 500.0, days_ago=95, customer=c1),    # fully settled
        _tx("udhar_given", 2000.0, days_ago=95, customer=c1),   # 1000 left → 90+ (age >90; exactly 90 is 61-90)
        _tx("udhar_settlement", 2500.0, days_ago=5, customer=c1),
    ]
    out = compute_officer_metrics(txs, {c1: _cust("Ahmad")}, NOW)
    buckets = {b["bucket"]: b for b in out["aging"]["buckets"]}
    assert buckets["90+"]["total"] == 1000.0
    assert buckets["0-30"]["total"] == 0.0
    assert out["aging"]["total_outstanding"] == 1000.0


# --- 2. collection rate --------------------------------------------------------


def test_collection_rate_is_settlements_over_credit_given():
    txs = [
        _tx("udhar_given", 4000.0, days_ago=20),
        _tx("udhar_settlement", 1000.0, days_ago=10),
        _tx("udhar_settlement", 1000.0, days_ago=3),
        _tx("sale", 9000.0),  # not credit — ignored
    ]
    out = compute_officer_metrics(txs, {}, NOW)
    assert out["collection"]["given_pkr"] == 4000.0
    assert out["collection"]["settled_pkr"] == 2000.0
    assert out["collection"]["rate"] == 0.5
    assert "50%" in out["collection"]["note_en"]


def test_collection_rate_is_none_when_no_credit_given():
    out = compute_officer_metrics([_tx("sale", 500.0)], {}, NOW)
    assert out["collection"]["rate"] is None
    assert "nothing to collect" in out["collection"]["note_en"]


# --- 3. top-debtor concentration -----------------------------------------------


def test_concentration_largest_and_top3_shares_with_warn():
    c = {cid: _cust(n) for cid, n in zip(
        (uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()),
        ("Big", "Mid", "Small", "Tiny"),
    )}
    txs = [
        _tx("udhar_given", 6000.0, days_ago=15, customer=list(c)[0]),  # Big 60%
        _tx("udhar_given", 2000.0, days_ago=15, customer=list(c)[1]),  # Mid 20%
        _tx("udhar_given", 1500.0, days_ago=15, customer=list(c)[2]),  # Small 15%
        _tx("udhar_given", 500.0, days_ago=15, customer=list(c)[3]),   # Tiny 5%
    ]
    out = compute_officer_metrics(txs, c, NOW)
    conc = out["concentration"]
    assert conc["top_debtor"] == "Big"
    assert conc["top_share"] == 60.0
    assert conc["top_3_share"] == 95.0
    assert conc["warn"] is True
    assert "60%" in conc["note_en"]


def test_no_concentration_warn_below_threshold():
    # three equal debtors: top share ~33% is under the 40% warning line
    ids = [uuid.uuid4() for _ in range(3)]
    names = {cid: _cust(n) for cid, n in zip(ids, ("A", "B", "C"))}
    txs = [_tx("udhar_given", 3000.0, days_ago=15, customer=cid) for cid in ids]
    out = compute_officer_metrics(txs, names, NOW)
    assert out["concentration"]["top_share"] == 33.3
    assert out["concentration"]["warn"] is False


# --- 4. weekly entries + activity drop ------------------------------------------


def test_activity_drop_when_latest_full_week_under_half_median():
    txs = []
    # windows 1..7 (0 = latest): steady 10/week inside each 7-day window
    # (half-day spacing keeps all 10 inside), latest week only 2
    for w in range(1, 8):
        for k in range(10):
            txs.append(_tx("sale", 100.0, days_ago=7 * w + 1 + k * 0.5))
    for k in range(2):
        txs.append(_tx("sale", 100.0, days_ago=k + 0.5))
    out = compute_officer_metrics(txs, {}, NOW)
    act = out["activity"]
    assert len(act["weeks"]) == 8
    assert act["eight_week_median"] == 10.0
    assert act["latest_full_week_count"] == 2
    assert act["activity_drop_pct"] == 80.0
    assert "slowed by 80%" in act["note_en"]


def test_no_activity_drop_when_keeping_steady():
    txs = [_tx("sale", 100.0, days_ago=7 * w) for w in range(8)]
    out = compute_officer_metrics(txs, {}, NOW)
    assert out["activity"]["activity_drop_pct"] is None
    assert "holding steady" in out["activity"]["note_en"]


def test_every_metric_carries_a_plain_english_note():
    txs = [_tx("sale", 100.0, days_ago=3),
           _tx("udhar_given", 900.0, days_ago=4),
           _tx("udhar_settlement", 400.0, days_ago=2)]
    out = compute_officer_metrics(txs, {}, NOW)
    for section in ("aging", "collection", "concentration", "activity"):
        assert out[section]["note_en"].strip(), f"{section} note missing"


def test_empty_ledger_gives_empty_structures_not_zeros_dressed_up():
    out = compute_officer_metrics([], {}, NOW)
    assert out["aging"]["total_outstanding"] == 0.0
    assert out["aging"]["note_en"] == "no outstanding udhar in this period"
    assert out["collection"]["rate"] is None
    assert out["concentration"]["top_debtor"] is None
    assert all(w["count"] == 0 for w in out["activity"]["weeks"])


# --- report + render integration -------------------------------------------------


def _db(tmp_path, name="t.db"):
    url = f"sqlite:///{tmp_path / name}"
    from sqlalchemy import create_engine

    Base.metadata.create_all(create_engine(url))
    return url


def test_report_carries_officer_block_and_renders_review_pack(tmp_path):
    url = _db(tmp_path)
    Session = get_sessionmaker(url)
    with Session() as s:
        m = Merchant(id=uuid.uuid4(), wa_id="wa", display_name="Pack Store")
        s.add(m)
        s.flush()
        c = Customer(id=uuid.uuid4(), merchant_id=m.id, name="Concentrated Cust")
        s.add(c)
        s.flush()
        now = datetime.now(timezone.utc)

        def add(kind, amount, days_ago, cust=None):
            from credit_agent.db_view import Transaction

            s.add(Transaction(
                id=uuid.uuid4(), merchant_id=m.id, customer_id=cust, kind=kind,
                amount_pkr=amount, description=kind,
                occurred_at=now - timedelta(days=days_ago),
                source_type="voice", source_media_id=uuid.uuid4(),
                source_model="qwen-flash", confidence=0.9, flag="none",
                status="confirmed",
            ))

        # 8 steady weeks of sales, then a thin latest week (dip; 0.5-day
        # offsets keep entries strictly inside the latest 7-day window)
        for w in range(1, 8):
            for k in range(10):
                add("sale", 500.0, 7 * w + 1 + k * 0.5)
        for k in range(2):
            add("sale", 500.0, k + 0.5)
        # aged udhar concentrated on one customer, partially settled
        add("udhar_given", 3000.0, 100, cust=c.id)
        add("udhar_given", 4000.0, 70, cust=c.id)
        add("udhar_settlement", 2000.0, 30, cust=c.id)
        s.commit()
        mid = m.id

    # period="all": a last-90-days window can never contain a 90+-day-old
    # entry, and this test must exercise every aging bucket
    report = generate_report(mid, period="all", db_url=url)
    off = report["officer"]
    assert off["aging"]["total_outstanding"] == 5000.0
    assert abs(off["collection"]["rate"] - 2000.0 / 7000.0) < 0.001
    assert off["concentration"]["top_share"] == 100.0
    assert off["activity"]["activity_drop_pct"] is not None

    html = render_report_html(report)
    assert "Officer review pack" in html
    assert "90+ days" in html and "61-90 days" in html
    assert "Concentrated Cust" in html
    assert "concentrated" in html          # warn chip at 100%
    assert "activity down" in html          # sparkline drop note
    # no raw ISO week stamps leak onto the printed artifact
    import re

    assert not re.search(r"\d{4}-\d{2}-\d{2}", html.split("Officer review pack")[-1])
