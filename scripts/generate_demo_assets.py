#!/usr/bin/env python3
"""Capture demo-asset frames and assemble the GIFs.

Asset 1 (approval-loop) needs Playwright + Chromium, e.g. spark-vm:
    python3 scripts/generate_demo_assets.py \
        --asset approval-loop --url https://127.0.0.1:18923 \
        --out assets/demo-approval-loop.gif
Expects a running confirmd with at least one pending approval (see
assets/demo_confirmd.py for the demo instance; file one with
confirm/confirm-request). Only ever point this at a DEMO instance —
never the live deployment.

Asset 2 (secrets the agent never sees) renders terminal frames with PIL
only — no browser, no live services:
    python3 scripts/generate_demo_assets.py \
        --asset secrets --work-dir ./demo-asset2-work \
        --out assets/demo-secrets-never-seen.gif
Everything shown is demo-named; the audit journal line is byte-for-byte
the output of the real SwapAddon._audit() code path (the script calls
it with SWAP_LOG_FILE pointed at the scratch journal). The transcript
frames are genuine command output: the recipe cats the fixture, tails
the real journal, and greps it for raw secret patterns.

Asset 5 (cred-ui on a phone) screenshots the REAL cred-ui page served by
the real cred-ui.py against a scratch swapd fixture (demo-named entries
only, empty secret files) at a 390px phone width, via
chrome-headless-shell -- no Playwright needed:
    python3 scripts/generate_demo_assets.py \
        --asset credui-phone --url http://127.0.0.1:18740 \
        --out assets/demo-cred-ui-phone.gif
Only ever point this at a DEMO cred-ui instance -- never the live one.
The headless-shell binary is found via $CHROME_HEADLESS_SHELL or the
Playwright browser cache.
"""
import argparse
import os
import subprocess
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
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
    # Playwright is needed only for the approval-loop asset; import it
    # here (not at module load) so --asset secrets works without it.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is required (pip install playwright; playwright install chromium)")
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


def assemble(shots, out_path, max_width=420, holds=None):
    if not shots:
        raise ValueError("assemble() needs at least one frame")
    holds = holds if holds is not None else FRAME_HOLDS
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


# --- Asset 2: "secrets the agent never sees" (20s terminal GIF) ---
#
# Renders genuine terminal transcripts as frames: the demo agent config
# (fixture, demo-named values only) catted, then the proxy's swap journal
# tailed — the journal line is byte-for-byte the output of the REAL
# SwapAddon._audit() code path, called here with SWAP_LOG_FILE pointed
# at a scratch journal. Nothing shown is a real secret.

SECRETS_FRAMES = [
    # (stem, caption). The commands staged in each frame are the ones the
    # generator actually executes in the work dir (see generate_secrets) —
    # the frames are genuine transcripts, not re-typings.
    ("s1-config",
     "1/3 — the agent's config: placeholders only, never real secrets"),
    ("s2-journal",
     "2/3 — the swap proxy's audit journal: it names the placeholder, never the value"),
    ("s3-proof",
     "3/3 — grep the journal for raw secret patterns: nothing to find"),
]
SECRETS_HOLDS = {"s1-config": 6.0, "s2-journal": 7.0, "s3-proof": 7.0}

_DEMO_CRED = "hsurr:demo-gh-ro"   # demo placeholder; never a real secret
_DEMO_HOST = "api.github.com"     # public host used in the spark-vm docs
_FIXTURE = """{
  "api_host": "api.github.com",
  "token": "hsurr:demo-gh-ro",
  "user": "demo-agent"
}
"""

_TERM_W = 480
_TERM_FONT = 13
_TERM_PAD = 14
_TERM_TITLE_H = 30
_TERM_CAPTION_H = 46
_BG, _BAR, _PROMPT, _CMD, _OUT, _CAPTION = (
    "#0d1117", "#161b22", "#3fb950", "#e6edf3", "#8b949e", "#d29922")


def _mono_font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
              "/usr/share/fonts/dejavu-sans-fonts/DejaVuSansMono.ttf",
              "/usr/share/fonts/dejavu/DejaVuSansMono.ttf"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap_term(text, n, hang="  "):
    # Word-wrap like a real terminal (break on spaces, not mid-token);
    # continuation lines get the hang indent so the wrap is explicit.
    # (The journal line is rendered wrapped for the frame — disclosed in
    # assets/README.md; its bytes are the real _audit() output.)
    out = []
    for line in text.splitlines() or [""]:
        first = True
        while len(line) > n:
            cut = line.rfind(" ", 0, n)
            if cut <= 0:
                cut = n
            out.append(line[:cut])
            line = hang + line[cut:].lstrip(" ")
            first = False
        out.append(line)
    return out


