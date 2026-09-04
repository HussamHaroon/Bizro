"""Vision Audit pipeline: receipt photo → schema.md §1 expense transaction.

``process_receipt_image`` is the single entry point the server (WhatsApp
webhook) calls. Contract notes:
- Returns the canonical transaction dict (schema.md §1): kind=expense,
  item_lines populated, source.model/confidence/raw_output per §7.2 audit trail.
- Non-receipt / unreadable images raise ``ReceiptRejected`` carrying a polite
  Urdu reply (notes.md D-V5) — schema has no reject kind and amount_pkr>0 must
  hold, so no fake transaction is ever returned.
- Every output is status="pending" (notes.md D-V3): the merchant confirms via
  WhatsApp reply or dashboard; confidence < CONFIDENCE_CONFIRM_THRESHOLD
  additionally forces flag=low_confidence + a clarification question.
- Mock runs are unmistakable: source.model="mock:<id>", raw_output.mock=true.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vision_agent.adapters import OcrAdapter, get_adapter
from vision_agent.config import Settings, default_settings
from vision_agent.sanity import FlagDetail, evaluate_flags
from vision_agent.schemas import ReceiptExtraction, TransactionResult
from vision_agent.urdu import confirmation_ur, reject_reply_ur


class ReceiptRejected(Exception):
    """The image is not a processable receipt. ``reply_ur`` is what WhatsApp
    sends back. reason: 'not_a_receipt' | 'unreadable'."""

    def __init__(self, reason: str, reply_ur: str) -> None:
        super().__init__(reply_ur)
        self.reason = reason
        self.reply_ur = reply_ur


def compute_confidence(extraction: ReceiptExtraction) -> float:
    """Audit-trail confidence for source.confidence (notes.md D-V1).

    The compatible-mode OCR endpoint returns no numeric confidence field, so we
    compute one from the extraction's own honesty signals — and never above the
    model's self-reported confidence.
    """
    confidence = 1.0
    confidence -= 0.10 * min(len(extraction.unclear_parts), 3)  # up to −0.30
    if extraction.stated_total is None:
        confidence -= 0.05
    if not extraction.items:
        confidence -= 0.20
    confidence = min(confidence, extraction.self_confidence)
    return round(max(0.0, min(1.0, confidence)), 3)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def process_receipt_image(
    image_path: str | Path,
    merchant: str | None = None,
    occurred_at: str | None = None,
    history: list[dict[str, Any]] | None = None,
    media_id: str | None = None,
    adapter: OcrAdapter | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """OCR a receipt photo and return the schema.md §1 transaction dict.

    Args:
        image_path: local path to the photo (jpg/png/webp/bmp).
        merchant: merchant identifier (audit context; the server joins by wa_id).
        occurred_at: ISO timestamp of the purchase; defaults to now (UTC).
        history: prior transactions (schema.md §1 dicts, newest-first) for the
            price-sanity flags. Empty/None simply disables those flags.
        media_id: media-blob UUID once the server has stored the raw photo.
        adapter: override the OCR adapter (tests / bake-off); default resolves
            via MOCK_MODE + OCR_MODEL.
        settings: override settings; default reads the process env.
    """
    settings = settings or default_settings()
    adapter = adapter or get_adapter(settings)
    history = history or []
    occurred_at = occurred_at or _now_iso()

    result = adapter.extract(Path(image_path))
    extraction = result.extraction

    # --- polite rejects (never persist a non-transaction; D-V5) --------------
    if not extraction.is_receipt:
        raise ReceiptRejected("not_a_receipt", reject_reply_ur("not_a_receipt"))
    item_lines = [
        {
            "item": item.item,
            "qty": _num(item.qty),
            "unit": item.unit,
            "unit_price": _num(item.unit_price),
            "line_total": _num(round(item.qty * item.unit_price, 2)),
        }
        for item in extraction.items
    ]
    if not item_lines and extraction.stated_total is None:
        raise ReceiptRejected("unreadable", reject_reply_ur("unreadable"))

    # --- amount (D-V4): stated total wins; else Σ line totals ----------------
    computed_total = round(sum(line["line_total"] for line in item_lines), 2)
    amount_pkr = float(extraction.stated_total if extraction.stated_total else computed_total)
    amount_pkr = _num(round(amount_pkr, 2))
    if amount_pkr <= 0:  # e.g. no items but a stated total of null-ish junk
        raise ReceiptRejected("unreadable", reject_reply_ur("unreadable"))

    # --- confidence + flags ---------------------------------------------------
    confidence = compute_confidence(extraction)
    low_confidence = confidence < settings.confidence_confirm_threshold
    flag, details = evaluate_flags(
        low_confidence,
        extraction,
        history,
        extraction.supplier_name,
        amount_pkr,
        occurred_at,
        ratio_threshold=settings.price_anomaly_ratio,
        min_samples=settings.price_anomaly_min_samples,
        history_window=settings.price_history_window,
        total_tolerance_pkd=settings.total_mismatch_tolerance_pkd,
        duplicate_window_minutes=settings.duplicate_window_minutes,
    )

    # --- Urdu confirmation (flag-aware) --------------------------------------
    confirmation = confirmation_ur(
        extraction.supplier_name,
        amount_pkr,
        item_lines,
        flag,
        details,
        numeral_style=settings.numeral_style,
    )

    description = "Supplier purchase (receipt photo)"
    if extraction.supplier_name:
        description = f"Supplier purchase: {extraction.supplier_name}"

    raw_output: dict[str, Any] = {
        "model_response_text": result.raw_text,
        "extraction": extraction.model_dump(),
        "sanity": [_detail_json(detail) for detail in details],
        "merchant": merchant,
    }
    if result.mock:
        raw_output["mock"] = True  # never presentable as real (D0-3 / D-V7)
        raw_output["mock_note"] = result.extra.get("note", "synthetic (mock)")
    if result.error:
        raw_output["adapter_error"] = result.error

    transaction = {
        "kind": "expense",
        "amount_pkr": round(amount_pkr, 2),
        "currency": "PKR",
        "counterparty": {"name": extraction.supplier_name, "phone": None},
        "description": description,
        "item_lines": item_lines,
        "occurred_at": occurred_at,
        "source": {
            "type": "photo",
            "media_id": media_id,
            "model": result.model,
            "confidence": confidence,
            "raw_output": raw_output,
        },
        "flag": flag,
        "status": "pending",  # every entry gets the confirm step (D-V3)
        "confirmation_ur": confirmation,
    }
    # Mechanical guarantee: the dict we hand back conforms to schema.md §1.
    return TransactionResult.model_validate(transaction).model_dump(mode="json")


def _num(value: float) -> float | int:
    """2.0 -> 2 (schema.md §1 examples use integer numerals when integral)."""
    rounded = round(float(value), 2)
    return int(rounded) if rounded.is_integer() else rounded


def _detail_json(detail: FlagDetail) -> dict[str, Any]:
    return {"kind": detail.kind, "message": detail.message, "data": detail.data}
