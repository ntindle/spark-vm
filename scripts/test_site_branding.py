"""Brand-logo asset + wiring tests (issue #852).

The logo ships as one SVG source plus PIL-derived PNG exports, generated
by site/derive_logo.py from a single set of geometry constants. These tests
pin the acceptance criteria: the assets exist with the right dimensions,
the SVG is well-formed with the expected structure, both site pages wire
the mark and favicon in, and the generator is deterministic (re-running it
reproduces the committed bytes exactly).
"""

import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "site" / "assets"
SITE_PAGES = [REPO / "site" / "index.html", REPO / "site" / "waitlist.html"]

EXPECTED_PNGS = {
    "logo-512.png": (512, 512),
    "logo-180.png": (180, 180),
    "favicon-32.png": (32, 32),
}


def _read_png_size(path):
    with open(path, "rb") as f:
        head = f.read(32)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", "bad PNG signature: %s" % path
    return struct.unpack(">II", head[16:24])


def test_svg_source_exists_and_parses():
    svg_path = ASSETS / "logo.svg"
    assert svg_path.is_file(), "logo.svg source missing"
    root = ET.fromstring(svg_path.read_text(encoding="utf-8"))
    assert root.tag.endswith("svg"), "root element is not <svg>"
    assert root.get("viewBox") == "0 0 64 64", "viewBox must be the 64-grid"
    tags = {el.tag.split("}")[-1] for el in root.iter()}
    assert "polygon" in tags, "spark star polygon missing"
    assert "rect" in tags, "badge/cursor rects missing"


def test_png_exports_exist_with_expected_dimensions():
    for name, (w, h) in EXPECTED_PNGS.items():
        path = ASSETS / name
        assert path.is_file(), "%s missing" % name
        assert _read_png_size(path) == (w, h), "%s wrong size" % name


def test_site_pages_wire_logo_and_favicon():
    for page in SITE_PAGES:
        html = page.read_text(encoding="utf-8")
        assert 'href="/assets/favicon-32.png"' in html, \
            "%s: favicon link missing" % page.name
        assert 'src="/assets/logo.svg"' in html, \
            "%s: logo mark missing from header" % page.name
        assert 'class="brandbar"' in html, \
            "%s: brand bar missing" % page.name
        assert 'alt="spark-vm logo"' in html, \
            "%s: logo alt text missing" % page.name


def test_generator_is_deterministic():
    before = {p.name: (ASSETS / p.name).read_bytes()
              for p in [ASSETS / "logo.svg", *[ASSETS / n for n in EXPECTED_PNGS]]}
    subprocess.run([sys.executable, "site/derive_logo.py"],
                   cwd=REPO, check=True, capture_output=True)
    for name, old in before.items():
        assert (ASSETS / name).read_bytes() == old, \
            "%s not deterministic: re-run changed the bytes" % name
