# Suspend/wake mechanics research

Date: 2026-09-19. Strategy loop, research archetype.

## Why

Two open items name this exact gap and it has never been researched as its
own subject:

- `docs/GPU_PATH_RESEARCH.md` (PR #40) follow-ups: "extend `status` with
  `suspended`/`waking` and define `dial()` wake semantics" before the H4
  Fly driver ships the planned contract extensions.
- `docs/PRICING_THINKING.md` (PR #30): "idle/suspend TBD, wake path TBD"
  blocks launch terms before the idle/suspend economics are decided; the
  H13 idle-detector design needs to know who owns idle detection —
  provider or control plane.

The H3 signup design (`docs/HOSTED_SIGNUP_ONBOARDING.md`, PR #24) defines
the interface every provider driver implements: `provision` / `status` /
`dial` / `ssh_info` / `destroy`. This pass answers: how do agent-sandbox
and VM providers implement idle suspend and wake, and what contract should
H4's `suspended`/`waking` states plus async `dial()` expose so it stays
provider-agnostic.

Honesty rules (`docs/POSITIONING.md`): everything below is current state
and work to do, not promises. Vendor facts are dated; vendor behavior
changes. Third-party-sourced claims are marked [T]; vendor docs [V].

## The short version

- Every serious provider suspends idle boxes and bills ~zero compute while
  suspended; the suspend mechanism varies (memory snapshot vs disk-only vs
  cold stop) and the contract must not promise memory preservation.
- **Wake-on-HTTP is provider-native** (Fly Proxy autostart, Runloop
  `wake_on_http`); **wake-on-SSH is never provider-native** — it exists in
  the wild only as a gateway layer (sandbox0's ssh-gateway). Our
  wake-on-SSH-dial is control-plane code we build, not a provider feature
  we inherit.
- Idle detection splits: HTTP-traffic-scoped providers (Fly) vs explicit
  control-plane idle policy (Runloop) vs lease heartbeats (agentarea).
  The H13 idle detector is control-plane work regardless of provider.

## Vendor findings

### Fly Machines [V]

- `auto_stop_machines`: `off` | `stop` | `suspend`. `stop` = cold shutdown
  (restart ~seconds). `suspend` = full VM state (memory, CPU, network)
  dumped to disk; resume in a few hundred milliseconds.
- Suspend is **not durable**: host migration, maintenance, or capacity
  pressure can turn a resume into a cold start. Fly's own guidance: treat
  suspend as a faster `stop`, not a guaranteed warm restart.
- Constraints: machines must have ≤ 4 GB RAM (current reference docs
  recommend ≤ 2 GB); no swap, no scheduled machines, no GPU; machines
  created before 2024-06-20 cannot suspend.
- **Consequence for H3's reference spec (Ubuntu 24.04, 8 vCPU / 15 GB RAM):
  it exceeds the memory-suspend cap, so on the H4 Fly driver the
  reference box's "suspend" degrades to cold `stop` — wake is a cold
  start (seconds), never a warm memory resume. Memory-suspend is a
  shape-dependent axis the driver must document per shape.**
- After resume the clock is briefly wrong — breaks JWT `nbf` validation,
  cron, cache TTLs, TLS cert validation for a second or two. **Direct
  implication for H3's short-lived SSH certs: cert validation needs a few
  seconds of clock-skew leeway, or wake→SSH races fail intermittently.**
- Billing: suspended == stopped == storage-only (no CPU/RAM). Attached
  volume storage is billed while the volume exists, regardless of machine
  state.
- States: `running`, `suspending`, `suspended`, `starting`, `stopped`.
  Machines API: suspend endpoint; wait-for-state accepts `suspended` as a
  target; starting a suspended machine resumes from snapshot with cold-start
  fallback; `stop` on a suspended machine discards the snapshot.
- Auto-wake: `auto_start_machines = true` resumes suspended machines for
  incoming requests **through the Fly Proxy (HTTP services)**. There is no
  SSH wake.

### Fly Sprites

- Purpose-built persistent VMs for coding agents (per
  `agent_notes/provider-recommendation-2026-09-18.md`): auto-pause when
  idle with compute billing stopped, filesystem checkpoint/restore ~1s,
  boot 1–12s, cold storage ~$0.02/GB-month billed on blocks actually
  written. This is almost exactly the idle-box model — an idle 20GB
  Sprite costs on the order of $0.40/month paused (figures volatile,
  2026-09-12 check).

### Runloop devboxes [V]

- Full published state machine: Provisioning → Initializing → Running,
  plus Failure, Shutdown, Suspending, Suspended, Resuming. **Compute is
  billed only in initializing / running / suspending / resuming.**
- Suspend preserves **disk only, not memory** — explicitly documented.
  This is the counterexample to memory-snapshot providers: a
  provider-agnostic contract cannot promise in-memory process survival.
- Idle policy is explicit control-plane configuration:
  `lifecycle.after_idle { idle_time_seconds, on_idle: suspend | shutdown }`.
  Default max lifetime 1h via `keep_alive_time_seconds` unless configured.
- `wake_on_http`: tunnel returns `503` + `Retry-After: 5` on a suspended
  devbox, resumes (<1s infrastructure overhead), caller retries; webhooks
  auto-retry so it works out of the box; browsers get an auto-refresh
  page. HTTP through the tunnel counts as activity (keeps the box awake).

### E2B [T]

- `autoPause` + `Sandbox.connect()` auto-resumes paused sandboxes
  transparently — the canonical "connect-resumes" pattern. Paused
  sandboxes cost $0 compute.
- Memory-snapshot restore on the order of milliseconds to ~1s; in-memory
  variables survive resume. Lifecycle separates `pause` (state saved)
  from `kill` (permanent).
- Operational pattern from the ecosystem (herdr-e2b): count paused boxes
  as *alive*; resume on open; correct the status record with a read-only
  probe, never with `connect` (which would undo the pause).

### CodeSandbox VMs [V]

- Hibernate = pause + save memory to disk; resume from memory snapshot
  ~1.5s. If no snapshot exists, clean boot re-runs setup tasks — the SDK
  exposes `bootupType` so callers can distinguish resume from clean boot.
- Workspace persists 8–15 days of inactivity (plan-dependent); memory
  snapshots are cleaned after 7–31 days with no work loss (disk state
  survives snapshot cleanup).

### sandbox0 [V] — new to the corpus

- SSH-first product: `s0 sandbox get` returns ssh host/port/username; plain
  `ssh`/`sftp` clients.
- "If the sandbox is paused, `ssh-gateway` asks the control plane to
  resume it before attaching the session." This is the proof that
  **wake-on-SSH-dial is a gateway-layer pattern, not a provider
  primitive** — and it is the shape our control plane should copy.
- Pause/resume lifecycle doc (vendor-verified 2026-09-19):
  `auto_resume` is a **sandbox-level gate** for whether inbound access
  may wake a paused sandbox (`true` default; `false` = explicit resume
  required). `ttl` triggers auto-pause; `hard_ttl` deletes the sandbox
  identity and durable state. Running PIDs, memory, sockets, and client
  attachments do **not** survive pause (disk-only, like Runloop).
- Distinguishes `503 "sandbox is waking up"` (accepted transition not yet
  committed — poll before retrying) from `503 sandbox_resume_failed`
  (attempt ended unsuccessfully — do not treat as still in progress).
  This is the failure-shape taxonomy our `dial()` should copy.

### Others

- **Cloudflare Containers [T]**: instances sleep on Cloudflare's own timer;
  no charge while asleep. The hub must model `asleep` as a *distinct*
  status from `stopped` — one is the substrate idling something out, the
  other is an operator action. Applies directly to our state model.
- **OpenKruise agents [T]**: OSS wake-on-traffic design — gateway → manager
  resume with first-writer-wins concurrent dedup, blocks until Ready, 503
  on timeout. The concurrency pattern `dial()` should copy.
- **Sandbase [T]**: E2B-shaped REST verbs `pause`/`resume` (1–3s), per-
  template inactivity timeouts, `stopped` = permanently deleted.
- **agentarea [T]**: lease-based — command heartbeats keep an active lease;
  after finish the binding moves to an idle TTL; a later request wakes or
  recreates and materializes the durable workspace.
- **Daytona / Vercel Sandboxes / Northflank / boat.dev**: suspend/idle
  mechanics unverified this pass — no claims made. **TermSquad**: always-
  on model per `docs/COMPETITOR_ANALYSIS.md` (no idle suspend).

## Mechanism comparison

| Provider | Suspend mechanism | Wake triggers | Wake latency | Billed while idle | Idle detection |
|---|---|---|---|---|---|
| Fly Machines | memory snapshot (≤4GB; not durable) | HTTP via proxy (auto) | ~100s of ms (resume) / ~seconds (cold) | storage only | HTTP traffic (proxy) |
| Fly Sprites | checkpoint/restore | agent activity | ~1s | ~$0.02/GB-mo cold storage | provider idle |
| Runloop | disk snapshot (memory NOT preserved) | HTTP via tunnel (503+Retry-After), manual resume | <1s | none (compute) | explicit `after_idle` policy |
| E2B | memory snapshot | `connect()` auto-resume | ~ms–1s | $0 compute | `autoPause` timeout |
| CodeSandbox | memory snapshot (cleaned 7–31d) | SDK resume | ~1.5s / clean boot | workspace retained | inactivity |
| sandbox0 | pause (gateway layer) | **SSH gateway → control-plane resume** | not published | not published | not published |
| Cloudflare Containers | sleep | explicit wake | not published | none | provider timer |

## Recommendations: the H4 contract

These are research recommendations for the H4 Fly driver and the H13
idle/suspend design, not shipped interfaces.

1. **State model**: `provisioning | running | suspending | suspended |
   waking | stopping | stopped | failed | destroyed`. The canonical
   transitional name is `waking` (matches the H4 extension BACKLOG.md
   already records, and sandbox0's `"sandbox is waking up"`). Keep
   `suspended` distinct from `stopped` in status and in every UI that
   shows it — one is the substrate (or control plane) idling a box out,
   the other is an operator/destroy action (Cloudflare lesson). Expose
   whether the last wake was a warm resume or a cold start as a
   `status()` field — Fly and CodeSandbox both degrade silently, and
   the caller needs to see it *after* the fact, not branch on it during
   the dial. Migration from H3 §6's enum (`creating | ready | degraded |
   dead`): `creating→provisioning`, `ready→running`, `dead` splits into
   `failed` (diagnosed, possibly retryable) and `destroyed` (terminal,
   operator/driver action). `degraded` stays — as an orthogonal health
   flag beside the lifecycle state, not as a lifecycle state itself.
2. **Transitions the model must define** (a state model that lists
   states without transitions is a diagram, not a contract):
   - *Resume failure*: back to `suspended`, with the error surfaced on
     the failed `dial()` — not terminal `failed`. Copy sandbox0's
     taxonomy: distinguish "waking up" (accepted, still in flight —
     poll and retry) from "resume failed" (attempt ended; do not treat
     as still in progress). A bounded retry is allowed; an unbounded
     spinner is not.
   - *`destroy()` always wins*: a destroy racing an in-flight wake
     cancels the wake; a `dial()` that arrives at a terminal box
     observes the terminal state and refuses (never starts a wake).
     The driver must be able to abandon in-flight transitions.
   - *`suspend` of a non-runnable box is an explicit driver error*
     (silent no-ops hide broken idle detectors; the control plane
     treats the error as log-and-skip).
   - *`auto_resume` gate*: borrow sandbox0's per-tenant flag — whether
     inbound dials may wake a paused box at all. Abuse-relevant
     (cf. H13's abuse-controls input): a compromised or runaway tenant
     must not be re-wakeable by anyone with the dial endpoint.
3. **Suspend guarantees**: guarantee **disk persistence only**. Do not
   promise in-memory process survival across suspend — Runloop doesn't,
   sandbox0 doesn't, and Fly's suspend degrades to cold start.
   Provider drivers must document the axis per shape
   (memory-suspend: yes / no / cold-stop-only). **And on the H4 Fly
   driver the reference shape gets "cold-stop-only": H3 §6's fixed
   spec (Ubuntu 24.04, 8 vCPU / 15 GB RAM) exceeds Fly's memory-suspend
   cap (≤ 4 GB hard cap, ≤ 2 GB recommended), so the reference box's
   "suspend" is a cold `stop` — wake is a cold start measured in
   seconds, never a warm memory resume.** If H13's "idle boxes suspend
   for free" needs warm resume at reference scale, that's Sprites'
   checkpoint/restore, not Machines' suspend.
4. **Idle detection is control-plane work (H13)** — with one explicit
   provider-native disable. Fly's proxy autostop sees HTTP traffic only;
   SSH sessions and cron jobs are invisible to it, and it would suspend
   boxes *underneath* running SSH sessions. So the H4 Fly driver sets
   `auto_stop_machines = "off"` and the control plane drives suspend
   through the Machines API — provider-native autostop is disabled,
   not worked around. The registered-workload registry decides what
   counts as activity: an SSH session, a running agent job, and —
   critically — scheduled cron workloads. A box whose only workload is
   cron must *wake on schedule*, not sleep through it; none of the
   surveyed providers solve wake-on-schedule for us (Fly `schedule`
   was considered and rejected: scheduled machines are disqualified
   from suspending, and the config is static, not per-tenant dynamic).
   Sequencing note: the registry can't be finalized until H11 answers
   the isolation shape (per-tenant box vs per-tenant processes) —
   BACKLOG.md already gates H13 on H11.
5. **`dial()` semantics** — an amendment to H3 §6, not a re-specification.
   H3 defines `dial(vm_id) -> bidirectional stream`; that return type
   stays, and `ssh_info()` keeps returning the connection bundle. What
   this research adds: `dial()` gets wake-wait semantics — it blocks
   (bounded, with the sandbox0/OpenKruise patterns: first-writer-wins
   concurrent dedup so N racing dials trigger one wake; failure
   taxonomy from rec 2) until the box is `running`, then opens the
   stream. The caller never distinguishes "was suspended" from "was
   cold" at dial time — warm-vs-cold is a `status()` field (rec 1), not
   a dial-time branch. Runloop's `503 + Retry-After: 5` is the HTTP
   analog of the wait contract; our analog is a blocking dial with a
   timeout, not a poll loop pushed onto every caller.
6. **Wake-on-SSH-dial is a gateway, not a flag**. Fly and Runloop prove
   no provider wakes on SSH natively. The control plane needs an
   ssh-gateway (sandbox0's shape): intercept the SSH dial, resume-or-
   provision, then attach. SSH keepalives alone cannot wake a suspended
   machine — the dial path must go through the gateway. **Tailnet
   interaction**: H3 §6.3's optional tailnet-direct SSH is an
   optimization that bypasses the gateway — a Muse SSHing over its
   tailnet to a suspended box never touches the gateway, so no wake
   happens. Either tailnet dials route through the gateway too, or
   suspend is disabled while the tailnet-direct path is active. This is
   an H13/H3 design decision, flagged here so it isn't discovered in
   production.
7. **Clock-skew fix for H3 certs: issuance-side, not validation-side.**
   Short-lived SSH certs plus Fly's post-resume clock skew is a
   designed-in race — but OpenSSH's validator (`sshd` on the VM, which
   holds the skewed clock) has no clock-skew-tolerance knob for
   `valid_after`/`valid_before`. So do it at issuance: the CA backdates
   `valid_after` by ~60s (negligible against ≤ 24h certs with
   50%-lifetime renewal), and/or the ssh-gateway gates SSH attach on
   NTP sync after a wake. The H3 follow-up targets cert *issuance*,
   not "cert validation."
8. **Billing posture for the operator spend-cap packet** (NEEDS_USER.md):
   suspended = storage-only on Fly Machines, none-compute on Runloop,
   cold storage on Sprites. The per-run cap math should price "suspended
   overnight" as storage-hours, not compute-hours — the abuse case
   (idle boxes) is cheap by construction, which is the point.

## Claimable vs forbidden (docs/marketing honesty)

- **Claimable**: "suspends when idle; wakes on SSH dial"; "no compute
  charges while suspended"; "disk state always persists across
  suspend."
- **Forbidden**: "instant wake" (cold-start fallback exists); "zero cost
  when idle" (storage costs exist); "everything resumes exactly as it
  was" (memory preservation is provider-dependent); "cron keeps running
  while suspended" (nothing runs while suspended — wake-on-schedule is
  a control-plane feature to build).

## Open verification (next pass)

- Daytona sleep/suspend mechanics (vendor docs).
- Vercel Sandboxes: max lifetimes, any suspend story.
- boat.dev: suspend/idle behavior — relevant to the Fly-vs-boat fallback
  evaluation (NEEDS_USER.md).
- Sandbox0 pricing/wake-latency figures (not published in the SSH docs).

## Follow-ups

- **H4** (Fly driver): implement `suspended`/`waking` states and wake-wait
  `dial()` per §"Recommendations" above; driver documents the
  memory-preservation axis **per shape** (reference shape =
  cold-stop-only on Fly); `auto_stop_machines = "off"` with control-plane
  suspend via the Machines API; per-tenant `auto_resume` gate (sandbox0
  pattern); operator spend-cap packet prices suspended hours as
  storage-hours.
- **H13** (suspend/idle design): control-plane idle detector +
  registered-workload registry (after H11 answers the isolation shape);
  wake-on-schedule for cron workloads; ssh-gateway wake-on-dial layer;
  tailnet-direct SSH vs suspend interaction decision.
- **H3** (signup doc): cert *issuance* backdates `valid_after` ~60s (or
  gateway gates SSH attach on NTP sync after wake); record the
  `dial()` wake-wait amendment and the status-enum migration
  (`creating→provisioning`, `ready→running`, `degraded` as orthogonal
  health flag).
- **PRICING_THINKING.md**: idle/suspend economics can now move from TBD —
  "suspends when idle, wakes on SSH dial; no compute charges while
  suspended; disk persists" is vendor-grounded.
- **Competitor corpus (C1 watch)**: sandbox0 is new to the corpus —
  SSH-first agent sandbox with gateway wake + `auto_resume` gate; worth
  a watch entry.
