# Competitor watch — 2026-10-18 (morning, cycle 74)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-73 baseline —
**17 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 0 UNVERIFIED** (19 opens /
18 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 15th consecutive cycle — recovery declined per the
standing rule) / 15 URL-recovery searches (discovery only, never
evidence)). A-lane delta: Vercel changelog dated sitemap 1430 → 1431
(one new 2026-10-17 entry — "AI Gateway logs now show session
affinity", AI Gateway, non-sandbox; bookkeeping delta per the C71
precedent).
Surveyor B (delegated subagent, read-only): bounded delta news scan —
**3 CANDIDATES / 12 clean dedupes / 5 flagged-only** (12 searches,
12 successful / 0 failed; 4 pages opened and read in full, 4
successful / 0 failed). One candidate re-graded in integration: the
Modal $750M Series D "candidate" is a clean dedupe — it is C80,
already filed VENDOR-VERIFIED on 2026-10-14 with the scale figures
already folded into the Modal row. Remaining corpus movement: 1 new
filing (C88 — AWS Kiro local sandboxing GA) + 1 fold (C76 third
advancement since the Vercel KVM zero-day filing: pwn.ai's full
technical write-up Part 1 published, Part 2 promised).
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still in talks —
latest closed round remains the June 2026 Series F; no first-party
close announcement); **C12 OPEN** (74th consecutive first-party
AgentComputer read — still no egress pricing).
**Corpus move this cycle: 1 mint + 1 fold; no new watch-only items.**
No age-out movements. Last-issued C-number: C88.
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261018-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-18 ~09:1x–~09:3x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (17
> VERIFIED NO-CHANGE, 1 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9), and with its fetch stats (18
> successful fetches + 1 established 404 = 19 opens). Surveyor B's
> capture enumerates exactly 3 candidates + 12 dedupes + 5
> flagged-only (20 enumerations; dedupe items 1 and 6 also carry a
> flagged texture note, so unique surveyed topics reconcile to 18),
> reconciling with its header and search stats (12/12 successful
> searches; 4/4 successful opens). The B-lane Modal candidate is
> re-graded dedupe (C80, filed 2026-10-14) — the integration records
> 1 mint + 1 fold, not 2 mints. Corpus-number integrity: last issued
> C-number C87 (cycle 73); this cycle issues C88; the C76
> advancement folds without a new C-number.

## Corpus moves: filings + folds

**C88 — AWS Kiro local sandboxing GA (announced 2026-10-14).**
Kernel-enforced command sandboxing in the Kiro IDE (1.3+) and CLI
(2.31+): Seatbelt on macOS, bubblewrap on Linux, AppContainer on
Windows. Credential paths refused at the syscall level; sandboxing
off by default. Brings to developer laptops the isolation Kiro Web
has offered in the cloud since May. Filed as a new corpus row —
distinct from C77 (Strands Box, AWS dev-preview SDK surface, macOS
only) — because Kiro is a distinct first-party GA on a distinct
product surface (IDE/CLI command sandboxing vs SDK preview).
Provenance: **THIRD-PARTY** (shashi.co write-up read in full this
pass: "On October 14, Amazon Web Services made command sandboxing
generally available in the Kiro integrated development
environment … and its command-line interface …"; quoting AWS's
first-party post "Local Sandboxing in Kiro: Keep Agent Commands
within Boundaries", dated 2026-10-14 — the first-party post itself
was not opened this pass, so the filing carries the third-party
grade). spark-vm relevance: the eighth convergent datapoint for
credential-brokering-at-the-boundary (credentials kept outside
agent-reachable code — cf. the C54 corpus rows including C87's
platform-held credentials, E2B Secrets, Modal Sidecars) — and the second
OS-level (Seatbelt/AppContainer) local-sandbox shape after C78's
Microsoft Execution Containers. Watch item: first-party page read
for vendor-verified grading + Kiro's credential-brokering posture
vs swapd's edge.

**C76 fold — pwn.ai's full technical write-up published, Part 2
promised (third advancement since the 2026-10-03 filing).** New
since the cycle-73 fold (CVE-2026-99999 assignment + stable-branch
backports): the research team has published its full technical
write-up (Part 1) and publicly promises a Part 2 covering the jump
from the write primitive to full host control (memory grooming →
64-byte kernel writes → host-root helper across 4 cold boots).
Still no evidence of in-the-wild exploitation; still not in CISA
KEV (third-party cross-checks). Provenance: third-party WebProNews
article read in full this pass ("PwnEscape Exposes Linux Kernel
Networking Flaw That Shatters VM Isolation", published
2026-10-16T10:42:13Z; "pwn.ai detailed the full research in its
technical write-up"; "pwn.ai indicated additional findings from the
Vercel challenge will appear in future posts"; backports and fixed
branch versions confirmed unchanged since cycle 73). No new
C-number — the advancement is the research going public in full,
not a new incident. The remaining gate items: Vercel's own
first-party technical write-up (still pending) + pwn.ai's promised
Part 2. spark-vm relevance: the write primitive → host-control
chain is the dated watch item — host-kernel baseline stays pinned
to the stable-branch fix versions; the deliberately-partial fix
posture (cycle-73 fold) stands.

