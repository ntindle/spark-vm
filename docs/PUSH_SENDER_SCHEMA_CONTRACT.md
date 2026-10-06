# Push-sender schema contract: D1 store, custody, VAPID lifecycle (#967 GP1 sub-slice / #988)

**Status.** Design contract, pinned to this repo at merge (PR number in
the CHANGELOG entry). Plane-side facts are pinned to the loop's
2026-10-04 reads of the `sparkvm-control` worker checkout — the plane
lives outside this repo, so the schema below is the contract the plane
must implement, not a description of what it does today. Doc-first;
honesty rules apply (`docs/POSITIONING.md`): everything below is the
**agreed design and the work to do**, not a promise. Nothing here sends
a push.

**Place in the slice plan** (`docs/HOSTED_PLANE_PUSH_GAP_ANALYSIS.md`
§3): GP1 sub-slice of #967 (plane Web Push sender). The S1 validation
proved the crypto mechanism (`hosted/push_crypto.py` — RFC 8291
`aes128gcm`, in-worker sender VALIDATED); #970 pinned the payload
discipline (`hosted/push_payload.py`); #969 pinned the event taxonomy
(D8–D13); #989 built the send path (`hosted/push_sender.py` — stdlib
RFC 8030 POST, per-code result taxonomy, and `acceptance_fields()`,
which deliberately leaves the D1 table to this contract: *"the
endpoint, `p256dh` and `auth` secrets never appear here. #988 owns the
D1 table; this pins the fields."*). What this doc pins is the schema
contract all of those consume: the D1 subscription store, the D10
budget counters, the send-result/acceptance records, and the digest
state — plus the custody section the parent doc's D3 left as a
paragraph. Builds against this contract: #990 (enqueue boundary +
backpressure), #968 (owner subscription surface).

**Vision tracker:** #849 (phone-approval loop). Implementation items:
#989 (shipped), #990 (shipped), #968. This contract is also what #428's §4
retirement criterion consumes: the criterion flips when the plane
records a push-service-accepted delivery for the tenant — the
record shape that makes it satisfiable is §1.3 below
(`outcome='accepted'`).

**Decision-number note.** The issue body for #988 asks for "D-series
D14+ pins" — written before the S4b lane claimed D14–D18
(`docs/S4B_SOCKET_LIFECYCLE_GAP_ANALYSIS.md`) and the terminal-stream
lane claimed D26–D44 (`docs/TERMINAL_STREAM_WIRE_PROTOCOL.md`). The
D-series is one global sequence; this doc continues it at **D45**.
Nothing is renumbered — the issue body's "D14+" is superseded by this
note.

## 1. D1 schema

Four tables. Conventions follow the plane's existing migrations
(`migrate_872.sql`, `migrate_958_s4b.sql`): `TEXT` timestamps as ISO
UTC or epoch integers where the writer already stamps epochs;
`CREATE TABLE IF NOT EXISTS` one-shot forward migrations (re-run is a
silent no-op); event-name columns stay plain `TEXT` (the loud
fail-closed whitelist in code is the real gate, not a `CHECK`).

### 1.1 `push_subscriptions` — the D3 store

Keyed `(owner_principal, box_id, device)` per the parent doc's D3.

