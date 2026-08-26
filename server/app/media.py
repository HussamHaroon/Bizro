"""Media blob storage — the raw audit trail (SKILL.md hard rule).

Bytes are stored under media/ (gitignored), sha256-hashed, never deleted.
Layout: media/<yyyy>/<mm>/<uuid>.<ext> — flat enough to browse, dated for volume.

SEC (bizro-security): inbound media is size-capped (16MB audio / 5MB image) and
magic-byte sniffed before anything is written — recognized-but-wrong content
(an Ogg page labeled as a photo, a PE/ELF executable) is rejected. Unrecognized
magic is allowed through with a warning so the local simulator's synthetic
fixtures keep working; real Graph-API downloads are well-formed by Meta.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings

logger = logging.getLogger("bizro.media")

_EXT_BY_MIME = {
    "audio/ogg": ".ogg",
    "audio/ogg; codecs=opus": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# bizro-security caps: 16MB audio / 5MB image.
MAX_BYTES = {
    "voice": 16 * 1024 * 1024,
    "image": 5 * 1024 * 1024,
}

# magic prefix -> sniffed media category. Only sniff what we actually accept
# plus the unambiguous "never this" magics (executables).
_MAGIC: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"OggS", "audio/ogg"),
    (b"MZ", "application/x-dos-executable"),
    (b"\x7fELF", "application/x-elf-executable"),
]

_ALLOWED_BY_KIND = {
    "voice": {"audio/ogg"},
    "image": {"image/jpeg", "image/png"},
}


class MediaValidationError(ValueError):
    """Inbound media failed the size cap or magic-byte sniff (SEC)."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sniff_media_type(data: bytes) -> str | None:
    """Best-effort content type from magic bytes; None when unrecognized."""
    for magic, media_type in _MAGIC:
        if data.startswith(magic):
            return media_type
    return None


def validate_media(data: bytes, kind: str) -> None:
    """Raise MediaValidationError when bytes can't be this kind of media.

    - size cap per kind (16MB voice / 5MB image)
    - recognized magic of a type that can never be valid for the declared kind
      (executable, or audio-bytes-on-an-image-message) → reject
    - unrecognized magic → allow, with a warning (simulator fixtures are
      synthetic; we don't reject what we can't identify)
    """
    if kind not in _ALLOWED_BY_KIND:
        raise MediaValidationError(f"unknown media kind {kind!r}")
    cap = MAX_BYTES[kind]
    if len(data) > cap:
        raise MediaValidationError(
            f"{kind} media is {len(data)} bytes, over the {cap}-byte cap"
        )
    sniffed = sniff_media_type(data)
    if sniffed is None:
        logger.warning(
            "Inbound %s media has no known magic prefix (%d bytes) — accepted with caution",
            kind,
            len(data),
        )
        return
    if sniffed not in _ALLOWED_BY_KIND[kind]:
        raise MediaValidationError(
            f"{kind} media rejected: magic bytes identify it as {sniffed}"
        )


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