def _flatten_transcript(transcript, ncols):
    # -> list of (show_prompt, text); wrapped command continuations align
    # under the command start instead of re-printing "$ ".
    segs = []
    for kind, text in transcript:
        if kind == "cmd":
            for i, ln in enumerate(_wrap_term(text, ncols - 2, hang="")):
                segs.append((i == 0, ln))
        else:
            for ln in _wrap_term(text, ncols):
                segs.append((False, ln))
    return segs


def _sh(cmd, cwd, env=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                       text=True, env=env, timeout=60)
    return r.stdout.rstrip("\n")


def generate_secrets(repo_root, work_dir, frames_dir):
    """Build the asset-2 transcript from real fixture + real audit path."""
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)
    fixture = os.path.join(work_dir, "demo-agent-config.json")
    journal = os.path.join(work_dir, "demo-swap.log")
    with open(fixture, "w") as f:
        f.write(_FIXTURE)
    if os.path.exists(journal):
        os.remove(journal)
    # The real audit path: SwapAddon._audit() with the journal redirected
    # to the scratch file. stderr carries the usual ssrf.deny-missing
    # warning on a box without the swapd layout; the frames show stdout.
    proxy_dir = os.path.join(repo_root, "proxy")
    code = ("import sys; sys.path.insert(0, %r); "
            "from swap_addon import SwapAddon; "
            "ok = SwapAddon()._audit(%r, %r); "
            "assert ok, 'audit write failed'") % (proxy_dir, _DEMO_HOST,
                                                 _DEMO_CRED)
    env = dict(os.environ, SWAP_LOG_FILE=journal)
    _sh("python3 -c %s" % _shell_quote(code), repo_root, env)
    with open(journal) as f:
        journal_line = f.read().strip().splitlines()[-1]
    print("journal line:", journal_line)

    shots = []
    # Every frame is a genuine transcript: the displayed command is run
    # for real in the work dir and its real stdout is rendered. Nothing
    # is re-typed.
    transcripts = {
        "s1-config": [("cmd", "cat demo-agent-config.json"),
                      ("out", _sh("cat demo-agent-config.json", work_dir))],
        "s2-journal": [("cmd", "tail -1 demo-swap.log"),
                       ("out", _sh("tail -1 demo-swap.log", work_dir))],
        "s3-proof": [("cmd", "grep -oE '[A-Za-z0-9_-]{40,}' demo-swap.log || "
                             "echo 'no 40+ char tokens anywhere in the journal'"),
                     ("out", _sh("grep -oE '[A-Za-z0-9_-]{40,}' demo-swap.log || "
                                 "echo 'no 40+ char tokens anywhere in the journal'",
                                 work_dir))],
    }
    # Uniform frame height: compute every frame's transcript segments,
    # take the tallest body, and render all frames to it (GIF viewers
    # crop or flash on mixed frame sizes).
    font_probe = _mono_font(_TERM_FONT)
    cw = max(font_probe.getlength("0123456789abcdef"), 1) / 16
    ncols = int((_TERM_W - 2 * _TERM_PAD) / cw)
    specs = {}
    for stem, caption in SECRETS_FRAMES:
        specs[stem] = (caption, _flatten_transcript(transcripts[stem], ncols))
    lh = _TERM_FONT + 6
    max_body = max(_TERM_PAD + len(s) * lh + 8 for _, s in specs.values())
    for stem, caption in SECRETS_FRAMES:
        caption_, segs = specs[stem]
        im = _render_terminal_segs(caption_, segs, max_body)
        path = os.path.join(frames_dir, stem + ".png")
        im.save(path)
        shots.append(path)
        print("frame:", path, im.size)
    return shots, journal_line


