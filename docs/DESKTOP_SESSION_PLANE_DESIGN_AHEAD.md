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
endpoint, publish credential, session/track ids, lease and revocation-signal
carrier, generation. The box publishes its `:98` capture (S3, #936); the
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
- **F-S2 — the signaling-carrier open question is closed.** Oct 3 left
  "HTTPS polling now vs the #847 WSS channel later — do not block S2 on
  #847" undecided. The channel now exists: BoxDO holds the box's WSS
  socket (S4a #958, S4b-1..4 #1000/#1001/#1002 all closed), the D15
  Worker→DO wakeup RPC (`/internal/commands-wakeup`, worker.py L1947)
  re-drives unacked work off the derived watermark, and `command_ack`
  frames ride the socket (S5b #976). Session-control signals ride the
  BoxDO→socket path — no interim carrier is built.
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

- **D-S1 — session-control carrier: BoxDO→socket, with HTTPS fetch as the
  box's cold-start sync.** The box fetches its session handle over a
  box-authenticated HTTPS endpoint (the #952 pattern — box Bearer <redacted>
  `current`/`grace` classes, worker.py L1764–1814). Lease/revocation
  signals ride the socket as session-control frames (a new frame kind in
  the §3 wire-spec registry, generation-bound like `command` frames).
  Revocation *also* enqueues a durable command for the disconnected case —
  idempotent by `session_id`, the box's ingest applies revoke-if-active and
  acks idempotently, the DO re-drives it off the watermark (#1001
  semantics). The box re-fetches active sessions on (re)connect; on a new
  generation the DO re-announces the box's active sessions from D1.
- **D-S2 — sessions are owner-key-only and invisible to agent sessions.**
  Opening a session is a write (mints SFU credentials, accrues metered
  spend): it is refused to AgentID agent sessions by the same
  `_require_owner_or_agent` central gate #1225 added — no new identity
  primitive, no allowlist entry. There is no session-visibility endpoint
  for agents; `GET /v1/boxes` reveals nothing about sessions. The #1225
  dashboard-copy lesson applies: dashboard session JS ships in the same
  turn as the plane endpoints (repo companion, the #1226 pattern).
- **D-S3 — the liveness gate: no socket, no session.** The plane asks the
  box's BoxDO whether a live socket is held; if not, session-open is
  refused with "box unreachable". Fail-closed: the durable channel covers
  *revoke*, never *open* — open needs the handle delivered to a live
  publisher, and a session that cannot be revoked promptly fails the S5
  acceptance by construction.
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
  TTL from the Oct-3 constraint.
- **D-S6 — journal: `phone_home_events` (D16), not G16/G17.** The S4b
  analysis (F-S4b-1) established that G16/G17 journals are box/operator-side;
  the plane's journal sink is `phone_home_events` (`migrate_958_s4b.sql`:
  `box_id`, `event`, `generation`, `seen_generation`, `code`,
  `server_time`). Session `open`/`close`/`auth_failure` events land there
  — session_id in `code` or the event string, owner principal in the event
  payload, never SFU credentials. Retention follows the table's 90-day
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
  against the live Realtime API). S2a's acceptance is the full S2
  acceptance minus the live-SFU rows.
- **D-S9 — the session names the input holder; #937 owns contention.**
  Session-open records the input mode (view-only / interactive) and the
  holder. The D1/D4 owner-vs-agent handoff rule is #937's build — #935
  only gives contention a session to arbitrate over, plus box-sourced
  input audit (the G54.3 pin).
- **D-S10 — session signals are generation-bound.** Like `command` frames,
  session-control frames carry the live generation; a new generation
  re-announces the box's active sessions (the DO reads the small
  per-box active set from D1). Stale-generation signals are ignored, not
  applied.

## 4. Slices

- **#935** stays the session-plane tracker. Its body's "Blocked on S1"
  line is amended by this doc (pointer comment): S2a is S1-independent.
- **New: S2a — app-independent session-plane build.** D1 schema, session
  CRUD, D-S2 auth, revocation fanout (D-S1/D-S5), metering reservation
  (D-S4), journal (D-S6), handle schema (D-S7), stub SFU carrier. Filed as
  #1231 by this turn.
- S2b (SFU binding), S3 (#936), S4 (#937) unchanged; all still wait on
  S1 (Realtime app provisioning — NEEDS_USER.md).

## 5. Acceptance deltas vs the Oct-3 S2 acceptance

Kept: owner requests → plane creates → box publishes → owner subscribes;
revoke-during-session kills media+input atomically; box A cannot touch
box B's sessions; expired sessions end; usage metered. Added: the
carrier's revocation-latency bound is now the DO re-drive bound (measured
in the S2a build, no interim carrier to bound); session-open refused
without a live socket (D-S3); agent sessions cannot open, close, or see
sessions (D-S2); over-budget requests refused at request time with
reservations released on session end (D-S4).
