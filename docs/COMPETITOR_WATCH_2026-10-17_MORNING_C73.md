# Competitor watch — 2026-10-17 (morning, cycle 73)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-72 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTAS, 0 UNVERIFIED** (19 opens /
18 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 14th consecutive cycle — recovery declined per the
standing rule) / 1 URL-recovery search (Hugo advisories index, never
used as evidence)).
A-lane deltas: Daytona SDK V0.225.0 (dated 2026-10-16 — NVIDIA B200
GPU type) and the Vercel changelog dated sitemap (1425 → 1430 — new
2026-10-16 and 2026-10-17 sections, all four entries AI Gateway model
launches, non-sandbox).
Surveyor B (delegated subagent, read-only): bounded delta news scan —
**1 CANDIDATE / 12 clean dedupes / 4 flagged-only** (15 searches,
15 successful / 0 failed; 5 pages opened and read in full, 5
successful / 0 failed).
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still in talks —
analyticsinsight roundup: "Neither round has closed, and the funding
amounts remain undisclosed"); **C76 ADVANCED — second advancement
since filing** (CVE-2026-99999 assigned, CVSS 9.3 Critical; NVD
record received; stable-branch backports with first fixed versions
published; the 2026-10-16 cyberpress caution that the identifier was
unconfirmed is now superseded); **C12 OPEN** (73rd consecutive
first-party AgentComputer read — still no egress pricing).
**Corpus move this cycle: 1 fold (C76 advancement), watch-doc deltas.**
No new C-numbers. Captures:
`hidden_files/agent_notes/surveyor-a|b-20261017-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-17 ~09:1x–~10:4x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTAS, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9), and with its fetch stats (18
> successful fetches + 1 established 404 = 19 opens). Surveyor B's
> capture enumerates exactly 1 candidate + 12 dedupes + 4
> flagged-only, reconciling with its header and search stats
> (15/15 successful searches; 5/5 successful opens). Corpus-number
> integrity: last issued C-number C87; this cycle issues none —
> the C76 advancement folds without a new C-number, and both A-lane
> deltas grade as watch-doc deltas per the C32/C69 version-bump
> precedent.

## Corpus moves: filings + folds

**C76 fold — CVE-2026-99999 assigned + stable-branch backports
(second advancement since the 2026-10-03 filing).** New since the
C72 fold (write-up + Linux mainline merge Oct 14, CVE pending): the
flaw — nicknamed PwnEscape — now has a formal CVE assignment,
**CVE-2026-99999**, rated Critical (CVSS 9.3) by the kernel
maintainers; the NVD record was received (NVD's own review pending);
the fix (commit 6785011f8b16, Red Hat's Michael S. Tsirkin) is
deliberately partial — framed as "defence in depth", with a fuller
ingress check still needed — and has been backported to stable
branches with first fixed versions published: 5.10.272, 5.15.223,
6.1.190, 6.6.159, 6.12.113, 6.18.57, 7.2.11; not in CISA KEV; no
real-world exploitation reported (third-party: The Hacker News, Oct
2026 — surveyor B read this coverage; the same coverage references
Vercel's own challenge report — $242,000 paid across 1,285 reports,
top report $50,000 — carried in the flagged section). This
supersedes the 2026-10-16 cyberpress caution recorded in the C72
fold (the identifier is now assigned, not merely sighted). Folded
into the C76 row (no new C-number — the advancement is CVE
assignment + stable backports, not a new incident). spark-vm
relevance: the guest-to-host memory disclosure via the host
kernel's IPv4 checksum path now has a formal CVE and stable-branch
fix versions, so spark-vm's host-kernel baseline can pin to the
fixed branch versions; the "deliberately partial" fix note keeps
the exposure posture live — the exposure window is now a tracked
patch-management fact, not just a watch item. Gate item updated:
Vercel's first-party technical write-up is still the outstanding
advancement.

## Watch-doc deltas (no new C-numbers)

**Daytona SDK V0.225.0 (dated 2026-10-16, first-party changelog read
in full).** "NVIDIA B200 GPU type" — adds the NVIDIA B200 GPU type
to the API client. The 2026-10-12 / V0.224.0, 2026-10-07 / V0.223.0,
2026-10-05 / V0.222.0, 2026-09-29 / V0.220.0, 2026-09-26 / V0.218.0
entries unchanged beneath; sequence intact. Recorded as a watch-doc
dated delta (no new C-number) per the C32/C69 version-bump
precedent. Note: the B200 type joins the previously-shipped B300
(V0.217.0) and MI355X GPU types (both observed on the first-party
changelog this pass) — Daytona's GPU-type cadence is now a watchable
pattern (V0.217.0 B300 → V0.225.0 B200), not a single event.

**Vercel changelog dated sitemap 1425 → 1430 (+5).** The new
2026-10-16 (3 entries — "Elorian AI's Glimpse now available on AI
Gateway", "Perplexity's Decider V1.2 models now available on AI
Gateway", "Reflection AI's Beam now available on AI Gateway for
free") and 2026-10-17 (1 entry — "DeepSeek V4.1 Flash 1017 now
available on AI Gateway") dated sections name 4 of the 5 — all AI
Gateway model launches, non-sandbox. The fifth post is not
identifiable in any dated section (every dated section below
2026-10-16 matches the C72 baseline record-for-record, including
the 2026-10-15 section's 12 entries); the count-field reading is
+5 while the named dated additions are 4 — recorded as observed,
not forced to reconcile. Sitemap bookkeeping, not sandbox novelty
— graded per the C71 precedent.

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  "reportedly in talks" — analyticsinsight.net funding roundup read
  this pass: "Neither round has closed, and the funding amounts
  remain undisclosed"; a Baseten-first-party close-announcement
  search returned only the $1.5B Series F (announced 2026-06-22 —
  pre-window, different round). Arm stays armed. (The Modal $750M
  arm closed at C70 — this is the Baseten arm only.)
- **C12 — OPEN (73rd consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-17;
  tracked fields verbatim; no went-live banner; first bill
  including egress still postured for November 1, 2026.
- **Vercel Drives GA — FILED (C86).** The tracked item is closed
  by the filing; no further GA re-check needed. Follow-through
  this pass: no pricing or posture changes since C86 (beta
  changelog page still carries the same iad1 rates). The sandbox
  docs Features-list "Drives" link (no "(beta)" qualifier) is
  consistent with GA; the private-beta changelog page's title
  wording ("are now in public beta") is a beta-posture page, not
  a GA contradiction — no move.
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm, Oct 13, Moderate; no 100690). File on
  first-party GHSA only. (The Hugo v0.168.0 release, dated
  2026-10-13, carries security fixes including GHSA-3ppm-p7r9-c5w3
  — release-notes coverage, not the advisories list; the
  advisories list is the graded surface.)
- **VerCellBreak (TL-2026-3425) — third-party-only.** Status ACTIVE;
  "No vendor patch available as of 2026-10-13" (threadlinqs); no
  CVE assigned; Vercel has not commented publicly. NOT a C76
  advancement (distinct mechanism, third-party only).
- **AgentCore SDK — no NEW AWS advisory** beyond 2026-127-AWS
  (Oct 6: CVE-2026-105812 / CVE-2026-106032). AWS bulletin
  2026-040-AWS (CVE-2026-11393, AgentCore CLI) is first-party
  but dated 2026-06-08 — pre-window; the reach-back policy bars
  a backfill (recorded in the flagged section for provenance).
- **Docker $250 Agent Challenge — through 2026-10-31.** No new
  development; carry. (docs.docker.com Agentic Platform release
  notes opened this pass — updated 2026-09-29, pre-window; the
  experimental public release is already in corpus.)
- **Modal VM Sandboxes GA — no progression** since the C80 fold
  (GA language already filed; follow-through color only). No
  egress-billing news ahead of the Nov 1, 2026 first bill.
- **Microsoft Execution Containers (C78) — no new movement**
  post-filing. Third-party texture only: Windows 365 support GA;
  NVIDIA OpenShell added to the integration list; enterprise
  management (Intune policy, Entra agent identity) still not
  shipped — below filing grade.
- **Hopx / Beam / Tenki — no new first-party vendor material.**
  Aggregator texture only (Hopx shows 0 monthly visits on
  Toolify). Beam appears in Boat's marketing comparison table —
  third-party marketing, not first-party material.
- **OpenAI training-agent DNS escape — pause holds.** No new
  sightings. (The AWS Bedrock Code Interpreter DNS-exfiltration
  research outcome — AWS posture "intended functionality",
  documentation clarified, VPC-mode recommended for sensitive
  workloads — is third-party-only (infosecurity-magazine,
  updated 2026-10-15), no AWS first-party bulletin; flagged, not
  filed.)
- **Perplexity SPACE Part II — still NOT sighted.** No new launch
  partners beyond Akamai/Crusoe/CoreWeave; no traction numbers
  from first-party; the OSS release (C87) is a separate
  first-party launch, not Part II.
- **Strands Box (C77) — still dev preview v0.1.0, macOS-only**
  (Apple silicon, macOS 15+); Linux support remains "planned" —
  no multi-OS follow-through.
- **Zenity AgentCorruption — no CVE assignment, no AWS bulletin;**
  vendor posture unchanged (Oct 13 statement to SC Media:
  "expected and documented behavior" stands; third-party
  coverage only).

## Flagged but not filed

- Baseten ~$26B round "close to finalizing" (techweekly, Sep 28)
  — still talks, third-party, no first-party close → below file
  bar; C11 stays armed.
- Modal $750M round "on the verge," led by Accel at ~$15.75B
  valuation (techweekly, Sep 28) — talks only, third-party; the
  closed-round C80 filing stands.
- 2026-040-AWS (first-party AWS bulletin, CVE-2026-11393 — code
  injection via triple-quote escaping in AgentCore CLI Bedrock
  agent import) — publication 2026-06-08, pre-window; the
  reach-back policy bars a backfill; recorded for provenance.
- DNS-exfiltration outcome: AWS's posture on the
  Bedrock AgentCore Code Interpreter DNS-exfiltration class —
  "intended functionality", documentation updated (Sandbox Mode
  = limited external network access, DNS resolution allowed),
  migrate-sensitive-workloads-to-VPC-mode recommendation —
  third-party only (infosecurity-magazine, updated 2026-10-15);
  no AWS first-party bulletin → flagged, not filed.
- Vercel $1M Sandbox challenge — carry (referenced in the
  PwnEscape coverage: $242,000 paid across 1,285 reports, top
  report $50,000; no first-party challenge page read this pass).
- Boat comparison-table expansion — the docs "Compared to others"
  table and homepage leaderboard now name more providers
  (Novita, exe.dev, Blaxel, Cloudflare, AWS AgentCore, Islo, Deno
  Sandbox, Fly.io Sprites, Runloop, Railway, Tensorlake, Morph,
  CodeSandbox) — marketing copy, below the tracked anchors; no
  first-party vendor material surfaced from the table.
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass; no re-folds.

## Aging

- No age-outs this pass. No re-folds. C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261017-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C76 — Vercel's
first-party technical write-up (the remaining advancement) +
stable-branch patch adoption tracking; VerCellBreak
first-party/CVE movement; SPACE open-source follow-through (repo
traction, second partner announcements); Vercel Drives GA
follow-through (usage/pricing posture changes); Perplexity SPACE
Part II (still unmet); Strands Box multi-OS follow-through; Hugo
GHSA movement on CVE-2026-100690; NanoCo re-grade (first-party
bar); AgentCore SDK — any NEW AWS advisory beyond 2026-127-AWS;
Modal egress billing post-Nov-1; Zenity AgentCorruption
CVE/bulletin; Docker Agent Challenge through 2026-10-31; Modal VM
Sandboxes progression; Hopx/Beam/Tenki first-party material;
Docker v0.48.x follow-through; Microsoft Execution Containers
enterprise-management follow-through (Intune/Entra); the Vercel
Drives beta-page title wording (private vs public beta) on the
next full A-chain re-read.
