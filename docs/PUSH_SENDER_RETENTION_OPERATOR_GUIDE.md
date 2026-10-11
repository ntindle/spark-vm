# Push-sender retention GC — operator guide

The hosted plane's push-sender tables accumulate rows forever: every page
filing writes budget buckets, digest state, and send-result audit rows, and
none of the lane's normal flows ever deletes them. The 90-day retention
sweeper (`hosted/push_gc.py`, shipped as #1058 / PR #1300, retention-shape
contract pinned in #1301) is the single mechanism that bounds them. This
guide is the operator's contract for that sweeper — what it deletes, what
it will never touch, how the 90-day bound is actually enforced, and what
the failure modes look like from the ops console.

Pinned to main `25027fc` (2026-10-11). This guide operationalizes the #988
table shapes
([docs/PUSH_SENDER_SCHEMA_CONTRACT.md](PUSH_SENDER_SCHEMA_CONTRACT.md)
§§1.2–1.4 — §4's GC bullet describes the sweep's scope, not its shape
contract) and the retention-shape contract pinned in
`hosted/push_gc.py`'s module docstring by #1301: the lexicographic-`at`
comparison and the `push_enqueue.utc_iso` single-render pin.

## The one thing to internalize: retention is enforced by a sweep, not by the schema

There is no TTL column, no expiring-row policy, no one-shot migration. The
tables refill every hour, so the 90-day bound is enforced by a recurring
sweep that deletes old rows (D90). Two consequences follow:

1. **Retention only works if the sweep runs.** The sweeper itself is in
   the repo, but the cron trigger and the manual ops trigger live in the
   plane workspace — the operator owns them (tracked on #1298, still open
   as of this writing). Until the trigger lands, no production retention
   is happening: the tables are growing unbounded and nobody is trimming
   them. The guide assumes the trigger exists; §"Trigger ownership" below
   says exactly whose it is.
2. **A missed sweep is benign.** The predicates are time-based and the
   sweep is idempotent: a second run deletes nothing new, and skipping a
   day only delays deletion, never corrupts anything. Retention degrades
   by delay, not by failure — the failure modes that matter are the ones
   that stop the sweep silently (§"Failure catalog").

## What the sweep deletes (and what it never touches)

Three of the four push tables are swept; the fourth is deliberately
excluded. Each sweep runs the deletes in table order, one table at a
time, committed per batch:

| Table | Predicate (D91) | Deletes |
| --- | --- | --- |
| `push_budget_counters` | `window_start < <hour-cutoff>` | Budget hour-buckets older than 90 days. `window_start` is the hour bucket (`YYYY-MM-DDTHH` UTC). |
| `push_digest_state` | `window_start < <hour-cutoff>` | Digest rows older than 90 days. |
| `push_send_results` | `at < <iso-cutoff> AND outcome != 'queued'` | Send-result audit rows older than 90 days, **except** outbox work items. |

The comparison is strictly `<` cutoff: a row exactly at the 90-day
boundary stays. `now` is the sweep's clock (UTC; naive datetimes are read
as UTC, the same convention as the enqueue path).

### Never touched, by design

- **`'queued'` outbox rows are immortal under the GC (D92).** A `queued`
  outcome is a live work item: it holds a D10 budget reservation and a
  page the owner never got. Deleting it would silently drop a page —
  the lane's "never a lost page" posture (D56f). An audit row for a
  91-day-old *completed* page may go while its outbox row, had it still
  existed, would stay; that asymmetry is the D81 follow-up's to resolve
  (see §"Known non-goals").
- **`push_subscriptions` is not swept at all (D93).** Unsubscribe deletes
  the row outright, so the only accumulating rows are `dead_410`
  tombstones — bounded by device churn (owner-actioned), not by page
  volume, which is what makes the other three tables unbounded. The
  tombstone's whole purpose is the dashboard's "died vs never subscribed"
  distinction and #968's re-subscribe prompt; deleting it would race the
  dashboard, and a re-subscribe is a fresh row with fresh key material
  anyway.

