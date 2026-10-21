"""Execution coverage for the wired event_emit call sites in
deploy/toolset-update.sh (#1649 S2 slice 2).

Mirrors deploy/test_wired_emit_execution.py (the repo updater's slice-1
coverage): text-only assertions are blind to quoting/expansion bugs in a
wired emit line, so this module extracts every `event_emit` line verbatim
from toolset-update.sh, evaluates it under `set -u` with stubbed
variables, and asserts the emitted journal row is valid JSONL with the
expected shape.

Drop into deploy/ and run:  python3 -m pytest deploy/test_toolset_wired_emit_execution.py -q
"""

import json
import os
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIB = os.path.join(REPO, "deploy", "event-journal.sh")
TOOLSET_UPDATE = os.path.join(REPO, "deploy", "toolset-update.sh")

# Stub values for every variable a wired emit line may reference.
STUBS = {
    "trig": "",
    "failed_comps": "cua-driver",
    "layer": "cua-driver",
    "snapdir": "/tmp/toolset-test-snapshots/20261020-000000-1-abcd",
}
# Second-pass overrides: sites referencing $trig get an extra run with
# the manual-trigger value (exercises the trigger path at real sites).
OVERRIDES = {
    "trig": ',"trigger":"manual"',
}

# The wired set, pinned per line: (kind, outcome). A slice that adds or
# removes a wired site updates this table deliberately — the wiring is
# the fleet-facing contract.
EXPECTED_SITES = {
    "check/skipped-frozen": "local failure-freeze",
    "check/deferred-arc": "idle-gate jobs-active deferral",
    "deploy/started": "cmd_update run start (non-dry-run)",
    "deploy/precheck-fail": "pre-update snapshot failure",
    "deploy/succeeded": "cmd_update success",
    "deploy/failed": "cmd_update layer failure",
    "rollback/rolled-back": "cmd_rollback success",
    "rollback/rollback-failed": "cmd_rollback failure",
}


def _emit_sites():
    sites = []
    with open(TOOLSET_UPDATE) as f:
        for i, line in enumerate(f, start=1):
            s = line.strip()
            if s.startswith("event_emit "):
                sites.append((i, s))
    return sites


def _cases():
    cases = []
    for lineno, line in _emit_sites():
        cases.append(pytest.param(lineno, line, "default", id=f"L{lineno}"))
        for var, val in OVERRIDES.items():
            if f"${var}" in line or "${" + var in line:
                cases.append(
                    pytest.param(lineno, line, f"{var}={val}", id=f"L{lineno}-{var}")
                )
    return cases


def test_wired_emit_set_matches_contract():
    """The pinned (kind, outcome) table covers exactly the wired sites."""
    sites = _emit_sites()
    assert len(sites) == len(EXPECTED_SITES), (
        f"wired site count changed: {len(sites)} sites vs "
        f"{len(EXPECTED_SITES)} pinned — update EXPECTED_SITES deliberately"
    )
    found = set()
    for lineno, line in sites:
        parts = line.split()
        kind, outcome = parts[3], parts[4]
        found.add(f"{kind}/{outcome}")
    assert found == set(EXPECTED_SITES), (
        f"wired set drifted: extra={found - set(EXPECTED_SITES)} "
        f"missing={set(EXPECTED_SITES) - found}"
    )


@pytest.mark.parametrize("lineno,line,variant", _cases())
def test_wired_emit_line_executes(tmp_path, lineno, line, variant):
    journal = os.path.join(str(tmp_path), "update-events.jsonl")
    env = dict(os.environ, EVENT_JOURNAL=journal, **STUBS)
    if "=" in variant:
        var, val = variant.split("=", 1)
        env[var] = val
    # set -u: a newly referenced-but-unstubbed variable fails loudly here
    # instead of silently expanding to "".
    r = subprocess.run(
        ["bash", "-c", f"set -u; source {LIB}; {line}; echo RC=$?"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, f"L{lineno}: {r.stderr}"
    assert "RC=0" in r.stdout, f"L{lineno}: emit failed: {r.stdout} {r.stderr}"
    assert r.stderr == "", f"L{lineno}: emit must be silent on success: {r.stderr}"
    with open(journal) as f:
        raw = f.read()
    rows = [json.loads(l) for l in raw.splitlines() if l.strip()]
    assert len(rows) == 1, f"L{lineno}: expected one JSONL row, got {len(rows)}"
    row = rows[0]
    assert row["source"] == "toolset-update" and row["component"] == "toolset-cua-driver"
    parts = line.split()
    assert row["kind"] == parts[3], f"L{lineno}: kind drift"
    assert row["outcome"] == parts[4], f"L{lineno}: outcome drift"
    # Trigger dedupe: exactly one "trigger" key even on override sites.
    assert raw.count('"trigger"') == 1, f"L{lineno}: duplicate/missing trigger key"
    assert row["trigger"] in ("scheduled", "manual", "extra-inputs", "freeze", "gate"), (
        f"L{lineno}: trigger outside §2 enum: {row['trigger']}"
    )
