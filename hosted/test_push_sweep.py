"""Tests for hosted/push_sweep.py (#1063 — D9 sweep scheduler build slice).

The fixture DDL below is the #988 contract (§§1.2–1.4) plus the D57
partial unique index (same as test_push_enqueue.py) plus an `approvals`
fixture pinning the #872 record shape (box_id, aid, owner_id, status,
decision, decision_seq, created_at/expires_at as epoch ints).
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hosted import push_enqueue, push_sweep

DDL_APPROVALS = """
CREATE TABLE approvals (
  box_id       TEXT NOT NULL,
  aid          TEXT NOT NULL,
  owner_id     TEXT NOT NULL,
  summary      TEXT NOT NULL,
  detail       TEXT,
  status       TEXT NOT NULL,
  decision     TEXT,
  decision_seq INTEGER,
  decided_by   TEXT,
  decided_at   REAL,
  created_at   INTEGER NOT NULL,
  expires_at   INTEGER NOT NULL,
  PRIMARY KEY (box_id, aid)
);
"""

DDL_BUDGET_COUNTERS = """
CREATE TABLE IF NOT EXISTS push_budget_counters (
  scope_type   TEXT NOT NULL,
  scope_id     TEXT NOT NULL,
  window_start TEXT NOT NULL,
  count        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (scope_type, scope_id, window_start)
);
"""

DDL_SEND_RESULTS = """
CREATE TABLE IF NOT EXISTS push_send_results (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  at              TEXT NOT NULL,
  owner_principal TEXT NOT NULL,
  box_id          TEXT NOT NULL,
  device          TEXT NOT NULL,
  event_kind      TEXT NOT NULL,
  event_key       TEXT NOT NULL,
  outcome         TEXT NOT NULL,
  http_status     INTEGER,
  latency_ms      REAL,
  sent_at         REAL,
  vapid_key_id    TEXT
);
CREATE INDEX IF NOT EXISTS idx_push_send_results_dedup
  ON push_send_results(box_id, event_kind, event_key);
CREATE INDEX IF NOT EXISTS idx_push_send_results_tenant
  ON push_send_results(owner_principal, at);
"""

DDL_DIGEST_STATE = """
CREATE TABLE IF NOT EXISTS push_digest_state (
  owner_principal TEXT NOT NULL,
  window_start    TEXT NOT NULL,
  count           INTEGER NOT NULL DEFAULT 0,
  enqueued_at     TEXT,
  PRIMARY KEY (owner_principal, window_start)
);
"""

DDL_PAGE_ONCE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_push_send_results_page_once
  ON push_send_results(box_id, event_kind, event_key)
  WHERE outcome IN ('queued', 'suppressed_budget', 'suppressed_terminal');
"""

T0 = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
EPOCH_T0 = int(T0.timestamp())


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.executescript(DDL_APPROVALS + DDL_BUDGET_COUNTERS + DDL_SEND_RESULTS
                    + DDL_DIGEST_STATE + DDL_PAGE_ONCE_INDEX)
    yield c
    c.close()


def _registry(mapping):
    def resolve_owner(box_id):
        return mapping[box_id]
    return resolve_owner


def _file_approval(conn, box_id, aid, *, ttl=600, age=400,
                   status="pending", decision=None, decision_seq=None):
    created = EPOCH_T0 - age
    conn.execute(
        "INSERT INTO approvals (box_id, aid, owner_id, summary, status,"
        " decision, decision_seq, created_at, expires_at)"
        " VALUES (?, ?, ?, 's', ?, ?, ?, ?, ?)",
        (box_id, aid, "owner-1", status, decision, decision_seq,
         created, created + ttl))
    conn.commit()


def _queued(conn, event_kind=None):
    q = "SELECT event_kind, event_key FROM push_send_results" \
        " WHERE outcome = 'queued'"
    params = ()
    if event_kind is not None:
        q += " AND event_kind = ?"
        params = (event_kind,)
    return conn.execute(q, params).fetchall()


