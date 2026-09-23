# Competitor deep-scan: live machine control axis (2026-09-20)

**Survey window:** 2026-09-20 ~14:54 → ~15:04 CDT. **Scope:** live interactive
machine control across the tracked set — real-time remote desktop / screen
view, live terminal, file browsing, suspend/wake — against spark-vm's hosted
control-plane design (ticket #47). Delta conventions: VERIFIED = read on a
vendor's own page/doc/repo this run (link inline); THIRD-PARTY = press or
third-party reporting; INFERRED = my characterization, labeled as such.

**Why this axis:** #47's design commits to real-time (WebRTC-class) streaming
with degrade-resolution/framerate fallback, and explicitly rules out
slow-screenshot-polling frame sync. Nobody on the field-at-a-glance table
advertises low-latency, human-first machine control as a product surface —
this scan tests whether that is a real gap or whether competitors cover it
incidentally.

## spark-vm's #47 control-plane baseline (what we intend to be compared against)

- Real-time web UI: start / stop / pause / resume / restart / snapshot /
  terminal / desktop on hosted VMs.
- Mobile remote-control UX (user's spec): top session bar + checkmark to end;
  floating toolbar (keyboard, touch/cursor toggle, copy, paste); in touch mode,
  tap = click, hold = left click; cursor mode = draggable pointer; pinch to
  zoom; keyboard button summons the native keyboard; red disconnect/stop
  button; local↔remote clipboard bridge.
- Transport requirement (user's #1): WebRTC-class low-latency streaming, never
  slow screenshot-polling frame sync; degrade resolution/framerate on bad
  networks but never settle into slow-sync mode.
- Transport stack (from REMOTE_DESKTOP_TRANSPORT_RESEARCH.md): prototype
  Selkies-GStreamer first; fallback ladder Sunshine host + Moonlight-Web web
  client, then Xpra shadow mode; terminal ships independently via ttyd/xterm.js.
- Trust context: per-action human approvals (confirmd), credential proxy
  (swapd), tailnet-first networking.

## Scorecard — live machine control

| Provider | Live desktop/screen | Live terminal | Suspend/wake | Transport |
|---|---|---|---|---|
| AgentComputer | Browser/VNC via `computer open --vnc` | CLI + ConnectRPC streaming exec | Start/stop endpoints; file ops on stopped VMs, no runtime charge | VNC + ConnectRPC |
| TermSquad | None found (no vendor evidence) | Browser Web Terminal + SSH | Stop is a power action; no stopped-state discount published | Not published |
| Fly.io Sprites | None found | `sprite console` (full TTY), `sprite exec --tty`, detachable sessions | Auto-pause ~30s idle; warm 100–500ms, cold 1–2s; FS persists | Not named by vendor |
| E2B | Browser desktop, 1 stream at a time | Terminal via SDK/desktop | Pause (FS+memory, resume ≈1s, pause ≈4s/GiB); FS-only cold-boot option | Desktop streaming (SDK) |
| Daytona | Browser VNC desktop (Xvfb+XFCE+x11vnc+noVNC) | Web Terminal (org members only, STARTED only) | Pause/resume (VM classes only — FS+memory preserved; auto-pause) + stop/archive/delete; auto-stop/auto-archive/auto-delete; FS persists on runner until archived | VNC (noVNC) |
| Docker Sandboxes | None (local microVM, no browser surface) | CLI shell, SSH/SFTP, terminal dashboard | stop = pause; auto-stop when idle; state persists across stop/restart | Local (no remote transport) |

**Stream concurrency / ownership (scorecard gap):** E2B documents a
one-stream-at-a-time limit for desktop streaming (VERIFIED — "There can be
only one stream at a time", "Creating multiple streams at the same time is
not supported"; the SDK also exposes view-only URLs on the single stream via
`get_url(view_only=True)`). No vendor evidence found for a published
concurrency policy beyond E2B in this pass. The architecturally relevant axis
for confirmd's approval model is three-fold: (1) the stream-count limit, (2)
concurrent view-only viewers, and (3) interactive-control holding and
handoff — and confirmd today approves discrete requests, not long-lived
sessions (REMOTE_DESKTOP_TRANSPORT_RESEARCH.md §5, 'Auth' (item 3)). #47 should define its
stream-ownership semantics explicitly — including the session-scoped
bearer/expiry/revocation binding (H9/H11 work) — rather than inheriting E2B's
documented limit.

## Per-provider detail

**Scope note:** this pass did not survey snapshot semantics (what gets
snapshotted, restore granularity, snapshot cost) — the scorecard covers
desktop/screen, terminal, suspend/wake, and transport only. File browsing
and restart are likewise unscored here (evidence exists for some providers
but the columns are omitted — flag as a gap for the C16 audit to close).
Snapshot needs its own survey pass (flagged under C16 below).

### AgentComputer

- **VERIFIED** — Browser is the primary surface; CLI opens graphical access via
  `computer open my-computer --vnc`; SSH is also supported
  ([docs](https://www.agentcomputer.ai/docs)).
- **VERIFIED** — Live process access runs over **ConnectRPC**, with streamed
  output, attach, PTY resize, continuous input, and signals
  ([API docs](https://www.agentcomputer.ai/docs/api)).
- **VERIFIED** — Explicit start/stop endpoints exist; file operations work on
  stopped computers without starting the VM and without accruing runtime
  ([docs](https://www.agentcomputer.ai/docs)); hot storage $0.000683/GB-hour
  (running), cold storage $0.000027/GB-hour (stopped)
  ([pricing](https://www.agentcomputer.ai/pricing)).
- **No vendor evidence found** for wake-latency figures or per-action approval
  gates; browser surface is VNC/terminal-class, not low-latency video
  (INFERRED).

### TermSquad

- **VERIFIED** — Browser **Web Terminal** plus compatible SSH tools; persistent
  Linux environment; sessions continue after browser/laptop disconnect
  ([always-on computer page](https://termsquad.com/features/always-on-cloud-computer)).
- **No vendor evidence found** for graphical remote desktop, VNC, WebRTC, or
  the Web Terminal's underlying transport.
- **VERIFIED** — Monthly plans $9/$19/$29/$49, advertised online 24/7
  ([pricing](https://termsquad.com/pricing)). Stop reads as a machine power
  action, not immediate subscription cancellation (INFERRED — no vendor page
  names it as such); no stopped-state discount, no wake-latency figure, and
  no detailed storage semantics published — **no vendor evidence found** on
  all three.
- **VERIFIED** — AI subscriptions/usage are not included (explicit on pricing
  page).

### Fly.io Sprites

- **VERIFIED** — `sprite console` is a full interactive TTY; `sprite exec
  --tty` and detachable/reattachable sessions are supported
  ([working-with-sprites docs](https://github.com/superfly/sprites-docs/blob/main/working-with-sprites.mdx)).
- **No vendor evidence found** for browser GUI desktop, VNC, WebRTC, or
  browser terminal; third-party sources say exec/console run over WebSockets
  (**THIRD-PARTY** — community design doc) but primary vendor docs read today
  do not name the transport.
- **VERIFIED** — Auto-pauses after ~30s idle; warm wake 100–500 ms with
  processes/memory retained; cold wake 1–2 s with processes/memory dropped;
  filesystem persists through both
  ([lifecycle docs](https://github.com/superfly/sprites-docs/blob/main/concepts/lifecycle.mdx)).
  Per-second compute billing stops while hibernated; two-tier storage (hot
  NVMe billed only while running, object storage 24/7); PAYG allows 3
  concurrent Sprites; subscription "Level 10" $20/mo
  ([billing docs (archived draft)](https://github.com/superfly/sprites-docs/blob/a02bc9704033a37e49e89da7c416c9ef711265f5/src/content/docs/reference/billing.mdx)
  — vendor-authored but flagged `draft: true` in the repo; the vendor removed
  the page in its Mintlify docs restructure, so the link is pinned to the last
  commit containing it).
- **VERIFIED** — User cannot choose or observe the warm→cold transition; open
  TCP connections do not survive either pause; fixed 100 GB ceiling; `/tmp`
  is not to be treated as persistent.

### E2B

- **VERIFIED** — Browser desktop streams the screen with interactive or
  view-only URLs and optional generated-key authentication
  ([desktop repo](https://github.com/e2b-dev/desktop)).
- **VERIFIED** — SDK limitation: only one stream at a time
  ([desktop repo](https://github.com/e2b-dev/desktop)).
- **VERIFIED** — Pause preserves filesystem + memory/processes by default;
  optional filesystem-only pause cold-boots on resume; resume ≈ 1 s; pause
  ≈ 4 s/GiB RAM; paused sandboxes persist indefinitely until explicitly
  killed ([persistence docs](https://e2b.dev/docs/sandbox/persistence)).
- **VERIFIED** — Billing is per second of a **running** sandbox
  ([pricing](https://e2b.dev/pricing)); no separate paused-storage price was
  located on the vendor pages read. Default timeout action is kill unless the
  lifecycle is configured to pause.
- **VERIFIED** — No configurable auto-kill-after-N-days; paused service
  connections disconnect; pause may return 503 while a prior snapshot
  finishes; continuous runtime max 1 hour Hobby / 24 hours Pro.

### Daytona

- **VERIFIED** — Browser graphical desktop uses **VNC**, specifically an Xvfb
  + XFCE + x11vnc + noVNC stack, with real-time observation and mouse/keyboard
  control ([VNC docs](https://www.daytona.io/docs/en/vnc-access/)).
- **VERIFIED** — A separate browser Web Terminal (dashboard `>_` icon, port
  22222) supports commands plus file navigation/view/edit, works only in
  `STARTED` state, and is restricted to organization members
  ([web-terminal docs](https://www.daytona.io/docs/en/web-terminal/)).
- **VERIFIED** — Lifecycle supports stop, archive, delete, plus
  auto-stop/auto-archive/auto-delete; stopped container sandboxes keep their
  filesystem on the runner (occupying disk quota until archived); archiving
  moves a stopped sandbox's filesystem to object storage and frees disk quota;
  VM sandboxes offload filesystem state to nearby storage
  ([sandboxes lifecycle docs](https://www.daytona.io/docs/en/sandboxes/)).
- **VERIFIED** — VM-class sandboxes support **pause/resume**: pausing preserves
  filesystem + memory state, and non-ephemeral VM sandboxes default to a
  60-minute auto-pause interval when neither auto-pause nor auto-stop is set
  ([sandboxes docs](https://www.daytona.io/docs/en/sandboxes/)).
- **VERIFIED** — $0.0504/vCPU-hour, $0.0162/GiB-hour, storage
  $0.000108/GiB-hour after the first 5 GiB free, per-second billing, $200 free
  compute ([pricing](https://www.daytona.io/pricing)).
- **No vendor evidence found** for a wake-latency figure.
- **VERIFIED** — Custom images require VNC packages for the desktop; VNC
  resolution cannot change while running; terminal unavailable while stopped;
  ephemeral sandboxes are deleted when stopped.

### Docker Sandboxes

- **VERIFIED** — Local CLI workflow: attach to agent sessions, open an
  interactive shell, SSH/SFTP integration, and a terminal dashboard
  ([usage docs](https://docs.docker.com/ai/sandboxes/usage/)).
- **No vendor evidence found** for a browser terminal, browser file browser,
  VNC, WebRTC, or remote cloud desktop.
- **VERIFIED** — `stop` pauses; local sandboxes stop automatically when no
  session keeps them running; `run --name` starts and reattaches
  ([usage](https://docs.docker.com/ai/sandboxes/usage/) +
  [FAQ](https://docs.docker.com/ai/sandboxes/faq/)). Installed packages,
  images, configuration, history, and mountless workspace persist across
  stop/restart; removal deletes sandbox-internal state; host-mounted workspace
  naturally remains.
- **VERIFIED** — The CLI and sandbox execution are free, including commercial
  use; the paid component is organization governance
  ([FAQ](https://docs.docker.com/ai/sandboxes/faq/)). Runs on the user's
  machine (local microVMs), so no cloud billing surface exists.
- **VERIFIED** — Browser/local tools cannot reach sandbox services by default
  without port publishing; direct→clone mode cannot be switched without
  recreation; clone mode is rejected from non-main Git worktrees; copying
  directly between sandboxes is unsupported.

### Side-check: launches / pricing / partner moves since ~08:50 CDT 2026-09-20

**No vendor-primary evidence found** of a launch, pricing change, or partner
move by any of the six providers in the ~6-hour window. Nearest-in-time
items, all outside the window: a **THIRD-PARTY** EINPresswire release dated
2026-09-15 for TermSquad's always-on cloud computer launch
([einpresswire](https://www.einpresswire.com/article/942479573/termsquad-launches-an-always-on-cloud-computer-for-ai-coding-agents));
Docker Sandboxes [release notes](https://docs.docker.com/ai/sandboxes/release-notes/) updated 2026-09-18 (two days before this survey's window).

## Where spark-vm wins

1. **Low-latency streaming vs VNC.** Daytona and AgentComputer name VNC as the
   transport for their browser/desktop surfaces; E2B streams the desktop via
   its own SDK streaming (transport not named by the vendor) — the closest
   existing reference, and not a VNC framebuffer, so treat it as the
   competitive bar rather than lumping it under VNC. #47's WebRTC-class
   streaming requirement — with degrade-resolution/framerate fallback — is a
   genuine latency differentiator (INFERRED — this compares unshipped design
   intent against shipped product, so the win is a bet, not a measured fact).
   Build-cost caveat (INFERRED — conditional on an open corpus question): by
   BYO-tailnet (bring-your-own-tailnet — the tenant's own devices joining a
   tailnet with their box), the cost picture for device-on-tailnet paths would
   change — media traversal would be handled by Tailscale (including DERP
   relaying — still relaying, delegated to Tailscale's infra, not
   operator-run TURN), shrinking operator-side bandwidth cost for those
   viewers. But per the corpus this path is undecided, not planned:
   REMOTE_DESKTOP_TRANSPORT_RESEARCH.md §5, 'Human reachability' (item 2)
   leaves the streamer binding an open design decision, and
   HOSTED_SIGNUP_ONBOARDING.md calls tailnet join an optimization, not a
   requirement, with the operator-run TURN relay as the primary path. So a
   phone browser without the Tailscale client reaches the streamer via the
   relay (operator pays the bandwidth); the client is needed only for the
   delegated low-operator-cost path. What #47's mobile UX spec leaves open is
   *which* path mobile targets and its cost/client-install trade-off — the
   decision is not yet made, not unacknowledged.
2. **Per-action human approvals.** No vendor in the surveyed six publishes a
   per-action human approval gate for live control (AgentComputer: none
   found; Daytona: org members get terminal access, not approvals; E2B:
   interactive or view-only URLs, no approval UX). "Unique in the set" is
   scoped to these six — Vercel's `eve` agent framework (a separate product
   from the Vercel Sandbox SKU) ships a genuine per-action human approval
   loop, so the uniqueness claim holds scoped to sandbox/computer offerings
   but breaks scoped to the vendor Vercel (corpus, 2026-09-18 pm watch) —
   so the approval-UX win is real but not landscape-unique.
3. **Governance baked into control (design-direction win).** Daytona has org
   membership; Docker has paid AI Governance; none tie credential proxying +
   approvals + streaming into the control plane the way spark-vm's
   swapd/confirmd architecture intends to — note this compares shipped
   components (swapd/confirmd) bundled with the unbuilt streaming design,
   so it is a direction win, not a current product win.
4. **Mobile-first control UX** (design-intent win — the #47 stack is spec'd,
   not shipped). TermSquad's own launch coverage advertises a
   "mobile-friendly web terminal" reachable by phone (THIRD-PARTY,
   2026-09-15 EINPresswire release cited in the side-check above) — the
   closest existing mobile surface, so the absolute claim "nobody publishes
   a mobile UX" would overstate. Scoped correctly, the win is the full #47
   stack nobody ships: floating toolbar, touch/cursor modes, clipboard
   bridge, and real-time streaming — not just terminal-on-a-phone.

## Where spark-vm lags / gaps to watch

1. **E2B and Daytona ship desktop control today** — it is a parity target, not
   a blank slate. #47's scope (start/stop/pause/resume/restart/snapshot/
   terminal/desktop) matches E2B's paused-session model and Daytona's VM
   pause/resume + stop/archive/delete model on the surveyed lifecycle axes;
   snapshot parity needs its own survey (see scope note). Match their
   lifecycle completeness.
2. **Published resume targets.** Fly.io Sprites publishes 100–500 ms warm
   wake / 1–2 s cold wake; E2B publishes resume ≈ 1 s, pause ≈ 4 s/GiB.
   spark-vm should set and publish its own measured resume/wake target for
   #47 — whatever the boat.dev/provider baseline shows — or the streaming
   win looks unmeasured. (Product judgment; see C14: competitor figures are
   market context only, not the number.)
3. **Stopped-state cost story.** AgentComputer publishes cold storage at
   $0.000027/GB-hour; E2B bills only running time; Fly.io stops compute
   billing on hibernate. spark-vm's hosted pricing story needs an equally
   explicit stopped/cold tier.
4. **TermSquad's $9/mo always-on simplicity** undercuts spark-vm for
   terminal-only users; the desktop + streaming + approvals stack must justify
   the complexity gap (marketing framing, not just engineering).
5. **Docker's free local-first model** is unbeatable on price for local use;
   spark-vm wins on hosted control, latency (design-intent), and governance
   — not on price.

## Implications → backlog

- **C14 — #47 resume-latency target** (competitor, informed by Fly.io/E2B
  published figures): publish a measurable resume/wake target for the live
  control plane; include it in the #47 spec before implementation. The
  target must be set from a measured boat.dev/provider baseline, with
  competitor figures used as market context only — not as the number (Fly.io's
  100–500 ms is a Firecracker-microVM figure; boat.dev hosted VMs are a
  different substrate with different snapshot-restore characteristics).
- **C15 — #47 stopped/cold cost tier** (competitor, informed by AgentComputer
  cold storage / E2B running-only billing): the hosted pricing thinking must
  include an explicit stopped/cold tier, or the always-on cost story loses to
  TermSquad's $9/mo and AgentComputer's cold-storage rate. Cross-component
  note: a stopped tier requires the control plane to expose stopped-state
  resource retention (disk) to billing — that is the real build surface.
- **C16 — #47 control-plane-visible lifecycle parity audit** (competitor):
  audit the #47 ticket scope against this scan's scorecard for the
  control-plane-visible lifecycle only (pause/resume/stop/start/restart —
  E2B's paused-session model, Daytona VM pause/resume, and Daytona's
  stop/archive/delete model are the parity targets), and file gaps as #47
  sub-items. Split archive in two: the storage-offload backend stays out of
  scope (substrate-conditional); the control-plane-visible archived state +
  auto-archive/auto-delete policy model are in scope, because lifecycle
  completeness (lag #1) and stopped/cold billing (C15) both require modeling
  retained states beyond stopped. Audit note: restore-path parity (Daytona's
  archive↔resume round-trip) belongs in the audit too — lifecycle
  completeness covers transitions, not just state names. Explicitly out of
  scope: snapshot semantics (not surveyed in this pass — needs its own
  survey; snapshot coverage was not in the scorecard).

## Sources

Survey conducted 2026-09-20 ~14:54–15:04 CDT; per-item inline links above are
the source record. Note on one corpus date: the morning watch's "June-2026
BrowserSkill open-sourcing" attestation was verified against the upstream
repo (github.com/tencent/browserskill) with coverage dated 2026-09-18, as
recorded in COMPETITOR_ANALYSIS.md; not re-read in this pass (out of scope
for this axis).

