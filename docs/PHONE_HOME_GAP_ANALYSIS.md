# Phone-home gap analysis: one Durable Object per box + outbound WSS (#847)

**Vision vs current state.** Statuses pinned to this repo at the merge of
PR #863 (box Bearer <redacted> rotation client), and to the `sparkvm-control`
Cloudflare Worker — the plane lives outside this repo, so plane-side facts
below are pinned to a 2026-10-02 read of it, not to a repo commit.
Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below is
**current state and work to do**, not promises.

## 1. The vision (#847 — settled control-plane architecture)

> One Durable Object per box owns the hibernating WebSocket, command queue,
> connection generation, and viewer sockets. Boxes connect outbound-only
> (HTTPS now, box-initiated WSS next) — no inbound ports, ever.

Acceptance: the box initiates and maintains a WSS connection to its Durable
Object; the socket hibernates correctly; reconnects resume cleanly; one DO
per box; no cross-box state leakage.

## 2. Current state

| Vision element | Current state |
|---|---|
| Box→plane transport | **HTTPS POST polling only.** Pairing endpoints + `POST /v1/boxes/{id}/heartbeat` (box Bearer <redacted>, JSON status → `{ok:true}`). No persistent connection anywhere. |
| Plane WebSocket | **Nothing.** `worker.py` is a plain Workers-Python Worker (D1-backed) with no WebSocket upgrade handler, no DO class, no `durable_objects` binding and no migration anywhere in the plane workspace. |
| Box-side client | `pairing/` (stdlib-only: ed25519, `init`/`request`/`redeem`/`rotate`/`revoke`). **No heartbeat sender exists in this repo** — the plane's heartbeat contract has no in-repo producer; no box long-lived process at all. |
| Token auth for the channel | Heartbeat verifies `sha256(token)` against `boxes.token_hash`; #843 owner keys gate fleet reads. #846 slice 1 shipped the repo rotation client; the **plane half is outstanding** (no rotate/revoke endpoints, no `revoked_at` on `boxes` — expiry is already enforced at heartbeat today via 401 "token expired"; what's missing is plane-side re-issuance and revocation). |
| Connection generation / epochs | **Nothing.** #848's durable commands (seq, acks, lease expiry, epochs) presuppose a channel that can carry an epoch handshake. |
| No cross-box leakage | N/A — no shared-state component exists to leak through; the addressing rule must be designed, not verified. |
| Outbound-only invariant | Honored by construction today (all calls are box→plane HTTPS). The relay splice (`docs/RELAY_LIVENESS_DESIGN.md`) is the *other* path — tenant SSH via the control-plane relay — and its liveness producer (`connection-unreachable`) is relay-owned. **The phone-home DO is a different liveness source**: box↔plane connectivity vs tenant↔box connectivity. The two must never be confused in status surfaces. |

## 3. Gaps

- **`[BLOCKER]` G47.1 — no box-side long-lived process.** The phone-home
  client needs somewhere persistent to live, and today there is nothing: no
  heartbeat sender, no daemon, no reconnect loop. The #847 vision forces a
  persistent box-side process — a cron job cannot hold an open socket
  between invocations, and reconnect churn every minute would defeat the
  hibernation semantics the design is built on. That process shape (`boxd`
  or otherwise) is decided with the box WSS client (S5), not before.
  Separately, and independent of #847: the fleet dashboard's "stale" chips
  (`hosted/dashboard/`) are only as honest as whatever sends the
  heartbeats, and that sender is not in this repo. The interim HTTPS
  heartbeat sender *is* cron-acceptable — `spark_pair.py rotate --auto`
  already proves the cron-mode shape — and makes the dashboard honest
  whether or not #847 ever ships. Filed as new issue #864, scoped to the
  sender only (see §6).
- **`[BLOCKER]` G47.2 — plane has no WebSocket surface.** No upgrade
  handler, no DO class, no binding, no migration — and no wrangler config
  exists in the plane workspace at all, so S4 creates the deploy shape
  from zero (config, compatibility date, entrypoint), not just a binding.
  This is plane-workspace work (wrangler `durable_objects` +
  `migrations: new_classes`), with the contract pinned here. Risk note for
  S4: hibernation-API support in workers-py (`state.acceptWebSocket`,
  alarm-driven wake) is assumed, not verified — confirm before committing
  to the DO class shape.
