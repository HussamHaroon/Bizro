"""Re-clean the Bizro wordmark: remove the cream background EVERYWHERE.

The original extraction was an edge-connected flood fill, so the letter
counters (the holes in B, R, O) survived as opaque cream and every
anti-aliased edge kept a cream fringe. Both are invisible on the cream
card background and glaring on the ink footer / green invoice band.

Fix: un-mix each pixel against the cream background. Every pixel is
modelled as  c = a*ink + (1-a)*bg  over the two flat inks the logo actually
uses (green, gold). Solving for a per ink and keeping the better fit gives
an exact alpha AND a fringe-free colour, because the stored RGB is replaced
by the pure ink. JPEG noise in the flat fills collapses to the ink colour,
which is what the vector original looks like. Pixels that fit neither ink
(a residual above SAFETY) are left byte-identical, so nothing unexpected
can be mangled.

Outputs (overwrite in place):
  wordmark.png            cleaned master
  wordmark-96/48/32.png   LANCZOS downscales of the cleaned master
  wordmark-cream-96/48.png  same alpha, ink recoloured to cream
Run from the repo root:  python assets/brand/clean_wordmark.py
"""

import pathlib
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent

BG = (249.0, 243.0, 230.0)          # cream background, measured from the asset
INKS = [(11.0, 92.0, 60.0),         # green, measured dominant fill
        (212.0, 145.0, 30.0)]       # gold bars, measured dominant fill
CREAM_INK = (247, 242, 231)         # ink colour of the existing cream variant
MIN_ALPHA = 0.03                    # below this a pixel is background
SAFETY = 45.0                       # max residual (0-255 space) before we bail


def unmix(c):
    """Return (rgb, alpha) for a composited-over-BG colour c, or None to keep."""
    d = [c[i] - BG[i] for i in range(3)]
    best = None
    for ink in INKS:
        u = [ink[i] - BG[i] for i in range(3)]
        uu = sum(x * x for x in u)
        a = sum(d[i] * u[i] for i in range(3)) / uu
        a = min(1.0, max(0.0, a))
        resid = sum((d[i] - a * u[i]) ** 2 for i in range(3)) ** 0.5
        if best is None or resid < best[0]:
            best = (resid, a, ink)
    resid, a, ink = best
    if resid > SAFETY:
        return None
    if a < MIN_ALPHA:
        return (0, 0, 0), 0
    return (round(ink[0]), round(ink[1]), round(ink[2])), round(a * 255)


def clean(src: Image.Image) -> Image.Image:
    im = src.convert("RGBA")
    px = im.load()
    kept = 0
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            out = unmix((r, g, b))
            if out is None:
                kept += 1
                continue
            (nr, ng, nb), na = out
            px[x, y] = (nr, ng, nb, na)
    print(f"  {im.width}x{im.height}: {kept} pixel(s) kept verbatim (no ink fit)")
    return im


def downscale(im: Image.Image, height: int) -> Image.Image:
    w = round(im.width * height / im.height)
    return im.resize((w, height), Image.LANCZOS)


def recolour(im: Image.Image, rgb) -> Image.Image:
    out = im.copy()
    px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            _, _, _, a = px[x, y]
            px[x, y] = (rgb[0], rgb[1], rgb[2], a)
    return out


def main():
    master = clean(Image.open(HERE / "wordmark.png"))
    master.save(HERE / "wordmark.png")

    for h in (96, 48, 32):
        downscale(master, h).save(HERE / f"wordmark-{h}.png")
    for h in (96, 48):
        recolour(downscale(master, h), CREAM_INK).save(HERE / f"wordmark-cream-{h}.png")

    # the two apps ship byte-copies of the served sizes; keep them in sync
    repo = HERE.parents[1]
    for h in (96, 48, 32):
        blob = (HERE / f"wordmark-{h}.png").read_bytes()
        for dest in (repo / "site" / "public" / "brand", repo / "dashboard" / "public" / "brand"):
            (dest / f"wordmark-{h}.png").write_bytes(blob)
    print("synced site/public/brand + dashboard/public/brand")


if __name__ == "__main__":
    main()
