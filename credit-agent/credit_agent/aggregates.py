"""Deterministic aggregate computation over the shared schema.

ALL numbers in a Credit Readiness Report are computed here, in plain Python — the
reasoning model (narrative.py) only ever SEES these aggregates and writes prose.
Never let a model do arithmetic on raw rows (bizro-credit-agent SKILL.md).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .db_view import Customer, Transaction

CONFIRMED_STATUSES = ("confirmed", "edited", "pending")  # rejected excluded


@dataclass
class Aggregates:
    period_start: datetime
    period_end: datetime
    total_entries: int = 0
    counts: dict = field(default_factory=dict)         # kind -> count
    sums: dict = field(default_factory=dict)           # kind -> PKR total
    weeks_in_span: int = 0
    weeks_active: int = 0
    entries_per_week: float = 0.0
    median_confidence: float | None = None
    low_confidence_count: int = 0
    pending_count: int = 0
    edited_count: int = 0
    provenance: dict = field(default_factory=dict)     # voice/photo/manual -> pct
    flag_counts: dict = field(default_factory=dict)    # flag -> count
    udhar_outstanding: float = 0.0
    udhar_by_customer: dict = field(default_factory=dict)  # customer name -> PKR
    cash_in: float = 0.0
    cash_out: float = 0.0
    net_cashflow: float = 0.0


def _week_key(dt: datetime) -> int:
    epoch = dt.replace(tzinfo=None) - datetime(1970, 1, 1)
    return epoch.days // 7


def compute_aggregates(
    txs: list[Transaction],
    customers_by_id: dict,
    now: datetime | None = None,
) -> Aggregates:
    now = now or datetime.now(timezone.utc)
    txs = [t for t in txs if t.status in CONFIRMED_STATUSES]
    agg = Aggregates(period_start=now, period_end=now)
    if not txs:
        return agg

    times = [t.occurred_at for t in txs]
    agg.period_start, agg.period_end = min(times), max(times)
    agg.total_entries = len(txs)

    udhar_given: dict = {}
    udhar_paid: dict = {}
    confidences: list = []

    for t in txs:
        agg.counts[t.kind] = agg.counts.get(t.kind, 0) + 1
        amount = float(t.amount_pkd)
        agg.sums[t.kind] = agg.sums.get(t.kind, 0.0) + amount

        if t.confidence is not None:
            c = float(t.confidence)
            confidences.append(c)
            if c < 0.75:
                agg.low_confidence_count += 1
        if t.status == "pending":
            agg.pending_count += 1
        if t.status == "edited":
            agg.edited_count += 1
        if t.flag and t.flag != "none":
            agg.flag_counts[t.flag] = agg.flag_counts.get(t.flag, 0) + 1

        cust = customers_by_id.get(t.customer_id)
        cname = (cust.name if cust else None) or "نامعلوم"
        if t.kind == "udhar_given":
            udhar_given[cname] = udhar_given.get(cname, 0.0) + amount
        elif t.kind == "udhar_settlement":
            udhar_paid[cname] = udhar_paid.get(cname, 0.0) + amount

    for name in set(udhar_given) | set(udhar_paid):
        out = udhar_given.get(name, 0.0) - udhar_paid.get(name, 0.0)
        if out > 0.005:
            agg.udhar_by_customer[name] = round(out, 2)
            agg.udhar_outstanding += out
    agg.udhar_outstanding = round(agg.udhar_outstanding, 2)

    agg.cash_in = round(agg.sums.get("sale", 0.0) + agg.sums.get("udhar_settlement", 0.0), 2)
    agg.cash_out = round(agg.sums.get("expense", 0.0), 2)
    agg.net_cashflow = round(agg.cash_in - agg.cash_out, 2)

    weeks = {_week_key(t.occurred_at) for t in txs}
    span_weeks = _week_key(agg.period_end) - _week_key(agg.period_start) + 1
    agg.weeks_in_span = max(1, span_weeks)
    agg.weeks_active = len(weeks)
    agg.entries_per_week = round(agg.total_entries / agg.weeks_in_span, 2)

    if confidences:
        agg.median_confidence = round(statistics.median(confidences), 3)
    total = agg.total_entries
    for src in ("voice", "photo", "manual"):
        agg.provenance[src] = round(
            sum(1 for t in txs if t.source_type == src) / total * 100, 1
        )
    return agg


def span_days(agg: Aggregates) -> int:
    return max(0, (agg.period_end - agg.period_start).days) + 1


def distinct_customers(agg: Aggregates) -> int:
    return len(agg.udhar_by_customer)
