# Competitor watch — 2026-09-26 (late afternoon)

Two-surveyor pass, delta-only against the mid-afternoon pass (#498,
slot 1424, merged as `95cc7f3`): (A) fast-mover re-verification vs the
~14:35 CDT baseline (~15:26–15:29 CDT), (B) delta news scan
~14:40–15:40 CDT. Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260926-1524.md`,
`agent_notes/surveyor-b-20260926-1524.md` (under `hidden_files/`).
Suffix `_LATE_AFTERNOON` admitted per the 2026-09-24 suffix-admission
precedent (the `_EARLY_AFTERNOON`/`_MID_AFTERNOON` chain) — 15:3x CDT
is genuinely late afternoon.

## Surveyor A — fast movers: 4/4 VENDOR-VERIFIED NO-CHANGE

All four vendor fetches succeeded first try — zero fetch failures, zero
UNVERIFIED grades (sixth all-first-try pass in a row).

1. **Daytona changelog** (`daytona.io/changelog`, read ~15:27 CDT) —
   newest still **SEP 26 2026 / V0.218.0** "KVM sandbox parameter and
   CLI WorkOS application" (verbatim body: "Daytona 0.218.0 adds a kvm
   parameter to sandbox creation in every SDK and moves CLI login to a
   dedicated WorkOS application"). Chain consistent below: V0.217.0
   (SEP 25), V0.216.1 / V0.216.2 (SEP 24), V0.216.0 (SEP 23); no
   V0.219.0, no 27-Sep entry.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated
   heading still **2026-09-22** ("Improved sandbox moves and support for
   private kit images in cloud sandboxes"). Desktop release notes
   separately read — newest dated entry 2026-09-21 (containerd v2.3.5,
   Docker Agent v1.140.0, Buildx v0.37.1), so the baseline's 2026-09-22
   is the Sandboxes page.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646,
   "chore: release v0.7.3" by @toksdotdev); no v0.7.4+.
4. **Vercel changelog (Sandbox lane)** — newest date header still **25
   September**; Sandbox entries: "Vercel Sandbox now supports memory
   observability" (25 Sep), "Drives for Vercel Sandbox are now in public
   beta" (23 Sep). Nothing dated 26 September. Drives not re-checked
   per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads
this pass, a step up from prior third-party spot-checks): E2B (Hobby
FREE / $100 one-time usage credit, Pro $150/month, $0.000014/s per
vCPU); boat.dev (small $0.018 / default $0.036 / large $0.072 / xlarge
$0.200 per hour, 25 free trial hours; stopped sandbox costs nothing);
TermSquad ($9/$19/$29/$49 tiers, BYO-AI intact); DigitalOcean Managed
Agents (public preview, active-CPU footnote intact; droplets
$4.00/$6.00/$12.00/$24.00 tiers intact); AgentComputer ($0.07 CPU-h,
$0.04375 GB-h, hot $0.000683 / stopped $0.000027 storage, still no
egress policy stated).

## Surveyor B — delta news scan: 0 new, 7 clean dedupes, 9 flagged-only

Quiet window. No in-window, in-lane launches, pricing changes, or
in-lane CVEs. Five targeted searches; every corpus-absent candidate
failed the window or lane bar.

Clean dedupes, seed by seed:

1. TechTimes 2026-09-25 DeepSeek DSec/"escape catalog" + CVE-2026-82533
   recrawl → **C56** — no new facts (VENDOR-VERIFIED).
2. thecybersecguru Docker Sandboxes CVE-2026-77179/79994 recrawl →
   **filed Docker row** — no new facts.
3. aratech.ae "Docker Sandboxes Escape: Agent Isolation Under Attack"
   (Sep 15 vintage) → **filed Docker row** — no new facts.
4. OpenAI "offline sandbox" DNS-tunnel escape press wave, all ~20h old
   (startupfortune, techbooky, jbiznews, neoteo, the-decoder, panews
   citing Bloomberg) — same Sep 20 incident + Sep 25 OpenAI incident
   report → **C62** (no new primary-source facts).
5. secnews.gr "OpenClaw Critical Gap in Google Meet Allows RCE"
   (2026-09-26 07:11) — THIRD-PARTY description of the same
   CVE-2026-100589 (fix 2026.7.1), no new facts → **C66**.
6. thehackerwire CVE-2026-100589 page (timeline "Sep 26 03:17 New CVE
   Received") — same CVE → **C66**.
7. GitHub datopian/wayintoai moc-ai-security-incidents.md — notes
   collage covering filed items (HF breach, DSEWiki, Alibaba
   crypto-mining) → no new facts, filed context.

Flagged-only (new to corpus but failing lane/window bars):

1. **vm2 CVE-2026-47686 exploit-analysis README** (1dayexploit
   1day-archive, updated ~1 day ago) — third-party-only recap of an
   already-flagged-only item; no new primary facts. NOT filed.
2. **pranava0x0/vibe-coding-security Heapjack+Overpatch advisory**
   (updated 2 days ago) — third-party-only recap of the Sep-15
   Accomplish disclosure; no new facts, no CVE. NOT filed.
3. **tokencost.app "OpenAI Agents API Pricing: The Sandbox Is the
   Fee"** (13 days old) — out of window. NOT filed.
4. **Jenkins CVE-2026-92122–92141 cluster write-up** (undercodenews, 9
   days old) — out of window / out of lane (CI-plugin Groovy sandbox).
   NOT filed.
5. **GitLab allowlisted-proxy escape** — no in-window coverage
   surfaced; stays on the deep-scan queue. NOT filed.
6. **CCB Belgium CVE-2026-25253** (Moltbot 1-click RCE, 236 days old) —
   out of window. NOT filed.
7. **bitdoze OpenClaw security guide** (2 days old) — third-party-only
   compilation; no new primary facts. NOT filed.
8. **OWASP AISVS workload-sandboxing validation chapter** (3 days
   old) — third-party-only research doc; no in-lane product event. NOT
   filed.
9. **tech-insider.org Agents API tutorial** (20h old) — third-party-only
   recitation of known OpenAI rates; no new facts. NOT filed.

Carried: C37, C57, C58, C66 (all OPEN, no movement; C57/C58/C66 not
re-surveyed this pass); C66 stays THIRD-PARTY (no vendor-primary
evidence surfaced). C26 stays CLOSED-resolved (watch color only).

## Verdict

**In-lane no-launch verdict dated 2026-09-25 stands — streak
continues.** No new C-numbers. The window's only lane-adjacent
movement was press recrawls of already-filed items (C56, C62/C66,
Docker row) and third-party recaps of stale disclosures.

## Deep-scan queue

Heapjack/Overpatch + GitLab proxy escape remain queued — no new
coverage surfaced in this pass's five searches (the Heapjack advisory
recap adds no new facts, no CVE).

Carried flagged-only (not queue members): Jenkins Script Security
CVE-2026-92122 cluster (Sep 17, no new coverage); tokencost.app
Agents-API pricing piece (13 days old).
