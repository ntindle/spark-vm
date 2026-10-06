"""The D9 reminder/digest sweep scheduler home (#1063).

The push lane's paging policy exists and is tested (`hosted/push_events.py`:
`maybe_enqueue_reminder`, `maybe_enqueue_digest`, `on_heartbeat_stale`,
`on_token_expiry_warning`), but nothing calls it. This module is the
cadence that calls the policy: one sweep reads the plane's D1 database
(the #988 contract tables plus the #872 approvals record), runs the
passes in order — reminders, then digests, then the cadence-driven
watchers — and lets the policy, the gate-1 re-read (D59/D12), and the
enqueue boundary (`hosted/push_enqueue.py`, D50-D57) make every timing,
dedup, and budget decision.

Decisions D66-D75 live in `docs/PUSH_SWEEP_SCHEDULER_DESIGN.md`; this
module is that doc's §3 build slice. The points the doc pins on the
plane worker — the per-minute `scheduled` cron trigger (D66) and the
deploy-side trigger-registration check (D72) — are tracked in #1069
(the plane-workspace cron-trigger wiring); the sweep's job is the
candidate selection and the pass order, and #1063 stays open until
#1069 lands the "without a human driving it" half of the acceptance
criterion.

Design summary (see the design doc for the full D-series):

- **Three passes per sweep: reminders, digests, watchers (D67, D74).**
  A reminder that tips an owner over budget coalesces into the digest
  in the same sweep (D10) — the only ordering that cannot strand
  counts. The watchers (D74/D63) run last. Overlapping sweeps are safe,
  not prevented: the D57 page-once index and the idempotent D61
  `suppressed_terminal` audit make a second concurrent sweep a no-op
  (D69, same discipline as the #874 ingest).
- **The candidate SELECT is a hint, not a decision (D68).** The sweep
  over-selects on purpose; the policy's gate-1 re-read is the timing
  decision, the boundary's page-once dedup is the never-double-page
  guarantee. The sweep writes no lease rows. Truncation is self-healing
  (D75): candidates the policy would certainly `duplicate` — a reminder
  page row already exists for the exact page key, the record is not
  terminal, the record is well-formed — are anti-joined out, so a
  truncated sweep's remainder is actually reached next tick instead of
  re-dominating the first pages. A paged approval that later
  clock-expires stays a candidate (gate-1 still writes its D61 audit);
  a paged record that corrupts between ticks stays a candidate (the D59
  fail-loud still fires).
- **The sweep never pre-checks the D10 budget (D70).** Every due page
  goes through `enqueue_page`; pre-checking would TOCTOU the atomic
  reservation and invent a second, racing budget ledger.
- **One clock, one read (D73).** `now` is taken once per sweep — an
  aware UTC datetime or epoch seconds — and threaded through every
  pass. Epoch-int record times are converted only inside the D49
  adapter; no ISO parsing in the hot path.
- **The watchers are the D62 quiet-period caller, not its inventor
  (D74/D63).** Stale-epoch derivation (missed-heartbeat counting per
  the #864 1/min cadence) and token-warning timing stay plane-side
  caller logic — they are injectable derivation functions here, so the
  sweep owns the cadence and nothing else.
- **DO-alarm retirement (D71):** when #958's per-approval Durable Object
  alarms land, the same change must retire this sweep's *reminder*
  pass (delete it or gate it). The `reminders_enabled` flag is the
  in-repo expression of that plane-side setting (default True); the
  digest pass is unaffected.

D2 (restated, fail-closed): `owner_principal` is resolved from the
plane's enrollment registry via the injected `resolve_owner(box_id)` —
never from a box assertion, never from the approvals row. A missing or
misbehaving resolver is a ValueError, not a guessed owner.

Acceptance reading (the D9 criterion, sliced): a due reminder produces
exactly one `queued` disposition; a decided/expired approval is never a
candidate, so it produces zero pages and zero audit rows (operator
visibility is the approvals record itself); a pending approval that is
terminal only by the clock (`now >= expires_at`) reaches gate-1 and
writes exactly one idempotent `suppressed_terminal` audit row (D61).
"""

from __future__ import annotations

from collections import namedtuple
from datetime import datetime, timezone

from hosted import push_enqueue
from hosted import push_events

# D8/D68 — approvals with a shorter TTL never qualify for a reminder.
REMINDER_MIN_TTL_SECONDS = 300

# D69 — bounded work per sweep: the candidate query pages instead of
# scanning the whole approvals table, and pages are capped. The cap is
# a capacity assumption, not a correctness bound: page_size*max_pages
# must exceed peak due-reminders/minute; repeated truncation is an
# operator alert (the D75 anti-join keeps truncation self-healing).
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 100

