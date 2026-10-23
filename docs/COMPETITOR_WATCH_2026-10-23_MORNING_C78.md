# Competitor watch — 2026-10-23 (morning, cycle 78)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-77 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED** (19 opens /
18 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 19th consecutive cycle — recovery declined per the
standing rule) / 1 URL-recovery open (`vercel.com/docs/sandbox/features`
now 404s — content recovered in full on `vercel.com/docs/sandbox`,
identical tracked anchors; anchor list updated for the next cycle)).
The two A-lane deltas: (1) Microsandbox **v0.7.9** (Full Changelog
`v0.7.8...v0.7.9` — 7 features, 24 fixes, kernel firmware to Linux
6.12.113, release bump PR #1829); (2) Vercel changelog dated sitemap
**1437 → 1440** — three new dated entries ("Eight more TLDs now
eligible for a free domain with Pro" 2026-10-22, "Routing Middleware
now supports Python" 2026-10-21, "Baseten's Mammoth-1 and Elephant-1
now available on AI Gateway for free" 2026-10-21), all non-sandbox by
title — sitemap bookkeeping per the C71 precedent (the Baseten
Mammoth-1 / Elephant-1 AI Gateway entry is a model-listing, not
financing news — no C11 movement). Surveyor B (delegated subagent,
read-only): bounded delta news scan — **1 CANDIDATE / 11 clean dedupes
/ 8 flagged-only** (15 searches, all successful; 1 page opened and read
in full, successful — first-party gohugoio GHSA, for grading evidence).
The candidate is corpus-move-grade: **Docker Sandboxes as the eval
backend for the Harbor AI-agent evaluation framework** (THIRD-PARTY —
imasters.com 2026-10-22, zot.news corroboration) — folded as a dated
delta into the Docker Sandboxes corpus row per the C52
integration-pattern precedent. The integrator read the B-lane's
handed-off first-party Kiro page in full this pass
(`kiro.dev/blog/local-sandboxing/`, dated 2026-10-14,
VENDOR-VERIFIED) — folded as the **C88 vendor-verified advancement**
(the C88 THIRD-PARTY grading now upgrades to vendor-verified).
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still talks-only —
PitchBook Series G dated 2026-09-22 still "Rumor/Speculation"; latest
confirmed round remains the June $13B Series F; no S-1; the Bloomberg
2026-10-22 $1.5B two-tranche detail reads as June-round tranche
structure, not a new close);
**C12 OPEN** (78th consecutive first-party AgentComputer read — still
no egress pricing line).
**Corpus move this cycle: 0 filings + 3 folds + 3 watch-doc dated
deltas; 0 age-out movements.** Last-issued C-number: C89 (unchanged).
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261023-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-23 ~09:1x–~09:5x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9), and with its fetch stats (18
> successful fetches + 1 established 404 = 19 opens; the 4b anchor
> migration accounts for the one URL-recovery open, which is one of
> the 18 successful fetches). Surveyor B's capture enumerates exactly
> 1 candidate + 11 dedupes + 8 flagged-only, reconciling with its
> header and search stats (15 successful searches; 1/1 successful
> open). The B-lane candidate and the two A-lane deltas are folds /
> dated deltas — the integration records 0 filings + 3 folds + 3
> watch-doc dated deltas. Corpus-number integrity: last issued
> C-number C89 (cycle 76); this cycle issues none.

## Corpus moves: folds

**C88 vendor-verified advancement — integrator reads the first-party
Kiro local-sandboxing post in full (VENDOR-VERIFIED, kiro.dev,
dated 2026-10-14).** New vendor-published facts beyond the
THIRD-PARTY shashi.co filing: (1) **GA status confirmed** —
"generally available now in Kiro IDE and Kiro CLI" (version floors:
Kiro IDE 1.3+, Kiro CLI 2.31+ on local V3 sessions; Windows needs a
one-time administrator setup); (2) **the agent itself stays outside
the sandbox** — only the commands it runs are restricted, so
sandboxing toggles mid-session without a restart; the machine
identity and model/backend credentials never enter the sandbox, so a
rogue sandboxed process cannot call out on the user's behalf; (3)
**network forced through a local domain-filtering proxy** (the same
model the Kiro cloud sandbox uses) — approved services such as
package registries reachable, other destinations blocked; (4)
**"one trust policy, enforced twice"** — `permissions.yaml` rules
(`fs_read`, `fs_write`, network capabilities) apply both at the
tool-call boundary and at the OS syscall layer, so a shell one-liner
or a script the agent writes to do the reading gets the same denial
as the `read_file` tool call (the post's worked example: a conftest
loading `~/.aws/credentials` gets `PermissionError: [Errno 13]`).
Sandboxing is off by default; enablement is a `sandbox.json`
(workspace/global) or `/sandbox on` in the CLI. No new C-number —
the advancement is the vendor's own disclosure, upgrading the filed
C88 from THIRD-PARTY to VENDOR-VERIFIED. spark-vm relevance: the
eighth convergent datapoint for credential-brokering-at-the-boundary
(credentials kept outside agent-reachable code — cf. C54 rows, E2B
Secrets, Modal Sidecars), and the strongest first-party statement
yet of the placeholder/proxy posture spark-vm's own swapd
implements (secrets never enter the agent's execution boundary —
Kiro's "the same denial whether it arrives through `read_file`, a
shell one-liner or a script" is the consumer-facing version of the
same design rule).