```sql
-- #988: push subscription store (D3). One row per owner/box/device.
-- p256dh/auth are CIPHERTEXT (D45) — see §2.
CREATE TABLE IF NOT EXISTS push_subscriptions (
  owner_principal TEXT NOT NULL,  -- the #843 owner-key identity
  box_id          TEXT NOT NULL,  -- enrolled box; must be a box the
                                 -- owner_principal owns (enforced in code)
  device          TEXT NOT NULL,  -- client-chosen label, 1-64 chars,
                                 -- [A-Za-z0-9._-] (the aid charset precedent)
  endpoint        TEXT NOT NULL,  -- push-service URL; https-only, no
                                 -- userinfo (validated like the pairing
                                 -- redirect-target discipline, #885)
  p256dh          BLOB NOT NULL,  -- AES-256-GCM ciphertext (D45)
  p256dh_nonce    BLOB NOT NULL,
  auth            BLOB NOT NULL,  -- AES-256-GCM ciphertext (D45)
  auth_nonce      BLOB NOT NULL,
  data_key_version TEXT NOT NULL DEFAULT 'v1',
                                 -- which Worker-secret data key encrypted
                                 -- this row (D45 dual-key-read discriminator)
  vapid_key_id    TEXT NOT NULL DEFAULT 'v1',
                                 -- which VAPID keypair signs sends to this
                                 -- subscription (D48c rotation discriminator)
  added_by        TEXT NOT NULL,  -- owner-key id that created the row
                                 -- (forensics: which key added this device)
  status          TEXT NOT NULL DEFAULT 'live',
                                 -- 'live' | 'dead_410' (the send path marks
                                 -- dead on 410; the dashboard prompts
                                 -- re-subscribe per the §1.3 note)
  created_at      TEXT NOT NULL,  -- ISO UTC
  last_page_at    TEXT,           -- ISO UTC, NULL until first page; written
                                 -- by the send path on outcome='accepted'
  PRIMARY KEY (owner_principal, box_id, device)
);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_fanout
  ON push_subscriptions(owner_principal, box_id, status);
```

Fanout (D3, pinned 2026-10-04): a page for an (owner, box) event fans
out to every `live` subscription under `(owner_principal, box_id, *)`
— the index serves exactly that query. Whether subscribing is
per-box opt-in or per-owner default is the open product question §5
carries; the schema supports either (rows exist only where the owner
subscribed).