SweepSummary = namedtuple(
    "SweepSummary",
    ["reminders", "digests", "stale_watchers", "token_warnings",
     "candidates_seen", "pages_truncated", "reminders_enabled"])
# Each of reminders/digests/stale_watchers/token_warnings is a dict
# disposition -> count, or {"skipped": True} when the pass did not run.

ReminderPassResult = namedtuple(
    "ReminderPassResult",
    ["dispositions", "candidates_seen", "pages_truncated"])
# The reminders pass keeps its meta out of the disposition map: the
# per-pass map is disposition -> count only; candidates_seen and
# pages_truncated ride alongside, and sweep_once copies them onto the
# SweepSummary's dedicated fields.


def _utcnow(now=None):
    """Normalize the sweep's single clock reading (D73).

    Accepts an aware/naive datetime (naive assumed UTC) or epoch
    seconds as int/float. Anything else is a ValueError — a sweep must
    never run on an untrusted clock reading.
    """
    if now is None:
        return datetime.now(timezone.utc)
    if isinstance(now, bool):
        raise ValueError("now must be a datetime or epoch seconds")
    if isinstance(now, (int, float)):
        return datetime.fromtimestamp(now, tz=timezone.utc)
    if isinstance(now, datetime):
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)
    raise ValueError("now must be a datetime or epoch seconds, not %r"
                     % (type(now).__name__,))


def _require_resolve_owner(resolve_owner):
    if not callable(resolve_owner):
        raise ValueError(
            "resolve_owner must be callable (D2: owner identity comes from"
            " the enrollment registry, never from a box assertion)")


def _resolve_owner(resolve_owner, box_id):
    _require_key_material("box_id", box_id)
    owner = resolve_owner(box_id)
    _require_key_material("owner_principal", owner)
    return owner


def _require_key_material(name, value):
    if isinstance(value, bool) or not isinstance(value, str) or not value:
        raise ValueError("%s must be a non-empty str" % name)
    if "\x00" in value:
        raise ValueError("%s must not contain U+0000" % name)


def make_record_adapter(conn, now):
    """Build the D49-style D59 reader adapter for the sweep (D68/D73).

    The #872 approvals record carries `created_at`/`expires_at` as
    epoch ints, `status` as a pending|approved|denied|expired enum, and
    `decision` as "approve"|"deny"|null — none of which is the D59 dict
    shape the policy's gate-1 re-read takes. This adapter runs the
    documented SELECT and builds the D59 dict:

        {"created_at": <full ISO-8601>, "ttl_seconds": <int>,
         "terminal": <bool>}

    Signature is `(box_id, aid)` — the sweep's adapter shape, since the
    candidate carries both; the sweep bridges it per-candidate into the
    policy's one-arg D59 reader. `now` is the sweep's single clock
    reading (D73); a missing row returns None (the policy reports
    `no_record`); a corrupt row is a ValueError — a sweep must never
    silently skip a record whose timing cannot be trusted (D59).
    """
    moment = _utcnow(now)
    moment_epoch = moment.timestamp()

    def get_record(box_id, aid):
        _require_key_material("box_id", box_id)
        _require_key_material("aid", aid)
        row = conn.execute(
            "SELECT created_at, expires_at, decision, status FROM approvals"
            " WHERE box_id = ? AND aid = ?", (box_id, aid)).fetchone()
        if row is None:
            return None
        created_at, expires_at, decision, status = row
        for name, value in (("created_at", created_at),
                            ("expires_at", expires_at)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    "approvals %s for (%r, %r) must be an epoch int, not %r"
                    % (name, box_id, aid, value))
        if decision is not None and not isinstance(decision, str):
            raise ValueError(
                "approvals decision for (%r, %r) must be a str or null"
                % (box_id, aid))
        if status not in ("pending", "approved", "denied", "expired"):
            raise ValueError(
                "approvals status for (%r, %r) must be pending|approved|"
                "denied|expired, not %r" % (box_id, aid, status))
        ttl = expires_at - created_at
        terminal = (
            decision is not None
            or status in ("approved", "denied", "expired")
            or (status == "pending" and moment_epoch >= expires_at))
        return {
            "created_at": datetime.fromtimestamp(
                created_at, tz=timezone.utc).isoformat(),
            "ttl_seconds": ttl,
            "terminal": terminal,
        }

    return get_record


