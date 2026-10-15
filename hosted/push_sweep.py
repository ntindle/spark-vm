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

Decisions D66-D75 live in `docs/PUSH_SWEEP_SCHEDULER_DESIGN.md` (D103,
the per-tick work bound, is pinned there too); this
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
- **Per-candidate error isolation (D78).** A raising candidate is
  counted `poisoned` on its pass's disposition map, logged loudly with
  its identity, and skipped — the pass continues with the next
  candidate. The poison row stays a candidate on the next tick, so
  D59's fail-loud is preserved (loud every tick, never silently
  skipped) without the fleet-wide starvation a whole-pass abort
  caused. Derivation-level failures stop only their own watcher; the
  other watcher still runs. Infrastructure failures (the candidate
  SELECT itself, the pending-window SELECT) are not data corruption —
  they still abort the pass loudly.
- **Per-tick work bound** (D103). D69's page cap bounds the reminders
  pass, but the watcher derivations are caller-supplied generators
  with no termination guarantee — a wedged derivation would hang the
  sweep forever and the per-minute cron would pile up overlapping
  sweeps. `sweep_once` takes an optional `time_budget_s`: one
  `time.monotonic()` deadline shared across all three passes, checked
  between candidates; on exhaustion the pass stops, records
  `budget_exhausted`, and the unreached candidates stay due for the
  next tick (the same discipline as the send loop's D96). An optional
  `tick_interval_s` fires a `tick_overrun` note on the summary when
  the sweep exceeds its schedule interval, so the operator sees the
  pile-up risk before it becomes one. Both default to None (unbounded,
  the previous behavior) and are validated fail-closed.

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

import math
import sys
import time
from collections import namedtuple
from datetime import datetime, timezone

from hosted import push_enqueue
from hosted import push_events

# D8 — approvals with a shorter TTL never qualify for a reminder.
# Single-sourced: the policy owns the constant
# (hosted/push_events.py); the sweep's hint predicate must agree with
# the policy's gate, so it reads the policy's value — a second local
# definition would let a one-sided future change silently miss
# reminders (#1507).

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
     "candidates_seen", "pages_truncated", "reminders_enabled", "notes",
     "budget_truncated"],
    defaults=[(), False])
# Each of reminders/digests/stale_watchers/token_warnings is a dict
# disposition -> count, or {"skipped": True} when the pass did not run.
# "notes" is a tuple of (key, message) sweep-level annotations — e.g.
# ("tick_overrun", ...) when the sweep exceeded its schedule interval
# (D103). It defaults to () so existing field-name readers are
# unaffected.
# "budget_truncated" is True when any pass stopped early on the D103
# time budget (the unreached candidates stay due for the next tick).
# It is deliberately distinct from "pages_truncated" (the D69 page
# cap): the two have different remediations — raise time_budget_s /
# the cadence vs. raise max_pages — so the operator alert reads
# `pages_truncated OR budget_truncated`, never one boolean for both.

ReminderPassResult = namedtuple(
    "ReminderPassResult",
    ["dispositions", "candidates_seen", "pages_truncated",
     "budget_truncated"],
    defaults=[False])
# The reminders pass keeps its meta out of the disposition map: the
# per-pass map is disposition -> count only; candidates_seen,
# pages_truncated, and budget_truncated ride alongside, and sweep_once
# copies them onto the SweepSummary's dedicated fields. budget_truncated
# (D103) is distinct from pages_truncated (D69): time-budget stop vs.
# page-cap stop — different remediations.


def _utcnow(now=None):
    """Normalize the sweep's single clock reading (D73).

    Accepts an aware/naive datetime (naive assumed UTC) or epoch
    seconds as int/float. Anything else is a ValueError — a sweep must
    never run on an untrusted clock reading. Non-finite epoch floats
    (NaN, ±inf) are rejected by the `math.isfinite` guard, and
    finite-but-out-of-range epochs by the `fromtimestamp` wrap below
    (`datetime.fromtimestamp` raises OverflowError — or OSError,
    depending on the platform — on those). Both become ValueError so
    callers that `except ValueError` around the clock boundary catch
    every bad reading (the D96 NaN/inf discipline).
    """
    if now is None:
        return datetime.now(timezone.utc)
    if isinstance(now, bool):
        raise ValueError("now must be a datetime or epoch seconds")
    if isinstance(now, (int, float)):
        if isinstance(now, float) and not math.isfinite(now):
            raise ValueError("now must be a finite datetime or epoch "
                             "seconds, not %r" % (now,))
        try:
            return datetime.fromtimestamp(now, tz=timezone.utc)
        except (OverflowError, OSError) as exc:
            raise ValueError("epoch seconds out of range: %r"
                             % (now,)) from exc
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


