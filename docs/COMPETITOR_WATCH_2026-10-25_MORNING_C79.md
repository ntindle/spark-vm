# Competitor watch — 2026-10-25 (morning, cycle 79)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-78 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED** (19 opens /
18 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 20th consecutive cycle — recovery declined per the
standing rule) / 0 URL-recovery opens — every anchor URL came from the
local agent_notes chain or a search result used only to locate the URL).
The two A-lane deltas: (1) Microsandbox **v0.7.10 + v0.7.11** (Full
Changelogs `v0.7.9...v0.7.10` and `v0.7.10...v0.7.11` — v0.7.11's
HTTP CONNECT proxy authentication feature #1914 extends the v0.7.9
proxy work; v0.7.10's anonymous registry auth feature #1900);
(2) Vercel changelog dated sitemap **1440 → 1448** — seven new dated
entries above the baseline top (six 2026-10-23, one 2026-10-22), all
non-sandbox by title — sitemap bookkeeping per the C71 precedent.
Surveyor B (delegated subagent, read-only): bounded delta news scan —
**0 CANDIDATES / 15 clean dedupes / 5 flagged-only** (17 searches,
all successful; 0 pages opened — no first-party grading open was
available: the Daytona first-party blog URL was not located by search).
The integrator ran three further targeted searches for the Daytona
first-party Series B post (including a daytona.io-scoped query) — no
daytona.io/blog URL surfaced, so the C89 vendor-verified advancement
stays ungraded this cycle.
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still talks-only —
PitchBook Series G dated 2026-09-22 still "Rumor/Speculation"; latest
confirmed round remains the June $13B Series F; no S-1 — accessipos:
"Baseten still hasn't filed an S-1"; metirai/bytevyte restate the talks
as "valuations under discussion, not closed rounds");
**C12 OPEN** (79th consecutive first-party AgentComputer read — still
no egress pricing line).
**Corpus move this cycle: 0 filings + 1 fold + 3 watch-doc dated
deltas; 0 age-out movements.** Last-issued C-number: C89 (unchanged).
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261025-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-25 ~09:1x–~10:0x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9), and with its fetch stats (18
> successful fetches + 1 established 404 = 19 opens; 0 URL-recovery
> opens this cycle). Surveyor B's capture enumerates exactly
> 0 candidates + 15 dedupes + 5 flagged-only, reconciling with its
> header and search stats (17 successful searches; 0 opens). The
> one A-lane fold and the three watch-doc dated deltas are the
> integration's corpus move — 0 filings + 1 fold + 3 watch-doc dated
> deltas. Corpus-number integrity: last issued C-number C89
> (cycle 76); this cycle issues none.

## Corpus moves: folds

