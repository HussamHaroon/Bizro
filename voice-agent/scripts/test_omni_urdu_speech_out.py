#!/usr/bin/env python3
"""Bizro Day-0 probe: can qwen3.5-omni-plus SPEAK Urdu out? (design.md §2 / §9)

Run the instant DASHSCOPE_API_KEY lands:
    .venv/Scripts/python.exe scripts/test_omni_urdu_speech_out.py

What it does (call shape per voice-agent/notes.md §1):
  1. Asks the omni model (modalities=["text","audio"], voice=<PROBE_VOICE|Tina>) to
     speak one fixed, unambiguous Urdu sentence.
  2. Saves the returned audio as WAV (docs default: 24 kHz 16-bit mono) under
     voice-agent/probe_output/.
  3. Prints a machine verdict (audio bytes received or not) and reminds you that a
     HUMAN must listen — doc language lists (notes.md §2) say nothing about accent or
     intelligibility.

Exit codes: 0 = audio bytes received; 1 = no audio / API refused; 2 = no API key.
Until this probe passes AND a human approves the audio, NOTHING in the pipeline may
depend on Urdu voice output — text confirmation is the MVP path.
"""

from __future__ import annotations

import datetime as dt
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # voice-agent/
sys.path.insert(0, str(ROOT))                        # import voice_agent from worktree

from voice_agent.config import load_settings          # noqa: E402
from voice_agent.dashscope_client import DashScopeClient, DashScopeError  # noqa: E402

TARGET_SENTENCE_UR = (
    "احمد کو پانچ ہزار روپے ادھار دیے گئے۔ کیا یہ اندراج درست ہے؟"
)

SYSTEM_PROMPT = (
    "You are testing Urdu speech output. Speak EXACTLY the sentence the user gives you, "
    "in natural Urdu. Do not add anything."
)


def probe_rate(resp) -> int:
    if getattr(resp, "audio_rate_hz", None):
        return int(resp.audio_rate_hz)
    return 24_000  # documented default for omni speech-out (notes.md §1)


def write_wav(pcm: bytes, rate: int, path: Path) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(rate)
        w.writeframes(pcm)


def main() -> int:
    settings = load_settings()
    if not settings.dashscope_api_key:
        print(
            "DASHSCOPE_API_KEY is not set — nothing to probe.\n"
            "Set it (or MOCK_MODE=always for pipeline dev) and re-run. "
            "Text-only confirmation remains the MVP path regardless (design.md §2)."
        )
        return 2

    print(f"Model:   {settings.model_voice}")
    print(f"Voice:   {settings.probe_voice}")
    print(f"Ask:     {TARGET_SENTENCE_UR}")
    print("-" * 60)

    client = DashScopeClient(settings)
    try:
        resp = client.omni_chat(
            system=SYSTEM_PROMPT,
            user_text=f"Speak this sentence in Urdu: {TARGET_SENTENCE_UR}",
            audio=None,  # text-in → audio-out is the minimal capability probe
            modalities=["text", "audio"],
            voice=settings.probe_voice,
            audio_format="wav",
        )
    except DashScopeError as exc:
        print(f"API ERROR: {exc}")
        print("Verdict: FAIL (no audio). Text-out MVP unchanged.")
        return 1

    print(f"Text replied:  {resp.text[:200] or '(none)'}")
    print(f"Audio chunks:  {len(resp.audio_b64_chunks)}")
    if resp.usage:
        print(f"Usage:         {resp.usage}")

    pcm = resp.pcm
    if not pcm:
        print("\nVerdict: FAIL — model returned no audio frames.")
        print("Urdu speech-out does not work with this configuration. "
              "Keep confirmation text-only (design.md §2) and re-file this result.")
        return 1

    out_dir = ROOT / "probe_output"
    out_dir.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    rate = probe_rate(resp)
    wav_path = out_dir / f"urdu_speech_out_{stamp}.wav"
    write_wav(pcm, rate, wav_path)

    summary = out_dir / f"urdu_speech_out_{stamp}.md"
    summary.write_text(
        f"# Urdu speech-out probe — {stamp}\n\n"
        f"- model: {settings.model_voice}\n- voice: {settings.probe_voice}\n"
        f"- audio: {len(pcm)} bytes PCM @ {rate} Hz → {wav_path.name}\n"
        f"- text: {resp.text[:300]!r}\n\n"
        "## Human check required\n"
        "A team member MUST listen to the WAV and judge: natural Urdu? correct numbers? "
        "respectable pace? Only a YES to all three upgrades voice-out from stretch goal.\n",
        encoding="utf-8",
    )

    dur = len(pcm) / 2 / rate
    print(f"\nAudio saved: {wav_path}  ({len(pcm)} bytes PCM, {rate} Hz, ~{dur:.1f}s)")
    print(f"Summary:     {summary}")
    print(
        "\nVerdict: AUDIO RECEIVED — machine check passed.\n"
        "HUMAN CHECK REQUIRED: listen to the WAV (accent, numbers, pace) before letting "
        "anything depend on Urdu voice output. Until then: text-only confirmation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
