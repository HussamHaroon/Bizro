"""Officer completeness metrics — the manual credit-officer's checklist,
computed from the ledger instead of guessed at a desk (schema.md §12).

These answer the questions a karyana lender asks before ANY scoring:
- How old is the money owed to the shop, and who owes it? (receivables aging)
- How much of the credit given out came back? (collection rate)
- Is one customer's debt so big it sinks the book? (top-debtor concentration)
- Is the shop still keeping the ledger up? (weekly entries + activity drop)

Everything is DISCLOSURE for the officer: deterministic arithmetic over the
same confirmed entries the aggregates use, with a one-line plain-English note
per metric. Nothing here feeds the readiness score (rubric.md).

Aging method (documented, deterministic): settlements are applied to the
OLDEST outstanding udhar_given entry per customer (FIFO), the standard
khata convention; each remaining entry ages from its occurred_at to the
period end and lands in exactly one bucket (0-30 / 31-60 / 61-90 / 90+).
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from .aggregates import CONFIRMED_STATUSES
from .formatting import ensure_aware

AGING_BUCKETS = ("0-30", "31-60", "61-90", "90+")
AGING_DAYS = (30, 60, 90)
CONCENTRATION_WARN_PCT = 40.0   # top debtor above this share warns the officer
ACTIVITY_WEEKS = 8              # weekly entries window
ACTIVITY_DROP_FRACTION = 0.5    # latest week < 50% of the median = a drop
UNKNOWN_CUSTOMER = "نامعلوم"    # entries without a linked customer record


def _aware(dt):
    return ensure_aware(dt)


def _bucket_for(age_days: int) -> str:
    for limit, name in zip(AGING_DAYS, AGING_BUCKETS):
        if age_days <= limit:
            return name
    return AGING_BUCKETS[-1]


def _aging(txs: list[Any], now: datetime) -> tuple[list[dict], float]:
    """FIFO settlement per customer → outstanding per bucket, per customer."""
    given: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    paid: dict[str, float] = defaultdict(float)
    for t in txs:
        amount = float(t.amount_pkr)
        # key by the RAW customer_id (same objects the customers_by_id map
        # is keyed by) — names resolve after the FIFO pass
        key = t.customer_id
        if t.kind == "udhar_given":
            given[key].append((_aware(t.occurred_at), amount))
        elif t.kind == "udhar_settlement":
            paid[key] += amount

    buckets: dict[str, dict[str, Any]] = {
        b: {"bucket": b, "total": 0.0, "customers": []} for b in AGING_BUCKETS
    }
    total_outstanding = 0.0
    for cust_id, entries in given.items():
        entries.sort(key=lambda e: e[0])  # oldest first
        # FIFO: pay down from the oldest entry
        remaining: list[tuple[datetime, float]] = []
        pool = list(entries)
        pay = paid.get(cust_id, 0.0)
        for when, amount in pool:
            if pay >= amount - 0.005:
                pay -= amount
                continue
            if pay > 0.005:
                amount -= pay
                pay = 0.0
            remaining.append((when, amount))
        for when, amount in remaining:
            age_days = max(0, (now - when).days)
            b = buckets[_bucket_for(age_days)]
            b["total"] += amount
            total_outstanding += amount
            b.setdefault("_by_cust", defaultdict(float))
            b["_by_cust"][cust_id] += amount

    for b in buckets.values():
        by_cust = b.pop("_by_cust", {})
        b["customers"] = [
            {"name": c, "amount": round(by_cust[c], 2)}
            for c in by_cust
        ]
        # names resolve later; amounts rounded now
        b["total"] = round(b["total"], 2)
        b["customers"].sort(key=lambda c: -c["amount"])
    return list(buckets.values()), round(total_outstanding, 2)


def compute_officer_metrics(
    txs: list[Any], customers_by_id: dict, now: datetime
) -> dict:
    """All four officer metrics over one reporting period. Deterministic;
    empty ledger → empty structures with honest notes."""
    now = _aware(now)
    txs = [t for t in txs if getattr(t, "status", "") in CONFIRMED_STATUSES]

    def cust_name(cust_id) -> str:
        c = customers_by_id.get(cust_id)
        return (c.name if c else None) or UNKNOWN_CUSTOMER

    # --- 1. receivables aging (FIFO per customer) ---------------------------
    bucket_rows, total_outstanding = _aging(txs, now)
    # resolve customer ids to names
    for row in bucket_rows:
        for c in row["customers"]:
            c["name"] = cust_name(c["name"])
    aged_61_plus = round(
        sum(r["total"] for r in bucket_rows if r["bucket"] in ("61-90", "90+")), 2
    )
    if total_outstanding > 0:
        aging_note = (
            f"PKR {total_outstanding:,.0f} outstanding; PKR {aged_61_plus:,.0f} of it "
            f"is more than 60 days old"
        )
    else:
        aging_note = "no outstanding udhar in this period"

    # --- 2. collection rate ---------------------------------------------------
    given_total = sum(float(t.amount_pkr) for t in txs if t.kind == "udhar_given")
    settled_total = sum(float(t.amount_pkr) for t in txs if t.kind == "udhar_settlement")
    given_total, settled_total = round(given_total, 2), round(settled_total, 2)
    rate = round(settled_total / given_total, 3) if given_total > 0 else None
    if rate is None:
        collection_note = "no credit was given in this period, so there is nothing to collect"
    else:
        collection_note = (
            f"PKR {settled_total:,.0f} came back of the PKR {given_total:,.0f} "
            f"credit given this period ({rate:.0%} collected)"
        )

    # --- 3. top-debtor concentration -----------------------------------------
    outstanding_by_cust: dict[str, float] = defaultdict(float)
    for row in bucket_rows:
        for c in row["customers"]:
            outstanding_by_cust[c["name"]] += c["amount"]
    shares = sorted(outstanding_by_cust.values(), reverse=True)
    top_share = round(shares[0] / total_outstanding * 100, 1) if shares else 0.0
    top_3_share = round(sum(shares[:3]) / total_outstanding * 100, 1) if shares else 0.0
    top_debtor = (
        max(outstanding_by_cust, key=outstanding_by_cust.get) if shares else None
    )
    warn = top_share > CONCENTRATION_WARN_PCT
    if top_debtor is None:
        concentration_note = "no outstanding udhar to concentrate"
    else:
        concentration_note = (
            f"{top_debtor} holds {top_share:g}% of all outstanding udhar "
            f"(top 3 hold {top_3_share:g}%)"
        )
        if warn:
            concentration_note += (
                f" — above the {CONCENTRATION_WARN_PCT:.0f}% warning line: one "
                "customer falling behind would take most of the book with them"
            )

    # --- 4. weekly entries + activity drop ------------------------------------
    weeks: list[dict] = []
    for i in range(ACTIVITY_WEEKS - 1, -1, -1):  # oldest → newest
        w_end = now - timedelta(days=7 * i)
        w_start = now - timedelta(days=7 * (i + 1))
        count = sum(
            1 for t in txs if w_start <= _aware(t.occurred_at) < w_end
        )
        weeks.append({
            "start": w_start.isoformat(),
            "end": w_end.isoformat(),
            "count": count,
        })
    counts = [w["count"] for w in weeks]
    latest = counts[-1] if counts else 0
    median = round(statistics.median(counts), 1) if counts else 0.0
    drop_pct = None
    if median > 0 and latest < ACTIVITY_DROP_FRACTION * median:
        drop_pct = round((1 - latest / median) * 100, 1)
    if median == 0:
        activity_note = "no entries in the last eight weeks"
    elif drop_pct is not None:
        activity_note = (
            f"{latest} entries in the latest week vs a median of {median:g} — "
            f"ledger-keeping slowed by {drop_pct:g}%"
        )
    else:
        activity_note = (
            f"{latest} entries in the latest week vs a median of {median:g} — "
            "ledger-keeping is holding steady"
        )

    return {
        "aging": {
            "buckets": bucket_rows,
            "total_outstanding": total_outstanding,
            "note_en": aging_note,
        },
        "collection": {
            "given_pkr": given_total,
            "settled_pkr": settled_total,
            "rate": rate,
            "note_en": collection_note,
        },
        "concentration": {
            "top_debtor": top_debtor,
            "top_share": top_share,
            "top_3_share": top_3_share,
            "warn": warn,
            "warning_threshold_pct": CONCENTRATION_WARN_PCT,
            "note_en": concentration_note,
        },
        "activity": {
            "weeks": weeks,
            "latest_full_week_count": latest,
            "eight_week_median": median,
            "activity_drop_pct": drop_pct,
            "note_en": activity_note,
        },
    }
