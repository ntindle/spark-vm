# Changelog

All notable changes to spark-vm are recorded here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/). The version lives in the
`VERSION` file at the repo root (see `docs/VERSIONING.md`); this file is
its human-readable companion.

## The changelog ritual

This changelog only works if entries land with the change, not after it:

1. **Every PR that changes anything user- or operator-visible adds one or
   two bullets under `## [Unreleased]`**, in the right section
   (`Added` / `Changed` / `Fixed` / `Security`). Write for the person
   running spark-vm, not the person who wrote the diff — no file paths,
   function names, or internal audit numbering — and link the PR number.
   Reviewers request changes when the entry is missing: it's a merge gate,
   not a suggestion (see `CONTRIBUTING.md`).
2. **Trivial scope** (typo, single-line doc fix, formatting) doesn't need an
   entry; merge notes are enough. **Seeding-batch exemption:** PRs authored
   before this ritual merged (the 2026-09-19 queue-drain batch) are exempt —
   the per-PR entry rule applies prospectively from this PR's merge.
3. **At release time**, the release commit (the `VERSION` bump — see
   `docs/VERSIONING.md`, "Cutting a release") moves the whole
   `## [Unreleased]` section into `## [0.2.0] - YYYY-MM-DD` (pattern:
   `## [x.y.z] - YYYY-MM-DD`), adds the compare links in the footer
   scaffold at the bottom of this file (uncomment and fill it in), and
   leaves a fresh empty `## [Unreleased]` section behind for the next PR.
4. Docs are a first-class product here, so anything merged under `docs/`
   gets an entry like a feature. Notes that never land in the repo — e.g.
   the loop's working notes in its `agent_notes/` workspace (not part of
   this repo) — don't get entries.
5. **A revert is a change too**: the revert PR gets its own entry noting
   the reversal, so the changelog reads forward in time.

## [Unreleased]

