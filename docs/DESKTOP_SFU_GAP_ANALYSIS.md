# Interactive-desktop SFU gap analysis (#854)

**Vision vs current state.** Statuses pinned to this repo at main `fa4da24`
(#897 funnel-events retention, 2026-10-03). The control plane
(`sparkvm-control` worker) lives outside this repo; plane-side facts below
are the standing ones from the prior analyses (no fresh plane read this
turn — none of them change the desktop-lane state). Cloudflare Realtime SFU
product facts were verified against `developers.cloudflare.com/realtime/`
this turn (2026-10-03). Doc-first; honesty rules apply
(`docs/POSITIONING.md`): everything below is **current state and work to
do**, not promises.

This is the #854 slice of the hosted build queue. #847 (phone-home),
#849 (phone approvals), #850 (credential vending), #851 (provisioning),
and #853 (terminal streams + R2) got the same treatment. Related vision
material: `docs/HOSTED_GAP_ANALYSIS.md` (signup→box pipeline),
`docs/REMOTE_DESKTOP_TRANSPORT_RESEARCH.md` (the #47 desktop-transport
bake-off — still unexecuted, §7 gates owed), `docs/CODEC_LICENSING_RESEARCH.md`
(H.264 Baseline via `x264enc` for the CPU-only fleet; counsel-level
sign-off still owed), `docs/STREAM_OWNERSHIP_DESIGN.md` (D3/D5/D6 session
semantics the terminal lane designed, not built).

## 1. The vision (#854 — verbatim)

> The long-term interactive desktop path is Cloudflare Realtime (SFU) —
> WebRTC-class low-latency streaming, never screenshot-polling.
> (Cloudflare Stream is not the path.)
>
> Acceptance:
> - Box publishes its desktop; owner views/interacts from the dashboard.
> - Latency suitable for interactive use; mobile gesture spec from #47 applies.

The #47 mobile spec (user-set, standing): floating toolbar, gestures —
pinch to zoom, tap = click, hold = left click, cursor mode = draggable
pointer — copy/paste bridges both clipboards; transport is WebRTC-class
low-latency streaming, never slow screenshot-polling frame sync.

## 2. Current state

| Vision element | Current state |
|---|---|
| Box publishes its desktop | **Nothing.** The box runs Xvfb `:98` + XFCE with `cua/bin/cua-bridge.py` (localhost-only, `X-CUA` CSRF): `GET /api/screenshot` is a PNG poll — the exact screenshot-sync class the vision forbids. `POST /api/click|type|key` give synthetic input. There is **no encoder, no WebRTC publisher, no persistent box process** — #847 G47.1 (the `boxd` decision) is still open, and #864's heartbeat sender is cron, not a daemon. |
| Cloudflare Realtime SFU usage | **Nothing.** No Realtime app, no app secret anywhere, no session-creation code. Product facts (verified 2026-10-03): the SFU routes WebRTC media tracks + DataChannels; **your backend holds the app secret** and creates sessions via the Realtime API (`rtc.live.cloudflare.com/v1`), authenticates users, authorizes publish/subscribe, and shares session/track ids through your application state. **The SFU defines no rooms, participants, roles, or presence** — the app owns all of it. Pricing: $0.05/GB egress, first 1,000 GB/month free (SFU + TURN shared); TURN is free when used with the SFU (`turn.cloudflare.com`, anycast). |
| Session/presence plane | **Nothing.** No session registry, no publish/subscribe authorization endpoints. The plane worker is a plain Workers-Python Worker (D1-backed): no WebSocket upgrade handler, no DO class (#847 open). Sessions, expiry, revocation — none of it exists. |
| Viewer surface | **Nothing.** The fleet dashboard (`hosted/dashboard/`, owner-authenticated per #845) is fleet rows only: no video element, no WebRTC client, no input forwarding, no gesture layer. |
| Mobile gestures | **Spec only.** The #47 gesture set is documented (standing user spec) with no client behind it. |
| Desktop-transport research | **Designed, never measured.** `docs/REMOTE_DESKTOP_TRANSPORT_RESEARCH.md` recommends prototyping Selkies-GStreamer first (fallbacks: Sunshine as host + Moonlight-Web web client, then Xpra shadow) — but its **§7 prototype gates never ran**: no CPU-only encode measurement, no :98 capture verification, no input-fidelity pass, no reachability test. Its standing quarterly upstream-health check (Selkies "needs maintainers" risk, §4) never ran either. The recommendation is unmeasured on spark-vm hardware. |
| Codec story | **Researched, not shipped.** `docs/CODEC_LICENSING_RESEARCH.md`: H.264 Baseline via `x264enc` for the CPU-only fleet; browser decode reality — H.264 is the only codec in every major browser **including all of iOS** (load-bearing for the mobile viewer). Counsel-level sign-off still owed (§8 of that doc). |
| TURN / hosted NAT reachability | **Solved in principle, unused.** The transport research's §5.2 reachability problem (provider ingress can't carry ICE/RTP media; operator-run TURN relay as new infrastructure with a bandwidth-cost line) **evaporates on the SFU path**: Cloudflare's TURN rides free with the SFU. This is the hosted lane's decisive advantage over the self-hosted WebRTC prototypes — no TURN relay to operate. |
| Self-hosted parity | **Unproven — asserted as a design constraint, verified by no slice yet.** The both-supported default is the target: the capture+encode pipeline (GStreamer) must stay transport-agnostic — the same pipeline publishing to the Cloudflare SFU (hosted) or to a self-hosted target. Note the honest gap: the transport research's ladder (Selkies-GStreamer → Sunshine+Moonlight-Web → Xpra) names non-SFU protocols, not "a self-hosted SFU" — S3's acceptance (parity probe) is what proves the seam is real rather than aspirational: either a demonstration against a non-Cloudflare WebRTC target, or the session/SFU target seam named as an explicit interface with the self-hosted binding scoped as a follow-up. Until then, "transport-agnostic" is a design constraint, not a fact. |
| Terminal lane (#853) | **Analyzed, same session discipline.** The terminal-stream spec (new issue #919) is this lane's low-bandwidth cousin: G53.2's read/write split applies here too — streams are observation, **input is an action on its own channel class**, and approval is the consent plane (#849), never the transport. |

## 3. Gaps

- **`[BLOCKER]` G54.1 — no box-side publisher.**
  The acceptance starts "box publishes its desktop" and there is no
  publisher. The slice must answer: (a) capture — attach to the existing
  `:98` (xdamage-diff capture), never launch a competing X server (the
  selkies-launches-its-own-X-server failure mode, transport research §7,
  gate 3);
  (b) encode — H.264 Baseline via `x264enc` per the codec research
  (CPU-only fleet; iOS decode reality); (c) publish — WebRTC publish of the
  encoded track to the SFU session (S2's session handle, §4). Recommended
  shape: **GStreamer `webrtcbin`** — capture+encode is transport-agnostic,
  so the same pipeline serves the hosted SFU and the self-hosted lane
  (parity — but see the §2 row: unproven until S3's parity probe). The
  process lives in the #847 S5 `boxd` (shared backoff/reconnect) but may
  be prototyped standalone before `boxd` exists — with a defined seam:
  the standalone prototype implements the publisher-as-supervised-process
  contract from day one (boxd owns session discovery, lease signals, and
  backoff; the publisher takes a session handle and an input-enable flag
  as input and owns only capture+encode+publish lifecycle). The prototype
  stub-fakes only the discovery feed — it must not invent its own backoff
  or lease logic, or the stranded publisher's de-facto interfaces become
  the contract boxd has to swallow. License rule from the transport
  research: GPLv3 components are consumed as external
  dependencies only — never vendored into the repo tree. Filed as a new
  issue (see §6).
- **`[BLOCKER]` G54.2 — the SFU has no rooms, so the session plane is ours
  to build.**
  This is the load-bearing design call the issue body skips: Cloudflare
  gives you forwarding, not a product. Nothing exists — no session
  registry, no authorization endpoints, no app secret anywhere. The S2
  slice builds: plane endpoints to request/open/close a desktop session
  (owner auth, the #845 dashboard shape); the plane holds the Realtime app
  secret **in worker env (deploy config, never the repo)** and creates SFU
  sessions via the Realtime API; a D1 `desktop_sessions` table
  (`session_id`, `box_id`, owner, SFU session/track ids, `created_at`,
  `expires_at`, `revoked_at`) — sessions expire and are revocable, and
  revocation kills the SFU session; authorization as box=publish /
  owner=subscribe with session ids server-derived from the **verified** box
  identity (the G47.5 pattern — never a client-supplied key). Signaling
  carrier is the slice's open decision: HTTPS polling works now, the #847
  WSS channel is the natural control carrier later — do not block S2 on
  #847 — with a recorded constraint: the interim carrier's poll interval
  is the worst-case revocation latency (a revoked input lease stays armed
  on the box for up to one poll interval), so the slice bounds it (or
  gives sessions a max TTL honored box-side) and the bound lands in S2's
  acceptance; the #847 WSS channel remains the target carrier. S2 also
  pins the **S2↔S3 box-facing session-handle schema** — SFU endpoint,
  publish credential, session/track ids, lease/revocation signal carrier,
  generation — the contract S3's publisher consumes. The handle's
  endpoint+credential fields are opaque and SFU-agnostic, so a self-hosted
  SFU endpoint slots into the same schema — that is what makes the box
  publisher transport-agnostic enforceable rather than aspirational.
  Filed as a new issue (see §6).
- **`[DESIGN]` G54.3 — input is an action, not pixels.**
  Owner input (click/type/key) flows dashboard → SFU DataChannel → box →
  cua-bridge's localhost-only `/api/click|type|key` (they already exist).
  The G53.2(a) split holds: viewing is observation, **input rides a
  dedicated DataChannel class** — never the media track, never the #849
  approvals decision wire. Owner-typed input into their own box is
  frictionless under owner auth; where an input action needs human
  authorization, the *decision* rides the approvals channel and the *bytes*
  ride the input channel — approval is the consent plane, not the
  transport. The unmade argument for the DataChannel wire: killing the SFU
  session kills media *and* input atomically — revocation never has to
  chase two wires. Session-scoped: one interactive driver per desktop
  stream (the D1 lineage), with audited open/close (D6). The control plane
  owns lease state; the box publisher enforces the input-channel binding —
  only the current lease-holder's DataChannel input is honored.
  Lease/revocation signals ride the S2 session carrier; on carrier loss
  the publisher fails closed (drops input, D1). The box journals
  input-session open/close into the fleet event journal (G54.7) — the plane
  cannot observe DataChannel traffic, so audit is box-sourced. Driver
  contention between the owner's interactive session and the tenant Muse's
  programmatic input follows the D4 handoff protocol (claim/yield,
  server-side grace, owner forced takeover) — the protocol already says
  who wins. Filed as part of the viewer issue (see §6).
- **`[DESIGN]` G54.4 — the viewer is a build, not a skin.**
  The dashboard needs a real WebRTC subscribe path: video element,
  session-scoped owner auth, the #47 mobile gesture set (pinch zoom,
  tap=click, hold=left-click, cursor-drag, clipboard bridge) — all
  client-side, all testable against the S3 publisher through the SFU.
  Filed as a new issue (see §6).
- **`[BLOCKER]` G54.5 — trust model: media transits Cloudflare.**
  The SFU is a forwarding unit on Cloudflare's edge: tenant desktop pixels
  flow box → Cloudflare → owner browser (SRTP/DTLS in transit per WebRTC;
  nothing at rest on the plane) — and the input DataChannel bytes transit
  it too (clicks, keys, pasted text). This is NOT the rejected
  `stream.moonlightweb.top` relay (a third-party hobby domain with an
  expiry date) — it is our own Cloudflare account — but it is still a
  third-party media hop and must be documented as one (POSITIONING
  honesty): what Cloudflare can observe (media *and* input bytes), what
  the tenant is told, and that the self-hosted lane keeps media on the
  tailnet. The S2 slice writes this down as an explicit trust-model-doc
  deliverable; it is not a reason to avoid the SFU, it is a reason to name
  the trust boundary. Folds into the session-plane issue.
- **`[DESIGN]` G54.6 — desktop streaming is the heaviest cost surface.**
  $0.05/GB after the 1,000 GB/month free tier. At 720p30 H.264
  (~1–2 Mbps) a viewer burns ~0.45–0.9 GB/hour — the free tier is roughly
  1.1k–2.2k viewer-hours/month: fine for the beta cohort, unbounded for a
  real fleet. The design work: the usage-*measurement source* (the plane
  never sees media bytes, so S2 must decide — Cloudflare Realtime usage
  API granularity vs session-duration × negotiated-bitrate estimate), the
  quota ledger shape, kill-switch mechanics, budget-alert wiring — into
  the H12 metering lineage (#380). The quota call is not "refuse
  over-budget requests": streaming minutes accrue *during* the session, so
  the slice must **reserve a max-session-duration budget at request time**
  (the D1-pending-row analog of the G53.6 mint race), or two racing
  session requests both pass before either accrues minutes. Acceptance:
  over-budget session requests refused at request time; budget alert
  fires; reservations released on session end. Folds into the
  session-plane issue's design + acceptance.
- **`[OBSERVABILITY]` G54.7 — feed the fleet journals.**
  Session open/close/auth-failure events in the G16/G17 envelope (the
  G47.7 pattern) so the P7 status page can render desktop health honestly —
  distinct from heartbeat freshness (box↔plane liveness) and the relay's
  `connection-unreachable` (tenant↔box liveness). Three liveness sources,
  three signals, never confused in status surfaces. Dependency honesty:
  the fleet journal itself is unbuilt (#796–#800 open; #847's journal
  feed is a shape) — so S2 **emits the events in the envelope and delivers
  them to the journal when it lands; it does not block on the journal's
  existence**. The box journals input-session open/close (G54.3) —
  box-sourced, because the plane cannot observe DataChannel traffic.
  Folds into the session-plane issue.
- **`[RESEARCH]` G54.8 — the transport research's §7 gates are still owed.**
  Every measurement the recommendation rests on (CPU-only encode on a 2–4
  vCPU box, :98 capture cleanliness, input fidelity, congestion behavior,
  per-path reachability) is unexecuted, and the quarterly upstream-health
  check never ran. For the hosted lane the SFU answers the *media-plane*
  question, but the *box-side* half of the gates (capture, CPU encode,
  congestion degradation) still gates the S3 publisher — so S3's
  acceptance includes that subset, measured, with numbers. The self-hosted
  bake-off (Selkies → Sunshine+Moonlight-Web → Xpra) remains a #47 item,
  untouched by this analysis.

**Explicit non-goals for this slice:** Cloudflare Stream (the issue rules
it out explicitly); terminal streams (#853) — the low-bandwidth cousin,
sharing the session/input discipline, not the transport; credential
vending (#850) — orthogonal, the publisher needs no secret on the box
beyond its existing bearer.

## 4. Slice plan (dependency order)

- **S1 — Realtime app provisioning (operator-owned).** Create the
  Cloudflare Realtime app; put the app ID + app secret into the
  `sparkvm-control` worker env (deploy config, never the repo). This is a
  **user/operator step** — logged in NEEDS_USER.md, not stalled on. S2–S5
  cannot ship without it.
- **S2 — desktop session plane** (new issue #935): G54.2 + G54.5 + G54.6
  (design + acceptance) + G54.7. Session endpoints, D1 `desktop_sessions`,
  SFU session creation with the env-held secret, publish/subscribe
  authorization, expiry + revocation, trust-model doc (G54.5 — media *and*
  input bytes), the **S2↔S3 box-facing session-handle schema** (SFU
  endpoint, publish credential, session/track ids, lease/revocation
  signal carrier, generation — opaque, SFU-agnostic), usage-measurement
  source decision + quota-ledger + kill switch + max-session-duration
  budget reservation (G54.6), event emission in the G16/G17 envelope
  (G54.7 — not blocked on the journal's existence). Signaling-carrier
  decision (HTTPS now vs #847 WSS later) in the slice, with the recorded
  revocation-latency bound. Acceptance: owner requests → plane creates SFU
  session → box publishes → owner subscribes; revoke-during-session kills
  the SFU session (media *and* input atomically); the carrier's
  revocation-latency bound is measured; subscriber→publisher DataChannel
  routing verified against the live Realtime API (not all SFU topologies
  route arbitrary subscriber→publisher data); over-budget requests
  refused at request time; reservations released on session end.
- **S3 — box-side SFU publisher** (new issue #936): G54.1 + the box-side
  half of G54.8. GStreamer `webrtcbin` capture of `:98`, H.264 Baseline
  `x264enc` encode, WebRTC publish to the SFU session — consuming only the
  S2↔S3 session-handle schema (SFU-agnostic). Standalone-prototype allowed
  with the supervised-process seam from day one (boxd owns discovery,
  leases, backoff later; the publisher owns only capture+encode+publish);
  transport-agnostic shape for parity; no GPL in the repo tree.
  Acceptance: measured CPU-only capture/encode at 720p and 1080p (the
  transport research's §7 gates 2/3/4/6 subset, with numbers); **parity
  probe** — the capture+encode pipeline is demonstrated against a
  non-Cloudflare WebRTC target (self-hosted receiver), or the
  session/SFU target seam is named as an explicit interface with the
  self-hosted binding scoped as a follow-up. The measurement half needs
  no Realtime app secret — it is S1-independent and may run in parallel
  with S2.
- **S4 — dashboard viewer + gestures** (new issue #937): G54.3 + G54.4.
  WebRTC subscribe in the dashboard, the #47 mobile gesture set, input →
  DataChannel → cua-bridge endpoints, audited input sessions. Acceptance:
  the **input-contention rule is defined, implemented, and exercised** —
  owner vs agent synthetic input sharing the display, who wins (the D4
  handoff protocol), with a test that proves it.
- **S5 — acceptance verification** (stays on #854): end-to-end
  publish → SFU → dashboard with a **measured** glass-to-glass latency
  against the "suitable for interactive use" bar (a number, not an
  adjective); no inbound ports (outbound-only publish, like heartbeat);
  revoke-during-session kills the SFU session; revoke-during-input-session
  kills input within the carrier's latency bound; box fails closed on
  session-carrier loss (drops input, D1); box A cannot view or
  publish box B's session (namespace isolation on server-derived session
  ids, filename-style normalization N/A here — the ids are ours);
  owner input works end to end; a month of free-tier burn measured and
  metered; the media-transits-Cloudflare trust note published.

## 5. Shape sketch (reserved, not final)

The owner requests a session: `POST /v1/desktop/sessions {box_id}` (owner
auth, #845 shape). The plane creates the SFU session via the Realtime API
(`rtc.live.cloudflare.com/v1`) with the app secret from env, writes
the D1 `desktop_sessions` row (box_id, owner, SFU session/track ids,
`expires_at`), and returns the session handle. The box learns its session
(the S2 slice picks HTTPS poll vs #847 WSS control frames) and its
GStreamer pipeline `webrtcbin`-publishes the `:98` capture + H.264
Baseline encode to the SFU. The dashboard subscribes (WebRTC) and maps
gestures to input events; input events ride a dedicated SFU DataChannel
class to the box, which forwards them to the localhost-only cua-bridge
`/api/click|type|key`. Auth reuses existing primitives everywhere — box
bearer, owner keys — no new identity primitive. Revocation: the plane
deletes the SFU session and marks `revoked_at`; the box stops publishing
on session-gone and backs off. Nothing above invents crypto; the exact SFU
API request/response shapes are pinned in the S2 slice against the live
API, not assumed here.

## 6. New backlog items filed by this analysis

- **New issue #935: desktop session plane** (G54.2/G54.5/G54.6, S2) — the
  SFU defines no rooms/presence: session endpoints, D1 `desktop_sessions`,
  env-held app secret, publish/subscribe authorization, the S2↔S3
  box-facing session-handle schema (opaque, SFU-agnostic), trust-model doc
  (media *and* input bytes transit Cloudflare), metering into H12
  (measurement source + budget reservation at request time), journal
  feeding (events in the G16/G17 envelope; not blocked on the journal).
  Blocked on S1 (Realtime app provisioning — NEEDS_USER.md).
- **New issue #936: box-side SFU publisher** (G54.1, S3) — `:98` capture,
  H.264 Baseline `x264enc`, GStreamer `webrtcbin` publish to the SFU
  session (consuming only the S2 schema); publisher-as-supervised-process
  seam from day one; parity probe (non-Cloudflare WebRTC target, or the
  seam named with the self-hosted binding as follow-up); box-side half of
  the transport research's §7 gates as measured acceptance (S1-independent).
- **New issue #937: dashboard desktop viewer + mobile gestures** (G54.3/G54.4,
  S4) — WebRTC subscribe in the dashboard, the #47 gesture set, input on
  the dedicated DataChannel class → cua-bridge endpoints, D1/D4 input
  contention rule defined + implemented + exercised, box-sourced input
  audit. Tested against the S3 publisher (#936).
- #854 stays the tracker; the PR's pointer comment carries the §4 slice
  plan and the §5 sketch. S5 acceptance lives on #854.

## 7. Honest summary

The media plane exists — Cloudflare's SFU is a live product, verified
today — but we use none of it. What exists: the `:98` desktop, the
cua-bridge's capture/input endpoints, the transport research (unexecuted
gates), the codec research (H.264 Baseline recommendation), the dashboard
shell, owner auth, box bearer auth. The load-bearing calls: the SFU has
no rooms or presence, so the session plane is the product work; input is
an action on its own channel class; media transits Cloudflare (a trust
call, documented, not avoided); the box-side publisher is the heaviest
engineering; the self-hosted lane keeps its own transport (parity). S1 —
provisioning the Realtime app and its secret — is operator-owned: logged
in NEEDS_USER.md, and everything downstream waits on it.