def _outcome_count(conn, outcome):
    return conn.execute(
        "SELECT COUNT(*) FROM push_send_results WHERE outcome = ?",
        (outcome,)).fetchone()[0]


# --- Pass 1: reminders ------------------------------------------------------

def test_due_reminder_pages_exactly_once(conn):
    # age 400 > ttl/2 (300): due.
    _file_approval(conn, "box-1", "aid-1")
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.reminders.get("queued") == 1
    assert len(_queued(conn, "reminder")) == 1
    # Second sweep: the D75 anti-join excludes the already-paged
    # reminder from candidates (it would have returned `duplicate`
    # from the boundary) — still exactly one page, never a second.
    s2 = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s2.reminders == {}
    assert s2.candidates_seen == 0
    assert len(_queued(conn, "reminder")) == 1


def test_decided_approval_pages_zero_times_no_audit(conn):
    # Decided rows are never candidates (the D68 hint's status filter),
    # so gate-1 never runs: zero pages AND zero audit rows. Operator
    # visibility for decided approvals is the approvals record itself.
    _file_approval(conn, "box-1", "aid-1", status="approved",
                   decision="approve", decision_seq=1)
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert _queued(conn) == []
    assert _outcome_count(conn, "suppressed_terminal") == 0
    assert s.candidates_seen == 0


def test_terminal_by_clock_writes_exactly_one_audit_row(conn):
    # The candidate SELECT is a hint (D68): this row matches the hint
    # (status pending, no decision) but the gate-1 re-read finds it
    # terminal because now >= expires_at. Only this clock-terminal
    # class reaches gate-1 and earns the D61 audit — decided/expired
    # rows never do (see the test above).
    # created == EPOCH_T0-700, ttl 600 -> reminder_at = EPOCH_T0-400
    # <= now: due.
    _file_approval(conn, "box-1", "aid-1", ttl=600, age=700)
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.reminders.get("superseded_terminal") == 1
    assert _queued(conn) == []
    assert _outcome_count(conn, "suppressed_terminal") == 1
    # Repeat sweep: the D61 audit is idempotent — still exactly one.
    s2 = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s2.reminders.get("superseded_terminal") == 1
    assert _outcome_count(conn, "suppressed_terminal") == 1


def test_not_due_approval_skips(conn):
    # age 100 < ttl/2 (300): not due yet. The D68 hint excludes it
    # from candidates entirely (the complement of the policy's
    # reminder_not_due) — no page, no policy call.
    _file_approval(conn, "box-1", "aid-1", age=100)
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.candidates_seen == 0
    assert s.reminders.get("reminder_not_due") is None
    assert _queued(conn) == []


def test_short_ttl_never_pages(conn):
    # ttl 200 < 300: the D68 hint excludes it entirely (D8).
    _file_approval(conn, "box-1", "aid-1", ttl=200, age=150)
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.candidates_seen == 0
    assert _queued(conn) == []
    assert s.reminders.get("queued") is None


