"""Media blob storage — the raw audit trail (SKILL.md hard rule).

Bytes are stored under media/ (gitignored), sha256-hashed, never deleted.
Layout: media/<yyyy>/<mm>/<uuid>.<ext> — flat enough to browse, dated for volume.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings

_EXT_BY_MIME = {
    "audio/ogg": ".ogg",
    "audio/ogg; codecs=opus": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_blob(data: bytes, mime_type: str, kind: str) -> tuple[Path, str]:
    """Write bytes to the media tree. Returns (storage_path, sha256).

    `kind` is 'voice' or 'image' (media_blobs.kind CHECK constraint).
    """
    if kind not in ("voice", "image"):
        raise ValueError(f"kind must be 'voice' or 'image', got {kind!r}")

    media_root = get_settings().media_dir
    now = datetime.now(timezone.utc)
    ext = _EXT_BY_MIME.get(mime_type.split(";")[0].strip(), ".bin")
    subdir = media_root / f"{now:%Y}" / f"{now:%m}"
    subdir.mkdir(parents=True, exist_ok=True)

    path = subdir / f"{uuid.uuid4()}{ext}"
    path.write_bytes(data)
    return path, sha256_bytes(data)
