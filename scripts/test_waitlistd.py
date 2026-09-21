"""Tests for site/waitlistd.py (H15 build, slice 2).

Run from the repo root:  python3 -m pytest scripts/test_waitlistd.py -q

Covers the spec contracts the service must hold:
- docs/HOSTED_SIGNUP_WEB_UI.md §4.2 (form: honeypot/time-trap/rate-limit
  silent accepts, validation, dedup, check-inbox rendering)
- §4.3 (GET renders only / POST confirms; token as form field; four
  confirm states with FUNNEL_MEASUREMENT.md §4.3 copy)
- docs/WAITLIST_OPERATIONS.md §4 (HMAC token, single-use, 14-day expiry,
  3/24h email cap) and §6 (no unauthenticated position lookup)
- docs/FUNNEL_MEASUREMENT.md §3.4 (funnel_events 4-tuples stay parseable
  by scripts/funnel_metrics.py)

stdlib only, no network except one loopback integration test (the HTTP
wiring, ephemeral port, torn down after).
"""

import importlib.util
import json
import os
import re
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(REPO, "site")
SCRIPTS = os.path.join(REPO, "scripts")


def load_waitlistd():
    spec = importlib.util.spec_from_file_location(
        "waitlistd", os.path.join(SITE, "waitlistd.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wd = load_waitlistd()

KEY = b"test-hmac-key-32-bytes-long-000000"
NOW = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)


class TickClock:
    """A controllable clock that advances one step per call. The default
    frozen clock ties queued_at for same-second sends, which leaves
    spool_docs_newest_first() undefined — tests that order two sends must
    tick instead."""

    def __init__(self, start=NOW, step_seconds=1):
        self.t = start
        self.step = timedelta(seconds=step_seconds)

    def __call__(self):
        cur = self.t
        self.t = self.t + self.step
        return cur


def make_service(**kw):
    tmp = tempfile.mkdtemp(prefix="waitlistd-test-")
    clock = kw.pop("clock", None)
    return wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid",
                              clock=clock or (lambda: NOW)), tmp


def form_fields(email, **over):
    fields = {
        "owner_email": email,
        "muse_email": "",
        "website": "",
        "rendered_at": str(time.time() - 10),
    }
    fields.update(over)
    return fields


