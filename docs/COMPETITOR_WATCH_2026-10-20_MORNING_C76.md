# Competitor watch — 2026-10-20 (morning, cycle 76)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-75 baseline —
**17 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 0 UNVERIFIED** (19 opens /
18 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 17th consecutive cycle — recovery declined per the
standing rule) / 12 URL-recovery searches (discovery only, never
evidence)). The A-lane delta: Vercel changelog dated sitemap 1432 →
1434 (+2) — two new 2026-10-19 entries ("Updates to Hobby and Pro
Terms of Service", "Mercury 3 now available on AI Gateway"), both
non-sandbox; sitemap bookkeeping per the C71 precedent, no new
C-number.
Surveyor B (delegated subagent, read-only): bounded delta news scan —
**1 CANDIDATE / 12 clean dedupes / 7 flagged-only** (13 searches,
all successful; 1 page opened and read in full, successful). The
candidate is corpus-move-grade: Daytona closed a **$60M Series B at a
$1B valuation** (FirstMark-led; "Daytona said Tuesday it has raised a
$60 million Series B venture capital round at a $1 billion
valuation. FirstMark led the round." — THIRD-PARTY, jbiznews
exclusive read in full this pass) — a new funding close since the
cycle-75 baseline's "no new funding" reading. Filed as a new corpus
entry (C89); the scale figures are folded into the Daytona vendor
row.
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still talks-only —
PitchBook lists the 2026-09-22 Series G as "Rumor/Speculation";
latest confirmed valuation remains $13B from the June 22, 2026
Series F; no first-party close announcement; no S-1 filing);
**C12 OPEN** (76th consecutive first-party AgentComputer read — still
no egress pricing line).
**Corpus move this cycle: 1 filing + 1 bookkeeping delta; 0 folds.**
No age-out movements. Last-issued C-number: C89.
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261020-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-20 ~09:1x–~09:2x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (17
> VERIFIED NO-CHANGE, 1 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9), and with its fetch stats (18
> successful fetches + 1 established 404 = 19 opens). Surveyor B's
> capture enumerates exactly 1 candidate + 12 dedupes + 7
> flagged-only, reconciling with its header and search stats (13
> successful searches; 1/1 successful open). The B-lane candidate is
> a new corpus filing (C89), not a re-fold — the integration
> records 1 filing + 1 bookkeeping delta; the bookkeeping delta
> was recorded as a delta, not minted.
> Corpus-number integrity: last issued C-number C88 (cycle 74); this
> cycle issues C89.

## Corpus moves: filings + folds

