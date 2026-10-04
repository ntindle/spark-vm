#!/usr/bin/env python3
"""Docs-index coverage: every published doc must be reachable from the docs index.

docs/README.md is the reader's entry point into docs/; a document that ships
without an index row is effectively invisible. This test fails when a new
docs/*.md file is added without a corresponding index row, so the coverage
invariant ("every doc indexed") holds without manual audits.

The index itself (docs/README.md) is the entry point, not an entry — it is
exempt.
"""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(REPO_ROOT, "docs")
INDEX_PATH = os.path.join(DOCS_DIR, "README.md")

# The index entry point itself needs no index row.
EXEMPT = {"README.md"}

# Matches markdown links whose target is a docs-local .md file
# ([NAME](NAME.md), possibly with a #anchor).
_LINK_RE = re.compile(r"\]\(([A-Za-z0-9_.\-]+\.md)(?:#[^)]*)?\)")


def _indexed_names():
    with open(INDEX_PATH, encoding="utf-8") as f:
        text = f.read()
    return set(_LINK_RE.findall(text))


def test_docs_index_covers_every_doc():
    indexed = _indexed_names()
    missing = []
    for name in sorted(os.listdir(DOCS_DIR)):
        if not name.endswith(".md") or name in EXEMPT:
            continue
        if not os.path.isfile(os.path.join(DOCS_DIR, name)):
            continue
        if name not in indexed:
            missing.append(name)
    assert not missing, (
        "docs/*.md files not indexed in docs/README.md: %s -- "
        "add a row to the index table"
        % ", ".join(missing)
    )


def test_docs_index_links_resolve():
    broken = []
    for name in sorted(_indexed_names()):
        if not os.path.isfile(os.path.join(DOCS_DIR, name)):
            broken.append(name)
    assert not broken, (
        "docs/README.md links to missing docs: %s" % ", ".join(broken)
    )
