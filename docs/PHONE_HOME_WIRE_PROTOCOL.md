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

- The box opens `wss://<plane>/v1/boxes/{box_id}/phone-home` (exact path
  is the plane workspace's to finalize; the contract is the handshake,
  not the path spelling).
- The box presents the **box Bearer <redacted> in the `Authorization`
  header of the upgrade request** — the same credential the heartbeat
  path uses (#844/#846). The credential **never travels in a message
  frame** and is **never written to any log or journal** (G47.3).
- The plane validates the token *before* completing the upgrade:
  unknown token → `401`; expired token → `401`; revoked token
  (`revoked_at` set, #846) → `403`. These are plain HTTP responses, not
  socket closes — no socket ever exists for an unauthenticated box.
- **Identity binding:** the handshake identity (token → box_id) is
  authoritative. The `hello` frame's `box_id` self-assertion MUST equal
  it; mismatch → the DO closes the socket with the control frame
  `{"type":"close","code":"identity-mismatch"}` and journals the event.
  A `box_id` in the URL path that disagrees with the token is ignored in
  favor of the token.

## 3. Frames

JSON text frames (UTF-8), one object per frame. Every frame carries the
session fence field (§5) except where a class explicitly opts out —
none do today.

### 3.1 Control frames (#847's own class)

| `type` | Direction | Fields |
|---|---|---|
| `hello` | box→DO | `box_id`, `generation` |
| `welcome` | DO→box | `box_id`, `accepted_generation`, `server_time` |
| `ping` / `pong` | both | `ts` (unix seconds) |
| `close` | both | `code`, `reason` (human-readable, never a secret) |

Control frames MUST be ≤ 4 KB. Unknown `type` values are ignored
(forward compatibility), except `hello` shape violations, which close
the socket with `protocol-error`.

### 3.2 The frame-class registry (reserved, no collisions)

The WSS channel is shared by design — every class below rides the same
socket, namespaced by `type`. This registry is the collision guard; a
new class needs a row here before any frame of its type may be sent.

| Class | `type` values | Owner | Notes |
|---|---|---|---|
| control | `hello`, `welcome`, `ping`, `pong`, `close` | #847 (this doc) | §3.1 |
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
  not a second queue. Acks still flow (as `command_ack` control-class
  frames or the existing HTTPS ack endpoint — S4/S5 choose; the queue
  contract is unchanged either way).

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
  no resume, §9). The box MUST persist it in durable local storage so a
  reboot never reuses a value. The DO keeps `last_generation` in **DO
  durable storage** (hibernation/eviction wipes memory; a restarted DO
  must not accept stale generations). Frames with
  `generation < last_generation` are dropped and journaled; a connect
  with `generation > last_generation` binds the new socket and the DO
  sends `close`/`superseded-generation` to the old one.
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
| `revoked` | box token revoked mid-socket (#846 `revoked_at`) | Fall back to HTTPS (§8); do NOT reconnect-loop — HTTPS will 401 → re-pair guidance (same as #864) |
| `expired` | box token expired mid-socket | Rotate via `POST /v1/boxes/token/rotate` (#846), then reconnect with a fresh generation |
| `superseded-generation` | a newer generation bound this DO | Normal: the old socket is dead by design; the box keeps the new one |
| `identity-mismatch` | `hello`'s `box_id` ≠ handshake identity | Bug — fix the client; journal the event |
| `protocol-error` | malformed control frame | Bug — fix the client |
| `going-away` | plane shedding or shutting down | Back off ≥ 60 s before reconnecting (§10) |

Plain WebSocket `1000`/`1001` closes without a control frame are
transport-level only and carry no protocol meaning.

**Revocation latency bound:** the DO closes `revoked` on the next
inbound frame or hibernate wake — whichever comes first. Worst case is
the wake interval; this is the documented ceiling (same discipline as
the input-lease revocation bound in the #854 analysis), not a hole.

## 7. One DO per box, no leakage (G47.5)

- DO id is derived from the box id only: `phone-home:<box_id>`.
- A DO binds exactly one box: the handshake identity at first connect.
  It never routes a frame to another stub and never accepts a second
  box's token (a token for a different `box_id` fails the binding check
  → `403` at upgrade).
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
- `phone_home.generation_fence` — dropped stale-generation frames
  (`box_id`, `seen_generation`, `last_generation`)
- `phone_home.revoked_kill` / `phone_home.expired_close` —
  credential-lifecycle closes
- `phone_home.identity_mismatch` — handshake/frame identity conflict

Staleness chips stay heartbeat-driven (§8); these events are the
operational trail, not the liveness signal.

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

- Exact upgrade path spelling (plane workspace).
- Whether acks ride the socket (`command_ack` frames) or stay HTTPS —
  the queue contract is identical either way (§3.3).
- DO hibernate wake interval (sets the §6 revocation-latency ceiling).
