"""Generate the three DEMO receipt images in samples/demo/ (Pillow).

These are REHEARSAL props for demo beat 2 ("photo in -> price-error flag out")
and are explicitly NOT bake-off material: synthetic receipts are useless for the
Qwen-VL-OCR vs Qwen3.5-OCR bake-off (samples/README.md, PROJECT_PLAN.md Day 0),
which still needs REAL phone-camera photos in samples/receipts/.

Every image carries an unmistakable DEMO watermark: a solid band top and bottom
plus a large translucent diagonal "DEMO" across the content. The watermark is
drawn AFTER any blur so it stays crisp even on receipt_blurry.png.

Item math mirrors mock_data.py scenarios exactly, so the offline mock run and a
real-OCR run of vision-agent/scripts/demo_vision.py see the same ledger:
  clean       chai patti 2x350 + cheeni 5x180 + dal masoor 3x320 = 2,560 PKR
  wrong_price chai patti at 3,500 (10x history median 350)      = 8,860 PKR
  blurry      same as clean, progressively blurred (top item least)

Usage (root venv):
  .venv/Scripts/python vision-agent/scripts/make_demo_receipts.py
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WORKTREE_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = WORKTREE_ROOT / "samples" / "demo"

WIDTH, HEIGHT = 800, 1000
PAPER = (249, 244, 233)  # warm cream receipt paper
INK = (40, 36, 30)  # ball-pen dark ink
BAND_BG = (17, 17, 17)  # watermark band background
BAND_FG = (255, 255, 255)
WATERMARK_FG = (200, 60, 40)  # translucent diagonal DEMO

# Deterministic output: same pixels every run (auditable, diff-friendly).
rng = random.Random(20260829)

ITEMS_CLEAN = [
    ("chai patti", "2 packet x 350", "700"),
    ("cheeni", "5 kg x 180", "900"),
    ("dal masoor", "3 kg x 320", "960"),
]
TOTAL_CLEAN = "2560"

ITEMS_WRONG = [
    ("chai patti", "2 packet x 3500", "7000"),
    ("cheeni", "5 kg x 180", "900"),
    ("dal masoor", "3 kg x 320", "960"),
]
TOTAL_WRONG = "8860"


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Handwriting-ish font if the host has one; graceful fallback otherwise."""
    for name in ("comic.ttf", "comicbd.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def draw_wavy(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill=INK) -> None:
    """Handwritten-ish text: per-character x-advance with a wavy baseline and
    slight jitter. Looks pen-written without needing a real handwriting font."""
    x, y = xy
    phase = rng.uniform(0, 6.28)
    for i, ch in enumerate(text):
        dy = 3 * ((i * 0.55 + phase) % 6.28) / 6.28 - 1.5  # gentle sine wave
        dy += rng.uniform(-1.2, 1.2)  # hand tremor
        draw.text((x, y + dy), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + rng.uniform(-0.4, 0.9)


def paper() -> Image.Image:
    """Cream paper with subtle speckle + slightly ragged edges."""
    img = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    px = img.load()
    for _ in range(2600):  # paper grain
        x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
        shade = rng.randint(-10, 8)
        r, g, b = px[x, y]
        px[x, y] = (
            max(0, min(255, r + shade)),
            max(0, min(255, g + shade)),
            max(0, min(255, b + shade)),
        )
    return img


def ragged_rule(draw: ImageDraw.ImageDraw, y: int) -> None:
    """A hand-drawn-looking horizontal rule (slightly wobbly)."""
    points = [(x, y + rng.uniform(-1.5, 1.5)) for x in range(80, WIDTH - 80, 24)]
    draw.line(points, fill=INK, width=2)


def draw_receipt(items, total: str) -> Image.Image:
    """The shared receipt body (shop header, item lines, grand total)."""
    img = paper()
    draw = ImageDraw.Draw(img)
    f_head = load_font(40)
    f_sub = load_font(24)
    f_item = load_font(30)
    f_total = load_font(36)

    draw_wavy(draw, (150, 110), "Al-Madina Kiryana Store", f_head)
    draw_wavy(draw, (250, 170), "karyana receipt", f_sub)
    ragged_rule(draw, 225)

    y = 260
    for name, qty_price, line_total in items:
        draw_wavy(draw, (90, y), name, f_item)
        draw_wavy(draw, (90, y + 44), qty_price, f_sub)
        draw_wavy(draw, (WIDTH - 200, y + 12), line_total, f_item)
        y += 118
    ragged_rule(draw, y)
    draw_wavy(draw, (90, y + 36), "TOTAL  PKR", f_total)
    draw_wavy(draw, (WIDTH - 230, y + 36), total, f_total)
    return img


def apply_progressive_blur(img: Image.Image) -> Image.Image:
    """Mimic a shaky low-light shot: the first item stays near-readable, the
    rest of the receipt smears out (mock scenario 'blurry': partial read)."""
    top = img.crop((0, 0, WIDTH, 320)).filter(ImageFilter.GaussianBlur(1.8))
    middle = img.crop((0, 320, WIDTH, 700)).filter(ImageFilter.GaussianBlur(5.5))
    bottom = img.crop((0, 700, WIDTH, HEIGHT)).filter(ImageFilter.GaussianBlur(8.5))
    out = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    out.paste(top, (0, 0))
    out.paste(middle, (0, 320))
    out.paste(bottom, (0, 700))
    return out


def stamp_demo_watermark(img: Image.Image) -> Image.Image:
    """Unmistakable DEMO marking: solid bands top+bottom + diagonal overlay.
    Always applied LAST so blur never softens the marking."""
    draw = ImageDraw.Draw(img)
    f_band = load_font(30)
    f_small = load_font(22)

    draw.rectangle((0, 0, WIDTH, 64), fill=BAND_BG)
    band = "DEMO - SYNTHETIC IMAGE - NOT A REAL RECEIPT"
    w = draw.textlength(band, font=f_band)
    draw.text(((WIDTH - w) / 2, 16), band, font=f_band, fill=BAND_FG)

    draw.rectangle((0, HEIGHT - 48, WIDTH, HEIGHT), fill=BAND_BG)
    foot = "demo rehearsal prop only - NOT for the OCR bake-off (see samples/README.md)"
    w = draw.textlength(foot, font=f_small)
    draw.text(((WIDTH - w) / 2, HEIGHT - 38), foot, font=f_small, fill=BAND_FG)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    f_wm = load_font(230)
    wm = "DEMO"
    w = odraw.textlength(wm, font=f_wm)
    odraw.text(((WIDTH - w) / 2 - 90, 330), wm, font=f_wm, fill=WATERMARK_FG + (70,))
    odraw.text(((WIDTH - w) / 2 + 40, 620), wm, font=f_wm, fill=WATERMARK_FG + (70,))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "receipt_clean.png": draw_receipt(ITEMS_CLEAN, TOTAL_CLEAN),
        "receipt_wrong_price.png": draw_receipt(ITEMS_WRONG, TOTAL_WRONG),
        "receipt_blurry.png": apply_progressive_blur(draw_receipt(ITEMS_CLEAN, TOTAL_CLEAN)),
    }
    for name, img in outputs.items():
        stamped = stamp_demo_watermark(img)
        path = OUT_DIR / name
        stamped.save(path, "PNG")
        print(f"wrote {path} ({stamped.size[0]}x{stamped.size[1]}, {path.stat().st_size // 1024} KB)")
    print("all images carry the DEMO band + diagonal watermark; bake-off still needs real photos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
