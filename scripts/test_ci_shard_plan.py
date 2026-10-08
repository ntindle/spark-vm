"""Pin the CI shard inventory: every `pytest.ini` testpaths dir runs in
exactly one CI shard (issue #1138).

Context: `.github/workflows/ci.yml` fans the `python tests` gate out into
one matrix job per shard, with the inventory defined in
`scripts/ci_shard_plan.py` (the `plan` job emits the matrix from it).
The residual drift class is a new suite landing in `pytest.ini`
`testpaths` without a shard (silently unwired from CI — the same class
`scripts/test_pytest_ini_covers_all.py` guards for the local one-liner),
or a shard naming a directory `testpaths` no longer lists (a stale shard
that would make pytest fail loud with "file or directory not found", but
a pin catches it before CI does).

Pure stdlib, no fixtures: load the plan module by path (repo convention —
see scripts/test_lint_changelog_ritual.py), parse `pytest.ini` with
configparser, and require a bijection between testpaths dirs and shard
members. Plain unittest so it runs even where pytest's collection is the
thing under test.
"""

import configparser
import importlib.util
import os
import re
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent
PYTEST_INI = ROOT / "pytest.ini"
_PLAN_PATH = _HERE / "ci_shard_plan.py"

_SHARD_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _load_plan():
    spec = importlib.util.spec_from_file_location("ci_shard_plan", _PLAN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _testpaths():
    parser = configparser.ConfigParser()
    parser.read(PYTEST_INI)
    raw = parser.get("pytest", "testpaths")
    return [line.strip() for line in raw.splitlines() if line.strip()]


class TestCiShardPlanCoversAll(unittest.TestCase):
    def test_every_testpaths_dir_is_in_exactly_one_shard(self):
        plan = _load_plan()
        counts = {}
        for shard, dirs in plan.SHARDS.items():
            for d in dirs:
                counts[d] = counts.get(d, 0) + 1
        missing = [p for p in _testpaths() if counts.get(p, 0) == 0]
        duplicated = sorted(d for d, c in counts.items() if c > 1)
        self.assertEqual(
            missing,
            [],
            "testpaths dirs with no CI shard (they would never run in CI):\n"
            + "\n".join(f"  {m}" for m in missing),
        )
        self.assertEqual(
            duplicated,
            [],
            "dirs claimed by more than one shard (they would run twice):\n"
            + "\n".join(f"  {d}" for d in duplicated),
        )

    def test_no_shard_names_dirs_outside_testpaths(self):
        plan = _load_plan()
        paths = set(_testpaths())
        stray = sorted(
            {d for dirs in plan.SHARDS.values() for d in dirs} - paths
        )
        self.assertEqual(
            stray,
            [],
            "shard dirs not in pytest.ini testpaths (pytest would fail\n"
            "with 'file or directory not found' — remove or fix the shard):\n"
            + "\n".join(f"  {s}" for s in stray),
        )

    def test_shard_inventory_shape(self):
        plan = _load_plan()
        self.assertTrue(
            plan.SHARDS, "ci_shard_plan.SHARDS is empty — CI would get an empty matrix"
        )
        for shard, dirs in plan.SHARDS.items():
            self.assertRegex(
                shard,
                _SHARD_NAME_RE,
                f"shard name {shard!r} is not identifier-safe "
                "(it lands in the check name as `python tests (<shard>)`)",
            )
            self.assertTrue(
                dirs, f"shard {shard!r} has no dirs — an empty shard is a dead CI job"
            )
            self.assertEqual(
                len(dirs),
                len(set(dirs)),
                f"shard {shard!r} lists a dir twice",
            )

    def test_matrix_payload_round_trips(self):
        plan = _load_plan()
        matrix = plan.shard_matrix()
        self.assertEqual(
            set(matrix),
            {"include"},
            "the plan job does fromJson(needs.plan.outputs.matrix) with "
            "matrix.include — any other top-level key is silently ignored",
        )
        seen = set()
        for entry in matrix["include"]:
            self.assertEqual(set(entry), {"shard", "dirs", "root_tests"})
            self.assertNotIn(entry["shard"], seen)
            seen.add(entry["shard"])
            self.assertEqual(
                entry["dirs"].split(),
                plan.SHARDS[entry["shard"]],
                "the `dirs` string must round-trip to the shard's dir list "
                "— the workflow passes it straight to `pytest -q ${{ matrix.dirs }}`",
            )
            self.assertIsInstance(entry["root_tests"], bool)
        self.assertEqual(seen, set(plan.SHARDS))

    def test_exactly_one_shard_runs_the_sudo_root_tests(self):
        plan = _load_plan()
        flagged = [
            entry["shard"]
            for entry in plan.shard_matrix()["include"]
            if entry["root_tests"]
        ]
        self.assertEqual(
            flagged,
            [s for s, dirs in plan.SHARDS.items() if "proxy" in dirs],
            "the root_tests flag must mark exactly the shard holding proxy/ "
            "(the workflow runs the sudo install-safety tests on that shard; "
            "a rename that drops the flag would silently skip them)",
        )
        self.assertEqual(len(flagged), 1)

    def test_workflow_consumes_the_root_tests_flag(self):
        # The plan emits root_tests per shard; the workflow must actually
        # gate the sudo root-tests step on it. If that wiring is deleted,
        # every pin above still passes while the sudo install-safety tests
        # silently never run — so the wiring itself is pinned here too.
        ci_yml = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertIn(
            "matrix.root_tests",
            ci_yml.read_text(),
            "ci.yml must gate the proxy install-safety root-tests step on "
            "the plan's data-driven matrix.root_tests flag (never a "
            "hardcoded shard name) — see scripts/ci_shard_plan.py",
        )


if __name__ == "__main__":
    unittest.main()