**Microsandbox v0.7.10 + v0.7.11 — dated-delta fold into the
Microsandbox row (VENDOR-VERIFIED, first-party releases page).**
Two new releases since the cycle-78 baseline (v0.7.9 top). New top
**v0.7.11** (Full Changelog `v0.7.10...v0.7.11`): feature — HTTP
CONNECT proxy authentication (#1914); fixes — terminal sessions hang
after output (#1917), caller overrides across rebuilds (#1913),
image pruning safety (#1919), interrupted creation cleanup (#1918),
detached jobs idle (#1923), empty exec stdin no-op (#1931); refactor
— SecretValue into microsandbox-types (#1848); revert #1928; release
PR #1924. Second **v0.7.10** (Full Changelog `v0.7.9...v0.7.10`):
feature — anonymous registry auth (#1900); fixes — secret policy
modify (#1880), published msb smoltcp fork (#1906), dependency update
/ redact example output (#1907), bootstrap trampoline rootfs reclaim
(#1841), custom filesystem backends (#1899); release PR #1916.
Recorded as a watch-doc dated delta and row fold (no new C-number)
per the C32/C69 version-bump precedent. Routine maintenance — low
spark-vm relevance beyond the proxy-auth cadence datum (v0.7.11's
HTTP CONNECT proxy authentication extends the v0.7.9 proxy work,
basic auth #1868). Note: the releases page now resolves under the
`superradcompany` org path (redirect from `microsandbox/microsandbox`);
release content unchanged.

## Watch-doc deltas (no new C-numbers)

**Docker Harbor stable non-arrival — dated-delta correction to the
Docker Sandboxes row.** The cycle-78 fold recorded the Harbor
integration's stable release as expected 2026-10-23 (per the Docker
blog and trade pieces). The B lane re-checked the
docs.docker.com Sandboxes release notes
(`https://docs.docker.com/ai/sandboxes/release-notes/`) this pass:
still **v0.49.1 (2026-10-20)** as the latest stable, with no Harbor
entry and no October 23 release. Harbor remains nightly-only as far
as the release notes show. The corpus row's "stable release expected
2026-10-23" is corrected to "stable did not land by 2026-10-25;
remains nightly-only per the release notes". Re-check next cycle;
do not treat the October 23 stable arrival as landed.

**Vercel changelog dated sitemap 1440 → 1448 (+8).** Seven new dated
entries sit above the cycle-78-recorded top entry; every dated
section beneath matches the C78 baseline record-for-record:
2026-10-23 — "Vercel CLI adds Spend Management"; 2026-10-23 —
"Send feedback from the Vercel MCP"; 2026-10-23 — "Deployments now
show build cache size"; 2026-10-23 — "Vercel Connect adds managed
Stripe API keys"; 2026-10-23 — "Send feedback from the Vercel CLI";
2026-10-23 — "Kimi K3.1 Pro and Kimi K3.1 Pro Highspeed are now
available now in AI Gateway"; 2026-10-22 — "Deploy without an
account using Vercel CLI". All non-sandbox by title (CLI, MCP,
build cache, Connect, AI Gateway models). The count rose by 8 while
7 new entries sit above the baseline top — one additional entry was
inserted deeper in the list (not at the top; unlocated in this pass,
not graded as a separate delta). Sitemap bookkeeping per the C71
precedent.

**boat docs regen datum.** The `docs.boat.dev/pricing` footer stamp
now reads 2026-10-25T05:53:37.223Z (was 2026-10-23T11:52:12.259Z —
page regenerated 2026-10-25 ~00:53 CDT). Every tracked anchor
(figures, Freestyle row, plan ladder, "boat does not bill egress")
reads verbatim — substance identical; recorded as a regen datum per
the C60 precedent, not a corpus delta. `boat.dev/pricing` remains
HTTP 404 (20th consecutive cycle).

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  talks-only — PitchBook Series G dated 2026-09-22 still
  "Rumor/Speculation"; latest confirmed round remains the June
  $13B Series F; no first-party close announcement; no S-1 filing.
  Flagged-only color (metirai.com, bytevyte.com, both ~late
  September 2026): the talks restated as "valuations under
  discussion, not closed rounds" — Baseten discussing ~$26B,
  Modal discussing ~$15B; accessipos: "Baseten still hasn't filed
  an S-1". Arm stays armed.
- **C12 — OPEN (79th consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-25;
  tracked fields verbatim; first bill including egress still
  postured for November 1, 2026. No went-live banner; B-lane
  reconfirm: no posture change (third-party pricing pages
  corroborate the corpus row verbatim; charging began October 1,
  usage visible since September 1 but not charged that month).
- **Vercel Drives GA — FILED (C86).** No posture or pricing change
  on the GA surface this pass; the private-beta page is unchanged
  since the C77 corroboration fold.
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm Oct 13 Moderate). VulnCheck remains the CVE
  assigner (cve.circl.lu record, published 2026-09-26, updated
  2026-09-30); the gohugoio GHSA-x3mx-cm49-8m9c still carries no
  CVE-2026-100690 identifier (verified by opening the page in
  cycle 78; no change signal this pass). File-on-first-party-GHSA
  bar stands.
- **PwnEscape patch-adoption texture (C76).** Debian DSA-6568-1
  delivers kernel 6.12.113 (Trixie); Debian 12 Bookworm still
  vulnerable; Ubuntu kernels still "under evaluation"; AlmaLinux
  8/9/10 all ship vulnerable code; NVD scoring pending. No CISA
  KEV entry (catalog version 2026-10-16), no in-the-wild
  exploitation reported. Texture: upstream fix commit
  6785011f8b16 (net.git 2026-10-08, mainline 2026-10-14); fixed
  releases 5.10.272 / 5.15.223 / 6.1.190 / 6.6.159 / 6.12.113 /
  6.18.57 / 7.2.11. One caution in the coverage: cyberpress.org
  notes Vercel's October 14 disclosure says CVEs remain pending,
  so the CVE-2026-99999 identifier "should not yet be treated as
  independently confirmed" — the corpus's "CVSS 9.3 Critical
  stands" line is the kernel-CNA score, not a Vercel confirmation.
  Deployment-only — not a corpus move.
- **pwn.ai Part 2 — still unpublished.** A dev.to explainer
  (2026-10-18) confirms "Details from writing to execution are
  not disclosed in Part 1" — the write-primitive-to-host-control
  chain details are still held back for the follow-up. Gate item
  pending.
- **Vercel KVM zero-day technical write-up — still pending.**
  Vercel's 2026-10-14 findings report (filed 2026-10-21) still
  withholds kernel details ("Fixes are under private review and
  CVEs are pending"); third-party write-ups only (dev.to
  explainer, CSO Online, cyberpress.org). CVE-2026-99999, CVSS 9.3
  Critical, stands.

## Flagged but not filed

- **Daytona first-party Series B post — URL still unlocated (C89
  lead).** TechCrunch (2026-10-23) quotes founder Ivan Burazin
  "in a blog post announcing the new round" — a first-party
  Daytona announcement that would advance C89 THIRD-PARTY to
  VENDOR-VERIFIED if graded. Surveyor B's two targeted searches
  plus the integrator's three further searches (including a
  daytona.io-scoped query) surfaced no daytona.io/blog URL. C89
  stays THIRD-PARTY; third-party corroboration only (TechCrunch
  Oct 23, Dealroom, Pulse2, tech.eu — all match the filed
  figures; new texture: Snorkel alone has provisioned 1M+
  sandboxes; revenue run rate up 25x Jan–Sep 2026, ~50.9% avg
  monthly growth; headcount 35, up from 20 in February).
  Re-check next cycle.
- **New Hugo CVE cluster (CVE-2026-109595 / CVE-2026-109596 /
  CVE-2026-109597) — watch item, not filed.** Third-party dossier
  (valtersit.com) lists the three as published 2026-10-12,
  MEDIUM (~5.4–5.5), path traversal via ESBuild's fallback
  resolver in js.Build / js.Batch / css.Build, fix in v0.167.0.
  Conflicting fix status: the Tenable Nessus plugin (published
  2026-10-21) says "There is no known solution at this time" for
  CVE-2026-109595. Same symlink/path-confinement class as the
  tracked Hugo items, but no first-party GHSA linkage established
  this pass; below the filing bar pending first-party grading.
- **VerCellBreak (TL-2026-3425)** — still third-party-only: no
  Vercel first-party comment published; no CVE; no vendor patch
  disclosed (Threadlinqs intel record: Severity HIGH, Status
  ACTIVE, first published 2026-10-13, last reviewed 2026-10-13,
  0 CVEs referenced). Carry.
- **Zenity AgentCorruption** — no CVE, no AWS bulletin; disclosure
  third-party-only; Zenity says fully mitigated 2026-09-29; AWS
  disputes the findings demonstrate a vulnerability (The
  Register, updated 2026-10-12; NeoTeo). Consistent with the
  corpus's existing resolved carry.
- **Perplexity SPACE repo traction** — 1,149 stars / 84 forks
  (~2026-10-17) unchanged from the C78 filing; no Part II; no
  partner-pricing movement; E2B Compatibility Wrapper and
  multi-operator posture unchanged from C87; innoscout.pro
  (2026-10-23) is commentary only, no new facts. Carry.
- **Docker eMudhra CA remediation** — docs.docker.com security
  announcements (updated 2026-10-21): Docker rebuilt sandbox
  template images for all built-in kits in response to the eMudhra
  CA compromise (disclosed 2026-10-20). Remediation, not a Docker
  vulnerability — below the bar (carry).
- **Agentic-seL4** — University of Surrey leads a £3.2M
  ARIA-funded formal-verification sandbox research project
  (announced 2026-10-22). Research, not a product — below the
  bar (carry).
- **TrueFoundry $19M / Mistlabs $26M** — adjacent (agent/LLMOps
  gateway, ambient consumer agent), not sandbox vendors (carry).
- **Nightona fork note** — bex.co (2026-10-02) notes the June-2026
  community fork of Daytona's frozen AGPL release — pre-existing,
  not new (carry).
- **Strands Box** — still macOS-only (first-party docs re-read
  this pass: macOS 15+ Apple silicon "Supported"; Linux "Not
  supported yet"; Windows "Unsupported"); multi-OS expansion still
  a priority with no dates (carry).
- **MS Execution Containers** — Intune/Entra still "coming soon"
  (first-party blogs.windows.com 2026-10-07; third-party
  summaries restate the same). Microsoft lists GitHub Copilot,
  OpenAI Codex, OpenClaw, Replit, LM Studio, NVIDIA OpenShell and
  Unsloth AI as already supporting MXC; Anthropic Claude Code,
  Perplexity and Manus named as coming (carry).
- **Modal VM Sandboxes** — GA stands; the "VM sandboxes in beta"
  phrasing in one third-party roundup is stale against the
  corpus's Oct-14 first-party GA filing (carry).
- **C79** — no new AWS advisory beyond 2026-127-AWS (carry). The
  BeyondTrust AgentCore SDK pair (CVE-2026-12530 /
  CVE-2026-16796, `install_packages()` RCE, fix SDK 1.18.1) is
  already in the corpus (C66 watch doc, 2026-10-09,
  third-party-only, no AWS advisory); the infosecurity-magazine
  piece updated 2026-10-23 is a restatement of the September 28
  BeyondTrust report, not a new bulletin.
- **Vercel sitemap entries** — non-sandbox bookkeeping only
  (carry).
- **Boat homepage leaderboards** — marketing copy naming providers
  (carry).
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass.

## Aging

- No age-outs this pass. 0 filings, 1 fold. C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261025-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C89 — Daytona's
first-party Series B confirmation (Burazin blog post — URL still
unlocated after five targeted searches across two lanes) +
pricing-posture follow-through; C76 — pwn.ai's promised Part 2
(the write-primitive-to-host-control chain) + stable-branch patch
adoption tracking + Vercel first-party KVM zero-day technical
write-up (distinct doc; still pending); C88 — Kiro
credential-brokering posture vs swapd's edge; VerCellBreak
first-party/CVE movement; SPACE open-source follow-through (repo
traction, second partner announcements, partner pricing posture);
Vercel Drives GA follow-through (usage/pricing posture changes);
Perplexity SPACE Part II (still unmet); Strands Box multi-OS
follow-through; Hugo GHSA movement on CVE-2026-100690 + the new
CVE-2026-109595/96/97 cluster (first-party grading pending);
NanoCo re-grade (first-party bar); AgentCore SDK — any NEW AWS
advisory beyond 2026-127-AWS; Modal egress billing post-Nov-1
(first bill arrives November 1); Zenity AgentCorruption
CVE/bulletin; Docker Agent Challenge through 2026-10-31; Modal VM
Sandboxes progression; Hopx/Beam/Tenki first-party material;
Docker v0.49.x follow-through + Harbor stable arrival re-check;
Microsoft Execution Containers enterprise-management
follow-through; the Vercel sitemap count field (1448 baseline);
the dead `vercel.com/docs/sandbox/features` URL (use
`/docs/sandbox`); Microsandbox releases now resolve under
`superradcompany/microsandbox`.
