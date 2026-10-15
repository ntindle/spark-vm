# Scheduler-home convergence, 2026-10-12: the D9 sweep's "without a human"

**Status: analysis, not a commitment.** Code-state claims below were
verified against the repo tree at main `c6cc64d1` (2026-10-12 ~16:4x CDT).
Issue/PR numbers are GitHub references as of 2026-10-12 (not
code-verifiable from the tree). Honesty rules apply (`docs/POSITIONING.md`):
this describes current state and work to do, not promises. Nothing here
deploys, schedules, or sends a push.

**Non-overlap map (what this doc is not):**
- `docs/PUSH_LANE_CONVERGENCE_2026-10-10.md` — the push-lane pin (2026-10-10,
  re-pinned 2026-10-12 to `e2747fe`); this doc narrows to the scheduler
  home (the D66–D78 slice) at the newer main `c6cc64d1`.
- `docs/PUSH_SWEEP_SCHEDULER_DESIGN.md` — the D66–D78 design record; the
  build, not the re-verification.
- `docs/D9_PUSH_SWEEP_OPERATOR_GUIDE.md` — the pager-half operator guide;
  its §6 documents the watcher derivations' plane-side ownership.
- `deploy/plane-cron/CRON_TRIGGER_CONTRACT.md` — the repo's deploy-contract
  half of #1069/#1298 (PR #1385); this doc pins what that contract leaves
  open.

## 1. The vision (D9, #1063/#1069)

