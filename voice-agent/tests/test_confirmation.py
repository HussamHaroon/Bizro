"""Confirmation builder + Urdu numeral/word tests (no network, no browser)."""

from __future__ import annotations

import pytest

from voice_agent.confirmation import (
    amount_in_urdu_words,
    build_confirmation_ur,
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


# --- Urdu amount words --------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "expect_words"),
    [
        (0, "صفر"),
        (5, "پانچ"),
        (21, "اکیس"),
        (99, "ننانوے"),
        (100, "سو"),
        (105, "سو پانچ"),
        (350, "تین سو پچاس"),
        (1000, "ایک ہزار"),
        (1500, "پندرہ سو"),
        (3500, "پینتیس سو"),
        (5000, "پانچ ہزار"),
        (7000, "سات ہزار"),
        (7250, "سات ہزار دو سو پچاس"),
        (15000, "پندرہ ہزار"),
        (20000, "بیس ہزار"),
        (125000, "ایک لاکھ پچیس ہزار"),
        (75000, "پچہتر ہزار"),
        (1500000, "پندرہ لاکھ"),
        (30000000, "تین کروڑ"),
    ],
)
def test_amount_in_urdu_words(amount, expect_words):
    assert amount_in_urdu_words(amount) == expect_words


# --- confirmation sentences ---------------------------------------------------


def test_udhar_confirmation_has_digits_and_words_and_question():
    text = build_confirmation_ur(_tx(), "western")
    assert "5000" in text
    assert "پانچ ہزار روپے" in text  # word form echoed (design.md §4.7)
    assert "احمد" in text
    assert text.rstrip().endswith("کیا یہ درست ہے؟")


def test_confirmation_urdu_numerals_when_configured():
    text = build_confirmation_ur(_tx(), "urdu")
    assert "۵۰۰۰" in text and "5000" not in text


def test_each_kind_builds_sentence_with_amount():
    for kind in ("sale", "expense", "udhar_settlement"):
        tx = _tx(kind=kind)
        text = build_confirmation_ur(tx, "western")
        assert "5000" in text and "کیا یہ درست ہے؟" in text, kind


def test_expense_mentions_supplier():
    tx = _tx(kind="expense", counterparty=Counterparty(name="المدینہ ڈسٹریبیوٹرز"))
    text = build_confirmation_ur(tx, "western")
    assert "المدینہ" in text


def test_low_confidence_returns_question_not_statement():
    # §6.2/§6.9: unknown amount travels as None (0.0 no longer validates)
    tx = _tx(flag="low_confidence", amount_pkr=None)
    text = build_confirmation_ur(tx, "western")
    assert "کیا یہ درست ہے؟" not in text  # never a confirm statement
    assert "رقم" in text  # asks for the amount
    assert "?" in text or "؟" in text


def test_unclear_kind_asks_kind_question():
    tx = _tx(flag="low_confidence", amount_pkr=None, description="UNCLEAR_KIND — needs clarification")
    text = build_confirmation_ur(tx, "western")
    assert "سمجھ" in text  # "I did not understand" lead
    assert "ادھار" in text  # kind clarification ask