def _render_terminal_segs(caption, segs, body_h):
    """Render one terminal frame from pre-flattened segments."""
    font = _mono_font(_TERM_FONT)
    small = _mono_font(11)
    scw = max(small.getlength("0123456789abcdef"), 1) / 16
    lh = _TERM_FONT + 6
    cap_lines = _wrap_term(caption, int((_TERM_W - 2 * _TERM_PAD) / scw), hang="")
    cap_h = _TERM_CAPTION_H if len(cap_lines) <= 2 else _TERM_CAPTION_H + 14
    h = _TERM_TITLE_H + body_h + cap_h

    im = Image.new("RGB", (_TERM_W, h), _BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, _TERM_W, _TERM_TITLE_H], fill=_BAR)
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        d.ellipse([12 + i * 18, 10, 22 + i * 18, 20], fill=c)
    d.text((_TERM_W // 2, 15), "demo — secrets the agent never sees",
           font=small, fill=_OUT, anchor="mm")
    prompt_w = font.getlength("$ ")
    y = _TERM_TITLE_H + _TERM_PAD
    for show_prompt, ln in segs:
        if show_prompt:
            d.text((_TERM_PAD, y), "$", font=font, fill=_PROMPT)
            d.text((_TERM_PAD + prompt_w, y), ln, font=font, fill=_CMD)
        else:
            d.text((_TERM_PAD, y), ln, font=font, fill=_OUT)
        y += lh
    cy = _TERM_TITLE_H + body_h
    d.rectangle([0, cy, _TERM_W, h], fill=_BAR)
    ty = cy + 10
    for ln in cap_lines:
        d.text((_TERM_PAD, ty), ln, font=small, fill=_CAPTION)
        ty += 15
    return im


# --- Asset 5: cred-ui on a phone viewport ---
#
# Screenshots the REAL cred-ui page (served by the real cred-ui.py against
# a scratch swapd fixture -- demo-named entries only, empty secret files)
# at a 390px phone width with chrome-headless-shell, then cuts the full
# page into the two viewports a user would actually scroll between. The
# GIF's "scroll" is a cut between two real viewports, not a re-render.
# Frames get a slim phone bezel + caption strip drawn by the generator.

CREDUI_FRAMES = [
    ("c1-form",
     "1/2 — the add/update form on a phone viewport: full width, no sideways scroll"),
    ("c2-list",
     "2/2 — stored credentials as stacked cards: names, states, hosts — values never appear"),
]
CREDUI_HOLDS = {"c1-form": 2.2, "c2-list": 2.6}

_PHONE_W = 390          # viewport width the frames claim
_BEZEL = 10             # side bezel
_NOTCH_H = 30           # top bar with the page title
_CAPTION_H = 58
_PHONE_BG, _PHONE_BEZEL, _PHONE_CAP = "#0a0a0a", "#1f1f1f", "#d29922"


def _headless_shell():
    env = os.environ.get("CHROME_HEADLESS_SHELL")
    if env and os.path.isfile(env):
        return env
    import glob
    hits = glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/"
        "chrome-headless-shell-linux64/chrome-headless-shell"))
    if hits:
        return sorted(hits)[-1]
    sys.exit("chrome-headless-shell not found: set CHROME_HEADLESS_SHELL "
             "or install it via Playwright (playwright install chromium)")


def _content_bottom(im):
    # Last row whose pixels vary -- i.e. the page's real content end.
    g = im.convert("L")
    px, w, h = g.load(), g.width, g.height
    for y in range(h - 1, -1, -1):
        row = [px[x, y] for x in range(0, w, 4)]
        if max(row) - min(row) > 12:
            return y + 1
    return h


