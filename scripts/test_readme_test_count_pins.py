"""Pin test: "(N tests)" claims in READMEs/docs must match the test files.

Drift class: component READMEs and docs state how many tests a test file
holds ("`test_foo.py` (N tests)"), and the count goes stale when tests are
added, removed, or consolidated — or is wrong at write time (four of the
claims pinned here were already stale the day they were written). A stale
count misleads contributors about suite size and erodes trust in the docs.

Contract (extends the deploy/plane-cron precedent,
`test_readme_test_count_matches` in
`deploy/plane-cron/test_verify_plane_cron.py`):
- Each registry entry names a doc, a test file, and an anchor regex with
  exactly one capture group for the stated count. The anchor must match
  exactly once in the doc, so a second mention can never shadow the pin.
- The count is the number of top-level `test_*` functions in the test
  file, counted via `ast` (not regex). This is test *functions*, not
  parametrized expansions: a parametrized test counts once, and adding
  parametrization does not change the pinned number (unlike the
  plane-cron pin, which forbids parametrization outright — several files
  pinned here already parametrize).
- Counts are top-level only, matching the plane-cron precedent. All files
  pinned here are flat today (no test classes); if a class-based suite is
  ever added, update the counting function, not just the number.

To pin a new claim: add one registry entry. To change a suite: update the
stated count in the doc in the same PR — CI fails otherwise.
"""

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (doc path relative to repo root, test file path relative to repo root,
#  anchor regex with exactly one capture group for the stated count)
_CLAIMS = [
    (
        "hosted/README.md",
        "hosted/test_push_crypto.py",
        r"`test_push_crypto\.py` \((\d+) tests\)",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_payload.py",
        r"`test_push_payload\.py` \((\d+) tests",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_sender.py",
        r"`test_push_sender\.py` \((\d+) tests",
    ),
    (
        "hosted/README.md",
        "hosted/test_push_sweep.py",
        r"`test_push_sweep\.py` \((\d+) tests",
    ),
    (
        "harness/README.md",
        "harness/test_key_registry.py",
        r"`test_key_registry\.py` \((\d+) tests",
    ),
    (
        "docs/PHONE_HOME_S6_READINESS_2026-10-11.md",
        "pairing/test_phone_home.py",
        r"`pairing/test_phone_home\.py` \((\d+) tests\)",
    ),
    (
        "docs/D9_PUSH_SWEEP_OPERATOR_GUIDE.md",
        "hosted/test_push_sweep.py",
        # The count sits on the line after the file reference, which itself
        # sits inside a `python3 -m pytest ...` command span (no opening
        # backtick before the path).
        r"hosted/test_push_sweep\.py`\s*\((\d+) tests",
    ),
]


def _test_function_count(test_path: Path) -> int:
    tree = ast.parse(test_path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )


def test_readme_test_count_claims_match():
    failures = []
    for doc_rel, test_rel, anchor in _CLAIMS:
        doc = REPO / doc_rel
        test_file = REPO / test_rel
        assert doc.is_file(), f"pinned doc missing: {doc_rel}"
        assert test_file.is_file(), f"pinned test file missing: {test_rel}"
        matches = re.findall(anchor, doc.read_text(encoding="utf-8"))
        if len(matches) != 1:
            failures.append(
                f"{doc_rel}: anchor for {test_rel} matched "
                f"{len(matches)} times (want exactly 1)"
            )
            continue
        stated = int(matches[0])
        actual = _test_function_count(test_file)
        if stated != actual:
            failures.append(
                f"{doc_rel} says {test_rel} has {stated} tests; "
                f"the file holds {actual} test functions"
            )
    assert not failures, (
        "stale test-count claims:\n" + "\n".join(failures)
    )
