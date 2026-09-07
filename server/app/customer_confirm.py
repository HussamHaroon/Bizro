"""Customer confirmation (two-factor entry verification) — demo showpiece.

Flow: merchant records a sale/udhar mentioning a customer with a phone →
the server pings THE CUSTOMER's WhatsApp with what was recorded → the
customer replies YES/NO from their own number → YES flips the entry to
status=confirmed + trust_tier=customer_confirmed (schema.md §11-§12), NO
rejects it politely and alerts the shopkeeper.

Design rules:
- The customer ping must NEVER break the shopkeeper flow (best-effort send).
- A customer's YES/NO is only honored for that customer's OWN pending entries
  (matched by Customer.phone).
- The merchant's own wa_id is never treated as a customer.
- Phrase sets are small and deterministic (same discipline as
  voice_agent.corrections).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Customer, OutboundMessage, Transaction

YES_RE = re.compile(r"^\s*(yes|y|haan|han|theek|sahi|confirm|ہاں|جی|ٹھیک)\b.*$", re.IGNORECASE)
NO_RE = re.compile(r"^\s*(no|n|nahi|nahin|wrong|غلط|نہیں)\b.*$", re.IGNORECASE)


def is_customer_confirmation(text: str | None) -> bool:
    """True when the text is a bare YES/NO-style confirmation (customer register)."""
    s = (text or "").strip()
    if not s or len(s) > 40:
        return False
    return bool(YES_RE.match(s) or NO_RE.match(s))


def classify_customer_reply(text: str | None) -> str | None:
    """'yes' | 'no' | None for a confirmation-style text."""
    s = (text or "").strip()
    if not s or len(s) > 40:
        return None
    if YES_RE.match(s):
        return "yes"
    if NO_RE.match(s):
        return "no"
    return None


def find_customer_by_phone(session: Session, wa_id: str) -> Customer | None:
    return session.scalars(
        select(Customer).where(Customer.phone == wa_id.strip())
    ).first()


def latest_pending_for_customer(
    session: Session, merchant_id: Any, customer_id: Any
) -> Transaction | None:
    return session.scalars(
        select(Transaction)
        .where(
            Transaction.merchant_id == merchant_id,
            Transaction.customer_id == customer_id,
            Transaction.status == "pending",
            Transaction.kind.in_(("sale", "udhar_given")),
        )
        .order_by(Transaction.created_at.desc())
        .limit(1)
    ).first()


def customer_ping_text(
    merchant_name: str,
    kind: str,
    amount: float,
    description: str,
    occurred_at,
) -> str:
    what = "cash purchase" if kind == "sale" else "credit (udhar)"
    when = occurred_at.date().isoformat() if hasattr(occurred_at, "date") else str(occurred_at)
    line = f": {description}" if description else ""
    return (
        f"Bizro (for {merchant_name}): You are recorded as receiving "
        f"PKR {float(amount):,.0f} ({what}{line}) on {when}. "
        f"Reply YES to confirm or NO if this is wrong."
    )


def _send_succeeded(sent: Any) -> bool:
    """True when a send actually went out. Three shapes reach us: the mock
    marker (simulated send — the demo's two-factor loop works offline, with
    the marker preserved on the audit row), a live Graph API success (Meta
    answers with messages[0].id), or an explicit delivered/error key from the
    best-effort wrapper. Anything else (or any error) counts as NOT pinged —
    the flag never overstates delivery."""
    if not isinstance(sent, dict) or sent.get("error"):
        return False
    if sent.get("delivered") is not None:
        return bool(sent.get("delivered"))
    return bool(sent.get("mock") or sent.get("messages"))


def ping_customers_for_entries(
    session: Session,
    merchant: Any,
    rows: list[Any],
    deliver_fn,
) -> list[dict[str, Any]]:
    """Best-effort customer pings for freshly persisted entries.

    Never raises: a failed/undeliverable ping is logged to the audit trail and
    reported in the results — the shopkeeper flow is untouched (their own
    confirmation was already sent).
    """
    results: list[dict[str, Any]] = []
    for tx in rows:
        if tx.kind not in ("sale", "udhar_given") or not tx.customer_id:
            continue
        cust = session.get(Customer, tx.customer_id)
        if cust is None or not (cust.phone or "").strip():
            continue
        body = customer_ping_text(
            merchant.display_name or "the shop",
            tx.kind,
            float(tx.amount_pkr),
            tx.description or "",
            tx.occurred_at,
        )
        try:
            sent = deliver_fn(cust.phone, body)
        except Exception as exc:  # noqa: BLE001 — ping is best-effort by contract
            sent = {"delivered": False, "error": str(exc)[:200], "to": cust.phone}
        session.add(
            OutboundMessage(
                merchant_id=merchant.id,
                transaction_id=tx.id,
                kind="customer_confirmation_request",
                body=body,
                payload={
                    "to": cust.phone,
                    "delivered": _send_succeeded(sent),
                    # §6.3: the mock marker survives onto the audit row
                    "mock": bool(isinstance(sent, dict) and sent.get("mock")),
                },
            )
        )
        results.append(
            {
                "transaction_id": str(tx.id),
                "customer": cust.name,
                "to": cust.phone,
                "pinged": _send_succeeded(sent),
                "body": body,
            }
        )
    return results


def apply_customer_reply(
    session: Session,
    merchant: Any,
    customer: Customer,
    reply: str,
    deliver_fn,
    send_reply_fn,
) -> dict[str, Any]:
    """Apply a YES/NO from a customer's own number to their latest pending entry.

    Returns the webhook outcome dict. Customer-facing replies go back to the
    CUSTOMER's thread; on NO the shopkeeper is additionally alerted on their
    own thread."""
    verdict = classify_customer_reply(reply)
    tx = latest_pending_for_customer(session, merchant.id, customer.id)
    if tx is None:
        body = "Nothing is waiting for your confirmation right now."
        sent = deliver_fn(customer.phone, body)
        session.add(OutboundMessage(
            merchant_id=merchant.id, kind="customer_reply", body=body,
            payload={"to": customer.phone, "delivered": _send_succeeded(sent)}))
        return {"ok": True, "type": "text", "customer_reply": verdict,
                "applied": False, "reply": body, "sent": sent}

    if verdict == "yes":
        tx.status = "confirmed"
        tx.trust_tier = "customer_confirmed"
        session.add(tx)
        body = (f"Thank you — PKR {float(tx.amount_pkr):,.0f} at "
                f"{merchant.display_name or 'the shop'} is confirmed.")
        out = {"applied": True, "confirmed": True}
    else:
        tx.flag = "low_confidence"
        session.add(tx)
        body = (f"Noted — you marked PKR {float(tx.amount_pkr):,.0f} at "
                f"{merchant.display_name or 'the shop'} as incorrect. "
                f"The shop has been asked to correct it.")
        # alert the shopkeeper on their own thread
        send_reply_fn(
            session, merchant,
            f"Your customer {customer.name} marked PKR "
            f"{float(tx.amount_pkr):,.0f} ({tx.description or tx.kind}) as "
            "incorrect — please review and correct that entry.",
        )
        out = {"applied": True, "confirmed": False}
    session.commit()  # the flip must survive the session close (webhook scope)

    sent = deliver_fn(customer.phone, body)  # back to the customer's thread
    session.add(OutboundMessage(
        merchant_id=merchant.id, transaction_id=tx.id,
        kind="customer_reply", body=body,
        payload={"to": customer.phone, "delivered": _send_succeeded(sent)}))
    out.update({"ok": True, "type": "text", "customer_reply": verdict,
                "transaction_id": str(tx.id), "reply": body, "sent": sent})
    return out
