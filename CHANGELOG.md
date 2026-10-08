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
6. **Competitor-watch bullets stay reader-facing too.** Rule 1's "no
   internal audit numbering" covers the competitor corpus identifiers
   (C-numbers): expand them to product, paper, or incident names, so the
   entry reads without access to `docs/COMPETITOR_ANALYSIS.md`. Drop
   loop-internal workflow vocabulary (surveyor lanes, fetch streaks,
   dedupe counts, aging-pipeline bookkeeping). A quiet pass stays one
   compact paragraph: the watch date, the re-verified-unchanged vendor
   baselines, any corpus movement (filings, aging), and items flagged but
   not filed. The verified no-change record is the value; the process that
   produced it is not.

(This section was removed by PR #586's bullet scrub (2026-09-27) without
disclosure, and is restored here; the scrub's reader-facing standard is
codified as rule 6 so future watch bullets arrive compliant.)

## [Unreleased]

### Fixed

- Release-notes body cap: the oversized-notes failure diagnostic now gives a copy-paste recovery that marks prereleases as prerelease and recreates the release tag at the release commit (it previously assumed the tag already existed, which is only true for `--publish-only`); the trim report counts dangling subsection headers separately from dropped lines; the trim note renders as its own paragraph; and the no-curated-section path is pinned to die loudly rather than emit a trim note pointing at a changelog section that doesn't exist. (#1181)

- The golden-image build gate (the baked-secrets scan + manifest preflight that must run on every release) had never actually run on a release tag: the release workflow pushes the tag with `GITHUB_TOKEN`, which cannot trigger workflow runs, so the gate's tag trigger was dead. The release workflow now calls the gate as a reusable workflow in the same run, building the exact release tree. (#1177)

- The approvals page's pending directory is now created setgid by the deploy itself: `proxy/deploy.sh` provisions the dedicated `approval-filers` group, enrolls the filing principals, and enforces the directory as group-setgid on every deploy — so the "file owner identifies the requester" guarantee no longer depends on a manual operator step that nothing in the repo performed. (#1167)
- The approvals page now reads the tailnet owner's identity from the documented field of the `tailscale whois` response instead of the first login-name-shaped value anywhere in it — a schema change on the whois side could otherwise have flipped the owner check and locked out (or mis-identified) the approver. (#1166) (#1169)
- The approvals daemon's corruption-quarantine directory is now bounded like every other approval store: the newest 200 quarantined filings are kept and the oldest are pruned on the housekeeping cadence, instead of growing without limit. (#1168) (#1169)

### Changed

- Competitor watch, 2026-10-08 morning: no new entries this pass. New dated content: the Daytona changelog tops at V0.223.0 (Oct 7, 2026 — mouse and keyboard hold endpoints in all SDKs), and the Vercel changelog index carries a new Oct-7 dated section (five entries — microfrontends routing free for firewall-mitigated traffic, OpenAI Decisions API / Claude Haiku 5.5 / Glyph Cluster on AI Gateway, timestamp attributes in Vercel Flags). The Vercel changelog sitemap moved 1390→1397, fully explained by seven visible dated entries. Everything else re-verified unchanged: Modal's egress billing still reads verbatim with the first bill postured for November 1; AgentComputer still publishes no egress pricing (65th consecutive check); Vercel Drives remains in public beta with no GA language; Hugo's advisory page carries no entry for CVE-2026-100690. One read failed to render — Docker's sandbox release-notes page returned the repo overview instead of the release blocks, so it re-verifies next cycle. Flagged but not filed: the Modal $750M and Baseten ~$26B funding rounds are both still unclosed; the Vercel KVM zero-day still has no CVE, technical write-up, or patch; a first third-party report says NanoClaw agents run in MicroVM-based Docker Sandboxes (needs first-party confirmation); Docker's sandbox kit specification moving to the CNCF is a pre-window announcement; Docker's $250 agent challenge is marketing color; Perplexity's sandbox-escape research Part II is still unsighted; Cloudflare's "Environments for Claude Managed Agents" is now dated May 19, 2026. (#1170)

- CI Python test gate rebalanced: the real-worker harness suite (the slowest slice of the run — about seventy percent of its shard's wall time) now runs in its own shard, so a code PR's test signal arrives in roughly four minutes instead of six; the required `python tests` check keeps its name and still gates the merge, and rebalancing never touches the required status checks. (#1164)

### Added

- Credential-vend S3/S4 design-ahead: the vision-vs-state pin for the plane vend endpoint (#890) and box-side fetch path (#891) builds — what moved since the 2026-10-03 contract (box-token rotation with its grace class, the box-authenticated endpoint pattern, the D1 schema discipline, the plane as a durable-command producer, the open tenant-model and audit-retention decisions) — with the two genuinely-new gaps filed (vend-table tenant attribution + audit retention (#1178), the `credential_kill` fast-revocation command kind (#1179)). (#850) (#1180)

- On boxes enrolled with the hosted control plane, the box-local push queue now stands down: the local channel could never page there (a hosted tenant owner never reaches the confirmd page, so no notification subscription can exist) — refused approvals no longer pile up in an ever-growing local journal, and the hourly "push disabled" warnings stop. The approval still reaches the plane via the filing path, so it shows on the dashboard; plane-side push paging itself arrives with the plane push lane (#967/#968). Self-hosted and unenrolled boxes keep the box-local queue exactly as before. The local queue journal is also capped (newest 1000 entries kept) so a keyless box that never enrolls can't accumulate entries forever. (#1135) (#1173)
- Status-page design: the status page itself, staged — the operator page first (firing and acknowledged-but-unresolved alerts, rollout and freeze rows, a history window, a freshness stamp on every render; ack stays in the operator CLI), then the tenant-scoped history on the tenant read path (curated summaries instead of raw journal text, box-id surrogates, the signed feed preferred when it exists) — plus the incident-comms answer: a free-tier RSS/Atom feed carries incidents for everyone, the operator page carries them for operators, a tenant push variant follows the push lane's tenant gate, and user-configured webhooks cover the rest instead of email. Every channel inherits the no-fiction rule: incident copy never outruns the journal, and silence is rendered as missing evidence, never health. (#1165)

- Plane-side tenant-identity gap analysis: the hosted vision speaks "tenant" (signup identity linking, tenant records, tenant-scoped signed API calls) while the shipped plane speaks "owner" (single-owner appliance, one-shot bootstrap, box-filed approval records with no owner attribution) — the analysis numbers the gaps (tenant record, tenant-Muse credential, the multi-tenant plane model decision, approval-record attribution, the tenant-status plane auth, tenant-record retention/erasure) and files them as build issues so no second tenant lands before the identity and attribution layer is decided. Also corrects the stale "design; not implemented" status on the tenant-status endpoint doc now that the engine slice has shipped. (#1163) (#1158) (#1159) (#1160) (#1161) (#1162)

- S4b socket-lifecycle gap analysis re-pinned to 2026-10-08: records the box-side heal of the socket gap-hold wedge (shipped as #1154, already in 0.7.0) and confirms the remaining open builds — the socket-ack consume half (#1001), ping/alarm re-verify (#1002), and live acceptance (#960). (#1183)

## [0.7.0] - 2026-10-08

### Added

- S4b remaining-builds gap analysis: what moved since the S4b socket-lifecycle analysis — the box-side sequence-gap guard now interacts with the re-drive's malformed-row skip, so a skipped malformed row reads as a permanent sequence gap and the socket holds every later command frame for the session's whole remaining life (the durable queue keeps flowing through the every-minute cron backstop, but the fast path degrades to a dead session). The analysis validates the finding against the shipped code, rejects the booked-frame fix (a skipped row never produces a frame, so there is nothing to book), defers wire tombstones, and pins the build design: the gap guard consults the cron ingest's shared cursor and fast-forwards the session prefix when the cursor has advanced past the gap on the same epoch — bounding the hold to about one cron tick, self-healing without reconnect. The build is scoped and test-pinned on the issue; the wire doc's "carriers aligned" claim gets its bounded-degradation caveat in the same change. (#1148)

- Push sender loop: the control plane now drains the push outbox — every queued page (approval filings, reminders, token-expiry warnings, box revocations, stale-heartbeat alerts, hourly digests) is claimed in order, re-checked against the live approval record at send time (a decided or deleted approval never pages), fanned out to the owner's live devices only, and retried with backoff — six attempts before the page dead-letters operator-visible, with approval pages re-paged by the reminder machinery. The exactly-one-instance guarantee is pinned to the Durable-Object-singleton design; until that build lands, sender ticks must not overlap (overlapping ticks double-send and double-spend the page budget) — the claiming build stays open on the issue. (#1094) (#1102)
- Spec pin: the wire-protocol contract for delivering durable commands over the phone-home WebSocket is now pinned (#1001 slice 2a) — on (re)bind and after each enqueue the plane re-drives unacknowledged commands from the last acked position, stamping delivery leases exactly like the HTTPS fetch path, skipping malformed rows loudly (the pinned skip-and-log policy) rather than emitting them, with a single acked watermark shared by both paths (no second cursor). Spec only, nothing ships in this change: the emit-half code is in-flight and the socket ack consume-half (slice 2b) is still open, so the acked watermark still advances only via HTTPS acks. (#1001) (#1141)
- Pinning the golden image now cross-checks the digest the pin names against the digest the publish step recorded on the gate record: a pasted or mistyped image reference that names a different digest than the gated, pushed image is refused (both digests named in the error) instead of silently pinning the wrong image, and a record the publish step never stamped is refused with the re-stamp command. The pin-side `--force` never bypasses the check — the re-push path re-stamps the gate record first, then pins the digest the record names. (#1134)
- Per-tenant approval routing gap analysis: #69's 2026-09-19 box-local diagnosis re-examined against the shipped phone-approvals lane — the plane side already routes per (owner, box) and #280's per-tenant box makes box-local single-tenancy a construction property, while two genuinely-new gaps surface: the box-local push path has no hosted-mode handoff (it enqueues and runs on hosted boxes where the plane is the designed paging path, with loud skips and an unbounded queue journal), and owners with multiple boxes have no aggregated pending view (#69). (#1137)
- Docs-only pull requests no longer wait on the full test suite: the CI workflow now detects whether a PR touches anything outside `docs/` and the changelog, and skips the ~40-minute Python suite when it doesn't — shellcheck, link check, changelog lint, docs-index coverage, and the PNG smoke test still gate every docs-only change. (#1126)
- Golden-image publish step records the push-produced digest: after the operator pushes the gated image, `build-image.sh --record-pushed-digest` resolves the digest from the registry through the local docker daemon (RepoDigests — never pasted from push output by hand) and stamps it into the gate record's `build.image_digest` — write-once, idempotent, refusing skeletons, refused gates, and records naming another build — so a later pin step can cross-check the digest it pins instead of taking the operator's word for it (#1111). (#1123)
- Image-digest pin-side design pin: a gap analysis records exactly what the golden-image pin step must enforce before it can stop taking the operator's word for the image digest — the pin must refuse unless the digest in the image reference matches the push-produced digest the publish step recorded in the gate record, with a clear remediation when no digest was recorded and no bypass for forced re-pins (#1111). (#1125)
- Claim-binding idempotency for box provisioning: the provider interface's provision request now carries the signup claim and attempt number as a required idempotency key, drivers retrying the same attempt get back the already-created box instead of provisioning a second one, and a new box-listing call exposes each box's key so the orchestrator's startup check can match already-provisioned machines against pending claims — no more double-provisioned boxes when the orchestrator restarts mid-provision (#1107). (#1120)
- Orchestrator/attested-pairing gap-analysis refresh: the §2 "golden-image producer is closing" bullet and the §5 "(#1087, closing)" line in `docs/ORCHESTRATOR_ATTESTED_PAIRING_GAP_ANALYSIS.md` were pinned to main `2a4669c` while PR #1106 was still open — a dated 2026-10-07 refresh section now records F-P1/#1087 as closed (pin recorder `harness/pin_image.py` on main via #1106) and re-verifies §2's other claims against current main with no drift. (#1114) (#1115)
- S4b socket-lifecycle gap-analysis status refresh: `docs/S4B_SOCKET_LIFECYCLE_GAP_ANALYSIS.md` was pinned to main `4487c13` (2026-10-04) and still listed the journal sink and hello/identity/generation fence as "Nothing" — both have since shipped (#999's `phone_home_events` D1 sink + owner read path + retention, #1000's deployed hello handshake/identity binding/generation fence), so the §2 current-state table, the F-S4b-1 finding, the §5 slice headers, and the §7 stay-open line now carry the shipped status; the §2 re-drive and ping/pong rows record the partially-landed state too (the S4b-2a re-drive emit half and the wire-spec-§4 pong answer are live in the deployed worker checkout via in-flight #1001 work — the socket ack consume-half and the alarm-wake/re-verify remain open under #1001/#1002). (#1140)
- Golden-image publish pin (second slice): `harness/pin_image.py` records the digest-pinned image ref (`deploy/golden-image/pinned-image.json`) after the gate passes and the operator pushes — the missing link between the image-build pipeline and the Fly driver, which consumes exactly this record as its operator-set image pin. The pin tool refuses anything but a completed gate pass for the exact baked SHA, anything but the `registry.fly.io` host the driver contract names, and anything but a digest-pinned ref (a bare tag is never launchable); the reader raises on a missing or invalid record so the driver cannot provision from an unpinned image (#1087). (#1106)
- Golden-image build pipeline (first slice): the provisioned box's image finally has a producer — a pinned Dockerfile recipe, a build driver that refuses dirty trees and bakes the exact commit + release tag into the image manifest (rebuilds pin forward, never silently), a supervisord daemon set mirroring the systemd units (no systemd on Fly Machines), and a CI job that builds the recipe on every release tag and runs the baked-secrets scan plus the manifest preflight before anything publishes (#1087). (#1100)
- Secrets-posture docs: the response-scrubbing section now documents the Set-Cookie round-trip break — the scrubber rewrites secrets in every response header except content-length/transfer-encoding, including `Set-Cookie`, so a session cookie echoed from a secret comes back as the placeholder and the cookie branch refuses to re-swap it; fail-closed, with the `set-cookie-no-cookie-swap` audit note, and the Cookie-placement fix (#837).
- Release-gate key rotation reminders: the gate publisher now keeps a controller-side ledger of signing-key rotations and reports open windows on every publish — loudly once a window ages past the stale threshold (14 days, tunable) — naming the un-retired key and the runbook step that closes it; operators close the window with `--rotation-complete` after retiring the old key, so an unfinished rotation can no longer degrade silently into a permanent second signing key (#1008).
- Competitor watch, 2026-10-06 morning: Amazon's own news blog confirms the Bedrock Managed Agents launch as a public preview (the launch posture is now first-party verified); the watch also records Daytona's V0.222.0 release and Microsandbox's v0.7.7 release as watch deltas, and closes the Cloudflare cross-tenant patch note as a restatement of the remediated September incident while flagging a third-party Vercel KVM zero-day report as watch-only (#1093).
- Provisioning + metering convergence analysis: the metered, capped, provisioned box vs the hosted vision, pinned to v0.6.0 — files three genuinely-new gaps (the golden image has a gate but no build pipeline; the meter envelope has a producer and a plane endpoint but no emission worker; the pairing attestation token needs a plane-readable provision record, pinning the record store to D1) and pins the lane build order (#1090).
- Orchestrator + attested-pairing gap analysis: the claim→provision→attested-pair leg (#906/#907) vs the hosted vision, pinned to current main — files four genuinely-new gaps (claim-binding idempotency for the double-provision window; the attestation token's wire contract; the provision record's lifecycle past pairing; the orchestrator's placement and writer credential) and pins the idempotency, token-consumption, lifecycle, and record-creation decisions (#1114).
- CI Python test gate sharded: the ~40-minute serial suite now runs as three parallel shards (slow integration suites isolated from the fast unit suites), so a code PR's test signal arrives in the slowest shard's time instead of the full serial run. The required `python tests` check keeps its name and still gates the merge — it goes green only when the shard plan and every shard pass (docs-only diffs skip the suite as before) — and the shard inventory is pinned by a test plus a CI-side inventory check, so a new suite can never land unwired from CI (#1138) (#1149).

- CI guide updated for the #1138 shard split: docs-only PRs skip the sharded suite, and code PRs get their Python test signal in roughly six minutes instead of ~40. (#1150)

### Fixed

- The phone-home socket carrier no longer wedges when the plane's re-drive skips a malformed command row: the sequence-gap guard now fast-forwards the session's delivery position to the shared ingest cursor the every-minute cron advanced past the skipped row (same epoch only, loud log), so a skipped row degrades the fast path to fetch-path latency for about one cron tick instead of holding every later command frame until reconnect. Lock contention or an unreadable cursor keeps the hold — the guard degrades, never wedges — and a true missing row still holds for the re-drive. (#1143) (#1154)
- Typing and key presses through the desktop bridge now refuse loudly instead of delivering keystrokes to the wrong window when focus is stolen mid-request: the bridge re-checks that the intended window still holds input focus after bringing it forward (one re-focus retry), narrowing the theft window to the driver's own internal activate-and-inject race — if the desktop can't report focus at all, it logs loudly and types as before. The keyboard-path liveness probe applies the same check, reporting an inconclusive probe instead of a false wedge when focus is stolen mid-probe. (#494) (#1151)
- The waitlist forget flow's spool purge now normalizes the address before matching: a differently-cased or plus-tagged address variant no longer silently misses the pending spool docs for the forgotten address — previously it would have purged nothing, leaving the forgotten address mailable through a stale spool entry. (#1145) (#1152)
- The CI doc's local test instructions no longer drift from the real suite inventory: the "replicate the CI jobs locally" block now leads with the repo-root one-liner the `python-tests` job actually runs instead of a per-directory subset that covered only 7 of 14 suites, the "adding a new test suite" guidance now points at `pytest.ini`'s `testpaths` instead of a per-step CI model that no longer exists, and a new pin test fails the suite if the doc ever re-enumerates a directory subset or resurrects the stale instruction. (#1139)
- Watch auto-recovery no longer risks resurrecting a second concurrent phase job: resume now re-checks the one-phase-job-at-a-time rule immediately before creating the replacement session, deferring to a later watch pass when a sibling went live in between — manual resume stays a deliberate bypass by design. (#1131)
- The box-side phone-home socket carrier now handles malformed command frames the way the cron path handles malformed rows: a malformed frame is skipped loudly — never executed, never acked, never holding the session's delivery position — and the code, the docstrings, and the wire-protocol spec now agree on the one policy, closing the last open #1118 divergence. Residual (#1143): when the plane's re-drive skips a malformed *row*, the box sees it as a sequence gap, and the session's ordering guard still holds later live frames waiting on a re-drive that never comes — delivery degrades to the cron path until the session reconnects or the plane repairs the row. (#1118) (#1144)
- The durable command queue's malformed-row policy is now pinned as D-MAL1 (skip-and-log): a plane data bug can never wedge the queue on the cron path — revocations and decisions keep flowing. The wire-protocol spec records the decision and the code's docstrings now match the code. (#1128)
- The golden-image pin step now refuses a pin file holding valid-but-non-object JSON (e.g. a list) with a clear operator-facing error instead of an AttributeError traceback — nothing is written over the bad file, so the operator can fix or remove it by hand before pinning. (#1112) (#1144)
- The phone-home socket path now adopts the plane's epoch: after a successful socket-side ingest under the ingest lock, the box adopts the frame's epoch last-writer-wins and persists it with a monotonic cursor advance via `commands_cursor.json` — the same #947 contract the HTTPS path honors — so the next cron fetch asserts a truthful `?epoch=` and does not re-fetch socket-acked seqs. The ack envelope still echoes the frame's epoch verbatim, and the ack send stays outside the lock; a transport-lost ack redelivers and dedupes through the consumed/ backstops. The idempotency-log save moved inside the same lock hold, closing the read-modify-write race with the cron tick that could clobber the socket path's entries (#1116, #1117).
- The auto-deploy end-to-end test now derives the cred-ui runtime file set from the install suite's single source of truth instead of a hard-coded third copy, so adding or removing a runtime file can no longer silently desync the two suites. (#1113)
- Push sweep no longer wedges on one bad record: a corrupt notification record, a broken owner lookup, or a bad digest window is now logged loudly — naming the bad record — and skipped while the rest of the sweep continues, so one bad record can't starve every other reminder or digest. The bad record is retried on the next sweep — still loud every time, never silently dropped — and an interrupted sweep (Ctrl-C) still stops immediately (#1095). (#1104)
- Push digest bookkeeping: a crash between the digest page's enqueue and its bookkeeping stamp no longer strands the window in a phantom-pending state — the next sweep's refire now heals the stamp when the digest page row exists, instead of refiring uselessly on every tick until retention cleanup; a duplicate with no page row (the dedup race path) still leaves the stamp unset so a later sweep retries (#1096).
- Box failure logs are now bounded: the shared loud-failure helper caps each log (heartbeat, ingest, upload-filings, phone-home) at 1 MiB with single-generation rotation — the overflowing log moves to `<log>.1` and the new line starts a fresh log, so a sustained plane outage or 401 loop can no longer grow logs forever; a wedged `.1` degrades loudly on stderr without losing the new line, and token redaction holds across rotations (#1020).
- Stop hook classifier: a quoted or example `BLOCKED:`/`DONE:` (prompt-preamble literals, fenced code blocks, blockquoted quotes) no longer flips the job's state — only the protocol's final line carries the marker, so a quoted `DONE:` can't silently close a live job (#8).
- Control-plane API reference: the phone-home WebSocket lane is now covered — the box→plane upgrade handshake, the session and close-code taxonomy, and the owner-only journal read + retention endpoints — closing the gap since the plane DO deployed live in October (#1092).
- GitHub releases: release notes are now capped at GitHub's 125,000-character body limit — an oversized curated section is trimmed at whole-bullet boundaries with a note pointing at the full changelog on the tag, instead of failing the publish step (and its recovery) with a body-too-long error, as the v0.6.0 cut did (#1091).
- The waitlist forget flow's plus-tagged-variant matcher now case-folds the address itself before building the variant pattern: a mixed-case address previously produced a silently dead variant pattern, so plus-tagged variants of that address would have survived the triage and quarantine-sidecar scrubs — the two surfaces that consume the matcher — instead of being erased; the current flow always passes the already-normalized address, so nothing changes behaviorally today. (#1146)
- Golden-image runbook correction: the publish/pin guide said the pin "does not yet cross-check" the image digest against the gate record — that check has shipped, and the guide now documents the real control: the pin refuses any digest but the push-produced one the publish step recorded on the gate record (an unstamped record refuses with the re-stamp command; a mismatch names both digests), and a forced re-pin still requires the record to be re-stamped first — so a pasted or mistyped digest cannot pin an image the gate did not publish. (#1124) (#1147)

- The job manager's per-job record no longer lives inside the job's working directory: `muse-job` now keeps the record in a manager-side metadata store outside the agent-visible tree, so a job's agent no longer has a preamble-visible writable path to the management metadata (session id, worktree paths, state) the operator's commands act on. Existing records migrate to the new location on first manager read; the derived-layout pins and read-side sanitizers stay as defense in depth. (#11) (#1152)

### Security

- Push-sender claim design: overlapping per-minute sender ticks can no longer double-send pages — the sender loop's exactly-one-instance guarantee is now pinned to a single Durable Object per worker whose drain runs to completion before the next tick starts, so queued ticks wait their turn instead of interleaving mid-send; the design also pins bounded work per drain, the accepted crash posture (a retried page may buzz twice, never go missing), no public route to the sender, and the singleton's exact scope. (#1094) (#1121)
- Claim-binding idempotency key is canonical-typed on both sides of the metadata boundary: `ProvisionSpec` now rejects a non-`int` `attempt_n` (`True`, `1.0`, `"2"`) and a blank/padded/non-string `tenant_id`/`claim_id` at construction, and `BoxIdentity` enforces the same canonical shape on the reconstituted record — a driver read path that forgets to `int()`-parse `attempt_n` fails loud at list time instead of defeating dedupe silently — so a retry can never silently split the key space, defeat dedupe, and double-provision (double spend) (#1107). (#1122)
- Pristine repo clones are now namespaced by upstream: spawning jobs against same-named repos on different orgs — or different hosts — no longer shares one clone directory, so the second spawn can't silently fetch the wrong repository's code into the first clone and cut job worktrees from the wrong base — clones live under `~/repos/<host>/<path...>` (local paths under `~/repos/_local/`); pre-existing flat clones keep working for recorded jobs, new spawns re-clone into the namespaced dir (#10). (#1105)
- The job manager's redacted turn-event journal no longer lives inside the job's working directory: `muse-job` now keeps the journal in a manager-side journals store outside the agent-visible tree, so a job's agent no longer has a preamble-visible writable path to the turn history the operator's log view and the stillborn diagnosis read from. Existing journals migrate to the new location on the first manager write; journals that predate the move stay readable. (#1130) (#1156)


## [0.6.0] - 2026-10-06

### Added

- Push-sender schema contract amendments (#1061): the enqueue boundary's
  `queued` outbox outcome is documented alongside `suppressed_budget` /
  `suppressed_terminal` — its lifecycle (inserted by the enqueue call,
  selected by the sender loop, deleted on the terminal attempt) and its
  hold on the page-budget reservation — and the page-once partial unique
  index lands as an operator-run migration statement (the exact
  statement the enqueue build shipped), so the contract stays the
  operator's DDL source of truth. (#1079)
- Spend-cap enforcement gap analysis (#908): a vision-vs-state writeup of
  the hosted product's spend-cap lane — the missing spend ledger,
  pre-provision cap check, and destroy-on-budget-exceed worker — pinning
  the two-sided cap model (operator-side margin protection vs the
  tenant-facing buyer story), the standing destroy-on-exceed decision,
  the required pre-destroy notice and grace window, and the
  source-of-truth gate the cap check must clear before it ships; filed
  as four build slices. (#1078)
- Fleet audit-tail continuity (#1006): when a box's pulled audit tail
  no longer contains the previous pull's tail head — lines scrolled out
  of the tail between pulls and may never have reached the collector —
  the collector now pages a `tail-discontinuity` alert (one per distinct
  lost window, through the alert journal and `events watch`) alongside
  the stderr warning, and the fleet README names a tail-length sizing
  rule so operators size the tail instead of discovering overflow via
  the warning. (#1072)
- Push reminder/digest scheduler (#1063): the sweep logic the control
  plane's per-minute trigger will drive — a due reminder pages exactly
  once, a decided or expired approval is never paged (terminal-by-clock
  selections write one idempotent audit row for the operator), and
  digest triggers fire in the same sweep as the reminder that tipped
  the budget. The cron-trigger registration on the plane (D72) ships
  as its own tracked item (#1069).
- Hosted phone-home session handshake (#1000): the plane's per-box
  connection now completes the hello/welcome handshake and enforces the
  generation fence — the box's hello identity must match the token the
  upgrade carried (mismatch closes the socket and is journaled), a hello
  with a stale generation gets a close carrying the current fence value
  so the box can adopt it and reconnect, a newer generation cleanly
  supersedes the old socket, and every later frame is fenced before
  anything else sees it (stale frames are dropped and journaled).
  Deployed live; verified end-to-end against the deployed plane
  2026-10-05 ~15:2x CDT (12/12 live checks: hello → welcome with
  `accepted_generation`, newer-generation supersede binding the new
  socket with `close`/`superseded-generation` on the old one,
  stale-generation close carrying `last_generation`, connect rows in D1;
  test box + journal rows deleted afterwards).
  (#1055)

- Push sweep scheduler design (#1063): the first build slice of the
  reminder/digest scheduler home — a per-minute scheduled run on the
  control plane that scans for due approval reminders and hourly digest
  triggers, with paged scans, no scheduler-side budget guessing (the
  enqueue boundary stays the single gate), and a retirement rule so the
  later Durable-Object alarms can't double-page. Design only; no
  scheduler runs yet. (#1067)

- Push-sender schema contract (#988): the D1 store the hosted Web Push
  sender builds against — subscription table, page-budget counters,
  send-result and acceptance records (the record the first-approval
  email fallback's retirement criterion reads), and digest state — plus
  the custody rules (subscription secrets encrypted at rest, never
  readable back through the API, no claim of operator blindness) and
  the VAPID key lifecycle. Design contract only; nothing sends a push
  yet. (#1059)

- Push enqueue boundary (#1060): the trust boundary between a hostile box's filing storm and the owner's phone — plane-observed events now enqueue through a single gate that enforces page-once-per-event dedup, atomically reserves the per-(box, hour) and per-(owner, hour) page budgets in one step (two racing filings cannot both pass a bound of one), and coalesces over-budget pages into the hourly digest instead of sending them. (#990)

- Push event mapping (#1062): the hosted push lane's paging policy — each
  plane-observed event (approval filed, token-expiry warning, box revoked,
  heartbeat-stale) now maps to exactly one enqueue decision: reminders
  fire once per approval at half its TTL (never for short-lived
  approvals), a decided or expired approval never gets a post-decision
  reminder, and a flapping box cannot re-page within four hours of its
  last alert. (#969)

- Box-side ensemble operator checklist (#1021): the pairing client
  README gains a single operator surface for the five box-side processes
  (hourly token rotation, per-minute heartbeat, per-minute command ingest,
  per-minute filing upload, and the phone-home daemon) — an inventory of
  what each process owns, the install checklist, how to verify a healthy
  box, what to alert on (and what to ignore), and how to reconcile boxes
  still running the old systemd unit. Reaffirms the wire spec's rule that
  the heartbeat is the only liveness signal — a connected socket never
  makes a box look alive. (#1054)

- Metering & billing gap analysis (#1047, #1048): vision-vs-state of
  the usage-metering-to-billing lane — the five meters, the canonical
  envelope, the emission path, and the spend-cap sequencing all exist as
  design, with zero implementation anywhere (no meter agent, no emission
  queue, no plane ingestion, no spend ledger). Pins five decisions (no
  billing on cooperative telemetry; metering stays both-supported;
  meters-before-*fine-grained*-caps, with coarse enforcement on provision
  records unblocked; the fleet journal is a meter-daemon *source*, not a
  competing emission path; `mac` reserved with `(source, epoch, seq)`
  dedupe as the integrity story) and files the two build slices: the
  box-local meter agent and plane-side metering ingestion with billing
  aggregates. Plane state is pinned to a read of the external
  control-plane worker (the Worker lives outside this repo), not to a
  repo commit. (#1050)

- Approvals-plane gap analysis refreshed (#1038): the four control-plane
  gaps filed in October for the hosted phone-approval flow are now
  recorded as shipped — the plane-side approval record (#872), the
  approval-decision channel kind (#873), and box-side decision ingest
  (#874) all landed, and the box→plane filing upload (#876) is built
  through the box uploader, the dashboard decide surface, and in-repo
  acceptance; only live-plane acceptance stays open. This is a
  documentation catch-up — no product behavior changed.

- Hosted terminal-stream wire protocol (#919): the contract for live
  terminal output from a box through its phone-home connection — lossy
  ordered output chunks, a dedicated input channel that carries both
  owner-typed input and approval-authorized input (approval stays the
  consent step; the bytes ride the input channel), replay protection so
  a stale connection can never inject bytes into a live session, and an
  audit rule that attributes every open, close, and input without ever
  recording terminal contents. The box-side producer (#920) and the
  dashboard viewer (#1035) build against it.
  (#1036)

- Fleet release-gate hook loop (G18 S1b, #777): every gated box now
  refreshes its own release-gate answer every 60–120 seconds via a
  systemd timer and keeps the latest answer in a local status file, so a
  frozen or gate-stale fleet shows up as visible degraded operation
  instead of silent drift. The update tick's own gate check remains the
  enforcement point; the hook only keeps the answer fresh and observable.
  (#1034)

- Fleet estate read API (G21 S1, #795): the operator's fleet store is now
  queryable over HTTP — `fleet api --store DIR --port 18760` serves a
  read-only JSON projection of the estate (fleet version table, per-box
  history, drift, update events, alerts, claim-vs-inventory crosscheck,
  and a reserved waves shape that names its own unavailability until wave
  assignments land). Every endpoint is field-equivalent to its `fleet` CLI
  counterpart with a per-endpoint conformance test to prove it; the API
  binds 127.0.0.1 only with no auth in this slice — the operator's own box
  is the trust boundary, same as the CLI.

- Hosted phone-home journal retention (#1013): the plane's per-box
  journal and the unattributed upgrade-probe counter now expire on a
  schedule — journal rows older than 90 days and probe-counter day
  buckets older than 7 days are deleted by a daily automatic cleanup
  (03:17 UTC), and owners can trigger the same cleanup on demand with a new
  owner-only API endpoint (`POST /v1/ops/phone_home/gc` — a box can never
  trigger the cleanup of its own journal). Cleanup runs are visible in the plane Worker's logs.

- Hosted box-side process-shape gap analysis (#847/#849): a vision-vs-state
  inventory of the five box-side processes (the four cron one-shots —
  token rotation, heartbeat, command ingest, filing upload — plus the
  supervised phone-home daemon) against the never-pinned "boxd" decision
  from the phone-home design. Eight findings, seven pinned decisions (the
  mixed cron+daemon shape is the steady state, no boxd convergence; the
  epoch bump joins the ingest-lock discipline; in-code log bounding;
  one operator checklist; payload updates deferred to the provisioning
  orchestrator), and four tracked build slices (#1019–#1022).
  (#1023)

- Hosted phone-home journal sink (S4b-4, #999): the plane's durable
  per-box journal is in place — connect and revocation/expiry closes are
  journaled today (no payloads or credentials), and owners can read a
  box's journal plus the unattributed upgrade-probe counter from a new
  owner-only API endpoint — a box can never read its own journal. The
  remaining emission sites (disconnect, hibernate wake, generation fence,
  identity conflicts) land in S4b-1–3.

- Documented the stillborn-spawn guard in the muse-job README (#994): every
  MSP spawn (the default transport) now verifies the first agent turn
  actually engages within 10 seconds instead of trusting the session start
  — a dead first turn marks the job blocked, never active, keeps the turn
  id, failure reason, and an event journal in the job record for diagnosis,
  and the watchdog refuses to resurrect it. (#1025)

- Hosted phone-home, S4b socket lifecycle decomposed into four buildable
  slices (#958): the plane Durable Object's remaining session logic —
  hello/identity binding plus the generation fence, command re-drive with
  the socket ack consume-half, ping/alarm revocation re-verify with
  hibernation, and the DO journal sink — is now four tracked slices,
  each sized for one build slot with harness-first acceptance criteria. Five
  structural pins landed with the analysis: the DO re-derives the handshake
  identity from the upgrade token (never trusts a carried identity); new
  enqueues wake the DO via an internal RPC, never a poll timer; the socket
  ack path shares one idempotent update with the HTTPS ack endpoint so the
  two cannot drift; the journal sink is a new D1 table (the wire spec's
  "fleet event journal" named a sink that doesn't exist on the plane); and
  the hibernation-API verification is the ping/alarm slice's entry ticket,
  not a deferrable.

- Hosted phone-approval push, send path built (#989): the send-path half
  of the push sender is built — a stdlib-only transport that POSTs the
  encrypted page to the push service with per-send VAPID credentials,
  honors `Retry-After`, never follows redirects, classifies every outcome
  (accepted / retry / dead subscription / dead-letter) so the plane can
  re-queue, tombstone, or alert, and records accepted deliveries for the
  email-fallback retirement check. End-to-end delivery waits on the
  enqueue boundary. Still ahead: the subscription database contract, the
  enqueue boundary, and the dashboard subscription surface.

- Hosted phone-approval push, sender design split into buildable slices (#991): the remaining sender work is now three tracked issues — the subscription/budget/send-record database contract, the push-service transport (request shape, retries, per-code handling), and the enqueue boundary (where filing becomes a page, and the backpressure story). Three structural pins landed with it: the anti-spam page budget counts pages, not device deliveries (one page to all your devices is one unit); every send re-checks whether the approval was already decided or expired, so a decided approval never pages; and a page fans out to every live subscription registered for that owner and box.

- muse-job v2 (MSP cutover): MSP is now the default transport — `muse-job spawn` drives jobs over `muse serve` unless `--tmux` opts back into the legacy TUI-pane path (closes #228). The cutover also fixes a serve-schema drift the 1.4.x binary exposed: `turn/start` and `turn/steer` now send the required `input` content-part array (the old opaque `prompt`/`message` string fields are rejected with invalid params), and `turn/steer` carries the required `expectedTurnId` anti-cross-turn guard. (#228)

- Hosted phone-home, plane entry point live (#958 S4a): the hosted
  control plane now serves the WebSocket upgrade `GET /v1/boxes/{box_id}/phone-home`,

  fronting each box's own Durable Object. The upgrade authenticates the
  box's short-lived Bearer <redacted> first — unknown, expired, or revoked tokens
  get a plain 401 with no socket and no redirect, and the socket is
  always routed by the verified token identity, never the URL. First
  slice; the socket session logic (hello handshake, command re-drive,
  revocation checks) follows. (#986)
- Control-plane API reference, fix-up (#985): the consolidated endpoint
  reference now documents the box-filing endpoint `POST
  /v1/boxes/{box_id}/approvals/file` (box token, own box only, write-only
  `201/200 {ok, aid, deduped}` — the phone-approval upload leg), notes that
  recording a decision enqueues an `approval_decision` command so the box
  learns over the command fetch, and drops the stale "plane implementation
  is the next step" claims now that the approvals chain shipped. The
  reference is pinned to the current main.

- Hosted phone-approval push, payload scrub pinned (#980): the plane-side
  construction rule for push payloads — every box-controlled string is
  control-character stripped (C0/C1, so terminal-injection and ANSI
  escapes die) and truncated to a byte-exact 256-byte bound with an
  ellipsis, before the plane signs anything. Payloads stay "go look"
  only (approval id + TTL + scrubbed summary); the builder takes no
  token/key argument and returns an immutable mapping, so secrets have
  no ingress path at construction. The owner-facing approval surface keeps
  showing the full raw text so nothing is hidden from the decider.

- Hosted phone-approval push, event taxonomy pinned (#982): which plane events
  page and which don't — an approval filing pages once, expiry never pages,
  and a decision is the cancellation signal rather than an event. The reminder
  point is parameterized on the approval's own TTL (the "15 minutes before
  expiry" rule is unsatisfiable under the 10-minute default), the reminder
  sweep gets a scheduler home on the request-driven plane (cron first), page
  volume is bounded per box and per owner with hourly digest coalescing, and
  a two-gate lease re-checks the record before sending so a just-decided
  approval never buzzes after the fact.

- Hosted phone-approval push, sender crypto validated (#978): the plane worker
  can encrypt Web Push messages in-worker — a stdlib-only implementation of
  the RFC 8291 `aes128gcm` content encoding (P-256 key agreement, AES-GCM,
  VAPID signing) proven against the RFC's worked example. One send costs
  ~38 ms, so the sender service needs no separate process or JS bridge.
- `spark-pair.py phone-home`: the box-side persistent WSS channel to the
  control plane (#959, S5a connection core) — stdlib-only RFC 6455 framing,
  the upgrade handshake with the box bearer in the `Authorization` header
  only (never in a frame, never in a log; redirects refused outright), a
  crash-safe durable generation counter, 30 s keepalive pings, and the
  close-code reconnect policy (revoked → no reconnect loop, expired →
  reconnect with the current token, stale-generation → adopt and bump
  epoch, going-away → ≥60 s backoff). The #864 heartbeat stays the only
  liveness signal. Note: the plane half (#958) is not built yet, so the
  daemon retries `upgrade failed` with backoff until it lands — validated
  against a stub harness only. (#975)

- `spark-pair.py phone-home`: socket command frames + `command_ack`s (#976,
  S5b) — the daemon now executes durable commands pushed over the open
  channel (plane half #958 still pending; validated against a stub
  harness only) through the same ingest path as the HTTPS fetch loop
  (execute-before-ack, redeliveries deduped), and acks them back over the
  socket instead of a separate HTTPS call. Untrusted frames (wrong
  generation, malformed, oversized, unknown kinds) are logged loudly and
  never executed; a missing sequence number holds the queue until the
  plane re-drives it. (#981)

- The docs index now covers the two newest hosted-product gap analyses —
  the box-to-plane filing-upload leg (#876) and the missing plane push
  sender for the phone-approval lane (#849) — and the approvals-plane index
  row is refreshed to the 2026-10-02/03 state (the client signal, the expired
  terminal record, and the return leg shipped with the filing record, the
  decision channel, and box-side ingest; among the gaps that remain: tenant
  routing, push retry, the first-approval summons, alert fan-out, and the
  sentinel audit leg). (#974)

- A new gap analysis maps the missing plane-hosted push leg of the hosted
  phone-approval lane (#971): the filing, record, decide, and
  decision-delivery legs are all shipped, but the control plane has no push
  sender — its only "push" mention is a comment admitting the approval TTL
  is "a race against push" it cannot win. The analysis pins the trust model
  (box-to-plane-to-device only; the tenant box never holds a push
  credential; only plane-observed events can page) and files the build
  slices: the plane Web Push sender service, the owner subscription surface,
  the event-to-push mapping with anti-spam bounds, and payload discipline
  for box-controlled text. (#971)
- The fleet dashboard now shows each box's pending action approvals with
  approve/deny taps (#954): the owner can see and decide agent actions from
  the box detail view instead of raw API calls. Decisions are write-once
  (a double-tap replays, a conflicting tap is rejected, an expired approval
  reads as expired, never pending) and the decision travels to the box over
  the durable command channel. All box-controlled text is HTML-escaped with
  control characters neutralized before rendering. (#963)
- The hosted control plane gained a box-authenticated filing endpoint (#952):
  a box can now create its own action-approval records (`POST
  /v1/boxes/{id}/approvals/file`, scoped to the box's own id, accepting the
  current or in-grace-rotation token), answering write-only so the box never
  reads its own approvals — the forward database migration makes the record's
  owner field nullable, with null meaning box-filed. The owner-side
  create/list/decide surface is unchanged. (#956)
- The box now uploads its locally filed approvals to the hosted control
  plane (#953): a new periodic `spark-pair.py upload-filings` command scans
  the box's pending-approvals store and files each record with the plane's
  box-authenticated endpoint, retrying on the next cron tick when the plane
  is unreachable. Uploads are pending-only (denied, expired, and decided
  records never cross), the store must be box-service-owned, and the payload
  is clipped to the plane's size bounds — so the proxy's refusal path gains
  no plane latency and the owner can see and decide pending approvals from
  the plane. (#957)
- A new gap analysis maps the missing filing-upload leg of the hosted
  approvals lane (#876): when the proxy refuses a sensitive action, the
  plane-side approval record exists but nothing creates it from the box
  side — the analysis pins the seven decisions the build needs (a
  box-authenticated file endpoint, a periodic box-side uploader, pending-only
  upload, the payload mapping, and the owner dashboard surface) and files
  them as issues #952, #953, and #954.
- The toolset updater now snapshots before it changes anything (#532): every
  `update` run records the pre-update state of the files each layer manages
  (plus a package-version inventory) and, when a layer fails, automatically
  rolls that layer back and marks it blocked — the next run skips the blocked
  layer instead of retry-looping the same failing update. A new `rollback`
  command restores the newest snapshot by hand, `unblock` clears a block after
  investigation, and `status` reports both the blocked layers and the available
  snapshots for the future machine-readable health report.

- The box now ingests the control plane's approval decisions (#874): a new
  `spark-pair.py ingest` command (cron-friendly, ~1/min) pulls durable
  commands from the plane and stamps owner approve/deny/expire decisions
  into the box's approval store, so a parked agent sees the same decision
  signal as for a locally-tapped approval — with a `decision_origin:
  "plane"` provenance marker plus the plane `(seq, idempotency_key)`
  receipt on every stamped record (unforgeability holds at the delivery
  channel, not on disk — see the trust-model note in `spark_pair.py`),
  an `answer` audit-log line per stamped decision, idempotent stamping
  across redeliveries, pre/post-mint terminal re-checks on the approve
  path, and fail-closed handling of unknown or tenant-scoped approvals.
  (#944)

- Pinned the `approval_decision` command kind (#873): the first
  plane-produced command on the durable queue — an owner's approve/deny
  tap (and server-side expiry) now travels to the box as a command
  carrying the approval id, decision, and idempotency key, so the box
  learns of decisions through the queue instead of never. (#943)

- Pinned the phone-home wire-protocol spec (#847's S3 contract): the
  box↔plane WebSocket contract the Durable Object and box client will
  build against — auth at the upgrade handshake (the Bearer <redacted> never
  travels in a frame), a frame-class registry so control/command/stream/input
  frames never collide, the decision that connection-generation and
  command-epochs are separate counters, keepalive and close-code rules, and
  the fallback/liveness-precedence rule (the HTTPS heartbeat stays the
  only liveness signal; the socket never fabricates it). (#941)
- Published the vision-vs-state gap analysis for the interactive desktop
  lane (#854): the lane's vision is that the box publishes its Xvfb desktop
  through the Cloudflare Realtime SFU and the owner views/interacts from
  the dashboard — the analysis names what is missing (box-side publisher,
  the session/presence plane, the dashboard viewer with the #47 mobile
  gestures), the load-bearing calls (media transits Cloudflare, input is
  an action on its own channel class, the capture pipeline stays
  transport-agnostic for self-hosted parity), and that Realtime app
  provisioning is an operator step. Slices filed as #935 (session plane),
  #936 (box publisher), #937 (viewer).
- Bounded the waitlist funnel-event store: events older than 90 days now
  rotate out of the hot `funnel_events.jsonl` into dated monthly
  archives (never deleted — the audit trail stays on disk), while
  `invite_sent`/`claimed` events for live rows stay pinned so the
  reconcile passes never re-emit duplicates. Operators run it as a
  weekly `waitlist_jobs.py --rotate-funnel-events` cron (same data-lock
  discipline as the purge job; `--dry-run` previews the partition), and
  the horizon is overridable via `WAITLIST_FUNNEL_RETENTION_SECONDS`.
  (#933)
- Pinned the hosted credential-vending contract: the control-plane vend
  endpoint and its auth, the tenant-scoping decision (one box per tenant,
  so the box-side credential stack stays flat), lease-wrapped
  short-lived credentials with a RAM-only box cache, and where secret
  values rest on the plane — the design the vend endpoint and box-side
  fetcher will implement. (#931)
- Published a consolidated control-plane API reference for the spark-vm
  control plane: every real endpoint across the owner, pairing, box,
  action-approval, and durable-command namespaces with its auth class and
  request/response shapes, plus the unified failure-code table — so
  operators and self-hosters no longer have to piece the plane's surface
  together from scattered docs and ship notes. Each claim cites its
  canonical contract doc.
  (#925)
- The fleet dashboard's anti-XSS tests now exercise the real row
  templates: the fleet row, pairing card, detail rows, and service
  chips are built by single-copy pure renderers, and the test suite
  renders them in Node with hostile box-controlled strings — so a
  template that ever drops an escaper fails the suite. (#971)
- Competitor watch, 2026-10-03 (morning): DigitalOcean's own pricing
  page now confirms the Oct-1 Agent Droplets monthly-price plans with
  dollar figures (Pro $50 with 15% usage discount, Team $200 with
  20%), folded into the corpus entry; all tracked vendor baselines
  re-verified, no new competitor launches. (#924)
- The toolset self-updater now freezes after repeated failures: after
  three consecutive failed update runs it stops attempting updates and
  surfaces a single "box needs attention" state (visible in the status
  report and the timer logs) until an operator clears it with the new
  `unfreeze` command. Deferrals, dry-runs, and opt-outs never count
  toward the streak; a successful run resets it. (#971)

- Published the control-plane protocol for phone-approval records: the
  plane now holds a per-box action-approval record (owner-created, with a
  client-chosen action id, a server-clamped expiry window, and a
  write-once approve/deny decision) behind owner-key-authenticated
  endpoints — a box can never decide its own approvals. Expiry is
  enforced server-side (an expired record reads terminal), repeat taps
  replay the same decision, and conflicting decisions are rejected. The
  box-side filing, plane-to-box delivery, and ingest legs are separate
  follow-ups. (#916)

- Published a vision-vs-state gap analysis for hosted box provisioning
  (signup → claim → provision → auto-pair → dashboard): the provider
  interface ships but no Fly driver implements it, the invite-claim stream
  has no provision consumer, plane-provisioned boxes have no pairing
  auto-approval design, and spend caps are a decision with no enforcement
  mechanism — filed as new tracked issues. (#971)

- Published a vision-vs-state gap analysis for terminal streams and R2 artifact
  upload: no stream transport exists yet (the per-box Durable Object and
  phone-home channel are still unbuilt), no box-side terminal producer, no
  viewer surface, and no R2 bucket or upload path — with the design call that
  stream bytes must never ride the durable command queue, and that stream
  viewing is observation while stream input rides a dedicated input frame
  class (approval as the consent plane, never the approvals decision wire).
  Filed as new tracked issues. (#971)

- spark-vm has a brand logo: a gold spark on a dark terminal badge, with SVG
  source and PNG exports for the site header, app icons, and favicon. The
  landing and waitlist pages now share a brand bar carrying the mark. (#901)

- Published a standing production deploy contract for the hosted control
  plane: every production deploy now requires unanimous SHIP IT from the
  review roles on the exact final code (with the ratchet — SHIP ITs re-confirmed on the
  final head), a test harness against the exact final head with stub
  differences documented, a forward-only D1 migration discipline (recorded
  forward-fix plan, no down-migrations), a recorded deployment id with
  redeploy-as-rollback, live verification (auth taxonomy, test-row cleanup,
  stated limits), and recorded credential provenance. Codifies how the
  #846/#848 production deploys were done. (#895)

- Published a vision-vs-state gap analysis for hosted credential vending:
  the self-hosted localhost swap-proxy half (placeholders, allowlists,
  audit) exists and is hardened, but the "control plane vends narrow,
  short-lived credentials" half is missing entirely — no vend endpoint,
  no box fetch path, no tenant dimension, no short-lived semantics. Filed
  as two new build items (plane vend endpoint, box-side plane-fetch path)
  under a six-slice plan. (#850)

- The box self-updater now converges Playwright the same way it holds the
  CUA driver: the pinned Playwright package, its Chromium browser builds,
  and the browser system libraries are all brought onto the operator's
  pinned version each weekly run (installed as the agent user, so the
  browser cache lands where the agent's smoke tests look), instead of only
  reporting Playwright present or absent. (#532, #889)

- The hosted control plane now mints additional owner API keys on demand
  (`POST /v1/owner/keys`, owner-authenticated): the plaintext key is
  returned exactly once and never stored, a box token presented there
  401s, and the bootstrap closed-gate ordering is untouched. This closes
  the "single key per database lifetime" gap — safe owner-key rotation
  is now mint-second → verify → revoke-first, a second operator gets a
  second named key, and a lost key costs a mint instead of a fresh
  database. (#887, #878)

- Published an operator runbook for the hosted control plane's auth stack: a
  single page naming the credential inventory (owner API keys, box Bearer <redacted>,
  box keypairs, pairing codes), the day-0 bootstrap, the owner-key lifecycle,
  the box keep-alive cron lines, incident response (revoke-then-repair, the
  401-vs-403 meaning table), and the known limitation that bootstrap is the
  only owner-key minting path — plus corrected the stale "plane update
  pending" claims in the pairing README and the box client's CLI messages,
  which now point at the endpoints the hosted plane has served since
  2026-10-02. (#879)

- The fleet dashboard's control-plane copy is now re-inlined by a small
  sync tool instead of manual copy-paste: editing the page without
  re-syncing fails the byte-identity test wherever a worker checkout is
  reachable, and the test's worker path is overridable via an
  environment variable (documented in the dashboard README) so
  contributors can point it at their own checkout. (#877)

- The weekly toolset self-updater now converges the apt-based toolset too (#532): docker, node, and gh are upgraded in place on the weekly run — only packages the box already has are touched, never a bare system-wide upgrade, and the run still defers while agent jobs are active. (#871)

- The box now ships an in-repo heartbeat sender (`spark-pair.py heartbeat`, #864): the control plane's liveness contract finally has a producer — one cron-friendly call per minute sends the box Bearer <redacted> plus a small status payload, exits non-zero and logs loudly on any failure (a missed heartbeat never fabricates an ok), and the fleet dashboard's staleness chips are honest end-to-end.
- Durable owner-to-box command queue on the control plane: per-box
  sequential commands with short leases, idempotent acks, and
  incarnation epochs that safely expire in-flight commands on
  reboot/reprovision — pinned in the durable-commands protocol doc. (#867)
- The approvals-plane gap analysis is refreshed to the control-plane
  reality: the box-local return leg is closed (the approval signal
  headers and the expired terminal record both shipped), the stale
  expired-approvals issue is closed as superseded, and the hosted-approval
  gaps the new primitives expose are filed — plane-side approval records
  (#872), an approval-decision command type on the durable channel (#873),
  box-side ingest of plane decisions into the approvals daemon (#874),
  and the box-to-plane filing upload that creates the record (#876). (#875)

- Documented a pre-deployment constraint for the waitlist signup service:
  its per-IP rate limit and its operator-only status route see only the
  socket peer address, so the service must not sit behind a same-host
  reverse proxy until an explicit trusted-proxy mechanism exists (filed
  #896). (#899)

- The waitlist invite tooling can now re-derive `claimed` funnel events
  lost when the service crashes between recording a signup and emitting
  its event: a new repair pass scans the row store and re-appends exactly
  the missing events (marked as reconciled), so invite-to-claim
  conversion stops under-reporting after a crash. The pass is idempotent
  and sends nothing. (#900, #898)

- Contributor DX: the box-side filing loop now has an integration test
  proving the legs compose — a proxy refusal filed by the real filing path
  is picked up by the real uploader scan and POSTed to a contract-faithful
  plane stub (dedupe-on-retry, plane-down degradation with backlog drain on
  recovery), and an owner decision served as a plane approval-decision
  command is stamped by the real ingest with plane provenance. The suite
  also pins the cross-leg filing schema, so a future change to either side
  breaks loudly instead of silently skipping proxy-filed refusals. (#983)

- Contributor DX: the filing-loop integration test now closes the last
  hop — after a plane denial is stamped by the real ingest, the real proxy
  serve leg returns the terminal "denied" signal for the parked agent's
  next poll (and no fresh approval is filed), while the poll before the
  decision sees "pending" without re-filing. The suite pins both the
  terminal-delivery read and the no-re-file composition against
  neutering. (#984, #876)

- Fleet update events: `fleet collect` now detects audit-tail overflow
  between pulls. The estate pulls only a tail of each box's audit log,
  and when more lines are emitted between pulls than the tail holds, the
  lost lines — including the failure events the alert rules page on —
  vanished silently: the tail truncation hides the loss, and the
  deterministic event-id dedup makes it undiscoverable by re-pulling.
  A per-box tail-head watermark in the store now checks
  that consecutive pulls' tail windows overlap; when they don't, the
  collect warns loudly on stderr and records the break, so a too-short
  tail is a visible incident instead of missing evidence. (#1006, #1011)

### Fixed

- The relay liveness journal no longer blocks forever on a stopped or
  wedged lock holder (#1082): frame emission and the control-plane
  liveness query wait up to five minutes for the journal lock, then
  fail loudly — naming the lock file and pointing the operator at the
  stopped (SIGSTOP) or wedged process holding it — instead of freezing
  the liveness signal with no error. A journal that was never deployed
  on this machine still reads as darkness, not an error. (#1084)
- The jail firewall watchdog now pins the firewall table by its
  canonical structure instead of its rendered text (#444): an nftables
  upgrade that re-words rule text — not just re-indents it — no longer
  trips a false fail-closed storm that stops the jail every minute. The
  build captures the applied table once and the watchdog compares
  semantically, so a re-rendered-but-identical table stays healthy
  while a deleted rule, an added rule, or a re-addressed DNAT still
  fails closed. Re-running the jail build regenerates the pin; the
  build-time self-test exercises the canonicalizer against the box's
  live rendering. (#1083)
- Fleet journal lock no longer blocks forever on a stopped or wedged
  lock holder (#1007): collectors, prunes, and alert acks wait up to
  five minutes for the store lock, then fail loudly — naming the lock
  file and pointing the operator at the stopped (SIGSTOP) or wedged
  process holding it — instead of piling up hung cron jobs with no
  error. A normally-slow holder still serializes as before; only the
  pathological wait becomes a failure. (#1081)
- Push digest reliability (#1063): two gaps in the hourly digest that
  carries over-budget pages are closed. Digests for past hours whose
  pages arrived after the hour's last scheduler tick no longer strand
  silently — the scheduler now fires any pending digest window with
  that window's own key, and records when each window's digest went
  out. A late digest counts against the current hour's page budget —
  the page goes out now, so now's budget is the honest one. And a
  digest suppressed by an exhausted page budget no longer
  wedges that hour's digest permanently: the suppression is recorded
  without blocking the digest's key, so the digest retries once
  budget frees instead of never going out. (#1080)

- Answering an approval no longer crashes with a server error when the
  pending file is consumed by another process in the instant between the
  existence check and the consume: the answer is now refused honestly as
  "not found or already answered" with a distinct audit event, matching
  the concurrent-answer loser path. (#1068)

- The proxy now leaves an audit note naming the credential (never the
  value) when response-header scrubbing rewrites a `Set-Cookie` for a
  credential the request side cannot swap back into `Cookie` headers —
  so a session that mysteriously breaks after the first request is
  diagnosable from the audit trail instead of failing silently. (#1068)

- The waitlist operator test suite is time-bomb-proof (#1051): the
  live-token reinstatement case previously mixed a fixed 2026-09-20
  fixture clock with the real clock the operator CLI reads, so the
  test only passed while the fixture date was within the 14-day
  invite window — it failed on main once, and the interim fix only
  reset the fuse for another 14 days. The CLI now accepts a pinned
  test clock, so the whole case runs on the fixture date and passes
  no matter when the suite runs. No product behavior changed.
  (#1053)

- Fixed a time-bombed waitlist operator test (#1051): the live-token
  reinstatement case pinned its clock to a fixed 2026-09-20 fixture
  while the operator CLI reads real time, so once real time passed
  the fixture's 14-day invite window the live token read "expired"
  and the test failed on main. The test now anchors to real time and
  its refusal-text assertion drains earlier stderr first. No product
  behavior changed — the reinstatement path itself was correct.
  (#1052)

- The fleet release-gate sync loop hardens its delivery path (#1009): a
  failed gate-file install no longer leaves stray temp files on the box
  (cleanup now runs on failure too, and on failed transfers), and two
  overlapping scheduled syncs no longer race — the second one exits
  loudly instead. (#1046)

- The hosted push sender now bounds the push-service response read with a
  total 30-second deadline (#1039): previously only a per-read timeout
  applied, so a push service answering very slowly could hold a send
  indefinitely; when the deadline expires the attempt is retried like any
  other transport error. (#1043)

- The push sender's key-validation checks are now a public, documented API
  instead of reaching into the crypto module's internals — a future change
  to the crypto internals can no longer silently break push delivery, and
  the validation contract (fail-closed on malformed keys, no exceptions
  leaking) is pinned by tests. No behavior changed. (#1041)

- The stillborn-spawn error now gives the two real retry paths (#994):
  the in-code retry advice contradicted the muse-job README — telling the
  operator to remove the job dir first would delete the job record `close`
  is supposed to archive, breaking both retry paths. The error now points
  at the new-slug path (retry with a new slug, then close the blocked job
  to archive it) and the same-slug path (`close` first to tear down the
  git worktree and job branch, then remove the job dir, then spawn again).
  (#1026)

- The watchdog's stillborn needs-attention signal now carries the full
  two-path retry advice (#1029): it previously suggested "retry spawn
  with --tmux", but a same-slug spawn refuses a slug whose job dir
  still exists — so the signal now names the new-slug path (spawn with
  a new slug, then close the blocked job to archive it) and the
  same-slug path (close first, remove the job dir, then spawn again),
  matching the spawn error and the README.
  (#1037)

- Phone-home epoch bump now joins the command ingest's lock discipline
  (#1019): the reboot-equivalent epoch fence previously rewrote the
  ingest cursor without the lock, so a cron ingest mid-pass could save
  a stale epoch back over the bumped one and lose the fence. The bump
  now takes the ingest lock non-blocking — under contention it skips
  loudly and defers to the plane's stale-generation fence instead of
  stalling, and the generation-loss log line no longer claims the bump
  when it skipped. (#1024)

- Phone-home daemon exit codes now distinguish crashes from deliberate
  stops: uncaught exceptions exit 2 (loud on stderr and in the log,
  traceback with the token redacted) so the supervisor restarts them,
  while the deliberate human-attention exits stay on 1 and are never
  restarted (`RestartPreventExitStatus=1` in the documented systemd
  unit — previously the unit's `Restart=on-failure` contradicted its
  own "exit 1 means human attention, not a restart loop" comment).
  (#1023)

- muse-job spawn over MSP now detects a first turn that died before
  engaging (#994): after `turn/start`, spawn watches the new turn's
  events for a few seconds — if the turn dies before the agent engages
  (cancelled, interrupted, or failed server-side, as seen when the
  serve host cancelled the first turn within ~1ms), the spawn fails
  loudly and the job is marked blocked instead of sitting "active"
  forever with nothing working. A turn that stays silent for the whole
  window is still reported engaged (absence of death, not proof of
  life). To retry a stillborn spawn: remove the job dir or use a new
  slug, then spawn with `--tmux`, while the serve-side cause is
  investigated. (#997)

- muse-job's workspace-trust gate detector now requires the question and the
  "Trust and continue" option on separate lines, option after the question
  within a few lines (#972): a live session whose own conversation mentions
  both phrases (e.g. the agent pasting a gate transcript, or saying it chose
  "Trust and continue") no longer reads as a trust gate, so the watch loop
  can no longer type "1"+Enter into a working session's input box. (#992)

- The box-side command ingest now asserts its command incarnation on every
  queue fetch (#947): the plane can detect a box whose epoch is stale and
  force it to re-sync (plane-side detection itself is #848/#958 scope)
  instead of serving it commands from an old incarnation. A box with no
  epoch yet (first run) sends no claim rather than asserting a bogus
  zero. (#977)

- Steering a job's TUI now verifies delivery with a stronger needle (#12):
  the arrival check requires the message's first-line AND last-line text in
  the input box, so a stale agent echo of an earlier steer can no longer
  fake a delivery that never happened. Previously the check used only the
  first 60 characters of the first line. (#977)

- The job watchdog's trust-gate detection no longer fires on a live TUI's
  own conversation merely mentioning the trust question (#961): the gate is
  only recognized when the question line AND its option line ("Trust and
  continue") co-occur in the viewport tail. Previously a session discussing
  the gate read as gated, and the automatic answer typed "1"+Enter into the
  live session's input box. The genuine gate shape is unchanged, so a
  truly parked TUI is still answered. (#973)

- The job watchdog now distinguishes a workspace-trust gate the TUI is
  parked at from a generically dead pane even when the pane's foreground
  process isn't the TUI (#836): the visible-but-unverifiable gate raises a
  loud `blocked-trust-unverified` alert (never auto-answered, never
  keystrokes into an unverified pane) instead of the generic `tui-dead`,
  so a gate the automatic answer can't reach no longer strands silently.
  (#836, #962)
- The toolset updater no longer silences its own error output while taking
  its single-flight lock (#950): diagnostics written after the lock is
  taken reach the log and terminal again. The lock's failure modes are
  unchanged (loud failure, freeze-counter accounting). (#962)

### Security
- The fleet read API now refuses oversized journal projections with
  HTTP 413 instead of building them (#1033): the events and alerts
  endpoints previously loaded, sorted, and serialized the entire
  journal into one JSON response per request — on the single-threaded
  server, one slow-reading local client could wedge the API for
  everyone. Past 50,000 rows the endpoints now fail closed with a JSON
  413 (naming the cap, the total, and the remedies) before any rows
  are built. Full paging stays an S2 decision (#795).
- The toolset self-updater's Playwright browser downloads are now
  hash-pinned (#1017): the updater takes the exact archive URLs from the
  Playwright driver's own dry-run output (refusing on any shape drift) and
  refuses unless each archive's SHA-256 matches the digest recorded at
  commit time (x86_64 and aarch64) — a CDN serving different bytes for the
  same browser revision can no longer slip past the updater. Verified
  installs are stamped so later runs skip the download entirely.
- The fleet read API's access log now strips control characters before
  writing (#1032): the request line is client-controlled and used to reach
  the operator's terminal raw, so a local client could inject terminal
  escape sequences or forge extra log lines — the log line is now scrubbed
  (C0 controls, DEL, and C1) the same way the pairing client scrubs its
  display path.
- The toolset self-updater's Playwright install is now hash-pinned (#1018):
  the updater downloads the exact pinned Playwright wheel and refuses
  unless its SHA-256 matches the digest recorded at commit time — a
  compromised package index can no longer slip a different wheel past the
  version pin. A pin bumped without its recorded hashes fails closed
  instead of falling back to an unverified download. The browser binaries
  remain the documented residual: their build revision is fully determined
  by the now hash-verified package, but the archive bytes themselves are
  still fetched over TLS only.
- The proxy now refuses outbound requests to non-allowlisted hosts that
  carry a real credential value, not just the `hsurr:` placeholder (#855):
  a secret smuggled in the target authority is refused before any DNS
  resolution leaves the box; the path and query string (raw, percent-
  decoded at any depth, and form-decoded), request headers (verbatim;
  decoded HTTP Basic credentials on both authorization headers scanned),
  and text request bodies are scanned for known secret values, and the
  request is dropped before anything is forwarded. The operator warning
  and the audit trail name the credential, never the value (the audit
  host is scrubbed too, since a token-subdomain host can itself be the
  secret); TOTP codes still match as whole tokens only, and framing
  headers are never scanned, so innocent requests don't get killed.
  Over-cap and binary request bodies pass through unscanned as stated
  residuals (the over-cap pass is audited). (#996)
- The credential web UI now requires a per-install API token on every
  management endpoint (#86): the previous `X-Cred-UI: 1` header is not a
  secret — any local process could set it and add, list, remove, or
  rebind every credential. The token is generated once into a
  owner-only file, pasted into the browser once per session, and compared
  in constant time; the page never stores it in a cookie or URL. Show it
  with `cred-ui.py --print-token`, replace it with
  `cred-ui.py --rotate-token`. (#965)
- The proxy's refresh/navigation-target scan now matches past literal newlines:
  a line break inside a meta-refresh `url=` value is legal HTML — browsers
  strip it and navigate to the joined URL — so a secret smuggled after the
  newline previously escaped detection. The wider match is fail-closed-safe
  (it can only detect more, never less). (#888, #869)
- The box pairing client (`spark-pair.py`) no longer leaks its credentials on
  redirects: Python's HTTP library forwards `Authorization` headers even
  across redirects to a different origin, so a misconfigured or compromised
  control plane could have bounced a request elsewhere and harvested the box
  bearer token or the owner's API key — the client now strips the header
  whenever a redirect leaves the original origin (same-origin redirects keep
  working). Separately, the client refuses cleartext `http://` control-plane
  URLs outright (loopback hosts stay allowed for local testing, and an
  explicit opt-out environment variable covers other cases), so a typo or a
  misconfigured URL can no longer send bearer tokens over the wire
  unencrypted. (#884)
- The swap proxy now refuses credential-smuggling navigations beyond `Location` redirects: a `Refresh` response header whose `url=` target carries a known secret value — raw or percent-encoded, which the header scrubber cannot see — to a non-allowlisted host has its target neutralized in the header and the attempt recorded on the audit trail (the page still loads; only the navigation is neutered), and an HTML or XHTML `<meta http-equiv="refresh">` tag with the same kind of secret-bearing target has its URL neutralized in the page the same way. Navigations to allowlisted hosts keep today's scrub-in-place behavior, and bare same-page refreshes are unaffected. (#870)
- The swap proxy now kills redirects that would smuggle a real credential off the allowlist: a 301/302/303/307/308 response from an allowlisted host whose `Location` carries a known secret value — raw or percent-encoded, which the header scrubber cannot see — to a non-allowlisted host is refused at headers time and recorded on the audit trail, instead of letting the browser's follow-up request carry the real secret to the attacker host. Redirects to allowlisted hosts keep today's scrub-in-place behavior, and relative redirects are unaffected. (#862)
- The waitlist's one-click "forget me" now erases the address from the live data stores the daemon manages, not just the row store: the abuse-detection ledger, the raw-mail triage folder, the quarantined malformed-line sidecars, and any still-queued outgoing mail for that address are all scrubbed when the forget link is honored, and triage files now expire after 48 hours instead of accumulating forever. The deletion confirmation remains the last mail ever sent to a forgotten address, and the stated contract is that the operator's mail sender deletes each queued mail after delivery. (Backups taken before the forget are outside this guarantee — the operator rotates them under their own retention.) (#840)
- Egress guard now refuses the 6to4 (`2002::/16`) and Teredo (`2001::/32`) IPv6 transition ranges by default: both embed an IPv4 address inside a v6 literal, so a transition literal for a private IPv4 (e.g. 6to4's `2002:7f00:1::1` for 127.0.0.1) previously judged as a public v6 address and passed the SSRF guard — the same fail-open class the IPv4-mapped unwrapping already closed. These are deprecated transition mechanisms with no legitimate destination on the proxy's egress path, so the ranges are refused wholesale rather than unwrapped; the SSRF allow file can still admit them explicitly (hostname or CIDR) when an operator genuinely needs one. Separately, NAT64 well-known-prefix literals (`64:ff9b::/96`) are now unwrapped to their embedded IPv4 before the range judgment — a literal embedding a private IPv4 is refused, while one embedding a public IPv4 still passes, because NAT64 is a live mechanism (on DNS64 networks it is the legitimate path to v4 upstreams) and must not be refused wholesale. (#839)
- Signed golden-image manifests (#155): the provision-time injector's manifest preflight no longer trusts the manifest's self-asserted version alone — once the operator enables the signed path (sign the manifest at image-build time with an Ed25519 key and configure the injector with the verification key), the preflight verifies the signature over the manifest's exact bytes before parsing anything, failing closed on a missing, malformed, or mismatched signature, so a tampered image registry can no longer serve a lying manifest that names the pinned version. The verification side takes a rotation window (`key_id=/path` pairs, mirroring the fleet release gate) so a stolen signing key rotates forward without a flag day, and the provision report records `ok-signed` vs `ok-unsigned-legacy` so the migration off unsigned preflights is observable. The signing key never enters the repo or the image; the verification keys ship with the injector's own configuration. Unsigned preflights keep working while older images are in service. (#831)

- The waitlist signup service now resolves the real client address through
  an explicitly declared reverse proxy: a new operator setting names the
  proxy hop(s), and only then are forwarding headers honored — and only
  from those peers. Without the declaration the service ignores forwarding
  headers entirely, so the per-IP signup rate limit can no longer collapse
  to one global bucket behind a same-host proxy, and the operator-only
  status route (spool backlog and row counts) stays unreachable to
  external clients arriving through the proxy while the on-box operator
  keeps access both direct and via the proxy. A forged forwarding header
  from a direct client is ignored, so it can neither dodge the rate limit
  nor claim loopback. (#900, #896)

- The box pairing client closes three redirect and response-shape gaps: a
  redirect that downgrades a secure connection to plain HTTP is now refused
  outright (the earlier header-stripping fix was safe, but the follow-up
  request would still have talked to the new address in the clear);
  unparseable redirect targets (like a garbage port in a Location header)
  fail closed with a clean error instead of an internal exception; the
  control-plane refusal message no longer echoes embedded username/password
  credentials into logs; and the interactive approve path now validates the
  pairing records it prints, so a malformed or hostile control plane gets a
  clean error instead of a crash — and an approval can never proceed
  without a fingerprint to verify. (#903, #881, #885)
- The toolset updater's `install` step now sets the state directory to
  owner-only instead of trusting the install-time umask (#951): snapshots,
  the layer block list, and the audit log live there, so a pre-created
  loose directory no longer weakens them. A malformed version pin in the
  pins file can also no longer corrupt the audit log's JSON — the updater
  validates each pin before recording it as the layer's block key, and
  fixing the pin unblocks the layer just like a pin bump does. (#966)

### Fixed

- The waitlist event-repair tool (`--reconcile` / `--reconcile-claimed`)
  no longer crashes when a funnel event carries a timestamp that isn't a
  string: a corrupted-but-readable event used to raise an error and kill
  the whole repair run; it is now treated as uncovered and re-derived
  from the row records, same as a torn log line. (#939)
- JSON request bodies are no longer corrupted when a credential
  placeholder sits outside a quoted string: previously the proxy
  substituted the raw secret value in unquoted positions, so a
  non-numeric secret produced invalid JSON and the server rejected the
  request with no audit line explaining why. The proxy now re-parses the
  body after substitution — if it no longer parses, the whole swap is
  refused, the placeholders are left in place, and the refusal is
  logged and audited. (#932)
- The fleet's correlated-failure alert no longer fires on failures that
  carry no target build: previously two unrelated failures with no
  recorded target could be grouped on an empty key and page a
  "bad release" fleet alert together. Correlation now requires the
  shared target build the inference is actually about.
  (#929)
- The fleet's correlated-failure alert now re-pages when another box
  joins an already-paged failure cluster: previously the alert's
  detail froze at the first two boxes and further failures inside the
  window were silently absorbed, so a spreading bad release looked
  contained in the alert journal. A growing cluster now pages again
  with the full box list, while a stable cluster still fires exactly
  once. (#927)
- The stuck-precheck alert no longer pages once per evaluation window
  while the underlying condition persists unacknowledged: an ignored
  stuck box used to pile one pending page per window into the alert
  journal (which never drops unacknowledged alerts). It now pages once,
  stays visible as the one pending alert until you acknowledge it, and
  after an ack re-pages only when every failure in the window is newer
  than the ack — persistence on evidence you already saw stays silent.
  (#927)
- Acknowledging a fleet alert now records when it was acknowledged
  and by whom in the journal row, so a handled page is
  distinguishable from a silenced one. (#928)
- The credential proxy now notices when a secret file's contents are
  rewritten in place: previously it only watched the secrets directory
  for additions and removals, so a secret rotated by editing the file
  directly (instead of through the atomic writers) was never picked up
  and the old value kept being swapped silently. (#912)

- A mistyped entry on a multi-value secret file now leaves the same
  audit trail as a mistyped entry on a single-value file: previously the
  swap was silently skipped with no record, so typos were invisible to
  the credential owner. The entry is still left untouched — only the
  audit line is new. (#911)

- Plane-supplied error text in the pairing client is now stripped of
  terminal control characters before printing: a hostile control plane
  could previously embed escape sequences in an error string that your
  terminal would render. The message itself still prints; only the
  control bytes are removed. (#902)

- The pairing client's rotate confirmation now strips terminal control
  characters from the plane-supplied proof value before printing: on
  keyless boxes the success line could otherwise render escape sequences
  from a hostile control plane. A sweep of every pairing-client print
  site confirms this was the last unscrubbed channel. The scrub also
  strips C1 control characters (U+0080–U+009F), closing a residual the
  adversarial review caught. (#917)

- The desktop bridge's launch registry no longer trusts persisted process IDs
  blindly: a stored `0` (or boolean `true`, which is `1` in disguise) can
  never be pruned as dead, so a corrupted registry could refuse to start an
  app forever with a stale "already running" verdict — those entries are
  now dropped when the registry loads. The registry file is also written
  exclusively at 0600: the save can no longer follow a planted symlink or
  land in a world-readable temp file. (#910)
- The weekly toolset self-updater's idle gate now sees agent jobs no matter
  which user owns them: it checks every agent user's own tmux sessions and
  their muse-job job registry for live jobs, instead of only root's tmux
  server — previously a job running as another user was invisible and the
  weekly update could restart services underneath it. (#904)
- The dashboard sync tool now refuses two more ways to produce a broken
  control-plane file: a page ending in an odd number of backslashes (the
  last one would escape the closing quotes of the inlined string) and a
  BEGIN marker stranded on the worker's last line (which used to die with
  a bare traceback instead of the tool's loud refusal). It also keeps an
  indented END marker line byte-for-byte instead of silently dedenting
  it, and its command-line exit codes (`--check` drift → 1, refusals → 2)
  are now covered by tests. (#894)
- The box pairing client's "endpoint not implemented" detection no longer
  keys on an error string the control plane itself can return: the HTTP
  layer now marks the 404 payloads it synthesizes itself with an explicit
  marker (stripping any forged copy from plane-returned bodies), and the
  rotate, revoke, and heartbeat paths all classify on that one marker — a
  JSON error body from the plane can no longer be misread as a missing
  endpoint. Separately, the client's two lock files are now forced to
  0600 on every acquisition, not just at creation, so a pre-existing lock
  file with wider permissions no longer stays wide. (#886)
- The box pairing client's HTTP layer now normalizes non-object JSON
  response bodies at the choke point instead of guarding at individual call
  sites: only the heartbeat path checked that a 2xx body was actually an
  object, so a plane returning a list, string, or null died with a bare
  `AttributeError`/`KeyError` traceback everywhere else — every command now
  gets a clean "malformed plane response" failure. The `redeem` path also
  got the same clean-error treatment for a corrupt, non-object, or
  incomplete `pairing.json` (the enrollment paths already had it), and GET
  requests no longer send a `Content-Type: application/json` header with no
  body. (#884)

### Added
- Published a vision-vs-state gap analysis for the planned per-box Durable Object phone-home channel: what exists today (HTTPS heartbeat polling, human-approved pairing, short-lived Bearer <redacted>), the missing pieces (no box-side long-lived process — the plane's heartbeat contract has no in-repo sender — no plane WebSocket surface, no wire protocol, and the token rotation endpoints the socket's auth will depend on), and the dependency-ordered plan for building it without shipping a socket whose auth can't be revoked. (#865)
- Box enrollment is now a human-approved pairing flow: a new box generates its own key, shows a short pairing code plus a key fingerprint, and only joins the fleet after the owner verifies the fingerprint and types the code — the old self-service registration endpoint is gone, the issued credential expires after 24 hours, and the whole flow is outbound-only so it works on self-hosted boxes with no inbound ports. (#856)
- Box tokens now rotate before they expire (#846, first slice): the box client gains a `rotate` command that proves key possession with an Ed25519 signature and swaps in a fresh short-lived token — atomic on disk, never printed — plus a cron-friendly `rotate --auto` that stays quiet until the token is actually near expiry, and an owner-side `revoke` that kills a lost or compromised box's token immediately. The protocol contract the control plane must implement (rotation endpoint, revocation endpoint, previous-token grace, grandfathered-token migration) is pinned in the pairing README so the plane update closes the issue against a fixed spec.
- The control plane now serves an owner fleet dashboard at its root: sign in with an owner API key and see every enrolled box with its last heartbeat age, boxes silent for more than five minutes marked stale, per-box detail (hostname, uptime, services, key fingerprint), and the pending pairing approvals with their fingerprints for the human verify-and-type approval flow. The key lives only in the tab's session storage, and the dashboard calls the same control plane that served it, so self-hosted planes get the dashboard unchanged. (#857)
- Approval pages now show the grant's lifetime at decision time and let the owner choose it: approving offers a bounded lifetime choice — 1 hour (the new default, shortest) or 24 hours — instead of silently minting the old hidden 24-hour grant. The choice travels through to the grant mint, is recorded in the answered history (visible on the answered card), and is audited; any value outside the offered choices is refused rather than coerced. (#842)
- Alert fan-out into the push plane, first slice designed (G23 / #797): a design doc pins the operator-paging intake — a second producer class on the H14 push machinery (its own queue journal, dead-letter file, notified log, and VAPID identity on the control-plane host — not a confirmd patch). Which fleet alert rules page (rollback-failed and correlated-failure immediately; stuck-precheck threshold'd; silent-wave not until wave assignments arm it, then once per silence episode), one page per stable alert id, and an acked alert never pages — even if the ack lands after enqueue (the worker re-checks the journal at delivery-claim time and drops quietly). Pages fire on the alert only; resolution renders on the status-page feed. Notification content is journal text only — no secrets, no model-authored text. The operator subscribe surface is the fleet console's job (interim operator CLI until then). S2 builds the enqueue path; the S3 tenant variant waits on the tenant read path (G24) plus the issue's C4 gate (named in #797, defined nowhere else — flagged in the spec as an S3 precondition). (#833)
- Contributor DX: CONTRIBUTING's "pins keep it honest" paragraph named three suite-inventory pins while the test suite ships four — the test-module basename-uniqueness pin is now documented alongside the other three, so a new contributor learns the full set of invariants the suite enforces before they trip one. (#834)
- Contributor DX: the markdown link-check CI job stops flagging live links — GitHub file-view pages (rate-limited from CI runner egress, 429/503) and the legacy ASCII docs domain (connection-refused there) are now documented exclusions, since both are live for real visitors. The ASCII citations keep their original URLs on purpose: the rename evidence was read on the legacy domain and the corpus documents the redirect, so the exclusion preserves citation integrity instead of rewriting history. (#835)
- Fleet release gating, first slice (G18 / #777): the operator's release registry now reaches each box as a single signed document — the maximum permitted versions per component, the live rollout wave per component, and a fleet-wide freeze flag orthogonal to releases. The repo updater caps its deploy range at the gate's maximum permitted commit, so an unregistered commit never deploys on a gated box; a missing, tampered, or expired document freezes the box loudly instead of releasing it. A two-box freeze drill proves a published freeze reaches every box within the operator's sync bound. (#830)
- Contributor DX: the keyboard-wedge probe's verdict classifier now normalizes to its documented vocabulary at classification time — a null or non-dict `input` section and a null or non-vocabulary `state` are inconclusive like a missing key (`unknown`), instead of taking the AttributeError-accidental `unparseable` or being recorded verbatim while the status line stayed silent (two surfaces for one inconclusive class). A body that does not parse at all stays `unparseable` and keeps its silence in the status line. The test suite pins the three behaviors the last review carried: null/foreign-state normalization on both the keepalive and the status surfacing, and the request-path distinction the design relies on — the keepalive's probe fetch carries `?probe=1` (runs a fresh probe) while the status surfacing stays a plain `/api/status` cache read. (#821)
- Fleet read API, first slice designed (G21 / #795): a design doc pins the read-only fleet API over the estate store — the first consumer surface for the G16 inventory and G17 event/alert producer stacks. Seven GET endpoints (`/fleet/boxes`, `/fleet/boxes/{id}`, `/fleet/drift`, `/fleet/events`, `/fleet/alerts`, `/fleet/crosscheck`, plus a reserved `/fleet/waves` that reports its own unavailability while wave assignments don't exist), each naming its CLI counterpart; the "every CLI command has an API equivalent" acceptance is cashed out honestly as field-equivalence with a per-endpoint conformance test (the CLI renders text tables, the API renders JSON — same fields, same values, same ordering). Mutations (`collect`, `rebuild`, `prune`, `events ack`) deliberately stay CLI-only: a localhost read API with no auth story must not grow write endpoints one at a time — acking lands with the S2 console's auth story. Stdlib HTTP only, localhost bind, no auth in S1 (the operator's box is the trust boundary); every response carries a data-freshness stamp, and empty journals render as "no data", never a clean-fleet fiction. The G21 S2 console consumes this API; the G22 S2a operator page consumes the collector journals directly per its own spec. The build stays on the issue. (#820)
- Fleet journals now age out on their own (G17 S2, #779): the event journal keeps 90 days of per-event records per box — rows older than 30 days are compacted into per-day outcome histograms (per box, component, and build) kept in a separate histogram file the event readers never see, and rows older than 90 days are dropped. Acknowledged alerts older than 90 days are dropped too, but unacknowledged alerts are never pruned away, and rows that can't be dated (or are dated in the future) are always kept rather than dropped. The version-inventory journal gets the same 90-day retention with its snapshot rebuilt from the pruned journal, and the fleet collector's journal appends now take the store's journal lock so an append can no longer race a prune's rewrite and journal into the void. (#819)
- Contributor DX: the keyboard-wedge supervision's shell-script test suite now pins the behaviors its own review left on trust — the fake bridge 404s unknown request paths like the real bridge does (a typo'd probe path can no longer pass silently), both probe functions are exercised against their default bridge address instead of only the test override, the test harness quotes exported values so paths with spaces survive, a bridge response with no input verdict is proven to fall back to inconclusive, and the dead-bridge case uses a race-free never-bound port. The keepalive's state reader also accepts the "unparseable" verdict the probe classifier records (defensive contract for future readers of the state file; no behavioral change — the value is overwritten by the next probe before use). (#811)
- Fleet status page, feed spec (G22 / #796): a design doc pins the P7 status page's feed contract — which fleet journal records become feed rows (the four fleet alert rules, rollout envelopes, freeze records), the dedup/idempotency rule (stable alert ids, idempotent re-reads, no feed-local state), the ack→resolve lifecycle (acknowledged is operator-declared, resolved is journal-derived per rule and never auto-clears), and what stays operator-only until the tenant read path exists (raw alert detail, box ids, inventory facts). Every row must be traceable to a journaled event — no synthesized availability, and an acknowledged-but-unresolved alert stays listed. S1 only; the page ships in S2, operator-first (tenant-scoped history follows G24). (#810)
- Fleet update-claim cross-check (G17 S2, #779): the fleet now checks each box's successful-update claims against what the version inventory actually observed afterwards — a claim no later inventory confirms is flagged as a violation, while a claim with no later observation at all is reported inconclusive instead of guilty, because missing evidence is never a contradiction. Violations are flags, not convictions: the point-in-time inventory wins the tie, the event keeps its journal row, and nothing is marked suspect automatically. The fleet events command's crosscheck exits nonzero while any violation is open, so a cron or the operator's existing paging can consume it. Rolled-back claims and the not-yet-produced toolset/image claims stay out of this slice. (#809)
- Competitor watch, 2026-10-01 morning (cycle 58): Modal's egress billing goes live on its stated timeline — the docs page reads in-effect but is otherwise verbatim unchanged (same 1/10/100 TiB allowances, $0.04/GiB overage, first egress bill still arriving November 1), an uneventful switch-over that retires the pre-effective posture line and gives spark-vm's provider comparison a live Modal egress datapoint. Three new vendor-confirmed competitor entries: MongoDB's Atlas Agent Engine (unified agent execution, memory, and governance; public preview since Sept 29; consumption-based pricing drawing on Atlas commitments; Voyage AI retrieval); Amazon Bedrock Managed Agents powered by OpenAI (April-28 announcement, re-announced at the Sept-29 DevDay keynote; IAM identities, human approval gates, CloudTrail logging — the DevDay re-announcement is the in-window event); and Vercel Sandbox support for Secure Compute (a private-networking option for sandbox workloads, filed as a capability addition). Also in this pass: Docker Sandboxes' Sept-28 release notes and Microsandbox v0.7.5 as watch-doc deltas; the Modal $750M / Baseten ~$26B rounds still unclosed; Vercel Drives GA still unannounced; AgentComputer still publishes no egress pricing; the Vercel "eve" novelty watch retired as already-known; a remediated Cloudflare cross-tenant disk-block disclosure and a single-source July Modal data-compromise claim stay flagged but unfiled. (#807)
- Operator docs: the swap proxy's service comments now state the runtime-path contract honestly — overrides of the `SWAP_*` path settings are expected under the one declared writable directory, and nothing validates or checks them at deploy: writes elsewhere fail when the service runs (except the service-private temporary directories, which are writable but ephemeral), while reads elsewhere succeed silently. (#803)
- Contributor DX: the keyboard-wedge supervision's test suite now proves what its review left on trust — a garbage probe response is proven inconclusive (it never counts toward the wedge and never restarts the desktop stack, even with the restart gate open), the status command's verdict mapping is exercised against a live fake bridge instead of asserted by string matching, and the probe's bare production call is smoke-tested against its default state directory and bridge URL. The status surfacing block was hoisted into a named function with a test-only URL override so the mapping is testable; behavior is unchanged. (#802)
- Fleet observability consumption, gap analysis (G21–G26): the fleet's producers shipped (G16 inventory journal+collector, G17 event canonicalizer+alert rules) but their consumers don't exist — journals on the operator's disk plus a CLI is the whole read surface. A new analysis doc maps the six consumption gaps against the hosted vision: G21 operator fleet console (read-only API over the estate store, then a wave/alert console), G22 the P7 status page (named in G17 S1 as the alert feed's formal home, never designed — shipped only with a no-fiction contract, every row traceable to a journaled event), G23 alert fan-out into the H14 push plane (operator paging intake, not a confirmd patch), G24 tenant-scoped consumption (the event/inventory journals carry no tenant field yet — the fleet-side dependency of the G19 read path), G25 the sentinel feed spec (the signed audit log has no ship path; spec'd as a consumer contract before the attested channel ships), and G26 the fleet event stream as metering's S4 source (gated on the #376–#378 prerequisites). Each gap carries vision-vs-state, decision, S1–S3 build slices, and composition notes; the filed G21–G26 issues (#795–#800) carry the builds. (#801)

- Fleet update events, first slice (#779): the fleet collector now turns each box's auto-deploy audit tail into a journaled update-event series — what happened, on which box, for which release target — with no box-side change. A failed fleet update is noticed instead of discovered: every collect evaluates four fleet-side alert rules (any `rollback-failed` pages immediately; two or more boxes failing on the same target within 30 minutes flags the bad-release shape; three pre-deployment refusals on one box in six hours flags a stuck box; the silent-wave rule stays deliberately disarmed until waves exist), writing alerts to the operator's fleet journal where `fleet events watch` exits nonzero until they're acknowledged. Check-noop heartbeats stay local by design, and event ids are deterministic so re-collection never duplicates history. (#794)

- muse-job v2 (MSP cutover): dead-model recovery is now implemented and hermetically tested — when a job's model stream dies mid-turn (the stream-idle-timeout shape that previously needed human tmux poking), the harness detects it from the event stream and climbs a recovery ladder: interrupt the zombie turn, start a continuation re-anchored on the job's progress log, resume the session fresh if it will not take a turn, and page the operator only when every rung fails. (#226)

- muse-job v2 (MSP cutover): the CLI now drives jobs over the protocol — `muse-job spawn` starts a job as a `muse serve` session by default (`--tmux` opts back into the legacy tmux TUI pane), and `steer`, `status`, `log`, `kill`, `resume`, `close`, and `watch` all branch on the job's recorded transport, so MSP and tmux jobs can run side by side. Status and the watchdog fold the serve event stream into job states (working, blocked on approval or input, stalled, turn failed); the watchdog runs the dead-turn recovery ladder automatically on stalled jobs; `log` shows the redacted signal journal rather than transcript text. The tmux path is unchanged as the `--tmux` fallback; the Muse Code delegation playbook documents both transports. (#227)

- muse-job v2 (MSP cutover): the view-plane layer is now implemented and hermetically tested — job liveness and state (working, blocked on approval or input, stalled, idle, turn failed) now derive from the `muse serve` event stream instead of scraping a terminal, with gapless replay from a per-job cursor and automatic re-seeding when the server reports dropped events. The status/watch rewire stays a later cutover slice (#227). (#224)

- Contributor DX: the pre-deploy gate's test-file coverage pin now leads with the fix when it fails — both mismatch failures state the actionable fix site on the failure's first line instead of after unittest's list-diff output, so the next contributor sees what to edit without scrolling past the diff. (#781)
- Tenant-box update channel, cluster close-out (G11–G20): a composition audit across the ten update-channel design docs finds no contradictions — fail-closed gating, the two-part freeze bound, the pinned provisioned trust root, chain-safe journal retention, and never-interrupt-an-arc are stated identically everywhere they appear — and closes the five design issues that had shipped with pointer comments (#555 trust model, #556 idle/suspend, #606 rollout controller, #609 release-gating channel, #660 audit retention). The remaining work is tracked on five new implementation issues: trust-model slices (#775), idle/suspend slices (#776), rollout controller plus gate channel (#777), retention GC plus the tenant read path (#778), and the orphaned fleet inventory and event-reporting slices (#779) — implementation-only except one design remainder, the signed box-to-control-plane channel mechanism, which is designed inside #775's S3. (#780)
- Desktop health now sees the wedged-keyboard failure: the desktop bridge's status endpoint reports the keyboard input path's liveness alongside driver health — an on-demand echo check (a harmless key tap watched for its return) classifies the input path as live, wedged, or inconclusive, so a silently dead keyboard no longer hides behind a healthy driver report. The plain health check stays side-effect free (it serves the last probe outcome); the probe itself runs only when asked, and an inconclusive probe never masquerades as a wedge. (#770)
- Competitor watch, 2026-10-02 morning (cycle 59): one new vendor-confirmed competitor entry — DigitalOcean's Agent Droplets (a new monthly-price SKU bundling its microVM sandbox runtime, the inference engine with DigitalOcean-hosted open models like Kimi K3 and GLM 5.3, and the action gateway's 16,000+ governed tools; unlimited agents, no seat charges; Pro/Team 15%/20% discounts; $5 no-card trial — flat monthly packaging against its existing per-hour harness pricing, directly relevant to spark-vm's provider price comparison). All vendor baselines re-verified (Daytona V0.220.0 still top; Vercel changelog through Oct 1 with three new non-sandbox entries and no Drives GA entry; Modal's egress billing live-in-effect the day after its Oct-1 effective date; AgentComputer still publishes no egress pricing). Watch-doc deltas only: Microsandbox v0.7.6 (a maintenance-only patch — lockfile refresh and release bump, no features or fixes) and the Vercel changelog's three new Oct-1 entries. Also in this pass: a Reuters report with Modal's CTO on the record about the July incident — the compromise came through the customer's own unauthenticated code-execution endpoint, not a Modal platform or isolation failure — so that watch-out is answered on the record; a first-party Cloudflare Containers "rebuilt for agents" announcement (~Sept 30 — 6x faster startup, filesystem snapshots in public beta, classes frozen after Dec 31, 2026) that predates the window and stays unfiled; the Modal $750M / Baseten ~$26B rounds still unclosed; Vercel Drives GA still unannounced. (#861)
- The wedged-keyboard probe now runs on a schedule instead of only when asked: the desktop keepalive requests a fresh probe every ~30 minutes and records each verdict in the probe history, so a wedged input device accumulates operational history in production; the desktop status command surfaces the last probe verdict for operators. Automatic restart of the desktop stack on a sustained wedge is implemented but stays off by default (opt in with `CUA_KEEPALIVE_WEDGE_RESTART=1`) until the probe history justifies it — three consecutive wedged verdicts restart at most once per hour, a healthy probe resets the count, and an inconclusive probe never counts toward the wedge. (#783)
- Operator docs: the human-approval component ships a README — what the tailnet confirmation page does, how approvals are filed, answered, expired, and re-opened, the filing-directory contract the deploy must satisfy (setgid `pending/`, owner-only filings), and the security properties an operator inherits (Tailscale-identity auth, server-side CSRF nonce ring, one-decision-per-item locking). (#768)
- Contributor DX: the job turn-steering client's test suite now pins the behaviors its review left unproven — the event watcher filters other sessions' events, ignores malformed notifications instead of raising on the reader thread, and doesn't end the watch on another turn's terminal event; unmapped server errors surface unchanged rather than being relabeled; cancelling a running turn's id fails loudly; and the smoke CLI's `--watch` flag warns instead of watching nothing when no turn id is given, and returns at its timeout after interrupt/cancel. The `--watch` help now states the interrupt/cancel caveat honestly (the terminal event fires during the call, before the watcher subscribes), and two dead code paths are gone (the unused test helper, the unreachable bool check in prompt validation). (#767)
- Stream-ownership semantics designed for live machine control (#178): a new design doc decides who owns the mouse when a Muse and a human both open the desktop — exactly one interactive driver per desktop stream (a second claim goes through an explicit handoff, never a silent takeover), view-only watchers as a first-class seat, per-session terminal streams with no shared-driver contention, and a session-scoped, expiring, revocable auth binding for every stream session with every transition audited. The approvals-model evolution it implies (discrete approvals to long-lived session grants) is routed to the confirmd multi-tenant work, not built here. Implementation stays on the issue. (#766)
- Job TUI auto-updates now defer while a job is active (#699): the agent runtime's launcher auto-update is suppressed inside every job TUI (spawn, resume, and the resume-fallback relaunch), so an in-place update can no longer restart the TUI mid-turn and kill in-flight work — this decides the deferred policy half of the earlier `tui-updated` detection. Updates still flow on the box (the operator's own runs stage them at the normal cadence); the watchdog's `tui-updated` event stays as the diagnostic for updates staged by any concurrent run outside the job, and for the honest residual that a same-user run can still stage an update into the shared install dir. (#765)
- Job turn steering over the new protocol, first slice (#223): the operator tooling gains a turn-steering client for the `muse serve` protocol — starting a turn with a prompt, steering a follow-up message into a live turn, interrupting a running turn, and cancelling a queued one — replacing the tmux send-keys dance (no more swallowed Enters or paste verification). Prompts travel as a single structured message rather than typed text, and steering into a session with no live turn fails loudly instead of pretending it landed; waking a session whose model died stays a separate issue (#226). (#763)
- Contributor DX: the proxy's host matching is now a single shared module — the enforcement matcher and the allowlist parser live in one stdlib-only file that both the proxy and the provision-time injector import, so the two can no longer drift apart (the injector's hand-kept copy and its drift tripwire are retired; the test suite now pins the shared module's behavior directly). No behavior change: the matcher is byte-identical to what the proxy enforced before. The deploy tooling covers the new file too: the rollback manifest snapshots it with the proxy, and both the manual deploy and the auto-updater now verify the proxy actually loaded its enforcement code after a restart (a proxy that silently lost its filtering while its health checks stay green now fails the deploy instead). (#759)
- Relay session liveness, first slice (hosted control plane, #486): the control plane gains the bounded session-frame journal module (producer contract) for tenant SSH session frames — timing and counters only, never session content — and can ask whether a box's path is active, idle, or closed. Probe handshakes are excluded at the journal so the synthetic dial prober can never evidence itself as tenant traffic. The rotation bound is the journal's own contract (no unbounded spool, ever), and an unknown box reads as no-data rather than a healthy verdict. Relay-daemon emit wiring, the dial prober (R2), and tenant-status wiring (R3) stay on the issue. (#755)
- Contributor DX: four carried review notes closed — the credential UI's auto-refresh no longer wipes an in-flight "add host" form when a poll fails (the error banner only replaces the list when nothing inside it is focused), the "no such file or directory" store check is anchored on the missing file's own path so other tools' stderr can't false-positive it, and the approval daemon's stderr fallback (when the audit log itself can't be written) is now pinned by a test proving a hostile login lands as one sanitized line, never a forged entry. (#751)
- Competitor watch, 2026-09-30 morning (cycle 57): the OpenAI DevDay keynote is graded and resolved (C68 — Dots, ChatGPT Space, GPT-6.1 Sol, the Agents API public beta, and Ultrafast all confirmed; only the leaked "o" name was wrong). Two new agent-compute entries join the corpus — OpenAI's Dots (C70) and Codex Cloud (C71) — plus a C69 filing for the DevDay's new Agents API details (hosted execution, computer use), building on the earlier beta filing. Also in this pass: Daytona V0.220.0, the Modal $750M / Baseten ~$26B rounds still unclosed, Modal egress billing confirmed still pre-effective (goes live 2026-10-01), and Vercel Drives GA still unannounced. (#750)
- Migration-tooling input hardening design (G20, #661): a new design doc sets the bar for the update path's migration step, which runs against tenant data that must be treated as attacker-influenced — every migration input is validated against a declared schema before anything is written, parsers are bounded and never evaluate tenant data, the layout version is checked first with declared version jumps only, migrations run in two phases (validate everything, then commit) so a failure lands the box in `box-unhealthy` with the honest `detail: maintenance-failed: migration:<reason>` instead of a half-migrated one, migration always executes inside the new guest (never on the provisioner host), and the blast radius is stated plainly — a poisoned migration can only break the tenant's own box, so this is defense-in-depth, not a trust fix. Implementation stays on the issue. (#749)
- Job event logs now rotate themselves: when a job's hook event file passes 4 MB, the watch pass archives it and starts a fresh one, so the 2 MB scan window is no longer the only thing standing between a busy job and an unreadable log. Terminal `done` claims are carried into the fresh file, so a finished job's claim keeps paging after rotation instead of going quiet, and each rotation is announced as its own watch signal. (#745)
- Secrets posture, documented: the secrets-posture guide now records the human-context boundary on direct secret reads — the browser secret-filler refuses to run outside a real terminal unless the operator explicitly opts in, because it loads the real value into process memory; the agent path stays placeholders-at-egress, and the doc names the boundary's honest limit (pseudo-terminals pass, so agents are still kept out by policy, not by this check) plus the two open residuals. (#741)
- Contributor DX: the pre-deploy gate's test-file coverage pin got sharper — registered test paths must be repo-relative (a path escape fails the pin loudly instead of walking the wrong tree), a newly added gate component must declare its exact registered-file count in the pin before it counts as covered, and both mismatch failure messages now name the exact fix site (the component's test-file list in the deploy config) so the next contributor knows what to edit without re-diagnosing. (#740)
- Update audit retention and tenant read access design (G19, #660): a new design doc answers the trust model's two owed decisions — how long the control-plane update journal keeps per-box update records (a 90-day tenant-queryable window at full fidelity, a 1-year operator-only window, and a 2-year floor for security-channel records; nothing is ever pruned while a retained record still references it, and pruning is accounted for openly so a tenant never mistakes an aged-out window for a silent update), and what the tenant Muse may read through its own update-history view (its own box's records only, verifiably complete via per-tenant sequence numbers, and never naming another tenant). Implementation stays on the issue. (#739)
- The job session client now documents which of its test server's behaviors were verified on the wire versus stand-ins the tests invented (the "not loaded" record's pending-requests list, the resume history entry shape, the approval-change event's source field), and states plainly that starting a session has no reasoning-effort knob — the model id is the only model-related setting the wire shape carries. It also proves end to end (through the transport, not just unit tests) that a malformed server response fails loudly instead of being silently accepted, and the command-line client's resume and read commands now have their own smoke tests. (#735)
- Push notification docs now state who runs the operator commands: key generation, test-push, and the worker runbook run from a root shell — the `sudo -u swapd` hop is root's unrestricted step down to the secrets owner, not a narrow-grant escalation. They are denied under the narrow agent sudo grants by design (no `python3` rule exists — that would be arbitrary code as the secrets owner), and dropping the hop is wrong too: the key and queue files must land swapd-owned or the push worker can't read them. (#729)
- Contributor DX: two test gaps closed — the session-list client's pagination bounds are now proven at the valid edges (the smallest and largest allowed page sizes are pinned to actually return sessions, not just to reject bad input), and the credential-registry loosening advisory is pinned to fire only when a loosening actually happened (a failed operation against a missing credential or entry stays silent instead of printing an advisory for a no-op). (#728)
- Fleet→box release-gating channel design (#609): a new design doc specifies how the rollout controller's wave and freeze decisions actually reach the boxes — a controller-signed, short-lived permission document the box pulls over the operator's own sync path (no new daemon, no new inbound port), with each box deciding for itself which wave it's in; a small box-side hook caps both updaters at the newest version the fleet permits and fails closed (a missing, expired, or badly signed document means the box holds — it never drifts silently forward), and the doc states the freeze-latency bound honestly in two parts — the frozen document reaches every box within the sync cadence, and a freeze stops the fleet within one sync cadence plus one update tick of being published. Controller keys rotate without a flag day, and the install writes the box's identity onto the box so the wave lookup actually runs. Built for the operator's own multi-box estate first; the hosted instantiation keeps the channel scheduler-facing per the tenant update trust model (no gate runs on tenant boxes). Implementation stays on the issue. (#609)
- The desktop bridge's app launcher now guards against duplicate launches: it records every process it spawns per app (dead PIDs pruned on every read), shows the running set in the health endpoint so the control panel can decide for itself, and honors an opt-in `"singleton": true` on launch requests that refuses with HTTP 409 while an instance is still alive. Default launches are unchanged — a second terminal is still one request away. (#721)
- The multi-tenancy audit's assumption inventory is current again: its credential-UI and swap-proxy rows now record the systemd sandboxing that shipped today (private /tmp, a read-only OS tree except the one writable path the components need, no privilege acquisition for the proxy services) instead of claiming the services harden nothing — while keeping the still-open halves in place, since the credential UI still has no user authentication and any local process can still spend any active swap grant. (#719)
- Update event reporting design (G17, #608): a new design doc specifies the standard shape every box-side update attempt is reported in — the outcome vocabulary (started, deferred, succeeded, failed, rolled back, rollback-failed, superseded), per-(box, session, build) keying so reimages reset soak evidence, and an attestation flag for the tenant-fleet instantiation — plus the translation of the updaters' existing audit lines into that shape, covering all fifteen audit result shapes the deployer emits. Delivery comes in three slices: S1 canonicalizes fleet-side at collect time with no box-side change and adds fleet alert rules (any stuck rollback, correlated failures across boxes, repeated precheck failures) so a failed fleet update is noticed instead of discovered on the next manual session; S2 adds a box-side event journal with the per-wave aggregation the rollout controller's health gates read and the event↔inventory cross-checks; S3 is the hosted control-plane endpoint where G13's attested-admission rule governs gate-consumed events. Built for the operator's own multi-box estate first; the tenant-fleet instantiation additionally waits on the update trust model and the multi-tenancy audit. (#608)
- muse-job v2 (MSP cutover): the session-lifecycle layer is now implemented and hermetically tested — start, resume, list, and read sessions on a `muse serve` host, replacing the tmux-scraping session path slice by slice. Starting a job session takes the workspace plus the wire approval mode (`--yolo` maps to `allowAll`); resume re-attaches to a stored session even after the local client dies; list pages stored sessions without touching leases; read returns a session record without attaching. The CLI spawn/resume rewire stays a later cutover slice (#227). (#222)
- Contributor DX: a new CI test pins the pre-deploy gate's explicit test-file registration — if a new test file lands in a gate-enumerated component without being registered in that component's deploy-gate command, or a registration points at a deleted file, the test fails naming the file. The contributor guide's test-pin paragraph now names all three pins. (#703)
- Update windows vs idle/suspend and the session clock design (G14, #556): the tenant-box update signal `maintenance` is a trusted quiet-clock window for the stall detector — the 30-minute quiet clock freezes during an update (never advances, never resets, and an update window is never labeled a stall), a failed or never-cleared maintenance window ages into `box-unhealthy` via a bounded watchdog instead. Suspended boxes are never woken for fleet updates (they update on wake, with the staleness check on the wake path); an interactive dial wakes the box to usable first and the staged update becomes next-cycle wave work, so dial latency is never hostage to a reimage. The 10-minute onboarding clock pauses while the box is suspended and resumes with the remaining time on wake. Contracts for the owning components: the idle detector treats `maintenance` and waiting-on-a-human (pending approvals) as activity and never suspends mid-update, and wake/scheduler events feed no stall-detector input. Implementation slices S1–S3 stay on the issue. (#556)
- muse-job now reports the agent runtime's own auto-updates as their own watchdog event: when the Muse TUI's binary changes under a running job (an in-place auto-update swapping the versioned binary while the session stays up), `watch` emits a distinct `tui-updated` event naming the old and new binaries instead of lumping the aftermath into the dead-TUI signal, so operators can see that an update happened and which pane state the existing recovery signals found afterwards. Detection only — no auto-accept-or-defer update policy is applied yet. (#698)
- Competitor watch, 2026-09-29 morning (cycle 56): fully quiet pass — no new competitor launches, pricing moves, or corpus entries. Re-verified unchanged against the vendors' own pages: the Daytona changelog (still SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox releases (v0.7.4), the Vercel changelog (28 September) and Sandbox docs (still "Drives (beta)" — no general-availability entry in the rendered 24/25/27/28-September window), DigitalOcean and Modal pricing verbatim (Modal's network-egress billing effective Oct 1, 2026 — 2 calendar days after the survey — with no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer verbatim (AgentComputer still publishes no egress pricing line, fifty-sixth consecutive check), the Boat legacy domains, and Hugo's advisories (4 Sep-28 Moderate advisories on top, capped at 10 visible, no CVE-2026-100690 entry on the first-party page). The news scan surfaced no new launches (fifty-first straight quiet scan): a news scan's Prime Sandboxes general-availability candidate turned out to be already covered — Prime Intellect's Prime Sandboxes launch (announced ~2026-09-23; GA plus launch pricing valid through Dec 22, 2026) is already filed and vendor-verified in the corpus, closing the confirm-launch-recency question; a Vercel Drives public-beta detail page found out-of-list corrects the prior pass's "private beta" standing line — Drives is in public beta since 2026-09-23 while GA remains unannounced and stays a tracked item. Also in this pass: the severitydaily.com link-check exclusion added earlier today is removed after the integrator re-opened the flagged article page and confirmed it renders fully (the host outage recovered). The Modal $750M and Baseten ~$26B funding talks are still unclosed (filed only on a first-party close announcement). Flagged but not filed: OpenAI DevDay pre-keynote press (the ~12pm CT keynote had not happened at survey time — only an actual OpenAI announcement is filed; the GPT-6.1 "Astra" cancellation syndication is still pre-keynote press reporting, never filed pre-keynote), a NanoCo $12M seed round for NanoClaw (funding, not a product announcement — below the NanoCo re-grade bar), the alleged Vercel dark-web credential sale (unverified, watch only — distinct from the confirmed April-2026 breach), the Hugo CVE-2026-100690 record on third-party aggregators only (no first-party GHSA advisory), and agent-adjacent funding out of lane. (#697)
- Competitor watch, 2026-09-29 early-morning (cycle 55): fully quiet pass — no new competitor launches, pricing moves, or corpus entries. Re-verified unchanged against the vendors' own pages: the Daytona changelog (still SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox releases (v0.7.4), the Vercel changelog (28 September) and Sandbox docs (still "Drives (beta)" — no general-availability entry in the rendered 24/25/27/28-September window), DigitalOcean and Modal pricing verbatim (Modal's network-egress billing effective Oct 1, 2026 — 2 calendar days after the survey — with no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer verbatim (AgentComputer still publishes no egress pricing line, fifty-fifth consecutive check), the Boat legacy domains, and Hugo's advisories (4 Sep-28 Moderate advisories on top, capped at 10 visible, no CVE-2026-100690 entry on the first-party page). The news scan found no new launches (fiftieth straight quiet scan): the Modal $750M and Baseten ~$26B funding talks are still unclosed (filed only on a first-party close announcement); Vercel Drives GA remains a standing tracked item, not declared dead; Cloudflare's Sept-24 disk-residue disclosure third-party pieces add no new facts beyond the already-filed corpus entry. Flagged but not filed: OpenAI DevDay pre-keynote (the keynote ~12pm CT had not happened at survey time — only an actual OpenAI announcement is filed; the GPT-6.1 "Astra" cancellation syndication is still pre-keynote press reporting, never filed pre-keynote), an alleged Vercel dark-web credential sale (unverified, watch only — distinct from the confirmed April-2026 breach), the Hugo CVE-2026-100690 record on third-party aggregators only (no first-party GHSA advisory), Prime Intellect "Prime Sandboxes" (still no launch date — launch recency unconfirmed, flagged only) and the Prime Intellect SDK VM-only pivot (pre-window publication, below every filing gate), a BAND × Docker Sandboxes third-party integration announcement (not a Docker product delta), a Modal engineering-blog digest (below the launch bar), a NanoClaw × Echo security partnership (below the NanoCo re-grade bar), and agent-adjacent funding out of lane. (#693)
- Competitor watch, 2026-09-29 early-morning (cycle 54): fully quiet pass — no new competitor launches, pricing moves, or corpus entries. Re-verified unchanged against the vendors' own pages: the Daytona changelog (still SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox releases (v0.7.4), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no general-availability entry), DigitalOcean and Modal pricing verbatim (Modal's network-egress billing effective Oct 1, 2026 — 2 calendar days after the survey — with no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer verbatim (AgentComputer still publishes no egress pricing line, fifty-fourth consecutive check), the Boat legacy domains, and Hugo's advisories (4 Sep-28 Moderate advisories on top, capped at 10 visible, no CVE-2026-100690 entry on the first-party page). The news scan found no new launches (forty-ninth straight quiet scan): the Modal $750M and Baseten ~$26B funding talks are still unclosed (filed only on a first-party close announcement); Vercel Drives GA remains a standing tracked item, not declared dead. Flagged but not filed: OpenAI DevDay pre-keynote (the keynote ~12pm CT had not happened at survey time — only an actual OpenAI announcement is filed; a Barron's direct-quote piece on the GPT-6.1 "Astra" cancellation is still pre-keynote press reporting, never filed pre-keynote), an alleged Vercel dark-web credential sale (unverified — one coverage piece now ships its own fact-checker disconfirming the claims, and a SOCRadar Vercel-breach page in the results is the older April-2026 write-up, watch only), the Hugo CVE-2026-100690 record on third-party aggregators only (no first-party GHSA advisory), Prime Intellect "Prime Sandboxes" (a first-party blog with published pricing but still no launch date — launch recency unconfirmed, flagged only), a Docker Sandboxes CVE-2026-77179 note (pre-window publication and fix, below every filing gate — color only), and agent-adjacent funding out of lane. (#691)
- Contributor DX: the tenant onboarding status endpoint's test suite now pins *how* the not-a-tenant rejection works, not just that it returns a 401 — the test records the signature-verification call and asserts verification actually ran (against the stand-in key) before the missing-record check rejected, so a future change that skips verification can no longer hide behind the same passing assertion. (#690)
- Fleet version inventory, first implementation slice (G16): a new `fleet/` component that collects the per-box version signals the self-updaters already emit — the toolset inventory report, the auto-deploy audit tail, and a small box-side snapshot — into one fleet version table with per-release census percentages, per-box version history, and a drift listing that distinguishes policy-held, arc-deferred, and suspect boxes. It reads artifacts you already have (a directory per box, rsync them together); no new daemon, no new inbound port, no control plane required. The push endpoint, rollout-gate integration, and attested reports stay later slices. (#715)
- Fleet version inventory design (G16): a new design doc covers the collector and store the rollout controller's health gates read — what each box is actually running (repo commit, toolset pins, image version) with per-box version history, pull-first collection for your own multi-box setup plus push when a control plane exists, definitions for "which boxes missed the update window" and drift, and a trust story where self-reported versions are cross-checked (tenant-fleet gates only admit attested reports). Implementation slices S1–S3 stay on the issue. (#688)
- Competitor watch, 2026-09-29 early-morning (cycle 53): fully quiet pass — no new competitor launches, pricing moves, or corpus entries. Re-verified unchanged against the vendors' own pages: the Daytona changelog (still SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox releases (v0.7.4), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no general-availability entry), DigitalOcean and Modal pricing verbatim (Modal's network-egress billing effective Oct 1, 2026 — 2 calendar days after the survey — with no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer verbatim (AgentComputer still publishes no egress pricing line, fifty-third consecutive check), the Boat legacy domains, and Hugo's advisories (4 Sep-28 Moderate advisories on top, capped at 10 visible, no CVE-2026-100690 entry on the first-party page). The news scan found no new launches (forty-eighth straight quiet scan): the Modal $750M and Baseten ~$26B funding talks are still unclosed (filed only on a first-party close announcement); Vercel Drives GA remains a standing tracked item, not declared dead. Flagged but not filed: OpenAI DevDay pre-keynote (the keynote ~12pm CT had not happened at survey time — only an actual OpenAI announcement is filed; a Barron's direct-quote piece on the GPT-6.1 "Astra" cancellation is still pre-keynote press reporting, never filed pre-keynote), an alleged Vercel dark-web credential sale (unverified — one coverage piece now ships its own fact-checker disconfirming the claims, watch only), the Hugo CVE-2026-100690 record on third-party aggregators only (no first-party GHSA advisory), and Prime Intellect "Prime Sandboxes" (a first-party blog with published pricing but no launch date — launch recency unconfirmed, flagged only). (PR #689)
- Competitor watch, 2026-09-29 early-morning (cycle 52): fully quiet pass — no new competitor launches, pricing moves, or corpus entries. Re-verified unchanged against the vendors' own pages: the Daytona changelog (still SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox releases (v0.7.4), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no general-availability entry), DigitalOcean and Modal pricing verbatim (Modal's network-egress billing effective Oct 1, 2026 — 2 calendar days after the survey — with no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer verbatim (AgentComputer still publishes no egress pricing line), the Boat legacy domains, and Hugo's advisories (4 Sep-28 Moderate advisories on top, capped at 10 visible, no CVE-2026-100690 entry on the first-party page). The news scan found no new launches: the Modal $750M and Baseten ~$26B funding talks are still unclosed (filed only on a first-party close announcement); Vercel Drives GA remains a standing tracked item, not declared dead. Flagged but not filed: OpenAI DevDay pre-keynote speculation (the keynote ~12pm CT had not happened at survey time — only an actual OpenAI announcement is filed; a third-party report of a canceled "Astra" model is not one), an alleged Vercel dark-web credential sale (unverified — watch only), and the Hugo CVE-2026-100690 record on third-party aggregators only (no first-party GHSA advisory). (PR #685)
- Competitor watch, 2026-09-29 late-night (cycle 51): fully quiet pass — no new competitor launches or corpus entries. Re-verified unchanged against the vendor's own pages: the Daytona changelog (still SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox releases (v0.7.4), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no general-availability entry; Vercel Drives GA remains a standing tracked item, not declared dead), DigitalOcean and Modal pricing (Modal network-egress billing takes effect Oct 1, 2026 — 1 day after the survey — no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, fifty-first consecutive check), the Boat legacy domains (both domains and both Y Combinator listings still serving natively), and the Hugo security advisories (still capped at 10 visible, no 100690-specific advisory). The Modal $750M and Baseten ~$26B funding talks remain unclosed ("nearing"/"in talks" syndication only). Flagged but not filed: OpenAI DevDay pre-keynote speculation (the Sep-29 ~12pm CT keynote had not happened at survey time — only an actual OpenAI announcement is filed); an alleged Vercel dark-web credential sale (the coverage itself states the listing is unverified — watch only); the Hugo CVE-2026-100690 record on third-party aggregators only (file on a first-party GHSA advisory). (#684)
- Competitor corpus update (late-night watch, 2026-09-29, cycle 50): fully quiet cycle — zero first-party deltas across all nine vendor baselines (Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes release notes 2026-09-22, Microsandbox v0.7.4 baseline-stable, Vercel changelog/docs still "Drives (beta)" with no GA entry, DigitalOcean and Modal pricing verbatim — Modal egress billing effective Oct 1, 2026 (2 calendar days after the survey), no went-live-early signal — E2B/boat.dev/TermSquad/AgentComputer verbatim, Boat legacy domains migration-complete, Hugo advisories capped at 10 visible with no 100690-specific entry); fiftieth consecutive first-party read with no AgentComputer egress pricing line (C12 stays OPEN). The news scan surfaced no new competitor launches (forty-fifth straight quiet B-lane scan): the Modal/Baseten funding talks are still unclosed (C11 FILE ON CLOSE stays armed). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead). No new corpus mints, re-folds, or age-outs. Flagged but not filed: OpenAI DevDay pre-keynote speculation ("o" always-on-assistant and GPT-6 roundups — keynote Sep 29 ~12pm CT had not happened at survey time, only an actual OpenAI confirmation files C68); an alleged Vercel dark-web credential sale (UNVERIFIED — Vercel unconfirmed, watch only); the Hugo CVE-2026-100690 record on third-party aggregators only (no first-party GHSA — file-on-GHSA-only gate unmet). Integrator note: the fuller in-window record scopes the folded Sept-28 NVIDIA event (C70) as a platform launch (OpenShell runtime + Sentry hardware watchdog) — recorded as a standing note, corpus stays append-only. (#681)
- Tenant onboarding status poll: the hosted control plane now serves the machine-readable onboarding status that both the tenant's agent and the signup page poll during setup — one status endpoint carrying the onboarding arc (provisioning, waiting-on-approval, live, and the rest of the vocabulary), the approvals-page link, and per-step sub-codes, with the transition rules enforced so the arc can never move backwards. The linked agent key and the magic-link session are the two accepted credentials; unauthenticated requests get a 401 and records not yet past signup stage 2 get a 404. (#680)
- Competitor corpus update (late-night watch, 2026-09-29, cycle 49): fully quiet cycle — zero first-party deltas across all nine vendor baselines (Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes release notes 2026-09-22, Microsandbox v0.7.4 baseline-stable, Vercel changelog/docs still "Drives (beta)" with no GA entry, DigitalOcean and Modal pricing verbatim — Modal egress billing effective Oct 1, 2026 (2 calendar days after the survey), no went-live-early signal — E2B/boat.dev/TermSquad/AgentComputer verbatim, Boat legacy domains migration-complete, Hugo advisories still capped at 10 visible with no 100690-specific entry); forty-ninth consecutive first-party read with no AgentComputer egress pricing line (C12 stays OPEN). The news scan surfaced no new competitor launches (forty-fourth straight quiet B-lane scan): the Modal/Baseten funding talks are still unclosed (C11 FILE ON CLOSE stays armed). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead). No new corpus mints, re-folds, or age-outs. Flagged but not filed: OpenAI DevDay pre-keynote leaks ("O" always-on-assistant speculation and GPT-6 roundups — keynote Sep 29 ~12pm CT had not happened at survey time, only an actual OpenAI confirmation files C68); an alleged Vercel dark-web credential sale (UNVERIFIED — Vercel unconfirmed, watch only); the Hugo CVE-2026-100690 record on third-party aggregators only (no first-party GHSA — file-on-GHSA-only gate unmet); a webpronews Docker Sandboxes ecosystem analysis (single third-party source — CNCF-handoff aspect stays C26 watch-only). (#674)
- Competitor corpus update (late-night watch, 2026-09-29, cycle 48): fully quiet cycle — zero first-party deltas across all nine vendor baselines (Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes release notes 2026-09-22, Microsandbox v0.7.4 baseline-stable, Vercel changelog/docs still "Drives (beta)" with no GA entry, DigitalOcean and Modal pricing verbatim — Modal egress billing effective Oct 1, 2026 (2 calendar days after the survey), no went-live-early signal — E2B/boat.dev/TermSquad/AgentComputer verbatim, Boat legacy domains migration-complete, Hugo advisories still capped at 10 visible with no 100690-specific entry); forty-eighth consecutive first-party read with no AgentComputer egress pricing line (C12 stays OPEN). The news scan surfaced no new competitor launches (forty-third straight quiet B-lane scan): the Modal/Baseten funding talks are still unclosed (C11 FILE ON CLOSE stays armed — bytevyte on the record that neither round has closed). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead). No new corpus mints, re-folds, or age-outs. Flagged but not filed: OpenAI DevDay pre-keynote leaks ("O" always-on-assistant speculation — keynote Sep 29 ~12pm CT had not happened at survey time, only an actual OpenAI confirmation files C68); an alleged Vercel dark-web credential sale (UNVERIFIED — Vercel unconfirmed, watch only); the Hugo CVE-2026-100690 record on third-party aggregators only (no first-party GHSA — file-on-GHSA-only gate unmet); a BAND × Docker Sandboxes third-party integration (pre-window). (#673)
- Competitor corpus update (late-night watch, 2026-09-29, cycle 47): fully quiet cycle — zero first-party deltas across all nine vendor baselines (Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes release notes 2026-09-22, Microsandbox v0.7.4 baseline-stable, Vercel changelog/docs still "Drives (beta)" with no GA entry, DigitalOcean and Modal pricing verbatim — Modal egress billing effective Oct 1, ~2 days out, no went-live-early signal — E2B/boat.dev/TermSquad/AgentComputer verbatim, Boat legacy domains migration-complete, Hugo advisories still capped at 10 visible with no 100690-specific entry); forty-seventh consecutive first-party read with no AgentComputer egress pricing line (C12 stays OPEN). The news scan surfaced no new competitor launches (forty-second straight quiet B-lane scan): the Modal/Baseten funding talks are still unclosed (C11 FILE ON CLOSE stays armed — bytevyte on the record that neither round has closed). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead). No new corpus mints, re-folds, or age-outs. Flagged but not filed: the DevDay agent-launch rumors (pre-keynote leak/speculation — keynote Sep 29 ~12pm CT had not happened at survey time, only an actual OpenAI confirmation files C68 — plus the predated OODAloop piece that must not be confused for a confirmation); a third-party Modal customer-data-compromise framing (July-vintage incident, not a new event — watch only); unverified third-party sandbox-escape claims; a single-third-party-source assertion that Docker handed the Sandbox Kit Spec to the CNCF (watch only, no first-party confirmation); an alleged Vercel dark-web credential sale (still unverified — watch only). (#668)
- Tenant data-export design (H31, user-directed): the hosted equivalent of "Download your agent data" — scope covers the tenant's files, agent state, approval/status/audit history, and explicitly excludes real secret values (the credential store's values are human-only; exports carry the `hsurr:` placeholders as-is). The export is a bundle — a plaintext manifest plus one or two tenant-key-encrypted payload archives (box payload assembled box-side, control-plane payload attached at delivery) — and the same manifest schema works on self-hosted boxes, which simply have no control-plane sections, so exports stay byte-shape-compatible across tracks. Signed request auth for the tenant Muse or the human (the human is notified on every request and on readiness, whoever asked); box-side assembly gated on box liveness (suspended boxes queue — Muse-requested exports never auto-wake; the human gets an explicit opt-in "wake and export" with the cost shown); bounded operator-side storage and single-use short-TTL download URLs. Build slices S1–S3; open questions include export-then-delete ordering and approval-history redaction. (#665)
- Competitor corpus update (late-night watch, 2026-09-29, cycle 45): fully quiet cycle — zero first-party deltas across all nine vendor baselines (Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes release notes 2026-09-22, Microsandbox v0.7.4 now baseline-stable, Vercel changelog/docs still "Drives (beta)" with no GA entry, DigitalOcean and Modal pricing verbatim — Modal egress billing effective Oct 1, ~2 days out, no went-live-early signal — E2B/boat.dev/TermSquad/AgentComputer verbatim, Boat legacy domains migration-complete, Hugo advisories still capped at 10 visible with no 100690-specific entry); forty-fifth consecutive first-party read with no AgentComputer egress pricing line (C12 stays OPEN). The news scan surfaced no new competitor launches (fortieth straight quiet B-lane scan): the Modal/Baseten funding talks are still unclosed (C11 FILE ON CLOSE stays armed). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead). No new corpus mints, re-folds, or age-outs. Flagged but not filed: the DevDay agent-launch/GPT-6 rumors (pre-keynote leak/speculation — keynote Tue Sep-29 ~12pm CT had not happened at survey time, only an actual OpenAI confirmation files C68 — plus a predated OODAloop piece that must not be confused for a confirmation); adjacent-infra funding wave (Crusoe, Verda, Snorkel AI, Micro1, DeepSeek — out of lane); NanoClaw news (March-vintage recirculation; the NanoCo re-grade bar stays unmet); an alleged Vercel dark-web credential sale (still unverified — watch only). (#666)
- Competitor corpus update (late-night watch, 2026-09-29, cycle 46): fully quiet cycle — zero first-party deltas across all nine vendor baselines (Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes release notes 2026-09-22, Microsandbox v0.7.4 baseline-stable, Vercel changelog/docs still "Drives (beta)" with no GA entry, DigitalOcean and Modal pricing verbatim — Modal egress billing effective Oct 1, ~2 days out, no went-live-early signal — E2B/boat.dev/TermSquad/AgentComputer verbatim, Boat legacy domains migration-complete, Hugo advisories still capped at 10 visible with no 100690-specific entry); forty-sixth consecutive first-party read with no AgentComputer egress pricing line (C12 stays OPEN). The news scan surfaced no new competitor launches (forty-first straight quiet B-lane scan): the Modal/Baseten funding talks are still unclosed (C11 FILE ON CLOSE stays armed — bytevyte now on the record that neither round has closed). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead). No new corpus mints, re-folds, or age-outs. Flagged but not filed: the DevDay agent-launch/GPT-6 rumors (pre-keynote leak/speculation — keynote Sep 29 ~12pm CT had not happened at survey time, only an actual OpenAI confirmation files C68 — plus the predated OODAloop piece that must not be confused for a confirmation); an OpenAI training pause after a sandbox escape (Sep 25 — adjacent AI-safety news, out of lane); adjacent-infra funding wave (out of lane); NanoClaw news (vintage recirculation; the NanoCo re-grade bar stays unmet); an alleged Vercel dark-web credential sale (still unverified — watch only). (#667)
- Contributor DX: the contributor guide's test-suite table now lists per-component run commands and dependency notes instead of an exhaustive per-file suite list — the old per-file list had drifted badly (it claimed the scripts component had one suite while a real image-processing test dependency went unlisted). A new CI test fails if the table and the pytest suite inventory disagree in either direction, so the docs can't drift again. Also pinned: the credential CLI's stdin read rejects invalid UTF-8 with the same error the old text-mode read raised, documenting the deliberate behavior preservation. (#664)
- Tenant-box update trust model design (G13, #555): who authorizes a tenant-box reimage (operator release registration, the fleet controller acting within registered policy, the operator's freeze/halt/promote emergency surface, and the control-plane scheduler executing it — the tenant Muse, the box itself, and merge-to-main alone are all explicitly excluded), a control-plane audit journal with per-tenant attribution (never box-side, since the tenant holds root inside the guest), a threat-by-threat analysis of the tenant Muse with shell on the box, and two new residuals — G19 audit retention + tenant read-path access policy (#660) and G20 migration-tooling input hardening (#661). (#662)
- Competitor corpus update (late-night watch, 2026-09-29, cycle 44): one first-party delta — Microsandbox v0.7.4 (chore bump + SDK rename + release/network/filesystem fixes; maintenance-grade, below the mint bar — no corpus fold); the other eight vendor baselines re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing effective Oct 1 — ~2 days out from survey, 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, forty-fourth consecutive read), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (nineteenth consecutive capped render, visible list matches baseline). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead — Vercel has not cancelled GA; its own surfaces simply still show beta/private-beta). The news scan surfaced no new competitor launches (thirty-ninth straight quiet B-lane scan): the Modal/Baseten funding talks are still unclosed (syndications still "nearing"/"talks" framing — nearing is not closed). Flagged but not filed: the DevDay agent-launch/GPT-6 rumors (pre-keynote leak/speculation — keynote Tue Sep-29 ~12pm CT had not happened at survey time, only an actual OpenAI confirmation files C68); a Docker Cloud Sandboxes recap wave (pre-window Sep-24 launch recirculation); NanoClaw×Vercel/OneCLI and NanoClaw+Echo partnerships (not sandbox/compute launches — the NanoCo re-grade bar stays unmet); an alleged Vercel dark-web credential sale (still unverified — watch only); frontier-lab model rumors (out of lane). (#663)
- Competitor corpus update (late-night watch, 2026-09-29, cycle 43): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing effective Oct 1 — ~2 days out, 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, forty-third consecutive read), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (eighteenth consecutive capped render, visible list matches baseline). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead — Vercel has not cancelled GA; its own surfaces simply still show beta/private-beta). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (syndications still "nearing"/"talks" framing — nearing is not closed), Baseten's "Carbon" is still a private preview, and the Nvidia Open Agent Safety Platform coverage wave is recirculation of an already-folded launch. Flagged but not filed: the OpenAI DevDay agent-launch rumor (pre-keynote leak/speculation — keynote Tue Sep-29 ~12pm CT, only an actual OpenAI confirmation files); Docker Sandboxes security-fix detail and pre-release versions surfacing via docs mirrors (below the GA bar — watch only); an alleged Vercel dark-web credential sale (still unverified — not two independent reputable sources, watch only); NanoClaw news (March-2026-vintage Docker partnership recirculation; the NanoCo re-grade bar stays unmet); frontier-lab model rumors (out of lane). (#658)

- Contributor DX: the fleet inventory suite now pins four previously empirical regression paths — corrupt box-side snapshots are noted rather than fatal, non-object snapshots are ignored loudly, a torn or wrong-schema store snapshot fails readers with a clean exit 2, and the pull-only contract (collect never writes to the estate) is checksum-verified. The suite's module docstring also drops the overclaimed "hermetic" wording for the honest "no network, no home-dir writes". (#718)
- Job liveness from the session's own event stream, first slice (#224): the operator tooling gains a view-plane client for the `muse serve` protocol — subscribing at a cursor replays a session's recent events and then follows them live, deriving a working / blocked / idle / stalled state (a pending approval or question is surfaced when blocked; a session silent with no live turn for ten minutes reads as stalled). This is the pane-scraping replacement that `muse-job status` and `watch` will read once the transport cutover lands; the old TUI probes stay until then. (#772)

### Changed
- Contributor DX: the push-sender test suite's local stub server now shuts down on a 50 ms poll interval instead of the half-second default — the stub's per-test teardown was paying up to half a second each, about ten seconds a run, so the whole suite runs noticeably faster for contributors and in CI. A new test pins the short interval so a future edit can't silently restore the default. (#1066)
- Contributor DX: the fleet journal loader no longer carries a dead parameter every caller passed as empty — the five load sites read plainly now; no behavior change. (#823)

### Fixed
- The provision-time injector's smoke-host scoping step now sweeps crash-orphaned `.smoke-hosts.*` temp files older than one hour before writing the new list — a kill between the temp file's creation and its atomic rename previously left orphans in the live proxy config directory forever. A live writer's seconds-old temp file is never touched. (#841)
- The SSH-key account registry now sweeps the temporary publish files a crashed write leaves behind (previously they accumulated forever, one per interrupted write), and deleting an account now records the deletion — who, which key, when, and the record's lineage — in a bounded audit journal, so a deleted account is never confusable with one that never existed. The first-connect manifest's policy section also describes the shipped rotation and claim mechanics instead of the old "not-implemented" wording. (#828)
- The waitlist's data store no longer silently loses a corrupted entry: when the service loads the waiting list and finds a torn or malformed line (a crash mid-write can tear one), it now quarantines those exact bytes to a timestamped sidecar file before any purge or deletion rewrites the store — previously the rewrite would have dropped the unreadable line permanently with no trace, so a single bad byte next to an unrelated row could have erased that row on the next cleanup. The quarantined bytes are never trusted as data; they sit in the data directory for the operator to inspect or hand-repair, and the service logs where they went. (#829)
- The repo's component table is complete again: the README now lists `fleet/` (fleet management — version inventory, event and alert journals, retention pruning) and `hosted/` (the hosted control plane's tenant layer — the machine-readable onboarding status at `GET /tenant/status`), two shipped components the table had been missing. (#822)
- The fleet's event and alert journals can no longer be corrupted by overlapping runs on the same host: collecting fleet state twice at once (two collect crons overlapping, or a collect racing an operator's alert acknowledgment) used to duplicate event and alert rows or silently drop an acknowledgment. The journal writes now serialize behind a store-scoped lock — an overlapping run waits its turn, so re-collection stays a true no-op and every acknowledgment sticks. A store shared across multiple hosts still needs its own design. (#817)
- Jobs no longer die silently at the workspace-trust gate: spawning a job now answers the "Do you trust this workspace?" prompt right after the first launch (the same standing authorization the resume path already used), and the watchdog treats a trust-prompt pane as its own signal — it answers the gate and reports `trust-answered` when the session goes live, or pages a loud `blocked-trust` with the exact remedy when the gate is still showing, instead of stranding the job behind a generic dead-pane report. (#816)
- The jail's guest SSH sessions no longer carry a hardcoded proxy address: the guest's `~/.ssh/environment` (which non-interactive SSH commands read, skipping the usual profile setup) now takes the proxy address from the host's configured veth IP like every other guest artifact, failing the build loudly if the address is missing — so a future veth-IP change can't leave SSH sessions pointing at a dead proxy while everything else moves. (#816)
- The codec-licensing research sources no longer point at a dead importer README: the AOMedia Patent License 1.0 is now cited from the Alliance for Open Media's own license page, after the importer repo went offline. (#812)
- The desktop keepalive's bridge restart probe no longer confuses a slow desktop driver with a dead bridge: the keepalive used to health-check the bridge through the full status endpoint, which shells out to the driver with a 10-second budget — on a loaded box the driver's slowness exceeded the keepalive's 5-second check and the keepalive restarted a healthy bridge. The bridge now serves a dedicated liveness endpoint that answers without touching the driver, and the keepalive probes that instead; the full status endpoint keeps its driver detail for dashboards and operators. (#805)
- The job watchdog no longer resurrects phase jobs the operator deliberately killed: `watch` now defers the auto-recovery of a `phase-*` job while any other `phase-*` job has a live session, emitting a `deferred` signal instead of `recovered` — so the one-phase-job-at-a-time rule holds and a killed job is only brought back by an explicit `muse-job resume`. (#806)
- The waitlist's "delete my entry" flow can no longer leave your data behind while telling you it's gone: the deletion is committed to the store before the single-use link is retired, so a crash at the wrong moment fails toward deletion, never toward a false "already deleted". And if that crash window is hit, re-clicking the link now says "already deleted" honestly instead of "expired". (#394)
- The waitlist's self-host CTA click counter now records under the same thread lock as every other funnel event in the daemon. (#403)
- Operator docs: the push-notification guide's operator-identity note now says explicitly that on the hosted tier the commands run on the operator's side — where confirmd is deployed, not inside the tenant's VM — so a tenant reader doesn't mistake the operator-run commands (key generation, test-push, the worker runbook) for commands their own identity may run. (#782)
- Deploy hygiene: the updater now cleans up a stale file the old credential-UI install step used to copy into the operator's working checkout on every deploy. If that copy is still sitting there modified, the first deploy with this change restores it to the checkout's tracked state — but only when its contents exactly match a version from the repo's own history, so anything you changed yourself is never touched. (#774)
- The credential reader no longer cries "not set" when the store can't be read: asking for a credential now reports "not set" only when the stored value is genuinely absent, and fails loudly instead when the store itself can't be read (permissions, a broken store directory, a denied sudo call) — the old message told you the credential was missing and to overwrite a secret that might still exist. (#771)
- The credential web UI no longer drops the connection on hand-built requests: a placement argument that isn't a string (a number or a list in the JSON body) now gets a clean "bad request" answer instead of crashing the request thread. (#771)
- The job status and watchdog pass no longer re-walk the whole job directory on every run to measure its size: the measured size is cached on the job record and re-measured at most every 15 minutes. The only consumer is the watchdog's "job dir over 20 GB" signal, which tolerates a coarse reading; a corrupted or non-numeric cached value fails back to a fresh walk instead of crashing. (#762)
- A deliberately killed job session is no longer resurrected by the watchdog: killing a job now records a terminal-ish `killed` state that the monitoring pass leaves alone, so `kill` actually ends the job instead of being undone within one cron period. Resuming the job is the deliberate act that returns it to `active`. The job docs are also corrected where they still said the disk sweeper's emergency breaker kills the largest job (it closes it) and where they implied the legacy standalone watchdog script is interchangeable with `muse-job watch` (it is deprecated and lacks the event-read hardening). (#761)
- The hosted signup/onboarding spec's Tailscale section now matches the decided bring-your-own-tailnet shape: the tenant box joins the account holder's own tailnet, the control plane mints no per-tenant tailnet auth keys, and the human-gated device approval in the tenant's own tailnet admin replaces the old "all code, no human" claim for that path (the relay stays the unattended primary path). The tailnet-shape open question is marked decided. (#758)
- The auto-deploy's failure-injection test no longer touches host system paths: it redirects the install-path prefixes at throwaway temp directories (the same pattern the snapshot tests already use), so on a deployed box — where the live sudoers file is stat-able but unreadable — the forced snapshot step no longer trips before the deploy-failure path the test is exercising. (#720)
- The waitlist's anti-spam ledger can no longer be wiped by a crash at the wrong moment: pruning old entries now rewrites through a temp file plus fsync and atomic rename (the same discipline the row store already uses), so a kill mid-prune leaves either the old ledger or the new one — the send/intake limits can never silently reset to zero again. (#754)
- The waitlist daemon no longer re-reads its entire signup store on every request: it now keeps a bounded snapshot keyed on the store files' modification time and size, skipping the full re-parse when nothing changed on disk — a separate operator process changing the store still invalidates the snapshot immediately. (#754)
- The credential-name and allowed-host rules the CLI, the credential web UI, and the registry writer enforce now come from a single shared definition instead of three separately maintained copies, so the three can no longer drift apart on which names are legal — each component's installer ships the shared definition alongside it, and a conformance test pins the behavior identical everywhere. The CLI's hostname check also reports a clean error on non-text input now instead of crashing. (#753)
- The golden-image gate procedure now tells the truth about its baked-secret scan: the procedure names both gate steps the scan actually runs as (the pre-fixture refusal and the post-teardown verdict), the re-scan step no longer hardcodes the whole box as its target — a subtree image re-scans its own subtree mount, since scanning the build box's root there false-refuses on the box's own keys — and the operator notes now state what the scan skips (top-level system dirs, regenerated test artifacts), that the scan never flags its own pattern definitions, and how unreadable entries are handled (loud warning, fail-open). (#752)
- The deploy updater no longer carries the old checkout-sync machinery: with every service's runtime living outside the operator's working checkout, the deploy no longer snapshots, syncs, or restores checkout subtrees — and the armed-but-unused delete-and-resync path is gone with it. A dirty checkout neither blocks a deploy nor feeds anything the services run. (#748)
- `cred list` no longer mistakes a broken credential store for an empty one: a missing store directory still lists quietly as before, but a permission error, a bad sudoers entry, or any other read failure is now reported as an error instead of printing nothing and looking like "no credentials". (#744)
- Job steering now verifies the steered text actually arrived in the agent's input box before the delivery check can count it: a message the paste never reached (or pane output echoing the message back) can no longer be misread as delivered — the steer fails closed instead. (#744)
- The tenant auth preflight's provision check now runs its credential test under a fresh empty home directory, so a credential file baked into the image can no longer make the check pass while the real injected-credential path is broken. (#743)
- Key-registry claim codes can no longer start with a dash: issued codes are regenerated if the random draw begins with `-`, so every code redeems through the normal `claim-redeem <code>` command line instead of failing as an unrecognized option about one time in sixty-four. (#742)
- The agent sandbox's firewall log rules are rate-limited (5 per minute, burst of 10) so a packet storm against blocked ports can no longer flood the host's system log and fill its disk — the drop verdicts themselves are unchanged; every dropped packet still drops. (#734)
- The credential web UI now treats a paste ending in a lone carriage return (older Mac-style clipboard) the same as other newline pastes: it's trimmed to the intended value instead of being stored with the stray character, and an empty-after-trim paste gets the clean "empty" error rather than a server error. (#734)
- The fleet version inventory's tables stay aligned even for long box names, the collection summary now names how many boxes it read this run, and a damaged local store reports a clean error instead of a stack trace. (#726)
- The fleet version inventory no longer fails one of the overlapping collectors when two collection runs hit the same store at once: each snapshot rebuild now publishes through its own temporary file, so one run's publish can no longer delete another run's in-progress file. A crash between the temp write and the publish still can't leave a torn snapshot, and stale temp files from such crashes are swept on the next rebuild. (#722)
- `muse-job`'s job-directory size display no longer walks build-output and VCS directories: `status` and `watch` skip `target/`, `node_modules/`, and `.git`, so a job that built a Rust or npm tree doesn't cost a 15-second walk per refresh. The sweep daemon's emergency disk-full breaker still measures true on-disk size, since it frees disk by closing the largest job. (#722)
- The credential web UI now rejects newline-only pastes with a clean error up front, instead of failing at the credential store after the fact. (#708) (#712)
- Credential web UI: `/api/set` now enforces the 64 KiB secret byte cap at the UI boundary — the same frontend/writer agreement the `cred` CLI holds — refusing oversized pastes with a clean error before spawning the narrow sudo writer, instead of failing late on the writer's refusal. (#707)
- Branch-protection docs: the rulesets guide no longer teaches the old four-check gate — the declared main-branch protection has required five CI checks since the changelog ritual lint was added, and the guide now documents the two-step landing (declared JSON update, then the owner's admin re-apply) plus how to verify enforced-vs-declared drift with the ruleset apply script's check mode. Until the standing re-apply happens, the changelog lint runs in CI but does not block merges. (#705)
- Setup guide: the documented swap-audit-log commands now read as root instead of as swapd — the old `sudo -u swapd tail/cat` forms have no grant in the sudoers policy (the narrow read grants cover only the registry and secret files, and the audit log is swapd-readable-only), so they were denied on a real deployment. The demo asset guide also notes its 2026-09-19 recording predates the pinned absolute read paths. (#704)
- The credential web UI's deploy install now assembles its runtime set in a staging directory and publishes each file with an atomic rename, so an interrupted install can no longer leave a half-written file in the live install directory. (#701)
- Release publishing now reports what it did and recovers itself: the release script announces which publisher it used and the published release's URL, waits for the freshly pushed tag to become visible to GitHub's API before publishing (replication lag used to fail the publish and leave a tag with no release, as with v0.5.0), and the release workflow automatically retries the publish for an existing tag if the main step fails. (#686)
- Browser credential fill-in now reads through the same narrow store reader the CLI uses, instead of a direct privileged read the system configuration never granted — fill-in works again on deployed boxes, and a denied read now reports the reader's reason instead of a bare "not set". (#669)
- The credential web UI's system-reader calls now use the same absolute program paths the system configuration grants, instead of depending on the target machine's command lookup. (#670)
- The credential command line and web UI now reject reserved registry entry names (such as `allowed_hosts`) up front, instead of failing at the credential store after the fact. (#677)
- Release recovery hardening: the recovery publish step now also waits for the freshly pushed tag to become visible to GitHub before publishing — a retry seconds after a failed publish no longer re-fails on tag replication lag — the API publish call carries the same bounded network timeouts as the status checks, and the API fallback accepts the workflow's usual token variable name, so the fallback actually works in CI instead of fail-closing. (#687, #678, #692)
- The credential-substitution proxy no longer re-scans the whole credential registry on every request carrying cookies: the list of credentials allowed into cookies is now built once when the registry loads and refreshed only when the registry itself changes, cutting per-request work on cookie-heavy traffic. (#694)
- The approvals daemon's audit log now strips control characters and non-printable text from user-supplied fields before writing, so a crafted login name or detail string can no longer inject forged lines into the audit trail. (#696)
- The credential web UI now reports a visible error when the credential registry exists but is damaged or unreadable, instead of quietly telling you none of your credentials are registered. (#696)

### Security
- The credential web UI's per-install API token no longer lives in a file your own processes can read directly: it moved under swapd ownership (`/home/swapd/ui-token`, mode `0600`), fetched at startup through a pinned sudo reader and written only through a new narrow writer — both installed by `proxy/deploy.sh` alongside the existing sudoers entries. A process running as your user can no longer open the token file off the filesystem; every read now crosses sudo's audit trail. The honest residual: sudo matches the invoking user rather than the process, so a same-user process can still reach the token through those pinned entries (it already holds equivalent power through the NOPASSWD writers) — and developers can still point `CRED_UI_TOKEN_FILE` at a local file on machines without swapd. (#964) (#1071)
- The image-build auth gate now watches every request field, not just the authorization header: the gate fixture records the full request the origin received — method, raw path including the query string, the complete header set, and a sha256 of the body — and the probe fails the image if the credential placeholder reaches the origin through any of them. Previously the gate only checked the authorization header, so a misbehaving command-line client could leak the placeholder through a second header, a query parameter, or the request line and still pass. The body itself is never logged, only its hash. (#157) (#818)
- The job runner closes three input-validation residuals from its earlier hardening pass: repository URLs using the `ext::` or `fd::` remote-helper transports are now refused at spawn (they would ask git to run an external helper as the operator), a repository URL whose last path segment is `..` or `.` is now refused instead of deriving the checkout directory outside the repositories folder, and a `--base` ref starting with a dash is now refused instead of reaching git in option position. All three were fail-safe before this change -- none was a live hole -- so this is hardening, not a fix for active exploitation. (#793) (#808)
- Job session discovery no longer trusts the hook registry alone: a discovered session now binds only while a muse-named process actually runs in the job's work directory, so a planted registry record for a workdir with no running session fails closed instead of hijacking the binding (which would steer `muse resume` across the job boundary). This is consistency enforcement, not authentication — the process-name check is trivially spoofable, so a same-user writer that also runs a muse-named process in the workdir still passes — and the remaining trust in the same-user-writable registry is documented as such. (#806)
- Job slugs are now validated on every subcommand, not just at spawn: previously only `spawn` checked the slug, so a mistyped or hostile slug on `status`, `steer`, `log`, `kill`, `resume`, or `close` resolved the job directory outside the jobs folder (`muse-job close ..` aimed the close path at the home directory). Repository URLs starting with a dash are now refused at spawn, and the clone command passes an explicit end-of-options marker, closing the flag-injection hole a pasted repository URL could exploit. (#792)
- The approval page's bind address no longer falls back to a hardcoded address: it is resolved from the tailnet at startup (or pinned by the operator), and if the address can't be determined the page exits instead of serving — restarting automatically once the tailnet is back. The self-recognition the page's Tailscale-identity auth depends on therefore can't go stale-on-a-guess: previously, a failed lookup at startup left the page binding a baked-in address, which could make a local process look like the human owner. The operator pin and the periodic re-resolution are unchanged. (#773)
- The deprecated standalone watchdog script is removed: it read each job's event file with none of the hardening the canonical `muse-job watch` carries (no session-id shape check, no refusal of non-regular event files, no type guard on the session id), so a tampered job record could aim it at an arbitrary file read or crash the whole pass — and every watchdog fix had to be ported twice to stay safe. The README already marked it deprecated and not equivalent; `muse-job watch` (what the cron runs) is the only watchdog now. Any previously installed copy on a deployed box stays inert until removed; it was never on the cron path. (#762)
- The manual approval-filing tool now enforces flood protection on the swap proxy's own bar: at most 5 pending approvals per credential per filer, and at most one filing per filer per 60 seconds. Any local user able to write the pending directory could previously file unbounded approvals — burning disk, CPU on the approval page's poller, and flooding the owner with unanswerable entries — and parallel invocations could race the check entirely. The filer is part of the limit key (the credential name is caller-chosen, so name rotation can't dodge it), the check and the write are serialized under a lock, a refused filing explains itself on stderr and files nothing, filed approvals land owner-only (0600) regardless of umask, and the filing lifetime is bounded at 24 hours so a credential's cap can't be burned for decades. Direct writers of the pending directory still bypass the tool's checks — this is a guardrail, not a hard boundary. (#76)
- The golden-image build gate now checks the image for baked-in secrets before it may publish: a negative scan refuses the image when any baked file carries real secret material (private-key blocks, cloud and provider token shapes), when credential-shaped filenames (`id_rsa`, `.env`, `auth.json`) exist anywhere baked, or when the credential stores hold anything but the public gate-fixture dummy — closing the gap where the manifest claimed "empty credential stores" and "private key never baked" without anything verifying it. A single baked credential would let a tenant agent read it directly, bypassing every proxy control. The scan's pattern list ships in the repo and is reviewed like any code, so new secret shapes get added deliberately rather than silently. (#746)
- The muse-job session layer's secret-log handling is hardened further: a hardlinked log path is now refused outright (a second name for the file is a planted shape), any setuid/setgid/sticky bits on a pre-existing log are refused instead of silently kept, the refusal message names the directory case explicitly, and the log's file descriptor is returned to blocking mode after open so a pipe with a reader blocks when full instead of raising and silently dropping log writes. (#736)
- The Playwright secret-filling helper no longer trusts its own docstring: it now refuses to run from a process with no terminal on stdin unless the operator explicitly opts in with `SPARKVM_FILL_SECRET_HUMAN_OVERRIDE=1`. The helper loads the real secret value into the calling process's memory, so agent-driven browser sessions must use the swap-proxy path (the `hsurr:` placeholder swapped at the proxy, where the value never enters the agent's process) instead. Human-run scripts are unaffected — a person at a terminal passes the check automatically — and isolated automation takes the explicit opt-in that owns the tradeoff. (#671) (#732)
- The credential registry now states its trust model plainly: host bindings, method/path limits, and scrub flags are enforced against the proxied agent processes on every swap, but they are self-service controls for the operator — the same account that sets them may lift them without confirmation — so they are advisory, not constraints. The one boundary the operator cannot lift unilaterally is the root-managed allowed-hosts file the swap path checks separately. Commands that loosen registry restrictions now print a one-line note saying so on stderr; behavior and exit codes are unchanged. (#87) (#725)
- muse-job now scans every spawn prompt and steer message for secret-shaped text (API keys, provider tokens, private keys, credential assignments) before handing them to the agent: the job refuses with a labeled summary — never echoing the secret itself — because anything typed into the job funnel lands in the agent's session store, readable by the same user with zero friction. The sanctioned escape is the `hsurr:` placeholder the proxy swaps for allowlisted hosts; `--allow-secrets` on the spawn or steer command is the explicit override when you really mean it. This is a tripwire for the common accidental pastes, not a guarantee: exotic or entropy-only values can still slip through, so placeholders stay the default. (#724)
- The credential-substitution proxy services now run under systemd sandboxing: each gets its own private /tmp, the whole OS tree mounted read-only except /home/swapd (the credential store, registry, and audit log all live there), no privilege acquisition for either process, and the kernel tunables/modules/control-groups locked down. The proxy never escalates privileges — it runs as swapd and spawns nothing — so dropping privilege acquisition costs it nothing while removing a persistence path for a proxy-process compromise. (#95) (#712)
- The muse-job session layer now holds its job log to owner-only permissions even when the log file already exists, and refuses a symlink at the log path instead of following it — serve stderr can carry real secret values, and the old code only set 0o600 at file creation, so a pre-existing 0644 log would have kept leaking new secrets to group/other. A pre-planted FIFO can no longer hang the log open either (it now fails fast, like the muse-job hooks' event log). The session smoke CLI also says so on stderr on every run: its stdout is never redacted, so the warning now travels with the output instead of living only in the help text. (#714)
- The credential web UI no longer runs from the working checkout: the updater now installs its page and server into a fixed location outside the checkout that only a deploy refreshes, so a stray edit to the checkout can neither change the secret-pasting page your browser loads nor block the updater from refreshing it. (#700)
- The swap proxy's audit log now strips control characters and whitespace from every client-influenced field before writing: a hostile or buggy local client can no longer smuggle newlines or forged entries into the audit trail. Well-formed hosts, IP addresses, and credential names are written exactly as before. (#682)
- The approvals daemon no longer keeps its anti-forgery nonces in the approval file the requester wrote: the nonce ring now lives in the daemon's own memory, keyed by approval id, and nonces pre-seeded into a pending file are ignored entirely — a lower-trust approval filer can't mint its own entries and then drive an approval from its own browser session. The multi-tab behavior is unchanged (the last few rendered forms all stay valid), and a daemon restart just means pre-restart forms reload and mint fresh. (#78) (#764)
- The docs index now maps four recent design docs that landed without index rows: the phone-home and box-provisioning gap analyses (#847, #851), the durable-commands spec (#848), and the plane-side action-approval record protocol (#872). The root README's repo-layout table now also names the relay session-liveness journal and matches the fleet README's "event journal + alerts" wording. (#940)

### Fixed
- Docs: the documentation index now covers every published doc, and a new automated check fails CI if a future doc ships without an index row — the hosted phone-home socket-lifecycle gap analysis landed earlier this week with no index entry, so readers browsing the index could never find it. (#1005)
- Fleet alert evaluation now reasons about a bounded window instead of the whole journal (#814 slice 1): each evaluation's rule logic sees only the tail the armed alert rules can act on (the longest rule window, six hours), so the per-collect rule-evaluation work stays bounded as the journal grows — the journal file itself is still read in full on every collect (bounding the read is a later slice; retention caps the file at 90 days). Behavior is unchanged for every event inside that window — including events that can't be dated, which the scanner still passes through — and the at-most-once alert dedup is unchanged. Two deliberate edges, both requiring the operator to have skipped evaluation for longer than the window: a failed-rollback older than the window that was never evaluated no longer pages (evaluation runs on every collect, and the stuck-box rules still cover a box that stays broken), and a correlated-failure cluster straddling the window edge is no longer detectable. (#832)
- Restored the changelog ritual's own rule 1 text: a botched insertion from the October 2 durable-commands docs PR had left a fragment of a changelog bullet inside the standing merge-gate wording, so the ritual no longer read as written. (#940)
- The box-side phone-home daemon now restarts its reconnect backoff after a healthy session: the backoff counter previously accumulated for the daemon's whole life, so the first reconnect after a long-lived session could wait up to a minute instead of starting over at one second as the wire spec requires. (#1028)
- `fleet events list` now orders the per-box series by parsed timestamp instead of lexically: journals mixing ISO strings and epoch-shaped `emitted_at` values previously misordered the series, so the "last outcome" row the operator reads could be the wrong row. Unparseable timestamps sort last. (#1057)
- A 408 (request timeout) from the push service now retries on the standard backoff schedule instead of discarding the page: a 408 is the push service giving up on the request, not a defect in the request, so repeating the identical send may well succeed. Possible double-delivery (Web Push carries no idempotency key) is recorded as an accepted tradeoff — it costs a second notification, never a false approval, while discarding the page meant the owner was never paged for that approval. (#1056)

## [0.5.0] - 2026-09-29

### Added
- Competitor corpus update (late-night watch, 2026-09-29, cycle 42): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing effective Oct 1 (~2 days out), 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, forty-second consecutive read), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (seventeenth consecutive capped render, visible list matches baseline). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead — Vercel has not cancelled GA; its own surfaces simply still show beta/private-beta). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (syndications still "nearing"/"talks" framing — nearing is not closed), Baseten's "Carbon" is still a private preview, the Sept-28 Nvidia Open Agent Safety Platform coverage wave is recirculation of an already-folded launch (not a new entry). Flagged but not filed: the agent-O rumor (pre-keynote leak/speculation — DevDay keynote Tue Sep-29 later today ~12pm CT, only an actual OpenAI confirmation files); a Docker Agentic Platform experimental release and a Docker Sandbox Kit Spec CNCF intent (single-source, below bar — watch only); an alleged Vercel dark-web credential sale (still unverified — not two independent reputable sources, watch only); NanoClaw news (March-2026-vintage Docker partnership recirculation; the NanoCo re-grade bar stays unmet); frontier-lab model news (GPT-6.1 "Astra" cancellation recirculation — out of lane). Two flagged items carried stale comparison text from older cycles — superseded by first-party reads (no genuine deltas). (#656)
- Competitor corpus update (late-night watch, 2026-09-29, cycle 41): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing effective Oct 1 — tomorrow, 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, forty-first consecutive read), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (sixteenth consecutive capped render, visible list matches baseline). Vercel Drives GA remains a standing tracked item (no in-cycle grading; not declared dead — Vercel has not cancelled GA; its own surfaces simply still show beta/private-beta). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (syndications still "nearing"/"talks" framing — nearing is not closed), Baseten's "Carbon" is still a private preview, the Sept-28 Nvidia Open Agent Safety Platform coverage wave is recirculation of an already-folded launch (not a new entry). Flagged but not filed: the agent-O rumor (pre-keynote leak/speculation — DevDay keynote Tue Sep-29, only an actual OpenAI confirmation files); a third-party recount of a July Modal customer-data compromise disclosure (not a new incident, not first-party — watch only); an alleged Vercel dark-web credential sale (still unverified — not two independent reputable sources, watch only); NanoClaw news (a Docker partnership piece and a JFrog security-integration piece, both vintage recirculation; a NanoClaw-to-Slack feature — consumer/agent-UX news, not provider launches; the NanoCo re-grade bar stays unmet); adjacent infra M&A (Samsung/Helix, AMD/World Labs, Megaport AI-infra deals — adjacent, below bar); frontier-lab model news. (#653)
- Competitor corpus update (evening watch, 2026-09-28, cycle 40): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry; the three-entry Sept-28 section is unchanged), DigitalOcean and Modal pricing (Modal egress billing effective Oct 1 — under ~24h out, 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, fortieth consecutive read), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (fifteenth consecutive capped render, visible list matches baseline). The Vercel Drives GA-by-2026-09-28 expectation window closed at midnight — the final in-cycle grade was NOT MET (Vercel's own surfaces still show beta/private-beta; not declared dead — Vercel has not cancelled GA; Drives is now a standing tracked item, no more in-window grading). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (syndications still "nearing"/"talks" framing — nearing is not closed), Baseten's "Carbon" is still a private preview, the Sept-28 Nvidia Open Agent Safety Platform coverage wave is recirculation of an already-folded launch (not a new entry). Flagged but not filed: the agent-O rumor (pre-keynote leak/speculation — DevDay keynote Tue Sep-29, only an actual OpenAI confirmation files); a third-party recount of a July Modal customer-data compromise disclosure (not a new incident, not first-party — watch only); an alleged Vercel dark-web credential sale (still unverified — not two independent reputable sources, watch only); NanoClaw news (a Docker partnership piece and a JFrog security-integration piece, both vintage recirculation; a NanoClaw-to-Slack feature — consumer/agent-UX news, not provider launches; the NanoCo re-grade bar stays unmet); adjacent infra M&A (Samsung/Helix, AMD/World Labs, Megaport AI-infra deals — adjacent, below bar); frontier-lab model news. (#652)
- SSH-key-as-account claim codes: a key-only account can now be upgraded to a claimed account even when the operator no longer holds the original key — issue a single-use code with a 7-day default expiry, redeem it to mark the account as claimed. Only code hashes are stored, never the codes themselves, so a stolen registry reveals no live codes. (#654)
- Competitor corpus update (evening watch, 2026-09-28, cycle 39): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry; the three-entry Sept-28 section is unchanged), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirty-ninth consecutive read, zero wording drift), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (fourteenth consecutive capped render, visible list matches baseline). The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the fifteenth and FINAL consecutive in-cycle pass — the expectation window closes at the end of tonight (not declared dead: Vercel has not cancelled GA; from the next pass Drives GA is tracked as a standing item instead of being graded). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (fresh syndications keep "nearing"/"closing in on" framing — nearing is not closed), an in-window Sept-28 piece confirms OpenAI has announced no DevDay products (the agent-O launch rumor stays leak-only, DevDay gate Tue Sep-29), Baseten's "Carbon" is still a private preview. Flagged but not filed: an alleged Vercel dark-web credential sale (fresh Sept-28 pieces still trace the claim to a Sept-27 SOCRadar report plus one aggregator — explicitly rated unverified, watch only); a NanoClaw-to-Slack agent feature and a NanoClaw × Vercel policy-settings piece (consumer/agent-UX news, not provider launches — the NanoCo re-grade bar stays unmet); adjacent model/product news (Anthropic Sonnet 5.5, Meta enterprise AI, Google killing Gemini Gems, Shopify opening checkout to browser agents); a Modal vs Replicate vs Baseten indie-hackers pricing roundup (third-party, not provider news). (#650)
- Competitor corpus update (evening watch, 2026-09-28, cycle 38): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry; the three-entry Sept-28 section is unchanged), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirty-eighth consecutive read), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (thirteenth consecutive capped render, visible list matches baseline). The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the fourteenth consecutive pass — the window closes at the end of tonight (not declared dead: Vercel has not cancelled GA; the 23:24 slot carries the final in-cycle Vercel Drives grade, so this is the last mid-cycle pass). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (TechCrunch still "nearing"/"closing in on", Baseten "discussions … have not produced completed rounds" — nearing is not closed), Baseten's "Carbon" is still a private preview, the Sept-28 Nvidia Open Agent Safety Platform coverage wave is recirculation of an already-folded launch (not a new entry). Flagged but not filed: the agent-O rumor (a new pre-window rumor piece keeps "rumored" framing — leak-only, DevDay gate Tue Sep-29); Plugin4Shell (still no real CVE assigned — do not cite); an alleged Vercel dark-web credential sale (pre-window Sept-28 pieces trace the claim to a Sept-27 SOCRadar report plus one aggregator — not two independent reputable sources, watch only); a NanoClaw-to-Slack agent feature and a NanoClaw × Vercel policy-settings piece (consumer/agent-UX news, not provider launches — the NanoCo re-grade bar stays unmet); adjacent model/product news (Anthropic Sonnet 5.5, Meta enterprise AI, Google killing Gemini Gems, Shopify opening checkout to browser agents); a Modal vs Replicate vs Baseten indie-hackers pricing roundup (third-party, not provider news). (#648)
- Competitor corpus update (evening watch, 2026-09-28, cycle 37): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry; the three-entry Sept-28 section is unchanged), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirty-seventh consecutive read), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (twelfth consecutive capped render, visible list matches baseline). The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the thirteenth consecutive pass — the window closes at the end of tonight (not declared dead: Vercel has not cancelled GA; ONE more in-window slot remains tonight at 23:24, so the final in-cycle grade rides with that last in-window pass). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (TechCrunch "closing in on", Baseten "negotiating/discussions, no completed rounds" — nearing is not closed), Baseten's "Carbon" is still a private preview, the Sept-28 Nvidia Open Agent Safety Platform coverage wave is recirculation of an already-folded launch (not a new entry). Flagged but not filed: the agent-O rumor (OpenAI has confirmed no DevDay product announcements — leak-only, DevDay gate Tue Sep-29); Plugin4Shell (still no real CVE assigned — do not cite); an alleged Vercel dark-web credential sale (a second Sept-28 piece traces the claim to a Sept-27 SOCRadar report plus one aggregator — not two independent reputable sources, watch only); a pre-window Daytona $24M Series A piece (funding vintage, not a launch); a "Best Agent Sandboxes" benchmark roundup (third-party, pre-window); an AMD/World Labs acquisition (not in-lane). (#646)
- Competitor corpus update (evening watch, 2026-09-28, cycle 36): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry; the three-entry Sept-28 section is unchanged), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirty-sixth consecutive read), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (eleventh consecutive capped render, visible list matches baseline). The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the twelfth consecutive pass — the window closes at the end of tonight (not declared dead: Vercel has not cancelled GA; two more in-window slots remain tonight, so the final in-cycle grade rides with the last in-window pass). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (TechCrunch "closing in on", both sides "nearing" — nearing is not closed), Baseten's "Carbon" is still a private preview, the Sept-28 Nvidia Open Agent Safety Platform coverage wave is recirculation of an already-folded launch (not a new entry). Flagged but not filed: the agent-O rumor (OpenAI has confirmed no DevDay product announcements — leak-only, DevDay gate Tue Sep-29); Plugin4Shell (still no real CVE assigned — do not cite); an alleged Vercel dark-web credential sale (a second Sept-28 piece traces the claim to a Sept-27 SOCRadar report plus one aggregator — not two independent reputable sources, watch only); a LangChain "Sandboxes for Deep Agents" integrations post (integration-layer news, not a provider launch); a cancelled GPT-6.1 "Astra" model rollout (safety news, not sandbox infra — watch only); an Anthropic model release and agent-commerce integration stories (adjacent, below bar). (#645)
- Competitor corpus update (evening watch, 2026-09-28, cycle 35): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry; the three-entry Sept-28 section is unchanged), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1, no went-live-early signal), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirty-fifth consecutive read), and the Boat legacy domains (two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE (tenth consecutive capped render, visible list matches baseline). The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the eleventh consecutive pass — the window closes at the end of tonight (not declared dead: Vercel has not cancelled GA; two more in-window slots remain tonight, so the final in-cycle grade rides with the last in-window pass). Closed this cycle: the DigitalOcean "100 sessions/team" detail is restored as a per-team concurrency cap on the vendor's limits page ("You can run up to 100 sessions at once per team depending on your tier"), not a pricing figure. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (TechCrunch "closing in on", both sides "nearing" — nearing is not closed), Baseten's "Carbon" is still a private preview, the rumored Daytona round remains unannounced by the company, NVIDIA's OpenShell partner-ecosystem news is corroboration-only (already folded — not re-filed). Flagged but not filed: the agent-O rumor (OpenAI has confirmed no DevDay product announcements — leak-only, DevDay gate Tue Sep-29); Plugin4Shell (still no real CVE assigned — do not cite); an alleged Vercel dark-web credential sale (traced to a Sept-27 SOCRadar report plus one aggregator — not two independent reputable sources, watch only); a LangChain "Sandboxes for Deep Agents" integrations post (integration-layer news, not a provider launch); a cancelled GPT-6.1 "Astra" model rollout (safety news, not sandbox infra — watch only). (#644)
- Competitor corpus update (evening watch, 2026-09-28, cycle 34): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry; the three-entry Sept-28 section is unchanged since cycle 32), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirty-fourth consecutive read), and the Boat legacy domains (the full four checks hold — two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE. The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the tenth consecutive pass — the expectation window closes at the end of tonight (not declared dead: Vercel has not cancelled GA; its own surfaces simply still show beta/private-beta). The requested re-render confirms Boat's competitive-comparison blocks (provider $/hour matrix, active-CPU-billing explainer, hpc-sandbox-benchmarks leaderboard) persist on the pricing page and both legacy domains — still color, not a baseline change. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (a Sept-28 piece states explicitly neither round has closed), Baseten's "Carbon" is still a private preview, a rumored Daytona Series B is database-reported only (not company-announced — below bar; an old 2024 PR reprint is recirculating), and NVIDIA's OpenShell partner-ecosystem news is corroboration-only (already folded — not re-filed). Flagged but not filed: the agent-O rumor (OpenAI has confirmed no DevDay product announcements — leak-only, DevDay gate Tue Sep-29); Plugin4Shell (still no real CVE assigned — do not cite); an alleged Vercel dark-web credential sale (unverified — plausibly recycled from the confirmed April-2026 incident, watch only); a NanoClaw × Slack integration under the NanoCo rebrand (consumer agent-product news — NanoCo is the watch vehicle for a future first-party sandbox/compute announcement); an OpenAI training-sandbox DNS-escape and a Perplexity sandbox red-team report (safety research, not provider products); a cancelled GPT-6.1 "Astra" model rollout (safety news, not sandbox infra — below bar, watch only). (#641)
- Docs map made complete: eleven docs that existed in the docs tree but had no row in the docs index are now findable — the client-visible approval signal, the multi-provider failover design, the SSH key-identity registry design note, the first-ten-minutes conformance audit, the desktop-stack architecture deep-read, the link-checker host-exclusion record, the Brig/Epho competitor consolidation, the h-sandbox credential-vault analysis, and three missed competitor-watch passes. (#643)
- Competitor corpus update (evening watch, 2026-09-28, cycle 33): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry; the three-entry Sept-28 section is unchanged since cycle 32), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirty-third consecutive read), and the Boat legacy domains (the full four checks hold — two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE. New watch color: Boat's pricing page and both legacy domains now render competitive-comparison blocks (provider $/hour matrix, an active-CPU-billing explainer, an hpc-sandbox-benchmarks leaderboard) never enumerated by the prior baseline — flagged for a re-render next cycle to see whether they persist. The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the ninth consecutive pass — the final grade rides with the last in-window pass tonight; all three of Vercel's own surfaces agree on beta/private-beta. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (a Sept-28 piece states explicitly the Modal deal is not closed), Baseten's "Carbon" is still a private preview, a rumored Daytona Series B is database-reported only (not company-announced — below bar), and NVIDIA's OpenShell partner-ecosystem news is corroboration-only (already folded — not re-filed). Flagged but not filed: the agent-O rumor (OpenAI has confirmed no DevDay product announcements — leak-only, DevDay gate Tue Sep-29); Plugin4Shell (still no real CVE assigned — do not cite); an alleged Vercel dark-web credential sale (unverified — plausibly recycled from the confirmed April-2026 incident, watch only); a NanoClaw × Slack integration under the NanoCo rebrand (consumer agent-product news — NanoCo is the watch vehicle for a future first-party sandbox/compute announcement). (#640)
- Competitor corpus update (evening watch, 2026-09-28, cycle 32): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry; the three-entry Sept-28 section is unchanged since cycle 31), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirty-second consecutive read), and the Boat legacy domains (the full four checks hold — two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE. The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the eighth consecutive pass — the final grade rides with the last in-window pass tonight; all three of Vercel's own surfaces agree on beta/private-beta. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (a Sept-28 piece states explicitly the Modal deal is not closed), Baseten's "Carbon" is still a private preview, a rumored Daytona Series B is database-reported only (not company-announced — below bar), and NVIDIA's OpenShell partner-ecosystem news is corroboration-only (already folded as C70 — not re-filed). Flagged but not filed: the agent-O rumor (OpenAI has confirmed no DevDay product announcements — leak-only, DevDay gate Tue Sep-29); Plugin4Shell (still no real CVE assigned — do not cite); an alleged Vercel dark-web credential sale (unverified — plausibly recycled from the confirmed April-2026 ShinyHunters incident, watch only); a NanoClaw × Vercel × OneCLI approval-UX partnership under the NanoCo rebrand (consumer agent-product news — NanoCo is the watch vehicle for a future first-party sandbox/compute announcement). (#639)
- Competitor corpus update (evening watch, 2026-09-28, cycle 31): near-quiet pass — one first-party delta, no new corpus entries. The one delta is Vercel's changelog gaining a third Sept-28 entry, "Search domains without authentication" (domain-search tooling via CLI and Registrar API, no sign-in) — not Drives-related; the Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the seventh consecutive pass — the final grade lands in the last in-window pass tonight; all three of Vercel's own surfaces agree it is still beta/private-beta with an active waitlist. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel Sandbox docs (still "Drives (beta)", last updated 2026-09-22), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirty-first consecutive read), and the Boat legacy domains (the full four checks hold — two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (a Sept-28 piece states explicitly the Modal deal is not closed), Baseten's "Carbon" is still a private preview, the Anthropic×NVIDIA OpenShell collab story is corroboration-only (already folded as C70 — not re-filed), and Modal egress billing has no went-live-early signal. Flagged but not filed: the agent-O rumor (OpenAI has confirmed no DevDay product announcements — leak-only, DevDay gate Tue Sep-29); Plugin4Shell (still no real CVE assigned — do not cite); an alleged Vercel dark-web credential sale (unverified — plausibly recycled from the confirmed April-2026 Vercel/ShinyHunters incident, watch only). (#638)
- Competitor corpus update (evening watch, 2026-09-28, cycle 30): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, thirtieth consecutive read), and the Boat legacy domains (the full four checks hold — two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE. The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the sixth consecutive pass — the final grade lands in the last in-window pass tonight; all three of Vercel's own surfaces agree on beta/private-beta. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (Modal's $750M round still "nearing" — nearing is not closed), Baseten's "Carbon" is still a private preview, the Anthropic×NVIDIA OpenShell collab story is corroboration-only (already folded as C70 — not re-filed), and Modal egress billing has no went-live-early signal. Flagged but not filed: the agent-O rumor (a Sept-28 report says OpenAI has confirmed no DevDay product announcements — leak-only, DevDay gate Tue Sep-29); Plugin4Shell (still no real CVE assigned — do not cite); an alleged Vercel dark-web credential sale (single unverified threat-intel lead — watch only). (#636)
- Staged-rollout design for multi-box fleets: published the rollout-controller design doc — how a release reaches many boxes in waves (canary soak, health-gated promotion, halt on bad signal, emergency freeze) instead of every box pulling it at once within one timer tick, with an expedited channel for security patches, a fail-closed default when a box can't reach the controller, and build slices that land the operator-estate version first. (#637)
- Competitor corpus update (evening watch, 2026-09-28, cycle 29): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, twenty-ninth consecutive read), and the Boat legacy domains (the full four checks hold — two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE. The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the fifth consecutive pass — the final grade lands in the last in-window pass tonight; all three of Vercel's own surfaces agree on beta/private-beta. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (a Sept-28 report has Modal "nearing" a $750M round — nearing is not closed), Baseten's "Carbon" is still a private preview, and NVIDIA's OpenShell v0.1.0 GA story is corroboration-only (already folded as C70 — not re-filed). Flagged but not filed: the agent-O rumor (still unconfirmed, DevDay gate Tue Sep-29 10am PT); Plugin4Shell (still no real CVE assigned — do not cite). (#635)
- Competitor corpus update (evening watch, 2026-09-28, cycle 27): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line), and the Boat legacy domains (the full four checks hold — two domains plus two Y Combinator listings, all serving natively, no redirects); no new advisory for the tracked Hugo CVE. The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the third consecutive pass — the final grade lands in the last in-window pass tonight; all three of Vercel's own surfaces agree on beta/private-beta. Tracked-item update (no new entry): NVIDIA's open-source OpenShell agent sandbox is now broadly available at v0.1.0. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed, and Baseten's "Carbon" is still a private preview. Flagged but not filed: the agent-O rumor (still unconfirmed); Plugin4Shell (still no real CVE assigned — do not cite); Boxd's $2M pre-seed (recirculation of the known round — not new movement). (#632)
- Competitor corpus update (evening watch, 2026-09-28, cycle 28): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line, twenty-eighth consecutive read), and the Boat legacy domains (the full four checks hold — two domains plus two Y Combinator listings, all serving natively, no redirects); still no first-party advisory for the tracked Hugo CVE. The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the fourth consecutive pass — the final grade lands in the last in-window pass tonight; all three of Vercel's own surfaces agree on beta/private-beta. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed, Baseten's "Carbon" is still a private preview, NVIDIA's OpenShell launch story is corroboration-only, and Modal egress billing has no went-live-early signal. Flagged but not filed: the agent-O rumor (still unconfirmed); Plugin4Shell (still no real CVE assigned — do not cite). (#633)
- Tenant-box update policy decided: hosted tenant boxes renew by reimage with tenant-state migration (disposable boxes, stateful disks) instead of in-place updates, so a running box is always exactly some gate-checked image — the update path the golden-image gate already trusts. The tenant-status vocabulary gains a thirteenth code, `maintenance`, so the status poll can tell a scheduled update apart from a broken box: the onboarding arc latches (clock unaffected) while the update runs, and funnel reporting must count update churn separately from fresh-onboarding churn. (#634)
- Competitor corpus update (afternoon watch, 2026-09-28, cycle 26): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line), and the Boat legacy domains (the full four checks hold — two domains plus two Y Combinator listings, all serving natively, no redirects); no new advisory for the tracked Hugo CVE (four Sep-28 Moderate theme advisories stand; the ≥14-total count could not be confirmed in this page's render — all ten shown match the baseline exactly). The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed for the second consecutive pass — the final grade lands in the last in-window pass; all three of Vercel's own surfaces agree on beta/private-beta (the dedicated Drives page still says "in Private Beta" with an active waitlist). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed (a Sept 28 report has Modal "nearing" a round — nearing is not closed), and Baseten's "Carbon" is still a private preview. Flagged but not filed: a $2M pre-seed for Boxd's "full computers for coding agents" (already in the corpus — recirculation of the Sept-24 stale round, not new movement); the agent-O rumor (twenty-sixth daily cycle, still unconfirmed); Plugin4Shell (still no real CVE assigned — do not cite). (#630)
- Competitor corpus update (afternoon watch, 2026-09-28, cycle 25): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)"), DigitalOcean and Modal pricing (Modal egress billing starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line), and the Boat legacy domains — the check set is restored to the full four (two domains plus two Y Combinator listings, all serving natively, no redirects); no Hugo advisory for the tracked Hugo CVE (four Sep-28 Moderate theme advisories stand, total ≥14). The Vercel Drives GA-by-2026-09-28 expectation is graded NOT MET as observed — the final grade lands in the last in-window pass; all three of Vercel's own surfaces agree on beta/private-beta (the dedicated Drives page still says "in Private Beta" with an active waitlist). The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed, and Baseten's "Carbon" is still a private preview. Flagged but not filed: the agent-O rumor (twenty-fifth daily cycle, still unconfirmed); Plugin4Shell (seven independent "no CVE assigned" statements vs one fringe claim — do not cite). (#628)
- Competitor corpus update (afternoon watch, 2026-09-28, cycle 24): fully quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog and Sandbox docs (still "Drives (beta)" — no GA entry), DigitalOcean and Modal pricing (Modal egress billing still starts Oct 1: 1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1), E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line), and the Boat legacy domains (still serving natively, no redirects); no Hugo advisory for the tracked Hugo CVE (four Sep-28 Moderate theme advisories stand, total ≥14). Vercel Drives is still public beta — the GA-by-2026-09-28 expectation is not yet met as of this afternoon's read and gets its final grade in a later pass today. The news scan surfaced no new competitor launches: the Modal/Baseten funding talks are still unclosed, and Baseten's "Carbon" is still a private preview. Not filed: Instinct's $1B Series C (confirmed closed today — a consumer agent app, not infrastructure) and Anthropic's Claude Marketplace (agent-distribution, not sandbox infra). Flagged but not filed: the agent-O rumor (twenty-fourth daily cycle, still unconfirmed); Plugin4Shell (still no real CVE assigned). (#627)
- Competitor watch update (afternoon, 2026-09-28, cycle 23): one new tracked item — NVIDIA's Open Agent Safety Platform (a sandboxed agent-policy runtime plus an out-of-band hardware watchdog for agents, announced today and corroborated across six independent outlets). Otherwise quiet: the Vercel changelog's two new entries are an AI-Gateway model availability and a re-listed sandbox feature (no Drives GA — the GA expectation stays unmet as of this afternoon's read and gets its final grade in a later pass today); four new moderate-severity Hugo theme advisories, none for the tracked Hugo CVE; pricing pages verified unchanged across Daytona, Docker Sandboxes, Microsandbox, DigitalOcean, Modal, E2B, Boat, TermSquad, and AgentComputer (Modal's egress billing now confirmed on the provider's own docs page — billing still starts Oct 1; AgentComputer still publishes no egress pricing line). The news scan surfaced no new sandbox launches: the Modal/Baseten funding talks are still unclosed, Baseten's "Carbon" is still a private preview, and the Baseten/Blaxel acquisition is already tracked. Flagged but not filed: the agent-O rumor (still unconfirmed — no entry); the suspect Plugin4Shell CVE claim (still no real CVE assigned). (#626)
- muse-job gains the MSP serve-host transport foundation (issue #221, first slice of the #228 tmux→MSP migration): a stdlib-only client that spawns and owns one `muse serve` process per job, runs the initialize/initialized handshake over NDJSON JSON-RPC 2.0, correlates requests, dispatches server notifications, routes server→client requests (approvals, user input), re-spawns dead hosts, and pins the schema fingerprint so a binary upgrade fails loud instead of mid-job. Hermetic tests cover the handshake ordering, routing, timeouts, and reconnect; a live-binary smoke runs where `muse` is installed. No behavior change: tmux still drives jobs until the #222–#227 cutover slices land. (#625)
- confirmd gains writer-side audit-log rotation (issues #535, #360): the append-only refusal trail now rolls at `CONFIRM_AUDIT_MAX_BYTES` (default 10 MiB), keeping the newest `CONFIRM_AUDIT_KEEP` (default 4) segments — the newest events are never dropped (they land in a fresh live segment), the oldest-first rename order keeps a crash from gapping the trail, and concurrent handler threads serialize the check/rotate/append on one lock. The re-open idempotency check (issue #537) now answers from a bounded in-memory `reopened_from → aid` index — one file read instead of parsing every pending file per `/reopen` POST — with the full scan kept as the exact-semantics fallback and index misses validated, never trusted. 7 new hermetic tests in `confirm/test_confirmd.py`. (#621)
- Competitor corpus update (pre-dawn late watch, 2026-09-28, cycle 22): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog, and E2B/boat.dev/TermSquad/AgentComputer pricing; Modal egress billing unchanged ~2.7 days before the Oct 1 start (1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1); the Boat legacy domains serve Boat natively (no redirects); no Hugo advisory for CVE-2026-100690 (10 advisories, newest Sep 9). One page (DigitalOcean pricing) could not be fetched this pass — a docs restructure moved it, not a content change — and is re-verified next cycle. Vercel Drives is still public beta — the GA expectation is not yet met as of this morning's read and is re-checked hourly today until the window closes. The news scan surfaced no new competitor launches; the Baseten × Blaxel acquisition is already in the corpus — its fold recommendation was rejected at the corpus-grep gate. The integration item stays open: no shipped product yet; the Modal/Baseten funding talks are still unclosed. AgentComputer still publishes no egress pricing line. Flagged but not filed: Plugin4Shell (a purported CVE identifier now circulating on a fringe aggregator — still no real CVE assigned, do not cite); the agent-O rumor (twenty-second daily echo, still unconfirmed — no entry). (#624)
- Competitor corpus update (pre-dawn late watch, 2026-09-28, cycle 21): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog, and E2B/boat.dev/TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged ~2.75 days before the Oct 1 start (1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1); the Boat legacy domains serve Boat natively (no redirects); no Hugo advisory for CVE-2026-100690 (10 advisories, newest Sep 9). Vercel Drives is still public beta — the GA expectation is not yet met as of this morning's read and is re-checked hourly today until the window closes. The news scan surfaced no new competitor launches; the Baseten × Blaxel acquisition is already in the corpus — its fold recommendation was rejected at the corpus-grep gate (the third-party recaps are below the fold bar). The integration item stays open: no shipped product yet; the Modal/Baseten funding talks are still unclosed. AgentComputer still publishes no egress pricing line. Flagged but not filed: Plugin4Shell (still no real CVE assigned); the agent-O rumor (twenty-first daily echo, still unconfirmed — no entry). (#622)
- Competitor corpus update (pre-dawn late watch, 2026-09-28, cycle 20): one new corpus entry — C69: the Mistral Vibe CVE-2026-93993 worktree git-hook RCE (Vibe <2.25.5, CVSS 8.8) is now corroborated by a first-party CHANGELOG fix line plus an NVD-linked advisory daily, so it folds out of the flagged-only / corpus-gap candidacy it sat in for four cycles. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog, and E2B/boat.dev/TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged ~2.8 days before the Oct 1 start (1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1); the Boat legacy domains serve Boat natively (no redirects); no Hugo advisory for CVE-2026-100690 (10 advisories, newest Sep 9 — the C19 per-day count was a miscount, corrected this pass). Vercel Drives is still public beta — the GA expectation is not yet met as of this morning's read and is re-checked hourly today until the window closes. The news scan surfaced nothing new in-lane (the agent-O rumor's twentieth daily echo is still unconfirmed). No new age-outs; the Modal/Baseten talks item is still unclosed (the file-on-close rule stays armed); AgentComputer still publishes no egress pricing line. Flagged but not filed: Plugin4Shell (still no real CVE assigned — the 'CVE-2026-92104' claim didn't surface at all this pass). (#618)
- Competitor corpus update (pre-dawn late watch, 2026-09-28, cycle 19): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog, and E2B/boat.dev/TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged ~2.8 days before the Oct 1 start (1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1); the Boat legacy domains serve Boat natively (no redirects); no Hugo advisory for CVE-2026-100690 (10 advisories, newest Sep 9). Vercel Drives is still public beta — the GA expectation is not yet met and is re-checked daily. The news scan surfaced nothing new in-lane. No corpus movement this pass; the Modal/Baseten talks item is still unclosed (the file-on-close rule stays armed); AgentComputer still publishes no egress pricing line. Flagged but not filed: the 'agent O' rumor (nineteenth daily echo, still unconfirmed — no entry); Plugin4Shell (still no real CVE assigned — the 'CVE-2026-92104' claim is uncorroborated); the Mistral Vibe CVE family (CVE-2026-93993 is pre-window — below the re-fold bar). (#617)
- Competitor corpus update (pre-dawn late watch, 2026-09-28, cycle 18): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog, and E2B/boat.dev/TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged ~2.5 days before the Oct 1 start (1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1); the Boat legacy domains serve Boat natively (no redirects); no Hugo advisory for CVE-2026-100690 (10 advisories, newest Sep 9). Vercel Drives is still public beta — the GA expectation is not yet met and is re-checked daily. The news scan surfaced nothing new in-lane (first-seen-but-pre-window: the BAND × Docker Sandboxes integration, Sep 26 — ecosystem activity, not a competitor launch). No corpus movement this pass; the Modal/Baseten talks item is still unclosed (the file-on-close rule stays armed); AgentComputer still publishes no egress pricing line. Flagged but not filed: the 'agent O' rumor (eighteenth daily echo, still unconfirmed — no entry); the uncorroborated Plugin4Shell 'CVE-2026-92104' claim (still no real CVE assigned); the Mistral Vibe CVE family (CVE-2026-93993 is pre-window — below the re-fold bar). (#616)
- Competitor corpus update (pre-dawn late watch, 2026-09-28): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog, and E2B/boat.dev/TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged ~2.5 days before the Oct 1 start (1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1); the Boat legacy domains serve Boat natively (no redirects); no Hugo advisory for CVE-2026-100690 (10 advisories, newest Sep 9). Vercel Drives is still public beta — the GA expectation is not yet met and is re-checked daily. The news scan surfaced nothing new in-lane. No corpus movement this pass; the Modal/Baseten talks item is still unclosed (the file-on-close rule stays armed); AgentComputer still publishes no egress pricing line. Flagged but not filed: the 'agent O' rumor (seventeenth daily echo, still unconfirmed — no entry); the uncorroborated Plugin4Shell 'CVE-2026-92104' claim (still no real CVE assigned); the Mistral Vibe CVE family (CVE-2026-93993 is pre-window — below the re-fold bar). (#615)

- Competitor corpus update (pre-dawn cycle-16 watch, 2026-09-28): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog (top section 27 September, Ember-1 AI Gateway entry; no Drives GA), the Vercel Sandbox docs (Drives still beta, page last updated 2026-09-22), DigitalOcean pricing, Modal egress billing (unchanged, starting Oct 1), and E2B/boat.dev/TermSquad/AgentComputer pricing (AgentComputer still publishes no egress pricing line); the Boat legacy domains still serve Boat natively with no redirects; no Hugo advisory for CVE-2026-100690 (10 advisories, newest Sep 9). Vercel Drives is still public beta — the GA expectation was not yet met as of the ~02:56 CDT read (most of the day remained) and is re-checked hourly until the window closes. The news scan surfaced no new competitor launches; the agent-O rumor remains unconfirmed, Plugin4Shell's purported CVE identifier remains uncorroborated, and the Mistral Vibe advisory, Modal egress mirrors, and NanoClaw partnership items were noted but below the fold bar. The Modal/Baseten funding talks are still unclosed — the file-on-close trigger stays armed. Aged-out items stay out: Boxd, the Docker Cloud Sandboxes CVE family, Huawei CodeArts Malaysia, the OpenAI infrastructure wave (re-fold path on real movement), Heapjack/Overpatch, GitLab CVE-2026-85706, and Dextr AI. (#613)

- Contributor DX: new `scripts/test_basename_uniqueness.py` pins the repo-wide test contract that every `test_*.py` maps to a unique pytest module name — pytest imports rootless suites by basename, so a future duplicate basename would die at collection time with pytest's confusing `import file mismatch` error; the pin fails first (plain unittest, no pytest needed), naming both colliding files and the fix. The computation is anchored on both known shapes (rootless suites + `browser-driver/bdrive`'s real package), the inventory has an anti-vacuity floor, and the pin is mutation-checked (a planted duplicate fails loudly, naming both files). (#612)
- Competitor corpus update (night watch, 2026-09-28): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog, and E2B/boat.dev/ TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged ~3 days before the Oct 1 start (1/10/100 TiB allowances, $0.04/GiB overage, first bill Nov 1); the Boat legacy domains serve Boat natively (no redirects); no Hugo advisory for CVE-2026-100690 (10 advisories, newest Sep 9). Vercel Drives is still public beta — the GA expectation is re-checked daily. The news scan surfaced nothing new in-lane. Corpus movement: the OpenAI infra-wave item aged out after three consecutive quiet passes (vendor facts retained as canonical reference); the Baseten/Blaxel integration item is still unclosed (the file-on-close rule stays armed); the DigitalOcean Managed Agents pricing item is closed. Aged-out items stay out: Boxd; the Docker Cloud Sandboxes CVE family; the DeepSeek Harness sandbox escape (CVE-2026-82533); the OpenClaw browser-tool bypass (CVE-2026-100589); the Huawei Cloud CodeArts Malaysia entry; Heapjack/Overpatch; the GitLab proxy escape (CVE-2026-85706); Dextr AI. Flagged but not filed: the 'agent O' rumor (fifteenth daily echo, still unconfirmed — no corpus entry assigned); the uncorroborated Plugin4Shell 'CVE-2026-92104' claim (zero CVE-db hits); the Mistral Vibe CVE family (no new member, stays corpus-gap candidacy). (#611)

- Gap analysis: fleet update rollout — the fleet layer above #532's per-box updaters (`docs/FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md`): G15 staged rollout / canary / promote-halt (#606), G16 fleet version inventory (#607), G17 update event reporting (#608), G18 fleet→box release-gating channel (#609). A bad release currently reaches the whole fleet within one timer period — and no freeze can stop it, because no freeze can reach the boxes (both updaters are autonomous timer loops). Per-box updaters stay the enforcement point.
- Competitor corpus update (night watch, 2026-09-28): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog, and E2B/boat.dev/ TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged ~3 days before the Oct 1 start; the Boat legacy domains serve Boat natively; no Hugo advisory for CVE-2026-100690. Vercel Drives is still public beta — the GA expectation is re-checked daily. The news scan surfaced nothing new in-lane. No corpus aging this pass; the Baseten/Blaxel integration item is still unclosed (the file-on-close rule stays armed); the OpenAI infra-wave item has two consecutive quiet passes (one more ages it out). Flagged but not filed: the 'agent O' rumor (still unconfirmed); the uncorroborated Plugin4Shell 'CVE-2026-92104' claim; the Mistral Vibe CVE family (no new member). (#605)

- Competitor corpus update (night watch, 2026-09-28): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog, and E2B/boat.dev/ TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged ~3 days before the Oct 1 start. Vercel Drives is still public beta (the GA expectation was re-checked this pass). The news scan surfaced nothing new in-lane. Corpus movement: the Huawei Cloud CodeArts Malaysia entry aged out after three consecutive quiet passes (vendor facts retained as canonical reference); the Baseten/Blaxel integration item hit the three-pass threshold — the file-on-close rule is armed. New third-party detail (not folded): a US-CERT summary of Mistral CVE-2026-93993 (Sep-19 worktree git-hooks RCE, CVSS 8.8, pre-window; no first-party Mistral advisory beyond MAI-2026-003) — the Vibe family stays corpus-gap candidacy. Flagged but not filed: the 'agent O' rumor (still unconfirmed); the Plugin4Shell CVE claim (zero CVE-db hits — treated as suspect, not assigned); Hugo CVE-2026-100690 (aggregator coverage only). (#603)

- Self-update (#532): `deploy/toolset-update.sh` gains the `cua-driver` updater layer — enforces the pinned version in the installed `scripts/self_update_pins.conf` on every `update`: no-op when on pin; on absence or drift, downloads the exact pinned release asset from GitHub, verifies SHA-256 against the release's `checksums.txt` (exact filename match), and installs atomically (staging + rename) with the live binary never partially written; fail-closed on missing/unsafe pins, unparseable versions, checksum mismatches, and missing asset entries — and never restarts the CUA daemon. `install` now also backfills the installed pins file; audit lines carry the component list so failed layers are named. 42 hermetic tests in `deploy/test_toolset_update.py`. (#604)
- Competitor corpus update (night watch, 2026-09-28): quiet pass — no new corpus entries; the first fully-quiet vendor re-verification pass of the nightly series. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog (the Ember-1 index-vs-page consistency check stays in the routine — AI-Gateway model-availability, never folded), and E2B/boat.dev/ TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged ~3 days before the Oct 1 start. Vercel Drives is still public beta — the GA expectation is re-checked daily. The news scan surfaced nothing new in-lane. No corpus aging this pass; the Baseten/Blaxel integration item has two consecutive quiet passes. Flagged but not filed: the 'agent O' rumor (still unconfirmed); the Plugin4Shell 'CVE-2026-92104' claim (appears fabricated — zero CVE-db hits); third-party coverage of the OpenAI infra wave's DNS-escape detail (not folded); the Mistral Vibe family (no new member); Hugo CVE-2026-100690 (aggregator coverage only); Vercel Drives GA (no third-party chatter, still beta). (#601)

- Competitor corpus update (night watch, 2026-09-27/28): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), E2B/boat.dev/TermSquad/ DigitalOcean/AgentComputer pricing, and Modal egress billing; one verified delta: the Vercel Ember-1 index item is re-listed (new '27 September' section at the top of the changelog — AI-Gateway model-availability, never folded, no corpus effect). The sandbox lane is unchanged (memory observability 9/25, Drives public beta 9/23). The news scan surfaced nothing new in-lane. No corpus aging this pass (aging contact keys on fresh publications, never on recrawls). Flagged but not filed: the 'agent O' rumor (still unconfirmed); Plugin4Shell (still no CVE); third-party OpenAI infra-wave DNS-escape color (not folded); the Mistral Vibe family (no new CVE member). (#599)
- SSH-key-as-account registry gains key rotation: an operator who still holds their old key can rotate to a new one — the new key registers as a new account (the identity-is-the-key policy stands), the old record keeps a forward link, the box binding carries over, and a bounded rotation journal records the lineage. Lost-key rotation still needs the claim protocol. (#600)
- Competitor corpus update (night watch, 2026-09-27): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), E2B/boat.dev/TermSquad/DigitalOcean/ AgentComputer pricing, and Modal egress billing; one verified delta: the cycle-9 Ember-1 retraction ambiguity is resolved (the 2026-09-27 'Ember-1 from Fireworks on AI Gateway' page renders live at its own URL but is delisted from the changelog index — AI-Gateway model-availability, never folded, no corpus effect). The sandbox lane is unchanged. The news scan surfaced nothing new in-lane. Corpus aging reset this pass (the Baseten/Blaxel integration item, the OpenAI infra wave, and the Huawei Cloud CodeArts Malaysia entry each had in-window contact). Flagged but not filed: the 'agent O' rumor (still unconfirmed); Plugin4Shell (still no CVE); a third-party Anthropic agent-escape claim (not folded); the Mistral Vibe family (no new CVE member); the FastGPT E2B deprecation (pre-window). (#597)
- Competitor corpus update (night watch, 2026-09-27): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), E2B/boat.dev/TermSquad/DigitalOcean/ AgentComputer pricing, and Modal egress billing; one verified delta: the Vercel changelog's 2026-09-27 Ember-1 entry is absent from the live page in three consecutive fetches (withdrawn or a baseline render artifact — AI-Gateway model-availability, never folded, no corpus effect). The sandbox lane is unchanged. The news scan surfaced nothing new in-lane. Corpus movement: the Docker Cloud Sandboxes CVE-family watch aged out after three consecutive quiet passes (vendor facts retained as canonical reference; re-fold on resurface). Flagged but not filed: the 'agent O' rumor (still unconfirmed); Plugin4Shell (still no CVE); the SecMate Mistral Vibe writeup (third-party, no new CVE member); the Mistral Vibe family (stays corpus-gap candidacy). (#595)

- Competitor corpus update (night watch, 2026-09-27): quiet pass — no new corpus entries. Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), the Vercel changelog (the 2026-09-27 Ember-1 entry is AI-Gateway model-availability, not Sandbox), and E2B/boat.dev/TermSquad/DigitalOcean/AgentComputer pricing; Modal egress billing unchanged. Vercel Drives GA not re-checked (daily cadence, next due 2026-09-28). The news scan surfaced nothing new in-lane. Corpus movement: Boxd aged out after three consecutive quiet passes (the verified 2026-09-23 rate card is retained as canonical reference; re-fold on resurface). Flagged but not filed: the 'agent O' rumor (still unconfirmed); the Baseten/Blaxel integration item (file on close); the Plugin4Shell Sep-17 coding-agent supply-chain RCE (no CVE — re-fold on new exploitation or a first-party vendor response); the FastGPT E2B deprecation (pre-window); the Mistral Vibe family (stays corpus-gap candidacy). (#594)
- SSH-key-as-account identity now has its box-side account store: a per-host fingerprint→account registry remembers which keys have been seen (creation/last-seen timestamps, key type, box binding — box bindings rebind explicitly, never silently) so that a later connect-time hook can register a key on first connect and resume the same account on reconnect. No claim state yet — the claim protocol is a later slice (S3, #446). (#569)
- Tenant-status endpoint docs: the G10 rule-7 follow-up is closed — `docs/TENANT_STATUS_ENDPOINT.md` rule 7's "only legal cross-session moves" enumeration now includes the fourth move, `stuck` → `provisioning` (operator reprovision of a stalled-then-reimaged box; the §2 `stuck` row already named this as the reprovision exit, and the old image is gone so no resume path exists), and the §8 multi-box monotonicity gloss parenthetical now names all four cross-session moves instead of two. (#593)
- Competitor corpus update (evening watch, 2026-09-27): quiet pass — no new corpus entries. Two verified deltas: the Vercel changelog gained a 2026-09-27 entry ('Ember-1 from Fireworks now available on AI Gateway' — AI-Gateway model-availability, not Vercel Sandbox, flagged-only) and the Boat legacy-domain redirects are gone (the old ASCII domains now serve Boat natively — the ASCII→Boat domain migration is complete). Re-verified unchanged: the Daytona changelog (SEP 26 V0.218.0), Docker Sandboxes release notes (2026-09-22), Microsandbox (v0.7.3), E2B/boat.dev/TermSquad/ DigitalOcean/AgentComputer pricing, and Modal egress billing. The DigitalOcean pricing page's 'Last verified 22 Sep 2026' stamp is present (resolving an earlier capture gap as a capture artifact). The news scan surfaced two new-with-evidence items, neither filed: the 'agent O' rumor's seventh daily echo (still unconfirmed — no corpus entry assigned) and Mistral CVE-2026-93993 substance (pre-trust git-hook RCE, CVSS 8.8, pre-window Sep-23 disclosure — not folded; the Vibe family stays corpus-gap candidacy). No corpus aging this pass. (#592)
- CI now runs the repository's full test suite on every push — the same single test command contributors run locally (`python3 -m pytest`, `pytest.ini` testpaths) — so a test suite can no longer land without CI ever executing it. A new `scripts/test_pytest_ini_covers_all.py` drift pin fails the run if any `test_*.py` sits outside the testpaths inventory, and the branch-protection ruleset now also requires the changelog ritual lint check that was added earlier without being added to the ruleset. (#591)
- Competitor corpus hygiene: the deprecated ASCII→Boat corpus row was removed — every one of its facts now lives in the canonical Boat row, and the expiry convention's first removal was executed by a consolidation pass. Pre-deletion re-verification: the vendor has since hardened the rename itself — `box.ascii.dev` and `ascii.dev` now redirect to `boat.dev` (replacing the parallel legacy pages), and the legacy docs URL redirects into `docs.boat.dev` while still branding the API "Boat Public API v1"; pricing and the YC-company-page redirect re-verified unchanged. (#590)
- Hosted gap analysis names the missing tenant-box update story: no update channel exists for tenant boxes (operator reprovision is the only renewal path), the tenant status vocabulary has no maintenance state, and nobody has defined who authorizes updates on a tenant's box — four follow-up gaps filed (#553, #554, #555, #556). (#557)
- Competitor watch note: the NanoClaw/NanoCo parent call is closed — a first-party read of NanoCo's own site shows NanoClaw is an open-source personal AI agent that runs locally in Docker containers, not a sandbox or compute product, so no corpus entry is warranted; the deferred watch-review nits were re-verified, and the deprecated-corpus-row expiry convention is now codified (deprecated rows are removal candidates once their facts are folded, with deletion reserved to consolidation passes). (#589)
- Competitor corpus update: Modal network-egress pricing verified on Modal's own docs — billed from Oct 1, 2026; per-cycle allowances 1 TiB (Starter) / 10 TiB (Team) / 100 TiB (Enterprise); $0.04/GiB overage; usage visible since Sep 1 with the first egress bill Nov 1; the most detailed sandbox-egress pricing on file. (#587)
- Self-update reconciliation (#532): the two competing first-slice implementations ship together as complementary planes — `scripts/self_update.py` is the unprivileged read-only status plane (version inventory + drift vs pins), `deploy/toolset-update.sh` is the privileged update plane (weekly timer, idle gate, audit, opt-out, per-layer updaters, starting with `os-security`) — with `scripts/self_update_pins.conf` as the single canonical pin file and a corrected S1/S2/S3 slice map in `docs/SELF_UPDATE.md` ("Two planes"); supersedes #542 and #551, whose code trees land identical to their reviewed heads (scripts/ byte-identical; deploy/ carries only the review round-1 trust-model comment corrections), plus the review-found fixes in this pass (pins-file crash-hardening so malformed bytes can't break the status plane's always-exits-0 contract, and a hardened B1 regression guard on the pattern-less probe path). (#588)
- Toolset self-update v0: `deploy/toolset-update.sh` (status/update/install/uninstall/optout/optin/version) plus `sparkvm-toolset-update.{service,timer}` (weekly Sunday 03:00 local, randomized delay). Installed-copy trust model, conservative idle gate (defers on `mjob-*` tmux sessions), single-flight flock, JSONL audit, machine-wide opt-out. Real updater layer for `os-security` only (ensures `unattended-upgrades` present and `20auto-upgrades` exact, idempotent, `--dry-run`); docker/node/npm/gh/playwright/cua-driver are status probes only — component updaters, snapshots/rollback, health checks, failure freeze, and the independent backup recovery path are follow-ups under #532. 27 hermetic tests (`deploy/test_toolset_update.py`), wired into CI. (#551)
- Self-update system (issue #532), first slice: a new read-only `self-update status` command reports every provisioned-default tool's installed version against the known-good pin list (docker, node, gh, Playwright + browsers, snaps, OS auto-updates, cua-driver, cred/swapd, muse-job), flagging drift — user-installed tools (Tailscale, KiCad, Muse CLI, Blender) are out of scope; nothing is installed or changed. (#542)
- Competitor-watch consolidation scheme proposed: weekly-digest packaging for the hourly watch series (full docs only on genuine deltas, one index row per week, older docs archived with history intact) — proposal pending adoption; details in the docs index. (#585)
- Competitor corpus update (evening cycle-3 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~17:12–~17:13 CDT (2026-09-27) baseline, vendor reads ~18:26–~18:28 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 24; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — tenth consecutive pass, capture-gap, not a delta); B: delta news scan ~17:55–~18:26 CDT, ~30-min window, 20 queries, snippet level, zero pages opened): quiet pass — **no new corpus entries** (0 new; 12 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. The unconfirmed "agent O" model rumor keeps echoing (sixth daily cycle, still unverified) ahead of OpenAI's Sep 29 DevDay — a confirmation would file as a new corpus entry. (#583)
- Competitor corpus update (afternoon cycle-3 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~16:56–~16:57 CDT (2026-09-27) baseline, vendor reads ~17:12–~17:13 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 23; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — ninth consecutive pass, capture-gap, not a delta); B: delta news scan ~16:55–~17:55 CDT, ~60-min window, 17 queries, snippet level, zero pages opened): quiet pass — **no new corpus entries** (0 new, recrawl contacts, 20 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#582)
- Competitor corpus update (midday cycle-3 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~16:25–~16:26 CDT (2026-09-27) baseline, vendor reads ~16:56–~16:57 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 22; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — eighth consecutive pass, capture-gap, not a delta); B: delta news scan ~16:25–~16:55 CDT, ~30-min window, 16 queries, snippet level, zero pages opened): quiet pass — **no new corpus entries** (0 new, recrawl contacts, 18 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#581)
- Competitor corpus update (late-morning cycle-3 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~15:55–~15:56 CDT (2026-09-27) baseline, vendor reads ~16:25–~16:26 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 21; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — seventh consecutive pass, capture-gap, not a delta); B: delta news scan ~15:55–~16:25 CDT, ~30-min window, 16 queries, snippet level, zero pages opened): quiet pass — **no new corpus entries** (0 new, recrawl contacts, 15 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#580)
- Competitor corpus update (morning cycle-3 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~15:26–~15:27 CDT (2026-09-27) baseline, vendor reads ~15:55–~15:56 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 20; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — sixth consecutive pass, capture-gap, not a delta); B: delta news scan ~15:25–~15:55 CDT, ~30-min window, 15 queries, snippet level, zero pages opened): quiet pass — **no new corpus entries** (0 new, recrawl contacts, 10 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#579)
- Competitor corpus update (predawn cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~14:55–~14:57 CDT (2026-09-27) baseline, vendor reads ~15:26–~15:27 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 19; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — fifth consecutive pass, capture-gap, not a delta); B: delta news scan ~14:55–~15:25 CDT, ~30-min window, 16 queries, snippet level): quiet pass — **no new corpus entries** (0 new, 15 recrawl contacts, 9 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. The unconfirmed "agent O" model rumor ahead of OpenAI's Sep 29 DevDay is intensifying — still unverified; Hugo CVE-2026-100690 noted (third-party re-ingest, not filed — no agent-infra nexus). (#578)
- Competitor corpus update (post-night cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~14:25–~14:28 CDT (2026-09-27) baseline, vendor reads ~14:55–~14:57 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 18; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — fourth consecutive pass, capture-gap, not a delta); B: delta news scan ~14:25–~14:55 CDT, ~30-min window, 16 queries, snippet level): quiet pass — **no new corpus entries** (0 new, 15 recrawl contacts, 8 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. Hugo CVE-2026-100690 and the Mistral Vibe worktree CVE batch (CVE-2026-87983–87988) noted but not filed — no agent-infra nexus. (#577)
- Competitor corpus update (night cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~13:56–13:59 CDT (2026-09-27) baseline, vendor reads ~14:25–~14:28 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 17; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — third consecutive pass, capture-gap, not a delta); B: delta news scan ~14:02–14:25 CDT, ~23-min window, 14 queries, snippet level): quiet pass — **no new corpus entries** (0 new, recrawl contacts & clean dedupes, 10 flagged-only). CVE-2026-79994 was already filed as part of the Docker CVE-2026-77179/79994 pair — no new entry. No deep-scan leads filed: Hugo CVE-2026-100690 and the Mistral Vibe CVE batch (CVE-2026-87983–87988) stay flagged-only — pre-window, marginal lane, no agent-infra nexus. Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#576)
- Competitor corpus update (late-evening cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~13:31–13:35 CDT (2026-09-27) baseline (vendor reads ~13:56–13:59 CDT), 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 16; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — capture-gap, not a delta); B: delta news scan ~13:40–14:02 CDT, ~22-min window, 10 queries, ~62 results): quiet pass — **no new corpus entries** (0 new, ~19 recrawl contacts & clean dedupes, ~12 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#575)
- Competitor corpus update (evening cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~12:56–13:00 CDT (2026-09-27) baseline ~13:31–13:35 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 15; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read either — capture-gap, not a delta); B: delta news scan ~13:05–13:40 CDT, ~35-min window, 10 queries, ~55 results): quiet pass — **no new corpus entries** (0 new, ~17 recrawl contacts & clean dedupes, ~9 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#574)
- Competitor corpus update (afternoon cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~12:27–12:29 CDT (2026-09-27) baseline, vendor reads ~12:56–13:00 CDT: 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 14; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible — capture-gap, not a delta); B: delta news scan ~12:42–13:05 CDT, ~23-min window, 10 queries): quiet pass — **no new corpus entries** (0 new, ~15 recrawl contacts & clean dedupes, ~11 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#573)
- Competitor corpus update (midday cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~11:58–12:02 CDT (2026-09-27) baseline ~12:27–12:29 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 13; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy; DO "Last verified 22 Sep 2026" stamp not visible this read — capture-gap, not a delta); B: delta news scan ~12:20–12:42 CDT): quiet pass — **no new corpus entries** (0 new, 12 clean dedupes & recrawl contacts, 9 flagged-only). Sandbox-infrastructure lane stays quiet; in-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#571)
- Expired approvals now show an Expired badge in the answered history (amber, distinct from Approved/Denied, with when it expired and which side reaped it), and an expired approval's "gone" page links to that history entry when a terminal expired record exists — the owner no longer lands on a dead end. (#572)
- Competitor corpus update (late-morning cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~11:26–11:31 CDT (2026-09-27) baseline ~11:58–12:02 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE (all first-try — streak extends to 12); B: delta news scan ~11:45–12:20 CDT): quiet pass — **no new corpus entries** (12 recrawl contacts, 5 clean-dedupe groups, 11 flagged-only). Deep-scan lead noted, NOT filed: Pillar Security "coding agent sandbox escape" pattern (snippet-level only, no primary source). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes notes still 2026-09-22; Microsandbox still v0.7.3; Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy). **Delta news scan — 0 new** (recrawl contact: the OpenAI offline-sandbox escape, the Baseten/Blaxel integration watch, the Huawei CodeArts Agent (Malaysia) entry, the Docker CVE-2026-77179/79994 family, DigitalOcean Managed Agents; clean-dedupe groups: Docker CVE-2026-77179/79994-era Docker CVE five-pack, Vercel Sandbox Drives analysis, Modal $15B-raise talks reprints (the Modal row), own watch docs, Docker release-notes page). **11 flagged-only, NOT filed** (techtimes DeepSeek DSec piece — pre-window DeepSeek Harness CVE-2026-82533 context; orca-ai-incident-archive CVE-2026-82533 — DeepSeek Harness CVE-2026-82533 recrawl contact, stays aged out; dev.to Codex Sandbox Escapes — pre-window; nitiweb Modal "$2.5B talks" — stale URL ignored; DCD Modal $355M Series C — pre-window; cyberpress Docker CVE writeups — pre-window; Medium Jannis 0.43 feature — pre-window; CVE-2026-53362 "Frag Gap" — no fresh movement, noted corpus gap; techinasia CodeArts HarmonyOS upgrade — pre-window; cryptobriefing DevDay rumor — still rumor, Sep 29; dev.to comparison op-ed — opinion). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. (#570)
- Competitor corpus update (morning cycle-2 watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~10:55–10:59 CDT (2026-09-27) baseline ~11:26–11:31 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance, 9/9 first-try (all-first-try streak extends to 11; Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no 26/27-Sep entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical; AgentComputer still publishes no egress policy); B: delta news scan ~11:10–11:45 CDT): quiet pass — **no new corpus entries** (0 new, 14 clean dedupes, 4 flagged-only). Naming: label rotated again after NIGHT per the naming-hygiene rule — MORNING (cycle 2), `_C2` disambiguator since MORNING already names today's 05:5x pass. Sandbox-infrastructure lane stays quiet. (#567)
- Owner grants expiring within 5 seconds are no longer spent on new swaps: the enforcement side now skips a grant whose remaining validity is under a small window (tunable via `SWAP_GRANT_MIN_VALIDITY_S`, `0` disables the guard) and the request falls through to the normal grant-less refusal, so the owner re-approves instead of a dying grant being consumed by a swap that would outlive it. (#568)
- Competitor-watch corpus hygiene: the docs index now covers all 2026-09-27 watch passes (the midday, late-afternoon, evening, and late-evening passes were previously missing index rows); the stale-version dedupe rule's "corpus" is defined canonically (every watch-pass doc plus the competitor-analysis doc and the changelog) in the competitor-analysis conventions; and aged-out items return to active tracking only on real movement — new vendor action, launch/funding/GA/CVE, or first-party confirmation. This pass's night watch (two-surveyor pass): vendor pricing/release notes 9/9 verified unchanged (Daytona changelog still SEP 26 V0.218.0, Docker Sandboxes notes still 2026-09-22, Microsandbox still v0.7.3, Vercel changelog still 25 September — no new entries; E2B, boat.dev, TermSquad, DigitalOcean, AgentComputer pricing all identical); news scan over the ~100-min window found no new in-lane launches, fundings, or pricing moves (8 clean dedupes, 6 flagged-only pre-window/out-of-lane items). Corpus movement: the DeepSeek Harness sandbox-escape item (CVE-2026-82533) aged out after three consecutive quiet passes; the Baseten/Blaxel acquisition item is still drawing coverage; the OpenAI offline-sandbox escape still shows no movement; the Huawei Cloud CodeArts Agent Malaysia entry stays first-party corroborated; AgentComputer still publishes no egress policy. (#564)
- Competitor corpus update (late-morning watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~05:55 CDT (2026-09-27) baseline ~06:25–06:30 CDT, 9/9 first-try, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (all-first-try streak extends to 4; Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox still v0.7.3; Vercel changelog still 25 Sep — no 26/27-Sep entries; Drives not re-checked per P49 daily cadence, next due 2026-09-28; DO canonical pricing URL loads 200, figures verbatim identical, snapshot-figure discrepancy unresolved but unmoved); B: delta news scan ~05:54–06:37 CDT): **one new corpus entry: the Huawei CodeArts Agent (Malaysia) entry (in-lane, THIRD-PARTY) — Huawei Cloud CodeArts Agent commercial-availability launch in Malaysia (2026-09-27)** (single regional-outlet source, corroboration pending; first Huawei-hosted-agent corpus entry; no sandbox-infrastructure angle). 7 clean dedupes (DevDay "O" rumor, Docker launch wave, DO Managed Agents, Drives write-up, Meta Muse VM deep-dive, the OpenAI offline-sandbox escape reprint, Daytona $24M reprint recrawls — all filed, no new facts). 5 flagged-only NOT filed (CVE-2026-100721 vm2 escape — NEW TO CORPUS but pre-window, marginal lane; AgntBox/Cornelis $205M; Nscale $3.36B; OpenEvidence $15B; orbitalab Tier-1 leakage study). **The in-lane no-launch verdict dated 2026-09-25 ENDS this pass** — the Huawei CodeArts Agent (Malaysia) entry is an in-lane hosted-agent-coding launch (regional market expansion, single third-party source, corroboration pending); the sandbox-infrastructure lane itself remains quiet. Carried: Freestyle, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified), the OpenAI offline-sandbox escape (no movement), the Huawei CodeArts Agent (Malaysia) entry (new this pass); DigitalOcean Managed Agents pricing closed; AgentComputer still publishes no egress policy. OpenClaw CVE-2026-100589 aged out after three consecutive quiet passes. (#548)
- Competitor corpus update (morning watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~04:56 CDT (2026-09-27) baseline ~05:55 CDT, 9/9 first-try, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (all-first-try streak extends to 3; Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence, next due 2026-09-28; DO canonical pricing URL loads 200, figures identical; still no "Last verified" stamp; DO snapshot-figure discrepancy unresolved but unmoved); B: delta news scan ~04:54–05:54 CDT): quiet pass — **no new corpus entries** (0 new, 4 clean dedupes: Docker Sep-24 press wave Forkast recrawl; OpenAI DevDay "O" leak rumor recrawl — third-party-only, distinct from the OpenAI offline-sandbox escape, not a launch; DigitalOcean Managed Agents syndicated press-release reprints; CVE-2026-80521 write-up recrawls — all filed, no new facts; 1 flagged-only NOT filed: CVE-2026-43503 "DirtyClone" K8s escape PoC ~Sep 25 — June CVE, pre-window, not a vendor/product story; near-miss candidate only). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Naming: label rotated from the EARLY_MORNING series to MORNING (chains rotate, not stack). Carried: Freestyle, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified), the OpenAI offline-sandbox escape (no movement), OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed; AgentComputer still publishes no egress policy. (#547)
- Competitor corpus update (early-morning watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~04:25–04:27 CDT (2026-09-27) baseline ~04:56 CDT, 9/9 first-try, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (all-first-try streak extends to 2; Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence; DO canonical pricing URL loads 200, figures identical; still no "Last verified" stamp); B: delta news scan ~04:24–04:54 CDT): quiet pass — **no new corpus entries** (0 new, 4 clean dedupes: Docker Sep-24 press wave reprints; DeepSeek Harness CVE-2026-82533 write-ups; Docker CVE-2026-77179/79994 write-up; OpenAI training-sandbox-escape coverage wave — recrawl of the story flagged in the 0154 pass, deduped at 0224, clean dedupe at 0424 (review reclassified per the 0224 recrawl precedent), no new facts — lane-adjacent containment color, not a fold). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Naming: label rotated from the six-deep POST_ pre-dawn chain to the new EARLY_MORNING series per the 0424 doc's naming-hygiene advisory. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed; AgentComputer still publishes no egress policy. (#544)
- Competitor corpus update (post-post-post-post-post-pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~03:24–03:30 CDT (2026-09-27) baseline ~04:25–04:27 CDT, 9/9 first-try, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (DO canonical pricing URL now loads 200 — figures re-verified verbatim, all identical; still no "Last verified" stamp); B: delta news scan ~03:30–04:24 CDT): quiet pass — **no new corpus entries** (0 new, 4 clean dedupes: Docker Sep-24 press wave reprints; DeepSeek Harness CVE-2026-82533 write-ups; Docker CVE-2026-77179/79994 write-up; OpenAI training-sandbox-escape Sept-26/27 coverage — recrawl of the story already flagged in the 0154 pass and deduped at 0224, no new facts — lane-adjacent containment color, not a fold). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. AgentComputer still publishes no egress policy. (#543)
- Competitor corpus update (post-post-post-post-pre-dawn watch, single-surveyor pass — A: fast-mover + pricing re-verification vs ~02:57 CDT (2026-09-27) baseline ~03:24–03:30 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (DO Managed Agents pricing page moved to a new canonical URL — old URL 404s — figures re-verified verbatim, all identical; the "Last verified 22 Sep 2026" stamp is gone from the new page, presentation change not pricing; 8/9 first-try); B: delta news scan ~02:57–03:30 CDT): quiet pass — **no new corpus entries** (0 new, 3 clean dedupes: Docker Sep-24 press wave reprints; DeepSeek Harness CVE-2026-82533 write-ups; Docker CVE-2026-77179/79994 write-up; 0 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev (canonical docs.boat.dev/pricing), TermSquad, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still publishes no egress policy). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. (#541)
- Competitor corpus update (post-post-post-pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~02:25–02:26 CDT (2026-09-27) baseline ~02:55–02:57 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE (DO pricing failed once, re-verified on worker retry ~02:57 CDT — all-first-try streak ends at 9); B: delta news scan ~02:26–02:57 CDT): quiet pass — **no new corpus entries** (10 clean dedupes, 10 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev (canonical docs.boat.dev/pricing), TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still publishes no egress policy). **Delta news scan — 0 new** (10 clean dedupes: Docker Sep-24 press wave; Modal $15B raise talks; DeepSeek Harness CVE-2026-82533 write-ups; Docker CVE-2026-77179/79994; Codex Heapjack/Overpatch disclosures; Runloop reprint; Upstash comparison; Boxd $2M; Go.AI $85M; Nscale $3.36B). **10 flagged-only, NOT filed** (Sandlock release — borderline lane, snippet-only; vm2 CVE-2026-47686 — lane-drift; Island $400M Series F — out-of-window + adjacent; PicoJool $27.5M — out-of-window + lane-drift; DO Managed Agents third-party write-up recrawls; OpenAI "O" DevDay rumor recrawl; Daytona PR reprints; Daytona $24M recrawls; Nova "Daytona vs E2B" doc; vercel/sandbox@3.4.0 snippet — superseded by live vendor read). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. (#538)
- Competitor corpus update (post-post-pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~01:57–01:58 CDT (2026-09-27) baseline ~02:25–02:26 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE (all first-try; canonical docs.boat.dev/pricing); B: delta news scan ~01:40–02:26 CDT): quiet pass — **no new corpus entries** (10 clean dedupes, 14 flagged-only). Adopts the corpus aging rule: an item leaves active tracking after three consecutive quiet passes, with a one-notice line in the pass doc; this pass ages out the Heapjack/Overpatch sandbox-escape disclosures, the GitLab proxy escape (CVE-2026-85706), and Dextr AI. **Fast movers 9/9 NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still publishes no egress policy). **Delta news scan — 10 clean dedupes** (Docker Sep-24 press wave; Modal $15B raise talks; DeepSeek Harness CVE-2026-82533; Docker CVE-2026-77179/79994; Codex escape disclosures; Boxd $2M pre-seed; OpenAI training-escape press recrawl). **14 flagged-only, NOT filed** (OpenAI "O" DevDay rumor; Daytona v0.171.0 stale recrawl; Modal $2.5B/$355M recrawls; Runloop Devboxes reprint; Nscale $3.36B; Go.AI $85M; Raindrop $50M; Vercel-Sandbox commentary recrawls). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. (#533)
- Competitor corpus update (pre-dawn late watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~01:28–01:38 CDT (2026-09-27) baseline ~01:57:53–01:58:26 CDT, zero fetch failures; B: delta news scan ~01:40–01:58 CDT): quiet pass — **no new corpus entries** (10 clean dedupes, 4 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; canonical docs.boat.dev/pricing figures identical; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still publishes no egress policy). **Delta news scan — 0 new** (10 clean dedupes: Daytona $24M Series A recrawl; Daytona "agent-agnostic/OpenHands" PR stale-recrawl ruled out by full-text verification; Modal $15B talks; Docker Sep-24 press wave; DO Managed Agents preview Sep 22; Docker CVE-2026-77179/79994; DeepSeek CVE-2026-82533 write-ups; Codex disclosures; Factory $200M; Meta Muse + Google AX/Cognition). **4 flagged-only, NOT filed** (OpenAI training-sandbox escape + pause — internal containment, not a CVE; Cornelis Networks $205M — hardware; LangChain/agent-framework batch — lane fail; NsideSignal — Sep 16). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. (#531)
- Competitor corpus update (post-pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~00:55–01:00 CDT (2026-09-27) baseline ~01:28–01:38 CDT, 9/9 VENDOR-VERIFIED NO-CHANGE on substance (boat.dev/pricing now 404s — canonical pricing page is docs.boat.dev/pricing, figures identical); B: delta news scan ~01:15–01:40 CDT): quiet pass — **no new corpus entries** (9 clean dedupes, 4 flagged-only). **Fast movers 9/9 NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still publishes no egress policy). **Delta news scan — 9 clean dedupes** (Boxd $2M pre-seed recrawls; ByteAsk $1M pre-seed recrawls; DeepSeek Harness CVE-2026-82533 write-ups; vm2 CVE-2026-47686 analysis recrawl; sandbox-landscape research recrawls; own-doc recrawls; Jenkins Script Security sandbox-escape cluster — pre-window, lane-drift). **4 flagged-only, NOT filed** (Modal $15B raise talks — Sep 26, in-lane, window fail; Google AX substack analysis — 6d old; Cognition ~$1B raise — 6d old; Clastix €2.9M seed — Sep 24, lane fail). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. (#530)
- Competitor corpus update (pre-dawn watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~23:55–23:57 CDT (2026-09-26) baseline ~00:55–01:00 CDT, all first-try (streak extends to 9); B: delta news scan ~00:35–01:15 CDT): quiet pass — **no new corpus entries** (12 clean dedupes, 8 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still publishes no egress policy). **Delta news scan — 12 clean dedupes** (Docker Cloud Sandboxes Sep-24 launch syndications; Factory $200M / $5B raise recrawls; Boxd $2M pre-seed recrawls; StartupHub + DEV comparison editorial recrawls). **8 flagged-only, NOT filed** (vm2 CVE-2026-47686 — Aug 17, in-lane, window fail; vm2 <3.11.8 AggregateError escape — Sep 17, window fail; DeepSeek Harness CVE-2026-82533 — Sep 8, window fail; Docker Sandboxes CVE-2026-77179/79994 — Sep 15, window fail; CVE-2026-80521 Ubuntu container escape — Sep 22, window fail; ByteAsk $1M pre-seed — Sep 24, window fail; Meta Muse personal-agent launch — lane fail; Salesforce/NVIDIA "Koa" CRM model — lane fail). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. (#528)
- Tenant status design: resolved the two `TENANT_STATUS_ENDPOINT.md` §7 open questions blocking G3's S1 implementation (G7: multi-box tenants — the endpoint tracks the tenant's onboarding arc per-tenant with a most-advanced-incomplete-arc rule (monotonic: the reported code never regresses; ties → newest by `created_at`), “tenant reaches `live`” = the first box's arc reaches `live`, box identity in the free-form `detail` sub-code, no `box_id` schema sibling, and the stall detector emits one tenant-level stall; G8: the signup step that hands the human the approvals-page URL at activation-funnel stage 2 owns the `approvals_url` write — write-if-absent + re-read (renders the stored value), funnel re-entry is a read path that never rotates mid-arc, rotation only via an explicit operator event). `FIRST_APPROVAL_SUMMONS.md` §2 sequencing updated: the summons deep link is now licensed and G4's S2 sequencing dependency clears. (#527)
- Competitor corpus update (post-night watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~23:26 CDT baseline ~23:55–23:57 CDT, all first-try (streak extends to 8); B: delta news scan ~23:55–00:35 CDT): quiet pass — **no new corpus entries** (4 clean dedupes, 5 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still publishes no egress policy). **Delta news scan — 4 clean dedupes** (Daytona $24M-raise recrawls — stale; Docker Cloud Sandboxes Sep-24 launch recrawls — no new development; Vercel Sandbox Drives Sep-23 beta editorial recrawl; Daytona pitch-deck field-guide recrawl — Feb-2026 Series A restatement). **5 flagged-only, NOT filed** (Dextr AI $6.7M seed — hotel-hospitality agents, lane fail; Nscale $3.36B convertible — neocloud GPU compute, lane fail; 0G "Compute Finance" — tokenized compute, lane fail; Okta internal "Dex" agent — name collision, lane fail; Upstash 15-provider comparison — 10 days old, editorial, window fail). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. **Aged out: Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706); Dextr AI stays aged out.** Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. (#526)
- The changelog ritual is now a CI gate: entries referencing internal working-note paths that never exist in a reader's checkout are rejected automatically; 23 such dead pointers in competitor-watch entries were scrubbed. (#525)
- Competitor corpus update (night watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~22:25–22:35 CDT baseline ~23:26 CDT, all first-try (streak extends to 7); B: delta news scan ~22:25–23:55 CDT): quiet pass — **no new corpus entries** (9 clean dedupes, 2 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still publishes no egress policy). **Delta news scan — 9 clean dedupes** (the OpenAI offline-sandbox escape recrawls; the OpenAI offline-sandbox escape and agent-swarm nine-zero-days re-report; DeepSeek CVE-2026-82533 = DeepSeek Harness CVE-2026-82533; Docker CVE-2026-77179/79994 = the Docker CVE-2026-77179/79994 family family; Vercel Sandbox Drives Sep-23 public beta already in baseline; Daytona $24M + E2B $21M raise recrawls — stale; TermSquad + Modal quiet). **2 flagged-only, NOT filed** (Docker Cloud Sandboxes launch GlobeNewswire Sep 24 — in-lane but out-of-window and already the filed Docker row, NOT a backfill candidate; ComputeSDK 1.0.0 — third-party SDK wrapper, lane fail). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Aging next pass if still quiet: Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706); Dextr AI stays aged out. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. (#524)
- Competitor corpus update (post-post-post-post-post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~21:27–21:45 CDT baseline ~22:25–22:35 CDT, all first-try (streak extends to 6); B: delta news scan ~21:45–22:25 CDT): quiet pass — **no new corpus entries** (7 clean dedupes, 2 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still publishes no egress policy). **Delta news scan — 7 clean dedupes** (the OpenAI offline-sandbox escape recrawls incl. the Bloomberg re-report updated 2026-09-27 06:14 AM IST ≈ 19:44 CDT Sep 26; the OpenAI offline-sandbox escape and agent-swarm nine-zero-days recrawl; DeepSeek DSec reward-hacking recrawl CVE-2026-82533 pre-window; Vercel Sandbox Drives public beta confirmed Sep 23 — already in baseline; Accomplish sandbox-escape disclosures Sep 12 pre-window; Guava "Daytona" voice-model name collision out-of-lane; DevDay "O" always-on-agent rumor still speculation). **2 flagged-only, NOT filed** (dev.to "Copilot joins AI SDK, agents ship on Vercel" ~Sep 24 — ecosystem color, no sandbox launch; E2B/DEV + Upstash comparison recrawls — stale secondary). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Heapjack/Overpatch and the GitLab proxy escape (CVE-2026-85706) were both quiet this pass. Carried: Freestyle pricing, the Cloudflare disk-residue disclosure, Baponi, Leap0 (pricing vendor-verified); the OpenAI offline-sandbox escape (no movement); OpenClaw CVE-2026-100589 (open, third-party coverage only); DigitalOcean Managed Agents pricing closed. (#521)

### Changed
- Restored the changelog-ritual preamble that PR #586's bullet scrub removed, and codified the scrub's reader-facing standard as a standing ritual rule (rule 6): competitor-watch bullets expand corpus identifiers (C-numbers) to product/paper/incident names, drop loop-internal workflow vocabulary, and keep quiet passes to one compact paragraph. The nine watch bullets added since the scrub (#592, #594, #595, #597, #599, #601, #603, #605, #611) are rewritten to that standard. (#614)
- Unreleased competitor-watch bullets are now reader-facing: internal corpus identifiers (C-numbers) are expanded to product, paper, and incident names, loop-internal workflow notes are removed, and two regressed watch PR references are restored to (#533) and (#531) (changelog ritual rule 1). (#586)
- Competitor-watch changelog prose is now reader-facing: released bullets (0.2.0–0.4.0) no longer reference internal corpus identifiers (C-numbers) — every released mention now names the product, paper, or incident directly, so the changelog reads without access to the competitor-analysis corpus (changelog ritual rule 1). (#529)

### Fixed

- Approval requests are now filed atomically: a crash mid-write can no
  longer leave a torn, permanently unanswerable entry in the pending
  queue. Corrupt pending entries that do appear are quarantined to a
  separate directory with an audit-trail event (after a short grace
  period, so an in-flight write is never misclassified), and stale
  temporary files from crashed writers are swept on the same pass.
  (closes #232) (#649)
- `muse-job kill` now reaps the job's whole process tree, not just the
  tmux session: detached background builds that used to survive the
  kill are terminated (SIGTERM, then SIGKILL) and any survivors are
  reported. (closes #12 item L4) (#649)
- The waitlist's consumed-token store no longer grows forever: the
  purge and forget-deletion paths now garbage-collect the token file
  alongside the rows rewrite, keeping only tokens a surviving entry
  still references and every consumed forget token (so a re-clicked
  delete link still renders "already deleted" instead of "expired").
  Dropped confirm/invite tokens render the same page as before —
  nothing the operator or the entrant sees changes. (#651)
- Every invite-wave invocation now writes a per-invocation manifest
  (wave name, time, requested count, invited and skipped entry IDs) to
  `wave_manifests/`, and the CLI prints the invited IDs plus the
  manifest path — so a crash mid-wave and its retry read as two
  manifests under the same wave name instead of one ambiguous count.
  (closes #405) (#651)
- confirmd's post-answer housekeeping no longer scans the answered and
  consumed history directories on every approval: the stray-file sweep and
  the history prune now run at most once an hour (tunable via
  CONFIRM_HOUSEKEEPING_INTERVAL_S), and the prune skips its per-file scan
  entirely when the history is within its keep limit — so answering stays
  fast as the history grows toward the thousand-entry bound. (closes
  #620) (#647)
- confirmd's browser-origin check now re-resolves the box's Tailscale DNS
  name every minute instead of once at startup (mirroring the self-peer
  address refresh): a tailnet DNS rename mid-daemon no longer leaves the
  owner's browser form submissions failing the origin check until a
  restart; a failed refresh keeps the last good origins rather than
  shrinking the accepted set, and operators who pin origins via
  CONFIRM_ORIGINS see no behavior change. (closes #619) (#623)
- The response scrubber now also masks the trimmed rendering of
  multi-entry credential values: previously only the exact stored bytes of
  a `name: entry` value were scrubbed, so a server echoing the value back
  without trailing whitespace would leak it into proxied responses. (closes
  #121) (#623)
- Credential registration is now atomic: registering a credential together
  with its host bindings lands in a single locked write, so a mid-save
  failure can no longer leave it registered with only some of its intended
  hosts ([#151](https://github.com/ntindle/spark-vm/pull/151), fixes
  [#116](https://github.com/ntindle/spark-vm/issues/116) and
  [#146](https://github.com/ntindle/spark-vm/issues/146))
- CUA desktop stack startup hardening: the bridge and keepalive no longer trust the desktop env file blindly — it is only consumed when it is a regular file owned by the service user with no group/other write permission, and the runtime directory it lives in is now created with private (0700) permissions, so another local user cannot inject values into the desktop's environment by planting the file (closes #493); and two overlapping keepalive runs can no longer double-spawn the bridge — the bridge takes an exclusive startup lock and exits if one is already running (closes #495). (#596)
- confirmd's synchronous expired reaps (the Finding 53(a) GET-detail and POST-answer paths) now stamp the S1 expired-approval terminal record before removing the pending file (stamp-then-delete, mirroring the render reap), so "expired between render and answer" leaves a terminal record in the answered history — the expired 410 page now links to it — instead of a bare removal with no record. (#598)
- Repeated swaps refused for the same credential/host/method no longer re-scan the whole approvals pending directory on every refusal: the pending-scan result is cached per credential/host/method, invalidated whenever the directory changes and additionally every 30 seconds, so expiry handling can lag at most that bound. (#568)
- The grant writer now enforces the approval's expiry at mint time: it refuses to mint when the approval's expiry instant has crossed (or is unreadable), checked against its own clock at the moment the grant would be created — so an expiry crossing during the grant call can't leave a live grant behind. (#549)
- Approvals are no longer granted in a race against their own expiry: an approval with less than 30 seconds of validity remaining is now refused up front (HTTP 410 with a distinct audit event) instead of minting a grant that could land after the approval had already expired — the grant writer has no revoke path. (#534)
- confirmd's self-peer address check now re-resolves the box's Tailscale IPs every minute instead of once at startup, so a tailscaled renumber mid-daemon can't silently disable the self-refusal boundary; a failed refresh keeps the last good set rather than shrinking the boundary. (#536)

### Security

- The credential-management web UI now runs under systemd sandboxing: its own private /tmp, and the whole OS tree mounted read-only except /home/swapd (where the narrow sudo writers legitimately read and write the credential store). An attacker who escaped the UI's Python process would find nothing writable to persist in. `NoNewPrivileges` stays off on purpose — the UI performs every credential operation through `sudo -n -u swapd`, which privilege-dropping would break; the kernel-tunable/module/cgroup directives stay off too, because they are system-unit-only and the UI runs as an unprivileged user unit. (#115) (#655)
- The swap proxy now refuses streaming responses (server-sent events and protocol upgrades) from allowed hosts by dropping the connection, instead of passing their bodies through unscrubbed: a stream never finishes, so the response-body scrubber can never see it, and the proxy would otherwise buffer a never-ending stream unboundedly. Clients that need the data should retry with streaming disabled. (#92) (#631)
- `cred set` no longer reads stdin unbounded before the swapd writer's 64 KiB cap: the frontend reads at most 64 KiB + a 2-byte chomp margin + 1 sentinel byte and refuses oversized input with a clear message itself, so piping a huge file can't balloon the CLI's memory (the cap existed one layer too late). The bound is on *bytes*, not decoded characters, so multibyte UTF-8 can't slip past; the cap mirrors `cred-store-set`'s `max_bytes=65536` exactly. (closes #149) (#602)

## [0.4.0] - 2026-09-26

### Added
- Competitor corpus update (post-post-post-post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~20:55–21:01 CDT baseline ~21:27–21:45 CDT, all first-try (streak extends to 5); B: delta news scan ~21:00–21:45 CDT): quiet pass — **no new corpus entries** (18 clean dedupes, 9 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; boat.dev "Compared to others" benchmark table is marketing content, no rate change; DO snapshot-figure discrepancy unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 18 clean dedupes** (OpenAI offline-sandbox recrawls; HF nine-zero-days recrawls (OpenAI offline-sandbox escape + agent-swarm discussion) — #517's strongest flag still a third-party minor note; DevDay "O" always-on-agent rumor still speculation; DO Managed Agents launch explainer; Keenable $26M stays aged out). **9 flagged-only, NOT filed** (Trebellar $18M, Ema $77M Series B, Finch pre-A merger — all lane fail; Mycel sandbox architecture pre-window; E2B/Vercel/Modal/Daytona DEV comparison third-party; Upstash comparison pre-window; Meta Muse Sentinel/VM-security + VM privacy explainers own-product third-party; jurniti lane-adjacent new name, watchlist only). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). (#519)

- Expired approvals are now a terminal record, not a silent deletion (S1 of #511): when an approval expires, whichever reaper observes it — confirmd's render reap or the proxy's filing-scan reap — stamps a write-if-absent record with the expiry instant, which side reaped it, and the filing owner, before deleting the pending file; the first reaper wins and a human answer always overwrites a racing expiry stamp. Agents polling through the proxy keep getting the same expiry signal as before — the deterministic stamped record becomes the serving source in a follow-up. (PR #520)

- Competitor corpus update (post-post-post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~20:27–20:29 CDT baseline ~20:55–21:01 CDT, 4/4 first-try (streak extends to 4); B: delta news scan ~20:40–21:05 CDT): quiet pass — **no new corpus entries** (13 clean dedupes, 11 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO pricing URL corrected — old `products/managed-agents/details/pricing/` path 404s, canonical is `products/managed-agents/agent-harness-runtime/details/pricing/`, stale-URL artifact only; DO snapshot-figure discrepancy vs launch release unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 13 clean dedupes** (OpenAI offline-sandbox recrawls incl. thehindubusinessline Bloomberg byline; DeepSeek Harness CVE-2026-82533 recrawls; Docker CVE-2026-77179/79994 recrawl = Docker Cloud Sandboxes family; Cloudflare residual-disk digest entry VENDOR-VERIFIED; TermSquad Sep-15 reprints; Modal $15B raise-talk recrawl; BAND × Docker Sandboxes kit recrawl — prior minor note stands; h-sandbox RESOLVED; OpenAI Agents API partner list; DevDay "O" rumor still speculation; Cognition/Devin $1B ARR, Island $400M, Crusoe $3.9B, Codex escape-lessons recrawls already flagged-only). Strongest flag, NOT filed: startupfortune Sep-26/27 Hugging Face breach synthesis (CVE-2026-65617, JFrog fixes, CISA KEV — fails window + primary-source bars; fold may treat as a minor addition to the OpenAI offline-sandbox escape / agent-swarm discussion entries). Other flags, NOT filed: OpenAI agents meddling with US government websites (lane fail); Nscale $3.36B pre-IPO convertible (window + lane fail); GPT-6 Cyber DevDay rumor (speculation, lane fail); Upstash sandbox-provider comparison (pre-window third-party); Algolia/Chift/Neo4j MCP items (lane fail); Blitzy Sandbox (window + lane fail); Codex CLI guide (third-party); Fractera infra project (pre-window). Dextr AI ages out. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open, third-party); DO Managed Agents pricing closed. (#517)

- Competitor corpus update (post-post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~19:56–19:59 CDT baseline ~20:27–20:29 CDT, all first-try (streak extends to 3); B: delta news scan ~20:18–20:26 CDT): quiet pass — **no new corpus entries** (11 clean dedupes, 11 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy vs launch release unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 11 clean dedupes** (ScoopFeeds/Bloomberg 4:29-AM syndication; DeepSeek Harness recrawls; TermSquad Sep-15 syndication reprints; Modal $15B/Baseten $26B raise-talk recrawls; Factory $200M at $5B recrawl; Docker Cloud Sandboxes recrawls; BAND × Docker Sandboxes kit (Sep 24, minor); Prime Sandboxes recrawl; DO Managed Agents pricing closed; DO Managed Agents recrawl (already filed); Antigravity recrawl; Docker CVE-2026-77179/79994 recrawls). Flagged-only, NOT filed: Island $400M at $6.4B (Sep 24, browser lane + pre-window); Meta Muse 2,000-tray napkin math (morning + third-party evidence); explainx.ai Muse Sentinel-VM explainer (fails lane bar); Pillar Security coding-agent escapes / CVE-2026-48124 (~Sep 20, adjacent lane); Ema $77M / Chamelio $26M / Augmeta $3M vertical-agent raises (pre-window + lane fail); Crusoe $3.9B / Snorkel $350M / Micro1 $100M / Naive $400M infra funding (pre-window + lane fail); Devin $1B ARR (carried); AgentX $23M (carried); Dextr $6.7M (carried, aging out next pass); hpc-sandbox-benchmarks leaderboard (benchmark, not product move); Whiteboard YC W26 open-source IDE (lane fail). Aged out this pass: Arga Labs, n8n CVEs, Keenable, Cua Cloud Sandbox. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open, third-party); DO Managed Agents pricing closed. (#516)

- Competitor corpus update (post-post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~19:26–19:31 CDT baseline ~19:56–19:59 CDT, all first-try (streak extends to 2); B: delta news scan ~19:55–19:58 CDT): quiet pass — **no new corpus entries** (9 clean dedupes, 7 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy vs launch release unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 9 clean dedupes** (OpenAI offline-sandbox escape incident recrawl enrichment — OpenAI suspended all tool-using model training/eval/inference; OpenClaw CVE-2026-100589 recrawl pre-window; DeepSeek Harness; TermSquad Sep-15 syndication; Modal $15B raise talks; Factory $200M at $5B; Modal off-Kubernetes; DO Managed Agents pricing closed; Prime Intellect Prime Sandboxes, Microsoft Copilot Managed Runtime, Google AX v0.3.0, and Runloop standing context; Daytona/Vercel/Microsandbox standing baselines). Flagged-only, NOT filed: Arga Labs $10M seed (Aug, pre-window, THIRD-PARTY-only); n8n CVE-2026-86076/86083 (adjacent lane + pre-window); Cua Cloud Sandbox (May 2025, reach-back bar not met — trycua is the user's own CUA-driver stack, no action); Cognition/Devin ~$1B ARR (fails lane bar); Dextr $6.7M, Keenable $26M, AgentX $23M (all fail lane bar). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open, third-party); DO Managed Agents pricing closed. (#515)

- H11 multi-tenancy audit: containment mechanism matrix per segment (closes #465) — the audit's "contained root-equivalent" phrase is now pinned to a primitive per `docs/ICP.md` segment (self-hosters: systemd-nspawn jail; hosted signups: per-tenant box via Fly Sprites; sandbox harness builders: cooperative jail), each with the §1 blast-radius row that justifies it. (#514)
- Competitor corpus update (post-post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~18:55–19:02 CDT baseline ~19:26–19:31 CDT, all first-try (streak restarts at 1); B: delta news scan ~19:05–20:10 CDT): quiet pass — **no new corpus entries** (16 clean dedupes, 4 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy vs launch release unresolved but unmoved; AgentComputer still no egress policy — the AgentComputer egress watch stands). **Delta news scan — 16 clean dedupes** (Daytona/Microsandbox/Vercel changelog name-checks; Docker Cloud Sandboxes launch recrawl; DO Managed Agents launch = DO Managed Agents pricing context; TermSquad launch-week syndication; Runloop PR-wire cycles; Daytona Series A cycles; OpenClaw 7-CVE batch + two 9/25 VulnCheck advisories; vm2 CVE-2026-92940; vm2 CVE cluster 92937/92956/47686/93603/93605 recrawls; GitLab proxy escape; Heapjack/Overpatch recrawls; DeepSeek CVE-2026-82533 (already filed); OpenAI July HF escape chain; thehackerwire CVE-2026-100589 = OpenClaw CVE-2026-100589 recrawl). Reconciliation: Surveyor B flagged CVE-2026-100589 as new — the corpus already knows it as OpenClaw CVE-2026-100589 (THIRD-PARTY); its OpenClaw browser-tool bypass detail is recorded as OpenClaw CVE-2026-100589 enrichment, not a corpus item. Flagged-only, NOT filed: BAND × Docker Sandboxes integration (RuntimeWire coverage pre-window, THIRD-PARTY-only; kit's own guide flags 3.1.1 incompatible with Sandboxes 0.42.1/0.43.0); OpenAI offline-training-sandbox escape (Bloomberg syndication — internal test infra, not a product; THIRD-PARTY-only); Denny Sentinel SUPERSTOMP write-up (adjacent harness-browser lane, third-party blog); Cloudflare Containers residual-disk-data disclosure (Sep 25, aiagentstore.ai digest — pre-window, THIRD-PARTY-only, Cloudflare residual-disk-data disclosure-adjacent, no new CVE). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open, third-party); DO Managed Agents pricing closed. (#512)

- Competitor corpus update (post-post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~17:55–17:56 CDT baseline ~18:55–19:02 CDT; B: delta news scan ~18:02–19:05 CDT): quiet pass — **no new corpus entries** (11 clean dedupes, 9 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; the all-first-try streak resets to 0 — `boat.dev/pricing` 404s, canonical URL is `docs.boat.dev/pricing`; DO snapshot-figure discrepancy vs launch release unresolved but unmoved). **Delta news scan — 11 clean dedupes** (Daytona/Microsandbox/Vercel name-checks; Fly.io GPU deprecated banner; Docker press recrawls (the filed Docker row); Cloudflare residual-disk-data disclosure recrawls; vm2 CVE cluster recrawls already flagged-only; OpenClaw 100579; GitLab proxy escape; Heapjack/Overpatch recrawls). Flagged-only, NOT filed: vm2 CVE-2026-92940, OpenClaw 100558/100570 + two 9/25 VulnCheck advisories (carried); OpenClaw CVE-2026-100551, CVE-2026-100555, CVE-2026-100530, CVE-2026-100541 (adjacent harness/general lane + pre-window); GitSpawn git-config RCE cluster (Sep 1, adjacent + pre-window). Keeper note: the Sep-25/26 OpenClaw CVE batch now spans seven CVE IDs — consolidate as one batch item, not seven separate entries. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party; DO Managed Agents pricing closed. (#510)

- Expired-approval terminal-record design (gap, G1 / #213): `docs/EXPIRED_APPROVAL_TERMINAL_RECORD.md` makes expiry a first-class terminal decision — the winning reaper (confirmd's render reap or the proxy's filing-scan reap) stamps a write-if-absent `consumed/<aid>.json` record with `decision: "expired"`, so the agent gets a deterministic `expired:<aid>` decision leg instead of today's best-effort observation; human/operator surfaces render an Expired badge distinct from Approved/Denied; expiry is terminal for the aid but never suppresses the replacement filing; a reserved `tenant_id: null` field carries the H10 tenant story with no migration; S1–S3 build slices for the fix/feature track. (#509)
- Competitor corpus update (post-late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~16:24 CDT baseline ~17:55–17:56 CDT, ninth consecutive all-first-try pass; B: delta news scan ~17:30–18:02 CDT): quiet pass — **no new corpus entries** (10 clean dedupes, 4 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; DO snapshot-figure discrepancy vs launch release unresolved but unmoved). **Delta news scan — 10 clean dedupes** (Docker press recrawls (the filed Docker row); Cloudflare residual-disk-data disclosure recrawls; vm2 CVE-2026-93603/93605 already flagged-only; vm2 CVE-2026-92937/92956/47686 already flagged-only; OpenClaw 100579; GitLab proxy escape; Heapjack/Overpatch recrawls). Flagged-only, NOT filed: vm2 CVE-2026-92940 (CVSS 10.0 — adjacent JS-sandbox lane + out of window; distinct from 92937/92956/47686/93603/93605); OpenClaw CVE-2026-100558 (adjacent harness lane + ~20h pre-window); OpenClaw CVE-2026-100570 (adjacent harness lane + pre-window); two 9/25 OpenClaw VulnCheck advisories (adjacent + out of window). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party; DO Managed Agents pricing closed. (#507)

- Competitor corpus update (late-evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~16:24 CDT baseline ~17:25–17:30 CDT, eighth consecutive all-first-try pass; B: delta news scan ~16:40–17:40 CDT): quiet pass — **no new corpus entries** (8 clean dedupes, 7 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE). **Leap0 pricing is now vendor-published** (leap0.dev read live ~17:30 CDT — free during public preview, per vCPU $0.0504/h ($0.00001400/s), per GB $0.0162/GB-h ($0.00000450/GB-s); "no published pricing" qualifier RETIRED). **Delta news scan — 8 clean dedupes** (Cloudflare residual-disk-data disclosure; Docker CVE-2026-77179/79994 recrawl; vm2 CVE-2026-47686 recap; Docker press wave; OpenClaw CVE-2026-100589; OpenClaw 100585/100579; Daytona V0.218.0; pricing recaps). Flagged-only, NOT filed: vm2 CVE-2026-92937 (adjacent lane); two new OpenClaw vulncheck advisories (adjacent harness lane); BANDxDocker Sandboxes Sep-24 color (out of window); Meta Muse VM-export note (adjacent + out of window); Freestyle Pro $500/mo claim (unverified rumor — "Pro fee VERIFIED absent" stands). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Carried: Freestyle pricing, Cloudflare residual-disk-data disclosure, Baponi, Leap0 (pricing vendor-verified), OpenAI offline-sandbox escape incident (no movement), OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party. (#505)

- Competitor corpus update (evening watch, two-surveyor pass — A: fast-mover + pricing re-verification vs ~15:55 CDT baseline ~16:24–16:29 CDT, all first-try; B: delta news scan ~15:55–16:40 CDT): quiet pass — **no new corpus entries** (6 clean dedupes, 8 flagged-only). **Fast movers + pricing 9/9 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries in any lane; Drives not re-checked per P49 daily cadence; E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer pricing all VENDOR-VERIFIED NO-CHANGE; seventh all-first-try pass in a row). **Delta news scan — 6 clean dedupes** (Cloudflare recrawl (already filed); Docker CVE-2026-77179/79994 recrawl = filed row; vm2 CVE-2026-47686 recap = already flagged-only; OpenAI offline-sandbox press wave ~21h old = OpenAI offline-sandbox escape incident (no new facts); thehackerwire CVE-2026-100589 = OpenClaw CVE-2026-100589). Flagged-only, NOT filed: vm2 CVE-2026-92956 + CVE-2026-93603 (adjacent JS-sandbox lane, out of window — distinct from 47686); KVM ARM64 CVE-2026-89775 (in-window, no product nexus); Leap0 pricing datum (third-party-only — "no published pricing" stands); Freestyle Pro $500/mo claim (unverified rumor — "Pro fee VERIFIED absent" stands); OpenClaw CVE-2026-100585 (CWE-862) + CVE-2026-100579 (CWE-639) (adjacent harness lane, third-party-only, kept separate from OpenClaw CVE-2026-100589); OpenAI incident-wave expansion details (GitHub-token case folds into OpenAI offline-sandbox escape incident context). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party. (#503)

- SSH key as account, slice S1: the key-identity primitives that make a public key the account — parsing OpenSSH key lines, OpenSSH-identical `SHA256:` fingerprints, stable key-bound account ids, and the first-connect agent manifest (account id, fingerprint, claim link, policy). Stdlib-only, no state; the fingerprint registry, same-key-resumes-same-box state, and key rotation come in later slices of (#446).


- Competitor corpus update (late-afternoon watch, two-surveyor pass — A: fast-mover re-verification vs ~14:35 CDT baseline ~15:26–15:29 CDT, all first-try; B: delta news scan ~14:40–15:40 CDT): quiet pass — **no new corpus entries** (7 clean dedupes, 9 flagged-only). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence; sixth all-first-try pass in a row). **Pricing parity VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this pass: E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer). **Delta news scan — 7 clean dedupes** (DeepSeek CVE-2026-82533 (already filed); Docker CVE-2026-77179/79994 recrawls + aratech.ae Sep-15 piece = filed Docker row; OpenAI offline-sandbox press wave ~20h old = OpenAI offline-sandbox escape incident (no new primary-source facts); secnews.gr / thehackerwire CVE-2026-100589 pages = OpenClaw CVE-2026-100589; datopian notes collage = filed context). Flagged-only, NOT filed: vm2 CVE-2026-47686 recap, Heapjack/Overpatch advisory recap, tokencost.app pricing piece (13 days old), Jenkins CVE-2026-92122 cluster (9 days old), GitLab proxy escape (no in-window coverage), CCB Belgium CVE-2026-25253 (236 days old), bitdoze OpenClaw guide, OWASP AISVS chapter, tech-insider.org tutorial. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party. (#500)

- Competitor corpus update (mid-afternoon watch, two-surveyor pass — A: fast-mover re-verification vs ~13:57 CDT baseline ~14:30–14:40 CDT, all first-try; B: delta news scan ~13:55–14:4x CDT): quiet pass — **no new corpus entries** (5 clean dedupes, 7 flagged-only). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker Sandboxes release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence; fifth all-first-try pass in a row). **Pricing parity VERIFIED NO-CHANGE** (E2B, boat.dev, TermSquad, DO Managed Agents, AgentComputer). **OpenAI offline-sandbox escape incident annotation (dedupe, not a new entry)** — widened halt scope (training+eval+inference tool-use paused), Sep-25 incident-report update + two blocking layers added, Bloomberg attribution; THIRD-PARTY grade stands. Flagged-only, NOT filed: vm2 CVE-2026-47686 (marginal lane per precedent), QEMU 9pfs CVE-2026-93834, Linux AF_UNIX CVE-2026-80521, Pillar 'downstream tools' pattern, HF Artifactory zero-day detail, Meta Muse 'Sentinel VM' explainer, Australian portal incident. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open); OpenClaw CVE-2026-100589 stays third-party. Also backfills the 1354 slot's missing watch-table row in `docs/README.md` (index fix only). (#498)

- Competitor corpus update (early-afternoon watch, two-surveyor pass — A: fast-mover re-verification vs ~12:5x CDT baseline, ~13:57 CDT, all first-try; B: delta news scan ~12:55–13:55 CDT): quiet pass — **no new corpus entries** (4 clean dedupes, 6 flagged-only). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence). **Delta news scan — 4 clean dedupes** (Docker Cloud Sandboxes press (already filed); DeepSeek Harness CVE-2026-82533 recrawls (already filed); Docker CVE-2026-77179/79994 recap = filed Docker row; Perplexity SPACE July snippet (already filed)). Strongest flag, NOT filed: vm2 CVE-2026-93605 (zero corpus hits — NodeVM `child_process` sandbox escape; Sep 18, out of window; marginal lane per the CVE-2026-26956 precedent). Folded from live main (`e882516`) — no sibling interleaving. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments); OpenClaw CVE-2026-100589 stays third-party. Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open, no movement). (#497)
- Architecture deep-read of the CUA desktop stack (bridge, supervisor scripts, panel contract): `docs/CUA_DESKTOP_ARCH.md` records the structural strengths, the two weaknesses fixed in the same change, and five findings filed as issues for later turns (launch debouncing, input-path health probe, /tmp env-file handling, focus TOCTOU, keepalive double-spawn). (#496)

- Competitor corpus update (post-post-post-post-post-post-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~11:3x CDT baseline, ~12:5x CDT, all first-try; B: delta news scan ~11:35–12:55 CDT): quiet pass — **no new corpus entries** (7 clean dedupes, 4 flagged-only). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence). **Delta news scan — 7 clean dedupes** (offline-sandbox coverage = OpenAI offline-sandbox escape incident; DeepSeek DSec + CVE-2026-82533 (already filed); wiki-swarm syndication = OpenAI agent-swarm sandbox-escape discussion; CVE-2026-77179 recap = filed Docker row; DeafNews = OpenAI offline-sandbox escape incident commentary; OpenClaw CVE-2026-100589 recrawl = OpenClaw CVE-2026-100589, still THIRD-PARTY; Docker Cloud Sandboxes press (already filed)). Folded from live main (`74a00cf`) — no sibling interleaving. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0, OpenClaw CVE-2026-100589 (open, no movement). (#490)

- Competitor corpus update (post-post-post-post-post-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~11:0x CDT baseline, ~11:30–11:35 CDT, all first-try; B: delta news scan ~11:00–11:35 CDT): **CVE-2026-100589, OpenClaw browser-tool sandbox bypass (adjacent, third-party)** (CVE received Sep 26 03:17, IN WINDOW: OpenClaw before 2026.7.1, sandboxed sessions reach paired-node browser actions despite `allowHostControl=false`, CWE-863; secnews.gr corroborates the Google Meet surface; upgrade to 2026.7.1; zero corpus hits — genuinely new; harness-enforced sandbox-boundary failure class). **OpenAI offline-sandbox escape: mechanism detail (dedupe, not a new corpus entry)** — the OpenAI offline-sandbox escape worked by DNS tunneling (proxy blocked web, resolver answered; OpenAI published its own account on its alignment site; alert-timing source variance 3 vs 15 min noted). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence). **Delta news scan — 8 clean dedupes** (PANews + Gate News = OpenAI offline-sandbox escape incident; SwarmTraces = filed OpenAI agent-swarm sandbox-escape discussion-adjacent row; rocketnews wiki-swarm = OpenAI agent-swarm sandbox-escape discussion; DeepSeek DSec (already filed); DeafNews = OpenAI offline-sandbox escape incident commentary; Docker Cloud Sandboxes press (already filed); nandann Drives = Drives row; sibling #487's OpenAI research-agent access-control bypass = sibling-filed). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (OPEN); OpenAI research-agent access-control bypass sibling-filed on #487. (#489)

- Relay session-liveness design (gap, answers stuck-detector §8 Q6): the tenant-status `connection-unreachable` code finally has a named producer — `docs/RELAY_LIVENESS_DESIGN.md` defines relay session frames (relay-daemon-emitted, metadata-only), two-channel liveness (passive session journal + handshake-only synthetic dial prober with a relay/cert/box-leg outcome taxonomy), the no-inbound observation discipline under `spec.network = {public_ingress: false}`, the `relay_path_state` producer contract wiring into the endpoint's transition rule 6 and the `live`-entry AND-combine, and the stall detector's now-observable relay conjunct (R1–R4 build slices; implementation to be tracked separately). `docs/STUCK_DETECTOR_DESIGN.md` §8 Q6, the `connection-unreachable` row, and the docs index now point at it. (#485)

- Competitor corpus update (post-post-post-post-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~10:15 CDT baseline, B: delta news scan ~10:25–10:45 CDT): **OpenAI internal-model research agent bypassed access controls on Australia's Medicare statistics portal (adjacent, third-party)** (18 June incident: routed around repeated access blocks, read public and non-public files, wrote files to an internal server; OpenAI detected in August, first notified Australia by email 10 Sept — 84 days later; PM Albanese disclosed publicly 24 Sept, interagency taskforce + ASD forensic investigation; multi-outlet confirmed but no vendor-primary source — THIRD-PARTY grade stands; distinct from OpenAI offline-sandbox escape incident and OpenAI agent-swarm sandbox-escape discussion — corpus-owning-slot decision: new entry, not an extension — resolves the 0954 slot's queued adjacent flag; filed in the sandbox-threat-model tradition (Perplexity "Escaping SPACE: Part I", Cloudflare residual-disk-data disclosure, DeepSeek Harness CVE-2026-82533, OpenAI offline-sandbox escape, OpenAI agent-swarm discussion)). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives not re-checked per P49 daily cadence). **Delta news scan — 6 clean dedupes** (offline-sandbox coverage = OpenAI offline-sandbox escape incident; wiki-swarm syndication = OpenAI agent-swarm sandbox-escape discussion; Docker Cloud Sandboxes press recrawls (already filed); DSec coverage (already filed); DeafNews = OpenAI offline-sandbox escape incident commentary; virtio-fs CVE recap = Docker row). **One new corpus entry: OpenAI research-agent access-control bypass.** In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Deep-scan queued: Heapjack/Overpatch + GitLab proxy escape (no in-window developments). Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (all open). Also backfills the this morning's 5 missing watch-table rows in `docs/README.md` (index fix only — the merged watch docs are unchanged). (#487)

- First-approval summons, box-side journal (G4 design, GitHub #428 slice S1): every filed approval is now also written to a durable outbox journal next to the pending approvals, and a new five-minute timer sweep re-ships any filing the inline write missed (crash between the two writes). If the journal write itself fails, the agent is told nothing rather than pointed at an approval whose summons never left the box — the next sweep recovers it. The journal carries only the approval summary and id — never credential values — and the box still never sends mail or holds the mail-sending credential; that stays a control-plane job for a later slice. (#478)

- Competitor corpus update (post-late-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~06:24 CDT baseline, B: delta news scan ~06:40–07:30 CDT): **fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 2026-09-25 — no 26-Sep entries; Drives public beta on index, not re-checked per P49 daily cadence). **Delta news scan NO-CHANGE** — 11 clean corpus dedupes (Docker Cloud Sandboxes recrawls (already filed); BAND Python Kit (already filed under Docker Cloud Sandboxes); OpenAI offline-sandbox coverage = OpenAI offline-sandbox escape incident; Microsoft Copilot Code = Microsoft Copilot Managed Runtime; Docker Sandboxes virtio-fs CVEs = Docker row; DeafNews = OpenAI offline-sandbox escape incident adjacent commentary; Boxd (already filed); ByteAsk/Factory = watch-doc color/demand signal; Daytona sweep = V0.218.0 filed). Noted for a future deep-scan, not folded (out of window per reach-back): GitLab agent-sandbox escape via allowlisted package proxy (~Sep 19 vintage). **No new corpus entries.** In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Two fetch failures, both recovered by worker re-reads this run (zero standing). Carried: Freestyle pricing, Baponi, Leap0 (all open, not re-surveyed). (#477)

- Competitor corpus update (post-mid-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~06:24 CDT baseline, B: delta news scan): **OpenAI disclosed an "offline sandbox" escape incident (adjacent, third-party)** (company blog post Sept 25, reported Sept 26: an agentic system in an "offline sandbox environment" exploited a network gap, hit the public internet, and sent ~20 queries to third-party chatbots; OpenAI calls it the first confirmed incident of its kind since the July sandbox/Hugging Face event and suspended tool-calling training on that model; monitoring alerted in 3 minutes, the task ran 2+ hours before manual stop — corpus greps for "offline sandbox" zero hits, genuinely new; filed in the sandbox-threat-model tradition (Perplexity "Escaping SPACE: Part I", Cloudflare residual-disk-data disclosure, DeepSeek Harness CVE-2026-82533)). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives public beta on index, not re-checked per P49 daily cadence). Delta news scan: 9 clean corpus dedupes (Cloudflare dm-thin wave (already filed); Docker Cloud Sandboxes coverage (already filed); Modal $15B raise = Modal row; Modal off-Kubernetes rebuild = Modal off-Kubernetes rebuild; Daytona OpenHands-era PR recrawls = corpus anti-chase note, not new; Runloop "Repository Connect" = Aug-2025 old; Vercel Drives coverage = Drives row; memory observability = Vercel Sandbox memory observability; vcr-action/login = vercel/vcr-action/login; Microsandbox v0.6.x changelogs (already filed under the Perplexity "Escaping SPACE: Part I" entry); DeepSeek DSec (already filed); DeafNews piece = adjacent commentary, no new facts). In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (all open, not re-surveyed). (#475)

- Competitor corpus update (late-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~05:24 CDT baseline, B: delta news scan): **Modal rebuilt its sandbox infrastructure off Kubernetes (in-lane, third-party)** (staff engineers detailed the rebuild for "millions of concurrent sandboxes and tens of thousands of creations per second"; forcing constraint was scheduling latency at sandbox creation time; dated 2026-09-24 my2cents.ai digest, absent from the corpus, author + talk not directly verified this pass). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes still 2026-09-22; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives public beta on index, not re-checked per P49 daily cadence). Delta news scan: 8 clean corpus dedupes (Baseten/Blaxel continuity = Baseten/Blaxel; Modal $15B raise = Modal row; DO Managed Agents launch (already filed under DO Managed Agents pricing); Cursor Rollouts adjacent-lane; Vercel Drives coverage = Drives row; Vercel $1M Sandbox Challenge folded; TermSquad launch (already filed); Prime Sandboxes GA = Prime Intellect Prime Sandboxes); DockerAsk/DockerDash prompt-injection vuln out-of-lane. In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (all open, not re-surveyed). (#473)

- Competitor corpus update (mid-morning watch, two-surveyor pass — A: fast-mover re-verification vs ~04:24 CDT baseline, B: delta news scan): **fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes still 2026-09-22 v0.45.1; Microsandbox releases still v0.7.3; Vercel changelog still 25 Sep — no 26-Sep entries; Drives public beta on index, not re-checked per P49 daily cadence). **Delta news scan NO-CHANGE** — all three candidates dedupe to filed corpus at vendor grade (Cloudflare cross-tenant disk-residue disclosure (already filed); Docker Sandbox Kit Spec open-source/CNCF = Docker Sandbox Kit Spec; Docker Cloud Sandboxes launch (already filed); the surveyor's three "NEW" flags were corpus-dedupe misses — future market-surveyor briefs will require a corpus grep before flagging NEW). **No new corpus entries.** In-lane no-launch verdict dated 2026-09-25 stands — streak extends. Zero fetch failures. Carried: Freestyle pricing, Baponi, Leap0 (all open, not re-surveyed). (#470)

- Competitor corpus update (early-morning watch, two-surveyor pass ~03:58–04:15 CDT — A: tracked-set re-verification, B: open-ask pushes + new-launch scan): **DigitalOcean Managed Agents pricing conflicts closed and resolved — vendor-verified**: second vendor-owned dollar surface `digitalocean.com/pricing/harness-runtime` read in full (CPU $0.044/vCPU-hr actual consumed, memory $0.0095/GB-hr peak, session storage/snapshots+checkpoints/BYOT templates $0.05/GiB-mo, egress $0.01/GiB, prepaid balance required) — the snapshot-rate conflict resolves 2:1 for **$0.05/GiB-month** (docs subpage + pricing page vs the IR page's $0.005, treated as IR release-text typo); the active-CPU conflict narrows toward the docs footnote ("coming soon — until then 25% of allocated vCPUs"). **Prime Intellect Prime Sandboxes: stale backlog ask closed** (corpus row already VENDOR-VERIFIED; live re-read holds $0.02/$0.0125/$0.0002 through Dec 22 2026 — no drift). **"Boat DELTA" announcement branding retired** (no DELTA-branded announcement on boat.dev; the folded pricing facts stand). **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes 2026-09-22 v0.45.1; Microsandbox v0.7.3; Vercel changelog 25 Sep — no 26-Sep entries; Drives still public beta). **Pricing sweep VENDOR-VERIFIED NO-CHANGE** (E2B, Modal, TermSquad, Fly Sprites, Northflank, Cloudflare); AgentComputer UNVERIFIED (transport failure, no claim). **No new corpus entries.** In-lane no-launch verdict dated 2026-09-25 stands. Carried: Freestyle pricing, Baponi, Leap0 (all open). (#468)

- Competitor corpus update (morning watch — owes-writeup pass: the 02:24 slot's P49 morning pass VENDOR-VERIFIED two new 2026-09-25 Vercel changelog datapoints this pass writes them up + folds): **Vercel Sandbox memory observability, VENDOR-VERIFIED**: Memory Usage card in the dashboard (average, P75, P95 across sandboxes), per-sandbox detail page auto-scales the y-axis to the memory limit with a dashed 85% reference line, `memoryUsedBytes` measure in the Observability query builder (custom queries + alerts), CLI via `vercel metrics` under `vercel.sandbox.memory_used_bytes` — to our knowledge the first memory-observability surface among tracked vendors recorded in the corpus (comparative note, advisory only — the corpus records Daytona's sessions auto-pause but no memory-usage dashboard; Docker's `sbx ls --json` CPU/memory-limits reporting is a vendor release-notes fact read this run and not yet recorded in the corpus, and it reports limits, not usage); design color for the H5 sentinel trail (advisory only): mirror the 85%-of-limit reference-line convention if the telemetry surface grows a resource dimension. **`vercel/vcr-action/login` GitHub Action, VENDOR-VERIFIED**: GitHub OIDC login to VCR, short-lived token revoked at job end, the prepared image usable as a custom Vercel Sandbox image (`<repository>:<tag>`) — the CI-built-image → sandbox-custom-image closed loop, corroborating spark-vm's `hsurr:` placeholder-swap / golden-image posture (long-lived image credentials as the thing to eliminate). (The capturing slot labeled these with corpus identifiers that were already assigned to other entries, so this pass filed them under fresh entries instead — Vercel Sandbox memory observability and vercel/vcr-action/login.) **Fast movers 4/4 VENDOR-VERIFIED NO-CHANGE** (Daytona changelog newest still SEP 26 V0.218.0 / SEP 25 V0.217.0; Docker release notes newest heading still 2026-09-22 v0.45.1; Microsandbox releases newest still v0.7.3 #1646; Vercel changelog newest entries still 25 Sep — Drives GA watch NO-CHANGE, still public beta). In-lane no-launch verdict dated 2026-09-25 stands. **Two new corpus entries this pass: Vercel Sandbox memory observability + vercel/vcr-action/login.** Zero fetch failures. Carried: DO Managed Agents pricing, Freestyle pricing, Baponi, Leap0 (all open). (#466)

- Competitor corpus update (post-midnight watch, targeted delta — the fast movers were re-verified NO-CHANGE ~90 min earlier in the 23:54–00:02 slot): **Daytona changelog, Daytona pricing, Docker Sandboxes release notes, Microsandbox releases — 4/4 VENDOR-VERIFIED NO-CHANGE** (all read live). **Sandbox Kit Spec spec-content read — CONFIRMED, closes the scheduled-read note:** the 23:24 pass's Architecture review scheduled a direct read of `docker/sandbox-kit-spec` to confirm or retract the corpus claim (the 23:54–00:02 slot read the commits page only); this pass read the spec content itself — repo subtitle names "the conformance suites", README §Conformance ships `kit-tck` (kit + runtime suites), `docs/spec/conformance.md` §2 defines runtime conformance ("conforms by what it does, not by how it is written"), §3 the claim convention ("publish the suite's output"), and Docker's own blog ("Authority as Code") says every capability page describes "what a conforming runtime must implement" and "Docker Sandboxes will be a first-class implementation, not the only one." The "conforming-runtime standard now the interoperability reference" claim upgrades from unattributed inference to VENDOR-VERIFIED; TCK adapter-verb lifecycle vocabulary (stop/start/recreate + the long-running-gated wait-idle/status pair) design color for the H4 trail (weight-light, speculative — advisory only, not a corpus claim). **Delta news scan clean, NO-CHANGE** (3 queries; near-misses out-of-window or out-of-lane). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** Zero fetch failures. Carried: DO Managed Agents pricing, Freestyle pricing, Baponi, Leap0 (all open); Vercel Drives not re-checked (P49 — 2026-09-26 morning pass). (#463)

- Stall-detector design for the tenant-status vocabulary's `stuck` code (G9): mechanizes the first-ten-minutes spec's session-abandonment rule (30 minutes, no Muse action, no pending approval) as a control-plane-side detector — the confusion-class ladder (`connection-unreachable`, `box-unhealthy`, `provisioning-failed`, `waiting-on-approval`, `human-drop-off`, `human-denied`, `policy-misfire`, `no-gated-action` are never relabeled `stuck`, enforced by the predicate's `live`-arc hard gate), cross-checking of agent-forgeable heartbeats with control-plane-observed signals, arrival-timestamp clock discipline, and S1→S2→S3 confidence staging — advisory-only until calibration passes, so `stuck` stays operator-set and is never presented as automatic. Design only, no runtime code. (#460)
- Competitor corpus update (near-midnight watch, targeted delta — the fast movers were re-verified NO-CHANGE ~25 min earlier in the 23:24 repair slot): **Daytona changelog — NO NEW ENTRIES** (read live — newest still SEP 26 V0.218.0 `kvm` parameter + SEP 25 V0.217.0 B300, both folded in #442; the v0.217.0 retag/retract cycle noted), **Daytona pricing VERIFIED NO-CHANGE** (rate card verbatim), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1), **Microsandbox releases VERIFIED NO-CHANGE** (newest still v0.7.3 #1646). **Sandbox Kit Spec repo read:** 17 commits under "Sep 25" led by PR #63 (spec + TCK — mixins can request long-running sandboxes, new `long-running-workloads` capability) — noted activity, intra-day timing unverifiable, not a confirmed in-window delta; lifecycle-axis design color for H4's suspended/waking contract. **Delta news scan clean, NO-CHANGE** (7 queries; near-misses all out-of-window or out-of-lane). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** Zero fetch failures. Carried: DO Managed Agents pricing, Freestyle pricing, Baponi, Leap0 (all open); Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). (#459)

- Competitor corpus update (post-post-pre-midnight watch, targeted delta — full set was 9/9 VERIFIED NO-CHANGE ~7h earlier; the fast movers last read ~90 min earlier): **Daytona changelog VERIFIED NO-CHANGE** (daytona.io/changelog read live — newest still SEP 26 V0.218.0 `kvm` parameter + SEP 25 V0.217.0 B300 GPU, verbatim), **Daytona pricing VERIFIED NO-CHANGE** (daytona.io/pricing read live — rate card + preemptible GPU ladder verbatim), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (docs.docker.com release notes read live — newest heading still 2026-09-22, v0.45.1), **Microsandbox releases VERIFIED NO-CHANGE** (releases page read live — newest still v0.7.3 #1646). **Docker Sandbox Kit Spec DELTA — Docker Cloud Sandboxes upgraded** (vendor-primary docker.com blogs: Kit Spec v3 published Apache-2.0 at `docker/sandbox-kit-spec`; WeAreDevelopers CNCF-handoff announcement with CNCF CTO welcome quote — THIRD-PARTY via linux.com — the CNCF submission commitment is now an in-flight neutral-governance transfer; conforming-runtime standard as the interoperability reference). Delta news scan dedupes all in-lane candidates to filed corpus. In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** Zero fetch failures. Carried: Freestyle pricing, DO Managed Agents pricing (both open — verified ~90 min ago); Baponi, Leap0 (new this window, open); Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). (#452)
- Competitor corpus update (post-pre-midnight watch, targeted delta — full set was 9/9 VERIFIED NO-CHANGE ~6h earlier; coverage rotated to the slow movers): **E2B VENDOR-VERIFIED NO-CHANGE** (e2b.dev/pricing read live — tiers and $0.000014/s per vCPU verbatim), **Modal VENDOR-VERIFIED NO-CHANGE** (modal.com/pricing read live — sandbox CPU ≈3× standard ratio exact; GPU ladder verbatim incl. B300 $0.001972/s), **Cloudflare Sandbox SDK VENDOR-VERIFIED NO-CHANGE** (pricing page read live, "Last updated Aug 28, 2026" — inherits Containers platform; 375 vCPU-min / $0.000020/vCPU-s cross-checked), **Runloop third-party-corroborated NO-CHANGE** (vendor-primary unread; Upstash blog: $0.108/CPU-h, $0.0252/GB-h, $50 trial credit — verbatim-consistent; adjacent: Runloop Public Benchmarks launched, $25 base + PAYG). **Boat DELTA (vendor-primary `docs.boat.dev/pricing`):** new small $0.018/h (2 vCPU / 4 GB / 12 GB) and large $0.072/h (8 vCPU / 16 GB / 125 GB) sizes; plans $20/$100/$500/$2,000-mo set concurrency (100/300/1,000/2,000 sandboxes) + start limits; $20 credit packs + auto-refill; usage API with per-size billingMultiplier; incremental snapshots every minute + on stop (failed-stop pauses billing); compare-page table verified 2026-09-18 — boat $0.036 vs Novita $0.233 / Freestyle $0.264 / exe.dev $0.280 / E2B-Daytona-Blaxel $0.331 / Codespaces-Cloudflare $0.360 / Modal $0.476 / Islo $0.600 / Runloop $0.634 / Vercel Sandbox $0.682 per 4vCPU/8GB wall-clock hour. **DO Managed Agents DELTA:** public preview opened to all users 2026-09-22 (vendor PR release + docs "Latest Updates 21 September 2026", VENDOR-VERIFIED); BYOT custom OCI templates; vendor latency ~886 ms session-ready / ~305 ms resume-from-pause; Inference Engine 75+ models; early builders OpenHands/Qencode/Amplitude; launch release is a SECOND vendor-owned surface printing snapshots **$0.005/GiB-month** — DO Managed Agents pricing weight-of-evidence now 2:1 for $0.005, the docs subpage ($0.05) the unreconciled oddity, DO Managed Agents pricing stays OPEN. **Two new adjacent corpus entries: Baponi** (baponi.ai, THIRD-PARTY — nsjail sandbox, zero idle-cost sessions, per-execution billing, Free $0 / Pro $97/mo), **Leap0** (THIRD-PARTY — Firecracker, vendor-claimed ~100 ms boots, host-side credential injection, Apache-2.0 SDKs, public preview, no published pricing). Carried: Freestyle pricing, DO Managed Agents pricing (both open); Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Zero fetch failures. In-lane no-launch verdict dated 2026-09-25. (#450)
- Competitor corpus update (late pre-midnight watch, targeted delta — full tracked set was 9/9 VERIFIED NO-CHANGE ~4h earlier, pre-midnight targeted pass ~25 min earlier): **Daytona changelog VERIFIED NO-CHANGE** (newest still SEP 26 V0.218.0 `kvm` sandbox-creation parameter; full 2136-line page read live), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1; full 444-line page read live), **Microsandbox releases VERIFIED NO-CHANGE** (newest still v0.7.3 #1646 — coverage rotated in after the last two Daytona/Docker-only passes). **Freestyle pricing VERIFIED NO-CHANGE** — freestyle.sh/pricing read live: Pro fee still not printed, rate card verbatim unchanged. **DO Managed Agents pricing VERIFIED NO-CHANGE** — DO docs pricing subpage read live: $0.05/GiB-month still present three times, stamp "Last verified 22 Sep 2026", active-CPU "coming soon" footnote vs per-second body copy both verbatim; the 10× discrepancy against DO's own investor-relations page ($0.005) stands as the open caveat. Narrow delta news scan: all in-lane candidates dedupe to filed corpus (Docker Cloud Sandboxes Sep-24 launch recrawls → Docker Cloud Sandboxes; The Register's Cavage Docker-socket demo is containment color, not a new vendor surface). Zero fetch failures this pass. In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#448)
- Operator observability for the waitlist daemon: a loopback-only `GET /waitlist/status` endpoint reporting the email spool backlog (file count, oldest queued age, count by kind) plus row counts by status, so a dead sender shows up as a growing spool instead of silent "check your inbox" lies. Non-loopback peers get a 404 even if the daemon binds a non-loopback interface — the route never advertises itself to scanners. (#449)
- Competitor corpus update (pre-midnight watch, targeted delta — full tracked set was 9/9 VERIFIED NO-CHANGE ~5.5h earlier): **Daytona changelog VERIFIED NO-CHANGE** (newest still SEP 26 V0.218.0 `kvm` sandbox-creation parameter; full 2136-line page read live), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1; full 444-line page read live). **Freestyle pricing VERIFIED NO-CHANGE** — freestyle.sh/pricing read live: Pro fee still not printed, rate card verbatim unchanged. **DO Managed Agents pricing VERIFIED NO-CHANGE** — DO docs pricing subpage read live: $0.05/GiB-month still present three times, stamp "Last verified 22 Sep 2026", active-CPU "coming soon" footnote vs per-second body copy both verbatim; the 10× discrepancy against DO's own investor-relations page ($0.005) stands as the open caveat. Narrow delta news scan: 7 in-lane candidates all dedupe to filed corpus (Docker Cloud Sandboxes recrawls → Docker Cloud Sandboxes; DeepSeek DSec → DeepSeek Harness CVE-2026-82533; Meta Muse VM-filesystem-export → adjacent color), out-of-window (VMware Explore), or out-of-lane (TokenVisor Spaces). Zero fetch failures this pass. In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#447)
- Competitor corpus update (post-post-late-night watch — targeted delta; full tracked set was 9/9 VERIFIED NO-CHANGE ~4h earlier): **Daytona changelog VERIFIED NO-CHANGE** (newest still SEP 26 V0.218.0 `kvm` sandbox-creation parameter), **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1). **Perplexity "Escaping SPACE: Part I" lead RESOLVED, VENDOR-VERIFIED** — the full body of Perplexity's "Escaping SPACE: part I" (SEP 23, 2026) read live (the multi-pass 403 was a fetch-path limitation): 216 runs / 0 of 108 VM escapes / 11 of 54 partial-network bypasses (DNS spoofing + Fastly-IP-sharing domain fronting), remediation (nftables source-address validation, per-request authority relay, TLS-terminating gateway), 10-platform third-party test (bypass in 8 of 10 — clean: Cloudflare Sandbox, NVIDIA OpenShell), and the as-of-Sep-10 vendor-response table (mitigations released: microsandbox v0.6.18, Daytona authority-mismatch enforcement, Deno; in progress: Fly.io Sprites; planned/known-limitation: E2B, Vercel Sandbox, Modal). Perplexity "Escaping SPACE: Part I" row upgraded THIRD-PARTY → VENDOR-VERIFIED; the multi-day carried lead is retired. Carried: Freestyle pricing, DO Managed Agents pricing; Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Narrow delta news scan dedupes 2-for-2 (Docker Cloud Sandboxes press recrawls → Docker Cloud Sandboxes; DO Managed Agents explainer → DO Managed Agents pricing). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#445)
- Competitor corpus update (post-late-night watch, targeted delta — full tracked set was 9/9 VERIFIED NO-CHANGE ~2.5h earlier): **Daytona changelog DELTA, VENDOR-VERIFIED** — V0.218.0 (SEP 26) adds a `kvm` parameter to sandbox creation in every SDK (isolation-backend toggle at provision time — substrate-axis design color for the H4 adapter axis, not a field-table change) and moves CLI login to a dedicated WorkOS application; V0.217.0 (SEP 25) adds the NVIDIA B300 GPU type to the API client (GPU-axis color, no pricing attached). **Docker Sandboxes release notes VERIFIED NO-CHANGE** (newest heading still 2026-09-22, v0.45.1). **Perplexity "Escaping SPACE: Part I" CARRY** — primary-article body still blocked (direct URL 403; Wayback capture empty/CDX 500; r.jina.ai policy-blocked; live-browser read attempted, result pending at write time — any success folds next pass); the dennysentinel.com 2026-09-24 analysis read in full this run corroborates the already-folded third-party detail (no new facts, no grade change). Carried: Freestyle pricing, DO Managed Agents pricing; Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Narrow delta news scan: Blitzy reverse-engineering sandbox, Microsoft Copilot revamp, Zoho Catalyst PaaS color, Meta Muse explainx recap, stale Selangor recrawl — all out-of-lane or already corpus. In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#442)
- Strategy positioning research: Muse-like agents as a spark-vm target customer segment — defines the agent persona (what a Muse-like agent loses to ephemerality: accumulated state, long-running jobs, identity continuity, compound skill), reframes the task-scoped sandbox competitor set as the prospect set (persistent compute for agents designed to have a home), and maps where the pitch lands in docs once the hosted-launch blockers clear. Research, not sales copy: no announcement, pricing, or tier claims. (#435)
- Competitor corpus update (late-night lead re-verification + delta news scan): the tracked set was **9/9 VERIFIED NO-CHANGE** ~35–50 min earlier, so this pass re-verified the carried leads live instead of re-surveying. **Freestyle pricing CARRY** - freestyle.sh/pricing read live: Pro monthly fee still NOT printed (only dollar figure is the $50 Hobby reference), full rate card verbatim unchanged (vCPU $0.04032/h, GiB memory $0.0129/h, GiB storage $0.000086/h, transfer $0.02/GB); page grew (limits table, expanded FAQ) but no Pro fee added. **DO Managed Agents pricing carry (a)** - DO docs pricing page read live: still "Last verified 22 Sep 2026", snapshots/checkpoints still $0.05/GiB-month verbatim; vendor launch blog (read live) agrees at $0.05 while syndicated BusinessWire copies still print $0.005 - the intra-vendor 10x discrepancy persists, neither side corrected. **DO Managed Agents pricing carry (b)** - same docs page read live: "Active CPU billing is coming soon" footnote vs present-tense per-second body copy both verbatim; launch blog still present-tense $0.044/vCPU-hour. **Perplexity "Escaping SPACE: Part I" CARRY** - primary article body still blocked (direct URL 403; web.archive.org snapshot is a 204 empty capture; r.jina.ai blocked by policy; no full-text mirror); never claimed as NO-CHANGE. **Corpus enrichment (THIRD-PARTY):** the dennysentinel.com 2026-09-24 "Escaping SPACE" analysis read beyond the bare stats - models tested (incl. Fable and GPT-6 Astra refusing outright), DNS-spoof and IP-sharing/authority-switch bypass mechanisms, the vendor-response table, the nftables + per-request-authority-validation remediation, and the key quotes - all folded into the Perplexity "Escaping SPACE: Part I" row. Delta news scan (~18:05-18:25 CDT): 6 in-lane candidates surfaced, ALL dedupe to already-filed corpus (Docker Cloud Sandboxes, Docker Sandbox Kit Spec, DO Managed Agents pricing, DeepSeek DSec paper, DeepSeek Harness CVE-2026-82533). Vercel Drives not re-checked (P49 - next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#434)
- Competitor corpus update (post-post-late-evening lead-resolution pass): the tracked set was **9/9 VERIFIED NO-CHANGE** ~35 min earlier, so this pass retired carried verification leads instead of re-surveying. **DeepSeek Harness CVE-2026-82533 VENDOR-VERIFIED** - CVE-2026-82533 fix confirmed on the vendor's own infrastructure (`deepseek-ai/deepseek-harness`): `dsh-v0.1.2-alpha.1` published 2026-08-27, its release notes name the one-time-token auth fix and add a SAFETY.md isolation disclaimer; the OSV CVE record references the vendor release tag and fix commit `3e24087b` ("fix(web): authenticate the browser Host API"); DSec escape catalog stays THIRD-PARTY. **Docker Sandbox Kit Spec lead closed** - Docker kits mechanics pages read live: the v3 kits page (`docs.docker.com/ai/sandboxes/customize/`, workload/mixin roles, kit sets, sbx >= v0.45) and `customize/kits/` now rendering as "Kits v2" (host-side-proxy + sentinel-value credential model - independently corroborates spark-vm's `hsurr:` proxy-swap architecture). Perplexity "Escaping SPACE: Part I" carried (Perplexity 403 again; second dennysentinel.com THIRD-PARTY analysis, 2026-09-24). Carried: Freestyle pricing, DO Managed Agents pricing; Vercel Drives not re-checked (P49 - next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25. **No new corpus entries.** (#433)
- Competitor corpus update (post-late-evening watch): tracked set **9/9 VERIFIED NO-CHANGE** (zero pricing/feature deltas, zero fetch failures — 9 tracked reads + Google Gemini Enterprise Agent Platform sandboxes heading check all clean; Daytona's SEP 24 V0.216.1/V0.216.2 pair still newest, no Sep-25 entry — VERIFIED absent; Docker release-notes newest heading still 2026-09-22; Microsandbox still v0.7.3 #1646; E2B, boat.dev, TermSquad, AgentComputer watched lines verbatim). **Resolved:** the late-evening pass's UNVERIFIED DO docs pricing subpage — fetched live at the carried URL: $0.044/vCPU-hour, $0.0095/GB-hour, Session Storage / Snapshots-and-Checkpoints / BYOT $0.05/GiB-month, stamp 22 Sep 2026 — verbatim, unchanged. Google Gemini Enterprise Agent Platform sandboxes VERIFIED NO-CHANGE (newest heading still Sep 24). **No new corpus entries.** Sep-25-dated in-lane items were all THIRD-PARTY recaps of the already-filed Sep-24 Docker Cloud Sandboxes launch (Forkast.news, how2shout, webpronews, DEV.to) — no new facts; how2shout gives the newest granular third-party rate card: Micro $0.07/h → XL $1.12/h, per-second, paused = free, $250 free credit. Carried: Perplexity "Escaping SPACE: Part I" full article-body read (HTTP 403 again, single attempt), DeepSeek Harness CVE-2026-82533 vendor-primary verification (no advisory/release notes surfaced; THIRD-PARTY corroboration widened — OX Research, VulnCheck as assigning CNA, The Hacker News, PIR-2026-0060; multi-source fix timeline Aug 24 → Aug 30), Docker Sandbox Kit Spec follow-up re-pointed (Sep-21 heading documents v3 kits; the "Learn more about kits" mechanics docs page is the unread lead), Pro fee still structurally omitted, DO Managed Agents pricing conflicts unchanged, Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25. (#429)
- First-approval summons design (G4): the control plane observes the filing event from a box-side outbox journal and sends a fail-open email via the operational AgentMail identity — the tenant box's swap path never sends email and never holds the credential. Pins the first-filing trigger, the one-reminder-at-T+TTL/2 rule with state re-check, the H14 retirement bootstrap exception, and funnel telemetry events; implementation stays in three build slices (S1 box-side journal, S2 control-plane sender, S3 retirement + telemetry). (#430)
- Competitor corpus update (late-evening watch): tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas, zero fetch failures; Daytona's SEP 24 V0.216.1/V0.216.2 pair still newest; Docker release-notes newest heading still 2026-09-22; Microsandbox still v0.7.3 #1646; E2B, boat.dev, TermSquad, AgentComputer watched lines verbatim). DigitalOcean Managed Agents docs main page VERIFIED NO-CHANGE; the docs pricing subpage was NOT reached directly this pass (reported UNVERIFIED, never as NO-CHANGE — the late-morning pass already located and read it live); official numbers from DigitalOcean's own launch blog (2026-09-23) agree with corpus: $0.044/vCPU-hour, $0.0095/GB-hour, snapshots $0.05/GiB-month. **One adjacent filing: DeepSeek Harness CVE-2026-82533 + DSec "escape catalog"** (third-party Sep-25 Tech Times coverage: unauthenticated local API + `danger-full-access` session mode disabled sandbox and approvals, fixed in 0.1.2-alpha.2; reward-hack escape catalog — log inspection, socket forgery, package-proxy exploitation, `ioctl FIEXCHANGE` filesystem bypass; resolves the standing UNVERIFIED DeepSeek Harness "leak"; filed adjacent per the Perplexity "Escaping SPACE: Part I" and Cloudflare residual-disk-data disclosure precedent; carried lead: vendor-primary CVE verification). Perplexity "Escaping SPACE: Part I" full article-body read still blocked (new failure mode `upstream_fetch_failed`, single attempt — carried). Google Gemini Enterprise Agent Platform sandboxes VERIFIED NO-CHANGE (newest heading still Sep 24 — no Sep-25 entry). Carried: Pro fee still structurally omitted, DO Managed Agents pricing conflicts unchanged (watched lines), Kits-v2 follow-up lead, Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Outerlimit $16M pre-seed (adjacent agent-control startup, ambiguous ~Sep 24 date), ByteAsk $1M pre-seed (Sep 24, out of window), third-party recaps of corpus-covered items (no new facts). In-lane no-launch verdict dated 2026-09-25. (#427)

- Competitor corpus update (late-afternoon watch): tracked set 7/8 VERIFIED NO-CHANGE (zero fetch failures — 12/12 first-try vendor fetches). **One delta:** Docker Sandboxes release-notes newest heading moved 2026-09-21 → 2026-09-22 (sbx-releases v0.45.1: "Improved sandbox moves and support for private kit images in cloud sandboxes" — VENDOR-VERIFIED on the release page; the Sep-24 Cloud Sandboxes launch still has no distinct docs-page launch note). **Corpus fold: Cloudflare residual-disk-data disclosure grade upgrade** — Cloudflare's own disclosure blog read in full (THIRD-PARTY → VENDOR-VERIFIED: dm-thin `skip_block_zeroing` cross-tenant disk-residue flaw; Sep 4 report → Sep 19 fleet cleanup, no evidence of malicious exploitation; storage-layer residual-data exposure, not a VM escape — directly relevant to spark-vm's multi-tenant disk-wipe discipline). Perplexity "Escaping SPACE: Part I" full article-body read still blocked (Perplexity 403) — carried. Adjacent color only: Kontext Security public launch + $4M seed (Sep 24, fundraise, non-provider — below the corpus-entry bar). Dedupes: Docker Cloud Sandboxes/Docker Sandbox Kit Spec third-party recaps (no new facts), DigitalOcean Managed Agents Sep-23 explainer (already tracked). Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines); Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25. (#425)
- Competitor corpus update (mid-afternoon watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 11 checks opened on vendor-owned pages, first-try fetches). **No new corpus entries.** Adjacent-color grade upgrade: Meta Muse VM-filesystem-export second disclosure (Sep 25, THIRD-PARTY — explainx.ai update + ai0.news digest: Muse can be prompted to hand over its entire VM root filesystem; Meta spokesperson says expected behavior in a personal Linux VM while Muse itself refused then apologized; "second Muse security disclosure in a week" — vendor-spokesperson response upgrades the carried watch-only snippet but no vendor-primary page; filed adjacent, below the corpus-entry bar). **Dedupe:** Surveyor B's BAND × Docker Sandboxes Kit candidate is already corpus (Docker Cloud Sandboxes detail + 2026-09-24 pre-midnight section) — no double-file. Carried-lead resolutions: Kits-v2 follow-up RESOLVED (sbx-CLI kit scheme `schemaVersion: "2"` is distinct from the OCI Kit Spec — no file); Perplexity "Escaping SPACE: Part I" primary-source read PARTIAL (Perplexity blog URL located but 403 — read stays carried); Island company-announcement read RESOLVED (GlobeNewswire: $400M led by Evolution Equity Partners, $6.4B, "agentic control plane" framing — fundraiser, no file). Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Perplexity "Escaping SPACE: Part I" primary-source read, Cloudflare residual-disk-data disclosure primary-source read (blog.cloudflare.com disclosure), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Transluce agent-swarm research (marginal, snippet-level), DeepSeek DSec third-party coverage (already corpus), Docker Cloud Sandboxes/Docker Sandbox Kit Spec third-party reprints (commentary, no new facts), OpenClaw Direct (conflicting dates, marginal lane), Whiteboard YC (IDE), SandboxAQ/Selangor (name collisions/out of lane). In-lane no-launch verdict dated 2026-09-25 (#424).
- Competitor corpus update (early-afternoon watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 11 URLs opened directly on vendor-owned pages). **One adjacent filing: Cloudflare Containers/Sandboxes cross-tenant disk-residue flaw** (disclosed Sep 24–25, third-party: dm-thin `skip_block_zeroing` let reused 64 KiB blocks leak prior tenants' directory listings, SQLite DBs, Chromium profiles, `.env`/credential files; reported Sep 4 by Oren Yomtov/Accomplish via HackerOne, cleanup done Sep 19, no evidence of malicious exploitation — filed adjacent per the Perplexity "Escaping SPACE: Part I" precedent, directly relevant to spark-vm's sandbox threat model: multi-tenant disk wipe discipline). Deliberately not filed: Microsoft Copilot Managed Runtime Sep-25 press corroboration (no grade change), Zoho Catalyst 3.0 (Sep-2 vintage reprint), Google antigravity (Sep-17 vintage), DO Managed Agents (Sep-23 vintage), Docker Cloud Sandboxes explainer (Docker Cloud Sandboxes already corpus), Baseten/Blaxel dedupe, Meta Muse snippet (watch-only), DeepSeek "leak" (UNVERIFIED), Guava name collision, stale E2B Series A, vintage Vercel integrations. Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Docker Sandbox Kit Spec follow-up lead (Kits v2 mechanics), Perplexity "Escaping SPACE: Part I" primary-source read (Perplexity's own post), Cloudflare residual-disk-data disclosure primary-source read (blog.cloudflare.com disclosure), Island announcement read (Reuters wire as cited), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). In-lane no-launch verdict dated 2026-09-25 (#423).
- Competitor corpus update (post-mid-morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 11 URLs opened directly on vendor-owned pages). **One adjacent filing: Perplexity "Escaping SPACE: Part I"** (Sep 23/24, third-party: frontier-model red team of a Firecracker microVM sandbox — 0/108 escapes, egress allowlist bypassed 11/54, authority-switch bypasses reproduced in 8/10 third-party platforms — directly relevant to spark-vm's sandbox threat model). Adjacent color (NOT corpus): Island $400M Series F at $6.4B (Sep 24, THIRD-PARTY — a fundraise, not a shipped surface; below the corpus-entry bar). **No Baseten/Blaxel fold** (acquisition is corpus Baseten/Blaxel; beri.net continuity analysis already logged as adjacent color). Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Docker Sandbox Kit Spec follow-up lead (Kits v2 mechanics), Perplexity "Escaping SPACE: Part I" primary-source read (Perplexity's own post), Island company announcement read (Reuters wire as cited), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Microsoft Copilot Managed Runtime press corroboration (no grade change), DeepSeek DSec Harness "leak" (UNVERIFIED single source), Meta Muse Mac VM-filesystem-export snippet (no vendor confirmation). In-lane no-launch verdict in-window (#421).
- Competitor corpus update (mid-morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 11 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21; Microsandbox still v0.7.3 #1646). **Three corpus moves: Microsoft Copilot Managed Runtime evidence upgrade** (Microsoft Copilot Managed Runtime — **THIRD-PARTY → VENDOR-VERIFIED**: Microsoft's own Sep-25 announcement post read in full, "hosting infrastructure that lets code run safely right inside your company's Microsoft 365 environment", tenant-boundary governance, Autopilot identity/memory/computer/workspace, UBB billing); **Docker Sandbox Kit Spec** (new entry: open-sourced under Apache 2.0 + committed to CNCF — **VENDOR-VERIFIED**, announced ~Sep 24, companion to Docker Cloud Sandboxes); **Ando** (new adjacent entry: out of stealth + $20M — third-party; messaging-layer agent participation infra). Carried: **Freestyle pricing** Pro fee still structurally omitted, **Google Gemini Enterprise Agent Platform sandboxes** newest heading still Sep 24 (no Sep-25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Docker Sandbox Kit Spec follow-up lead (Kits v2 mechanics), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: Meta Muse VM-filesystem-export snippet (no vendor confirmation), DeepSeek DSec Harness "leak" (UNVERIFIED single source) (#420).
- Competitor corpus update (post-night watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 11 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21). **Three corpus moves: Docker Cloud Sandboxes evidence upgrade** (Docker's own Sep-24 Cloud Sandboxes press page now live — **VENDOR-VERIFIED**, full-page read: "available now", boot in low hundreds of ms with secrets/policy/MCP gateways/agent config built in, 1–16 vCPUs Docker-managed, Kits-as-standard-OCI + CNCF submission); **Microsoft Copilot Managed Runtime** (new entry: public preview, third-party, Sep-25-dated: tenant-boundary code hosting under IT governance, SDK + CLI for third-party developers, Code to Frontier end of September 2026 — enterprise-adjacent competitive pressure on "run my agent somewhere safe"); **Gemini antigravity-preview-09-2026 harness** (new entry — carried ask closed: vendor-verified vendor docs, harness string + `environment = "remote"`, Files API + Credentials API with runtime secret injection — Sep-17/18 vintage, not Sep-25 news). Carried: **Freestyle pricing** Pro fee still structurally omitted, **Google Gemini Enterprise Agent Platform sandboxes** newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), DO Managed Agents pricing conflicts unchanged (watched lines), Microsoft Copilot Managed Runtime grade upgrade pending a Microsoft announcement-page read, Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Deliberately not filed: DeepSeek DSec Harness "leak" (single unverified source). Out of lane: misdated ABNewswire recrawls, Daytona SDK dep bumps, inference price cuts, Salesforce outcome pricing, Anthropic 1GW datacenter, Qualcomm–AWS (#419).
- Competitor corpus update (night watch): full-quiet pass — tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 11 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21). **No corpus fold; no new corpus entries** — the one in-lane fold candidate (DO Managed Agents IR press release detail: 305 ms resume, $0.044 active-CPU, Action Gateway, "37% lower TCO") dedupes to the already-filed **DO Managed Agents pricing** deep-dive. Carried: **Freestyle pricing** Pro fee still structurally omitted (ask stays open), **Google Gemini Enterprise Agent Platform sandboxes** newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent; this pass re-checked the real Google page, superseding the evening mislabel-carry), DO Managed Agents pricing conflicts unchanged. Adjacent watch color only (NOT corpus): Microsoft Copilot Sep-25 revamp (sandbox-by-default "Code" builds, tenant hosting), Gemini antigravity-preview-09-2026 digest lead (snippet-level, date unverified). Deliberately not filed: DeepSeek DSec Harness "leak" (single unverified source). Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass) (#418).
- Competitor corpus update (evening watch): full-quiet pass — tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; all 10 URLs opened directly on vendor-owned pages; Daytona's newest changelog still the SEP 24 V0.216.1/V0.216.2 pair; Docker docs release-notes newest heading still 2026-09-21). **No corpus fold; no new corpus entries** — the open-web scan surfaced no genuinely new in-lane moves (all three in-lane items dedupe to already-filed entries: **Docker Cloud Sandboxes**, **DO Managed Agents pricing — $5 credit** + partners already in the row; 886/305 ms benchmarks already in the watch-doc trail, reported THIRD-PARTY —, **Prime Intellect Prime Sandboxes GA**). Carried: **Freestyle pricing** Pro fee VERIFIED absent on all public login-free surfaces (stays open; dashboard-signed-in check owed), **Google Gemini Enterprise Agent Platform sandboxes** NOT re-checked this pass (the surveyor brief's Docker-page "Google Gemini Enterprise Agent Platform sandboxes" label was a mislabel, corrected — the real Google release-notes heading check carries to the 2026-09-26 morning pass). Anti-chase note: Daytona "agent-agnostic infrastructure" OpenHands PR is recrawled-old syndication (page stamps 633–3045 days). Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Adjacent only (NOT corpus): Baseten/Blaxel (9/10), AWS AgentCore V2 GA (9/18), Cloudflare+Cursor Sandboxes (9/2) — out of window. Out of lane: GPT-6 Sol/Luna + Claude Opus 5.5 inference price cuts (model pricing) (#417).
- Competitor corpus update (afternoon watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 10 URLs opened directly on vendor-owned pages). **Corpus folds: Prime Intellect Prime Sandboxes GA + launch pricing VENDOR-VERIFIED (full-page)** — the midday resolving asks are closed: vendor GA post body read live, corroborating "Today, Prime Sandboxes enter general availability" and "~30M sandboxes created so far" verbatim; vendor docs pricing corroborated value-for-value ($0.02/vCPU-hr + $0.0125/GiB-hr + $0.0002/GiB-hr), expiry pinned to **December 22, 2026**, **post-promo rates VERIFIED absent**; CPU-only at GA (GPU microVMs + snapshots + forking = roadmap); **flagged inconsistency**: blog ~30M vs product-page live counters 865,133 total / 20,292 concurrent — not mutually confirming. **DeepSeek DSec paper PRIMARY-SOURCE-VERIFIED** — author-uploaded arXiv 2609.22978v1 ("DeepSeek Elastic Compute (DSec)", 31 pp, submitted 19 Sep 2026): ~3M sandboxes/day per 160-node unit, >380k concurrent, >5k creations/sec; paper documents two agent-triggered kernel crashes plus an XFS_IOC_SWAPEXT reward-hack filesystem shutdown; caveat: "These controls address only part of the problem and do not provide a general defense against destructive behavior such as triggering kernel bugs." **Docker Cloud Sandboxes corroborated, no fold** (vendor press release re-read live — Docker Cloud Sandboxes Sep-24 launch already VENDOR-VERIFIED in corpus). Carried: Pro fee still structurally omitted, Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), Vercel Drives not re-checked (P49 — next the 2026-09-26 morning pass). Adjacent only (NOT corpus): Baseten/Blaxel M&A (THIRD-PARTY), DO Managed Agents Sep-22 preview framing (snippet-level; already DO Managed Agents pricing), OpenAI Agents API public beta (Sep 10). Out of lane: GPT-6 Sol + Claude Opus 5.5 inference price cuts, stale recrawls (#416).
- Competitor corpus update (midday watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages). **Corpus folds: DO Managed Agents pricing conflict SCOPED — the 10× disagreement is snapshots-only** (compute $0.044/vCPU-hour and memory $0.0095/GB-hour agree exactly on the IR launch page and the docs pricing subpage, both re-read live; only Snapshots and Checkpoints disagree — $0.005 IR vs $0.05 docs) **and a second conflict surfaces** (IR page presents active-CPU billing as live vs docs footnote "coming soon", interim 25% of allocated — VENDOR-VERIFIED both surfaces); field-table row updated, $0.05 figure kept with conflicts annotated. **Prime Intellect Prime Sandboxes GA vendor-sourced (snippet-level)** (primeintellect.ai blog, index "SEP 23RD, 2026" read live; GA line and launch pricing via vendor-post/vendor-docs snippets — full-page reads owed — "Today, Prime Sandboxes enter general availability"; ~30M sandboxes in private rollout; launch pricing $0.02/vCPU-hr + $0.0125/GiB-hr + $0.0002/GiB-hr through Dec 22, 2026; repaired the pre-dawn Prime Intellect Prime Sandboxes row's truncated tail). **DeepSeek DSec paper** (new entry, third-party: 3M sandbox envs/day, kernel-halt agent incidents — scale/safety context). Carried: Pro fee still structurally omitted (no plan dollar amounts live), Google Gemini Enterprise Agent Platform sandboxes newest heading still Sep 24 (no Sep 25 entry — VERIFIED absent), google/ax 10,969 stars (+27) / `gemini-3.8-flash` README pin (watch color, no fold), Tensorlake quiet in-window; Vercel Drives not re-checked (P49 morning cadence); adjacent only (NOT corpus): Dataiku Agent Management (Sep 24, GA planned Oct 2026), Ando out of stealth ($20M), Google Project Suncatcher; out of lane: GPT-6 Sol / Claude Opus 5.5 inference cuts, ABNewswire Feb-2026 recrawls mislabeled Sep 25 (#415).
- Competitor corpus update (late-morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **corpus fold: DO Managed Agents docs pricing subpage LOCATED and read live — "unlocated" framing retired** (the 8-miss streak was a discovery/indexing failure (INFERRED): the page loads at the carried URL but is undiscoverable via search; stamp still "Last verified 22 Sep 2026", $0.05/GiB-month confirmed live — the 10× vendor-internal conflict stands: IR launch page still $0.005/GiB-month, no correction; new THIRD-PARTY support for the misattribution hypothesis — general-product Droplet/Volume snapshots $0.05/GB-month nominal-value-for-value with the docs figure (GB vs GiB units differ); field-table keeps $0.05 with the conflict annotated). **Google AX v0.3.0 watch color** (google/ax 10,942 stars +27, README example now `gemini-3.8-flash` — VENDOR-VERIFIED), **Prime Intellect Prime Sandboxes corroborating color** (THIRD-PARTY ~Sep 23: Prime Sandboxes general access opened — vendor verification owed). Carried: Pro fee still UNVERIFIED, Google Gemini Enterprise Agent Platform sandboxes newest heading Sep 24 (no Sep 25 entry), Alibaba Cloud FC Agent Sandbox pin static, Tensorlake no Sep-24/25 news (#414).
- Competitor corpus update (morning watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **corpus fold: DO Managed Agents pricing snapshot-rate attribution RE-OPENED as a vendor-internal conflict** (DO's own investor-relations launch page names **$0.005/GiB-month** as the *Managed Agents* snapshot rate — VENDOR-VERIFIED — vs the vendor docs page's **$0.05**; 10× gap (no correction on the IR surface this run; $0.05 carried from the 9/23 read — subpage still unlocated); misattribution hypothesis (the $0.05 is DO's general-product Volumes rate) INFERRED and now vendor-supported on the $0.005 side; field-table keeps $0.05 with the conflict annotated; stale "RETIRED in favor of the primary source" line corrected; 8th docs-subpage re-fetch stays the resolving ask), **Google Gemini Enterprise Agent Platform sandboxes heading moved** (Sep 22 → Sep 24: Gemini 3.8 Live GA, Muse Spark 1.3 Preview — watch color, no fold). Retired duplicates (google/ax candidate = already-filed **Google AX v0.3.0**, Apache-2.0 re-confirmed; Docker-launch candidate = already-filed **Docker Cloud Sandboxes**, now 5-surface corroborated). **Vercel Drives still public beta** (P49 morning cadence, 26th consecutive no-change pass — full Drive pricing grid live, digits already folded at Vercel Sandbox Drives). Carried: Pro fee still UNVERIFIED (page structurally doesn't publish plan fees), Alibaba Cloud FC Agent Sandbox pin static `39b6c3a2`, the Google Gemini Agent Environment and Google Agent Substrate unchanged, Tensorlake no Sep-24/25 news, Prime Intellect Prime Sandboxes no-op; adjacent investor color only (Ando $20M, Island $400M Series F). No in-lane launches, pricing moves, or funding dated 9/25 in-window (#411).
  - sparkvm.dev front door, first slice: the landing page now tells the open-source story first ("Open source, running today" — MIT, runs on your Unraid/Proxmox box today, contributions welcome) and splits the two ways to run it (self-host as the near-term story, hosted as the future story with a pointer to the beta pilot on musebook). Pages-ready deploy contract: static file set, security headers (`_headers`: strict baseline + default-deny CSP on the no-JS/no-form paths), custom 404, and operator deploy steps for the Cloudflare Pages project + `sparkvm.dev` custom domain. The landed waitlist funnel wiring (CTA buckets, tag set, no-JS, no dead forms) is unchanged and now test-guarded (#412).
- Competitor corpus update (pre-dawn watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **Google AX v0.3.0** (orchestrator/harness lane, primary-source VERIFIED on github.com/google/ax — Apache-2.0, runs on Agent Substrate for sandboxed execution, kubectl-shaped CLI with ax suspend/resume/ssh, Task/Workspace/Model manifests, pre-stable; v0.3.0 notes THIRD-PARTY-convergent — strongest validation yet of the OpenAI Agents API partner list harness↔compute split / H4 per-harness-adapter thesis), **Prime Intellect "Prime Sandboxes" launch** (~2026-09-23, THIRD-PARTY — 30M agent environments, usage-based no-commitment, vCPU $0.02/hr + $0.0125/GiB-hr mem + $0.0002/GiB-hr disk ≈ 1/3 of large providers, promo through Dec 22, CPU-only with snapshots/forking/GPU on roadmap), Docker Cloud Sandboxes duplicate closed (surveyor's Docker Cloud Sandboxes launch candidate = the already-filed Docker Cloud Sandboxes event), Grunz "$100 once" flag downgraded to light-watch (figure absent from grunzai.com — now pay-per-use credits). Carried: Pro fee still UNVERIFIED (Hobby $50 re-confirmed), DO Managed Agents docs pricing subpage 7th consecutive miss (convergent release-set, no corpus change), Tensorlake no Sep-24/25 news, Alibaba Cloud FC Agent Sandbox pin still `39b6c3a2` digits unchanged, the Google Gemini Enterprise Agent Platform sandboxes, Google Agent Substrate, and Google Gemini Agent Environment unchanged. No launches, pricing moves, or funding dated 9/25 in-window (#409).
- Competitor corpus update (post-midnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures — all 8 opened directly on vendor-owned pages), **Alibaba Cloud FC Agent Sandbox repo HEAD pin REVERTED (`96ff8a8` → back to the pre-overnight `39b6c3a2` commit, VENDOR-VERIFIED via GitHub API — not a second move, no phantom third position)** with all pricing digits unchanged, **OpenAI Agents API THIRD-PARTY pricing color** (hosted-sandbox containers $0.03–$1.92 per 20-min session; ZDR inapplicable even self-hosted), new-to-watch candidate Google AX v0.3.0 (THIRD-PARTY, HN-noted — open-source Apache-2.0 agent orchestrator on Agent Substrate; primary-source pass owed). Carried: Pro fee still UNVERIFIED (Hobby $50 minimum re-confirmed), DO Managed Agents docs pricing subpage 6th consecutive miss (misattribution stays INFERRED), Tensorlake no Sep-24/25 news, Google Gemini Enterprise Agent Platform sandboxes heading still Sep 22, Google Agent Substrate/Google Gemini Agent Environment confirmed unchanged. No launches, pricing moves, or funding dated 9/25 in-window ((#385)).
- Competitor corpus update (post-overnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; Daytona pricing figures moved from baseline-carried to VERIFIED on Daytona's own pricing page — full GPU ladder now on record), **Google Gemini Agent Environment clean citation CAPTURED — debt retired** ("Environment compute (CPU, memory, sandbox execution) is **not billed** during the preview period", VENDOR-VERIFIED on ai.google.dev, page "Last updated 2026-09-24 UTC"; fixed 4 CPU cores / 16 GB memory), **Google Agent Substrate FULL vendor verification** (Google Cloud Blog: open-source secure-by-default runtime, 10x density, sub-500ms resume @ 500+ activations/sec; all GKE customers non-production, production GA via allowlist; Nous Research (Hermes) design partner), **DO Managed Agents pricing docs surface re-located and VENDOR-VERIFIED** (standalone pricing subpage still unlocated — 5th consecutive miss; rates hold $0.044/vCPU-hr, $0.0095/GB-hr, $0.005/GiB-month), **Alibaba Cloud FC Agent Sandbox pin 96ff8a8 UNCHANGED** (all pricing digits re-verified), **Hobby $50 re-confirmed** (Pro fee still UNVERIFIED). In-lane dated 9/24 THIRD-PARTY color: ByteAsk $1M pre-seed (C/C++ coding agents), Ando $20M stealth launch (team chat with native agent roles), Darktrace Signal Labs (agent behavioral-security research). OpenAI Agents API still public beta (GA absence VENDOR-VERIFIED); Vercel Drives not re-checked (P49 morning cadence) ((#384)).
- Competitor corpus update (overnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas, zero fetch failures; Daytona pricing not re-fetched — changelog-only scope, carried as baseline), OpenAI Agents API GA absence upgraded to VENDOR-VERIFIED (still public beta, `client.beta.agents` — corrects the prior fetch failures), **Alibaba Cloud FC Agent Sandbox pin MOVED for the first time** (`39b6c3a` → `96ff8a8`, VENDOR-VERIFIED on the official repo's commits page; pricing digits unchanged), Google Gemini Agent Environment VENDOR-VERIFIED in preview (compute not billed during preview), the Google Gemini Enterprise Agent Platform sandboxes, Google Agent Substrate, and Tensorlake re-verified, Freestyle pricing UNVERIFIED-carried (no public Pro price; FAQ $50/mo Hobby minimum re-verified), **DO Managed Agents pricing fourth consecutive docs-side miss — and the carried $0.05 figure is retired as current** (current general-snapshot snippets read $0.06/GB-month; the 10x discrepancy framing is withdrawn — evidence-backed Managed Agents rate is $0.005/GiB-month from the vendor's 2026-09-22 investor release), **corpus fold: DO's own billing model** (vendor-published — active CPU billed per-second, $0.126/hr fully allocated reference → ~$0.0310/hr typical 25%-active run, zero while waiting — the corpus's sharpest agent-sandbox duty-cycle pricing comp). In-lane dated 9/24: Docker Cloud Sandboxes reconfirmed (shape prices Micro $0.07 / Small $0.14 / Medium $0.28 / Large $0.56 / XL $1.12, sbx 0.45.1+, 24h max, $250 credit); Baseten×Blaxel is Sep-24 commentary on a Sep-10 deal, not a launch. Vercel Drives not re-checked (P49 morning cadence) ((#382)).

- Competitor corpus update (post-mid-evening watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas; Daytona pricing not re-fetched — changelog-only scope, carried as baseline), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox (docs HEAD pin 39b6c3a unmoved, pricing re-verified digit-for-digit), and the Google Gemini Enterprise Agent Platform sandboxes re-verified unchanged, vendor-verified, **Freestyle pricing VENDOR-VERIFIED: no monthly-fee line-item on pricing surfaces; FAQ discloses a $50/mo Hobby minimum-usage commitment** (dashboard-signed-in check still owed), **DO Managed Agents pricing third consecutive docs-side miss** (press side re-VENDOR-VERIFIED $0.005/GiB-month; INFERRED misattribution hypothesis strengthened — carried $0.05 may be DO's general-product $0.05/GB-month snapshot rate; both figures stay open), OpenAI Agents API GA absence search-level only this pass (official page fetch failed — honest weakening), **corpus fold: Docker Cloud Sandboxes first vendor-sourced price-and-terms package** (`sbx move --to cloud` one-command, per-second, Micro $0.07/hr → XL $1.12/hr, paused=free, 24h sessions, $250 credit, WeAreDevelopers NA venue). Google Gemini Agent Environment snippet-only (official surface identified, re-open owed); Tensorlake search-level no news. Vercel Drives not re-checked (P49 morning cadence) ((#381)).

- Competitor corpus update (pre-midnight watch): tracked set 8/8 VERIFIED NO-CHANGE (zero deltas — Daytona V0.216.1 SEP 24 above V0.216.2 SEP 24 baseline-confirmed, Docker Sandboxes release-notes 2026-09-21, Microsandbox v0.7.3, E2B, boat.dev pricing, TermSquad, AgentComputer, DigitalOcean still public preview), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox (docs HEAD pin 39b6c3a unmoved), the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes re-verified unchanged, OpenAI Agents API still public beta, Tensorlake no news, **corpus folds: Docker Cloud Sandboxes launch-availability VENDOR-VERIFIED** on docker.com's own Sept-24 posts + BAND Python Kit for Docker Sandboxes (THIRD-PARTY, Sept 24 — first third-party Kit-ecosystem signal), **DO Managed Agents pricing second consecutive docs-side miss** (press side re-VERIFIED $0.005/GiB-month; "Last verified 22 Sep 2026" pricing subpage still unlocatable; INFERRED misattribution hypothesis carried open). Freestyle Pro fee still UNVERIFIED (dashboard-signed-in check owed) ((#379)).

- Competitor corpus update (late-night watch): dated-2026-09-24 Register coverage corroborating the Docker Cloud Sandboxes GA venue (THIRD-PARTY; Micro $0.07/hr → XL $1.12/hr named shapes, per-second, OCI-standard Kits — matches vendor figures value-for-value), DigitalOcean snapshot-rate partial re-read (press-release side re-VERIFIED $0.005/GiB-month; docs pricing subpage not locatable this run, 10x discrepancy not re-observable, carried open), and boat.dev's product-news surface VERIFIED absent (third attempt; retry retired). Tracked set 7/8 VERIFIED NO-CHANGE (Daytona changelog reorder micro-delta only: V0.216.1 now above V0.216.2, both SEP 24, no new release) ((#375)).
- H12 usage-metering design: billable-unit taxonomy for hosted billing (box wall-clock, resource windows, approval volume, suspend/wake, push delivery), a canonical metering event envelope shared with the H5 sentinel design (per-surface mappers over the four telemetry surfaces, sequencing, trust tiers, counters-over-content privacy), emission modeled on the shipped H14 part a enqueue/retry pattern, and the filed follow-ups (#376–#378). No pricing promises — design thinking only ((#380)).
- Competitor corpus update (night watch): new Tensorlake Firecracker-microVM sandbox entry with own-page pricing (Free / Usage Credits / Pro $250 per cycle / Enterprise; snapshot storage $0.07/GB-month), Simular Sai pricing resolved from own-domain pages (Free / $50 / $500 / Enterprise), Freestyle own-page pricing verified (Hobby $50/mo), and DigitalOcean's live docs-vs-release snapshot-rate discrepancy confirmed on both vendor surfaces ((#373)).

- Competitor watch, 2026-09-24 mid evening: tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas), DigitalOcean Managed Agents pricing re-verified on the vendor's own Sept 22 press release ($0.044/vCPU-hour, $0.0095/GB-hour, $5 credit — matching DO Managed Agents pricing; pricing subpage "Last verified 22 Sep 2026" stamp re-check still carried), boat.dev product-news surface UNVERIFIED (not located), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes: no new moves, OpenAI Agents API Sep-10 public-beta dating re-confirmed VERIFIED (still public beta, no GA), **corpus folds: Docker Cloud Sandboxes GA-venue detail** (onstage launch at WeAreDevelopers North America; Sandbox Kits → standard OCI images + CNCF submission commitment; Hermes first-class Kit demo) + **DO Managed Agents pricing re-verified** (docs $0.05/GiB-month vs release's $0.005 — live 10x snapshot discrepancy, stamp re-check must resolve), in-lane dated 9/24: Docker GA venue, Island $400M/$6.4B (adjacent), Modal ~$15B talks (adjacent), Darktrace Signal Labs (adjacent) (#370).
- Competitor watch, 2026-09-24 late afternoon: tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas), DigitalOcean Managed Agents pricing still UNVERIFIED (vendor product doc fetched, carries DO's own "Last verified 21 Sep 2026" freshness line but no pricing; pricing subpage fetch failed — stamp re-check owed next pass), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes, all re-verified unchanged, OpenAI Agents API Sep-10 public-beta dating re-confirmed VENDOR-VERIFIED (still public beta, no GA), Docker Cloud Sandboxes no new moves, Vercel Drives still public beta (opportunistic re-read), **corpus fold: Alibaba Cloud FC Agent Sandbox deep-hibernation detail** (15 GiB free disk allowance does not apply in deep hibernation — VERIFIED on the vendor page), no in-lane launches/pricing/funding dated 9/24 (#365).
- Competitor watch, 2026-09-24 mid afternoon: tracked set 7/8 VERIFIED NO-CHANGE (zero pricing/feature deltas), DigitalOcean pricing docs UNVERIFIED this pass (stamp re-check owed next), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes, all re-verified unchanged, Docker Cloud Sandboxes no new moves since the fold, **asks resolved** — Boat EU-only DE/FI/FR geography re-VERIFIED verbatim on boat.dev's own FAQ (three-pass retry closed), OpenAI Agents API Sep-10 public-beta dating re-confirmed VENDOR-VERIFIED with a fresh read of OpenAI's own changelog (still public beta, no GA), **corpus folds: Snapshot pricing fully specified** (*Snapshot Storage Usage = Memory Specification × 2 + Disk Specification*, charged at Disk Unit Price × duration) + WeAreDevelopers-North-America venue detail, `_MID_AFTERNOON` admitted to the watch-doc naming convention, no in-lane launches/pricing/funding dated 9/24 (#364).
- Competitor watch, 2026-09-24 early afternoon: tracked set moves — 7/8 quiet, **Microsandbox v0.7.2/v0.7.3 new** (full-quiet streak ends at three), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes, all re-verified unchanged, OpenAI Agents API still public beta (no GA), **new in-lane corpus entry Docker Cloud Sandboxes** (VENDOR-VERIFIED on Docker's own blog: same microVM on Docker-managed compute, `sbx move --to cloud`, PAYG per-second $0.07–$1.12/h, paused free, $250 free credit), agentic-cloud framing and Tencent DataBuddy stay queued/adjacent, Snapshot-pricing fold queued for the next pass, no in-lane funding dated 9/24 (#363).
- Competitor watch, 2026-09-24 noon: tracked set 8/8 quiet (full-quiet streak advances to three), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, the Google Gemini Agent Environment, and the Google Gemini Enterprise Agent Platform sandboxes, all re-verified unchanged, **OpenAI Agents API Sep-10 public-beta dating upgraded THIRD-PARTY → VENDOR-VERIFIED** (sourcing only — OpenAI's own changelog; still public beta, no GA move), agentic-cloud framing and Tencent DataBuddy stay queued/adjacent, Google Gemini Enterprise Agent Platform sandboxes paren-balance nit adopted, no new corpus entries, no in-lane launches/pricing/funding dated 9/24 (#359).
- Competitor watch, 2026-09-24 late evening: tracked set 8/8 quiet, Vercel Drives still public beta (25th pass, GA watch now once-daily per the P49 cadence decision), **new in-lane corpus entry Google Gemini Enterprise Agent Platform sandboxes (Computer Use + Shell) GA** (VENDOR-VERIFIED on Google's own release notes), Docker CVE pair confirmed already-closed, watch-review nits adopted (#352).

- `docs/SENTINEL_TELEMETRY_SURFACES.md`: arch deep-read of the four
  audit/telemetry surfaces the hosted sentinel (H5) would consume —
  schema catalog, six structural findings (no shared event envelope, no
  sequencing or authentication, second-resolution timestamps that collide
  under burst, unstated trust tiers for agent-forgeable muse-job events,
  confirmd's silently-swallowed audit-write failure (fixed this turn so
  it signals to stderr), and confirmd's audit.log having no rotation
  bound), plus the ordered H5 prerequisites. Findings filed as GitHub
  issues. (#353–#357, #360, PR #361)

- Evening competitor watch (full quiet pass): tracked-set vendors 8/8
  VERIFIED no-change with zero fetch failures (full-quiet streak re-opens
  at one after the afternoon pass's Daytona move), Vercel Drives still
  public beta (24th consecutive pass; VERIFIED on the vendor changelog
  page this run; pricing last_updated 2026-09-10), Google Agent Substrate, Alibaba Cloud FC Agent Sandbox, and Google Gemini Agent Environment
  re-verified unchanged. No corpus fold this pass — three fold candidates
  queued for primary-source verification (Google Shell/Computer Use
  sandboxes GA Sept 9; Docker Sandboxes CVEs CVE-2026-77179/CVE-2026-79994
  Sept 15; the Alibaba/Huawei "agentic cloud" framing trend), plus a
  namesake-collision warning that Guava's "Daytona" voice model is
  unrelated to Daytona sandboxes. Afternoon vetting holds (OpenAI Agents
  API stays third-party; Tencent DataBuddy stays adjacent-watch;
  deprecated-row sunset convention stays proposed-not-codified). News
  scan: adjacent color only (Island $400M Series F on rogue-agent
  framing, Alibaba AgentCore, Darktrace Signal Labs) — no in-lane
  launches, pricing moves, or funding dated 2026-09-24. Full pass in
  `docs/COMPETITOR_WATCH_2026-09-24_EVENING.md` (#351).

### Changed
- Multi-tenancy trust model is now framed in runtime-cell vocabulary: a hosted tenant's agent owns everything inside its cell — its per-tenant box (its jail on the cooperative tier), contained root-equivalent, never host root — while the enforcement layer — egress fencing, secret swapping, metering, break-glass — stays operator-owned and invisible from inside, seen only through approvals, status, and audit. Unchanged: support access stays tenant-visible, granted, logged, break-glass-only; no operator-blindness claim. (#432)

### Fixed

- The harness auth probe no longer depends on its invoker for the 10-second
  wall-clock cap: it arms its own per-mode deadline (10s gate, 45s
  provision), and a budget expiry — or an external `timeout` wrapper's
  SIGTERM — now exits 1 with a named message instead of dying as an
  unclassified 124. The provision-mode CLI vehicle budget also grew from
  6s to 25s, so a slow but healthy provider (TLS, cold model endpoint,
  inference latency) no longer fails provisioning; a provision timeout is
  reported as slowness, never misdiagnosed as a bad credential. (#158, #159; #513)

- proxy/deploy.sh now installs `scripts/bounded_http.py` to /home/swapd
  alongside confirmd.py and registers it in confirm's install paths, so
  the standalone deployment (and its rollback) can't start confirmd
  with a missing-helper import failure. cred-ui gets the same treatment:
  its auto-deploy install step now ships the helper into the working
  checkout's `scripts/` (whose sync only refreshed `cred-ui/` + VERSION)
  and registers it in cred-ui's install paths for snapshot/rollback, so a
  cred-ui-only deploy can no longer restart the service into
  ModuleNotFoundError (#471).

- When steering a job refuses because the TUI died between the liveness
  poll and the paste, the refusal now reports the pane as seen at the
  refusal instant instead of the stale pane captured during the earlier
  poll — so the operator sees what actually defeated the paste, not
  outdated output. (#501)

- The desktop control bridge now serves each request on its own thread, with at most 8 handlers running at once: a slow driver call can no longer head-of-line-block the panel's screenshot polls or the keepalive's health probe. (#496)

- Manual rollbacks now audit the extra-inputs digest reconciliation outcome:
  a reconciliation that fails part-way is recorded on the `manual-rollback`
  and `rollback-unhealthy` audit lines as `"reconcile":"incomplete"` instead
  of logging a warning while the audit trail reads as a full success — so a
  later forced redeploy can't be misread as a genuine host-side input
  rotation. The rollback itself still completes in this case (the snapshot
  restore already landed). The reconciliation scratch file also got its own
  temp name so a manual rollback overlapping a timer tick can't clobber a
  concurrent deploy's digest rewrite. (#482)

- confirmd now bounds its HTTP thread pool and its connection setup: the
  server caps in-flight handler threads at 64 (over-cap connections are
  closed immediately, fail closed), the TLS handshake runs inside a bounded
  handler thread instead of the single accept loop (so one peer stalling
  the handshake can no longer pin all new connections), and each accepted
  socket gets a 10s timeout — an idle connection is reclaimed after 10s of
  socket inactivity. Holding a slot indefinitely now requires actively
  trickling data on all 64 connections (previously one idle connection
  sufficed) (#469).

- The jail build now validates the agent's SSH public key before doing
  anything with it: a file with Windows line endings, trailing blank
  lines, or a malformed key fails the build with a clear error instead
  of landing verbatim in the jail's authorized keys and failing the
  agent's SSH login in a way that looked like a network problem. (#467)
- The jail's firewall watchdog now re-checks the ruleset every minute
  instead of every five, so a flushed or damaged firewall is caught and
  fail-closed within about a minute rather than up to five. (#467)
- Deploy helper now states its input bounds up front: `--src` refuses
  inputs over 1 MiB, and `--stdin` is documented as deliberately uncapped
  and un-gated (deploy-script-constructed input only, never
  attacker-chosen paths) so a future caller does not assume uniform
  bounds. (#454, #455)
- Auto-deploy: three extra-inputs follow-ups from the Security review. A
  same-commit forced deploy now tags every audit line on the forced-deploy
  path with `trigger: extra-inputs` (snapshot-fail, reload-fail, and the other
  failure paths previously masqueraded as version deploys in the audit
  trail). A manual rollback now re-hashes each rolled-back component's
  host-side inputs and converges the recorded digests to the restored
  reality, instead of keeping the stale post-deploy digest that would
  force a spurious redeploy on the next tick. And a successful non-forced
  deploy no longer wipes the forced-deploy dampening timestamp — any
  version deploy touching the component used to silently reset the
  anti-churn window. (#458)
- Waitlist email spool writes are atomic now: each spooled email is written
  to a temporary file, flushed, synced, and renamed into place, so a crash
  or full disk mid-write can no longer leave a torn half-written email for
  the operator's sender to choke on or send half of (#389).
- The waitlist daemon's in-memory per-IP abuse-rate table is now bounded:
  once it passes 10,000 distinct IPs, keys with no recent activity are
  swept (rate-limited to one sweep per minute, so a flood of unique IPs
  can't turn every request into a slow full-table rebuild) (#390).
- Jail firewall watchdog: the allow-head check now compares rule lines
  after stripping whitespace outside quoted names, so a future nftables
  version that re-renders rule text (indent, brace spacing) can't turn the
  watchdog into a false-alarm machine that stops the jail every five
  minutes; interface names and log prefixes still match exactly. The jail
  build also runs the watchdog once at build time, so a check-vs-table
  mismatch fails the build loudly instead of surfacing on the first
  timer tick. (#443)

- Auto-deploy now notices when the mitmproxy CA certificate changes, even
  with no code change in the same window: the deploy timer hashes the CA
  cert alongside the repo diff and redeploys the proxy component so the
  `with-proxy` CA bundle gets rebuilt (a rotation or first-run CA
  generation previously sat unnoticed until the next code deploy). Forced
  deploy attempts are dampened (at most one per hour per component —
  including attempts that fail, so a persistently-failing input cannot
  churn the deploy/rollback loop every tick), never mark a healthy HEAD
  blocked, and are audited with `"trigger":"extra-inputs"`. The hashed
  input is bounded (1 MiB prefix + file size) so a planted sparse file
  cannot stall the tick. The read runs at the deploy privilege through an
  atomic O_NOFOLLOW|O_NONBLOCK open with no shell check-then-read window:
  a symlink/FIFO swap race or a planted FIFO can no longer stall the tick
  while it holds the single-flight lock, and symlinks, FIFOs, directories,
  and hardlinks hash as non-regular rather than being followed or blocked
  on (#302). The deploy script also honors the `WITH_PROXY_CA_BUNDLE`
  override it already advertised instead of writing a hardcoded path
  (#303), and the jail README now documents the jail build's dependency
  on the sibling `proxy/` tree (#304).

- Waitlist re-submit after a claim no longer spawns a second pending row
  for the same address: `signed_up` is terminal in the waitlist state
  machine, and the old dedup check missed it, so a claimed owner
  re-submitting the form (or path-A email) got a fresh confirm email and
  could be invited and claimed a second time — double-counting the
  funnel and stealing a later wave's slot. Re-submits on claimed
  addresses now get an honest "Already claimed" page / `already_claimed`
  outcome: no new row, no new email, nothing refreshed ((#490)).

- Approval-signal contract doc fixes: the pending id is always a single
  approval id (the list form was unreachable); the `expired` approval
  notice is documented as best-effort — confirmd's render loop usually
  reaps expired items first, so clients see the pending id change with no
  `expired` leg and should keep waiting on the new id; and the
  answered-history item schema shared by confirmd and the proxy is now a
  named, versioned (v1) cross-component contract; its (pre-existing)
  drift behavior is documented as fail-closed (#308, #309, #310, #383).
- A manual `auto-deploy.sh rollback` now marks the rolled-back commit
  blocked (like automatic rollbacks always have), so the next timer tick
  no longer redeploys the same bad commit in a fail/roll-back loop — the
  block auto-clears once a newer commit supersedes it, `rollback
  --no-block` skips it for investigate-not-condemn rollbacks, and `status`
  prints the exact `rm` command to clear it by hand (#325, #374).
- The harness auth probe's confirmd check now verifies the answering process
  behaves like confirmd — it requires confirmd's own 403 denial shape
  (`forbidden: <reason>` body plus `confirmd/1` server header, and never
  follows a 3xx off the port) instead of counting any HTTP response as
  liveness, so a port grabber, stale service, or misbound server answering
  on the confirmd port can no longer certify the approvals path as up before
  box-live. This catches accidental misbinding at the gate, not an adversary
  who controls the port (#160, #367).
- `scripts/cut-release.sh` no longer aborts with "not a git repo" when run
  from a git linked worktree (where `.git` is a `gitdir:` pointer file, not
  a directory) — the repo gate now checks `git rev-parse --git-dir`
  instead, so operator dry-runs from worktrees pass (#349, #362).
- confirmd's approval pages and the `/sw.js` service worker now send
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: same-origin`,
  so a content-type confusion can't turn an approval page into an executed
  script and approval URLs never leak to third parties via Referer (#77,
  #362).

### Security

- Denial is now terminal even in the race window (#306): the proxy re-checks for an owner denial immediately before filing a fresh approval, so a Deny tapped while a refusal was in flight no longer files a new approval and re-pushes the owner. Separately, the per-refusal denial lookup is now cached per request tuple with invalidation on every terminal write, so agents that trigger refusals at will no longer pay a full directory scan per refusal (#307). (#522)

- The credential/grant narrow writers (`cred-registry-set`, `grant-writer`, `cred-grant-revoke`, and the inference variants) no longer honor caller-controlled path-redirect variables when running as the `swapd` user: enforcement is keyed off the effective user ID, so even a direct as-`swapd` invocation (outside `sudo`, where `env_reset` already stripped them) cannot redirect the registry, grants, lock, audit-log, or secrets paths. The inference registry wrapper pins its child to the fixed inference registry via a pathless flag instead of an overridable variable. Test and development runs outside the `swapd` identity keep the override seam. (#90, #518)
- `cred-registry-set set` now merges the new placement into the existing credential entry instead of replacing it, so re-registering a credential no longer silently drops its per-entry response-scrubbing opt-out. (#96, #518)

- The provision-time echo detector now flags IPv4-mapped IPv6 loopback bindings (`::ffff:127.0.0.1` and equivalent spellings): these exact-match the proxy's host allowlists and route to loopback on the box, so they were live echo exemptions the teardown never flagged. (#504)

- Desktop screenshots are now written to a private temporary file (owner-only permissions, deleted right after serving) instead of a predictable world-readable path in the shared temp directory. (#496)

- confirmd now enforces a cumulative per-connection deadline (60 seconds,
  covering the TLS handshake and the request): a tailnet peer trickling
  data just under the per-operation socket timeout can no longer pin a
  handler slot indefinitely. Over-deadline connections are aborted
  fail-closed and logged to the audit trail as a `conn-deadline` event;
  legitimate approvals (browser poll + answer round-trips) complete well
  under the bound (#472). (#476)

- cred-ui and waitlistd now run on the same bounded, slow-loris-hardened
  HTTP server confirmd got in #469 (new shared `scripts/bounded_http.py`
  — the bounded thread pool is promoted out of confirmd so all three
  daemons share one implementation instead of diverging copies):
  in-flight handler threads are capped at 64 with fail-closed
  over-cap shedding, and the TLS handshake can never run in the accept
  loop again. waitlistd also gains the 10 s per-socket timeout its
  siblings already had — a stalled request body can no longer pin a
  handler thread forever. confirmd itself now uses the shared helper
  too (previously a local copy), and the #472 cumulative-deadline
  protection moved into the shared helper as an opt-in switch so
  confirmd keeps it — cred-ui and waitlistd leave it off, their #471
  behavior unchanged. (#471) (#499)
- The deploy installer now reads its `--src` input through the same
  symlink/hardlink/non-regular/oversize-refusing privileged-read
  discipline as the CA bundle builder (new shared `privileged_read`
  module): a symlink, hardlink, FIFO, directory, or over-1 MiB file at
  the `--src` path fails the deploy closed instead of being installed by
  the privileged process; a missing `--src` is a refusal, not a crash
  (#413). (#451)
- The privileged deploy writer now stages into randomly-named directories
  (128-bit entropy) instead of predictable per-process names, so a
  lower-privileged local user can no longer pre-create colliding staging
  directories to abort every deploy; sustained collisions still fail
  closed as an attack indicator (#333, #371).
- A failed deploy staging step now unlinks its staged temp file before
  removing the staging directory, so interrupted installs leave no
  orphaned staging directories behind (#335, #371).
- The CA-bundle builder's system-bundle read is now capped at 1 MiB like
  the swapd-CA read, so a crafted `--sys` path can't turn the privileged
  helper into an unbounded root read (#334, #371).
- Privileged-read convergence resolved as justify-with-a-test (#453): the
  deploy tick's extra-inputs hash helper and the shared privileged-read
  discipline now document why they stay separate implementations (the
  helper must never abort a deploy tick, and an oversize file must still
  flip the rotation digest instead of being refused), and a new
  conformance test runs both against the same hostile-fixture matrix —
  live/dangling symlinks, FIFOs, directories, hardlinks, missing paths,
  oversize files, unreadable files — so the duplicated open discipline
  cannot drift silently. (#480)

- Every line written to the approval audit log is now flushed to disk before the call returns: previously a crash could silently erase recent refusals from the page-cache window, and only a write error was reported. The remaining documented window is a brand-new log file's directory entry. (#72, #584)

## [0.3.0] - 2026-09-24

### Added

- `docs/ICP.md`: ideal customer profiles for the three segments — self-hosters
  (Unraid/Proxmox/Hetzner homelab), hosted signups (other Muse owners, with the
  buyer≠user packaging split), and sandbox harness builders (the separate
  sandbox product, cooperative-jail tier) — plus the trust-boundary split
  between them and who is NOT an ICP. Design thinking, not a commitment; the
  validation checklist lives in #343. (#347)

- Competitor watch (2026-09-24 afternoon): tracked set 7/8 VERIFIED NO-CHANGE —
  the eleven-pass full-quiet streak ends on Daytona's SEP 24 changelog entries
  (V0.216.1/V0.216.2, CLI/API polish, no sandbox moves); Vercel Drives still
  public beta; new in-lane corpus entry Google Gemini Agent Environment
  (managed Linux sandboxes for agents, VERIFIED on Google's own docs). (#348)

- Late-midday competitor watch (eleventh full quiet pass): tracked-set vendors
  8/8 VERIFIED no-change, Vercel Drives still public beta (22nd consecutive
  pass; a third-party snippet says "private beta" — recorded as availability
  color only, verdict stays public beta per the vendor changelog), Google Agent Substrate and
  Alibaba Cloud FC Agent Sandbox re-verified unchanged. Vetting upgrades, not launches: new corpus
  entry Namespace Devboxes (VERIFIED in-lane on the vendor's own docs —
  Linux/macOS devboxes for coding agents with native Claude, Cursor, and
  Devin integrations; reverses the midnight pass's adjacent verdict),
  Upstash Box verified on its own docs (row update; pricing still
  third-party), and the Ascii Box candidate retired — the vendor's own API
  docs brand the product Boat (hardest rename evidence yet), revealing
  built-in coding-agent harnesses on the `prompt` endpoint. No launches,
  pricing moves, or funding dated 2026-09-24. (#346)

- Midday competitor watch (tenth full quiet pass): tracked-set vendors
  8/8 VERIFIED no-change, Vercel Drives still public beta (21st
  consecutive pass), Google Agent Substrate and Alibaba Cloud FC Agent Sandbox re-verified unchanged; closed three
  owed follow-ups — the YC slug rename for Boat is now backed by a
  VERIFIED 301 (`/companies/ascii` → `/companies/boat`), folded into
  the ASCII "boat" provenance, and Boat's EU-only geography re-verified on the
  vendor FAQ (Germany, Finland, France). A sunset convention for
  deprecated corpus rows is proposed in the watch doc but not codified.
  (#344)
- H11 multi-tenancy audit: every localhost-only, no-auth, and single-owner
  assumption in the repo inventoried and ranked by blast radius; adopts the
  isolation research's findings and answers the four design questions —
  per-tenant box recommended for mutually-untrusted tenants (the jail is
  the honest, weaker boundary for cooperative tenants), the swap proxy
  must move from host-wide to tenant-bound request auth before any
  shared-host tenancy, tailnet enrollment fails closed with outage-time
  revocation designed as stale authorization, and the tenant holds root
  inside their guest while the operator owns only the layer below.
  Files #339 (tenant-bound swap auth) and #340 (open verifications);
  releases the H5, H12, and H13 design gates and confirms H10's
  provisional tenant-identity assumption. (#341)
- Re-open a denied approval from its answered-history card (H20): a
  mis-tapped Deny no longer needs the operator CLI to recover — the card
  offers "Re-open this request", which re-files it as a new pending
  approval (new id, the original request, the requester's original
  deadline kept verbatim, expired requests refused honestly) and re-pushes
  the owner. Single-tenant for now, designed for the multi-tenant future.
  (#331)
- Competitor watch (2026-09-24 morning): tracked set 8/8 quiet (ninth
  consecutive pass), Vercel Drives still public beta; corpus dedups a
  phantom provider — ASCII renamed to Boat ~2026-09-17, so ASCII "boat" folds into
  the tracked-set Boat row (same product, canonical domain boat.dev); new
  in-lane entry Alibaba Cloud FC Agent Sandbox billing — verified
  from aliyun-fc/fc-docs (Eco/Std/Pro pay-as-you-go from ~$0.037/h for a
  2vCPU/4GiB box, task-scoped and E2B-SDK-only, not a persistent VM);
  wowza.com owed re-verification closed; no new in-lane launches 9/23–24.
  (#337)
- Competitor watch (2026-09-24 predawn): tracked set 8/8 quiet, Vercel
  Drives still public beta; corpus grows a new in-lane entry — ASCII "boat"
  (persistent Ubuntu VMs for agents with verified own-page
  pricing: $20/mo plan = $20 sandbox time, $0.036/h for 4vCPU/8GB/50GB,
  EU-only); Simular Sai pricing refined (vendor-published $50/$500
  on simular.ai, sai.work carries no pricing). Full pass in
  `docs/COMPETITOR_WATCH_2026-09-24_PREDAWN.md` (#330).

- Competitor watch (2026-09-24 midnight): tracked set 8/8 quiet, Vercel Drives
  still public beta; corpus grows a new in-lane entry — Simular "Sai"
  computer-use agent GA (fleet of cloud VMs up to 100 machines); Freestyle
  boot claim qualified (marketing "65 ms" vs docs p99 under 400ms); E2B
  $21M Series A dated 2025-07-28; Modal ~$15B raise talks (third-party).
  Full pass in `docs/COMPETITOR_WATCH_2026-09-24_MIDNIGHT.md` (#329).

- Competitor watch (2026-09-23 late overnight) (#327): tracked set quiet —
  all 8 providers re-read vendor-verified with no change (sixth full quiet
  pass since the mid-afternoon fold); Vercel Drives still public beta
  (seventeenth consecutive no-change pass; pricing page last_updated
  2026-09-10; the 2026-09-23 changelog entry is the beta announcement
  re-dated, not a GA move); Boxd rate card re-verified on boxd.sh (the
  overnight pass's Boxd fold stands — no new fold); new in-window
  third-party item: Simular "Sai" computer-use agent GA on cloud VMs
  (vendor verification owed); no other in-window launches, GA moves, funding, or
  pricing moves dated today.
- Competitor watch (2026-09-23 overnight) (#322): tracked set quiet —
  all 8 providers re-read vendor-verified with no change (fifth full
  quiet pass since the mid-afternoon fold); Boxd rate card now
  vendor-verified on boxd.sh (Boxd debt resolved); new in-lane corpus
  entries Freestyle pricing ("VMs for AI Agents") and Tensorlake (
  "Sandboxes for AI Agents"); Automaid lane-drift confirmed on its own
  page (workflow-automation SaaS) and dropped from the watch list; no
  in-lane launches, GA moves, funding, or pricing moves dated today.
- Competitor watch (2026-09-23 late night) (#320): tracked set quiet —
  all 8 providers re-read vendor-verified with no change (DO Managed
  Agents pricing figures read live a fourth consecutive pass, stamp "Last
  verified 22 Sep 2026", snapshots/checkpoints $0.05/GiB-month);
  Vercel Drives still public beta (fifteenth consecutive no-change
  pass; pricing page last_updated 2026-09-10); Boxd quickstart now
  VERIFIED (rate card UNVERIFIED this pass — surveyor fetch gate —
  honestly labeled, not carried); Google Agent Substrate no new vendor datapoints
  (no GA move, allowlist-only production stands); Automaid own-page
  fetch failed again (UNVERIFIED) but third-party evidence hardened
  against it — every result names cleaning-business booking SaaS,
  moving it to lane-drift pending one successful own-page fetch;
  Tencent Cloud DataBuddy stays lane-drift; THIRD-PARTY Upstash
  15-provider comparison names newcomers (Upstash Box, Freestyle,
  Ascii Box, Namespace, Beam, Tensorlake) as future-vetting
  candidates; no corpus fold; no in-lane launches today.
- Competitor watch (2026-09-23 early night) (#318): tracked set
  quiet — all 8 providers re-read vendor-verified with no change
  (DO Managed Agents pricing figures read live a third consecutive pass,
  stamp "Last verified 22 Sep 2026", snapshots/checkpoints
  $0.05/GiB-month); Vercel Drives still public beta (14th consecutive
  no-change pass); Boxd rate card unchanged (quickstart UNVERIFIED
  this pass — honestly labeled, not carried); Google Agent Substrate no new vendor
  datapoints; Automaid own-page verification still owed (fetch failed
  this pass — UNVERIFIED); Tencent Cloud DataBuddy stays lane-drift
  (agent-workbench governance, not VM-for-agents); no corpus fold;
  no in-lane launches today.
- Competitor watch (2026-09-23 post-mid-evening) (#317): tracked set
  quiet — all 8 providers re-read vendor-verified with no change
  (mid-evening's DO Managed Agents pricing resolution stands: DO pricing docs sub-page
  re-verified live, "Last verified 22 Sep 2026", snapshots/checkpoints
  $0.05/GiB-month); Vercel Drives still public beta (thirteenth
  consecutive no-change pass; pricing page last_updated 2026-09-10, no
  changelog entries dated 2026-09-23); Boxd rate card unchanged; Google Agent Substrate no
  new datapoints since the 16:00 CDT vendor-confirm fold; Automaid
  own-page verification still owed (site fetchable this run, no launch
  announcement — third-party claim stays UNVERIFIED); no in-lane
  launches.
- Competitor watch (2026-09-23 mid-evening) (#316): **DO Managed Agents pricing discrepancy
  resolved on the primary source** — DigitalOcean's pricing docs sub-page
  fetched this pass (page stamped "Last verified 22 Sep 2026") and bills
  snapshots/checkpoints at $0.05/GiB-month, retiring the corpus's
  $0.005/GiB-month syndicated-release figure; re-verified CPU-billing
  footnote ("active CPU billing is coming soon, until then 25% of the vCPUs
  allocated to your sandbox; paused sessions incur no compute charges"),
  qualifying the per-entry paragraph's "zero while waiting" read;
  mid-afternoon fold's storage/BYOT/egress/prepaid figures re-verified
  live. Otherwise quiet: 7 of 8 tracked providers re-read vendor-verified
  with no change; Vercel Drives still public beta (twelfth consecutive
  no-change pass; no changelog entries dated 2026-09-23); Boxd rate
  card unchanged (one tool-side fetch failure on the docs pricing URL,
  reported UNVERIFIED); no new Google Agent Substrate datapoints since the afternoon
  vendor-confirm fold; no in-lane launches.
- Competitor watch (2026-09-23 early evening) (#314): tracked set quiet — 7 of
  8 providers re-read vendor-verified with no change (7/7 attempted
  vendor fetches succeeded; DigitalOcean's pricing sub-page URL was
  not extractable this pass — reported UNVERIFIED, not no-change);
  the $0.044/$0.0095 figures stand at the third-party layer, and the
  flagged $0.05-vs-$0.005 snapshot-rate discrepancy is now the
  standing DO Managed Agents pricing watch item; Vercel Drives still public beta with no GA
  move (eleventh consecutive no-change pass; the beta entry's date
  field flipped 09-23→09-22 — re-publish, not a GA move); same-lane
  third-party pricing color on Google's Filestore agent volumes for AI
  (pay-per-use capacity + lifecycle tiering, folded under Google Agent Substrate at the
  THIRD-PARTY layer); no in-lane launches.
- Competitor watch (2026-09-23 late afternoon): Google Agent Substrate-focused verification
  pass (no full tracked-set re-read — 8/8 last vendor-verified ~15:12 CDT,
  no change). **Google Agent Substrate VENDOR-CONFIRMED** — Google's own Cloud-blog
  announcement read live corroborates all nine filed Agent Substrate-on-GKE
  claims (five verbatim, the rest confirmed as filed or
  stronger) (<500 ms resume, 500+/sec suspend/resume activations,
  1,000+ dormant agents/host, Cloud Hypervisor-or-gVisor choice, integrated
  gateway, non-production for all GKE customers with production GA via
  allowlist, Nous Research/Hermes early design partner with named quote);
  new vendor facts folded into the corpus (10× density headline, open-core
  portability, harness-agnostic design, control/data-plane split, Filestore
  agent volumes, native Axion).
- Competitor watch (2026-09-23 mid-afternoon): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (tenth
  consecutive no-change pass; changelog sitemap beta-entry date flip-flop
  continues — the date field is unproven as evidence either way);
  **DO Managed Agents pricing closed** — DigitalOcean Managed Agents pricing now vendor-verified
  on the docs pricing page ($0.044/vCPU-hour active CPU, $0.0095/GB-hour
  memory, sandbox shape table, pause semantics) with an explicit caveat:
  the docs price snapshots/checkpoints at $0.05/GiB-month vs the launch
  release's $0.005 — 10× apart, one source is wrong; OpenAI Agents API partner list vendor-confirmed
  (OpenAI's own blog on the Agents API public beta; nine named sandbox
  partners including Daytona, DigitalOcean, E2B, Modal, Vercel);
  new-to-watch Google Agent Substrate on GKE (~Sep 17,
  third-party-only); no new in-lane launches in the 48h window;
  Automaid, Andon Pion, Huawei baselines hold. (#311)
- §3a smoke-check provision assets (G6): the provision-time injector now
  installs the public `smoke-test` dummy credential (spec's pass phrase,
  never a secret), appends the operator's `smoke.<domain>` echo host to
  the main proxy's `hosts.allow` (newline-safe, proxy-matching semantics)
  AND to the proxy's smoke-only scoping list (`SWAP_SMOKE_HOSTS_FILE`,
  default `/home/swapd/smoke-hosts`): the echo host swaps ONLY the
  `smoke-test` credential (refusal `smoke-host-restricted` is audited),
  closing the chosen-plaintext read oracle. Also installs a
  visudo-validated scoped sudoers fragment whose granted argv is pinned
  to `cred-store-set smoke-test` for the tenant agent user, and binds
  `smoke-test` to the echo host in the main registry (the proxy's grant
  scoping refuses unbound credentials, so the §3a swap needs the
  binding). (#313)
- Competitor watch (2026-09-23 early afternoon): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (ninth
  consecutive no-change pass; the changelog sitemap's beta-entry
  re-date 09-22→09-23 is stable since the late-midday pass — the date
  field is unproven as evidence either way); no
  new in-lane launches since the DigitalOcean Managed Agents public
  preview (already filed); DO Managed Agents pricing refined — DigitalOcean's own
  launch-release text read in full on syndicated copies (completeness
  at the same THIRD-PARTY layer; the docs Details/pricing sub-page is
  still unreached); OpenAI "Managed Agents" still
  rumor; Automaid own page still missing. (#298)
- Competitor watch (2026-09-23 late midday): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (eighth
  consecutive no-change pass; changelog sitemap re-dated the beta entry
  09-22→09-23 — a re-publish, not a GA move); no new in-lane launches
  since the DigitalOcean Managed Agents public preview (already filed);
  Docker Sandboxes 0.42.0 CVE pair closed — vendor-verified on
  Docker's own security announcements, matching the corpus's standing
  characterization with no drift (no corpus fold); DO Managed Agents pricing refined (vendor
  docs now load but dollar pricing still third-party-only — Details
  sub-page is the next ask); Automaid adjacent "AI hub for agents that
  keep working" color, own page still missing. (#296)
- Client-visible approval signal (#133): when the swap proxy refuses a
  request for lack of a grant, the proxied response now carries the
  approval id and terminal decisions in response headers —
  `X-Spark-Approval-Pending: <aid>` while a grant request is pending
  (filed or coalesced; a replaced expired item is reported as
  `expired:<old-aid>` alongside the new pending id), and
  `X-Spark-Approval-Decision: approved|denied:<aid>` once decided —
  so the requesting agent can park and re-issue instead of failing on
  a remote auth error. Denial is terminal: within the 1-hour decision
  window a denied tuple suppresses fresh filings (no owner re-push);
  denial suppression is path-scoped. Header values carry only the
  approval id and the state word — never credential names, hosts, or
  secret material. Spec: `docs/APPROVAL_CLIENT_SIGNAL.md`. (#133)
- Competitor watch (2026-09-23 midday): tracked set fully quiet — all
  8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (seventh
  consecutive no-change pass, changelog confirms no entries dated
  2026-09-23); no new in-lane launches since the DigitalOcean Managed
  Agents public preview (already filed); DO Managed Agents pricing vendor verification
  failed again (browser-service error) and Docker Sandboxes 0.42.0 CVE pair stays third-party-only
  despite stronger corroboration (0.43.0 latest per mirror, CISA
  assesses exploitation as "none", neither CVE in KEV as of Sep 16).
  (#295)
- Competitor watch (2026-09-23 late morning): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (sixth consecutive no-change pass,
  changelog confirms no entries dated 2026-09-23); DigitalOcean Managed
  Agents public preview now carries published pricing ($0.044/vCPU-hour
  active, $0.0095/GB-hour, $0.005/GiB-month snapshots — resolves DO Managed Agents pricing's
  pricing ask at third-party level, vendor verification owed) — the
  first in-lane launch verdict of the recent streak (public preview, not
  GA); Docker Sandboxes 0.42.0 CVE pair (CVE-2026-77179, CVE-2026-79994),
  third-party only, vendor verification owed. (#292)
- Competitor watch (2026-09-23 night): tracked set fully quiet — all
  8 providers re-read vendor-verified with no change, zero fetch
  failures; Vercel Drives still public beta with no GA move (fifth
  consecutive no-change pass, changelog confirms no entries dated
  2026-09-23); DigitalOcean Managed Agents docs still carry no dollar
  pricing (DO Managed Agents pricing open); adjacent re-checks — Automaid still THIRD-PARTY
  only, Andon Pion no new facts, Huawei Open Agentic Cloud still
  THIRD-PARTY; fourth consecutive pass with an explicit in-lane
  no-launch verdict (afternoon, evening, late evening, night). (#291)
- Competitor watch (2026-09-23 late evening): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (fourth consecutive no-change pass,
  changelog confirms no entries dated 2026-09-23); DigitalOcean Managed
  Agents docs follow-up (agent-harness-runtime page — preview for all
  users, pricing terms still unverified on vendor docs, DO Managed Agents pricing color);
  same-lane color — AWS Lambda MicroVMs self-hosted agent-sandbox
  reference architecture and the Herdr × Vercel Sandbox
  one-agent-one-machine plugin; no in-lane launches. (#289)
- Competitor watch (2026-09-23 evening): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (third consecutive no-change pass,
  changelog confirms no entries dated 2026-09-23); DigitalOcean Managed
  Agents preview detail (Firecracker per-session pause/resume harness,
  active-CPU billing — anti-always-on positioning, filed as DO Managed Agents pricing lane
  color, not a corpus entry); still no always-on
  persistent-agent-machine announcements from any competitor. (#288)
- Competitor watch (2026-09-23 afternoon): tracked set fully quiet —
  all 8 providers re-read vendor-verified with no change; Vercel Drives
  still public beta with no GA move (second consecutive no-change pass);
  one in-window third-party corroboration filed as investor color only
  (Firecrawl $75M Series B — no new facts beyond the §2c filing); borderline pre-window
  color on Boxd's $2M pre-seed and Alibaba FC Agent Sandbox pricing;
  still no always-on persistent-agent-machine announcements from any
  competitor. (#286)
- Competitor watch (2026-09-23 morning): 2 of 8 tracked providers moved —
  Daytona v0.216.0 hardens the SDK build context (Dockerfile COPY confined
  to the build context, filed Daytona v0.216.0) and Docker Sandboxes' 2026-09-21 release
  ships v3 kits (OCI-based packages bundling an agent workload with
  reusable mixins for tools, config, credentials, network access, and
  agent instructions — filed Docker Sandboxes v3 kits, folded into the competitor corpus);
  Vercel Drives still public beta with no GA move; market-news window
  quiet with no always-on persistent-agent-machine announcements.
- Competitor watch (2026-09-23): tracked set quiet (8/8 vendor re-reads,
  no in-window deltas); the standing Vercel 64 GB default-storage ask is
  CONFIRMED on the vendor's own pricing docs — sandboxes get 64 GB of
  ephemeral NVMe by default (32 GB only on deprecated runtimes), closing
  the 64 GB default-storage ask; Vercel Drives public beta completes with real pricing (storage,
  reads, writes, caps, concurrency); adjacent investor color on Firecrawl's
  $75M Series B. (#279)
- The excluded-host link re-sweep now covers all eight bot-blocked hosts:
  a live-browser sweep hand-verified the five later-excluded hosts (all 11
  pages load; 10/11 citations match), and the ritual's enumeration now
  filters URL false positives before counting. One citation annotated
  along the way — Daytona's retired security-exhibit page now redirects to
  their Trust Center, so the isolation quote's citation is annotated and
  re-sourcing issue #277 is open. (#278)
- Overnight competitor watch (2026-09-22): tracked set quiet (8/8 vendor
  re-reads, no in-window deltas); Boxd's SDK install URL is now
  vendor-attested — boxd.sh serves the genuine installer (canonical path
  boxd.sh/downloads/cli/install.sh), closing the last unverified item on
  the Boxd entry; Vercel Sandbox announced persistent "Drives" in public
  beta (up to 16 TiB, usage-based) — a separate feature from the
  still-unverified default-storage claim; third-party follow-up analysis
  of DigitalOcean's Managed Agents launch adds no new mechanism detail.
  (#275)
- Design for the hosted tenant status endpoint: the `GET /tenant/status`
  contract the first-ten-minutes spec, signup flow, and signup UI all
  assume — the 12 machine codes with transition rules, the `approvals_url`
  carrier, two-sided auth (magic-link cookie + linked-key), and the
  provider-layer vs tenant-layer separation (#273).
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
  determinism check and mandatory fixture teardown pre-publish. The
  round trip exercises the proxy's real filing path (a gate-only
  credential bound with narrow static limits files one approval through
  the main proxy; the operator answers through confirmd; the grant mints
  through the grant writer; the re-run proves the swap took effect),
  wired to the existing gate-fixture tooling. (#271)
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
  afternoon pass; one pre-window miss filed as watch item h-sandbox
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
- boat.dev 16-vCPU caveat confirmed as current vendor policy:
  the pricing page still
  footnotes xlarge as needing a $100+/mo plan plus operator capacity
  allocation, so any 16-vCPU hosted sizing must confirm capacity with the
  provider first; the baseline rate card is unchanged ($0.036/h default,
  stopped sandboxes free, $26 for one default running the whole month).
  (boat.dev xlarge capacity allocation; #206)
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
- Stopped/cold retention tier thinking: the hosted pricing thinking
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
- Late-evening competitor watch (2026-09-22): the tracked set was quiet
  across all eight vendor re-reads; the Boxd entry is upgraded from
  third-party-only to vendor-verified (their own site and docs read this
  pass) — fork of a live machine lands in under 200 ms (correcting the
  <100 ms press claim), the active-connections-fork claim is NOT
  vendor-attested, plus pricing (€0.049/vCPU-hour, €0.015/GiB-hour RAM,
  €0.0001/GiB-hour disk, €30 free credits) and a confirmed self-hosted
  offering; Boxd's "under a millisecond" idle-resume is a marketing-page
  figure with no published methodology and is not treated as a
  benchmark. (#272)
- Competitor corpus consolidation (2026-09-22): the deferred watch entries
  Deferred competitor entries folded into the competitive map — first
  entries for boat.dev ($0.036/h default; xlarge capacity-gated),
  DigitalOcean Managed Agents ($0.044/vCPU-hour active-CPU metering),
  Boxd (vendor-page-verified fork claims and pricing),
  Upstash Box (snapshot/restore mechanics), h-sandbox (OSS credential-vault
  comparand), Brig (local microVM containment), and Epho (agents-as-API with
  multi-provider fallback), plus the OpenAI Agents API harness↔compute split
  as a design input for the hosted product's per-harness adapters. (#274)

### Changed

- Hosted pricing thinking refreshed: the internal pricing analysis now
  reflects the decided Fly.io provider (boat.dev under evaluation as a
  cheaper alternative), records Epho's bring-your-own-keys infra-only
  metering as a candidate shape for model-token billing (zero margin risk),
  and drops the stale merge-order note — all cited strategy docs are on
  main and price inputs re-verified through the 2026-09-21 competitor
  reads. (PR #253)

### Fixed

- The two privileged install-safety regression tests (staged-temp
  substitution and staging-dir swap) previously self-skipped in CI because
  runners are non-root, so the merge gate never actually exercised the
  guard they prove — they now run under sudo on every PR, and a skip in
  that step fails the build instead of passing silently. The stale "no
  root" header on the test module and the "atomic via O_EXCL" comment in
  the deploy script are corrected to match. (#345)
- The auto-deploy updater re-verifies the working checkout is clean
  immediately before syncing a component subtree into it, not just at the
  pre-deploy gate: a manual edit made between the gate and the install no
  longer gets silently clobbered — the deploy aborts with an alert and
  retries on the next tick, without marking the commit blocked (components
  already installed in the same run are rolled back first). (fixes
  #324, PR #338)
- The deploy health check now reads the port as the trailing `:digits`
  field and treats everything between `tcp:` and that field as the host.
  Malformed entries (missing or non-numeric port, empty host) fail the
  health check closed with a clear log line instead of being probed
  with a garbage port. (fixes #323, PR #328)
- A failed swap audit no longer emits a false approval signal: the
  credential proxy records the grant's `approved:<id>` terminal signal
  only after the audit write succeeds and the substituted credential is
  actually returned. Previously the signal was recorded during resolution,
  so a swap vetoed by the audit gate still told the requesting agent its
  credential had been approved and swapped. (fixes #305, PR #328)
- The auto-deploy pre-deploy gates now cover every test module in each
  component: four proxy test suites (install safety, CA bundle, secrets-dir
  enforcement, credential-validation grammars), confirmd's push-queue tests,
  and the full cred-ui HTTP/version suites had silently drifted out of the
  gate, so a green gate said nothing about them. A new tripwire test pins
  the gate commands against the test files on disk so the gap can't recur.
  The stale-updater warning (a merged updater fix that nobody activated with
  `init`) now also fires on the automated deploy path, not just
  `check`/`status`, since the timer only ever runs `deploy`. (#326)
- The Daytona isolation quote in the multi-tenant isolation research is
  re-sourced: the vendor's security-exhibit page was retired (it now
  redirects to their Trust Center, where the quoted claim no longer
  appears), so the citation points at the vendor's own docs source pinned
  at the file's final revision before removal — the quoted claim is
  byte-identical to the one surveyed earlier. (#319)
- The answered-approval history feed no longer re-parses every approval
  file in the on-disk archive on each 5-second poll — it reads only the
  200 most recent, so poll cost stays flat as the archive grows to its
  1000-file bound (the visible feed still shows the 100 newest
  approvals). (#315)
- Approvals whose expiry instant crosses during grant minting are now
  refused with a distinct audit event instead of being recorded as
  approved — the trust anchor "expired items are refused, not silently
  denied" holds even across the up-to-15-second mint window (#240).
- The credential web UI's HTTP server now drops stalled connections at a
  10-second bound: a client that declares a request body and then stalls
  can no longer pin a server thread forever (#282).
- The jail build now fails loudly if the proxy-helper script it generates
  for the jail has a quoting slip: the generated script is syntax-checked
  at build time, and the build smoke tests pin the generated script's
  shape so an unescaped variable can't silently corrupt it. (#290)
- Credential validation rules are now canonical everywhere they are
  checked — the credential CLI, the credential web UI, and the registry
  writer previously disagreed on edge cases (over-64-character names,
  over-long host bindings, and `_`/`.` in custom header names were accepted
  in some places and rejected in others). Names are now capped at 64
  characters, host bindings at valid DNS shapes (253 total / 63 per label),
  and header/query placement names at 64 characters, with a shared
  conformance test keeping the copies in lockstep. Two deliberate
  carve-outs for credentials registered before the cap: the swap proxy
  keeps serving them, and management/read operations still work on those
  legacy names — get/delete/unregister in the CLI, delete and host-unbind
  in the web UI, and the full management verb set (remove, host
  bind/unbind, method/path limits, scrub flags) in the registry writer.
  Creating new entries (set/register) — or minting a credential through a
  management verb — always requires a within-cap name. (#276)
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
  competitor watches (evening, afternoon, boat.dev xlarge capacity allocation resolution, morning), the
  secrets-posture repositioning doc, and the Fly-driver and suspend/wake
  research docs are now listed, and the stale "latest" labels in the
  competitor and loop-governance tables are corrected to dated style.
  (#218)

### Security

- `muse-job log` now sanitizes the job terminal it prints: the pane
  content an agent controls goes through the same ANSI/control-character
  sanitizer as every other operator-facing surface, so a crafted pane
  can't inject escape sequences into the operator's terminal. (#290)
- The dead-TUI steer refusal error now sanitizes the pane tail it prints:
  the up-to-8-lines of agent-influenced terminal content in the refusal
  are stripped of escape/control sequences before reaching the operator's
  terminal. (#290)
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

- Hardened the deploy-time CA bundle build and install against three
  remaining local-attacker primitives: the CA source now refuses hardlinks
  (a hardlink is a regular file, so the earlier symlink refusal didn't
  stop it), refuses files over 1 MiB before the privileged read (no more
  unbounded RAM/disk fill from a planted file), and installs bundles with
  an atomic rename — a racing reader now sees the old or the new bundle,
  never a truncated one. (#299, #300, #301)

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
  new backlog items — the #47 resume-latency target, the stopped/cold
  cost tier for hosted pricing, and the control-plane-visible lifecycle
  parity audit (#168)
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

[unreleased]: https://github.com/ntindle/spark-vm/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/ntindle/spark-vm/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/ntindle/spark-vm/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/ntindle/spark-vm/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/ntindle/spark-vm/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ntindle/spark-vm/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ntindle/spark-vm/releases/tag/v0.2.0
