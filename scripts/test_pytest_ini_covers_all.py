"""Pin the repo-wide test contract: every `test_*.py` must be reachable from
the repo-root one-liner (`python3 -m pytest`, `pytest.ini` `testpaths`).

Context: CI's merge gate used to name test files one by one in
`.github/workflows/ci.yml`, so a new suite could land without ever running
in CI — silently unwired. CI now runs the one-liner, which makes
`pytest.ini`'s `testpaths` the single inventory of suites. The residual
drift class is a `test_*.py` added under a directory `testpaths` doesn't
list (a new component subtree, a stray file at the root). This test fails
loudly on that, naming the file, so the inventory can never drift again.

Pure stdlib, no fixtures: parse `pytest.ini` with configparser, walk the
tree for `test_*.py` (skipping `.git`), and require each to sit under one
of the listed testpaths. A file that must NOT run in CI does not exist
today; if one ever does, it gets an explicit, reviewed exemption here —
not silent omission.
"""

import configparser
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTEST_INI = ROOT / "pytest.ini"


def testpaths():
    parser = configparser.ConfigParser()
    parser.read(PYTEST_INI)
    raw = parser.get("pytest", "testpaths")
    paths = [line.strip() for line in raw.splitlines() if line.strip()]
    if not paths:
        raise AssertionError("pytest.ini [pytest] testpaths is empty")
    return [ROOT / p for p in paths]


def all_test_files():
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            if name.startswith("test_") and name.endswith(".py"):
                found.append(Path(dirpath) / name)
    if not found:
        raise AssertionError("no test_*.py files found — the walk is broken")
    return found


class TestPytestIniCoversAll(unittest.TestCase):
    def test_every_test_file_is_under_testpaths(self):
        paths = testpaths()
        uncovered = [
            f.relative_to(ROOT).as_posix()
            for f in all_test_files()
            if not any(
                f == p or p in f.parents  # the file itself, or inside the dir
                for p in paths
            )
        ]
        self.assertEqual(
            uncovered,
            [],
            "test files not reachable from the repo-root one-liner "
            "(add their directory to pytest.ini testpaths, or exempt "
            "explicitly here with a reviewed reason):\n"
            + "\n".join(f"  {u}" for u in uncovered),
        )

    def test_testpaths_entries_exist(self):
        missing = [str(p.relative_to(ROOT)) for p in testpaths() if not p.exists()]
        self.assertEqual(
            missing,
            [],
            "pytest.ini testpaths lists directories that do not exist:\n"
            + "\n".join(f"  {m}" for m in missing),
        )


if __name__ == "__main__":
    unittest.main()
