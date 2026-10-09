"""Pin docs/CI.md's link-check exclusion inventory to .github/workflows/ci.yml.

docs/CI.md's `markdown-links` row once named eight excluded hosts while the
job already excluded 41 hosts/URL patterns: the #1202 exclusions (x264.org,
marktechpost.com, investors.digitalocean.com) and ~30 earlier host adds had
never reached the doc, and docs/EXCLUDED_HOSTS_RESWEEP.md still claimed the
quarterly re-sweep ritual "covers all eight lychee-excluded hosts" — so the
majority of CI-skipped links were rotting with no re-sweep coverage and no
doc admitting it.

The job's `args:` line in `.github/workflows/ci.yml` is the source of truth.
The doc carries its claimed inventory in a
<!-- link-check-excludes:start --> ... <!-- link-check-excludes:end -->
comment block (one token per line, invisible in GitHub's rendered view; see
the block's own note for the token scheme). This pin fails loudly on drift
in either direction:
- a job `--exclude` the doc doesn't name (stale doc, understated set),
- a doc-named entry the job no longer excludes (dead inventory),
- an unsorted block (regeneration must stay deterministic).

The test rides two CI gates: the sharded python-tests suite (via testpaths)
for code PRs, and the always-on docs-guard job for docs-only PRs — a
docs-only inventory edit can't land unwatched. The job's lychee step also
carries a comment pointing editors at the inventory when they add an
--exclude.

When the job's exclude list grows, regenerate the doc's block from the job
(the token scheme is deterministic — see `normalize`) and keep the prose
honest; do not hand-edit one side.

Pure stdlib, no fixtures. Run from the repo root:
  python3 -m pytest scripts/test_ci_md_link_excludes.py -q
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
DOC = ROOT / "docs" / "CI.md"

INVENTORY_RE = re.compile(
    r"<!-- link-check-excludes:start -->(.*?)<!-- link-check-excludes:end -->",
    re.S,
)

# Non-host entries: URL-pattern classes, not single bot-blocking hosts. They
# live in the inventory (the job excludes them) but are not "excluded hosts"
# for the re-sweep ritual's host enumeration in
# docs/EXCLUDED_HOSTS_RESWEEP.md.
NON_HOST_TOKENS = frozenset(
    {"release-compare-url", "github-blob-urls", "archive-single-url"}
)

HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")


def normalize(raw):
    """A raw --exclude token from ci.yml's (YAML double-quoted) args line.

    The args string passes through YAML double-quote unescaping and then
    bash single quotes before lychee sees it as regex, so the raw text
    carries doubled backslashes and `\\.`-escaped dots. The canonical token
    is the bare host (or a named token for the URL-pattern classes).
    """
    v = raw.replace("\\\\", "\\")  # undo YAML double-quote unescaping
    v = v.replace("\\.", ".")  # undo regex dot-escaping
    if "compare/" in v:
        return "release-compare-url"
    if "/blob/" in v:
        return "github-blob-urls"
    if v.startswith("https?://web.archive.org/web/"):
        return "archive-single-url"
    assert v.startswith("https?://"), f"unexpected exclude shape: {raw!r}"
    v = v[len("https?://"):]
    for prefix in ("(www.)?", "([a-z0-9-]+.)?"):
        if v.startswith(prefix):
            v = v[len(prefix):]
            break
    assert v.endswith("/.*"), f"unexpected exclude shape: {raw!r}"
    return v[: -len("/.*")]


def ci_excludes():
    """The normalized token set from the markdown-links job's args line."""
    text = CI_YML.read_text(encoding="utf-8")
    matches = [
        m.group(1)
        for m in re.finditer(r'args:\s*"((?:[^"\\]|\\.)*)"', text)
        if "--no-progress" in m.group(1)
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected exactly one lychee args line in ci.yml, found {len(matches)} "
            "(the pin anchors on an `args:` line containing `--no-progress` "
            "with single-quoted `--exclude '...'` tokens — if the job's arg "
            "shape changed, update the extraction, don't weaken the test)"
        )
    pats = re.findall(r"--exclude\s+'([^']+)'", matches[0])
    if not pats:
        raise AssertionError("no --exclude tokens found in the lychee args line")
    toks = [normalize(p) for p in pats]
    dupes = sorted({t for t in toks if toks.count(t) > 1})
    if dupes:
        raise AssertionError(f"duplicate excludes in ci.yml: {dupes}")
    return set(toks)


def doc_inventory_ordered():
    """The doc's inventory tokens in block order (for the sortedness pin)."""
    text = DOC.read_text(encoding="utf-8")
    blocks = INVENTORY_RE.findall(text)
    if len(blocks) != 1:
        raise AssertionError(
            "docs/CI.md must carry exactly one link-check-excludes inventory "
            f"block, found {len(blocks)}"
        )
    # Human notes may live inside the block as <!-- ... --> comments (possibly
    # multi-line); they are not inventory tokens. (They must stay comments —
    # a bare prose line here would be parsed as a token and fail the match
    # test.)
    body = re.sub(r"<!--.*?-->", "", blocks[0], flags=re.S)
    toks = [line.strip() for line in body.splitlines()]
    toks = [t for t in toks if t]
    dupes = sorted({t for t in toks if toks.count(t) > 1})
    if dupes:
        raise AssertionError(f"duplicate tokens in the doc inventory: {dupes}")
    return toks


def doc_inventory():
    """The token set the doc claims in its machine-readable inventory block."""
    return set(doc_inventory_ordered())


class TestLinkCheckExcludesInventory(unittest.TestCase):
    def test_inventory_matches_ci(self):
        ci = ci_excludes()
        doc = doc_inventory()
        missing = sorted(ci - doc)
        extra = sorted(doc - ci)
        self.assertFalse(
            missing or extra,
            "docs/CI.md's link-check-excludes inventory disagrees with "
            ".github/workflows/ci.yml:\n"
            + "".join(f"  job excludes, doc omits: {t}\n" for t in missing)
            + "".join(f"  doc names, job does not exclude: {t}\n" for t in extra),
        )

    def test_inventory_tokens_are_canonical(self):
        for t in sorted(doc_inventory()):
            self.assertTrue(
                t in NON_HOST_TOKENS or HOST_RE.match(t),
                f"non-canonical inventory token: {t!r} "
                "(must be a bare hostname or one of "
                f"{sorted(NON_HOST_TOKENS)})",
            )

    def test_inventory_block_is_sorted(self):
        toks = doc_inventory_ordered()
        self.assertEqual(
            toks,
            sorted(toks),
            "the inventory block must stay sorted so regeneration is "
            "deterministic (the block's own note says 'one token per line, "
            "sorted')",
        )


if __name__ == "__main__":
    unittest.main()
