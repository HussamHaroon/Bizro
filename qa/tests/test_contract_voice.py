"""Voice pipeline mock outputs vs the qa-agent schema.md mirror (§1 + §6).

Every canned voice scenario runs through the REAL pipeline assembly (mock mode
fakes only the network call) and the resulting dict is validated against the
mirror written from schema.md, not against voice_agent's own models.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from mirror_schema import MirrorTransaction, mock_marker_locations

from voice_agent.config import Settings as VoiceSettings
from voice_agent.mock_data import SCENARIOS
from voice_agent.pipeline import process_voice_note

VOICE_SETTINGS = VoiceSettings(mock_mode="always")

HAPPY = ["clean_udhar", "sale_with_items", "mixed_urdu_english", "expense_supplier"]
UNCLEAR = ["ambiguous_amount", "unclear_kind", "garbage_audio"]


def _audio(tmp_path: Path, name: str = "note.ogg") -> Path:
    # >=64 non-null junk bytes => infer_scenario would pick clean_udhar; we
    # always pin the scenario explicitly, so content only needs to be readable.
    p = tmp_path / name
    p.write_bytes(b"\x01" + b"mock-audio-payload " * 8)
    return p


@pytest.mark.parametrize("scenario", HAPPY)
def test_happy_scenario_conforms_to_schema_mirror(tmp_path, scenario):
    tx = process_voice_note(
        _audio(tmp_path), mock_scenario=scenario, settings=VOICE_SETTINGS
    )
    mirror = MirrorTransaction.model_validate(tx)  # raises on any drift
    assert mirror.amount_pkd and mirror.amount_pkd > 0
    assert mirror.source.confidence >= 0.0
    assert (mirror.confirmation_ur or "").strip()


@pytest.mark.parametrize("scenario", UNCLEAR)
def test_unclear_scenario_never_guesses(tmp_path, scenario):
    """Current voice behavior: amount 0.0 + low_confidence + clarification.

    The clarification question itself must be present and ask about the right
    thing (amount for ambiguous_amount, kind for unclear_kind).
    """
    tx = process_voice_note(
        _audio(tmp_path), mock_scenario=scenario, settings=VOICE_SETTINGS
    )
    assert tx["flag"] == "low_confidence"
    assert tx["confirmation_ur"].strip()
    if scenario == "ambiguous_amount":
        assert tx["amount_pkd"] == 0.0  # documented deviation: 0.0, not null
        assert "رقم" in tx["confirmation_ur"]  # asks about the amount


@pytest.mark.xfail(
    reason="F-1 [P1]: voice returns amount_pkd=0.0 for unknown amounts; schema.md "
    "§6.2 ruling requires null. Server TransactionIn(gt=0) rejects both, so the "
    "merchant gets silence instead of the clarification question.",
    strict=False,
)
@pytest.mark.parametrize("scenario", UNCLEAR)
def test_unclear_scenario_null_amount_per_ruling_6_2(tmp_path, scenario):
    tx = process_voice_note(
        _audio(tmp_path), mock_scenario=scenario, settings=VOICE_SETTINGS
    )
    # §6.2: amount_pkd null + low_confidence. Mirror accepts null ONLY then.
    MirrorTransaction.model_validate(tx)


def test_occurred_at_wire_form_is_iso_string(tmp_path):
    tx = process_voice_note(
        _audio(tmp_path), mock_scenario="clean_udhar", settings=VOICE_SETTINGS
    )
    assert isinstance(tx["occurred_at"], str)  # §6.6: string on the wire
    dt.datetime.fromisoformat(tx["occurred_at"])  # must parse


def test_occurred_at_accepts_datetime_and_string_inputs(tmp_path):
    when = dt.datetime(2026, 8, 21, 19, 3, tzinfo=dt.timezone.utc)
    for value in (when, when.isoformat()):
        tx = process_voice_note(
            _audio(tmp_path), mock_scenario="clean_udhar",
            occurred_at=value, settings=VOICE_SETTINGS,
        )
        assert isinstance(tx["occurred_at"], str)
        assert dt.datetime.fromisoformat(tx["occurred_at"]) == when


@pytest.mark.xfail(
    reason="F-2 [P1]: voice mock rows persist raw_output.mock_scenario / "
    "mock_note, not the canonical §6.3 marker source.raw_output.mock=true — "
    "any consumer keying on the ruling's field misses voice mock rows.",
    strict=False,
)
def test_mock_marker_canonical_6_3(tmp_path):
    tx = process_voice_note(
        _audio(tmp_path), mock_scenario="clean_udhar", settings=VOICE_SETTINGS
    )
    assert "source.raw_output.mock" in mock_marker_locations(tx)


def test_mock_marker_current_voice_convention(tmp_path):
    """What voice actually does today (documents the F-2 deviation)."""
    tx = process_voice_note(
        _audio(tmp_path), mock_scenario="clean_udhar", settings=VOICE_SETTINGS
    )
    raw = tx["source"]["raw_output"]
    assert raw.get("mock_scenario") == "clean_udhar"  # non-canonical marker
    assert tx.get("mock") is True  # top-level marker exists pre-persist


def test_threshold_boundary_exact_0_75_is_not_low_confidence(tmp_path):
    """§Threshold rule is strict <: exactly 0.75 must NOT be flagged; a hair
    below must be. Voice pipeline's own derived-flag logic."""
    from voice_agent.models import Transaction
    from voice_agent.pipeline import _apply_derived_flags

    def build(conf: float) -> Transaction:
        return Transaction(
            kind="udhar_given",
            amount_pkd=5000.0,
            occurred_at=dt.datetime.now(dt.timezone.utc),
            source={"type": "voice", "model": None, "confidence": conf},
            mock=True,
        )

    for conf in (0.75, 0.75 + 1e-9):
        tx = build(conf)
        _apply_derived_flags(tx, VOICE_SETTINGS)
        assert tx.flag == "none", f"confidence {conf!r} must not be low_confidence"

    for conf in (0.75 - 1e-9, 0.749999, 0.7):
        tx = build(conf)
        _apply_derived_flags(tx, VOICE_SETTINGS)
        assert tx.flag == "low_confidence", f"confidence {conf!r} must be low_confidence"


def test_every_scenario_in_mock_data_is_covered():
    assert set(HAPPY) | set(UNCLEAR) == set(SCENARIOS), "new voice scenario not mirrored in qa suite"
