#!/usr/bin/env python3
"""Pin the proxy narrow-writer inventory against deploy.sh.

proxy/README.md's "The secret store and its writers" section is the
reader-facing inventory of the narrow writers; proxy/deploy.sh's
`/usr/local/bin` install loop is the operational one. A new writer that
lands in the repo but is installed without being documented (or
documented without being installed) currently drifts silently — the
README claims the family is "the only way secrets get into the store",
so the claim and the install loop must name the same set.

This test pins both directions:

1. every `cred-*` writer the README names (except `grant-writer`, which
   the README documents as exec'd directly by confirmd at
   /home/swapd/grant-writer — deliberately NOT in /usr/local/bin) is
   installed into /usr/local/bin by deploy.sh;
2. every `cred-*` binary deploy.sh installs into /usr/local/bin is named
   in the README's writer section — an installed-but-undocumented writer
   is the drift direction that would silently widen the privileged
   surface.

Non-writer /usr/local/bin installs (with-proxy, confirm-request,
credvalidate.py) are out of scope here: they are documented elsewhere in
the README, not in the writer section.

Non-vacuity (all verified by neutering, then reverted): renaming an
install dest fails direction 1 and renaming a README writer name fails
both directions; a new undocumented cred-* installed from proxy/ AND
from confirm/ each fail direction 2 by name; an install line with a
trailing comment fails the unparsed-line guard instead of slipping
through; moving a comment-only SPARKVM_* mention below the split anchor
does not fail the seam scan.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "proxy" / "README.md"
DEPLOY = REPO_ROOT / "proxy" / "deploy.sh"

WRITER_SECTION_START = "## The secret store and its writers"

# Documented as exec'd directly by confirmd (which already runs as
# swapd) at /home/swapd/grant-writer — deliberately not installed to
# /usr/local/bin and not covered by the sudoers fragment.
NON_BIN_WRITERS = {"grant-writer"}


def _readme_writer_names():
    text = README.read_text()
    assert WRITER_SECTION_START in text, (
        "proxy/README.md no longer has the %r section heading — update "
        "the pin's section bounds" % WRITER_SECTION_START
    )
    start = text.index(WRITER_SECTION_START)
    # The writer section runs until the next top-level heading.
    end = text.find("\n## ", start)
    assert end != -1, (
        "proxy/README.md's writer section is now the last section — the "
        "pin needs a new end bound"
    )
    section = text[start:end]
    return set(re.findall(r"`(cred-[a-z0-9-]+)`", section))


def _deploy_bin_installs():
    """Map /usr/local/bin/<name> -> install line for every `sudo install`
    line in deploy.sh that targets /usr/local/bin, regardless of source
    directory.

    deploy.sh installs to /usr/local/bin from several source dirs
    (proxy/, credlib/ -> credvalidate.py, confirm/ -> confirm-request),
    so the capture must not be coupled to the proxy/ source dir: a future
    cred-* writer installed from credlib/ or confirm/ — exactly the shape
    credvalidate.py and confirm-request take today — must still be seen by
    the writer pins below.
    """
    src = DEPLOY.read_text()
    installs = {}
    strict = re.compile(
        r"^\s*sudo\s+install(?:\s+\S+)*?\s+(\S+)\s+(/usr/local/bin/\S+)\s*$",
        re.MULTILINE,
    )
    for m in strict.finditer(src):
        source, dest = m.group(1), m.group(2)
        name = dest.rsplit("/", 1)[1]
        if source.startswith("proxy/"):
            assert source.rsplit("/", 1)[1] == name, (
                "deploy.sh renames %s to %s — the writer pin assumes "
                "source == dest" % (source, dest)
            )
        installs[name] = m.group(0).strip()
    # Fail loudly on any /usr/local/bin install line the strict pattern
    # did not consume (trailing comment, line continuation, reformat): a
    # silently skipped line would pass the pins below vacuously.
    loose = re.findall(
        r"^\s*sudo\s+install\b.*?\s(/usr/local/bin/\S+)",
        src,
        re.MULTILINE,
    )
    unconsumed = [
        dest for dest in loose if dest.rsplit("/", 1)[1] not in installs
    ]
    assert not unconsumed, (
        "proxy/deploy.sh has /usr/local/bin install lines the pin cannot "
        "parse (trailing comment? continuation?): %s — extend the strict "
        "pattern, do not let them slip through" % ", ".join(unconsumed)
    )
    return installs


def test_readme_writers_are_all_installed():
    """Every writer the README names is installed by deploy.sh."""
    writers = _readme_writer_names() - NON_BIN_WRITERS
    assert writers, "the README's writer section names no cred-* writers"
    installs = _deploy_bin_installs()
    missing = sorted(w for w in writers if w not in installs)
    assert not missing, (
        "writers documented in proxy/README.md but not installed to "
        "/usr/local/bin by proxy/deploy.sh: %s" % ", ".join(missing)
    )


def test_deploy_installed_writers_are_all_documented():
    """Every cred-* binary deploy.sh installs is named in the README."""
    installs = _deploy_bin_installs()
    installed_writers = {name for name in installs if name.startswith("cred-")}
    assert installed_writers, "deploy.sh installs no cred-* to /usr/local/bin"
    documented = _readme_writer_names() - NON_BIN_WRITERS
    undocumented = sorted(installed_writers - documented)
    assert not undocumented, (
        "cred-* binaries installed to /usr/local/bin by proxy/deploy.sh "
        "but not documented in proxy/README.md's writer section: %s"
        % ", ".join(undocumented)
    )
