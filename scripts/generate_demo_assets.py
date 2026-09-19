#!/usr/bin/env python3
"""Capture the confirmd approval-loop demo frames and assemble the GIF.

Usage (on a machine with Playwright + Chromium, e.g. spark-vm):
    python3 scripts/generate_demo_assets.py \
        --url https://127.0.0.1:18923 --out assets/demo-approval-loop.gif

Expects a running confirmd with at least one pending approval (see
assets/demo_confirmd.py for the demo instance; file one with
confirm/confirm-request). Only ever point this at a DEMO instance —
never the live deployment.
"""
import argparse
import os
import sys

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright is required (pip install playwright; playwright install chromium)")

try:
    from PIL import Image
except ImportError:
    sys.exit("pillow is required (pip install pillow)")


# (frame name, seconds to hold in the GIF)
# Design review: give time to information, not whitespace — the dense
# detail frame holds longest, the empty "cleared" frame shortest.
FRAME_HOLDS = {
    "01-pending": 1.8,
    "02-detail": 2.2,
    "03-armed": 1.6,
    "04-answered": 1.2,
}


def _hide_push_artifact(page):
    # Demo staging: the headless camera cannot register a service
    # worker, so the push-status UI always shows a "push unavailable"
    # camera artifact here. Hide it in the frames (documented in
    # assets/README.md); the frames are about the approval loop.
    # Re-applied after every navigation (fresh DOM each time).
    # NOTE: use a uniquely-named variable — the page's own inline script
    # declares a global `var b` for the approve button and its click
    # handler closes over that global; reassigning `b` here would repoint
    # the handler at the push button and break the two-tap arm.
    page.evaluate(
        "var demoPushBtn=document.getElementById('pushBtn');"
        "if(demoPushBtn&&demoPushBtn.parentElement)"
        "demoPushBtn.parentElement.style.display='none';")


def capture(url, frames_dir):
    os.makedirs(frames_dir, exist_ok=True)
    shots = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            ctx = browser.new_context(
                viewport={"width": 390, "height": 844},
                device_scale_factor=2,
                is_mobile=True,
                ignore_https_errors=True,
            )
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle")
            # Wait for the pending card the demo approval filed.
            try:
                page.wait_for_selector(".card", timeout=15000)
            except Exception:
                sys.exit("no pending approval found at %s — file one first "
                         "(see assets/README.md step 2)" % url)
            page.wait_for_timeout(600)
            _hide_push_artifact(page)

            def snap(name):
                path = os.path.join(frames_dir, name + ".png")
                page.screenshot(path=path)
                shots.append(path)
                print("frame:", path)
                return path

            snap("01-pending")
            # Open the approval detail page — server-rendered, two-tap approve.
            href = page.locator(".card").first.get_attribute("href")
            page.goto(url + href, wait_until="networkidle")
            page.wait_for_selector("#approveBtn", timeout=15000)
            page.wait_for_timeout(600)
            _hide_push_artifact(page)
            snap("02-detail")
            # Tap via JS dispatch: the page's own two-tap handler runs unchanged,
            # but headless mobile-emulation taps are flaky, so the clicks are
            # dispatched deterministically (documented in assets/README.md).
            page.evaluate("document.getElementById('approveBtn').click()")
            page.wait_for_selector("#approveBtn.armed", timeout=10000)
            page.wait_for_timeout(700)
            _hide_push_artifact(page)
            snap("03-armed")
            page.evaluate("document.getElementById('approveBtn').click()")
            # POST /answer 303-redirects to / — wait for the landing, then snap.
            page.wait_for_url(url + "/", timeout=15000)
            page.wait_for_timeout(800)
            _hide_push_artifact(page)
            snap("04-answered")
        finally:
            browser.close()
    return shots


def assemble(shots, out_path, max_width=420):
    if not shots:
        raise ValueError("assemble() needs at least one frame")
    holds = FRAME_HOLDS
    frames = []
    for s in shots:
        im = Image.open(s).convert("RGB")
        if im.width > max_width:
            im = im.resize((max_width, int(im.height * max_width / im.width)),
                           Image.LANCZOS)
        stem = os.path.splitext(os.path.basename(s))[0]
        frames.append((im, int(holds.get(stem, 1.5) * 1000)))
    # Build the frame list: repeat each frame per its hold at 10 fps.
    seq = []
    for im, ms in frames:
        n = max(1, ms // 100)
        seq.extend([im] * n)
    seq[0].save(out_path, save_all=True, append_images=seq[1:],
                duration=100, loop=0, optimize=True)
    kb = os.path.getsize(out_path) // 1024
    print("wrote %s (%d KB, %.1fs loop)" % (out_path, kb, len(seq) / 10))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="demo confirmd base URL")
    ap.add_argument("--frames-dir", default="/tmp/demo-frames")
    ap.add_argument("--out", required=True, help="output GIF path")
    args = ap.parse_args()
    # Engineering review: a trailing-slash --url (exactly what a browser
    # address bar yields) would build "//approval/<id>" and 404, and break
    # the wait_for_url match on the 303 landing. Normalize once.
    url = args.url.rstrip("/")
    shots = capture(url, args.frames_dir)
    if len(shots) < 4:
        sys.exit("expected 4 frames, got %d — the demo flow broke" % len(shots))
    assemble(shots, args.out)


if __name__ == "__main__":
    main()
