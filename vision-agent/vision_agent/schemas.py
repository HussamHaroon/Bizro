"""Pydantic models: OCR extraction output and the schema.md §1 transaction.

Two validation layers:
1. ``ReceiptExtraction`` — validates the model's JSON answer (with tolerant
   numeric coercion: "350", "Rs 350", "1,200" -> numbers).
2. ``TransactionResult`` — validates what the pipeline returns, so tests can
   assert schema.md §1 conformance mechanically.
"""

from __future__ import annotations

import re
from datetime import datetime as _dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

_NUMERIC_NOISE = re.compile(r"(?i)(rs\.?|pkr|₨|,|\s)")


def _clean_number(value: Any) -> Any:
    """Strip currency noise from numeric-ish strings; pass everything else through."""
    if isinstance(value, str):
        cleaned = _NUMERIC_NOISE.sub("", value)
        if cleaned and re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
            return float(cleaned) if "." in cleaned else int(cleaned)
    return value


class ExtractedItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item: str = Field(min_length=1)
    qty: float = Field(gt=0)
    unit_price: float = Field(gt=0)
    unit: str | None = None
    line_total: float | None = None

    @field_validator("item", mode="before")
    @classmethod
    def _strip_item(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("qty", "unit_price", "line_total", mode="before")
    @classmethod
    def _tolerant_numbers(cls, value: Any) -> Any:
        return _clean_number(value)

    @field_validator("unit", mode="before")
    @classmethod
    def _blank_unit_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class ReceiptExtraction(BaseModel):
    """What the OCR model is asked to produce (prompts.py)."""

    model_config = ConfigDict(extra="ignore")

    is_receipt: bool = True
    supplier_name: str | None = None
    items: list[ExtractedItem] = Field(default_factory=list)
    stated_total: float | None = Field(default=None, gt=0)
    unclear_parts: list[str] = Field(default_factory=list)
    self_confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator("supplier_name", mode="before")
    @classmethod
    def _blank_supplier_is_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("stated_total", "self_confidence", mode="before")
    @classmethod
    def _tolerant_numbers(cls, value: Any) -> Any:
        return _clean_number(value)

    @field_validator("unclear_parts", mode="before")
    @classmethod
    def _coerce_unclear(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        return value

    @model_validator(mode="before")
    @classmethod
    def _drop_unreadable_items(cls, data: Any) -> Any:
        """Drop item lines the model could not read (missing/zero qty or price).

        An unreadable line must not invalidate the whole extraction, and we
        never repair it by guessing — it becomes an ``unclear_parts`` note the
        confidence calculation (pipeline) and the Urdu confirmation then surface
        to the merchant. SKILL.md: "Never guess a digit."
        """
        if not isinstance(data, dict):
            return data
        items = data.get("items")
        if not isinstance(items, list):
            return data
        kept: list[Any] = []
        unclear: list[str] = [str(x) for x in (data.get("unclear_parts") or [])]
        for entry in items:
            try:
                ExtractedItem.model_validate(entry)
                kept.append(entry)
            except ValidationError:
                summary = entry.get("item") if isinstance(entry, dict) else str(entry)
                unclear.append(f"unreadable item line dropped: {summary!r}")
        data["items"] = kept
        data["unclear_parts"] = unclear
        return data


class Counterparty(BaseModel):
    name: str | None = None
    phone: str | None = None


class SourceInfo(BaseModel):
    type: str = "photo"  # voice | photo | manual (schema.md §1)
    media_id: str | None = None
    model: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    raw_output: dict[str, Any] = Field(default_factory=dict)


class TransactionResult(BaseModel):
    """schema.md §1 canonical transaction — the pipeline's return contract."""

    model_config = ConfigDict(extra="forbid")

    kind: str = "expense"
    amount_pkd: float | int = Field(gt=0)
    currency: str = "PKR"
    counterparty: Counterparty = Field(default_factory=Counterparty)
    description: str = ""
    item_lines: list[dict[str, Any]] = Field(default_factory=list)
    occurred_at: str

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _coerce_datetime(cls, v: Any) -> Any:
        # In-process callers (server dispatch) pass tz-aware datetimes; the
        # canonical wire form is the ISO-8601 string (schema.md §1).
        if isinstance(v, _dt):
            return v.isoformat()
        return v
    source: SourceInfo
    flag: str = "none"
    status: str = "pending"
    confirmation_ur: str

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        allowed = {"sale", "expense", "udhar_given", "udhar_settlement"}
        if value not in allowed:
            raise ValueError(f"kind must be one of {sorted(allowed)}")
        return value

    @field_validator("flag")
    @classmethod
    def _flag(cls, value: str) -> str:
        allowed = {"none", "price_anomaly", "total_mismatch", "duplicate_suspect", "low_confidence"}
        if value not in allowed:
            raise ValueError(f"flag must be one of {sorted(allowed)}")
        return value

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        allowed = {"pending", "confirmed", "edited", "rejected"}
        if value not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return value
