"""Tests for the #1649 S2 slice-4 collector read switch.

fleet/events.py::collect_box_events reads a box's `update-events.jsonl`
(the native standard-shape journal the S2 producers emit) INSTEAD of
translating audit tails whenever the estate dir carries it — exclusive
per box, so the same underlying event is never double-journaled under
two event_ids. Boxes without the journal keep the legacy audit-tail
translation.

Run from the repo root:  python3 -m pytest fleet/test_journal_read_switch.py -q

Conventions follow fleet/test_events.py: estates and stores live under
tmp dirs, and `fleet inventory collect` is exercised through
subprocess. The unit tests import the events module directly
(precedent: fleet/test_retention.py, fleet/test_events_lock.py) so the
canonicalizer's fail-closed table is pinned without a full collect.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile

import pytest

FLEET = os.path.dirname(os.path.abspath(__file__))
INVENTORY = os.path.join(FLEET, "inventory.py")

_spec = importlib.util.spec_from_file_location(
    "fleet_events_under_test", os.path.join(FLEET, "events.py"))
events = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(events)

RECEIVED_AT = "2026-10-21T07:45:00+00:00"


def journal_row(**fields):
    row = {
        "event_id": "0193b2c4-0000-7000-8000-000000000001",
        "box_id": None,
        "session_epoch": None,
        "emitted_at": "2026-10-21T07:44:00Z",
        "received_at": None,
        "source": "auto-deploy",
        "component": "repo",
        "kind": "deploy",
        "outcome": "succeeded",
        "rollout": None,
        "trigger": "scheduled",
        "attested": False,
    }
    row.update(fields)
    return row


def write_journal(box_dir, rows):
    os.makedirs(box_dir, exist_ok=True)
    path = os.path.join(box_dir, "update-events.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(row if isinstance(row, str) else json.dumps(row))
            fh.write("\n")
    return path


def write_audit_tail(box_dir, lines):
    os.makedirs(box_dir, exist_ok=True)
    path = os.path.join(box_dir, "audit-tail.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line if isinstance(line, str) else json.dumps(line))
            fh.write("\n")
    return path


def test_journal_row_maps_to_standard_shape():
    evs, noops, notes = events.canonicalize_journal_rows(
        [journal_row(**{
            "event_id": "0193b2c4-0000-7000-8000-0000000000aa",
            "source": "gate-hook", "component": "gate",
            "kind": "gate-answer", "outcome": "skipped-frozen",
            "trigger": "gate", "reason": "operator freeze",
            "repo_max": "abc123",
            "note": "fleet freeze (release gate)",
        })],
        "box-7", RECEIVED_AT)
    assert noops == 0
    assert notes == []
    assert len(evs) == 1
    ev = evs[0]
    assert ev["schema"] == "fleet-event/1"
    assert ev["event_id"] == "0193b2c4-0000-7000-8000-0000000000aa"
    assert ev["box_id"] == "box-7"          # pull context, not the row
    assert ev["received_at"] == RECEIVED_AT  # collector stamps it
    assert ev["window"] is None
    assert ev["attested"] is False
    assert ev["note"] == "fleet freeze (release gate)"
    # Producer-fragment extras ride through verbatim.
    assert ev["reason"] == "operator freeze"
    assert ev["repo_max"] == "abc123"


def test_journal_box_id_disagreement_is_loud_but_uses_estate_dir():
    evs, _, notes = events.canonicalize_journal_rows(
        [journal_row(box_id="impostor-box")], "box-7", RECEIVED_AT)
    assert len(evs) == 1
    assert evs[0]["box_id"] == "box-7"
    assert any("disagrees with estate dir box" in n for n in notes)


def test_journal_non_string_box_id_is_loud():
    # A present-but-not-a-string box_id is the same loudness class as
    # a disagreeing one (a null row box_id is the normal unset case
    # and stays silent).
    evs, _, notes = events.canonicalize_journal_rows(
        [journal_row(box_id=123)], "box-7", RECEIVED_AT)
    assert len(evs) == 1
    assert evs[0]["box_id"] == "box-7"
    assert any("non-string box_id" in n for n in notes)
    evs, _, notes = events.canonicalize_journal_rows(
        [journal_row(box_id=None)], "box-7", RECEIVED_AT)
    assert len(evs) == 1
    assert notes == []


def test_journal_extras_verbatim_and_serializable():
    evs, _, notes = events.canonicalize_journal_rows(
        [journal_row(**{"reason": "operator freeze",
                        "counts": {"a": 1}, "tags": ["t1", "t2"]})],
        "box-7", RECEIVED_AT)
    assert len(evs) == 1
    assert evs[0]["reason"] == "operator freeze"
    assert evs[0]["counts"] == {"a": 1}
    assert evs[0]["tags"] == ["t1", "t2"]
    # Extras arrive as parsed JSON values, so they are always
    # serializable — the downstream journal write cannot crash on them.
    json.dumps(evs[0])
    # The raw attestation member never leaks into the journal row.
    evs, _, _ = events.canonicalize_journal_rows(
        [journal_row(attestation={"sig": "00"})], "box-7", RECEIVED_AT)
    assert "attestation" not in evs[0]


def test_journal_noop_stays_local():
    evs, noops, notes = events.canonicalize_journal_rows(
        [journal_row(kind="check", outcome="noop")], "box-7", RECEIVED_AT)
    assert evs == [] and noops == 1
    # The noise-discipline note is added by collect_box_events (the
    # same layering as the S1 audit path).
    with tempfile.TemporaryDirectory() as tmp:
        box_dir = os.path.join(tmp, "box-7")
        write_journal(box_dir,
                      [journal_row(kind="check", outcome="noop")])
        evs, noops, notes = events.collect_box_events(
            box_dir, "box-7", RECEIVED_AT)
        assert evs == [] and noops == 1
        assert any("noise discipline" in n for n in notes)


def test_journal_fail_closed_table():
    bad_rows = [
        "not a dict at all",                                   # non-object
        journal_row(event_id=""),                              # empty id
        journal_row(event_id=None),                            # null id
        journal_row(source="mystery-producer"),                # bad source
        journal_row(component="flux-capacitor"),               # bad component
        journal_row(kind="teleport"),                          # bad kind
        journal_row(outcome="transcended"),                    # bad outcome
    ]
    evs, noops, notes = events.canonicalize_journal_rows(
        bad_rows, "box-7", RECEIVED_AT)
    assert evs == []
    assert noops == 0
    assert len(notes) == len(bad_rows)
    assert any("non-object journal line" in n for n in notes)
    assert any("without event_id" in n for n in notes)
    assert any("kept out of the event journal" in n for n in notes)


def test_journal_unknown_trigger_defaults_scheduled_loud():
    evs, _, notes = events.canonicalize_journal_rows(
        [journal_row(trigger="quantum")], "box-7", RECEIVED_AT)
    assert len(evs) == 1
    assert evs[0]["trigger"] == "scheduled"
    assert any("unknown trigger" in n for n in notes)


def test_journal_type_confusion_is_coerced_not_crashed():
    evs, _, notes = events.canonicalize_journal_rows(
        [journal_row(**{"to": 12345, "note": ["not", "a", "string"]})],
        "box-7", RECEIVED_AT)
    assert len(evs) == 1
    assert evs[0]["to"] is None
    assert evs[0]["note"] is None
    # json.dumps must still succeed on the emitted row.
    json.dumps(evs[0])


def test_journal_attestation_member_is_verified_before_shape_gates():
    # A malformed attestation member is the loud note even though the
    # row's shape is otherwise valid — the #1516 property survives the
    # read switch.
    evs, _, notes = events.canonicalize_journal_rows(
        [journal_row(attestation="not-an-object")], "box-7", RECEIVED_AT)
    assert len(evs) == 1
    assert evs[0]["attested"] is False
    assert any("attestation member is not an object" in n for n in notes)


def test_journal_rows_none_is_empty():
    evs, noops, notes = events.canonicalize_journal_rows(
        None, "box-7", RECEIVED_AT)
    assert evs == [] and noops == 0 and notes == []


def test_collect_prefers_journal_over_audit_tail_exclusively():
    # The same underlying deploy is described BOTH by the S2 journal
    # row (native UUIDv7 id) and by the legacy audit line (which would
    # canonicalize to a deterministic UUIDv5 id): the read switch must
    # journal exactly one event — never both.
    with tempfile.TemporaryDirectory() as tmp:
        box_dir = os.path.join(tmp, "box-7")
        write_journal(box_dir, [journal_row(
            event_id="0193b2c4-0000-7000-8000-0000000000bb",
            outcome="succeeded")])
        write_audit_tail(box_dir, [{
            "ts": "2026-10-21T07:44:00Z", "event": "deploy",
            "result": "ok", "to": "d" * 40, "components": "cua-driver",
        }])
        evs, _, notes = events.collect_box_events(
            box_dir, "box-7", RECEIVED_AT)
        assert len(evs) == 1
        assert evs[0]["event_id"] == "0193b2c4-0000-7000-8000-0000000000bb"
        assert not any("audit" in n for n in notes)


def test_collect_legacy_path_when_no_journal():
    # Boxes that predate (or disable) the S2 sink keep the audit-tail
    # translation: the read switch must not strand them.
    with tempfile.TemporaryDirectory() as tmp:
        box_dir = os.path.join(tmp, "box-7")
        write_audit_tail(box_dir, [{
            "ts": "2026-10-21T07:44:00Z", "event": "deploy",
            "result": "ok", "to": "d" * 40, "components": "cua-driver",
        }])
        evs, _, notes = events.collect_box_events(
            box_dir, "box-7", RECEIVED_AT)
        assert len(evs) == 1
        assert evs[0]["outcome"] == "succeeded"
        assert evs[0]["source"] == "auto-deploy"
        assert evs[0]["received_at"] == RECEIVED_AT


def test_collect_journal_malformed_lines_are_skipped_loud():
    with tempfile.TemporaryDirectory() as tmp:
        box_dir = os.path.join(tmp, "box-7")
        write_journal(box_dir, [
            journal_row(event_id="0193b2c4-0000-7000-8000-0000000000cc"),
            "{this is not json",
        ])
        evs, _, notes = events.collect_box_events(
            box_dir, "box-7", RECEIVED_AT)
        assert len(evs) == 1
        assert any("malformed line(s) skipped" in n for n in notes)


def test_collect_e2e_journal_rows_land_in_store_and_rededup():
    # End to end through `fleet inventory collect`: the journal rows
    # reach the store's event journal, and a second collect is a no-op
    # (dedup on (box_id, event_id)).
    with tempfile.TemporaryDirectory() as tmp:
        estate = os.path.join(tmp, "estate")
        store = os.path.join(tmp, "store")
        os.makedirs(estate)
        box_dir = os.path.join(estate, "box-7")
        write_journal(box_dir, [
            journal_row(event_id="0193b2c4-0000-7000-8000-0000000000dd",
                        outcome="succeeded"),
            journal_row(event_id="0193b2c4-0000-7000-8000-0000000000de",
                        kind="check", outcome="deferred-arc"),
        ])
        for argv in (["collect", "--estate", estate, "--store", store],
                     ["collect", "--estate", estate, "--store", store]):
            proc = subprocess.run(
                [sys.executable, INVENTORY, *argv],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            assert proc.returncode == 0, proc.stderr
        stored, err = events.load_events(store)
        assert err is None
        ids = sorted(e["event_id"] for e in stored
                     if e.get("box_id") == "box-7")
        assert ids == ["0193b2c4-0000-7000-8000-0000000000dd",
                       "0193b2c4-0000-7000-8000-0000000000de"]
        row = next(e for e in stored
                   if e["event_id"].endswith("dd"))
        assert row["schema"] == "fleet-event/1"
        assert row["outcome"] == "succeeded"


def _status_json():
    from datetime import datetime, timezone
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "slice": "S1", "tools": [], "pin_warnings": []}


def _snapshot_json(commit):
    from datetime import datetime, timezone
    return {"repo_commit": commit,
            "gate": {"frozen": None, "answer_age_s": 42},
            "arc_active": None, "image_version": None, "note": None,
            "emitted_at": datetime.now(timezone.utc).isoformat()}


def _store_snapshot(store):
    with open(os.path.join(store, "snapshot.json")) as fh:
        return json.load(fh)


def test_collect_e2e_version_leg_still_reads_audit_tail():
    # The read switch moves only the event-journal leg: the
    # version-inventory leg still reads the audit tail on a
    # journal-path box.
    commit = "d" * 40
    with tempfile.TemporaryDirectory() as tmp:
        estate = os.path.join(tmp, "estate")
        store = os.path.join(tmp, "store")
        os.makedirs(estate)
        box_dir = os.path.join(estate, "box-7")
        write_journal(box_dir, [
            journal_row(event_id="0193b2c4-0000-7000-8000-0000000000ee",
                        outcome="succeeded"),
        ])
        write_audit_tail(box_dir, [{
            "ts": "2026-10-21T07:44:00Z", "event": "deploy",
            "result": "ok", "to": commit, "components": "cua-driver",
        }])
        with open(os.path.join(box_dir, "status.json"), "w") as fh:
            json.dump(_status_json(), fh)
        with open(os.path.join(box_dir, "snapshot.json"), "w") as fh:
            json.dump(_snapshot_json(commit), fh)
        proc = subprocess.run(
            [sys.executable, INVENTORY, "collect",
             "--estate", estate, "--store", store],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, proc.stderr
        # Event leg: exactly the journal row (no legacy translation of
        # the same deploy).
        stored, err = events.load_events(store)
        assert err is None
        box_rows = [e for e in stored if e.get("box_id") == "box-7"]
        assert [e["event_id"] for e in box_rows] == [
            "0193b2c4-0000-7000-8000-0000000000ee"]
        # Version leg: the box record exists and carries the
        # audit-tail-derived repo_commit claim.
        snap = _store_snapshot(store)
        assert snap["boxes"]["box-7"]["versions"]["repo_commit"] == commit


def test_collect_migration_seam_journals_each_event_once():
    # Temporal exclusivity: run N on the legacy path journals the
    # audit-derived (UUIDv5) row; the journal then appears; run N+1
    # journals the NEW incident under its native (UUIDv7) id and must
    # NOT re-translate the overlapping audit tail — each underlying
    # event lands exactly once.
    old_commit, new_commit = "d" * 40, "e" * 40
    with tempfile.TemporaryDirectory() as tmp:
        estate = os.path.join(tmp, "estate")
        store = os.path.join(tmp, "store")
        os.makedirs(estate)
        box_dir = os.path.join(estate, "box-7")
        old_line = {"ts": "2026-10-21T06:00:00Z", "event": "deploy",
                    "result": "ok", "to": old_commit,
                    "components": "cua-driver"}
        write_audit_tail(box_dir, [old_line])
        proc = subprocess.run(
            [sys.executable, INVENTORY, "collect",
             "--estate", estate, "--store", store],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, proc.stderr
        # The journal appears (sink wired); the audit tail still holds
        # the old line plus the new deploy's audit line.
        write_journal(box_dir, [
            journal_row(event_id="0193b2c4-0000-7000-8000-0000000000ef",
                        outcome="succeeded", to=new_commit),
        ])
        write_audit_tail(box_dir, [old_line, {
            "ts": "2026-10-21T07:44:00Z", "event": "deploy",
            "result": "ok", "to": new_commit, "components": "cua-driver",
        }])
        proc = subprocess.run(
            [sys.executable, INVENTORY, "collect",
             "--estate", estate, "--store", store],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.returncode == 0, proc.stderr
        stored, err = events.load_events(store)
        assert err is None
        box_rows = [e for e in stored if e.get("box_id") == "box-7"]
        assert len(box_rows) == 2
        # The legacy row (UUIDv5, old commit) and the journal row
        # (native UUIDv7, new commit) — the new deploy's audit line was
        # NOT translated a second time.
        by_to = {e.get("to"): e for e in box_rows}
        assert set(by_to) == {old_commit, new_commit}
        assert by_to[new_commit]["event_id"] == \
            "0193b2c4-0000-7000-8000-0000000000ef"


def test_collect_empty_journal_is_loud_and_skips_audit_translation():
    # An empty (or all-blank) journal still flips the exclusive switch:
    # say so loudly, or the operator cannot distinguish "box emitted
    # nothing" from "sink broke".
    with tempfile.TemporaryDirectory() as tmp:
        box_dir = os.path.join(tmp, "box-7")
        write_journal(box_dir, [])
        write_audit_tail(box_dir, [{
            "ts": "2026-10-21T07:44:00Z", "event": "deploy",
            "result": "ok", "to": "d" * 40, "components": "cua-driver",
        }])
        evs, _, notes = events.collect_box_events(
            box_dir, "box-7", RECEIVED_AT)
        assert evs == []
        assert any("present but yielded no events" in n for n in notes)
        # The audit tail's deploy line was NOT translated: evs is empty
        # and the note records the skipped translation explicitly.


def test_collect_directory_at_journal_path_is_loud_not_fatal():
    # A directory (or otherwise unreadable path) at the journal path
    # fails closed with a loud note — never a raise, never a silent
    # fall back to audit translation (which would double-journal
    # already-journaled rows).
    with tempfile.TemporaryDirectory() as tmp:
        box_dir = os.path.join(tmp, "box-7")
        os.makedirs(os.path.join(box_dir, "update-events.jsonl"))
        write_audit_tail(box_dir, [{
            "ts": "2026-10-21T07:44:00Z", "event": "deploy",
            "result": "ok", "to": "d" * 40, "components": "cua-driver",
        }])
        evs, _, notes = events.collect_box_events(
            box_dir, "box-7", RECEIVED_AT)
        assert evs == []
        assert any("update-events.jsonl unreadable" in n for n in notes)


def test_append_events_dedups_duplicates_inside_one_batch():
    # Two rows with the same (box_id, event_id) inside ONE collect
    # append exactly one journal row — the paging rules must never
    # read the duplicate twice.
    with tempfile.TemporaryDirectory() as store:
        evs, _, _ = events.canonicalize_journal_rows(
            [journal_row(event_id="0193b2c4-0000-7000-8000-0000000000f0"),
             journal_row(event_id="0193b2c4-0000-7000-8000-0000000000f0")],
            "box-7", RECEIVED_AT)
        assert len(evs) == 2  # canonicalizer does not dedup; the leg does
        appended, duplicates, err = events.append_events(store, evs)
        assert err is None
        assert appended == 1
        assert duplicates == 1
        stored, err = events.load_events(store)
        assert err is None
        assert len(stored) == 1
