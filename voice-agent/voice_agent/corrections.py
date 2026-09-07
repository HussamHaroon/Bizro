"""Cancel-command detector — CONTRACT with the server agent (build exactly this).

Server webhook contract (server agent integrates this BEFORE the pipeline):
  1. On every inbound WhatsApp text/voice-note transcript, call
     ``is_cancel_command(text)`` FIRST. It is pure, stdlib-only, and offline —
     safe to call on the hot webhook path before any model work.
  2. When it returns True, the webhook MUST NOT call the voice pipeline for
     that message. The SERVER performs the actual cancel of the merchant's
     most recent entry (it owns the ledger write) and replies with the string
     from ``CANCEL_CONFIRMATION_REPLIES`` for the message's language key
     ("en" | "ur" — same language ruling as confirmation.detect_language:
     Arabic-script material = "ur", Roman Urdu/digits = "en").
  3. This module is detection + reply copy ONLY. It never touches the ledger
     and never decides WHAT was cancelled — that is server state.

Matcher design (deliberately dead simple, deterministic, fully unit-tested):
  - Normalize: NFC, casefold, unify Arabic yeh/alif/heh variants (the ones ASR
    engines and keyboards spell inconsistently), strip punctuation to spaces,
    collapse whitespace.
  - Rule 1 (exact): normalized text equals one of the contract phrases.
  - Rule 2 (substring on SHORT input): a contract phrase appears as a
    contiguous substring AND the input has at most len(phrase words) + 2
    words — this absorbs politeness padding ("please", "bhai") without ever
    matching a real transaction note (those carry names/amounts and run long).
  - Anything else → False. "cancel" alone, a bare greeting, or a full
    transaction sentence NEVER match; they flow to the pipeline as usual.

EXTENDING the phrase set is a cross-agent contract change: server-agent and
voice-agent must update the same list in lockstep (this file is the source of
truth for both detection and the reply copy below).
"""

from __future__ import annotations

import re
import unicodedata

# --- The contract phrase set (case-insensitive after normalization) ---------
_CANCEL_PHRASES_RAW = (
    # English
    "cancel last",
    "cancel last entry",
    "undo last",
    "undo last entry",
    "delete last entry",
    # Roman Urdu
    "wo wapas karo",
    "pichla entry cancel",
    "pichli entry khatam karo",
    "pichla cancel karo",
    # Urdu script
    "پچھلی انٹری کینسل کرو",
    "آخری انٹری کینسل",
)

# Politeness padding budget for the substring rule (in extra words).
_MAX_SLACK_WORDS = 2

_VARIANT_MAP = str.maketrans(
    {"ی": "ي", "ى": "ي", "أ": "ا", "إ": "ا", "آ": "ا", "ۀ": "ہ", "ة": "ه"}
)
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def _normalize(text: object) -> str:
    """Case/punct/variant-insensitive form used for BOTH phrases and input."""
    if text is None:
        return ""
    s = unicodedata.normalize("NFC", str(text))
    s = s.casefold().translate(_VARIANT_MAP)
    s = _PUNCT_RE.sub(" ", s)
    s = _SPACE_RE.sub(" ", s)
    return s.strip()


# Normalized once at import; order preserved, duplicates dropped.
_PHRASES: tuple[str, ...] = tuple(dict.fromkeys(_normalize(p) for p in _CANCEL_PHRASES_RAW))
_PHRASE_SET = frozenset(_PHRASES)


def is_cancel_command(text: object) -> bool:
    """True only when the message is a request to cancel the last entry.

    None-safe and offline-safe: `None`, empty, whitespace, "cancel" alone, and
    any ordinary transaction sentence all return False. Exact contract with
    the server webhook — see module docstring for the integration ruling.
    """
    norm = _normalize(text)
    if not norm:
        return False
    if norm in _PHRASE_SET:
        return True
    words = norm.split()
    for phrase in _PHRASES:
        if phrase in norm and len(words) <= len(phrase.split()) + _MAX_SLACK_WORDS:
            return True
    return False


# Reply copy the server sends after a successful cancel — single source of
# truth so the webhook's wording never drifts from the voice agent's rulings.
# Keys follow the language ruling ("en" for Roman-Urdu/digits, "ur" for
# Arabic-script material — confirmation.detect_language).
CANCEL_CONFIRMATION_REPLIES = {
    "en": "Done. Your last entry is cancelled.",
    "ur": "ہو گیا۔ آخری اندراج کینسل ہو گیا۔",
}