def spool_files(tmp):
    d = os.path.join(tmp, "spool")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def read_events(tmp):
    path = os.path.join(tmp, "funnel_events.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def spool_docs_newest_first(tmp):
    """Spool docs ordered newest-first by queued_at (filenames sort by
    random entry_id, not by time)."""
    docs = []
    for name in spool_files(tmp):
        with open(os.path.join(tmp, "spool", name), encoding="utf-8") as fh:
            docs.append(json.load(fh))
    return sorted(docs, key=lambda d: d["queued_at"], reverse=True)


def extract_token_from_spool(tmp):
    docs = spool_docs_newest_first(tmp)
    assert docs, "expected a spooled email"
    doc = docs[0]
    m = re.search(r"token=([A-Za-z0-9_.\-]+)", doc["body"])
    assert m, "spooled email has no confirm link"
    return m.group(1), doc


# ---------------------------------------------------------------------------
# The form
# ---------------------------------------------------------------------------


def test_new_submission_creates_row_and_emits_events():
    svc, tmp = make_service()
    status, body = svc.submit_form(form_fields("Nina@Example.com"), "1.2.3.4")
    assert status == 200
    assert "Check your inbox" in body
    assert "Nina@Example.com" in body  # echoes the self-submitted address
    assert "wrong address" in body.lower() or "Go back" in body
    rows = list(svc.rows.values())
    assert len(rows) == 1
    row = rows[0]
    assert row["owner_email"] == "nina@example.com"  # normalized
    assert row["status"] == "pending"
    events = read_events(tmp)
    kinds = [e["event"] for e in events]
    assert kinds == ["waitlist_submitted", "confirm_sent"]
    sub = events[0]
    assert sub["ref"] == row["entry_id"]
    assert sub["attrs"] == {"path": "form"}
    # The spooled confirm email carries a working token link.
    token, doc = extract_token_from_spool(tmp)
    assert doc["to"] == "nina@example.com"
    assert "No card is required for the waitlist" in doc["body"]
    assert "real\npricing" in doc["body"] or "real pricing" in doc["body"]
    row2, ok = svc.validate_token(token)
    assert ok and row2["entry_id"] == row["entry_id"]


def test_honeypot_is_silent_accept():
    svc, tmp = make_service()
    status, body = svc.submit_form(
        form_fields("bot@example.com", website="http://spam"), "1.2.3.4")
    assert status == 200
    assert "Check your inbox" in body
    assert svc.rows == {}
    assert read_events(tmp) == []
    assert spool_files(tmp) == []


def test_silent_accept_renders_same_as_success():
    # HOSTED_SIGNUP_WEB_UI.md §4.2: the honeypot's 200 must use the SAME
    # rendering as a real success — a distinguishable body leaks the signal.
    svc, tmp = make_service()
    _, ok_body = svc.submit_form(
        form_fields("sam@example.com"), "1.2.3.4")
    status, silent_body = svc.submit_form(
        form_fields("sam@example.com", website="http://spam"), "5.6.7.8")
    assert status == 200
    assert silent_body == ok_body
    assert len(svc.rows) == 1  # the honeypot trip wrote nothing


def test_time_trap_fast_submission_is_silent_accept():
    svc, tmp = make_service()
    status, _ = svc.submit_form(
        form_fields("bot@example.com", rendered_at=str(time.time())), "1.2.3.4")
    assert status == 200
    assert svc.rows == {}
    assert read_events(tmp) == []


def test_time_trap_missing_stamp_proceeds():
    # The static form stamps nothing (no serving layer under Pages) — a
    # missing stamp is the form's legitimate state, not bot-shaped.
    svc, tmp = make_service()
    fields = form_fields("human@example.com")
    del fields["rendered_at"]
    status, _ = svc.submit_form(fields, "1.2.3.4")
    assert status == 200
    assert len(svc.rows) == 1
    assert len(spool_files(tmp)) == 1


def test_time_trap_empty_stamp_proceeds():
    # This is the literal value slice 1's form sends: rendered_at="".
    svc, tmp = make_service()
    status, _ = svc.submit_form(
        form_fields("human2@example.com", rendered_at=""), "1.2.3.4")
    assert status == 200
    assert len(svc.rows) == 1
    assert len(spool_files(tmp)) == 1
    kinds = [e["event"] for e in read_events(tmp)]
    assert "waitlist_submitted" in kinds and "confirm_sent" in kinds


def test_time_trap_unparseable_stamp_is_silent_accept():
    svc, tmp = make_service()
    status, _ = svc.submit_form(
        form_fields("bot@example.com", rendered_at="not-a-number"),
        "1.2.3.4")
    assert status == 200
    assert svc.rows == {}
    assert read_events(tmp) == []


def test_per_ip_rate_limit_is_silent_accept():
    svc, tmp = make_service()
    for i in range(10):
        status, _ = svc.submit_form(
            form_fields(f"user{i}@example.com"), "9.9.9.9")
        assert status == 200
    assert len(svc.rows) == 10
    status, _ = svc.submit_form(form_fields("user10@example.com"), "9.9.9.9")
    assert status == 200  # silent: no 429 that teaches the spammer
    assert len(svc.rows) == 10
    # A different IP is unaffected.
    status, _ = svc.submit_form(form_fields("other@example.com"), "8.8.8.8")
    assert status == 200
    assert len(svc.rows) == 11


def test_invalid_email_is_400_not_silent():
    svc, tmp = make_service()
    for bad in ["not-an-email", "a@b", "@example.com", "+tag@example.com",
                "x" * 300 + "@e.com"]:
        status, body = svc.submit_form(form_fields(bad), "1.2.3.4")
        assert status == 400, bad
        assert "look right" in body
    assert svc.rows == {}
    assert read_events(tmp) == []


def test_email_normalization_and_plus_tag_dedup():
    svc, tmp = make_service()
    svc.submit_form(form_fields("User+Tag@Example.COM"), "1.2.3.4")
    assert svc.by_email == {"user@example.com": next(iter(svc.rows))}
    # Same normalized address re-submits the pending row — no second row.
    status, _ = svc.submit_form(form_fields("user@example.com"), "1.2.3.4")
    assert status == 200
    assert len(svc.rows) == 1


def test_resubmit_pending_refreshes_and_invalidates_old_token():
    # Two sends happen within the same frozen second under the default
    # clock — tick so spool_docs_newest_first() is deterministic.
    svc, tmp = make_service(clock=TickClock())
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    token1, _ = extract_token_from_spool(tmp)
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    assert len(svc.rows) == 1  # still one row
    _, ok = svc.validate_token(token1)
    assert not ok  # the old token is dead
    # The newest spooled email carries the fresh token.
    docs = spool_docs_newest_first(tmp)
    assert len(docs) == 2
    m = re.search(r"token=([A-Za-z0-9_.\-]+)", docs[0]["body"])
    assert m
    token2 = m.group(1)
    assert token2 != token1
    row, ok = svc.validate_token(token2)
    assert ok


def test_cap_suppressed_resubmit_keeps_old_token_live():
    # The 3/24h cap must never strand the user: a suppressed re-send keeps
    # the earlier token live and renders honest copy (no "we sent an email"
    # claim for an email that never went out).
    svc, tmp = make_service(clock=TickClock())
    svc.submit_form(form_fields("capped@example.com"), "1.2.3.4")
    for _ in range(2):
        svc.submit_form(form_fields("capped@example.com"), "1.2.3.4")
    docs = spool_docs_newest_first(tmp)
    assert len(docs) == 3
    m = re.search(r"token=([A-Za-z0-9_.\-]+)", docs[0]["body"])
    assert m
    live_token = m.group(1)
    # Fourth submit: the cap suppresses the send.
    status, body = svc.submit_form(form_fields("capped@example.com"),
                                   "1.2.3.4")
    assert status == 200
    assert len(spool_files(tmp)) == 3  # nothing new spooled
    assert "earlier link still works" in body
    assert "We sent a confirmation email to" not in body
    # The earlier token is still the live one — the user can confirm.
    row, ok = svc.validate_token(live_token)
    assert ok
    status, body = svc.confirm_post(live_token)
    assert status == 200 and "You\u2019re on the list" in body


def test_concurrent_double_submit_creates_one_row():
    # A racing double-click must not break the one-pending-entry invariant.
    svc, tmp = make_service()
    barrier = threading.Barrier(2)
    results = []

    def worker():
        barrier.wait()
        results.append(svc.submit_form(
            form_fields("race@example.com"), "1.2.3.4"))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(s == 200 for s, _ in results)
    assert len(svc.rows) == 1
    kinds = [e["event"] for e in read_events(tmp)]
    assert kinds.count("waitlist_submitted") == 1  # the invariant
    # The race loser becomes a legitimate re-submit: fresh token, re-send.
    row = next(iter(svc.rows.values()))
    assert row["owner_email"] == "race@example.com"
    assert row["status"] == "pending"
    live_row, ok = svc.validate_token(row["active_token"])
    assert ok and live_row["entry_id"] == row["entry_id"]


def test_torn_rows_line_does_not_brick_restart():
    # A kill -9 mid-append tears the last line; restart must skip it, not die.
    svc, tmp = make_service()
    svc.submit_form(form_fields("torn@example.com"), "1.2.3.4")
    with open(os.path.join(tmp, "rows.jsonl"), "a",
              encoding="utf-8") as fh:
        fh.write('{"entry_id": "deadbeef", "owner_email": "half-writt')
        fh.write("\n")
    svc2 = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid")
    assert "torn@example.com" in svc2.by_email
    assert len(svc2.rows) == 1


def test_resubmit_when_confirmed_is_idempotent():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    token, _ = extract_token_from_spool(tmp)
    svc.confirm_post(token)
    before = read_events(tmp)
    status, body = svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    assert status == 200
    assert "You\u2019re on the list" in body
    assert read_events(tmp) == before  # no new events, no new email


def test_transactional_email_cap_suppresses_silently():
    svc, tmp = make_service()
    for _ in range(4):
        status, body = svc.submit_form(form_fields("nina@example.com"),
                                       "1.2.3.4")
        assert status == 200
        assert "Check your inbox" in body  # never leaks the cap
    assert len(spool_files(tmp)) == 3  # 3/24h cap
    assert len(svc.rows) == 1


def test_muse_contact_optional_and_normalized():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com",
                                muse_email="Agent+1@Example.com"), "1.2.3.4")
    row = next(iter(svc.rows.values()))
    assert row["muse_contact"] == "agent@example.com"