def test_corrupt_record_fails_loud(conn, capsys):
    # created_at stored as text: the D49 adapter must ValueError, not
    # silently skip (D59). D78: the loudness is per-candidate now —
    # the corrupt row is counted `poisoned` and logged loudly while
    # the pass completes (#1095).
    conn.execute(
        "INSERT INTO approvals (box_id, aid, owner_id, summary, status,"
        " created_at, expires_at)"
        " VALUES ('box-1', 'aid-1', 'owner-1', 's', 'pending',"
        " 'not-an-epoch', ?)", (EPOCH_T0 + 600,))
    conn.commit()
    _file_approval(conn, "box-2", "aid-2")
    reg = _registry({"box-1": "owner-1", "box-2": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.reminders.get("poisoned") == 1
    err = capsys.readouterr().err
    assert "poisoned" in err and "box-1" in err and "aid-1" in err
    # The healthy candidate behind the poison row still pages.
    assert s.reminders.get("queued") == 1


def test_missing_resolve_owner_fails_loud(conn):
    _file_approval(conn, "box-1", "aid-1")
    with pytest.raises(ValueError):
        push_sweep.sweep_once(conn, now=T0, resolve_owner=None)


def test_bad_owner_from_registry_fails_loud(conn, capsys):
    # A resolver that returns a bad owner is still fail-closed per D2
    # (no guessed owner) — D78: the failure is per-candidate now, a
    # loud `poisoned` count while the pass completes (#1095).
    _file_approval(conn, "box-1", "aid-1")
    s = push_sweep.sweep_once(conn, now=T0,
                              resolve_owner=_registry({"box-1": ""}))
    assert s.reminders.get("poisoned") == 1
    assert s.reminders.get("queued") is None
    assert "poisoned" in capsys.readouterr().err
    assert _queued(conn, "reminder") == []


def test_reminders_disabled_skips_pass(conn):
    # D71: the DO-alarm change retires the reminder pass via this flag.
    _file_approval(conn, "box-1", "aid-1")
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg,
                              reminders_enabled=False)
    assert s.reminders_enabled is False
    assert s.reminders == {"skipped": True}
    assert _queued(conn) == []


def test_candidates_paged_bounded(conn):
    # page_size=2, 5 due approvals on distinct boxes (each box gets
    # its own D10 budget): 3 pages, all swept, none truncated.
    for i in range(5):
        _file_approval(conn, "box-%d" % i, "aid-%d" % i)
    reg = _registry({"box-%d" % i: "owner-1" for i in range(5)})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg,
                              page_size=2)
    assert s.candidates_seen == 5
    assert s.pages_truncated is False
    assert s.reminders.get("queued") == 5


def test_max_pages_truncates_leaves_rest_for_next_sweep(conn):
    for i in range(5):
        _file_approval(conn, "box-%d" % i, "aid-%d" % i)
    reg = _registry({"box-%d" % i: "owner-1" for i in range(5)})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg,
                              page_size=2, max_pages=1)
    assert s.candidates_seen == 2
    assert s.pages_truncated is True
    assert s.reminders.get("queued") == 2
    # D75 self-healing: the D75 anti-join excludes the two already-
    # paged reminders, so the next sweep reaches the remainder instead
    # of re-dominating the first pages as duplicates.
    s2 = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg,
                               page_size=10)
    assert s2.reminders.get("queued") == 3
    assert s2.reminders.get("duplicate") is None
    assert s2.pages_truncated is False


def test_paged_then_clock_expired_still_audits(conn):
    # D75 precision: the anti-join excludes only candidates the policy
    # would certainly `duplicate`. A paged approval that later
    # clock-expires stays a candidate — gate-1 still writes its D61
    # audit (pre-D75 behavior preserved; the terminal check runs
    # before the boundary dedup).
    _file_approval(conn, "box-1", "aid-1", ttl=600, age=400)
    reg = _registry({"box-1": "owner-1"})
    s1 = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s1.reminders.get("queued") == 1
    later = T0 + timedelta(seconds=300)  # past expires_at (T0+200)
    s2 = push_sweep.sweep_once(conn, now=later, resolve_owner=reg)
    assert s2.reminders.get("superseded_terminal") == 1
    assert _outcome_count(conn, "suppressed_terminal") == 1
    # Still exactly one page — the audit is not a second page.
    assert len(_queued(conn, "reminder")) == 1


