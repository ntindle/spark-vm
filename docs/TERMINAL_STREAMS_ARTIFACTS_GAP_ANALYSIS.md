# Terminal-streams + R2-artifacts gap analysis (#853)

**Vision vs current state.** Statuses pinned to this repo at main `d058a10`
(#532 failure freeze, 2026-10-03). The control plane (`sparkvm-control`
worker) lives outside this repo; plane-side facts below are pinned to a
2026-10-03 read of the plane workspace (worker.py + schema.sql + migrations
through #872), not to a repo commit. Doc-first; honesty rules apply
(`docs/POSITIONING.md`): everything below is **current state and work to
do**, not promises.

This is the #853 slice of the hosted build queue. #847 (phone-home),
#849 (phone approvals), #850 (credential vending), and #851 (provisioning)
got the same treatment. Related vision material: `docs/HOSTED_GAP_ANALYSIS.md`
(signup→box pipeline), `docs/STREAM_OWNERSHIP_DESIGN.md` (D3 pins
per-session terminal streams), `docs/REMOTE_DESKTOP_TRANSPORT_RESEARCH.md`
(WebRTC-class bar for the desktop lane).

## 1. The vision (#853 — verbatim)

> Later product slices:
> - Live terminal streams from the box through the control plane (via the
>   box's Durable Object).
> - Agent artifacts (files, build outputs) upload outbound from the box to R2.
>
> Acceptance:
> - Terminal output streams with low latency; no inbound ports.
> - Artifacts land in R2 namespaced per box, retrievable from the dashboard.

## 2. Current state

| Vision element | Current state |
|---|---|
| Box→plane stream transport | **HTTPS POST polling only.** Heartbeat (`spark_pair.py heartbeat`, cron, `{ok:true}`-gated, #864), pairing endpoints, #848's durable command channel (enqueue/pending/ack, leased, epoch-scoped). **No persistent connection anywhere.** |
| The box's Durable Object | **Does not exist.** #847 is analyzed only (`docs/PHONE_HOME_GAP_ANALYSIS.md`): no WS upgrade handler, no DO class, no `durable_objects` binding, no migration in the plane workspace — and no wrangler config at all, so the DO's deploy shape starts from zero. |
| Box-side stream producer | **Nothing.** No pty capture, no terminal endpoint, no long-lived box process anywhere in this repo (`hosted/`, `cua/`, `deploy/` all grep-clean for pty/capture-pane/terminal-stream). `cua/bin/cua-bridge.py` is localhost-only (`127.0.0.1:18731`, `X-CUA` CSRF header) with no terminal surface. The #847 analysis already named the missing persistent process (`boxd`, G47.1) — the terminal producer is that process's first workload alongside the WSS client. |
| Terminal session semantics | **Designed, not built.** `docs/STREAM_OWNERSHIP_DESIGN.md` D3: terminal streams are per-session (one pty, one input), no shared-driver contention, per-box session cap, session-scoped auth (D5), audited transitions (D6). No implementation of any of it. |
| Plane→viewer fan-out | **Nothing.** The fleet dashboard (`hosted/dashboard/`, owner-authenticated, #845) has no terminal or stream UI; its rows come from pairing/enrollment + heartbeat freshness. No SSE, no viewer WebSocket, no stream-subscription endpoint on the plane. |
| R2 artifact upload | **Nothing.** No bucket, no binding on the worker (worker.py is grep-clean for r2/bucket/presign), no upload code, no download surface. The only R2 mention in the repo is the provisioning analysis's image-build note. No wrangler config exists in the plane workspace, so the R2 binding's deploy shape must be designed with the deploy — not inherited from config files that don't exist (the loop's prior deploys to this worker went through the Cloudflare API, not wrangler). |
| Artifact namespacing | **No concept of it.** The plane has no tenant dimension (#280 open — same caveat as #850's G50.3); box identity is bearer-derived (`sha256(token)` → box_id, #843/#844). Any per-box namespace must be derived from the *verified* identity, never a client-supplied key (the G47.5 pattern). |
| Artifact retrieval | **Nothing.** The dashboard has no artifact UI; the plane has no download endpoint. |

## 3. Gaps

- **`[BLOCKER]` G53.1 — the channel the vision names doesn't exist.**
  #853 says "through the control plane (via the box's Durable Object)" —
  but #847's DO + WSS phone-home is analyzed only. No upgrade handler, no
  DO class, no boxd, no WSS client (G47.1/G47.2/G47.6 all still open).
  Terminal streams ride that channel: you cannot stream over a socket that
  doesn't exist. #848's durable command channel exists and is live, but it
  is the wrong transport for real-time output (see G53.2) — it can carry
  stream *control* frames (open/close), not stream *data*.
- **`[DESIGN]` G53.2 — no stream wire protocol.**
  Terminal output is lossy real-time: ordered-per-session, no acks, no
  redelivery — the opposite of #848's at-least-once, leased, acked command
  frames. Routing stream bytes through the durable command queue would
  inherit lease/replay semantics that corrupt a live tail (a replayed
  lease-expiry re-delivers stale output). The spec must define a distinct
  frame class on the WSS channel (reserved alongside #848's frames), plus:
  (a) **read/write split** — viewing output is observation; *injecting
  input* into a terminal is an action and must not share the stream's data
  frame class. Input travels a dedicated **WSS input frame class**
  (ordered per session, fire-and-forget like data, under the D5
  session-scoped auth binding and D6 audit) — never the stream's data
  frames, and never the #849 **approvals decision channel**, whose wire
  shape is approve/deny/expire of a specific approval record, not
  interactive writes. Where an input action needs human authorization (the
  #849 case — e.g. an agent injecting input into a live terminal), the
  *authorization* is decided on the approvals channel and the *bytes* are
  delivered on the input frame class: approval is the consent plane, not
  the transport. Owner-typed input (the owner typing into their own box's
  terminal) rides the same input frame class under D5 auth with no approval
  step — D3's per-session interactive semantics hold for the owner,
  frictionless; (b) **viewer fan-out** — the DO fans out to owner-authenticated
  viewers (dashboard SSE or viewer WSS; the dashboard's owner-auth shape
  from #845 is the auth model); (c) **D3 compliance** — per-session pty,
  session-scoped auth binding (D5), audited open/close/handoff (D6);
  (d) **stream-loss semantics** — when the socket dies or egress blocks the
  WSS upgrade, does the stream pause, degrade to HTTPS long-poll, or end?
  (the G47.8 fallback/precedence pattern, load-bearing here too: which
  signal — socket state vs heartbeat freshness — the fleet journal and the
  P7 status page trust when they disagree). Stream and input frames both
  carry the #847 generation field (G47.4): after a reconnect with a bumped
  generation, the DO drops old-generation frames — a stale socket must
  never inject old stream data or old input into a new session. Filed as
  a new issue (see §6).
- **`[BLOCKER]` G53.3 — no box-side stream producer.**
  The box has no pty capture and no persistent process to host it (the
  heartbeat is cron-acceptable; a stream is not). The producer shape is
  decided with the #847 S5 boxd work — same process, shared backoff and
  reconnect loop — but the pty source is this slice's own design question:
  (a) spawn a dedicated pty per streamed session, or (b) attach to existing
  tmux panes (the box runs tmux for agent sessions). (a) is cleaner
  isolation; (b) streams what the agent is actually doing. Decide in the
  slice, not here. Filed as a new issue (see §6).
- **`[DESIGN]` G53.4 — stream content is secret-bearing.**
  Terminal output carries what the agent sees: env dumps, API keys in build
  logs, file contents. Owner views own box, so the principals match — but
  session-open must be explicit and audited (D6), the producer must never
  log frames, and the dashboard must treat stream content as
  owner-confidential (no caching in shared surfaces). Artifacts are
  arbitrary box bytes: the download path serves them `Content-Disposition:
  attachment` with sniffing disabled — never inline, never executed.
  Folds into the G53.2 spec issue.
- **`[BLOCKER]` G53.5 — R2: no bucket, no binding, no path.**
  Presigned-URL flow is the design that fits the constraints: the plane
  holds an R2 API token **in worker env only (deploy config, never the
  repo)** and mints short-lived presigned PUTs bounded to
  `artifacts/<box_id>/` with a content-length cap and ~15-min TTL; the box
  PUTs bytes **directly to R2 over outbound HTTPS** — the outbound-only
  invariant holds and stream bytes never transit the worker (no bandwidth
  or CPU cost on the plane). What's missing: the bucket itself, the
  token-in-env deploy shape (no wrangler config to declare it in — the
  API-deploy path must carry it), the mint endpoint, the box uploader, and
  the D1 `artifacts` table recording completions. Filed as a new issue
  (see §6).
- **`[DESIGN]` G53.6 — R2 namespace, quota, and retrieval.**
  Key prefix derived from the verified box identity (G47.5 pattern —
  `bearer → box_id → artifacts/<box_id>/`, never a client-supplied key);
  no tenant dimension until #280 lands (same caveat as #850 G50.3 —
  box-namespacing only, documented as provisional). Presigned PUTs cannot
  enforce content-length server-side, so the quota story must close the
  **mint race**: the mint endpoint writes a D1 **pending row** (key,
  box_id, minted_at, max_bytes) and counts pending + completed bytes
  against the per-box daily quota **at mint time** — a mint that would
  exceed quota is refused outright. A sweeper R2-deletes keys whose pending
  row is older than the URL TTL plus slack and never completed, so
  minted-but-never-completed uploads can't accumulate unbounded storage
  spend invisible to the ledger. The stronger alternative is presigned
  POST with a `content-length-range` policy (enforces size server-side);
  the slice may choose it over PUT. The `<filename>` component is
  server-normalized (basename + charset whitelist — a `../` in a
  box-supplied name must never mint an escaping key, or the S5 "box A
  cannot mint a URL outside its own prefix" acceptance fails at the
  server). The box's completion ack carries the final size and the plane
  HEAD-verifies before recording the completion row. Dashboard retrieval
  is owner-authenticated presigned GETs (short TTL) — the #845 dashboard
  auth shape, extended to a new artifact surface — with a sanitized
  filename on the download path. Folds into the G53.5 issue.
- **`[OBSERVABILITY]` G53.7 — feed the fleet journals.**
  Stream open/close/auth-failure events and artifact upload completions
  should land in the fleet event journal (the G16/G17 shape, G47.7
  pattern) so the P7 status page can render stream health honestly —
  distinct from heartbeat freshness (box↔plane liveness) and the relay's
  `connection-unreachable` (tenant↔box liveness). The plane-side events
  need a defined path into the box-journaled stream (e.g. piggybacked on
  the heartbeat response for boxd to journal). Three liveness sources,
  three signals, never confused in status surfaces. Folds into the
  G53.2/G53.5 issues' acceptance.

**Explicit non-goals for this slice:** the desktop SFU (#854) is a
different transport (WebRTC/TURN per the transport research) — the
terminal lane is its low-bandwidth cousin, not its dependency, and neither
blocks the other. #850's localhost credential vending is orthogonal: R2
uploads need no secret on the box at all under the presigned-URL design
(G53.5), so the two never share a credential path.

## 4. Slice plan (dependency order)

- **S1 — #847's S3/S4/S5** (wire protocol spec, plane DO class + upgrade
  handler, box WSS client + boxd). The hard prerequisite for terminal
  streams; do not build S2 first.
- **S2 — terminal-stream wire-protocol spec** (new issue, §6): G53.2 +
  G53.4 + G53.7(stream half). Real-time frame class on the WSS channel
  (never through #848's durable queue); a dedicated input frame class
  (never the stream's data frames, never the approvals decision channel —
  approval is the consent plane, bytes ride the input class); viewer
  fan-out to the owner-authenticated dashboard; audit discipline;
  stream-loss fallback rule; generation field on all frame classes.
  Builds on D3; does not re-litigate it.
- **S3 — box-side stream producer** (new issue, §6): G53.3. Lives in the
  #847 S5 boxd; pty-source decision (dedicated pty vs tmux attach);
  backoff/reconnect shared with the WSS client. May run in parallel with
  S4 once S2 pins the contract.
- **S4 — R2 artifact flow** (new issue, §6): G53.5 + G53.6 + G53.7
  (artifact half). Bucket + token-in-env deploy shape, presigned-PUT mint
  endpoint, box uploader, D1 `artifacts` table + quota ledger + reaper,
  dashboard retrieval surface (presigned GETs, attachment discipline).
  Independent of S1 — the R2 flow is plain HTTPS and can ship before the
  WSS channel exists.
- **S5 — acceptance verification** (stays on #853): stream latency
  measured end-to-end (box pty → DO → viewer) against the "low latency"
  bar with a number, not an adjective; no-inbound-ports verified at the
  box egress (outbound-only, like heartbeat); revoke-during-stream kills
  the socket on resume (the G47.3 pattern); artifact round-trip
  box→R2→dashboard with namespace isolation proved (box A cannot mint a
  URL outside its own prefix — filename normalization included);
  over-quota mint refused at mint time; minted-but-never-completed uploads
  swept and R2-deleted.

## 5. Shape sketch (reserved, not final)

Stream frames ride the #847 WSS channel as a distinct frame class from
#848's durable commands (the S2 spec assigns the class tag), and all
stream frame classes — data and input — carry the #847 generation field
(G47.4) so the DO's old-generation fence applies to them. Control
frames (`stream_open` / `stream_close`) may travel the durable command
channel; data frames never do — a data frame is fire-and-forget,
ordered per session, dropped on disconnect, never replayed. Input is a
separate WSS frame class (never the stream's data class, never the
approvals decision channel); where an input action needs human
authorization, the decision travels the #849 approvals channel and the
bytes travel the input class. Cross-channel ordering note for the S2
spec: control frames on #848 (HTTPS polling) and data frames on WSS have
no mutual ordering — `stream_close` must be session-id-keyed and race
in-flight data safely. Authentication is established once at the WSS
handshake (G47.3); viewers authenticate to the plane as owners (#845's
dashboard auth) and subscribe per box+session.
The R2 mint endpoint is `POST /v1/artifacts/upload-url` (box
Bearer <redacted>): `{key, url, expires_at, max_bytes}` with the key
server-derived as `artifacts/<box_id>/<uuid>/<filename>` (filename
server-normalized, basename + charset whitelist); the mint writes a D1
pending row and counts against quota before issuing the URL. The box PUTs
directly to R2, then `POST /v1/artifacts/complete` with the size for the
plane to HEAD-verify and record; uncompleted pending rows past TTL+slack
are swept and their keys R2-deleted. Nothing above invents crypto or a new
identity primitive: auth reuses the box bearer and the owner keys the
fleet already has.

## 6. New backlog items filed by this analysis

- **New issue #919: terminal-stream wire-protocol spec** (G53.2/G53.4,
  S2) — the real-time frame class, a dedicated input frame class (never
  the data frames, never the approvals decision channel — approval is
  the consent plane, bytes ride the input class; owner-typed input
  frictionless under D5), viewer fan-out, audit discipline, generation
  field on all frame classes, stream-loss fallback, cross-channel
  ordering, journal feeding.
- **New issue #920: box-side terminal-stream producer** (G53.3, S3) — pty
  capture in the #847 S5 boxd, dedicated-pty vs tmux-attach decision,
  shared backoff/reconnect.
- **New issue #921: R2 artifact-upload flow** (G53.5/G53.6, S4) — bucket +
  token-in-env deploy shape, presigned-PUT/POST mint endpoint with D1
  pending row + mint-time quota check + sweeper (closes the mint race),
  server-normalized filename, box uploader, D1 artifacts table,
  dashboard retrieval surface.
- #853 stays the tracker; the PR's pointer comment carries the §4 slice
  plan and the §5 sketch. S5 acceptance lives on #853.

## 7. Honest summary

Both halves of #853 are greenfield: no stream transport (the DO and WSS
channel #853 names don't exist), no box-side producer (no pty capture, no
persistent box process), no viewer surface, no R2 bucket or binding or
upload path. The one thing that exists is the *design* for terminal
session semantics (D3) and the *durable* command channel (#848) — which is
the wrong transport for real-time output and must be kept out of the data
path by design, not by accident. The dependency order is S1 (#847's
channel) → S2/S3 → S5 for streams, with the R2 flow (S4) shippable
independently on plain HTTPS. The read/write split is the load-bearing
security call: streams are observation, input is an action, and the two
must not share a frame class — with approval as the consent plane
(decided on the #849 channel) and a dedicated input frame class as the
transport, never the approvals decision wire itself.
