"""Dual-engine STT cross-check — agreement between two INDEPENDENT
transcriptions as a confidence signal.

Idea: Groq/Qwen Whisper hears the voice note one way; OpenAI Whisper hears it
again with a different acoustic model. If the two transcripts agree, the words
are almost certainly right (confidence boost). If they disagree, either engine
may have misheard — entries are penalized below the confirm threshold and the
audit trail records the divergence, so the merchant gets asked to confirm
instead of a wrong number slipping through silently.

Pure functions here; the network lives in stt_client.transcribe_dual.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import Any

from .config import Settings

# Arabic-Indic / Urdu digits → ASCII so "۵۰۰۰" and "5000" compare equal.
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
# Arabic yeh/alif/heh variants that ASR engines spell inconsistently.
_CHAR_MAP = str.maketrans({"ی": "ي", "ى": "ي", "أ": "ا", "إ": "ا", "آ": "ا", "ۀ": "ہ", "ة": "ه"})
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_transcript(text: str) -> str:
    """Aggressive normalization for COMPARISON ONLY — never shown to anyone."""
    s = unicodedata.normalize("NFC", text or "")
    s = s.casefold().translate(_DIGIT_MAP).translate(_CHAR_MAP)
    # roman-u arabic-ayn-lam forms and tatweel
    s = s.replace("\u0640", "")
    s = _PUNCT_RE.sub(" ", s)
    s = _SPACE_RE.sub(" ", s)
    return s.strip()


def similarity(a: str, b: str) -> float:
    """0..1 SequenceMatcher ratio over normalized transcripts."""
    na, nb = normalize_transcript(a), normalize_transcript(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def evaluate(
    primary: str, secondary: str, settings: Settings
) -> dict[str, Any]:
    """Compare the two engine transcripts → crosscheck record (auditable)."""
    sim = similarity(primary, secondary)
    agreed = sim >= settings.stt_agree_threshold
    delta = settings.stt_agree_bonus if agreed else -settings.stt_disagree_penalty
    return {
        "agreed": agreed,
        "similarity": round(sim, 4),
        "threshold": settings.stt_agree_threshold,
        "confidence_delta": delta,
        "primary_preview": (primary or "")[:120],
        "secondary_preview": (secondary or "")[:120],
    }


def apply_crosscheck(entries: list[dict], cross: dict[str, Any] | None) -> list[dict]:
    """Stamp the crosscheck record on every entry's raw_output and adjust each
    entry's source.confidence by the agreement delta (clamped to [0, 1]).

    Mutates and returns the entries. When `cross` is None (single-engine run)
    this is a no-op — the plain path is byte-identical to before."""
    if not cross:
        return entries
    delta = float(cross.get("confidence_delta") or 0.0)
    for tx in entries or []:
        src = dict(tx.get("source") or {})
        raw = dict(src.get("raw_output") or {})
        raw["stt_crosscheck"] = cross
        src["raw_output"] = raw
        conf = src.get("confidence")
        if isinstance(conf, (int, float)):
            src["confidence"] = round(min(1.0, max(0.0, float(conf) + delta)), 3)
        tx["source"] = src
    return entries
