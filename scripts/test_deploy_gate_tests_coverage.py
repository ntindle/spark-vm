"""Pin the deploy gate's explicit test-file registration.

`deploy/components.conf` names each component's pre-deploy gate command in a
`<component>_tests` string. The proxy and confirm gates enumerate their test
*files* explicitly (rather than a whole directory), so a new `test_*.py`
file under one of those directories can land without ever being exercised
by the pre-deploy gate — the gate's test signal then silently stops covering
new tests. This is exactly the tripwire that fired on the G4 S1
implementation PR (a new test file not registered in `proxy_tests` — CI
failed, and the registration was added).

This test fails loudly, naming the file, in either drift direction:

  1. a `test_*.py` exists on disk under a gate-enumerated directory but is
     not named in that component's `<c>_tests` string (the CI-failing class);
  2. a `<c>_tests` string names a `.py` file that no longer exists on disk
     (stale registration — a gate command that would fail outright).

A component gate that names a whole directory (e.g. `cred_ui_tests` runs
`pytest cred-ui/tests/`) cannot drift this way, so only `<c>_tests`
variables that register individual `.py` files are pinned.

Intentional exclusions do not exist today. If one ever does (a test file
that must run in CI but must NOT run in the pre-deploy gate), it gets an
explicit, reviewed entry in `_INTENTIONAL_EXCLUSIONS` with a reason — never
silent omission.

Pure stdlib, no fixtures: parse `deploy/components.conf` textually (never
source the shell — it is deploy machinery), walk the enumerated
directories, and compare sets. Run from the repo root:
`python3 -m pytest scripts/test_deploy_gate_tests_coverage.py -q`.
"""

import os
import re
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS_CONF = ROOT / "deploy" / "components.conf"

# Exact registered-file counts per gate-enumerated component, as shipped.
# Registering or removing a test file is a deliberate gate-policy change:
# it must edit this pin, not slip through a range check.
EXPECTED_REGISTERED_COUNTS = {
    "proxy": 14,
    "confirm": 4,
}

# Test files that intentionally run in CI but are NOT in the pre-deploy
# gate, per component. Empty today: an entry here needs a reviewed reason.
_INTENTIONAL_EXCLUSIONS = {}


def _gate_tests_vars():
    """Return {component: set of registered .py paths (relative posix)}.

    Only <c>_tests variables that register individual .py files; a gate
    that runs a whole directory (cred_ui_tests) cannot drift this way.
    """
    text = COMPONENTS_CONF.read_text(encoding="utf-8")
    if not text.strip():
        raise AssertionError(f"{COMPONENTS_CONF} is empty")
    found = {}
    for match in re.finditer(r'^([A-Za-z][\w]*)_tests="([^"]*)"', text, re.M):
        component, value = match.group(1), match.group(2)
        # Only .py tokens that are test modules: a gate like cred_ui_tests
        # registers a source file (py_compile cred-ui/cred-ui.py) and runs
        # the whole directory — that form cannot drift this way, so it is
        # excluded from the pin, not pinned.
        py_files = {
            PurePosixPath(tok).as_posix()
            for tok in value.split()
            if tok.endswith(".py")
            and PurePosixPath(tok).name.startswith("test_")
        }
        if py_files:
            found[component] = py_files
    return found


def _on_disk_test_files(dirs):
    """Recursively collect test_*.py under dirs as relative posix paths."""
    found = set()
    for d in dirs:
        for dirpath, dirnames, filenames in os.walk(ROOT / d):
            dirnames[:] = [dn for dn in dirnames if dn != "__pycache__"]
            for name in filenames:
                if name.startswith("test_") and name.endswith(".py"):
                    found.add(
                        (Path(dirpath) / name).relative_to(ROOT).as_posix()
                    )
    return found


def _expected_dirs(registered):
    """Directories a gate-enumerated component covers, from its tokens."""
    dirs = set()
    for tok in registered:
        parent = str(PurePosixPath(tok).parent)
        if parent in ("", "."):
            raise AssertionError(
                f"registered token {tok!r} has no directory — "
                "the gate tokens must be repo-relative paths"
            )
        dirs.add(parent)
    return dirs


class TestDeployGateTestsCoverage(unittest.TestCase):
    def test_gate_vars_are_enumerable(self):
        gate_vars = _gate_tests_vars()
        if not gate_vars:
            self.fail(
                "no <component>_tests variables registering .py files found "
                f"in {COMPONENTS_CONF} — the parse is broken, not the gate"
            )
        # Anti-vacuity: the pin must actually enumerate the proxy + confirm
        # gates; passing on an empty inventory would be a silent no-op.
        self.assertGreaterEqual(
            len(gate_vars), 2,
            f"expected >= 2 gate-enumerated components, found {sorted(gate_vars)}",
        )

    def test_registered_counts_are_exact(self):
        gate_vars = _gate_tests_vars()
        for component, expected in EXPECTED_REGISTERED_COUNTS.items():
            actual = gate_vars.get(component)
            self.assertIsNotNone(
                actual,
                f"no .py registrations found for the {component} gate — "
                "the gate was rewritten to a directory form, so this pin "
                "must be retired or re-scoped, not silently skipped",
            )
            # Pin the exact count: adding or removing a registered test file
            # is a deliberate gate-policy change, not a tune-by-feel tweak,
            # so it must edit this assertion, not slip through a range check.
            self.assertEqual(
                len(actual), expected,
                f"{component} gate registers {len(actual)} files, pin "
                f"expects {expected} — update both this pin and "
                "deploy/components.conf together",
            )

    def test_every_on_disk_test_file_is_gate_registered(self):
        gate_vars = _gate_tests_vars()
        missing = []
        for component, registered in gate_vars.items():
            on_disk = _on_disk_test_files(_expected_dirs(registered))
            exclusions = _INTENTIONAL_EXCLUSIONS.get(component, set())
            for path in sorted(on_disk - registered - exclusions):
                missing.append(f"{component}: {path}")
        self.assertEqual(
            missing, [],
            "test file(s) exist on disk but are NOT registered in the "
            "pre-deploy gate — the gate will not exercise them:\n"
            + "\n".join(missing),
        )

    def test_no_stale_registrations(self):
        gate_vars = _gate_tests_vars()
        stale = []
        for component, registered in gate_vars.items():
            on_disk = _on_disk_test_files(_expected_dirs(registered))
            for path in sorted(registered - on_disk):
                stale.append(f"{component}: {path}")
        self.assertEqual(
            stale, [],
            "gate registration(s) point at .py files that do not exist on "
            "disk — the gate command would fail outright:\n" + "\n".join(stale),
        )

    def test_registered_floor(self):
        # Anti-vacuity across the whole pin: the inventory must keep covering
        # the shipped gate surface (14 proxy + 4 confirm = 18 today).
        total = sum(len(reg) for reg in _gate_tests_vars().values())
        self.assertGreaterEqual(
            total, 17,
            f"only {total} gate-registered test files — the pin's inventory "
            "shrank, which means the parse broke or the gate was gutted",
        )


if __name__ == "__main__":
    unittest.main()