The D9 sweep exists so the push lane's paging policy fires without a human
driving it: one per-minute sweep reads the plane's D1 database, runs the
three passes in order — reminders, then digests, then the cadence-driven
watchers (D67) — and lets the policy, the gate-1 re-read (D59/D12), and the
enqueue boundary (D50–D57) make every timing, dedup, and budget decision.
#1063's acceptance criterion is the gate: one observed live cron tick
enqueues a due reminder with no human driving it. #1069 exists to kill the
silently-unwired failure mode — the handler deployed, the trigger never
registered, nothing ever ticks — which a handler-runs check cannot catch.
D69 binds the whole sweep to the 1-minute cadence ("bounded work per
sweep; overlap is safe, not prevented"); when #958's per-approval Durable
Object alarms land, the same change retires the sweep's reminder pass
(D71) — the digest pass is unaffected.

## 2. Vision vs state (pinned 2026-10-12, main `c6cc64d1`)

| Leg | State |
|---|---|
| Sweep logic (in-repo) | SHIPPED: `hosted/push_sweep.py` (#1095/#1104) — three passes, `sweep_once` returning `SweepSummary`; D76 pending-window scan + `enqueued_at` stamping and the D77 suffixed suppression-audit key (#1080); D78 per-candidate error isolation (#1095). |
| Operator guide | SHIPPED: `docs/D9_PUSH_SWEEP_OPERATOR_GUIDE.md` (PR #1368) — §§4–6 the three passes' verified behaviors, §7 capacity sizing, the #1069 trigger-ownership honest model, the DO-alarm retirement flag (§8), the failure catalog (§9), verification probes (§10). |
| Deploy contract + proof | SHIPPED (this pin's delta): `deploy/plane-cron/` (PR #1385) — `CRON_TRIGGER_CONTRACT.md` (the exact `wrangler.toml` `[triggers]` declaration, the scheduled-handler dispatch contract, the manual ops triggers, the post-deploy verification procedure), `verify_plane_cron.py` (stdlib-only, Workers API read of registered cron triggers, exit 0/1/2 contract, fixture mode labeled as not-live-proof), `test_verify_plane_cron.py` (27 tests). The contract's §5 is the repo-side half of #1063's acceptance: the verifier asserts registration, and the staging/live-tick observation is the operator's to record. |
| Retention GC (in-repo) | SHIPPED: `hosted/push_gc.py` (PR #1300, #1058 closed) — 90-day retention, LIMIT-batched idempotent rounds, D91–D95; `queued` outbox rows and `push_subscriptions` excluded (D92/D93). |
| Retention GC (deploy half) | OPEN (#1298, p3): the contract now pins the daily `30 3 * * *` trigger declaration and the `POST /v1/ops/push/gc` manual-trigger shape (contract §§1–4), but the plane-workspace wiring, the staging probe-row verification, and one observed daily cron tick are all still the operator's to do. The contract is the repo's last word on this half; #1298 stays open for the wiring + observation. |
| Cron trigger wiring + live tick | OPEN (#1069, p2): same shape — the contract pins the per-minute `* * * * *` declaration, the dispatch order (`sweep_once` then the sender-loop drain, per #1094's pairing), and the verification procedure; the `wrangler.toml` declaration, the `scheduled`-handler dispatch, the manual `POST /v1/ops/push/sweep`, and the one observed live tick enqueuing a due reminder are operator-side (the plane workspace is not in this repo) and still to do. #1063 stays open until that tick is observed. |
| Digest-pass boundedness | GAP — VERIFIED (#1383, p3): see §3 F-SH-1. |
| Watcher derivations | GAP — NEW (filed #1386, p3): see §3 F-SH-2. |

## 3. Verified findings

**F-SH-1 — #1383's claim is byte-accurate, and the D69 promise is stated
sweep-wide.** `hosted/push_sweep.py::sweep_digests` (main `c6cc64d1`)
fetches the full pending-window set with no `LIMIT` — the issue's code
quote matches the tree exactly — while `sweep_reminders` pages with
`LIMIT ?` and reports `pages_truncated` on the `SweepSummary`. The design
doc states D69 as a sweep-level invariant ("Bounded work per sweep; ...
the candidate query pages (`LIMIT`, ordered by `(box_id, aid)`) instead
of scanning the whole table"; "a sweep must normally finish inside the
1-minute cadence"), and the module's own D69 comment ("bounded work per
sweep", `push_sweep.py` ~L97) reads the same way — but only the reminders
pass implements it. The accumulation mechanism is real: over-budget ticks
leave `enqueued_at` NULL by design (retry later), so one row per
(owner, hour) piles up while the lane is suppressed, and each tick
re-reads and re-attempts all of them. The watchers pass is not the same
shape: the D74-specified derivations are fleet-bounded by construction —
per-box reads against the fleet registry — and accumulate no pending
state; the sweep itself cannot bound an opaque caller-supplied generator,
so fleet-boundedness there is a caller-side obligation, not a sweep
property. Pointer comment on #1383 records the verification. The D69
overstatement lives in three renderings the #1383 fix must reconcile:
`docs/PUSH_SWEEP_SCHEDULER_DESIGN.md:62` (the design-doc D69 text —
amended either way: bound the digest pass, or narrow D69's stated
scope), the module comment (`hosted/push_sweep.py` ~L97), and the
just-merged deploy contract (`deploy/plane-cron/CRON_TRIGGER_CONTRACT.md`
§1: "the sweep is bounded per tick (D69)" — now known-false for the
digest pass); `scripts/test_push_lane_decision_numbers.py` (~L173-176)
pins D69's normalized phrases, so any rewording must update that test or
CI breaks. D71's retirement removes the only pass that implements D69's
paging — the #1383 digest bound is what keeps the sweep-wide invariant
meaningful after retirement. No new issue filed — #1383 already owns the
build.

**F-SH-2 — the watcher derivations have no owning issue.** D74 places the
stale-epoch and token-warning derivations plane-side ("the sweep's job is
the cadence, not the derivation"), the operator guide documents them as
caller-injected (§6), and the sweep reports `{"skipped": True}` when they
are absent — all by design. But neither #1069's body nor the deploy
contract's dispatch step (contract §2: `sweep_once(conn,
resolve_owner=resolve_owner)`) names who builds them, so the D74 watchers
can never fire on a contract-conformant deploy: the contract's own
dispatch example leaves them unwired. Filed as #1386 (p3): the stale-epoch
derivation (missed-heartbeat counting per the #864 1/min cadence, armed
by `queued|accepted` rows per the D74 design note) and the token-warning
derivation (2h lead + the F6 no-rotation-since-last-window check, per the
`sweep_watchers` docstring). Not a correctness gap in the in-repo code —
the fail-silent-by-design "skipped" is honest — but the lane's third pass
has no build owner, and without one the heartbeat-stale and
token-expiry-warning pages never fire.

## 4. What is still unbuilt (the honest list)

1. **The observed live tick** (#1069, p2; gates #1063): the `wrangler.toml`
   declaration, the `scheduled`-handler dispatch (including the sender-loop
   drain pairing and the watcher derivations from F-SH-2), the manual ops
   triggers, and one observed per-minute tick enqueuing a due reminder with
   no human driving it. Operator-side; the contract + verifier are the
   repo's complete contribution.
2. **The GC deploy half** (#1298, p3): plane-workspace cron + ops-trigger
   wiring, staging probe-row verification, one observed daily tick.
   Operator-side.
3. **Digest-pass boundedness** (#1383, p3): cap the pending-window scan
   (oldest-first, preserving D76's self-healing strand), report truncation
   on the sweep summary (the digest analog of `pages_truncated`), keep the
   full `hosted/test_push_sweep.py` suite green; correct the D69 module
   comment's scope as part of the fix.
4. **Watcher derivations** (#1386, p3): the two plane-side derivation
   functions, wired into the dispatch the contract's §2 pins; each
   derivation completing within the tick budget against a fleet-bounded
   read is an acceptance constraint of #1386.
5. **Adjacent, unchanged:** subscriptions (#968, p2, blocked on the
   operator data key), the sender-loop claim mechanism (#1094, p2),
   digest content adjudication (#1064, p3), #967's #428-§4 acceptance.

## 5. What this does not claim

- **No hosted sweep ticks anywhere.** The sweep, the sender loop, and the
  GC are in-repo Python with a contract and a verifier; nothing schedules
  them. The deployed tenant plane has no push code.
- This doc files one new issue (F-SH-2) and changes no code. #1383 is
  verified, not fixed, here.
- Issue/PR numbers are GitHub references as of 2026-10-12.
