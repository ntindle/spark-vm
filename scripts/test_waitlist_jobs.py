"""Tests for site/waitlist_jobs.py + the waitlistd lifecycle additions
(H15 build, slice 3a).

Run from the repo root:  python3 -m pytest scripts/test_waitlist_jobs.py -q

Covers the contracts the lifecycle jobs must hold:
- docs/WAITLIST_OPERATIONS.md §4 (one +7d reminder with the §4 draft copy,
  queue position, "same link unless within 7d of expiry", 3/24h cap
  honored by every transactional send; 14d drop of unconfirmed rows,
  no third email)
- §5 (drop_at fixed at first submission — a re-submit must not postpone
  the drop; `dropped` terminal)
- docs/FUNNEL_MEASUREMENT.md §3.4 (reminder_sent + dropped events stay
  parseable by scripts/funnel_metrics.py; confirmed via=reminder follows
  the email the token arrived in)
- the Engineering deferred blocker from PR #165 (413 closes the
  connection instead of desyncing a keep-alive stream)

stdlib only, no network except one loopback integration test for the 413
(plus the service-level tests run in-process).
"""

import importlib.util
import json
import multiprocessing
import os
import socket
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "site")
SCRIPTS = os.path.join(REPO, "scripts")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # waitlist_jobs does `from waitlistd import ...`
    spec.loader.exec_module(mod)
    return mod


wd = load_module("waitlistd", os.path.join(SITE, "waitlistd.py"))
wj = load_module("waitlist_jobs", os.path.join(SITE, "waitlist_jobs.py"))

KEY = b"test-hmac-key-32-bytes-long-000000"
NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)


class MutClock:
    """A clock the test can move."""

    def __init__(self, start=NOW):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def make_service(clock=None, data_dir=None):
    tmp = data_dir or tempfile.mkdtemp(prefix="waitlist-jobs-test-")
    clock = clock or MutClock()
    return wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                              clock=clock), tmp, clock


def submit(service, email):
    return service.submit_form({"owner_email": email}, "127.0.0.1")


def spool_docs(tmp):
    spool = os.path.join(tmp, "spool")
    docs = []
    for name in sorted(os.listdir(spool)):
        with open(os.path.join(spool, name), encoding="utf-8") as fh:
            docs.append(json.load(fh))
    return docs


