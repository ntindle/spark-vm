"""Concurrency tests for the fleet journal lock (issue #813).

append_events / evaluate_alerts / ack_alert serialize their
load -> dedup -> write sequences under a store-scoped flock
(<store>/journal.lock). These tests prove it with real overlapping
processes — flock is per-fd, so threads cannot exercise it. Every worker
waits on a barrier so the mutations genuinely overlap; the journal is
then asserted to hold exactly one copy of each row, and every worker's
ack to have stuck.

Run from the repo root:  python3 -m pytest fleet/test_events_lock.py -q

Hermetic: stores live under tmp dirs; no network, no home-dir writes.
Workers are forked (Linux-only — the fleet estate is Linux, and so is
CI). Each test joins its workers with a timeout: a hung worker means
the lock deadlocked, and the test fails loudly instead of hanging the
suite.
"""

import json
import multiprocessing
import os
import sys
import tempfile

import pytest

FLEET = os.path.dirname(os.path.abspath(__file__))

_N_WORKERS = 6
_JOIN_TIMEOUT_S = 120


def _import_events():
    if FLEET not in sys.path:
        sys.path.insert(0, FLEET)
    import events
    return events


events = _import_events()


def _make_event(box_id, event_id):
    return {
        "box_id": box_id,
        "event_id": event_id,
        "emitted_at": "2026-10-01T16:00:00Z",
        "received_at": "2026-10-01T16:00:01Z",
        "kind": "deploy",
        "outcome": "succeeded",
    }


def _run_workers(target, nworkers, *args):
    """Spawn nworkers forked processes behind a barrier, join them with
    a deadlock-guarding timeout, and return their result payloads."""
    barrier = multiprocessing.Barrier(nworkers)
    queue = multiprocessing.Queue()
    procs = [multiprocessing.Process(target=target,
                                     args=(barrier, queue) + args)
             for _ in range(nworkers)]
    for proc in procs:
        proc.start()
    hung = []
    for proc in procs:
        proc.join(_JOIN_TIMEOUT_S)
        if proc.is_alive():
            hung.append(proc)
    for proc in hung:
        proc.terminate()
        proc.join(10)
    assert not hung, \
        "worker processes hung under the journal lock (deadlock?)"
    for proc in procs:
        assert proc.exitcode == 0, \
            "worker exited with code %s" % proc.exitcode
    results = []
    while not queue.empty():
        results.append(queue.get())
    return results


def _append_worker(barrier, queue, store, payload):
    barrier.wait()
    appended, duplicates, err = events.append_events(store, payload)
    queue.put((appended, duplicates, err))


def _read_journal_lines(store, name):
    path = os.path.join(store, name)
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_concurrent_append_events_dedups(tmp_path):
    """Six overlapping collects appending the same 25 events journal
    exactly 25 rows: without the lock the load -> dedup -> append race
    duplicates rows."""
    store = str(tmp_path / "store")
    payload = [_make_event("box1", "evt-%02d" % i) for i in range(25)]
    results = _run_workers(_append_worker, _N_WORKERS, store, payload)
    assert all(err is None for _, _, err in results), results
    assert sum(appended for appended, _, _ in results) == 25, results
    rows = _read_journal_lines(store, "events.jsonl")
    assert len(rows) == 25
    assert sorted(r["event_id"] for r in rows) == \
        sorted("evt-%02d" % i for i in range(25))
    assert os.path.isfile(os.path.join(store, "journal.lock"))


def _evaluate_worker(barrier, queue, store, fired_at):
    barrier.wait()
    fired, err = events.evaluate_alerts(store, fired_at)
    queue.put((len(fired) if fired is not None else None, err))


def test_concurrent_evaluate_alerts_single_row(tmp_path):
    """Six overlapping alert evaluations over one rollback-failed event
    journal exactly one alert row: without the lock the load-alerts ->
    dedup -> append race appends the same alert_id repeatedly."""
    store = str(tmp_path / "store")
    seed = [{
        "box_id": "box1",
        "event_id": "evt-rb",
        "emitted_at": "2026-10-01T16:00:00Z",
        "received_at": "2026-10-01T16:00:01Z",
        "kind": "rollback",
        "outcome": "rollback-failed",
        "note": "bad build",
    }]
    appended, duplicates, err = events.append_events(store, seed)
    assert err is None and appended == 1, (appended, duplicates, err)
    fired_at = "2026-10-01T16:30:00+00:00"
    results = _run_workers(_evaluate_worker, _N_WORKERS, store, fired_at)
    assert all(err is None for _, err in results), results
    assert sum(n for n, _ in results) == 1, results
    rows = _read_journal_lines(store, "alerts.jsonl")
    assert len(rows) == 1
    assert rows[0]["rule"] == "rollback-failed"
    assert rows[0]["acked"] is False


