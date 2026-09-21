#!/usr/bin/env python3
"""waitlist_invites — the invite-wave sender + expiry rollover (H15 build,
slice 3 remainder).

Implements docs/WAITLIST_OPERATIONS.md §7 (invite waves) on top of
waitlistd.WaitlistService:

    waitlist_invites.py --send-wave --wave NAME --count N \\
        --pricing-file pricing.txt --trial-terms-file terms.txt
        the operator opens a wave: the top N confirmed rows FIFO by
        confirmed_at are marked invited (invite_wave = NAME,
        invite_expires_at = now + 14d) and the §7 invite email goes out —
        pricing lines + trial terms filled at send time from the decided
        pricing (the template never contains numbers; compliance:
        WAITLIST_OPERATIONS.md §7 + §11). Emits `invite_sent`
        (FUNNEL_MEASUREMENT.md §3.4) per mailed row. Rows past the 3/24h
        transactional-email cap stay confirmed for a later wave.

    waitlist_invites.py --rollover
        §7 expiry: unclaimed invites expire 14 days after the wave; the
        slot rolls to the next confirmed entry and the expired entry
        rejoins `confirmed` at the back of the queue (confirmed_at reset
        to the expiry time, §5 — no re-confirmation, no new funnel event).

Pricing and trial terms arrive as FILES (not argv): the pricing lines are
operator data that must be byte-stable across the wave and stay out of
shell history / process tables. pricing-file holds one plan/price line
per non-empty line; trial-terms-file holds the trial-terms paragraph.
Both are REQUIRED and must be non-empty — an invite without real pricing
is the honesty violation §11 exists to prevent.

The claim link in the invite email points at
{public_host}/waitlist/claim?token=… — the signup-era claim route (H15
stage 2), not yet served by waitlistd. The page is still NOT deployable
until every WAITLIST_OPERATIONS.md §10 item is live (site/README.md).

Operator cron shape (same env as the other waitlist tooling):

    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \\
        waitlist_invites.py --send-wave --wave wave1 --count 25 \\
        --pricing-file ./pricing.txt --trial-terms-file ./terms.txt
    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \\
        waitlist_invites.py --rollover   # daily

Config (env — same fail-loud contract as waitlistd/waitlist_jobs):
    WAITLIST_HMAC_KEY    operator HMAC key — REQUIRED, fail loud if unset.
    WAITLIST_DATA        operator-owned data dir — REQUIRED, fail loud if
                         unset or unwritable. Never the repo.
    WAITLIST_PUBLIC_HOST public origin for links in queued email
                         (default https://waitlist.example.invalid).

stdlib only. Tested by scripts/test_waitlist_invites.py.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from waitlistd import (  # noqa: E402
    WaitlistService,
    data_lock,
)


def load_config(argv):
    if "--help" in argv or "-h" in argv:
        sys.stdout.write(__doc__ + "\n")
        raise SystemExit(0)
    key_raw = os.environ.get("WAITLIST_HMAC_KEY")
    if not key_raw:
        sys.stderr.write(
            "waitlist_invites: WAITLIST_HMAC_KEY is not set — refusing to "
            "run without the operator HMAC key.\n")
        raise SystemExit(2)
    try:
        key = bytes.fromhex(key_raw)
    except ValueError:
        key = key_raw.encode("utf-8")
    if len(key) < 16:
        sys.stderr.write(
            "waitlist_invites: WAITLIST_HMAC_KEY is too short "
            "(need >= 16 bytes).\n")
        raise SystemExit(2)
    data_dir = os.environ.get("WAITLIST_DATA")
    if not data_dir:
        sys.stderr.write(
            "waitlist_invites: WAITLIST_DATA is not set — refusing to run "
            "without an operator-owned data dir.\n")
        raise SystemExit(2)
    if not os.path.isdir(data_dir) or not os.access(data_dir, os.W_OK):
        sys.stderr.write(
            f"waitlist_invites: WAITLIST_DATA={data_dir!r} is not a "
            "writable directory.\n")
        raise SystemExit(2)
    host = os.environ.get("WAITLIST_PUBLIC_HOST",
                           "https://waitlist.example.invalid")
    return key, data_dir, host


def read_text_file(path, label):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read().strip()
    except OSError as exc:
        sys.stderr.write(f"waitlist_invites: cannot read {label} "
                         f"{path!r}: {exc}\n")
        raise SystemExit(2)
    if not text:
        sys.stderr.write(
            f"waitlist_invites: {label} {path!r} is empty — refusing to "
            "send invites without real pricing/terms (§11).\n")
        raise SystemExit(2)
    return text


def main(argv):
    want_wave = "--send-wave" in argv
    want_rollover = "--rollover" in argv
    if sum((want_wave, want_rollover)) != 1:
        sys.stderr.write(
            "waitlist_invites: pass exactly one of --send-wave, "
            "--rollover\n")
        raise SystemExit(2)
    dry_run = "--dry-run" in argv
    key, data_dir, host = load_config(argv)

    wave = count = pricing = terms = None
    if want_wave:
        def flag(name):
            for i, a in enumerate(argv):
                if a == name and i + 1 < len(argv):
                    return argv[i + 1]
            return None
        wave = flag("--wave")
        count_raw = flag("--count")
        pricing_path = flag("--pricing-file")
        terms_path = flag("--trial-terms-file")
        if not wave or not count_raw or not pricing_path or not terms_path:
            sys.stderr.write(
                "waitlist_invites: --send-wave needs --wave NAME "
                "--count N --pricing-file F --trial-terms-file F\n")
            raise SystemExit(2)
        try:
            count = int(count_raw)
            if count <= 0:
                raise ValueError
        except ValueError:
            sys.stderr.write(
                f"waitlist_invites: --count must be a positive integer "
                f"(got {count_raw!r}).\n")
            raise SystemExit(2)
        pricing = read_text_file(pricing_path, "pricing-file")
        terms = read_text_file(terms_path, "trial-terms-file")

    with data_lock(data_dir):
        service = WaitlistService(data_dir, key, host)
        service.reload()  # never scan from a pre-daemon view
        if want_wave:
            if dry_run:
                eligible = [r for r in service.rows.values()
                            if r.get("status") == "confirmed"]
                sys.stdout.write(
                    f"waitlist_invites: dry-run — {len(eligible)} "
                    f"confirmed row(s) eligible, wave {wave!r} would "
                    f"invite up to {count}\n")
                return 0
            invited = service.send_invite_wave(
                pricing_lines=pricing, trial_terms=terms,
                wave=wave, count=count)
            sys.stdout.write(
                f"waitlist_invites: wave {wave!r} invited "
                f"{len(invited)} row(s)\n")
        else:
            if dry_run:
                due = [r["entry_id"] for r in service.rows.values()
                       if r.get("status") == "invited"]
                sys.stdout.write(
                    f"waitlist_invites: dry-run — {len(due)} invited "
                    "row(s) would be expiry-checked\n")
                return 0
            rolled = service.rollover_expired_invites()
            sys.stdout.write(
                f"waitlist_invites: rolled over {len(rolled)} expired "
                "invite(s)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
