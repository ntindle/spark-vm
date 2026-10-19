# Competitor watch — 2026-10-19 (morning, cycle 75)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-74 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTAs, 0 UNVERIFIED** (21 opens /
20 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 16th consecutive cycle — recovery declined per the
standing rule) / 12 URL-recovery searches (discovery only, never
evidence)). A-lane deltas: Vercel changelog dated sitemap 1431 → 1432
(one new 2026-10-19 entry — "MiniMax M3.1 Flash now available on AI
Gateway for free", AI Gateway, non-sandbox; sitemap bookkeeping per the
C71 precedent) + docs.boat.dev/pricing "Compared to others" table
gained a Freestyle row (small $0.132 (7x) / default $0.264 (7x) /
large $0.529 (7x) / xlarge $1.06 (5x); boat's own figures verbatim;
footer stamp 2026-10-19T06:39:46.511Z, stamp text per the C60
precedent).
Surveyor B (delegated subagent, read-only): bounded delta news scan —
**1 CANDIDATE / 11 clean dedupes / 5 flagged-only** (12/15 searches,
all successful / 0 failed; 1 page opened and read in full,
successful). The 1 candidate is corpus-move-grade: Perplexity SPACE
partner follow-through — Akamai has now launched SPACE on its cloud,
Crusoe is adding it to its Managed AI Services, and CoreWeave has
published setup guidance for CKS — converting the Oct-15
announcement-day partner list into first deployments; folded into the
tracked SPACE capture (no new C-number).
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still talks-only —
latest closed round remains the June 22, 2026 Series F; DefiLlama
estimated $19.8B as of Oct 18; no first-party close announcement);
**C12 OPEN** (75th consecutive first-party AgentComputer read — still
no egress pricing).
**Corpus move this cycle: 1 fold + 2 bookkeeping deltas; 0 mints.**
No age-out movements. Last-issued C-number: C88.
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261019-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-19 ~09:1x–~09:5x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTAs, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9), and with its fetch stats (20
> successful fetches + 1 established 404 = 21 opens). Surveyor B's
> capture enumerates exactly 1 candidate + 11 dedupes + 5
> flagged-only, reconciling with its header and search stats (12/15
> successful searches; 1/1 successful open). The B-lane candidate is
> a re-fold of the tracked SPACE item, not a new filing — the
> integration records 1 fold + 2 bookkeeping deltas, not a mint.
> Corpus-number integrity: last issued C-number C88 (cycle 74); this
> cycle issues none.

## Corpus moves: filings + folds

