"""EXIF provenance forensics for receipt photos.

A photographed piece of paper carries camera truth the merchant doesn't
control (unless they strip it — and stripping ITSELF is a signal when the
merchant's other photos have it): capture timestamp, camera model, flash.

All functions best-effort: missing/unreadable EXIF returns a None-field dict,
never raises. Comparison against the CLAIMED date happens credit-side
(forensics.py); here we only extract honestly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def extract_exif(image_path: str | Path) -> dict[str, Any]:
    """Best-effort EXIF provenance for one photo.

    Returns: {"exif_present": bool, "captured_at": iso|None, "camera": str|None}
    Non-JPEG or EXIF-less images → exif_present=False (a real signal credit-side).
    """
    out: dict[str, Any] = {"exif_present": False, "captured_at": None, "camera": None}
    try:
        from PIL import Image, ExifTags  # lazy: pillow already a runtime dep
    except ImportError:  # pragma: no cover — pillow is required in practice
        return out

    try:
        with Image.open(image_path) as im:
            exif = im.getexif()
    except Exception:
        return out
    if not exif:
        return out

    out["exif_present"] = True
    tag_map = {ExifTags.TAGS.get(k): k for k in exif}
    model = exif.get(tag_map.get("Model"))
    if model:
        out["camera"] = str(model).strip()

    dt = exif.get(tag_map.get("DateTimeOriginal")) or exif.get(tag_map.get("DateTime"))
    if dt:
        try:
            out["captured_at"] = datetime.strptime(str(dt).strip(), "%Y:%m:%d %H:%M:%S").isoformat()
        except ValueError:
            out["captured_at"] = None
    return out
