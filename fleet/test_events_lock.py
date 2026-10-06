"""Concurrency tests for the fleet journal lock (issue #813).

append_events / evaluate_alerts / ack_alert serialize their
load -> dedup -> write sequences under a store-scoped flock
(<store>/journal.lock). These tests prove it with real overlapping
processes — flock is per-fd, so threads cannot exercise it. Every worker
waits on a barrier so the mutations genuinely overlap; the journal is
then asserted to hold exactly one copy of each row, and every worker's
ack to have stuck.

The lock's wait is bounded (#1007): a holder stopped with SIGSTOP (or
wedged on a stuck filesystem) never releases its flock, so waiters get
a loud JournalLockError naming the lock file after the timeout instead
of blocking forever — the #1007 tests below pin that contract, again
with real stopped processes.

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
import signal
import sys
import tempfile
import time

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
    found, err = events.ack_alert(store, "anything")
    assert found is None and err is not None
    assert "not a directory" in err, err


# --- Bounded wait (#1007) -------------------------------------------------

def _stopped_lock_holder(store, ready, resume):
    """Child body for the #1007 wedge scenario: take the journal lock,
    signal readiness, then block until the parent resumes us. The PARENT
    performs the SIGSTOP (see _LockHolder._stop_child) and the resume is
    a multiprocessing.Event — never signal semantics. Two races this
    avoids: (1) a child that SIGSTOPs itself races the parent's cleanup
    SIGCONT — a SIGCONT that lands first is a silent no-op and the
    child then stops itself after the only resume was spent; (2)
    signal.pause() does NOT wake on SIGCONT (the stop resumes but
    pause() keeps sleeping), so pause() can never be the resume
    mechanism."""
    with events.journal_lock(store):
        ready.set()
        resume.wait()
    # Exiting the with-block releases the lock.


def _brief_lock_holder(store, hold_s, ready):
    """Child body for the serialize-not-skip case: hold the lock
    briefly, then release it normally."""
    with events.journal_lock(store):
        ready.set()
        time.sleep(hold_s)


def _proc_state(pid):
    """Single-letter process state from /proc (Linux-only, like the
    rest of this file). Raises ProcessLookupError/FileNotFoundError
    when the pid is gone."""
    with open("/proc/%d/stat" % pid, "r", encoding="utf-8") as fh:
        data = fh.read()
    # comm may itself contain spaces/parens: the state field follows
    # the last ')'.
    return data.rsplit(")", 1)[1].split()[0]


class _LockHolder:
    """Fork a child holding the journal lock (stopped or brief), and
    guarantee it is resumed and reaped on exit even if the test fails.

    For the stopped holder the parent performs the SIGSTOP itself and
    verifies the child actually reached the stopped state before the
    test body runs — deterministic ordering, no self-stop race. Cleanup
    uses timed joins only, escalating to SIGKILL (which, unlike SIGTERM,
    terminates even a stopped process): no untimed wait anywhere, so a
    wedged child can fail the test but never hang the suite."""

    def __init__(self, store, hold_s=None):
        self.store = store
        self.hold_s = hold_s
        self.ready = multiprocessing.Event()
        self.resume = multiprocessing.Event()
        if hold_s is None:
            target = _stopped_lock_holder
            args = (store, self.ready, self.resume)
        else:
            target, args = _brief_lock_holder, (store, hold_s, self.ready)
        self.proc = multiprocessing.Process(target=target, args=args)

    def __enter__(self):
        self.proc.start()
        try:
            if not self.ready.wait(30):
                raise AssertionError(
                    "lock-holder child never took the lock")
            if self.hold_s is None:
                self._stop_child()
        except BaseException:
            self._cleanup()
            raise
        # The brief holder set readiness while still holding the lock;
        # the stopped holder is verified stopped by _stop_child.
        return self

    def _stop_child(self):
        """SIGSTOP the child and wait until it is actually stopped."""
        pid = self.proc.pid
        if pid is None:
            raise AssertionError("lock-holder child has no pid")
        try:
            os.kill(pid, signal.SIGSTOP)
        except ProcessLookupError:
            raise AssertionError(
                "lock-holder child died before it could be stopped")
        for _ in range(200):
            try:
                if _proc_state(pid) == "T":
                    return
            except (ProcessLookupError, FileNotFoundError):
                raise AssertionError(
                    "lock-holder child died while being stopped")
            time.sleep(0.01)
        raise AssertionError(
            "lock-holder child never entered the stopped state")

    def _cleanup(self):
        proc = self.proc
        pid = proc.pid
        if pid is not None:
            try:
                os.kill(pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
        # Wake the child via the Event (a no-op if it already exited;
        # the flag stays set, so there is no lost-wakeup race even if
        # the child has not reached resume.wait() yet). The brief
        # holder never waits on it — harmless.
        self.resume.set()
        proc.join(10)
        if proc.is_alive():
            # Escalate: SIGKILL terminates even a stopped process
            # (a pending SIGTERM would not).
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, TypeError):
                pass
            proc.join(10)
        assert not proc.is_alive(), \
            "lock-holder child could not be reaped"

    def __exit__(self, *exc):
        self._cleanup()


def test_lock_times_out_on_sigstop_holder(tmp_path):
    """A holder stopped with SIGSTOP never releases its flock: the
    waiter's bounded wait raises JournalLockError (not a silent
    forever-block), and the error names the lock file and points the
    operator at the holder — the exact #1007 failure mode."""
    store = str(tmp_path / "store")
    os.makedirs(store)
    with _LockHolder(store):
        with pytest.raises(events.JournalLockError) as excinfo:
            with events.journal_lock(store, timeout_s=2):
                pytest.fail("acquired a lock held by a stopped process")
    msg = str(excinfo.value)
    assert "journal.lock" in msg, msg
    assert "SIGSTOP" in msg, msg
    assert "fuser" in msg, msg
    assert "2 seconds" in msg, msg


