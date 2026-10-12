# D9 push-sweep operator guide

(2026-10-12, #1063 — pinned to main `0fa65a7`.)

The push lane's paging policy exists and is tested, but the policy does
nothing on its own — the sweep is the cadence that calls it. This is the
operator's runbook for `hosted/push_sweep.py`: what it does, how to run
it, how to read what it reports, how to size it, and what every failure
looks like. The design rationale lives in
[PUSH_SWEEP_SCHEDULER_DESIGN.md](PUSH_SWEEP_SCHEDULER_DESIGN.md) (D66–D78)
and the module layout in [hosted/README.md](../hosted/README.md); this
guide is the "I'm holding the pager" half.

Every behavioral claim below was probed against the real module with a
scratch sqlite store built from the #988-contract DDL in
`hosted/test_push_sweep.py` — the same shape the plane's D1 tables carry.
Probe transcripts are in §10.

## 1. What the sweep is, and what it is not

One call — `hosted.push_sweep.sweep_once(conn, resolve_owner=...)` —
runs **three passes in order: reminders, then digests, then the
cadence-driven watchers** (heartbeat-stale, token-expiry warning).

The sweep only *selects candidates*. It never decides timing (the
policy's gate-1 re-read, D59), never decides dedup (the D57 page-once
index), and never decides budget (the atomic D10 reservation in
`hosted/push_enqueue.py`). That split is load-bearing: the candidate
SELECT is deliberately a *hint* (D68) that over-selects, because the
policy and the boundary are the authority. Over-selecting is safe;
under-selecting is the bug.

One clock reading is taken at sweep start and threaded through every
pass (D73) — a reminder and the digest that carries it can never
disagree about what time it is.

The sweep never sends anything. The paging policy enqueues `queued`
work items; the sender loop (#967, #1094) drains them. If pages aren't
going out, the sweep is at most the second place to look — the sender
loop is the first.

## 2. Running it

`push_sweep.py` is stdlib-only and importable on the plane, the
operator laptop, or anywhere else:

```python
from hosted import push_sweep
summary = push_sweep.sweep_once(conn, resolve_owner=resolve_owner)
```

- `conn` — a sqlite3 connection to the plane's database: the #872
  `approvals` record plus the #988-contract tables (`push_budget_counters`,
  `push_send_results` with the D57 partial unique index, `push_digest_state`).
- `resolve_owner(box_id)` — **required** (D2): a callable returning the
  owner principal from the plane's enrollment registry. Owner identity
  never comes from a box assertion and never from the approvals row.
  A non-callable resolver raises `ValueError` before the first pass.
  A resolver that *returns* a non-string/empty owner, or one containing
  U+0000, raises `ValueError` per candidate — one loud `poisoned` per
  candidate (§9), the pass completes, and no page is ever enqueued with
  a guessed owner (D2, #1095). The sweep fails closed on the owner
  either way; it just doesn't always fail before the first pass.
- `now` — the sweep's single clock reading: an aware or naive datetime
  (naive is assumed UTC) or epoch seconds. Anything else — including
  `True` — raises `ValueError`: a sweep must never run on an untrusted
  clock reading.
- Optional: `page_size` / `max_pages` (capacity, §7), `reminders_enabled`
  (§8), `derive_stale` / `derive_token_warnings` (watcher derivations,
  §6), `record_adapter` (tests).

**Trigger ownership is honest, not assumed:** nothing in-repo runs the
sweep on a schedule. The per-minute `scheduled` cron trigger on the
control-plane Worker (D66) and the deploy-side trigger-registration
check (D72) are tracked in **#1069**, which owns the "without a human
driving it" half of #1063's acceptance. Until #1069 lands, the sweep
runs only when invoked — harness, manual probe, or operator script.
Expect no reminders and no digests from a plane that never calls it.

## 3. Reading the summary

`sweep_once` returns a `SweepSummary` namedtuple:

| Field | What it is |
| --- | --- |
| `reminders`, `digests`, `stale_watchers`, `token_warnings` | disposition → count per pass (`reminders` reports `{"skipped": True}` when the flag is off; a watcher reports `{"skipped": True}` when its derivation is not wired; `digests` has no skip path and always runs) |
| `candidates_seen` | reminder candidates the hint query returned this sweep |
| `pages_truncated` | `True` when the reminder candidate pages hit `max_pages` |
| `reminders_enabled` | echoes the flag |

The disposition vocabulary (verified against the real module):

- `queued` — the policy decided to page. A due reminder produces
  **exactly one** `queued` disposition; a due digest window produces
  exactly one.
- `superseded_terminal` — the reminder pass's summary disposition when
  a pending approval turned out to be terminal only by the clock.
  **This is not the audit row's name.** Gate-1 writes an audit row whose
  `outcome` is `suppressed_terminal` (the D57 vocabulary) with the
  event key = the page key + a `\x00superseded` suffix (the D61
  suffixed-key pattern), and the summary reports `superseded_terminal`.
  The split is deliberate (D61), but it bites operators: if you query
  `push_send_results` for the summary's disposition name you find
  nothing — query `outcome = 'suppressed_terminal'` for the audit rows,
  and read `superseded_terminal` as "the summary's word for it."
- `suppressed_quiet_period` — a heartbeat-stale event fell inside the
  4-hour quiet period (F7; the token-warning watcher has no quiet
  period): no page, no audit row, no budget consumed.
- `duplicate` — the boundary's page-once dedup caught it; no second
  page, no state change.
- `suppressed_budget` — the D10 boundary spent the owner budget; no
  page, budget accounting is the boundary's.
- `no_record` — the approvals row vanished between the hint query and
  gate-1 (a race, not corruption): no page, no audit.
- `reminder_not_due` — gate-1's re-read found the candidate not yet
  due (the hint query over-selects by design): no page, no audit.
- `no_reminder_ttl` — gate-1 found the record's TTL under 300 s: never
  qualified, not a suppression.
- `no_digest_due` — the digest window's `count` was 0 by fire time
  (coalescing moved between the pending scan and the fire): no page.
- `poisoned` — the candidate (or derivation) raised; it was logged
  loudly (§9) and skipped; the pass continued.
- `skipped` — the pass did not run at all: `reminders_enabled=False`
  for reminders; a watcher whose derivation is not wired (the default —
  derivations are plane-side caller logic, §6).

A decided or expired approval is never a candidate, so it produces
zero pages **and** zero audit rows — operator visibility for those is
the approvals record itself, not the sweep output.

## 4. The reminder pass

The hint query selects `status = 'pending' AND decision_seq IS NULL`
plus the D8 timing predicate: the reminder point
(`created_at + TTL/2`) has passed **and** the TTL is at least
`REMINDER_MIN_TTL_SECONDS` (300 s) — approvals with a shorter TTL
never qualify for a reminder (D8). Gate-1 re-reads the record (D59)
and is the timing decision; the hint must never filter harder.

Keyset pagination (`ORDER BY box_id, aid`) keeps each query bounded;
defaults are 100 candidates per page, 100 pages. The D75 anti-join
excludes candidates whose reminder page already exists in
`push_send_results` — precisely those the policy would certainly
`duplicate` — so a truncated sweep's *remainder* is reached next tick
instead of the already-processed rows re-dominating the first pages.
A paged approval that later clock-expires, or corrupts between ticks,
stays a candidate: gate-1 still writes its audit, and the fail-loud
still fires (§9).

The sweep never pre-checks the D10 budget (D70): every due page goes
through `enqueue_page`, because pre-checking would TOCTOU the atomic
reservation and invent a second, racing budget ledger.

## 5. The digest pass

Fires `maybe_enqueue_digest` for every *pending* digest window —
`count > 0 AND enqueued_at IS NULL AND window_start <= hour_bucket(now)` — oldest
first (D76). The current window is the common case; the pending scan
is what heals the hour-boundary strand: coalescing that lands on
window H's row after H's last digest-pass tick fires late with H's
own window key (a fresh page-once key, no dedup conflict) and consumes
the **current** window's owner budget — the page goes out now, so now's
budget is the honest one. A window whose digest already fired
(`enqueued_at` set) is never refired. `enqueued_at` is stamped with
the sweep's single clock reading on accept — the acceptance time, not
the send time (the sender loop zeroes `count` atomically with the
queued-row DELETE later).

The digest pass runs after reminders in the same sweep (D67): a
reminder that coalesced into the digest this sweep is carried by the
digest in the same sweep — the only ordering that cannot strand
counts.

## 6. The watcher pass

`derive_stale(conn, moment)` and `derive_token_warnings(conn, moment)`
are **plane-side caller logic** — missed-heartbeat counting per the
#864 cadence, the boxes-row read with the 2h lead and the
no-rotation-since-last-window check. The sweep owns the cadence, not
the derivation; a derivation that is `None` means the watcher is not
wired, and the pass reports `{"skipped": True}` — it is never guessed.

`stale_epoch` is the caller's derived staleness identity — an opaque
non-empty string. Paging is once per epoch (the boundary's dedup),
and new epochs for the same box are suppressed for 4 hours after the
last stale page (`suppressed_quiet_period`, F7) — no page, no row, no
budget. A derivation that raises stops *only its own watcher* (one
loud `poisoned`, §9); the other watcher still runs.

## 7. Capacity sizing

`page_size * max_pages` must exceed peak due-reminders per minute —
verified defaults are 100 × 100. The cap is a **capacity assumption,
not a correctness bound**: truncation is self-healing (D75), so an
undersized cap degrades to "remainder next tick," not lost pages.
Repeated `pages_truncated = True` on the summary is the operator
alert — no alert sink is wired in-repo, so the deployment that drives
the sweep (#1069) must watch the summary. When raising the cap, raise
`max_pages` before `page_size`: more pages keeps each query bounded;
a larger page makes each query heavier.

## 8. The DO-alarm retirement

When #958's per-approval Durable Object alarms land, the same change
**must retire the reminder pass** (delete it or gate it) — the
`reminders_enabled` flag is the in-repo expression of that plane-side
setting (default `True`). Two reminder producers double-pages; the
digest pass is unaffected by the retirement. This is the one flag an
operator sets by hand during the cutover.

## 9. Failure catalog

- **Poisoned candidate.** Any `Exception` from a candidate's body is
  counted `poisoned` on its pass's summary map, logged loudly with its
  identity, and skipped — the pass continues. The poison row stays a
  candidate on the next tick, so the fail-loud is preserved: loud
  every tick, never silently skipped, and never starving the rest of
  the pass. Verified shape of the loud line:
  `[push_sweep] reminders: poisoned candidate box_id='bad' aid='a1':
  ValueError("approvals created_at for ('bad', 'a1') must be an epoch
  int, not 'not-an-int'") — pass continues`.
- **Corrupt record.** A record whose timing can't be trusted (non-epoch
  `created_at`/`expires_at`, non-enum `status`) raises `ValueError`
  from the adapter — which lands in the per-candidate isolation above:
  one loud `poisoned` per tick. It is never silently skipped and never
  aborts the pass.
- **Derivation failure.** A watcher derivation that raises at call
  time, or mid-iteration, is counted once as `poisoned` and logged
  loudly; *that watcher* stops, the other still runs.
- **Infrastructure failure.** The candidate SELECT itself, the
  pending-window SELECT, or a missing table are **not** isolated —
  they abort the pass loudly (no swallow). Data corruption gets a
  loud skip; broken plumbing gets a loud abort.
- **Operator signals still abort.** Only `Exception` is caught:
  `BaseException` (`KeyboardInterrupt`, `SystemExit`) propagates and
  stops the whole sweep — those are operator signals, not data.
- **The loud channel is stderr**, prefixed `[push_sweep]`, flushed,
  and the writer never raises — a broken stderr cannot kill the pass
  it is reporting on. On the plane this is the surface #1069's
  scheduled handler already exposes; in a manual run it is your
  terminal.
- **Bad clock / bad resolver.** A non-datetime/non-epoch `now` or a
  non-callable `resolve_owner` raises `ValueError` before the first
  pass. A missing/empty/NUL owner from the resolver is a per-candidate
  loud `poisoned` — fail-closed on the owner (D2: no page is ever
  enqueued with a guessed owner) — and the pass completes. The sweep
  would rather not run than run on an untrusted clock or page to a
  guessed owner.

## 10. Verification probes

Against a scratch copy of the plane database (never the live one —
these INSERT test rows):

```python
import sqlite3
from hosted import push_sweep as ps
c = sqlite3.connect("scratch.db")          # schema per test_push_sweep.py DDL
s = ps.sweep_once(c, resolve_owner=lambda box_id: "owner-1")
print(s)  # quiet sweep: empty maps, watchers {"skipped": True}
```

- **Due reminder pages once:** insert a `pending` approval with
  `created_at = T0, expires_at = T0+600`, sweep at `T0+400` →
  `reminders == {"queued": 1}`, `candidates_seen == 1`.
- **Short TTL never qualifies:** same at `expires_at = T0+200` →
  empty map, `candidates_seen == 0`.
- **Decided/expired never candidates:** a decided approval →
  empty map and zero new rows in `push_send_results`.
- **Terminal-by-clock audits once:** a `pending` approval swept after
  `expires_at` → summary `{"superseded_terminal": 1}`, one audit row
  with `outcome = 'suppressed_terminal'`, and a second sweep adds no
  second row (idempotent).
- **D75 self-healing:** insert the reminder page row for the exact
  page key, sweep again → the candidate is anti-joined out
  (`candidates_seen == 0`, no duplicate page).
- **Truncation:** `page_size=1, max_pages=1` with three due
  candidates → `pages_truncated is True`, `candidates_seen == 1`.
- **Digest late fire:** a pending window row (`count = 2`,
  `enqueued_at IS NULL`) → `digests == {"queued": 1}` and
  `enqueued_at` stamped with the sweep's `now`.
- **Watcher wiring:** `derive_stale` yielding `("b1", "epoch-9")` →
  `stale_watchers == {"queued": 1}`; a second sweep with a new epoch →
  `stale_watchers == {"suppressed_quiet_period": 1}` (the 4h quiet period).
- **Isolation:** a corrupt `created_at` beside a good candidate →
  `{"poisoned": 1, "queued": 1}` and one loud stderr line; a
  derivation raising at call time → that watcher `{"poisoned": 1}`,
  the other watcher still runs.

The repo's own suite is `python3 -m pytest hosted/test_push_sweep.py`
(29 tests, neutering-verified non-vacuous) — run it after any change
to the sweep or its tables.

## 11. Known non-goals

The sweep does not own: the per-minute trigger (#1069), the sender
loop's claim/fanout/retry/schedule (#1094, the #967 remainder),
digest *content* adjudication (#1064), push subscriptions (#968),
retention GC (#1058), or the phone-home liveness signal (the #864
heartbeat stays the only liveness signal — the sweep never emits one).
What the sweep selects, the policy and the boundary decide; what the
boundary enqueues, the sender loop delivers. Each layer's runbook is
its own doc.

## 12. Doc-hygiene note

While writing this guide, one `sweep_once` docstring line called the
D61 row a "`superseded_terminal` audit row." The audit row's `outcome`
is `suppressed_terminal` (the D57 vocabulary); `superseded_terminal`
is the summary's disposition word for it. The line is corrected in
this turn — comment-only, no behavior change; the suite re-runs
green. If you are reconciling old notes: the module's older docstring
("writes exactly one idempotent `suppressed_terminal` audit row") was
the accurate one.
