#!/usr/bin/env python3
"""Derive the spark-vm brand logo from one set of geometry constants.

Acceptance (issue #852): SVG source plus raster exports (at least 512px
and 180px), readable at the 32px favicon size, wired into the site header.

The SVG and the PNGs are generated from the SAME constants below, so the
vector source and the rasters cannot drift apart. PIL-only — no SVG
rasterizer is needed in CI. Deterministic: identical constants produce
byte-identical files (PIL's PNG encoder writes no timestamps).

Design: a dark terminal-badge (the site's near-black hero tone) carrying a
gold four-point spark (the name) and a blue terminal cursor bar (the
product: a computer your agent types into). No text in the artwork — the
wordmark is HTML next to the mark, so the 32px favicon stays legible.

Usage: python3 site/derive_logo.py   (run from the repo root)
"""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "site" / "assets"

GRID = 64  # the SVG viewBox grid; every coordinate below is in grid units

BADGE = {
    "x0": 4, "y0": 4, "x1": 60, "y1": 60, "r": 14,
    "fill": (13, 19, 25),      # --hero near-black
    "stroke": (43, 53, 66), "sw": 2,
}
STAR = {
    "cx": 32, "cy": 28, "r_outer": 15, "r_inner": 6.2,
    "grad_top": (255, 224, 138), "grad_bottom": (245, 165, 36),
}
CURSOR = {
    "x0": 37, "y0": 45, "x1": 49, "y1": 49, "r": 2,
    "fill": (31, 111, 235),    # --accent
}

MASTER_PX = 512
EXPORTS = {  # name -> pixel size (master is resized with LANCZOS)
    "logo-512.png": 512,
    "logo-180.png": 180,
    "favicon-32.png": 32,
}


def star_points():
    """Four-point spark star polygon in grid coordinates."""
    pts = []
    for k in range(8):
        r = STAR["r_outer"] if k % 2 == 0 else STAR["r_inner"]
        a = math.radians(-90 + k * 45)
        pts.append((STAR["cx"] + r * math.cos(a),
                    STAR["cy"] + r * math.sin(a)))
    return pts


def _rgb(t):
    return "#%02x%02x%02x" % t


def build_svg():
    pts = " ".join("%.2f,%.2f" % p for p in star_points())
    b, s, c = BADGE, STAR, CURSOR
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img"'
        ' aria-label="spark-vm logo">\n'
        '  <defs>\n'
        '    <linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">\n'
        '      <stop offset="0" stop-color="%s"/>\n'
        '      <stop offset="1" stop-color="%s"/>\n'
        '    </linearGradient>\n'
        '  </defs>\n'
        '  <rect x="%d" y="%d" width="%d" height="%d" rx="%d"'
        ' fill="%s" stroke="%s" stroke-width="%d"/>\n'
        '  <polygon points="%s" fill="url(#spark)"/>\n'
        '  <rect x="%d" y="%d" width="%d" height="%d" rx="%d"'
        ' fill="%s"/>\n'
        '</svg>\n' % (
            _rgb(s["grad_top"]), _rgb(s["grad_bottom"]),
            b["x0"], b["y0"], b["x1"] - b["x0"], b["y1"] - b["y0"], b["r"],
            _rgb(b["fill"]), _rgb(b["stroke"]), b["sw"],
            pts,
            c["x0"], c["y0"], c["x1"] - c["x0"], c["y1"] - c["y0"], c["r"],
            _rgb(c["fill"]),
        )
    )


def render_master():
    """Render the 512px master with PIL from the same constants."""
    sc = MASTER_PX / GRID

    def S(v):
        return v * sc

    img = Image.new("RGBA", (MASTER_PX, MASTER_PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    b = BADGE
    d.rounded_rectangle([S(b["x0"]), S(b["y0"]), S(b["x1"]), S(b["y1"])],
                        radius=S(b["r"]), fill=b["fill"] + (255,),
                        outline=b["stroke"] + (255,), width=max(1, round(S(b["sw"]))))

    # Gold vertical gradient clipped to the star polygon.
    top = STAR["grad_top"] + (255,)
    bot = STAR["grad_bottom"] + (255,)
    y_lo, y_hi = S(STAR["cy"] - STAR["r_outer"]), S(STAR["cy"] + STAR["r_outer"])
    grad = Image.new("RGBA", (MASTER_PX, MASTER_PX), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    span = max(1, y_hi - y_lo)
    for y in range(int(y_lo), int(y_hi) + 1):
        t = (y - y_lo) / span
        gd.line([(0, y), (MASTER_PX, y)],
                fill=tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(4)))
    mask = Image.new("L", (MASTER_PX, MASTER_PX), 0)
    ImageDraw.Draw(mask).polygon([(S(x), S(y)) for x, y in star_points()], fill=255)
    img = Image.composite(grad, img, mask)

    c = CURSOR
    ImageDraw.Draw(img).rounded_rectangle(
        [S(c["x0"]), S(c["y0"]), S(c["x1"]), S(c["y1"])],
        radius=S(c["r"]), fill=c["fill"] + (255,))
    return img.convert("RGB")


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    svg = build_svg()
    # The SVG must parse — a malformed source file is worse than none.
    ET.fromstring(svg)
    (ASSETS / "logo.svg").write_text(svg, encoding="utf-8")

    master = render_master()
    for name, px in EXPORTS.items():
        out = master.resize((px, px), Image.LANCZOS) if px != MASTER_PX else master
        out.save(ASSETS / name)
        print("wrote site/assets/%s (%dx%d)" % (name, px, px))


if __name__ == "__main__":
    main()
