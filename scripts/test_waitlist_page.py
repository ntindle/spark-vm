"""Tests for the waitlist page build slice (site/).

Guards the funnel-measurement follow-up "typeset the §5 tags, wire the
src= CTA URLs" (docs/FUNNEL_MEASUREMENT.md §9, docs/HOSTED_SIGNUP_WEB_UI.md
§4): the exact §5 <head> tag set, the ?src= CTA buckets, and the §4.2 form
markup. stdlib-only (html.parser), no network.
"""

import re
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE = REPO / "site"

# docs/FUNNEL_MEASUREMENT.md §5, exact content values (<host> is the
# deploy-time placeholder documented in site/README.md).
EXPECTED_TAGS = [
    ("meta", {"property": "og:url", "content": "https://<host>/"}),
    ("meta", {"name": "description",
              "content": "A persistent computer for your AI agent: files, jobs, and desktop still there tomorrow."}),
    ("meta", {"property": "og:type", "content": "website"}),
    ("meta", {"property": "og:title", "content": "spark-vm — a real computer that stays yours"}),
    ("meta", {"property": "og:description",
              "content": "A persistent computer for your AI agent: files, jobs, and desktop still there tomorrow. No third-party trackers on this page."}),
    ("meta", {"property": "og:image", "content": "https://<host>/assets/og-persistence-pair.png"}),
    ("meta", {"property": "og:image:alt",
              "content": "The same desktop, today and tomorrow — nothing lost overnight."}),
    ("meta", {"name": "twitter:card", "content": "summary_large_image"}),
]

EXPECTED_BUCKETS = ["hero", "trust", "faq", "final"]


class TagCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas = []
        self.links = []
        self.inputs = []
        self.scripts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            self.metas.append(attrs)
        elif tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        elif tag == "input":
            self.inputs.append(attrs)
        elif tag == "script":
            self.scripts += 1


def parse(page):
    text = (SITE / page).read_text(encoding="utf-8")
    collector = TagCollector()
    collector.feed(text)
    return text, collector


def test_tag_set_matches_section5():
    """Both pages carry exactly the §5 tag set, with the exact content."""
    for page in ("index.html", "waitlist.html"):
        _, c = parse(page)
        for tag, expected_attrs in EXPECTED_TAGS:
            matches = [m for m in c.metas
                       if all(m.get(k) == v for k, v in expected_attrs.items())]
            assert len(matches) == 1, f"{page}: tag {expected_attrs} found {len(matches)}x"


def test_no_extra_og_or_twitter_tags():
    """No fb:app_id, no pre-claimed handles, no extra OG tags (§5 rules)."""
    for page in ("index.html", "waitlist.html"):
        _, c = parse(page)
        for m in c.metas:
            prop = m.get("property", "")
            name = m.get("name", "")
            assert prop != "fb:app_id", f"{page}: fb:app_id must not be pre-claimed"
            assert not name.startswith("twitter:site"), f"{page}: no pre-claimed handles"
            if prop.startswith("og:"):
                assert any(prop == e[1].get("property") for e in EXPECTED_TAGS), \
                    f"{page}: unexpected OG tag {prop}"


def test_no_page_javascript():
    """The waitlist funnel has no page JS (docs/HOSTED_SIGNUP_WEB_UI.md §4.2)."""
    for page in ("index.html", "waitlist.html"):
        _, c = parse(page)
        assert c.scripts == 0, f"{page}: no <script> allowed"


def test_src_buckets_wired():
    """Each waitlist CTA is a distinct first-party URL with its section bucket
    (docs/HOSTED_SIGNUP_WEB_UI.md §4.1, docs/FUNNEL_MEASUREMENT.md §3.2)."""
    text, c = parse("index.html")
    for bucket in EXPECTED_BUCKETS:
        hits = [h for h in c.links if h == f"/waitlist?src={bucket}"]
        assert len(hits) == 1, f"bucket {bucket}: found {len(hits)}x, want exactly 1"
    # No CTA may leak src= onto a third-party domain.
    for h in c.links:
        if "src=" in h:
            assert h.startswith("/"), f"src= must stay on our domain: {h}"


def test_selfhost_cta_exactly_twice():
    """The secondary CTA appears exactly twice (hero, FAQ) via the first-party
    redirect (docs/LANDING_PAGE_COPY.md §2, H15 §4.1)."""
    _, c = parse("index.html")
    hits = [h for h in c.links if h == "/go/selfhost?src=selfhost"]
    assert len(hits) == 2, f"self-host CTA found {len(hits)}x, want exactly 2"


def test_waitlist_form_markup():
    """Form markup per docs/HOSTED_SIGNUP_WEB_UI.md §4.2."""
    text, c = parse("waitlist.html")
    assert 'action="/waitlist/form"' in text
    assert 'method="post"' in text
    owner = next(i for i in c.inputs if i.get("name") == "owner_email")
    assert "required" in owner, "owner email must be required"
    assert owner.get("autocomplete") == "email"
    assert owner.get("inputmode") == "email"
    muse = next(i for i in c.inputs if i.get("name") == "muse_email")
    assert "required" not in muse, "agent-contact email must be optional"
    assert muse.get("autocomplete") == "off"
    assert muse.get("inputmode") == "email"
    honeypot = [i for i in c.inputs if i.get("name") == "website"]
    assert honeypot and honeypot[0].get("tabindex") == "-1", "honeypot field missing"
    hp_rule = re.search(r"\.hp\{([^}]*)\}", text.replace(" ", ""))
    assert hp_rule, "honeypot .hp rule missing"
    assert "display:none" not in hp_rule.group(1), \
        "honeypot must be off-screen, never display:none"
    trap = [i for i in c.inputs if i.get("name") == "rendered_at"]
    assert trap and trap[0].get("type") == "hidden", "time-trap field missing"


def test_og_image_exists_and_sized():
    """og:image exists at the deployed path and is a 1200x630 PNG."""
    from PIL import Image
    img_path = SITE / "assets" / "og-persistence-pair.png"
    assert img_path.exists(), "og:image asset missing"
    with Image.open(img_path) as im:
        assert im.size == (1200, 630), f"og:image is {im.size}, want 1200x630"
        assert im.format == "PNG"


def test_no_launch_dates_or_pricing_numbers():
    """Honesty rules that the markup itself can carry: no dates, no numbers
    that aren't decided (docs/LANDING_PAGE_COPY.md §5)."""
    for page in ("index.html", "waitlist.html"):
        text, c = parse(page)
        assert not re.search(r"\$\d", text), f"{page}: pricing numbers must not appear"
        assert "free tier" not in text.lower(), f"{page}: never print 'free tier'"
        assert "session clock" not in text.lower(), f"{page}: paid-tier property"
