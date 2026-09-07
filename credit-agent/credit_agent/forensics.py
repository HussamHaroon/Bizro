"""Receipt & ledger forensics — pricing fabrication, not detecting lies.

Companion to data_quality.py (§9 disclosures). The merchant-volunteered ledger
can be fabricated (fake paper, photographed daily). These indicators attack the
FABRICATION PROCESS — the parts a faker does not control or must work harder
to fake:

1. bill-number forensics — printed bill numbers come from the DISTRIBUTOR's
   bill book. Reused numbers across dates, or sequences that run backwards in
   time, are physical-world inconsistencies on paper the merchant didn't print.
2. EXIF capture-time mismatch — the camera's own timestamp vs the claimed
   occurrence date. A "60-day-old receipt" photographed yesterday shows it.
   Photos with NO exif are also counted when the merchant's other photos have
   it (stripping is itself a fingerprint).
3. ledger naturalness — real commerce is noisy: amounts carry unit-price × qty
   remainders, daily totals vary widely, the same exact figure doesn't repeat
   verbatim. Naive fabrication is round, uniform, and repetitive. Low
   "naturalness" is a disclosure, never a verdict.

Every output feeds the loan officer's data-quality card as DISCLOSURE
(schema.md §10): patterns, not accusations; no trust score.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

EXIF_MISMATCH_DAYS = 3          # captured_at vs claimed occurred_at gap
ROUND_DIVISOR = 500             # amounts divisible by this count as "round"
ROUND_SUSPECT_SHARE = 0.9       # share above which amounts look manufactured
ROUND_MIN_ENTRIES = 10
CV_TOO_LOW = 0.25               # daily-sales coefficient of variation floor
CV_MIN_DAYS = 10
REPEAT_SAME_AMOUNT = 4          # same amount+kind+customer repeated N times


def _aware(dt):
    """Normalize BOTH directions to aware-UTC: Neon returns tz-aware rows while
    exif.py produces naive datetimes — mixing them in a subtraction 500s the
    whole report (reliability audit P1). Naive is treated as UTC, the
    server-wide storage convention (same rule as server/app/nudges.py)."""
    from datetime import timezone as _tz

    if dt.tzinfo is None:
        return dt.replace(tzinfo=_tz.utc)
    return dt.astimezone(_tz.utc)


def _meta(tx: Any) -> dict:
    raw = getattr(tx, "raw_model_output", None) or {}
    meta = raw.get("receipt_meta") if isinstance(raw, dict) else None
    return meta if isinstance(meta, dict) else {}


def compute_forensics(txs: list[Any], customers_by_id: dict, now) -> dict[str, Any]:
    txs = [t for t in txs if getattr(t, "status", "") != "rejected"]
    indicators: list[str] = []

    def _cust_name(t: Any) -> str:
        c = customers_by_id.get(getattr(t, "customer_id", None))
        return (c.name if c else None) or ""

    # --- 1. bill-number forensics (per supplier) -----------------------------
    bills: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    photos = [t for t in txs if getattr(t, "source_type", "") == "photo"]
    for t in photos:
        meta = _meta(t)
        bn = meta.get("bill_number")
        supplier = (_cust_name(t) or (meta.get("supplier_phone") or "unknown-supplier"))
        if bn:
            bills[str(supplier)][str(bn)].append(t)
    reused = 0
    for supplier, by_bill in bills.items():
        for bn, group in by_bill.items():
            dates = {_aware(t.occurred_at).date() for t in group}
            if len(dates) > 1:  # same printed bill number on different days
                reused += 1
    out_of_order = 0
    for supplier, by_bill in bills.items():
        numeric = []
        for bn, group in by_bill.items():
            try:
                numeric.append((min(_aware(t.occurred_at) for t in group), int(bn)))
            except (ValueError, TypeError):
                continue
        if len(numeric) >= 3:
            numeric.sort()  # by date
            seq = [n for _, n in numeric]
            inversions = sum(
                1 for a, b in zip(seq, seq[1:]) if b < a
            )
            out_of_order += inversions
    if reused:
        indicators.append(
            f"{reused} printed bill number(s) reused across different dates"
        )
    if out_of_order:
        indicators.append(
            f"{out_of_order} bill-number sequence inversion(s) against claim dates"
        )

    # --- 2. EXIF capture-time vs claim ---------------------------------------
    exif_hits = [t for t in photos if _meta(t).get("exif_present")]
    mismatches = 0
    for t in exif_hits:
        try:
            captured = datetime.fromisoformat(str(_meta(t)["captured_at"]))
        except (KeyError, TypeError, ValueError):
            continue
        if abs(_aware(captured) - _aware(t.occurred_at)) > timedelta(
            days=EXIF_MISMATCH_DAYS
        ):
            mismatches += 1
    no_exif = len(photos) - len(exif_hits)
    stripped_suspect = (
        no_exif > 0
        and len(exif_hits) > 0
        and no_exif / len(photos) >= 1 / 3
    )
    if mismatches:
        indicators.append(
            f"{mismatches} receipt photo(s) captured more than {EXIF_MISMATCH_DAYS} days "
            "from their claimed date (camera EXIF)"
        )
    if stripped_suspect:
        indicators.append(
            f"{no_exif} of {len(photos)} receipt photos carry no camera metadata "
            "while others do"
        )

    # --- 3. ledger naturalness ------------------------------------------------
    amounts = [float(t.amount_pkr) for t in txs]
    round_share = None
    if len(amounts) >= ROUND_MIN_ENTRIES:
        round_share = round(
            sum(1 for a in amounts if a % ROUND_DIVISOR == 0) / len(amounts), 3
        )
        if round_share >= ROUND_SUSPECT_SHARE:
            indicators.append(
                f"{round(round_share * 100)}% of amounts are exact multiples of "
                f"PKR {ROUND_DIVISOR} (real ledgers carry unit-price remainders)"
            )

    repeats = 0
    seen: dict[tuple, int] = defaultdict(int)
    for t in txs:
        key = (t.kind, round(float(t.amount_pkr), 2), _cust_name(t))
        seen[key] += 1
    for key, n in seen.items():
        if n >= REPEAT_SAME_AMOUNT:
            repeats += 1
    if repeats:
        indicators.append(
            f"{repeats} amount(s) repeat verbatim ≥{REPEAT_SAME_AMOUNT} times for the "
            "same party"
        )

    daily: dict[Any, float] = defaultdict(float)
    for t in txs:
        if t.kind == "sale":
            daily[_aware(t.occurred_at).date()] += float(t.amount_pkr)
    cv = None
    if len(daily) >= CV_MIN_DAYS:
        vals = list(daily.values())
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        if mean > 0:
            cv = round((var ** 0.5) / mean, 3)
            if cv < CV_TOO_LOW:
                indicators.append(
                    f"daily sales totals are unusually uniform (CV {cv} over "
                    f"{len(daily)} selling days)"
                )

    return {
        "bill_numbers": {
            "suppliers_with_bills": len(bills),
            "reused_across_dates": reused,
            "sequence_inversions": out_of_order,
        },
        "exif": {
            "photos": len(photos),
            "with_exif": len(exif_hits),
            "capture_mismatches": mismatches,
            "missing_exif_share": round(no_exif / len(photos), 3) if photos else 0.0,
        },
        "naturalness": {
            "round_amount_share": round_share,
            "verbatim_repeat_groups": repeats,
            "daily_sales_cv": cv,
        },
        "indicators": indicators,
    }
