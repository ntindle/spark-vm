"""D-PP-2 conformance tripwire for the D9 sweep's async plane port (#1566 S2).

For every scenario in `hosted/push_sweep_port/scenarios.py`, this test
rebuilds the fixture database, runs the in-repo sync sweep, serializes
the outputs, and diffs them against the checked-in recorded outputs in
`hosted/push_sweep_port/recorded/`. Any divergence fails the test.

The recorded files are generated FROM the sync module by
`python3 -m hosted.push_sweep_port.record` — the sync module is the
harness truth (D-PP-1); the async port must reproduce these records.
A green run proves the fixture set is self-consistent; the records are
what the port is held to.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted.push_sweep_port import conformance, scenarios


def _diff_paths(actual, expected, path=""):
    """Yield human-readable paths where two JSON-able values differ."""
    if type(actual) is not type(expected):
        yield "%s: type %s != %s" % (
            path or "<root>", type(actual).__name__,
            type(expected).__name__)
        return
    if isinstance(actual, dict):
        for key in sorted(set(actual) | set(expected)):
            sub = "%s.%s" % (path, key) if path else str(key)
            if key not in actual:
                yield "%s: missing in actual" % sub
            elif key not in expected:
                yield "%s: unexpected in actual" % sub
            else:
                yield from _diff_paths(actual[key], expected[key], sub)
    elif isinstance(actual, list):
        if len(actual) != len(expected):
            yield "%s: len %d != %d" % (path or "<root>", len(actual),
                                       len(expected))
        for i, (a, e) in enumerate(zip(actual, expected)):
            yield from _diff_paths(a, e, "%s[%d]" % (path, i))
    elif actual != expected:
        yield "%s: %r != %r" % (path or "<root>", actual, expected)


@pytest.mark.parametrize("scenario", scenarios.SCENARIOS,
                         ids=scenarios.scenario_names())
def test_scenario_matches_recorded(scenario):
    recorded = conformance.load_recorded(scenario["name"])
    # Provenance: the record must come from the sync module under test.
    assert recorded["sweep_module_sha256"] == \
        conformance.sweep_module_sha256(), (
            "recorded outputs for %r were produced by a different "
            "hosted/push_sweep.py — regenerate with "
            "`python3 -m hosted.push_sweep_port.record`" % scenario["name"])
    actual = conformance.run_scenario(scenario)
    diffs = list(_diff_paths(actual["summary"], recorded["summary"],
                             "summary")) + list(
        _diff_paths(actual["db"], recorded["db"], "db"))
    assert not diffs, (
        "scenario %r diverged from its recorded outputs:\n%s" % (
            scenario["name"], "\n".join(diffs[:25])))


def test_no_orphan_scenarios_or_records():
    """Every scenario has a record and every record has a scenario."""
    names = set(scenarios.scenario_names())
    recorded = {f[:-5] for f in os.listdir(conformance.RECORDED_DIR)
                if f.endswith(".json")}
    assert names - recorded == set(), \
        "scenarios with no recorded file: %s" % sorted(names - recorded)
    assert recorded - names == set(), \
        "recorded files with no scenario: %s" % sorted(recorded - names)


def test_recorded_files_are_not_hand_edited():
    """The recorded files must be valid JSON with the expected shape."""
    for name in scenarios.scenario_names():
        recorded = conformance.load_recorded(name)
        assert recorded["scenario"] == name
        assert set(recorded["summary"]) == {
            "reminders", "digests", "stale_watchers", "token_warnings",
            "candidates_seen", "pages_truncated", "reminders_enabled",
            "notes", "budget_truncated", "digests_truncated"}, name
        assert set(recorded["db"]) == {
            "push_send_results", "push_digest_state",
            "push_budget_counters"}, name
        assert isinstance(recorded["sweep_module_sha256"], str) \
            and len(recorded["sweep_module_sha256"]) == 64, name
