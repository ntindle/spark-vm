# Push sender claim design (D56a, #1094)

Security-archetype design slice for issue #1094 (push sender loop —
claim/fanout/retry/schedule, #967 follow-up). This doc pins the one
unpinned security property in the #849 phone-approval lane: **D56a —
the sender loop MUST run exactly one instance per D1 store**, because
page-once is the lane's core promise and a double-send is a double
buzz that no downstream dedup can un-ring.

Pinned to spark-vm main `e940738` (2026-10-07). Companion docs: the
D56 sender-loop contract (`hosted/push_enqueue.py`, D56a–f, #990), the
D9 sweep scheduler (`PUSH_SWEEP_SCHEDULER_DESIGN.md`, D66–D74, #1063),
the schema contract (`PUSH_SENDER_SCHEMA_CONTRACT.md`, #988/#1061),
the transport (`hosted/push_sender.py`, #989). This doc is the
mechanism #1094's builder executes against; #1094 owns the drain body.

## 1. Why the claim is a security property

Everything downstream of the claim is a correctness property *given*
serialization: the D56b terminal transaction, the D57 page-once
partial unique index, and gate-2's terminal-state re-read all assume
one writer. Two loop instances SELECTing the same `'queued'` rows
send the same page twice — the per-attempt rows do not dedup (D57's
page-once index covers the queued row, not the attempts), and the
buzz does not un-ring.
The claim is therefore mutual exclusion with a user-visible failure
mode, and it deserves a mechanism whose guarantee is structural, not
arithmetical.

## 2. Candidates, and why two lose

**Cron-isolate serialization — rejected.** #1094's own issue body
rules it out: Cloudflare Workers cron invocations can overlap, so
cron alone is not a singleton. No further analysis needed.

**D1 lease row with expiry + fencing token — rejected.** It works on
paper (conditional `UPDATE ... WHERE expires_at < now`, heartbeat
renewals, the fencing token riding the attempt rows so a stale holder's
writes fail closed), but it loses on three counts:

1. The expiry window is a *real* double-claim race, not a theoretical
   one: two instances separated by a slow D1 write or a paused isolate
   can both believe they hold the lease across the boundary, and the
   fencing check only fails the *second* writer's DB writes — the first
   writer's already-sent buzzes stand. The lease bounds the race; it
   does not eliminate it.
2. It needs a new D1 table against #988's frozen schema (contract
   amendment, forward migration, and a new retention surface for
   #1058 to own).
3. Heartbeat/renewal logic is new failure surface (what renews the
   lease during a 90-second digest drain? what is the renewal
   interval's relationship to the worst-case send latency?) with no
   upside over the platform primitive below.

## 3. The design: a Durable Object singleton

**C1. The claim is a `PushSenderDO` Durable Object, one instance per
worker script.** The plane Worker (Python, workers-py — the `BoxDO`
class in `control-plane/worker.py` is the deployed precedent, #958
S4a) already speaks Durable Objects. The sender stub is derived as
`env.PUSH_SENDER_DO.idFromName("push-sender")` — a constant name,
one instance per (worker script, namespace). (The D1 store plays no
role in `idFromName`; the script↔store pairing is the deploy hygiene
§4 names.)

The DO is the fence *only while the input gate is held closed*: the
input gate blocks new events during synchronous execution and the
DO's own storage operations, but **awaiting any external I/O — the
D1 binding calls and the push POSTs — opens the gate and lets an
overlapping `/drain` interleave** (Cloudflare "Rules of Durable
Objects": "Input gates only protect during storage operations.
Non-storage I/O like `fetch()` … allows other requests to
interleave, which can cause race conditions"). SELECTing `'queued'`
rows, awaiting a push POST, then awaiting the terminal transaction
is exactly that anti-pattern — a second drain can SELECT the same
rows mid-send and double-buzz. The `/drain` handler MUST therefore
run its whole body — SELECT, sends, terminal transactions — with
the input gate held closed (`blockConcurrencyWhile` semantics; the
exact workers-py binding name is verified against the plane
workspace's pinned workers release at build time — #1094's
acceptance). This is the justified exception to the "reserve
gate-holding for init/migrations" guidance: D56a demands true
serialization, cadence is one tick per minute, and C3's N/T bound
keeps the head-of-line wait bounded. There is no expiry arithmetic
to misconfigure and no fencing token to plumb — the *held* input
gate is the fence.

Rejected alternative: a per-row atomic claim (`UPDATE … SET
outcome='sending' WHERE id=? AND outcome='queued'`, rowcount-checked
before each send). It serializes the sends, but a crash between
claim and terminal transaction strands rows in `'sending'` forever —
which needs a reaper with a lease expiry, and the expiry arithmetic
walks back in through the side door. Gate-holding needs no new
outcome value and no reaper.

**C2. Handoff: the per-minute `scheduled` handler drives the DO.**
D66/#1069 own the cron trigger (`* * * * *` on the plane Worker).
The handler runs the D9 sweep passes first (reminders, then digests
— D67 — then the D74 cadence watchers), then POSTs `{now}` to the
sender stub's `/drain` and awaits the summary (the POST-with-JSON-body
`stub.fetch` form is confirmed against the installed workers-py at
build time). The sweep's enqueue half is idempotent-by-design (D69);
the drain half is serialized by C1; composing them in one invocation
is safe, and a tick's newly-enqueued pages can send in the same tick.
Overlapping ticks queue on the DO's input gate — they wait, never
run concurrently (true only because C1 holds the gate closed across
the drain body). Fail-safe: if the handler's own fetch to a
gate-held drain times out on the caller side, the DO continues
independently and the next tick re-scans — cursor-free C3 makes the
orphaned tick harmless.

**C3. Bounded work per drain.** Each `/drain` processes at most N
queued rows or T seconds, whichever comes first (the values are
#1094's to tune against measured push-service RTT; the mechanism is
pinned here). N is additionally bounded by the Workers subrequest
ceiling per invocation (each push POST is a subrequest) and T by the
scheduled-event maximum duration — both plan-dependent; #1094's
tuning reads them from the pinned workers release. Selection is
cursor-free —
`WHERE outcome = 'queued' ORDER BY id ASC LIMIT n` (D56a's ordering
pin) — so a crash or an overrun restarts by re-scan, never by
restoring a cursor. The common case (empty outbox) is one cheap
SELECT and a fast return, which is what keeps the input-gate queue
short.

**C4. Crash posture: retry may double-buzz; that is accepted.**
If the DO's isolate dies mid-drain, the in-flight row is still
`'queued'` and the next tick sends it again. This is the same
posture the lane already accepted twice: D56f's under-counted
attempt on crash, and #989's 408 reasoning (a second buzz is never a
safety violation; a lost page is worse). The DO keeps no durable
state of its own — all state lives in D1 — so there is nothing to
recover and nothing to reconcile.

**C5. No public route reaches the sender stub.** The Worker's `fetch`
router MUST NOT expose the DO. The stub is obtained only from `env`
inside the `scheduled` handler. If operators want a manual drain
trigger, it follows the journal GC's precedent (`POST
/v1/ops/phone_home/gc`, owner-key authed) — owner-auth, plane-side,
logged. Whether to add it is #1094's call, not this doc's.

**C6. No schema change.** The claim needs no D1 table: #988's frozen
schema stays frozen, and #1058's retention scope is untouched.

**C7. VAPID custody inside the DO.** The DO inlines the I/O-free
helpers (`hosted/push_crypto.py`, `hosted/push_payload.py` — pure
stdlib, no sockets) via the WORKER COPY pattern; the POST transport
is #1094's to close against a staging Worker —
`push_sender.py`'s `http.client`/raw-socket transport does not run
unmodified in the Workers sandbox (Pyodide has no functional raw
sockets; outbound HTTP is shimmed through the Fetch API with
different timeout/cancellation semantics), so the send path ships
as a fetch-based POST or a shim-verified adapter, staging-verified
before it pages anyone. The VAPID private key arrives via worker env
(operator-owned; custody rules D45/D46, VAPID lifecycle D48 in the
schema contract); the DO never logs it — the crypto/payload helpers
log nothing and keep no state, and the DO's own logs carry only
`subscription_ref`, outcome, and latency.

**C8. Deploy scope.** New DO class binding in the plane workspace
(`PUSH_SENDER_DO`), a one-time `new_sqlite_classes` migration entry
on the first deploy that introduces the class (re-sending it is
rejected — later deploys omit `migrations` entirely, per the
`deploy_worker.py` comment; `new_classes` fails with error 10097 on
the current plan), and the class added to `worker.py` directly
(BoxDO is the direct-definition precedent; the `hosted/` helpers
arrive via the WORKER COPY inlining into `worker.py` source) and
shipped by `deploy_worker.py`. The `scheduled`-handler handoff rides
#1069's cron-trigger wiring (D66): #1069 owns the trigger, this doc
owns the claim, #1094 owns the drain body. All three land before the
lane can page.

**C9. Scope boundaries.** The DO is the drain *only*: not the sweep
(D9's passes stay in the scheduled handler per D66–D74), not
subscription management (#968), not the D10 budget (enqueue-time,
#990), not digest assembly (#1064). When #958's per-approval DO
alarms land and the D9 reminder pass retires per D71, the sender DO
is unaffected — it drains whatever is queued. Liveness note: the
sender DO's only driver is the `scheduled` handler — safe today
because D71 keeps the cron for the digest and watcher passes, but a
future full cron retirement would need a new `/drain` driver.

## 4. The claim's exact scope (read this before extending it)

The singleton holds per **(worker script, namespace)** pair — the D1
store plays no role in the id derivation, so the exactly-one-per-D1
guarantee is a property of the deploy, not the platform. Two
different worker scripts (production vs staging) bound to the same
D1 would each derive their own `"push-sender"` instance and could
double-send; likewise a second worker binding this DO class via
`script_name` must never point at the production D1. The design
therefore requires deploy hygiene — when a staging worker script is
created it binds its own D1, never production's — and names it here
so the invariant is explicit rather than assumed. (Sharding D1 per
tenant in the future would promote the stub name to
`idFromName("push-sender:" + tenant)`; that is a future design's
call.)

## 5. What #1094 still owns

The drain body per D56b–f (terminal transaction, fanout rows,
gate-2, retry accounting), the C3 bound values, the digest TTL
header pin, the VAPID `sub` mailbox existence check, and the
`acceptance_fields()` wiring into the #988 store. #1094's acceptance
also carries: (a) a grep check that `PUSH_SENDER_DO` is referenced
only in the `scheduled` handler (the C5 no-public-route rule, made
checkable); (b) the outbox depth on the `/drain` summary (D75's
`pages_truncated`-on-summary precedent) so a wedged sender is
operator-visible; (c) unhandled-exception paths in the DO must not
leak VAPID key material into platform logs. This doc amends nothing
in D56's contract text — D56a's "MUST run exactly one instance per
D1 store" now names this doc as its mechanism.

Status 2026-10-07: the drain body landed — `hosted/push_send_loop.py`
(#1102) implements the D56b–f drain the loop runs under this claim:
claims `'queued'` outbox rows in `id` ASC, gate-2 terminal-state re-read
(D56d/D80/D85 — aid-keyed kinds re-read the live approval record before
any send; decided or deleted approvals never page), per-device fanout
against live subscriptions only, six retry attempts with backoff
(429 Retry-After honored; 410/404 tombstones; then per-device
dead-letter), and aid-keyed re-page by the reminder machinery. The
Durable-Object singleton claim build itself is still open on #1094 —
until it ships, the interim claiming mechanism is the non-overlap
scheduler rule pinned in `docs/PRODUCTION_DEPLOY_CONTRACT.md`
"Scheduled plane jobs" (the claim-design doc's §3 pins the
DO-singleton's input-gate behavior for the built world, not the
interim rule). Companion: `hosted/push_sender.py` (#989) owns the
transport; `hosted/push_enqueue.py` (#990) owns the enqueue boundary.
