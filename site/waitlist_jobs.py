#!/usr/bin/env python3
"""waitlist_jobs — the waitlist lifecycle cron jobs (H15 build, slice 3a/3b).

Three cron entry points against the operator-side waitlist store
(WAITLIST_OPERATIONS.md §10):

    waitlist_jobs.py --remind     the +7d reminder job (§4 draft)
    waitlist_jobs.py --drop       the 14d drop job (§4: unconfirmed →
                                  status `dropped`, no third email)
    waitlist_jobs.py --purge      the 30d post-drop purge (§5: dropped →
                                  row deleted; slice 3b)

--purge is the operator pass slice 3a's docstring deferred: it rewrites
rows.jsonl, so it has its own lock discipline (data lock held across
reload + scan + atomic rewrite; os.replace() swap, fsync before the
rename). The funnel events are the audit trail — `purged` is emitted per
row before the rewrite; the PII leaves with the row.

All are idempotent, --remind honors the 3/24h transactional-email cap,
and each takes waitlistd's cross-process data lock around a reload +
scan so they never race the live daemon (or a second cron instance).

Operator cron shape (all three jobs share the service's env):

    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... waitlist_jobs.py --remind
    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... waitlist_jobs.py --drop
    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... waitlist_jobs.py --purge

Config (env — same fail-loud contract as waitlistd):
    WAITLIST_HMAC_KEY    operator HMAC key — REQUIRED, fail loud if unset.
    WAITLIST_DATA        operator-owned data dir — REQUIRED, fail loud if
                         unset or unwritable. Never the repo.
    WAITLIST_PUBLIC_HOST public origin for links in queued email
                         (default https://waitlist.example.invalid).

Reminder semantics (WAITLIST_OPERATIONS.md §4 DRAFT, verbatim copy in
waitlistd.REMINDER_BODY):
- One reminder at +7 days, computed off drop_at (= first submission +
  14d, never refreshed by re-submits), so the reminder fires at
  first-submit +7d.
- Same link as the confirm email; fresh token only when the live token is
  within 7 days of expiry. A cap-suppressed reminder is deferred, never
  skipped silently — the job retries on the next cron run.
- Emits `reminder_sent`; the reminder's confirm lands with via=reminder.

Drop semantics (§4, §5):
- Unconfirmed at drop_at → status `dropped` (terminal), the live token
  consumed, a `dropped` funnel event emitted. No third email — the
  reminder was the last touch.
- The row is retained 30 days after drop per §5, then purged by the
  --purge job (its own atomic-rewrite lock discipline, below).

Purge semantics (§5):
- status `dropped` and now >= dropped_at + 30d → the row is deleted.
  A `purged` funnel event is emitted per row before deletion, so the
  counts survive the PII. A dropped row with no parseable dropped_at is
  never purge-due (can't prove the 30 days elapsed; the operator handles
  hand-edited stores by hand).

stdlib only. Tested by scripts/test_waitlist_jobs.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from waitlistd import (  # noqa: E402
    WaitlistService,
    data_lock,
)


def load_job_config(argv):
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(__doc__ + "\n")
        raise SystemExit(0)
    key_raw = os.environ.get("WAITLIST_HMAC_KEY")
    if not key_raw:
        sys.stderr.write(
            "waitlist_jobs: WAITLIST_HMAC_KEY is not set — refusing to run "
            "without the operator HMAC key.\n"
        )
        raise SystemExit(2)
    try:
        key = bytes.fromhex(key_raw)
    except ValueError:
        key = key_raw.encode("utf-8")
    if len(key) < 16:
        sys.stderr.write(
            "waitlist_jobs: WAITLIST_HMAC_KEY is too short "
            "(need >= 16 bytes).\n"
        )
        raise SystemExit(2)
    data_dir = os.environ.get("WAITLIST_DATA")
    if not data_dir:
        sys.stderr.write(
            "waitlist_jobs: WAITLIST_DATA is not set — refusing to run "
            "without an operator-owned data dir.\n"
        )
        raise SystemExit(2)
    if not os.path.isdir(data_dir) or not os.access(data_dir, os.W_OK):
        sys.stderr.write(
            f"waitlist_jobs: WAITLIST_DATA={data_dir!r} is not a writable "
            "directory.\n"
        )
        raise SystemExit(2)
    host = os.environ.get("WAITLIST_PUBLIC_HOST",
                           "https://waitlist.example.invalid")
    return key, data_dir, host


def main(argv):
    want_remind = "--remind" in argv
    want_drop = "--drop" in argv
    want_purge = "--purge" in argv
    if sum((want_remind, want_drop, want_purge)) != 1:
        sys.stderr.write(
            "waitlist_jobs: pass exactly one of --remind, --drop, --purge\n")
        raise SystemExit(2)
    dry_run = "--dry-run" in argv
    key, data_dir, host = load_job_config(argv)

    with data_lock(data_dir):
        service = WaitlistService(data_dir, key, host)
        service.reload()  # never scan from a pre-daemon view
        if dry_run:
            due_remind = [r["entry_id"] for r in service.rows.values()
                          if service.reminder_due(r)]
            due_drop = [r["entry_id"] for r in service.rows.values()
                        if service.drop_due(r)]
            due_purge = [r["entry_id"] for r in service.rows.values()
                         if service.purge_due(r)]
            if want_remind:
                sys.stdout.write(
                    f"waitlist_jobs: dry-run — {len(due_remind)} reminder(s) "
                    f"due: {','.join(due_remind) or '(none)'}\n")
            elif want_drop:
                sys.stdout.write(
                    f"waitlist_jobs: dry-run — {len(due_drop)} drop(s) due: "
                    f"{','.join(due_drop) or '(none)'}\n")
            else:
                sys.stdout.write(
                    f"waitlist_jobs: dry-run — {len(due_purge)} purge(s) "
                    f"due: {','.join(due_purge) or '(none)'}\n")
            return 0
        if want_remind:
            sent = service.send_reminders()
            sys.stdout.write(f"waitlist_jobs: sent {sent} reminder(s)\n")
        elif want_drop:
            dropped = service.drop_expired()
            sys.stdout.write(f"waitlist_jobs: dropped {len(dropped)} row(s)\n")
        else:
            purged = service.purge_dropped()
            sys.stdout.write(f"waitlist_jobs: purged {len(purged)} row(s)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
