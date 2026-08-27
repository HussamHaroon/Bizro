"""REST API surface — server/schema.md §4.

- GET   /api/merchants/{id}/transactions?from=&to=&kind=
- GET   /api/merchants/{id}/udhar                     (derived view, schema.md §3)
- POST  /api/transactions/{id}/confirm
- PATCH /api/transactions/{id}                        (audit-preserving correction)
- GET   /api/merchants/{id}/report/preview
- GET   /api/media/{id}                              (audit trail: original voice note / receipt photo)
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
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from . import dispatch
from .db import CreditReport, Customer, Merchant, MediaBlob, OutboundMessage, Transaction, db_session
from .nudges import compute_streak
from .schemas import TransactionPatch, transaction_to_wire

router = APIRouter(prefix="/api")


@router.get("/media/{media_id}")
def get_media(media_id: str):
    """Serve the original voice note / receipt photo for the audit trail
    (design.md §7.2). Path comes from our own UUID-named storage, never the client."""
    try:
        mid = uuid.UUID(media_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid media id")
    with db_session() as session:
        blob = session.get(MediaBlob, mid)
        if blob is None:
            raise HTTPException(status_code=404, detail="media not found")
        path = blob.storage_path
        mime = blob.mime_type
    import os

    if not os.path.isfile(path):
        raise HTTPException(status_code=410, detail="media file missing on disk")
    return FileResponse(path, media_type=mime)

_EDITABLE_FIELDS = ("kind", "amount_pkd", "currency", "description", "occurred_at", "item_lines", "flag")


@router.get("/merchants")
def list_merchants():
    """Merchant picker source (D1-2); also proves server liveness for the dashboard."""
    with db_session() as session:
        rows = session.scalars(select(Merchant).order_by(Merchant.created_at)).all()
        return [{"id": str(m.id), "display_name": m.display_name, "wa_id": m.wa_id} for m in rows]


def _get_merchant(session, merchant_id: str) -> Merchant:
    # 'me' = first merchant (single-merchant demo mode, ruling D1-2) — lets the
    # dashboard go live with zero VITE_MERCHANT_ID configuration.
    if merchant_id == "me":
        m = session.scalars(select(Merchant).order_by(Merchant.created_at)).first()
        if m is None:
            raise HTTPException(
                status_code=404, detail="no merchants yet — seed data or send a webhook first"
            )
        return m
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


def _confirmation_ur(session, transaction_id: uuid.UUID) -> str | None:
    """W-1: the WhatsApp confirmation we sent for this transaction (earliest
    outbound row), so wire rows carry confirmation_ur."""
    row = session.scalar(
        select(OutboundMessage)
        .where(
            OutboundMessage.transaction_id == transaction_id,
            OutboundMessage.kind == "confirmation_text",
        )
        .order_by(OutboundMessage.created_at)
        .limit(1)
    )
    return row.body if row else None


def _confirmation_map(session, tx_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Batch form of _confirmation_ur for list endpoints."""
    if not tx_ids:
        return {}
    rows = session.scalars(
        select(OutboundMessage).where(
            OutboundMessage.transaction_id.in_(tx_ids),
            OutboundMessage.kind == "confirmation_text",
        )
    ).all()
    out: dict[uuid.UUID, str] = {}
    for row in sorted(rows, key=lambda r: r.created_at):
        if row.transaction_id not in out:
            out[row.transaction_id] = row.body or ""
    return out


def _tx_to_wire(session, tx: Transaction, customer: Customer | None) -> dict:
    return transaction_to_wire(
        tx,
        customer.name if customer else None,
        customer.phone if customer else None,
        confirmation_ur=_confirmation_ur(session, tx.id),
    )


