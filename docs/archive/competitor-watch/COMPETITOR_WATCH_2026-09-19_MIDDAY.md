> **Archived 2026-09-19.** This watch pass's deltas were consolidated into `docs/COMPETITOR_ANALYSIS.md` (the 2026-09-19 night + morning + midday watch update); the original doc is preserved verbatim below. Supersedes the corresponding watch-pass PR #102, which should be closed as superseded.

# Competitor watch — 2026-09-19 (midday pass)

Delta-only update against the 2026-09-19 ~05:30 CDT morning baseline
(PR #82, `docs/COMPETITOR_WATCH_2026-09-19_MORNING.md`). Surveyed 2026-09-19
~10:55 → ~11:35 CDT.

Summary: **the sandbox-escape-week story deepens** — the same Docker
Sandboxes 0.42.0 release that shipped the fix for CVE-2026-77179/79994
unlabeled in its release notes also closed two *other* sandbox-boundary
vulnerabilities (host D-Bus command execution, cross-sandbox OAuth port
claim), per a third-party read of the release notes. Otherwise the window
is quiet: no new launches, pricing changes, tier changes, or partnership
moves across the tracked set. C1, C9, C10, C11, C12 all stay open. This
pass also closes the open #64 methodology item by **declaring the corpus
left edge and reach-back policy** (§6).

Conventions: **VERIFIED** = read on a vendor's own page, doc, repo, or
security announcement this run (link inline). **INFERRED** = third-party
characterization, labeled as such. "No change detected" is reported
explicitly.

## 1. Docker Sandboxes: the escape week is four vulnerabilities, not two

- **INFERRED (third-party outlet Severity Daily, quoting Docker's own
  release notes, [article](https://severitydaily.com/docker-sandboxes-cve-2026-77179-virtio-fs-symlink-fix-unlabeled-0-42-0/)):**
  the 0.42.0 release notes (Sep 7) contain roughly thirty bug-fix entries,
  two of which are *explicitly described as vulnerabilities* — and neither
  is CVE-2026-77179 or CVE-2026-79994:
  > "Fixed a vulnerability where a sandboxed process could get the daemon
  > to open a host D-Bus transport and execute an arbitrary command on
  > the host."
  >
  > "Fixed a vulnerability where a malicious sandbox could hijack another
  > sandbox's OAuth login by pre-claiming its callback port."
  The two CVEs have no entry naming them in the notes at all — the
  critical virtio-fs symlink escape (CVE-2026-77179) shipped unlabeled,
  eight days before the Sep 15 CVE records. Docker has not connected the
  D-Bus fix to either CVE.
- **INFERRED (thehackernews / realhacker.news / hacklido press roundup,
  all third-party, [one](https://hacklido.com/news/critical-docker-sandboxes-flaw-lets-malicious-guest-code-read-and-modify-macos-host-files)):**
  Docker's stated remediation — upgrade to 0.42.0+, or use `--clone` mode
  and avoid read-write host mounts. Clone-mode caveat from Docker's own
  docs (quoted in the press): it mounts the repo read-only at
  `/run/sandbox/source` but **does not prevent reads** — untracked files
  such as `.env` stay readable inside the sandbox. CVE records were
  published Sep 15 (8 days after the fix shipped); CVE-2026-79994's record
  initially listed a never-published 0.41.0 as the fix version, corrected
  to 0.42.0 ~1h after publication (matches #82's vendor-record caveat).
  Credits: Oren Yomtov of accomplish.ai (CVE-2026-77179), Jurre van Bergen
  of ThreatNotify (CVE-2026-79994).
- **Implication:** four sandbox-boundary vulnerabilities closed in a
  single release — two vendor-announced (CVE-2026-77179/79994) plus two
  reported via a third-party read of the release notes (D-Bus command
  execution, OAuth port claim). The shared-workspace boundary is the
  trust story of a persistent-VM-for-agents product, and this is the
  week's loudest object lesson that "a microVM + mounted host folder" is
  a fragile model; Docker's unlabeled-shipping of the critical fix is a
  disclosure-process data point too. Strong raw material for the **O13
  trust/transparency doc** (already a backlog item) — with honest
  scoping: spark-vm's full-VM-without-host-folder-sharing design
  (`jail/README.md`) is outside the shared-workspace guest→host
  sub-class both CVEs broke, while the D-Bus daemon-boundary and OAuth
  port-claim classes are surfaces any managed product retains —
  including a hosted spark-vm — so the O13 writer must treat them as
  owned-risk categories, not solved-by-architecture.
  Note for the O13 writer: the D-Bus and OAuth-port quotes are
  third-party-quoted-from-vendor here, not yet read directly on the
  vendor's release-notes page.

## 2. Blaxel — minor releases only (C11 stays open)

- **VERIFIED (GitHub releases, [blaxel-ai/sandbox](https://github.com/blaxel-ai/sandbox/releases/tag/v0.2.59)):**
  Sandbox API v0.2.59: "Link the sandbox welcome response to its built-in
  API reference." v0.2.58: dependabot dep patches + "skip Unix sockets in
  the export" — maintenance, no capability or pricing change.
- **VERIFIED (GitHub, [changelog](https://github.com/blaxel-ai/deepseek-harness-blaxel-sandbox/blob/HEAD/CHANGELOG.md)):**
  the `deepseek-harness-blaxel-sandbox` IDE plugin shipped 0.1.2 (Sep 3);
  the 0.1.3 candidate is unreleased. Plugin-level moves only.
- **No change detected** on Blaxel's pricing, tiers, or sandbox model this
  window. C11 stays open.

## 3. OpenAI Agents API — nine partners unchanged (C9 stays open)

- **INFERRED (third-party roundups describing the Sep 10 public beta,
  e.g. [fourweekmba](https://fourweekmba.com/ai-openai-agents-api-public-beta-codex-harness/)):**
  the partner set is unchanged — **Blaxel, Cloudflare, Daytona,
  DigitalOcean, E2B, Modal, Oracle, Runloop, Vercel**. No new partners,
  no terms changes (US-only data residency, no ZDR).
- **INFERRED ([aicraftjournal pricing data point](https://aicraftjournal.com/articles/openai-agents-api-public-beta-no-extra-fee-hosted-sandbox-1gb-003)
  — third-party, unverified against OpenAI's own pricing page):**
  OpenAI-hosted sandbox 1 GB at $0.03 per 20 minutes. Directional pricing
  floor for the ephemeral-exec axis, not corpus fact.
- **Observation (third-party, architectural):** the Agents API separates
  the harness (OpenAI runs the loop, sessions, compaction) from execution
  (your infra / partner sandbox / VPC). The market's most important
  platform is normalizing bring-your-own-sandbox as a first-class shape —
  which supports the **hosted** spark-vm pitch: a *persistent, full-VM,
  sign-up-and-use* computer where the platform operates the loop and the
  tenant's box is the execution plane, positioned against the
  ephemeral-exec pricing floor rather than competing with it. C9 stays
  open.

## 4. Tracked set — no change detected

- **TermSquad (C1):** no in-window pricing, tier, or session-model moves
  surfaced. x.com/trytermsquad remains login-gated (the watch-method gap
  stands — updates still route through the closed channel).
- **WSO2 (C10):** reception remains thin — wire syndication plus a
  badsignal.ai editorial take and a TechGig recap (both third-party).
  Next milestone: the Sep 29 webinar. C10 stays open.
- **AgentComputer (C12):** repos unchanged (computer-guest untouched; no
  new releases). No change detected; C12's narrowed-to-egress-only status
  stands.
- **Quiet in window:** E2B, Daytona, Modal, Runloop, Northflank, Vercel,
  Cloudflare, GitHub Copilot (JetBrains controls — verified #82), the
  OpenRouter `openrouter:shell` tool (verified #82), Tencent BrowserSkill
  (verified #82) — no new moves.

## 5. Backlog deltas from this pass

- **O13 (trust/transparency doc) gains material:** four boundary vulns in
  one Docker release + unlabeled critical fix + Docker's own "clone mode
  doesn't prevent reads" caveat. The O13 writer now has a strong but
  partially-sourced negative example; the D-Bus/OAuth quotes need a direct
  read of the vendor release notes before publication
  (https://docs.docker.com/ai/sandboxes/release-notes/).
- **C2 (pricing inputs) optional third-party datapoint:** OpenAI-hosted
  sandbox ~$0.03/20min per 1 GB (unverified) — useful only if the pricing
  corpus wants an ephemeral-exec anchor; labeled third-party.

## 6. Corpus left edge and reach-back policy (closes the #64 follow-up)

- **Left edge:** the Sept-2026 competitive map in
  `docs/COMPETITOR_ANALYSIS.md` (PR #26, deepened by the #34 pm watch;
  open PR #54 carries the still-pending evening-pass consolidation).
  Watch docs are delta-only against the *previous watch doc*, which
  chains back to this baseline.
- **Reach-back policy:** a watch pass backfills a pre-window item only
  when a primary-source verification or a factual correction demands it
  (the #82 pattern); otherwise pre-window items are not re-researched.
- **Deep-scan cadence:** on-demand by review/meta runs, not by the hourly
  loop. The hourly pass stays delta-only.
