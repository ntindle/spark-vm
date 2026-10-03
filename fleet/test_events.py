"""Tests for fleet/events.py (G17 / #608 S1) and its wiring into
fleet/inventory.py's collect + `fleet events` CLI.

Run from the repo root:  python3 -m pytest fleet/test_events.py -q

All tests run locally with no network and no home-dir writes: estates
and stores live under tmp dirs, and the CLIs are exercised through
subprocess, never imported. Time is controlled by writing audit lines
with explicit ts values, so no test depends on the wall clock beyond
"collect just ran". The one exception is the alert-lifecycle section
(#927): pinning the rule-4 window anchor across evaluations needs an
explicit fired_at, so those tests import the events module directly
(precedent: fleet/test_retention.py, fleet/test_events_lock.py).
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


def test_rule2_empty_target_does_not_fire(dirs):
    # #926: two failed lines that carry no target (`to`) carry no
    # shared-release evidence — they must not correlate on the empty
    # key, whether or not their subcomponents agree.
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "reload-fail", ts=ts(20),
                   **{"from": COMMIT_A}),  # no `to`, no component
    ])
    write_box(estate, "cabin", [
        audit_line("deploy", "deploy-fail", ts=ts(10),
                   **{"from": COMMIT_A, "component": "proxy",
                      "phase": "install"}),  # no `to`, component set
    ])
    write_box(estate, "shed", [
        audit_line("deploy", "reload-fail", ts=ts(5),
                   **{"from": COMMIT_A}),  # no `to`, matches tower's key
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    corr = [a for a in journal(store, "alerts.jsonl")
            if a["rule"] == "correlated-failure"]
    assert corr == []


def test_rule2_different_targets_do_not_correlate(dirs):
    # The #926 guard in the other direction: correlation is
    # target-scoped — same subcomponent, different targets within the
    # window -> no fleet alert.
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "deploy-fail", ts=ts(20),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    write_box(estate, "cabin", [
        audit_line("deploy", "deploy-fail", ts=ts(10),
                   **{"from": COMMIT_A, "to": COMMIT_C,
                      "component": "proxy", "phase": "install"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    corr = [a for a in journal(store, "alerts.jsonl")
            if a["rule"] == "correlated-failure"]
    assert corr == []


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


# --- Alert lifecycle (#927 / #928) ------------------------------------------
def _import_events_module():
    # Time-pinned alert tests import the module directly (precedent:
    # test_retention.py / test_events_lock.py); the CLI-driven tests
    # above keep going through subprocess.
    if FLEET not in sys.path:
        sys.path.insert(0, FLEET)
    import events
    return events


def _precheck_row(box_id, emitted_at, seq):
    return {"schema": "fleet-event/1", "event_id": "lifecycle-%s-%d" % (box_id, seq),
            "box_id": box_id, "emitted_at": emitted_at,
            "received_at": emitted_at, "kind": "deploy",
            "outcome": "precheck-fail", "component": "deploy",
            "subcomponent": None, "from": COMMIT_A, "to": COMMIT_B,
            "note": "test"}


def test_rule2_cluster_growth_refires(dirs):
    # #927: a third box joining a paged correlated-failure cluster
    # re-fires with the grown box list; the journaled 2-box row stays
    # (it was true when it fired) and the new row carries a distinct id.
    estate, store = dirs
    line = {"from": COMMIT_A, "to": COMMIT_B, "component": "proxy",
            "phase": "install"}
    write_box(estate, "tower", [
        audit_line("deploy", "deploy-fail", ts=ts(20), **line)])
    write_box(estate, "cabin", [
        audit_line("deploy", "deploy-fail", ts=ts(10), **line)])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    corr = [a for a in journal(store, "alerts.jsonl")
            if a["rule"] == "correlated-failure"]
    assert len(corr) == 1
    assert "shed" not in corr[0]["detail"]
    write_box(estate, "shed", [
        audit_line("deploy", "deploy-fail", ts=ts(5), **line)])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    corr = [a for a in journal(store, "alerts.jsonl")
            if a["rule"] == "correlated-failure"]
    assert len(corr) == 2
    ids = {a["alert_id"] for a in corr}
    assert len(ids) == 2  # growth is a new page, not a dedup no-op
    grown = max(corr, key=lambda a: a["fired_at"])
    assert "tower" in grown["detail"] and "cabin" in grown["detail"] \
        and "shed" in grown["detail"]


def test_rule2_stable_cluster_does_not_refire(dirs):
    # #927 contract pin: re-evaluating the identical cluster must stay
    # silent — growth pages, stability dedups.
    estate, store = dirs
    line = {"from": COMMIT_A, "to": COMMIT_B, "component": "proxy",
            "phase": "install"}
    write_box(estate, "tower", [
        audit_line("deploy", "deploy-fail", ts=ts(20), **line)])
    write_box(estate, "cabin", [
        audit_line("deploy", "deploy-fail", ts=ts(10), **line)])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    corr = [a for a in journal(store, "alerts.jsonl")
            if a["rule"] == "correlated-failure"]
    assert len(corr) == 1


def test_rule4_suppressed_while_unacked_repages_after_ack(dirs):
    # #927: a persistent stuck-precheck condition pages once and stays
    # pending while unacknowledged — even across an anchor move (the
    # pre-fix code paged again on the new anchor). After the ack, the
    # re-fire gate needs genuinely new evidence: the candidate's anchor
    # must postdate the ack (Product B1) — persistence on pre-ack
    # evidence stays silent instead of re-paging immediately.
    # Timeline is relative to the module's NOW so the ack (wall clock)
    # always lands after batch2's evidence.
    events = _import_events_module()
    estate, store = dirs
    batch1 = [_precheck_row("tower",
                            (NOW - timedelta(hours=5, minutes=55)).isoformat(),
                            0),
              _precheck_row("tower",
                            (NOW - timedelta(hours=5, minutes=50)).isoformat(),
                            1),
              _precheck_row("tower",
                            (NOW - timedelta(hours=5, minutes=45)).isoformat(),
                            2)]
    events.append_events(store, batch1)
    fired, err = events.evaluate_alerts(store, NOW.isoformat())
    assert err is None
    assert len(fired) == 1
    first_id = fired[0]["alert_id"]
    # Second batch straddles the first batch's age-out: by the next
    # evaluation batch1 is outside the 6h window, so the anchor moves
    # to batch2's min (new alert_id pre-fix).
    batch2 = [_precheck_row("tower",
                            (NOW - timedelta(hours=2, minutes=50)).isoformat(),
                            3),
              _precheck_row("tower",
                            (NOW - timedelta(hours=2, minutes=40)).isoformat(),
                            4),
              _precheck_row("tower",
                            (NOW - timedelta(hours=2, minutes=30)).isoformat(),
                            5)]
    events.append_events(store, batch2)
    fired, err = events.evaluate_alerts(
        store, (NOW + timedelta(hours=3, minutes=10)).isoformat())
    assert err is None
    assert fired == []  # suppressed: the first alert is still unacked
    stuck = [a for a in events.load_alerts(store)[0]
             if a["rule"] == "stuck-precheck"]
    assert len(stuck) == 1 and stuck[0]["alert_id"] == first_id
    # Acknowledge (acked_at = this test's wall clock K, after batch2).
    # New failures arrive after the ack, but the window still holds
    # pre-ack evidence: the anchor (batch2's min) predates the ack ->
    # stays silent.
    found, err = events.ack_alert(store, first_id)
    assert err is None and found is True
    acked_at = datetime.fromisoformat(
        events.load_alerts(store)[0][0]["acked_at"])
    assert acked_at > NOW - timedelta(hours=2, minutes=50)
    batch3 = [_precheck_row(
        "tower", (acked_at + timedelta(minutes=10)).isoformat(), 6),
        _precheck_row(
            "tower", (acked_at + timedelta(minutes=20)).isoformat(), 7),
        _precheck_row(
            "tower", (acked_at + timedelta(minutes=30)).isoformat(), 8)]
    events.append_events(store, batch3)
    fired, err = events.evaluate_alerts(
        store, (acked_at + timedelta(minutes=40)).isoformat())
    assert err is None
    assert fired == []
    # Once the pre-ack evidence ages out of the 6h window, the anchor
    # postdates the ack -> genuinely new evidence -> re-pages.
    fired, err = events.evaluate_alerts(
        store, (acked_at + timedelta(hours=6, minutes=10)).isoformat())
    assert err is None
    assert len(fired) == 1
    assert fired[0]["alert_id"] != first_id
    assert fired[0]["box_id"] == "tower"


def test_ack_alert_stamps_provenance(dirs, monkeypatch):
    # #928: the ack records when and by whom; the journal row is the
    # transport a cron or the status page reads.
    events = _import_events_module()
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "rollback-failed", ts=ts(30),
                   **{"from": COMMIT_A, "to": COMMIT_B, "phase": "x"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    alert_id = journal(store, "alerts.jsonl")[0]["alert_id"]
    monkeypatch.setenv("USER", "op-test")
    monkeypatch.delenv("LOGNAME", raising=False)
    found, err = events.ack_alert(store, alert_id)
    assert err is None and found is True
    row = journal(store, "alerts.jsonl")[0]
    assert row["acked"] is True
    assert row["acked_by"] == "op-test"
    parsed = datetime.fromisoformat(row["acked_at"])
    assert parsed.tzinfo is not None  # collector clock, aware


def test_ack_alert_unknown_operator_does_not_fail(dirs, monkeypatch):
    # #928 fail-closed posture: no operator identity available must not
    # fail the ack — provenance degrades to null, the ack still lands.
    events = _import_events_module()
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "rollback-failed", ts=ts(30),
                   **{"from": COMMIT_A, "to": COMMIT_B, "phase": "x"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    alert_id = journal(store, "alerts.jsonl")[0]["alert_id"]
    monkeypatch.delenv("USER", raising=False)
    monkeypatch.delenv("LOGNAME", raising=False)
    found, err = events.ack_alert(store, alert_id)
    assert err is None and found is True
    row = journal(store, "alerts.jsonl")[0]
    assert row["acked"] is True
    assert row["acked_by"] is None
    assert row["acked_at"] is not None


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


# --- Bounded alert-evaluation scan window (§4 S2, #814 slice 1) ------------
def test_scan_window_rule1_ancient_rollback_failed_does_not_fire(dirs):
    # #814 slice 1's deliberate behavior delta: a rollback-failed older
    # than the scan window that never fired an alert no longer fires
    # (non-vacuous: the pre-change evaluate_alerts fired this).
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "rollback-failed", ts=ts(7 * 60 + 5),
                   **{"from": COMMIT_A, "to": COMMIT_B, "phase": "x"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert journal(store, "alerts.jsonl") == []


def test_scan_window_rule1_recent_rollback_failed_fires(dirs):
    # The window does not break rule 1 inside the horizon: a 30-min-old
    # rollback-failed still fires (passes on old code too — this pins
    # the window's lower edge, not the delta).
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


def test_scan_window_rule1_undatable_rollback_failed_fires(dirs):
    # Undatable rows pass through the windowed loader: rule 1's "any
    # rollback-failed" keeps its old behavior for events that cannot be
    # placed in time (non-vacuous: fails if the loader dropped them).
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "rollback-failed", ts=12345,
                   **{"from": COMMIT_A, "to": COMMIT_B, "phase": "x"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    alerts = journal(store, "alerts.jsonl")
    assert len(alerts) == 1
    assert alerts[0]["rule"] == "rollback-failed"


def test_scan_window_rule2_ancient_pair_does_not_fire(dirs):
    # Two failed boxes 8h ago within 30 min of each other: old code
    # fired a correlated-failure alert; the bounded scan does not
    # (non-vacuous: fails pre-change).
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "deploy-fail", ts=ts(8 * 60),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    write_box(estate, "cabin", [
        audit_line("deploy", "deploy-fail", ts=ts(8 * 60 + 10),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    corr = [a for a in journal(store, "alerts.jsonl")
            if a["rule"] == "correlated-failure"]
    assert corr == []


def test_scan_window_rule2_recent_pair_still_fires(dirs):
    # In-window correlated pair still fires with ancient noise present
    # beyond the window (pins rule 2's behavior under the new loader).
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "deploy-fail", ts=ts(20),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
        audit_line("deploy", "deploy-fail", ts=ts(8 * 60),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    write_box(estate, "cabin", [
        audit_line("deploy", "deploy-fail", ts=ts(10),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy", "phase": "install"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    corr = [a for a in journal(store, "alerts.jsonl")
            if a["rule"] == "correlated-failure"]
    assert len(corr) == 1
    assert "tower" in corr[0]["detail"] and "cabin" in corr[0]["detail"]


def _ts_now(minutes_ago):
    # Execution-time timestamp (not the module-import NOW): the full
    # suite runs ~9 min before fleet tests execute, so a near-window-edge
    # ts() frozen at import would age past the 6h edge by test time.
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_scan_window_rule4_boundary_pins(dirs):
    # Rule 4's own 6h cutoff equals the scan window: 3 precheck-fails
    # inside the window still fire. Pinned at 5h55m (5 min slack against
    # clock skew); exactness at the 6h edge holds structurally — the
    # loader's `emitted >= since` and rule 4's `ts >= cutoff` are the
    # same inclusive comparison on the same parsed fired_at.
    estate, store = dirs
    write_box(estate, "tower", [
        audit_line("deploy", "gate-fail", ts=_ts_now(60),
                   **{"from": COMMIT_A, "to": COMMIT_B,
                      "component": "proxy"}),
        audit_line("deploy", "snapshot-fail", ts=_ts_now(5 * 60 + 50),
                   **{"from": COMMIT_A, "to": COMMIT_B}),
        audit_line("check", "precheck-fail", ts=_ts_now(5 * 60 + 55)),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    stuck = [a for a in journal(store, "alerts.jsonl")
             if a["rule"] == "stuck-precheck"]
    assert len(stuck) == 1
    assert stuck[0]["box_id"] == "tower"


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


# --- Control-character injection (Security B1, PR #794) ---------------------
# Injected newlines/escapes inside a *field* are the forgery vector
# (extra cron-log lines, forged alert rows, terminal escape codes).
# Structural newlines between output rows are legitimate, so the check
# allows \n and \t but nothing else below 0x20 or DEL.
def _has_control_chars(text):
    return any((ord(c) < 0x20 and c not in ("\n", "\t"))
               or ord(c) == 0x7f for c in text)


def test_control_chars_never_reach_journal_or_output(dirs):
    estate, store = dirs
    hostile = json.dumps({
        "ts": "2026-10-01T10:00:00Z",
        "event": "deploy",
        "result": "deploy-fail",
        "from": "a" * 40,
        "to": "b" * 40 + "\x1b]0;terminal-title-pwn\x07",
        "component": "proxy\nFAKE cron line",
        "phase": "install\r\nINJECTED",
    })
    write_box(estate, "tower", [
        hostile,
        # Unknown shape with control chars in the shape fields: the
        # fail-closed note must not carry them raw either.
        json.dumps({"ts": "2026-10-01T10:01:00Z",
                    "event": "deploy\nFAKE",
                    "result": "ok\r\nANOTHER"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert not _has_control_chars(proc.stderr), proc.stderr
    for ev in journal(store, "events.jsonl"):
        for key, value in ev.items():
            if isinstance(value, str):
                assert not _has_control_chars(value), (key, value)
    # The hostile to-value is stripped, not dropped: the event survives.
    evs = journal(store, "events.jsonl")
    assert len(evs) == 1
    assert evs[0]["outcome"] == "failed"
    assert "\x1b" not in evs[0]["to"] and "\n" not in evs[0]["subcomponent"]
    # Strip-not-drop: the payload text remains but cannot break structure.
    assert "terminal-title-pwn" in evs[0]["to"]
    assert evs[0]["subcomponent"] == "proxyFAKE cron line"

    proc = run_inventory("events", "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert not _has_control_chars(proc.stdout), proc.stdout
    assert "\x1b" not in proc.stdout
    # No forged extra table row: the injected newline is gone, so the
    # events list prints exactly its structural lines.
    assert proc.stdout.count("\n") == 3  # header + col header + 1 box row


def test_control_chars_in_alert_paths(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        json.dumps({"ts": ts(30), "event": "deploy",
                    "result": "rollback-failed", "from": "a" * 40,
                    "to": "b" * 40 + "\nFORGED alert row",
                    "phase": "x"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    alerts = journal(store, "alerts.jsonl")
    assert len(alerts) == 1
    for key, value in alerts[0].items():
        if isinstance(value, str):
            assert not _has_control_chars(value), (key, value)
    proc = run_inventory("events", "watch", "--store", store)
    assert proc.returncode == 1
    assert not _has_control_chars(proc.stdout), proc.stdout
    # The payload text remains (strip-not-drop) but cannot forge an
    # extra alert row: exactly the structural 4 lines for one alert.
    assert proc.stdout.count("\n") == 4
    assert "\n" not in alerts[0]["to"]
    assert "FORGED alert row" in alerts[0]["to"]


# --- Type-confusion hardening (Engineering B1, PR #794) ---------------------
# A type-confused-but-valid audit line (e.g. `"to":12345`) must never
# poison alert evaluation: free-form fields coerce to str-or-None at
# synthesis, so the journal carries `to: None` and every future collect
# evaluates alerts cleanly.
def test_numeric_to_coerced_to_none_and_alerts_keep_running(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        json.dumps({"ts": ts(20), "event": "deploy", "result": "deploy-fail",
                    "from": "a" * 40, "to": 12345, "component": "proxy",
                    "phase": "install"}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    evs = journal(store, "events.jsonl")
    assert len(evs) == 1
    assert evs[0]["to"] is None
    assert evs[0]["outcome"] == "failed"
    # Second collect: alert evaluation runs over the journaled event
    # without the TypeError the poisoned row used to cause.
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "unexpected failure" not in proc.stderr


def test_non_string_versions_and_trigger_fall_back(dirs):
    estate, store = dirs
    write_box(estate, "tower", [
        json.dumps({"ts": 12345, "event": "deploy", "result": "ok",
                    "from": ["not", "a", "string"], "to": "b" * 40,
                    "components": "proxy", "to_version": 7,
                    "trigger": ["scheduled"]}),
    ])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    evs = journal(store, "events.jsonl")
    assert len(evs) == 1
    ev = evs[0]
    assert ev["from"] is None
    assert ev["to_version"] is None
    assert ev["emitted_at"] is None
    assert ev["trigger"] == "scheduled"
