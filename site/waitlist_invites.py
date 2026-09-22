#!/usr/bin/env python3
"""waitlist_invites — the invite-wave sender + expiry rollover (H15 build,
slice 3 remainder).

Implements docs/WAITLIST_OPERATIONS.md §7 (invite waves) on top of
waitlistd.WaitlistService:

    waitlist_invites.py --send-wave --wave NAME --count N \
        --pricing-file pricing.txt --trial-terms-file terms.txt
        the operator opens a wave: up to N confirmed rows FIFO by
        confirmed_at are mailed the §7 invite email — pricing lines +
        trial terms filled at send time from the decided pricing (the
        template never contains pricing numbers; compliance:
        WAITLIST_OPERATIONS.md §7 + §11) — and marked invited
        (invite_wave = NAME, invite_expires_at = now + 14d). Emits
        `invite_sent` (FUNNEL_MEASUREMENT.md §3.4) per mailed row. Rows
        past the 3/24h transactional-email cap stay confirmed for a
        later wave.

    waitlist_invites.py --rollover
        §7 expiry: unclaimed invites expire 14 days after the wave; the
        slot rolls to the next confirmed entry and the expired entry
        rejoins `confirmed` at the back of the queue (confirmed_at reset
        to the expiry time, §5 — no re-confirmation, no new funnel event).

    waitlist_invites.py --reconcile [--dry-run]
        Issue #234: re-derive `invite_sent` funnel events lost to the
        commit -> emit crash window. The wave commits the invited row
        BEFORE emitting `invite_sent`; a crash in that window
        leaves an invited row whose email is spooled but whose event
        never fired, and the funnel reads conservatively until repaired.
        This pass re-derives exactly those missing events from rows.jsonl
        (append-only posture — no hand-edits to funnel_events.jsonl) and
        marks each with attrs reconciled=True + via=reconcile_invite_events.
        Idempotent: re-running emits nothing new. Sends no email, so no
        WAITLIST_CLAIM_LIVE gate.

    waitlist_invites.py --reinstate-confirmed --entry-id EID [--entry-id ...] --reason TEXT [--dry-run] [--force]
        Issue #235: flip stranded invited rows back to confirmed in the
        append-only posture — the repair the fault-injection tests
        perform by hand. Covers the `_consume_token(old)` -> row-commit
        crash window (on-disk row still invited with a consumed token)
        and operator-initiated re-waves (bounced/lost invite email).
        One new rows.jsonl revision per row: status -> confirmed, the
        invite keys popped, confirmed_at KEPT (crash repair, not expiry:
        the entry keeps its original queue position), the revision
        stamped with `reinstate_at` + `reinstate_reason`. The next wave
        re-invites with a fresh token. A row whose invite token is still
        LIVE is refused unless --force (reinstating kills the claim
        link); --force consumes the live token so the trail reads
        "consumed". An EXPIRED invite is refused outright — reinstating it would silently skip the
        disclosed 14-day expiry -> back-of-queue rule; run --rollover instead. --reason is required —
        it is the audit trail. Sends no email, so no WAITLIST_CLAIM_LIVE gate.

    waitlist_invites.py --diagnose
        Issue #235 item 3: read-only listing of every invited row with
        its token state (ok / expired / consumed / invalid / missing)
        and the recommended action — healthy rows, --rollover-due rows,
        crash-suspect reinstate candidates, and hand-damaged rows the
        operator inspects manually. Sends nothing, mutates nothing.

Pricing and trial terms arrive as FILES (not argv): the pricing lines are
operator data that must be byte-stable across the wave and stay out of
shell history / process tables. pricing-file holds one plan/price line
per non-empty line; trial-terms-file holds the trial-terms paragraph.
Both are REQUIRED and must be non-empty — an invite without real pricing
is the honesty violation §11 exists to prevent.

The claim link in the invite email points at
{public_host}/waitlist/claim?token=… — served by waitlistd (the claim
slice: renders-only GET, records the claim on POST, emits the `claimed`
funnel event). The page is still NOT deployable
until every WAITLIST_OPERATIONS.md §10 item is live (site/README.md).

Operator cron shape (same env as the other waitlist tooling):

    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \\
        waitlist_invites.py --send-wave --wave wave1 --count 25 \\
        --pricing-file ./pricing.txt --trial-terms-file ./terms.txt
    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \\
        waitlist_invites.py --rollover   # daily

On demand (no claim-live gate — sends nothing; idempotent):

    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \\
        waitlist_invites.py --reconcile [--dry-run]  # after any suspected crash
    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \\
        waitlist_invites.py --diagnose  # which stranded state each invited row is in
    WAITLIST_HMAC_KEY=... WAITLIST_DATA=... \\
        waitlist_invites.py --reinstate-confirmed --entry-id EID \\
            --reason "re-invite crashed before row commit; stray email dead" [--dry-run] [--force]

Config (env — same fail-loud contract as waitlistd/waitlist_jobs):
    WAITLIST_HMAC_KEY    operator HMAC key — REQUIRED, fail loud if unset.
    WAITLIST_DATA        operator-owned data dir — REQUIRED, fail loud if
                         unset or unwritable. Never the repo.
    WAITLIST_PUBLIC_HOST public origin for links in queued email
                         (default https://waitlist.example.invalid).
    WAITLIST_CLAIM_LIVE  set to exactly "1" only when GET
                         /waitlist/claim actually serves invite tokens —
                         the route ships in waitlistd (claim slice), and
                         this attestation is the operator's confirmation
                         that the deployed control plane carries it.
                         REQUIRED for a real --send-wave (not for
                         --dry-run or --rollover): the invite email's
                         single prominent action is the claim link, and
                         nothing but this attestation stands between an
                         operator typo and a wave of dead-CTA first
                         touches. The page stays non-deployable until
                         every WAITLIST_OPERATIONS.md §10 item is live;
                         this is the guard at the send moment.

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
    want_reconcile = "--reconcile" in argv
    want_reinstate = "--reinstate-confirmed" in argv
    want_diagnose = "--diagnose" in argv
    actions = (want_wave, want_rollover, want_reconcile,
               want_reinstate, want_diagnose)
    if sum(actions) != 1:
        sys.stderr.write(
            "waitlist_invites: pass exactly one of --send-wave, "
            "--rollover, --reconcile, --reinstate-confirmed, --diagnose\n")
        raise SystemExit(2)
    dry_run = "--dry-run" in argv
    key, data_dir, host = load_config(argv)

    def flag(name):
        for i, a in enumerate(argv):
            if a == name and i + 1 < len(argv):
                return argv[i + 1]
        return None

    def flags_all(name):
        return [argv[i + 1] for i, a in enumerate(argv)
                if a == name and i + 1 < len(argv)]

    if want_wave and not dry_run and \
            os.environ.get("WAITLIST_CLAIM_LIVE") != "1":
        # The dead-form rule protects the page; this protects the
        # sender. A wave's only CTA is the claim link — refuse to send
        # one while the claim route is unbuilt.
        sys.stderr.write(
            "waitlist_invites: refusing to send a wave — "
            "WAITLIST_CLAIM_LIVE is not \"1\". Set it only when GET "
            "/waitlist/claim serves invite tokens "
            "(WAITLIST_OPERATIONS.md §10).\n")
        raise SystemExit(2)

    wave = count = pricing = terms = None
    if want_wave:
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

    reinstate_ids = reason = None
    reinstate_force = False
    if want_reinstate:
        reinstate_ids = flags_all("--entry-id")
        reason = flag("--reason")
        if not reinstate_ids:
            sys.stderr.write(
                "waitlist_invites: --reinstate-confirmed needs at least "
                "one --entry-id EID\n")
            raise SystemExit(2)
        if not reason or not reason.strip():
            sys.stderr.write(
                "waitlist_invites: --reinstate-confirmed needs --reason "
                "TEXT — it is recorded on the row as the audit trail\n")
            raise SystemExit(2)
        reinstate_force = "--force" in argv

    with data_lock(data_dir):
        service = WaitlistService(data_dir, key, host)
        service.reload()  # never scan from a pre-daemon view
        if want_diagnose:
            rows = service.diagnose_invites()
            if not rows:
                sys.stdout.write(
                    "waitlist_invites: no invited rows — nothing to "
                    "diagnose\n")
                return 0
            for r in rows:
                sys.stdout.write(
                    f"waitlist_invites: {r['entry_id']} "
                    f"({r['owner']}) token={r['token_state']}: "
                    f"{r['recommendation']}\n")
            return 0
        if want_wave:
            if dry_run:
                eligible = [r for r in service.rows.values()
                            if r.get("status") == "confirmed"]
                sys.stdout.write(
                    f"waitlist_invites: dry-run — {len(eligible)} "
                    f"confirmed row(s) eligible, wave {wave!r} would "
                    f"invite up to {count} (rows past the 3/24h email cap "
                    "stay confirmed — the real wave mails only cap-clear "
                    "rows)\n")
                return 0
            invited = service.send_invite_wave(
                pricing_lines=pricing, trial_terms=terms,
                wave=wave, count=count)
            sys.stdout.write(
                f"waitlist_invites: wave {wave!r} invited "
                f"{len(invited)} row(s)\n")
        elif want_reconcile:
            reconciled = service.reconcile_invite_events(dry_run=dry_run)
            verb = "would reconcile" if dry_run else "reconciled"
            sys.stdout.write(
                f"waitlist_invites: {verb} "
                f"{len(reconciled)} missing invite_sent event(s)"
                + (f": {', '.join(reconciled)}" if reconciled else "")
                + "\n")
            return 0
        elif want_reinstate:
            try:
                if dry_run:
                    plan = service.reinstate_confirmed(
                        reinstate_ids, reason=reason,
                        force=reinstate_force, dry_run=True)
                    for p in plan:
                        sys.stdout.write(
                            f"waitlist_invites: dry-run — "
                            f"{p['entry_id']} token={p['token_state']}: "
                            f"would {p['would']}\n")
                    return 0
                reinstated = service.reinstate_confirmed(
                    reinstate_ids, reason=reason, force=reinstate_force)
            except ValueError as exc:
                sys.stderr.write(f"waitlist_invites: {exc}\n")
                raise SystemExit(2)
            sys.stdout.write(
                f"waitlist_invites: reinstated {len(reinstated)} row(s) "
                f"to confirmed"
                + (f": {', '.join(reinstated)}" if reinstated else "")
                + " — re-wave to re-invite with a fresh token\n")
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
