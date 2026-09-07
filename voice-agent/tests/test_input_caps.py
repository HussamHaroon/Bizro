"""Length caps on model-extracted strings (pipeline-security F4, 2026-09-07).

bizro-security: "OCR/voice-extracted strings (names, items) are length-capped
by the contract." A garbled/hostile note must degrade to the EXISTING
low-confidence clarification path — never a crash, never a confirmation over
the WhatsApp 4096-char send limit, never megabytes in the audit row.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from voice_agent.config import Settings
from voice_agent.models import (
    Counterparty,
    ItemLine,
    RawOutput,
    Transaction,
)
from voice_agent.pipeline import process_voice_note

WHEN = "2026-09-07T21:30:00+05:00"
FAKE_AUDIO = b"RIFF\xf4\x00\x00\x00WAVEfmt " + b"\x00" * 240


def _settings(**over) -> Settings:
    base = dict(
        dashscope_api_key="",
        mock_mode="always",
        numeral_style="western",
        repo_root=Path(__file__).resolve().parents[2],
    )
    base.update(over)
    return Settings(**base)


def _tx(**over) -> Transaction:
    base = dict(
        kind="udhar_given",
        amount_pkr=500.0,
        counterparty=Counterparty(name="احمد"),
        description="udhar",
        occurred_at=WHEN,
        source={
            "type": "voice",
            "media_id": None,
            "model": "qwen-flash",
            "confidence": 0.9,
            "raw_output": {"transcript": "احمد کو پانچ سو"},
        },
    )
    base.update(over)
    return Transaction(**base)


def test_over_long_model_strings_rejected_at_contract():
    """Over-cap name/item/unit/description fail validation (routing to the
    pipeline's existing clarification path) — never stored unbounded."""
    with pytest.raises(ValidationError):
        _tx(counterparty=Counterparty(name="ا" * 121))
    with pytest.raises(ValidationError):
        _tx(description="d" * 501)
    with pytest.raises(ValidationError):
        _tx(item_lines=[ItemLine(item="i" * 121, qty=1, unit_price=10, line_total=10)])
    with pytest.raises(ValidationError):
        _tx(item_lines=[ItemLine(item="i", qty=1, unit="u" * 25, unit_price=10, line_total=10)])
    # the cap boundary itself is accepted
    _tx(counterparty=Counterparty(name="ا" * 120))


def test_transcript_capped_not_rejected():
    """The audit transcript is an echo — truncated at 4000, never an error,
    so a runaway model reply cannot land megabytes in raw_model_output."""
    raw = RawOutput(transcript="ت" * 10_000)
    assert len(raw.transcript) == 4000
    tx = _tx(source={"type": "voice", "confidence": 0.9,
                     "raw_output": {"transcript": "ت" * 10_000}})
    assert len(tx.source.raw_output.transcript) == 4000


def test_hostile_over_long_name_becomes_clarification_not_crash(tmp_path, monkeypatch):
    """End-to-end: a model reply carrying a 10k-char customer name degrades to
    the low-confidence clarification — no crash, confirmation stays short."""
    import voice_agent.pipeline as pl

    hostile = {
        "transcript": "نوٹ",
        "confidence": 0.9,
        "transaction": {
            "kind": "udhar_given",
            "amount_pkr": 500,
            "counterparty": {"name": "ا" * 10_000, "phone": None},
            "description": "udhar",
            "item_lines": [],
            "unclear": [],
        },
    }
    monkeypatch.setattr(
        pl, "mock_response_text",
        lambda s: "```json\n" + json.dumps(hostile, ensure_ascii=False) + "\n```",
    )
    p = tmp_path / "note.wav"
    p.write_bytes(FAKE_AUDIO)
    tx = process_voice_note(p, occurred_at=WHEN, settings=_settings())
    assert tx["flag"] == "low_confidence"
    assert tx["amount_pkr"] is None
    assert "?" in tx["confirmation_ur"] or "؟" in tx["confirmation_ur"]
    assert len(tx["confirmation_ur"]) < 1000
