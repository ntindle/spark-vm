"""Tests for scripts/funnel_metrics.py.

Run from the repo root:  python3 -m pytest scripts/test_funnel_metrics.py -q

The fixture is a small synthetic funnel_events JSONL covering every event
the script reads, including the edge cases the cohort-windowing design
must handle: a confirmation that lands after the window still counts
(r2), a submission outside the window never enters a cohort (r5), a
claimed-before-invite row is data rot for the duration median (r10), and
unconfirmed spray rows depress only the raw confirm-rate split (r3).
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(SCRIPTS, "funnel_metrics.py")

ROWS = [
    # Rollups: in-window buckets count; out-of-window buckets don't.
    {"event": "page_view_day", "at": "2026-09-14T00:00:00Z", "ref": "2026-09-14",
     "attrs": {"count": 100}},
    {"event": "page_view_day", "at": "2026-09-15T00:00:00Z", "ref": "2026-09-15",
     "attrs": {"count": 120}},
    {"event": "page_view_day", "at": "2026-09-16T00:00:00Z", "ref": "2026-09-16",
     "attrs": {"count": 500}},
    {"event": "crawler_hits", "at": "2026-09-14T00:00:00Z", "ref": "2026-09-14",
     "attrs": {"count": 30}},
    {"event": "cta_click", "at": "2026-09-14T00:00:00Z", "ref": "2026-09-14",
     "attrs": {"src": "hero", "count": 20}},
    {"event": "cta_click", "at": "2026-09-15T00:00:00Z", "ref": "2026-09-15",
     "attrs": {"src": "faq", "count": 7}},
    {"event": "cta_click", "at": "2026-09-15T00:00:00Z", "ref": "2026-09-15",
     "attrs": {}},
    {"event": "cta_click", "at": "2026-09-12T00:00:00Z", "ref": "2026-09-12",
     "attrs": {"src": "hero", "count": 99}},
    # r1: aligned, confirms in window (2h latency).
    {"event": "waitlist_submitted", "at": "2026-09-14T10:00:00Z", "ref": "r1",
     "attrs": {"path": "email", "inbound_auth": True}},
    {"event": "confirm_sent", "at": "2026-09-14T10:05:00Z", "ref": "r1",
     "attrs": {}},
    {"event": "confirmed", "at": "2026-09-14T12:00:00Z", "ref": "r1",
     "attrs": {"via": "original"}},
    # r2: aligned, confirms AFTER the window — still counts (cohort).
    {"event": "waitlist_submitted", "at": "2026-09-14T11:00:00Z", "ref": "r2",
     "attrs": {"path": "email", "inbound_auth": True}},
    {"event": "confirm_sent", "at": "2026-09-14T11:05:00Z", "ref": "r2",
     "attrs": {}},
    {"event": "reminder_sent", "at": "2026-09-21T11:00:00Z", "ref": "r2",
     "attrs": {}},
    {"event": "confirmed", "at": "2026-09-22T09:00:00Z", "ref": "r2",
     "attrs": {"via": "reminder"}},
    # r3: unauthenticated spray row — depresses raw, excluded from aligned.
    {"event": "waitlist_submitted", "at": "2026-09-15T09:00:00Z", "ref": "r3",
     "attrs": {"path": "email", "inbound_auth": False}},
    {"event": "confirm_sent", "at": "2026-09-15T09:05:00Z", "ref": "r3",
     "attrs": {}},
    # r4: path-B form row, no inbound_auth — raw only, confirms (1.5h).
    {"event": "waitlist_submitted", "at": "2026-09-15T10:00:00Z", "ref": "r4",
     "attrs": {"path": "form"}},
    {"event": "confirm_sent", "at": "2026-09-15T10:05:00Z", "ref": "r4",
     "attrs": {}},
    {"event": "confirmed", "at": "2026-09-15T11:30:00Z", "ref": "r4",
     "attrs": {"via": "original"}},
    # r5: submitted outside the window — never enters the cohort.
    {"event": "waitlist_submitted", "at": "2026-09-10T10:00:00Z", "ref": "r5",
     "attrs": {"path": "email", "inbound_auth": True}},
    {"event": "confirmed", "at": "2026-09-14T08:00:00Z", "ref": "r5",
     "attrs": {"via": "original"}},
    # Invite/claim cohort.
    {"event": "invite_sent", "at": "2026-09-13T10:00:00Z", "ref": "r6",
     "attrs": {}},
    {"event": "claimed", "at": "2026-09-14T10:00:00Z", "ref": "r6",
     "attrs": {}},
    {"event": "invite_sent", "at": "2026-09-13T12:00:00Z", "ref": "r7",
     "attrs": {}},
    {"event": "claimed", "at": "2026-09-13T18:00:00Z", "ref": "r7",
     "attrs": {}},
    {"event": "invite_sent", "at": "2026-09-14T10:00:00Z", "ref": "r8",
     "attrs": {}},
    {"event": "invite_sent", "at": "2026-09-16T10:00:00Z", "ref": "r9",
     "attrs": {}},
    {"event": "invite_sent", "at": "2026-09-13T10:00:00Z", "ref": "r10",
     "attrs": {}},
    {"event": "claimed", "at": "2026-09-13T09:00:00Z", "ref": "r10",
     "attrs": {}},
]

WINDOW = ["--since", "2026-09-13", "--until", "2026-09-15"]


def write_events(tmp_path, rows=ROWS):
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return str(path)


def run(events_path, *extra):
    return subprocess.run(
        [sys.executable, SCRIPT, "--events", events_path, *extra],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_full_pack(tmp_path):
    proc = run(write_events(tmp_path), *WINDOW)
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout

    # Primary: confirmed-from-window (r1, r2, r4) / visitors (100+120).
    assert "3/220 = 1.4%" in out
    # Out-of-window rollups excluded (no 500-visitor day, no 99 hero clicks).
    assert "720" not in out and "119" not in out

    # Secondary: CTA by src + uncategorized.
    assert "  hero: 20" in out
    assert "  faq: 7" in out
    assert "missing src: 1" in out

    # Interim confirm rate: raw 3/4 (spray row depresses), aligned 2/2.
    assert "raw: 3/4 = 75.0%" in out
    assert "DMARC-aligned senders only: 2/2 = 100.0%" in out
    # Spray signature: aligned minus raw, reported — never averaged.
    assert "spray-gap (aligned minus raw): +25.0pp" in out

    # Reminder lift: r2 confirmed via reminder / 1 reminder_sent.
    assert "confirmed via reminder / reminder_sent: 1/1 = 100.0%" in out

    # Invite -> claim: 3/4 (r10's claim counts; its negative duration
    # doesn't poison the median), median of [24h, 6h] = 15.0h.
    assert "claimed / invite_sent: 3/4 = 75.0%; median invite->claim: 15.0h" in out

    # Submit -> confirm latency: median of [2.0, 190.0, 1.5] = 2.0h.
    assert "median waitlist_submitted->confirmed: 2.0h" in out

    # Bridge visible but not instrumented; crawlers excluded from primary.
    assert "not instrumented yet" in out
    assert "crawler_hits in window: 30" in out

    # Interim labeling stays on the confirm rate (doc section 8).
    assert "INTERIM CONFIRM RATE" in out


def test_empty_store_is_all_na(tmp_path):
    proc = run(write_events(tmp_path, rows=[]), *WINDOW)
    assert proc.returncode == 0, proc.stderr
    assert "n/a (denominator 0)" in proc.stdout
    assert "n/a (no rows)" in proc.stdout


def test_unknown_event_rejected(tmp_path):
    rows = ROWS + [
        {"event": "page_view", "at": "2026-09-14T00:00:00Z",
         "ref": "2026-09-14", "attrs": {}}
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 2
    assert "unknown event 'page_view'" in proc.stderr


def test_bad_timestamp_rejected(tmp_path):
    rows = [
        {"event": "page_view_day", "at": "not-a-date", "ref": "2026-09-14",
         "attrs": {"count": 1}}
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 2
    assert "unparseable timestamp" in proc.stderr


def test_negative_count_rejected(tmp_path):
    rows = [
        {"event": "page_view_day", "at": "2026-09-14T00:00:00Z",
         "ref": "2026-09-14", "attrs": {"count": -1}}
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 2
    assert "non-negative int" in proc.stderr


def test_missing_events_file(tmp_path):
    proc = run(str(tmp_path / "nope.jsonl"), *WINDOW)
    assert proc.returncode == 2


def test_bad_window_args(tmp_path):
    proc = run(write_events(tmp_path), "--since", "2026-09-15", "--until",
               "2026-09-13")
    assert proc.returncode == 2
    assert "--since is after --until" in proc.stderr


def test_bridge_line_when_instrumented(tmp_path):
    rows = ROWS + [
        {"event": "signup_started", "at": "2026-09-14T13:00:00Z", "ref": "r1",
         "attrs": {}},
        {"event": "identity_linked", "at": "2026-09-14T14:00:00Z", "ref": "r1",
         "attrs": {}},
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 0, proc.stderr
    # 1 linked / 3 confirmed-from-window, never folded into the primary.
    assert "identity-linked / confirmed waitlist entries: 1/3 = 33.3%" in proc.stdout
    assert "not instrumented yet" not in proc.stdout


def test_rollup_windows_on_day_bucket_not_emission(tmp_path):
    # The nightly rollup job routinely emits after midnight: a rollup for
    # bucket 2026-09-13 emitted at 2026-09-14T00:05 must count for 2026-09-13.
    rows = [
        {"event": "page_view_day", "at": "2026-09-14T00:05:00Z",
         "ref": "2026-09-13", "attrs": {"count": 40}},
        {"event": "page_view_day", "at": "2026-09-14T00:05:00Z",
         "ref": "2026-09-14", "attrs": {"count": 10}},
    ]
    proc = run(write_events(tmp_path, rows), "--since", "2026-09-13",
               "--until", "2026-09-13")
    assert proc.returncode == 0, proc.stderr
    assert "confirmed (submitted in window) / unique visitors: 0/40 = 0.0%" \
        in proc.stdout


def test_bad_day_bucket_rejected(tmp_path):
    rows = [
        {"event": "page_view_day", "at": "2026-09-14T00:00:00Z", "ref": "r1",
         "attrs": {"count": 1}}
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 2
    assert "bad day-bucket ref 'r1'" in proc.stderr


def test_reminder_sent_alone_is_not_a_reminder_conversion(tmp_path):
    # §7's numerator is "confirmed with via=reminder" — a reminder merely
    # sent does not credit the reminder program with the original link's
    # conversion.
    rows = [
        {"event": "waitlist_submitted", "at": "2026-09-14T10:00:00Z",
         "ref": "r1", "attrs": {"path": "email", "inbound_auth": True}},
        {"event": "confirm_sent", "at": "2026-09-14T10:05:00Z", "ref": "r1",
         "attrs": {}},
        {"event": "reminder_sent", "at": "2026-09-21T11:00:00Z", "ref": "r1",
         "attrs": {}},
        {"event": "confirmed", "at": "2026-09-22T09:00:00Z", "ref": "r1",
         "attrs": {"via": "original"}},
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 0, proc.stderr
    assert "confirmed via reminder / reminder_sent: 0/1 = 0.0%" in proc.stdout


def test_unknown_src_warns_on_stderr(tmp_path):
    rows = [
        {"event": "cta_click", "at": "2026-09-14T00:00:00Z", "ref": "2026-09-14",
         "attrs": {"src": "heros", "count": 3}},
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 0, proc.stderr
    assert "unknown cta_click src 'heros'" in proc.stderr
    # ... but the bucket still counts (warn, don't drop).
    assert "  heros: 3" in proc.stdout


def test_negative_duration_disclosure(tmp_path):
    proc = run(write_events(tmp_path), *WINDOW)
    assert proc.returncode == 0, proc.stderr
    # r10's claimed-before-invite row is excluded from the medians and
    # disclosed in the report, not silently dropped.
    assert "medians exclude 1 negative-duration row(s)" in proc.stdout


def test_non_dict_attrs_rejected_with_line(tmp_path):
    rows = [
        {"event": "confirmed", "at": "2026-09-14T10:00:00Z", "ref": "r1",
         "attrs": "nope"},
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 2
    assert ":1: attrs must be an object" in proc.stderr


@pytest.mark.parametrize("count", ["x", -5, True, 1.5])
def test_cta_click_bad_count_rejected(tmp_path, count):
    rows = [
        {"event": "cta_click", "at": "2026-09-14T00:00:00Z", "ref": "2026-09-14",
         "attrs": {"src": "hero", "count": count}},
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 2
    assert "attrs.count must be a non-negative int" in proc.stderr


def test_rollup_bool_count_rejected(tmp_path):
    # JSON true would silently count as 1 without the bool guard.
    rows = [
        {"event": "page_view_day", "at": "2026-09-14T00:00:00Z",
         "ref": "2026-09-14", "attrs": {"count": True}},
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 2
    assert "attrs.count must be a non-negative int" in proc.stderr


def test_timezone_offset_windows_on_utc_date(tmp_path):
    # 2026-09-14T00:30:00+02:00 == 2026-09-13T22:30Z: the UTC date is Sept 13,
    # so the row belongs to the Sept-13 cohort, not Sept 14.
    rows = [
        {"event": "page_view_day", "at": "2026-09-14T00:05:00Z",
         "ref": "2026-09-13", "attrs": {"count": 50}},
        {"event": "waitlist_submitted", "at": "2026-09-14T00:30:00+02:00",
         "ref": "r1", "attrs": {"path": "email", "inbound_auth": True}},
        {"event": "confirmed", "at": "2026-09-14T10:00:00Z", "ref": "r1",
         "attrs": {"via": "original"}},
    ]
    proc = run(write_events(tmp_path, rows), "--since", "2026-09-14",
               "--until", "2026-09-14")
    assert proc.returncode == 0, proc.stderr
    assert ("confirmed (submitted in window) / unique visitors: "
            "n/a (denominator 0)") in proc.stdout
    proc = run(write_events(tmp_path, rows), "--since", "2026-09-13",
               "--until", "2026-09-13")
    assert proc.returncode == 0, proc.stderr
    assert ("confirmed (submitted in window) / unique visitors: "
            "1/50 = 2.0%") in proc.stdout


def test_default_window_is_seven_inclusive_utc_days(tmp_path):
    proc = run(write_events(tmp_path, rows=[]))
    assert proc.returncode == 0, proc.stderr
    today = datetime.now(timezone.utc).date()
    expected = (f"window {(today - timedelta(days=6)).isoformat()}"
                f"..{today.isoformat()}")
    assert expected in proc.stdout


def test_orphan_confirmation_diagnostic(tmp_path):
    rows = [
        {"event": "confirmed", "at": "2026-09-14T10:00:00Z", "ref": "ghost",
         "attrs": {"via": "original"}},
    ]
    proc = run(write_events(tmp_path, rows), *WINDOW)
    assert proc.returncode == 0, proc.stderr
    # Dropped from every numerator (no submission anchor) but visible in
    # the hygiene line, not silently swallowed.
    assert ("1 confirmation(s) dropped with no matching "
            "waitlist_submitted row") in proc.stdout