## The retention-shape contract (the part an operator must defend)

The `at < cutoff` comparison on `push_send_results` is **lexicographic
TEXT**, so it is chronological only while every writer of the `at`
column emits the same string shape — `moment.astimezone(timezone.utc).isoformat()`
(`+00:00`-suffixed), single-sourced through `push_enqueue.utc_iso`.
#1301 pinned this after a sweep review caught the dependency living in
one module's docstring while three other modules' writers sustained it.

Why the operator cares: **a new writer that bypasses `utc_iso` with a
different shape (naive ISO, `Z` suffix, epoch) silently corrupts retention
in either direction** — premature deletion of the audit trail (which also
re-opens the §"Replay after retention" window early), or retention
silently stopping and unbounded D1 growth. Both failure modes look like
nothing from the sweep's log line: the sweep ran, the counts were
honest, the predicate just stopped matching reality.

Defenses, in order:

1. New `at` writers must render through `push_enqueue.utc_iso` — no
   exceptions, no "equivalent" formats.
2. `test_utc_iso_byte_shape` and `test_gc_writer_at_shape_matches_cutoff`
   enforce it in CI; both are neuter-verified non-vacuous (each fails
   when its guard is reverted).
3. The operator's check (§"Verifying the sweep works") catches the
   drift that slips past 1 and 2: rows that never age out.

## Replay after retention (accepted, not a bug)

Deleting `suppressed_budget` / `suppressed_terminal` rows after 90 days
re-opens the D53 dedup window for very old replays: a filing replayed
after its rows aged out can re-page (D94). This is accepted — retention
is a bounded-memory dedup, and the #1013 precedent has the same
property. The D57 index only ever covered the live window anyway. If a
page arrives for a filing older than the retention window, that is the
system working as designed, not a sweep malfunction.

## Trigger ownership

