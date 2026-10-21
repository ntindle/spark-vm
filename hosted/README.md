# hosted — the hosted control plane's tenant layer (S1)

`GET /tenant/status`: the machine-readable onboarding status that the tenant
Muse (linked ed25519 key, signed requests) and the signup page (magic-link
session cookie) poll during the first-ten-minutes onboarding arc.

The full contract is `docs/TENANT_STATUS_ENDPOINT.md`. What this component
implements (G3 implementation slice S1):

- the 13-code §2 machine vocabulary, exactly spelled, with the operator-only
  codes (`policy-misfire`, `no-gated-action`) carrying no `human_key`;
- the §2 transition rules 1–8 (no backwards moves; the relay/cert suspension
  latch; the maintenance latch; the rule-7 session-restart carve-outs) as a
  tested event→transition mapping over per-box arc records;
- the JSON tenant-record store, with the `approvals_url` carrier minted once
  at signup stage 2 (write-if-absent + re-read, linearizable across processes
  via an `flock`'d lock — exactly one minter wins a concurrent stage-2 race;
  funnel re-entry is a read path; rotation only via an explicit operator
  event), and the §8 empty-candidate hold (when the leading box is deleted
  pre-`live`, the endpoint holds the last reported code with `detail` noting
  the operator event);
- the endpoint itself: two-sided auth, 401 when the caller's identity can't
  be established, 404 for valid credentials with no servable record (deleted
  or pre-stage-2), `Cache-Control: no-store`, and GET never changes state.

Run the tests: `python3 -m pytest hosted/` from the repo root.
Run the daemon: `python3 -m hosted.tenant_status --store /path/tenants.json`
(signed-request verification is wired by the control plane at deploy time —
the daemon refuses signed requests until then rather than trusting them).

Deliberately stdlib-only, so the module runs unchanged on the self-hosted
box, the hosted control plane, and the operator laptop. The ed25519 verify
primitive is injected (stdlib has no ed25519) — the endpoint never trusts
an unverified signature.

Slice boundaries: S2 wires the H4 driver's `BoxStatus` into the tenant
layer (the `live`-entry AND-combine is the `live_entry_ready` unit); S3
wires the readers (signup page meta-refresh, Muse poller).

## relay_liveness.py — the relay session-liveness journal (R1)

The passive liveness instrument from `docs/RELAY_LIVENESS_DESIGN.md`:
the relay daemon emits one §2 session frame per tenant↔VM SSH session
to a bounded local JSONL journal, and the control plane asks
`relay_session_liveness(vm_id)` → `{session_id, state, last_bytes_at,
hostkey_verified}` where state is `active` (bytes within the last
5 minutes), `idle` (no bytes for over 5 minutes), or `closed` (the
session ended with a §2 cause).

Frames are metadata only — timing and counters, never payload; the
schema validator rejects any non-§2 field. Rotation is the journal's
own contract: the journal plus at most 3 rotated generations are
capped by a byte bound (worst case 4 × (64 MiB + one row)), so total
on-disk footprint is bounded regardless of session volume. The bound
is bytes, not rows — stated plainly so no reader assumes a row count
the code doesn't enforce. The prober identity marker (R2's
discriminator) is enforced at the journal: prober-marked frames are
dropped, never journaled. Unknown boxes return no data — darkness is
insufficient-observability, never an `ok` (a missing journal directory
is darkness too, not an error; only the writer fails loud).

Run the tests: `python3 -m pytest hosted/` from the repo root.
Query smoke test: `python3 hosted/relay_liveness.py --query <vm-id>
[--journal /path/journal.jsonl]`.

## relay_tenant_wiring.py — the operator-driven rule-6 tick (R3)

The relay-liveness tenant wiring never self-drives: one explicit
`--tick` run per tenant drives rule-6 suspensions, the recovery pair,
anchor selection, and stale-reachability resync, and prints the tick
report as JSON (exit 0; exit 1 with the error on stderr — a broken
instrument is loud, never silent). At most one tick per box at a time
(D-RL34-7 — the drive decision documented in the module docstring).
`--tick` is the manual/override path; the auto-cadence drivers are
`relay_auto_driver.py` (drive, S1) and `relay_probe_driver.py`
(probe, S5) — see below.

Drive one tick: `python3 -m hosted.relay_tenant_wiring --store
/path/tenants.json --tick TENANT_ID`.

## relay_probe_driver.py — the probe-cadence driver (S5, #1725)

