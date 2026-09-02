"""Thin DashScope client for the Qwen-Omni chat completions API.

Call shape verified against live docs 2026-08-21 (voice-agent/notes.md §1):
- POST {DASHSCOPE_BASE_URL}/chat/completions, OpenAI-compatible.
- Audio in: content item {"type":"input_audio","input_audio":{"data":<url|data:;base64,..>,"format":"wav"}}.
- stream=true is MANDATORY for Qwen-Omni (docs: otherwise it errors) → SSE parsing here.
- Text-only replies: modalities=["text"] (our MVP). Audio-out: ["text","audio"] +
  audio={"voice":...,"format":"wav"} — used by the speech-out probe only.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field

import httpx

from voice_agent.config import Settings
from voice_agent.decode import DecodedAudio


class DashScopeError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


@dataclass
class OmniResponse:
    text: str = ""
    audio_b64_chunks: list[str] = field(default_factory=list)  # base64 PCM frames (probe)
    audio_format: str | None = None
    audio_rate_hz: int | None = None
    finish_reason: str | None = None
    usage: dict | None = None

    @property
    def pcm(self) -> bytes:
        """Concatenated raw audio bytes (docs: WAV 24 kHz 16-bit mono by default)."""
        return b"".join(base64.b64decode(c) for c in self.audio_b64_chunks)


class DashScopeClient:
    """Real client. Requires DASHSCOPE_API_KEY (MOCK_MODE=never/auto-with-key)."""

    def __init__(self, settings: Settings):
        if not settings.dashscope_api_key:
            raise DashScopeError("DASHSCOPE_API_KEY not set (MOCK_MODE=auto would mock)")
        self.settings = settings

    def omni_chat(
        self,
        *,
        system: str,
        user_text: str,
        audio: DecodedAudio | None = None,
        modalities: list[str] | None = None,
        voice: str | None = None,
        audio_format: str | None = None,
        temperature: float = 0.1,
    ) -> OmniResponse:
        content: list[dict] = []
        if audio is not None:
            content.append(
                {
                    "type": "input_audio",
                    "input_audio": {"data": audio.data_uri, "format": audio.api_format},
                }
            )
        content.append({"type": "text", "text": user_text})

        payload: dict = {
            "model": self.settings.model_voice,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "modalities": modalities or ["text"],
            "stream": True,  # mandatory for Qwen-Omni (notes.md §1)
            "stream_options": {"include_usage": True},
            "temperature": temperature,
        }
        if "audio" in payload["modalities"]:
            payload["audio"] = {"voice": voice or self.settings.probe_voice,
                                "format": audio_format or "wav"}

        url = self.settings.dashscope_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.dashscope_api_key}"}

        import llm_guard  # free-tier budget guard (repo root; D6-2)

        llm_guard.allow(self.settings.model_voice)

        resp = OmniResponse(audio_format=audio_format if "audio" in payload["modalities"] else None)
        timeout = httpx.Timeout(connect=10.0, read=180.0, write=120.0, pool=30.0)
        try:
            with httpx.Client(timeout=timeout) as http:
                with http.stream("POST", url, headers=headers, json=payload) as stream:
                    if stream.status_code != 200:
                        body = stream.read().decode("utf-8", "replace")[:1000]
                        raise DashScopeError(
                            f"DashScope HTTP {stream.status_code}: {body}",
                            status=stream.status_code,
                            body=body,
                        )
                    for line in stream.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[len("data:"):].strip()
                        if not data or data == "[DONE]":
                            if data == "[DONE]":
                                break
                            continue
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        _merge_chunk(resp, chunk)
        except DashScopeError:
            raise
        except httpx.HTTPError as exc:
            raise DashScopeError(f"DashScope transport error: {exc}") from exc
        llm_guard.record(self.settings.model_voice, usage=resp.usage)
        return resp


def _merge_chunk(resp: OmniResponse, chunk: dict) -> None:
    if chunk.get("usage"):
        resp.usage = chunk["usage"]
    choices = chunk.get("choices") or []
    if not choices:
        return
    choice = choices[0]
    if choice.get("finish_reason"):
        resp.finish_reason = choice["finish_reason"]
    delta = choice.get("delta") or {}
    if delta.get("content"):
        resp.text += delta["content"]
    audio = delta.get("audio") or {}
    if audio.get("data"):
        resp.audio_b64_chunks.append(audio["data"])
        if audio.get("sample_rate"):
            resp.audio_rate_hz = audio["sample_rate"]
