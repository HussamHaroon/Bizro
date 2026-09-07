"""Cancel-command detector tests — the server webhook contract (corrections.py).

Every phrase in the contract set must match; every ordinary transaction text
(including the word "cancel" alone) must NOT. All offline, pure functions.
"""

from __future__ import annotations

import pytest

from voice_agent.corrections import CANCEL_CONFIRMATION_REPLIES, is_cancel_command

# --- The exact contract phrases must match ---------------------------------

CONTRACT_PHRASES = [
    "cancel last",
    "cancel last entry",
    "undo last",
    "undo last entry",
    "delete last entry",
    "wo wapas karo",
    "pichla entry cancel",
    "pichli entry khatam karo",
    "pichla cancel karo",
    "پچھلی انٹری کینسل کرو",
    "آخری انٹری کینسل",
]


@pytest.mark.parametrize("phrase", CONTRACT_PHRASES)
def test_contract_phrases_match_exactly(phrase):
    assert is_cancel_command(phrase) is True


@pytest.mark.parametrize(
    "shouty",
    [
        "CANCEL LAST",
        "Cancel Last Entry",
        "UNDO LAST",
        "Wo Wapas Karo",
        "PICHLA CANCEL KARO",
        "  cancel last  ",
        "cancel last!",
        "wo wapas karo?",
        "pichli entry khatam karo.",
    ],
)
def test_case_whitespace_and_punctuation_tolerance(shouty):
    assert is_cancel_command(shouty) is True


@pytest.mark.parametrize(
    "padded",
    [
        # substring rule with ≤ +2 politeness words
        "please cancel last entry",
        "cancel last entry please",
        "wo wapas karo bhai",
        "undo last entry please",
        "pichli entry khatam karo please",
        "پچھلی انٹری کینسل کرو بھائی",
        "آخری انٹری کینسل کرو",
    ],
)
def test_short_politeness_padding_still_matches(padded):
    assert is_cancel_command(padded) is True


def test_arabic_yeh_variant_normalization():
    # "انٹری" spelled with Arabic yeh (ي) instead of Urdu yeh (ی) must still match.
    assert is_cancel_command("آخري انٹري کینسل") is True


# --- Must NOT match: transaction text, bare words, empty, None --------------


@pytest.mark.parametrize(
    "text",
    [
        None,
        "",
        "   ",
        "cancel",
        "Cancel",
        "cancel it",
        "cancel karo",  # bare "cancel karo" is not a contract phrase
        "Ahmad ko 5000 ka udhar diya",
        "Usman ne panch hazar ka saman liya",
        "usman ne kaha tha wo cancel karunga",  # mentions cancel, is a transaction
        "delete last entry and add a new one for Ahmad 5000",  # compound, too long
        "پچھلے مہینے کا حساب دکھاؤ",
        "ahmad ko panch hazar aur bilal ko do hazar ka udhar",
        "12345",
        "ok",
    ],
)
def test_non_cancel_text_rejected(text):
    assert is_cancel_command(text) is False


def test_ambiguous_long_sentence_not_matched():
    # 6 words with a 3-word phrase: slack is 2 → too far from the command form.
    assert is_cancel_command("آج کی آخری انٹری کینسل ہوئی تھی") is False


# --- Reply copy contract -----------------------------------------------------


def test_cancel_confirmation_replies_exact_copy():
    assert CANCEL_CONFIRMATION_REPLIES == {
        "en": "Done. Your last entry is cancelled.",
        "ur": "ہو گیا۔ آخری اندراج کینسل ہو گیا۔",
    }


def test_cancel_confirmation_replies_language_keys():
    assert set(CANCEL_CONFIRMATION_REPLIES) == {"en", "ur"}
    for text in CANCEL_CONFIRMATION_REPLIES.values():
        assert text.strip()


# --- Determinism / typing ----------------------------------------------------


def test_returns_real_bool_and_is_deterministic():
    for text in ["cancel last", "Ahmad ko 5000 ka udhar diya", None, ""]:
        out = is_cancel_command(text)
        assert isinstance(out, bool)
        assert out == is_cancel_command(text)
