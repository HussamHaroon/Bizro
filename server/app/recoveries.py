"""Udhaar recovery ladder — polite, escalating reminders to customers whose
udhaar is aging, plus an escalation notice to the shopkeeper when a customer
is seriously overdue.

THE LADDER (phase-1 design; implementation lands in phase 2)
============================================================
    oldest outstanding entry age   tier          who is messaged
    ----------------------------   -----------   -------------------------------
    0-14 days                      none          nobody — the weekly nudge
                                                 (nudges.py) covers fresh
                                                 udhaar
    15-29 days                     gentle        customer (CC: shopkeeper)
    30-44 days                     firm          customer (CC: shopkeeper)
    45+ days                       escalation    customer (CC: shopkeeper) AND
                                                 a separate escalation notice
                                                 to the SHOPKEEPER

Aging (mirrors credit_agent/credit_agent/officer.py's FIFO day math, but
re-implemented locally — the server never imports the credit-agent package):
  - per customer, udhar_settlement amounts pay down that customer's
    udhar_given entries OLDEST FIRST (the standard khata FIFO convention);
  - each surviving entry ages from its occurred_at to `now`:
    age_days = max(0, (now - when).days);
  - the OLDEST surviving entry's age sets the tier (the ladder keys on how
    long the oldest money has been out, not on an average);
  - entry statuses: "rejected" never counts (same rule as the weekly nudge);
    pending entries count (officer.py's CONFIRMED_STATUSES convention — the
    merchant's own ledger claim, awaiting only confirmation);
  - a customer is messaged only when the FIFO-adjusted outstanding balance
    is explicitly > 0 (0.005 epsilon, as in officer.py) — never on a
    zero/overpaid book;
  - udhaar not linked to a customer row (customer_id NULL) can never be
    messaged — there is nobody to address.

Rules of engagement (each enforced in code and pinned by tests):
  1. ONE message per customer per run, idempotent per day: every send is
     recorded as an OutboundMessage with kind="recovery_<tier>" and a
     payload carrying the customer_id; a customer already covered earlier
     the same PKT day is skipped on re-runs.
  2. Every customer message is ALSO delivered to the shopkeeper's thread as
     fine print (kind="recovery_<tier>_cc") — the shopkeeper always sees
     exactly what was sent to their customer.
  3. At 45+ days a separate escalation notice goes to the SHOPKEEPER
     (kind="recovery_escalation_shopkeeper"):
     "<customer>'s balance is 45+ days overdue — we suggest a personal
     visit." It fires even when the customer has no phone on file (the body
     is then marked "no phone on file").
  4. Customers without a phone number are never messaged — they are listed
     in the run result for the shopkeeper instead.
  5. Polite register everywhere — these are customers first; the ladder
     rises in firmness, never in rudeness.

Message copy (exact, low-literacy friendly, simple English per the owner
ruling 2026-09-04):
  gentle      "Assalam-o-alaikum! A gentle reminder: PKR <amount> is
               outstanding at <shop> since <date>. Pay whenever convenient —
               reply here if you need a day."
  firm        "Your balance of PKR <amount> at <shop> is now 30+ days old.
               Please arrange payment this week."
  escalation  "Your PKR <amount> balance is 45+ days overdue. Our team may
               visit to settle the account in person."        (to customer)
              "<customer>'s balance is 45+ days overdue — we suggest a
               personal visit."                             (to shopkeeper)

Sending is mock-safe: delivery goes through dispatch.deliver() (mock mode
logs, live mode sends) and every send gets an outbound_messages audit row
either way. The public surface is:

  compute_recovery_actions(session, merchant_id, now=None)
      -> [{customer, customer_id, phone, amount, oldest_days, tier,
           message, oldest_tx_id}, ...]      (worst debtor first)
  send_recovery_messages(session, merchant_id=None, now=None)
      -> per-merchant run results: sent / no_phone / skipped_today
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Customer, Merchant, OutboundMessage, Transaction
from .nudges import PKT, _aware

# deliver() is dispatch's best-effort WhatsApp send (mock mode logs, live
# mode sends) — imported flat so tests can monkeypatch recoveries.deliver.
from .dispatch import deliver

# --- the ladder (phase-1 design) ---------------------------------------------

TIER_GENTLE = "gentle"
TIER_FIRM = "firm"
TIER_ESCALATION = "escalation"

GENTLE_FROM_DAYS = 15
FIRM_FROM_DAYS = 30
ESCALATE_FROM_DAYS = 45

# Outstanding balances below this epsilon count as settled (officer.py parity).
OUTSTANDING_EPSILON = 0.005

_KINDS = ("udhar_given", "udhar_settlement")


def tier_for_days(age_days: int) -> str | None:
    """Ladder lookup: oldest outstanding entry age → tier (None = 0-14d)."""
    if age_days >= ESCALATE_FROM_DAYS:
        return TIER_ESCALATION
    if age_days >= FIRM_FROM_DAYS:
        return TIER_FIRM
    if age_days >= GENTLE_FROM_DAYS:
        return TIER_GENTLE
    return None


# --- message copy (exact wording per the phase-1 design) ---------------------


def _fmt_amount(amount: float) -> str:
    return f"PKR {amount:,.0f}"


def _fmt_date(when: datetime) -> str:
    """The oldest entry's date in the merchant's local day (PKT), e.g.
    '18 Aug 2026' — simple and unambiguous for the customer."""
    d = _aware(when).astimezone(PKT)
    return f"{d.day} {d.strftime('%b %Y')}"


def build_message(tier: str, amount: float, shop: str, oldest_when: datetime) -> str:
    """Customer-facing copy per tier — polite register everywhere."""
    amt = _fmt_amount(amount)
    if tier == TIER_GENTLE:
        return (
            f"Assalam-o-alaikum! A gentle reminder: {amt} is outstanding at {shop} "
            f"since {_fmt_date(oldest_when)}. Pay whenever convenient — reply here "
            "if you need a day."
        )
    if tier == TIER_FIRM:
        return (
            f"Your balance of {amt} at {shop} is now 30+ days old. "
            "Please arrange payment this week."
        )
    if tier == TIER_ESCALATION:
        return (
            f"Your {amt} balance is 45+ days overdue. "
            "Our team may visit to settle the account in person."
        )
    raise ValueError(f"unknown tier: {tier!r}")


def shopkeeper_notice(customer: str, no_phone: bool = False) -> str:
    """The 45d+ escalation notice to the SHOPKEEPER (design rule 3)."""
    body = f"{customer}'s balance is 45+ days overdue — we suggest a personal visit."
    if no_phone:
        body += " (no phone on file)"
    return body


def cc_body(customer: str, message: str) -> str:
    """Fine print: the shopkeeper sees exactly what was sent (design rule 2)."""
    return f"[Copy sent to {customer}]: {message}"


# --- aging --------------------------------------------------------------------


def _fifo_outstanding(
    entries: list[tuple[datetime, float, Any]], pay: float
) -> list[tuple[datetime, float, Any]]:
    """Pay `pay` down the OLDEST entry first (khata FIFO, officer.py parity);
    return the surviving (when, amount, tx_id) entries, oldest first."""
    remaining: list[tuple[datetime, float, Any]] = []
    for when, amount, tx_id in sorted(entries, key=lambda e: e[0]):
        if pay >= amount - OUTSTANDING_EPSILON:
            pay -= amount
            continue
        if pay > OUTSTANDING_EPSILON:
            amount -= pay
            pay = 0.0
        remaining.append((when, amount, tx_id))
    return remaining


def compute_recovery_actions(
    session: Session, merchant_id: Any, now: datetime | None = None
) -> list[dict[str, Any]]:
    """The ladder for one merchant: which customers get messaged today.

    Returns one action per customer with an explicit outstanding balance
    (FIFO-adjusted) whose oldest surviving entry is 15+ days old, worst
    debtor first. 0-14d balances return nothing — the weekly nudge covers
    fresh udhaar (design: tier "none")."""
    now = _aware(now) if now else datetime.now(timezone.utc)
    merchant_id = merchant_id if isinstance(merchant_id, uuid.UUID) else uuid.UUID(str(merchant_id))
    merchant = session.get(Merchant, merchant_id)
    shop = (merchant.display_name if merchant else None) or "our shop"

    txs = session.scalars(
        select(Transaction).where(
            Transaction.merchant_id == merchant_id,
            Transaction.kind.in_(_KINDS),
            Transaction.status != "rejected",
        )
    ).all()

    given: dict[Any, list[tuple[datetime, float, Any]]] = defaultdict(list)
    paid: dict[Any, float] = defaultdict(float)
    for t in txs:
        if t.customer_id is None:
            continue  # unlinked udhaar can never be messaged
        if t.kind == "udhar_given":
            given[t.customer_id].append((_aware(t.occurred_at), float(t.amount_pkr), t.id))
        else:
            paid[t.customer_id] += float(t.amount_pkr)

    customers = {
        c.id: c
        for c in session.scalars(
            select(Customer).where(Customer.merchant_id == merchant_id)
        ).all()
    }

    actions: list[dict[str, Any]] = []
    for cust_id, entries in given.items():
        remaining = _fifo_outstanding(entries, paid.get(cust_id, 0.0))
        if not remaining:
            continue  # fully settled — nothing to recover
        outstanding = sum(amount for _, amount, _ in remaining)
        if outstanding <= OUTSTANDING_EPSILON:
            continue  # design rule: no message without an explicit balance > 0
        oldest_when, _, oldest_tx_id = remaining[0]  # FIFO order: first = oldest
        oldest_days = max(0, (now - oldest_when).days)
        tier = tier_for_days(oldest_days)
        if tier is None:
            continue  # 0-14d: the weekly nudge covers fresh udhaar
        customer = customers.get(cust_id)
        actions.append(
            {
                "customer": customer.name if customer else "Customer",
                "customer_id": str(cust_id),
                "phone": customer.phone if customer else None,
                "amount": round(outstanding, 2),
                "oldest_days": oldest_days,
                "tier": tier,
                "message": build_message(tier, outstanding, shop, oldest_when),
                "oldest_tx_id": str(oldest_tx_id) if oldest_tx_id is not None else None,
            }
        )
    actions.sort(key=lambda a: -a["oldest_days"])  # worst debtor first
    return actions


# --- idempotency (one message per customer per PKT day) -----------------------


def _start_of_pkt_day_utc(now: datetime) -> datetime:
    """Midnight PKT of `now`'s local day, expressed in UTC — the cutoff the
    per-day idempotency check compares stored created_at values against."""
    pkt_now = _aware(now).astimezone(PKT)
    return pkt_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def _already_sent_today(session: Session, merchant_id: Any, now: datetime) -> set[str]:
    """customer_ids (as str) already covered by a recovery message earlier
    this PKT day (design rule 1). Loads the merchant's recovery rows and
    filters in Python — SQLite stores/returns naive datetimes and mixed UTC
    offsets make SQL-side comparisons unreliable."""
    cutoff = _start_of_pkt_day_utc(now)
    rows = session.scalars(
        select(OutboundMessage).where(
            OutboundMessage.merchant_id == merchant_id,
            OutboundMessage.kind.like("recovery%"),
        )
    ).all()
    covered: set[str] = set()
    for row in rows:
        payload = row.payload or {}
        if payload.get("customer_id") and _aware(row.created_at) >= cutoff:
            covered.add(str(payload["customer_id"]))
    return covered


# --- sending -------------------------------------------------------------------


def _record(
    session: Session,
    merchant: Merchant,
    *,
    kind: str,
    body: str,
    customer_id: str,
    tier: str,
    transaction_id: uuid.UUID | None,
    now: datetime,
) -> OutboundMessage:
    """One outbound_messages audit row (payload carries the per-customer
    idempotency key; created_at is pinned to the run's `now` so the per-day
    check stays deterministic when `now` is injected)."""
    row = OutboundMessage(
        merchant_id=merchant.id,
        transaction_id=transaction_id,
        kind=kind,
        body=body,
        payload={"customer_id": customer_id, "tier": tier},
        created_at=_aware(now).astimezone(timezone.utc),
    )
    session.add(row)
    return row


def send_recovery_messages(
    session: Session, merchant_id: Any | None = None, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Execute the ladder: compute actions per merchant, deliver every
    customer message (and its fine-print CC) via deliver(), fire the 45d+
    shopkeeper notices, and record everything. Mock-safe: deliver() logs in
    mock mode, and every send gets an audit row either way.

    merchant_id=None runs ALL merchants (the nightly-cron shape); a specific
    id runs just that merchant. Returns one result row per merchant:
      sent          — every outbound message this run (kind + recipient)
      no_phone      — customers skipped for a missing number (listed for the
                      shopkeeper; their 45d+ notice still fires, rule 3/4)
      skipped_today — customers already covered earlier this PKT day
    """
    now = _aware(now) if now else datetime.now(timezone.utc)
    if merchant_id is None:
        merchants = session.scalars(select(Merchant)).all()
    else:
        mid = merchant_id if isinstance(merchant_id, uuid.UUID) else uuid.UUID(str(merchant_id))
        found = session.get(Merchant, mid)
        merchants = [found] if found is not None else []

    results: list[dict[str, Any]] = []
    for merchant in merchants:
        actions = compute_recovery_actions(session, merchant.id, now=now)
        covered = _already_sent_today(session, merchant.id, now)
        result: dict[str, Any] = {
            "merchant_id": str(merchant.id),
            "merchant": merchant.display_name,
            "sent": [],
            "no_phone": [],
            "skipped_today": [],
        }
        for action in actions:
            cust_key = action["customer_id"]
            tier = action["tier"]
            if cust_key in covered:
                result["skipped_today"].append({"customer": action["customer"], "tier": tier})
                continue

            if not action["phone"]:
                # Rule 4: never message a customer without a number — list
                # them instead. Rule 3 still applies: the shopkeeper's 45d+
                # notice fires regardless.
                if tier == TIER_ESCALATION:
                    body = shopkeeper_notice(action["customer"], no_phone=True)
                    sent = deliver(merchant.wa_id or "", body)
                    _record(
                        session, merchant,
                        kind=f"recovery_{tier}_shopkeeper", body=body,
                        customer_id=cust_key, tier=tier,
                        transaction_id=None, now=now,
                    )
                    result["sent"].append(
                        {"customer": action["customer"], "to": merchant.wa_id,
                         "kind": f"recovery_{tier}_shopkeeper", "body": body, "send": sent}
                    )
                result["no_phone"].append(
                    {
                        "customer": action["customer"],
                        "tier": tier,
                        "amount": action["amount"],
                        "oldest_days": action["oldest_days"],
                    }
                )
                covered.add(cust_key)  # the notice covers today for this customer
                continue

            # 1) the customer message itself
            sent = deliver(action["phone"], action["message"])
            _record(
                session, merchant,
                kind=f"recovery_{tier}", body=action["message"],
                customer_id=cust_key, tier=tier,
                transaction_id=(uuid.UUID(action["oldest_tx_id"])
                                  if action.get("oldest_tx_id") else None),
                                  now=now,
            )
            result["sent"].append(
                {"customer": action["customer"], "to": action["phone"],
                 "kind": f"recovery_{tier}", "body": action["message"], "send": sent}
            )

            # 2) the fine-print CC to the shopkeeper's thread (rule 2)
            cc = cc_body(action["customer"], action["message"])
            cc_sent = deliver(merchant.wa_id or "", cc)
            _record(
                session, merchant,
                kind=f"recovery_{tier}_cc", body=cc,
                customer_id=cust_key, tier=tier,
                transaction_id=(uuid.UUID(action["oldest_tx_id"])
                                  if action.get("oldest_tx_id") else None),
                                  now=now,
            )
            result["sent"].append(
                {"customer": action["customer"], "to": merchant.wa_id,
                 "kind": f"recovery_{tier}_cc", "body": cc, "send": cc_sent}
            )

            # 3) the separate 45d+ escalation notice to the shopkeeper (rule 3)
            if tier == TIER_ESCALATION:
                notice = shopkeeper_notice(action["customer"])
                sk_sent = deliver(merchant.wa_id or "", notice)
                _record(
                    session, merchant,
                    kind=f"recovery_{tier}_shopkeeper", body=notice,
                    customer_id=cust_key, tier=tier,
                    transaction_id=(uuid.UUID(action["oldest_tx_id"])
                                  if action.get("oldest_tx_id") else None),
                                  now=now,
                )
                result["sent"].append(
                    {"customer": action["customer"], "to": merchant.wa_id,
                     "kind": f"recovery_{tier}_shopkeeper", "body": notice, "send": sk_sent}
                )
            covered.add(cust_key)
        session.commit()
        results.append(result)
    return results
