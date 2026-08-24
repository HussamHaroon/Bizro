"""Bizro voice-agent — Voice Khata pipeline.

WhatsApp Urdu voice note in → structured transaction JSON (server/schema.md §1) +
clean Urdu text confirmation out, plus the branded WhatsApp invoice renderer.

Text-only confirmation is the MVP path (design.md §2): Urdu speech-OUT for the omni
model is only usable after `scripts/test_omni_urdu_speech_out.py` passes with a key.
"""

from voice_agent.config import Settings, load_settings
from voice_agent.confirmation import (
    amount_in_urdu_words,
    build_confirmation_ur,
    to_numeral_digits,
)
from voice_agent.invoice import render_invoice
from voice_agent.pipeline import process_voice_note

__all__ = [
    "process_voice_note",
    "render_invoice",
    "build_confirmation_ur",
    "amount_in_urdu_words",
    "to_numeral_digits",
    "Settings",
    "load_settings",
]
