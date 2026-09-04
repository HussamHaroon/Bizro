"""Pydantic models mirroring server/schema.md §1 — the pipeline output contract.

- `amount_pkr` is nullable per §6.2/§6.9: `null` means "amount unknown / not guessed"
  and always travels with flag=low_confidence + a clarification question in
  `confirmation_ur`. When present it is a positive number bounded 0 < x ≤ 10_000_000
  (§6.10). Never a guessed value, never 0.0.
- `mock: bool = False`: top-level marker so a mock payload can never be presented as
  real model output (SKILL.md hard rule). Mirrors `source.raw_output.mock` (§6.3/§6.11).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Kind = Literal["sale", "expense", "udhar_given", "udhar_settlement"]
Flag = Literal["none", "price_anomaly", "total_mismatch", "duplicate_suspect", "low_confidence"]
Status = Literal["pending", "confirmed", "edited", "rejected"]


class Counterparty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    phone: str | None = None


class ItemLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str
    qty: float = Field(ge=0)
    unit: str | None = None
    unit_price: float = Field(ge=0)
    line_total: float = Field(ge=0)


class RawOutput(BaseModel):
    model_config = ConfigDict(extra="allow")  # keep whatever the model said (audit trail)

    transcript: str = ""


class SourceBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["voice", "photo", "manual"] = "voice"
    media_id: str | None = None
    model: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)  # required for AI-parsed entries (§7.2 audit)
    raw_output: RawOutput = Field(default_factory=RawOutput)


class Transaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Kind
    # §6.2/§6.9: null = unknown (never guessed) → flag=low_confidence + clarification.
    # §6.10: when present, 0 < amount ≤ 10_000_000 (PKR 1 crore).
    amount_pkr: float | None = Field(default=None, gt=0, le=10_000_000)
    currency: str = "PKR"
    counterparty: Counterparty = Field(default_factory=Counterparty)
    description: str = ""
    item_lines: list[ItemLine] = Field(default_factory=list)
    occurred_at: datetime
    source: SourceBlock
    flag: Flag = "none"
    status: Status = "pending"
    confirmation_ur: str = ""
    mock: bool = False

    @field_validator("occurred_at")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @field_validator("amount_pkr")
    @classmethod
    def _no_fractional_paisa_noise(cls, v: float | None) -> float | None:
        return None if v is None else round(float(v), 2)
