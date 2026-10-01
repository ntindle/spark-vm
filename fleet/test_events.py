"""Tests for fleet/events.py (G17 / #608 S1) and its wiring into
fleet/inventory.py's collect + `fleet events` CLI.

Run from the repo root:  python3 -m pytest fleet/test_events.py -q

All tests run locally with no network and no home-dir writes: estates
and stores live under tmp dirs, and the CLIs are exercised through
subprocess, never imported. Time is controlled by writing audit lines
with explicit ts values, so no test depends on the wall clock beyond
"collect just ran".
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

FLEET = os.path.dirname(os.path.abspath(__file__))
INVENTORY = os.path.join(FLEET, "inventory.py")

NOW = datetime.now(timezone.utc)
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
COMMIT_C = "c" * 40


def run_inventory(*argv):
    return subprocess.run(
        [sys.executable, INVENTORY, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def audit_line(event, result, ts=None, **fields):
    line = {"ts": ts or NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event, "result": result}
    line.update(fields)
    return json.dumps(line)


@pytest.fixture()
def dirs():
    with tempfile.TemporaryDirectory() as tmp:
        estate = os.path.join(tmp, "estate")
        store = os.path.join(tmp, "store")
        os.makedirs(estate)
        yield estate, store


def write_box(estate, box_id, audit_lines):
    box_dir = os.path.join(estate, box_id)
    os.makedirs(box_dir, exist_ok=True)
    with open(os.path.join(box_dir, "audit-tail.jsonl"), "w",
              encoding="utf-8") as fh:
        for line in audit_lines:
            fh.write(line + "\n")
    return box_dir


def journal(store, name):
    path = os.path.join(store, name)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def ts(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


# --- Translation table (§3) ------------------------------------------------
TRANSLATION_CASES = [
    # (audit event, result, extra fields, expected kind, expected outcome)
    ("check", "precheck-fail", {}, "check", "precheck-fail"),
    ("deploy", "precheck-fail", {"from": COMMIT_A, "to": COMMIT_B},
     "deploy", "precheck-fail"),
    ("deploy", "gate-fail", {"from": COMMIT_A, "to": COMMIT_B,
                             "component": "proxy"},
     "deploy", "precheck-fail"),
    ("deploy", "snapshot-fail", {"from": COMMIT_A, "to": COMMIT_B},
     "deploy", "precheck-fail"),
    ("deploy", "checkout-dirty", {"from": COMMIT_A, "to": COMMIT_B,
                                  "component": "proxy"},
     "deploy", "precheck-fail"),  # retired result: still translates
    ("deploy", "deploy-fail", {"from": COMMIT_A, "to": COMMIT_B,
                               "component": "proxy", "phase": "install"},
     "deploy", "failed"),
    ("deploy", "reload-fail", {"from": COMMIT_A, "to": COMMIT_B},
     "deploy", "failed"),
    ("deploy", "rollback-failed", {"from": COMMIT_A, "to": COMMIT_B,
                                   "phase": "reload"},
     "deploy", "rollback-failed"),
    ("deploy", "rolled-back", {"from": COMMIT_B, "to": COMMIT_A,
                               "to_version": "v1"},
     "deploy", "rolled-back"),
    ("deploy", "pull-only", {"from": COMMIT_A, "to": COMMIT_B,
                             "from_version": "v1", "to_version": "v2"},
     "deploy", "succeeded"),
    ("deploy", "ok", {"from": COMMIT_A, "to": COMMIT_B,
                      "components": "proxy confirm",
                      "to_version": "v2", "from_version": "v1"},
     "deploy", "succeeded"),
    ("rollback", "rollback-failed", {"snapshot": "/x/snap"}, "rollback",
     "rollback-failed"),
    ("rollback", "manual-rollback", {"to": COMMIT_A,
                                     "rolled_back_from": COMMIT_B,
                                     "to_version": "v1"},
     "rollback", "rolled-back"),
    ("rollback", "rollback-unhealthy", {"to": COMMIT_A,
                                        "rolled_back_from": COMMIT_B},
     "rollback", "rolled-back"),
]


@pytest.mark.parametrize("event,result,fields,kind,outcome",
                         TRANSLATION_CASES)
def test_translation_table_shapes(dirs, event, result, fields, kind,
                                  outcome):
    estate, store = dirs
    write_box(estate, "tower", [audit_line(event, result, **fields)])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    evs = journal(store, "events.jsonl")
    if event == "deploy" and result == "ok":
        # Fan-out: one event per component in the plural `components`.
        assert len(evs) == 2
        subs = sorted(e["subcomponent"] for e in evs)
        assert subs == ["confirm", "proxy"]
        assert all(e["subcomponents"] == "proxy confirm" for e in evs)
        assert all(e["kind"] == kind and e["outcome"] == outcome
                   for e in evs)
    else:
        assert len(evs) == 1, evs
        ev = evs[0]
        assert ev["kind"] == kind
        assert ev["outcome"] == outcome
        assert ev["schema"] == "fleet-event/1"
        assert ev["box_id"] == "tower"
        assert ev["source"] == "auto-deploy"
        assert ev["component"] == "repo"
        assert ev["attested"] is False
        assert ev["session_epoch"] is None
        assert ev["rollout"] is None
        assert ev["received_at"]  # collect clock


def test_check_noop_stays_local(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("check", "noop"),
        audit_line("check", "noop"),
        audit_line("deploy", "ok", **{"from": COMMIT_A, "to": COMMIT_B,
                                      "components": "proxy"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    evs = journal(store, "events.jsonl")
    # The two check-noops never reach the journal; the ok line does.
    assert [e["outcome"] for e in evs] == ["succeeded"]


def test_unknown_shape_is_note_not_event(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        '{"ts": "2026-01-01T00:00:00Z", "event": "deploy", '
        '"result": "mystery-future-result", "to": "abc"}',
        "this is not json at all",
        audit_line("deploy", "ok", **{"from": COMMIT_A, "to": COMMIT_B,
                                      "components": "proxy"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    evs = journal(store, "events.jsonl")
    assert len(evs) == 1  # only the ok line
    assert evs[0]["outcome"] == "succeeded"
    # Fail-closed notes surface on stderr (the collector note).
    assert "no translation" in proc.stderr
    assert "malformed" in proc.stderr


def test_event_id_deterministic_and_deduped(dirs):
    estate, store = dirs
    line = audit_line("deploy", "deploy-fail", ts=ts(60),
                      **{"from": COMMIT_A, "to": COMMIT_B,
                         "component": "proxy", "phase": "install"})
    write_box(estate, "tower", [line])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    first = journal(store, "events.jsonl")
    assert len(first) == 1
    # Re-collect the identical tail: dedup is a no-op.
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    second = journal(store, "events.jsonl")
    assert len(second) == 1
    assert second[0]["event_id"] == first[0]["event_id"]


def test_reload_fail_phase_synthesized(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "reload-fail",
                   **{"from": COMMIT_A, "to": COMMIT_B}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    evs = journal(store, "events.jsonl")
    assert len(evs) == 1
    assert evs[0]["phase"] == "reload"
    assert "synthesized" in evs[0]["note"]
    assert evs[0]["subcomponent"] is None  # line carries no component


def test_extra_inputs_trigger(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "ok", **{"from": COMMIT_A, "to": COMMIT_B,
                                      "components": "proxy",
                                      "trigger": "extra-inputs"}),
        audit_line("check", "precheck-fail"),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    evs = journal(store, "events.jsonl")
    by_outcome = {e["outcome"]: e for e in evs}
    assert by_outcome["succeeded"]["trigger"] == "extra-inputs"
    # Absent trigger canonicalizes to scheduled.
    assert by_outcome["precheck-fail"]["trigger"] == "scheduled"


def test_manual_rollback_from_is_rolled_back_from(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("rollback", "manual-rollback",
                   **{"to": COMMIT_A, "rolled_back_from": COMMIT_B}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    evs = journal(store, "events.jsonl")
    assert len(evs) == 1
    assert evs[0]["from"] == COMMIT_B
    assert evs[0]["to"] == COMMIT_A


# --- Alert rules ------------------------------------------------------------
def _alert_ids(store):
    return [a["alert_id"] for a in journal(store, "alerts.jsonl")]


def test_rule1_rollback_failed_alerts(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "rollback-failed", ts=ts(30),
                   **{"from": COMMIT_A, "to": COMMIT_B, "phase": "x"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    alerts = journal(store, "alerts.jsonl")
    assert len(alerts) == 1
    assert alerts[0]["rule"] == "rollback-failed"
    assert alerts[0]["box_id"] == "tower"
    assert alerts[0]["acked"] is False
    # Re-collect: the same event does not re-fire.
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert len(journal(store, "alerts.jsonl")) == 1


def test_rule2_correlated_failure(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "deploy-fail", ts=ts(20),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    write_box(estate, "cabin", [
        audit_line("deploy", "deploy-fail", ts=ts(10),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    write_box(estate, "shed", [
        audit_line("deploy", "deploy-fail", ts=ts(600),  # 10h earlier
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    alerts = journal(store, "alerts.jsonl")
    corr = [a for a in alerts if a["rule"] == "correlated-failure"]
    assert len(corr) == 1
    assert corr[0]["subcomponent"] == "proxy"
    assert corr[0]["to"] == COMMIT_B
    assert "tower" in corr[0]["detail"] and "cabin" in corr[0]["detail"]
    assert "shed" not in corr[0]["detail"]  # outside the 30-min window


def test_rule2_no_component_correlates_on_to(dirs):
    estate, store = dirs
    # reload-fail lines carry no component: correlate on (to) alone.
    write_box(estate, "tower", [
        audit_line("deploy", "reload-fail", ts=ts(20),
                   **{"from": COMMIT_A, "to": COMMIT_B}),
    ])
    write_box(estate, "cabin", [
        audit_line("deploy", "reload-fail", ts=ts(10),
                   **{"from": COMMIT_A, "to": COMMIT_B}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    corr = [a for a in journal(store, "alerts.jsonl")
            if a["rule"] == "correlated-failure"]
    assert len(corr) == 1
    assert corr[0]["subcomponent"] == "unknown"


def test_rule2_single_box_does_not_fire(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "deploy-fail", ts=ts(20),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
        audit_line("deploy", "deploy-fail", ts=ts(10),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    corr = [a for a in journal(store, "alerts.jsonl")
            if a["rule"] == "correlated-failure"]
    assert corr == []


def test_rule4_stuck_precheck(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "gate-fail", ts=ts(60),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy"}),
        audit_line("deploy", "snapshot-fail", ts=ts(120),
                   **{"from": COMMIT_A, "to": COMMIT_B}),
        audit_line("check", "precheck-fail", ts=ts(180)),
        audit_line("deploy", "ok", ts=ts(300),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "components": "proxy"}),
    ])
    write_box(estate, "cabin", [
        audit_line("deploy", "gate-fail", ts=ts(60),
                   **{"from": COMMIT_A, "to": COMMIT_B}),
        audit_line("deploy", "gate-fail", ts=ts(120),
                   **{"from": COMMIT_A, "to": COMMIT_B}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    stuck = [a for a in journal(store, "alerts.jsonl")
             if a["rule"] == "stuck-precheck"]
    assert len(stuck) == 1
    assert stuck[0]["box_id"] == "tower"  # 3 precheck-fails in 6h
    assert "3 precheck-fail" in stuck[0]["detail"]


def test_rule3_silent_wave_disarmed(dirs):
    estate, store = dirs
    # A box with a quiet tail: at S1 this must NOT page (every rollout
    # envelope is null; the rule cannot fire).
    write_box(estate, "tower", [audit_line("check", "noop")])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    silent = [a for a in journal(store, "alerts.jsonl")
              if a["rule"] == "silent-wave"]
    assert silent == []


# --- CLI readers ------------------------------------------------------------
def test_events_list_and_box_filter(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "rolled-back", ts=ts(50),
                   **{"from": COMMIT_B, "to": COMMIT_A,
                      "to_version": "v1"}),
    ])
    write_box(estate, "cabin", [
        audit_line("deploy", "ok", ts=ts(40),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "components": "proxy"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr

    proc = run_inventory("events", "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "tower" in proc.stdout and "cabin" in proc.stdout
    assert "rolled-back" in proc.stdout and "succeeded" in proc.stdout

    proc = run_inventory("events", "--store", store, "--box", "tower")
    assert proc.returncode == 0, proc.stderr
    assert "rolled-back" in proc.stdout
    assert "cabin" not in proc.stdout

    proc = run_inventory("events", "--store", store, "--box", "nope")
    assert proc.returncode == 2
    assert "no events" in proc.stderr


def test_events_wave_filter_empty_at_s1(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "ok", **{"from": COMMIT_A, "to": COMMIT_B,
                                      "components": "proxy"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    # Rollout envelopes are null until G15 S2: the filter matches nothing
    # but is not an error.
    proc = run_inventory("events", "--store", store, "--wave", "canary")
    assert proc.returncode == 0, proc.stderr


def test_watch_exit_codes_and_ack(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "rollback-failed", ts=ts(30),
                   **{"from": COMMIT_A, "to": COMMIT_B, "phase": "x"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr

    proc = run_inventory("events", "watch", "--store", store)
    assert proc.returncode == 1, proc.stdout  # unacknowledged alerts
    assert "UNACKNOWLEDGED ALERTS" in proc.stdout

    alert_id = _alert_ids(store)[0]
    proc = run_inventory("events", "ack", "--store", store,
                         "--alert-id", alert_id)
    assert proc.returncode == 0, proc.stderr
    assert "acknowledged" in proc.stdout

    proc = run_inventory("events", "watch", "--store", store)
    assert proc.returncode == 0
    assert "no unacknowledged alerts" in proc.stdout

    # Unknown alert id is a clean exit-2, not a traceback.
    proc = run_inventory("events", "ack", "--store", store,
                         "--alert-id", "no-such-id")
    assert proc.returncode == 2
    assert "no alert" in proc.stderr


def test_watch_clean_store(dirs):
    estate, store = dirs
    proc = run_inventory("events", "watch", "--store", store)
    assert proc.returncode == 0
    assert "no unacknowledged alerts" in proc.stdout


def test_collect_keeps_inventory_behavior(dirs):
    # The G17 wiring must not change the inventory record semantics:
    # a failed deploy's `to` is an attempt, not a state claim.
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "deploy-fail", ts=ts(30),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    proc = run_inventory("inventory", "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "tower" in proc.stdout
    # The box reports no successful claim: the table shows no repo
    # commit, and the event journal still carries the failure.
    assert "(no report)" in proc.stdout
    assert len(journal(store, "events.jsonl")) == 1


def test_missing_audit_tail_is_note(dirs):
    estate, store = dirs
    os.makedirs(os.path.join(estate, "tower"))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert journal(store, "events.jsonl") == []
    assert "audit-tail.jsonl missing" in proc.stderr
