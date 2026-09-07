"""Dual-engine STT cross-check tests — all offline (fake transcribers / pure fns).

The contract: two independent transcriptions agreeing on the same voice note
BOOST entry confidence; disagreeing engines PENALIZE it and leave both
previews in the audit trail. Single-engine runs are byte-identical to before.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice_agent.config import load_settings
from voice_agent.stt_crosscheck import (
    apply_crosscheck,
    evaluate,
    normalize_transcript,
    similarity,
)
from voice_agent import stt_client


@pytest.fixture()
def settings_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-crosscheck")
    monkeypatch.setenv("STT_CROSSCHECK", "auto")
    return load_settings()


# ---------------------------------------------------------------------------
# Normalization + similarity (comparison-only transforms)
# ---------------------------------------------------------------------------

def test_normalize_folds_urdu_digits_and_punctuation():
    a = normalize_transcript("احمد کو ۵۰۰۰ روپے دیے۔")
    b = normalize_transcript("احمد کو 5000 روپے دیے")
    assert a == b


def test_normalize_folds_yeh_alif_variants():
    assert normalize_transcript("Ahmed کے") != ""  # roman survives
    a = normalize_transcript("بلال نے دیے")
    b = normalize_transcript("بلال نے دئے")  # yeh-barree variant spelling
    # not guaranteed equal (different letters), but similarity must be high
    assert similarity(a, b) > 0.7


def test_similarity_identical_vs_different():
    t = "احمد کو پانچ ہزار روپے ادھار دیے"
    assert similarity(t, t) == 1.0
    assert similarity(t, "برفانی توتے کھاؤ") < 0.3
    assert similarity("", t) == 0.0


# ---------------------------------------------------------------------------
# Agreement evaluation → confidence delta
# ---------------------------------------------------------------------------

def test_agreement_above_threshold_gives_bonus(settings_with_key):
    cross = evaluate(
        "احمد کو پانچ ہزار روپے ادھار دیے",
        "احمد کو پانچ ہزار روپے ادھار دیا",  # one-word inflection
        settings_with_key,
    )
    assert cross["agreed"] is True
    assert cross["confidence_delta"] == pytest.approx(0.10)


def test_disagreement_below_threshold_gives_penalty(settings_with_key):
    cross = evaluate(
        "احمد کو پانچ ہزار روپے ادھار دیے",
        "احمد کو دو ہزار روپے ادھار دیے اور بلال کو تین ہزار",
        settings_with_key,
    )
    assert cross["agreed"] is False
    assert cross["confidence_delta"] == pytest.approx(-0.10)
    # BOTH previews travel in the audit record
    assert "پانچ ہزار" in cross["primary_preview"]
    assert "بلال" in cross["secondary_preview"]


# ---------------------------------------------------------------------------
# apply_crosscheck: entries stamped + confidence adjusted
# ---------------------------------------------------------------------------

def _entry(conf):
    return {
        "source": {
            "type": "voice", "media_id": None, "model": "m",
            "confidence": conf, "raw_output": {"transcript": "t"},
        },
        "flag": "none",
    }


def test_apply_crosscheck_boosts_on_agreement(settings_with_key):
    cross = evaluate("same words", "same words", settings_with_key)
    entries = [_entry(0.85), _entry(0.88)]
    apply_crosscheck(entries, cross)
    assert entries[0]["source"]["confidence"] == pytest.approx(0.95)
    assert entries[1]["source"]["confidence"] == pytest.approx(0.98)
    rec = entries[0]["source"]["raw_output"]["stt_crosscheck"]
    assert rec["agreed"] is True


def test_apply_crosscheck_clamps_at_one(settings_with_key):
    cross = evaluate("same words", "same words", settings_with_key)
    entries = [_entry(0.97)]
    apply_crosscheck(entries, cross)
    assert entries[0]["source"]["confidence"] == 1.0


def test_apply_crosscheck_none_is_noop(settings_with_key):
    entries = [_entry(0.85)]
    before = dict(entries[0]["source"])
    apply_crosscheck(entries, None)
    assert entries[0]["source"]["confidence"] == before["confidence"]
    assert "stt_crosscheck" not in entries[0]["source"]["raw_output"]


# ---------------------------------------------------------------------------
# transcribe_dual: engine selection + graceful degradation (fake engines)
# ---------------------------------------------------------------------------

def test_transcribe_dual_both_engines(settings_with_key, monkeypatch):
    monkeypatch.setattr(
        stt_client, "transcribe",
        lambda *a, **k: "احمد کو پانچ ہزار روپے ادھار دیے",
    )
    monkeypatch.setattr(
        stt_client, "_openai_transcribe",
        lambda *a, **k: "احمد کو پانچ ہزار روپے ادھار دیا",
    )
    out = stt_client.transcribe_dual(b"x" * 64, settings=settings_with_key)
    assert out["transcript"].startswith("احمد")
    assert out["secondary"] is not None
    assert out["cross"]["agreed"] is True
    assert len(out["engines"]) == 2


def test_transcribe_dual_secondary_failure_degrades(settings_with_key, monkeypatch):
    monkeypatch.setattr(
        stt_client, "transcribe", lambda *a, **k: "primary heard this"
    )

    def boom(*a, **k):
        raise stt_client.STTError("openai down")

    monkeypatch.setattr(stt_client, "_openai_transcribe", boom)
    out = stt_client.transcribe_dual(b"x" * 64, settings=settings_with_key)
    assert out["transcript"] == "primary heard this"
    assert out["cross"] is None
    assert "secondary" in out["errors"]


def test_transcribe_dual_primary_failure_uses_secondary(settings_with_key, monkeypatch):
    def boom(*a, **k):
        raise stt_client.STTError("primary down")

    monkeypatch.setattr(stt_client, "transcribe", boom)
    monkeypatch.setattr(
        stt_client, "_openai_transcribe", lambda *a, **k: "secondary heard this"
    )
    out = stt_client.transcribe_dual(b"x" * 64, settings=settings_with_key)
    assert out["transcript"] == "secondary heard this"
    assert out["cross"] is None  # only one transcript → no comparison


def test_transcribe_dual_both_fail_raises(settings_with_key, monkeypatch):
    monkeypatch.setattr(
        stt_client, "transcribe",
        lambda *a, **k: (_ for _ in ()).throw(stt_client.STTError("p down")),
    )
    monkeypatch.setattr(
        stt_client, "_openai_transcribe",
        lambda *a, **k: (_ for _ in ()).throw(stt_client.STTError("s down")),
    )
    with pytest.raises(stt_client.STTError):
        stt_client.transcribe_dual(b"x" * 64, settings=settings_with_key)


def test_crosscheck_off_never_calls_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("STT_CROSSCHECK", "off")
    s = load_settings()
    assert s.crosscheck_enabled is False
    monkeypatch.setattr(
        stt_client, "transcribe", lambda *a, **k: "solo transcript"
    )
    called = {"openai": False}

    def must_not_call(*a, **k):
        called["openai"] = True
        return "should not happen"

    monkeypatch.setattr(stt_client, "_openai_transcribe", must_not_call)
    out = stt_client.transcribe_dual(b"x" * 64, settings=s)
    assert out["cross"] is None and called["openai"] is False


def test_auto_mode_requires_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("STT_CROSSCHECK", "auto")
    assert load_settings().crosscheck_enabled is False
