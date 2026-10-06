#!/usr/bin/env python3
"""Tests for the relay session-liveness journal (R1, #486).

Run: ``python3 -m pytest hosted/`` from the repo root.
"""

import json
import multiprocessing
import os
import signal
import time

import pytest

import relay_liveness as rl

NOW = 1_758_000_000.0


def frame(**over):
    f = {
        "session_id": "sess-1",
        "vm_id": "vm-1",
        "opened_at": NOW - 600,
        "last_bytes_at": NOW - 10,
        "closed_at": None,
        "close_cause": None,
        "hostkey_verified": True,
        "bytes_in": 42,
        "bytes_out": 7,
    }
    f.update(over)
    return f


@pytest.fixture()
def journal(tmp_path, monkeypatch):
    path = str(tmp_path / "journal.jsonl")
    monkeypatch.setenv("RELAY_SESSION_JOURNAL", path)
    return path


# ---------------------------------------------------------------------------
# Schema validation (§2 — metadata only, never payload)


def test_valid_frame_passes():
    rl.validate_frame(frame())


def test_unknown_key_rejected_never_payload():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(payload_b64="aGVsbG8="))


def test_missing_required_rejected():
    bad = frame()
    del bad["session_id"]
    with pytest.raises(ValueError):
        rl.validate_frame(bad)


def test_bad_close_cause_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(closed_at=NOW, close_cause="mystery"))


def test_closed_requires_cause():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(closed_at=NOW, close_cause=None))


def test_open_must_not_carry_cause():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(closed_at=None, close_cause="client_closed"))


def test_negative_counter_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(bytes_in=-1))


def test_last_bytes_before_open_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(opened_at=NOW, last_bytes_at=NOW - 5))


def test_hostkey_verified_must_be_bool():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(hostkey_verified="yes"))


# ---------------------------------------------------------------------------
# Emission + prober exclusion


def test_emit_journaled(journal):
    assert rl.emit_frame(**frame()) == "journaled"
    with open(journal, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    assert len(rows) == 1
    assert rows[0]["session_id"] == "sess-1"
    assert rows[0]["vm_id"] == "vm-1"


def test_emit_invalid_frame_writes_nothing(journal):
    bad = frame()
    bad["payload"] = "x"
    with pytest.raises(ValueError):
        rl.emit_frame(**bad)
    assert not os.path.exists(journal)


def test_prober_frame_dropped_never_journaled(journal):
    assert rl.emit_frame(**frame(prober=True, session_id="probe-1")) == "dropped"
    assert not os.path.exists(journal)


def test_emit_missing_journal_dir_fails_loud(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RELAY_SESSION_JOURNAL", str(tmp_path / "nope" / "journal.jsonl")
    )
    with pytest.raises(OSError):
        rl.emit_frame(**frame())


def test_journal_file_mode_0600(journal):
    rl.emit_frame(**frame())
    assert os.stat(journal).st_mode & 0o777 == 0o600


# ---------------------------------------------------------------------------
# Rotation — the journal's own contract (#376; unbounded = fail)


def test_rotation_bounds_total_footprint(journal, monkeypatch):
    monkeypatch.setattr(rl, "MAX_JOURNAL_BYTES", 200)
    monkeypatch.setattr(rl, "MAX_ROTATED", 2)
    for i in range(60):
        rl.emit_frame(**frame(session_id="sess-%d" % i))
    gens = [journal] + ["%s.%d" % (journal, g) for g in (1, 2)]
    assert not os.path.exists("%s.3" % journal), "generation .3 must not exist"
    total = sum(os.path.getsize(g) for g in gens if os.path.exists(g))
    assert total <= 3 * 200 + 4096, "total footprint must stay bounded"


def test_rotation_preserves_newest_frame(journal, monkeypatch):
    monkeypatch.setattr(rl, "MAX_JOURNAL_BYTES", 200)
    monkeypatch.setattr(rl, "MAX_ROTATED", 2)
    for i in range(60):
        rl.emit_frame(**frame(session_id="sess-%d" % i))
    assert rl.relay_session_liveness("vm-1", now=NOW)["session_id"] == "sess-59"


def test_rotation_evicts_oldest_frames(journal, monkeypatch):
    monkeypatch.setattr(rl, "MAX_JOURNAL_BYTES", 200)
    monkeypatch.setattr(rl, "MAX_ROTATED", 2)
    for i in range(60):
        rl.emit_frame(**frame(session_id="sess-%d" % i))
    seen = set()
    for fr, _gen in rl._iter_frames(journal):
        seen.add(fr["session_id"])
    assert "sess-0" not in seen, "oldest frames must be evicted"
    assert "sess-59" in seen


# ---------------------------------------------------------------------------
# The query surface — relay_session_liveness(vm_id)


def test_liveness_active(journal):
    rl.emit_frame(**frame())
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got == {
        "session_id": "sess-1",
        "state": "active",
        "last_bytes_at": NOW - 10,
        "hostkey_verified": True,
    }


def test_liveness_idle_past_threshold(journal):
    rl.emit_frame(**frame(last_bytes_at=NOW - 301))
    assert rl.relay_session_liveness("vm-1", now=NOW)["state"] == "idle"


def test_liveness_idle_boundary_stays_active(journal):
    rl.emit_frame(**frame(last_bytes_at=NOW - 300))
    assert rl.relay_session_liveness("vm-1", now=NOW)["state"] == "active"


def test_liveness_closed(journal):
    rl.emit_frame(
        **frame(
            opened_at=NOW - 3600,
            closed_at=NOW - 60,
            close_cause="idle_timeout",
            last_bytes_at=NOW - 61,
        )
    )
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got["state"] == "closed"


def test_liveness_hostkey_verified_surfaced(journal):
    rl.emit_frame(**frame(hostkey_verified=False))
    assert rl.relay_session_liveness("vm-1", now=NOW)["hostkey_verified"] is False


def test_liveness_newest_frame_wins(journal):
    rl.emit_frame(
        **frame(session_id="old", opened_at=NOW - 1200, last_bytes_at=NOW - 1000)
    )
    rl.emit_frame(
        **frame(session_id="new", opened_at=NOW - 600, last_bytes_at=NOW - 5)
    )
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got["session_id"] == "new"
    assert got["state"] == "active"


def test_liveness_unknown_vm_is_none(journal):
    rl.emit_frame(**frame())
    assert rl.relay_session_liveness("vm-9", now=NOW) is None


def test_liveness_missing_journal_is_none(tmp_path, monkeypatch):
    monkeypatch.setenv("RELAY_SESSION_JOURNAL", str(tmp_path / "absent.jsonl"))
    assert rl.relay_session_liveness("vm-1", now=NOW) is None


def test_liveness_missing_journal_dir_is_darkness_not_error(tmp_path, monkeypatch):
    # The module runs on machines where the journal dir was never
    # deployed (operator laptop, fresh control plane): darkness, not
    # an exception — the R3 consumer must never need to catch.
    monkeypatch.setenv(
        "RELAY_SESSION_JOURNAL", str(tmp_path / "never-deployed" / "j.jsonl")
    )
    assert rl.relay_session_liveness("vm-1", now=NOW) is None


def test_query_tolerates_non_utf8_bytes(journal):
    # A hand edit or disk-level corruption can leave undecodable bytes;
    # the "never fatal" guarantee must hold for them too.
    rl.emit_frame(**frame())
    with open(journal, "ab") as f:
        f.write(b'{"vm_id": "vm-1", "broken": \xff\xfe}\n')
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got is not None
    assert got["session_id"] == "sess-1"


def test_query_tolerates_torn_trailing_line(journal):
    rl.emit_frame(**frame())
    with open(journal, "a", encoding="utf-8") as f:
        f.write('{"session_id": "torn", "vm_id": "vm-1"')  # no newline, invalid
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got["session_id"] == "sess-1"


def test_bool_counter_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(bytes_in=True))