def _validate_budget_arg(name, value):
    """Fail-closed validation for the D103 tick-bound args (the D96 discipline).

    A bound is a finite non-negative number or None (unbounded, the
    documented default) — nothing else. NaN and inf must not pass:
    `elapsed >= nan` is always False, so a NaN budget would silently
    disable the bound while appearing configured (the opposite of
    fail-closed; a JSON config's NaN/Infinity literals are the realistic
    vector). Mirrors the validation in hosted/push_send_loop.py so the
    two tick bounds reject the same shapes.
    """
    if value is not None and (isinstance(value, bool)
                              or not isinstance(value, (int, float))
                              or not math.isfinite(value)
                              or value < 0):
        raise ValueError(
            "%s must be a finite non-negative number or None" % name)


def _deadline_reached(deadline):
    """True once the sweep's wall-clock budget is spent (D103).

    `deadline` is an absolute time.monotonic() reading computed once in
    sweep_once, or None for the unbounded default. Checked between
    candidates so a pass stops promptly without abandoning a candidate
    mid-flight.
    """
    return deadline is not None and time.monotonic() >= deadline


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


def _loud(msg):
    """Emit a loud operator-visible line for a poisoned candidate (D78).

    The sweep is driven by #1069's scheduled handler; stderr is the
    loud channel that handler already surfaces. Never raises — a
    broken loud channel must not kill the pass it is reporting on.
    """
    try:
        print("[push_sweep] " + msg, file=sys.stderr, flush=True)
    except Exception:
        pass


def _isolate_candidate(counts, pass_name, identity, fn):
    """Run one candidate's sweep body with per-candidate isolation (D78).

    A raising candidate is counted as a `poisoned` disposition on its
    pass's summary map, logged loudly with its identity, and skipped —
    the pass continues. The poison row stays a candidate on the next
    tick, so D59's fail-loud is preserved (still loud every tick, never
    silently skipped) without the fleet-wide starvation. Only
    `Exception` is caught: `BaseException` (KeyboardInterrupt,
    SystemExit) still aborts the whole sweep — those are operator
    signals, not data corruption.
    """
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 — per-candidate isolation is the point
        counts["poisoned"] = counts.get("poisoned", 0) + 1
        _loud("%s: poisoned candidate %s: %r — pass continues"
              % (pass_name, identity, exc))


def _close_abandoned(items, label):
    """Deliver GeneratorExit to a derivation abandoned on the D103 budget.

    Deterministic cleanup instead of GC timing: a suspended generator
    gets `close()` (GeneratorExit at its current yield) rather than
    being left for refcount collection. Non-generator iterables
    (e.g. the list derivations tests use) have no `close` — tolerated.
    A raising `close()` is logged loudly, never fatal: the sweep is
    already on the budget-exhaustion path and must not die in cleanup.
    """
    close = getattr(items, "close", None)
    if close is None:
        return
    try:
        close()
    except Exception as exc:  # noqa: BLE001 — cleanup must not kill the sweep
        _loud("%s: derivation close() raised during budget abandonment: "
              "%r — continuing" % (label, exc))


