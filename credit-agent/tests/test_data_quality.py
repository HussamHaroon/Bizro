"""Data-quality & consistency indicator tests — the HONEST verifier subset.

These indicators are DISCLOSURES computed from ledger internals (created_at vs
occurred_at, item_lines arithmetic, provenance). The tests lock the boundaries:
a healthy ledger stays clean; each specific inconsistency is caught; nothing
here ever produces a "trust score" or an accusation of intent.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.data_quality import (
    BACKFILL_LAG_DAYS,
    BURST_MIN_ENTRIES,
    SPIKE_FACTOR,
    compute_data_quality,
)


NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def _tx(days_ago=30, kind="sale", amount=1000.0, created_days_ago=None,
        source="voice", item_lines=None):
    occurred = NOW - timedelta(days=days_ago)
    created = NOW - timedelta(days=created_days_ago if created_days_ago is not None else days_ago)
    return type("T", (), {
        "kind": kind, "amount_pkr": amount, "source_type": source,
        "occurred_at": occurred, "created_at": created,
        "item_lines": item_lines, "status": "confirmed",
    })()


def test_empty_ledger_clean_and_never_crashes():
    dq = compute_data_quality([], now=NOW)
    assert dq["backfill"]["count"] == 0
    assert dq["stock_coherence"]["violations"] == []
    assert dq["indicators"] == []
    assert dq["provenance"]["photo_pct"] == 0.0


def test_healthy_ledger_has_no_indicators():
    txs = [
        _tx(days_ago=d, kind="sale" if d % 2 else "expense", amount=900 + d)
        for d in range(60, 0, -1)
    ]
    dq = compute_data_quality(txs, now=NOW)
    # created_at == occurred_at → no backfill; no bursts; no stock lines → no violations
    assert dq["backfill"]["count"] == 0
    assert dq["burst_insertion"]["count"] == 0
    assert dq["stock_coherence"]["violations"] == []
    assert dq["indicators"] == []


def test_backfill_detected_when_created_long_after_occurrence():
    txs = [_tx(days_ago=60) for _ in range(5)] + [
        _tx(days_ago=60 - i, created_days_ago=1)  # logged today, claimed weeks ago
        for i in range(5)
    ]
    dq = compute_data_quality(txs, now=NOW)
    assert dq["backfill"]["count"] == 5
    assert dq["backfill"]["ratio"] == 0.5
    assert any(str(BACKFILL_LAG_DAYS) in s for s in dq["indicators"])


def test_burst_insertion_detected():
    # 10 entries all created right now, occurrence dates spread over weeks
    txs = [_tx(days_ago=10 + i, created_days_ago=0) for i in range(10)]
    dq = compute_data_quality(txs, now=NOW)
    assert dq["burst_insertion"]["count"] >= BURST_MIN_ENTRIES
    assert any("bursts" in s for s in dq["indicators"])


def test_stock_coherence_catches_sold_exceeds_bought():
    txs = [
        _tx(days_ago=40, kind="expense", item_lines=[
            {"item": "Chai Patti", "qty": 10, "unit": "packet"}]),
        # sales of 15 packets of the same item (name differs only by case/space)
        _tx(days_ago=20, kind="sale", item_lines=[
            {"item": "chai patti", "qty": 8, "unit": "packet"}]),
        _tx(days_ago=10, kind="sale", item_lines=[
            {"item": "Chai  Patti", "qty": 7, "unit": "packet"}]),
    ]
    dq = compute_data_quality(txs, now=NOW)
    assert dq["stock_coherence"]["checked_items"] == 1
    v = dq["stock_coherence"]["violations"][0]
    assert v["item"] == "chai patti"
    assert v["sold"] == 15.0 and v["bought"] == 10.0
    assert any("sold than purchased" in s for s in dq["indicators"])


def test_stock_coherence_ok_when_within_tolerance():
    txs = [
        _tx(days_ago=40, kind="expense", item_lines=[
            {"item": "dal", "qty": 100, "unit": "kg"}]),
        _tx(days_ago=10, kind="sale", item_lines=[
            {"item": "dal", "qty": 100, "unit": "kg"}]),  # == bought, within 5%
    ]
    dq = compute_data_quality(txs, now=NOW)
    assert dq["stock_coherence"]["violations"] == []


def test_window_spike_detected():
    # 60-day ledger: steady ~PKR 1000/day for the first 46 days,
    # then a burst of sales in the trailing 14 days (~10x baseline)
    txs = [_tx(days_ago=d, kind="sale", amount=1000) for d in range(60, 14, -1)]
    txs += [_tx(days_ago=d, kind="sale", amount=10000) for d in range(14, 0, -1)]
    dq = compute_data_quality(txs, now=NOW)
    assert dq["window_spike"]["ratio"] is not None
    assert dq["window_spike"]["ratio"] >= SPIKE_FACTOR
    assert any("baseline" in s for s in dq["indicators"])


def test_no_spike_on_steady_ledger():
    txs = [_tx(days_ago=d, kind="sale", amount=1000) for d in range(60, 0, -1)]
    dq = compute_data_quality(txs, now=NOW)
    assert dq["window_spike"]["ratio"] is not None
    assert dq["window_spike"]["ratio"] < SPIKE_FACTOR
    assert dq["indicators"] == []


def test_provenance_mix_and_rejected_rows_excluded():
    txs = [
        _tx(source="photo"), _tx(source="photo"), _tx(source="voice"),
        _tx(source="manual"),
    ]
    txs[0].status = "rejected"
    dq = compute_data_quality(txs, now=NOW)
    # rejected photo row excluded → 3 rows left, one of each source
    assert dq["provenance"]["photo_pct"] == 33.3
    assert dq["provenance"]["voice_pct"] == 33.3
    assert dq["provenance"]["manual_pct"] == 33.3


def test_basis_note_disclaims_intent():
    dq = compute_data_quality([_tx()], now=NOW)
    assert "not a trust score" in dq["basis_note"]
