"""Weekly Urdu financial-health nudge (design.md §7.3, PROJECT_PLAN Day 3).

Ships as TEXT, not voice (design.md §2 ruling): a Friday WhatsApp message —
this week's sales vs last week, expenses, udhar outstanding. Deterministic
computation, mock-safe send (logged to outbound_messages either way).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Merchant, Transaction
from . import whatsapp_client


def _aware(dt: datetime) -> datetime:
    """SQLite reads return naive datetimes; schema.md says timestamptz (UTC)."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _sum_kind(txs: list[Transaction], kind: str) -> float:
    return sum(float(t.amount_pkd) for t in txs if t.kind == kind and t.status != "rejected")


def _trend(current: float, previous: float) -> str:
    if previous <= 0:
        return "پچھلے ہفتے کوئی فروخت ریکارڈ نہیں ہوئی" if current > 0 else ""
    pct = (current - previous) / previous * 100
    if pct >= 5:
        return f"فروخت {pct:.0f}% بڑھی ہے"
    if pct <= -5:
        return f"فروخت {abs(pct):.0f}% کم ہوئی ہے"
    return "فروخت پچھلے ہفتے جیسی ہے"


def compute_weekly_nudge(session: Session, merchant_id, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    txs = session.scalars(
        select(Transaction).where(
            Transaction.merchant_id == merchant_id,
            Transaction.occurred_at >= two_weeks_ago,
        )
    ).all()

    this_week = [t for t in txs if _aware(t.occurred_at) >= week_ago]
    last_week = [t for t in txs if _aware(t.occurred_at) < week_ago]

    sales_now = _sum_kind(this_week, "sale")
    sales_prev = _sum_kind(last_week, "sale")
    expenses_now = _sum_kind(this_week, "expense")
    udhar_new = _sum_kind(this_week, "udhar_given")
    udhar_collected = _sum_kind(this_week, "udhar_settlement")

    all_txs = session.scalars(
        select(Transaction).where(
            Transaction.merchant_id == merchant_id, Transaction.status != "rejected"
        )
    ).all()
    outstanding = _sum_kind(all_txs, "udhar_given") - _sum_kind(all_txs, "udhar_settlement")

    parts = [
        "ہفتہ وار خلاصہ:",
        f"اس ہفتے کی فروخت PKR {sales_now:,.0f}۔",
    ]
    trend = _trend(sales_now, sales_prev)
    if trend:
        parts.append(trend + "۔")
    if expenses_now:
        parts.append(f"خرچ PKR {expenses_now:,.0f}۔")
    if udhar_new or udhar_collected:
        parts.append(
            f"نیا اُدھار PKR {udhar_new:,.0f}، وصول PKR {udhar_collected:,.0f}۔"
        )
    parts.append(f"کل بقایا اُدھار PKR {outstanding:,.0f}۔")

    return {
        "text_ur": " ".join(parts),
        "stats": {
            "sales_this_week": round(sales_now, 2),
            "sales_last_week": round(sales_prev, 2),
            "expenses_this_week": round(expenses_now, 2),
            "udhar_outstanding": round(outstanding, 2),
        },
    }


def send_weekly_nudges(session: Session, now: datetime | None = None) -> list[dict]:
    """Send to every merchant; returns one result row per merchant (mock-safe)."""
    results = []
    for m in session.scalars(select(Merchant)).all():
        nudge = compute_weekly_nudge(session, m.id, now=now)
        send = whatsapp_client.send_text(m.wa_id or "", nudge["text_ur"])
        results.append({"merchant_id": str(m.id), "stats": nudge["stats"], "send": send})
    return results
