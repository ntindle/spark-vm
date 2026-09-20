# Remote desktop transport research

**For issue #47 (Live machine control).** Product research: which technology can
deliver the live desktop/terminal surface the ticket needs, given the user's
#1 requirement — it must feel real-time. WebRTC-class low-latency streaming;
never a slow screenshot-polling frame sync. Degrade resolution/framerate on bad
networks, never settle into slow-sync mode.

This doc is research, not a commitment. Nothing here is built. All latency and
feature claims are sourced; where a claim is unverified against spark-vm's own
stack it is labeled as such. The prototype gates in §7 are the go/no-go before
any implementation work starts.

## 1. Requirements

From #47 plus the standing UX spec:

1. **Latency is the feature.** Real-time feel for both the human (mobile browser)
   and any embedded agent use. Frame-sync polling (e.g. periodic screenshots
   over HTTP) is explicitly out.
2. **Browser-native client.** No native client install — the control surface is
   a web UI. Mobile gestures (pinch zoom, tap = click, hold = left click,
   cursor-drag mode) must be expressible in the client.
3. **Self-hostable / open-source parity.** Per the parity rule, whatever the
   hosted product streams should also run on a self-hosted box. Proprietary
   SaaS relays and closed protocols are out unless nothing OSS works.
4. **X11 fit.** The box already runs the CUA stack on Xvfb `:98` + XFCE. The
   capture path should attach to that display without rebuilding the stack.
5. **Per-tenant isolation.** H11 (multi-tenancy audit) precedes shared control
   paths. The transport must be deployable per-tenant (per-box localhost-only
   process), with tenant-scoped auth and audited session start/stop.
6. **Provider-agnostic.** Must work on the hosted control plane (boat.dev
   target, Fly.io fallback) and on a bare self-hosted box.
7. **Terminal too.** #47 wants both terminal and desktop from the web UI.

Out of scope: the machine *control* API (start/stop/snapshot — provider
interface), which is #47's other half and already scoped in the ticket.

## 2. Candidates

| Candidate | Transport | Client | License | Status |
|---|---|---|---|---|
| Selkies-GStreamer | WebRTC | Browser (HTML5) | Open source | Upstream alive; "in need of maintainers" |
| Moonlight-Web + Sunshine (or its own engine) | WebRTC | Browser | GPLv3 (web); Sunshine GPLv3 | Active (release days ago) |
| Sunshine alone + Moonlight native clients | GameStream (RTSP/RTP) | Native clients | GPLv3 | Mature |
| RustDesk | Custom (TCP/UDP) | Native; 3rd-party browser clients only | License needs verification (see §2.3) | Active, but no first-party web client |
| KasmVNC | VNC over WebSocket | Browser | Open source | Active |
| Xpra | Xpra protocol over TCP/WebSocket (adaptive batch encoding) | Browser (HTML5) + native | Open source (GPLv2+) | Active; rejected §2.8 |
| MeshCentral | VNC-class desktop + terminal over web | Browser | Apache-2.0 | Active; rejected for latency bar |
| Apache Guacamole | Guacamole protocol over HTTP | Browser (clientless) | Apache 2.0 | Mature, Java stack |
| noVNC | VNC over WebSocket | Browser | Open source | Baseline — slow over the internet |
| ttyd / xterm.js | WebSocket | Browser | Open source | Terminal only |

### 2.1 Selkies-GStreamer

Open-source, low-latency, GPU/CPU-accelerated WebRTC HTML5 remote desktop for
Linux X11 — "Moonlight, Google Stadia, or GeForce NOW in noVNC form factor,"
targeting ≥60 FPS at Full HD. Started by Google engineers, expanded by
academic researchers. Streams the X11 desktop to any modern browser; two-way
clipboard; keyboard/mouse/gamepad input. Explicitly positioned as the
high-performance replacement for noVNC and Apache Guacamole.

- Design doc: https://github.com/yarikoptic/selkies-gstreamer/blob/HEAD/docs/design.md
- Upstream project page: https://github.com/pmohanj/selkies
  (fork mirror; notes that newer Selkies streams over plain WebSockets by
  default with WebRTC as opt-in — verify against the GStreamer variant before
  building, since the WebRTC path is the one we need)

Fit notes:

