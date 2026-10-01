"""Retention tests for the fleet journal 90-day/30-day discipline
(G17 S2, issue #779).

`fleet events prune` compacts event rows 30-90 days old into per-day
outcome histograms keyed (box, component, build) in
events_histograms.jsonl and drops rows >= 90 days old; `fleet
inventory prune` drops inventory journal rows >= 90 days old and
rebuilds the snapshot. Both run under the store-scoped journal lock
and rewrite journals atomically.

Run from the repo root:  python3 -m pytest fleet/test_retention.py -q

Hermetic: stores live under tmp dirs; no network, no home-dir writes.
Prune time is pinned via the now= parameter (CLI tests use rows far
from the boundaries so wall-clock drift cannot flake them).
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

FLEET = os.path.dirname(os.path.abspath(__file__))
EVENTS = os.path.join(FLEET, "events.py")
INVENTORY = os.path.join(FLEET, "inventory.py")

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def _import():
    if FLEET not in sys.path:
        sys.path.insert(0, FLEET)
    import events
    import inventory
    return events, inventory


events, inventory = _import()


def _event(box_id, event_id, age_days=None, emitted=None, outcome="succeeded",
           to="abc123", component="repo"):
    if emitted is None:
        emitted = (NOW - timedelta(days=age_days)).isoformat()
    return {
        "schema": "fleet-event/1",
        "event_id": event_id,
        "box_id": box_id,
        "emitted_at": emitted,
        "received_at": NOW.isoformat(),
        "kind": "deploy",
        "outcome": outcome,
        "component": component,
        "subcomponent": None,
        "from": "000000",
        "to": to,
        "note": "test",
    }


def _write(store, name, rows, raw_lines=()):
    os.makedirs(store, exist_ok=True)
    with open(os.path.join(store, name), "w", encoding="utf-8") as fh:
        for line in raw_lines:
            fh.write(line + "\n")
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _read(store, name):
    rows = []
    with open(os.path.join(store, name), "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def _read_raw(store, name):
    with open(os.path.join(store, name), "r", encoding="utf-8") as fh:
        return fh.read()


def test_bands_keep_compact_drop(tmp_path):
    """10d rows stay raw, 45d rows compact into histograms, 100d rows
    are dropped outright."""
    store = str(tmp_path / "store")
    _write(store, "events.jsonl", [
        _event("box1", "evt-keep", age_days=10),
        _event("box1", "evt-compact", age_days=45, outcome="failed"),
        _event("box1", "evt-drop", age_days=100),
    ])
    summary, err = events.prune_events(store, now=NOW)
    assert err is None, err
    assert summary["kept"] == 1
    assert summary["compacted"] == 1
    assert summary["dropped"] == 1
    rows = _read(store, "events.jsonl")
    assert [r["event_id"] for r in rows] == ["evt-keep"]
    hist = _read(store, "events_histograms.jsonl")
    assert len(hist) == 1
    bucket = hist[0]
    assert bucket["schema"] == "fleet-event-histogram/1"
    assert bucket["box_id"] == "box1"
    assert bucket["component"] == "repo"
    assert bucket["build"] == "abc123"
    assert bucket["day"] == (NOW - timedelta(days=45)).date().isoformat()
    assert bucket["counts"] == {"failed": 1}
    assert bucket["folded_at"] == NOW.isoformat()


def test_exact_boundaries(tmp_path):
    """Exactly 30d compacts (30d <= age), exactly 90d drops (age >= 90d).
    These pin the band edges the docstring promises."""
    store = str(tmp_path / "store")
    _write(store, "events.jsonl", [
        _event("box1", "evt-30", age_days=30),
        _event("box1", "evt-90", age_days=90),
        _event("box1", "evt-29", age_days=29, outcome="failed"),
    ])
    summary, err = events.prune_events(store, now=NOW)
    assert err is None, err
    assert summary["kept"] == 1, summary
    assert summary["compacted"] == 1, summary
    assert summary["dropped"] == 1, summary
    rows = _read(store, "events.jsonl")
    assert [r["event_id"] for r in rows] == ["evt-29"]


def test_histogram_merges_across_prunes(tmp_path):
    """Two prunes folding different raw rows from the same
    (day, box, component, build) bucket add to its counts — no second
    bucket row, no lost counts."""
    store = str(tmp_path / "store")
    day_iso = (NOW - timedelta(days=45)).isoformat()
    _write(store, "events.jsonl",
           [_event("box1", "evt-a", emitted=day_iso, outcome="succeeded")])
    summary, err = events.prune_events(store, now=NOW)
    assert err is None and summary["compacted"] == 1, (summary, err)
    # A second raw row from the same UTC day, freshly aged past 30d.
    _write(store, "events.jsonl",
           [_event("box1", "evt-b", emitted=day_iso, outcome="failed")])
    later = NOW + timedelta(days=10)
    summary, err = events.prune_events(store, now=later)
    assert err is None and summary["compacted"] == 1, (summary, err)
    hist = _read(store, "events_histograms.jsonl")
    assert len(hist) == 1, hist
    assert hist[0]["counts"] == {"failed": 1, "succeeded": 1}, hist
    # The raw journal holds no compacted rows after either prune.
    assert _read(store, "events.jsonl") == []


def test_reprune_is_noop(tmp_path):
    """A second prune with nothing to do changes no bytes: no-op
    prunes are observable as no-ops (and never duplicate histograms)."""
    store = str(tmp_path / "store")
    _write(store, "events.jsonl", [
        _event("box1", "evt-keep", age_days=10),
        _event("box1", "evt-compact", age_days=45),
    ])
    summary, err = events.prune_events(store, now=NOW)
    assert err is None and summary["compacted"] == 1
    before_events = _read_raw(store, "events.jsonl")
    before_hist = _read_raw(store, "events_histograms.jsonl")
    summary, err = events.prune_events(store, now=NOW)
    assert err is None, err
    assert summary["kept"] == 1 and summary["compacted"] == 0 \
        and summary["dropped"] == 0, summary
    assert _read_raw(store, "events.jsonl") == before_events
    assert _read_raw(store, "events_histograms.jsonl") == before_hist


def test_undatable_future_malformed_kept(tmp_path):
    """Missing/unparseable emitted_at rows are kept and counted as
    undatable; future-dated rows are kept (never prune the future);
    malformed lines survive verbatim."""
    store = str(tmp_path / "store")
    no_ts = _event("box1", "evt-no-ts", age_days=45)
    del no_ts["emitted_at"]
    bad_ts = _event("box1", "evt-bad-ts", age_days=45, emitted="not-a-time")
    future = _event("box1", "evt-future",
                    emitted=(NOW + timedelta(days=1)).isoformat())
    _write(store, "events.jsonl", [no_ts, bad_ts, future],
           raw_lines=["{this is not json"])
    summary, err = events.prune_events(store, now=NOW)
    assert err is None, err
    assert summary["skipped_undatable"] == 2, summary
    assert summary["kept"] == 1, summary  # the future-dated row
    assert summary["compacted"] == 0 and summary["dropped"] == 0, summary
    raw = _read_raw(store, "events.jsonl")
    assert "{this is not json" in raw
    rows = _read(store, "events.jsonl")
    assert sorted(r["event_id"] for r in rows) == \
        ["evt-bad-ts", "evt-future", "evt-no-ts"]


def _alert(alert_id, age_days, acked, fired=None):
    return {
        "schema": "fleet-alert/1",
        "alert_id": alert_id,
        "rule": "rollback-failed",
        "fired_at": fired if fired is not None
        else (NOW - timedelta(days=age_days)).isoformat(),
        "box_id": "box1",
        "acked": acked,
    }


def test_alert_prune_rules(tmp_path):
    """Only acknowledged alerts >= 90d old are dropped. Unacknowledged
    alerts are never dropped; young or undatable acked alerts stay."""
    store = str(tmp_path / "store")
    _write(store, "events.jsonl", [])
    _write(store, "alerts.jsonl", [
        _alert("old-acked", 100, True),
        _alert("old-unacked", 100, False),
        _alert("young-acked", 10, True),
        _alert("undatable-acked", 0, True, fired="garbage"),
    ])
    summary, err = events.prune_events(store, now=NOW)
    assert err is None, err
    assert summary["alerts_dropped"] == 1, summary
    assert summary["alerts_kept"] == 3, summary
    rows = _read(store, "alerts.jsonl")
    assert sorted(r["alert_id"] for r in rows) == \
        ["old-unacked", "undatable-acked", "young-acked"]


def test_prune_missing_store(tmp_path):
    """Pruning a nonexistent store fails loudly (exit-2 class) and does
    not create the directory as a side effect; a file squatting on the
    store path is an error too."""
    missing = str(tmp_path / "no-store")
    err = events.cmd_events_prune(missing)
    assert err is not None and "not found" in err, err
    assert not os.path.exists(missing)
    err = inventory.cmd_prune(missing)
    assert err is not None and "not found" in err, err
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    err = events.cmd_events_prune(str(blocker))
    assert err is not None and "not a directory" in err, err


def _inv_record(box_id, age_days=None, observed=None):
    if observed is None:
        observed = (NOW - timedelta(days=age_days)).isoformat()
    return {
        "schema": "fleet-inventory-record/1",
        "box_id": box_id,
        "observed_at": observed,
        "reporter": "test",
        "versions": {"repo_commit": "abc123"},
    }


def test_inventory_prune_drops_old_and_rebuilds(tmp_path):
    """Inventory rows >= 90d old are dropped; the snapshot is rebuilt
    from the pruned journal, so a box whose only records expired
    disappears from the snapshot honestly."""
    store = str(tmp_path / "store")
    _write(store, "journal.jsonl", [
        _inv_record("oldbox", age_days=100),
        _inv_record("youngbox", age_days=10),
        _inv_record("youngbox", age_days=100),  # superseded, expired
    ])
    summary, err = inventory.prune_journal(store, now=NOW)
    assert err is None, err
    assert summary["dropped"] == 2, summary
    assert summary["kept"] == 1, summary
    rows = _read(store, "journal.jsonl")
    assert [r["box_id"] for r in rows] == ["youngbox"]
    snapshot, err = inventory.load_snapshot(store)
    assert err is None, err
    assert sorted(snapshot["boxes"]) == ["youngbox"], snapshot["boxes"]


def test_inventory_prune_keeps_undatable(tmp_path):
    """Inventory rows with missing/unparseable/future observed_at are
    kept; a no-op prune leaves the journal byte-identical."""
    store = str(tmp_path / "store")
    no_ts = _inv_record("box1", age_days=100)
    del no_ts["observed_at"]
    bad_ts = _inv_record("box2", age_days=100, observed="junk")
    future = _inv_record("box3",
                         observed=(NOW + timedelta(days=5)).isoformat())
    _write(store, "journal.jsonl", [no_ts, bad_ts, future],
           raw_lines=["[1,2,3"])
    before = _read_raw(store, "journal.jsonl")
    summary, err = inventory.prune_journal(store, now=NOW)
    assert err is None, err
    assert summary["dropped"] == 0, summary
    assert summary["skipped_undatable"] == 2, summary
    assert _read_raw(store, "journal.jsonl") == before


def test_append_journal_fails_closed_on_lock_error(tmp_path, monkeypatch):
    """append_journal takes the store-scoped journal lock (it would
    otherwise race prune's os.replace and journal into the void); a
    lock failure fails the append loudly instead of proceeding
    unsynchronized."""
    def _boom(store_dir):
        raise events.JournalLockError("lock unavailable")
    monkeypatch.setattr(events, "journal_lock", _boom)
    n, err = inventory.append_journal(
        str(tmp_path / "store"), [_inv_record("box1", age_days=1)])
    assert n is None and err == "lock unavailable", (n, err)


def _run_cli(argv):
    return subprocess.run(
        [sys.executable, INVENTORY, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def test_cli_prune_end_to_end(tmp_path):
    """Both CLIs exit 0 and print the one-line summary; the event CLI
    path honors the same banding as the library call."""
    store = str(tmp_path / "store")
    _write(store, "events.jsonl", [
        _event("box1", "evt-old", age_days=200),
        _event("box1", "evt-new", age_days=1),
    ])
    _write(store, "journal.jsonl", [
        _inv_record("oldbox", age_days=200),
        _inv_record("newbox", age_days=1),
    ])
    proc = _run_cli(["events", "prune", "--store", store])
    assert proc.returncode == 0, proc.stderr
    assert "fleet events: pruned" in proc.stdout, proc.stdout
    rows = _read(store, "events.jsonl")
    assert [r["event_id"] for r in rows] == ["evt-new"]
    proc = _run_cli(["prune", "--store", store])
    assert proc.returncode == 0, proc.stderr
    assert "fleet inventory: pruned" in proc.stdout, proc.stdout
    rows = _read(store, "journal.jsonl")
    assert [r["box_id"] for r in rows] == ["newbox"]
    proc = _run_cli(["events", "prune", "--store",
                     str(tmp_path / "no-store")])
    assert proc.returncode == 2, (proc.returncode, proc.stderr)