def _drive_watcher(counts, label, derive, conn, moment, on_item,
                   deadline=None):
    """Drive one watcher derivation with per-candidate isolation (D78).

    Each yielded item is an isolated candidate (see
    `_isolate_candidate`). A derivation that raises mid-iteration
    cannot continue — the generator is dead — so it is counted once as
    `poisoned`, logged loudly, and *that watcher* stops; the other
    watcher still runs. The derivation call itself is inside the same
    guard: caller-wired logic that fails at call time is one loud
    poisoned count, not a whole-sweep abort.

    D103 — the derivation is caller-supplied and carries no termination
    guarantee, so the deadline is checked at the top of every loop
    iteration, *before* `next(items)`: a derivation that blocks before
    its first yield would otherwise never reach a post-`next()` check,
    and an already-exhausted budget must not spend one more derivation
    call discovering it. On exhaustion the watcher stops, the
    derivation generator is `close()`d (deterministic GeneratorExit
    delivery — see `_close_abandoned`), the pass records
    `budget_exhausted`, and the sweep continues with the next watcher.

    Abandonment contract (pinned while the plane-side derivations are
    still unwritten, #1069): derivations must tolerate abandonment at
    any yield — no open transactions across yields; cursors and other
    resources released via `try/finally` (GeneratorExit is delivered
    deterministically on abandonment). The sweep guarantees GeneratorExit
    delivery and nothing more about derivation-held resources.

    Cooperative residual, stated honestly: the bound is checked
    *between* candidates and cannot preempt a single `next()` — or a
    single candidate's processing — that blocks indefinitely.
    Derivations must not block unboundedly within one step; a wedged
    step still hangs the sweep, and `tick_overrun` is the operator
    signal for it.
    """
    if _deadline_reached(deadline):
        counts["budget_exhausted"] = True
        _loud("%s: time budget already exhausted — watcher skipped; "
              "items stay due for the next tick" % label)
        return
    try:
        items = iter(derive(conn, moment))
    except Exception as exc:  # noqa: BLE001 — see _isolate_candidate
        counts["poisoned"] = counts.get("poisoned", 0) + 1
        _loud("%s: poisoned derivation (failed at call time): %r — "
              "watcher stops, other watchers continue"
              % (label, exc))
        return
    while True:
        if _deadline_reached(deadline):
            counts["budget_exhausted"] = True
            _close_abandoned(items, label)
            _loud("%s: time budget exhausted — watcher stops; "
                  "unreached items stay due for the next tick"
                  % label)
            return
        try:
            item = next(items)
        except StopIteration:
            return
        except Exception as exc:  # noqa: BLE001 — see _isolate_candidate
            counts["poisoned"] = counts.get("poisoned", 0) + 1
            _loud("%s: poisoned derivation (raised mid-iteration): %r — "
                  "watcher stops, other watchers continue"
                  % (label, exc))
            return
        _isolate_candidate(counts, label, repr(item),
                           lambda _it=item: on_item(_it))


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
    decision. The D8 bound is the policy's constant
    (`push_events.REMINDER_MIN_TTL_SECONDS`, single-sourced per #1507)
    — the hint must agree with the gate it feeds. Keyset pagination
    ordered by (box_id, aid) keeps each
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
        params = [now_epoch, push_events.REMINDER_MIN_TTL_SECONDS,
                  now_epoch]
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
        last_box, last_aid = rows[-1]
        yield rows
        if len(rows) < page_size:
            break
    yield {"__meta__": {"truncated": truncated}}


def sweep_reminders(conn, *, now=None, resolve_owner, record_adapter=None,
                    page_size=DEFAULT_PAGE_SIZE,
                    max_pages=DEFAULT_MAX_PAGES,
                    reminders_enabled=True, deadline=None):
    """Pass 1: due reminders (D67, D68, D69, D70, D75, D103).

    For every candidate the sweep calls the policy's
    `maybe_enqueue_reminder` with the D49 adapter (the D59 dict bridge)
    — the sweep never re-implements timing, dedup, or budget (D70).
    `record_adapter` is the sweep's two-arg `(box_id, aid)` adapter
    (default: the built-in D49 adapter over the approvals table).
    Each candidate is isolated (D78): a raising candidate is counted
    `poisoned`, logged loudly, and skipped — the pass continues.
    D103 — `deadline` is the sweep's absolute time.monotonic() budget
    (None = unbounded, the default): when it is reached the pass stops,
    records `budget_exhausted`, and reports `budget_truncated=True`
    (not `pages_truncated` — the D69 page cap is a different stop with
    a different remediation) — the unreached candidates stay due for
    the next tick, exactly the truncation contract's self-healing half.
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
    if _deadline_reached(deadline):
        counts["budget_exhausted"] = True
        _loud("reminders: time budget already exhausted — pass skipped;"
              " candidates stay due for the next tick")
        return ReminderPassResult(counts, 0, False, True)
    seen, truncated = 0, False
    for page in _reminder_candidates(conn, now_epoch, page_size,
                                     max_pages):
        if isinstance(page, dict):
            truncated = page["__meta__"]["truncated"]
            break
        for box_id, aid in page:
            if _deadline_reached(deadline):
                counts["budget_exhausted"] = True
                _loud("reminders: time budget exhausted — pass stops;"
                      " unreached candidates stay due for the next tick")
                return ReminderPassResult(counts, seen, False, True)
            seen += 1
            def _one(_box=box_id, _aid=aid):
                owner_principal = _resolve_owner(resolve_owner, _box)
                r = push_events.maybe_enqueue_reminder(
                    conn, box_id=_box, owner_principal=owner_principal,
                    aid=_aid,
                    get_record=lambda a, _b=_box: adapter(_b, a),
                    now=moment)
                counts[r.disposition] = counts.get(r.disposition, 0) + 1
            _isolate_candidate(counts, "reminders",
                               "box_id=%r aid=%r" % (box_id, aid), _one)
    return ReminderPassResult(counts, seen, truncated)


def sweep_digests(conn, *, now=None, deadline=None):
    """Pass 2: the D54 digest trigger (D64, D67, D76, D103).

    Fires `maybe_enqueue_digest` for every *pending* digest window —
    `count > 0` with `enqueued_at IS NULL` — oldest first (D76). The
    current window is the common case; the pending scan is what heals
    the hour-boundary strand: coalescing that lands on window H's row
    after H's last digest-pass tick fires late with H's own window
    key (a fresh page-once key — no dedup conflict with any other
    window) and consumes the current window's owner budget (the page
    goes out now, so now's budget is the honest one). A window whose
    digest already fired (`enqueued_at` set) is never refired — the
    D67 accepted drift for post-fire coalescing stands. Runs after
    the reminder pass (D67): a reminder that coalesced into the
    digest this sweep must be carried by the digest in the same sweep.
    Each window is isolated (D78): a raising window is counted
    `poisoned`, logged loudly, and skipped — the pass continues.
    D103 — `deadline` is the sweep's absolute time.monotonic() budget
    (None = unbounded, the default): when it is reached the pass stops
    and records `budget_exhausted`; unfired windows stay pending for
    the next tick. Returns a dict disposition -> count.
    """
    moment = _utcnow(now)
    if _deadline_reached(deadline):
        _loud("digests: time budget already exhausted — pass skipped;"
              " windows stay pending for the next tick")
        return {"budget_exhausted": True}
    current = push_enqueue.hour_bucket(moment)
    pending = conn.execute(
        "SELECT owner_principal, window_start FROM push_digest_state"
        " WHERE count > 0 AND enqueued_at IS NULL"
        " AND window_start <= ?"
        " ORDER BY window_start, owner_principal",
        (current,)).fetchall()
    counts = {}
    for owner_principal, window_start in pending:
        if _deadline_reached(deadline):
            counts["budget_exhausted"] = True
            _loud("digests: time budget exhausted — pass stops;"
                  " unfired windows stay pending for the next tick")
            break
        def _one(_owner=owner_principal, _window=window_start):
            r = push_events.maybe_enqueue_digest(
                conn, owner_principal=_owner, now=moment,
                window_start=_window)
            counts[r.disposition] = counts.get(r.disposition, 0) + 1
        _isolate_candidate(
            counts, "digests",
            "owner=%r window=%r" % (owner_principal, window_start), _one)
    return counts


def sweep_watchers(conn, *, now=None, resolve_owner=None,
                   derive_stale=None, derive_token_warnings=None,
                   deadline=None):
    """Pass 3: the cadence-driven watchers (D74/D63, D103, scope extension).

    `derive_stale(conn, moment)` yields `(box_id, stale_epoch)` —
    missed-heartbeat counting per the #864 1/min cadence — and
    `derive_token_warnings(conn, moment)` yields
    `(box_id, token_hash)` — the boxes-row read with the 2h lead and
    F6's no-rotation-since-last-window check. Both stay plane-side
    caller logic (the #969 docstring's D2 restatement); the sweep only
    supplies the cadence and resolves owners from the registry (D2).
    A derivation that is None means the watcher is not wired — the
    pass reports "skipped", it is never guessed. Each yielded item is
    an isolated candidate (D78); a derivation that raises stops only
    its own watcher. D103 — `deadline` is the sweep's absolute
    time.monotonic() budget (None = unbounded, the default), checked
    before every derived item: without it a wedged derivation hangs
    the sweep and the per-minute cron piles up overlapping sweeps.
    Returns {"stale": {...}, "token_warnings": {...}}
    disposition maps.
    """
    moment = _utcnow(now)
    stale_counts = {}
    if derive_stale is not None:
        _require_resolve_owner(resolve_owner)
        def _stale(item, _resolve=resolve_owner):
            box_id, stale_epoch = item
            owner_principal = _resolve_owner(_resolve, box_id)
            r = push_events.on_heartbeat_stale(
                conn, box_id=box_id, owner_principal=owner_principal,
                stale_epoch=stale_epoch, now=moment)
            stale_counts[r.disposition] = \
                stale_counts.get(r.disposition, 0) + 1
        _drive_watcher(stale_counts, "stale_watchers",
                       derive_stale, conn, moment, _stale,
                       deadline=deadline)
    else:
        stale_counts = {"skipped": True}
    warning_counts = {}
    if derive_token_warnings is not None:
        _require_resolve_owner(resolve_owner)
        def _warn(item, _resolve=resolve_owner):
            box_id, token_hash = item
            owner_principal = _resolve_owner(_resolve, box_id)
            r = push_events.on_token_expiry_warning(
                conn, box_id=box_id, owner_principal=owner_principal,
                token_hash=token_hash, now=moment)
            warning_counts[r.disposition] = \
                warning_counts.get(r.disposition, 0) + 1
        _drive_watcher(warning_counts, "token_warnings",
                       derive_token_warnings, conn, moment, _warn,
                       deadline=deadline)
    else:
        warning_counts = {"skipped": True}
    return {"stale": stale_counts, "token_warnings": warning_counts}


def sweep_once(conn, *, now=None, resolve_owner, record_adapter=None,
               page_size=DEFAULT_PAGE_SIZE, max_pages=DEFAULT_MAX_PAGES,
               reminders_enabled=True, derive_stale=None,
               derive_token_warnings=None,
               time_budget_s=None, tick_interval_s=None):
    """Run one full D9 sweep: reminders, then digests, then watchers.

    `now` is taken once and threaded through every pass (D73).
    `resolve_owner(box_id)` is required (D2) whenever a pass needs an
    owner; `record_adapter` overrides the built-in D49 adapter (tests);
    the watchers fire only when their derivations are wired.

    D103 — `time_budget_s` (the D96 discipline, applied to the sweep):
    the sweep stops driving new candidates once its elapsed wall-clock
    time reaches the budget; unreached candidates stay due for the next
    tick. None (the default) keeps the unbounded behavior.
    `tick_interval_s` (the schedule interval): when set and the
    measured sweep duration exceeds it, a `tick_overrun` note lands on
    the summary — the operator sees the overrun before the next tick
    can overlap. Both are validated fail-closed (finite non-negative
    number or None; NaN/inf/bool/str/negative are ValueError).

    Returns a SweepSummary. The D9 acceptance criterion reads off it:
    a due reminder produces exactly one `queued` disposition; a
    decided/expired approval is never a candidate, so it produces zero
    pages and zero audit rows; a pending approval terminal only by the
    clock writes exactly one idempotent `suppressed_terminal` audit row
    (D61) — the summary reports the matching `superseded_terminal`
    disposition; the names split deliberately (see §12 of
    docs/D9_PUSH_SWEEP_OPERATOR_GUIDE.md).
    """
    _validate_budget_arg("time_budget_s", time_budget_s)
    _validate_budget_arg("tick_interval_s", tick_interval_s)
    moment = _utcnow(now)
    # (D103) wall-clock, not the injected logical clock: the budget and
    # the overrun alarm measure how long the sweep *ran*, which is
    # time.monotonic() regardless of what `now` the caller injected
    # (mixing them would compare real time against a fixture date).
    tick_start = time.monotonic()
    deadline = (tick_start + time_budget_s
                if time_budget_s is not None else None)
    rem = sweep_reminders(
        conn, now=moment, resolve_owner=resolve_owner,
        record_adapter=record_adapter, page_size=page_size,
        max_pages=max_pages, reminders_enabled=reminders_enabled,
        deadline=deadline)
    digests = sweep_digests(conn, now=moment, deadline=deadline)
    watchers = sweep_watchers(
        conn, now=moment, resolve_owner=resolve_owner,
        derive_stale=derive_stale,
        derive_token_warnings=derive_token_warnings,
        deadline=deadline)
    notes = []
    duration_s = time.monotonic() - tick_start
    if tick_interval_s is not None and duration_s > tick_interval_s:
        # (D103) the sweep overran its schedule interval: the next tick
        # may have overlapped, which the operator must see before it
        # becomes a pile-up (this is the #1506 failure mode made
        # visible).
        msg = ("sweep ran %.1fs, exceeding the %.1fs schedule interval"
               " — the next tick may have overlapped"
               % (duration_s, tick_interval_s))
        _loud("sweep_once: tick_overrun — " + msg)
        notes.append(("tick_overrun", msg))
    # D103/B2 — the operator alert reads `pages_truncated OR
    # budget_truncated`: any pass stopping early on the time budget
    # marks the sweep, so a tick that did partial work is visible even
    # when the page cap was never hit.
    budget_truncated = (
        rem.budget_truncated
        or "budget_exhausted" in digests
        or "budget_exhausted" in watchers["stale"]
        or "budget_exhausted" in watchers["token_warnings"])
    return SweepSummary(
        reminders=rem.dispositions,
        digests=digests,
        stale_watchers=watchers["stale"],
        token_warnings=watchers["token_warnings"],
        candidates_seen=rem.candidates_seen,
        pages_truncated=rem.pages_truncated,
        reminders_enabled=reminders_enabled,
        notes=tuple(notes),
        budget_truncated=budget_truncated)
