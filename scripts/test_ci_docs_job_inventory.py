#!/usr/bin/env python3
"""Pin docs/CI.md's job table against .github/workflows/ci.yml's job ids.

Drift class: docs/CI.md carries the prose job table ("| Job | What it runs |"),
the first doc a contributor reads about the merge gate and the only one that
names every job in plain language — but nothing checks the table still matches
the workflow. A new job that lands without a table row (or a renamed/deleted
job that leaves a stale row) currently drifts silently; a contributor reading
stale docs then wonders why CI ran a job they never heard of, or waits on a
gate that no longer exists.

The pin asserts exact set equality in both directions:
- every job id defined under `jobs:` in ci.yml has a backticked table row, and
- every backticked first-cell name in the table is a real job id in ci.yml.

Parsing is deliberately syntactic (regexes over the two files, no YAML
dependency): ci.yml job ids are the two-space-indented `id:` lines after the
column-0 `jobs:` key (trigger names like `push:` live under `on:` before that
key, so they can never leak in); table rows are the `| `name` | ...` lines
after the `| Job | What it runs |` header.

Non-vacuity (all verified by neutering, then reverted): removing the
`png-check` row from docs/CI.md fails the missing-job direction; inserting a
bogus `fake-job` row fails the stale-row direction; adding a `fake-job:` id
under `jobs:` in ci.yml fails the missing-table direction.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CI_DOC = REPO_ROOT / "docs" / "CI.md"


def _workflow_job_ids():
    """The job ids defined under `jobs:` in ci.yml, in file order."""
    lines = CI_WORKFLOW.read_text().splitlines()
    in_jobs = False
    ids = []
    for line in lines:
        if line == "jobs:":
            in_jobs = True
            continue
        if in_jobs:
            if line and not line.startswith(" "):
                break  # next top-level key — jobs section is over
            m = re.match(r"^  ([A-Za-z0-9_-]+):$", line)
            if m:
                ids.append(m.group(1))
    assert in_jobs, "ci.yml has no top-level `jobs:` key"
    assert ids, "ci.yml defines no jobs under `jobs:`"
    return ids


def _doc_table_job_names():
    """The backticked first-cell names of docs/CI.md's job table."""
    lines = CI_DOC.read_text().splitlines()
    in_table = False
    names = []
    for line in lines:
        if re.match(r"^\| Job \| What it runs \|$", line):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break  # table is over
            m = re.match(r"^\| `([^`]+)` \|", line)
            if m:
                names.append(m.group(1))
    assert in_table, "docs/CI.md has no `| Job | What it runs |` table"
    assert names, "docs/CI.md job table has no rows"
    return names


def test_ci_docs_job_table_matches_workflow_jobs():
    """docs/CI.md's job table and ci.yml's job ids are exactly the same set,
    in either direction — a new CI job needs a table row, and a stale row
    for a removed job fails the gate."""
    workflow_ids = _workflow_job_ids()
    doc_names = _doc_table_job_names()
    missing_from_doc = [j for j in workflow_ids if j not in doc_names]
    stale_in_doc = [n for n in doc_names if n not in workflow_ids]
    assert not missing_from_doc, (
        "ci.yml jobs missing from the docs/CI.md job table: %s — add a row "
        "describing each" % missing_from_doc
    )
    assert not stale_in_doc, (
        "docs/CI.md job table rows with no such job in ci.yml: %s — update "
        "or remove the stale rows" % stale_in_doc
    )
