"""Multi-entry voice pipeline tests — the anti-collapse contract.

The bug being locked down: one voice note naming SEVERAL people with SEPARATE
amounts used to collapse into ONE summed total. Every test here exists to make
a specific part of that bug impossible to reintroduce.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice_agent.confirmation import QUESTION, QUESTION_UR, build_combined_confirmation
from voice_agent.numbers import (
    collapse_suspected,
    count_amount_signals,
    count_person_joins,
    normalize_spoken_numbers,
)
from voice_agent.pipeline import (
    _assemble_all,
    process_transcript,
    process_transcript_multi,
)
from voice_agent.config import load_settings


@pytest.fixture()
def mock_settings(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "always")
    return load_settings()


# ---------------------------------------------------------------------------
# The core fix: person→amount association survives one multi-person note
# ---------------------------------------------------------------------------

def test_two_people_two_amounts_two_entries(mock_settings):
    env = process_transcript_multi(
        "ignored in mock", settings=mock_settings, mock_scenario="multi_udhar_two"
    )
    txs = env["transactions"]
    assert len(txs) == 2, "two people in one note must yield two entries"
    by_amount = {t["amount_pkr"]: t for t in txs}
    assert set(by_amount) == {5000.0, 2000.0}, "amounts must stay separate — never summed"
    assert by_amount[5000.0]["counterparty"]["name"] == "احمد"
    assert by_amount[2000.0]["counterparty"]["name"] == "بلال"
    assert all(t["flag"] == "none" for t in txs)
    # each entry linked to the same shared audit transcript
    for t in txs:
        assert "احمد" in t["source"]["raw_output"]["transcript"]


def test_combined_reply_enumerates_both_and_asks_once(mock_settings):
    env = process_transcript_multi(
        "ignored in mock", settings=mock_settings, mock_scenario="multi_udhar_two"
    )
    reply = env["reply_text"]
    assert "5000" in reply and "2000" in reply
    assert "احمد" in reply and "بلال" in reply
    assert reply.count(QUESTION_UR) == 1, "exactly ONE trailing question"


def test_mixed_clarity_clean_entry_stays_clean(mock_settings):
    env = process_transcript_multi(
        "ignored in mock",
        settings=mock_settings,
        mock_scenario="multi_mixed_one_unclear",
    )
    txs = env["transactions"]
    assert len(txs) == 2
    usman = next(t for t in txs if t["amount_pkr"] == 800.0)
    nasir = next(t for t in txs if t["amount_pkr"] is None)
    assert usman["flag"] == "none", "certain entry must not be poisoned by the unclear one"
    assert nasir["flag"] == "low_confidence"
    assert "ناصر" in env["reply_text"], "clarification must name the unclear person"


# ---------------------------------------------------------------------------
# The collapse guard: model MERGED people → never silently persisted
# ---------------------------------------------------------------------------

def test_collapse_guard_catches_merged_total():
    """Model returned ONE 7000-rupee entry for a transcript naming TWO people
    with separate amounts — the guard must append a clarification entry."""
    model_text = (
        '{"transcript": "احمد کو پانچ ہزار اور بلال کو دو ہزار کا ادھار دیا",'
        ' "confidence": 0.9,'
        ' "transaction": {"kind": "udhar_given", "amount_pkr": 7000,'
        ' "counterparty": {"name": "احمد و بلال"}, "description": "udhar",'
        ' "item_lines": [], "unclear": []}}'
    )
    import datetime as dt

    when = dt.datetime.now(dt.timezone.utc)
    from voice_agent.config import load_settings

    txs, reply, errors = _assemble_all(
        model_text, when, None, load_settings(), mock=True
    )
    assert len(txs) == 2, "merged entry + guard clarification"
    assert txs[0]["amount_pkr"] == 7000.0  # model's (wrong) merge, kept for audit
    guard = txs[1]
    assert guard["flag"] == "low_confidence"
    assert "collapse guard" in guard["description"]
    assert "7000" not in reply or guard["confirmation_ur"] in reply


# ---------------------------------------------------------------------------
# Numbers layer (the deterministic accuracy helpers)
# ---------------------------------------------------------------------------

def test_normalize_spoken_numbers_inserts_digit_hints():
    out = normalize_spoken_numbers("Ahmad ko panch hazar aur Bilal ko do hazar")
    assert "[5000]" in out and "[2000]" in out
    # verbatim words still present (audit never replaced)
    assert "panch hazar" in out and "do hazar" in out


def test_normalize_urdu_script_numbers():
    out = normalize_spoken_numbers("احمد کو پانچ ہزار روپے دیے")
    assert "[5000]" in out


def test_amount_signals_ignore_item_quantities():
    # ordinary single sale with items: quantities must NOT look like udhar amounts
    text = "do packet chai patti, ek dabba ghee, kul pandrah sau"
    assert count_amount_signals(text) == 0
    assert collapse_suspected(text, entry_count=1) is False


def test_amount_signals_detect_scale_amounts():
    text = "احمد کو پانچ ہزار اور بلال کو دو ہزار"
    assert count_amount_signals(text) == 2
    assert count_person_joins(text) >= 1
    assert collapse_suspected(text, entry_count=1) is True
    assert collapse_suspected(text, entry_count=2) is False


def test_normalize_composes_hundred_scale():
    # the module docstring documents this: "پندرہ سو" → [1500]. Hundreds compose
    # in the HINT layer but stay OUT of the amount signals (quantities).
    assert "[1500]" in normalize_spoken_numbers("Usman ne pandrah sau ka saman liya")
    assert "[800]" in normalize_spoken_numbers("Usman ne aath sau diye")
    assert "[200000]" in normalize_spoken_numbers("do lakh ka udhar")
    # ...and still no signal → single-entry sales with item totals don't trip the guard
    text = "do packet chai patti, ek dabba ghee, kul pandrah sau"
    assert count_amount_signals(text) == 0


def test_urdu_comma_does_not_glue_onto_words():
    # ، (U+060C) sits inside the Arabic range — it must not fuse with "ہزار"
    # or the number/scale tables stop matching exactly where Urdu uses commas.
    text = "عثمان کو دو ہزار، ناصر کو تین ہزار اور شاہد کو چار ہزار کا ادھار"
    out = normalize_spoken_numbers(text)
    assert "[2000]" in out and "[3000]" in out and "[4000]" in out
    # the Urdu comma itself survives verbatim (normalization only inserts)
    assert "ہزار [2000]،" in out
    assert count_amount_signals(text) == 3
    assert count_person_joins(text) == 2
    assert collapse_suspected(text, entry_count=2) is True
    assert collapse_suspected(text, entry_count=3) is False


# ---------------------------------------------------------------------------
# Backward compatibility: single-entry behavior byte-identical
# ---------------------------------------------------------------------------

def test_legacy_singular_shape_still_parses(mock_settings):
    env = process_transcript_multi(
        "ignored", settings=mock_settings, mock_scenario="clean_udhar"
    )
    assert len(env["transactions"]) == 1
    assert env["transactions"][0]["amount_pkr"] == 5000.0
    # single clean entry short-circuits to the EXACT single confirmation
    assert env["reply_text"].endswith(QUESTION_UR)
    assert env["reply_text"].startswith("سمجھ گیا۔")


def test_compat_wrapper_single_entry_unchanged(mock_settings):
    tx = process_transcript("ignored", settings=mock_settings,
                            mock_scenario="clean_udhar")
    assert tx["amount_pkr"] == 5000.0
    assert tx["counterparty"]["name"] == "احمد"


def test_compat_wrapper_multi_never_returns_summed_total(mock_settings):
    tx = process_transcript("ignored", settings=mock_settings,
                            mock_scenario="multi_udhar_two")
    assert tx["amount_pkr"] is None, "legacy caller must get clarification, not 7000"
    assert tx["flag"] == "low_confidence"


def test_combined_builder_handles_all_flagged(mock_settings):
    env = process_transcript_multi(
        "ignored", settings=mock_settings, mock_scenario="multi_mixed_one_unclear"
    )
    # builder directly: all-flagged input returns clarification text, no header
    flagged = [dict(t) for t in env["transactions"] if t["flag"] == "low_confidence"]
    out = build_combined_confirmation(flagged)
    assert "اندراجات" not in out
