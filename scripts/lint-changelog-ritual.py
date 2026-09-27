#!/usr/bin/env python3
"""Enforce the changelog ritual (CHANGELOG.md, "The changelog ritual" section).

Rule 1: entries are written for the person running spark-vm — no file paths,
function names, or internal audit numbering. Rule 4: notes that never land in
the repo (the loop's working notes) don't get entries.

This lint covers the mechanically checkable half of that: changelog entries
must never reference the loop's workspace-internal paths, which cannot exist
in a reader's checkout:

  - ``agent_notes/``   — the loop's working-notes workspace (per ritual rule 4)
  - ``hidden_files/``  — the loop's internal bookkeeping dir
  - ``workspace/goals/`` — the agent's goal workspace on its own VM

The ritual preamble at the top of CHANGELOG.md (before the first ``## [x]``
release heading) is exempt — it documents the rule and names ``agent_notes/``
as the example.

Usage:
    python3 scripts/lint-changelog-ritual.py [PATH-TO-CHANGELOG]

Exit 0 when clean; exit 1 listing each violating line number and pattern.
"""

import re
import sys

CHANGELOG = "CHANGELOG.md"

# Workspace-internal path prefixes that can never exist in a reader's checkout.
INTERNAL_PATH_PATTERNS = ("agent_notes/", "hidden_files/", "workspace/goals/")


def find_violations(text):
    """Return [(lineno, pattern, excerpt)] for entries after the preamble."""
    violations = []
    in_preamble = True
    for lineno, line in enumerate(text.splitlines(), start=1):
        if re.match(r"^## \[", line):
            in_preamble = False
        if in_preamble:
            continue
        for pattern in INTERNAL_PATH_PATTERNS:
            if pattern in line:
                violations.append((lineno, pattern, line.strip()[:160]))
                break
    return violations


def main(argv):
    path = argv[1] if len(argv) > 1 else CHANGELOG
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
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
