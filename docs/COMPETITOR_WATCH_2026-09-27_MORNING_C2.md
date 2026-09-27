# Competitor watch — 2026-09-27 (morning, cycle 2)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the night pass (#564, merged as `00f2b3b`): (A)
fast-mover + pricing re-verification vs the ~10:55–10:59 CDT (2026-09-27)
baseline (vendor reads ~11:26–11:31 CDT 2026-09-27), (B) delta news scan
~11:10–~11:45 CDT (~35-min delta window; scan ran ~11:27–11:45 CDT; 10
search queries). Read-only, no logins, no writes. Captures:
`hidden_files/agent_notes/surveyor-a-20260927-1124.md`,
`hidden_files/agent_notes/surveyor-b-20260927-1124.md`.

Naming-hygiene note: the rotation restarts — `NIGHT` → `MORNING` (cycle
2), per the night doc's "rotates again rather than reusing or
POST_-stacking" rule. `MORNING` already names today's 05:5x pass, so this
file carries the cycle disambiguator (`_C2`); the label remains a rotation
counter, not a wall-clock claim (this pass ran ~11:26–11:45 CDT).

**Corpus aging pipeline (P63):** quiet pass = a pass with no new
information, movement, or recrawl-mention of the item; vendor
re-verification contact counts as contact, not a quiet pass. Applied this
pass: **C62 (OpenAI offline-sandbox escape) drew in-window recrawl contact
— quiet count RESETS (1/3 → 0):** Surveyor B found a 7-outlet recrawl wave
of the Sept 25 incident report with the frontier-model training pause
still in effect — recrawl contact under the corrected-lineage standard,
not a quiet pass. **C11 (Baseten/Blaxel) recrawl contact — stays reset
(0):** the beri.net "Keeps Running pledge" acquisition commentary
recrawled again in this pass's scan, no new facts. **C67 (Huawei Cloud
CodeArts Agent, Malaysia) recrawl contact** (pocketnews.com.my) — grade
unchanged FIRST-PARTY-CORROBORATED; not a quiet pass. C56 (DeepSeek
Harness CVE-2026-82533) **stays aged out:** the DeepSeek DSec
reward-hacking piece surfaced this pass is pre-window C56 context, not a
new vendor action — correctly NOT re-folded under the drafted re-fold
path (real movement only: new vendor action, launch/funding/GA/CVE, or
first-party confirmation). C12 stays OPEN (AgentComputer still no egress
line; surveyor A vendor-verified, surveyor B zero mentions). Aged-out stay
out: C66 silent; Heapjack/Overpatch pre-window recaps only; GitLab
CVE-2026-85706 zero mentions; Dextr AI zero mentions. No age-outs this
pass; no re-folds.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~11:26–11:31 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks. The all-first-try
streak extends to **11 passes**.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26
   2026 / V0.218.0** ("KVM sandbox parameter and CLI WorkOS application").
   SEP 25 V0.217.0 ("NVIDIA B300 GPU type") still second; SEP 24
   V0.216.1/V0.216.2, SEP 23 V0.216.0 unchanged.
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22** (improved sandbox moves,
   private kit images); the 2026-09-21 v3-kits entry unchanged.
3. **Microsandbox releases** (`github.com/superradcompany/microsandbox/releases`)
   — newest still **v0.7.3** (#1646); entries beneath unchanged.
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September**; no 26-Sep or 27-Sep entries in any lane.
5. **E2B pricing** (`e2b.dev/pricing`) — $150 Pro, $3,000 Enterprise
   estimator floor, per-second billing tops $0.000014/s per vCPU; tables
   intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans). Capture-gap note (not a delta): the page
   also carries comparison-table, benchmark, and worked-examples sections
   not captured in the prior baseline summary — no figures changed.
7. **TermSquad** (`termsquad.com/pricing`) — $9/$19/$29/$49 tiers
   (Starter/Builder/Power/Ultra) intact.
8. **DigitalOcean harness-runtime pricing**
   (`digitalocean.com/pricing/harness-runtime`) — CPU $0.044/vCPU-hr,
   Memory $0.0095/GB-hr, egress $0.01/GiB, snapshots $0.05/GiB-month;
   25%-of-allocated active-CPU footnote intact; snapshot-figure discrepancy
   unresolved but unmoved.
9. **AgentComputer.ai pricing** (`agentcomputer.ai/pricing`) — $0.07/CPU-hr,
   $0.04375/GB-hr, Hot $0.000683/Cold $0.000027, Enterprise custom tier
   present, still no egress line — C12 stays OPEN.

**No changes detected on any primary source (C32 precedent: nothing to fold).**
No UNVERIFIED items this pass. Drives not re-checked per the out-of-scope
P49 daily cadence (next due 2026-09-28).

## Surveyor B — delta news scan: 0 NEW / 14 clean dedupes / 4 flagged-only

10 search queries (~11:10–~11:45 CDT delta window; scan ran ~11:27–11:45
CDT); every candidate grepped against the full watch-doc series + the
corpus before classification. No new in-window in-lane launches, pricing
moves, or fundings. No new C-numbers — **C68 not opened**.

**Recrawl contact (existing item mentioned again, no new facts):** C62
(7-outlet Sept 25 incident-report recrawl wave, training pause still in
effect — quiet count resets, see aging section); C11 (beri.net Baseten/
Blaxel commentary recrawl); C67 (pocketnews.com.my recrawl, grade
unchanged).

**14 clean dedupes** (all filed, no new facts): vm2 CVE series
(CVE-2026-92937/92956/93605/100721); Docker Cloud Sandboxes launch
syndications; BAND × Docker Sandboxes integration; Modal Labs $15B raise
talks; Daytona and TermSquad recrawls; Codex Heapjack/Overpatch recrawls;
GitLab CVE-2026-85706 recrawl; C67 and C11 recrawls (counted as contact
above); Perplexity "Escaping SPACE" Firecracker egress findings recrawl.

**4 flagged-only, NOT folded, no C-number** (pre-window or out-of-lane):
1. **CVE-2026-53362 "Frag Gap"** (Linux kernel IPv6 OOB write, CVSS 7.8,
   CISA KEV) — no fresh movement this window; stays a noted corpus gap,
   not filed.
2. DeepSeek DSec reward-hacking piece — pre-window C56 context, not a
   re-fold (see aging section).
3. (two additional flagged-only items documented in the capture — both
   pre-window or out-of-lane, none in-lane.)

Stale-version rule compliant: Surveyor B ran the dedupe against the full
series + COMPETITOR_ANALYSIS.md under the canonical corpus-leg definition
— no false first-sightings.

## Verdict

**No new in-window in-lane launches this window; the
sandbox-infrastructure lane stays quiet.** Vendors: 9/9 unchanged; the
all-first-try streak reaches 11 passes. News: 0 new, 14 clean dedupes, 4
flagged-only. Corpus movement: C62 recrawl wave — quiet count reset to
0/3; C11 stays reset (0); C67 FIRST-PARTY-CORROBORATED, recrawl contact;
C12 OPEN; C56 stays aged out (no re-fold — pre-window context only);
aged-out items stay out (C66 silent; Heapjack/Overpatch pre-window recaps;
GitLab CVE-2026-85706 zero; Dextr AI zero). C68 not opened. The in-window
news cycle was almost entirely recrawl; the only hosted-agent launch in
the corpus remains C67 (Sept 27, first-party-corroborated).