def _reminder_candidates(conn, now_epoch, page_size, max_pages):
    """Yield (box_id, aid) candidate pages per the D68 hint query.

    The predicate must never filter *harder* than the policy: it is a
    hint (D68), so `status='pending' AND decision_seq IS NULL` plus the
    D8 timing — the policy's gate-1 re-read (D59) is the timing
    decision. Keyset pagination ordered by (box_id, aid) keeps each
    query bounded (D69); stops after max_pages and reports truncation
    so the remainder stays due for the next sweep.

    D75 — self-healing truncation: the hint additionally anti-joins
    candidates whose reminder page already exists in
    `push_send_results` — the boundary's outcome-blind dedup fast-path,
    mirrored on `box_id || char(0) || aid` (the exact page-key
    encoding). The exclusion is precise: only candidates the policy
    would certainly `duplicate` are excluded — a page row exists for
    the exact key, the record is not terminal (`decision IS NULL` and
    not clock-expired, mirroring the adapter's terminal derivation),
    and the record is well-formed (epoch ints, null-or-text decision).
    A paged approval that later clock-expires stays a candidate, so
    gate-1 still writes its D61 audit (pre-D75 behavior preserved);
    a paged record that corrupts between ticks stays a candidate, so
    the D59 fail-loud still fires. Every excluded candidate would have
    returned `duplicate` — no page, no audit, no state change — so the
    exclusion is behavior-preserving, and a truncated sweep's
    remainder is actually reached next tick instead of the
    already-processed rows re-dominating the first pages.
    """
    last_box, last_aid = None, None
    pages = 0
    truncated = False
    seen = 0
    while True:
        if pages >= max_pages:
            truncated = True
            break
        where = (
            "WHERE status = 'pending' AND decision_seq IS NULL"
            " AND created_at + (expires_at - created_at) / 2 <= ?"
            " AND (expires_at - created_at) >= ?"
            " AND NOT EXISTS ("
            "  SELECT 1 FROM push_send_results r"
            "  WHERE r.box_id = approvals.box_id"
            "    AND r.event_kind = 'reminder'"
            "    AND r.event_key ="
            "        approvals.box_id || char(0) || approvals.aid"
            "    AND approvals.decision IS NULL"
            "    AND approvals.expires_at > ?"
            "    AND typeof(approvals.created_at) = 'integer'"
            "    AND typeof(approvals.expires_at) = 'integer'"
            ")")
        params = [now_epoch, REMINDER_MIN_TTL_SECONDS, now_epoch]
        if last_box is not None:
            where += " AND (box_id > ? OR (box_id = ? AND aid > ?))"
            params += [last_box, last_box, last_aid]
        rows = conn.execute(
            "SELECT box_id, aid FROM approvals " + where +
            " ORDER BY box_id, aid LIMIT ?", params + [page_size]
        ).fetchall()
        pages += 1
        if not rows:
            break
        seen += len(rows)
        last_box, last_aid = rows[-1]
        yield rows
        if len(rows) < page_size:
            break
    yield {"__meta__": {"seen": seen, "truncated": truncated}}


def sweep_reminders(conn, *, now=None, resolve_owner, record_adapter=None,
                    page_size=DEFAULT_PAGE_SIZE,
                    max_pages=DEFAULT_MAX_PAGES,
                    reminders_enabled=True):
    """Pass 1: due reminders (D67, D68, D69, D70, D75).

    For every candidate the sweep calls the policy's
    `maybe_enqueue_reminder` with the D49 adapter (the D59 dict bridge)
    — the sweep never re-implements timing, dedup, or budget (D70).
    `record_adapter` is the sweep's two-arg `(box_id, aid)` adapter
    (default: the built-in D49 adapter over the approvals table).
    Returns a ReminderPassResult: the disposition -> count map plus
    the pass meta (kept out of the map).
    """
    if not reminders_enabled:
        return ReminderPassResult({"skipped": True}, 0, False)
    _require_resolve_owner(resolve_owner)
    if not isinstance(page_size, int) or isinstance(page_size, bool) \
            or page_size <= 0:
        raise ValueError("page_size must be a positive int")
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) \
            or max_pages <= 0:
        raise ValueError("max_pages must be a positive int")
    moment = _utcnow(now)
    now_epoch = moment.timestamp()
    adapter = record_adapter if record_adapter is not None else \
        make_record_adapter(conn, moment)
    counts = {}
    seen, truncated = 0, False
    for page in _reminder_candidates(conn, now_epoch, page_size,
                                     max_pages):
        if isinstance(page, dict):
            seen = page["__meta__"]["seen"]
            truncated = page["__meta__"]["truncated"]
            break
        for box_id, aid in page:
            owner_principal = _resolve_owner(resolve_owner, box_id)
            r = push_events.maybe_enqueue_reminder(
                conn, box_id=box_id, owner_principal=owner_principal,
                aid=aid,
                get_record=lambda a, _b=box_id: adapter(_b, a),
                now=moment)
            counts[r.disposition] = counts.get(r.disposition, 0) + 1
    return ReminderPassResult(counts, seen, truncated)