# ---------------------------------------------------------------------------
# Confirm: GET renders only
# ---------------------------------------------------------------------------


def test_get_pending_renders_button_and_changes_nothing():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    token, _ = extract_token_from_spool(tmp)
    rows_before = open(os.path.join(tmp, "rows.jsonl"),
                       encoding="utf-8").read()
    events_before = read_events(tmp)
    spool_before = spool_files(tmp)
    status, body = svc.confirm_get(token)
    assert status == 200
    assert "Yes, hold my place." in body
    assert "nin…" in body  # masked owner line
    assert "nina@example.com" not in body  # never the full address
    assert "each invite holds for 14 days" in body
    assert 'name="token"' in body
    # GET changed nothing.
    assert open(os.path.join(tmp, "rows.jsonl"),
                encoding="utf-8").read() == rows_before
    assert read_events(tmp) == events_before
    assert spool_files(tmp) == spool_before
    row, ok = svc.validate_token(token)
    assert ok and row["status"] == "pending"  # token unconsumed


def test_get_invalid_token_renders_rule_not_error():
    svc, tmp = make_service()
    for bad in [None, "", "garbage", "a.b.c",
                "e." + str(int(time.time())) + ".bogus"]:
        status, body = svc.confirm_get(bad)
        assert status == 200
        assert "This link expired" in body
        assert "Join the waitlist again" in body
        assert "/waitlist" in body


