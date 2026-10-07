# Phone-home wire protocol (S3 contract for #847)

The S3 contract for #847 (one Durable Object per box + outbound WSS
phone-home): the wire the box and the plane speak on the persistent
socket. S4 (plane DO class + upgrade handler) and S5 (box WSS client +
reconnect loop) build against this; S6 verifies against it.

Pinned to `main` at the merge of PR #940 (2026-10-03) and to the control
plane as documented in `docs/CONTROL_PLANE_API_REFERENCE.md`,
`docs/DURABLE_COMMANDS.md` (#848), and `docs/PHONE_HOME_GAP_ANALYSIS.md`
(§5 wire-protocol sketch). Decisions here supersede the sketch where they
differ — the sketch was reserved shape, this is the contract.

## 1. Scope and non-goals

- **In scope:** the upgrade handshake, authentication presentation, the
  frame-class registry, keepalive, the close taxonomy, the
  generation-vs-epoch decision, one-DO-per-box addressing, WSS↔HTTPS
  fallback and liveness precedence, the journal events the DO emits, and
  the S6 acceptance checklist.
- **Out of scope (owned elsewhere):** the box's persistent-process shape
  and reconnect-loop internals (S5, G47.1/G47.6); the DO implementation
  (S4); the stream/input frame payloads (#853/#919); the durable command
  payload semantics (#848); desktop media and input (the #854 SFU lane —
  never this channel); the approval consent wire (#849 — approvals are the
  consent plane, never the transport).

## 2. Upgrade handshake and authentication (G47.3)

- The box opens `wss://<plane>/v1/boxes/{box_id}/phone-home` (path
  pinned by #958 S4a, deployed live 2026-10-04; see §7).
- The box presents the **box Bearer <redacted> in the `Authorization`
  header of the upgrade request** — the same credential the heartbeat
  path uses (#844/#846). The credential **never travels in a message
  frame** and is **never written to any log or journal** (G47.3).
- The plane MUST NOT redirect the upgrade path, and the box MUST NOT
  follow redirects for the upgrade — any 3xx is an upgrade failure (fall
  back to HTTPS, §8). A redirect-following client could otherwise forward
  the `Authorization` header cross-origin.
- The plane validates the token *before* completing the upgrade, and
  routes on the verified identity: **the Worker MUST derive the DO stub
  name via `idFromName` from the token's `box_id`; the URL `{box_id}` is
  a routing hint only and MUST NOT select the stub** (G47.5 — the stub
  name comes from the verified identity, never a client-supplied path
  id; path/token disagreement therefore cannot mistarget a DO).
- Token states at upgrade, aligned with the runbook's failure-code
  table (`docs/HOSTED_AUTH_OPERATOR_RUNBOOK.md` — one code, one operator
  action, and no token-state oracle for unauthenticated probers):
  unknown, expired, or revoked (`revoked_at` set, #846) → `401`. The
  #846 15-minute previous-token grace is honored at the upgrade exactly
  as on the heartbeat path. These are plain HTTP responses, not socket
  closes — no socket ever exists for an unauthenticated box.
- **Box behavior on upgrade `401`:** the box MUST NOT reconnect-loop.
  If it holds no live token it MAY attempt one
  `POST /v1/boxes/token/rotate`; rotate-`401` → print re-pair guidance
  and exit (re-pair is the human path); rotate-`403` → check clock skew
  (±300 s, do NOT re-pair), per the runbook.
- **Identity binding:** the handshake identity (token → box_id) is
  authoritative. The `hello` frame's `box_id` self-assertion MUST equal
  it; mismatch → the DO closes the socket with the control frame
  `{"type":"close","generation":N,"code":"identity-mismatch"}` and
  journals the event.

## 3. Frames

JSON text frames (UTF-8), one object per frame. Every frame carries the
session fence field (§5) except where a class explicitly opts out —
none do today.

### 3.1 Control frames (#847's own class)

| `type` | Direction | Fields |
|---|---|---|
| `hello` | box→DO | `box_id`, `generation` |
| `welcome` | DO→box | `box_id`, `accepted_generation`, `server_time` |
| `ping` / `pong` | both | `generation`, `ts` (unix seconds) |
| `close` | both | `generation`, `code`, `reason` (human-readable, never a secret; optional) |
| `command_ack` | box→DO | `generation`, `seq`, `epoch` — S5b decision (§3.3): the box acks over the socket; the HTTPS `/commands/ack` endpoint stays as the fetch path's ack; the DO consumes both into the same `acked_watermark` |

Control frames MUST be ≤ 4 KB. Unknown `type` values are ignored
(forward compatibility), except `hello` shape violations, which close
the socket with `protocol-error`.

### 3.2 The frame-class registry (reserved, no collisions)

The WSS channel is shared by design — every class below rides the same
socket, namespaced by `type`. This registry is the collision guard; a
new class needs a row here before any frame of its type may be sent.

| Class | `type` values | Owner | Notes |
|---|---|---|---|
| control | `hello`, `welcome`, `ping`, `pong`, `close`, `command_ack` | #847 (this doc) | §3.1; `command_ack` rides the socket per the S5b decision (§3.3) |
| command | `command` | #848 | Reserved shape §3.3; payload semantics are #848's lane |
| terminal stream | `stream_open`, `stream_data`, `stream_close` | #853 / #919 | Real-time, lossy, ordered-per-session, never acked; stream bytes MUST NEVER ride the at-least-once command queue (G53.2) |
| input | `input` | #853 / #919 | Dedicated input frame class (G53.2(a)): owner-typed bytes and programmatic input; approval is the consent plane (#849), the bytes ride here |
| — | *(approvals decisions)* | #849 / #873 | NOT a WSS frame class: approval decisions travel the durable channel; reserved against so nobody invents a second decision wire |
| — | *(desktop media/input)* | #854 | Never this channel: media and desktop input ride the SFU DataChannel |

All stream and input frames MUST carry the `generation` field: the DO's
old-generation fence (§5) applies to every class, so a stale socket can
never inject bytes into a live session.

### 3.3 Command frames (reserved shape — #848 finalizes)

`{"type":"command","generation":N,"seq":S,"epoch":E,"payload":{...}}`

- `seq`/`epoch` are #848's per-box sequence and incarnation epoch;
  payloads are opaque to the plane (≤ 16 KB, verbatim).
- The same table/seq/epoch semantics as `docs/DURABLE_COMMANDS.md` are
  transport-agnostic: the socket is a faster carrier for the same queue,
  not a second queue.
- **Ack decision (S5b, #976, box client):** `command_ack` frames ride the
  socket. The ack goes out on the same authenticated session that
  received the command (no extra TLS handshake per command), carries the
  session's `generation` so the DO can reject acks from a stale session
  by the same fence, and lands directly in the queue-owning DO instead
  of traveling through the durable table first. The existing HTTPS
  `/commands/ack` endpoint stays as the fetch path's ack — the DO
  consumes both into the same `acked_watermark`. Ack-loss recovery is
  identical either way: the command redelivers and the box dedupes by
  `(box_id, seq)`. The queue contract is unchanged either way.
- **Re-drive rendezvous:** on (re)bind the DO re-drives from the durable
  queue's `acked_watermark` — it owns the queue, so it knows where to
  resume pushing; the box dedupes redeliveries by `(box_id, seq)` per
  #848. No cursor travels in `hello`.
- **Malformed command-row policy (D-MAL1, 2026-10-07, #1118):** the
  pinned policy is skip-and-log for both carriers. A row that fails the
  box-side shape check — not a dict, or a missing/mistyped `seq`,
  `kind`, or `payload`, or a mistyped `epoch` (the check
  `_ingest_command_shape` performs) — is the plane's bug: it is never executed, and never
  acked — the row failed shaping, so the box cannot trust any of its
  fields (including its `seq`). The box logs it LOUDLY on the box's
  ingest log (stderr + `ingest.log`) — the same loud channel that
  reports all ingest failures — and the queue flows past it: a plane
  data bug must not wedge the durable queue, because revocations and
  decisions must keep moving (the `docs/DURABLE_COMMANDS.md` "Plane
  bugs" liveness principle — a single bad row never wedges the queue
  behind a version skew — applied here as skip-without-ack: the cursor
  advances past the row instead of acking it, unlike unknown kinds,
  which the reference implementation acked-and-logged). The
  DURABLE_COMMANDS.md fail-closed carve-out governs well-formed rows
  of security-effect kinds; it cannot apply here because a malformed
  row has no valid kind to route on — which is why skip-and-log, not
  per-kind fail-closed, is the policy for unparseable rows. On the
  HTTPS path the row drops out of redelivery once the cursor advances
  past its seq (the loud log is the only record). KNOWN DIVERGENCE —
  **CLOSED by the S4b-2a pin below (2026-10-07, #1001):** the socket
  carrier's re-drive now skips malformed rows per D-MAL1 (never
  emitted, journaled LOUDLY as `phone_home.redrive_malformed`)
  instead of holding its per-session acked prefix; socket and HTTPS
  carriers are aligned on malformed rows.

- **S4b-2 implementation pin (2026-10-07, #1001 slice 2a):** the plane
  DO's re-drive (on every (re)bind, and on the D15 Worker→DO wakeup
  RPC after each enqueue) reads the acked watermark (`MAX(seq)` over
  `state='acked'` — no second cursor) and emits `command` frames in
  seq order for current-epoch rows (`epoch` equal to the session's
  accepted generation, §5) with `seq > watermark`, stamping
  leases exactly as the HTTPS fetch path does (per-row conditional
  UPDATE, `MAX_PENDING_FETCH` cap per pass; see
  `docs/DURABLE_COMMANDS.md`'s lease-stamping contract). A (re)bind never expires
  in-flight commands — only epoch claims do. Malformed rows are
  skipped on the re-drive (never emitted) and journaled LOUDLY as
  `phone_home.redrive_malformed` (code = seq); every re-drive pass —
  including the no-bound-socket wakeup no-op — journals
  `phone_home.redrive` (code = frames emitted). The D15 wakeup rides
  an internal, never-publicly-routable RPC
  (`/internal/commands-wakeup` on the box's stub): no bound socket →
  no-op; enqueue-succeeds/wakeup-fails → the Worker retries once,
  bounded and loud (the loud channel is the Worker's operational log —
  a wakeup that never reaches the DO cannot appear in the DO's
  `phone_home.redrive` journal), degrading to fetch-path latency, never
  loss; a wakeup racing a (re)bind may double-emit, absorbed by
  at-least-once + the box's `(box_id, seq)` dedup + the conditional
  lease stamp. A re-drive pass that throws journals
  `phone_home.redrive` with code `-1` and keeps the bind: transient
  bind-path throws (e.g. socket write) are covered by the next wakeup
  or fetch poll, but a throw in the shared queue-read re-throws
  identically on wakeup — the wakeup is not a backstop for read-path
  throws. After 3 consecutive `-1` journals the DO closes the bind,
  engaging §8's fetch-path fallback (degrading to fetch-path latency,
  never loss): a queue-read failure is never session-fatal, and the
  `-1` streak in the journal is the operator-visible signal. The
  socket `command_ack` consume-half is slice 2b (still open): slice 2b
  MUST record each consumed socket `command_ack` into the same
  watermark source the re-drive reads (`state='acked'` on the row, so
  the derived `MAX(seq)` watermark advances) — §3.3's S5b text ("lands
  directly in the queue-owning DO instead of traveling through the
  durable table first") describes the fast path only; durability still
  flows through the table. Until 2b lands, the watermark advances only
  via HTTPS acks, so `phone_home.redrive`'s emitted-count overstates
  *new* deliveries after lease expiry — at-least-once + box-side
  dedup absorb the re-emissions.

## 4. Keepalive

- The box sends `ping` every 30 s; the DO MAY send `ping` on its own
  schedule. Either side answers `pong` promptly.
- No `pong` within 90 s of a `ping` → the DO hibernates the socket
  (wake on the next box connect or inbound frame). **Absence of
  keepalive never fabricates liveness** — a silent socket is a dead
  socket for operational purposes, and liveness itself is §8's rule, not
  this section's.

## 5. Generation vs epoch (the G47.4 decision)

The sketch reserved one field; the contract uses **two separate
counters** with separate semantics:

- **`generation`** — the *network-session* fence. Box-chosen monotonic
  counter, bumped on **every fresh connect** (never on resume — there is
  no resume; see §11 item 3). Sharing one field would conflate a
  transport reconnect with a command-incarnation change, and a plain
  reconnect must never kill in-flight commands — hence two counters.
  The box MUST persist it in durable local storage so a reboot never
  reuses a value. The DO keeps `last_generation` in **DO durable
  storage** (hibernation/eviction wipes memory; a restarted DO must not
  accept stale generations).
- Fence rules: frames with `generation < last_generation` are dropped
  and journaled; **the DO MUST drop frames arriving on any socket other
  than the currently bound socket**. A `hello` with
  `generation > last_generation` binds the new socket, and the DO sends
  `close`/`superseded-generation` to the old one. A `hello` with
  `generation <= last_generation` (counter loss, or a reconnect that
  forgot to bump) gets `close`/`stale-generation` carrying
  `last_generation` — never `protocol-error` (which would wedge the box):
  the box MUST adopt `last_generation + 1`, treat it as counter loss
  (bump epoch per the rule below), and reconnect.
- **`epoch`** — the *command-incarnation* fence (#848). Bumped on
  reboot, reprovision, or counter loss — **not** on a plain transport
  reconnect. Rides command frames only; kills stale commands per
  `docs/DURABLE_COMMANDS.md`.

They do not share the field. A reboot bumps both (new incarnation AND
new session); a reconnect bumps generation only. Counter loss on the
box is a reboot-equivalent: the box MUST bump epoch too, per #848's
"claim a higher epoch" rule.

## 6. Close taxonomy

The `close` control frame's `code`:

| `code` | Meaning | Box behavior |
|---|---|---|
| `revoked` | box token revoked mid-socket (#846 `revoked_at`) | Fall back to HTTPS (§8); MUST NOT reconnect-loop — HTTPS will 401 → print re-pair guidance and exit (re-pair is the human path) |
| `expired` | box token expired mid-socket | Reconnect with the box's current token (a post-rotation socket riding the previous token lands here once the 15-min grace lapses — do NOT rotate again, just use the current token); if the box holds no live token, attempt one rotate; rotate-`401` → follow the `revoked` row; rotate-`403` → check clock skew (±300 s), do NOT re-pair |
| `superseded-generation` | a newer generation bound this DO | Normal: the old socket is dead by design; the box keeps the new one and MUST NOT reconnect the old one |
| `stale-generation` | `hello` arrived with `generation <= last_generation`; carries `last_generation` | Adopt `last_generation + 1`, treat as counter loss (bump epoch, §5), reconnect |
| `identity-mismatch` | `hello`'s `box_id` ≠ handshake identity | Bug — fix the client; MUST NOT auto-reconnect |
| `protocol-error` | malformed control frame | Bug — fix the client; MUST NOT retry the malformed frame in a loop |
| `going-away` | plane shedding or shutting down | Back off ≥ 60 s before reconnecting (§10) |

Plain WebSocket `1000`/`1001` closes without a control frame are
transport-level only and carry no protocol meaning.

**Revocation latency bound:** for a compliant box the bound is the 30 s
ping interval — the next inbound frame closes `revoked`. The DO MUST
also wake on a bounded interval via alarm (S4-chosen, ≤ 15 min
recommended, recorded in the S4 design) and re-verify the bound token's
`revoked_at`/`token_expires_at` on every wake: a hibernated socket is
re-verified before any further frame is accepted (G47.3). The
revocation-latency ceiling for a silent socket is that wake interval.

## 7. One DO per box, no leakage (G47.5)

- DO id is derived from the box id only: `phone-home:<box_id>`, where
  the box id is the **token's** `box_id` — the worker verifies the token
  before routing and derives the stub name via `idFromName` from it (§2).
- **Implemented 2026-10-04 (#958 S4a):** the plane serves
  `GET /v1/boxes/{box_id}/phone-home` — the §2 upgrade entry point,
  deployed live to the hosted control plane. The token is classified by
  the shared box-token classifier, so the upgrade path shares the exact
  revoked/grace logic with no drift; unknown, expired, or revoked tokens
  get one undifferentiated HTTP 401 (no socket, no redirect, no
  token-state oracle); the 15-minute rotation grace is honored; an
  authenticated non-upgrade request gets 426. The stub name is
  `idFromName("phone-home:" + box_id)` from the **token's** `box_id` —
  the URL id is a routing hint only and cannot mistarget a DO. The
  `BoxDO` class accepts the socket and holds it; session logic
  (hello/identity binding, generation fence, re-drive, ping/alarm
  revocation re-verify, journal) is the S4b slice. The contract is
  plane-neutral — self-hosted planes implement the same §2 entry point.
  Live-verified: 101 on a proper handshake, 401/426 paths,
  verification's test registry rows removed.
- **Implemented 2026-10-05 (#1000 S4b-1):** the `BoxDO` now runs the §2
  hello handshake and the §5 generation fence, deployed live to the
  hosted control plane. The hello's `box_id` self-assertion must equal
  the handshake identity re-derived from the upgrade `Authorization`
  header (mismatch → `close`/`identity-mismatch` + journal; malformed
  hello → `close`/`protocol-error`); `generation > last_generation`
  (DO durable storage) binds the new socket and closes the old one
  `superseded-generation`; `<= last_generation` →
  `close`/`stale-generation` carrying `last_generation` (never
  `protocol-error`), then `welcome` with `accepted_generation`. Every
  subsequent frame is fenced before the unknown-`type` ignore
  (`generation < last_generation` → drop + journal
  `phone_home.generation_fence`); frames on a non-bound socket are
  dropped; control frames over 4 KB are refused before parsing (§3.1);
  transport close journals `phone_home.disconnect`. Implementation note
  for self-hosted planes: workers-py requires socket listeners wrapped
  in `pyodide.ffi.create_proxy` — a raw Python callable registered with
  `addEventListener` is silently never invoked. The proxy must also be
  **retained** for the socket's lifetime (e.g. a per-socket list pruned
  on close): Pyodide destroys a proxy once Python drops its last
  reference, which silently detaches the listener mid-session — the same
  silent-failure class as the unwrapped callable. Live-verified against
  the deployed plane 2026-10-05 ~15:2x CDT
  (`control-plane/live_smoke_1000.py`, 12/12 checks: hello → welcome
  with `accepted_generation`, newer-generation supersede binding the
  new socket with `close`/`superseded-generation` on the old one,
  stale-generation close carrying `last_generation`, connect rows in
  D1; test box + journal rows deleted
  afterwards).
- A DO binds exactly one box: the handshake identity at first connect.
  It never routes a frame to another stub.
- Defense in depth: every frame's effective identity is the bound
  handshake identity, never a frame field.

## 8. Fallback and liveness precedence (G47.8)

- The box **prefers WSS** when egress allows it. On socket loss, or
  where WSS egress is blocked, the box falls back to the interim HTTPS
  path: the #864 cron heartbeat plus `GET /commands/pending` polling.
  The fallback is always available and MUST be exercised (S6), not
  assumed.
- **Liveness authority:** the plane's last-confirmed-heartbeat timestamp
  (the HTTP `200 {ok:true}` the #864 sender keys off) is the ONLY
  freshness signal the fleet dashboard's staleness chips may use.
  The socket MUST NOT write or refresh it. Socket connect/disconnect
  are operational signals (journal, §9-facing ops) — they never make a
  box "live" and their absence never makes it "dead" beyond what the
  heartbeat already says.
- Rationale: a socket the plane accepted is not proof the box is
  healthy (the DO can't see the box's load, disk, or agent state); the
  heartbeat's explicit `uptime_s`/`load_1` body is. Letting the socket
  refresh freshness would let a wedged-but-connected box look alive —
  the exact fake-liveness class #864 was built to refuse.

## 9. Journal events (G47.7)

The DO emits into the fleet event journal (no payloads, no tokens, no
frame contents):

- `phone_home.connect` — `box_id`, `generation`, `server_time`
- `phone_home.disconnect` — `box_id`, `generation`, close `code`
- `phone_home.hibernate_wake` — `box_id`, `generation`, wake cause
  (alarm tick vs inbound frame); S6 observes hibernation through this
- `phone_home.generation_fence` — dropped stale-generation frames
  (`box_id`, `seen_generation`, `last_generation`)
- `phone_home.revoked_kill` / `phone_home.expired_close` —
  credential-lifecycle closes
- `phone_home.identity_mismatch` — handshake/frame identity conflict
- `phone_home.redrive` — re-drive pass (`box_id`, `generation` —
  NULL when unbound, e.g. the no-bound-socket wakeup no-op); `code` =
  frames emitted as decimal, `-1` on re-drive-pass throw (bind kept;
  3 consecutive `-1`s close the bind — §3.3)
- `phone_home.redrive_malformed` — malformed row skipped on the
  re-drive (`box_id`, `generation` — NULL when unbound); `code` = the
  malformed row's `seq` as decimal

Pre-handshake upgrade `401`s are not DO journal events — no DO exists
yet and the prober is unattributable; upgrade auth failures are the
Worker entrypoint's lane (S4 may keep an unattributed counter there).

Staleness chips stay heartbeat-driven (§8); these events are the
operational trail, not the liveness signal.

### Sink (S4b-4)

The journal is the D1 table `phone_home_events` (migration
`migrate_958_s4b.sql`, re-run safe):

| column | meaning |
|---|---|
| `box_id` | owning box |
| `event` | one of the names above — the plane's journal helper is the only writer and raises (fail-closed) on anything else |
| `generation` | bound generation for `connect` / `disconnect` / `hibernate_wake` / `revoked_kill` / `expired_close` / `redrive` / `redrive_malformed`; for `generation_fence` this is the **kept** generation; NULL when unbound (connect is unbound until S4b-1 binds the fence; `redrive` is unbound on the no-bound-socket wakeup no-op) |
| `seen_generation` | only `generation_fence`: the dropped stale generation |
| `code` | TEXT: close code as decimal (`disconnect`) or wake cause (`hibernate_wake`); frames emitted as decimal or `-1` on throw (`redrive`); malformed row's `seq` as decimal (`redrive_malformed`); NULL otherwise |
| `server_time` | unix seconds, plane clock |

Owner read path: `GET /v1/boxes/{id}/phone-home/events` (`limit`,
default 50 / max 200; `since` unix-seconds cursor), newest-first; the
response also carries the unattributed `upgrade_401s_7d` series (the
probe counter from the paragraph above). A box token is explicitly
refused on this path — a box cannot read its own journal. Retention:
90 days — enforced by a daily Worker cron cleanup (03:17 UTC) plus an owner-run
`POST /v1/ops/phone_home/gc` manual trigger (owner-only; a box token is
explicitly refused, mirroring the read path). The unattributed
upgrade-401 day buckets older than 7 days are deleted, matching the read
path's 7-day series. Cleanup runs are visible in the plane Worker's logs; the manual
endpoint returns the deleted-row counts. (#1013)

## 10. Box-side wire constraints (G47.6)

- The wire is plain RFC 6455 over TLS (wss). The stdlib-only client
  decision (G47.6) lives in S5; this contract constrains it to: no
  third-party framing dependencies required, JSON text frames only, and
  the §5 durable-generation requirement.
- Reconnect backoff (box): 1 s initial, doubling, 60 s cap, ±25% jitter.
  The DO MAY shed with `going-away` if connects exceed ~1 per 5 s per
  box; the box MUST then wait ≥ 60 s.
- The box MUST NOT auto-reconnect on `revoked` (fall back to HTTPS;
  re-pair is the human path).

## 11. S6 acceptance checklist

S6 verifies, against a live plane, on this contract:

1. **Two boxes, distinct stubs, no cross-talk:** two boxes connect;
   each DO binds its own `box_id`; a frame sent on box A's socket never
   surfaces on box B's stub (journal + stub-id assertion).
2. **Revoke-during-socket:** revoke box A's token mid-socket; the DO
   closes `revoked` on next inbound/wake; box A falls back to HTTPS,
   gets `401`, prints re-pair guidance; no reconnect storm.
3. **Reconnect-resume clean:** box reconnects with `generation+1`;
   the old socket gets `superseded-generation`; pending commands
   re-drive off the durable-queue cursor (no loss, no double-execution
   beyond #848's at-least-once contract).
4. **Stale-generation fence:** a replayed frame with an older
   generation is dropped + journaled (`phone_home.generation_fence`).
5. **Fallback honored:** kill the socket AND block WSS egress; the box
   keeps heartbeating and polling commands over HTTPS; staleness chips
   stay honest throughout.
6. **Epoch untouched by reconnect:** plain reconnects never bump epoch;
   a reboot bumps epoch and kills in-flight commands per #848.

## 12. Open questions for S4/S5 (not blocking this contract)

- Exact upgrade path spelling — PINNED by #958 S4a, deployed live
  2026-10-04: `GET /v1/boxes/{box_id}/phone-home` (see §7 note).
- Ack transport — DECIDED by S5b (#976): `command_ack` frames ride the
  socket (rationale in §3.3); S4 implements the DO-side consume half.
  (Was: socket vs HTTPS, queue contract identical either way.)
