"""Pipeline tests over the five required mock scenarios (SKILL.md deliverable 5):
clean udhar note / sale with item lines / ambiguous note (must flag, never guess) /
mixed Urdu-English / empty-garbage audio. Plus schema-conformance checks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from voice_agent.config import Settings
from voice_agent.pipeline import process_voice_note

FAKE_AUDIO = b"MOCK-AUDIO-" + bytes(range(256)) * 4  # >64B so infer_scenario picks clean

WHEN = "2026-08-21T19:03:00+05:00"


def _settings(**over) -> Settings:
    base = dict(
        dashscope_api_key="",
        mock_mode="always",
        numeral_style="western",
        confidence_confirm_threshold=0.75,
        repo_root=Path(__file__).resolve().parents[2],
    )
    base.update(over)
    return Settings(**base)


@pytest.fixture()
def audio_file(tmp_path: Path) -> Path:
    p = tmp_path / "note.ogg"
    p.write_bytes(FAKE_AUDIO)
    return p


def _run(audio_file, scenario=None, **settings_over):
    return process_voice_note(
        audio_file, merchant={"display_name": "کریانہ اسٹور"}, occurred_at=WHEN,
        media_id="11111111-1111-1111-1111-111111111111",
        settings=_settings(**settings_over), mock_scenario=scenario,
    )


def _required_keys_present(tx: dict) -> None:
    for key in ("kind", "amount_pkd", "currency", "counterparty", "description",
                "item_lines", "occurred_at", "source", "flag", "status", "confirmation_ur"):
        assert key in tx, f"missing contract key {key}"


# --- 1. clean udhar note -------------------------------------------------------


def test_clean_udhar(audio_file):
    tx = _run(audio_file, scenario="clean_udhar")
    _required_keys_present(tx)
    assert tx["kind"] == "udhar_given"
    assert tx["amount_pkd"] == 5000
    assert tx["counterparty"]["name"] == "احمد"
    assert tx["flag"] == "none"  # 0.93 ≥ 0.75
    assert tx["status"] == "pending"
    assert tx["source"]["type"] == "voice"
    assert tx["source"]["confidence"] == pytest.approx(0.93)
    assert tx["confirmation_ur"].endswith("کیا یہ درست ہے؟")
    assert "5000" in tx["confirmation_ur"] and "پانچ ہزار" in tx["confirmation_ur"]
    assert tx["source"]["raw_output"]["transcript"]


def test_mocks_are_never_presentable_as_real(audio_file):
    for scenario in ("clean_udhar", "sale_with_items", "mixed_urdu_english"):
        tx = _run(audio_file, scenario=scenario)
        assert tx["mock"] is True
        assert tx["source"]["model"] is None  # never claims a real model ran
        # §6.3/§6.11 (F-2): stored raw_output carries BOTH the canonical mock
        # marker and the scenario name for debugging
        assert tx["source"]["raw_output"]["mock"] is True
        assert tx["source"]["raw_output"]["mock_scenario"] == scenario


# --- 2. sale with item lines ---------------------------------------------------


def test_sale_with_items(audio_file):
    tx = _run(audio_file, scenario="sale_with_items")
    assert tx["kind"] == "sale"
    assert tx["amount_pkd"] == 1500
    lines = tx["item_lines"]
    assert len(lines) == 2
    assert lines[0]["item"] == "چائے پتی" and lines[0]["qty"] == 2
    assert sum(li["line_total"] for li in lines) == tx["amount_pkd"]
    assert tx["flag"] == "none"  # totals agree
    assert "1500" in tx["confirmation_ur"] and "پندرہ سو" in tx["confirmation_ur"]


def test_item_total_mismatch_flagged_not_fixed():
    from voice_agent.mock_data import SCENARIOS
    import copy

    scenario = copy.deepcopy(SCENARIOS["sale_with_items"])
    scenario["transaction"]["amount_pkd"] = 1600  # spoken total disagrees with items
    import voice_agent.mock_data as md

    md.SCENARIOS["temp_mismatch"] = scenario
    try:
        audio = b"MOCK-AUDIO-" + bytes(range(256)) * 4
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "n.ogg"
            p.write_bytes(audio)
            tx = process_voice_note(
                p, occurred_at=WHEN, settings=_settings(), mock_scenario="temp_mismatch"
            )
        assert tx["flag"] == "total_mismatch"
        assert tx["amount_pkd"] == 1600  # kept what was said, did NOT silently fix
    finally:
        md.SCENARIOS.pop("temp_mismatch", None)


def test_low_confidence_model_output_flags(audio_file):
    """Confidence below threshold but fields present → flag low_confidence, keep data."""
    import copy

    import voice_agent.mock_data as md
    from voice_agent.mock_data import SCENARIOS

    scenario = copy.deepcopy(SCENARIOS["clean_udhar"])
    scenario["confidence"] = 0.6
    md.SCENARIOS["temp_lowconf"] = scenario
    try:
        tx = _run(audio_file, scenario="temp_lowconf")
        assert tx["flag"] == "low_confidence"
        assert tx["amount_pkd"] == 5000  # data kept — flagged, not discarded
        assert tx["status"] == "pending"
    finally:
        md.SCENARIOS.pop("temp_lowconf", None)


# --- 3. ambiguous note: must flag, never guess ---------------------------------


def test_ambiguous_amount_never_guesses(audio_file):
    """§6.2/§6.9 (F-1): ambiguous amount → amount_pkd null, never 0.0, never a guess."""
    tx = _run(audio_file, scenario="ambiguous_amount")
    assert tx["flag"] == "low_confidence"
    assert tx["amount_pkd"] is None  # null = unknown; NOT 5000, NOT 6000, NOT 0.0
    assert tx["status"] == "pending"
    assert tx["source"]["confidence"] == pytest.approx(0.31)
    # confirmation is a clarification question, not a statement
    assert "کیا یہ درست ہے؟" not in tx["confirmation_ur"]
    assert "رقم" in tx["confirmation_ur"]
    assert tx["counterparty"]["name"] == "احمد"  # what WAS clear is kept
    # F-2: fallback raw_output carries the mock marker too
    assert tx["source"]["raw_output"]["mock"] is True
    assert tx["source"]["raw_output"]["mock_scenario"] == "ambiguous_amount"


def test_not_a_transaction_notes_query(audio_file):
    tx = _run(audio_file, scenario="unclear_kind")
    assert tx["flag"] == "low_confidence"
    assert tx["amount_pkd"] is None
    assert "سمجھ" in tx["confirmation_ur"]  # "I didn't understand"


# --- 4. mixed Urdu-English ------------------------------------------------------


def test_mixed_urdu_english(audio_file):
    tx = _run(audio_file, scenario="mixed_urdu_english")
    assert tx["kind"] == "sale"
    assert tx["amount_pkd"] == 5000  # "panch hazar" → 5000
    assert tx["counterparty"]["name"] == "Usman"
    assert tx["flag"] == "none"
    assert "Usman" in tx["confirmation_ur"]
    # transcript keeps the code-switch verbatim
    assert "panch hazar" in tx["source"]["raw_output"]["transcript"]


# --- 5. garbage / empty audio ----------------------------------------------------


def test_garbage_audio(tmp_path):
    p = tmp_path / "garbage.ogg"
    p.write_bytes(b"\x00\x01\x02garbage-not-audio" * 10)
    tx = process_voice_note(p, occurred_at=WHEN, settings=_settings(),
                            mock_scenario="garbage_audio")
    _required_keys_present(tx)
    assert tx["flag"] == "low_confidence"
    assert tx["amount_pkd"] is None  # §6.9: null, never 0.0
    assert tx["status"] == "pending"
    assert tx["confirmation_ur"]  # a clarification question exists
    assert tx["source"]["confidence"] == 0.0
    assert tx["source"]["raw_output"]["mock"] is True  # F-2 applies to fallbacks too
    assert tx["source"]["raw_output"]["mock_scenario"] == "garbage_audio"


def test_empty_audio_file(tmp_path):
    p = tmp_path / "empty.ogg"
    p.write_bytes(b"")
    tx = process_voice_note(p, occurred_at=WHEN, settings=_settings(),
                            mock_scenario="garbage_audio")
    assert tx["flag"] == "low_confidence"


def test_unparsable_model_output_falls_back(tmp_path):
    """Simulate the real (non-mock) model returning junk → low-confidence fallback."""
    import voice_agent.pipeline as pl

    p = tmp_path / "n.ogg"
    p.write_bytes(b"RIFF....WAVEfmt " + b"\x00" * 128)  # wav-magic so decode passes
    original = pl.mock_response_text
    pl.mock_response_text = lambda s: "sorry I cannot answer that"  # junk model reply
    try:
        tx = process_voice_note(p, occurred_at=WHEN, settings=_settings())
    finally:
        pl.mock_response_text = original
    assert tx["flag"] == "low_confidence"
    assert tx["amount_pkd"] is None
    assert "sorry I cannot answer" in tx["source"]["raw_output"]["transcript"]


# --- environment behavior --------------------------------------------------------


def test_mock_mode_never_without_key_raises(tmp_path):
    from voice_agent.dashscope_client import DashScopeError

    p = tmp_path / "real.wav"
    p.write_bytes(b"RIFF\xf4\x00\x00\x00WAVEfmt " + b"\x00" * 240)  # wav-magic payload
    with pytest.raises(DashScopeError):
        process_voice_note(p, occurred_at=WHEN, settings=_settings(mock_mode="never"))


def test_auto_without_key_is_mock(tmp_path):
    p = tmp_path / "n.ogg"
    p.write_bytes(FAKE_AUDIO)
    tx = process_voice_note(p, occurred_at=WHEN, settings=_settings(mock_mode="auto"))
    assert tx["mock"] is True


def test_output_json_serializable_roundtrip(audio_file):
    tx = _run(audio_file, scenario="sale_with_items")
    roundtripped = json.loads(json.dumps(tx, ensure_ascii=False))
    assert roundtripped == tx


# --- §6.10 amount bounds (QA E-1) -------------------------------------------------


def _contract_tx(amount_pkd):
    from voice_agent.models import Counterparty, SourceBlock, Transaction

    return Transaction(
        kind="udhar_given",
        amount_pkd=amount_pkd,
        counterparty=Counterparty(name="احمد"),
        description="bound check",
        item_lines=[],
        occurred_at=WHEN,
        source=SourceBlock(confidence=0.9, raw_output={"transcript": "…"}),
    )


def test_amount_over_one_crore_rejected_by_contract():
    """§6.10 (E-1): 10_000_001 must fail validation — a hallucinated billion-rupee
    entry would poison udhar totals and the credit report."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _contract_tx(10_000_001)
    with pytest.raises(ValidationError):
        _contract_tx(1e9)