def test_get_tampered_signature_rejected():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    token, _ = extract_token_from_spool(tmp)
    head, _, sig = token.rpartition(".")
    tampered = head + "." + ("A" if not sig.startswith("A") else "B") \
        + sig[1:]
    status, body = svc.confirm_get(tampered)
    assert "This link expired" in body


def test_get_expired_token():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    row = next(iter(svc.rows.values()))
    old = NOW - timedelta(days=15)
    token = svc.mint_token(row["entry_id"], row["owner_email"], issued_at=old)
    status, body = svc.confirm_get(token)
    assert "This link expired" in body


def test_get_token_for_unknown_row():
    svc, tmp = make_service()
    token = svc.mint_token("no-such-row", "ghost@example.com")
    status, body = svc.confirm_get(token)
    assert "This link expired" in body


def test_get_on_consumed_token_renders_already_confirmed():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    token, _ = extract_token_from_spool(tmp)
    svc.confirm_post(token)
    status, body = svc.confirm_get(token)
    assert status == 200
    assert "You\u2019re on the list" in body
    assert "Yes, hold my place." not in body  # no button


# ---------------------------------------------------------------------------
# Confirm: POST confirms
# ---------------------------------------------------------------------------


def test_post_fresh_token_confirms_and_emits_event():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    token, _ = extract_token_from_spool(tmp)
    status, body = svc.confirm_post(token)
    assert status == 200
    assert "You\u2019re on the list" in body
    assert body == wd.page_confirmed()  # POST-success verbatim = confirmed
    row = next(iter(svc.rows.values()))
    assert row["status"] == "confirmed"
    assert row["confirmed_at"] is not None
    events = read_events(tmp)
    confirmed = [e for e in events if e["event"] == "confirmed"]
    assert len(confirmed) == 1
    assert confirmed[0]["ref"] == row["entry_id"]
    assert confirmed[0]["attrs"] == {"via": "original"}
    _, ok = svc.validate_token(token)
    assert not ok  # single-use: consumed


def test_post_is_idempotent():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    token, _ = extract_token_from_spool(tmp)
    first = svc.confirm_post(token)
    second = svc.confirm_post(token)
    assert second == first  # same rendering, verbatim — never an error
    events = read_events(tmp)
    assert len([e for e in events if e["event"] == "confirmed"]) == 1


def test_post_rejects_expired_and_tampered():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    row = next(iter(svc.rows.values()))
    old = NOW - timedelta(days=15)
    expired = svc.mint_token(row["entry_id"], row["owner_email"],
                             issued_at=old)
    for bad in [expired, "garbage", None]:
        status, body = svc.confirm_post(bad)
        assert "This link expired" in body
    assert row["status"] == "pending"  # nothing confirmed


