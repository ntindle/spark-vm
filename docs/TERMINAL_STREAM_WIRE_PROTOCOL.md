# Terminal-stream wire protocol (#919, the S2 spec for #853)

The real-time stream frame class on the #847 WSS channel — the G53.2/G53.4
design slice of #853 (terminal streams + R2 artifact upload). The S3
contract (`docs/PHONE_HOME_WIRE_PROTOCOL.md`, PR #941) reserved the frame
types (`stream_open`, `stream_data`, `stream_close`, `input`) and pinned
the channel rules; this spec pins the payloads, the session lifecycle,
the read/write split on the wire, viewer fan-out, stream-loss semantics,
and the audit/journal discipline. #920 (box-side producer) and the
dashboard slice (#1035) build against this; #853's S5 verifies against
it.

Pinned to `main` at the merge of PR #1034 (2026-10-05), the S3 contract
as merged (PR #941), the #847/#958 deployed state (#958 S4a live
2026-10-04; S4b-4 #999 landed — the `phone_home_events` sink is live;
S4b-1/2/3 #1000–#1002 still open), `docs/DURABLE_COMMANDS.md` (#848),
`docs/APPROVALS_PLANE_PROTOCOL.md` (#872), and
`docs/STREAM_OWNERSHIP_DESIGN.md` (D3/D5/D6). Decisions here continue the
loop's D-series (D26–D44); they supersede the §5 shape sketch of
`docs/TERMINAL_STREAMS_ARTIFACTS_GAP_ANALYSIS.md` where they differ —
the sketch was reserved shape, this is the contract. Doc-first; honesty
rules apply (`docs/POSITIONING.md`): everything below is the contract to
build against, not a claim that it exists.

## 1. Scope and non-goals

- **In scope:** the box↔DO wire for terminal streams — frame payloads,
  the generation fence, session lifecycle (including the
  owner→DO initiation leg), the close-vs-data race rule, the viewer
  fan-out contract, stream-loss semantics, byte encoding, and the
  audit + journal discipline.
- **Out of scope (owned elsewhere):** box-side pty capture and the
  pty-source decision (S3, #920); the dashboard viewer surface and the
  SSE-vs-WSS choice (#1035); the durable-channel stream-control
  variant's registry row (#848's lane — §7 names the reservation);
  desktop media and input (the #854 SFU lane — never this channel);
  approval decisions (the #849 durable channel — the consent plane,
  never this transport); R2 artifacts (S4, #921).

## 2. What the S3 contract already pins (not re-litigated)

- The frame-class registry rows: terminal stream
  (`stream_open`, `stream_data`, `stream_close`) and input (`input`).
  Approvals decisions are NOT a WSS class; desktop media is never
  this channel.
- Control frames ≤ 4 KB; the `generation` field on every stream and
  input frame; the DO's old-generation fence (§5) and the
  drop-on-any-non-bound-socket rule; handshake identity binding (G47.3);
  the close taxonomy and revocation-latency bound; keepalive; WSS↔HTTPS
  fallback and liveness precedence (§8 — the socket, and by extension
  any stream, NEVER refreshes heartbeat freshness).

## 3. Frame shapes

All frames are S3 §3 JSON text frames (UTF-8), one object per frame.

### 3.1 `stream_open` (DO→box)

```json
{"type":"stream_open","generation":N,"session_id":"sess_<ulid>","cols":C,"rows":R,"principal":"<owner principal>"}
```

- DO→box only. The DO mints the session id — never the viewer, never
  the box. `sess_` + 26-char ULID: time-ordered, owner-opaque.
- `principal`: the authenticated opener, in the #845 dashboard auth
  model's principal spelling — the D5 session-bearer's principal, one
  meaning across docs. No new identity primitive is invented here.
  Owner-typed input rides this same lane under D5 with no approval
  step.
- **Initiation surface** (D41): the owner asks the DO through an
  owner-authenticated plane request —
  `POST /v1/boxes/{id}/stream/open` (owner auth, #845 model), carrying
  a client-supplied `idempotency_key` and the requested `cols`/`rows`.
  The plane forwards to the DO; the DO mints the session id (the
  single-minter invariant) and is idempotent on the key for a live
  session — a retried initiation returns the existing `session_id`,
  never a second pty.
- Idempotent on the wire: an open for an already-open `session_id`
  is a no-op — **except for geometry**: re-`stream_open` for an
  already-open session applies the new `cols`/`rows` to the existing
  pty (D27 — the resize path; no new frame class, no S3 registry
  amendment).
- Box at cap: D3's per-box session cap is the box's own process limits
  as the default. The box answers
  `stream_close{session_id, code:"cap-reached"}`; the DO documents the
  knob and never invents the number.
- **No open-ack frame** (D26 — "data is the ack"): the box's first
  `stream_data` for the session is the implicit open confirmation. If
  the pty cannot be spawned, the box answers
  `stream_close{session_id, code:"open-failed", reason:"<scrubbed>"}` —
  the close doubles as the open failure, so no fourth frame type is
  needed and the S3 registry stays at three types.

### 3.2 `stream_data` (box→DO)

```json
{"type":"stream_data","generation":N,"session_id":"...","seq":S,"data_b64":"..."}
```

- `seq`: per (session_id, generation), box-chosen, starts at 1 per
  generation. Wire order is TCP's; `seq` exists so the DO can assert
  per-session contiguity as a fail-closed sanity check on its own
  forwarding path.
- `data_b64`: base64 of the raw pty bytes. Rationale (D28): terminal
  bytes are not valid UTF-8 in general, and S3 pins JSON text frames —
  base64 is the honest encoding. Raw chunk ≤ 12,288 bytes, so
  `data_b64` ≤ 16,384 chars; the producer splits larger writes. The
  ceiling mirrors the #848 command carrier's 16 KB so the DO's
  per-frame memory bound is in the same class (the JSON envelope adds
  a few hundred bytes on top — the bound is on the payload, not the
  envelope).
- **Lossy by design** (D29 — the anti-replay rule): no acks, never
  replayed. A reconnected box does NOT resend missed chunks; replaying
  stale output into a live tail is the exact corruption G53.2 named.
  Viewers see a discontinuity note rendered by the viewer surface on
  reconnect (§5), not fabricated history.
- The DO forwards to subscribed viewers and **never stores frame
  contents** — hibernation-safe by construction: only session metadata
  lives in DO durable storage (§4).

### 3.3 `stream_close` (box↔DO), `stream.control` (DO→viewer)

Box↔DO wire codes, split by direction (D38):

- **box→DO:** `pty-exited`, `open-failed`, `cap-reached`.
- **DO→box:** `viewer-closed` (last viewer unsubscribed),
  `owner-killed`, `session-revoked` (the viewer's D5 session bearer was
  revoked), `box-revoked` (the box's own token was revoked mid-stream —
  distinct from `session-revoked`, which is the viewer's bearer; the DO
  closes streams with `box-revoked` before shedding the socket per the
  S3 `revoked` row — the #853 S5 "revoke kills the socket" acceptance,
  mechanism refined: sessions close first so viewers see why, then the
  socket sheds).
- **DO→viewer** (the §5 control event, not the box wire):
  `paused`, `resumed`, `gap`, `box-gone` (the box's socket died with
  the session open — a dead box can never send it, so it is not a
  box-wire code), plus the §3.3 codes surfaced to the viewer.

`reason` is optional, human-readable, never a secret, and C0/C1-scrubbed.

- **Cross-channel race rule** (D30): close is session-id-keyed, never
  seq-keyed. The DO resolves close-vs-in-flight-data by
  first-wins-for-close: once it marks a session closed it drops
  subsequent `stream_data` for that session id silently; once the box
  sends `stream_close` it stops emitting data and ignores further
  `input` frames for the session. No mutual ordering is assumed between
  socket frames and any durable-channel variant — hence session-id
  keys, never sequence gates.

### 3.4 `input` (DO→box)

```json
{"type":"input","generation":N,"session_id":"...","data_b64":"...","principal":"<acting principal>","provenance":"owner|approval","approval_id":"<aid, when provenance=approval>"}
```

- **Single-ingress rule** (D31): every byte that enters a pty from
  outside the box arrives as an `input` frame from the DO on the box's
  one authenticated socket. The box never distinguishes consent
  provenance on the wire; the DO enforces it.
- `principal` is always the acting principal in the #845 spelling
  (D42): for owner-typed input, the owner principal of the
  authenticated viewer session (#845 auth model — no approval step:
  D3's per-session interactive semantics hold for the owner,
  frictionless); for approved input, the approval record's
  `decided_by` (the owner key that decided —
  `docs/APPROVALS_PLANE_PROTOCOL.md`'s record). `approval:<aid>` is a
  decision reference, not a principal — the wire keeps them separate.
- `provenance` names the consent path: `"owner"` or `"approval"`.
  `approval_id` rides along when provenance is `"approval"`.
- **Approved input** (the G53.2(a) call, pinned as wire): an
  `approval_decision` for aid with decision=approve does NOT carry the
  input bytes — `docs/DURABLE_COMMANDS.md` pins that kind's payload to
  `{aid, decision, decision_seq, idempotency_key}` and this spec does
  not amend it. The plane resolves the approved bytes from its own
  approval record (aid-keyed lookup; the record's `detail` is the
  owner-authored action blob per `docs/APPROVALS_PLANE_PROTOCOL.md`)
  and forwards them as an `input` frame. **Approval is the consent
  plane; the bytes ride the input class.** Never the stream's data
  frames, never the approvals decision wire.
- Ordered per session, fire-and-forget (no acks): input is an action,
  not a command — at-least-once would double-type.
- `data_b64` carries the same bound as stream data (D39): raw input
  chunk ≤ 12,288 bytes, `data_b64` ≤ 16,384 chars; the DO-side producer
  (dashboard, #1035) splits pastes. An unbounded input class would
  break the per-frame memory bound §3.2 justifies for the DO.
- Input to a closed or unknown session is dropped and journaled
  (`stream.input_dropped`), never buffered. Input to a **paused**
  session is likewise dropped and journaled (D43 — code `"paused"`):
  buffering keystrokes across a reconnect is the at-least-once
  semantics this lane explicitly rejects; the viewer surface shows the
  session as paused and rejects typing.

### 3.5 What does NOT ride this wire

- Approval decisions (durable channel only — S3 §3.2).
- Command frames (#848's class — unchanged).
- Heartbeat or liveness refresh (S3 §8 — a stream never fabricates
  liveness, and neither does its pause or its gap).
- The box bearer (S3 §2 — never in frames, never in logs).

## 4. Session lifecycle and the generation fence

- Sessions are generation-independent: the DO binds
  session_id → current generation on resume, and frames from a stale
  generation are dropped per S3 §5 even when the session id is right
  (D32 — the fence applies to frames, not sessions).
- On socket loss the box **keeps the pty** (D33): a network blip must
  never kill real work. The DO marks the session `paused`, tells
  viewers "reconnecting", and on reconnect the box's new-generation
  frames resume the same session id. The DO journals
  `stream.gap{session_id, old_generation, new_generation}` — the gap is
  visible, never silent.
- **No HTTPS-long-poll degrade for stream data** (D34): a lossy
  real-time tail over polling is a design wart. The heartbeat stays the
  only polling path and carries zero stream bytes. Pause — buffer
  nothing, resume on reconnect — is the single fallback rule: simpler
  than a degraded mode that would lie about completeness.
- Viewer attach/detach never touches the box: the DO multiplexes. A
  viewer arriving mid-session gets the live tail, not history (D35 —
  no scrollback over the wire; the viewer surface may keep its own
  in-memory tail, #1035's UI call).

## 5. Viewer fan-out contract (DO→viewer)

Normative names; the dashboard slice (#1035) chooses SSE or viewer
WSS — this spec pins the contract, not the transport.

- Initiation: the owner-authenticated
  `POST /v1/boxes/{id}/stream/open` (D41) — the single path that
  reaches the DO's session mint.
- Subscribe: owner-authenticated (#845) per (box_id, session_id). A
  box token is refused on the subscribe path — a box cannot subscribe
  to its own stream; the operator's terminal is the box-local surface.
- Events: `stream.data{session_id, seq, data_b64}`,
  `stream.control{session_id, code, ...}` (open/close/pause/resume/gap
  notices), `stream.error{session_id, code}` (`cap-reached`,
  `session-revoked`, `box-revoked`, and the §3.3 codes surfaced to the
  viewer).
- Fan-out is DO-side: the box's socket carries exactly one copy of
  each frame regardless of viewer count.

## 6. Audit and observability

- D6 audit lines are written at session granularity (D40 — reconciled
  with D6's transition semantics, not per keystroke): `stream_open`
  and `stream_close` each write a line carrying (session_id,
  principal, provenance, code) — **never frame contents** (D36 — the
  content-exclusion rule: audit is attribution, not a second copy of
  the terminal). The first `input` frame of a *new* provenance on an
  open session writes one `stream.input_provenance` line (session_id,
  principal, provenance, approval_id) — subsequent same-provenance
  input is silent by design.
- DO journal events (fleet event journal shape, G16/G17; sink is the
  S4b-4 `phone_home_events` D1 table — **landed** per #999, present
  tense in S3 §9). Journaling the five `stream.*` names requires the
  S4b lane to apply an explicit S3 §9 amendment first (D44 — named,
  not applied here; §9's fail-closed event registry raises on anything
  but its six names today): extend the registry to the five names
  below (deliberately, not by bypass) and add a re-run-safe
  `session_id TEXT` column. Per-event → column mapping, in S4b-4's
  style:
  - `stream.open` → (box_id, session_id, generation=current)
  - `stream.close` → (box_id, session_id, generation=current,
    code=close code)
  - `stream.gap` → (box_id, session_id, generation=new_generation,
    seen_generation=old_generation — the fence event's convention)
  - `stream.auth_failure` → (box_id, session_id, code=reason key
    e.g. `unknown-session` / `wrong-generation`)
  - `stream.input_dropped` → (box_id, session_id,
    generation=current, code=`paused` | `closed` | `unknown-session`)
  Until the amendment lands, the DO's journal helper is the writer of
  record and MUST fail closed (not silently skip) on the new names —
  the amendment is a hard prerequisite for the DO build, not an
  optional follow-on.
- Producer discipline (G53.4, pinned as wire rules): the producer
  never logs frames; the dashboard treats stream content as
  owner-confidential — rendered in the terminal widget only, never in
  shared surfaces, never cached. Plane *control* surfaces (journal
  reasons, audit lines) are C0/C1-scrubbed per the #970 `_plane_text`
  rule; the stream bytes themselves are forwarded byte-exact — the
  payload is the product, not a log line.
- Three liveness sources, three signals (G53.7, S3 §8): heartbeat
  freshness is box↔plane; socket state is operational; stream health is
  the DO's session table. Staleness chips stay heartbeat-driven; a
  paused stream never flips a box "dead".

## 7. Durable-channel stream control (reserved, not pinned)

The #853 gap analysis reserves `stream_open`/`stream_close` on the
durable command channel for the socket-down case. This spec does NOT
pin it: enqueueing stream control requires a `DURABLE_COMMANDS.md`
registry row (the plane owns the registry) and a #874 executor
honored-kind — both #848's lane. The socket is the normative
transport; the durable variant stays a named future extension, not a
second live contract (D37 — one live contract at a time).

## 8. S5 acceptance deltas (feeds #853's S5)

On top of #853's S5 acceptance: stream latency measured end-to-end
(box pty → DO → viewer) as a number, not an adjective; the
generation fence on stream and input frames (stale-generation input
dropped, never injected); revoke-mid-stream closes sessions with
`box-revoked` before the socket sheds (§3.3); the close-vs-data race
(close wins, no wedge); owner-vs-approved input provenance carried in
the audit line; resize via idempotent re-open applies geometry without
a new pty.

## 9. Open questions for #920 / #1035 / #921 (not blocking this contract)

- Pty source: dedicated pty vs tmux attach (S3, #920).
- Viewer transport: SSE vs viewer WSS (this spec's §5 names the event
  contract; #1035 chooses).
- Scrollback: no wire scrollback (D35); whether the dashboard keeps a
  client-side tail is #1035's UI call.
- R2: S4 (#921) is untouched by this spec.