def _ack_worker(barrier, queue, store, alert_id):
    barrier.wait()
    found, err = events.ack_alert(store, alert_id)
    queue.put((found, err))


def test_concurrent_ack_alert_no_lost_update(tmp_path):
    """Four overlapping acks of four distinct alerts all stick: without
    the lock the load -> rewrite race lets the last os.replace clobber
    the earlier acks."""
    store = str(tmp_path / "store")
    os.makedirs(store)
    alert_ids = ["alert-%d" % i for i in range(4)]
    with open(os.path.join(store, "alerts.jsonl"), "w",
              encoding="utf-8") as fh:
        for alert_id in alert_ids:
            fh.write(json.dumps({"schema": "fleet-alert/1",
                                 "alert_id": alert_id,
                                 "rule": "rollback-failed",
                                 "fired_at": "2026-10-01T16:30:00+00:00",
                                 "acked": False}) + "\n")
    barrier = multiprocessing.Barrier(4)
    queue = multiprocessing.Queue()
    procs = [multiprocessing.Process(target=_ack_worker,
                                     args=(barrier, queue, store, aid))
             for aid in alert_ids]
    for proc in procs:
        proc.start()
    hung = []
    for proc in procs:
        proc.join(_JOIN_TIMEOUT_S)
        if proc.is_alive():
            hung.append(proc)
    for proc in hung:
        proc.terminate()
        proc.join(10)
    assert not hung, "ack workers hung under the journal lock (deadlock?)"
    assert all(proc.exitcode == 0 for proc in procs)
    results = [queue.get() for _ in procs]
    assert all(found is True and err is None for found, err in results), \
        results
    rows = _read_journal_lines(store, "alerts.jsonl")
    assert len(rows) == 4
    assert all(r["acked"] is True for r in rows), rows


def test_serial_paths_unchanged(tmp_path):
    """The lock does not change single-process behavior: append dedups,
    evaluate fires once and then dedups, ack is idempotent, and acks on
    a missing store stay (False, None) without creating the dir."""
    store = str(tmp_path / "store")
    payload = [_make_event("box1", "evt-%02d" % i) for i in range(3)]
    appended, duplicates, err = events.append_events(store, payload)
    assert (appended, duplicates, err) == (3, 0, None)
    appended, duplicates, err = events.append_events(store, payload)
    assert (appended, duplicates, err) == (0, 3, None)
    fired_at = "2026-10-01T16:30:00+00:00"
    fired, err = events.evaluate_alerts(store, fired_at)
    assert err is None and fired == []
    rb = dict(payload[0], outcome="rollback-failed", kind="rollback",
              event_id="evt-rb", note="bad build")
    appended, _, err = events.append_events(store, [rb])
    assert err is None and appended == 1
    fired, err = events.evaluate_alerts(store, fired_at)
    assert err is None and len(fired) == 1
    fired, err = events.evaluate_alerts(store, fired_at)
    assert err is None and fired == []
    rows = _read_journal_lines(store, "alerts.jsonl")
    alert_id = rows[0]["alert_id"]
    found, err = events.ack_alert(store, alert_id)
    assert (found, err) == (True, None)
    found, err = events.ack_alert(store, "no-such-alert")
    assert (found, err) == (False, None)
    missing = str(tmp_path / "no-store")
    found, err = events.ack_alert(missing, "anything")
    assert (found, err) == (False, None)
    assert not os.path.exists(missing)


def test_lock_fail_closed_when_store_unwritable(tmp_path):
    """If the store dir cannot be created (here: a file squats on the
    path), journal mutations fail loudly instead of proceeding
    unsynchronized."""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir", encoding="utf-8")
    store = str(blocker)
    appended, duplicates, err = events.append_events(
        store, [_make_event("box1", "evt-1")])
    assert appended is None and duplicates is None
    assert err is not None and "cannot create store dir" in err, err
    assert blocker.read_text(encoding="utf-8") == "not a dir"
    fired, err = events.evaluate_alerts(store, "2026-10-01T16:30:00+00:00")
    assert fired is None and err is not None
