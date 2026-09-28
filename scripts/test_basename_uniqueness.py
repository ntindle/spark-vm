"""Pin the repo-wide test contract: every `test_*.py` maps to a unique
pytest module name (basename for rootless suites, package-prefixed for
the one packaged suite).

Context: pytest's default import mode (`prepend`) imports test modules
without an `__init__.py` chain by their bare basename — and the repo
deliberately has no `__init__.py` files in its test trees (see
CONTRIBUTING.md "Running the tests", except `browser-driver/bdrive/`,
which is a real package imported as `bdrive.test_bdrive_protocol` per
pytest.ini). If two `test_*.py` files ever share a basename, pytest's
collection dies with an `import file mismatch` error — loud, but late,
and with a message that doesn't tell the contributor which two files
collide. This test fails before pytest does (plain unittest, no pytest
needed), naming every colliding file and the fix, so a contributor gets
the answer from the pin instead of decoding pytest's error. (Contrast
the testpaths drift pin, `test_pytest_ini_covers_all.py`, which closed a
genuinely *silent* drift class — unwired suites passing green.)

The walk covers the whole tree, so this enforces the repo-wide contract
(pytest.ini's comment already documents basename uniqueness across the
repo), not just the set pytest currently collects.

This test computes each file's pytest module name the way the importer
does — walking up past directories that contain `__init__.py` to build
the package prefix — and fails loudly on any collision, naming every
colliding file. A test that genuinely needs a duplicate module name does
not exist today; if one ever does, it gets an explicit, reviewed
exemption here — not silent collision.

Pure stdlib, no fixtures.
"""

import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Anti-vacuity: a broken walk (or a mass deletion) must fail this test
# instead of passing on an empty inventory. Count verified 2026-09-28
# (56 files, including this pin); the floor has headroom for legitimate
# suite deletions.
MIN_TEST_FILES = 50


def pytest_module_name(path: Path) -> str:
    """Module name pytest (importmode=prepend) would import `path` under.

    Rootless test files import by basename. A file inside a chain of
    directories that each contain `__init__.py` imports with the package
    prefix (today only `browser-driver/bdrive/` is such a package).
    """
    parts = [path.stem]
    parent = path.parent
    # NOTE: the `parent != ROOT` guard is a deliberate simplification, not
    # exact pytest parity: if the repo root itself ever gained an
    # `__init__.py`, pytest would keep walking and prefix the repo dir
    # name, while this helper stops here. Acceptable — a root-level
    # `__init__.py` would break far more than this pin.
    while (parent / "__init__.py").exists() and parent != ROOT:
        parts.append(parent.name)
        parent = parent.parent
    return ".".join(reversed(parts))


def all_test_files():
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            d for d in dirnames if d not in (".git", "__pycache__")
        ]
        for name in filenames:
            if name.startswith("test_") and name.endswith(".py"):
                found.append(Path(dirpath) / name)
    return found


class TestModuleNamesUnique(unittest.TestCase):
    def test_no_duplicate_module_names(self):
        files = all_test_files()
        self.assertGreaterEqual(
            len(files),
            MIN_TEST_FILES,
            f"only {len(files)} test files found — the walk is broken or "
            "the inventory shrank unexpectedly",
        )
        by_module = {}
        for f in files:
            by_module.setdefault(pytest_module_name(f), []).append(
                f.relative_to(ROOT).as_posix()
            )
        collisions = {
            mod: paths for mod, paths in by_module.items() if len(paths) > 1
        }
        self.assertEqual(
            collisions,
            {},
            "duplicate pytest module names — pytest's collection dies with "
            "an `import file mismatch` error on these (rename one of the "
            "files):\n"
            + "\n".join(
                f"  {mod}:\n" + "\n".join(f"    - {p}" for p in sorted(paths))
                for mod, paths in sorted(collisions.items())
            ),
        )

    def test_module_name_computation_is_anchored(self):
        # Guards the computation itself: if this drifts from pytest's
        # import behavior, the uniqueness test above becomes vacuous.
        # The two known shapes today: a rootless suite and the one real
        # package (browser-driver/bdrive/__init__.py).
        rootless = ROOT / "scripts" / "test_pytest_ini_covers_all.py"
        packaged = ROOT / "browser-driver" / "bdrive" / "test_bdrive_protocol.py"
        # The computation is pure path-string math, so anchor the files
        # too — a deleted anchor file must fail here, not pass vacuously.
        self.assertTrue(rootless.exists(), f"anchor file missing: {rootless}")
        self.assertTrue(packaged.exists(), f"anchor file missing: {packaged}")
        self.assertEqual(pytest_module_name(rootless), "test_pytest_ini_covers_all")
        self.assertEqual(
            pytest_module_name(packaged), "bdrive.test_bdrive_protocol"
        )


if __name__ == "__main__":
    unittest.main()