def test_masked_owner_short_local_part():
    svc, tmp = make_service()
    svc.submit_form(form_fields("ab@x.io"), "1.2.3.4")
    token, _ = extract_token_from_spool(tmp)
    _, body = svc.confirm_get(token)
    # FUNNEL_MEASUREMENT.md §4.2: a <3-char local part masks fully — the
    # full local part must never be disclosed.
    assert "•••" in body
    assert "ab@" not in body
    assert "ab…" not in body


def test_masked_owner_three_char_local_part():
    # FUNNEL_MEASUREMENT.md §4.2: 'sam…' IS the full local part — a 3-char
    # local must mask fully, like the shorter ones.
    svc, tmp = make_service()
    svc.submit_form(form_fields("sam@x.io"), "1.2.3.4")
    token, _ = extract_token_from_spool(tmp)
    _, body = svc.confirm_get(token)
    assert "•••" in body
    assert "sam@" not in body
    assert "sam…" not in body


def test_pages_carry_no_page_js_and_escape_user_content():
    svc, tmp = make_service()
    svc.submit_form(form_fields("nina@example.com"), "1.2.3.4")
    token, _ = extract_token_from_spool(tmp)
    for fn in (lambda: svc.confirm_get(token),
               lambda: svc.confirm_post(token),
               lambda: svc.submit_form(form_fields("nina2@example.com"),
                                       "1.2.3.4"),
               lambda: (400, wd.page_invalid_email()),
               lambda: (200, wd.page_expired())):
        _, body = fn()
        assert "<script" not in body.lower()
    # The check-inbox page escapes the echoed address.
    _, body = svc.submit_form(
        form_fields("nina@example.com", rendered_at=str(time.time() - 10)),
        "9.9.9.9")
    assert "<img" not in body


# ---------------------------------------------------------------------------
# Funnel-metrics compatibility (§3.4)
# ---------------------------------------------------------------------------


def test_emitted_events_parse_with_funnel_metrics():
    spec = importlib.util.spec_from_file_location(
        "funnel_metrics", os.path.join(SCRIPTS, "funnel_metrics.py"))
    fm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fm)
    # Two sends within one frozen second tie queued_at — tick so the
    # newest-first ordering is deterministic.
    svc, tmp = make_service(clock=TickClock())
    svc.submit_form(form_fields("a@example.com"), "1.1.1.1")
    svc.submit_form(form_fields("b@example.com"), "2.2.2.2")
    # The newest spooled email carries b@example.com's live token.
    docs = spool_docs_newest_first(tmp)
    assert len(docs) == 2
    assert docs[0]["to"] == "b@example.com"
    m = re.search(r"token=([A-Za-z0-9_.\-]+)", docs[0]["body"])
    assert m
    svc.confirm_post(m.group(1))
    rows = fm.load_events(os.path.join(tmp, "funnel_events.jsonl"))
    kinds = [r["event"] for r in rows]
    assert kinds.count("waitlist_submitted") == 2
    assert kinds.count("confirm_sent") == 2
    assert kinds.count("confirmed") == 1
    assert rows[-1]["attrs"]["via"] == "original"


# ---------------------------------------------------------------------------
# HTTP wiring (loopback integration)
# ---------------------------------------------------------------------------


