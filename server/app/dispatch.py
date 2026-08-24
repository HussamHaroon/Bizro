"""Pipeline dispatch — the server's only doorway into voice/vision/credit code.

Call contracts (each agent's SKILL.md; schema.md §1 is the shared output shape):
- voice_agent.pipeline.process_voice_note(audio_path, merchant, occurred_at) -> tx dict
- vision_agent.pipeline.process_receipt_image(image_path, merchant, occurred_at) -> tx dict
- credit_agent.report.generate_report(merchant_id, period) -> credit report

Packages are being built in parallel worktrees, so every import is lazy and
defensive: if a package isn't importable yet, a SERVER FALLBACK runs instead —
a clearly-labeled synthetic pipeline (source.model=null, raw_output.mock=true,
confidence below the confirm threshold so entries stay pending). Fallback
output can never be mistaken for real model results (STATUS.md D0-3).
"""

from __future__ import annotations

import importlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import whatsapp_client
from .config import ensure_repo_root_on_path, get_settings
from .db import Customer, Merchant, OutboundMessage, Transaction
from .media import sha256_bytes
from .schemas import TransactionIn

logger = logging.getLogger("bizro.dispatch")

PipelineFn = Callable[..., dict[str, Any]]

_pipeline_cache: dict[str, PipelineFn | None] = {}


def _load_pipeline_fn(hyphen_dir: str, module: str, func: str) -> PipelineFn | None:
    """Import `module.func`, tolerating both layouts:
    repo-root/<hyphen_dir>/<module>.py  (worktree state, per each agent SKILL)
    repo-root/<module>.py               (hypothetical flat layout)
    Cached; returns None when unavailable (caller uses the server fallback).
    """
    key = f"{module}.{func}"
    if key in _pipeline_cache:
        return _pipeline_cache[key]

    ensure_repo_root_on_path()
    try:
        mod = importlib.import_module(module)
        fn = getattr(mod, func, None)
    except ImportError as exc:
        logger.info("Pipeline %s not importable yet (%s) — server fallback will run.", key, exc)
        fn = None
    _pipeline_cache[key] = fn
    return fn


def pipeline_status() -> dict[str, str]:
    """For /health: which pipelines are real packages vs server fallbacks."""
    return {
        "voice_agent": "imported" if _load_pipeline_fn("voice-agent", "voice_agent.pipeline", "process_voice_note") else "server_fallback_mock",
        "vision_agent": "imported" if _load_pipeline_fn("vision-agent", "vision_agent.pipeline", "process_receipt_image") else "server_fallback_mock",
        "credit_agent": "imported" if _load_pipeline_fn("credit-agent", "credit_agent.report", "generate_report") else "server_fallback_mock",
    }


def _call_with_occurred_at(fn: PipelineFn, path: str, merchant: dict, occurred_at: datetime) -> dict:
    """Call a pipeline per its documented signature; if the parallel agent's
    implementation expects occurred_at as an ISO string instead of a datetime,
    retry once with the string form."""
    try:
        return fn(path, merchant, occurred_at)
    except TypeError:
        return fn(path, merchant, occurred_at.isoformat())


def process_voice_note(
    audio_path: str, merchant: Merchant, occurred_at: datetime, media_sha256: str
) -> dict[str, Any]:
    fn = _load_pipeline_fn("voice-agent", "voice_agent.pipeline", "process_voice_note")
    merchant_ctx = {
        "id": str(merchant.id),
        "wa_id": merchant.wa_id,
        "display_name": merchant.display_name,
    }
    if fn is not None:
        return _call_with_occurred_at(fn, audio_path, merchant_ctx, occurred_at)
    return _fallback_voice(audio_path, merchant, occurred_at, media_sha256)


def process_receipt_image(
    image_path: str, merchant: Merchant, occurred_at: datetime, media_sha256: str
) -> dict[str, Any]:
    fn = _load_pipeline_fn("vision-agent", "vision_agent.pipeline", "process_receipt_image")
    merchant_ctx = {
        "id": str(merchant.id),
        "wa_id": merchant.wa_id,
        "display_name": merchant.display_name,
    }
    if fn is not None:
        return _call_with_occurred_at(fn, image_path, merchant_ctx, occurred_at)
    return _fallback_vision(image_path, merchant, occurred_at, media_sha256)


# --- server fallback pipelines (clearly-labeled synthetic output) -----------


def _synth_amount(seed_hex: str, lo: int, hi: int) -> int:
    """Deterministic-in-range amount derived from the media sha256 so each
    distinct blob yields a distinct synthetic amount (and repeat runs of the
    simulator on fresh blobs don't produce duplicate-looking rows)."""
    seed = int(seed_hex[:8], 16)
    return lo + seed % (hi - lo)