def test_amount_bounds_valid_edges():
    from pydantic import ValidationError

    assert _contract_tx(10_000_000).amount_pkd == 10_000_000  # 1 crore: valid
    assert _contract_tx(0.5).amount_pkd == 0.5
    assert _contract_tx(None).amount_pkd is None  # §6.2/§6.9: null = unknown, allowed
    for bad in (0, -500, -0.01):  # never zero/negative when present
        with pytest.raises(ValidationError):
            _contract_tx(bad)


def test_absurd_amount_routes_to_clarification_not_guess(audio_file):
    """Pipeline-level §6.10: a model reply claiming >1 crore fails contract
    validation → low-confidence clarification with amount null (never persisted)."""
    import copy

    import voice_agent.mock_data as md
    from voice_agent.mock_data import SCENARIOS

    scenario = copy.deepcopy(SCENARIOS["clean_udhar"])
    scenario["transaction"]["amount_pkd"] = 10_000_001
    md.SCENARIOS["temp_absurd"] = scenario
    try:
        tx = _run(audio_file, scenario="temp_absurd")
        assert tx["flag"] == "low_confidence"
        assert tx["amount_pkd"] is None  # not 10000001, not 0.0
        assert "کیا یہ درست ہے؟" not in tx["confirmation_ur"]
        assert "رقم" in tx["confirmation_ur"]  # asks for the amount again
        assert tx["source"]["raw_output"]["mock"] is True
        assert tx["source"]["raw_output"]["mock_scenario"] == "temp_absurd"
    finally:
        md.SCENARIOS.pop("temp_absurd", None)