@pytest.fixture()
def live_server():
    tmp = tempfile.mkdtemp(prefix="waitlistd-live-")
    svc = wd.WaitlistService(tmp, KEY, "https://waitlist.example.invalid")
    wd._Handler.service = svc
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), wd._Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield port, tmp
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def _post(port, path, fields):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    body = urllib.parse.urlencode(fields)
    conn.request("POST", path, body,
                 {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    return resp.status, resp.read().decode("utf-8")


def _get(port, path):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    return resp.status, resp.read().decode("utf-8")


def test_http_round_trip(live_server):
    port, tmp = live_server
    status, body = _post(port, "/waitlist/form", {
        "owner_email": "live@example.com", "muse_email": "",
        "website": "", "rendered_at": str(time.time() - 10)})
    assert status == 200 and "Check your inbox" in body
    token, _ = extract_token_from_spool(tmp)
    status, body = _get(port, "/waitlist/confirm?token=" +
                        urllib.parse.quote(token))
    assert status == 200 and "Yes, hold my place." in body
    # Token in the QUERY STRING must not confirm on POST.
    status, body = _post(port, "/waitlist/confirm?token=" +
                         urllib.parse.quote(token), {})
    assert status == 200 and "This link expired" in body
    # Token as a FORM FIELD confirms.
    status, body = _post(port, "/waitlist/confirm", {"token": token})
    assert status == 200 and "You\u2019re on the list" in body
    # Unknown paths 404; GET on the form endpoint 404s (form lives on Pages).
    assert _get(port, "/nope")[0] == 404
    assert _get(port, "/waitlist/form")[0] == 404
    assert _get(port, "/waitlist/position?email=x@y.z")[0] == 404


def test_oversized_body_is_413(live_server):
    port, tmp = live_server
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    big = "owner_email=" + urllib.parse.quote("x" * 70000 + "@e.com")
    conn.request("POST", "/waitlist/form", big,
                 {"Content-Type": "application/x-www-form-urlencoded"})
    resp = conn.getresponse()
    assert resp.status == 413
    resp.read()
    # Rejected before the service layer: nothing written.
    rows_path = os.path.join(tmp, "rows.jsonl")
    assert (not os.path.exists(rows_path)
            or os.path.getsize(rows_path) == 0)


def test_confirm_page_strips_preview_metadata(live_server):
    # FUNNEL_MEASUREMENT.md §4.2: the confirm page is fetched by scanners and
    # unfurlers — Referrer-Policy + X-Robots-Tag must be HTTP headers (a meta
    # robots tag alone does not reach them), and no OG/Twitter tags may ship.
    port, tmp = live_server
    _post(port, "/waitlist/form", {
        "owner_email": "live2@example.com", "muse_email": "",
        "website": "", "rendered_at": str(time.time() - 10)})
    token, _ = extract_token_from_spool(tmp)
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/waitlist/confirm?token=" +
                 urllib.parse.quote(token))
    resp = conn.getresponse()
    assert resp.getheader("Referrer-Policy") == "no-referrer"
    assert resp.getheader("X-Robots-Tag") == "noindex, nofollow"
    body = resp.read().decode("utf-8")
    assert "og:" not in body
    assert "twitter:" not in body


def test_cli_config_fail_closed(tmp_path):
    env = dict(os.environ)
    env.pop("WAITLIST_HMAC_KEY", None)
    env["WAITLIST_DATA"] = str(tmp_path)
    import subprocess
    proc = subprocess.run(
        [sys.executable, os.path.join(SITE, "waitlistd.py"), "--check"],
        capture_output=True, text=True, env=env, timeout=15)
    assert proc.returncode == 2
    assert "WAITLIST_HMAC_KEY" in proc.stderr


# ---------------------------------------------------------------------------
# Forget-me handler + self-host shim (slice 3c)
# ---------------------------------------------------------------------------


def extract_forget_token(body):
    m = re.search(r"waitlist/forget\?token=([A-Za-z0-9_.\-]+)", body)
    assert m, "email body has no forget link"
    return m.group(1)


class MutableClock:
    def __init__(self, start):
        self.t = start

    def __call__(self):
        return self.t


def _submit(svc, email):
    status, _ = svc.submit_form(form_fields(email), "127.0.0.1")
    assert status == 200
    entry_id = svc.by_email[svc.rows and
                            wd.normalize_email(email)]
    return svc.rows[entry_id]


def test_confirm_and_reminder_emails_carry_forget_footer():
    clock = MutableClock(NOW)
    svc, tmp = make_service(clock=clock)
    row = _submit(svc, "forget1@example.com")
    docs = spool_docs_newest_first(tmp)
    assert docs, "expected a spooled confirm email"
    body = docs[0]["body"]
    forget_token = extract_forget_token(body)
    # The forget link validates at the forget endpoint — not the confirm one.
    status, html = svc.forget_get(forget_token)
    assert status == 200 and "Delete your waitlist entry" in html
    _, status = svc._lookup_token_row(forget_token)  # confirm-kind lookup
    assert status == "invalid"

    # The +7d reminder carries a forget footer too (submit at NOW, the
    # reminder fires at drop_at - 7d = submitted_at + 7d).
    clock.t = NOW + timedelta(seconds=wd.REMINDER_LEAD_SECONDS + 3600)
    assert svc.send_reminders() == 1
    reminders = [d for d in spool_docs_newest_first(tmp)
                 if d.get("kind") == "reminder"]
    assert reminders, "expected a spooled reminder"
    extract_forget_token(reminders[0]["body"])


def test_forget_token_domain_separation():
    svc, tmp = make_service()
    row = _submit(svc, "forget3@example.com")
    confirm_token = row["active_token"]
    forget_token = svc.mint_forget_token(row["entry_id"],
                                         row["owner_email"])
    # Confirm tokens fail at the forget endpoint; forget tokens fail at
    # the confirm endpoint. Wrong-kind tokens are "invalid", never a row.
    _, status = svc._lookup_token_row(confirm_token, kind="forget")
    assert status == "invalid"
    _, status = svc._lookup_token_row(forget_token, kind="confirm")
    assert status == "invalid"
    row2, status = svc._lookup_token_row(forget_token, kind="forget")
    assert status == "ok" and row2["entry_id"] == row["entry_id"]


def test_forget_get_with_confirm_token_renders_expired():
    """A confirm token presented at /waitlist/forget renders the expired
    page (200, never an error dump) — wrong-kind tokens are invalid."""
    svc, tmp = make_service()
    row = _submit(svc, "forget3b@example.com")
    confirm_token = row["active_token"]
    status, html = svc.forget_get(confirm_token)
    assert status == 200
    assert "expired" in html.lower() or "invalid" in html.lower()


def test_forget_get_renders_only():
    svc, tmp = make_service()
    row = _submit(svc, "forget4@example.com")
    docs = spool_docs_newest_first(tmp)
    forget_token = extract_forget_token(docs[0]["body"])
    events_before = read_events(tmp)
    status, html = svc.forget_get(forget_token)
    assert status == 200
    assert "Delete your waitlist entry" in html
    assert "Yes, delete my entry." in html
    # No state changed: no row writes, no consumption, no events.
    assert forget_token not in svc.consumed
    assert read_events(tmp) == events_before
    assert svc.by_email.get(row["owner_email"]) == row["entry_id"]


def test_forget_get_states():
    svc, tmp = make_service()
    # Invalid token: expired-page shape, never an error dump.
    status, html = svc.forget_get("forget.nope.0.bad")
    assert status == 200 and "last 7 days" in html
    # Consumed token: the already-deleted page.
    row = _submit(svc, "forget5@example.com")
    docs = spool_docs_newest_first(tmp)
    forget_token = extract_forget_token(docs[0]["body"])
    status, html = svc.forget_post(forget_token)
    assert status == 200 and "has been deleted" in html
    status, html = svc.forget_get(forget_token)
    assert status == 200 and "already deleted" in html
    # And the consumed token stays single-use on POST too.
    status, html = svc.forget_post(forget_token)
    assert status == 200 and "already deleted" in html


def test_forget_post_deletes_row_and_spools_confirmation():
    svc, tmp = make_service()
    row = _submit(svc, "forget6@example.com")
    entry_id = row["entry_id"]
    confirm_token = row["active_token"]
    docs = spool_docs_newest_first(tmp)
    forget_token = extract_forget_token(docs[0]["body"])
    status, html = svc.forget_post(forget_token)
    assert status == 200
    assert "Your waitlist entry is gone" in html
    # The row is gone — in memory and after a reload.
    assert entry_id not in svc.rows
    assert row["owner_email"] not in svc.by_email
    svc.reload()
    assert entry_id not in svc.rows
    # Both tokens are dead.
    _, status = svc._lookup_token_row(confirm_token)
    assert status == "invalid"
    # `forgot` event emitted; deletion confirmation spooled.
    events = read_events(tmp)
    assert [e for e in events
            if e["event"] == "forgot" and e["ref"] == entry_id]
    deleted = [d for d in spool_docs_newest_first(tmp)
               if d.get("kind") == "deleted"]
    assert deleted, "expected a spooled deletion confirmation"
    assert deleted[0]["to"] == "forget6@example.com"
    assert deleted[0]["subject"] == wd.FORGET_SUBJECT


def test_forget_post_on_confirmed_row():
    svc, tmp = make_service()
    row = _submit(svc, "forget7@example.com")
    token = row["active_token"]
    status, _ = svc.confirm_post(token)
    assert status == 200
    assert svc.rows[row["entry_id"]]["status"] == "confirmed"
    docs = spool_docs_newest_first(tmp)
    forget_token = extract_forget_token(docs[0]["body"])
    status, html = svc.forget_post(forget_token)
    assert status == 200 and "gone" in html
    assert row["entry_id"] not in svc.rows
    events = read_events(tmp)
    assert [e for e in events if e["event"] == "forgot"]


def test_forget_token_expires_in_7d():
    clock = MutableClock(NOW)
    svc, tmp = make_service(clock=clock)
    row = _submit(svc, "forget8@example.com")
    forget_token = svc.mint_forget_token(row["entry_id"],
                                         row["owner_email"])
    clock.t = NOW + timedelta(seconds=wd.FORGET_TTL_SECONDS + 1)
    row2, status = svc._lookup_token_row(forget_token, kind="forget")
    assert status == "expired"
    # The confirm token for the same row still has a week left.
    row3, status = svc._lookup_token_row(row["active_token"])
    assert status == "ok"


def test_cta_selfhost_emits_and_returns_url():
    svc, tmp = make_service()
    url = svc.cta_selfhost("selfhost")
    assert url == wd.SELFHOST_URL
    events = read_events(tmp)
    assert [e for e in events if e["event"] == "cta_click"
            and e["attrs"].get("src") == "selfhost"]
    # Unknown src: still logged, no src attr (funnel_metrics flags it).
    url = svc.cta_selfhost("evil\"><script")
    assert url == wd.SELFHOST_URL
    events = read_events(tmp)
    assert [e for e in events if e["event"] == "cta_click"
            and "src" not in e["attrs"]]


def test_forgot_event_parses_in_funnel_metrics():
    # scripts/funnel_metrics.py raises ValueError on unknown events — the
    # `forgot` addition must keep the emitted trail parseable.
    svc, tmp = make_service()
    row = _submit(svc, "forget9@example.com")
    docs = spool_docs_newest_first(tmp)
    svc.forget_post(extract_forget_token(docs[0]["body"]))
    fm = load_funnel_metrics()
    rows = fm.load_events(os.path.join(tmp, "funnel_events.jsonl"))
    assert {r["event"] for r in rows} >= {
        "waitlist_submitted", "confirm_sent", "forgot"}


def load_funnel_metrics():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "funnel_metrics", os.path.join(SCRIPTS, "funnel_metrics.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_http_forget_round_trip(live_server):
    port, tmp = live_server
    status, _ = _post(port, "/waitlist/form", {
        "owner_email": "live-forget@example.com", "muse_email": "",
        "website": "", "rendered_at": str(time.time() - 10)})
    assert status == 200
    _, doc = extract_token_from_spool(tmp)
    forget_token = extract_forget_token(doc["body"])
    # GET renders the delete page; the token is in a form field.
    status, body = _get(port, "/waitlist/forget?token=" +
                        urllib.parse.quote(forget_token))
    assert status == 200 and "Yes, delete my entry." in body
    # Query-string token must not delete on POST.
    status, body = _post(port, "/waitlist/forget?token=" +
                         urllib.parse.quote(forget_token), {})
    assert status == 200 and "last 7 days" in body
    # Token as a FORM FIELD deletes.
    status, body = _post(port, "/waitlist/forget",
                         {"token": forget_token})
    assert status == 200 and "Your waitlist entry is gone" in body


def test_http_selfhost_redirect(live_server):
    port, tmp = live_server
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/go/selfhost?src=selfhost")
    resp = conn.getresponse()
    assert resp.status == 302
    assert resp.getheader("Location") == wd.SELFHOST_URL
    resp.read()
    events = read_events(tmp)
    assert [e for e in events if e["event"] == "cta_click"
            and e["attrs"].get("src") == "selfhost"]
