# Competitor watch — 2026-09-27 (late morning, cycle 2)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the morning cycle-2 pass (#567, merged as `a0fa535`):
(A) fast-mover + pricing re-verification vs the ~11:26–11:31 CDT
(2026-09-27) baseline (vendor reads ~11:58–12:02 CDT 2026-09-27), (B) delta
news scan ~11:45–~12:20 CDT (~35-min delta window; scan ran ~11:57–12:20
CDT; 10 search queries, ~30 results at snippet level). Read-only, no
logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1154.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1154.md`.

Naming-hygiene note: label rotation continues — `MORNING_C2` →
`LATE_MORNING` (cycle 2), per the rotation chains-rotate-don't-stack rule.
`LATE_MORNING` already names an earlier pass, so this file carries the
cycle disambiguator (`_C2`); the label remains a rotation counter, not a
wall-clock claim (this pass ran ~11:57–12:20 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied this
pass: **C62 (OpenAI offline-sandbox escape) recrawl contact again**
(gagadget reprint of the Sep-20 DNS-tunnel escape / Sep-25 training-pause
story; deafnews.it recrawl of the July 2026 OpenAI→HF incident) — quiet
count stays reset (0/3) under the corrected-lineage standard. **C11 (Baseten/Blaxel) recrawl
contact** (beri.net commentary + Blaxel Sapiom 2.5M-sandboxes case study)
— stays reset (0). **C67 (Huawei CodeArts Agent, Malaysia) recrawl
contact** (pocketnews.com.my Sep-27-dateline follow-up — new color only:
"16 specialised agents" + 3-month Early Bird; the Sep-7 launch event is
already first-party-corroborated) — grade unchanged
FIRST-PARTY-CORROBORATED; not a quiet pass, no new launch facts.
**C45 (Docker Cloud Sandboxes) recrawl contact** (forkast.news + merge.news
launch analyses) — filed item, contact only. **C26 recrawl contact** — C26
CLOSED; recrawl contact does not reopen. **C56 (DeepSeek Harness
CVE-2026-82533) stays aged out:** an orca-ai-incident-archive entry is
recrawl contact on the aged-out item — not a re-fold (real movement only:
new vendor action, launch/funding/GA/CVE, or first-party confirmation);
the techtimes DeepSeek DSec reward-hacking piece is pre-window C56
context, likewise NOT re-folded. C12 stays OPEN (AgentComputer still no
egress line — surveyor A vendor-verified; surveyor B zero mentions).
Aged-out stay out: C66 silent; Heapjack/Overpatch zero mentions;
GitLab CVE-2026-85706 zero; Dextr AI zero. No age-outs this pass; no
re-folds.

Deep-scan lead noted, NOT filed: surveyor B surfaced (snippet-level only)
a Pillar Security "coding agent sandbox escape" pattern — downstream tools
executing sandbox-produced files. No primary source, no primary-sourced
facts; queued as a possible future deep-scan lead, not a C-number.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~11:58–12:02 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **12 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26
   2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS
   application"). SEP 25 V0.217.0 ("NVIDIA B300 GPU type") still second;
   SEP 24 V0.216.1/V0.216.2, SEP 23 V0.216.0 unchanged. No 27-Sep entry.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22** (improved sandbox moves,
   private kit images); the 2026-09-21 v3-kits entry unchanged.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (#1646); entries beneath unchanged.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September** (VCR GitHub Action login, Pixel Canary on AI Gateway,
   sandbox memory observability); no 26-Sep or 27-Sep entries in any lane.
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro **$150/mo**, Enterprise CUSTOM; per-second table tops **$0.000014/s**
   per vCPU; $3,000/mo Enterprise estimator floor intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans). Capture-gap note (not a delta): the page
   still carries the comparison-table, benchmark, and worked-examples
   sections — marketing content, no rate change.
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers
   (Starter/Builder/Power/Ultra) intact; BYO-AI stance intact ("AI
   subscriptions and usage are not included").
8. **DigitalOcean harness-runtime pricing** (`digitalocean.com/pricing/harness-runtime`)
   — "Last verified 22 Sep 2026" stamp intact; CPU $0.044/vCPU-hr, memory
   $0.0095/GB-hr, session storage $0.05/GiB-month, egress $0.01/GiB,
   snapshots/checkpoints $0.05/GiB-month, BYOT $0.05/GiB-month;
   25%-of-allocated active-CPU footnote intact.
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr, Hot $0.000683/Cold $0.000027 per GB-hr, Enterprise
   custom tier present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / 12 recrawl contacts + 5 clean-dedupe groups / 11 flagged-only

10 search queries (~11:45–~12:20 CDT delta window; scan ran ~11:57–12:20
CDT; ~30 results at snippet level); every candidate grepped against the
full watch-doc series + the corpus before classification. No new
in-window in-lane launches, pricing moves, or fundings. No new C-numbers —
**C68 not opened**.

**Recrawl contact (existing item mentioned again, no new facts):** C62
(gagadget reprint; deafnews.it HF-incident recrawl); C11
(beri.net commentary + Blaxel Sapiom case study); C67
(pocketnews.com.my Sep-27-dateline follow-up + malaysiasme.com.my and
huawei.com press-release reprints — color only, grade unchanged); C45
(forkast.news + merge.news launch analyses); C26 (subagentic.ai + DO
investor release + DO docs reprint — closed item, contact only).

**Clean-dedupe groups (all filed, no new facts):** C35-era Docker
Sandboxes CVE five-pack (dev.to analysis, incl. Sep-15 pair
CVE-2026-77179 / CVE-2026-79994); Vercel Sandbox Drives (nandann.com
analysis of the filed Sep-23 public beta); Modal $15B-raise talks reprints
(techflier + bytevyte — Modal row, not C61); ~6 hits on spark-vm's own Sep
22–23 watch docs; Docker release-notes page crawled ~1h ago tops out at
2026-09-22 (corroborates the vendor no-change baseline).

**11 flagged-only, NOT folded, no C-number** (pre-window, out-of-lane, or
no fresh movement): techtimes DeepSeek DSec reward-hacking piece (2 days —
pre-window C56 context, as expected); orca-ai-incident-archive
CVE-2026-82533 entry (C56 recrawl contact, stays aged out); dev.to "Lessons
from the Codex Sandbox Escapes" (6 days — pre-window); nitiweb Modal "$2.5B
talks" piece (stale February-era URL, ignored); DCD Modal $355M Series C
(May round — pre-window facts); cyberpress/cybersecuritynews Docker
Sandboxes CVE writeups (10 days — pre-window); Medium Jannis Docker
Sandboxes 0.43 overflow-provider feature (11 days — pre-window);
CVE-2026-53362 "Frag Gap" (secnews.gr, 30 days — noted corpus gap, no
fresh movement); techinasia CodeArts HarmonyOS coding-model upgrade
(5 days — pre-window, adjacent lane); cryptobriefing OpenAI "Managed
Agents" DevDay rumor (16+ days — still rumor, DevDay is Sep 29); dev.to
sandbox comparison op-ed (16h, syndicated — opinion, no vendor news).

Stale-version rule compliant: Surveyor B ran the dedupe against the full
series + COMPETITOR_ANALYSIS.md under the canonical corpus-leg definition
— no false first-sightings.

## Verdict

**No new in-window in-lane launches this window; the
sandbox-infrastructure lane stays quiet.** Vendors: 9/9 unchanged; the
all-first-try streak reaches 12 passes. News: 0 new, 12 recrawl contacts,
5 clean-dedupe groups, 11 flagged-only. Corpus movement: C62 recrawl wave —
quiet count stays reset at 0/3; C11 stays reset (0); C67
FIRST-PARTY-CORROBORATED, recrawl contact (color only); C26/C45 recrawl
contact (no movement; C26 closed); C12 OPEN; C56 stays aged out (no re-fold
— recrawl of an aged-out item and pre-window DSec context only); aged-out
items stay out (C66 silent, Heapjack/Overpatch zero mentions, GitLab
CVE-2026-85706 zero, Dextr AI zero). C68 not opened. The in-window news
cycle was entirely recrawl; the only hosted-agent launch in the corpus
remains C67 (Sept 27, first-party-corroborated).