def _fallback_voice(
    audio_path: str, merchant: Merchant, occurred_at: datetime, media_sha256: str
) -> dict[str, Any]:
    amount = _synth_amount(media_sha256, 1500, 9000)
    return {
        "kind": "udhar_given",
        "amount_pkd": float(amount),
        "currency": "PKR",
        "counterparty": {"name": "Ahmad", "phone": None},
        "description": "Udhar given to Ahmad",
        "item_lines": [],
        "occurred_at": occurred_at,
        "source": {
            "type": "voice",
            "media_id": None,  # linked by the caller (server) on persist
            "model": None,  # null: NOT a real model parse
            "confidence": 0.55,  # below CONFIDENCE_CONFIRM_THRESHOLD → stays pending
            "raw_output": {
                "mock": True,
                "generator": "server_fallback",
                "note": (
                    "SYNTHETIC server fallback — voice_agent package not merged yet; "
                    "no model ran on this audio."
                ),
                "audio_path": str(audio_path),
                "audio_sha256": media_sha256,
            },
        },
        "flag": "low_confidence",
        "status": "pending",
        "confirmation_ur": (
            f"احمد کو {amount} روپے ادھر دیے۔ کیا یہ درست ہے؟ [mock — voice_agent not merged]"
        ),
    }


def _fallback_vision(
    image_path: str, merchant: Merchant, occurred_at: datetime, media_sha256: str
) -> dict[str, Any]:
    qty = 2 + int(media_sha256[:2], 16) % 4
    unit_price = _synth_amount(media_sha256[2:], 120, 480)
    total = qty * unit_price
    return {
        "kind": "expense",
        "amount_pkd": float(total),
        "currency": "PKR",
        "counterparty": {"name": "Karachi Wholesale Supplier", "phone": None},
        "description": "Supplier receipt (synthetic)",
        "item_lines": [
            {
                "item": "chai patti",
                "qty": qty,
                "unit": "packet",
                "unit_price": unit_price,
                "line_total": total,
            }
        ],
        "occurred_at": occurred_at,
        "source": {
            "type": "photo",
            "media_id": None,
            "model": None,
            "confidence": 0.6,
            "raw_output": {
                "mock": True,
                "generator": "server_fallback",
                "note": (
                    "SYNTHETIC server fallback — vision_agent package not merged yet; "
                    "no OCR ran on this image."
                ),
                "image_path": str(image_path),
                "image_sha256": media_sha256,
            },
        },
        "flag": "low_confidence",
        "status": "pending",
        "confirmation_ur": (
            f"رسید: چائے پتی {qty} پیکٹ × {unit_price} = {total} روپے۔ کیا یہ درست ہے؟ "
            "[mock — vision_agent not merged]"
        ),
    }


# --- persistence ------------------------------------------------------------


def persist_transaction(
    session: Session,
    merchant: Merchant,
    tx_data: dict[str, Any],
    media_row_id: uuid.UUID | None,
) -> Transaction:
    """Validate pipeline output (schema.md §1) and persist it.

    Threshold rule (schema.md §1): confidence < CONFIDENCE_CONFIRM_THRESHOLD
    forces status=pending until the merchant confirms.
    """
    parsed = TransactionIn.model_validate(tx_data)
    settings = get_settings()

    customer = None
    name = (parsed.counterparty.name if parsed.counterparty else None) or ""
    if parsed.kind in ("sale", "udhar_given", "udhar_settlement") and name.strip():
        customer = session.scalar(
            select(Customer).where(
                Customer.merchant_id == merchant.id,
                Customer.name.ilike(name.strip()),
            )
        )
        if customer is None:
            customer = Customer(
                merchant_id=merchant.id,
                name=name.strip(),
                phone=(parsed.counterparty.phone if parsed.counterparty else None),
            )
            session.add(customer)
            session.flush()

    confidence = parsed.source.confidence
    status = parsed.status or "pending"
    if confidence is not None and confidence < settings.confidence_confirm_threshold:
        status = "pending"

    # Server-known media row wins; fall back to the pipeline's reference.
    if media_row_id is None and parsed.source.media_id:
        try:
            media_row_id = uuid.UUID(str(parsed.source.media_id))
        except (ValueError, TypeError, AttributeError):
            media_row_id = None

    tx = Transaction(
        merchant_id=merchant.id,
        customer_id=customer.id if customer else None,
        kind=parsed.kind,
        amount_pkd=parsed.amount_pkd,
        currency=parsed.currency or "PKR",
        description=parsed.description,
        item_lines=[line.model_dump() for line in parsed.item_lines] or [],
        occurred_at=parsed.occurred_at,
        source_type=parsed.source.type,
        source_media_id=media_row_id,
        source_model=parsed.source.model,
        confidence=confidence,
        raw_model_output=parsed.source.raw_output or {},
        flag=parsed.flag or "none",
        status=status,
    )
    session.add(tx)
    session.flush()

    if parsed.confirmation_ur:
        session.add(
            OutboundMessage(
                merchant_id=merchant.id,
                transaction_id=tx.id,
                kind="confirmation_text",
                body=parsed.confirmation_ur,
            )
        )
    session.commit()
    return tx


