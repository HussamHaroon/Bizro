"""Pydantic models mirroring server/schema.md §1 — the pipeline output contract.

Deviations from the JSON example (documented in voice-agent/notes.md §4):
- `amount_pkd` allows 0.0: 0.0 means "amount unknown / not guessed" and always travels
  with flag=low_confidence + a clarification question. Never a guessed value.
- `mock: bool = False`: top-level marker so a mock payload can never be presented as
  real model output (SKILL.md hard rule).
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
    amount_pkd: float = Field(ge=0)  # positive; 0.0 only for unknown (flagged) parses
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

    @field_validator("amount_pkd")
    @classmethod
    def _no_fractional_paisa_noise(cls, v: float) -> float:
        return round(float(v), 2)