def events(tmp):
    path = os.path.join(tmp, "funnel_events.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# -- reminder -------------------------------------------------------------


def test_reminder_fires_at_plus_seven_days():
    svc, tmp, clock = make_service()
    status, _ = submit(svc, "rem@example.com")
    assert status == 200
    entry_id = svc.by_email["rem@example.com"]
    old_token = svc.rows[entry_id]["active_token"]

    clock.advance(days=8)
    assert svc.send_reminders() == 1
    row = svc.rows[entry_id]
    assert row["reminder_sent_at"] is not None
    assert row["active_token"] != old_token  # submit-minted token had ~7d
    assert old_token in svc.consumed  # left — the §4 freshness rule

    docs = spool_docs(tmp)
    reminder = [d for d in docs if d.get("kind") == "reminder"]
    assert len(reminder) == 1
    assert reminder[0]["subject"] == wd.REMINDER_SUBJECT
    assert "This is the last reminder" in reminder[0]["body"]
    assert "#1 in line" in reminder[0]["body"]
    assert row["active_token"] in reminder[0]["body"]

    evs = events(tmp)
    assert [e for e in evs if e["event"] == "reminder_sent"][0]["ref"] == entry_id


def test_reminder_not_before_plus_seven_days():
    svc, tmp, clock = make_service()
    submit(svc, "early@example.com")
    clock.advance(days=6, hours=23)
    assert svc.send_reminders() == 0
    assert len(spool_docs(tmp)) == 1  # only the original confirm email


def test_reminder_skips_confirmed():
    svc, tmp, clock = make_service()
    submit(svc, "done@example.com")
    row = svc.rows[svc.by_email["done@example.com"]]
    svc.confirm_post(row["active_token"])
    clock.advance(days=8)
    assert svc.send_reminders() == 0


def test_reminder_never_sent_after_drop_deadline():
    svc, tmp, clock = make_service()
    submit(svc, "late@example.com")
    clock.advance(days=15)  # reminder window long past, job ran late
    assert svc.send_reminders() == 0  # never a reminder this late
    assert not [d for d in spool_docs(tmp)
                if d.get("kind") == "reminder"]
    assert len(svc.drop_expired()) == 1  # the row goes to the drop job instead
    assert svc.by_email.get("late@example.com") is None  # dropped, unmapped


def test_reminder_is_idempotent():
    svc, tmp, clock = make_service()
    submit(svc, "once@example.com")
    clock.advance(days=8)
    assert svc.send_reminders() == 1
    assert svc.send_reminders() == 0
    assert len([d for d in spool_docs(tmp)
                if d.get("kind") == "reminder"]) == 1


def test_reminder_defers_when_capped():
    svc, tmp, clock = make_service()
    submit(svc, "capped@example.com")
    entry_id = svc.by_email["capped@example.com"]
    old_token = svc.rows[entry_id]["active_token"]
    clock.advance(days=8)
    # Three sends inside the 24h window — the cap bites.
    svc.rows[entry_id]["email_sends"] = [
        (clock.t - timedelta(hours=h)).timestamp() for h in (1, 2, 3)
    ]
    assert svc.send_reminders() == 0
    row = svc.rows[entry_id]
    assert row["reminder_sent_at"] is None  # deferred, not skipped
    assert row["active_token"] == old_token  # never strand the user
    assert old_token not in svc.consumed


def test_reminder_reuses_live_token_when_far_from_expiry():
    svc, tmp, clock = make_service()
    submit(svc, "late@example.com")
    entry_id = svc.by_email["late@example.com"]
    clock.advance(days=6)
    # A day-6 re-submit mints a fresh token with ~14d of life left.
    submit(svc, "late@example.com")
    fresh = svc.rows[entry_id]["active_token"]
    clock.advance(days=2)  # now at first-submit +8d: reminder is due
    assert svc.send_reminders() == 1
    row = svc.rows[entry_id]
    # §4 draft: "same link" when the live token is NOT within 7d of expiry.
    assert row["active_token"] == fresh
    assert fresh not in svc.consumed


def test_confirmed_via_reminder_follows_the_email():
    svc, tmp, clock = make_service()
    submit(svc, "via@example.com")
    entry_id = svc.by_email["via@example.com"]
    clock.advance(days=8)
    svc.send_reminders()
    token = svc.rows[entry_id]["active_token"]
    svc.confirm_post(token)
    confirmed = [e for e in events(tmp) if e["event"] == "confirmed"]
    assert len(confirmed) == 1
    assert confirmed[0]["attrs"]["via"] == "reminder"


def test_confirmed_via_original_unchanged():
    svc, tmp, clock = make_service()
    submit(svc, "orig@example.com")
    token = svc.rows[svc.by_email["orig@example.com"]]["active_token"]
    svc.confirm_post(token)
    confirmed = [e for e in events(tmp) if e["event"] == "confirmed"]
    assert confirmed[0]["attrs"]["via"] == "original"


def test_confirm_post_sees_row_dropped_by_another_process():
    svc1, tmp, _clock1 = make_service()
    submit(svc1, "stale@example.com")
    entry_id = svc1.by_email["stale@example.com"]
    token = svc1.rows[entry_id]["active_token"]
    # A second process (the drop job) mutates the shared data dir. Its own
    # clock is past the 14d deadline; svc1's view is now stale (pending).
    clock2 = MutClock()
    svc2 = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                              clock=clock2)
    clock2.advance(days=15)
    assert len(svc2.drop_expired()) == 1
    # confirm_post refreshes the persistent view under the data lock and
    # must NOT confirm the dropped row: the token is consumed, so it
    # renders the expired state.
    status, body = svc1.confirm_post(token)
    assert status == 200
    assert "Link expired" in body
    assert svc1.rows[entry_id]["status"] == "dropped"


def test_queue_position_confirmed_first_then_pending_fifo():
    svc, tmp, clock = make_service()
    submit(svc, "a@example.com")
    clock.advance(hours=1)
    submit(svc, "b@example.com")
    clock.advance(hours=1)
    submit(svc, "c@example.com")
    # b confirms — confirmed entries jump ahead of pending FIFO.
    svc.confirm_post(svc.rows[svc.by_email["b@example.com"]]["active_token"])
    ids = {m: svc.by_email[f"{m}@example.com"] for m in "abc"}
    assert svc.queue_position(ids["b"]) == 1
    assert svc.queue_position(ids["a"]) == 2
    assert svc.queue_position(ids["c"]) == 3


# -- drop -----------------------------------------------------------------


def test_drop_fires_at_fourteen_days():
    svc, tmp, clock = make_service()
    submit(svc, "dropme@example.com")
    entry_id = svc.by_email["dropme@example.com"]
    token = svc.rows[entry_id]["active_token"]
    clock.advance(days=15)
    dropped = svc.drop_expired()
    assert dropped == [entry_id]
    row = svc.rows[entry_id]
    assert row["status"] == "dropped"
    assert row["dropped_at"] is not None
    assert row["active_token"] is None
    assert token in svc.consumed
    assert entry_id not in svc.by_email
    evs = events(tmp)
    assert [e for e in evs if e["event"] == "dropped"][0]["ref"] == entry_id
    # A dropped token no longer confirms — renders the expired state.
    status, _ = svc.confirm_post(token)
    assert status == 200


