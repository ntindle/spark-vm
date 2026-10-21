#!/usr/bin/env python3
"""Enforce the changelog ritual (CHANGELOG.md, "The changelog ritual" section).

Rule 1: entries are written for the person running spark-vm — no file paths,
function names, or internal audit numbering. Rule 4: notes that never land in
the repo (the maintainer's working notes) don't get entries. Rule 7: each
``### `` section heading appears at most once per release block and sections
follow the Keep-a-Changelog order — enforced for ``## [Unreleased]`` only, so
released blocks stay grandfathered.

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
_UNRELEASED_RE = re.compile(r"^##\s*\[unreleased\]", re.IGNORECASE)
_SECTION_HEADING_RE = re.compile(r"^###\s+(\S.*?)\s*$")

# Canonical Keep-a-Changelog section order (1.1.0): Added, Changed,
# Deprecated, Removed, Fixed, Security. Skipping a kind is fine; going
# backwards is not.
_SECTION_ORDER = {
    "added": 0,
    "changed": 1,
    "deprecated": 2,
    "removed": 3,
    "fixed": 4,
    "security": 5,
}


def _find_section_shape_violations(numbered_lines):
    """Return [(lineno, kind, excerpt)] for section-heading drift.

    ``numbered_lines`` is the Unreleased block as (lineno, line) pairs.
    Flags (a) a ``### `` heading whose normalized name already appeared in
    the block and (b) a recognized section heading that steps backwards in
    the canonical Keep-a-Changelog order. Unrecognized headings (e.g. a
    one-off ``### Notes``) are still duplicate-checked but not order-checked.
    """
    violations = []
    seen = {}  # normalized name -> first lineno
    last_order = -1
    for lineno, line in numbered_lines:
        match = _SECTION_HEADING_RE.match(line)
        if match is None:
            continue
        name = match.group(1).strip().lower()
        if name in seen:
            violations.append(
                (
                    lineno,
                    "duplicate section heading",
                    f"duplicate '### {match.group(1).strip()}' heading "
                    f"(first at line {seen[name]})",
                )
            )
        else:
            seen[name] = lineno
        order = _SECTION_ORDER.get(name)
        if order is not None:
            if order < last_order:
                violations.append(
                    (
                        lineno,
                        "section heading out of order",
                        f"'### {match.group(1).strip()}' breaks the "
                        "Keep-a-Changelog section order (Added, Changed, "
                        "Deprecated, Removed, Fixed, Security)",
                    )
                )
            else:
                last_order = order
    return violations


def find_violations(text):
    """Return [(lineno, kind, excerpt)] for entries after the preamble.

    ``kind`` is the matched workspace-internal path pattern for rules 1+4
    violations, ``<changelog>`` for a missing release heading, and the
    rule-7 label (``duplicate section heading`` /
    ``section heading out of order``) for Unreleased section-shape drift.
    """
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
    # Rule 7: section headings in the Unreleased block must be unique and
    # follow the Keep-a-Changelog order. Released blocks are grandfathered,
    # so the scan stays scoped to Unreleased.
    unreleased = next(
        (i for i, line in enumerate(lines) if _UNRELEASED_RE.match(line)),
        None,
    )
    if unreleased is not None:
        block_end = next(
            (
                i
                for i, line in enumerate(lines[unreleased + 1:], start=unreleased + 1)
                if _HEADING_RE.match(line)
            ),
            len(lines),
        )
        violations.extend(
            _find_section_shape_violations(
                [(i + 1, lines[i]) for i in range(unreleased, block_end)]
            )
        )
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
    for lineno, kind, excerpt in violations:
        if kind in ("duplicate section heading", "section heading out of order"):
            label = kind
        elif kind == "<changelog>":
            label = "missing release heading"
        else:
            label = f"workspace-internal path '{kind}'"
        print(f"{path}:{lineno}: {label}: {excerpt}")
    if violations:
        print(
            f"lint-changelog-ritual: {len(violations)} violation(s) "
            "(see CHANGELOG.md 'The changelog ritual')",
            file=sys.stderr,
        )
        return 1
    print(f"lint-changelog-ritual: {path} clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
