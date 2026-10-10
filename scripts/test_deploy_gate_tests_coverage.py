"""Pin the deploy gate's explicit test-file registration.

`deploy/components.conf` names each component's pre-deploy gate command in a
`<component>_tests` string. The proxy and confirm gates enumerate their test
*files* explicitly (rather than a whole directory), so a new `test_*.py`
file under one of those directories can land without ever being exercised
by the pre-deploy gate — the gate's test signal then silently stops covering
new tests. This is exactly the tripwire that fired on the G4 S1
implementation PR (a new test file not registered in `proxy_tests` — CI
failed, and the registration was added).

This test fails loudly, naming the file and the fix site (the component's
`<c>_tests` string in `deploy/components.conf`), in either drift direction:

  1. a `test_*.py` exists on disk under a gate-enumerated directory but is
     not named in that component's `<c>_tests` string (the CI-failing class);
  2. a `<c>_tests` string names a `.py` file that no longer exists on disk
     (stale registration — a gate command that would fail outright).

Registered test-module tokens must be repo-relative paths with no `..`
segments or absolute forms: anything else escapes the tree the pin walks,
so it fails loudly instead of walking the wrong tree. Every gate-enumerated component
also carries an exact registered-file count in EXPECTED_REGISTERED_COUNTS,
and the enumerated set itself is pinned exactly — adding a gate is a
deliberate gate-policy change that must extend the pin, not slip through a
count floor. The on-disk tree is walked once per component and the
inventory shared by the two direction checks (no duplicate walks).

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
    "proxy": 17,  # issue #1167 set 15 (incl. test_enforce_pending_dir.py); +test_readme_inventory.py; +test_deploy_inventory.py (#1235)
    "confirm": 4,
}

# Test files that intentionally run in CI but are NOT in the pre-deploy
# gate, per component. Empty today: an entry here needs a reviewed reason.
_INTENTIONAL_EXCLUSIONS = {}


def _gate_tests_vars():
    """Return {component: set of registered .py paths (relative posix)}.

    Only <c>_tests variables that register individual .py files; a gate
    that runs a whole directory (cred_ui_tests) cannot drift this way.
    Test-module tokens must be repo-relative paths with no `..` segments
    or absolute forms: anything else escapes the walk root the pin derives
    from the tokens, so it fails loudly instead of walking the wrong tree.
    (Non-test tokens in the gate command string are never walked and are
    not checked.)
    """
    text = COMPONENTS_CONF.read_text(encoding="utf-8")
    if not text.strip():
        raise AssertionError(f"{COMPONENTS_CONF} is empty")
    found = {}
    for match in re.finditer(r'^([A-Za-z][\w]*)_tests="([^"]*)"', text, re.M):
        component, value = match.group(1), match.group(2)
        py_files = set()
        for tok in value.split():
            # Only .py tokens that are test modules: a gate like cred_ui_tests
            # registers a source file (py_compile cred-ui/cred-ui.py) and runs
            # the whole directory — that form cannot drift this way, so it is
            # excluded from the pin, not pinned.
            if not (tok.endswith(".py")
                    and PurePosixPath(tok).name.startswith("test_")):
                continue
            pp = PurePosixPath(tok)
            if pp.is_absolute() or ".." in pp.parts:
                raise AssertionError(
                    f"registered token {tok!r} is not a repo-relative path — "
                    f"gate tokens in {component}_tests "
                    "(deploy/components.conf) must be repo-relative with "
                    "no '..' segments"
                )
            py_files.add(pp.as_posix())
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
    # One on-disk walk per component, computed once and shared by the two
    # drift-direction tests: walking the same tree twice per suite run is
    # pure duplicate cost. (The textual parse in _gate_tests_vars is cheap;
    # the other tests keep calling it directly.)
    _registered = None
    _on_disk = None

    @classmethod
    def setUpClass(cls):
        cls._registered = _gate_tests_vars()
        cls._on_disk = {
            component: _on_disk_test_files(_expected_dirs(registered))
            for component, registered in cls._registered.items()
        }
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

    def test_enumerated_components_match_pin_exactly(self):
        # The pin covers the exact enumerated-component set, not just a
        # floor: a new <c>_tests variable appearing in components.conf is a
        # deliberate gate-policy change, so it must extend
        # EXPECTED_REGISTERED_COUNTS with its exact registered-file count
        # (this pin), not slip through the >= 2 floor in the test above.
        gate_vars = _gate_tests_vars()
        self.assertEqual(
            set(gate_vars), set(EXPECTED_REGISTERED_COUNTS),
            "gate-enumerated components drifted from the pin — add the new "
            "<component>_tests variable's exact registered-file count to "
            "EXPECTED_REGISTERED_COUNTS in "
            "scripts/test_deploy_gate_tests_coverage.py (this pin), or "
            "remove the stale pin entry",
        )

    def test_every_on_disk_test_file_is_gate_registered(self):
        missing = []
        for component, registered in self._registered.items():
            on_disk = self._on_disk[component]
            exclusions = _INTENTIONAL_EXCLUSIONS.get(component, set())
            for path in sorted(on_disk - registered - exclusions):
                missing.append(f"{component}: {path}")
        self.assertFalse(
            missing,
            "test file(s) exist on disk but are NOT registered in the "
            "pre-deploy gate — the gate will not exercise them. Fix: add "
            "each file to that component's *_tests string in "
            "deploy/components.conf (or register a reviewed entry in "
            "_INTENTIONAL_EXCLUSIONS in this pin):\n" + "\n".join(missing),
        )

    def test_no_stale_registrations(self):
        stale = []
        for component, registered in self._registered.items():
            on_disk = self._on_disk[component]
            for path in sorted(registered - on_disk):
                stale.append(f"{component}: {path}")
        self.assertFalse(
            stale,
            "gate registration(s) point at .py files that do not exist on "
            "disk — the gate command would fail outright. Fix: remove the "
            "stale name from that component's *_tests string in "
            "deploy/components.conf:\n" + "\n".join(stale),
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