def test_paged_then_corrupted_still_fails_loud(conn, capsys):
    # D75 precision: a paged record that corrupts between ticks stays
    # a candidate — the D59 fail-loud still fires instead of the sweep
    # silently excluding it. D78: the loudness is per-candidate now —
    # the corrupt row is counted `poisoned` and logged loudly while the
    # healthy candidate behind it still pages (no more whole-pass
    # abort; #1095).
    _file_approval(conn, "box-1", "aid-1", ttl=600, age=400)
    reg = _registry({"box-1": "owner-1", "box-2": "owner-1"})
    s1 = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s1.reminders.get("queued") == 1
    conn.execute(
        "UPDATE approvals SET created_at = 'garbage'"
        " WHERE box_id = 'box-1' AND aid = 'aid-1'")
    conn.commit()
    # A healthy candidate filed after the corruption: pre-D78 the
    # sweep raised at box-1 (sorts first in keyset order) and box-2
    # never paged. Now box-2 pages and box-1 is a loud poisoned count
    # — still loud every tick (D59), never silent.
    _file_approval(conn, "box-2", "aid-2", ttl=600, age=400)
    s2 = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s2.reminders.get("queued") == 1
    assert s2.reminders.get("poisoned") == 1
    err = capsys.readouterr().err
    assert "poisoned" in err and "box-1" in err and "aid-1" in err
    # Next tick: the poison row is still a candidate, still loud.
    s3 = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s3.reminders.get("poisoned") == 1
    assert "poisoned" in capsys.readouterr().err

def test_resolver_failure_mid_sweep_is_fail_closed_and_resumable(conn, capsys):
    # box-0 pages, then the registry fails on box-1: D78 isolates the
    # failure — box-1 is a loud `poisoned` count (never a guessed
    # owner, still fail-closed per D2) while the pass completes; the
    # next sweep with a healthy registry resumes box-1, and box-0
    # dedups cleanly.
    for i in range(2):
        _file_approval(conn, "box-%d" % i, "aid-%d" % i)

    def flaky(box_id):
        if box_id == "box-1":
            raise RuntimeError("registry down")
        return "owner-1"

    s1 = push_sweep.sweep_once(conn, now=T0, resolve_owner=flaky)
    assert s1.reminders.get("queued") == 1
    assert s1.reminders.get("poisoned") == 1
    assert s1.candidates_seen == 2
    assert "poisoned" in capsys.readouterr().err
    assert len(_queued(conn, "reminder")) == 1
    reg = _registry({"box-0": "owner-1", "box-1": "owner-1"})
    s2 = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    # box-1 pages; box-0 is anti-joined out (already paged — it would
    # have deduped at the boundary). Exactly the two pages, no more.
    assert s2.reminders.get("queued") == 1
    assert s2.reminders.get("poisoned") is None
    assert s2.candidates_seen == 1
    assert len(_queued(conn, "reminder")) == 2


# --- Pass 2: digests --------------------------------------------------------

def test_digest_fires_in_same_sweep_as_coalescing(conn):
    # D67: a reminder that tips the box over budget must coalesce into
    # the digest in the SAME sweep, not after the digest already fired.
    # Exhaust the per-box budget (3) so the reminder suppresses and
    # coalesces; the owner budget (10) still has room for the digest.
    ws = push_enqueue.hour_bucket(T0)
    for i in range(3):
        push_enqueue.enqueue_page(
            conn, event_kind="approval_filed", owner_principal="owner-1",
            box_id="box-1", key_material="k%d" % i, now=T0)
    assert push_enqueue.get_digest_count(conn, "owner-1", ws) == 0
    _file_approval(conn, "box-1", "aid-1")
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.reminders.get("suppressed_budget") == 1
    assert push_enqueue.get_digest_count(conn, "owner-1", ws) == 1
    # The digest pass ran after the reminder pass in the same sweep:
    # the digest is queued now, not on a later tick.
    assert s.digests.get("queued") == 1
    assert len(_queued(conn, "digest")) == 1


def test_no_coalesced_digest_fires_nothing(conn):
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.digests == {}
    assert _queued(conn, "digest") == []


def _seed_digest(conn, owner, window, count, enqueued_at=None):
    conn.execute(
        "INSERT INTO push_digest_state"
        " (owner_principal, window_start, count, enqueued_at)"
        " VALUES (?, ?, ?, ?)",
        (owner, window, count, enqueued_at))
    conn.commit()


def _digest_row(conn, owner, window):
    return conn.execute(
        "SELECT count, enqueued_at FROM push_digest_state"
        " WHERE owner_principal = ? AND window_start = ?",
        (owner, window)).fetchone()


