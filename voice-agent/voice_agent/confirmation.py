"""confirmation_ur builder — SIMPLE ENGLISH confirmation text for WhatsApp.

Owner ruling (2026-09-04): ALL merchant-facing output is simple English — short
sentences, everyday words ("We got it. 5000 rupees credit to Ahmad. Is this
correct?"). Only the CONTENT changed: the field name `confirmation_ur`, the DB
column, and the API keys keep their historical names (contracts unchanged).

INBOUND voice notes are still Urdu — Whisper still transcribes Urdu and the
parse prompt still understands Urdu transcripts. Only this OUTPUT text is
English. Numbers stay in digits (NUMERAL_STYLE still honored: western|urdu).
"""

from __future__ import annotations

from voice_agent.models import Transaction

# ---------------------------------------------------------------------------
# Numerals
# ---------------------------------------------------------------------------

_URDU_DIGITS = "۰۱۲۳۴۵۶۷۸۹"  # U+06F0..U+06F9 extended Arabic-Indic (Urdu/Persian forms)


def to_numeral_digits(value: float, numeral_style: str = "western") -> str:
    """Render a number's digits per NUMERAL_STYLE. Truncates paisa noise (.0)."""
    if float(value).is_integer():
        text = str(int(value))
    else:
        text = f"{value:.2f}".rstrip("0").rstrip(".")
    if numeral_style == "urdu":
        return "".join(_URDU_DIGITS[int(ch)] if ch.isdigit() else ch for ch in text)
    return text


# ---------------------------------------------------------------------------
# Amount in simple English words (South-Asian scale: thousand / lakh / crore)
# ---------------------------------------------------------------------------

_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS_EN = {
    2: "twenty", 3: "thirty", 4: "forty", 5: "fifty",
    6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety",
}


