"""Tests for the sparkvm.dev front door deploy slice (H28).

Guards the Cloudflare Pages contract for site/: the static file set,
the _headers security policy, the custom 404, and the front-door
content contracts on site/index.html (open-source story, hosted vs
self-hosted split, repo + beta-pilot pointers) — without breaking the
landed waitlist funnel wiring (scripts/test_waitlist_page.py owns those
assertions; this file adds the H28-specific ones and the dead-CTA guard).

Run from the repo root:  python3 -m pytest scripts/test_frontdoor_deploy.py -q

stdlib-only (html.parser), no network.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.scripts = 0
        self.forms = 0
        self.metas = []
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        elif tag == "script":
            self.scripts += 1
        elif tag == "form":
            self.forms += 1
        elif tag == "meta":
            self.metas.append(attrs)

    def handle_data(self, data):
        self.text_parts.append(data)

    @property
    def text(self):
        return " ".join(self.text_parts)


def parse(page):
    text = (SITE / page).read_text(encoding="utf-8")
    collector = LinkCollector()
    collector.feed(text)
    return text, collector


def parse_headers():
    """Parse site/_headers into {path: {header-name: value}}."""
    blocks = {}
    current = None
    for raw in (SITE / "_headers").read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            current = line.strip()
            blocks[current] = {}
        else:
            name, _, value = line.strip().partition(":")
            assert current is not None, "_headers: header before any path"
            blocks[current][name.strip().lower()] = value.strip()
    return blocks


def test_pages_static_file_set():
    """The Pages deploy ships exactly the static front-door set."""
    for rel in ("index.html", "404.html", "_headers",
                "go/selfhost/index.html", "assets/og-persistence-pair.png"):
        assert (SITE / rel).exists(), f"site/{rel} missing from the deploy set"


def test_headers_baseline():
    """Baseline security headers on every path; strict CSP only where the
    no-JS/no-form guarantee holds (waitlist.html is served by waitlistd,
    not Pages — its form posts cross-origin, so it is excluded by design)."""
    blocks = parse_headers()
    baseline = blocks["/*"]
    assert baseline.get("x-content-type-options") == "nosniff"
    assert baseline.get("x-frame-options") == "DENY"
    assert baseline.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "content-security-policy" not in baseline, \
        "the /* baseline must never carry a CSP — a CSP there would silently " \
        "scope waitlist.html too and break its cross-origin form post"
    pp = baseline.get("permissions-policy", "")
    for feat in ("camera=()", "microphone=()", "geolocation=()"):
        assert feat in pp, f"Permissions-Policy missing {feat}"
    for path in ("/", "/404.html", "/go/*"):
        csp = blocks[path].get("content-security-policy", "")
        assert "default-src 'none'" in csp, f"{path}: CSP must default-deny"
        assert "script-src" not in csp, f"{path}: no script source may be listed"
        assert "style-src 'unsafe-inline'" in csp, \
            f"{path}: inline <style> needs the style-src allowance"
    assert not any("waitlist" in p for p in blocks), \
        "waitlist.html must not be CSP-scoped on Pages (control-plane served)"


def test_404_page():
    """Custom 404: honest, no JS, links home, never indexed."""
    text, c = parse("404.html")
    assert c.scripts == 0, "404 must carry no JS"
    assert "/" in c.links, "404 must link home"
    robots = [m for m in c.metas if m.get("name") == "robots"]
    assert robots and "noindex" in robots[0].get("content", ""), \
        "404 must not be indexed"


def test_frontdoor_open_source_story():
    """H28: the open-source story is a first-class section, not a footer line."""
    text, c = parse("index.html")
    assert "Open source, running today." in text
    assert "https://github.com/ntindle/spark-vm" in c.links
    assert "https://github.com/ntindle/spark-vm/blob/main/CONTRIBUTING.md" in c.links
    assert "MIT" in text, "the license must be named"


def test_frontdoor_hosted_vs_selfhosted_split():
    """H28: the hosted vs self-hosted split, with the repo + beta-pilot pointers."""
    text, c = parse("index.html")
    assert "Two ways to run it." in text
    assert "Unraid" in text and "Proxmox" in text, \
        "the BYO self-host paths must be named"
    assert "https://musebook.me" in c.links, "beta-pilot pointer missing"


def test_funnel_wiring_preserved():
    """The landed funnel contracts survive the H28 rework: the four ?src=
    buckets exactly once, /go/selfhost?src=selfhost exactly twice, no other
    /waitlist links (the waitlist is not deployed — no dead CTAs)."""
    _, c = parse("index.html")
    for bucket in ("hero", "trust", "faq", "final"):
        hits = [h for h in c.links if h == f"/waitlist?src={bucket}"]
        assert len(hits) == 1, f"bucket {bucket}: found {len(hits)}x, want 1"
    selfhost = [h for h in c.links if h == "/go/selfhost?src=selfhost"]
    assert len(selfhost) == 2, f"self-host CTA found {len(selfhost)}x, want 2"
    waitlistish = [h for h in c.links if h.startswith("/waitlist")]
    assert len(waitlistish) == 4, \
        f"only the four funnel buckets may link /waitlist, found {waitlistish}"


def test_no_dead_forms_no_js():
    """The front door carries no signup form and no JS (dead-form rule +
    FUNNEL_MEASUREMENT §2: analytics are server-side)."""
    _, c = parse("index.html")
    assert c.forms == 0, "the front door must not typeset a dead form"
    assert c.scripts == 0, "no page JS on the front door"


def test_internal_links_resolve_statically():
    """Every internal absolute link on the front door must resolve on the
    static Pages host (no dynamic-only paths except the four funnel
    buckets, which the control plane serves when the waitlist is live)."""
    _, c = parse("index.html")
    static_paths = {"/", "/404.html", "/go/selfhost"}
    for h in c.links:
        if h.startswith("#"):
            continue
        if h.startswith("/"):
            base = h.split("?")[0]
            assert base in static_paths or h.startswith("/waitlist?src="), \
                f"{h} has no static target on the Pages host"
        elif h.startswith("http"):
            assert h.startswith("https://github.com/ntindle/spark-vm") or \
                h.startswith("https://musebook.me"), \
                f"unexpected external link: {h}"


def test_no_pricing_numbers_or_dates():
    """P3 marketing gate, machine-checkable half: the front door prints no
    hosted pricing promises and no launch dates."""
    text, _ = parse("index.html")
    assert not re.search(r"\$\d", text), "pricing numbers must not appear"
    assert "sign up now" not in text.lower()
