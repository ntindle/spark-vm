#!/usr/bin/env python3
"""Pin scripts/README.md's inventories against the code they describe.

Two drift classes, both cheap to introduce by accident in a component
whose whole job is keeping the project's rituals honest:

1. **Gate-step names** — scripts/README.md documents local-gate.sh's six
   checks in prose, but the script's actual `step "..."` names are free
   text echoed to the terminal. A step renamed in the script (or a step
   added without a docs touch) silently desyncs the README's description.
   The `<!-- gate-steps:start -->` block in the README is the
   machine-readable inventory; this test pins it against the script.
2. **Test-file inventory** — the README's test-inventory table names
   every test_*.py in scripts/. A new pin test that lands without a table
   row (or a renamed/deleted file that leaves a stale row) currently
   drifts silently; this test pins the table against the directory.

Non-vacuity: rename a step in local-gate.sh, or add/rename/remove a
test_*.py without updating the README, and the corresponding test fails
(verified by hand during development).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
README = SCRIPTS_DIR / "README.md"
GATE = SCRIPTS_DIR / "local-gate.sh"


def _readme_gate_steps():
    text = README.read_text()
    m = re.search(
        r"<!-- gate-steps:start -->\n(.*?)\n<!-- gate-steps:end -->",
        text,
        re.S,
    )
    assert m, "scripts/README.md gate-steps inventory block missing"
    return [line.strip() for line in m.group(1).splitlines() if line.strip()]


def _script_step_names():
    src = GATE.read_text()
    steps = re.findall(r'^\s*step "([^"]+)"', src, re.MULTILINE)
    assert steps, "local-gate.sh has no step \"...\" calls"
    # The python-tests step is emitted in three forms (real run + two
    # loud skips: --quick, docs-only diff). Strip the skip suffixes and
    # dedupe so the pin compares the step set, not the skip variants.
    bases = [re.sub(r" \(skipped.*$", "", s) for s in steps]
    return list(dict.fromkeys(bases))


def test_readme_gate_steps_match_local_gate():
    """The README's six documented steps are exactly local-gate.sh's."""
    documented = _readme_gate_steps()
    assert len(documented) == 6, (
        "gate-steps inventory drift: expected the six merge-gate steps, "
        "got %d: %s" % (len(documented), documented)
    )
    actual = _script_step_names()
    assert actual == documented, (
        "local-gate.sh steps drifted from scripts/README.md: "
        "script=%s README=%s" % (actual, documented)
    )


def _readme_test_inventory():
    text = README.read_text()
    rows = re.findall(r"^\|\s*`(test_[a-z0-9_]+\.py)`\s*\|", text, re.MULTILINE)
    assert rows, "scripts/README.md test-file inventory table missing"
    assert len(rows) == len(set(rows)), "duplicate rows in the inventory table"
    return set(rows)


def test_readme_names_every_test_file():
    """Every scripts/test_*.py is named in the README inventory table."""
    documented = _readme_test_inventory()
    on_disk = {p.name for p in SCRIPTS_DIR.glob("test_*.py")}
    assert on_disk, "no test_*.py files found in scripts/"
    missing = sorted(on_disk - documented)
    assert not missing, (
        "test files not named in scripts/README.md's inventory table: %s "
        "-- add a row" % ", ".join(missing)
    )
    stale = sorted(documented - on_disk)
    assert not stale, (
        "inventory table rows with no file on disk: %s -- remove the row"
        % ", ".join(stale)
    )
