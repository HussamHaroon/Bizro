"""Speech-to-text client (D6-3) — Qwen ASR primary, Groq Whisper fallback.

Two providers, one function:

    STT_PROVIDER=auto (default) → the documented architecture, made true:
                         Qwen ASR (qwen3-asr-flash via the DashScope
                         chat-completions endpoint) runs FIRST whenever a
                         DASHSCOPE_API_KEY is present; without a key the
                         free-tier Groq path is used. Any Qwen failure falls
                         back to Whisper.
    STT_PROVIDER=qwen  → pin Qwen ASR: qwen3-asr-flash via the DashScope
                         chat-completions endpoint (single user message, one
                         input_audio content item carrying a base64 data URI —
                         the strict shape the ASR task accepts; text+audio
                         mixes and system messages are rejected). Any failure
                         falls back to Whisper.
    STT_PROVIDER=groq  → pin the OpenAI-shaped /audio/transcriptions, i.e.
                         Groq whisper-large-v3-turbo (free, no card, Urdu) —
                         the free-tier fallback.

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

from . import stt_crosscheck
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

# Omni-audio chat models need this alongside the audio; dedicated ASR tasks
# tolerate it (documented vocab/context slot).
_ASR_INSTRUCTION = (
    "This audio is a shopkeeper's voice note for a ledger. Transcribe it "
    "VERBATIM in its original language (usually Urdu). Output ONLY the "
    "transcript text — no explanations, no translation, no commentary."
)


def transcribe(audio_bytes: bytes, *, filename: str = "voice.wav", settings: Settings) -> str:
    """Transcribe one voice note → transcript text (verbatim).

    Provider selection (settings.stt_provider):
      "auto" (default) → Qwen ASR when a DashScope key is present, else Groq;
      "qwen" / "groq"  → pin one engine (qwen still degrades to Groq without
      a DashScope key). A Qwen failure ALWAYS falls back to Groq Whisper.
    """
    wants_qwen = settings.stt_provider == "qwen" or (
        settings.stt_provider == "auto" and bool(settings.dashscope_api_key)
    )
    if wants_qwen and settings.dashscope_api_key:
        try:
            return _qwen_asr(audio_bytes, filename=filename, settings=settings)
        except Exception as exc:  # noqa: BLE001 — any Qwen failure falls back
            logger.warning(
                "Qwen ASR failed (%s) — falling back to %s on %s",
                exc, settings.stt_model, settings.stt_base_url,
            )
    return _whisper_transcribe(audio_bytes, filename=filename, settings=settings)


def transcribe_dual(
    audio_bytes: bytes, *, filename: str = "voice.wav", settings: Settings
) -> dict[str, Any]:
    """Primary engine + independent OpenAI Whisper second opinion.

    Returns `{"transcript", "primary", "secondary", "cross", "engines", "errors"}`
    where `cross` is the stt_crosscheck record (see stt_crosscheck.evaluate) or
    None when the second engine is disabled/failed. The chosen transcript is the
    primary's when it succeeded, else the secondary's (never lose a voice note
    to one engine's hiccup)."""
    transcript = None
    errors: dict[str, str] = {}
    try:
        transcript = transcribe(audio_bytes, filename=filename, settings=settings)
    except Exception as exc:  # noqa: BLE001 — recorded, secondary still runs
        errors["primary"] = str(exc)[:200]
        logger.warning("primary STT failed: %s", exc)

    secondary = None
    cross: dict[str, Any] | None = None
    if settings.crosscheck_enabled:
        try:
            secondary = _openai_transcribe(
                audio_bytes, filename=filename, settings=settings
            )
        except Exception as exc:  # noqa: BLE001 — crosscheck is best-effort
            errors["secondary"] = str(exc)[:200]
            logger.warning("crosscheck STT failed: %s", exc)

    if transcript is None and secondary is not None:
        transcript = secondary
    if transcript is None:
        raise STTError(
            "all STT engines failed: " + "; ".join(f"{k}: {v}" for k, v in errors.items())
            or "no STT engine available"
        )
    if transcript is not None and secondary is not None and transcript != secondary:
        cross = stt_crosscheck.evaluate(transcript, secondary, settings)
    engines = [settings.stt_model]
    if secondary is not None:
        engines.append(settings.stt_secondary_model)
    return {
        "transcript": transcript,
        "primary": transcript,
        "secondary": secondary,
        "cross": cross,
        "engines": engines,
        "errors": errors,
    }


def _openai_transcribe(
    audio_bytes: bytes, *, filename: str, settings: Settings
) -> str:
    """OpenAI's own Whisper (or gpt-4o-transcribe) — the INDEPENDENT second
    opinion for the cross-check. Same OpenAI-shaped endpoint, different vendor."""
    if not settings.openai_api_key:
        raise STTError("OPENAI_API_KEY not set — crosscheck engine unavailable")
    import llm_guard  # free-tier budget guard (repo root; D6-2)

    llm_guard.allow(f"stt:{settings.stt_secondary_model}")
    files = {"file": (filename, audio_bytes, "audio/wav")}
    data: dict[str, Any] = {"model": settings.stt_secondary_model, "response_format": "json"}
    if settings.stt_language:
        data["language"] = settings.stt_language
    resp = httpx.post(
        settings.openai_base_url.rstrip("/") + "/audio/transcriptions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        files=files,
        data=data,
        timeout=20.0,
    )
    if resp.status_code != 200:
        raise STTError(
            f"OpenAI STT HTTP {resp.status_code}: {resp.text[:300]}"
        )
    payload = resp.json()
    text = str(payload.get("text") or "").strip()
    llm_guard.record(
        f"stt:{settings.stt_secondary_model}", usage={"completion_tokens": len(text)}
    )
    if not text:
        raise STTError("OpenAI STT returned an empty transcript")
    return text


def _qwen_asr(audio_bytes: bytes, *, filename: str, settings: Settings) -> str:
    """Qwen ASR — chat-completions with an inline base64 data URI.

    Works with the dedicated qwen3-asr task and with omni-audio chat models
    (qwen3.8-omni-flash); the latter require an explicit verbatim instruction,
    otherwise they explain the audio instead of transcribing it.
    """
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
                    {"type": "text", "text": _ASR_INSTRUCTION},
                ]},
            ],
        },
        timeout=20.0,
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
        timeout=20.0,
    )
    if resp.status_code != 200:
        raise STTError(f"STT HTTP {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    text = str(payload.get("text") or "").strip()
    llm_guard.record(f"stt:{settings.stt_model}", usage={"completion_tokens": len(text)})
    if not text:
        raise STTError("STT returned an empty transcript")
    return text
