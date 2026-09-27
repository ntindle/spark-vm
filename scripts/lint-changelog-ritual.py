#!/usr/bin/env python3
"""Enforce the changelog ritual (CHANGELOG.md, "The changelog ritual" section).

Rule 1: entries are written for the person running spark-vm — no file paths,
function names, or internal audit numbering. Rule 4: notes that never land in
the repo (the maintainer's working notes) don't get entries.

This lint covers the mechanically checkable half of that: changelog entries
must never reference workspace-internal paths, which cannot exist in a
reader's checkout:

  - ``agent_notes``    — the maintainer's working-notes workspace (rule 4)
  - ``hidden_files``   — internal bookkeeping dir
  - ``workspace/goals`` — the maintainer's goal workspace on its own machine

The ritual preamble at the top of CHANGELOG.md (before the first release
heading, e.g. ``## [Unreleased]``) is exempt — it documents the rule and
names ``agent_notes/`` as its example. A changelog with no release heading
at all is reported as a violation, not silently passed.

Usage:
    python3 scripts/lint-changelog-ritual.py [PATH-TO-CHANGELOG]

When run without an argument, the changelog defaults to the repo root,
resolved relative to this script's location (so `cd scripts && ./lint-
changelog-ritual.py` works). Exit 0 when clean, 1 when violations are found,
2 when the changelog cannot be read.
"""

import os
import re
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANGELOG = os.path.join(_REPO_ROOT, "CHANGELOG.md")

# Workspace-internal path stems that can never exist in a reader's checkout.
# Slash variants first so "agent_notes/" reports with its full match; the
# slashless forms catch bare mentions like "the agent_notes workspace".
INTERNAL_PATH_PATTERNS = (
    "agent_notes/",
    "agent_notes",
    "hidden_files/",
    "hidden_files",
    "workspace/goals",
)

_HEADING_RE = re.compile(r"^##\s*\[")


def find_violations(text):
    """Return [(lineno, pattern, excerpt)] for entries after the preamble."""
    lines = text.splitlines()
    first_heading = next(
        (i for i, line in enumerate(lines) if _HEADING_RE.match(line)), None
    )
    if first_heading is None:
        return [
            (
                0,
                "<changelog>",
                "no release heading (## [x.y.z]) found — "
                "the ritual preamble cannot be exempted",
            )
        ]
    violations = []
    for lineno, line in enumerate(lines[first_heading:], start=first_heading + 1):
        for pattern in INTERNAL_PATH_PATTERNS:
            if pattern in line:
                violations.append((lineno, pattern, line.strip()[:160]))
                break
    return violations


def main(argv):
    if len(argv) > 2:
        print(
            "usage: lint-changelog-ritual.py [PATH-TO-CHANGELOG]",
            file=sys.stderr,
        )
        return 2
    path = argv[1] if len(argv) == 2 else CHANGELOG
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"lint-changelog-ritual: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    violations = find_violations(text)
    for lineno, pattern, excerpt in violations:
        print(f"{path}:{lineno}: workspace-internal path '{pattern}': {excerpt}")
    if violations:
        print(
            f"lint-changelog-ritual: {len(violations)} violation(s) — "
            "changelog entries must not reference workspace-internal paths "
            "(see CHANGELOG.md 'The changelog ritual', rules 1 and 4)",
            file=sys.stderr,
        )
        return 1
    print(f"lint-changelog-ritual: {path} clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
