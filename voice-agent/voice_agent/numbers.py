"""Deterministic spoken-number utilities for the voice pipeline.

Three jobs, all pure functions (no model involved — testable by construction):

1. ``normalize_spoken_numbers`` — rewrite Roman-Urdu / Urdu-script /
   phonetic-English number words into digits as an AID transcript for the
   structuring model ("Ahmad ko panch hazar" → "Ahmad ko panch hazar [5000]").
   The verbatim transcript is never replaced — audit keeps the original; the
   normalized form only travels alongside it in the structuring prompt.
2. ``count_amount_signals`` — count amount-like tokens in a transcript.
3. ``count_person_joins`` — count connectors that join multiple person-amount
   clauses (",", "aur", "اور", "and", "or", "یا").

2 + 3 power the pipeline's COLLAPSE GUARD: if a transcript signals more
person-amount clauses than the model returned entries, entries were merged —
the guard refuses to persist a silently-summed total.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Number-word tables: Roman Urdu + Urdu script + phonetic English
# ---------------------------------------------------------------------------

_NUM_WORDS: dict[str, int] = {
    # Roman Urdu / English 0..20
    "zero": 0, "sifar": 0,
    "one": 1, "ek": 1, "aik": 1, "ایک": 1,
    "two": 2, "do": 2, "دو": 2,
    "three": 3, "teen": 3, "تین": 3,
    "four": 4, "char": 4, "chaar": 4, "چار": 4,
    "five": 5, "panch": 5, "paanch": 5, "پانچ": 5,
    "six": 6, "chhay": 6, "cheh": 6, "چھ": 6,
    "seven": 7, "sat": 7, "saat": 7, "سات": 7,
    "eight": 8, "aath": 8, "آٹھ": 8,
    "nine": 9, "nau": 9, "نو": 9,
    "ten": 10, "das": 10, "دس": 10,
    "eleven": 11, "giyarah": 11, "گیارہ": 11,
    "twelve": 12, "barah": 12, "بارہ": 12,
    "thirteen": 13, "terah": 13, "تیرہ": 13,
    "fourteen": 14, "chaudah": 14, "چودہ": 14,
    "fifteen": 15, "pandrah": 15, "پندرہ": 15,
    "sixteen": 16, "solah": 16, "سولہ": 16,
    "seventeen": 17, "satrah": 17, "سترہ": 17,
    "eighteen": 18, "atharah": 18, "اٹھارہ": 18,
    "nineteen": 19, "unnees": 19, "انیس": 19,
    "twenty": 20, "bees": 20, "بیس": 20,
    # tens
    "tis": 30, "تیس": 30, "chalees": 40, "chalis": 40, "چالیس": 40,
    "pachaas": 50, "pacas": 50, "پچاس": 50,
    "saathh": 60, "saat10": 60, "saath60": 60, "ساٹھ": 60,
    "sattar": 70, "ستر": 70, "assi": 80, "اسی": 80,
    "naway": 90, "navay": 90, "نوے": 90,
    # scales
    "sau": 100, "so": 100, "hundred": 100, "سو": 100,
}

_TENS_COMPOUNDS: dict[str, int] = {
    "tees": 30, "تیس": 30, "untalees": 39, "انتالیس": 39,
    "chalees": 40, "پنتالیس": 45, "pentalis": 45, "paintalis": 45,
    "chappan": 56, "چھپن": 56, "sath": 60, "سرسٹھ": 69,
    "unhattar": 69, "انہتر": 69, "inhattar": 69,
    "shiyaasi": 86, "چھیاسی": 86, "nabbe": 90, "ننانوے": 99,
}

_SCALE_WORDS: dict[str, int] = {
    "hazar": 1_000, "hazaar": 1_000, "hazaram": 1_000, "thousand": 1_000,
    "ہزار": 1_000, "ہزاروں": 1_000,
    "lakh": 100_000, "lac": 100_000, "لاکھ": 100_000,
    "crore": 10_000_000, "krore": 10_000_000, "کروڑ": 10_000_000,
}

for _w, _v in _TENS_COMPOUNDS.items():
    _NUM_WORDS.setdefault(_w, _v)

_WORD_RE = re.compile(
    r"[A-Za-z\u0600-\u06ff]+", re.UNICODE
)
_DIGIT_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _word_value(word: str) -> int | None:
    return _NUM_WORDS.get(word.lower())


def normalize_spoken_numbers(text: str) -> str:
    """Insert bracketed digit forms after spoken number phrases.

    "Ahmad ko panch hazar diye" → "Ahmad ko panch hazar [5000] diye"
    "پندرہ سو روپے" → "پندرہ سو [1500] روپے"
    Digit tokens pass through untouched; unknown words are left alone.
    """
    if not text:
        return text
    words = _WORD_RE.findall(text)
    out = text
    i = 0
    inserts: list[tuple[int, int, str]] = []  # (start, end, replacement)
    while i < len(words):
        w = words[i]
        low = w.lower()
        val = _word_value(low)
        if val is not None:
            j = i + 1
            total = val
            scale_used = False
            # compose: number word(s) followed by scales (hazar/lakh/crore/sau)
            while j < len(words):
                nxt = words[j].lower()
                if nxt in _SCALE_WORDS and not scale_used:
                    total = val * _SCALE_WORDS[nxt] if val < 100 else total * _SCALE_WORDS[nxt]
                    scale_used = True
                    j += 1
                    continue
                break
            span_text = " ".join(words[i:j])
            inserts.append((i, j, f"{span_text} [{total}]"))
            i = j
            continue
        i += 1

    # replace by word index → rebuild string. Walk once, preserving separators.
    if not inserts:
        return text
    result = []
    last = 0
    positions = []
    # map word indexes to char offsets
    offset = 0
    for w in words:
        idx = text.find(w, offset)
        positions.append((idx, idx + len(w)))
        offset = idx + len(w)
    for (wi, wj, repl) in inserts:
        start = positions[wi][0]
        end = positions[wj - 1][1]
        result.append(text[last:start])
        result.append(repl)
        last = end
    result.append(text[last:])
    return "".join(result)


_SCALE_ONLY: dict[str, int] = {
    "hazar": 1_000, "hazaar": 1_000, "thousand": 1_000, "ہزار": 1_000,
    "lakh": 100_000, "lac": 100_000, "لاکھ": 100_000,
    "crore": 10_000_000, "krore": 10_000_000, "کروڑ": 10_000_000,
}


def count_amount_signals(text: str) -> int:
    """Count STRONG amount signals only — the things multi-person udhar notes
    actually carry: '<number-word> hazar/lakh/crore/thousand' pairs and digit
    groups ≥ 100 (or followed by a currency word). Item quantities ("do
    packet", "aath bori", "pandrah sau") deliberately do NOT count — they must
    not trip the collapse guard on ordinary single-entry sales."""
    if not text:
        return 0
    signals = 0
    words = [w.lower() for w in _WORD_RE.findall(text)]
    for i, w in enumerate(words):
        if w in _SCALE_ONLY and i > 0 and _word_value(words[i - 1]) is not None:
            signals += 1
    # digit groups: ≥100 counts always; smaller counts only with currency context
    for m in _DIGIT_RE.finditer(text):
        raw = m.group(0).replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        tail = text[m.end(): m.end() + 12].lower()
        if val >= 100 or tail.lstrip().startswith(("rup", "روپ")):
            signals += 1
    return signals


_PERSON_JOIN_RE = re.compile(
    r"(?:,\s*|\s+(?:aur|or|and|اور|یا|ya)\s+)", re.IGNORECASE
)


def count_person_joins(text: str) -> int:
    """Count connectors that typically join two person-amount clauses."""
    if not text:
        return 0
    return len(_PERSON_JOIN_RE.findall(text))


def collapse_suspected(transcript: str, entry_count: int) -> bool:
    """True when the transcript signals more person-amount clauses than entries
    returned — i.e., the model probably merged them into a summed total."""
    if not transcript or entry_count < 1:
        return False
    signals = count_amount_signals(transcript)
    joins = count_person_joins(transcript)
    return signals >= entry_count + 1 and joins >= 1
