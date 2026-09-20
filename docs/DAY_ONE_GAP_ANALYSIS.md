# Day-one gap analysis: what a tenant Muse needs vs what the repo has

**Status: analysis, not a commitment.** Code-state claims below were verified
against the repo tree at `c2e68e8` (2026-09-19); issue/PR numbers are GitHub
references as of 2026-09-19 (not code-verifiable from the tree).
Honesty rules apply (`docs/POSITIONING.md`): this describes current
state and work to do, not promises. This is design thinking, not a ship
announcement; claims stay on the self-hosted reality until the hosted
product exists.

**Non-overlap map (what this doc is not):**
- The pipeline stages (discover → signup → identity → provision → box →
  sentinel → push → app) are `docs/HOSTED_GAP_ANALYSIS.md`. This doc is the
  capability slice: the five things a Muse needs *on the box on day one*.
- The command-level first-run script (exact commands, pass criteria, status
  vocabulary) is `docs/FIRST_TEN_MINUTES_SPEC.md`. This doc maps the
  surfaces that script assumes; it does not re-argue the script.
- Funnel, activation framework, and research are `docs/FIRST_RUN_ACTIVATION.md`,
  `docs/RESEARCH_AGENT_SANDBOX_ADOPTION.md`, `docs/RESEARCH_FIRST_RUN_PILOT.md`.

**The five surfaces.** A day-one Muse needs: a **browser** (drive the web
without seeing credential values), **creds** (secrets installed and swapped
without touching values), **jobs** (spawn background work and steer it),
**approvals** (file a request, park on a signal, have a human answer), and
**push** (the summons must reach the human). For each: need, state, gaps.

Gap classes: `[BUILD]` exists nowhere, build it; `[HOSTED]` the single-user
OSS substrate needs a tenant dimension for hosted; `[DESIGN]` design exists,
code does not; `[POLICY]` needs an operator (user) decision first.

## 1. Browser — spec only, no hands

**Need.** The on-box equivalent of the managed `browser.spawn_task` /
`browser.steer_task` vocabulary: drive Chromium for logins, forms, scraping,
checkout flows — with the SPEC's hard rule that no real credential value
ever exists in the stack (only `hsurr:` placeholders, swapped on egress).

**State (c2e68e8).** `browser-driver/SPEC.md` + `REVIEW.md` — spec-only;
**no bdrive code, no obox agent loop exists in the repo** (directory holds
only the two markdown files). The only real browser-driving surface today
is the CUA bridge (`cua/bin/cua-bridge.py`: loopback `127.0.0.1:18731`,
screenshot + input) — the *operator's* desktop over an SSH tunnel, not a
tenant-visible browser service.

**Gaps.**
- `[DESIGN]` browser-driver implementation not started: the fixed `bdrive`
  action protocol (the "hands") and the on-box agent loop (the "brain")
  are unwritten code. New item **H17**.
- `[HOSTED]` the SPEC's trust model is single-tenant (one obox, one swapd,
  one box); per-tenant browser profiles, per-tenant bdrive routing, and
  the jail cell-mirror for obox are unaddressed in code. Fold the tenant
  dimension into H11's audit; H17's first slice ships single-tenant.
  Note: the SPEC bakes in same-box proxy (`http://127.0.0.1:18080`,
  refuse-to-start without it); the multi-tenancy research findings 2
  (proxy outside the tenant guest) and 4 (secrets out-of-guest) could
  reshape H17's hosted deployment — the first slice must not cement the
  same-box-proxy assumption behind anything but an interface.
- `[HOSTED]` CUA bridge posture (loopback-only, operator-tunnel) is
  correct for self-hosted and wrong as a hosted surface — the tenant
  Muse reaches its own box's bridge instance over its own SSH session
  only after H4's connection bundle exists. Not a defect today; a known
  shape constraint.

## 2. Creds — the strongest surface, single-user shaped

**Need.** The Muse installs and uses secrets it can never see: provision-time
install via narrow writers, placeholder→value swap on egress, audit lines.

