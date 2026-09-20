#!/usr/bin/env python3
"""Derive the waitlist page's og:image from the shipped demo-asset GIF.

Per docs/FUNNEL_MEASUREMENT.md §5 (PR #99) and docs/HOSTED_SIGNUP_WEB_UI.md
§4.1 (H15): og:image reuses the persistence pair from the demo-assets plan —
reuse, don't reshoot. Source of truth is assets/demo-persistence-pair.gif
(asset 3, shipped as PR #137); this script extracts its first frame and
renders it onto a 1200x630 social-card canvas (first-party hosted, no
query-string trackers).

Usage: python3 site/derive_og_image.py
Output: site/og-persistence-pair.png (overwritten)
Requires: Pillow (pip install pillow)
"""

import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "assets" / "demo-persistence-pair.gif"
DST = REPO / "site" / "assets" / "og-persistence-pair.png"

CANVAS = (1200, 630)
BG = (13, 17, 23)  # near-black, matches the terminal-frame aesthetic


def main() -> int:
    if not SRC.exists():
        print(f"missing source: {SRC}", file=sys.stderr)
        return 1
    im = Image.open(SRC)
    im.seek(0)  # first frame: the Xvfb birth record (pid/etime/lstart)
    frame = im.convert("RGB")
    scale = CANVAS[0] / frame.width
    frame = frame.resize((CANVAS[0], round(frame.height * scale)), Image.LANCZOS)
    card = Image.new("RGB", CANVAS, BG)
    card.paste(frame, (0, (CANVAS[1] - frame.height) // 2))
    card.save(DST, "PNG")
    print(f"wrote {DST} ({CANVAS[0]}x{CANVAS[1]}) from {SRC.name} frame 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