def test_tenant_id_must_be_str_when_present():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(tenant_id=123))
    rl.validate_frame(frame(tenant_id="tenant-a"))


def test_closed_at_before_last_bytes_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(
            frame(
                closed_at=NOW - 100,
                close_cause="client_closed",
                last_bytes_at=NOW - 50,
            )
        )


def test_liveness_other_vm_frames_ignored(journal):
    rl.emit_frame(**frame(vm_id="vm-2", session_id="other"))
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got is None


# ---------------------------------------------------------------------------
# Bounded journal lock (#1082) — a stopped or wedged writer can delay the
# instrument, never freeze it silently.


def _proc_state(pid):
    """Single-letter process state from /proc (Linux-only, like the
    fleet lock tests this mirrors). Raises ProcessLookupError /
    FileNotFoundError when the pid is gone."""
    with open("/proc/%d/stat" % pid, "r", encoding="utf-8") as fh:
        data = fh.read()
    # comm may itself contain spaces/parens: the state field follows
    # the last ')'.
    return data.rsplit(")", 1)[1].split()[0]


def _stopped_holder_body(path, ready, resume):
    """Child body for the #1082 wedge scenario: take the exclusive
    journal lock, signal readiness, then block until the parent resumes
    us. The PARENT performs the SIGSTOP (see _LockHolder._stop_child)
    and the resume is a multiprocessing.Event — never signal semantics.
    Parent-driven stop avoids the self-stop race (a child that SIGSTOPs
    itself races the parent's cleanup SIGCONT: a SIGCONT that lands
    first is a silent no-op and the child then stops itself after the
    only resume was spent)."""
    with rl._journal_locked(path, exclusive=True):
        ready.set()
        resume.wait()
    # Exiting the with-block releases the lock.


def _brief_holder_body(path, hold_s, ready):
    """Child body for the serialize-not-skip case: hold the lock
    briefly, then release it normally."""
    with rl._journal_locked(path, exclusive=True):
        ready.set()
        time.sleep(hold_s)