def sweep_digests(conn, *, now=None):
    """Pass 2: the D54 digest trigger (D64, D67).

    Scans `push_digest_state` for owners with `count > 0` in the
    owner's current hour window and fires `maybe_enqueue_digest` per
    owner. Runs after the reminder pass (D67): a reminder that
    coalesced into the digest this sweep must be carried by the digest
    in the same sweep. Returns a dict disposition -> count.
    """
    moment = _utcnow(now)
    window_start = push_enqueue.hour_bucket(moment)
    owners = conn.execute(
        "SELECT owner_principal FROM push_digest_state"
        " WHERE window_start = ? AND count > 0", (window_start,)
    ).fetchall()
    counts = {}
    for (owner_principal,) in owners:
        r = push_events.maybe_enqueue_digest(
            conn, owner_principal=owner_principal, now=moment)
        counts[r.disposition] = counts.get(r.disposition, 0) + 1
    return counts


def sweep_watchers(conn, *, now=None, resolve_owner=None,
                   derive_stale=None, derive_token_warnings=None):
    """Pass 3: the cadence-driven watchers (D74/D63, scope extension).

    `derive_stale(conn, moment)` yields `(box_id, stale_epoch)` —
    missed-heartbeat counting per the #864 1/min cadence — and
    `derive_token_warnings(conn, moment)` yields
    `(box_id, token_hash)` — the boxes-row read with the 2h lead and
    F6's no-rotation-since-last-window check. Both stay plane-side
    caller logic (the #969 docstring's D2 restatement); the sweep only
    supplies the cadence and resolves owners from the registry (D2).
    A derivation that is None means the watcher is not wired — the
    pass reports "skipped", it is never guessed.
    Returns {"stale": {...}, "token_warnings": {...}} disposition maps.
    """
    moment = _utcnow(now)
    stale_counts = {}
    if derive_stale is not None:
        _require_resolve_owner(resolve_owner)
        for box_id, stale_epoch in derive_stale(conn, moment):
            owner_principal = _resolve_owner(resolve_owner, box_id)
            r = push_events.on_heartbeat_stale(
                conn, box_id=box_id, owner_principal=owner_principal,
                stale_epoch=stale_epoch, now=moment)
            stale_counts[r.disposition] = \
                stale_counts.get(r.disposition, 0) + 1
    else:
        stale_counts = {"skipped": True}
    warning_counts = {}
    if derive_token_warnings is not None:
        _require_resolve_owner(resolve_owner)
        for box_id, token_hash in derive_token_warnings(conn, moment):
            owner_principal = _resolve_owner(resolve_owner, box_id)
            r = push_events.on_token_expiry_warning(
                conn, box_id=box_id, owner_principal=owner_principal,
                token_hash=token_hash, now=moment)
            warning_counts[r.disposition] = \
                warning_counts.get(r.disposition, 0) + 1
    else:
        warning_counts = {"skipped": True}
    return {"stale": stale_counts, "token_warnings": warning_counts}


def sweep_once(conn, *, now=None, resolve_owner, record_adapter=None,
               page_size=DEFAULT_PAGE_SIZE, max_pages=DEFAULT_MAX_PAGES,
               reminders_enabled=True, derive_stale=None,
               derive_token_warnings=None):
    """Run one full D9 sweep: reminders, then digests, then watchers.

    `now` is taken once and threaded through every pass (D73).
    `resolve_owner(box_id)` is required (D2) whenever a pass needs an
    owner; `record_adapter` overrides the built-in D49 adapter (tests);
    the watchers fire only when their derivations are wired.

    Returns a SweepSummary. The D9 acceptance criterion reads off it:
    a due reminder produces exactly one `queued` disposition; a
    decided/expired approval is never a candidate, so it produces zero
    pages and zero audit rows; a pending approval terminal only by the
    clock writes exactly one idempotent `superseded_terminal` audit
    row (D61).
    """
    moment = _utcnow(now)
    rem = sweep_reminders(
        conn, now=moment, resolve_owner=resolve_owner,
        record_adapter=record_adapter, page_size=page_size,
        max_pages=max_pages, reminders_enabled=reminders_enabled)
    digests = sweep_digests(conn, now=moment)
    watchers = sweep_watchers(
        conn, now=moment, resolve_owner=resolve_owner,
        derive_stale=derive_stale,
        derive_token_warnings=derive_token_warnings)
    return SweepSummary(
        reminders=rem.dispositions,
        digests=digests,
        stale_watchers=watchers["stale"],
        token_warnings=watchers["token_warnings"],
        candidates_seen=rem.candidates_seen,
        pages_truncated=rem.pages_truncated,
        reminders_enabled=reminders_enabled)