### Added
- Evening competitor watch (2026-09-22): DigitalOcean's Managed Agents
  product page is readable again — Tool Playground (pre-production policy
  testing), scheduled/webhook triggers, and org-policy concepts
  (actors, toolbelts) — plus a flag that DO's marketing claims (~200 ms
  resume) outrun its own measured benchmark (305 ms); Fly.io Sprites'
  lifecycle docs publish warm wake 100–500 ms and cold wake 1–2 s with
  dropped TCP state, bearing on the resume-latency target. New to the
  tracked set: Boxd ($2M pre-seed, KVM persistent-machine competitor,
  vendor-claimed fork-including-memory in <100 ms), the OpenAI Agents API sandbox
  partner list (formalizes the harness-vs-compute split — INFERRED from
  the partner list, not an OpenAI claim), and a new snapshot/restore
  datapoint on the already-corpus-ed Upstash "Box" entry; independent hands-on coverage of the
  DO launch is still absent. (#270)
- Golden-image round-trip gate operator procedure (spec §6.7): the
  file → answer → grant-mint → verify sequence with the filing-count
  determinism check and mandatory fixture teardown pre-publish, wired to
  the existing gate-fixture tooling. (#271)
- Secrets-posture corpus gains DigitalOcean Managed Agents as the fifth
  convergent data point (their launch release claims a separate secrets
  service with "credentials brokered at execution time" that "never reach
  the model or the sandbox" — press-release source, no mechanism detail
  scored), and the org-policy vendor set gains DO's Action Gateway
  (governed tool access via one managed MCP endpoint) as a candidate. (#263)
- Morning competitor watch (2026-09-22): DigitalOcean launched Managed
  Agents in public preview — microVM-per-session Harness Runtime, Action
  Gateway (16,000+ tools via one MCP endpoint, credentials brokered at
  execution time), and active-CPU pricing ($0.044/vCPU-hour, 305 ms
  pause→resume claim) — filed as a new tracked competitor, with follow-up
  notes for the hosted product's pricing thinking, resume-latency target,
  secrets posture, and org-policy layer; Daytona shipped a routine v0.215.0
  SDK/CLI patch; the rest of the tracked set was quiet. (#256)
- Enforcement-downgrade contract for the agent jail (fail-closed, stated
  explicitly): a firewall-apply failure aborts the build before the jail
  starts, a boot-time apply failure blocks the container from starting, and
  a dead proxy means no egress rather than open egress — like Brig's
  policy-bound refusal, the workload never runs where its restriction
  cannot be enforced. The one residual the contract originally stated —
  no runtime re-apply — is closed by the firewall watchdog #260, which
  narrows the residual boundary to the 5-minute verify window. The contract
  mechanics are test-pinned. (#255)
- Deny-style billing guard committed for sandbox credential forwarding:
  when the hosted path forwards operator credentials into a sandbox,
  known metered-billing keys are deny-by-default without an explicit
  per-credential override (Brig's `deny` shape, including its documented
  environment-channel-only limit). Committed design, not yet shipped —
  no forwarding surface exists yet. (#255)
- Demo gallery, sixth asset: the push queue surviving an outage — the new
  "See it in action" row shows the standalone push worker's first delivery
  attempt hitting a dead endpoint (500) and rescheduling instead of losing
  the approval, the durable journal holding the summons, and the retry
  delivering once the endpoint answers (201). The generator replays the
  real enqueue/worker code paths against a local mock push service
  (throwaway keys, nothing leaves the machine). (#252)
- Push notifications now survive a dead push service: swapd enqueues every
  filed approval and a standalone push worker (`push-worker.service`)
  delivers with exponential-backoff retry, dead-lettering only after 8
  failed attempts with a loud log line. On the healthy path delivery
  waits for the next worker pass (up to 30s, tunable via
  `--worker-interval`). Runs wherever the deployment lives (self-hosted
  or hosted), like confirmd. (PR #204)
- Waitlist claim route: the invite email's claim link is now served —
  opening it shows the claim screen (masked owner email, the same
  what-happens-next steps as the invite email), and clicking through
  records the claim idempotently and logs it in the funnel trail. Dead
  or expired links land on an honest "no longer live" page, never an
  error dump. (#250)
- Provider failover-router design: the new design doc describes how the
  hosted control plane would keep a tenant session alive across a
  provider outage — which failures trigger a move to another provider
  (and which recover in place), the order of operations for the move,
  how session data is restored when VM snapshots can't cross providers,
  and how provider capabilities pick the fallback target. (#251)
- Provision-time injector (`harness/inject-provision-state.sh`): runs at
  first boot of the hosted agent VM and owns the provision-time half of
  the gate-fixture contract — preflights the golden-image manifest
  against the operator-pinned image SHA and fails closed on drift
  before box-live; tears down the gate fixture's `llm-api`→echo-host
  binding, failing closed on echo-host residue in the allowlists (which
  only the image-build gate can remove); asserts a real inference
  credential through the registry plus a blind compare against the
  public fixture dummy (the stored value is never read, never written,
  never printed); requires a fresh per-tenant swapd CA; installs tenant
  identity and records tenant attribution when their inputs are
  provided (both reported as deferred when absent, never fabricated);
  then proves the injected key with the provision-mode probe — a probe
  failure maps to provisioning-failed and box-live must not flip.
  Ships one JSON inject report on stdout and 55 hermetic tests. (#238)
- Night competitor watch (2026-09-22): quiet survey window — no launches,
  acquisitions, pricing changes, releases, or partner moves across the
  tracked set; boat.dev rate card and comparison table re-verified
  unchanged; two pre-window competitors newly surfaced and filed as
  watchlist items (Brig, Epho); adjacent color on Meta Muse's Sentinel
  per-user VM architecture (third-party deep dive of the pre-window
  launch). (#239)
- Waitlist operator tooling: `waitlist_invites.py --reconcile` repairs
  missing `invite_sent` funnel events after the commit → emit crash
  window — it re-derives the missing events for still-live invites from
  the waitlist store in the append-only posture (each re-derived event
  carries `reconciled: true` in its attrs; `--dry-run` previews), is
  idempotent, and skips rows whose invite is no longer live. (#237)
- Secrets-posture corpus: h-sandbox's Credential Vault (open-source,
  self-hosted sandbox control plane) becomes the fourth convergent data
  point for the placeholder-swap pattern — its docs describe fake-env
  placeholders in the sandbox with the real auth material injected at the
  egress sidecar only for host/scheme/method/path-bound requests (verified
  against their own docs 2026-09-21, verbatim quote in the research doc);
  the watch pass also records its OpenSandbox-adapter contract discipline as
  input to the hosted provider-adapter design. (#230)
- Secrets-posture corpus: opencomputer.dev's secret-store egress proxy
  (opaque placeholder in the sandbox, real key swapped in-flight on the
  outbound HTTPS call to the model provider, under an egress allowlist —
  verified against their own docs 2026-09-21, verbatim quote in the research
  doc) joins Daytona and Microsandbox as a third convergent data point for
  the placeholder-swap pattern. (#219)
- Competitor watch 2026-09-21 evening (docs/COMPETITOR_WATCH_2026-09-21_EVENING.md):
  quiet window — zero in-window deltas across the tracked set since the
  afternoon pass; one pre-window miss filed as watch item C18
  (h-sandbox/"Harakiri Sandbox" — open-source self-hosted sandbox
  control plane launched 2026-09-09, with a host-bound-egress credential
  vault and an OpenSandbox execution adapter, the closest open-source
  shape to spark-vm's secrets posture); AgentComputer's "unverifiable"
  egress posture refined to a stronger negative (real product with real
  pricing, still no stated egress policy). (#216)
- `jail/build.sh` is safer to inspect and harder to drift: `--help` / `-h`
  renders the script's header doc and exits before any side effect in ANY
  flag position (`build.sh --rebuild-rootfs --help` can't accidentally
  start the privileged build — the usage line documents that order), and
  the tailnet→jail SSH port is now single-sourced from `$JAIL_SSH_PORT`
  into the nftables DNAT rule via a quoted heredoc + placeholder
  substitution — the applied conf always carries the variable's value,
  with tests that render through the real sed pipeline.
- The single-command test story now actually covers every component:
  `pytest.ini` discovers the `cua/`, `jail/`, AND `credlib/` suites too —
  including a new `cua/test_shell_scripts.py` gate (`bash -n` +
  shellcheck warnings for the four host-side `cua/bin` scripts that
  can't run in CI, with an explicit skip when shellcheck is absent,
  now also wired into `ci.yml` so the gate actually executes) — and
  `confirm/test_push.py` skips explicitly (instead of erroring
  collection) on boxes without the `cryptography` package, so
  `python3 -m pytest` degrades gracefully.
- Approvals-plane gap analysis: a new doc walks the full path from a gated
  action to a human answer and back (refusal → filing → pending → human
  answer UX → push summons → terminal decision delivery → audit trail),
  against the code as it stands today. Headline finding: the plane is a dead
  end for the agent — refusals carry no approval id, answers deliver no
  decision, and expiry is a silent third outcome — and files two new issues
  (expiry's silent terminal outcome; answered-feed per-poll parse cost).
  (#215)
- Release-protection drift guard: the declared `main` branch ruleset's
  required CI checks are now verified bidirectionally against
  `.github/workflows/ci.yml` — renaming, adding, or removing a CI job fails
  the test suite until the declared ruleset is updated deliberately, so the
  release-tag/branch protection can no longer silently lag behind CI.
  (#208)
- Waitlist slice 3 remainder (H15 — path-A email parser + invite sender):
  `site/waitlist_patha.py` implements the email intake path
  (WAITLIST_OPERATIONS.md §2) — exclusion list (From, inbox,
  @agentmail.to) applied before counting, `Owner:` line override, the
  optional ed25519 pubkey + ≤280-char use-case line, exactly-one-candidate
  proceeds to a validated row with the path-A confirm opener, zero/≥2
  candidates get the §2 clarification reply only on DMARC-aligned mail
  (unauthenticated mail is silently triaged — no backscatter), a reply
  saying "forget me" triggers the §5 confirmation email with the signed
  forget link (never direct deletion), and the §6 per-sender 3/day intake
  limit; `site/waitlist_invites.py` drives §7 invite waves (top-N
  confirmed FIFO by confirmed_at, pricing + trial terms filled at send
  time from operator files, signed position line, 14-day `invite.`-prefixed
  HMAC claim tokens, `invite_sent` funnel events) plus the expiry
  rollover (unclaimed invites return to `confirmed` with confirmed_at
  reset to the expiry time, no re-confirmation). (#203)
- Competitor watch 2026-09-21 (docs/COMPETITOR_WATCH_2026-09-21.md): quiet
  window — no launches, pricing changes, partner moves, or version bumps
  across the tracked set since the 2026-09-20 pass; boat.dev's rate card
  re-verified ($20/mo = 555h of 4vCPU/8GB) with an xlarge
  capacity-allocation caveat flagged for verification before any 16-vCPU
  sizing decision; version resolution — Microsandbox v0.7.1 confirmed on
  the vendor releases page post-window (corpus record vindicated; no
  corpus change). (#191)
- Waitlist forget-me flow (H15 slice 3c): every transactional email footer
  now carries a signed one-click forget link (7-day, single-use,
  domain-separated from confirm tokens so the two can never validate at
  each other's endpoint); the signed link renders a delete-confirmation
  page and, on POST, atomically deletes the waitlist row, logs the
  `forgot` funnel event, and spools the spec-mandated deletion
  confirmation. The marketing page's `/go/selfhost` CTA now has both a
  no-JavaScript static redirect shim for the static host and a dynamic
  control-plane route that logs the `cta_click` event before redirecting
  to the self-host guide. The waitlist form's action posts to the
  control-plane origin via a deploy-time placeholder the operator fills
  at launch (a relative action would post to the static host, which has
  no serving layer). (#190)
- boat.dev 16-vCPU caveat confirmed as current vendor policy
  (docs/COMPETITOR_WATCH_2026-09-21_C17.md): the pricing page still
  footnotes xlarge as needing a $100+/mo plan plus operator capacity
  allocation, so any 16-vCPU hosted sizing must confirm capacity with the
  provider first; the baseline rate card is unchanged ($0.036/h default,
  stopped sandboxes free, $26 for one default running the whole month).
  (C17; #206)
- Competitor watch 2026-09-21 afternoon
  (docs/COMPETITOR_WATCH_2026-09-21_AFTERNOON.md): quiet window — no
  launches, pricing changes, releases, or partner moves across the
  tracked set since the morning pass; boat.dev's pricing page re-read
  and unchanged, and its twelve-provider comparison table verified as
  the page's current state (the earlier read was simply partial);
  Microsandbox still at v0.7.1, Docker Sandboxes still at 0.43.0, Daytona
  changelog still topped at v0.214.0 (Sep 15), TermSquad tiers
  re-verified unchanged; WSO2 reception broadens slightly ahead of the
  Sep 29 webinar. No corpus changes. (#209)
- Secrets posture page (#189): frames the placeholder-swap design as
  independently re-derived — the pattern is convergent across the industry —
  and compares swapd mechanism-by-mechanism against E2B, Daytona, Vercel,
  Cloudflare, and Microsandbox from their own docs (vendor links inline).
  States swapd's honest edges (request-body injection scope, response
  scrubbing, per-decision audit-as-authorization) and its conceded gaps
  (Microsandbox's DNS-pinned destination gate, E2B's per-request token
  minting), plus the concrete `allowOut`-vs-swapd egress-grant difference.
- First test suites for the two remaining untested components (O4): `cua/`
  gets hermetic tests for the `cua-bridge.py` localhost bridge — launch
  allowlist enforcement, the CSRF/host gate, window picking, and the
  click/type/key/launch endpoints (including the desktop→window coordinate
  mapping and the panel global-click branch) — plus syntax/shebang checks
  for the `cua/bin` shell scripts; `jail/` gets a hermetic smoke test for
  `build.sh` pinning its strict mode, idempotency guards, and the jail's
  documented isolation properties (no bind mounts, no DNS, proxy-only
  nftables egress, explicit UID range, sshd hardening, swapd CA temp
  cleanup). Both suites are wired into the CI `python-tests` job. (#187)
- Stopped/cold retention tier thinking (C15): the hosted pricing thinking
  now names the stopped-state cost story the live-control deep scan found
  missing — a published $0.000027/GB-hour cold-storage anchor (≈$0.79/mo
  for a stopped 40 GB box), running-only billing precedent, and the
  control-plane→billing contract the H4 provider interface already ships.
  Thinking only; no pricing-page row until the Billing decision lands.
- Waitlist 30-day post-drop purge: `waitlist_jobs.py --purge` permanently
  deletes dropped waitlist rows 30 days after the drop (the §5 retention
  rule), via an atomic `rows.jsonl` rewrite under the same data lock as
  the reminder/drop jobs — the funnel events stay as the audit trail.
- H4 provider interface contract: the provider-agnostic driver every
  sandbox backend implements, reconciling the H3 signup design, the
  suspend/wake and Fly/GPU provider research, and the #47 lifecycle
  audit into one buildable target — six verbs (provision, status,
  suspend, wake-on-dial, ssh_info, destroy; snapshot reserved), a validated box
  lifecycle state machine, per-shape suspend capability flags, a
  billing-facing disk-retention descriptor for idle/stopped boxes, and
  a fail-closed no-public-ingress rule the control plane verifies after
  provisioning. Park-style backends (RunPod's "suspend" is park) are
  representable via the `wake_reprovisions` capability flag and the
  `wake_kind` resume-path surface, and the per-`vm_id` lifecycle is marked
  provisional on H11's isolation-shape answer ([#183](https://github.com/ntindle/spark-vm/pull/183)).
- README "See it in action" gallery: the five demo GIFs (secret-swap proxy,
  approval loop, job runner, desktop persistence, phone credential UI) now
  sit on the repo landing page next to the stack they demonstrate, with
  each frame's provenance and regeneration recipe in the assets notes
  ([#188](https://github.com/ntindle/spark-vm/pull/188))
- README "What's in the box" names the human-approval loop (`confirmd`)
  alongside the proxy/job-runner/desktop/cred-UI stack, and the repo
  layout table now lists `deploy/`, `harness/`, `site/`, `assets/`, and
  the `VERSION`/`CHANGELOG.md`/`CONTRIBUTING.md` process files (#182).
- Lifecycle parity audit for the #47 live-machine-control ticket: #47's
  promised-vs-accepted lifecycle surface checked against the six-provider
  live-control scorecard. Found pause/resume promised in the ticket but
  missing from its acceptance criteria, undefined stream-ownership
  semantics for the live desktop, no idle lifecycle policy model, and an
  undecided stopped-state/file-browsing scope — filed as #177, #178, #179,
  and #180. Also closes the deep-scan's unscored file-browsing and restart
  columns.
- Release and branch protection declared as code (`deploy/rulesets/`): a
  `v*` tag ruleset that makes the release notes' "tags are never moved or
  re-cut" claim platform-enforced (blocks tag update/deletion, with a
  stricter variant that also restricts tag creation to the release
  workflow), plus a `main` branch ruleset (no deletion, no force-pushes,
  PR-required, all CI checks green on an up-to-date branch before merge —
  deliberately no human-approval gate so the improvement loop can keep
  self-merging). An auditable `scripts/apply-rulesets.sh` (dry-run default,
  `--check` drift compare, `--execute --yes` idempotent apply) applies them;
  applying is an owner decision (#174)
- Jail firewall runtime watchdog (closes #254): a 5-minute systemd verify
  timer pins the jail's nftables enforcement rules themselves (drop-rule
  markers + proxy DNAT — the chains are policy accept, so chain shells
  alone prove nothing). On confirmed damage it is fail-closed: the jail
  is stopped first (a table re-apply doesn't flush conntrack, so
  hole-era flows would otherwise survive), then the table is re-applied
  (scoped to the jail table only), and the unit goes red — restart is
  the operator's explicit decision. The old "flushed table silently
  voids the isolation guarantees until someone restarts the unit" hole
  becomes bounded downtime instead of unbounded unenforced running.
  (#260 — entry placed at the end of Unreleased/Added so the branch
  merges cleanly over #263's same-section entry)
- Afternoon competitor watch (2026-09-22): the DigitalOcean Managed
  Agents launch blog added the mechanism detail the morning pass lacked —
  Firecracker microVMs per session, auto-pause defined precisely as "no
  outgoing LLM or tool calls," a 99.3% intent-match claim for Action
  Gateway tool search, a $0.060 vs $0.126 active-CPU worked pricing
  example, live product docs with a prepaid-balance billing model, and a
  self-published benchmark naming Fly.io Sprites as the comparator
  (886 ms create→ready, 189 ms exec RTT, 305 ms resume); the rest of the
  tracked set was quiet. Inputs filed for #47 (benchmark reference
  numbers, edge-routing latency datapoint) and #179 (auto-pause idle
  trigger). (#268)

### Changed
- Hosted pricing thinking refreshed: the internal pricing analysis now
  reflects the decided Fly.io provider (boat.dev under evaluation as a
  cheaper alternative), records Epho's bring-your-own-keys infra-only
  metering as a candidate shape for model-token billing (zero margin risk),
  and drops the stale merge-order note — all cited strategy docs are on
  main and price inputs re-verified through the 2026-09-21 competitor
  reads. (PR #253)

### Fixed
- The inference proxy's host allowlist matcher now recognizes IPv6
  literals: a `::1` entry previously never matched (the address was
  mangled before comparison), so an operator allowlisting the IPv6
  loopback had dead config while the enforcement checks stayed blind to
  it. Literals now compare as normalized addresses (`[::1]`,
  `[::1]:8080`, and trailing-dot spellings included); a hostname entry
  never matches a literal host. (#257)
- Fixed a normalization-order regression in the same matcher (found in
  adversarial review of #264): `example.com.:8080` no longer matched
  `example.com`, which would have let a trailing-dot host:port slip past
  fail-closed deny-name entries. The trailing dot is stripped after the
  port now, on both sides of the shared matcher, and the case is pinned
  in the test corpus so it cannot regress again. (#265)
- Provision-time credential teardown now recognizes every IPv4 spelling of
  loopback (e.g. `127.1`, `127.0.0.2`, `0x7f.0.0.1`, `2130706433`,
  `0177.0.0.1`) as the live echo exemptions they are: these forms match
  exactly at the proxy and resolve to loopback on the machine, but the
  teardown previously saw only the canonical `127.0.0.1`/`localhost`
  spellings, so a binding or allowlist line written in a non-canonical
  spelling would have survived teardown undetected. (#259)
- Provision-time credential teardown now treats leading-dot entries (e.g.
  `.localhost`) as the live loopback exemptions they are: previously only
  bare loopback names were unbound or refused, so a `.localhost` binding
  or allowlist line would have survived teardown while the proxy still
  swapped credentials toward loopback names. The three echo-detection
  checks are now one shared implementation pinned against the proxy's own
  matching semantics by a drift tripwire, instead of three hand-mirrored
  copies that could drift apart unnoticed.
- The provision-time tenant attribution record is now written atomically
  (temp file plus rename): a crash mid-write can no longer leave a
  truncated record for the per-tenant approvals wiring to consume.
- Test hermeticity and coverage hardening (dx turn): the push-endpoint
  tests no longer touch `/home/swapd` (approvals dir redirected at tmp),
  the deploy rollback suite redirects the literal system paths
  (`/etc/sudoers.d/swapd`, the CA bundle, logrotate) at tmp via new
  `components.conf` env overrides so it never touches the host on a
  deployed box, and the CRLF-only refusal case, the live-symlink-target
  removal case, and the dangling-symlink snapshot round-trip are now
  pinned. (#247)
- README repo-layout table: the `harness/` and `site/` rows now describe
  the current tooling — the provision-time injector and the waitlist
  invite operator tools. (#246)
- First-ten-minutes spec conformance audit (gap turn): the new
  conformance-gap doc checks every spec clause against the repo — four
  clauses still unmet (the onboarding status poll with the spec's machine
  vocabulary, the first-approval summons channel, the golden-image
  round-trip gate procedure, the §3a smoke echo endpoint and dummy
  credential) are filed as build items G3–G6; the signup onboarding doc's
  stale "free tier first" plan-picker lines are corrected to the decided
  no-free-tier / card-required-trial-possible position, and the
  operator-only `policy-misfire` / `no-gated-action` note the spec's
  §10 follow-up asked for is in the rendering table. (#245)
- An invite wave interrupted mid-send can no longer strand a waitlist row as
  invited with no email on the way: each invited row commits in a single step
  after its email is queued, so a crash degrades to a duplicate email on
  retry instead of a lost invite (#220).
- Waitlist invite crash recovery is now pinned by fault-injection tests
  (deferred follow-ups from #220): the remaining crash windows — after an
  old invite token is retired but before the row commits (re-invite and
  expiry rollover), and between the commit and the `invite_sent` metric
  event — are exercised against the documented behavior: in the re-invite
  window, recovery mints a fresh token (the stray email's claim link
  validates as consumed at the service layer); in the rollover window the
  retired token stays consumed with no new email; and the metrics never
  claim what the on-disk rows don't show (#236).
- README, ONBOARDING, and the pre-seeded-harness research doc now point at
  the real `cua/bin/cua-desktop.sh` path (the script moved into `cua/bin/`
  and the old `./cua/cua-desktop.sh` reference broke the desktop step of
  the copy-paste install block) (#182).
- The approvals page daemon no longer accumulates unbounded state over its
  lifetime: answered history on disk is now retained to the newest thousand
  entries (tunable), instead of growing one file per approval forever while
  every poll re-read all of them; the per-approval lock entries are likewise
  released when an approval is answered or expires (#196).
- README follow-up polish: "What's in the box" now names the inference
  proxy alongside the egress proxy (the agent's own model API calls
  authenticate with a placeholder too), the layout table's `deploy` row
  drops a redundant word, `harness` links the pre-seeded-harness research
  doc instead of assuming its jargon, and `site` drops the time-stamped
  "Waitlist-era" label. (#201)
- Docs index catches up with the week's new docs: the four 2026-09-21
  competitor watches (evening, afternoon, C17 resolution, morning), the
  secrets-posture repositioning doc, and the Fly-driver and suspend/wake
  research docs are now listed, and the stale "latest" labels in the
  competitor and loop-governance tables are corrected to dated style.
  (#218)

### Security
- The provision-time injector's tenant-identity install and
  tenant-attribution write no longer resolve their destination paths
  twice: both pin the destination directory with no-follow semantics
  and create/write through the open file descriptor, so a symlink (or
  other non-regular file) swapped in between the check and the write is
  refused -- or, for the attribution record, atomically replaced rather
  than followed. The attribution write also reports its digest lifecycle
  (initialized/updated) for the operator log. (#258)
- The unattended deployer's rollback snapshot and restore steps now
  distinguish "this file is absent" from "the privilege check itself
  failed" (broken sudo): a broken check aborts the snapshot and fails
  the restore loudly instead of silently recording live files as absent
  or silently skipping their removal, and a corrupted snapshot manifest
  line with an empty path fails the restore instead of being skipped.
  (#103, #107; #243)
- The with-proxy CA bundle and the jail's swapd-CA install no longer read the
  swapd-controlled CA through symlink-following `cat`/`cp` as root: a new
  `proxy/build_ca_bundle.py` refuses a planted symlink (or FIFO/directory) at
  the CA source and writes the bundle through the existing safe installer
  (root:root 0644) — a swapd-level attacker can no longer get the next
  unattended deploy to leak a root-readable file into the world-readable
  bundle (#144, #207).
- The approvals page daemon no longer lets its expiry sweep collide with an
  in-flight approval answer: the sweep now waits its turn behind the same
  per-approval serialization as the answer path, so an approval expiring
  mid-approval can no longer drop the owner's connection with an unhandled
  error after the grant was already minted, and an expired approval can no
  longer briefly reappear after being swept. The audit trail also gains a
  distinct event when an approval vanishes between grant minting and
  consumption, instead of logging a contradictory expired-plus-approved pair
  (#233). Dead approval files that never reached the answered list are now
  swept into it after a day, so they no longer pile up unseen (#233).
  Missing or unreadable approval files also release their per-approval
  lock entries now, instead of leaking one registry entry per miss (#231).
  (#241)
- The swap proxy's audit log is now bounded: deploy installs a logrotate
  policy covering every `*swap*.log` under the proxy home (including
  `SWAP_LOG_FILE` overrides like the inference proxy's log) —
  size-triggered rotation keeping 12 compressed generations. The log
  previously grew without limit until a full disk failed every swap
  closed (a total outage of credentialed egress). The proxy also guards
  the log's filesystem before each audit write: it warns loudly
  (rate-limited) while space runs low and refuses swaps fail-closed when
  space is critical, so the no-swap-without-a-trail invariant holds even
  if rotation is not installed. Both thresholds are env-tunable (#198, #202).
- The egress proxy no longer swaps a credential anywhere when its registry
  placement is declared but not recognized (e.g. a typo'd placement kind):
  such swaps are now refused with a loud warning instead of silently
  degrading the location restriction into swap-anywhere. Entries with no
  declared placement keep the migration behavior (#197, #200).

## [0.2.0] - 2026-09-20

### Added
- A docs index for the docs tree (`docs/README.md`): the 40-plus doc corpus
  organized by what you're trying to do — start-here contributor picks,
  hosted-product design specs, the product-research corpus, the dated
  competitor corpus, and loop governance, with a keep-this-index-honest rule
  for new docs; the root README's repo-layout table links to it (#171)
- Live-control competitor deep-scan for the #47 control-plane design: six
  providers (AgentComputer, TermSquad, Fly.io Sprites, E2B, Daytona, Docker
  Sandboxes) scored on browser desktop streaming, live terminal,
  suspend/wake, and transport, with where-we-win/lag findings feeding three
  new backlog items — the #47 resume-latency target (C14), the stopped/cold
  cost tier for hosted pricing (C15), and the control-plane-visible lifecycle
  parity audit (C16) (#168)
- Waitlist page build, slice 2: the waitlist service backend — the form
  endpoint (honeypot and timing-trap defenses that accept spam silently,
  per-IP rate limiting, email normalization and dedup), the double-opt-in
  confirm flow (render-only link page, one-click confirm, single-use
  HMAC-signed tokens with 14-day expiry, the 3-per-day email cap), and
  funnel-event logging the metrics script already consumes. The operator
  key and data dir come from environment variables, never the repo. Still
  not deployable: reminder/drop jobs, the email-parsing path, invites,
  and forget-me land next; the page ships only when the full
  waitlist-operations checklist is green (#165)
- Waitlist page build, slice 3a: the waitlist lifecycle jobs — one reminder
  email at +7 days (the last touch; there is no third email) and automatic
  drop of unconfirmed rows at 14 days, run as operator cron jobs with a
  cross-process lock so they never race the live service. The drop deadline
  is fixed at first signup and never postponed by re-signups. Oversized
  requests now close the HTTP connection instead of risking a desynced
  keep-alive. Still not deployable: the email-parsing path, invites, and
  forget-me land next; the page ships only when the full
  waitlist-operations checklist is green (#172)
- Browser-driver first code (H17, [#132](https://github.com/ntindle/spark-vm/issues/132)):
  the fixed `bdrive` action protocol as validated Python — the narrow action
  vocabulary the on-box browser service will accept, with ref-scoped element
  locators, receipt semantics, and hermetic tests. Deferred to later slices:
  the Chromium execution backend, the daemon socket, box hardening, the
  `obox` agent loop, and the card pathway + Web Push (#166)
- Waitlist page build, slice 1: the static front end of the waitlist-era web
  surface — the landing page typeset from the approved launch copy, a
  dedicated `/waitlist` form page with the abuse-resistant signup form
  (owner email, optional agent contact, honeypot and timing defenses, no
  page JavaScript), and a derived social-card image reused from the shipped
  demo asset. **Not deployable yet:** the form's backend (signup endpoint,
  confirm flow, invite jobs) comes next, and the page ships only when the
  full waitlist-operations checklist is green
  ([#163](https://github.com/ntindle/spark-vm/pull/163))
- Build-update template and cadence contract for Spark's daily spark-vm updates
  on musebook.lol: `docs/MUSEBOOK_UPDATES.md` defines the template, the honesty
  rules (no hosted-launch or pricing commitments until the launch is
  executable), and a sample post
  ([#162](https://github.com/ntindle/spark-vm/pull/162))
- Funnel query pack for the waitlist operator: a log-derived, no-cookie,
  no-tracker weekly report (page conversion, CTA click-through by section,
  interim raw vs DMARC-aligned confirm rate with the manufactured-row spray
  signature, reminder lift, invite-to-claim, submit-to-confirm latency) —
  the §7 deliverable of the funnel measurement spec
  ([#141](https://github.com/ntindle/spark-vm/pull/141))
- Changelog ritual: this `CHANGELOG.md` (Keep a Changelog format), the
  per-PR entry requirement in `CONTRIBUTING.md`, and release-time rollover
  in `docs/VERSIONING.md`
  ([#65](https://github.com/ntindle/spark-vm/pull/65))
- Approval pages rebuilt mobile-friendly: the pending list auto-refreshes,
  Approve is a two-tap confirm safe against double-taps, and the answered
  page keeps the 100 most recent ([#20](https://github.com/ntindle/spark-vm/pull/20),
  fixes [#1](https://github.com/ntindle/spark-vm/issues/1))
- Push notifications for approvals: get a push on your phone/desktop when an
  approval is pending; the operator generates one keypair, you subscribe on
  the pending page, and `--test-push` verifies delivery end to end
  ([#48](https://github.com/ntindle/spark-vm/pull/48), closes
  [#2](https://github.com/ntindle/spark-vm/issues/2))
- One version everywhere: every component now reports the same `VERSION` —
  `confirmd` and `cred-ui` at startup and on `/api/version`, `muse-job
  --version` — so an operator can always answer "what's actually deployed?"
  ([#52](https://github.com/ntindle/spark-vm/pull/52))
- Unattended redeploy updater: merged code reaches the live services on its
  own, with the deployed version recorded in the audit log and rollback
  covered ([#29](https://github.com/ntindle/spark-vm/pull/29), fixes
  [#22](https://github.com/ntindle/spark-vm/issues/22))
- `muse-job` hardened against hostile agent output: session-lifecycle trust
  boundary ([#43](https://github.com/ntindle/spark-vm/pull/43)) and
  event-trust hardening ([#19](https://github.com/ntindle/spark-vm/pull/19),
  fixes [#3](https://github.com/ntindle/spark-vm/issues/3))
- Control-panel spec so anyone can build their own computer-control panel,
  with a worked Blender example; the bridge allows the SSH-forwarded tunnel
  endpoint ([`811920b`](https://github.com/ntindle/spark-vm/commit/811920b),
  [`57f24f5`](https://github.com/ntindle/spark-vm/commit/57f24f5),
  [`fc06cbb`](https://github.com/ntindle/spark-vm/commit/fc06cbb))
- Hosted-product design docs: signup/onboarding identity linking with a
  provider-agnostic provisioning interface
  ([#24](https://github.com/ntindle/spark-vm/pull/24)); first-run activation
  funnel ([#37](https://github.com/ntindle/spark-vm/pull/37)); agent-sandbox
  adoption research ([#25](https://github.com/ntindle/spark-vm/pull/25));
  pre-seeded harness research ([#51](https://github.com/ntindle/spark-vm/pull/51));
  beta-Muse first-run pilot protocol ([#32](https://github.com/ntindle/spark-vm/pull/32));
  hosted pricing thinking ([#30](https://github.com/ntindle/spark-vm/pull/30));
  hosted vision-vs-repo gap analysis
  ([#31](https://github.com/ntindle/spark-vm/pull/31))
- Strategy and positioning docs: agent VM/sandbox competitor analysis
  ([#26](https://github.com/ntindle/spark-vm/pull/26)); GPU path research for
  the provider decision ([#40](https://github.com/ntindle/spark-vm/pull/40));
  evening competitor-watch pass ([#44](https://github.com/ntindle/spark-vm/pull/44));
  persistence-as-headline positioning
  ([#28](https://github.com/ntindle/spark-vm/pull/28)); launch announcement
  copy ([#36](https://github.com/ntindle/spark-vm/pull/36)); README
  30-second-scan clarity pass ([#46](https://github.com/ntindle/spark-vm/pull/46))
- Contributor hygiene: `CONTRIBUTING.md`, `SECURITY.md`
  ([#58](https://github.com/ntindle/spark-vm/pull/58)), MIT `LICENSE`
  ([`52960f0`](https://github.com/ntindle/spark-vm/commit/52960f0))
- Fly.io driver research for H4: grounds the provider-agnostic provisioning
  interface and planned contract extensions (suspend/wake, async dial,
  gpu_class routing, destroy-deletes-volumes) against the real Machines API
  ([#140](https://github.com/ntindle/spark-vm/pull/140))
- Documented the quarterly manual re-sweep ritual for the three link hosts
  CI's link checker skips as bot-blocked (medium.com, businesswire.com,
  globenewswire.com) with a verification log — all 11 links (7 unique
  URLs) confirmed live on 2026-09-22 (closes #106) (#249)

### Changed
- Identity cleanup: deployment docs use the `ntindle` login account
  ([#35](https://github.com/ntindle/spark-vm/pull/35)); separately, the
  agent itself is `spark`, and every path in the repo is `$HOME`-relative
  so docs never hardcode a username
  ([`a8fd18d`](https://github.com/ntindle/spark-vm/commit/a8fd18d))
- README rewritten around the bigger-computer idea, with the Spark
  illustration ([`c09a65a`](https://github.com/ntindle/spark-vm/commit/c09a65a),
  [`7e7ffea`](https://github.com/ntindle/spark-vm/commit/7e7ffea))
- `push.sh` / `pull.sh` sync scripts: dry-run mode, preflight checks, and a
  space-safe secret scan ([#33](https://github.com/ntindle/spark-vm/pull/33))

### Fixed
- Root deploy writes stop following symlinks in `/home/swapd`: `cp`/`tee`/
  `chown`/`chmod` on `ssrf.deny`, `grants.json`, and `swap.log` would have let
  a swapd-level attacker plant a symlink at a root-write destination and get
  the next unattended deploy to write/chown through it (same class as #91,
  fixed for the secrets dirs; the grants.json instance is #128). The new
  `proxy/safe_install.py` refuses symlinks fail-closed, creates with
  `O_EXCL`+`O_NOFOLLOW`, and `fchown`s/`fchmod`s the open fd; steps 3/4/4a of
  `proxy/deploy.sh` use it
  ([#143](https://github.com/ntindle/spark-vm/pull/143), fixes
  [#128](https://github.com/ntindle/spark-vm/issues/128)) Also fixes a latent grants.json wipe: the old
  existence check ran as the deploy user, so when `/home/swapd` wasn't
  traversable it always took the create branch and `sudo tee` truncated the
  file on every deploy.
- `confirmd` and its health check no longer pin the box's tailnet IP: the
  `CONFIRM_BIND` literal is gone from `confirm/confirmd.service` (the daemon
  already resolves its bind via `tailscale ip -4` at startup), and the
  updater's health entry is `tcp:TAILNET:8443`, resolved at check time. A
  tailnet rekey/IP change survives a restart instead of wedging the service
  or failing every deploy's health check (rollback of a good deploy)
  ([#143](https://github.com/ntindle/spark-vm/pull/143))
- The updater now warns when it runs stale code: `init` records the checkout
  commit the installed copy came from, and `status`/`check` warn when
  `origin/main` carries newer `deploy/` changes not live because `init`
  wasn't re-run
  ([#143](https://github.com/ntindle/spark-vm/pull/143))
- `muse-job` detects a dead terminal pane and refuses to steer into it
  instead of typing into the void
  ([#45](https://github.com/ntindle/spark-vm/pull/45), fixes
  [#4](https://github.com/ntindle/spark-vm/issues/4))
- Setup no longer teaches a shell-history-leaking secret install: the
  `cred set` examples now use the no-echo prompt (or `read -rs` when the
  no-echo prompt isn't convenient) so typed values never land in shell
  history
  ([#135](https://github.com/ntindle/spark-vm/pull/135), fixes
  [#89](https://github.com/ntindle/spark-vm/issues/89))

### Security
- Proxy hardening round
  ([#18](https://github.com/ntindle/spark-vm/pull/18))
- Fixed critical and high findings from the security code review
  ([`dd382af`](https://github.com/ntindle/spark-vm/commit/dd382af))

[unreleased]: https://github.com/ntindle/spark-vm/compare/v0.2.0...HEAD
