#!/usr/bin/env python3
"""Enforce the changelog ritual (CHANGELOG.md, "The changelog ritual" section).

Rule 1: entries are written for the person running spark-vm — no file paths,
function names, or internal audit numbering. Rule 4: notes that never land in
the repo (the maintainer's working notes) don't get entries. Rule 7: each
``### `` section heading appears at most once per release block and sections
follow the Keep-a-Changelog order — enforced for every ``## [Unreleased]``
block (all occurrences are scanned), so released blocks stay grandfathered.

Section headings inside fenced code blocks are not headings: a ``### ``
line in an example is ignored by the shape check. Likewise a ``## [``
line inside a fence neither starts nor ends a release block. A fence that
never closes inside the scanned block is not honored (fail-closed): a
dangling fence cannot silently hide real headings.

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
# Fenced code blocks (CommonMark: up to three leading spaces, three or more
# backticks or tildes). The info-string half is only relevant on opens.
_FENCE_RE = re.compile(r"^( {0,3})(`{3,}|~{3,})")

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


def _fenced_line_indexes(lines):
    """Return the 0-based indexes of lines inside properly closed fenced code
    blocks.

    Fences are document-level per CommonMark, so this is computed once over
    the whole document and shared by the block segmentation and the
    per-block shape scans. The fence lines themselves are included. A fence
    that never closes in the document is NOT honored — its would-be interior
    is excluded, so a dangling fence cannot silently hide content
    (fail-closed). A fence-like line inside a fence that is not a valid
    close (wrong char, too short, or carrying an info string) leaves the
    fence state unchanged.
    """
    inside = set()
    fence_char = None
    fence_len = 0
    start = 0
    for i, line in enumerate(lines):
        match = _FENCE_RE.match(line)
        if match is None:
            continue
        char = match.group(2)[0]
        run = len(match.group(2))
        rest = line[match.end() :].strip()
        if fence_char is None:
            # Opening fence: the info string (```bash) is fine here.
            fence_char, fence_len, start = char, run, i
        elif char == fence_char and run >= fence_len and not rest:
            # Closing fence: same char, at least as long, no info string.
            inside.update(range(start, i + 1))
            fence_char = None
            fence_len = 0
    return inside


def _find_section_shape_violations(numbered_lines, fenced):
    """Return [(lineno, kind, excerpt)] for section-heading drift.

    ``numbered_lines`` is one Unreleased block as (lineno, line) pairs;
    ``fenced`` is the set of 0-based file line indexes inside properly
    closed fenced code blocks (computed once over the whole document — see
    _fenced_line_indexes). Flags (a) a ``### `` heading whose normalized
    name already appeared in the block and (b) a recognized section heading
    that steps backwards in the canonical Keep-a-Changelog order.
    Unrecognized headings (e.g. a one-off ``### Notes``) are still
    duplicate-checked but not order-checked.

    ``### `` lines inside properly closed fenced code blocks are ignored —
    they are examples, not headings. Duplicate/order state is per block:
    a heading that already appeared in an earlier Unreleased block does not
    flag; only repeats within the same block count.
    """
    violations = []
    seen = {}  # normalized name -> first lineno
    last_order = -1
    for lineno, line in numbered_lines:
        if (lineno - 1) in fenced:
            continue
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
    # Rule 7: section headings in every Unreleased block must be unique and
    # follow the Keep-a-Changelog order. Released blocks are grandfathered,
    # so the scan stays scoped to Unreleased. Each block is checked with its
    # own duplicate/order state (see _find_section_shape_violations).
    #
    # Fences are document-level: a ``## [`` line inside a fenced example
    # neither starts nor ends a block, so compute the fenced indexes once
    # over the whole file and reuse them for both the block segmentation
    # and the per-block shape scans.
    fenced = _fenced_line_indexes(lines)
    unreleased_starts = [
        i
        for i, line in enumerate(lines)
        if i not in fenced and _UNRELEASED_RE.match(line)
    ]
    for unreleased in unreleased_starts:
        block_end = next(
            (
                i
                for i, line in enumerate(lines[unreleased + 1:], start=unreleased + 1)
                if i not in fenced and _HEADING_RE.match(line)
            ),
            len(lines),
        )
        violations.extend(
            _find_section_shape_violations(
                [(i + 1, lines[i]) for i in range(unreleased, block_end)], fenced
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