**C89 filing — Daytona $60M Series B at $1B valuation
(THIRD-PARTY).** "Daytona said Tuesday it has raised a $60 million
Series B venture capital round at a $1 billion valuation. FirstMark
led the round." (~$50M from existing investors; total raised ~$91M;
revenue run-rate up 25x Jan–Sep 2026; customers include Anthropic,
OpenAI, Nvidia, Cursor, Meta, and Cohere.) Provenance: jbiznews
exclusive read in full this pass — third-party with vendor
quotation; no first-party vendor announcement sighted yet, so the
vendor-verified bar is unmet and the filing is graded THIRD-PARTY.
New funding close vs the corpus's Feb-2026 $24M Series A baseline
for Daytona (the cycle-75 baseline recorded "no new launch or
funding" for Daytona/Microsandbox/E2B — superseded this pass).
Gate items: first-party confirmation (vendor blog or press release);
pricing-posture follow-through; second-half-2026 launch cadence vs
the GPU-type cadence already tracked in the Daytona vendor row.
spark-vm relevance: the closest sandbox-priced peer (the
Agent37-authored comparison prices Daytona and E2B identically at
$120.89/mo on the same workload) reaches unicorn status on 25x
nine-month revenue growth with the largest model labs as customers —
the clearest demand signal yet for task-scoped agent sandboxes as a
unicorn-scale market, and pricing/feature-velocity pressure on every
sandbox vendor including spark-vm's hosted lane.

## Watch-doc deltas (no new C-numbers)

**Vercel changelog dated sitemap 1432 → 1434 (+2).** The two new
dated entries (2026-10-19 — "Updates to Hobby and Pro Terms of
Service" and "Mercury 3 now available on AI Gateway") sit above the
cycle-75-recorded top entry; every dated section beneath matches the
C75 baseline record-for-record. A terms-of-service update plus an AI
Gateway model launch — both non-sandbox. Sitemap bookkeeping per the
C71 precedent. The ToS-adjacent entry carries no plan/terms price or
quota movement in its title; a plan-level read is below this lane's
evidence bar.

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  talks-only — PitchBook lists the 2026-09-22 Series G as
  "Rumor/Speculation"; latest confirmed round remains the June 22,
  2026 Series F ($1.61B at $13B); no first-party close announcement;
  no S-1 filing. Arm stays armed.
- **C12 — OPEN (76th consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-20;
  tracked fields verbatim; first bill including egress still
  postured for November 1, 2026. B-lane reconfirm: no posture
  change.
- **Vercel Drives GA — FILED (C86).** Closed by the filing; no
  further GA re-check needed. Follow-through this pass: no pricing
  or posture changes (usagepricing.com + qovery.com reconfirm the
  $0.05/GB-month storage / $0.0015/GB reads / $0.004/GB writes
  iad1 rates).
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm, Oct 13, Moderate; no 100690). File on
  first-party GHSA only.
- **VerCellBreak (TL-2026-3425) — third-party-only.** No new
  movement — still no CVE, no vendor patch, no first-party
  response published. NOT a C89 advancement.
- **C76 — no new advancement (no coverage surge this pass).** The
  promised pwn.ai Part 2 still unpublished; still not in CISA KEV;
  no confirmed in-the-wild exploitation; the mainline fix landed
  October 14. The remaining gate items stand: Vercel's first-party
  technical write-up (still pending) + pwn.ai's promised Part 2 +
  stable-branch patch adoption tracking.
- **OpenAI training-agent DNS escape — pause holds.** No new
  sightings.
- **Perplexity SPACE Part II — still unmet.** No Part II label
  anywhere this pass.

## Flagged but not filed

- **OpenAI sandbox-escape researcher claim** — details private, no
  CVE, no vendor confirmation; watch color (carry).
- **Escaping SPACE Part I red-team texture** — third-party summary
  of the already-first-party C54 report; texture only (carry).
- **Modal VM-Sandboxes GA date nuance** — texture on the already
  folded C80 VM-Sandboxes GA; below the filing bar (carry).
- Baseten "~$37B after OpenAI partnership" third-party number —
  talks-only arithmetic on an unclosed round; C11 stays armed
  (carry).
- **EU cross-border regulatory sandbox** — regulatory, out of the
  sandbox-for-agents lane (carry).
- **Microsoft Project Perception (Oct 19) — NEW this pass.**
  Agent-governance tooling (agent controls), no prices or dates
  sighted; out of the sandbox-provider lane; below the file bar.
- **SandboxAQ Switch Trust+ROI (Oct 19) — NEW this pass.**
  Agent-governance tooling announcement; not a sandbox-provider
  move; below the file bar.
- **Vercel $1M Sandbox challenge — carry** ($242,000 paid across
  1,285 reports, top report $50,000; no first-party challenge page
  read this pass).
- **Boat homepage leaderboards — carry** (marketing copy naming
  providers, now including Freestyle alongside the previously-seen
  set; not first-party vendor material; no move graded).
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass.

## Aging

- No age-outs this pass. One filing (C89). C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261020-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C89 — Daytona's
first-party Series B confirmation (vendor blog/press release) +
pricing-posture follow-through; C76 — pwn.ai's promised Part 2
(the write-primitive-to-host-control chain) + Vercel's first-party
technical write-up (still pending) + stable-branch patch adoption
tracking; VerCellBreak first-party/CVE movement; C88 — first-party
Kiro page read for vendor-verified grading + Kiro
credential-brokering posture; SPACE open-source follow-through
(repo traction, second partner announcements, partner pricing
posture); Vercel Drives GA follow-through (usage/pricing posture
changes); Perplexity SPACE Part II (still unmet); Strands Box
multi-OS follow-through; Hugo GHSA movement on CVE-2026-100690;
NanoCo re-grade (first-party bar); AgentCore SDK — any NEW AWS
advisory beyond 2026-127-AWS; Modal egress billing post-Nov-1;
Zenity AgentCorruption CVE/bulletin; Docker Agent Challenge through
2026-10-31; Modal VM Sandboxes progression; Hopx/Beam/Tenki
first-party material; Docker v0.48.x follow-through; Microsoft
Execution Containers enterprise-management follow-through;
Microsoft Project Perception / SandboxAQ Switch follow-ups if
prices/dates appear; the Vercel Drives beta-page title wording on
the next full A-chain re-read.