- **Transport:** WebRTC native — purpose-built for the WebRTC-class bar. ✓
- **Client:** pure browser. ✓
- **X11 fit:** X11 capture; designed for exactly our display model. ✓
- **License:** open source. ✓
- **Risk 1 — maintenance health:** the project page itself says "We are in need
  of maintainers and community contributors." A WebRTC stack that loses its
  maintainers rots fast (browser codec/API churn). This is the single biggest
  risk and the first prototype gate.
- **Risk 2 — CPU encode on small VMs:** the 60 FPS/FHD claim assumes GPU
  encoding; the software-encode fallback is quoted at "at least 30 FPS at
  720p" in the design doc. A hosted trial box (2–4 vCPU, no GPU) has to be
  measured, not assumed. Fly GPU deprecation (competitor pass, C6) means the
  hosted fleet is CPU-only for the foreseeable future.
- **Risk 3 — transport drift:** confirm the GStreamer variant still defaults
  to WebRTC (the mirror's WebSocket-default note is about the non-GStreamer
  build).

### 2.2 Moonlight-Web + Sunshine

Moonlight-Web (https://github.com/linckosz/moonlight-web) is a C++/Qt server
that streams over WebRTC (DataChannels + RTP) to a browser client — nothing to
install on the client side. Codecs H.264/HEVC/AV1, hardware encode on
NVENC/AMF/Quick Sync/VA-API/VideoToolbox with software fallback. The project
claims under-20 ms glass-to-glass over LAN Wi-Fi and ~25 ms over the internet
— project claims (https://github.com/linckosz/moonlight-web), not our
measurements. Codec licensing diligence still owed: H.264 sits in a patent
pool, HEVC's pools are fragmented, AV1 is royalty-free, x264 is GPL — the
hosted product needs a counsel-level answer before committing to a codec. It either
brings **its own capture & encode engine** (host is streaming-ready with no
Sunshine, no pairing) or pairs with Sunshine/Apollo/Wolf hosts over the
GameStream protocol. Input: keyboard, mouse (pointer-lock), touch trackpad,
gamepads. Releases: https://github.com/linckosz/moonlight-web/releases

Sunshine (upstream LizardByte/Sunshine, GPLv3 per fork descriptions, e.g.
https://github.com/juvepr/switchdesk-engine) is the mature self-hosted host:
hardware encoding on AMD/Intel/NVIDIA, software fallback, web UI for
configuration and pairing only. A May 2026 release added Vulkan encoding,
PipeWire/KWin direct screencast capture, and FFmpeg 8.1
(https://www.gamingonlinux.com/2026/05/sunshine-game-streaming-tool-adds-vulkan-encoding-plus-xdg-pipewire-and-kwin-direct-screencast-capture/).

Fit notes:

- **Transport:** WebRTC to the browser — meets the bar. ✓
- **Client:** browser-native; the project's entire premise is zero-install
  clients. ✓
- **X11 fit:** Sunshine captures Linux desktops (X11 path established); the
  Moonlight-Web own-engine path also claims Linux hosts. The own-engine path is
  the risky one for our stack: the upstream README states the native engine
  "captures a GPU surface and hands it straight to the GPU encoder" and that
  "if it cannot run at all (headless machine, no usable encoder, Windows
  ARM64), the card simply does not appear" — a headless Xvfb box is exactly the
  case where the native engine offers nothing (verified against
  https://github.com/linckosz/moonlight-web, 2026-09-18). Needs verification
  against Xvfb specifically; see the reordered fallback in §4.
- **License:** GPLv3 throughout. Two hard constraints for this repo (MIT-licensed):
  (1) the improvement loop must NEVER vendor GPLv3 code into the repo tree —
  consume the streamer strictly as an external dependency (container image /
  OS package), keeping our own code MIT; (2) serving Moonlight-Web's GPLv3 web
  client JavaScript to tenants *is* distribution, so any gesture-set or other
  client modification triggers the GPLv3 source-offer obligation — satisfiable
  for an OSS project, but it must be honored, not assumed away.
- **Risk 1 — the one-click internet relay:** the project offers opt-in public
  URLs at `stream.moonlightweb.top` with automatic DNS/TLS, and notes that
  existing subdomains are kept "until February 2027." A hosted product must
  NOT route tenant desktops through a third-party hobby domain with an expiry
  date — privacy, reliability, and our own TLS story all forbid it. LAN-only
  (or our own relay) is the only acceptable mode.
- **Risk 2 — gaming-shaped input model:** pointer-lock mouse and gamepad
  support are first-class; the agent-control use case (synthetic clicks from
  the CUA driver, hold-to-click, cursor-drag mode) must be verified through
  the web client, not assumed from the gaming path.
- **Risk 3 — operational weight:** a C++/Qt server with FFmpeg 8.1 is a
  heavier build/packaging story than a Python service, and the hosted fleet
  inherits that maintenance.

### 2.3 RustDesk — rejected for this surface

RustDesk is the strongest OSS answer for native-client remote control
(self-hostable hbbs/hbbr relay, E2E encrypted, H.265; anecdotal reports
suggest sub-50 ms on LAN — unverified). But it fails the browser-native
requirement: there is no
first-party web client — the web console is a **Pro (paid)** feature
(http://www.makeuseof.com/rustdesk-teamviewer-alternative-self-hosted-remote-desktop/),
and third-party browser clients are immature (one working deployment reports
3–16 FPS H264 with open keyboard-forwarding bugs:
https://github.com/linkzy/rustdesk-custom-web-client/blob/HEAD/docs/AI_GUIDELINES.md).
Latency-sensitive reviewers also note it "isn't built for latency-sensitive
use cases like gaming" compared with Sunshine/Parsec-class stacks
(https://www.makeuseof.com/rustdesk-free-features-replace-teamviewer/).

License caution: sources disagree (one says GPLv3, another AGPL-3.0 for server
+ client — https://github.com/tortuvshin/open-apps/blob/HEAD/content/records/rustdesk.md).
For a hosted product, AGPL network-copyleft would be the load-bearing question
— verify against upstream before any reconsideration. Not our transport; keep
it in the back pocket as a native-client alternative for power users.

### 2.4 KasmVNC — rejected for this surface

KasmVNC is the modern OSS VNC server: web-native client, webp encoding,
vendor-claimed 30% better compression than classic VNC (kasm.com product page
— vendor claim, unverified). A recent independent research note chose KasmVNC
over TigerVNC+noVNC (single component, seamless clipboard) while rejecting
Guacamole as duplicated gateway weight
(https://github.com/whereiskurt/klanker-maker/blob/HEAD/.planning/phases/93-km-desktop-kasmvnc-backed-browser-xfce-remote-session-over-ssm-port-forward/93-RESEARCH.md).

It is still VNC: better encoding does not make it WebRTC-class. Acceptable as
a fallback/admin path, not the primary live surface.

### 2.5 Apache Guacamole — rejected for the live surface

Apache 2.0, clientless HTML5, RDP/VNC/SSH through a Java gateway. Its custom
protocol genuinely beats raw VNC over high-latency links
(https://news.ycombinator.com/item?id=8166388), and it is the right shape for a
*bastion* (SSH/RDP to many boxes through one gateway). It is not a low-latency
video transport — no WebRTC, no hardware encode — and it drags a Java/Tomcat
stack into the fleet. Useful later as the admin bastion behind the hosted
control plane; wrong for the "feels alive" desktop.

### 2.6 noVNC — baseline only

VNC protocol tunneled over WebSockets to the browser. "You'll get performance
no better than TCP VNC (bad performance over the internet)"
(https://news.ycombinator.com/item?id=8166388). This is exactly the slow
screenshot-sync class the UX spec forbids. Kept as the measured baseline in
any prototype bake-off, nothing more.

### 2.8 Xpra — in the bake-off, not the primary

Xpra (https://github.com/diyism/xpra) is the closest analog to Selkies for this
exact stack and was wrongly omitted from the first draft of this doc:
browser-native via an HTML5 client (xpra required only on the host), attaches
to Xvfb (it connects as a compositing window manager to an Xvfb display;
https://en.wikipedia.org/wiki/Xpra), `xpra shadow` attaches to an *existing*
desktop session — i.e. it can sit on `:98` without displacing the CUA stack's
display, and it is actively maintained (upstream changelog updated ~19 days
before this research; recent entries include "significant latency and
performance improvements": https://github.com/xpra-org/xpra/blob/HEAD/docs/CHANGELOG.md).

It is not the primary because it fails requirement 1: its documented transports
are TCP, SSL, SSH, HTTP/WebSockets, and RFB on a single port
(https://github.com/diyism/xpra) — adaptive batch encoding over TCP-class
transport, not WebRTC media with ICE/SRTP. Field notes report latency problems
on slower systems and low bandwidth
(https://github.com/velvet-os/velvet-os.github.io/blob/HEAD/using-xpra-as-remote-desktop.md).
It belongs in the prototype bake-off as fallback #2 (ahead of KasmVNC/noVNC):
if both WebRTC candidates fail on a CPU-only Xvfb box, Xpra's shadow mode is
the best non-WebRTC answer, and its HTML5 client already works through the SSH
tunnels we use today.

### 2.9 Terminal: ttyd + xterm.js

The terminal half of #47 needs no research gamble: ttyd (or equivalent
pty-to-WebSocket bridge) + xterm.js in the browser is the standard,
boring, correct answer. It can ship independently of the desktop transport
decision. Two caveats for the implementation run: ttyd's built-in auth is
basic-auth, not tenant-scoped — it must sit behind the H9 identity / proxy
auth layer, not be exposed directly; and ttyd has no native audit log, so the
session audit story from §5 must be built around it rather than assumed from it.

## 3. Scoring against the requirements

| Requirement (§1) | Selkies-GStreamer | Moonlight-Web | RustDesk | KasmVNC | Xpra | Guacamole | MeshCentral | noVNC |
|---|---|---|---|---|---|---|---|---|
| 1. WebRTC-class latency | ✓ native | ✓ native | ~ (native app only) | ✗ VNC-class | ✗ TCP/batch | ✗ | ✗ VNC-class | ✗ |
| 2. Browser-native client | ✓ | ✓ | ✗ (3rd-party, immature) | ✓ | ✓ (HTML5) | ✓ | ✓ | ✓ |
| 3. OSS / parity | ✓ | ✓ (GPLv3, constraints in §2.2) | license TBD | ✓ | ✓ | ✓ (Apache 2.0) | ✓ (Apache 2.0) | ✓ |
| 4. X11 (`:98`) fit | ✓ by design | verify on Xvfb | ✓ | ✓ | ✓ (shadow mode) | ✓ | ✓ | ✓ |
| 5. Per-tenant deploy | ✓ (per-box process) | ✓ (per-box process) | ✓ | ✓ | ✓ | ~ (shared gateway) | ~ (mesh mgmt) | ✓ |
| 6. Provider-agnostic | ✓ | ✓ (LAN-only mode) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Maintenance health | ⚠ needs maintainers | ✓ active | ✓ active | ✓ active | ✓ active | ✓ mature | ✓ active | ✓ mature |

## 4. Recommendation

**Prototype Selkies-GStreamer first** as the desktop transport for #47, with
a reordered fallback ladder: **Sunshine as host (X11 capture, software encode)
+ Moonlight-Web as the web client** if Selkies fails gate 2; **Xpra in shadow
mode** if both WebRTC candidates fail on a CPU-only Xvfb box. Ship the
ttyd/xterm.js terminal independently — it does not wait for the desktop
decision.

Why Selkies first: it is the only candidate that is simultaneously
browser-native, WebRTC, X11-native, and open source. (Xpra matches on
browser-native + X11 + OSS but is TCP/WebSocket transport, not WebRTC-class —
see §2.8.)

On the maintenance risk, honestly: it is **structural, not bounded**. The
prototype gates measure technology (encode, latency, capture, input); a
"needs maintainers" project can pass all of them and still rot from browser
codec/API churn — exactly the failure mode named in §2.1. So the maintenance
answer is a policy, not a prototype: pin the dependency, consume it as an
external container image (never vendored into this repo — see the GPL
constraints in §2.2), run a quarterly upstream-health check as a standing
loop item, and define the re-platform trigger now: if upstream goes >3 months
without a commit or leaves browser-compat issues unaddressed for >3 months,
the recommendation flips to the Sunshine + Moonlight-Web fallback without
re-litigating this doc. Gate 1 (below) is the first instance of that check.

### Why not Moonlight-Web's native engine first

The native engine is the stronger *project* (active releases days ago, richer
client), but the weaker fit for our degenerate case: the upstream README
itself says that on a headless machine with no usable encoder "the card
simply does not appear." So the fail-branch of gate 2 points at **Sunshine as
the host** — X11/XShm capture and a mature headless + software-encode story —
with Moonlight-Web serving only as the browser client (its GameStream-client
mode), LAN-only, no relay. The Moonlight-Web native engine gets measured only
if the prototype box has a usable hardware encoder. Beyond that: gaming-shaped
input assumptions, a heavier C++/Qt packaging story for the fleet, and the
one-click relay is a trap we must actively avoid.

### Explicitly not promised

- No latency numbers in this doc are measured on spark-vm hardware. The 60
  FPS/FHD and 30 FPS/720p figures are project claims, not our measurements.
- No hosted pricing or tier claims follow from this (POSITIONING.md
  anti-claims still apply).
- The one-click `stream.moonlightweb.top` relay is rejected for the hosted
  product — tenant desktops never traverse a third-party domain.

## 5. Integration sketch (for the prototype run)

1. Per-box `selkies-gstreamer` process, bound to **localhost only** on the
   tenant box, capturing Xvfb `:98`. No public ingress — consistent with the
   H3 provisioning interface's `public_ingress: false` clause.
2. Human reachability — signaling and media are two different paths, and the
   doc's first draft wrongly treated WebRTC media like a plain TCP service:
   - **Signaling** (SDP/HTTP) can ride anything: the SSH tunnel, the tailnet,
     provider ingress. This part works like the CUA bridge pattern.
   - **Media** needs ICE connectivity between browser and streamer, and
     `ssh -L` forwards TCP only. Establishing media over an SSH tunnel
     requires ICE-TCP candidates or a TURN server reachable through the
     tunnel — possible, but it is an explicit design, not "the same pattern
     as the CUA bridge on 127.0.0.1:18731."
   - **Bind address:** "localhost-only" contradicts tailnet reachability. A
     socket bound to localhost is not reachable from another tailnet node.
     The streamer must bind the tailnet interface (behind tailnet ACLs) or a
     tailnet-side forwarder must exist — this is an open design decision, not
     a default.
   - **Hosted:** provider ingress (L7 HTTP / TCP LB) cannot carry ICE/RTP
     media. A hosted fleet behind provider NAT needs STUN for discovery and,
     in the common symmetric-NAT case, a **TURN relay through which 100% of
     media flows**. That relay is real infrastructure: an operator-run
     component, a bandwidth-cost line (likely the dominant infra cost for
     this surface), and audit scope. Media relayed through TURN is
     SRTP-encrypted — the relay sees ciphertext, not pixels — but it is
     still a trust and cost decision the control-plane design must own. The
     third-party `stream.moonlightweb.top` relay is rejected for exactly
     this reason (§2.2); the hosted product operates its own or does not
     ship this surface.
   No new public listener is invented here for the *streamer*, but the TURN
   requirement for hosted is new infrastructure and must be costed and
   designed before the prototype claims "works on hosted."
3. Auth: tenant-scoped, delegated to the hosted identity service (H9) when it
   exists. The identity-to-stream binding does not exist yet — confirmd
   approves discrete credential-swap requests, not long-lived sessions, so
   there is no confirmd session to reuse as a stopgap. Naming that binding
   (session-scoped bearer, expiry, revocation on tenant-offboard) is H9/H11
   work. Every stream session start/stop writes an audit line (same
   discipline as the swap proxy's audit log).
4. Adaptive quality: degrade resolution/framerate under congestion per the UX
   spec — verify the candidate exposes this (WebRTC congestion control should,
   but the knob must be confirmed, not assumed).
5. Mobile: the browser client must support the gesture set (pinch zoom,
   tap=click, hold=left-click, cursor-drag) — client-side work on top of the
   stream, testable against the prototype.

## 6. What this changes in the backlog

- **#47** gains a transport answer: prototype Selkies-GStreamer → fallback
  **Sunshine as host + Moonlight-Web web client** → Xpra shadow mode as the
  non-WebRTC last resort; terminal via ttyd/xterm.js ships independently.
  (Comment to be posted on the issue when the PR merges.)
- New follow-up for a build-loop `feature` run: the §7 prototype itself
  (bake-off harness + measured numbers + a go/no-go), including the ICE/TURN
  reachability design and the codec-licensing diligence line.
- Guacamole stays a candidate for the later admin-bastion story; MeshCentral
  rejected for this surface (VNC-class desktop fails the latency bar) but
  noted for the same bastion conversation later.
- License rule recorded: GPLv3 streamers are consumed as external dependencies
  only — never vendored into the repo tree; client-code modifications honor
  the GPLv3 source-offer obligation.

## 7. Prototype gates (go/no-go before implementation)

1. **Maintenance health:** verify against the canonical upstream (not a fork
   mirror): recent commits, responsive issue tracker. Fail threshold: no
   commits or releases in the last 3 months, or browser-compat issues
   unaddressed for 3+ months → the gate FAILS and the recommendation flips to
   the Sunshine + Moonlight-Web fallback without re-litigating this doc.
   Standing mitigation regardless of outcome: pinned external dependency,
   quarterly upstream-health re-check as a loop item, re-platform trigger as
   defined in §4.
2. **CPU-only encode:** measure end-to-end glass-to-glass latency and FPS on a
   2–4 vCPU box with no GPU, software encode, 1080p and 720p. Pass = feels
   real-time to a human tester against the noVNC baseline, with a <150 ms
   glass-to-glass target alongside the subjective bar; fail = fall back to
   Sunshine as host + Moonlight-Web web client and re-measure (the native
   engine is measured only if the box has a usable hardware encoder).
3. **Xvfb capture:** verify clean capture of the existing `:98` display (no
   GPU/GLX assumptions in the capture path). Explicitly cover the
   selkies-launches-its-own-X-server failure mode: the streamer must attach
   to `:98`, not insist on owning the X server (which would orphan the CUA
   stack's display and violate §1.4).
4. **Input fidelity:** tap=click, hold=left-click, pinch zoom, cursor-drag —
   through the web client, plus the existing CUA driver's synthetic input
   continuing to work on the same display.
5. **Tenancy hooks:** per-box process, tenant-scoped auth integration point,
   auditable session lifecycle. Feeds H11.
6. **Congestion behavior:** confirm resolution/framerate degrades before
   latency does.
7. **Reachability:** establish a real media session over EACH intended path —
   SSH-forwarded, tailnet, and hosted-NAT-equivalent (through the TURN
   relay). A LAN-only latency number does not pass this gate; ICE must
   complete on every path the product will actually use.

## 8. Sources

All links verified live during this research pass (2026-09-18):

- Selkies-GStreamer design doc —
  https://github.com/yarikoptic/selkies-gstreamer/blob/HEAD/docs/design.md
- Selkies project page (maintainers note, transport note) —
  https://github.com/pmohanj/selkies
- Moonlight-Web — https://github.com/linckosz/moonlight-web
- Moonlight-Web releases — https://github.com/linckosz/moonlight-web/releases
- Sunshine fork description (GPLv3, capture + NVENC + Moonlight protocol) —
  https://github.com/juvepr/switchdesk-engine
- Sunshine 2026 release (Vulkan encode, PipeWire/KWin capture, FFmpeg 8.1) —
  https://www.gamingonlinux.com/2026/05/sunshine-game-streaming-tool-adds-vulkan-encoding-plus-xdg-pipewire-and-kwin-direct-screencast-capture/
- RustDesk free-vs-Pro (web console is Pro) —
  http://www.makeuseof.com/rustdesk-teamviewer-alternative-self-hosted-remote-desktop/
- RustDesk latency-sensitive caveat —
  https://www.makeuseof.com/rustdesk-free-features-replace-teamviewer/
- Third-party RustDesk web client (immature: 3–16 FPS, keyboard bugs) —
  https://github.com/linkzy/rustdesk-custom-web-client/blob/HEAD/docs/AI_GUIDELINES.md
- License table (RustDesk AGPL-3.0 claim; Guacamole Apache-2.0) —
  https://github.com/tortuvshin/open-apps/blob/HEAD/content/records/rustdesk.md
- Xpra project page (shadow mode, HTML5 client, connection types) —
  https://github.com/diyism/xpra
- Xpra operation (Xvfb compositing WM, HTML5 client) —
  https://en.wikipedia.org/wiki/Xpra
- Xpra upstream changelog (maintenance activity, latency improvements) —
  https://github.com/xpra-org/xpra/blob/HEAD/docs/CHANGELOG.md
- Xpra field note (latency caveat on slow systems) —
  https://github.com/velvet-os/velvet-os.github.io/blob/HEAD/using-xpra-as-remote-desktop.md
- Independent KasmVNC-vs-alternatives research note —
  https://github.com/whereiskurt/klanker-maker/blob/HEAD/.planning/phases/93-km-desktop-kasmvnc-backed-browser-xfce-remote-session-over-ssm-port-forward/93-RESEARCH.md
- Guacamole vs noVNC performance discussion —
  https://news.ycombinator.com/item?id=8166388
