# Terminal-streams + R2: producer + upload design-ahead (#853 S3/S4)

**Vision-vs-state design-ahead for the two unbuilt #853 build slices —
#920 (box-side stream producer) and #921 (R2 artifact flow).** Statuses
pinned to this repo at main `3b76c0f0` (2026-10-08) and a 2026-10-08 read
of the deployed `sparkvm-control` worker checkout (`worker.py`, the S4a
deploy plus the #1001 S4b-2b plane half). Doc-first; honesty rules apply
(`docs/POSITIONING.md`): everything below is current state and work to
do, not promises. Findings continue the G53 series as F-S53-n;
decisions continue the loop's D-series as D-S53-n.

Parent analysis: `docs/TERMINAL_STREAMS_ARTIFACTS_GAP_ANALYSIS.md`
(main `d058a10`, 2026-10-03 — predates the real channel). Wire contract:
`docs/TERMINAL_STREAM_WIRE_PROTOCOL.md` (#919, shipped 2026-10-05,
D26–D44). Session semantics: `docs/STREAM_OWNERSHIP_DESIGN.md` (D3/D5/D6).
The S3 contract: `docs/PHONE_HOME_WIRE_PROTOCOL.md` (frame registry §3,
the §9 journal contract).

## 1. What moved since the 2026-10-03 analysis

| Oct-03 claim | Current state (2026-10-08) |
|---|---|
| "No persistent connection anywhere" | **False.** The phone-home WSS channel is live: S4a plane DO deployed 2026-10-04 (#958, PR #986); S4b-1 hello/identity + generation fence merged (#1000); S4b-2b socket `command_ack` consume-half deployed live today (slot 20261008-1959); S4b-4 journal sink landed (#999 — `phone_home_events` D1 table live, 90-day retention, fail-closed event registry). Remaining: S4b-3 ping/alarm + hibernation (#1002, open), S6 live acceptance (#960, open). |
| "The box's Durable Object does not exist" | **False.** One-DO-per-box, route-by-token via `idFromName`, `BoxDO` holds the socket. |
| "No box-side persistent process" | **False.** `spark_pair.py phone-home` holds the persistent outbound WSS channel (S5a session #976's session half; S5b socket command frames + acks #976). Durable generation file (`phone_home_generation.json`), 1s→60s ±25% backoff, `_WsReader`, `_handle_socket_command` dispatch — all in `pairing/spark_pair.py` on main. |
| "No stream wire protocol" (G53.2) | **Closed.** #919 shipped `docs/TERMINAL_STREAM_WIRE_PROTOCOL.md`: frame shapes (`stream_open` DO→box, `stream_data` box→DO, `stream_close` box↔DO, `input` DO→box), 12,288-byte raw chunk / 16,384-char `data_b64` bound, D26 "data is the ack" (no open-ack; close doubles as open failure), D27 resize via idempotent re-open, D29 lossy-by-design (no acks, never replayed), D30 close-vs-data race rule (close wins, session-id-keyed), D31 single-ingress input, D32 generation fence on frames, D33 box keeps the pty on socket loss (DO marks paused, resume same session id), D34 no HTTPS-long-poll degrade, D35 no wire scrollback, D36 content-exclusion audit, D37 durable-channel stream control reserved-not-pinned, D38 close-code split by direction, D39 input size bound, D40 session-granularity audit, D41 initiation surface `POST /v1/boxes/{id}/stream/open` (owner auth, idempotency key, DO mints the single session id), D42 principal spelling, D43 paused-session input dropped, D44 journal amendment named-not-applied. |
| G53.4 (secret-bearing streams) | Pinned as wire rules in #919 §6: producer never logs frames; audit carries attribution only (D36); control surfaces C0/C1-scrubbed per the #970 `_plane_text` rule; stream bytes forwarded byte-exact. |
| "R2: no bucket, no binding, no path" (G53.5) | **Still true.** The worker is still grep-clean for r2/bucket/presign (verified 2026-10-08 in the deployed checkout). No bucket, no R2 API token, no mint endpoint, no uploader, no D1 `artifacts` table. |
| G53.6 (mint race, quota, namespace) | **Design pinned, not built.** The mint-time-pending-row + mint-time quota check + sweeper closure and the presigned-POST-with-`content-length-range` stronger alternative are #921's scope, unchanged. |
| #280 per-tenant box | **ADOPTED** (same caveat as #850 G50.3: box-namespacing only until the T3 gate #1159 decides). |

## 2. Current state: the two slices

### #920 — box-side stream producer

What exists: the S5a/S5b `phone-home` process (persistent, reconnecting,
generation-fenced) and the #919 wire contract it must speak. What does
not exist: pty capture anywhere (`pairing/`, `hosted/`, `cua/`, `deploy/`
all grep-clean for pty on main), a producer session table, the
`stream_open`→pty-spawn handler, the resize path, the session-cap knob.

### #921 — R2 artifact flow

What exists: the box-authenticated endpoint pattern (#952 — box bearer,
`current`+`grace` classes), the D1 forward-migration discipline, the
fleet journal (`phone_home_events`) for completion events. What does not
exist: the bucket, the token, the mint endpoint, the uploader, the
artifacts table, the sweeper, the retrieval surface.

## 3. Findings and decisions

### F-S53-1 — the producer's host process already exists, and it's `phone-home`

The Oct-03 analysis named boxd as the producer's host "alongside the WSS
client." The WSS client shipped as `spark_pair.py phone-home` — a
long-running daemon with reconnect/backoff/generation claim. The producer
is a workload inside that process, not a second daemon: the session's
socket writer is the single egress for all WSS frames, and a second
process would need its own socket (the DO's drop-on-any-non-bound-socket
rule forbids it). **D-S53-1: the #920 producer lives in the `phone-home`
process's session loop; no new daemon.**

### F-S53-2 — D3 already settles the pty-source question

#920's body defers "dedicated pty vs tmux attach" to the slice. The
evidence closes it: (1) stdlib `pty` is available in the box Python
(verified — `import pty, termios` succeeds); tmux is NOT a guaranteed
box dependency (the golden image does not pin it); (2) STREAM_OWNERSHIP_DESIGN.md
D3 pins "each terminal tab is its own pty session … there is no
shared-driver contention" — attaching a viewer to the agent's live tmux
pane reintroduces exactly the shared-driver contention D3 forbids (whose
keystrokes win when owner and agent type at once?). Observation of the
agent's pane is a different product from an interactive session.
**D-S53-2: the producer spawns a dedicated pty per streamed session
(D3); tmux-attach is out of slice scope.** The slice's remaining choice
is only which shell the dedicated pty spawns (default: the box user's
login shell; the initiation request may carry an optional `command` —
see D-S53-8).

### F-S53-3 — the producer's session table is generation-agnostic; the transport owns the fence

#919 D32/D33: sessions are generation-independent; the DO rebinds
session_id → current generation on resume and fence-drops stale frames.
Consequence for the producer: its session table is keyed by session_id
alone. On socket loss it keeps every pty (D33) and emits nothing — data
written to a dead socket is dropped, never buffered (D34's
pause-not-degrade rule). The generation number on each outbound frame is
supplied by the transport layer at send time (the session's current
bound generation), never cached in the producer. A producer that caches
the generation will emit fence-dropped frames after a reconnect —
silently correct on the DO side (they drop), but a loud box-side bug.
**D-S53-3: generation lives in the transport, not the producer; the
producer asks the session for the current generation per frame.**

### F-S53-4 — one socket, one writer, the S5b lock discipline

S5b's Security round-1 B1 established the `.ingest.lock` serialization
discipline: socket-ingest paths serialize through a non-blocking lock.
The producer adds a second writer (pty reader threads → socket). Two
unsynchronized writers interleave JSON frames on one TLS stream — a
corruption the DO would read as protocol errors. **D-S53-4: all outbound
WSS frames (command acks, stream data, input handling, keepalive)
serialize through the session's single socket writer under the existing
lock discipline; pty reader threads enqueue to the writer, never write
the socket.**

### F-S53-5 — the session cap gets a concrete default

D3: "the box's own process limits decide; the control plane documents
the knob, it does not invent a small number." The producer needs a
number anyway. Each pty costs ~3 fds (master, reader bookkeeping,
epoll registration) — the honest default is derived, not invented:
`cap = min(configured_cap, rlimit_nofile // 8)`, floored at a sane
minimum (8) so a constrained box still streams. At cap, the box answers
`stream_close{session_id, code:"cap-reached"}` per #919 §3.1; the DO
documents the knob per D3. **D-S53-5: cap default derived from
`RLIMIT_NOFILE`, knob `stream_session_cap` in the box config; the DO
never invents the number.**

### F-S53-6 — resize is an ioctl, not a re-fork

#919 D27: re-`stream_open` for an open session applies geometry. The
producer implements it as `ioctl(TIOCSWINSZ)` on the live pty master —
no re-fork, no session-id change, the running process keeps its state.
**D-S53-6: resize path = TIOCSWINSZ on the existing pty.**

### F-S53-7 — open failure and spawn hygiene

`stream_open` arrives; the fork fails (cap, rlimit, ENOENT shell). Per
D26 the box answers `stream_close{session_id, code:"open-failed",
reason:"<scrubbed>"}` — the close doubles as the failure, no fourth
frame type. The reason is scrubbed per the #970 `_plane_text` rule
(C0/C1 strip, 256 B bound) — a failing shell's stderr may contain
secrets. The child side closes all inherited fds except the pty slave
(the session's socket fd must never leak into the pty child — a child
that inherits the WSS socket could keep the box's channel half-open
across exec; close-on-exec everywhere, asserted in the slice's tests).
**D-S53-7: fail-closed spawn — scrubbed reason, CLOEXEC on the socket,
no fd leaks into pty children.**

### F-S53-8 — the initiation request's optional command

#919 §3.1's initiation request carries `idempotency_key` + `cols`/`rows`
and the DO mints the session id. The producer needs one more optional
field to be useful: `command` (argv to exec in the pty; default: login
shell). This is a #919-contract extension, not an amendment — the frame
shape is unchanged (`stream_open` gains an optional field), and D41's
single-minter invariant is untouched. **D-S53-8: initiation carries
optional `command`; absent → login shell. Recorded here as the
contract delta #920 ships with.**

### F-S53-9 — the DO-side stream machinery has no build owner (NEW GAP)

#919 pinned the box↔DO wire; #920 is box-only; #1035 owns the
dashboard/viewer half (initiation UI + surface, viewer transport,
widget, input path). Between them sits the DO's stream half with no
slice: the DO stream session table (session_id → box socket binding),
`stream_open`→box dispatch with the single-minter + idempotency-key
contract (D41), generation-fenced stream/input frame handling, fan-out
to subscribed viewers, revoke-mid-stream session close (`box-revoked`
before the socket sheds, #919 §3.3), and the D44 journal-registry
amendment (the deployed `_journal_phone_home_event` is fail-closed on
its six names — verified 2026-10-08 in the deployed worker — so the
five `stream.*` names + a re-run-safe `session_id TEXT` column must be
added deliberately, not bypassed). **Filed as a new issue (see §5).**

### F-S53-10 — R2: presigned POST wins, the pending row stays

G53.6 named presigned PUT with a D1 pending row, or presigned POST with
`content-length-range` as the stronger alternative. POST's server-side
size enforcement closes the mint race at the R2 edge; the pending row
remains the ledger (quota accounting, completion matching, sweeper
target). Both, not either. **D-S53-10: presigned POST +
`content-length-range` policy; the D1 pending row stays as the quota
ledger.**

### F-S53-11 — R2 namespace stays box-scoped, tenant caveat carried

Key `artifacts/<box_id>/<uuid>/<filename>`, server-derived from the
verified box identity (G47.5 pattern); filename basename + charset
whitelist, `../` can never escape the prefix (the #853 S5 acceptance).
No tenant dimension until the T3 gate (#1159) decides — the same
provisional caveat as #850's G50.3. **D-S53-11: box-scoped keys now;
tenant namespacing is #1159's call, not #921's.**

### F-S53-12 — the bucket and the token are operator-owned (NEW GAP)

Everything in #921 is loop-buildable except two account actions: creating
the R2 bucket and minting the R2 API token that lives in worker env. The
loop deploys the worker through the Cloudflare API and can carry the
token in env config, but it cannot create the billing-account-side
objects — and the token is a secret the loop must never see in the
clear. Precedent: #854's S1 (Realtime app provisioning) is
operator-owned in NEEDS_USER.md. **Filed as a new issue + logged to
NEEDS_USER.md (see §5); #921's build slices gate on it.**

### F-S53-13 — artifact completion feeds the journal

G53.7: upload completions land in the fleet event journal. The
`phone_home_events` sink is live; an `artifact.completed` name needs the
same deliberate registry treatment as D44 (the writer is fail-closed).
Completion rows carry (box_id, key, bytes, sha) — never file contents.
**D-S53-13: `POST /v1/artifacts/complete` HEAD-verifies the key, records
the row, journals `artifact.completed`; the journal name is added by the
same amendment that carries D44.**

### F-S53-14 — retrieval is attachment-only, and stays in #921's scope

G53.4's retrieval half: owner-authenticated presigned GETs (short TTL),
`Content-Disposition: attachment`, sniffing disabled, filename sanitized
on the download path. The retrieval surface ships with #921 (it is the
artifact half's user-visible payoff), reusing the #845 dashboard auth
shape — it does not wait for #1035's terminal widget. **D-S53-14:
retrieval is #921's scope, attachment-discipline, never inline.**

## 4. Slice plan deltas (amends the Oct-03 §4)

- **S2 (#919):** shipped. Its open questions (§9) are answered here for
  #920: pty source = dedicated pty (D-S53-2); viewer transport stays
  #1035's call; scrollback stays client-side (D35).
- **S3 (#920):** builds the producer per D-S53-1–D-S53-8 inside the
  `phone-home` process. Depends on the channel (shipped) and the new
  DO-stream-machinery slice for end-to-end testing (the box half can be
  harness-tested against a contract-faithful DO stub first).
- **S3b (new):** DO-side stream session machinery (F-S53-9) — dispatch,
  session table, fence, fan-out, revoke close, D44 + artifact journal
  amendment. Blocks #920's live acceptance and #1035's viewer.
- **S4 (#921):** mint endpoint (D-S53-10), artifacts table + quota
  ledger + sweeper, box uploader, completion endpoint (D-S53-13),
  retrieval surface (D-S53-14). Gated on the operator bucket+token
  (F-S53-12). Independent of the WSS channel — still shippable on plain
  HTTPS first, as the Oct-03 analysis said.
- **S5 (#853):** acceptance unchanged, plus: end-to-end latency measured
  box-pty → DO → viewer (a number); revoke-mid-stream closes sessions
  with `box-revoked` before the socket sheds; namespace isolation proved
  (box A cannot mint outside its prefix, filename normalization
  included); over-quota mint refused at mint time; uncompleted uploads
  swept and R2-deleted.

## 5. New backlog items filed by this analysis

- **#1190 (S3b): DO-side stream session machinery (#853)** —
  F-S53-9: DO stream session table, `stream_open`→box dispatch +
  single-minter + idempotency-key contract, generation-fenced
  stream/input handling, viewer fan-out, revoke-mid-stream close, the
  D44 journal amendment (five `stream.*` names + `session_id` column)
  plus the `artifact.completed` name. Priority p2, track hosted-product.
- **#1191: R2 bucket + API token provisioning (operator-owned,
  gates #921)** — F-S53-12: create the bucket, mint the R2 API token
  into worker env via the API-deploy path, never in the repo. Logged to
  NEEDS_USER.md (operator-owned, precedent #854 S1). Priority p2, track
  hosted-product.
- #853 stays the tracker; #920 and #921 bodies get pointer comments to
  this doc. S5 acceptance lives on #853.

## 6. Honest summary

The Oct-03 analysis's two blockers are gone: the channel is real (DO
deployed, journal live, wire contract pinned) and the box has a
persistent process to host the producer. What remains genuinely
greenfield is the R2 half (no bucket, no token, no path — and the two
account actions are the operator's, not the loop's) and the DO's stream
half (the wire contract exists, the box half is specified, the dashboard
half is specced — but nobody owns the DO session table, dispatch,
fan-out, or the journal amendment the fail-closed registry requires).
The pty-source question resolves to dedicated pty by D3, not by new
argument. The producer's hard invariants are: generation lives in the
transport (D-S53-3), one serialized socket writer (D-S53-4), derived cap
(D-S53-5), and fail-closed spawn hygiene (D-S53-7).
