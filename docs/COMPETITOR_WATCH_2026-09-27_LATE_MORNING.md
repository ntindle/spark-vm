# Competitor watch — 2026-09-27 (late-morning)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the morning pass (#547, merged as `4a6fd78c`): (A)
fast-mover + pricing re-verification vs the ~05:55 CDT (2026-09-27) baseline
(vendor reads ~06:25–06:30 CDT 2026-09-27), (B) delta news scan ~05:54–06:37
CDT (~43-min delta window; queries ran ~06:37–06:42 CDT). Read-only, no logins,
no writes. Captures: `hidden_files/agent_notes/surveyor-a-20260927-0624.md`,
`hidden_files/agent_notes/surveyor-b-20260927-0624.md`.

Naming-hygiene note: this pass continues the label rotation the 0454/0554
passes started — `EARLY_MORNING` → `MORNING` → `LATE_MORNING` (chains rotate,
not stack). If a fourth same-day morning pass lands, it rotates again (a later
morning label) rather than reusing or POST_-stacking.

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: **C66 (CVE-2026-100589,
OpenClaw browser-tool sandbox bypass) drew no in-window contact for its
third consecutive quiet pass (quiet at 0454, quiet at 0554, quiet now) —
AGED OUT with this one-notice line.** C62 (OpenAI offline-sandbox escape)
drew a recrawl this pass (Forbes Europe tag archive of the Sep-26 Bloomberg
story) — NOT a quiet pass for C62; its quiet count resets. The already-aged-out
trio: Heapjack/Overpatch drew recrawl contact this pass
(pranava0x0/vibe-coding-security GitHub advisory, ~2 days old, pre-window,
no new facts, no exploitation-in-wild change) — stays aged out; this pass is
NOT a quiet pass for it (recrawl-mention resets the quiet count). GitLab proxy
escape (CVE-2026-85706) and Dextr AI drew zero hits — stay out. Re-fold-path
gap still open: no re-fold path for an aged-out item that resurfaces with
real movement (follow-up proposal from the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~06:25–06:30 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero fetch failures (the all-first-try
streak restarted at the 0424 pass extends to **4 passes**). Every verified
figure matches the ~05:55 CDT baseline on substance. No corpus fold (C32
precedent: nothing changed on a primary source).

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26 2026 /
   V0.218.0** ("KVM sandbox parameter and CLI WorkOS application").
2. **Docker Sandboxes release notes** (`docs.docker.com/ai/sandboxes/release-notes/`)
   — newest dated heading still **2026-09-22**.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646).
4. **Vercel changelog** (`vercel.com/changelog`) — newest date header still
   **25 September**; no 26-Sep or 27-Sep entries in any lane.
   (Vercel Drives not re-checked per P49 daily cadence — next due 2026-09-28.)
5. **E2B pricing** (`e2b.dev/pricing`) — Hobby FREE + $100 one-time credit,
   Pro $150/mo, per-second billing tiers intact.
6. **boat.dev pricing** (canonical `docs.boat.dev/pricing`) — figures
   identical ($0.018/0.036/0.072/0.200 per hour; 25 free trial hours;
   $20/$100/$500/$2000 plans).
7. **TermSquad** — $9/$19/$29/$49 tiers, BYO-AI FAQ intact.
8. **DigitalOcean harness-runtime pricing** (canonical URL 200) — all figures
   + 25%-of-allocated active-CPU footnote intact; still no "Last verified"
   stamp; DO snapshot-figure discrepancy unresolved but unmoved.
9. **AgentComputer.ai pricing** — $0.07/CPU-hr, $0.04375/GB-hr, Hot
   $0.000683/Cold $0.000027, still no egress line — C12 stays OPEN.

## Surveyor B — delta news scan: 1 NEW / 7 clean dedupes / 5 flagged-only

