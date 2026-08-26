"""Pydantic schemas for the canonical transaction JSON — server/schema.md §1.

Pipelines (voice_agent / vision_agent / any manual-entry path) return this
shape; the server validates before persisting. Validation is deliberately
lenient about *extra* keys (raw_output is free-form) and strict about the
load-bearing ones (kind enum, positive amount, confidence bounds).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Kind = Literal["sale", "expense", "udhar_given", "udhar_settlement"]
SourceType = Literal["voice", "photo", "manual"]
Flag = Literal[
    "none", "price_anomaly", "total_mismatch", "duplicate_suspect", "low_confidence"
]
Status = Literal["pending", "confirmed", "edited", "rejected"]

# E-1 (ruling §6.10): amount enters the system as 0 < amount ≤ 10,000,000 PKR
# (1 crore, ~4× Mawakhat's max loan). Hallucinated billion-rupee entries must
# never reach the ledger/udhar/credit report.
AMOUNT_MAX_PKD = 10_000_000


class Counterparty(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    phone: str | None = None


class ItemLine(BaseModel):
    model_config = ConfigDict(extra="allow")

    item: str
    qty: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    line_total: float | None = None


class SourceInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: SourceType
    media_id: str | None = None
    model: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    raw_output: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: Any) -> Any:
        if v is None:
            raise ValueError("source.confidence is required for AI-parsed entries (schema.md §1)")
        return v


class TransactionIn(BaseModel):
    """Canonical transaction JSON — pipeline output / API wire format."""

    model_config = ConfigDict(extra="allow")

    kind: Kind
    amount_pkd: float = Field(gt=0, le=AMOUNT_MAX_PKD)
    currency: str = "PKR"
    counterparty: Counterparty | None = None
    description: str | None = None
    item_lines: list[ItemLine] = Field(default_factory=list)
    occurred_at: datetime
    source: SourceInfo
    flag: Flag = "none"
    status: Status = "pending"
    confirmation_ur: str | None = None


class TransactionPatch(BaseModel):
    """PATCH /api/transactions/{id} body — any subset of editable fields."""

    kind: Kind | None = None
    amount_pkd: float | None = Field(default=None, gt=0, le=AMOUNT_MAX_PKD)
    currency: str | None = None
    description: str | None = None
    counterparty: Counterparty | None = None
    occurred_at: datetime | None = None
    item_lines: list[ItemLine] | None = None
    flag: Flag | None = None
    status: Status | None = None


def transaction_to_wire(
    tx,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    confirmation_ur: str | None = None,
) -> dict[str, Any]:
    """Map a persisted Transaction row back to the schema.md §1 wire shape.

    W-1: `confirmation_ur` is always present on the wire (null when the stored
    outbound confirmation can't be found) — the dashboard type declares it and
    AuditTrail renders it.
    """
    counterparty = None
    if customer_name or customer_phone:
        counterparty = {"name": customer_name, "phone": customer_phone}

    source = {
        "type": tx.source_type,
        "media_id": str(tx.source_media_id) if tx.source_media_id else None,
        "model": tx.source_model,
        "confidence": tx.confidence,
    }
    if tx.raw_model_output:
        source["raw_output"] = tx.raw_model_output

    out: dict[str, Any] = {
        "id": str(tx.id),
        "merchant_id": str(tx.merchant_id),
        "kind": tx.kind,
        "amount_pkd": float(tx.amount_pkd),
        "currency": tx.currency,
        "counterparty": counterparty,
        "description": tx.description,
        "item_lines": tx.item_lines or [],
        "occurred_at": tx.occurred_at.isoformat(),
        "source": source,
        "flag": tx.flag,
        "status": tx.status,
        "confirmation_ur": confirmation_ur,
        "created_at": tx.created_at.isoformat(),
        "updated_at": tx.updated_at.isoformat(),
    }
    if tx.original_values:
        out["original_values"] = tx.original_values  # audit: pre-edit snapshot
    return out