def send_confirmation(merchant: Merchant, tx: Transaction, confirmation_ur: str) -> dict[str, Any]:
    """Send (or mock-log) the WhatsApp confirmation text. The outbound row is
    persisted by persist_transaction; this only does delivery."""
    return whatsapp_client.send_text(merchant.wa_id, confirmation_ur)


# --- text replies (merchant confirms/rejects by WhatsApp text) ---------------

_CONFIRM_WORDS = {"1", "haan", "han", "ji", "yes", "y", "درست", "ہاں", "جی ہاں", "ٹھیک"}
_REJECT_WORDS = {"0", "nahi", "na", "no", "n", "غلط", "نہیں", "نہیں"}


def handle_text_reply(session: Session, merchant: Merchant, text: str) -> str | None:
    """Minimal confirm/reject-by-reply. Returns the Urdu reply to send, or None
    if the text isn't a confirmation/rejection."""
    normalized = text.strip().lower()
    # normalize Urdu punctuation variants
    normalized = normalized.replace("؟", "").replace("۔", "")

    wants_confirm = any(normalized == w or normalized.startswith(w + " ") for w in _CONFIRM_WORDS)
    wants_reject = any(normalized == w or normalized.startswith(w + " ") for w in _REJECT_WORDS)
    if not (wants_confirm or wants_reject):
        return None

    tx = session.scalar(
        select(Transaction)
        .where(Transaction.merchant_id == merchant.id, Transaction.status == "pending")
        .order_by(Transaction.created_at.desc())
        .limit(1)
    )
    if tx is None:
        return "کوئی زیرِ التوا اندراج نہیں ملا۔"

    if wants_confirm:
        tx.status = "confirmed"
        reply = "شکریہ! اندراج درست کر دیا گیا۔"
    else:
        tx.status = "rejected"
        reply = "ٹھیک ہے، اندراج ہٹا دیا گیا۔"
    session.add(tx)
    session.add(
        OutboundMessage(
            merchant_id=merchant.id,
            transaction_id=tx.id,
            kind="confirmation_text",
            body=reply,
        )
    )
    session.commit()
    return reply


# --- credit report preview (credit_agent boundary) ---------------------------


def _normalize_report_result(result: Any) -> dict[str, Any]:
    """credit_agent may return a dict, a credit_reports-like row, or a pydantic
    model — coerce to a plain dict for the API layer."""
    if isinstance(result, dict):
        return result
    if hasattr(result, "report_json"):
        out = dict(result.report_json) if isinstance(result.report_json, dict) else {"report": result.report_json}
        for attr in ("id", "period_start", "period_end", "model", "narrative_ur"):
            val = getattr(result, attr, None)
            if val is not None:
                out[attr] = str(val)
        return out
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return {"report": str(result)}


def generate_report_preview(session: Session, merchant_id: uuid.UUID) -> dict[str, Any]:
    """GET /api/merchants/{id}/report/preview — try credit_agent.generate_report;
    fall back to a deterministic, clearly-labeled aggregate (never a fake LLM
    narrative)."""
    fn = _load_pipeline_fn("credit-agent", "credit_agent.report", "generate_report")
    if fn is not None:
        try:
            result = fn(merchant_id, period="last_30_days")
        except TypeError:
            result = fn(merchant_id=merchant_id, period="last_30_days")
        return _normalize_report_result(result)

    from .db import CreditReport, Transaction as Tx

    txs = session.scalars(
        select(Tx).where(Tx.merchant_id == merchant_id).order_by(Tx.occurred_at)
    ).all()
    now = datetime.now(timezone.utc)
    totals = {"sale": 0.0, "expense": 0.0, "udhar_given": 0.0, "udhar_settlement": 0.0}
    for t in txs:
        if t.status != "rejected":
            totals[t.kind] = totals.get(t.kind, 0.0) + float(t.amount_pkd)
    confirmed = sum(1 for t in txs if t.status in ("confirmed", "edited"))
    pending = sum(1 for t in txs if t.status == "pending")
    ai_parsed = [t for t in txs if t.source_type in ("voice", "photo")]
    avg_conf = (
        sum(float(t.confidence or 0.0) for t in ai_parsed) / len(ai_parsed) if ai_parsed else None
    )

    report = {
        "mock": True,
        "generator": "server_fallback",
        "note": (
            "SYNTHETIC deterministic preview — credit_agent package not merged yet; "
            "no model generated this. Aggregates are real, the 'readiness' framing is not."
        ),
        "merchant_id": str(merchant_id),
        "generated_at": now.isoformat(),
        "period": {"start": None, "end": now.date().isoformat()},
        "transaction_counts": {
            "total": len(txs), "confirmed": confirmed, "pending": pending,
            "rejected": sum(1 for t in txs if t.status == "rejected"),
        },
        "totals_pkr": totals,
        "udhar_outstanding_pkr": totals["udhar_given"] - totals["udhar_settlement"],
        "avg_parse_confidence": round(avg_conf, 3) if avg_conf is not None else None,
        "readiness": "insufficient_data" if len(txs) < 5 else "mock_preview_only",
    }
    return report