**Dedupe re-grade (recorded, not corpus movement):** the B-lane
Modal $750M Series D "candidate" is **C80** — filed 2026-10-14
(VENDOR-VERIFIED, first-party modal.com blog read in full) with
the $300M sandbox run-rate / ~3B sandboxes / 1M concurrent / VM
Sandboxes GA-language scale figures already folded into the Modal
vendor row. The third-party badsignal.ai story read this pass
corroborates the closed round but adds no new fact.

## Watch-doc deltas (no new C-numbers)

**Vercel changelog dated sitemap 1430 → 1431 (+1).** The new
dated entry (2026-10-17 — "AI Gateway logs now show session
affinity") sits alongside the cycle-73-recorded DeepSeek V4.1
Flash 1017 entry in the same 2026-10-17 section; every dated
section beneath matches the C73 baseline record-for-record. An AI
Gateway item — non-sandbox. Sitemap bookkeeping per the C71
precedent.

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  talks-only — latest closed round remains the June 22, 2026 $1.5B
  Series F at $11–13B; no first-party close announcement; the
  third-party "close to finalizing" texture (techweekly, Sep 28)
  is talks, not a close. Arm stays armed.
- **C12 — OPEN (74th consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-18;
  tracked fields verbatim; first bill including egress still
  postured for November 1, 2026.
- **Vercel Drives GA — FILED (C86).** Closed by the filing; no
  further GA re-check needed. Follow-through this pass: no pricing
  or posture changes since C86 (two third-party pricing trackers
  corroborate the same iad1 rates).
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm, Oct 13, Moderate; no 100690). File on
  first-party GHSA only.
- **VerCellBreak (TL-2026-3425) — third-party-only.** No new
  movement — still no CVE, threadlinqs still "No vendor patch
  available as of 2026-10-13"; Vercel still has not commented
  publicly. NOT a C76 advancement.
- **OpenAI training-agent DNS escape — pause holds.** No new
  sightings. (The AWS Bedrock Code Interpreter DNS-exfiltration
  research outcome — AWS posture "intended functionality",
  documentation clarified, VPC-mode recommended for sensitive
  workloads — is third-party-only (infosecurity-magazine,
  updated 2026-10-15), no AWS first-party bulletin; flagged, not
  filed.)
- **Perplexity SPACE Part II — still unmet.** Oct 15–16 coverage
  (Forkast, tokenpost, marktechpost: 820 stars by Oct 16, E2B
  Compatibility Wrapper, 0.8.0 baseline) duplicates the corpus
  capture — no Part II.

## Flagged but not filed

- Modal $750M Series D third-party close story — already C80
  (dedupe, see the dedupe re-grade above).
- **Vercel deployment-storage billing for existing Pro teams
  (first-party changelog, dated 2026-10-09)** — $0.10/GB-month
  for Deployment + Functions Storage on all Pro teams, 30-day
  retention default, deletions starting 2026-10-23. First-party
  and new, but deployment storage, not Drives/sandbox — sandbox
  adjacency only; flagged, not filed.
- **AWS AgentCore SDK flaws (BeyondTrust research)** —
  infosecurity-magazine, updated 2026-10-16: code execution via
  `install_packages()` into attacker-influenced input + AWS
  credential reach, CVSS 7.3/3.1 and 8.4/4.0, fixed in AgentCore
  SDK 1.18.1. Separate from the Sep 29-dated BeyondTrust report,
  but third-party with no AWS first-party bulletin → flagged,
  not filed.
- **severitydaily texture on 2026-127-AWS** — upgrading
  bedrock-agentcore-starter-toolkit to 0.3.14 does not remove
  already-generated injected code; affected agents must be
  reimported. Third-party texture on an already-filed bulletin →
  flagged, not filed.
- **Vercel $1M Sandbox challenge — carry** (referenced in the
  PwnEscape coverage: $242,000 paid across 1,285 reports, top
  report $50,000; no first-party challenge page read this pass).
- **Boat comparison-table expansion — carry** (the docs
  "Compared to others" table and homepage leaderboard name
  additional providers — Novita, exe.dev, Blaxel, Cloudflare,
  AWS AgentCore, Islo, Deno Sandbox, Fly.io Sprites, Runloop,
  Railway, Tensorlake, Morph, CodeSandbox — marketing copy,
  below the tracked anchors; no first-party vendor material
  surfaced from the table).
- Baseten ~$26B "close to finalizing" texture — still talks,
  third-party; C11 stays armed.
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass; no re-folds beyond C76.

## Aging

- No age-outs this pass. One re-fold (C76). C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261018-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C76 — pwn.ai's promised
Part 2 (the write-primitive-to-host-control chain) + Vercel's
first-party technical write-up (still pending) + stable-branch
patch adoption tracking; VerCellBreak first-party/CVE movement;
C88 — first-party Kiro page read for vendor-verified grading +
Kiro credential-brokering posture; SPACE open-source follow-through
(repo traction, second partner announcements); Vercel Drives GA
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
