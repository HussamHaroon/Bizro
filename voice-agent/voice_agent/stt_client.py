"""Free-tier speech-to-text client (D6-3) — OpenAI transcription API shape.

The OpenRouter free tier has no audio-input models (agentic-gated or $0.50
min balance), so the voice pipeline splits in two when STT_API_KEY is set:

    WhatsApp voice note → STT (Groq whisper-large-v3-turbo, free) → transcript
    transcript → text model (OpenRouter `:free`) → schema.md §1 transaction JSON

Defaults target Groq (console.groq.com/keys — free tier, no card, Urdu via
whisper-large-v3-turbo), but any OpenAI-shaped /audio/transcriptions endpoint
works: STT_BASE_URL + STT_API_KEY + STT_MODEL.

Every successful call is counted by llm_guard (STT calls consume free-tier
quota too).
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import Settings


class STTError(RuntimeError):
    pass


def transcribe(audio_bytes: bytes, *, filename: str = "voice.wav", settings: Settings) -> str:
    """Transcribe one voice note → transcript text (Urdu, verbatim)."""
    if not settings.stt_api_key:
        raise STTError("STT_API_KEY not set — speech-to-text unavailable")
    url = settings.stt_base_url.rstrip("/") + "/audio/transcriptions"
    import llm_guard  # free-tier budget guard (repo root; D6-2)

    llm_guard.allow(f"stt:{settings.stt_model}")
    files = {"file": (filename, audio_bytes, "audio/wav")}
    data: dict[str, Any] = {"model": settings.stt_model, "response_format": "json"}
    if settings.stt_language:
        data["language"] = settings.stt_language
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {settings.stt_api_key}"},
        files=files,
        data=data,
        timeout=120.0,
    )
    if resp.status_code != 200:
        raise STTError(f"STT HTTP {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    text = str(payload.get("text") or "").strip()
    llm_guard.record(f"stt:{settings.stt_model}", usage={"completion_tokens": len(text)})
    if not text:
        raise STTError("STT returned an empty transcript")
    return text
