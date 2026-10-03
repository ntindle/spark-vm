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
| Cloudflare Realtime SFU usage | **Nothing.** No Realtime app, no app secret anywhere, no session-creation code. Product facts (verified 2026-10-03): the SFU routes WebRTC media tracks + DataChannels; **your backend holds the app secret** and creates sessions via the Realtime API (`https://rtc.live.cloudflare.com/v1`), authenticates users, authorizes publish/subscribe, and shares session/track ids through your application state. **The SFU defines no rooms, participants, roles, or presence** — the app owns all of it. Pricing: $0.05/GB egress, first 1,000 GB/month free (SFU + TURN shared); TURN is free when used with the SFU (`turn.cloudflare.com`, anycast). |
| Session/presence plane | **Nothing.** No session registry, no publish/subscribe authorization endpoints. The plane worker is a plain Workers-Python Worker (D1-backed): no WebSocket upgrade handler, no DO class (#847 open). Sessions, expiry, revocation — none of it exists. |
| Viewer surface | **Nothing.** The fleet dashboard (`hosted/dashboard/`, owner-authenticated per #845) is fleet rows only: no video element, no WebRTC client, no input forwarding, no gesture layer. |
| Mobile gestures | **Spec only.** The #47 gesture set is documented (standing user spec) with no client behind it. |
| Desktop-transport research | **Designed, never measured.** `docs/REMOTE_DESKTOP_TRANSPORT_RESEARCH.md` recommends prototyping Selkies-GStreamer first (fallbacks: Sunshine as host + Moonlight-Web web client, then Xpra shadow) — but its **§7 prototype gates never ran**: no CPU-only encode measurement, no :98 capture verification, no input-fidelity pass, no reachability test. Its standing quarterly upstream-health check (Selkies "needs maintainers" risk, §4) never ran either. The recommendation is unmeasured on spark-vm hardware. |
| Codec story | **Researched, not shipped.** `docs/CODEC_LICENSING_RESEARCH.md`: H.264 Baseline via `x264enc` for the CPU-only fleet; browser decode reality — H.264 is the only codec in every major browser **including all of iOS** (load-bearing for the mobile viewer). Counsel-level sign-off still owed (§8 of that doc). |
| TURN / hosted NAT reachability | **Solved in principle, unused.** The transport research's §5.2 reachability problem (provider ingress can't carry ICE/RTP media; operator-run TURN relay as new infrastructure with a bandwidth-cost line) **evaporates on the SFU path**: Cloudflare's TURN rides free with the SFU. This is the hosted lane's decisive advantage over the self-hosted WebRTC prototypes — no TURN relay to operate. |
| Self-hosted parity | **Intact so far — the SFU names the hosted distribution, not the protocol.** The both-supported default holds: the capture+encode pipeline (GStreamer) is transport-agnostic — the same pipeline can publish to the Cloudflare SFU (hosted) or a self-hosted SFU/peer (self-hosted lane keeps the transport research's ladder). The SFU choice must not hard-code Cloudflare into the box publisher's shape. |
| Terminal lane (#853) | **Analyzed, same session discipline.** The terminal-stream spec (new issue #919) is this lane's low-bandwidth cousin: G53.2's read/write split applies here too — streams are observation, **input is an action on its own channel class**, and approval is the consent plane (#849), never the transport. |

## 3. Gaps

- **`[BLOCKER]` G54.1 — no box-side publisher.**
  The acceptance starts "box publishes its desktop" and there is no
  publisher. The slice must answer: (a) capture — attach to the existing
  `:98` (xdamage-diff capture), never launch a competing X server (the
  selkies-launches-its-own-X-server failure mode, transport research §7.3);
  (b) encode — H.264 Baseline via `x264enc` per the codec research
  (CPU-only fleet; iOS decode reality); (c) publish — WebRTC publish of the
  encoded track to the SFU session (S2's session ids). Recommended shape:
  **GStreamer `webrtcbin`** — capture+encode is transport-agnostic, so the
  same pipeline serves the hosted SFU and the self-hosted lane (parity).
  The process lives in the #847 S5 `boxd` (shared backoff/reconnect) but
  may be prototyped standalone before `boxd` exists. License rule from the
  transport research: GPLv3 components are consumed as external
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
  #847. Filed as a new issue (see §6).
- **`[DESIGN]` G54.3 — input is an action, not pixels.**
  Owner input (click/type/key) flows dashboard → SFU DataChannel → box →
  cua-bridge's localhost-only `/api/click|type|key` (they already exist).
  The G53.2(a) split holds: viewing is observation, **input rides a
  dedicated DataChannel class** — never the media track, never the #849
  approvals decision wire. Owner-typed input into their own box is
  frictionless under owner auth; where an input action needs human
  authorization, the *decision* rides the approvals channel and the *bytes*
  ride the input channel — approval is the consent plane, not the
  transport. Session-scoped: one interactive controller per session with
  audited open/close (the D3/D6 lineage) — the agent's own synthetic input
  and the owner's share the display, and the protocol must say who wins.
  Filed as part of the viewer issue (see §6).
- **`[DESIGN]` G54.4 — the viewer is a build, not a skin.**
  The dashboard needs a real WebRTC subscribe path: video element,
  session-scoped owner auth, the #47 mobile gesture set (pinch zoom,
  tap=click, hold=left-click, cursor-drag, clipboard bridge) — all
  client-side, all testable against the S3 publisher through the SFU.
  Filed as a new issue (see §6).
- **`[BLOCKER]` G54.5 — trust model: media transits Cloudflare.**
  The SFU is a forwarding unit on Cloudflare's edge: tenant desktop pixels
  flow box → Cloudflare → owner browser (SRTP/DTLS in transit per WebRTC;
  nothing at rest on the plane). This is NOT the rejected
  `stream.moonlightweb.top` relay (a third-party hobby domain with an
  expiry date) — it is our own Cloudflare account — but it is still a
  third-party media hop and must be documented as one (POSITIONING
  honesty): what Cloudflare can observe, what the tenant is told, and that
  the self-hosted lane keeps media on the tailnet. The S2 slice writes
  this down; it is not a reason to avoid the SFU, it is a reason to name
  the trust boundary. Folds into the session-plane issue.
- **`[DESIGN]` G54.6 — desktop streaming is the heaviest cost surface.**
  $0.05/GB after the 1,000 GB/month free tier. At 720p30 H.264
  (~1–2 Mbps) a viewer burns ~0.45–0.9 GB/hour — the free tier is roughly
  1.1k–2.2k viewer-hours/month: fine for the beta cohort, unbounded for a
  real fleet. Per-box usage must be metered into the H12 metering lineage
  (#380) with a budget alert and a kill switch; over-budget sessions are
  refused at session-request time (the mint-race pattern from G53.6, applied
  to minutes instead of bytes). Folds into the session-plane issue's
  acceptance.
- **`[OBSERVABILITY]` G54.7 — feed the fleet journals.**
  Session open/close/auth-failure events into the fleet event journal (the
  G47.7 pattern) so the P7 status page renders desktop health honestly —
  distinct from heartbeat freshness (box↔plane liveness) and the relay's
  `connection-unreachable` (tenant↔box liveness). Three liveness sources,
  three signals, never confused in status surfaces. Folds into the
  session-plane issue.
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
  (acceptance) + G54.7. Session endpoints, D1 `desktop_sessions`,
  SFU session creation with the env-held secret, publish/subscribe
  authorization, expiry + revocation, trust-model doc, metering into the
  H12 lineage, journal feeding. Signaling-carrier decision (HTTPS now vs
  #847 WSS later) in the slice.
- **S3 — box-side SFU publisher** (new issue #936): G54.1 + the box-side
  half of G54.8. GStreamer `webrtcbin` capture of `:98`, H.264 Baseline
  `x264enc` encode, WebRTC publish to the SFU session; standalone-prototype
  allowed, `boxd` home when #847 S5 lands; transport-agnostic shape for
  parity; no GPL in the repo tree.
- **S4 — dashboard viewer + gestures** (new issue #937): G54.3 + G54.4.
  WebRTC subscribe in the dashboard, the #47 mobile gesture set, input →
  DataChannel → cua-bridge endpoints, audited input sessions.
- **S5 — acceptance verification** (stays on #854): end-to-end
  publish → SFU → dashboard with a **measured** glass-to-glass latency
  against the "suitable for interactive use" bar (a number, not an
  adjective); no inbound ports (outbound-only publish, like heartbeat);
  revoke-during-session kills the SFU session; box A cannot view or
  publish box B's session (namespace isolation on server-derived session
  ids, filename-style normalization N/A here — the ids are ours);
  owner input works end to end; a month of free-tier burn measured and
  metered; the media-transits-Cloudflare trust note published.

## 5. Shape sketch (reserved, not final)

The owner requests a session: `POST /v1/desktop/sessions {box_id}` (owner
auth, #845 shape). The plane creates the SFU session via
`https://rtc.live.cloudflare.com/v1` with the app secret from env, writes
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
  env-held app secret, publish/subscribe authorization, trust-model doc,
  metering into H12, journal feeding. Blocked on S1 (Realtime app
  provisioning — NEEDS_USER.md).
- **New issue #936: box-side SFU publisher** (G54.1, S3) — `:98` capture,
  H.264 Baseline `x264enc`, GStreamer `webrtcbin` publish to the SFU
  session; transport-agnostic for parity; box-side half of the transport
  research's §7 gates as measured acceptance.
- **New issue #937: dashboard desktop viewer + mobile gestures** (G54.3/G54.4,
  S4) — WebRTC subscribe in the dashboard, the #47 gesture set, input on
  the dedicated DataChannel class → cua-bridge endpoints, audited input
  sessions.
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