@router.get("/merchants/{merchant_id}/transactions")
def list_transactions(
    merchant_id: str,
    _from: date | None = Query(None, alias="from"),
    to: date | None = None,
    kind: str | None = None,
):
    with db_session() as session:
        merchant = _get_merchant(session, merchant_id)
        q = (
            select(Transaction, Customer)
            .outerjoin(Customer, Transaction.customer_id == Customer.id)
            .where(Transaction.merchant_id == merchant.id)
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
        confirmations = _confirmation_map(session, [tx.id for tx, _ in rows])
        return {
            "count": len(rows),
            "transactions": [
                transaction_to_wire(
                    tx,
                    customer.name if customer else None,
                    customer.phone if customer else None,
                    confirmation_ur=confirmations.get(tx.id),
                )
                for tx, customer in rows
            ],
        }


@router.get("/merchants/{merchant_id}/udhar")
def udhar_outstanding(merchant_id: str):
    """Udhar Radar — derived view, no new tables (schema.md §3):
    outstanding = Σ(udhar_given) − Σ(udhar_settlement) over confirmed+pending."""
    with db_session() as session:
        merchant = _get_merchant(session, merchant_id)
        rows = session.execute(
            select(Customer, Transaction)
            .join(Transaction, Transaction.customer_id == Customer.id)
            .where(
                Transaction.merchant_id == merchant.id,
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
        # §6.7 (C-1): mutation responses carry the wire row top-level — the
        # dashboard consumes the body directly as the Transaction.
        return _tx_to_wire(session, tx, session.get(Customer, tx.customer_id) if tx.customer_id else None)


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
        # §6.7 (C-2): the wire transaction at TOP level (original_values rides
        # along inside the row per transaction_to_wire) — no {ok, transaction}
        # wrapper; the dashboard maps rows by body.id.
        return _tx_to_wire(session, tx, customer)


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
        return _refresh_report(session, mid)


def _report_history_entry(row: CreditReport) -> dict[str, Any]:
    """§7.2 history item: {"generated_at", "score", "band"} — score/band come
    from report_json.readiness (§6.5 skeleton). Tolerates the server-fallback
    shape where readiness is a bare band string, and missing keys."""
    report = row.report_json if isinstance(row.report_json, dict) else {}
    readiness = report.get("readiness")
    if isinstance(readiness, dict):
        band = readiness.get("band")
        score = readiness.get("score")
    else:  # fallback reports store a bare band string
        band = readiness
        score = None
    return {
        "generated_at": row.created_at.isoformat(),
        "score": int(score) if score is not None else 0,
        "band": str(band or ""),
    }


@router.get("/merchants/{merchant_id}/report/history")
def report_history(merchant_id: str):
    """Readiness history (schema.md §7.2): every credit_reports row for the
    merchant, oldest→newest — the dashboard renders a trend sparkline."""
    with db_session() as session:
        merchant = _get_merchant(session, merchant_id)
        rows = session.scalars(
            select(CreditReport)
            .where(CreditReport.merchant_id == merchant.id)
            .order_by(CreditReport.created_at.asc())
        ).all()
        return {"history": [_report_history_entry(row) for row in rows]}


@router.get("/merchants/{merchant_id}/streak")
def merchant_streak(merchant_id: str):
    """Savings streak (schema.md §7.3): consecutive Mon–Sun (PKT) weeks with
    net cash-flow > 0; zero-entry weeks break the streak."""
    with db_session() as session:
        merchant = _get_merchant(session, merchant_id)
        return compute_streak(session, merchant.id)


def _refresh_report(session, mid: uuid.UUID) -> dict:
    """R-1: one refresh writes exactly ONE credit_reports row.

    credit_agent.generate_report persists its own row (report.py does the
    commit itself, with the §6.3 `mock` key stripped); the API used to add a
    SECOND row on top. Instead: detect a row created during the generate call
    and adopt it — restoring the full returned report_json (mock key kept,
    mirroring what generate_report returns) and the real generator id — or, on
    the server-fallback path (no credit_agent), insert the single row here.
    """
    before_ids = set(
        session.scalars(select(CreditReport.id).where(CreditReport.merchant_id == mid))
    )
    report = dispatch.generate_report_preview(session, mid)

    model = None
    if isinstance(report, dict):
        model = report.get("model") or report.get("generator")

    rows_after = session.scalars(
        select(CreditReport)
        .where(CreditReport.merchant_id == mid)
        .order_by(CreditReport.created_at.desc())
    ).all()
    adopted = next((r for r in rows_after if r.id not in before_ids), None)

    if adopted is not None:
        adopted.report_json = report  # keep mock/generator keys (§6.3)
        adopted.model = model or adopted.model
        row = adopted
    else:
        today = date.today()
        row = CreditReport(
            merchant_id=mid,
            period_start=today - timedelta(days=30),
            period_end=today,
            model=model,
            report_json=report,
        )
        session.add(row)
    session.commit()
    return {"cached": False, "report": report, "created_at": row.created_at.isoformat()}
