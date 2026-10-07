# S4b socket-lifecycle gap analysis: the plane DO's session logic (#958)

**Vision vs current state.** Statuses pinned to this repo at main
`7b20178` (2026-10-07) and to the deployed plane worker — the S4a slice
landed 2026-10-04 (upgrade route + `BoxDO` accept-and-hold, deployed
live via `deploy_worker.py`; the deployed source is the
`diff-958-s4a-worker.patch` state), the S4b-4 journal sink shipped
2026-10-04 (#999, PR #1014), and S4b-1 (hello/identity/generation fence)
shipped and deployed live 2026-10-05 (#1000, PR #1055). The plane lives
outside this repo, so plane-side facts below are pinned to that deployed
checkout, not to a repo commit. Doc-first; honesty rules apply
(`docs/POSITIONING.md`): everything below is **current state and work to
do**, not promises.

## 1. The S4b vision

#958 split the plane half of #847 into S4a (shipped) and S4b (this doc).
S4a proved the entry point: `GET /v1/boxes/{box_id}/phone-home` routes
by the token's `box_id` via `idFromName("phone-home:" + box_id)`,
unknown/expired/revoked tokens get one undifferentiated HTTP 401, the
#846 grace is honored, non-upgrade gets 426, and `BoxDO.fetch` accepts the
socket and holds it. The `BoxDO` docstring names the S4b slice explicitly:

- hello handshake + identity binding (wire spec §2)
- generation fence (wire spec §5)
- durable-queue re-drive (wire spec §3.3)
- 30 s ping interval, bounded alarm wake, token re-verify on wake; `revoked`
  during a socket → close `revoked` on next inbound/wake (wire spec §4/§6)
- DO journal events (wire spec §7)[^s4a-docstring-typo]; heartbeat stays
  the only liveness signal (wire spec §8)

[^s4a-docstring-typo]: Quoted faithfully: the deployed `BoxDO` docstring
  cites "wire spec §7" here, but §7 is "One DO per box, no leakage" —
  the journal events are wire spec §9. A real typo in the deployed code,
  flagged here rather than silently corrected, so the next reader can
  trace doc-to-source without a mismatch.

Acceptance is #960's S6 checklist, harness-first per the S4 contract.

## 2. Current state

| S4b element | Current state |
|---|---|
| `hello` frame handling | **Shipped — #1000 (S4b-1), PR #1055, deployed live 2026-10-05.** `BoxDO.fetch` reads the first frame as `hello`; malformed → `close`/`protocol-error`. The box side (#959 S5a, closed) sends `hello` with `(box_id, generation)` — it is now answered, not left waiting. |
| Identity binding | **Shipped — #1000 (S4b-1), PR #1055, deployed live 2026-10-05.** The DO re-derives the handshake identity from the upgrade request's `Authorization` Bearer <redacted> per D14; the `hello` frame's `box_id` self-assertion must equal it (mismatch → `close`/`identity-mismatch` + journal). |
| Generation fence | **Shipped — #1000 (S4b-1), PR #1055, deployed live 2026-10-05.** `last_generation` lives in DO durable storage: `hello` with `generation > last_generation` binds the new socket and closes the old one `superseded-generation`; `<= last_generation` → `close`/`stale-generation` carrying `last_generation`; every subsequent frame is generation-checked (stale → dropped + `phone_home.generation_fence` journaled). The box side (#959) already bumps a crash-safe durable generation per connect and adopts `last_generation + 1` on a stale-generation close — the plane half of that contract is now built. |
| Re-drive | **Partially landed — the emit half is in the deployed worker checkout (in-flight #1001 S4b-2a work; the sibling feature turn is live, review not yet converged).** `_phone_home_redrive` emits `command` frames on (re)bind and on the D15 Worker→DO wakeup RPC (`/internal/commands-wakeup`, fired after `_enqueue_command`); leases stamped exactly as the HTTPS path; `phone_home.redrive` journaled; malformed rows skipped-and-logged per D-MAL1. The socket `command_ack` consume-half is still open (S4b-2b, #1001). |
| Socket `command_ack` consume half | **Nothing on the plane.** The box (#976 S5b) sends `command_ack` frames with `(generation, seq, epoch)`; the DO ignores them as unknown frame types (they are never fenced-bypassed — the generation fence already ran). The HTTPS `POST /commands/ack` endpoint is the only ack path that lands; the socket ack UPDATE hoist is S4b-2b, still open (#1001). |
| Ping / pong | **Pong answered in the deployed worker checkout (wire spec §4 keepalive).** The DO answers the box's `ping` with `pong` (keeps the box's 90 s watchdog from flapping the session). The 90 s pong-timeout → hibernate rule and the alarm-wake + token re-verify are still open (#1002). |
| Alarm wake + token re-verify | **Nothing.** No alarm is set; a hibernated socket is never re-verified. The revocation-latency ceiling for a silent socket is currently unbounded — the exact hole wire spec §6's bound exists to close. |
| Hibernation | **Not used.** S4a's `server.accept()` pins the DO in memory. The `BoxDO` docstring already names the move to `self.ctx.acceptWebSocket(server)` as S4b scope. |
| Journal events | **Shipped — #999 (S4b-4), PR #1014, 2026-10-04.** The sink is the D1 table `phone_home_events` (D16's decision implemented, migration `migrate_958_s4b.sql`, re-run safe); owner-only read path `GET /v1/boxes/{box_id}/phone-home/events`; 90-day retention with the daily Worker cron + manual trigger `POST /v1/ops/phone_home/gc` (#1013). Wire spec §9's sink reference was corrected to this table by the same slice. |
| Liveness writes from the socket | **Correctly absent** — and must stay absent (§8). The #864 heartbeat remains the only liveness signal; nothing in S4b changes that. |

## 3. Findings

- **F-S4b-1 — wire spec §9 names a journal sink that does not exist on
  the plane.** §9 says "The DO emits into the fleet event journal", but
  the G16/G17 fleet journals are box/operator-side JSONL (`fleet/events.py`,
  `fleet/inventory.py`) — a plane-side DO cannot write to them. The
  plane's D1 schema (`schema.sql`: `boxes`, `owner_keys`, `pairings`,
  `commands`, `approvals`) has no events table. The S4b journal slice must
  pin the real sink; until it does, every other S4b slice's "journal the
  event" acceptance criterion has nowhere to land. Decision D16 pins it.
  **Status 2026-10-07: RESOLVED.** #999 shipped 2026-10-04 (PR #1014):
  the sink is the D1 table `phone_home_events` per D16, wire spec §9 was
  corrected to it, and the owner-only read path plus 90-day retention
  shipped with it (#1013). The finding above is historical — it was true
  when written; the §2 "Journal events" row carries the shipped state.
- **F-S4b-2 — the new-enqueue wakeup path is unspecified.** The DO owns
  the socket, but enqueues land on the Worker (`_enqueue_command`, owner
  API + #873 approval decisions). Nothing tells the DO a new command is
  waiting — re-drive-on-bind alone leaves up to a reconnect interval of
  latency on the "faster carrier". The two candidate designs are
  Worker→DO wakeup RPC on enqueue (immediate) vs DO-side poll on a tick
  (adds a staleness bound and a second cursor-adjacent timer). Decision
  D15 picks the RPC; the poll is rejected, not deferred — a DO that polls
  D1 on a timer reintroduces the timer the hibernation design is trying
  to remove.
- **F-S4b-3 — the ack consume-half is a drift risk, not just new code.**
  The idempotent ack UPDATE (`state='acked'` only from
  `pending`/`leased`, never rewriting an `expired` row's audit trail)
  exists in the Worker's `_commands_ack`. The DO's `command_ack` ingest
  must apply the identical transition. The `_classify_box_token` hoist
  (S4a) is the precedent: hoist the ack UPDATE into a shared
  module-level helper and refactor `_commands_ack` onto it
  (behavior-identical), so the two paths cannot drift the way
  `_pairing_row`'s single-row-shape rule was created to prevent.
- **F-S4b-4 — hibernation-API support in workers-py is still assumed,
  not verified.** G47.2 flagged it; S4a committed to the DO class shape
  anyway (accept-and-hold needs no hibernation). S4b-3's entry ticket is
  the explicit verification: `ctx.acceptWebSocket` + `ctx.storage.setAlarm`
  against the workers-py runtime the harness models. If the API surface
  differs, the slice adapts the design — it does not ship a guess.
- **F-S4b-5 — the handshake identity must be re-derived in the DO, not
  carried.** The Worker validated the token and routed by it, but the DO
  must not trust a Worker-passed box_id (a header is a new trust surface
  and a second place the #844 fingerprint-spoof class can recur).
  `_classify_box_token` is already module-level and shared for exactly
  this: the DO re-classifies from the upgrade request's `Authorization`
  header (the credential travels in the upgrade request, never in a
  frame — §2 already permits this). Decision D14. Cost: two extra
  indexed point lookups per session setup — negligible against a
  socket's lifetime.
- **F-S4b-6 — mid-socket rotation changes the bound token's state, and
  the lapsed-grace case reads `unknown`, not `expired`.** Re-verify on
  alarm wake classifies the *bound* token against the pinned classifier:
  after a rotation the bound token reads `grace` (15 min) — then, once
  the grace lapses, it matches neither `token_hash` nor `prev_token_hash`
  and classifies `unknown` (`_classify_box_token` returns `(None, None)`;
  `expired` only fires when the *current* token is past
  `token_expires_at`). Grace proceeds (the socket stays up). A
  previously-bound token that now classifies `unknown` = grace lapsed →
  close `expired` + journal `expired_close` per §6 — the exact case §6's
  close table anticipates ("a post-rotation socket riding the previous
  token lands here once the 15-min grace lapses — do NOT rotate again,
  just use the current token"). Never-known tokens cannot occur at
  re-verify: bind required `current`/`grace`.
- **F-S4b-7 — the F389 watch: S4b has been deferred six times as a
  "2+ slot" item, and the ~45-min slot discipline is now its structural
  blocker.** The decomposition in §5 is the fix: four slices, each
  ≤ one slot, each harness-first, deployable in the stated build order
  (4→1→2→3) with each slice live-verifiable on landing — "independently
  deployable" means order-respecting independence, not
  order-indifference: S4b-2 emits onto S4b-1's bound socket and S4b-1–3
  emit into S4b-4's sink. No slice may grow a fifth; if one does, it
  splits again rather than deferring. Pre-declared split line for the
  likeliest overflow: S4b-2 divides into 2a (re-drive + D15 wakeup RPC)
  / 2b (socket ack consume-half + shared-helper hoist).

## 4. Decisions pinned (continuing the wire doc's D-series)

- **D14 — DO re-derives the handshake identity.** `BoxDO.fetch`
  re-classifies the upgrade request's `Authorization` Bearer <redacted> via
  the shared module-level `_classify_box_token`. No Worker→DO identity
  carry, no new trust surface. The `hello` frame's `box_id` self-assertion
  MUST equal the re-derived identity; mismatch → close
  `identity-mismatch` + journal (spec §2).
- **D15 — Worker→DO wakeup RPC on enqueue, no polling.** After a
  successful `_enqueue_command` (owner API + #873 approval decisions),
  the Worker calls the box's stub on an internal
  `/internal/commands-wakeup` route (not an upgrade request; never
  publicly routable — stubs are only reachable via Worker binding). The
  DO re-drives from the acked watermark on wakeup. Re-drive-on-bind
  covers reconnects; the RPC covers the steady state. The DO never polls
  D1 on a timer. Three failure rules are pinned with the decision:
  (a) a wakeup arriving with **no bound socket** (box disconnected, DO
  evicted/hibernated) is a **no-op** — the next (re)bind re-drives, so
  nothing is emitted into the void; (b) enqueue-succeeds/wakeup-fails →
  the Worker **retries once**, bounded and loud on final failure; the
  standing HTTPS fetch path is the backstop, so the failure mode
  degrades to fetch-path latency, never loss; (c) a wakeup racing a
  (re)bind re-drive may double-emit — absorbed by the at-least-once
  contract, the box's `(box_id, seq)` dedup, and the conditional
  lease-stamp UPDATE, stated here so the implementer doesn't invent a
  second dedup.
- **D16 — journal sink is a new D1 table.** `phone_home_events`
  (`box_id`, `event`, `generation`, `seen_generation`, `code`,
  `server_time`; no payloads, no tokens, no frame contents — §9's rule),
  forward migration `migrate_958_s4b.sql`, owner-only read path
  (consistent with #872's approval records), 90-day retention (bounds the
  table; same horizon as the waitlist funnel's 90-day retention) with a GC
  follow-up filed, not deferred silently. Tenant-privacy: `box_id` only
  today; the H10/H11 tenant dimension extends this table when it lands
  (the same operator-declared mapping rule as G16's interim box_id rule).
  Wire spec §9's "fleet event journal" reference is corrected to this sink
  by the S4b-4 slice — §9 named a sink that doesn't exist on the plane
  (F-S4b-1), and the correction ships with the table, not as a
  drive-by doc edit. **Per-event column mapping** (all six §9 events):
  `phone_home.connect` → generation=bound generation, code=NULL;
  `phone_home.disconnect` → generation=bound generation,
  code=close code; `phone_home.hibernate_wake` → generation=bound
  generation, code=wake cause (`alarm`|`inbound`); `phone_home.generation_fence`
  → generation=`last_generation`, seen_generation=the dropped frame's
  generation, code=NULL; `phone_home.revoked_kill` /
  `phone_home.expired_close` → generation=bound generation, code=NULL
  (the event name carries the close); `phone_home.identity_mismatch` →
  generation=the hello-asserted generation (NULL if the hello was
  malformed), code=NULL.
- **D17 — alarm interval 10 minutes.** Within spec §6's ≤ 15 min
  recommendation; the 30 s ping interval bounds the compliant-box case,
  the 10 min alarm bounds the silent socket. The honest ceiling is
  recorded in the S4b-3 slice's docs: revocation-latency ≤ 10 min for a
  silent socket, ≤ 30 s for a compliant one.
- **D18 — hibernation API verification is S4b-3's entry ticket.**
  Before committing the `acceptWebSocket`/alarm shape, the slice
  verifies `ctx.acceptWebSocket` + `ctx.storage.setAlarm` against the
  real workers-py runtime surface (the harness models it; the model is
  checked against the SDK, per the harness_958_s4a precedent that caught
  three masked runtime bugs). Not deferrable.

## 5. Slices (each ≤ one slot, harness-first, independently deployable)

**S4b-1 — hello, identity binding, generation fence. SHIPPED 2026-10-05
(#1000, PR #1055, deployed live).** The §2 hello handshake and §5
generation fence run in `BoxDO` against the deployed plane worker; wire
spec §7 carries the shipped pin.
`BoxDO.fetch`: re-derive identity per D14; read the first frame as
`hello`; `box_id` mismatch → `close`/`identity-mismatch` + journal;
malformed `hello` → `close`/`protocol-error`. Generation: `hello`
with `generation > last_generation` (DO durable storage) binds the new
socket and closes the old one `superseded-generation`; `<=
last_generation` → `close`/`stale-generation` carrying `last_generation`;
then `welcome` with `accepted_generation`. Every subsequent frame is
checked: `generation < last_generation` → drop + journal
`phone_home.generation_fence`; frames arriving on any socket other than
the bound socket are dropped (spec §5). Unknown control `type`s are
ignored (forward compatibility, §3.1); the 4 KB control-frame bound is
enforced.
*Acceptance:* harness matrix — good hello → welcome; identity mismatch
→ close + journal; stale generation → close carrying last_generation
(never protocol-error); superseded → old socket closed; replayed frame
on old generation dropped + journaled; frame on non-bound socket
dropped; oversized control frame refused; the fence check runs before
the unknown-`type` ignore (a stale-generation frame of an unknown type
is still fenced, not ignored). Live: the #959 box client
completes hello/welcome against the deployed plane.

**S4b-2 — command re-drive + socket ack consume half. PARTIALLY LANDED
(2026-10-07): the emit half is in the deployed worker checkout via
in-flight #1001 S4b-2a work (sibling feature turn live, review pending) —
re-drive on (re)bind + the D15 wakeup RPC, leases stamped exactly as the
HTTPS path, `phone_home.redrive` journaled (D-MAL1 malformed-row skip);
the socket `command_ack` consume-half (S4b-2b) is still open.**
On (re)bind and on the D15 wakeup RPC, the DO reads the acked watermark
(the existing `MAX(seq) ... state='acked'` query — no second cursor) and
emits `command` frames onto **S4b-1's bound socket** (the bound-socket
concept is S4b-1's prerequisite; without it there is no emission target)
for current-epoch rows with `seq > watermark`
(the pending-fetch SELECT shape: `epoch = ? AND seq > ? AND
(state='pending' OR (state='leased' AND lease_until <= ?))`), stamping
leases exactly as the HTTPS path does. The DO consumes `command_ack`
frames: `generation` must equal the bound generation (else drop — the
stale-session fence, §3.3); the ack UPDATE is the hoisted shared helper
(F-S4b-3), pending/leased-only, idempotent. The Worker's `_commands_ack`
is refactored onto the same helper, behavior-identical. A (re)bind
NEVER calls `_expire_inflight` — only epoch claims do (#848 header
comment; the DO's re-drive path selects current-epoch rows only).
*Acceptance:* harness — re-drive emits exactly the unacked set;
socket acks advance the watermark identically to HTTPS acks (parity
matrix: socket-only, HTTPS-only, mixed); stale-generation acks
dropped; ack of an `expired`-epoch row never rewrites it to `acked`;
reconnect re-drives without `_expire_inflight` firing (in-flight
commands survive). The `_commands_ack` refactor lands as its own
commit inside the slice, so the live HTTPS path rolls back
independently of the DO's ack ingest. Live: box receives a command
over WSS, acks over the socket, watermark advances; S6 item 3's
re-drive leg.

**S4b-3 — ping/alarm revocation re-verify + hibernation.**
D18 verification first. Then: move to `self.ctx.acceptWebSocket(server)`;
answer `pong` to box `ping`; the DO MAY ping on its own schedule; no
pong within 90 s of a ping → hibernate (wake on next box connect or
inbound frame). `ctx.storage.setAlarm` every 10 min (D17): on wake,
re-classify the bound token (F-S4b-6 — full current/grace/expired/revoked
mapping); `revoked` → close `revoked` + journal `revoked_kill`;
`expired` → close `expired` + journal `expired_close`; grace proceeds.
The honest latency bound (≤ 30 s compliant, ≤ 10 min silent) is recorded
in the slice's docs.
*Acceptance:* harness — alarm wake with revoked fixture → `revoked`
close + journal; expired → `expired` close; grace → socket stays;
post-grace-lapse (bound token now classifies `unknown`) → `expired`
close + journal `expired_close` (F-S4b-6); pong-timeout → hibernate;
wake re-verifies before accepting further frames. Live:
revoke-during-socket closes on next inbound/wake (S6
item 2's plane half).

**S4b-4 — journal sink + events. SHIPPED 2026-10-04 (#999, PR #1014).**
D16's decision implemented as shipped: `phone_home_events` D1 table
(created by `migrate_958_s4b.sql`, re-run safe), the DO's
`_journal_phone_home_event` helper as the only writer (never
payloads/tokens/frames), the owner-only
read path `GET /v1/boxes/{box_id}/phone-home/events`, 90-day retention
with the daily Worker cron + manual `POST /v1/ops/phone_home/gc` (#1013),
and the wire spec §9 sink correction to this table.
D16: `migrate_958_s4b.sql` creates `phone_home_events`; the DO's
`_journal_phone_home_event` helper writes it (box_id, event, generation, code,
server_time — never payloads/tokens/frames); owner-only read path;
90-day retention + GC follow-up filed. Correct wire spec §9's sink
reference to the D1 table. Worker-side: the unattributed pre-handshake
401 counter §9 permits (S4 "may keep" — upgrade auth failures are the
Worker entrypoint's lane, not DO journal events).
*Acceptance:* harness — every §9 event lands with the D16
per-event→column mapping above and nothing else (in particular
`generation_fence` carries both `generation`=`last_generation` and
`seen_generation`); pre-handshake 401s never create DO journal rows;
retention bound documented. *Build order note:* S4b-4's sink decision
is a prerequisite for S4b-1–3's emission call sites — build S4b-4
first, or land 1–3 against a `_journal_phone_home_event` no-op stub that S4b-4
replaces. Recommended: 4 → 1 → 2 → 3.

## 6. Explicit non-scope

Stream/input frame classes (#853/#919 — the registry reserves them;
the DO's generation fence in S4b-1 already covers every class, but no
stream/input payload handling is built here). Approval decisions (#873 —
durable channel, never a WSS frame class). Any write to
`last_heartbeat.json` or heartbeat freshness (§8 — the socket never
touches liveness). Box-side changes (#959/#976 shipped; the S5 client
already speaks every frame S4b-1–3 implement). Desktop/SFU (#854).

## 7. Deployment and acceptance wiring

Each slice deploys via `deploy_worker.py` per
`docs/PRODUCTION_DEPLOY_CONTRACT.md` (deployed-bytes SHA-256 verified,
live smoke per slice). Each slice extends the real-worker harness
(`harness_958_s4a.py` → `harness_958_s4b.py`) against the sqlite D1 stub
before any deploy. #960 (S6) consumes all four: its six-item checklist
(two-box no-cross-talk, revoke-during-socket, reconnect-resume,
stale-generation fence, fallback honored, epoch untouched) is the
integration gate. S4b-4 (#999) and S4b-1 (#1000) have shipped; #958 stays
OPEN until S4b-2 (#1001) and S4b-3 (#1002) land (S4b-2's emit half is
partially landed in the deployed checkout — see §2); #847 stays OPEN until
S4b + S6.
