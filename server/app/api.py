"""REST API surface — server/schema.md §4.

- GET   /api/merchants/{id}/transactions?from=&to=&kind=
- GET   /api/merchants/{id}/udhar                     (derived view, schema.md §3)
- POST  /api/transactions/{id}/confirm
- PATCH /api/transactions/{id}                        (audit-preserving correction)
- GET   /api/merchants/{id}/report/preview
- GET   /health lives in main.py

PATCH audit rule: the pre-edit snapshot of every editable field is stored in
`transactions.original_values` on the FIRST edit (never overwritten), and the
response returns `original_values` alongside the edited row. Source provenance
columns (source_type/media/model/confidence/raw_model_output) are immutable.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from . import dispatch
from .db import CreditReport, Customer, Merchant, Transaction, db_session
from .schemas import TransactionPatch, transaction_to_wire

router = APIRouter(prefix="/api")

_EDITABLE_FIELDS = ("kind", "amount_pkd", "currency", "description", "occurred_at", "item_lines", "flag")


def _get_merchant(session, merchant_id: str) -> Merchant:
    try:
        mid = uuid.UUID(merchant_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid merchant id (not a UUID)")
    m = session.get(Merchant, mid)
    if m is None:
        raise HTTPException(status_code=404, detail="merchant not found")
    return m


def _get_transaction(session, transaction_id: str) -> Transaction:
    try:
        tid = uuid.UUID(transaction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid transaction id (not a UUID)")
    tx = session.get(Transaction, tid)
    if tx is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return tx


@router.get("/merchants/{merchant_id}/transactions")
def list_transactions(
    merchant_id: str,
    _from: date | None = Query(None, alias="from"),
    to: date | None = None,
    kind: str | None = None,
):
    with db_session() as session:
        _get_merchant(session, merchant_id)
        q = (
            select(Transaction, Customer)
            .outerjoin(Customer, Transaction.customer_id == Customer.id)
            .where(Transaction.merchant_id == uuid.UUID(merchant_id))
            .order_by(Transaction.occurred_at.desc())
        )
        if _from is not None:
            q = q.where(Transaction.occurred_at >= datetime.combine(_from, time.min, tzinfo=timezone.utc))
        if to is not None:
            end = datetime.combine(to, time.min, tzinfo=timezone.utc) + timedelta(days=1)
            q = q.where(Transaction.occurred_at < end)
        if kind:
            q = q.where(Transaction.kind == kind)

        rows = session.execute(q).all()
        return {
            "count": len(rows),
            "transactions": [
                transaction_to_wire(tx, customer.name if customer else None, customer.phone if customer else None)
                for tx, customer in rows
            ],
        }


@router.get("/merchants/{merchant_id}/udhar")
def udhar_outstanding(merchant_id: str):
    """Udhar Radar — derived view, no new tables (schema.md §3):
    outstanding = Σ(udhar_given) − Σ(udhar_settlement) over confirmed+pending."""
    with db_session() as session:
        _get_merchant(session, merchant_id)
        rows = session.execute(
            select(Customer, Transaction)
            .join(Transaction, Transaction.customer_id == Customer.id)
            .where(
                Transaction.merchant_id == uuid.UUID(merchant_id),
                Transaction.kind.in_(["udhar_given", "udhar_settlement"]),
                Transaction.status.in_(["confirmed", "pending", "edited"]),
            )
        ).all()

        by_customer: dict[uuid.UUID, dict[str, Any]] = {}
        for customer, tx in rows:
            entry = by_customer.setdefault(
                customer.id, {"name": customer.name, "phone": customer.phone, "outstanding": 0.0}
            )
            sign = 1 if tx.kind == "udhar_given" else -1
            entry["outstanding"] += sign * float(tx.amount_pkd)

        customers = [
            {
                "customer_id": str(cid),
                "name": e["name"],
                "phone": e["phone"],
                "outstanding_pkd": round(e["outstanding"], 2),
            }
            for cid, e in by_customer.items()
            if round(e["outstanding"], 2) != 0
        ]
        return {
            "merchant_id": merchant_id,
            "total_outstanding_pkd": round(sum(c["outstanding_pkd"] for c in customers), 2),
            "customers": sorted(customers, key=lambda c: -c["outstanding_pkd"]),
        }


@router.post("/transactions/{transaction_id}/confirm")
def confirm_transaction(transaction_id: str):
    with db_session() as session:
        tx = _get_transaction(session, transaction_id)
        if tx.status not in ("pending",):
            raise HTTPException(
                status_code=409,
                detail=f"cannot confirm: transaction status is '{tx.status}', not 'pending'",
            )
        tx.status = "confirmed"
        session.add(tx)
        session.commit()
        session.refresh(tx)
        return {"ok": True, "transaction_id": transaction_id, "status": tx.status}


@router.patch("/transactions/{transaction_id}")
def patch_transaction(transaction_id: str, patch: TransactionPatch):
    with db_session() as session:
        tx = _get_transaction(session, transaction_id)
        updates: dict[str, Any] = patch.model_dump(exclude_unset=True)

        if not updates:
            raise HTTPException(status_code=422, detail="empty patch")

        if tx.status == "rejected":
            raise HTTPException(status_code=409, detail="cannot edit a rejected transaction")

        counterparty = updates.pop("counterparty", None)

        # Audit: snapshot editable fields on FIRST edit only (schema.md §4).
        if tx.original_values is None:
            tx.original_values = {f: getattr(tx, f) for f in _EDITABLE_FIELDS}
            if tx.occurred_at is not None:
                tx.original_values["occurred_at"] = tx.occurred_at.isoformat()

        for field in _EDITABLE_FIELDS:
            if field in updates:
                value = updates[field]
                if field == "item_lines" and value is not None:
                    value = [dict(v) for v in value]
                setattr(tx, field, value)

        if counterparty is not None:
            name = (counterparty.get("name") or "").strip()
            if name:
                customer = session.scalar(
                    select(Customer).where(
                        Customer.merchant_id == tx.merchant_id,
                        func.lower(Customer.name) == name.lower(),
                    )
                )
                if customer is None:
                    customer = Customer(
                        merchant_id=tx.merchant_id,
                        name=name,
                        phone=counterparty.get("phone"),
                    )
                    session.add(customer)
                    session.flush()
                tx.customer_id = customer.id

        # A correction marks the entry edited unless the patch sets status itself.
        tx.status = updates.get("status") or "edited"

        session.add(tx)
        session.commit()
        session.refresh(tx)

        customer = session.get(Customer, tx.customer_id) if tx.customer_id else None
        return {
            "ok": True,
            "transaction": transaction_to_wire(
                tx, customer.name if customer else None, customer.phone if customer else None
            ),
        }


@router.get("/merchants/{merchant_id}/report/preview")
def report_preview(merchant_id: str, refresh: bool = False):
    with db_session() as session:
        merchant = _get_merchant(session, merchant_id)
        mid = merchant.id

        if not refresh:
            latest = session.scalar(
                select(CreditReport)
                .where(CreditReport.merchant_id == mid)
                .order_by(CreditReport.created_at.desc())
                .limit(1)
            )
            if latest is not None:
                return {"cached": True, "report": latest.report_json, "created_at": latest.created_at.isoformat()}

        report = dispatch.generate_report_preview(session, mid)
        today = date.today()
        row = CreditReport(
            merchant_id=mid,
            period_start=today - timedelta(days=30),
            period_end=today,
            model=report.get("generator") if isinstance(report, dict) else None,
            report_json=report,
        )
        session.add(row)
        session.commit()
        return {"cached": False, "report": report, "created_at": row.created_at.isoformat()}
