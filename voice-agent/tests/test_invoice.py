"""Invoice renderer tests: token-law HTML, PNG render via system Edge (if available),
and the never-block text fallback. Also decode-step tests (ffmpeg via imageio-ffmpeg)."""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

from voice_agent.config import Settings
from voice_agent.invoice import build_invoice_html, build_invoice_text, load_tokens, render_invoice
from voice_agent.decode import DecodeError, decode_audio, looks_like_ogg

REPO_ROOT = Path(__file__).resolve().parents[2]


def _settings(**over) -> Settings:
    base = dict(mock_mode="always", numeral_style="western", repo_root=REPO_ROOT)
    base.update(over)
    return Settings(**base)


@pytest.fixture()
def udhar_tx() -> dict:
    return {
        "kind": "udhar_given",
        "amount_pkd": 5000,
        "currency": "PKR",
        "counterparty": {"name": "احمد", "phone": None},
        "description": "Udhar given to Ahmad",
        "item_lines": [],
        "occurred_at": "2026-08-21T19:03:00+05:00",
        "source": {"type": "voice", "media_id": "abc-123", "model": None,
                   "confidence": 0.93, "raw_output": {"transcript": "…"}},
        "flag": "none",
        "status": "pending",
        "confirmation_ur": "…",
        "mock": True,
    }


# --- token law ------------------------------------------------------------------


def test_html_uses_only_token_colors(udhar_tx):
    tokens = load_tokens(_settings())
    html = build_invoice_html(udhar_tx, tokens, "western")
    allowed = set(tokens["color"].values())
    # every hex we emit must come from tokens.json
    import re

    for hexcode in set(re.findall(r"#[0-9A-Fa-f]{6}\b", html)):
        assert hexcode.upper() in {c.upper() for c in allowed}, hexcode
    assert "box-shadow" not in html  # elevation rule: rule-lines, never shadows
    assert html.count('xmlns="http://www.w3.org/2000/svg"') >= 1  # torn edge + seal


def test_html_distinguishes_debit_vs_settled_by_more_than_color():
    tokens = load_tokens(_settings())
    red = build_invoice_html({**_base("udhar_given"), "kind": "udhar_given"}, tokens)
    teal = build_invoice_html({**_base("udhar_settlement"), "kind": "udhar_settlement"}, tokens)
    assert "UDHAR GIVEN" in red and "SETTLEMENT" in teal  # word differs
    assert "▲" in red and "✓" in teal                      # icon differs


def _base(kind: str) -> dict:
    return {
        "kind": kind, "amount_pkd": 5000,
        "counterparty": {"name": "احمد"}, "item_lines": [],
        "occurred_at": "2026-08-21T19:03:00+05:00",
        "source": {"confidence": 0.9}, "flag": "none", "mock": False,
    }


def test_mock_watermark_present_only_for_mock(udhar_tx):
    tokens = load_tokens(_settings())
    assert "MOCK DATA" in build_invoice_html(udhar_tx, tokens)
    real = {**udhar_tx, "mock": False}
    assert "MOCK DATA" not in build_invoice_html(real, tokens)


def test_amounts_in_digits_and_words(udhar_tx):
    tokens = load_tokens(_settings())
    html = build_invoice_html(udhar_tx, tokens, "western")
    assert "5000" in html and "پانچ ہزار" in html  # §4.7 numbers shown AND word form


# --- PNG render (system Edge) + text fallback -------------------------------------


def test_render_png_or_fallback(udhar_tx, tmp_path):
    out = render_invoice(udhar_tx, tmp_path / "inv", settings=_settings())
    assert out.exists() and out.is_file()
    if out.suffix == ".png":
        assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    else:
        assert out.suffix == ".txt" and "5000" in out.read_text(encoding="utf-8")


def test_render_never_blocks_confirmation_path(udhar_tx, tmp_path, monkeypatch):
    """Break playwright entirely → text receipt, no exception."""
    import sys

    monkeypatch.setitem(sys.modules, "playwright", None)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", None)
    out = render_invoice(udhar_tx, tmp_path / "inv", settings=_settings())
    assert out.suffix == ".txt"
    text = out.read_text(encoding="utf-8")
    assert "5000" in text and "پانچ ہزار" in text
    assert "MOCK DATA" in text
    assert "Alibaba Cloud AI Verified" in text


def test_low_confidence_invoice_carries_warning(udhar_tx, tmp_path):
    udhar_tx["flag"] = "low_confidence"
    tokens = load_tokens(_settings())
    html = build_invoice_html(udhar_tx, tokens)
    assert "پکا نہیں" in html


# --- decode step -------------------------------------------------------------------


def _make_wav(path: Path, seconds: float = 0.2, rate: int = 16000) -> bytes:
    n = int(seconds * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(struct.pack("<h", int(8000 * __import__("math").sin(i / 20)))
                          for i in range(n))
        w.writeframes(frames)
    return path.read_bytes()


def test_decode_passthrough_wav(tmp_path):
    wav_bytes = _make_wav(tmp_path / "t.wav")
    decoded = decode_audio(wav_bytes, strategy="ffmpeg")
    assert decoded.api_format == "wav" and decoded.strategy == "passthrough"
    assert decoded.data == wav_bytes


def test_decode_ogg_via_ffmpeg(tmp_path):
    """Round-trip: wav → ogg (bundled ffmpeg encodes) → decode back to 16k wav."""
    import subprocess

    import imageio_ffmpeg

    src = tmp_path / "t.wav"
    _make_wav(src)
    ogg = tmp_path / "t.ogg"
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    enc = subprocess.run(
        [exe, "-hide_banner", "-loglevel", "error", "-i", str(src),
         "-c:a", "libopus", "-b:a", "24k", str(ogg)],
        capture_output=True, timeout=120,
    )
    if enc.returncode != 0:  # bundled build without opus encoder → skip, not fail
        pytest.skip("bundled ffmpeg cannot encode opus")
    assert looks_like_ogg(ogg.read_bytes())
    decoded = decode_audio(ogg.read_bytes(), strategy="ffmpeg")
    assert decoded.api_format == "wav" and decoded.data[:4] == b"RIFF"


def test_decode_garbage_raises():
    with pytest.raises(DecodeError):
        decode_audio(b"not audio at all" * 8, strategy="ffmpeg")


def test_decode_empty_raises():
    with pytest.raises(DecodeError):
        decode_audio(b"", strategy="ffmpeg")


def test_decode_raw_rejects_ogg():
    with pytest.raises(DecodeError):
        decode_audio(b"OggS" + b"\x00" * 64, strategy="raw")
