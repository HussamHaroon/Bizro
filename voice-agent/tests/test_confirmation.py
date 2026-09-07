"""Confirmation builder + numeral/word tests (no network, no browser).

Merchant-facing confirmations are SIMPLE ENGLISH now (owner ruling 2026-09-04);
the counterparty name stays whatever the voice note carried. The Urdu-numeral
style setting and the legacy Urdu words helper remain covered — names contract.

Item-line read-back (2026-10-02): entries that carry item_lines echo up to three
of them in an Items: sentence before the question; item kinds parsed without
line detail get an explicit dropped-detail notice instead.
"""

from __future__ import annotations

import pytest

from voice_agent.confirmation import (
    amount_in_english_words,
    amount_in_urdu_words,
    build_confirmation,
    to_numeral_digits,
)
from voice_agent.models import Counterparty, ItemLine, SourceBlock, Transaction


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


def _line(item: str, qty: float, unit_price: float) -> ItemLine:
    return ItemLine(item=item, qty=qty, unit_price=unit_price, line_total=qty * unit_price)


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
    # udhar_given with no item_lines → dropped-detail notice sits before the ask
    text = build_confirmation(_tx(), "western")
    assert text == (
        "Got it. 5000 rupees credit to احمد. "
        "Only the total is recorded — no item detail. Is this correct?"
    )


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


# --- item-line read-back (2026-10-02) --------------------------------------------


def test_items_sentence_en_lists_lines_before_question():
    tx = _tx(kind="sale", item_lines=[_line("ghee", 2, 650), _line("cheeni", 3, 200)])
    text = build_confirmation(tx, "western")
    assert "Items:" in text
    assert "ghee" in text and "cheeni" in text  # item names verbatim
    assert "Items: 2 ghee" in text and "3 cheeni" in text  # qty per numeral style
    assert text.index("Items:") < text.index("Is this correct?")  # before the ask
    assert "Only the total" not in text  # items present → no dropped-notice


def test_items_sentence_ur_lists_lines_before_question():
    tx = _tx(kind="sale", item_lines=[_line("گھی", 2, 650), _line("چینی", 3, 200)])
    text = build_confirmation(tx, "urdu", lang="ur")
    assert "آئٹمز:" in text
    assert "گھی" in text and "چینی" in text
    assert "۲" in text and "۳" in text  # qty digits honor NUMERAL_STYLE
    assert text.index("آئٹمز:") < text.index("کیا یہ درست ہے؟")
    assert "صرف کل رقم" not in text


def test_no_item_lines_sale_gets_dropped_notice_en():
    text = build_confirmation(_tx(kind="sale", item_lines=[]), "western")
    assert "Only the total is recorded — no item detail." in text
    assert "Is this correct?" in text


def test_no_item_lines_gets_dropped_notice_ur():
    text = build_confirmation(_tx(kind="expense", item_lines=[]), "western", lang="ur")
    assert "صرف کل رقم درج ہوئی — آئٹم کی تفصیل شامل نہیں۔" in text
    assert "کیا یہ درست ہے؟" in text


def test_udhar_settlement_without_items_has_no_extra_line():
    # settlement is not an item kind: no items → output identical to today
    text = build_confirmation(_tx(kind="udhar_settlement", item_lines=[]), "western")
    assert text == "Got it. احمد paid back 5000 rupees. Is this correct?"
    assert "Only the total" not in text
    assert "Items:" not in text


def test_items_sentence_caps_at_three_lines_then_more():
    lines = [_line(f"item{i}", 1, 100) for i in range(1, 6)]
    text = build_confirmation(_tx(kind="sale", item_lines=lines), "western")
    assert "+2 more" in text
    assert all(f"item{i}" in text for i in (1, 2, 3))  # first three shown
    assert "item4" not in text and "item5" not in text


def test_question_stays_last_with_items_and_notice():
    with_items = build_confirmation(_tx(kind="sale", item_lines=[_line("ghee", 2, 650)]), "western")
    with_notice = build_confirmation(_tx(kind="udhar_given", item_lines=[]), "western")
    ur_items = build_confirmation(
        _tx(kind="sale", item_lines=[_line("گھی", 2, 650)]), "western", lang="ur"
    )
    for text, question in (
        (with_items, "Is this correct?"),
        (with_notice, "Is this correct?"),
        (ur_items, "کیا یہ درست ہے؟"),
    ):
        assert text.rstrip().endswith(question)  # last line, byte-identical
        assert text.count(question) == 1
