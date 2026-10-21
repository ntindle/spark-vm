"""SUGGESTED (not yet in repo): execution coverage for the wired event_emit
call sites in deploy/auto-deploy.sh.

QA finding (2026-10-20, role QA): deploy/test_event_journal.py verifies the
wiring with TEXT assertions only (the WIRING table + _emit_after_audit). No
test ever executes a wired emit line, so a quoting/expansion bug in any of
the 17 call sites — or a regression at the dynamic touch-verdict site
(auto-deploy.sh ~L1478, whose audit line is interpolated and therefore
invisible to the WIRING table; proven by mutation: breaking its outcome
kept the suite green) — ships silently.

This module extracts every `event_emit` line verbatim from
auto-deploy.sh, evaluates it under `set -u` with stubbed variables, and
asserts the emitted journal row is valid JSONL with the expected shape.
Drop into deploy/ and run:  python3 -m pytest deploy/test_wired_emit_execution.py -q

Verified 2026-10-20 against hourly/event-journal-s1-20261020-2059 @ 33a12ed5:
17/17 sites execute cleanly (rc 0, silent stderr, one valid JSON row).
"""

import json
import os
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIB = os.path.join(REPO, "deploy", "event-journal.sh")
AUTO_DEPLOY = os.path.join(REPO, "deploy", "auto-deploy.sh")

# Stub values for every variable a wired emit line may reference.
STUBS = {
    "old": "abc123",
    "new": "def456",
    "failed_c": "proxy",
    "phase": "install",
    "atrig": "",
    "trig": ',"trigger":"extra-inputs"',
    "rbv": "1.2.3",
    "nv": "1.2.4",
    "ov": "1.2.3",
    "c": "proxy",
    "snapc": "proxy",
    "complist": "proxy confirm",
    "started_comps": "proxy",
    "touch_verdict": "verdict=fleet-freeze",
}
# Second-pass overrides: sites referencing these get an extra run with the
# override value (exercises the trigger-dedupe path at real call sites).
OVERRIDES = {
    "atrig": ',"trigger":"extra-inputs"',
    "touch_verdict": "verdict=wave-not-live",
}


def _emit_sites():
    sites = []
    with open(AUTO_DEPLOY) as f:
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
    assert row["source"] == "auto-deploy" and row["component"] == "repo"
    # Trigger dedupe: exactly one "trigger" key even on override sites.
    assert raw.count('"trigger"') == 1, f"L{lineno}: duplicate/missing trigger key"
    assert row["trigger"] in ("scheduled", "manual", "extra-inputs", "freeze", "gate"), (
        f"L{lineno}: trigger outside §2 enum: {row['trigger']}"
    )
