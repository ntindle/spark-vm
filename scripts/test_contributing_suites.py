"""Pin CONTRIBUTING's component table to pytest.ini's testpaths.

CONTRIBUTING's "Running the tests" section carries a per-component table
whose Component column enumerates the suite directories. The old table
enumerated individual test *files* and drifted badly: proxy/ grew from 3
listed suites to 13 real ones, and scripts/ claimed only test_sparkvm_version
while pillow — a real test dependency — went unlisted. The table now
enumerates directories, and this pin fails loudly if the table and
pytest.ini's testpaths disagree in either direction, so the contributor
docs can't drift from the real inventory again.

Pure stdlib, no fixtures: parse pytest.ini with configparser, scan
CONTRIBUTING for the per-component table rows.

Run from the repo root:  python3 -m pytest scripts/test_contributing_suites.py -q
"""

import configparser
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
PYTEST_INI = ROOT / "pytest.ini"
MIN_COMPONENTS = 10  # anti-vacuity floor: the parse must find the real table


def get_testpaths():
    parser = configparser.ConfigParser()
    parser.read(PYTEST_INI)
    raw = parser.get("pytest", "testpaths")
    paths = [line.strip().rstrip("/") for line in raw.splitlines() if line.strip()]
    if not paths:
        raise AssertionError("pytest.ini [pytest] testpaths is empty")
    return paths


def get_table_components():
    text = CONTRIBUTING.read_text(encoding="utf-8")
    rows = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("Per-component dependency notes"):
            in_section = True
            continue
        if not in_section:
            continue
        if line.startswith("|"):
            rows.append(line)
        elif rows:
            break  # first non-table line ends the table
    # Data rows only: skip the header row, and the `|---|---|` separator
    # row (whose first cell is all dashes).
    comps = []
    for row in rows:
        cell = row.split("|")[1].strip()
        if cell.lower() == "component" or set(cell) <= {"-", ":", " "}:
            continue
        m = re.fullmatch(r"`([^`]+)`", cell)
        if not m:
            raise AssertionError(f"component cell is not a single backtick span: {row!r}")
        comps.append(m.group(1).rstrip("/"))
    if len(comps) < MIN_COMPONENTS:
        raise AssertionError(
            f"parsed only {len(comps)} components from the CONTRIBUTING table "
            "— the parse is broken, not the docs"
        )
    return comps


class TestContributingSuites(unittest.TestCase):
    def test_table_matches_testpaths(self):
        testpaths = get_testpaths()
        comps = get_table_components()
        missing = [p for p in testpaths if p not in comps]
        stale = [c for c in comps if c not in testpaths]
        assert not missing, f"testpaths dirs missing from the CONTRIBUTING table: {missing}"
        assert not stale, f"CONTRIBUTING table lists dirs not in testpaths: {stale}"

    def test_table_component_cells_are_unique(self):
        comps = get_table_components()
        assert len(comps) == len(set(comps)), f"duplicate component rows: {comps}"
