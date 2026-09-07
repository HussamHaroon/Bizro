"""STT_PROVIDER=auto routing tests — Qwen ASR when a DashScope key exists,
else the free-tier Groq path (the documented production architecture, made
true at the config level).

Pure `transcribe()` unit tests with fake transports: no wav file needed, no
network, no seeded media — so they do NOT live in test_stt_path.py, whose
module-level skipif (seeded wav) would silently skip them in fresh worktrees.
"""

from __future__ import annotations

import json

from voice_agent.config import Settings, load_settings
from voice_agent.stt_client import transcribe


class _FakeResp:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def _auto_settings(**over) -> Settings:
    """Defaults EXCEPT the knobs under test — stt_provider stays 'auto'."""
    base = dict(
        dashscope_api_key="sk-dash-test",
        dashscope_base_url="https://dashscope.test/compatible-mode/v1",
        model_voice="qwen-flash",
        mock_mode="never",
        stt_api_key="gsk_test",
        stt_base_url="https://api.groq.test/openai/v1",
        stt_model="whisper-large-v3-turbo",
        stt_language="ur",
    )
    base.update(over)
    return Settings(**base)


# --- config-level truth ------------------------------------------------------


def test_default_provider_is_auto():
    assert Settings().stt_provider == "auto"
    assert load_settings(env={}).stt_provider == "auto"


def test_provider_env_override_respected():
    assert load_settings(env={"STT_PROVIDER": "groq"}).stt_provider == "groq"
    assert load_settings(env={"STT_PROVIDER": "AUTO"}).stt_provider == "auto"
    assert load_settings(env={"STT_PROVIDER": "Qwen"}).stt_provider == "qwen"


# --- auto routing ------------------------------------------------------------


def test_auto_chooses_qwen_when_dashscope_key_present(monkeypatch):
    """auto + DashScope key → Qwen ASR answers; whisper is never called."""
    seen = []

    def _post(url, **kwargs):
        seen.append(url)
        if "chat/completions" in url:
            assert kwargs["json"]["model"] == "qwen3-asr-flash"
            return _FakeResp({"choices": [{"message": {"content": "qwen heard this"}}]})
        return _FakeResp({"text": "WHISPER-SHOULD-NOT-RUN"})

    monkeypatch.setattr("voice_agent.stt_client.httpx.post", _post)
    out = transcribe(b"x" * 64, filename="voice.wav", settings=_auto_settings())
    assert out == "qwen heard this"
    assert seen == ["https://dashscope.test/compatible-mode/v1/chat/completions"]


def test_auto_without_dashscope_key_uses_groq(monkeypatch):
    """auto + no DashScope key → free-tier Groq Whisper path, no Qwen attempt."""
    seen = []

    def _post(url, **kwargs):
        seen.append(url)
        assert "audio/transcriptions" in url
        assert kwargs["data"]["model"] == "whisper-large-v3-turbo"
        return _FakeResp({"text": "groq heard this"})

    monkeypatch.setattr("voice_agent.stt_client.httpx.post", _post)
    s = _auto_settings(dashscope_api_key="")
    assert transcribe(b"x" * 64, filename="voice.wav", settings=s) == "groq heard this"
    assert seen == ["https://api.groq.test/openai/v1/audio/transcriptions"]


def test_auto_qwen_failure_falls_back_to_groq(monkeypatch):
    """auto + Qwen outage → Groq catches the note; a voice note is never lost."""
    seen = []

    def _post(url, **kwargs):
        seen.append(url.split("/")[-1])
        if "chat/completions" in url:
            return _FakeResp({"error": "boom"}, status=500)
        return _FakeResp({"text": "groq saved it"})

    monkeypatch.setattr("voice_agent.stt_client.httpx.post", _post)
    s = _auto_settings()
    assert transcribe(b"x" * 64, filename="voice.wav", settings=s) == "groq saved it"
    assert seen == ["completions", "transcriptions"]


# --- explicit overrides keep working ------------------------------------------


def test_explicit_groq_override_skips_qwen(monkeypatch):
    """STT_PROVIDER=groq pins the free tier even with a DashScope key present."""
    seen = []

    def _post(url, **kwargs):
        seen.append(url)
        assert "audio/transcriptions" in url
        return _FakeResp({"text": "groq pinned"})

    monkeypatch.setattr("voice_agent.stt_client.httpx.post", _post)
    s = _auto_settings(stt_provider="groq")
    assert transcribe(b"x" * 64, filename="voice.wav", settings=s) == "groq pinned"
    assert all("chat/completions" not in u for u in seen)


def test_explicit_qwen_without_dashscope_key_degrades_to_groq(monkeypatch):
    """STT_PROVIDER=qwen but no DashScope key → Groq, never a crash."""
    seen = []

    def _post(url, **kwargs):
        seen.append(url)
        assert "audio/transcriptions" in url
        return _FakeResp({"text": "groq degraded"})

    monkeypatch.setattr("voice_agent.stt_client.httpx.post", _post)
    s = _auto_settings(stt_provider="qwen", dashscope_api_key="")
    assert transcribe(b"x" * 64, filename="voice.wav", settings=s) == "groq degraded"
    assert all("chat/completions" not in u for u in seen)