The probe half of the relay-liveness auto-cadence story
(`docs/RELAY_LIVENESS_AUTO_CADENCE_GAP_ANALYSIS.md`): once scheduled
and given a bundle supplier, it ticks every tenant's live anchor
through `relay_path_state.maybe_probe` on the shared
`RELAY_PROBE_CADENCE_S` cadence, so the wiring driver stops ticking
against permanently stale probe history. **Status: ships unscheduled**
— the scheduled entrypoint + timer (the S1/S3 pattern) and the
bundle-supplier wiring are open follow-up slices; until they land,
the wiring driver's loud "stale probe history" notes remain the
steady state by design, and the probe tick's own LOUD "wire a bundle
supplier" note is the forcing function.

Probe bundles are caller-supplied per probe via a `bundle_fn` seam —
never persisted, never invented by the loop (D-RL2-3); a due tick
with no bundle is noted loud, not failed. The supplier contract:
`bundle_fn(tenant_id, vm_id) -> {"relay_host", "relay_port",
"pinned_fingerprint"} | None`, called after anchor selection on every
due tick; raising fails that tenant's tick loud (never the sweep).
The loop stands down observably when the box's provider reads
`suspended`/`destroyed` or no post-`live` arc exists (D-RL2-2), and
one tenant's broken supplier fails loud without wedging the sweep
(D-AC-3). Each tick writes a probe watermark
(`<store>.relay-probe-watermarks.json`, distinct from the drive
watermark) and a `relay-probe` fleet-journal note — the loop's own
observability, so a dead probe loop reads as probe trouble, not
driver trouble. The watermark sidecar, journal-note, and note-scrub
machinery shared with the S1 auto-driver lives in the public
`hosted/relay_tick_sidecar.py` module (extracted behavior-identical
from `relay_auto_driver.py`).

## push_crypto.py — Web Push content-encoding crypto (RFC 8291), stdlib-only

The design-hypothesis validation for #967 S1 (the plane Web Push sender):
proves the Python plane worker can do in-worker Web Push sending with no
JS interop and no C extensions. Implements ECDH P-256, HKDF-SHA-256,
AES-128-GCM, and RFC 6979 deterministic ECDSA (for VAPID JWTs, RFC 8292)
in pure Python, and pins every step against the RFC 8291 section 5 /
Appendix A worked example in `test_push_crypto.py` (30 tests).

