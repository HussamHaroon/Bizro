"""EXIF provenance extraction — the camera's timestamp vs the merchant's claim."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vision_agent.exif import extract_exif


def _jpeg_with_exif(tmp_path, captured: datetime) -> Path:
    from PIL import Image

    p = tmp_path / "receipt.jpg"
    im = Image.new("RGB", (60, 40), "white")
    exif = im.getexif()
    exif[0x0132] = captured.strftime("%Y:%m:%d %H:%M:%S")       # DateTime
    exif[0x0110] = "TestCam 1"                                   # Model
    im.save(p, format="JPEG", exif=exif.tobytes())
    return p


def test_exif_present_and_parsed(tmp_path):
    shot = datetime(2026, 10, 21, 18, 30, 0)
    out = extract_exif(_jpeg_with_exif(tmp_path, shot))
    assert out["exif_present"] is True
    assert out["captured_at"] == shot.isoformat()
    assert out["camera"] == "TestCam 1"


def test_exif_absent_reported_honestly(tmp_path):
    from PIL import Image

    p = tmp_path / "plain.jpg"
    Image.new("RGB", (60, 40), "white").save(p, format="JPEG")  # no EXIF
    out = extract_exif(p)
    assert out["exif_present"] is False
    assert out["captured_at"] is None


def test_non_image_never_raises(tmp_path):
    p = tmp_path / "garbage.jpg"
    p.write_bytes(b"not an image at all")
    out = extract_exif(p)
    assert out["exif_present"] is False
