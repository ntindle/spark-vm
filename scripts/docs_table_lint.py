#!/usr/bin/env python3
"""Lint GFM tables in the markdown docs for wrapped (multi-line) rows.

Rule W1: a GFM table row must live on exactly one line. A wrapped row — a
row line whose continuation lands on a line that does not start with `|` —
silently kills the table at render time: the fragment becomes a paragraph
and the row's cell is truncated. (Observed live in
docs/H4_FAILOVER_ROUTER_DESIGN.md, docs/FLEET_READ_API_SPEC.md and
docs/COMPETITOR_ANALYSIS.md; the 20261019-2359 docs turn's review caught one
and named this follow-up.)

Detection: a table opens at a `|`-line immediately followed by a delimiter
row (`|---|---|`). Inside the table, a row line followed by a non-blank
line that neither starts with `|` nor opens a new block (heading, fence,
list item, blockquote, horizontal rule, HTML block, 4-space-indented code)
is a W1 finding; the fragment line is reported. Fenced code blocks are
skipped. Conservative by design: deeply indented fragments (4+ spaces) never
flag, and `|`-lines that are not delimiter-adjacent are prose, not tables.

Scope: docs/**/*.md plus the repo-root markdown (README.md, CONTRIBUTING.md,
SETUP.md, ENVIRONMENT.md). Exit 0 = clean, 1 = findings printed as
`path:line: W1 ...`, 2 = usage error. Stdlib only.

Run from the repo root: `python3 scripts/docs_table_lint.py`
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Markdown files in scope: every doc plus the repo-root guides.
ROOT_DOCS = ("README.md", "CONTRIBUTING.md", "SETUP.md", "ENVIRONMENT.md")

# A delimiter cell is hyphens with an optional leading/trailing colon.
_DELIM_CELL = re.compile(r":?-+:?")

# A line that unambiguously opens a new block ends a table region instead
# of being read as a wrapped fragment. (Ordered to match the cheapest
# discriminators first; 4-space indentation is the conservative "unknown"
# case that must never flag.)
_BLOCK_OPENER = re.compile(
    r"^(?:"
    r"#{1,6}(?:\s|$)"          # ATX heading
    r"|```|~~~"               # fence (also toggles the fence tracker)
    r"|>\s?"                  # blockquote
    r"|[-*+](?:\s|$)"         # bullet list
    r"|\d+[.)](?:\s|$)"       # ordered list
    r"|<[a-zA-Z!/]"           # HTML block-ish
    r"| {4,}|\t"              # indented code (conservative: never a finding)
    r"|(?:\*\s*){3,}$"        # hr ***
    r"|(?:-\s*){3,}$"         # hr ---
    r"|(?:_\s*){3,}$"         # hr ___
    r")"
)


def _is_delimiter_row(line: str) -> bool:
    """True for a GFM delimiter row like `|---|---|` or `|:--:|--|`."""
    cells = line.strip().strip("|").split("|")
    if not cells:
        return False
    return all(_DELIM_CELL.fullmatch(cell.strip()) for cell in cells) and any(
        "-" in cell for cell in cells
    )


def lint_lines(lines):
    """Yield (line_no, message) W1 findings for one file's lines."""
    in_fence = False
    in_table = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            in_table = False
            continue
        if in_fence:
            continue
        is_pipe_line = line.lstrip().startswith("|")
        if not in_table:
            # A table opens only at a `|`-line immediately followed by a
            # delimiter row — `|`-lines elsewhere are prose, not tables.
            if (
                is_pipe_line
                and i + 1 < len(lines)
                and _is_delimiter_row(lines[i + 1])
            ):
                in_table = True
            continue
        # Inside a table region.
        if is_pipe_line:
            continue  # a real row (the delimiter row itself can't recur)
        if not stripped:
            in_table = False  # blank line ends the table
            continue
        if _BLOCK_OPENER.match(line):
            in_table = False  # new block ends the table; not a fragment
            continue
        # Non-blank, non-pipe, non-block-opener line inside a table: the
        # row above was wrapped.
        yield (
            i + 1,
            "W1 wrapped table row: this line continues the table row above "
            "but does not start with `|` — the table renders truncated. "
            "Join this line onto the end of the previous line with a space "
            "(drop the previous line's trailing `|` first if it has one) so "
            "the text stays in the same cell; do not add a `|` separator — "
            "GFM silently drops cells beyond the header count, deleting the "
            "text",
        )
        in_table = False


def lint_paths(paths, root):
    """Lint the given markdown files; return the findings list.

    `root` is the repo root the paths live under — finding paths are
    reported relative to it (the `--root` flag changes it)."""
    findings = []
    for path in paths:
        rel = path.relative_to(root) if path.is_absolute() else path
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_no, message in lint_lines(lines):
            findings.append((str(rel), line_no, message))
    return findings


def _scope_files(root):
    docs = sorted((root / "docs").glob("**/*.md"))
    roots = [root / name for name in ROOT_DOCS if (root / name).exists()]
    return sorted(docs + roots, key=str)


def main(argv):
    args = [a for a in argv[1:] if a != "--"]
    root = ROOT
    if args and args[0] == "--root":
        if len(args) < 2:
            print("usage: docs_table_lint.py [--root PATH]", file=sys.stderr)
            return 2
        root = Path(args[1]).resolve()
        args = args[2:]
    if args:
        print("usage: docs_table_lint.py [--root PATH]", file=sys.stderr)
        return 2
    if not (root / "docs").is_dir():
        print(f"docs_table_lint: no docs/ under {root}", file=sys.stderr)
        return 2
    findings = lint_paths(_scope_files(root), root)
    for rel, line_no, message in findings:
        print(f"{rel}:{line_no}: {message}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