def test_lock_timeout_zero_fails_fast_when_held(tmp_path):
    """timeout_s=0 is the fail-fast knob: one LOCK_NB attempt, then the
    loud error — no sleeping when the caller wants an answer now."""
    store = str(tmp_path / "store")
    os.makedirs(store)
    with _LockHolder(store):
        start = time.monotonic()
        with pytest.raises(events.JournalLockError):
            with events.journal_lock(store, timeout_s=0):
                pass
        assert time.monotonic() - start < 2


def test_lock_negative_timeout_rejected(tmp_path):
    """A negative timeout is a caller bug: fail loudly and immediately,
    never silently clamp to a forever-wait."""
    store = str(tmp_path / "store")
    with pytest.raises(events.JournalLockError) as excinfo:
        with events.journal_lock(store, timeout_s=-1):
            pass
    assert "negative" in str(excinfo.value)


def test_lock_nan_timeout_rejected(tmp_path):
    """NaN is not a timeout: like a negative timeout it is a caller
    bug and must fail loudly, never degrade to the unbounded wait
    #1007 eliminated (NaN comparisons never trip the deadline)."""
    store = str(tmp_path / "store")
    with pytest.raises(events.JournalLockError) as excinfo:
        with events.journal_lock(store, timeout_s=float("nan")):
            pass
    assert "non-negative" in str(excinfo.value)


def test_lock_waits_its_turn_then_acquires(tmp_path):
    """The bounded wait preserves the design intent: a waiter behind a
    normally-slow holder still serializes (no silent skip, no loud
    error) — only the pathological wait becomes a failure."""
    store = str(tmp_path / "store")
    os.makedirs(store)
    with _LockHolder(store, hold_s=1.0):
        start = time.monotonic()
        with events.journal_lock(store, timeout_s=30):
            elapsed = time.monotonic() - start
    assert elapsed >= 0.5, \
        "acquired without waiting behind the holder (%0.2fs)" % elapsed
    assert elapsed < 30


def test_journal_mutation_fails_loud_on_wedged_lock(tmp_path, monkeypatch):
    """End to end through the public mutation path: with the lock held
    by a stopped process, append_events returns the loud timeout error
    — the collect fails instead of journaling unsynchronized."""
    monkeypatch.setattr(events, "_JOURNAL_LOCK_WAIT_TIMEOUT_S", 2)
    store = str(tmp_path / "store")
    with _LockHolder(store):
        appended, duplicates, err = events.append_events(
            store, [_make_event("box1", "evt-1")])
    assert appended is None and duplicates is None
    assert err is not None, "wedged lock produced no error"
    assert "journal.lock" in err and "SIGSTOP" in err, err
    # Nothing was journaled unsynchronized behind the wedge.
    assert not os.path.exists(os.path.join(store, "events.jsonl"))
