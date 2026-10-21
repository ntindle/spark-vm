# Competitor watch — 2026-10-21 (morning, cycle 77)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-76 baseline —
**15 VERIFIED NO-CHANGE, 3 VERIFIED DELTA, 0 UNVERIFIED** (19 opens /
18 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 18th consecutive cycle — recovery declined per the
standing rule) / 0 URL-recovery searches (all anchors from the slot
brief or local chain grep)). The three A-lane deltas: (1) Docker
Sandboxes **v0.49.1** (dated 2026-10-20; "v0.49.0 was skipped — covers
all changes since v0.48.0"); (2) Vercel changelog dated sitemap **1434
→ 1437** — three new dated entries ("Skipped monorepo deployments no
longer count against limits" 2026-10-21, "WebSocket support is now
generally available" 2026-10-20, "DeepSeek V4.1 Flash is now available
in Token Pass" 2026-10-20), all non-sandbox by title — sitemap
bookkeeping per the C71 precedent; (3) the Vercel Drives private-beta
changelog page now opens with a **GA callout** ("Vercel Drives is
generally available as of October 15, 2026") linking the launch blog
post, the C86-tracked 2026-10-15 GA changelog entry, and a complete
guide — first-party corroboration of the filed C86 GA on the legacy
beta page; page head title now "Drives for Vercel Sandbox in Private
Beta" (URL-slug wording) vs the cycle-76 public-beta wording.
Surveyor B (delegated subagent, read-only): bounded delta news scan —
**1 CANDIDATE / 9 clean dedupes / 10 flagged-only** (17 searches, all
successful; 1 page opened and read in full, successful). The candidate
is corpus-move-grade: **Vercel published its first-party $1M sandbox
challenge findings report** (`vercel.com/blog/findings-from-the-1-
million-dollar-vercel-sandbox-challenge`) — read in full by the
integrator this pass (VENDOR-VERIFIED), with the B-lane's
third-party distillation (vibeleaderboard.ai, Oct 14, read in full)
corroborating. Folded as the **fourth C76 advancement**; no new
C-number.
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still talks-only —
PitchBook Series G dated 2026-09-22 still "Rumor/Speculation"; latest
confirmed round remains the June $13B Series F; no S-1);
**C12 OPEN** (77th consecutive first-party AgentComputer read — still
no egress pricing line).
**Corpus move this cycle: 0 filings + 2 folds + 2 watch-doc dated
deltas; 0 age-out movements.** Last-issued C-number: C89 (unchanged).
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261021-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-21 ~09:1x–~09:3x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (15
> VERIFIED NO-CHANGE, 3 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9), and with its fetch stats (18
> successful fetches + 1 established 404 = 19 opens). Surveyor B's
> capture enumerates exactly 1 candidate + 9 dedupes + 10
> flagged-only, reconciling with its header and search stats (17
> successful searches; 1/1 successful open). The B-lane candidate is
> a re-fold (C76 fourth advancement), not a new filing — the
> integration records 0 filings + 2 folds + 2 watch-doc dated deltas;
> the Docker and sitemap deltas were recorded as dated deltas per
> their precedents, not minted. Corpus-number integrity: last issued
> C-number C89 (cycle 76); this cycle issues none.

## Corpus moves: folds

**C76 fourth advancement — Vercel publishes its first-party $1M
sandbox challenge findings report (VENDOR-VERIFIED, read in full by
the integrator 2026-10-21).** New vendor-published facts on the C76
incident surface: (1) **day-one snapshot cross-account swap flaw** —
when a sandbox snapshots, the control plane recorded the snapshot's
`{storage_url, size, checksum}` from software running inside the
guest, and host services trusted it; a researcher intercepted the
snapshot response inside their own sandbox, rewrote it, and swapped
the storage objects of two snapshots belonging to two separate
accounts they owned — restoring "your" snapshot materialized the
other account's entire filesystem (read + modify, hash-verified by
the researcher). Targeted attack on a specific victim required
knowing the victim's internal snapshot storage key (a random 96-bit
identifier the platform generates per snapshot and never exposes
through the API — the only place it appears is inside the victim's
own sandbox), so no stranger-to-victim path was demonstrated; Vercel
treated it as a priority fix regardless ("a boundary that depends on
a secret staying secret is not a boundary"). Fix shipped within a
week: snapshots bound to the originating project (anything else
rejected), creation moved host-side out of guest reach,
project-scoped strictly validated storage paths. Trail of Bits
independently flagged the same root cause. (2) **Vercel-internal
device-mapper recycled-block cross-tenant leak** — found by Vercel
intern Marcos Hernanz: any sandbox could read recycled disk blocks
from previously deleted sandboxes. (3) **Trail of Bits white-box** —
4 engineer-weeks, 20 findings (each tested, confirmed, and
code-referenced); architectural review concludes the Firecracker
virtualization boundary is sound (each sandbox its own microVM,
dedicated guest kernel, tiny device model; no guest shares a
running kernel with the host or another tenant); three structural
recommendations implemented (eliminate all guest trust — anything
crossing the boundary is server-derived or signed with a
guest-unreachable key; one policy, one decider — single
canonicalization routine per data type, revalidate connections on
policy change; assume the next zero day — host kernels current,
nested virtualization disabled, Firecracker's jailer with restricted
permissions). (4) **Challenge stats:** 1,285 reports in two weeks
(877 duplicates, 319 not applicable, 57 valid, 32 informative); 1
Critical / 5 High / 9 Medium / 42 Low; $242,000 in bounties paid;
the most severe finding was the kernel zero day (the filed C76
vuln — PwnEscape, Paulos Yibelo, day three); no report showed
anyone accessing customer data. "Fixes are under private review
and CVEs are pending, so we are not publishing additional
details until the patches are public" — the vendor's own
disclosure states the kernel-zero-day CVEs are still pending. The
B-lane's third-party distillation (vibeleaderboard.ai, Oct 14,
read in full) corroborates the snapshot swap, the device-mapper
leak, the Trail of Bits posture, and the challenge stats;
its "Patches and CVEs are pending" line is redundant with the
first-party page. No new C-number — the advancement is the
vendor's own findings disclosure, not a new incident. Gate items:
pwn.ai's promised Part 2 (still pending) + stable-branch patch
adoption tracking (the deliberately-partial fix commit
6785011f8b16's fuller ingress check, per the cycle-73 fold).
spark-vm relevance: the vendor's own "eliminate all guest trust"
recommendation independently corroborates spark-vm's server-derived
posture on trust boundaries (fingerprint/spoof discipline, #844);
the snapshot-swap flaw is a concrete instance of the class —
guest-supplied addressing metadata must be server-derived or
project-scoped server-side, which is exactly the shape of the
hosted lane's snapshot/fork binding thinking.

**C86 corroboration fold — Drives GA callout lands on the legacy
private-beta changelog page.** `vercel.com/changelog/drives-for-
vercel-sandbox-in-private-beta` (dated 2026-09-23) now opens with:
"Vercel Drives is generally available as of October 15, 2026. Read
the launch blog post, changelog, and complete guide for more
information." — linking the C86-tracked GA changelog entry, the
launch blog post, and a complete guide. The rest of the beta page
body (beta SDK instructions, waitlist typeform) is unchanged. Page
head title now reads "Drives for Vercel Sandbox in Private Beta"
(URL-slug wording) vs cycle-76's "Drives for Vercel Sandbox are
now in public beta". No new C-number — the GA is filed (C86); this
is first-party corroboration on the legacy page. The beta-page
title-wording watch item is answered: the wording is now the URL
slug, not a status claim.

## Watch-doc deltas (no new C-numbers)

**Docker Sandboxes v0.49.1 — dated delta (VENDOR-VERIFIED, first-
party release notes, dated 2026-10-20).** "> v0.49.0 was skipped.
These release notes cover all changes since v0.48.0." Headline
clusters: **kit compatibility** — `sbx kit validate` / `sbx kit
inspect --offline`, build-time `--kit-arg` scoped overrides for
local/Git v3 kits, multi-agent-kit sandbox starts, Windows junction
kit mixing, multi-OAuth kit auth, `sbx kit sign` git-warning,
kit-directory rejection of unsupported entries + `sbx kit pack`
symlink rejection; **proxy support for cloud connections** —
`proxy.sshDirect` cloud-SSH setting, cloud commands/TUI/cloud SSH
honor system and PAC proxies, `sbx mcp add` OAuth discovery over
HTTP proxy; **sandbox shutdown reliability** — startup waits for
Docker, daemon shutdown/sandbox reset no longer hang, reset
concurrency, port-change clean failures, SSH fail-cleanly; daemon
log size/retention settings
(`daemon.log.maxSizeMB/maxBackups/maxAgeDays`); `browser.enabled`
host-browser setting; C/C++ toolchain in full templates; Cursor
Workspace Trust prompt fix; CIDR deny precedence; `-q` rule-ID
output for `sbx policy ls` / `settings ls` / `policy approval ls`.
Recorded as a watch-doc dated delta (no new C-number) per the
C32/C69 version-bump precedent.

**Vercel changelog dated sitemap 1434 → 1437 (+3).** The three new
dated entries sit above the cycle-76-recorded top entry; every
dated section beneath matches the C76 baseline
record-for-record: 2026-10-21 — "Skipped monorepo deployments no
longer count against limits"; 2026-10-20 — "WebSocket support is
now generally available"; 2026-10-20 — "DeepSeek V4.1 Flash is now
available in Token Pass". All non-sandbox by title (deployment
limits, WebSocket, AI Gateway model). Sitemap bookkeeping per the
C71 precedent. Note: the WebSocket GA entry is unqualified by
product in the title; not graded sandbox-relevant — no follow-up
folded.

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  talks-only — PitchBook Series G dated 2026-09-22 still
  "Rumor/Speculation"; latest confirmed round remains the June
  $13B Series F; no first-party close announcement; no S-1 filing.
  The third-party "~$37B eyes valuation after OpenAI partnership"
  arithmetic is talks-only on an unclosed round. Arm stays armed.
- **C12 — OPEN (77th consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-21;
  tracked fields verbatim; first bill including egress still
  postured for November 1, 2026. No went-live banner; B-lane
  reconfirm: no posture change.
- **Vercel Drives GA — FILED (C86).** Corroboration fold this pass
  (GA callout on the legacy private-beta page); no pricing or
  posture changes on the GA surface.
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm, Oct 13, Moderate; no 100690). File on
  first-party GHSA only.
- **VerCellBreak (TL-2026-3425) — third-party-only.** No new
  movement — still no CVE, no vendor patch, no first-party
  response published. Below the filing gate.
- **C76 — fourth advancement filed this pass (see above).** The
  vendor's findings report closes the challenge-corpus write-up
  gate item only — the **KVM zero-day technical write-up is a
  distinct document and still pending** (the first-party page: "we
  are not publishing additional details until the patches are
  public"; "Fixes are under private review and CVEs are pending").
  Remaining gates: pwn.ai's promised Part 2 + stable-branch patch
  adoption tracking (fuller ingress check for the
  deliberately-partial 6785011f8b16) + Vercel first-party KVM
  zero-day technical write-up (distinct doc; still pending).
- **C89 — Daytona Series B first-party confirmation pending.**
  Vendor-verified bar still unmet (no vendor blog or press
  release sighted); pricing-posture follow-through watched.
- **OpenAI training-agent DNS escape — pause holds.** No new
  sightings.
- **Perplexity SPACE Part II — still unmet.** No Part II label
  anywhere this pass.

## Flagged but not filed

- **Daytona Series B wave texture** — deduped to C89 (vendor-
  verified bar unmet; carry).
- **SPACE recaps** — deduped to C87 (no new partners, no Part II,
  no traction figures; carry).
- **Drives pricing guides** — deduped to C86 (no posture changes;
  carry).
- **severitydaily 2026-127-AWS persistence** — deduped to C79
  (already folded; carry).
- **Microsoft Project Perception (Oct 19) / SandboxAQ Switch Trust+ROI
  (Oct 19)** — agent-governance tooling, out of the
  sandbox-provider lane; below the file bar (carry).
- **Zenity AgentCorruption** — no CVE, no bulletin; only recaps
  (carry).
- **MXC Intune "coming soon"** — deduped to C78 (carry).
- **Docker $250 Agent Challenge** — active through Oct 31 (carry).
- **Vercel WebSocket GA / monorepo-deployment limits / DeepSeek V4.1
  Flash Token Pass** — non-sandbox entries, sitemap bookkeeping only
  (carry).
- **Boat homepage leaderboards** — marketing copy naming providers
  (carry).
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass.

## Aging

- No age-outs this pass. 0 filings, 2 folds. C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261021-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C89 — Daytona's
first-party Series B confirmation (vendor blog/press release) +
pricing-posture follow-through; C76 — pwn.ai's promised Part 2
(the write-primitive-to-host-control chain) + stable-branch patch
adoption tracking (fuller ingress check) +
Vercel first-party KVM zero-day technical write-up (distinct doc; still pending); C88 — first-party Kiro
page read for vendor-verified grading + Kiro credential-brokering
posture; VerCellBreak first-party/CVE movement; SPACE open-source
follow-through (repo traction, second partner announcements,
partner pricing posture); Vercel Drives GA follow-through
(usage/pricing posture changes); Perplexity SPACE Part II (still
unmet); Strands Box multi-OS follow-through; Hugo GHSA movement on
CVE-2026-100690; NanoCo re-grade (first-party bar); AgentCore SDK —
any NEW AWS advisory beyond 2026-127-AWS; Modal egress billing
post-Nov-1 (first bill arrives November 1); Zenity
AgentCorruption CVE/bulletin; Docker Agent Challenge through
2026-10-31; Modal VM Sandboxes progression; Hopx/Beam/Tenki
first-party material; Docker v0.49.x follow-through; Microsoft
Execution Containers enterprise-management follow-through; the
Vercel sitemap count field (1437 baseline).