**State (c2e68e8).** swap proxy (`proxy/swap-proxy.service`: mitmdump on
`127.0.0.1:18080` with `swap_addon.py`), narrow writers (`cred-store-set`,
`cred-registry-set`, `grant-writer` — sudoers-scoped to the operator),
`cred` CLI, cred-ui (loopback `127.0.0.1:18740`, SSH-tunnel access), and
the #91 secrets-dir hardening (`proxy/enforce_secrets_dir.py`, 0700
`swapd:swapd` on `/home/swapd/secrets` + inference dir, load-time warn on
drift). All single-user/operator-shaped.

**Gaps.**
- `[HOSTED]` Per-tenant secret stores: swapd has one secrets tree; the
  grants registry scopes per-host (`hosts.allow`, `ssrf.allow/deny`) with
  **no tenant dimension**; audit lines carry no requester/job attribution
  (open issue #14). Folds into H11/H5's schema work.
- `[POLICY]` Provision-time install: the ten-minute spec §3a needs a
  provisioned `smoke-test` credential, an echo endpoint in `hosts.allow`,
  and a **scoped sudoers extension for the tenant agent user** (shipped
  `proxy/sudoers-swapd` grants writers only to the operator). No
  provisioning sequence exists yet (H4's territory); consolidated as new
  item **H19**.
- `[BUILD]` Open creds/swap hardening issues: #92 SSE response bodies
  bypass scrubbing (medium), #94 open-redirect on an allowlisted host
  forwards the real secret off-allowlist (low), #93 `ssrf.deny` rewritten
  non-atomically against mtime hot-reload (low), #90 env-var overrides
  redirect security-critical writer paths (low), #121 bare-rendering scrub
  triples for multi-entry secrets (low), #89 SETUP.md teaches the
  shell-history-leaking secret-install pattern (low).
- `[BUILD]` Open cred-ui hardening: #85 served from the writable checkout
  — JS injection into the human's secret-pasting page (high), #86 no
  authentication beyond a non-secret header (medium), #114/#96 silent
  registry-key drops, #118/#116 non-atomic host registration + input
  validation.

## 3. Jobs — ships, but the trust model is one operator

**Need.** Spawn background work, steer it by turns, read results, watch
for stalls — the `muse-job spawn/status/log/kill/resume/close/watch`
vocabulary.

**State (c2e68e8).** `muse-job/bin/muse-job` (plus `-sweep`, `-watchdog`),
client library, plugin hooks, one worktree + tmux session per job —
real and used daily by the loop itself.

**Gaps.**
- `[BUILD]` Open trust/isolation issues: #11 job agent can rewrite
  `../job.json` (management metadata in the agent-writable tree,
  medium), #9 no secret scanning on the operator→agent funnel
  (enhancement), #12 hardening batch (low), #13 no agent-immutable
  protected sections (enhancement).
- `[BUILD]` Watch gaps: #42 no signal for "muse process gone, pane at
  shell" (enhancement), #41 dead-tmux auto-recovery runs multi-minute
  resume inside the monitoring pass (enhancement).
- `[HOSTED]` No tenant job isolation or per-tenant job attribution —
  folds into H11.

## 4. Approvals — the loop exists; the signal it parks on does not

**Need.** Muse files an approval, parks on a machine-readable signal, human
answers on a page, grant mints, task verifies end-to-end.

**State (c2e68e8).** confirmd (`confirm/confirmd.py`: tailnet-only service,
`CONFIRM_OWNER` expected Tailscale LoginName — **single owner, no
multi-tenant roles**), mobile pending page with auto-refresh + two-tap
Approve (#20), `confirm-request` CLI (TTL default 3600).

**Gaps.**
- `[BUILD]` **The client-visible pending/terminal-decision signal does not
  exist.** `/api/pending` is a JSON poller for the human page (same owner
  auth gate as the pages); what is missing is the *agent-client* leg: a
  machine-readable pending signal carrying the approval id back to the
  refused request, plus terminal decision (approved/denied/expired)
  delivery. The ten-minute spec §6.6 requires it; today on swap refusal
  the proxy returns None (placeholder goes upstream untouched → remote
  auth failure) and on egress refusal the connection is killed — neither
  is parkable. Without it the minute 5–8 script is not executable.
  New item **H18**; pre-launch, proxy/confirmd track.
- `[HOSTED]` H10: per-tenant pending queues, tenant attribution on every
  approval/audit line, roles beyond single `CONFIRM_OWNER`.
- `[BUILD]` Open confirmd hardening: #70 HOST_ADDRS snapshotted at startup
  (high), #71 serialize `/answer` per approval id (medium), #72 fail loud
  when the audit log is unwritable (medium), #76 flood control + atomic
  writes (medium), #77 low-risk leftovers (low), #78 HMAC-authenticate
  CSRF nonce-ring entries before any lower-trust filer exists (medium,
  hosted).
- `[BUILD]` Email-fallback summons (ten-minute spec §4): no operational
  AgentMail sender identity, no signup-collected email → summons channel
  mapping. Fold into H14's summons work or file when H4's signup
  mechanics exist.

## 5. Push — sender library ships; the service does not

**Need.** The first approval's summons must reach the human's phone without
the page open.

**State (c2e68e8).** `confirm/push.py` — RFC 8030/8292/8291 VAPID Web Push
sender (keygen, ES256 JWT, aes128gcm), operator-generated keypair
(`CONFIRM_VAPID_KEYS`), push disabled unless configured; shipped via PR
#48. The pending page has a push-subscribe button.

**Gaps.**
- `[BUILD]` H14(a): standalone push service (enqueue/retry) unbuilt —
  **unblocked now** (VAPID keypair is operator-generated at setup per the
  shipped `push.py --gen-keys` flow, and the component is a portable
  service that runs hosted or self-hosted alike — the loop's P16 already
  treats H14(a) this way, though the base doc's stale "H2 BLOCKED" row
  hasn't caught up).
- `[HOSTED]` H14(b): confirmd approval-created hook + per-tenant
  subscription scoping — gated on H10/H11's tenant model. Note the
  separable slice: the approval-created hook itself is not
  tenant-dependent and can ride H14(a) as a both-supported item; only
  the per-tenant subscription scoping needs H10/H11.
- `[BUILD]` The email-fallback summons (§4 above) retires only when H14
  ships; until then no summons channel is operational at all.

## New backlog items proposed by this analysis

- **H17 — browser-driver implementation, first slice**: turn
  `browser-driver/SPEC.md` into code — the `bdrive` fixed action protocol
  + Chromium driver service on the box (single-tenant first; tenant
  dimension rides H11). The `obox` agent loop is deliberately deferred
  to a follow-up item (it rides H11's tenant dimension too — the jail
  cell-mirror and the proxy placement are H11's audit outputs). Ships in
  OSS, hosted runs it per tenant.
- **H18 — client-visible approval pending/terminal signal**: the
  ten-minute spec §6.6 interface — machine-readable pending signal
  carrying the approval id + terminal decision (approved/denied/expired)
  delivery. Proxy/confirmd track; pre-launch blocker for the first-run
  script.
- **H19 — provision-time credential install packet**: scoped sudoers for
  the tenant agent user + `smoke-test` credential install + echo
  endpoint allowlist entry (ten-minute spec §3a mechanics as one tracked
  item). H4 provisioning-track when it starts; designable now. **The
  design is conditional on H11's privilege-domain answer** (multi-tenancy
  research finding 4): if the audit keeps secrets out-of-guest, the
  install packet becomes an operator-side/control-plane mechanism, not
  tenant sudoers — do not build the tenant-sudoers shape before H11
  names the privilege domain.

## Honest summary

Of the five day-one surfaces, **jobs** is the most complete (real CLI,
loop-proven, trust issues open), **creds** is the strongest technically
but single-user shaped, **approvals** has the human half (page, two-tap)
and is missing the Muse half (the parkable signal — H18) and the
multi-tenant half (H10), **push** has the sender library and no service
(H14), and **browser** has a spec and no code (H17). ("Push" names both
a pipeline stage and a capability surface here: the stage is the
summons-reaching-the-human half of the funnel; the surface is the
sender/service machinery — the split is deliberate, not a duplication.)
The shared spine: approvals (H18), push (H14), and creds all converge on
the proxy→confirmd `_file_approval` path — hardening that path
(attribution, atomicity, the parkable signal) is shared work, not three
separate projects. Nothing here changes the pipeline-stage map
(`HOSTED_GAP_ANALYSIS.md`): the box half is real, the hosted half is
designs and operator decisions — this analysis adds the capability-surface
view and three buildable items.