Result: validated — one full send (ephemeral keygen + ECDH + KDF +
AES-GCM + VAPID sign, 200 B payload) costs ~38 ms on the loop's dev VM,
so S1 proceeds in-worker. Read the module docstring before reusing: the
field arithmetic is not constant-time (assessed non-exploitable in the
plane's threat model), peer keys are curve-validated per RFC 8291
section 7, and the VAPID private key must never leave the plane.

## push_payload.py — push payload construction discipline (#970 / GP4)

The plane's push path is a hostile-*box* surface: box-controlled strings
flow into payloads the plane signs and sends to the owner's lock screen.
This module pins the single construction-time rule the future sender's
enqueue boundary applies to every box-controlled payload field —
control-character strip (C0 + C1, so ANSI escapes die) plus an explicit
byte-length bound with ellipsis truncation that never splits a code
point — proven by `test_push_payload.py` (22 tests, neutering-verified
non-vacuous). Payload shape is exactly `{aid, ttl_s, summary}` ("go
look" payloads, decision D4): the builder takes no token, key, or VAPID
argument and returns an immutable mapping, so secrets have no ingress
path at construction. Push-construction
only: the owner-facing decision surface keeps showing the full raw text.

## push_sender.py — Web Push send-path transport (#989 / GP1)

The other half of the GP1 sender: `push_crypto.py` proved the crypto but
deliberately has no HTTP layer — this module PINs the transport decisions
and executes one send attempt per call (stdlib-only, side-effect free —
it returns a `PushResult`, never sleeps, never logs).

- **Request:** RFC 8030 POST with `Authorization: vapid t=<jwt>, k=<pubkey>`
  (VAPID `exp` = now + 12 h, `aud` = the endpoint origin per send, `k` =
  the caller's current key — rotation lives with the caller), `TTL:` =
  the payload's own `ttl_s`, `Urgency: high` (page-only channel — D2/D4),
  no `Topic` (never replace a page), `record_size` pinned at 1024
  (deliberate, not the 4096 default; oversized plaintext is rejected
  pre-send, never truncated). No caller salts anywhere — `secrets` mints
  a fresh one per send (finding 7, stated as a rule).
- **TLS:** `https://` endpoints only, no userinfo (cleartext refused —
  a VAPID-signed request never travels unencrypted); hostname + cert
  verification on; connect 5 s / read 10 s. Redirects are never followed
  — any 3xx is a dead-letter (credential-orientation).
- **Result taxonomy** (the per-code table the module docstring pins):
  any 2xx → `accepted` (201 is the RFC 8030 norm, but FCM answers
  successful sends with 200 — record it; feeds #428's §4 email-fallback
  retirement via `acceptance_fields()`); 429 → `retry` honoring
  `Retry-After` (clamped ≤ 600 s) else the 2/8/32/128/300 backoff
  schedule; 410/404 → `tombstone` (caller deletes, dashboard offers
  re-subscribe); 5xx and transport errors → `retry`; 400/401/413, any
  other 4xx, any 3xx → `dead-letter` + operator-visible alert. `retry`
  returns a `retry_after_s` hint — the #990 enqueue machinery owns the
  wait; the module's `MAX_ATTEMPTS = 5` is the policy the caller enforces.
- **Latency:** every attempt reports `latency_ms` (network only — the
  timer starts after crypto + VAPID signing, so VAPID-sign timing is
  excluded from the observable output). Real push-service RTT is still
  unmeasured, and this is the load-bearing input to the
  inline-vs-outbox decision (#990).

Tested by `test_push_sender.py` (36 tests, neutering-verified
non-vacuous) against a stub push service; the stub speaks plain HTTP on
localhost — the difference from production is documented and compensated
by a dedicated test pinning the production transport's TLS policy.

## push_sweep.py — the D9 reminder/digest sweep scheduler (#1063)

The cadence that calls the push lane's paging policy: one sweep reads
the plane's D1 database (the #988 contract tables plus the #872
approvals record) and runs three passes in order — due reminders,
digest triggers, then the cadence-driven watchers (heartbeat-stale,
token-expiry warning). The sweep only *selects candidates*; every
timing, dedup, and budget decision stays with the policy's gate-1
re-read and the enqueue boundary (`push_enqueue.py`). Over-selecting is
safe, under-selecting is the bug — the candidate SELECT is a hint, not
a decision. Truncation is self-healing (D75): already-paged reminders
are anti-joined out of the hint, so a truncated sweep's remainder is
reached next tick. Overlapping sweeps are safe without locks: the
page-once dedup and the idempotent superseded audit (D61, index-backed)
make a second concurrent sweep a no-op.

A due reminder pages exactly once; a decided/expired approval is never
a candidate, so it pages zero times and writes zero audit rows
(operator visibility is the approvals record itself); a pending
approval terminal only by the clock writes exactly one idempotent
audit row.

Owner identity is resolved from the enrollment registry via an injected
`resolve_owner(box_id)` — never from a box assertion, never from the
approvals row (fail-closed). The heartbeat-stale and token-warning
*derivations* stay plane-side caller logic (injected, off by default);
the sweep owns the cadence, not the derivation. The `reminders_enabled`
flag is the retirement hook for #958's Durable Object alarms. One
clock reading per sweep, threaded through every pass. The per-minute
cron trigger registration on the plane (D66/D72) is tracked in #1069.

Tested by `test_push_sweep.py` (47 tests, neutering-verified
non-vacuous): due reminder pages exactly once; decided/expired
approvals page zero times with zero audit rows; terminal-by-clock
selections write exactly one idempotent audit row; corrupt records
fail loud; paged candidate queries stay bounded and self-heal after
truncation; same-sweep reminder→digest ordering; mid-sweep resolver
failure is fail-closed and resumable; watchers page once per epoch /
per token generation.

Run the tests: `python3 -m pytest hosted/test_push_sweep.py` from the
repo root.

The async plane port's conformance set lives in `push_sweep_port/`
(scenarios + recorded outputs, the port's dispatch truth — see its
README); `test_push_sweep_port_conformance.py` (3 tests) replays every
scenario against this sync sweep and diffs the outputs against the
recorded files, failing on divergence. Regenerate the records with
`python3 -m hosted.push_sweep_port.record` after any intentional
behavior change.

## push_sweep_async.py — the D9 sweep's async plane port (#1566 S2-b1)

The canonical async rewrite of `push_sweep.py` against the plane
worker's async `_D1` (`await db.prepare(sql).bind(*params).all()` /
`.first()` / `.run()`; rows as dicts). Entry point
`push_sweep_async_tick(db, *, now, resolve_owner, policy,
reminders_enabled=True, ...)` — the four policy calls
(`maybe_enqueue_reminder`, `maybe_enqueue_digest`, `on_heartbeat_stale`,
`on_token_expiry_warning`) are an injected async `policy` boundary
(the async policy port is the next slice); the D8 bound rides the
policy as `reminder_min_ttl_seconds` so the hint/gate single-source
(#1507) holds across the seam. Watcher derivations may be sync
iterables (tests) or async iterables (the worker). The worker's
`control-plane/worker.py` derives its marked section from this file at
deploy time (D-PP-5 order); anti-drift is the D-PP-2 conformance, not
byte-identity (F-PP-2).

Tested by `test_push_sweep_async.py` (6 tests, neutering-verified
non-vacuous): all 21 D-PP-2 scenarios replayed through the async port
and diffed (summary + DB state) against the recorded outputs; the
record adapter's parity with the sync adapter; the policy boundary's
fail-closed validation; worker-shaped async-generator derivations.

Run the tests: `python3 -m pytest hosted/test_push_sweep_async.py`
from the repo root.

### Push-subscription endpoints (`push_subscriptions_async.py`)

The async plane-port of the GP2 subscription endpoints (#1392): the four
owner-authenticated endpoints pinned in
`docs/PUSH_SUBSCRIPTION_WIRE_CONTRACT.md` (decisions D98–D102) against the
#988 D1 `push_subscriptions` schema — VAPID key delivery, display-only
subscription list (secrets never travel on the read path), subscribe with
loud D99 validation and single-statement upsert on the D3 key, and
unsubscribe as a real delete — plus the D102 `/sw.js` serving rule with
its deploy-time byte pin. Browser key material is encrypted under the
plane's D45 data key through an injected seam (fresh nonce per
encryption, version mismatch fails closed) before every write; the
module never reads plaintext back (D46 write-only-after-set by
construction). Droppable into `worker.py` verbatim: stdlib-only, no
sync-module imports, the DB seam as awaited `_D1` calls.

Tested by `test_push_subscriptions_async.py` (28 tests, neutering-verified
non-vacuous): the full D99 400 taxonomy (device, endpoint, p256dh
length/prefix/curve, auth length), 201-vs-200 upsert with key-material
replacement + `last_page_at` clearing, `dead_410` resurrection,
real-delete 404s, multi-owner/box read+delete isolation, ownership 404s,
charset-before-lookup on unsubscribe, fresh-nonce-per-encryption with
decrypt roundtrip, the `_DISPLAY_COLUMNS` pin, the sync/coroutine/Future
ownership seam, both `.meta` shapes, and the service-worker
content-type + deploy pin.

Run the tests: `python3 -m pytest hosted/test_push_subscriptions_async.py`
from the repo root.

## push_events_async.py — the endpoint-driven push mappings' async plane port (#1492)

The async port of the two endpoint-driven push mappings from
`push_events.py` (the #969/#1062 paging policy). Four of the six
mappings are sweep-driven (reminders, digests, heartbeat-stale,
token-expiry-warning — the D9 sweep drives them). These two —
`on_approval_filed` and `on_box_revoked` — must be called from the
plane worker's HTTP request path: the filing endpoint after the
approvals record write, the revoke endpoint after the revocation
stamp. The sync modules can't be called from the worker because the
plane worker's D1 is async-only (`await db.prepare(...).bind(...).run()`;
no synchronous D1 exists), so like `push_sweep_async.py` this file is
droppable into `worker.py` verbatim: stdlib-only, no imports from the
sync modules, pure-compute validators inlined with source citations.

The async `enqueue_page` contract is injected, not imported: `await
enqueue_page(db, *, event_kind, owner_principal, box_id, key_material,
now=None)` — `db` is the worker's async `_D1`, `now` an aware UTC
datetime or None (the boundary defaults it, exactly like the sync
version). The result's `.disposition` (`queued`, `duplicate`,
`suppressed_budget`, ...) passes straight through — the D10 budget,
D57 page-once dedup, and D54 digest coalescing all live at the
boundary by construction.

Caller obligations (restated from the sync mappings, because the call
sites are what obey them): the filing endpoint must never emit a
filing event for an approvals record that's already terminal — there
is no gate-1 re-read on this path by design, so a terminal record
filed here would page spuriously; and revocation paging fires only
for real revocations, never for the keyless-grandfathered path.

Tested by `test_push_events_async.py` (11 tests, neutering-verified
non-vacuous): exact-argument delegation for both mappings,
disposition passthrough verbatim, loud rejection of bad owner / box /
aid shapes, non-timestamp revoked-at rejection, naive timestamps read
as UTC, a non-callable boundary raising loud, and boundary exceptions
propagating.

Run the tests: `python3 -m pytest hosted/test_push_events_async.py`
from the repo root.

## push_enqueue_async.py — the D10 enqueue boundary's async plane port (#1614)

The async counterpart of `push_enqueue.py`'s enqueue boundary against
the plane worker's async `_D1`. The sync module stays the harness and
test truth; the boundary reuses the sync decision table verbatim —
D10 budget, D57 page-once dedup, D54 digest coalescing. Policy is not
re-decided, only the DB-API boundary is ported. Like the other async
ports this file is droppable into `worker.py` verbatim: stdlib-only, no
sync-module imports, pure-compute helpers inlined with source
citations, and the DB seam as awaited `_D1` calls.

Entry point (the contract the #1492 mappings inject):
`await enqueue_page_async(db, *, event_kind, owner_principal, box_id,
key_material, now=None) -> EnqueueResult` — the `_async` suffix is the
in-repo naming convention (the `push_sweep_async` precedent); in the
worker's marked section it is the contract's `enqueue_page`.

D1 durability model: the `_D1` contract exposes no interactive
transaction across awaits, so every `.run()` is individually durable
and the port orders statements so every crash window is either
idempotent under retry or a documented under-count — the D52 guarded
UPDATE stays the single atomic gate; ensure-INSERTs are `INSERT OR
IGNORE`; the filing path's audit INSERT is idempotent under retry via
the D57 page-once index; the lost-dedup-race rule is
exception-type-agnostic but outcome-gated (a same-key row carrying a
D57-covered outcome declares `duplicate` and releases any taken
reservation; any other failure re-raises loud).

Trust posture: the boundary never accepts a box-asserted owner — the
caller resolves `box_id → owner_principal` from the plane's enrollment
registry and passes the resolved principal in. The obligation travels
with this file because it drops into `worker.py` verbatim, ahead of
the endpoint wiring.

Tested by `test_push_enqueue_async.py` (19 tests, neutering-verified
non-vacuous): happy-path parity with the sync version (UTC ISO shape),
the duplicate fast path consuming no budget, budget exhaustion
coalescing into the digest, digest-suppression never touching the
digest count, owner-only digest reservations, floor-at-zero release,
the lost-dedup race returning `duplicate` with the reservation
released, uncovered-outcome failures re-raising, no-page kinds as
value errors, sync-conformance on dispositions and DB state under
budget overflow, and the async mappings composing with the async
boundary end to end.

Run the tests: `python3 -m pytest hosted/test_push_enqueue_async.py`
from the repo root.

## vend_rate_limit.py — per-box mint rate limiter (#1405)

The mechanism behind the contract's §2.2 rate-limit sentence
(`docs/CREDENTIAL_VEND_CONTRACT.md`): a D1-backed token bucket, one
per `(box_id)`, capacity 10 mints / 300 s / box (D105 — at the §2.3
minimum TTL the legitimate cadence is already ~1 mint request / 300 s /
box (all due names batched per the §5 discipline, D-VC-13),
so the bucket only ever fires on abuse loops; the point is bounding
the D1 write amplification of a compromised box, not throttling
tenants). The take is one atomic single-statement UPDATE — refill
(capped at capacity, float dust snapped with `ROUND(..., 6)`) and
spend under the `>= 1.0` gate — so concurrent takers serialize in the
writer and the bucket can never over-spend (D106 keeps the
first-mint INSERT race from double-spending too). Denied takes get an
advisory `retry_after_s` for the 429's `Retry-After`; emitting the 429
at the endpoint is #890's scope. Fail-closed typing: non-`str`
`box_id` raises `TypeError` before any SQL runs.

`vend_rate_limit_async.py` is the async plane port against the
worker's async `_D1` — droppable into `worker.py` verbatim
(stdlib-only, no sync-module imports, `_to_py`/`_run_changes`
inlined with source citations, the D-PP-1/D-PP-2 pattern). The sync
module stays the harness and test truth.

Tested by `test_vend_rate_limit.py` (10 tests, neutering-verified
non-vacuous): first-mint allowed, capacity exhaustion with
hand-computed `retry_after_s`, refill over time with the idle cap,
per-box isolation (interleaved-budget shape — the exhaust-then-probe
shape was blind to cross-box theft), a 20-thread race proving the
bucket never over-spends, fail-closed typing, `retry_after_s`
rounding up at non-integral quotients, and the advisory hint shrinking
as time passes. Conformance by `test_vend_rate_limit_async.py` (5 tests):
every scenario runs against both the sync truth and the async port
over a worker-faithful `_D1` shim and asserts identical outcomes plus
hand-computed expectations — the shim mirrors the worker's
`success + meta.changes` shape, so port-shape mistakes fail loud.

Run the tests: `python3 -m pytest hosted/test_vend_rate_limit.py hosted/test_vend_rate_limit_async.py`
from the repo root.
