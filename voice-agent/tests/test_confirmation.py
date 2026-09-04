"""Confirmation builder + numeral/word tests (no network, no browser).

Merchant-facing confirmations are SIMPLE ENGLISH now (owner ruling 2026-09-04);
the counterparty name stays whatever the voice note carried. The Urdu-numeral
style setting and the legacy Urdu words helper remain covered — names contract.
"""

from __future__ import annotations

import pytest

from voice_agent.confirmation import (
    amount_in_english_words,
    amount_in_urdu_words,
    build_confirmation,
    to_numeral_digits,
)
from voice_agent.models import Counterparty, SourceBlock, Transaction


def _tx(**over) -> Transaction:
    base = dict(
        kind="udhar_given",
        amount_pkr=5000,
        counterparty=Counterparty(name="احمد"),
        description="Udhar given to Ahmad",
        item_lines=[],
        occurred_at="2026-08-21T19:03:00+05:00",
        source=SourceBlock(confidence=0.93, raw_output={"transcript": "…"}),
        flag="none",
        status="pending",
    )
    base.update(over)
    return Transaction(**base)


# --- numerals ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "style", "expect"),
    [
        (5000, "western", "5000"),
        (5000, "urdu", "۵۰۰۰"),
        (1500, "urdu", "۱۵۰۰"),
        (350.5, "western", "350.5"),
    ],
)
def test_numeral_styles(value, style, expect):
    assert to_numeral_digits(value, style) == expect


# --- English amount words (invoice words-form) ---------------------------------


@pytest.mark.parametrize(
    ("amount", "expect_words"),
    [
        (0, "zero"),
        (5, "five"),
        (21, "twenty-one"),
        (99, "ninety-nine"),
        (100, "one hundred"),
        (105, "one hundred five"),
        (350, "three hundred fifty"),
        (1000, "one thousand"),
        (1500, "one thousand five hundred"),
        (5000, "five thousand"),
        (7250, "seven thousand two hundred fifty"),
        (15000, "fifteen thousand"),
        (20000, "twenty thousand"),
        (125000, "one lakh twenty-five thousand"),
        (75000, "seventy-five thousand"),
        (1500000, "fifteen lakh"),
        (30000000, "three crore"),
    ],
)
def test_amount_in_english_words(amount, expect_words):
    assert amount_in_english_words(amount) == expect_words


# --- legacy Urdu amount words (kept for the package export contract) ------------


@pytest.mark.parametrize(
    ("amount", "expect_words"),
    [
        (0, "صفر"),
        (5, "پانچ"),
        (5000, "پانچ ہزار"),
        (1500, "پندرہ سو"),
        (125000, "ایک لاکھ پچیس ہزار"),
    ],
)
def test_amount_in_urdu_words_legacy(amount, expect_words):
    assert amount_in_urdu_words(amount) == expect_words


# --- confirmation sentences (simple English) -----------------------------------


def test_udhar_confirmation_matches_owner_example_format():
    text = build_confirmation(_tx(), "western")
    assert text == "Got it. 5000 rupees credit to احمد. Is this correct?"


def test_confirmation_has_digits_and_question():
    text = build_confirmation(_tx(), "western")
    assert "5000" in text
    assert "احمد" in text
    assert text.rstrip().endswith("Is this correct?")


def test_confirmation_urdu_numerals_when_configured():
    text = build_confirmation(_tx(), "urdu")
    assert "۵۰۰۰" in text and "5000" not in text


def test_each_kind_builds_sentence_with_amount():
    for kind in ("sale", "expense", "udhar_settlement"):
        tx = _tx(kind=kind)
        text = build_confirmation(tx, "western")
        assert "5000" in text and "Is this correct?" in text, kind


def test_expense_mentions_supplier():
    tx = _tx(kind="expense", counterparty=Counterparty(name="المدینہ ڈسٹریبیوٹرز"))
    text = build_confirmation(tx, "western")
    assert "You spent" in text
    assert "المدینہ" in text


def test_low_confidence_returns_question_not_statement():
    # §6.2/§6.9: unknown amount travels as None (0.0 no longer validates)
    tx = _tx(flag="low_confidence", amount_pkr=None)
    text = build_confirmation(tx, "western")
    assert "Is this correct?" not in text  # never a confirm statement
    assert "How much" in text  # asks for the amount
    assert "?" in text


def test_unclear_kind_asks_kind_question():
    tx = _tx(flag="low_confidence", amount_pkr=None, description="UNCLEAR_KIND — needs clarification")
    text = build_confirmation(tx, "western")
    assert "did not understand" in text  # simple "I didn't understand" lead
    assert "credit" in text  # kind clarification ask


def test_legacy_alias_build_confirmation_ur_still_importable():
    """voice_agent/__init__.py exports build_confirmation_ur — the alias must
    keep working (name contract), building the same English text."""
    from voice_agent.confirmation import build_confirmation_ur

    assert build_confirmation_ur(_tx(), "western") == build_confirmation(_tx(), "western")