def test_drop_spares_confirmed_and_young():
    svc, tmp, clock = make_service()
    submit(svc, "keep@example.com")
    submit(svc, "old@example.com")
    svc.confirm_post(svc.rows[svc.by_email["keep@example.com"]]["active_token"])
    clock.advance(days=13)
    submit(svc, "young@example.com")
    clock.advance(days=2)  # old row is now at +15d (droppable); young at +2d
    dropped = svc.drop_expired()
    assert len(dropped) == 1
    assert svc.rows[svc.by_email["keep@example.com"]]["status"] == "confirmed"
    young = [r for r in svc.rows.values()
             if r["owner_email"] == "young@example.com"][0]
    assert young["status"] == "pending"  # +2d — untouched


def test_resubmit_does_not_postpone_drop():
    svc, tmp, clock = make_service()
    submit(svc, "stubborn@example.com")
    entry_id = svc.by_email["stubborn@example.com"]
    first_drop_at = svc.rows[entry_id]["drop_at"]
    clock.advance(days=10)
    submit(svc, "stubborn@example.com")  # refreshes submitted_at + token
    row = svc.rows[entry_id]
    assert row["submitted_at"] != first_drop_at  # activity moved
    assert row["drop_at"] == first_drop_at  # the deadline did NOT move
    clock.advance(days=5)  # first-submit +15d
    assert svc.drop_expired() == [entry_id]


def test_drop_at_backfilled_for_legacy_rows():
    tmp = tempfile.mkdtemp(prefix="waitlist-jobs-legacy-")
    row = {
        "entry_id": "legacy1",
        "owner_email": "legacy@example.com",
        "muse_contact": None,
        "path": "form",
        "source": "form",
        "submitted_at": "2026-09-01T12:00:00Z",
        "confirmed_at": None,
        "status": "pending",
        "email_sends": [],
        "active_token": None,
    }
    with open(os.path.join(tmp, "rows.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
    svc, _, _ = make_service(data_dir=tmp)
    assert svc.rows["legacy1"]["drop_at"] == "2026-09-15T12:00:00Z"


# -- events stay parseable ------------------------------------------------


def test_dropped_and_reminder_events_parse_in_funnel_metrics():
    fm = load_module("funnel_metrics",
                     os.path.join(SCRIPTS, "funnel_metrics.py"))
    svc, tmp, clock = make_service()
    submit(svc, "metrics@example.com")
    clock.advance(days=8)
    svc.send_reminders()
    clock.advance(days=7)
    svc.drop_expired()
    rows = fm.load_events(os.path.join(tmp, "funnel_events.jsonl"))
    kinds = {r["event"] for r in rows}
    assert {"waitlist_submitted", "confirm_sent", "reminder_sent",
            "dropped"} <= kinds


# -- 413 closes keep-alive (PR #165 deferred Engineering blocker) ----------


def test_oversized_body_closes_connection():
    # PR #165 deferred Engineering blocker: on keep-alive connections the
    # unread remainder of an oversized body would desync the next request,
    # so the server must close instead of persisting. NOTE: this uses a
    # raw socket on purpose — http.client silently RECONNECTS when it
    # notices the server closed (sock goes None), so the close is
    # unobservable through HTTPConnection.
    tmp = tempfile.mkdtemp(prefix="waitlist-413-test-")
    svc = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                             clock=MutClock())
    wd._Handler.service = svc
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), wd._Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        port = httpd.server_address[1]
        s = socket.create_connection(("127.0.0.1", port), timeout=5)
        big = b"owner_email=" + b"a" * (wd.MAX_BODY_BYTES + 1)
        s.sendall(b"POST /waitlist/form HTTP/1.1\r\n"
                  b"Host: 127.0.0.1\r\n"
                  b"Content-Length: " + str(len(big)).encode() + b"\r\n"
                  b"Content-Type: application/x-www-form-urlencoded\r\n"
                  b"Connection: keep-alive\r\n"
                  b"\r\n" + big)
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = s.recv(4096)
            assert chunk, "server closed before sending the 413"
            head += chunk
        assert b" 413 " in head.split(b"\r\n", 1)[0], head[:60]
        # Drain the error page, then the server MUST hit EOF — a timeout
        # here means the connection was kept alive (the #165 desync bug).
        s.settimeout(3)
        try:
            while s.recv(65536):
                pass
        except socket.timeout:
            pytest.fail("server kept the connection alive after a 413")
    finally:
        httpd.shutdown()
        httpd.server_close()