class _LockHolder:
    """Fork a child holding the relay journal's exclusive lock (stopped
    or brief), and guarantee it is resumed and reaped on exit even if
    the test fails.

    For the stopped holder the parent performs the SIGSTOP itself and
    verifies the child actually reached the stopped state before the
    test body runs — deterministic ordering, no self-stop race.
    Cleanup uses timed joins only, escalating to SIGKILL (which, unlike
    SIGTERM, terminates even a stopped process): no untimed wait
    anywhere, so a wedged child can fail the test but never hang the
    suite."""

    def __init__(self, path, hold_s=None):
        self.path = path
        self.hold_s = hold_s
        self.ready = multiprocessing.Event()
        self.resume = multiprocessing.Event()
        if hold_s is None:
            target = _stopped_holder_body
            args = (path, self.ready, self.resume)
        else:
            target, args = _brief_holder_body, (path, hold_s, self.ready)
        self.proc = multiprocessing.Process(target=target, args=args)

    def __enter__(self):
        self.proc.start()
        try:
            if not self.ready.wait(30):
                raise AssertionError("lock-holder child never took the lock")
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
            raise AssertionError("lock-holder child died before stopping")
        for _ in range(200):
            try:
                if _proc_state(pid) == "T":
                    return
            except (ProcessLookupError, FileNotFoundError):
                raise AssertionError("lock-holder child died while stopping")
            time.sleep(0.01)
        raise AssertionError("lock-holder child never stopped")

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
        assert not proc.is_alive(), "lock-holder child could not be reaped"

    def __exit__(self, *exc):
        self._cleanup()


def test_emit_lock_timeout_raises_loud(journal, monkeypatch):
    """A writer stopped with SIGSTOP while holding LOCK_EX never
    releases its flock: the emitter's bounded wait raises
    JournalLockError (not a silent forever-block), naming the lock
    sidecar and pointing the operator at the holder — the exact #1082
    failure mode."""
    monkeypatch.setattr(rl, "_JOURNAL_LOCK_WAIT_TIMEOUT_S", 2)
    with _LockHolder(journal):
        with pytest.raises(rl.JournalLockError) as excinfo:
            rl.emit_frame(**frame())
    msg = str(excinfo.value)
    assert journal + ".lock" in msg, msg
    assert "SIGSTOP" in msg, msg
    assert "fuser" in msg, msg
    assert "2 seconds" in msg, msg
    # JournalLockError is an OSError: emit_frame's fail-loud contract
    # ("raises OSError when the journal cannot be written") is intact.
    assert isinstance(excinfo.value, OSError)


def test_query_lock_timeout_raises_loud_not_darkness(journal, monkeypatch):
    """The issue's core: a wedged writer must not freeze the
    control-plane query path silently. The query takes the shared lock
    behind the stopped exclusive holder, waits its bounded turn, then
    raises — it never reads as darkness."""
    monkeypatch.setattr(rl, "_JOURNAL_LOCK_WAIT_TIMEOUT_S", 2)
    rl.emit_frame(**frame())  # the journal exists; darkness is off the table
    with _LockHolder(journal):
        with pytest.raises(rl.JournalLockError):
            rl.relay_session_liveness("vm-1", now=NOW)


def test_lock_timeout_zero_fails_fast_when_held(journal):
    """timeout_s=0 is the fail-fast knob: one LOCK_NB attempt, then the
    loud error — no sleeping when the caller wants an answer now."""
    with _LockHolder(journal):
        start = time.monotonic()
        with pytest.raises(rl.JournalLockError):
            with rl._journal_locked(journal, exclusive=False, timeout_s=0):
                pytest.fail("acquired a lock held by a stopped process")
        assert time.monotonic() - start < 2


def test_lock_negative_timeout_rejected(journal):
    """A negative timeout is a caller bug: fail loudly and immediately,
    never silently clamp to a forever-wait."""
    with pytest.raises(rl.JournalLockError) as excinfo:
        with rl._journal_locked(journal, timeout_s=-1):
            pass
    assert "non-negative" in str(excinfo.value)


def test_lock_nan_timeout_rejected(journal):
    """NaN is not a timeout: fail loudly instead of computing a
    nonsense deadline."""
    with pytest.raises(rl.JournalLockError):
        with rl._journal_locked(journal, timeout_s=float("nan")):
            pass


def test_lock_brief_holder_serializes_waiter(journal):
    """Normal contention still serializes: a waiter behind a
    briefly-held lock acquires it after release — the LOCK_NB loop
    waits its turn, it never skips or fails spuriously."""
    with _LockHolder(journal, hold_s=0.5):
        with rl._journal_locked(journal, exclusive=False, timeout_s=10):
            pass  # acquired after the holder released


def test_lock_missing_dir_stays_darkness(tmp_path, monkeypatch):
    """The FileNotFoundError carve-out: a journal dir that was never
    deployed still reads as darkness (None), never as a lock error —
    the wedge shape and the absent-instrument shape stay distinct."""
    monkeypatch.setenv(
        "RELAY_SESSION_JOURNAL", str(tmp_path / "never-deployed" / "j.jsonl")
    )
    assert rl.relay_session_liveness("vm-1", now=NOW) is None