Unsubscribe deletes the row outright (no tombstone — a re-subscribe is
a fresh row with fresh key material; the `dead_410` status exists so
the dashboard can distinguish "subscription died" from "never
subscribed" before the owner acts).

### 1.2 `push_budget_counters` — the D10 bound, made countable

D10: per-(box, hour) ≤ 3, per-(owner, hour) ≤ 10; the bound caps
*successful pages*, not attempts; budget counts **pages, not device
deliveries**.

```sql
-- #988: D10 page-budget counters. One row per (scope, hour bucket).
-- Reservation model: enqueue atomically checks both scopes against the
-- bound AND increments both (one atomic step). Terminal outcomes then
-- resolve the reservation: 'accepted' keeps it (budget consumed);
-- 'tombstone', 'dead-letter', and 'suppressed_terminal' release it
-- (decrement both scopes); 'suppressed_budget' never took one.
-- The 'queued' outbox row (D50) holds the reservation for the whole
-- outbox wait; the terminal outcome's rule above resolves it when the
-- queued row is DELETEed at the terminal attempt.
CREATE TABLE IF NOT EXISTS push_budget_counters (
  scope_type   TEXT NOT NULL,  -- 'box' | 'owner'
  scope_id     TEXT NOT NULL,  -- box_id | owner_principal
  window_start TEXT NOT NULL,  -- hour bucket, YYYY-MM-DDTHH UTC
  count        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (scope_type, scope_id, window_start)
);
```

The atomic check-and-increment primitive is #990's to build — this
contract requires it as one atomic step over both scopes (a page
consumes one unit of each), because check-then-increment in two steps
lets two racing enqueues both read under-bound, both send, both
succeed, and both keep — over the bound with no violation recorded.
The reservation model is what makes "bounds successful buzzes, not
attempts" implementable: a page that is retried three times then
accepted holds one reservation and lands four rows (three `retry` +
one `accepted`) but consumes one unit of budget; a page that
dead-letters releases its reservation, consuming zero. Stale hour
buckets are never read again; GC of buckets older than 90 days is
filed follow-up #1058 (see §4).

### 1.3 `push_send_results` — the record #428's §4 criterion consumes

Every send attempt lands exactly one row. The outcome vocabulary is
the sender's verbatim (`hosted/push_sender.py::OUTCOMES`), plus three
documented *extensions* for enqueue-boundary decisions (not part of
#989's taxonomy) — D50 added the third, the `'queued'` outbox work
item (documented here by #1061). The table preserves `acceptance_fields()`' pinned
fields (`outcome`, `http_status`, `sent_at`, `latency_ms`),
decomposing its opaque `subscription_ref` into the key columns so the
D13 dedup keys and the fanout queries work without parsing.

```sql
-- #988: send-result / acceptance records. One row per send attempt.
-- This is the table #428's §4 retirement criterion reads: the criterion
-- flips when a row with outcome='accepted' exists for the tenant.
-- Never carries payload contents (aid only per D4; never secrets).
CREATE TABLE IF NOT EXISTS push_send_results (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  at              TEXT NOT NULL,  -- ISO UTC, writer-stamped
  owner_principal TEXT NOT NULL,
  box_id          TEXT NOT NULL,
  device          TEXT NOT NULL,  -- the subscription's device label
  event_kind      TEXT NOT NULL,  -- taxonomy §2 event name
                                 -- ('approval_filed', 'reminder',
                                 -- 'token_expiry_warning', 'box_revoked',
                                 -- 'heartbeat_stale', 'digest')
  event_key       TEXT NOT NULL,  -- the D13 dedup key with values, encoded
                                 -- as components joined by U+0000
                                 -- (§1.3a); never the bare key shape
  outcome         TEXT NOT NULL,  -- sender vocabulary verbatim: accepted |
                                 -- retry | tombstone | dead-letter; plus
                                 -- enqueue-boundary extensions:
                                 -- suppressed_budget | suppressed_terminal
                                 -- | queued (D50, the outbox work item)
  http_status     INTEGER,        -- the push-service status (NULL for
                                 -- suppressed_* and queued — nothing was
                                 -- sent)
  latency_ms      REAL,           -- measured send latency (NULL for
                                 -- suppressed_* and queued); the ~38 ms
                                 -- crypto-only figure is NOT this column
  sent_at         REAL,           -- epoch seconds, the sender's clock
  vapid_key_id    TEXT            -- which VAPID key signed this send (NULL
                                 -- for suppressed_* and queued); the D48d
                                 -- compromise audit joins on this, not the
                                 -- subscription's current row
);
CREATE INDEX IF NOT EXISTS idx_push_send_results_dedup
  ON push_send_results(box_id, event_kind, event_key);
CREATE INDEX IF NOT EXISTS idx_push_send_results_tenant
  ON push_send_results(owner_principal, at);
-- D57 (pinned in the contract by #1061's amendment — this is #990's
-- shipped statement, PR #1060; the operator applies it with
-- migrate_967_push.sql, which lives in the control-plane workspace
-- outside this repo): page-once is a DB invariant — one row per event
-- across the enqueue boundary, enforced at the database layer. The
-- predicate excludes the sender loop's per-attempt rows (which
-- legitimately share the event key and must not collide), so D50's
-- "every send attempt lands exactly one row" is untouched.
CREATE UNIQUE INDEX IF NOT EXISTS idx_push_send_results_page_once
  ON push_send_results(box_id, event_kind, event_key)
  WHERE outcome IN ('queued', 'suppressed_budget', 'suppressed_terminal');
```

#### 1.3a `event_key` encoding

The D13 dedup keys with values, components joined by a single U+0000
(which cannot appear in a box_id, aid, or ISO timestamp):

| event_kind | event_key |
|---|---|
| `approval_filed`, `reminder` | `box_id + "\x00" + aid` |
| `token_expiry_warning` | `box_id + "\x00" + token_hash` (D13: generation := the current `token_hash`) |
| `box_revoked` | `box_id + "\x00" + revoked_at` (ISO UTC — the revocation event's identity) |
| `heartbeat_stale` | `box_id + "\x00" + stale_epoch` |
| `digest` | `owner_principal + "\x00" + window_start` (the digest carries a count, never an aid — not cancellable per-aid, by design) |

Outcome semantics (the #989 result taxonomy, recorded here so the
table reads without the code; `suppressed_*` and `queued` are the enqueue
boundary's extensions):

- `accepted` — push service returned 2xx (any 2xx — the sender
  accepts 201/202 and FCM's 200 alike). Feeds the D10 budget
  reservation (kept) and #428's §4 criterion.
- `retry` — 429/5xx or transport error; the attempt will be retried
  per the #989 backoff. Non-terminal: the D10 reservation is held
  across retries of the same page.
- `tombstone` — 410/404: the subscription is dead. The send path
  marks `push_subscriptions.status = 'dead_410'` and releases the
  D10 reservation; the dashboard (#968 surface) prompts
  re-subscribe.
- `dead-letter` — 400/401/413 or exhausted 5xx retries: never
  delivered, operator-visible. Releases the D10 reservation.
- `suppressed_budget` — the enqueue gate rejected the page as over
  the D10 bound; coalesced into the hourly digest. Never took a
  reservation. (Extension, not a sender outcome.)
- `suppressed_terminal` — gate-2 (D12) dropped it: decided or
  expired between enqueue and send; the reservation taken at
  enqueue is released. The audit row the taxonomy promises the
  sentinel leg is this row. (Extension, not a sender outcome.)
- `queued` — D50: the outbox work item, not a send result. Inserted
  by `enqueue_page` when the page takes the D10 reservation and
  waits for the sender loop (enqueue-time rows carry `device=''`;
  `http_status`, `latency_ms`, `sent_at`, `vapid_key_id` NULL —
  nothing was sent yet). The sender loop selects `'queued'` rows in
  `id` ASC, INSERTs one row per send attempt, and DELETEs the
  `queued` row on the terminal attempt — so "every send attempt lands
  exactly one row" and the "three retries then accepted lands four
  rows" accounting hold verbatim, per device (the fanout multiplicity
  is one row per (device × attempt), D56c; the `queued` row is gone by
  the time the row-count is read). Holds the D10 reservation for the
  whole outbox wait; the terminal outcome's §1.2 rule resolves it.
  (Extension, not a sender outcome.)

**D57 — the predicate covers `suppressed_terminal` too.** The
partial unique index above is #990's shipped statement, not #1061's
issue-body draft (which proposed only `('queued',
'suppressed_budget')`): the #990 build (unanimous SHIP IT,
PR #1060) carries the three-value predicate, and the contract pins
the shipped statement. `suppressed_terminal` does not false-collide
under the predicate: the D61 audit key is the page key plus a
U+0000 `"superseded"` suffix, distinct from every page and attempt
key, so the audit's exactly-once holds under overlapping sweeps
(D69) with no false collisions. **Operator note (forward
migration):** SQLite cannot ALTER an index predicate — when the
predicate changes, run `DROP INDEX IF EXISTS
idx_push_send_results_page_once` then CREATE with the new
predicate, and do it *before* deploying any build that writes these
tables, alongside `migrate_967_push.sql`. Before dropping, confirm
the current predicate with `SELECT sql FROM sqlite_master WHERE
name='idx_push_send_results_page_once';` — if it shows anything
other than the statement above (e.g. an earlier two-value
predicate), the DROP/CREATE applies.

### 1.4 `push_digest_state` — the D10 digest, made stateless-safe

```sql
-- #988: hourly digest state (D10). One row per (owner, hour).
-- The digest carries a count + dashboard deep-link, never an aid
-- (not cancellable per-aid — by design, stated here).
CREATE TABLE IF NOT EXISTS push_digest_state (
  owner_principal TEXT NOT NULL,
  window_start    TEXT NOT NULL,  -- hour bucket, YYYY-MM-DDTHH UTC
  count           INTEGER NOT NULL DEFAULT 0,  -- coalesced pages
  enqueued_at     TEXT,           -- ISO UTC the digest page was accepted
                                 -- (enqueue-time; NULL = pending, not yet fired)
  PRIMARY KEY (owner_principal, window_start)
);
```

## 2. Custody: where subscription secrets rest on the plane (D3, hardened)

The parent doc's D3 says subscription secrets "rest in the D1
database, readable only by the owner principal's own authenticated
reads" — findings 2–4 of #988 require harder answers. They are
decisions here, not follow-ups.

- **D45. At rest: encrypted.** `push_subscriptions.p256dh` and
  `.auth` are AES-256-GCM ciphertexts with a fresh random nonce per
  encryption (each nonce stored in its own column alongside the
  ciphertext it was used for). The data key lives as a **Cloudflare
  Worker secret** — never in D1, never in the repo, never in logs,
  never in a send-result row. This is vend-lane parity
  (`CREDENTIAL_VEND_CONTRACT.md` §3): the D1-reader spam-cannon class
  finding 2 names is real — a D1 reader with plaintext `p256dh`/`auth`
  can buzz every subscribed device indefinitely — so the at-rest
  answer is encryption, not the parent doc's default. Key rotation is
  an operator procedure (re-encrypt under the new key, discriminated
  by `data_key_version`; old key destroyed ≤ 24 h after the rotation
  completes, the vend lane's bound). Stated plainly, as the vend
  contract states it: one data key protects all tenants'
  subscription secrets, so one key compromise exposes every
  `p256dh`/`auth` — which is why the key lives in a Worker secret
  and rotates as an operator procedure. (A D1-only reader still
  needs the *separate* VAPID private key to actually send — §3 —
  so finding 2's "buzz every device" framing is the D1+Worker-secret
  compromise case, not the D1-only case; the D1-only case gets
  ciphertexts it cannot use.)
- **In flight:** plaintext exists only in worker memory during the
  subscribe encrypt-and-store and while assembling a send (decrypt
  → encrypt-push-message), over TLS, to the authenticated owner or
  the push service. The vend contract states this explicitly; so
  does this one.
- **D46. Write-only-after-set.** The owner manages subscriptions
  (subscribe/unsubscribe via #968) but **never reads `p256dh`/`auth`
  back through the API** — the browser supplies them at subscribe
  time and the plane's sender is the only reader. `GET` on
  subscriptions returns metadata only (`device`, `status`,
  `created_at`, `last_page_at`) — never key material. This
  tightens the parent doc's D3 ("readable only by the owner
  principal's own authenticated reads"): the owner never needs the
  raw values, so the read path does not exist. Values are
  write-only after set; rotation means re-subscribe, not read-back.
  (Vend-lane precedent: "Owner keys manage but cannot read
  plaintext values.")
- **D47. Honest limit: no operator blindness.** The plane operator
  controls the worker and its secrets. There is **no claim of
  operator blindness** — H11's finding 4 (decided 2026-09-24),
  inherited here exactly as the vend contract §3 inherits it. This
  design protects against *infrastructure-layer* exposure
  (Cloudflare-side, backups, mis-scoped service tokens), not the
  operator. Users wanting provider-blind infrastructure self-host.
- **What a D1-reading attacker gets:** subscription metadata
  (owner/box/device, endpoint URLs — which leak the push-service
  origin and per-subscription tokens, i.e. device platform/browser
  family — timestamps, `added_by`, budget counters, send-result rows
  with event keys and outcomes — no payload contents), ciphertexts
  (unreadable without the Worker secret). They do **not** get any
  subscription key material, the data key, the VAPID private key
  (never in D1, §3), or a box token. (Endpoints are sensitive enough
  to keep out of logs per "Never in logs" below, but not sufficient
  for sends: without key material and the VAPID key they are
  addressing metadata, not a capability.)
- **No box-legibility.** No endpoint serves subscription rows —
  metadata or otherwise — to box-bearer callers. The box holds no
  push credentials and no VAPID material (parent D1); the
  subscription store is owner-plane only.
- **Never in logs.** Endpoints, `p256dh`/`auth` (ciphertext or
  otherwise), and VAPID material never appear in worker logs —
  including 4xx/5xx error bodies, exception traces, and edge logs;
  subscribe-validation errors must not echo the endpoint.
  Send-result rows carry event keys + outcomes, never payload
  contents (D4's aid+TTL-only rule holds at rest too).

## 3. VAPID lifecycle (D48)

`hosted/push_crypto.py::generate_keypair` exists (P-256, RFC 8291
§4.1 / RFC 8292). The lifecycle around it:

- **D48a. Generation is operator-run, offline.** The operator runs
  `generate_keypair()` on a trusted machine — never on the plane,
  never in CI. The private key is installed as a Cloudflare Worker
  secret; the public key is published to subscribers at subscribe
  time (served by the #968 dashboard affordance) and sent as the
  `k=` parameter of the VAPID `Authorization` header per send.
- **D48b. Provisioning path.** Worker secret (not D1, not the repo —
  D3's "never committed" rule). The deploy path that installs it is
  pinned when the #990 build wires the sender into the worker; the
  secret's *existence* is this contract's requirement, the install
  procedure is the build's.
- **D48c. Rotation is per-subscription-keyed, never fleet-wide.**
  Push services verify the VAPID JWT against the presented `k=`
  and consult no published registry — and the likeliest push
  service (FCM) binds a subscription to the `applicationServerKey`
  used at subscribe time, so swapping `k=` under existing
  subscriptions yields 401 → `dead-letter` fleet-wide. Rotation
  therefore never swaps the signing key under live rows:
  generate the new pair → install as a Worker secret alongside
  the old (keyed by `vapid_key_id`) → new subscriptions are
  created under the new id; the sender signs each subscription's
  sends with its own row's `vapid_key_id` → migrate old rows via
  re-subscription (dashboard affordance, #968) or natural churn →
  destroy the old private key only when no `live` subscription
  references its id, and in any case ≤ 90 days after the rotation
  starts. The availability cost is stated, not hidden: during the
  migration window two VAPID identities are live, and rows that
  never re-subscribe keep working under the old key until the
  bound — rotation pages nobody into silence.
- **D48d. Compromise response.** Rotate immediately per D48c; audit
  `push_send_results` for sends under the old key during the
  window via the row's `vapid_key_id` (recorded per send, so the
  audit survives later re-subscription migrations).
- **D48e. `exp`/`aud`/`sub` policy.** `exp`: now+12h (RFC 8292
  allows ≤ 24h; 12h is the pin — the #989 build records it).
  `aud`: the push-service endpoint origin, derived per send.
  `sub`: a `mailto:` contact for the plane operator (RFC 8292) —
  the #990 build pins the address. `k=`: the subscription row's
  `vapid_key_id` public key — rotation swaps it per D48c, per row,
  never fleet-wide.

## 4. Forward migration plan (D49)

- **D49. One one-shot forward migration: `migrate_967_push.sql`.**
  Creates all four tables + the three indexes (the §1.3 dedup index,
  the tenant index, and the D57 page-once partial unique index —
  #1061), `IF NOT EXISTS` throughout (re-run is a silent no-op — the
  #846/#848/#952/#999 precedent: applied statement-by-statement
  against live D1). **Both** builds that touch these tables carry the
  migration as
  a pre-deploy step (#968 for `push_subscriptions`; #990 for the
  other three) — the second apply is a no-op. The conditional
  "whichever build is first carries it" is deliberately rejected:
  "first" is knowable only in hindsight, so each build assuming
  the other is first leaves the tables uncreated, and code
  deploying before its migration writes to missing tables. The
  migration file lives in the control-plane workspace next to
  `migrate_958_s4b.sql`; this doc is its contract.
- 90-day retention + GC for all four tables is filed follow-up #1058
  (the #999 precedent filed #1013 for `phone_home_events`), not
  part of this migration. Budget buckets older than the current
  hour are never read; digest rows older than 90 days are never
  read.

## 5. Open product question (carried, not settled)

#988's issue body requires this slice to carry, not silently
settle: **subscription UX scope — per-box opt-in vs per-owner
default.** The schema supports either (rows exist only where the
owner subscribed; D3's fanout key is `(owner_principal, box_id,
*)` either way). Per-box opt-in is the conservative option (no
surprise buzzes; the #428 email fallback covers cold start);
per-owner default is the activation-friendly option (every new box
pages until the owner opts out — louder, and the D10 budget is the
backstop). The #968 build adopts one and records it; this contract
does not pre-decide it.

## 6. What's next

- **#990 (shipped, PR #1060):** the enqueue API, the
  atomic D10 check-and-increment over both scopes together, the
  first-page path, the digest enqueue split — implemented against
  §§1.2–1.4; carries `migrate_967_push.sql` as a pre-deploy step
  (D49 — both builds carry it).
- **#968 (owner subscription surface):** owner-auth subscribe /
  unsubscribe on the plane + the dashboard affordance — implemented
  against §1.1 and the D45/D46 custody rules; carries
  `migrate_967_push.sql` as a pre-deploy step (D49 — both builds
  carry it).
- **#967 stays OPEN** (send-path #989 shipped; enqueue #990 and
  surface #968 remain). **#849 stays OPEN** (the phone-approval
  loop's buzz leg).

Pointer comments on #967 and #849 carry this contract's location.
