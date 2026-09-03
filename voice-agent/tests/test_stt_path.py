"""D6-3 — the STT branch of process_voice_note (Groq whisper → text parse).

Offline-only: both the transcription POST and the text-parse POST are faked,
so the test proves the BRANCHING and data flow (wav → STT → transcript into
the parse prompt → schema transaction), never real endpoints.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from voice_agent.config import Settings
from voice_agent.pipeline import process_voice_note

REPO = Path(__file__).resolve().parents[2]
WAV = sorted((REPO / "media" / "2026").rglob("*.wav"))
WAV_PATH = str(WAV[0]) if WAV else None

pytestmark = pytest.mark.skipif(WAV_PATH is None, reason="no seeded sample wav on disk")


class _FakeResp:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


@pytest.fixture
def stt_settings(monkeypatch) -> Settings:
    s = Settings(
        dashscope_api_key="sk-or-test",  # live-ish: forces the non-mock branch
        dashscope_base_url="https://openrouter.test/api/v1",
        model_voice="test/text-model:free",
        mock_mode="never",
        stt_api_key="gsk_test",
        stt_base_url="https://api.groq.test/openai/v1",
        stt_model="whisper-large-v3-turbo",
        stt_language="ur",
    )
    monkeypatch.setattr("voice_agent.pipeline.DashScopeClient", _FakeClient)
    monkeypatch.setattr("voice_agent.stt_client.httpx.post", _fake_stt_post)
    return s


class _FakeStream:
    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_lines(self):
        yield "data: " + json.dumps({"choices": [{"delta": {"content": _PARSE_REPLY}}]})
        yield "data: [DONE]"


class _FakeHttpxClient:
    def __init__(self, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def stream(self, method, url, headers=None, json=None):
        return _FakeStream()


_PARSE_REPLY = json.dumps(
    {
        "transcript": "احمد کو پانچ ہزار کا ادھار دیا",
        "confidence": 0.9,
        "transaction": {
            "kind": "udhar_given",
            "amount_pkd": 5000,
            "counterparty": {"name": "احمد", "phone": None},
            "description": "Udhar 5000 to Ahmad",
            "item_lines": [],
            "unclear": [],
        },
    },
    ensure_ascii=False,
)


class _FakeClient:
    """Stands in for DashScopeClient; captures the parse prompt it is given."""

    last_user_text = ""

    def __init__(self, settings):
        self.settings = settings

    def chat_text(self, *, system, user_text, **kwargs):
        _FakeClient.last_user_text = user_text
        return type("R", (), {"text": _PARSE_REPLY, "usage": None})()

    def omni_chat(self, *, system, user_text, **kwargs):
        _FakeClient.last_user_text = user_text
        return type("R", (), {"text": _PARSE_REPLY, "usage": None})()


def _fake_stt_post(url, **kwargs):
    assert "audio/transcriptions" in url
    assert kwargs["data"]["model"] == "whisper-large-v3-turbo"
    return _FakeResp({"text": "احمد کو پانچ ہزار کا ادھار دیا"})


def test_stt_branch_transcribes_then_parses(stt_settings):
    out = process_voice_note(WAV_PATH, settings=stt_settings)
    # the transcript went INTO the parse prompt...
    assert "احمد کو پانچ ہزار کا ادھار دیا" in _FakeClient.last_user_text
    # ...and the parsed transaction came out the other end
    assert out["amount_pkd"] == 5000
    assert out["kind"] == "udhar_given"
    assert out["counterparty"]["name"] == "احمد"
    assert not out.get("mock")


def test_stt_failure_asks_again_instead_of_crashing(monkeypatch):
    s = Settings(
        dashscope_api_key="sk-or-test",
        mock_mode="never",
        stt_api_key="gsk_test",
        stt_model="whisper-large-v3-turbo",
    )
    monkeypatch.setattr("voice_agent.pipeline.DashScopeClient", _FakeClient)
    monkeypatch.setattr("voice_agent.dashscope_client.httpx.Client", _FakeHttpxClient)

    def _boom(url, **kwargs):
        from voice_agent.stt_client import STTError

        raise STTError("groq down")

    monkeypatch.setattr("voice_agent.stt_client.httpx.post", _boom)
    out = process_voice_note(WAV_PATH, settings=s)
    assert out["amount_pkd"] is None  # nothing fabricated
    assert out["flag"] == "low_confidence"
    assert out["status"] == "pending"
    assert "stt path failed" in out["description"]