- **`[PARTIAL]` G47.3 — auth story for the socket.** The heartbeat path
  proves the verification pattern (`sha256(token)` vs `token_hash`, like
  heartbeat, with the D1 JsNull gotchas documented in the plane header);
  the WS upgrade must do exactly that at handshake time, then enforce
  `token_expires_at` and (once #846's plane half lands) `revoked_at` on
  every reconnect. Short-lived rotation (#846) is what makes a long-lived
  socket's auth sane: a socket authenticated once must re-verify on resume
  after hibernation, or a revoked box's socket lingers.
- **`[DESIGN]` G47.4 — the phone-home wire protocol.** Frame shapes for:
  hello (box_id + presented generation), auth presentation (bearer at the
  upgrade handshake, per G47.3), ping/pong keepalive, close-code taxonomy,
  and the reconnect handshake that #848's epochs will build on — the
  protocol must reserve the generation/epoch field now so #848 doesn't
  re-handshake. See §5 sketch.
- **`[DESIGN]` G47.5 — one-DO-per-box addressing without leakage.**
  `idFromName(box_id)`; the stub name must be derived from the *verified*
  identity (the bearer token), never trusted from a client-supplied path
  id or frame field. The URL path `{id}` on the upgrade request is a
  routing hint, not an identity claim — re-derive and compare after auth.
- **`[DESIGN]` G47.6 — stdlib-only WSS client.** Python's stdlib has no WSS
  client; the box posture so far is stdlib-only (ed25519 hand-rolled in
  `pairing/ed25519.py`). Options: (a) hand-rolled TLS+WS handshake
  (brittle, matches posture), (b) vendored minimal client (auditable,
  dependency-free for the user), (c) a real `websockets`/`aiohttp` dep
  (best engineering, breaks posture, needs packaging story). The brittle
  part of (a) is the WS framing/handshake, not TLS (stdlib `ssl` handles
  that). Decide in the
  slice, not here.
- **`[OBSERVABILITY]` G47.7 — feed the fleet journals.** DO-side liveness
  events (connect, hibernate-wake, reconnect-with-new-generation, auth
  failure) should land in the fleet event journal (G16/G17 shape) so the
  P7 status page (G22) can render box↔plane connectivity honestly —
  distinct from the relay's `connection-unreachable` (tenant↔box path).
- **`[DESIGN]` G47.8 — WSS↔HTTPS fallback and liveness precedence.** When
  the socket is down — or the box's egress kills the WSS upgrade entirely —
  does the box fall back to HTTPS heartbeats, and which signal wins in the
  fleet journal and the P7 status page? A liveness channel with an undefined
  failure mode is a product gap, and for this feature it's load-bearing:
  G47.7's journal-feeding story is unbuildable without the precedence rule
  (socket events vs heartbeat freshness — which is authoritative when they
  disagree?). Feeds into S5/S6 acceptance: socket loss and egress-blocked
  WSS must be exercised, not assumed.

## 4. Slice plan (dependency order)

- **S1 — #846 plane half** (already tracked on #846): rotate/revoke
  endpoints, `revoked_at`, expiry stamping on re-issuance. The phone-home socket's auth
  can't be short-lived-safe before this; do not build S4 first.
- **S2a — interim HTTPS heartbeat sender** (new issue #864, §6): the
  missing in-repo heartbeat sender. Cron-acceptable and independent of
  #847; makes the fleet dashboard's staleness chips honest whether or not
  #847 ever ships.
- **S3 — phone-home wire protocol spec** (§5 → full spec): frames,
  auth presentation, keepalive, close codes, generation/epoch reservation
  for #848, and the G47.8 fallback/precedence rule. Contract pinned here,
  like #846's server-contract checklist.
- **S4 — plane DO class + upgrade handler** (plane workspace): binding,
  migration, hibernating WS, G47.5 addressing rule, G47.3 auth-at-handshake.
- **S5 — box WSS client + reconnect loop** (this repo): G47.6 decision,
  backoff, G47.4 reconnect handshake, the persistent-process shape (G47.1's
  `boxd` decision lives here), G47.8 fallback behavior. May run in parallel
  with S4 once S3 pins the contract — the S1→S6 order is a dependency order,
  not a schedule lock.
- **S6 — acceptance verification**: one DO per box (two boxes, distinct
  stubs, no cross-talk), revoke-during-socket (socket dies on resume),
  reconnect-resume clean, generation bump kills stale commands (feeds #848),
  fallback honored under socket loss and egress-blocked WSS (G47.8).

## 5. Wire-protocol sketch (reserved shape, not final)

JSON text frames over the WSS channel. Authentication happens at the
upgrade handshake (`Authorization: Bearer …`), per G47.3. The credential
never travels in a message frame and is never logged. `generation` is a box-chosen
monotonic counter bumped on every fresh connect (never on resume); the DO
keeps `last_generation` and drops frames from older generations — this is
the reserved slot #848's epochs may build on (the S3 spec decides whether
connection-generation and command-epochs share the field; the sketch only
reserves it). The fence itself must live in DO durable storage, not
memory — hibernation/eviction wipes in-memory state and a restarted DO
must not accept stale generations. (The counter needs durable box-side storage
to survive reboots — a sketch-level caveat the full S3 spec must resolve.)

| Frame | Direction | Fields |
|---|---|---|
| `hello` | box→DO | `box_id`, `generation` (identity already established at handshake) |
| `welcome` | DO→box | `box_id`, `accepted_generation`, `server_time` |
| `ping` / `pong` | both | `ts` (keepalive; absence drives hibernate, not fake liveness) |
| `close` | both | `code`, `reason` (taxonomy: `revoked`, `expired`, `superseded-generation`, `going-away`) |

Nothing above invents crypto: auth reuses the bearer verification the
heartbeat path already does. Command frames are #848's lane, not this doc's.

## 6. New backlog items filed by this analysis

- **New issue #864: interim HTTPS heartbeat sender** (G47.1/S2a) — the
  plane's heartbeat contract has no in-repo producer; the fleet
  dashboard's staleness rendering is only as honest as that sender. Scoped
  to the cron-acceptable HTTPS sender only, independent of #847 — the
  persistent-process shape for the WSS client lives with S5, not in #864.
- #847 stays the DO/phone-home tracker; the PR's pointer comment on #847
  carries the §4 slice plan and the §5 protocol sketch. S3–S6 are #847
  acceptance slices, not separate issues.

## 7. Honest summary

The settled architecture (#847) is a real step up from HTTPS polling, but
almost none of its machinery exists yet: no box long-lived process, no
plane WebSocket surface, no wire protocol, and the rotation endpoints the
socket's auth depends on are still outstanding (#846 plane half). The
dependency order is S1 → S2a → S3 → S4/S5 → S6; building the DO (S4)
before the rotation plane half (S1) would ship a socket whose auth can't
be revoked. The box side of today's heartbeat is the most immediate gap —
it should exist whether or not #847 ever ships.
