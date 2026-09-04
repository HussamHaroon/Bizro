"""Speech-to-text client (D6-3) — Qwen ASR primary, Groq Whisper fallback.

Two providers, one function:

    STT_PROVIDER=qwen  → qwen3-asr-flash via the DashScope chat-completions
                         endpoint (single user message, one input_audio content
                         item carrying a base64 data URI — the strict shape the
                         ASR task accepts; text+audio mixes and system messages
                         are rejected). Any failure falls back to Whisper.
    STT_PROVIDER=groq  (default) → OpenAI-shaped /audio/transcriptions, i.e.
                         Groq whisper-large-v3-turbo (free, no card, Urdu).

The fallback is deliberate resilience: Qwen ASR rejects some container formats
(browser webm, Meta ogg/opus on some plans) and shares the Model Studio quota —
Whisper catches every one of those so a voice note is never lost to a
transcriber hiccup. Every successful call is counted by llm_guard.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class STTError(RuntimeError):
    pass


# Data-URI mediatypes the qwen3-asr task accepts (probe-verified: mp3 yes).
_QWEN_MIME = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
}


def transcribe(audio_bytes: bytes, *, filename: str = "voice.wav", settings: Settings) -> str:
    """Transcribe one voice note → transcript text (verbatim)."""
    if settings.stt_provider == "qwen" and settings.dashscope_api_key:
        try:
            return _qwen_asr(audio_bytes, filename=filename, settings=settings)
        except Exception as exc:  # noqa: BLE001 — any Qwen failure falls back
            logger.warning(
                "Qwen ASR failed (%s) — falling back to %s on %s",
                exc, settings.stt_model, settings.stt_base_url,
            )
    return _whisper_transcribe(audio_bytes, filename=filename, settings=settings)


def _qwen_asr(audio_bytes: bytes, *, filename: str, settings: Settings) -> str:
    """qwen3-asr-flash — chat-completions with an inline base64 data URI."""
    import llm_guard  # free-tier budget guard (repo root; D6-2)

    llm_guard.allow(f"stt:{settings.stt_qwen_model}")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".wav"
    mime = _QWEN_MIME.get(ext, "audio/mpeg")
    data_uri = f"data:{mime};base64,{base64.b64encode(audio_bytes).decode()}"
    resp = httpx.post(
        settings.dashscope_base_url.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {settings.dashscope_api_key}"},
        json={
            "model": settings.stt_qwen_model,
            "messages": [
                {"role": "user", "content": [
                    {"type": "input_audio", "input_audio": {"data": data_uri}},
                ]},
            ],
        },
        timeout=120.0,
    )
    if resp.status_code != 200:
        raise STTError(f"Qwen ASR HTTP {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    try:
        text = str(payload["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise STTError(f"Qwen ASR unexpected response: {payload!r:.300}") from exc
    llm_guard.record(f"stt:{settings.stt_qwen_model}", usage={"completion_tokens": len(text)})
    if not text:
        raise STTError("Qwen ASR returned an empty transcript")
    return text


def _whisper_transcribe(audio_bytes: bytes, *, filename: str, settings: Settings) -> str:
    """OpenAI-shaped /audio/transcriptions (Groq whisper-large-v3-turbo)."""
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