**C67 (in-lane, THIRD-PARTY) — Huawei Cloud CodeArts Agent
commercial-availability launch in Malaysia (2026-09-27).** Single
regional-outlet source — pocketnews.com.my, "Huawei Cloud Launches Enterprise
AI Coding Tool CodeArts Agent in Malaysia" (URL carries the 2026/09/27 date;
Kuala Lumpur dateline). Corroboration pending — THIRD-PARTY grade stands.
Who/what: an enterprise AI coding platform with 16 specialised agents
(architecture, coding, testing, troubleshooting, code review), claimed
tens-of-millions-of-lines codebase handling, 30+ reusable engineering
skills; eligible enterprises get three months of free Professional Edition
under an Early Bird Programme. When: in-window (Sep 27, 2026). Why it
matters: a hyperscaler pushing an agentic coding platform to commercial
availability in a new market — first Huawei-hosted-agent entry in the
corpus; adds a regional dimension the watch doesn't track for any vendor.
Filing note: no sandbox-infrastructure angle in the reporting — this is the
hosted coding-agent surface, not execution isolation. Filed in the
C54/C55/C56/C64/C65/C66 adjacent-lane tradition.

**7 clean dedupes** (all filed, no new facts): OpenAI DevDay persistent-agent
"O" leak rumor recrawl (third-party-only, unconfirmed, out-of-window); Docker
Cloud Sandboxes Sep-24/25 launch wave recrawl (merge.news "Docker Friday,
September 25, 2026"); DigitalOcean Managed Agents third-party launch recap
(explainx.ai); Vercel Sandbox Drives design write-up (nandann.com);
Meta Muse / "Muse Secure VM" deep-dive (explainx.ai Sentinel-VM); OpenAI
offline-training-sandbox escape (C62) — Forbes Europe tag archive reprint of
the Sep-26 Bloomberg story (recrawl of the filed C62 family; this pass is not
a quiet pass for C62); Daytona $24M Series A (Feb 2026) recrawl via the
Alex Yedi Daytona field-guide doc.

**5 flagged-only, NOT folded, no C-numbers:**
1. CVE-2026-100721 — vm2 sandbox escape via custom-resolver auth bypass
   (StackFlag, surfaced ~Sep 26 evening). NEW TO CORPUS but pre-window and
   marginal lane per the established vm2 precedent (47686/92956/93603 all
   flagged-only at the Sep-26 MID_AFTERNOON pass): vm2 is a Node process-level
   sandbox library, not agent-VM infrastructure. Near-miss candidate only —
   carried if a future pass sees fresh movement.
2. AgntBox / Cornelis Networks $205M raise (Sep 27) — AI interconnect
   hardware startup; out-of-lane.
3. Nscale $3.36B convertible financing pre-US-IPO (Sep 26–27) — British AI
   neocloud; infra-neocloud story, out of lane.
4. OpenEvidence $15B healthcare-AI round (Sep 27) — out of scope.
5. orbitalab/rnd-ai-sandboxes-sec-study-part-1 — third-party Tier-1
   information-leakage study across e2b / microsandbox / arrakis / gvisor /
   daytona (~Sep 22, pre-window); no movement, no new facts; lane-adjacent
   research, not a product/funding/GA/CVE story.

Also surfaced, not counted: ComputeSDK 1.0.0 changelog (already in corpus);
Cmux provider-row retirement, ironclaw benchmark, memroos comparison, Nova
Daytona-vs-E2B doc — all third-party research/repo docs, pre-window or
undated, no news value.

Stale-version rule compliant; Surveyor B grepped the last 3 watch docs for
recrawls before classifying (the 0424 pass's process lesson) — no false
first-sightings.

## Verdict

**The in-lane no-launch verdict dated 2026-09-25 ENDS this pass.** C67 is an
in-lane hosted-agent-coding launch (commercial availability in a new regional
market) — caveated as a single third-party regional-outlet source with
corroboration pending, and as a market-expansion of an existing agent product
rather than a new platform. The sandbox-infrastructure lane itself remains
quiet this window. A new verdict baseline is set from this pass.

Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement,
recrawl contact — quiet count reset), C67 (NEW this pass, carried forward
for P63 quiet-count tracking); C26 CLOSED; C12 OPEN (AgentComputer
still no egress policy). Aged out this pass: C66 (third consecutive quiet
pass — one-notice line above). Aged out (staying out): Heapjack/Overpatch
(recrawl contact, no new facts), GitLab proxy escape (CVE-2026-85706),
Dextr AI. Re-fold-path gap still open.
