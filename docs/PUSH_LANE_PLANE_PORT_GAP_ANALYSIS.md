# Push-lane plane-port gap analysis

Pinned to main `0cff7ef9` (2026-10-16) and the deployed `sparkvm-control`
worker fetched live 2026-10-16 (250,545 bytes; its only `scheduled`
handler is the daily #1013 phone-home GC). The live D1 was queried the
same day: **zero `push_*` tables**.

## 1. Vision vs state

The push lane's in-repo build is done: crypto (#967 S1), payload scrub
(#970), enqueue boundary (#990), event mapping (#1062), the D9 sweep
(#1063), the sender loop (#1094), the schema contract (#988/#1061), the
retention GC (#1058), and the cron-trigger contract (#1385). The vision
is that all of it *runs on the plane*: the D9 sweep ticks per-minute
(D66), the sender loop drains the outbox (D56), the GC sweeps retention
daily, digests assemble and deliver (#1064), subscriptions are managed
(#968).

The state: **the lane is 100% in-repo, 0% on-plane.** `hosted/` holds
4,660 lines of push-lane code, every DB-touching module written against
the synchronous DB-API (`conn.execute(...)`). The deployed worker has
no push code, the live D1 has no push tables, and exactly one cron
trigger is registered (`17 3 * * *`, the #1013 GC). #1069 (D9 sweep
trigger) and #1298 (GC trigger) are open with no build slices; #967's
sender-loop remainder and #1064 have no plane-port tracker at all.

This analysis exists because the port is not the copy the existing
docs imply. §2 names the gaps; §3 pins the port decisions; §4 files
the build slices (slot-sized; the sender-loop S3 builds as three
sequenced slices under its epic).

## 2. Findings

- **F-PP-1 — the port surface is 4,660 in-repo lines, zero on-plane.**
  `hosted/push_sweep.py` (836), `push_events.py` (562),
  `push_enqueue.py` (526), `push_payload.py` (122),
  `push_crypto.py` (561), `push_send_loop.py` (1286),
  `push_sender.py` (571), `push_gc.py` (196). Cross-imports form a
  shallow tree (`push_send_loop` → `push_enqueue`/`push_payload`/
  `push_sender`; `push_sweep` → `push_enqueue`/`push_events`;
  `push_events` → `push_enqueue`; `push_gc` → `push_enqueue`;
  `push_sender` → `push_crypto`); every module is stdlib-only. The
  modules split into two port classes: pure-compute (`push_crypto`,
  `push_payload` — 683 lines, no DB, no I/O) and DB-touching (the
  other 3,977 lines, all sync `conn.execute`). The `push_send_loop`
  port must therefore resolve four sibling imports to ported/inlined
  counterparts — the async rewrite's dependency surface is the whole
  subtree, not one module.
- **F-PP-2 — the sync/async seam: the port is a rewrite, not a copy.**
  The worker's D1 access is async-only
  (`await db.prepare(...).bind(...).run()` via the `_D1` wrapper;
  workers-py exposes no synchronous D1, and the event loop cannot be
  blocked from inside a `scheduled` handler). Every DB-touching module
  calls the synchronous DB-API throughout. No adapter bridges
  sync→async here — the "plane-side seams injected" phrasing in
  `deploy/plane-cron/CRON_TRIGGER_CONTRACT.md` §2 does not name this,
  and a literal reading (call `sweep_once(conn)` with the worker's
  `_D1`) fails on the first `conn.execute`. The contract's §2 needs
  the async amendment: the handler calls async ports, not the in-repo
  entry points.
- **F-PP-3 — the sender transport has no worker equivalent.**
  `push_sender.py` drives RFC 8030 POSTs over `http.client` + `socket`
  + `ssl`. The worker's outbound HTTPS is `pyodide.http.pyfetch`
  (identified from the deployed worker source fetched for this
  analysis — the repo itself never names `pyfetch`; the repo's #1225
  documents only the fail-closed worker-side JWKS *fetch* pattern).
  The #989 transport policy (findings 1–7) ports as policy; the I/O
  layer must be worker-native. The sender is the hardest port: async
  DB *and* a transport adapter.
- **F-PP-4 — the ed25519 precedent gives the port its anti-drift
  pattern.** The deployed worker (fetched live for this analysis)
  inlines the repo's `pairing/ed25519.py` under the marker
  `# --- BEGIN ed25519 (#844 pairing-code enrollment) ---`, with the
  comment: "the Worker deploys as a single file, so the module lives
  here too. The two copies MUST stay byte-identical:
  `pairing/test_ed25519.py` asserts this". The test exists —
  `test_worker_inline_copy_byte_identical` in
  `pairing/test_ed25519.py` extracts the inlined block and asserts
  equality with the repo module — but it is locally-gated: it skips
  when the deployment workspace is not reachable, and it does not run
  in CI. So the *pattern* (inline + a repo test asserting
  byte-identity) is established, but each port must *write* its own
  test; no enforcement is inherited. The pattern applies verbatim to
  the pure-compute modules (`push_crypto`, `push_payload`). It does
  *not* apply to the DB-touching modules: their worker ports are
  async rewrites by F-PP-2, so byte-identity is impossible; their
  anti-drift is conformance scenarios (§3, D-PP-2).
- **F-PP-5 — trigger tooling exists and works; live is pre-port.**
  `set_cron_schedule.py` (plane workspace) PUTs/GETs the schedules
  subresource, independent of deploys. Live today: only `17 3 * * *`.
  `deploy/plane-cron/verify_plane_cron.py` expects
  `{"* * * * *", "30 3 * * *"}` — it fails against live today, which
  is correct: the verifier is a pre-port signal, not a broken test.
- **F-PP-6 — the `scheduled` handler doesn't multiplex yet.**
  Today's handler runs the daily GC unconditionally; it never reads
  `controller.cron`. The per-minute/daily multiplex is new code, and
  the #1013 GC keeps its existing trigger and behavior inside the
  multiplex (no cadence change for the journal GC).
- **F-PP-7 — the sender's run home is already decided.**
  `docs/PUSH_SENDER_CLAIM_DESIGN.md` (#1094, D56a) pins the drain
  inside a `PushSenderDO` Durable Object singleton (stub
  `env.PUSH_SENDER_DO.idFromName("push-sender")`, C1 — the input gate
  held closed across the whole drain body, the justified exception to
  the gate-holding guidance), driven by the per-minute `scheduled`
  handler which runs the D9 sweep first and then POSTs `{now}` to the
  stub's `/drain` (C2), with C3's N/T per-drain bound. The S3 port
  therefore builds a new DO class + namespace binding (+ the
  `new_sqlite_classes` migration entry the free plan requires for a
  new class — the #958 S4a deploy precedent), not an inline drain.
  #968's subscription endpoints, by contrast, are ordinary fetch
  routes — the worker's native shape, no port problem; they stay on
  #968/#1392. Digest assembly (#1064) shares S2's port shape once S2
  lands; it keeps its own tracker.

## 3. Decisions

- **D-PP-1 — port by module class.** Pure-compute modules inline
  byte-identical per the ed25519 precedent (F-PP-4), with the same
  repo-test-asserts-byte-identity discipline. DB-touching modules are
  async rewrites against the worker's `_D1` (F-PP-2); the in-repo sync
  modules stay the harness and test truth.
- **D-PP-2 — conformance, not identity, for the rewrites — as a
  standing mechanism, not a one-time acceptance.** Each async port
  slice vendors its scenario fixtures into the plane workspace *and*
  checks the port's recorded fixture outputs into this repo next to
  the sync module. A repo-side test replays the fixtures against the
  in-repo sync module on every CI run and diffs the outputs against
  the checked-in port outputs, failing on divergence. The in-repo
  sync modules stay the evolving harness truth (D-PP-1); the checked-
  in outputs are the tripwire that forces the port to follow. A port
  that passes the fixtures at ship time is conformant; the CI test is
  what keeps it conformant.
- **D-PP-3 — one `scheduled` handler, branched on
  `controller.cron`.** Per-minute → the D9 sweep passes, then the C2
  handoff: POST `{now}` to the `PushSenderDO` stub's `/drain` and
  await the summary (the sweep enqueues, the DO drains — a tick that
  enqueues without draining strands pages in the outbox).
  `30 3 * * *` → `gc_push_tables`. `17 3 * * *` → the existing
  phone-home GC, unchanged. Unknown cron values log loud and no-op
  (fail-soft, the #1013 handler's existing discipline). The C2
  handoff's failure mode is C2's fail-safe: if the handler's POST to
  a gate-held `/drain` times out caller-side, the DO continues
  independently and the next tick re-scans — the orphaned tick is
  harmless, never retried into a double-drain.
- **D-PP-4 — schema first.** The four push tables plus the contract's
  indexes (`docs/PUSH_SENDER_SCHEMA_CONTRACT.md` §1/§4) land on the
  live D1 via forward `CREATE TABLE / CREATE INDEX IF NOT EXISTS`
  migration before any worker code references them. Re-run is a
  silent no-op, per the contract's migration convention.
- **D-PP-5 — D72's order is the deploy order.** Handler deploys first,
  then a manual probe (`POST /v1/ops/push/sweep`, the #1013 pattern —
  owner-key only, box token refused), then the trigger registers, then
  `verify_plane_cron.py` proves the registration, then one observed
  live tick against a test approval (rows cleaned up after) is the
  #1063 acceptance. The trigger never registers before the handler
  proves itself.
- **D-PP-6 — the sender's worker transport is `pyfetch`.** The #989
  policy ports; `http.client`+`socket` does not. VAPID private-key
  custody for the live sender stays the standing operator item (the
  VAPID mailbox item in the goal workspace's `NEEDS_USER.md`) — the
  port slice proves the path with
  a test key and names the production key as the operator step.
- **D-PP-7 — the D71 retirement rule rides the port.** The async sweep
  port carries the `reminders_enabled` flag from day one, so the
  future #958 DO-alarm change flips it off without a second port.

## 4. Slices

Filed by this analysis (all `track:hosted-product`):

- **#1565** (p2) — push-lane D1 schema live migration. The four
  tables + indexes from the schema contract §1/§4 as one forward
  migration, applied to the live plane D1, verified (tables + indexes
  present, re-run no-op, existing tables untouched). Unblocks S2–S4.
- **#1566** (p2) — D9 sweep async plane port. The async sweep port
  (reminders + digests + watchers) against `_D1`; the `scheduled`
  multiplex (D-PP-3); `POST /v1/ops/push/sweep`; the #1385 contract
  §2 async amendment — which must name the concrete async port entry
  points (plane-workspace module paths), cite the D-PP-2 fixture set
  as the dispatch truth, and explicitly replace §2's step 2 (direct
  `send_loop(...)` call) with the C2 handoff. D72 verification for
  this slice is the manual probe only (`POST /v1/ops/push/sweep`
  against a test approval); the per-minute trigger registration is
  explicitly NOT this slice's — it is #1571's, gated on the proven
  drain (D-PP-3's stranding rule: a tick that enqueues without
  draining strands pages in the outbox). Closes #1069's port half;
  #1069 closes fully when #1571's live tick lands.
- **#1567** (p2) — sender-loop plane port, tracked as an epic: the
  #1094 claim design executed across three sequenced slices —
  **#1569** (S3a: `PushSenderDO` skeleton + namespace binding +
  `new_sqlite_classes` migration entry + byte-identical inlines of
  `push_crypto.py`/`push_payload.py` with the byte-identity test),
  **#1570** (S3b: async drain body with C1 gate-holding under the C3
  bound + `pyfetch` transport adapter + conformance fixtures),
  **#1571** (S3c: C2 handoff + per-minute trigger registration +
  `verify_plane_cron` proof + observed live tick with test-approval
  cleanup). VAPID production key as the named operator step.
  Advances #967's remainder; the epic closes when all three land.

**Ordering constraint:** #1565 (schema) lands before #1566, #1569,
and #1568. #1566 lands before #1571 — the per-minute trigger
registers only against the proven drain. #1569 → #1570 → #1571 in
sequence. #1568 (GC) is independent of the sweep/sender chain once
the schema lands.
- **#1568** (p3) — push-GC async plane port. Async `gc_push_tables`
  port; `30 3 * * *` trigger; `POST /v1/ops/push/gc`. Closes #1298.

Kept on their existing trackers (pointer comments, no new issues):
#1064 (digest assembly follows S2's port shape), #968/#1392
(subscription endpoints are fetch routes — F-PP-7), #1063 (whose
acceptance S2's live tick satisfies).
