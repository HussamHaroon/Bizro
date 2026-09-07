"""Anti-fabrication forensics tests — pricing fabrication, not detecting lies.

The threat being locked down: a merchant fabricates paper entries for months
and photographs them daily. Each test covers one fingerprint that process
leaves: reused printed bill numbers, EXIF capture-time vs claim dates,
stripped metadata, and manufactured (round/uniform/repetitive) amounts.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credit_agent.forensics import (
    EXIF_MISMATCH_DAYS,
    compute_forensics,
)

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def _tx(days_ago=30, kind="sale", amount=1000.0, source="voice",
        raw=None, customer=None, occurred=None):
    return type("T", (), {
        "kind": kind, "amount_pkr": amount, "source_type": source,
        "occurred_at": occurred or (NOW - timedelta(days=days_ago)),
        "created_at": NOW - timedelta(days=days_ago),
        "item_lines": [], "status": "confirmed",
        "customer_id": customer, "raw_model_output": raw or {},
    })()


def _customers():
    class C:
        def __init__(self, name):
            self.name = name
    return {"s1": C("Al-Madina Distributors"), "c1": C("Ahmad")}


# ---------------------------------------------------------------------------
# Bill-number forensics: the distributor's bill book is not the merchant's
# ---------------------------------------------------------------------------

def _receipt(days_ago, bill, supplier="s1"):
    return _tx(
        days_ago=days_ago, kind="expense", source="photo", customer=supplier,
        raw={"receipt_meta": {"bill_number": bill, "exif_present": False}},
    )


def test_reused_bill_number_across_dates_flagged():
    txs = [_receipt(40, "4401"), _receipt(10, "4401")]  # same printed number, 30 days apart
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["bill_numbers"]["reused_across_dates"] == 1
    assert any("reused" in s for s in fo["indicators"])


def test_same_bill_twice_same_day_not_flagged():
    # two photos of the SAME paper on the same day is a dup-photo case,
    # not a bill-number forgery signal
    txs = [_receipt(10, "4401"), _receipt(10, "4401")]
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["bill_numbers"]["reused_across_dates"] == 0


def test_sequence_inversion_flagged():
    # bill numbers must run forward in time per supplier
    txs = [_receipt(40, "100"), _receipt(30, "200"), _receipt(20, "150")]
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["bill_numbers"]["sequence_inversions"] >= 1
    assert any("inversion" in s for s in fo["indicators"])


def test_clean_sequence_not_flagged():
    txs = [_receipt(40, "100"), _receipt(30, "150"), _receipt(20, "200")]
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["bill_numbers"]["reused_across_dates"] == 0
    assert fo["bill_numbers"]["sequence_inversions"] == 0


# ---------------------------------------------------------------------------
# EXIF: the camera's timestamp vs the claim
# ---------------------------------------------------------------------------

def test_exif_capture_mismatch_flagged():
    old_receipt = _tx(
        days_ago=60, kind="expense", source="photo", customer="s1",
        raw={"receipt_meta": {
            "exif_present": True,
            "captured_at": (NOW - timedelta(days=1)).isoformat(),  # shot yesterday
        }},
        occurred=NOW - timedelta(days=60),  # claims to be 60 days old
    )
    fo = compute_forensics([old_receipt], _customers(), now=NOW)
    assert fo["exif"]["capture_mismatches"] == 1
    assert any("EXIF" in s or "captured" in s for s in fo["indicators"])


def test_exif_match_not_flagged():
    ok = _tx(
        days_ago=5, kind="expense", source="photo", customer="s1",
        raw={"receipt_meta": {
            "exif_present": True,
            "captured_at": (NOW - timedelta(days=5, hours=2)).isoformat(),
        }},
        occurred=NOW - timedelta(days=5),
    )
    fo = compute_forensics([ok], _customers(), now=NOW)
    assert fo["exif"]["capture_mismatches"] == 0


def test_exif_stripping_suspected_when_partial():
    txs = [_receipt(40, "100"), _receipt(30, "150")]
    txs[0].raw_model_output = {"receipt_meta": {"exif_present": True}}
    txs[1].raw_model_output = {"receipt_meta": {"exif_present": False}}  # stripped
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["exif"]["missing_exif_share"] > 0
    assert any("metadata" in s for s in fo["indicators"])


# ---------------------------------------------------------------------------
# Ledger naturalness: real commerce is noisy; naive fabrication isn't
# ---------------------------------------------------------------------------

def test_round_amount_share_flagged():
    txs = [_tx(days_ago=d % 30 + 1, amount=5000.0) for d in range(12)]
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["naturalness"]["round_amount_share"] == 1.0
    assert any("multiples" in s for s in fo["indicators"])


def test_natural_amounts_not_flagged():
    txs = [_tx(days_ago=d % 30 + 1, amount=1000 + d * 137) for d in range(15)]
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["naturalness"]["round_amount_share"] < 0.9
    assert not any("multiples" in s for s in fo["indicators"])


def test_verbatim_repeat_group_flagged():
    txs = [_tx(days_ago=d + 1, amount=2500.0, customer="c1") for d in range(5)]
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["naturalness"]["verbatim_repeat_groups"] == 1
    assert any("verbatim" in s for s in fo["indicators"])


def test_too_uniform_daily_sales_flagged():
    # 15 selling days, identical totals → CV 0
    txs = [_tx(days_ago=d, kind="sale", amount=4000.0) for d in range(1, 16)]
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["naturalness"]["daily_sales_cv"] is not None
    assert fo["naturalness"]["daily_sales_cv"] < 0.25
    assert any("uniform" in s for s in fo["indicators"])


def test_varied_daily_sales_not_flagged():
    txs = []
    for d in range(1, 16):
        txs.append(_tx(days_ago=d, kind="sale", amount=800 * (d % 5 + 1) * 3))
    fo = compute_forensics(txs, _customers(), now=NOW)
    assert fo["naturalness"]["daily_sales_cv"] >= 0.25


def test_empty_ledger_forensics_clean():
    fo = compute_forensics([], {}, now=NOW)
    assert fo["indicators"] == []
    assert fo["exif"]["photos"] == 0
