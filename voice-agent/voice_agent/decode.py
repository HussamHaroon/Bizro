"""Swappable WhatsApp audio decode step.

WhatsApp voice notes arrive as `audio/ogg; codecs=opus`. The Qwen-Omni docs list
input formats "AMR、WAV、3GP、3GPP、AAC、MP3 等主流格式" — ogg/opus is not explicitly
named (voice-agent/notes.md §1), so the default strategy decodes to 16 kHz mono WAV
via the ffmpeg binary bundled with imageio-ffmpeg (pip-only, no system ffmpeg).

Strategies (env `AUDIO_DECODE`):
- `ffmpeg` — subprocess to imageio-ffmpeg's bundled binary (default)
- `pyav`   — in-process PyAV decode (av wheel, no subprocess)
- `raw`    — pass original bytes through untouched, for if/when live API testing
             confirms the endpoint accepts ogg/opus directly
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

TARGET_RATE = 16_000  # plenty for ASR; keeps base64 payload small (<10MB doc limit)


class DecodeError(RuntimeError):
    """Raised when audio cannot be decoded. Pipeline catches this → low_confidence."""


@dataclass
class DecodedAudio:
    data: bytes
    mime_type: str = "audio/wav"       # what we will TELL the API we're sending
    api_format: str = "wav"            # input_audio.format value
    strategy: str = "ffmpeg"

    @property
    def data_uri(self) -> str:
        import base64

        return "data:;base64," + base64.b64encode(self.data).decode("ascii")


def looks_like_ogg(data: bytes) -> bool:
    return data[:4] == b"OggS"


def needs_decode(data: bytes) -> bool:
    """Only ogg/opus (WhatsApp voice) forces a decode; wav/mp3 pass through."""
    return looks_like_ogg(data)


def decode_audio(data: bytes, strategy: str = "ffmpeg") -> DecodedAudio:
    """Dispatch to the configured strategy. Raises DecodeError on failure."""
    if not data:
        raise DecodeError("empty audio payload")

    if not needs_decode(data):
        # Already a doc-listed container — send as-is, labelled by magic bytes.
        if data[:4] == b"RIFF":
            return DecodedAudio(data, "audio/wav", "wav", strategy="passthrough")
        if data[:3] == b"ID3" or data[:2] == b"\xff\xfb" or data[:2] == b"\xff\xf3":
            return DecodedAudio(data, "audio/mpeg", "mp3", strategy="passthrough")
        # Unknown container but not Ogg — try the configured decoder anyway; it is the
        # cheapest way to learn whether the bytes are audio at all.

    if strategy == "raw":
        if needs_decode(data):
            raise DecodeError(
                "AUDIO_DECODE=raw but payload is ogg/opus, which is not a doc-listed "
                "input format (voice-agent/notes.md §1)"
            )
        return DecodedAudio(data, "application/octet-stream", "wav", strategy="raw")

    if strategy == "pyav":
        return _decode_pyav(data)
    return _decode_ffmpeg(data)


# ---------------------------------------------------------------------------
# Strategy: imageio-ffmpeg subprocess
# ---------------------------------------------------------------------------


def _ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # not installed / no binary on this platform
        raise DecodeError(f"imageio-ffmpeg unavailable: {exc}") from exc


def _decode_ffmpeg(data: bytes) -> DecodedAudio:
    import tempfile
    from pathlib import Path

    exe = _ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix="bizro_decode_") as tmp:
        tmp_path = Path(tmp)
        src = tmp_path / "in.bin"
        dst = tmp_path / "out.wav"
        src.write_bytes(data)
        cmd = [
            exe, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-i", str(src),
            "-vn", "-ac", "1", "-ar", str(TARGET_RATE), "-c:a", "pcm_s16le",
            "-f", "wav", str(dst),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DecodeError(f"ffmpeg subprocess failed: {exc}") from exc
        if proc.returncode != 0 or not dst.is_file() or dst.stat().st_size < 44:
            detail = proc.stderr.decode("utf-8", "replace")[:300]
            raise DecodeError(f"ffmpeg could not decode audio: {detail}")
        return DecodedAudio(dst.read_bytes(), "audio/wav", "wav", strategy="ffmpeg")


# ---------------------------------------------------------------------------
# Strategy: PyAV (in-process)
# ---------------------------------------------------------------------------


def _decode_pyav(data: bytes) -> DecodedAudio:
    try:
        import av  # lazy — optional dependency
        import io
    except ImportError as exc:
        raise DecodeError(f"PyAV unavailable: {exc}") from exc

    try:
        container = av.open(io.BytesIO(data))
        resampler = av.AudioResampler(format="s16", layout="mono", rate=TARGET_RATE)
        chunks: list[bytes] = []
        for frame in container.decode(audio=0):
            for resized in resampler.resample(frame):
                chunks.append(bytes(resized.planes[0]))
        pcm = b"".join(chunks)
        if not pcm:
            raise DecodeError("PyAV produced no audio frames")
        wav = _wav_header(len(pcm), TARGET_RATE) + pcm
        return DecodedAudio(wav, "audio/wav", "wav", strategy="pyav")
    except av.error.InvalidDataError as exc:
        raise DecodeError(f"PyAV: invalid audio data: {exc}") from exc
    except Exception as exc:  # av raises many subclasses; all mean "cannot decode"
        if isinstance(exc, DecodeError):
            raise
        raise DecodeError(f"PyAV decode failed: {exc}") from exc


def _wav_header(pcm_len: int, rate: int, channels: int = 1, bits: int = 16) -> bytes:
    import struct

    byte_rate = rate * channels * bits // 8
    block_align = channels * bits // 8
    return (
        b"RIFF" + struct.pack("<I", 36 + pcm_len) + b"WAVE"
        b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, rate, byte_rate, block_align, bits)
        + b"data" + struct.pack("<I", pcm_len)
    )