def test_digest_pending_past_window_fires_with_own_key(conn):
    # D76: the hour-boundary strand — coalescing that landed on a past
    # window's row after that window's last digest-pass tick fires late
    # with the past window's own page-once key, and enqueued_at is
    # stamped. (T0 is 2026-10-05T12Z; the stranded row is T10.)
    past = "2026-10-05T10"
    _seed_digest(conn, "owner-1", past, 3)
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.digests.get("queued") == 1
    rows = _queued(conn, "digest")
    assert len(rows) == 1
    assert rows[0][1] == "owner-1\x00" + past
    count, enqueued_at = _digest_row(conn, "owner-1", past)
    assert count == 3
    assert enqueued_at is not None


def test_digest_fired_window_never_refires(conn):
    # D76: a window whose digest already fired (enqueued_at set) is
    # never refired, even with more coalesced counts — D67's accepted
    # drift for post-fire coalescing stands.
    past = "2026-10-05T10"
    _seed_digest(conn, "owner-1", past, 5,
                 enqueued_at="2026-10-05T11:59:05+00:00")
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.digests == {}
    assert _queued(conn, "digest") == []


def test_digest_budget_suppressed_stays_pending_and_retries(conn):
    # D76: a budget-suppressed digest leaves enqueued_at NULL (so a
    # later sweep retries) and coalesces into the current window; once
    # budget frees, the pending past window fires.
    past = "2026-10-05T10"
    _seed_digest(conn, "owner-1", past, 2)
    ws = push_enqueue.hour_bucket(T0)
    for _ in range(10):
        assert push_enqueue.reserve_budget(conn, None, "owner-1", ws)
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.digests.get("suppressed_budget") == 1
    assert _digest_row(conn, "owner-1", past)[1] is None
    cur_count, cur_enq = _digest_row(conn, "owner-1", ws)
    assert cur_count == 1 and cur_enq is None
    for _ in range(10):
        push_enqueue.release_reservation(conn, None, "owner-1", ws)
    s2 = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s2.digests.get("queued") == 2
    assert _digest_row(conn, "owner-1", past)[1] is not None
    assert _digest_row(conn, "owner-1", ws)[1] is not None
    keys = sorted(r[1] for r in _queued(conn, "digest"))
    assert keys == sorted(["owner-1\x00" + past, "owner-1\x00" + ws])


# --- Pass 3: watchers --------------------------------------------------------

def test_stale_watcher_pages_once_per_epoch(conn):
    reg = _registry({"box-1": "owner-1"})
    derived = [("box-1", "epoch-1")]
    s = push_sweep.sweep_once(
        conn, now=T0, resolve_owner=reg,
        derive_stale=lambda c, m: derived)
    assert s.stale_watchers.get("queued") == 1
    assert len(_queued(conn, "heartbeat_stale")) == 1
    # Same epoch again: page-once dedup.
    s2 = push_sweep.sweep_once(
        conn, now=T0, resolve_owner=reg,
        derive_stale=lambda c, m: derived)
    assert s2.stale_watchers.get("duplicate") == 1
    assert len(_queued(conn, "heartbeat_stale")) == 1


def test_token_warning_pages_once_per_generation(conn):
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(
        conn, now=T0, resolve_owner=reg,
        derive_token_warnings=lambda c, m: [("box-1", "hash-1")])
    assert s.token_warnings.get("queued") == 1
    # A rotation (new hash) is a new generation: pages again (D13).
    s2 = push_sweep.sweep_once(
        conn, now=T0, resolve_owner=reg,
        derive_token_warnings=lambda c, m: [("box-1", "hash-2")])
    assert s2.token_warnings.get("queued") == 1
    assert len(_queued(conn, "token_expiry_warning")) == 2


def test_watchers_off_by_default(conn):
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.stale_watchers == {"skipped": True}
    assert s.token_warnings == {"skipped": True}
    assert _queued(conn) == []


# --- D78: per-candidate error isolation (#1095) --------------------------------