def capture_credui_phone(url, frames_dir):
    """Capture the two phone viewports of the demo cred-ui page."""
    os.makedirs(frames_dir, exist_ok=True)
    shell = _headless_shell()
    full = os.path.join(frames_dir, "credui-full.png")
    cmd = [shell, "--no-sandbox", "--hide-scrollbars",
           "--window-size=%d,2000" % _PHONE_W,
           "--virtual-time-budget=9000",
           "--screenshot=" + full, url.rstrip("/")]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not os.path.isfile(full):
        sys.exit("headless capture failed: %s" % (r.stderr or r.stdout)[-500:])
    page = Image.open(full).convert("RGB")
    bottom = _content_bottom(page)
    # The two viewports a phone user scrolls between: top of page, and
    # scrolled to the bottom (list card). Honest pixels, honest crops.
    viewports = [
        ("c1-form", (0, 0, _PHONE_W, min(_PHONE_W * 844 // 390, bottom))),
        ("c2-list", (0, max(0, bottom - 844), _PHONE_W, bottom)),
    ]
    shots = []
    for stem, box in viewports:
        shot = page.crop(box)
        # Pad a short final viewport to 390x844 so frames are uniform
        # (GIF viewers crop or flash on mixed frame sizes).
        if shot.height < 844:
            pad = Image.new("RGB", (_PHONE_W, 844), "#111111")
            pad.paste(shot, (0, 0))
            shot = pad
        path = os.path.join(frames_dir, stem + ".png")
        shot.save(path)
        shots.append(path)
        print("frame:", path, shot.size)
    return shots


def _render_phone_frame(caption, shot_path):
    """Draw the slim phone bezel + notch bar + caption strip around a shot."""
    shot = Image.open(shot_path).convert("RGB")
    if shot.width != _PHONE_W:
        shot = shot.resize((_PHONE_W, int(shot.height * _PHONE_W / shot.width)),
                           Image.LANCZOS)
    sw, sh = shot.size
    font = _mono_font(13)
    small = _mono_font(11)
    cap_lines = _wrap_term(caption, int((sw - 28) / max(small.getlength("0"), 1)),
                           hang="")
    cap_h = _CAPTION_H + (14 if len(cap_lines) > 2 else 0)
    w = sw + 2 * _BEZEL
    h = _NOTCH_H + sh + cap_h + _BEZEL
    im = Image.new("RGB", (w, h), _PHONE_BEZEL)
    d = ImageDraw.Draw(im)
    # screen well
    d.rectangle([_BEZEL, _NOTCH_H, _BEZEL + sw, _NOTCH_H + sh], fill="#111111")
    im.paste(shot, (_BEZEL, _NOTCH_H))
    # notch pill
    d.rounded_rectangle([w // 2 - 52, 8, w // 2 + 52, 22], radius=7,
                        fill=_PHONE_BG)
    d.text((w // 2, 15), "cred-ui · spark-vm", font=small, fill="#8b949e",
           anchor="mm")
    # caption strip
    cy = _NOTCH_H + sh
    ty = cy + 12
    for ln in cap_lines:
        d.text((_BEZEL + 4, ty), ln, font=small, fill=_PHONE_CAP)
        ty += 15
    return im


def generate_credui_phone(url, frames_dir):
    shots = capture_credui_phone(url, frames_dir)
    if len(shots) != 2:
        sys.exit("expected 2 phone frames, got %d" % len(shots))
    framed = []
    framed_dir = os.path.join(frames_dir, "framed")
    os.makedirs(framed_dir, exist_ok=True)
    for (stem, caption), shot in zip(CREDUI_FRAMES, shots):
        im = _render_phone_frame(caption, shot)
        # Keep the original stem so assemble() finds the per-frame holds.
        path = os.path.join(framed_dir, stem + ".png")
        im.save(path)
        framed.append(path)
        print("framed:", path, im.size)
    return framed


def _shell_quote(s):
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _ensure_out_dir(out_path):
    # The recipe only works because assets/ exists in a checkout; don't
    # fail obscurely if someone points --out at a fresh directory.
    d = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(d, exist_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", choices=("approval-loop", "secrets",
                                       "credui-phone"),
                    default="approval-loop")
    ap.add_argument("--url", help="demo confirmd base URL (approval-loop only); "
                    "demo cred-ui base URL (credui-phone only)")
    # ./demo-frames default: /tmp gets wiped mid-run on this box, keep
    # intermediates in the working tree (asset-1's documented recipe
    # doesn't pass --frames-dir, so it just lands there instead of /tmp).
    ap.add_argument("--frames-dir", default="./demo-frames")
    ap.add_argument("--work-dir", default="./demo-asset2-work",
                    help="scratch dir for --asset secrets (fixture + journal)")
    ap.add_argument("--out", required=True, help="output GIF path")
    args = ap.parse_args()
    if args.asset == "secrets":
        repo_root = os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))
        shots, _ = generate_secrets(repo_root, args.work_dir, args.frames_dir)
        if len(shots) != 3:
            sys.exit("expected 3 frames, got %d" % len(shots))
        _ensure_out_dir(args.out)
        assemble(shots, args.out, max_width=_TERM_W, holds=SECRETS_HOLDS)
        return
    if args.asset == "credui-phone":
        if not args.url:
            sys.exit("--url is required for --asset credui-phone "
                     "(a DEMO cred-ui instance -- never the live one)")
        shots = generate_credui_phone(args.url, args.frames_dir)
        _ensure_out_dir(args.out)
        assemble(shots, args.out, max_width=410, holds=CREDUI_HOLDS)
        return
    if not args.url:
        sys.exit("--url is required for --asset approval-loop")
    # Engineering review: a trailing-slash --url (exactly what a browser
    # address bar yields) would build "//approval/<id>" and 404, and break
    # the wait_for_url match on the 303 landing. Normalize once.
    url = args.url.rstrip("/")
    shots = capture(url, args.frames_dir)
    if len(shots) < 4:
        sys.exit("expected 4 frames, got %d — the demo flow broke" % len(shots))
    _ensure_out_dir(args.out)
    assemble(shots, args.out)


if __name__ == "__main__":
    main()