**C87 fold — Perplexity SPACE partner follow-through (first
advancement since the 2026-10-15 filing).** New since the cycle-74
capture ("no new launch partners or traction numbers"): third-party
corroboration of the announcement-day partner posture — Akamai's
cloud launch confirmed outside the vendor page (already
VENDOR-VERIFIED at filing as "tested and launched"); Crusoe moves
from "partnering to add" to actively adding SPACE to its Managed AI
Services; CoreWeave's setup guidance is now specified for CKS
deployments. Net: the announcement-day partner list is
materializing into live operator offerings. Provenance:
**THIRD-PARTY** (dev.to piece read in full this pass: "Early
adopters. Akamai has launched it on its cloud, Crusoe is adding it
to Managed AI Services, and CoreWeave published setup guidance for
CKS"; published 2026-10-17T12:54:51Z). No new C-number — the
advancement is deployment follow-through, not a new release. Gate
items: repo traction on the open-source release; second-wave
partner announcements; pricing posture if/when any partner prices
the managed surface.
spark-vm relevance: a permissively-licensed, production-tested,
multi-cloud agent-sandbox runtime is increasingly reachable through
commercial clouds — the SPACE platform (Firecracker microVMs,
platform-held credentials outside the sandbox, operator-side
red-teaming) was already the closest public reference architecture
to spark-vm's own posture; live operator offerings tighten the
competitive bar on "bring-your-own runtime" options for spark-vm's
self-host / open-source positioning.

## Watch-doc deltas (no new C-numbers)

**Vercel changelog dated sitemap 1431 → 1432 (+1).** The new dated
entry (2026-10-19 — "MiniMax M3.1 Flash now available on AI Gateway
for free") sits above the cycle-74-recorded 2026-10-17/2026-10-18
entries; every dated section beneath matches the C74 baseline
record-for-record. An AI Gateway model launch — non-sandbox. Sitemap
bookkeeping per the C71 precedent. Date-render note: the two
entries the C74 pass read as both 2026-10-17 now render as
2026-10-18 / 2026-10-17 — a date re-render with no count implication
beyond the +1.

**docs.boat.dev/pricing "Compared to others" table now carries
Freestyle as a full per-tier row.** Small $0.132 (7x) / default
$0.264 (7x) / large $0.529 (7x) / xlarge $1.06 (5x). Reconciliation:
Freestyle already appeared in the corpus row's 2026-09-18
wall-clock transcription (4vCPU/8GB tier, $0.264); the C73/C74
tracked-row baseline did not carry a per-tier Freestyle row. Boat's
own figures verbatim; footer stamp now 2026-10-19T06:39:46.511Z
(stamp text, not a figure change — C60 precedent). First-party boat
material; no move graded beyond the table addition.

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  talks-only — latest closed round remains the June 22, 2026 $1.61B
  Series F at $13B; DefiLlama estimated $19.8B as of Oct 18, 2026;
  no first-party close announcement; no IPO filing. Arm stays
  armed.
- **C12 — OPEN (75th consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-19;
  tracked fields verbatim; first bill including egress still
  postured for November 1, 2026. Breadcrumb note: the egress content
  now renders on a dedicated first-party page
  (`modal.com/docs/guide/network-egress-billing`) reached via the
  billing guide's own "network egress allowance" outlink — a page
  relocation, not a content move.
- **Vercel Drives GA — FILED (C86).** Closed by the filing; no
  further GA re-check needed. Follow-through this pass: no pricing
  or posture changes since C86.
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm, Oct 13, Moderate; no 100690). File on
  first-party GHSA only.
- **VerCellBreak (TL-2026-3425) — third-party-only.** No new
  movement — still no CVE, "No vendor patch available as of
  2026-10-13"; Vercel still has not commented publicly. NOT a C76
  advancement.
- **C76 — no new advancement (coverage surge only).** A fresh wave
  of third-party coverage (Oct 19) recaps the same corpus facts;
  pwn.ai's promised Part 2 still unpublished; still not in CISA
  KEV; no confirmed in-the-wild exploitation. The remaining gate
  items stand: Vercel's first-party technical write-up (still
  pending) + pwn.ai's promised Part 2 + stable-branch patch
  adoption tracking.
- **OpenAI training-agent DNS escape — pause holds.** No new
  sightings.
- **Perplexity SPACE Part II — still unmet.** Oct-15-release
  follow-through this pass is the partner deployment fold above —
  not the tracked Part II (no Part II label anywhere).

## Flagged but not filed

- **OpenAI sandbox-escape researcher claim** — details private, no
  CVE, no vendor confirmation; watch color.
- **Escaping SPACE Part I red-team texture** — third-party
  red-team texture on the tracked SPACE platform, below the filing
  bar.
- **Modal VM-Sandboxes GA date nuance** — texture on the already
  folded C80 VM-Sandboxes GA; below the filing bar.
- Baseten "~$37B after OpenAI partnership" third-party number —
  talks-only arithmetic on an unclosed round; C11 stays armed.
- **EU cross-border regulatory sandbox** — regulatory, out of the
  sandbox-for-agents lane.
- **Vercel $1M Sandbox challenge — carry** ($242,000 paid across
  1,285 reports, top report $50,000; no first-party challenge page
  read this pass).
- **Boat homepage leaderboards — carry** (marketing copy naming
  providers, now including Freestyle alongside the previously-seen
  set; not first-party vendor material; no move graded).
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass; no re-folds beyond C87.

## Aging

- No age-outs this pass. One re-fold (C87). C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261019-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C76 — pwn.ai's promised
Part 2 (the write-primitive-to-host-control chain) + Vercel's
first-party technical write-up (still pending) + stable-branch
patch adoption tracking; VerCellBreak first-party/CVE movement;
C88 — first-party Kiro page read for vendor-verified grading +
Kiro credential-brokering posture; SPACE open-source follow-through
(repo traction, second partner announcements, partner pricing
posture); Vercel Drives GA follow-through (usage/pricing posture
changes); Perplexity SPACE Part II (still unmet); Strands Box
multi-OS follow-through; Hugo GHSA movement on CVE-2026-100690;
NanoCo re-grade (first-party bar); AgentCore SDK — any NEW AWS
advisory beyond 2026-127-AWS; Modal egress billing post-Nov-1;
Zenity AgentCorruption CVE/bulletin; Docker Agent Challenge through
2026-10-31; Modal VM Sandboxes progression; Hopx/Beam/Tenki
first-party material; Docker v0.48.x follow-through; Microsoft
Execution Containers enterprise-management follow-through; the
Vercel Drives beta-page title wording on the next full A-chain
re-read.