# -- data lock ------------------------------------------------------------


def test_data_lock_serializes_concurrent_submits():
    svc, tmp, _ = make_service()
    errors = []

    def worker(i):
        # NOTE: do NOT take data_lock() here — submit_form() already takes
        # data_lock + the service lock itself, and flock on a second fd
        # from the same process blocks (deadlock).
        #
        # Every thread submits the SAME address: the dedup check-then-act
        # is the shared path this test must serialize. (Eight distinct
        # addresses would never touch the shared path — a lock-free
        # implementation would pass identically.)
        try:
            svc.submit_form({"owner_email": "race@example.com"},
                            "127.0.0.1")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    svc2 = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                              clock=MutClock())
    raced = [r for r in svc2.rows.values()
             if r["owner_email"] == "race@example.com"]
    assert len(raced) == 1  # the dedup race created exactly one row


def _child_remind_worker(data_dir, key_hex, out_q):
    """Mimic `waitlist_jobs.py --remind` in a SEPARATE process: take the
    cross-process lock, reload from disk, scan. Module-level so the
    multiprocessing child can run it; the child inherits the already
    imported wd module but builds its own service instance — the only
    thing the two processes share is the data dir and the flock."""
    key = bytes.fromhex(key_hex)
    with wd.data_lock(data_dir):
        service = wd.WaitlistService(data_dir, key,
                                     "https://waitlist.example.invalid")
        service.reload()
        out_q.put(service.send_reminders())


def test_two_job_processes_send_exactly_one_reminder():
    # The data lock's actual purpose: two --remind cron instances (or a
    # job racing the live daemon) must not double-send. Without the lock
    # both processes see the due row and both spool a reminder; with it,
    # exactly one does.
    clock = MutClock(start=wd.utcnow() - timedelta(days=8))
    svc, tmp, _ = make_service(clock=clock)
    submit(svc, "dupe@example.com")
    ctx = multiprocessing.get_context("fork")
    out_q = ctx.Queue()
    procs = [ctx.Process(target=_child_remind_worker,
                         args=(tmp, KEY.hex(), out_q)) for _ in range(2)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(60)
    assert all(p.exitcode == 0 for p in procs)
    assert sorted(out_q.get() for _ in procs) == [0, 1]
    assert len([d for d in spool_docs(tmp)
                if d.get("kind") == "reminder"]) == 1


# -- CLI ------------------------------------------------------------------


def test_jobs_cli_dry_run_writes_nothing(monkeypatch, capsys):
    tmp = tempfile.mkdtemp(prefix="waitlist-cli-test-")
    # The CLI runs on the REAL clock, not MutClock: submit 8 days in the
    # past (MutClock started back-dated from utcnow) so the +7d reminder
    # is due when the CLI scans — anchored to the real clock so the test
    # holds on any run date (a fixed anchor would age past the 14d drop
    # deadline and the never-remind-past-drop guard would kick in).
    clock = MutClock(start=wd.utcnow() - timedelta(days=8))
    svc = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                             clock=clock)
    svc.submit_form({"owner_email": "cli@example.com"}, "127.0.0.1")
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY.hex())
    monkeypatch.setenv("WAITLIST_DATA", tmp)
    monkeypatch.setattr(sys, "argv",
                        ["waitlist_jobs.py", "--remind", "--dry-run"])
    assert wj.main(["--remind", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "dry-run" in out and "1 reminder(s)" in out
    # Nothing written: no reminder email, no reminder_sent_at.
    assert len(spool_docs(tmp)) == 1
    entry_id = [r for r in svc.rows.values()][0]["entry_id"]
    svc.reload()
    assert svc.rows[entry_id]["reminder_sent_at"] is None


def test_jobs_cli_requires_exactly_one_job(monkeypatch):
    tmp = tempfile.mkdtemp(prefix="waitlist-cli-test-")
    monkeypatch.setenv("WAITLIST_HMAC_KEY", KEY.hex())
    monkeypatch.setenv("WAITLIST_DATA", tmp)
    with pytest.raises(SystemExit) as exc:
        wj.main([])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        wj.main(["--remind", "--drop"])
    assert exc.value.code == 2


def test_jobs_cli_fails_loud_without_key(monkeypatch):
    tmp = tempfile.mkdtemp(prefix="waitlist-cli-test-")
    monkeypatch.delenv("WAITLIST_HMAC_KEY", raising=False)
    monkeypatch.setenv("WAITLIST_DATA", tmp)
    with pytest.raises(SystemExit) as exc:
        wj.main(["--remind"])
    assert exc.value.code == 2