**Docker Sandboxes × Harbor agent-eval integration — dated-delta fold
into the Docker Sandboxes row (THIRD-PARTY).** Third-party coverage
(imasters.com, 2026-10-22; zot.news corroboration) of Docker's
integration of Docker Sandboxes as an eval backend for the **Harbor**
AI-agent evaluation framework: runs in the `sbx` nightly (pinned
`0.24.1.dev202610150414`), stable release expected **October 23,
2026**; Docker Cloud Sandboxes support Docker Compose in a single
microVM; tested up to 64 concurrent tasks; configurable network
policies (dependencies pulled during setup, then internet restricted
during the run); Harbor joins Daytona, Modal, E2B, Runloop as
sandbox backends. The Sep-era "Harbor" corpus mentions are Harbor's
own product, not this integration — new evidence, no new C-number
(folded per the C52 ecosystem-integration precedent). spark-vm
relevance: eval-harness backends are a standing corpus pattern
(GitHub Agentic Workflows, NanoClaw) — another major framework
picking a microVM sandbox backend corroborates the "sandbox as eval
substrate" demand thesis; the hosted lane's eval story should
assume sandbox-backed eval harnesses as the default consumer
shape.

**Microsandbox v0.7.9 — dated-delta fold into the Microsandbox row
(VENDOR-VERIFIED, first-party releases page).** Release
`v0.7.9` (Full Changelog `v0.7.8...v0.7.9`): features — published-
port modify (#1789), retained sandbox exit outcomes (#1812), JSON
policy denials by default (#1825), output backpressure (#1832), live
label modifications (#1881), config backend restrict (#1898), HTTP
CONNECT proxy basic auth (#1868); 24 fixes; kernel firmware to
Linux 6.12.113 (#1876); release bump PR #1829. Recorded as a
watch-doc dated delta and row fold (no new C-number) per the
C32/C69 version-bump precedent. Routine maintenance — low
spark-vm relevance beyond the kernel-firmware cadence datum.

## Watch-doc deltas (no new C-numbers)

**Vercel changelog dated sitemap 1437 → 1440 (+3).** The three new
dated entries sit above the cycle-77-recorded top entry; every
dated section beneath matches the C77 baseline
record-for-record: 2026-10-22 — "Eight more TLDs now eligible for a
free domain with Pro"; 2026-10-21 — "Routing Middleware now supports
Python"; 2026-10-21 — "Baseten's Mammoth-1 and Elephant-1 now
available on AI Gateway for free". All non-sandbox by title (TLD
domains, middleware, AI Gateway models). Sitemap bookkeeping per the
C71 precedent. Note: the Baseten Mammoth-1 / Elephant-1 entry is a
model-listing on AI Gateway — adjacent to the C11 Baseten arm in
name only; no financing signal.

**Vercel docs anchor migration.** The watched anchor
`vercel.com/docs/sandbox/features` now returns HTTP 404; the
Features section has moved into `vercel.com/docs/sandbox` (opened
in full this pass). Tracked anchors verbatim on the recovered page:
front matter `last_updated: 2026-09-22`; Features-list description
"Attach persistent filesystem storage to sandboxes and reuse data
across sandbox runs"; the dedicated `[Drives]` link (to
`/docs/sandbox/concepts/drives`) with no "(beta)" qualifier. The
next cycle's A-chain anchor list uses `/docs/sandbox`. No
substance change — not a corpus delta.

**boat docs regen datum.** The `docs.boat.dev/pricing` footer stamp
now reads 2026-10-23T11:52:12.259Z (was 2026-10-19T06:39:46.511Z —
page regenerated 2026-10-23 ~06:52 CDT). Every tracked anchor
(figures, Freestyle row, plan ladder, "boat does not bill egress")
reads verbatim — substance identical; recorded as a regen datum per
the C60 precedent, not a corpus delta. `boat.dev/pricing` remains
HTTP 404 (19th consecutive cycle).

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  talks-only — PitchBook Series G dated 2026-09-22 still
  "Rumor/Speculation"; latest confirmed round remains the June
  $13B Series F; no first-party close announcement; no S-1 filing.
  Flagged-only color (Bloomberg 2026-10-22): $1.5B closed in two
  tranches at $11B then $13B valuations (Altimeter / Conviction /
  Spark, revenue up 20x) — tranche-structure detail on the June
  round, not a new close; arm stays armed.
- **C12 — OPEN (78th consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-23;
  tracked fields verbatim; first bill including egress still
  postured for November 1, 2026. No went-live banner; B-lane
  reconfirm: no posture change (third-party pricing pages
  corroborate the corpus row verbatim).
- **Vercel Drives GA — FILED (C86).** No posture or pricing change
  on the GA surface this pass; the private-beta page is unchanged
  since the C77 corroboration fold.
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm Oct 13 Moderate). The B lane opened the
  first-party advisory page `GHSA-x3mx-cm49-8m9c` in full today:
  the advisory (symlink/Node.js-permission-model arbitrary file
  read, fixed in v0.166.0) carries **no CVE-2026-100690
  identifier**; VulnCheck's CVE record cites the GHSA as a vendor
  advisory, but linkage remains third-party-only. File-on-first-
  party-GHSA bar stands.
- **PwnEscape patch-adoption texture (C76).** Debian DSA-6568-1
  delivers kernel 6.12.113 (Trixie); Debian 12 Bookworm still
  vulnerable; Ubuntu kernels still "under evaluation"; AlmaLinux
  8/9/10 all ship vulnerable code; NVD scoring pending. No CISA
  KEV entry, no in-the-wild exploitation reported. Deployment-only
  — not a corpus move.
- **pwn.ai Part 2 — still unpublished.** Multiple third-party
  pieces confirm the write-primitive-to-host-control chain details
  are "being held back for a follow-up write-up". Gate item
  pending.
- **Vercel KVM zero-day technical write-up — still pending.**
  Vercel's 2026-10-14 findings report (filed 2026-10-21) still
  withholds kernel details ("Fixes are under private review and
  CVEs are pending"); third-party write-ups only (dev.to
  explainer, CSO Online). CVE-2026-99999, CVSS 9.3 Critical,
  stands.

## Flagged but not filed

- **VerCellBreak (TL-2026-3425)** — still third-party-only: no
  Vercel first-party comment published; no CVE; no vendor patch
  disclosed (carry).
- **Zenity AgentCorruption** — no CVE, no AWS bulletin; disclosure
  third-party-only; Zenity says fully mitigated 2026-10-09; AWS
  disputes the findings demonstrate a vulnerability (carry).
- **Perplexity SPACE repo traction** — 820 → 1,149 stars / 84
  forks (third-party counts); no Part II; no partner-pricing
  movement; E2B Compatibility Wrapper and multi-operator posture
  unchanged from C87 (carry).
- **Docker eMudhra CA remediation** — docs.docker.com security
  announcements (updated 2026-10-21): Docker rebuilt sandbox
  template images for all built-in kits in response to the eMudhra
  CA compromise (disclosed 2026-10-20). Remediation, not a Docker
  vulnerability — below the bar (carry).
- **Agentic-seL4** — University of Surrey leads a £3.2M
  ARIA-funded formal-verification sandbox research project
  (announced 2026-10-22). Research, not a product — below the
  bar.
- **TrueFoundry $19M / Mistlabs $26M** — adjacent (agent/LLMOps
  gateway, ambient consumer agent), not sandbox vendors (carry).
- **Strands Box** — still macOS-only (first-party docs:
  macOS 15+ Apple silicon "Supported"; Linux "Not supported
  yet"; Windows "Unsupported"); multi-OS expansion still a
  priority with no dates (carry).
- **MS Execution Containers** — Intune/Entra still "coming soon"
  (carry).
- **Modal VM Sandboxes** — GA stands; the "VM sandboxes in beta"
  phrasing in one third-party roundup is stale against the
  corpus's Oct-14 first-party GA filing (carry).
- **C79** — no new AWS advisory beyond 2026-127-AWS (carry).
- **Vercel TLD / Routing Middleware Python / Baseten Mammoth-1+
  Elephant-1 entries** — non-sandbox sitemap bookkeeping only
  (carry).
- **Boat homepage leaderboards** — marketing copy naming providers
  (carry).
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass.

## Aging

- No age-outs this pass. 0 filings, 3 folds. C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261023-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C89 — Daytona's
first-party Series B confirmation (vendor blog/press release) +
pricing-posture follow-through; C76 — pwn.ai's promised Part 2
(the write-primitive-to-host-control chain) + stable-branch patch
adoption tracking + Vercel first-party KVM zero-day technical
write-up (distinct doc; still pending); C88 — Kiro
credential-brokering posture vs swapd's edge; VerCellBreak
first-party/CVE movement; SPACE open-source follow-through (repo
traction, second partner announcements, partner pricing posture);
Vercel Drives GA follow-through (usage/pricing posture changes);
Perplexity SPACE Part II (still unmet); Strands Box multi-OS
follow-through; Hugo GHSA movement on CVE-2026-100690; NanoCo
re-grade (first-party bar); AgentCore SDK — any NEW AWS advisory
beyond 2026-127-AWS; Modal egress billing post-Nov-1 (first bill
arrives November 1); Zenity AgentCorruption CVE/bulletin; Docker
Agent Challenge through 2026-10-31; Modal VM Sandboxes
progression; Hopx/Beam/Tenki first-party material; Docker v0.49.x
follow-through; Microsoft Execution Containers
enterprise-management follow-through; the Vercel sitemap count
field (1440 baseline); the dead `vercel.com/docs/sandbox/features`
URL (use `/docs/sandbox`).