def _words_under_100_en(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, unit = divmod(n, 10)
    return _TENS_EN[tens] if unit == 0 else f"{_TENS_EN[tens]}-{_ONES[unit]}"


def _words_under_1000_en(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} hundred")
    if rest:
        parts.append(_words_under_100_en(rest))
    return " ".join(parts)


def amount_in_english_words(amount: float) -> str:
    """Amount → simple English words WITHOUT the trailing 'rupees' (caller adds it).
    South-Asian scale, the way Pakistani merchants say numbers: 125000 →
    "one lakh twenty-five thousand"."""
    rupees = int(amount)
    paisa = round((float(amount) - rupees) * 100)

    if rupees == 0:
        words = "zero"
    else:
        parts: list[str] = []
        crore, rest = divmod(rupees, 10_000_000)
        lakh, rest = divmod(rest, 100_000)
        thousand, rest = divmod(rest, 1000)
        if crore:
            parts.append(f"{_words_under_100_en(crore)} crore")
        if lakh:
            parts.append(f"{_words_under_100_en(lakh)} lakh")
        if thousand:
            parts.append(f"{_words_under_100_en(thousand)} thousand")
        if rest:
            parts.append(_words_under_1000_en(rest))
        words = " ".join(parts)

    if paisa:
        return f"{words} point {_words_under_100_en(paisa)}"
    return words


# ---------------------------------------------------------------------------
# Legacy Urdu number words — KEPT ONLY because voice_agent/__init__.py exports
# `amount_in_urdu_words` (name contract; no longer used by any output text).
# ---------------------------------------------------------------------------

_UNITS = [
    "صفر", "ایک", "دو", "تین", "چار", "پانچ", "چھ", "سات", "آٹھ", "نو",
    "دس", "گیارہ", "بارہ", "تیرہ", "چودہ", "پندرہ", "سولہ", "سترہ", "اٹھارہ", "انیس",
]
_TENS = {
    20: "بیس", 30: "تیس", 40: "چالیس", 50: "پچاس", 60: "ساٹھ", 70: "ستر", 80: "اسی", 90: "نوے",
}
_IRREGULAR_21_99 = {
    21: "اکیس", 22: "بائیس", 23: "تئیس", 24: "چوبیس", 25: "پچیس", 26: "چھببیس",
    27: "ستائیس", 28: "اٹھائیس", 29: "انتیس",
    31: "اکتیس", 32: "بتیس", 33: "تینتیس", 34: "چونتیس", 35: "پینتیس", 36: "چھتیس",
    37: "انتالیس", 38: "اڑتیس", 39: "انتالیس",
    41: "اکتالیس", 42: "بیالیس", 43: "تینتالیس", 44: "چوالیس", 45: "پینتالیس",
    46: "چھیالیس", 47: "سینتالیس", 48: "اڑتالیس", 49: "انچاس",
    51: "اکاون", 52: "باوان", 53: "ترپن", 54: "چون", 55: "پچپن", 56: "چھپن",
    57: "ستاون", 58: "اٹھاون", 59: "انسٹھ",
    61: "اکسٹھ", 62: "باسٹھ", 63: "ترسٹھ", 64: "چونسٹھ", 65: "پینسٹھ", 66: "چھیاسٹھ",
    67: "سڑسٹھ", 68: "اڑسٹھ", 69: "انہتر",
    71: "اکہتر", 72: "بہتر", 73: "تہتر", 74: "چوہتر", 75: "پچہتر", 76: "چھہتر",
    77: "ستتر", 78: "اٹھہتر", 79: "اناسی",
    81: "اکیاسی", 82: "بیاسی", 83: "تراسی", 84: "چوراسی", 85: "پچاسی",
    86: "چھیاسی", 87: "ستاسی", 88: "اٹھاسی", 89: "نواسی",
    91: "اکانوے", 92: "بانوے", 93: "ترانوے", 94: "چورانوے", 95: "پچانوے",
    96: "چھیانوے", 97: "ستانوے", 98: "اٹھانوے", 99: "ننانوے",
}


def _words_under_100(n: int) -> str:
    if n < 20:
        return _UNITS[n]
    if n in _IRREGULAR_21_99:
        return _IRREGULAR_21_99[n]
    tens, unit = (n // 10) * 10, n % 10
    if unit == 0:
        return _TENS[tens]
    return f"{_UNITS[unit]} {_TENS[tens]}"


def _words_under_1000(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_UNITS[hundreds]} سو" if hundreds > 1 else "سو")
    if rest:
        parts.append(_words_under_100(rest))
    return " ".join(parts)


def amount_in_urdu_words(amount: float) -> str:
    """LEGACY (unused by output text): Amount → Urdu words WITHOUT the trailing
    'روپے'. Kept for the voice_agent package export contract only."""
    rupees = int(amount)
    paisa = round((float(amount) - rupees) * 100)

    if rupees == 0:
        words = "صفر"
    elif 1100 <= rupees <= 9900 and rupees % 100 == 0 and rupees % 1000 != 0:
        # Spoken-natural short form for non-thousand round hundreds:
        # 1500 → پندرہ سو ، 3500 → پینتیس سو — but 5000 stays پانچ ہزار (never "پچاس سو")
        words = f"{_words_under_100(rupees // 100)} سو"
    else:
        # Formal South-Asian decomposition: کروڑ / لاکھ / ہزار / remainder
        parts: list[str] = []
        crore, rest = divmod(rupees, 10_000_000)
        lakh, rest = divmod(rest, 100_000)
        thousand, rest = divmod(rest, 1000)
        if crore:
            parts.append(f"{_words_under_100(crore)} کروڑ")
        if lakh:
            parts.append(f"{_words_under_100(lakh)} لاکھ")
        if thousand:
            parts.append(f"{_words_under_100(thousand)} ہزار")
        if rest:
            parts.append(_words_under_1000(rest))
        words = " ".join(parts)

    if paisa:
        return f"{words} روپے {_words_under_100(paisa)} پیسے".strip()
    return words


# ---------------------------------------------------------------------------
# Confirmation sentences (simple English)
# ---------------------------------------------------------------------------

QUESTION = "Is this correct?"  # one-tap / 1-or-0 reply yes/no

# Transaction descriptions starting with this marker mean "kind itself was unclear"
# (pipeline sets it when the model could not tell what kind of entry this was).
UNCLEAR_KIND_MARKER = "UNCLEAR_KIND"


def _amount_phrase(amount: float, numeral_style: str) -> str:
    """'5000 rupees' — digits per NUMERAL_STYLE, everyday wording."""
    return f"{to_numeral_digits(amount, numeral_style)} rupees"


_KIND_TEMPLATES = {
    # {amount}: minimal, simple English. direction per schema.md §1.
    "sale": "{amount} cash sale to {name}.",
    "expense": "You spent {amount}.{supplier}",
    "udhar_given": "{amount} credit to {name}.",
    "udhar_settlement": "{name} paid back {amount}.",
}


def _name_or_fallback(counterparty) -> str:
    name = (getattr(counterparty, "name", None) or "").strip()
    return name if name else "a customer"  # only when the model found no name


def build_confirmation(tx: Transaction, numeral_style: str = "western") -> str:
    """Build the WhatsApp text confirmation in SIMPLE ENGLISH. For flag=low_confidence
    this returns a CLARIFICATION QUESTION, never a statement (schema.md §1: never
    guess). NOTE: callers store it in the `confirmation_ur` field/DB column — the
    name is historical, the content is English (owner ruling, 2026-09-04)."""
    if tx.flag == "low_confidence":
        return _build_clarification(tx, numeral_style)

    amount = _amount_phrase(tx.amount_pkr, numeral_style)
    tpl = _KIND_TEMPLATES[tx.kind]
    if tx.kind == "expense":
        supplier = (tx.counterparty.name or "").strip() if tx.counterparty else ""
        suffix = f" Bought from {supplier}." if supplier else ""
        sentence = tpl.format(amount=amount, supplier=suffix)
    else:
        sentence = tpl.format(name=_name_or_fallback(tx.counterparty), amount=amount)
    return f"Got it. {sentence} {QUESTION}"


# Historical name kept: voice_agent/__init__.py (and older callers) import
# `build_confirmation_ur`. The content it builds is simple English now.
build_confirmation_ur = build_confirmation


# Per-field clarification questions for ambiguous parses.
_CLARIFY_AMOUNT = "How much was it? Please type the amount or say it again."
_CLARIFY_KIND = "Was this credit, a cash sale, or an expense?"
_CLARIFY_NAME = "What is the customer's name?"


def _build_clarification(tx: Transaction, numeral_style: str) -> str:
    # §6.2/§6.9: unknown amount travels as None (never 0.0); <= 0 kept as a
    # defensive legacy guard.
    unknown_amount = tx.amount_pkr is None or tx.amount_pkr <= 0
    unknown_kind = tx.description.startswith(UNCLEAR_KIND_MARKER)
    known_name = (tx.counterparty.name or "").strip() if tx.counterparty else ""

    lead = "Sorry, we could not confirm this entry."
    if known_name and not unknown_kind:
        lead = f"Sorry, we could not confirm {known_name}'s entry."
    if unknown_kind:
        lead = "Sorry, we did not understand your note."  # "I could not understand."

    asks: list[str] = []
    if unknown_amount:
        asks.append(_CLARIFY_AMOUNT)
    if unknown_kind:
        asks.append(_CLARIFY_KIND)
    elif not known_name and tx.kind in ("sale", "udhar_given", "udhar_settlement"):
        asks.append(_CLARIFY_NAME)
    if not asks:
        asks.append("Please say it again.")

    return f"{lead} {' '.join(asks)}"
