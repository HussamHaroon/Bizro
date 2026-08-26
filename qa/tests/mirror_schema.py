"""qa-agent's OWN pydantic mirror of server/schema.md §1 + §6 (v0.2 rulings).

Written from the schema document, NOT from either pipeline's models — that is
the point of cross-package contract conformance: if voice/vision drift from
schema.md, this mirror must catch it even when their own suites stay green.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Kind = Literal["sale", "expense", "udhar_given", "udhar_settlement"]
SourceType = Literal["voice", "photo", "manual"]
Flag = Literal["none", "price_anomaly", "total_mismatch", "duplicate_suspect", "low_confidence"]
Status = Literal["pending", "confirmed", "edited", "rejected"]


class MirrorCounterparty(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str | None = None
    phone: str | None = None


class MirrorItemLine(BaseModel):
    model_config = ConfigDict(extra="allow")
    item: str
    qty: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    line_total: float | None = None


class MirrorSource(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: SourceType
    media_id: str | None = None
    model: str | None = None
    confidence: float  # REQUIRED for AI-parsed entries (§1 / §7.2 audit trail)

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence_required(cls, v):
        if v is None:
            raise ValueError("source.confidence is required for AI-parsed entries")
        return v


class MirrorTransaction(BaseModel):
    """schema.md §1 canonical transaction + §6.2/§6.6 rulings.

    §6.2: unknown amount => ``amount_pkd: null`` (never 0, never a guess).
    §6.6: wire form of occurred_at is ALWAYS an ISO-8601 string (tz-aware).
    """

    model_config = ConfigDict(extra="allow")
    kind: Kind
    amount_pkd: float | None = None
    currency: str = "PKR"
    counterparty: MirrorCounterparty | None = None
    description: str | None = None
    item_lines: list[MirrorItemLine] = []
    occurred_at: str
    source: MirrorSource
    flag: Flag = "none"
    status: Status = "pending"
    confirmation_ur: str | None = None

    @model_validator(mode="after")
    def _check_rulings(self):
        # §6.2 — amount is null (unknown, flagged) or strictly positive.
        if self.amount_pkd is not None and not self.amount_pkd > 0:
            raise ValueError(
                f"amount_pkd must be null (unknown) or > 0, got {self.amount_pkd} "
                "(§6.2: persisting 0 or a guess is a contract violation)"
            )
        if self.amount_pkd is None and self.flag != "low_confidence":
            raise ValueError("amount_pkd null must travel with flag=low_confidence (§6.2)")
        # §6.6 — wire occurred_at is an ISO-8601 string.
        try:
            dt = datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError(
                f"occurred_at must be an ISO-8601 string on the wire, got {self.occurred_at!r} (§6.6)"
            ) from exc
        if dt.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware (§1 example is +05:00)")
        # §1 — low-confidence/unknown parse carries a clarification question.
        if self.flag == "low_confidence" and not (self.confirmation_ur or "").strip():
            raise ValueError("flag=low_confidence needs a clarification question in confirmation_ur (§1)")
        return self


def mock_marker_locations(tx: dict) -> list[str]:
    """Where §6.3 mock markers can be found on a pipeline output dict."""
    places: list[str] = []
    if tx.get("mock") is True:
        places.append("top-level .mock")
    raw = ((tx.get("source") or {}).get("raw_output") or {})
    if raw.get("mock") is True:
        places.append("source.raw_output.mock")
    return places
