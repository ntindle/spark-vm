#!/usr/bin/env python3
"""Derive the waitlist page's og:image from the shipped demo asset.

docs/FUNNEL_MEASUREMENT.md §5 + docs/HOSTED_SIGNUP_WEB_UI.md §4.1 require
the social image at /assets/og-persistence-pair.png to be REUSED from
assets/demo-persistence-pair.gif (the shipped persistence pair, asset 3 of
PR #137) — "reuse, don't reshoot."

This script composes the actual pair: both GIF frames (the Xvfb birth
record, then the same desktop 4 days later) on a 1200×630 social-card
canvas with a legible headline and the spark-vm wordmark. The macOS
window-chrome title bar is cropped off each frame (it duplicates the card
headline); everything visible below it is the shipped frame, untouched.

Deterministic: same source GIF -> byte-identical PNG. Requires Pillow.
Usage: python3 site/derive_og_image.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "assets" / "demo-persistence-pair.gif"
DST = REPO / "site" / "assets" / "og-persistence-pair.png"

W, H = 1200, 630
BG = (16, 20, 24)        # page hero band, near-black
INK = (244, 246, 248)    # near-white
ORANGE = (232, 163, 61)  # matches the pair's own caption color
MUTED = (174, 182, 194)

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def font(name, size):
    return ImageFont.truetype(str(FONT_DIR / name), size)


def main():
    if not SRC.exists():
        sys.exit(f"missing source GIF: {SRC} (PR #137 asset 3)")

    with Image.open(SRC) as gif:
        frames = []
        for i in range(gif.n_frames):
            gif.seek(i)
            frames.append(gif.convert("RGB"))
    if len(frames) < 2:
        sys.exit(f"{SRC} has {len(frames)} frame(s); the pair needs 2")

    card = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(card)

    # Headline.
    head = font("DejaVuSans-Bold.ttf", 54)
    text = "The same desktop, days apart"
    tw = d.textlength(text, font=head)
    d.text(((W - tw) / 2, 34), text, font=head, fill=INK)

    # The pair: crop each frame's title bar (46px, duplicated chrome),
    # keep everything below untouched, scale to 560 wide.
    label_font = font("DejaVuSans.ttf", 26)
    labels = ["1/2 \u2014 then", "2/2 \u2014 now, 4 days later"]
    panel_y = 140
    for i, (frame, label) in enumerate(zip(frames[:2], labels)):
        cropped = frame.crop((0, 46, frame.width, frame.height))
        scale = 560 / cropped.width
        panel = cropped.resize(
            (560, round(cropped.height * scale)), Image.LANCZOS)
        x = 24 + i * (560 + 32)
        d.text((x, 100), label, font=label_font, fill=ORANGE)
        card.paste(panel, (x, panel_y))

    # Wordmark + one-liner, bottom band.
    word = font("DejaVuSans-Bold.ttf", 44)
    wtext = "spark-vm"
    ww = d.textlength(wtext, font=word)
    d.text(((W - ww) / 2, 412), wtext, font=word, fill=INK)
    sub = font("DejaVuSans.ttf", 30)
    stext = "A real computer that stays yours."
    sw = d.textlength(stext, font=sub)
    d.text(((W - sw) / 2, 478), stext, font=sub, fill=MUTED)

    DST.parent.mkdir(parents=True, exist_ok=True)
    card.save(DST)
    print(f"wrote {DST} ({W}x{H}) from {SRC.name} frames 0+1")


if __name__ == "__main__":
    main()
