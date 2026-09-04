"""Weekly Urdu financial-health nudge (design.md §7.3, PROJECT_PLAN Day 3).

Ships as TEXT, not voice (design.md §2 ruling): a Friday WhatsApp message —
this week's sales vs last week, expenses, udhar outstanding. Deterministic
computation, mock-safe send (logged to outbound_messages either way).

Also home of the savings-streak math (schema.md §7.3): consecutive Mon–Sun
weeks (PKT) with net cash-flow > 0, zero-entry weeks breaking the streak.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Merchant, Transaction
from . import whatsapp_client


def _aware(dt: datetime) -> datetime:
    """SQLite reads return naive datetimes; schema.md says timestamptz (UTC)."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# Pakistan Standard Time, fixed UTC+05:00 (no DST) — the streak weeks are
# Mon–Sun in the merchant's local week (schema.md §7.3).
PKT = timezone(timedelta(hours=5), name="PKT")

# Net cash-flow direction per kind (schema.md §1): money into the drawer vs out.
_CASH_IN_KINDS = frozenset({"sale", "udhar_settlement"})
_CASH_OUT_KINDS = frozenset({"expense", "udhar_given"})


def _pkt(dt: datetime) -> datetime:
    return _aware(dt).astimezone(PKT)


def week_key(dt: datetime) -> int:
    """Mon–Sun week identifier (ordinal of the PKT Monday) — monotonically
    ordered, so consecutive weeks are consecutive keys."""
    pkt_date = _pkt(dt).date()
    monday = pkt_date - timedelta(days=pkt_date.weekday())
    return monday.toordinal()


def compute_streak(
    session: Session, merchant_id: Any, now: datetime | None = None
) -> dict[str, Any]:
    """Savings streak (schema.md §7.3): {"streak_weeks": int,
    "best_streak_weeks": int, "current_week_positive": bool}.

    - Weeks are Mon–Sun in PKT.
    - A week qualifies when its net cash-flow (in − out over non-rejected
      entries) is > 0. Weeks with zero entries break the streak, as do
      net-negative weeks.
    - streak_weeks counts qualifying weeks backwards from the current week;
      best_streak_weeks is the longest qualifying run over all history.
    Rejected entries never count (consistent with the nudge and Udhar Radar).
    """
    now = now or datetime.now(timezone.utc)
    txs = session.scalars(
        select(Transaction).where(
            Transaction.merchant_id == merchant_id, Transaction.status != "rejected"
        )
    ).all()

    net: dict[int, float] = {}
    for t in txs:
        amount = float(t.amount_pkr)
        sign = 1 if t.kind in _CASH_IN_KINDS else -1
        key = week_key(t.occurred_at)
        net[key] = net.get(key, 0.0) + sign * amount

    current = week_key(now)
    # week_key is a Monday ordinal: consecutive weeks are 7 apart.
    streak = 0
    week = current
    while net.get(week, 0.0) > 0:
        streak += 1
        week -= 7

    best = 0
    run = 0
    for week in range(min(net, default=current), current + 1, 7):
        if net.get(week, 0.0) > 0:
            run += 1
            best = max(best, run)
        else:
            run = 0

    return {
        "streak_weeks": streak,
        "best_streak_weeks": best,
        "current_week_positive": net.get(current, 0.0) > 0,
    }


def _sum_kind(txs: list[Transaction], kind: str) -> float:
    return sum(float(t.amount_pkr) for t in txs if t.kind == kind and t.status != "rejected")


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

    # §7.3: the nudge carries the savings streak when there is one.
    streak = compute_streak(session, merchant_id, now=now)
    streak_weeks = streak["streak_weeks"]

    parts = [
        "ہفتہ وار خلاصہ:",
        f"اس ہفتے کی فروخت PKR {sales_now:,.0f}۔",
    ]
    trend = _trend(sales_now, sales_prev)
    if trend:
        parts.append(trend + "۔")
    if streak_weeks >= 1:
        parts.append(f"لگاتار {streak_weeks} ہفتے سے کمائی خرچ سے زیادہ ہے — بہت خوب!")
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
            "streak_weeks": streak_weeks,
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
