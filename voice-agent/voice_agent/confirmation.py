"""confirmation_ur builder — clean Urdu text for WhatsApp (design.md §4.7: numbers in
digits AND word form; schema.md §1: Western digits by default, NUMERAL_STYLE env).

Urdu conventions used:
- South-Asian scale words: سو (100), ہزار (10^3), لاکھ (10^5), کروڑ (10^7).
- 1100..99000 round hundreds spoken the natural way where possible: 1500 → پندرہ سو.
- 0–99 have irregular single words (اکیس، بائیس، …) — full table encoded below.
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
# Urdu number words (0 .. 99,99,99,999)
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
    return f"{_UNITS[unit]} {_TENS[tens]}"  # e.g. 34 → چونتیس irregular; 105 → پانچ سو


def _words_under_1000(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_UNITS[hundreds]} سو" if hundreds > 1 else "سو")
    if rest:
        parts.append(_words_under_100(rest))
    return " ".join(parts)


def amount_in_urdu_words(amount: float) -> str:
    """Amount → Urdu words WITHOUT the trailing 'روپے' (caller appends currency).
    Handles paisa as 'X روپے Y پیسے' fragments via the caller if fractional.
    """
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
# Confirmation sentences
# ---------------------------------------------------------------------------

QUESTION = "کیا یہ درست ہے؟"  # "Is this correct?" — one-tap reply yes/no

# Transaction descriptions starting with this marker mean "kind itself was unclear"
# (pipeline sets it when the model could not tell what kind of entry this was).
UNCLEAR_KIND_MARKER = "UNCLEAR_KIND"


def _amount_phrase(amount: float, numeral_style: str) -> str:
    """'5000 روپے (پانچ ہزار روپے)' — digits AND words (design.md §4.7)."""
    digits = to_numeral_digits(amount, numeral_style)
    words = amount_in_urdu_words(amount)
    if float(amount).is_integer():
        return f"{digits} روپے ({words} روپے)"
    return f"{digits} روپے ({words})"  # words already carry the paisa fragment


_KIND_TEMPLATES = {
    # {name} {amount}: minimal-word, register-safe Urdu. direction per schema.md §1.
    "sale": "{name} نے {amount} کا سودا لیا، ادائیگی نقد کی۔",
    "expense": "آپ نے {amount} کا خرچ کیا۔{supplier}",
    "udhar_given": "{name} کو {amount} ادھار دیے۔",
    "udhar_settlement": "{name} نے {amount} ادھار لوٹائے۔",
}

_KIND_LABEL_UR = {
    "sale": "فروخت",
    "expense": "خرچ",
    "udhar_given": "ادھار دیا",
    "udhar_settlement": "ادھار وصول",
}


def _name_or_fallback(counterparty) -> str:
    name = (getattr(counterparty, "name", None) or "").strip()
    return name if name else "کسی گاہک"  # "a customer" — only when model found no name


def build_confirmation_ur(tx: Transaction, numeral_style: str = "western") -> str:
    """Build the WhatsApp text confirmation. For flag=low_confidence this returns a
    CLARIFICATION QUESTION, never a statement (schema.md §1: never guess)."""
    if tx.flag == "low_confidence":
        return _build_clarification_ur(tx, numeral_style)

    amount = _amount_phrase(tx.amount_pkd, numeral_style)
    tpl = _KIND_TEMPLATES[tx.kind]
    if tx.kind == "expense":
        supplier = (tx.counterparty.name or "").strip() if tx.counterparty else ""
        suffix = f" {supplier} سے۔" if supplier else ""
        sentence = tpl.format(amount=amount, supplier=suffix)
    else:
        sentence = tpl.format(name=_name_or_fallback(tx.counterparty), amount=amount)
    return f"{sentence} {QUESTION}"


# Per-field clarification questions for ambiguous parses.
_CLARIFY_AMOUNT = "رقم کتنی تھی؟ نمبر میں لکھ کر بھیجیں یا دوبارہ بولیں۔"
_CLARIFY_KIND = "کیا یہ ادھار تھا، نقد فروخت، یا خرچ؟"
_CLARIFY_NAME = "گاہک کا نام کیا ہے؟"


def _build_clarification_ur(tx: Transaction, numeral_style: str) -> str:
    unknown_amount = tx.amount_pkd <= 0
    unknown_kind = tx.description.startswith(UNCLEAR_KIND_MARKER)
    known_name = (tx.counterparty.name or "").strip() if tx.counterparty else ""

    lead = "یہ اندراج پکا نہیں ہو سکا۔"  # "This entry could not be confirmed."
    if known_name and not unknown_kind:
        lead = f"{known_name} کا اندراج پکا نہیں ہو سکا۔"
    if unknown_kind:
        lead = "آپ کی بات سمجھ نہیں آئی۔"  # "I could not understand."

    asks: list[str] = []
    if unknown_amount:
        asks.append(_CLARIFY_AMOUNT)
    if unknown_kind:
        asks.append(_CLARIFY_KIND)
    elif not known_name and tx.kind in ("sale", "udhar_given", "udhar_settlement"):
        asks.append(_CLARIFY_NAME)
    if not asks:
        asks.append("براہ کرم دوبارہ بولیں۔")

    return f"{lead} {' '.join(asks)}"
