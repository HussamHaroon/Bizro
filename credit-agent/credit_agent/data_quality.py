"""Data-quality & consistency indicators — the HONEST alternative to a "verifier".

Positioning (owner ruling 2026-10-22): Bizro cannot and must not try to detect
merchant lies — every input is merchant-volunteered, so omission is invisible
and a "lie detector" claim would be technically false AND adoption-poisonous.
What the system CAN do is measure properties of the LEDGER that don't require
trusting anyone:

- backfill: entries created long after the claimed occurrence (created_at vs
  occurred_at), or history inserted in a burst — discloses HOW the ledger was
  kept, never asserts WHY.
- stock coherence: for items with BOTH supplier purchases and sales logged,
  sold quantity exceeding bought quantity is a real arithmetic inconsistency.
- window spike: sales concentrated at the end of the reporting period vs the
  baseline inside it — a pattern a loan officer would want to see either way.
- provenance mix: photo-anchored vs voice-only vs manual share of the ledger.

Everything here is DISCLOSURE for the loan officer (evidence for their
judgment), phrased as data quality — never an accusation, never a "trust score"
(idea.md: a visible audit trail, not a black-box number).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import timedelta
from typing import Any

# Thresholds are named constants so tests assert boundaries mechanically.
BACKFILL_LAG_DAYS = 7          # created more than this long after occurrence
BURST_WINDOW_HOURS = 24        # entries created within this window...
BURST_MIN_ENTRIES = 8          # ...in this count = a backfill burst
SPIKE_WINDOW_DAYS = 14         # trailing window compared against baseline
SPIKE_FACTOR = 3.0             # recent daily sales >= factor × baseline = spike
STOCK_TOLERANCE = 1.05         # sold may exceed bought by 5% (rounding/unit noise)


def _norm_item(name: str) -> str:
    s = unicodedata.normalize("NFC", name or "").casefold().translate(
        str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    )
    return re.sub(r"[^\w\s]", "", re.sub(r"\s+", " ", s)).strip()


def _lines(tx: Any) -> list[dict]:
    out = tx.item_lines if tx.item_lines else []
    return out if isinstance(out, list) else []


def _aware(dt):
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=None)


def compute_data_quality(txs: list[Any], now) -> dict[str, Any]:
    """Compute all indicators over a merchant's transactions (one reporting
    period). Deterministic; empty ledger → clean empty structure."""
    txs = [t for t in txs if getattr(t, "status", "") != "rejected"]
    indicators: list[str] = []

    # --- 1. backfill: creation lag + burst insertion -------------------------
    backfilled = 0
    for t in txs:
        created = _aware(t.created_at) if t.created_at else None
        if created and (created - _aware(t.occurred_at)) > timedelta(days=BACKFILL_LAG_DAYS):
            backfilled += 1
    backfill_ratio = round(backfilled / len(txs), 3) if txs else 0.0

    burst_count = 0
    created_times = sorted(
        _aware(t.created_at) for t in txs if t.created_at
    )
    window = timedelta(hours=BURST_WINDOW_HOURS)
    i = 0
    while i < len(created_times):
        j = i
        while j < len(created_times) and created_times[j] - created_times[i] <= window:
            j += 1
        if (j - i) >= BURST_MIN_ENTRIES:
            burst_count += j - i
            i = j  # consume the burst; don't double-count overlapping windows
        else:
            i += 1
    burst_ratio = round(burst_count / len(txs), 3) if txs else 0.0

    if backfill_ratio >= 0.2:
        indicators.append(
            f"{round(backfill_ratio * 100)}% of entries were recorded more than "
            f"{BACKFILL_LAG_DAYS} days after their claimed date"
        )
    if burst_count:
        indicators.append(
            f"{burst_count} entries were inserted in bursts of ≥{BURST_MIN_ENTRIES} "
            f"within {BURST_WINDOW_HOURS}h (history added in bulk, not as it happened)"
        )

    # --- 2. stock coherence: sold must not exceed bought ----------------------
    bought: dict[str, float] = {}
    sold: dict[str, float] = {}
    for t in txs:
        for line in _lines(t):
            item = _norm_item(str(line.get("item") or ""))
            qty = float(line.get("qty") or 0)
            if not item or qty <= 0:
                continue
            if t.kind == "expense":
                bought[item] = bought.get(item, 0.0) + qty
            elif t.kind in ("sale", "udhar_given"):
                sold[item] = sold.get(item, 0.0) + qty
    violations = []
    for item in sorted(set(bought) & set(sold)):
        if sold[item] > bought[item] * STOCK_TOLERANCE:
            violations.append({
                "item": item,
                "bought": round(bought[item], 2),
                "sold": round(sold[item], 2),
            })
    if violations:
        indicators.append(
            f"{len(violations)} item(s) show more quantity sold than purchased "
            "(sales ledger inconsistent with supplier receipts)"
        )

    # --- 3. window spike: trailing sales vs in-period baseline ----------------
    spike_ratio = None
    if txs:
        times = [_aware(t.occurred_at) for t in txs]
        end = max(times)
        start = min(times)
        span_days = max(1, (end - start).days + 1)
        if span_days >= SPIKE_WINDOW_DAYS * 2:
            cut = end - timedelta(days=SPIKE_WINDOW_DAYS)

            def _sales_in(lo, hi):
                return sum(
                    float(t.amount_pkr)
                    for t in txs
                    if t.kind == "sale" and lo <= _aware(t.occurred_at) < hi
                )

            recent = _sales_in(cut, end + timedelta(microseconds=1))
            baseline = _sales_in(start, cut)
            base_days = max(1, span_days - SPIKE_WINDOW_DAYS)
            recent_daily = recent / SPIKE_WINDOW_DAYS
            base_daily = baseline / base_days
            if base_daily > 0:
                spike_ratio = round(recent_daily / base_daily, 2)
                if spike_ratio >= SPIKE_FACTOR:
                    indicators.append(
                        f"sales in the trailing {SPIKE_WINDOW_DAYS} days run "
                        f"{spike_ratio}× the earlier baseline"
                    )

    # --- 4. provenance mix -----------------------------------------------------
    n = len(txs)
    photo = sum(1 for t in txs if t.source_type == "photo")
    voice = sum(1 for t in txs if t.source_type == "voice")
    manual = sum(1 for t in txs if t.source_type in ("manual", "text"))
    prov = {
        "photo_pct": round(photo / n * 100, 1) if n else 0.0,
        "voice_pct": round(voice / n * 100, 1) if n else 0.0,
        "manual_pct": round(manual / n * 100, 1) if n else 0.0,
    }

    return {
        "backfill": {
            "lag_days_threshold": BACKFILL_LAG_DAYS,
            "count": backfilled,
            "ratio": backfill_ratio,
        },
        "burst_insertion": {
            "window_hours": BURST_WINDOW_HOURS,
            "min_entries": BURST_MIN_ENTRIES,
            "count": burst_count,
            "ratio": burst_ratio,
        },
        "stock_coherence": {
            "checked_items": len(set(bought) & set(sold)),
            "violations": violations,
        },
        "window_spike": {
            "window_days": SPIKE_WINDOW_DAYS,
            "factor": SPIKE_FACTOR,
            "ratio": spike_ratio,
        },
        "provenance": prov,
        "indicators": indicators,
        "basis_note": (
            "Data-quality disclosures computed from ledger internals only — "
            "they do not assert intent and are not a trust score."
        ),
    }
