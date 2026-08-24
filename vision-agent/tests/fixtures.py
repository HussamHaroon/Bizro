"""Zero-dependency deterministic PNG generator for test fixtures.

The mock scenarios route on filename (mock_data.scenario_for_path), so tests
just need REAL image files (valid PNG, non-empty, right mime) — the pixels only
need to look plausibly receipt-ish vs photo-ish. Writing PNGs with zlib+struct
keeps the suite dependency-free and keeps binaries out of git.

samples/receipts/ stays EMPTY for real human photographs (HANDOFF.md ③) —
synthetic receipts are explicitly useless for the bake-off (samples/README.md).
"""

from __future__ import annotations

import random
import struct
import zlib
from pathlib import Path

CREAM = (247, 242, 231)
INK = (33, 30, 26)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _png(pixels: list[list[tuple[int, int, int]]]) -> bytes:
    height, width = len(pixels), len(pixels[0])
    raw = b"".join(
        b"\x00" + b"".join(bytes(pixel) for pixel in row) for row in pixels
    )
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            _chunk(b"IDAT", zlib.compress(raw, 6)),
            _chunk(b"IEND", b""),
        ]
    )


def receipt_png(*, blurry: bool = False, seed: int = 7, width: int = 96, height: int = 160) -> bytes:
    """A receipt-looking image: cream paper with ragged dark 'handwriting' rows."""
    rng = random.Random(seed)
    pixels = [[CREAM for _ in range(width)] for _ in range(height)]
    y = 12
    while y < height - 8:
        line_length = rng.randint(width // 3, int(width * 0.85))
        offset = rng.randint(2, max(3, width - line_length - 2))
        thickness = rng.randint(1, 2)
        for dy in range(thickness):
            for x in range(offset, min(offset + line_length, width)):
                if rng.random() > 0.08:  # handwriting gaps
                    pixels[y + dy][x] = INK
        y += rng.randint(6, 10)
    if blurry:
        for _ in range(width * height // 6):
            x, yy = rng.randrange(width), rng.randrange(height)
            smear = rng.randint(1, 4)
            shade = rng.randint(90, 180)
            for dx in range(smear):
                if x + dx < width:
                    pixels[yy][x + dx] = (min(255, CREAM[0] - shade + dx * 8),) * 3
    return _png(pixels)


def photo_png(*, seed: int = 3, width: int = 96, height: int = 96) -> bytes:
    """A non-receipt 'photo': sky gradient with a horizon — no text-like rows."""
    rng = random.Random(seed)
    pixels = []
    for y in range(height):
        t = y / height
        if t < 0.7:  # sky
            row = [(110 + int(60 * t), 160 + int(50 * t), 230)] * width
        else:  # ground
            row = [(90 + rng.randint(-8, 8), 120 + rng.randint(-8, 8), 70)] * width
        pixels.append([pixel for pixel in row])
    return _png(pixels)


def write_fixture(directory: Path, name: str, data: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(data)
    return path


def standard_fixtures(directory: Path) -> dict[str, Path]:
    """The four canonical scenario images, named to route mock_data correctly."""
    return {
        "clean": write_fixture(directory, "receipt_clean.png", receipt_png()),
        "blurry": write_fixture(directory, "receipt_blurry.png", receipt_png(blurry=True, seed=11)),
        "wrong_price": write_fixture(directory, "receipt_wrong_price.png", receipt_png(seed=13)),
        "not_receipt": write_fixture(directory, "photo_not_receipt.png", photo_png()),
    }
