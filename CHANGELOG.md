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
- Night competitor watch (2026-09-22): quiet survey window — no launches,
  acquisitions, pricing changes, releases, or partner moves across the
  tracked set; boat.dev rate card and comparison table re-verified
  unchanged; adjacent color on Meta Muse's Sentinel per-user VM
  architecture (third-party deep dive of the pre-window launch). (PR TBD)
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

### Fixed
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
- The with-proxy CA bundle and the jail's swapd-CA install no longer read the
  swapd-controlled CA through symlink-following `cat`/`cp` as root: a new
  `proxy/build_ca_bundle.py` refuses a planted symlink (or FIFO/directory) at
  the CA source and writes the bundle through the existing safe installer
  (root:root 0644) — a swapd-level attacker can no longer get the next
  unattended deploy to leak a root-readable file into the world-readable
  bundle (#144, #207).
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