def test_digest_pass_isolates_corrupt_window(conn, capsys):
    # D78: a corrupt digest-state row (empty owner_principal fails the
    # policy's key-material gate) is a loud `poisoned` count while the
    # healthy window still fires in the same pass — pre-D78 the whole
    # digest pass aborted at the corrupt row ("", ws sorts first).
    ws = push_enqueue.hour_bucket(T0)
    _seed_digest(conn, "", ws, 1)  # corrupt: fails _require_key_material
    _seed_digest(conn, "owner-1", ws, 1)
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=T0, resolve_owner=reg)
    assert s.digests.get("queued") == 1
    assert s.digests.get("poisoned") == 1
    err = capsys.readouterr().err
    assert "poisoned" in err and "digests" in err
    assert _digest_row(conn, "owner-1", ws)[1] is not None


def test_watchers_isolate_per_candidate_errors(conn, capsys):
    # D78: a raising candidate in one watcher is a loud `poisoned`
    # count; the sibling candidate and the other watcher still run.
    def flaky(box_id):
        if box_id == "box-a":
            raise RuntimeError("registry down")
        return "owner-1"
    s = push_sweep.sweep_once(
        conn, now=T0, resolve_owner=flaky,
        derive_stale=lambda c, m: [("box-a", "epoch-1"),
                                   ("box-b", "epoch-2")],
        derive_token_warnings=lambda c, m: [("box-b", "hash-1")])
    assert s.stale_watchers.get("queued") == 1
    assert s.stale_watchers.get("poisoned") == 1
    err = capsys.readouterr().err
    assert "poisoned" in err and "box-a" in err
    # The token watcher ran independently of the stale watcher's poison.
    assert s.token_warnings.get("queued") == 1
    assert s.token_warnings.get("poisoned") is None


def test_watcher_derivation_failure_stops_only_that_watcher(conn, capsys):
    # D78: a derivation that raises mid-iteration cannot continue (the
    # generator is dead) — one loud `poisoned` count for that watcher;
    # the other watcher still runs.
    def broken(conn, moment):
        yield ("box-1", "epoch-1")
        raise RuntimeError("derivation blew up")
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(
        conn, now=T0, resolve_owner=reg,
        derive_stale=broken,
        derive_token_warnings=lambda c, m: [("box-1", "hash-1")])
    assert s.stale_watchers.get("queued") == 1
    assert s.stale_watchers.get("poisoned") == 1
    assert "poisoned" in capsys.readouterr().err
    assert s.token_warnings.get("queued") == 1


def test_watcher_derivation_call_time_failure_is_loud(conn, capsys):
    # D78: caller-wired logic that fails at call time is one loud
    # `poisoned` count for that watcher, not a whole-sweep abort.
    def broken(conn, moment):
        raise RuntimeError("derivation down")
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(
        conn, now=T0, resolve_owner=reg,
        derive_stale=broken,
        derive_token_warnings=lambda c, m: [("box-1", "hash-1")])
    assert s.stale_watchers == {"poisoned": 1}
    assert "poisoned" in capsys.readouterr().err
    assert s.token_warnings.get("queued") == 1


def test_base_exception_still_aborts_whole_sweep(conn):
    # D78 pin: only `Exception` is isolated. BaseException
    # (KeyboardInterrupt, SystemExit) is an operator signal, not data
    # corruption — it still aborts the whole sweep.
    _file_approval(conn, "box-1", "aid-1")

    def kb(box_id):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        push_sweep.sweep_once(conn, now=T0, resolve_owner=kb)


# --- Clock ------------------------------------------------------------------

def test_single_clock_threaded_through(conn):
    # D73: one `now`, epoch form accepted, shared by all passes.
    _file_approval(conn, "box-1", "aid-1")
    reg = _registry({"box-1": "owner-1"})
    s = push_sweep.sweep_once(conn, now=float(EPOCH_T0),
                              resolve_owner=reg)
    assert s.reminders.get("queued") == 1


def test_bad_clock_fails_loud(conn):
    reg = _registry({"box-1": "owner-1"})
    with pytest.raises(ValueError):
        push_sweep.sweep_once(conn, now="soon", resolve_owner=reg)
