# Desktop session-plane design-ahead: vision vs state at main `8971129`

**Vision vs current state for the #935 session-plane build** — pinned to
spark-vm main `8971129` (2026-10-09) and a 2026-10-09 read of the deployed
`sparkvm-control` worker checkout (`worker.py`, migrations through
`migrate_agentid.sql`). This is the design-ahead pass over
`docs/DESKTOP_SFU_GAP_ANALYSIS.md` (pinned 2026-10-03, PR #922, slice S2 /
G54.2): what moved in the six days since the pin, what the #935 build still
needs pinned before it is built, and the two genuinely-new gaps the build
uncovered. #936 (box publisher) and #937 (dashboard viewer) are unchanged —
this doc does not re-open them.

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below
is **current state and work to do**, not promises. The hosted product is
not live. The plane lives outside this repo, so plane-side rows below are
the contract the plane must implement, not a description of what it does
today.

## 1. The vision, restated for #935

An owner opens a desktop session for one of their boxes from the dashboard
box-detail card. The plane — which owns all session state because the
Cloudflare Realtime SFU defines no rooms, presence, or roles — creates the
SFU session with the operator-provisioned app secret (worker env, never the
repo), records it in a D1 `desktop_sessions` table
(`session_id`, `box_id`, owner, SFU session/track ids, `created_at`,
`expires_at`, `revoked_at`), and hands the box a session handle: SFU
endpoint, publish credential, session/track ids, generation. The box publishes its `:98` capture (S3, #936); the
owner subscribes in the dashboard (S4, #937) and drives input over a
dedicated DataChannel class. Sessions expire, are revocable, and revocation
kills the SFU session — media *and* input atomically. Session ids are
server-derived from the verified box identity (the G47.5 pattern), never
client-supplied. Streaming usage is metered with a budget reservation at
request time (G54.6); session open/close/auth-failure events feed the fleet
journal (G54.7); the media-transits-Cloudflare trust call is documented
(G54.5).

## 2. What moved since the Oct-3 pin

- **F-S1 — the "Blocked on S1" line in #935's body is overbroad.**
  S1 (Realtime app provisioning) is still operator-owned (NEEDS_USER.md),
  but only the *SFU binding* waits on it. The session plane's registry,
  auth, revocation fanout, metering reservation, and journal feeding are
  all app-independent — §4 splits S2 into S2a (shippable now, stub SFU
  carrier) and S2b (the SFU binding). The Oct-3 analysis's "S2–S5 cannot
  ship without it" no longer holds for the plane half.
- **F-S2 — the signaling-carrier open question is closed, and the answer
  is the command channel, not a new frame class.** Oct 3 left "HTTPS
  polling now vs the #847 WSS channel later — do not block S2 on #847"
  undecided. The channel now exists: BoxDO holds the box's WSS socket
  (S4a #958's S4b-1..4 slices #1000/#1001/#1002 shipped; #958 itself
  stays open for S6 live acceptance), the D15 Worker→DO wakeup RPC
  (`/internal/commands-wakeup`, worker.py L1947) re-drives unacked work
  off the derived watermark, and `command_ack` frames ride the socket
  (S5b #976). Crucially, the wire spec's §3.2 reserved row establishes
  the governing principle: *"NOT a WSS frame class: approval decisions
  travel the durable channel; reserved against so nobody invents a
  second decision wire."* Session revocation is a security-effect
  decision — it travels the durable command channel as a new
  `session_revoke` kind, which already rides the socket fast path
  (generation-bound, epoch-fenced, at-least-once with `acked_watermark`,
  lease-stamped, HTTPS-fetch fallback). No new frame class is built;
  box→plane session liveness rides the existing heartbeat.
- **F-S3 — a new auth consumer exists: AgentID agent sessions.** #1225
  (deployed 2026-10-09T18:40:47Z) lets AgentID id_token holders read
  exactly `GET /v1/boxes` and `GET /v1/boxes/{id}` (the `AGENT_READ_ROUTES`
  allowlist, worker.py L1634; everything else stays owner-only). The Oct-3
  design predates this — §3 pins sessions as owner-key-only and invisible
  to agent sessions.
- **F-S4 — the plane surface is verified empty of session state.** No
  `desktop_sessions` table, no SFU code, no app secret anywhere in the
  deployed worker checkout (grep-verified 2026-10-09). The build starts
  from zero, against real primitives.
- **F-S5 — a liveness gate the Oct-3 design never named.** The revocation
  story requires a live control channel to the box. A session opened for a
  box with no live phone-home socket cannot be revoked within any bound —
  so opening it violates the revocation-latency acceptance. §3 pins the
  fail-closed gate.
- **F-S6 — the handle-at-rest discipline.** Session handles contain an SFU
  publish credential. The durable-command queue (`_ensure_approval_decision_command`,
  worker.py L4182 — `approval_decision` is the only command kind so far)
  persists commands in D1: handles must never be enqueued there. The
  credential-at-rest custody story (vend lane, G50.9) applies by analogy —
  handles are fetched, never stored plane-side beyond the session row.

## 3. Decisions pinned for the #935 build (D-S series)

- **D-S1 — session control is a command kind, not a frame class.**
  Plane→box session control travels the durable command channel as a
  new `session_revoke` kind — honoring the wire spec's §3.2 reserved
  row (*"NOT a WSS frame class: approval decisions travel the durable
  channel; reserved against so nobody invents a second decision
  wire"*). The kind gets everything commands already have for free:
  the socket fast path on (re)bind and D15 wakeup, generation binding,
  epoch fencing, at-least-once delivery with `acked_watermark`,
  lease stamps, and the HTTPS-fetch fallback. No new frame class is
  built in either direction — box→plane session liveness rides the
  existing heartbeat. Payload is `session_id` + `action` only: F-S6's
  no-credentials rule is pinned here explicitly, not implied —
  **no SFU publish credential ever rides a command** (the queue
  persists in D1). The S2a build adds the `DURABLE_COMMANDS.md`
  kind-registry row before the plane may enqueue it, with idempotency
  key `session_revoke:<box_id>:<session_id>`, the enqueue gate as the
  D-S5 `revoked_at` conditional-UPDATE winner (the write-once analog
  of `approval_decision`'s gate), and fail-closed unknown-client
  behavior per the registry's security-effect rule (not acked, run
  stops loudly — an old box never silently skips a revoke and keeps
  publishing). The box fetches its session *handle* (endpoint, publish
  credential, SFU ids) over a box-authenticated HTTPS endpoint — the
  #952 pattern, box Bearer <redacted> `current`/`grace` classes
  (worker.py L1764–1814) — because handles hold credentials and are
  pulled, never enqueued. The box reconciles active sessions on
  (re)connect via the handle fetch; on a new generation the standing
  command re-drive re-delivers unacked revokes.
- **D-S2 — sessions are owner-key-only and invisible to agent sessions.**
  Opening a session is a write (mints SFU credentials, accrues metered
  spend): it is refused to AgentID agent sessions by the same
  `_require_owner_or_agent` central gate #1225 added — no new identity
  primitive, no allowlist entry. There is no session-visibility endpoint
  for agents; `GET /v1/boxes` reveals nothing about sessions. The #1225
  dashboard-copy lesson applies: dashboard session JS ships in the same
  turn as the plane endpoints (repo companion, the #1226 pattern).
- **D-S3 — the reachability gate: open requires the box be reachable
  within the revocation bound.** The gate is keyed to *box
  reachability*, not socket presence: session-open requires the box be
  reachable via at least one carrier — a live socket **or**
  heartbeat-fresh per §8's liveness authority (the heartbeat, not the
  socket, is the liveness signal; "live socket" is also undefined
  under hibernation). The per-carrier revocation bound is pinned as a
  taxonomy, measured in the S2a build: socket carrier = the DO re-drive
  bound; fetch carrier = the heartbeat/fetch cadence. Revocation is
  *enforced* at the SFU delete (D-S5 step 2 — needs no box socket);
  the box signal is hygiene, deliverable at fetch-path latency for
  socketless boxes. This resolves the D-S1/D-S3 tension: the HTTPS
  handle fetch serves the reachable-but-socketless box (WSS-blocked,
  fetch-path-manageable per §8) — it is the second carrier, not a
  contradiction. If the product decision is "no desktop sessions for
  WSS-blocked boxes at all," that is a stated product call with the §8
  conflict acknowledged — this doc does not make it unilaterally.
- **D-S4 — metering reservation: #990's atomic pattern, applied.** The
  max-session-duration budget is reserved with a single-statement
  check-and-increment (the D10 atomic-reservation discipline from
  `hosted/push_enqueue.py`), released on session end, refused
  over-budget at request time. The usage-measurement *source* (Realtime
  usage API granularity vs duration×bitrate estimate — the plane never
  sees media bytes) stays the S2b build's decision against the live API.
- **D-S5 — revocation order: D1 first, SFU second, box signal third.**
  `revoked_at` is stamped first (the source of truth the dashboard reads);
  then the SFU session is deleted (media *and* input die atomically —
  one delete, not two); then the box signal fans out (socket + durable
  command per D-S1). A failed SFU delete retries with backoff against the
  already-stamped row — the dashboard never shows a revoked session as
  live. Box-side: stop publishing on session-gone *and* on socket loss
  (fail-closed, the S5 box acceptance), plus the box-honored max session
  TTL from the Oct-3 constraint. Named explicitly: revocation is
  *enforced* at the SFU delete — the box signal is hygiene, not the
  enforcement point.
- **D-S6 — journal: `phone_home_events` (D16), not G16/G17 — with the
  sink's own column discipline.** The S4b analysis (F-S4b-1) established
  that G16/G17 journals are box/operator-side; the plane's journal sink
  is `phone_home_events` (`migrate_958_s4b.sql`: `box_id`, `event`,
  `generation`, `seen_generation`, `code`, `server_time`). The sink is
  fail-closed on unknown event names (`_PHONE_HOME_JOURNAL_EVENTS`
  allowlist; worker.py L1844) and its column contract is *"no payloads,
  no tokens, no frame contents"* — there is no payload column, so the
  S2a build pins the encoding inside the existing schema: new event
  names `session.open` / `session.close` / `session.auth_failure`
  registered in the allowlist (an S2a build step); `code` carries the
  session id with the owner key id suffixed (`<session_id>
  owner=<key-id>` — key ids, never keys); the §9 "no tokens" rule is
  extended explicitly to "no SFU credentials, no Bearer <redacted>
  no owner keys — key ids only." Retention follows the table's 90-day
  rule (worker.py L1891).
- **D-S7 — the handle schema stays opaque and SFU-agnostic (Oct-3 pin
  kept).** Endpoint + publish-credential fields are opaque strings; in the
  S2a build they are empty-and-documented (S1-gated). A self-hosted SFU
  endpoint slots into the same schema — that is what keeps the S3
  publisher transport-agnostic enforceable rather than aspirational.
- **D-S8 — the S1 split (the headline).** S2a: D1 `desktop_sessions`
  schema, session CRUD endpoints, D-S2 auth, D-S1/D-S5 revocation fanout,
  D-S4 metering reservation, D-S6 journal events, the S2↔S3 handle schema
  — all against a stub SFU carrier, shippable and testable now. S2b: the
  real SFU binding (session creation via `rtc.live.cloudflare.com`,
  publish credentials, the subscriber→publisher DataChannel routing check
  *and* the SFU-delete atomicity check (one delete kills media *and*
  input — verified, not assumed) against the live Realtime API). S2a's
  acceptance is the full S2 acceptance minus the live-SFU rows.
- **D-S9 — the session names the input holder; #937 owns contention.**
  Session-open records the input mode (view-only / interactive) and the
  holder. The D1/D4 owner-vs-agent handoff rule is #937's build — #935
  only gives contention a session to arbitrate over, plus box-sourced
  input audit (the G54.3 pin).
- **D-S10 — generation binding comes from the command channel.** The
  `session_revoke` command is generation-bound like every command
  frame; a new generation re-delivers unacked revokes through the
  standing re-drive, and the box reconciles active sessions via the
  handle fetch on (re)connect. No separate re-announce mechanism.
- **D-S11 — epoch bumps do not kill sessions.** The durable-command
  epoch model kills in-flight commands on incarnation change, but
  sessions are D1 state, not command state: a box reboot (epoch bump)
  re-fetches its active sessions on reconnect and keeps publishing
  while the plane row is live (`revoked_at` NULL, `expires_at` in the
  future). Fail-closed stranding on every reboot would make sessions
  unusable on any box that restarts; the revocation path (D-S5) is the
  enforcement point, not the epoch.
- **D-S12 — `expires_at` is swept plane-side.** A plane-side sweeper
  marks sessions past `expires_at` as ended and releases the D-S4
  metering reservation — covering the box-dies-mid-session case where
  no close signal ever arrives. The box-honored max session TTL is the
  backstop, not the mechanism.

## 4. Slices

- **#935** stays the session-plane tracker. Its body's "Blocked on S1"
  line is amended by this doc (pointer comment): S2a is S1-independent.
- **New: S2a — app-independent session-plane build.** D1 schema, session
  CRUD, D-S2 auth, revocation fanout (D-S1/D-S5), metering reservation
  (D-S4), journal (D-S6: allowlist names + encoding), `DURABLE_COMMANDS.md`
  `session_revoke` registry row (D-S1), `expires_at` sweeper (D-S12),
  handle schema (D-S7), stub SFU carrier. Filed as
  #1231 by this turn.
- S2b (SFU binding), S3 (#936), S4 (#937) unchanged; all still wait on
  S1 (Realtime app provisioning — NEEDS_USER.md).

## 5. Acceptance deltas vs the Oct-3 S2 acceptance

Kept: owner requests → plane creates → box publishes → owner subscribes;
revoke-during-session kills media+input atomically; box A cannot touch
box B's sessions; expired sessions end; usage metered. Added: the
carrier's revocation-latency bound is now a pinned per-carrier taxonomy
(socket: DO re-drive bound; fetch: heartbeat/fetch cadence — measured
in the S2a build); session-open requires box reachability via at least
one carrier, not socket presence (D-S3); agent sessions cannot open,
close, or see sessions (D-S2); over-budget requests refused at request
time with reservations released on session end *and* by the
`expires_at` sweeper (D-S4/D-S12); epoch bumps do not kill sessions
(D-S11).
