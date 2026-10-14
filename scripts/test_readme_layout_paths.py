#!/usr/bin/env python3
"""README repo-layout table: every listed path must exist, with the right kind.

The "## Repo layout" table is the newcomer's map of the checkout: a path
listed there must resolve. A trailing slash means directory, no slash
means file — the distinction is the whole point of the check. It caught
a real drift: the table listed `cred/` (a directory that never existed)
while `cred` is a root-level single-file executable and `credlib/` is
the library directory. A reader following the old row looked for a
directory that isn't there.

Only the Path column (first cell) is checked: description cells carry
prose references (commands, routes, file names in passing) that are not
path claims. The row-count floor guards against vacuity-by-deletion —
dropping the table must fail, not pass.
"""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(REPO_ROOT, "README.md")

_BACKTICK_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\]\(([^)]+)\)")


def _layout_rows():
    with open(README_PATH, encoding="utf-8") as f:
        lines = f.read().splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.strip() == "## Repo layout"
        )
    except StopIteration:
        raise AssertionError(
            "README has no '## Repo layout' section; the layout table "
            "may have been deleted"
        )
    rows = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            rows.append(line)
    return rows


def _first_cell(row):
    # | Path | What it is | -> " Path "
    return row.split("|")[1]


def test_readme_layout_paths_exist_with_right_kind():
    rows = _layout_rows()
    data_rows = [r for r in rows if "`" in _first_cell(r)]
    assert len(data_rows) >= 15, (
        "README repo-layout table has only %d data rows; the table may "
        "have been deleted or gutted" % len(data_rows)
    )
    checked = []
    failures = []
    for row in data_rows:
        cell = _first_cell(row)
        for token in _BACKTICK_RE.findall(cell):
            checked.append(token)
            path = os.path.join(REPO_ROOT, token.rstrip("/"))
            if token.endswith("/"):
                if not os.path.isdir(path):
                    failures.append(
                        "%r claims a directory but %s is not one"
                        % (token, token.rstrip("/"))
                    )
            else:
                if not os.path.isfile(path):
                    failures.append(
                        "%r claims a file but %s is not one"
                        % (token, token)
                    )
        for target in _LINK_RE.findall(cell):
            target = target.split("#", 1)[0]
            checked.append(target)
            if not os.path.isfile(os.path.join(REPO_ROOT, target)):
                failures.append(
                    "layout-table link target %r does not exist" % target
                )
    assert checked, "no paths found in the README repo-layout table"
    assert not failures, (
        "README repo-layout table lists paths that do not resolve: %s"
        % "; ".join(failures)
    )