The in-repo build slice is only the sweeper function
(`gc_push_tables`): portable, stdlib + DB-API, no Worker secret, no data
key, no box token ever in scope. The two halves the plane workspace owns
(the #1298 deploy half, open):

- the **scheduled trigger** — the plane worker's scheduled handler
  calling the sweeper (the #1013 precedent: cron at a sane cadence —
  daily is plenty, the bound is 90 days and the sweep is idempotent);
- the **manual ops trigger** — an operator-invoked sweep on the same
  pattern, for verification runs and catch-up after trigger outages.

Until #1298 ships, the operator's honest mental model is "no retention";
the §"Verifying" probes below will show the tables growing.

## The sweep's own contract

- `gc_push_tables(conn, *, now=None, retention_days=90, batch_size=1000, log=None)`:
  deletes in batches of 1000 (D1 write limits), one commit per batch,
  and returns `{table: deleted_count}`. It also emits one log line per
  sweep: `push_gc: retention_days=90 deleted={'push_budget_counters': N, ...} total=M`.
  That line is the sweep's ops presence — a sweep that ran but found
  nothing still emits it with zeros.
- Batch size and retention window are positive-int validated **before**
  any DELETE executes: a misconfigured trigger fails loud with
  `ValueError`, not with a partial or unbounded delete.
- Termination and the returned counts are derived from row existence
  (before/after `COUNT(*)`), never from `cursor.rowcount` (D95) — a D1
  wrapper reporting `-1` for DELETEs can neither spin the loop nor
  corrupt the counts. The operator's own ad-hoc tooling must not use
  rowcount either; use the returned dict.
- Concurrent inserts cannot corrupt a sweep: the predicates are
  time-based, so a fresh insert never matches an old-row predicate. A
  sweep may run while the sender loop is inserting — the counts stay
  honest.

## Verifying the sweep works

The honest probe is row existence, not the log line (the log line tells
you the sweep ran; the probe tells you retention holds). After a sweep,
with the cutoff in hand — rendered exactly the way the sweeper renders
it (from the repo root):

```bash
# the push_send_results.at cutoff (instant, +00:00-suffixed ISO)
python3 -c "from datetime import datetime, timedelta, timezone; from hosted import push_enqueue; print(push_enqueue.utc_iso(datetime.now(timezone.utc) - timedelta(days=90)))"
# the hour-bucket cutoff for push_budget_counters / push_digest_state
python3 -c "from datetime import datetime, timedelta, timezone; from hosted import push_enqueue; print(push_enqueue.hour_bucket(datetime.now(timezone.utc) - timedelta(days=90)))"
```

run:

- `SELECT COUNT(*) FROM push_send_results WHERE at < <cutoff> AND outcome != 'queued'` → 0
- `SELECT COUNT(*) FROM push_budget_counters WHERE window_start < <hour-cutoff>` → 0
- `SELECT COUNT(*) FROM push_digest_state WHERE window_start < <hour-cutoff>` → 0

A non-zero count after a clean sweep is either the retention-shape drift
(§"Retention-shape contract" — rows whose `at` shape never matches the
cutoff) or a sweep that did not run (check for the log line). The two
have different fixes; the probe distinguishes them.

Two trends worth watching on the ops console:

- **Sweep deleted counts trending up** across runs means page volume is
  growing (normal) — or the trigger was down for a while and the sweep
  is catching up (also normal; idempotent).
- **`queued` row count** (§"Known non-goals") is the unbounded residue
  retention does not touch. Watch it; a steady climb is a sender-loop
  problem, not a retention problem.

## Known non-goals (not this sweeper's job)

- **Bounding `queued` outbox rows** is the D81 follow-up (bound or
  expire parked pages) — the sender loop's and #968's problem. The GC
  predicate's `outcome != 'queued'` is the deliberate seam.
- **Bounding `dead_410` tombstones** — bounded by device churn by
  design (D93). If device churn ever makes the table's growth a cost
  problem, that is a new decision, not a sweep bug.
- **The D94 replay window** — accepted by design, not a defect.
- **Tenant-visible retention policy** — the tenant's update-history
  surface is
  [docs/UPDATE_AUDIT_RETENTION_AND_ACCESS.md](UPDATE_AUDIT_RETENTION_AND_ACCESS.md);
  this guide is the plane operator's machinery underneath it. The two
  windows are different systems; do not conflate them.

## Failure catalog

| Symptom | Cause | Operator response |
| --- | --- | --- |
| Tables grow unbounded; sweep log line present with zeros | Retention-shape drift: a new `at` writer bypassed `utc_iso`, so old rows never match the cutoff | Find the non-conforming writer, route it through `utc_iso`, verify with the §"Verifying" probes |
| Audit rows vanish earlier than 90 days | Shape drift in the other direction (writer emits shapes that sort older than they are) | Same as above; also re-opens the D94 replay window early — treat as a lane incident, not just a data issue |
| No sweep log line for a full trigger cycle | Trigger down (plane-workspace cron, #1298) or the scheduled handler never called the sweeper | Check the trigger half first; the sweeper failing would log loudly (validation raises before any DELETE) |
| Sweep emits counts but rows remain | `conn` held an open transaction across the call — the module commits per batch inside itself and requires no open transaction from the caller | Fix the caller; the sweeper's own contract is per-batch commit |
| `queued` rows accumulate | By design (D92) — the sender loop / D81 follow-up owns them | Do not hand-delete them; that would silently drop pages. Watch the trend, file/raise on the sender loop |
| `dead_410` tombstones accumulate | By design (D93) — bounded by device churn | Expected; only a cost problem if churn explodes |
| A page fires for a months-old filing | D94 replay-after-retention — accepted | Working as designed |

One rule for the manual trigger: **deletions go through the sweeper, not
through hand SQL.** The predicate set is the single source of truth for
what may be deleted; a hand `DELETE` bypasses the immortality invariant
(D92), the tombstone policy (D93), and the audit-trail shape contract —
and nothing enforces those from outside the module.
