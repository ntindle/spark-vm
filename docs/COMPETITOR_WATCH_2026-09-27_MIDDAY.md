# Competitor watch — 2026-09-27 (midday)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the late-morning pass (#548, merged as `c3579a32`): (A)
fast-mover + pricing re-verification vs the ~05:55 CDT (2026-09-27) baseline
(vendor reads ~07:16–07:17 CDT 2026-09-27), (B) delta news scan ~06:37–07:16
CDT (~39-min delta window; 10 search queries). Read-only, no logins, no
writes. Captures: `hidden_files/agent_notes/surveyor-a-20260927-0654.md`,
`hidden_files/agent_notes/surveyor-b-20260927-0654.md`.

Naming-hygiene note: label rotation continues — `MORNING` → `LATE_MORNING` →
`MIDDAY` (chains rotate, not stack). A further same-day pass rotates again
rather than reusing or POST_-stacking.

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: nothing ages out — C67 drew
in-window contact (first-party corroboration below), so it is NOT a quiet
pass. C62 (OpenAI offline-sandbox escape) drew recrawl contact (coverage
wave reprints: pulseofnations, forkast, gagadget, notebookcheck — incremental
color only) — NOT a quiet pass for C62; its quiet count resets. The
already-aged-out trio: Heapjack/Overpatch drew recrawl contact — stays aged
out; this pass is NOT a quiet pass for it (recrawl-mention resets the quiet
count). GitLab proxy escape (CVE-2026-85706) drew recrawl contact (Tenable,
The Register KEV/exploitation coverage Sep 14–16, IOC repos) — aged out,
stays out; count resets. Dextr AI drew zero hits — stays out. C66 (aged out
last pass) drew zero hits — stays aged out. Re-fold-path gap still open: no
re-fold path for an aged-out item that resurfaces with real movement
(follow-up proposal from the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~07:16–07:17 CDT; every page loaded on first
attempt — 9/9 first-try, zero retries, zero bot-blocks (the all-first-try
streak restarted at the 0424 pass extends to **5 passes**). Every verified
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

## Surveyor B — delta news scan: 0 NEW / 9 clean dedupes / 5 flagged-only

**C67 — FIRST-PARTY CORROBORATION CONFIRMED (grade upgrade: THIRD-PARTY →
FIRST-PARTY-CORROBORATED).** Huawei's own press release
(https://www.huawei.com/my/news/2026/huawei-cloud-unveils-codearts-agent-for-enterprise-grade-ai-coding-in-malaysia,
"KUALA LUMPUR, 18 SEPTEMBER 2026" dateline, hand-verified this pass: HTTP
200, title and CodeArts Agent commercial-launch claims match) confirms the
CodeArts Agent commercial launch for the Malaysian market, plus two
independent regional outlets (malaysiasme.com.my, yamchatime.com).
Substance of the Sep-27 pocketnews re-report holds: 16 specialised agents,
30+ reusable engineering skills, tens-of-millions-of-lines codebase handling,
three-month complimentary Professional Edition Early Bird Programme.

**Filing correction:** the actual launch event was **September 7, 2026**
(Huawei Cloud AI Boost Day Malaysia, day one of WAIC CONNECT Malaysia 2026);
the Sep-27 pocketnews story was a delayed re-report. C67's in-lane status is
unchanged (a hyperscaler pushing agentic coding to commercial availability in
a new regional market — first Huawei-hosted-agent entry in the corpus), but
the launch itself is pre-window; the in-window event is the corroborated
news coverage confirming the commercial launch, not a fresh launch. C67 gets
in-window contact — not a quiet pass.

**9 clean dedupes** (all filed, no new facts): Docker Sep-24/25 Cloud
Sandboxes launch-wave recrawls (techstrong, merge.news, forkast, webpronews,
GlobeNewswire syndication); BAND × Docker Sandboxes integration (new
ecosystem detail, announcement dated Sep 24 — pre-window, dedupes against the
Docker family); C62 coverage-wave recrawl (pulseofnations, forkast, gagadget,
notebookcheck — incremental color only, quiet count resets); Heapjack/
Overpatch recrawl (aged-out pair; contact resets quiet count); GitLab
CVE-2026-85706 recrawl (Tenable, The Register KEV/exploitation coverage Sep
14–16, IOC repos — aged out, stays out); Daytona $24M Series A and E2B $21M
Series A recrawls; TermSquad Sep-15 launch reprints; Vercel Sandbox Drives
write-up.

**5 flagged-only, NOT folded, no C-numbers:**
1. CVE-2026-55607 — Claude Code git-worktree sandbox escape (StackFlag,
   surfaced ~Sep 26 evening, pre-window): consumer "seatbelt" sandbox,
   lane-adjacent, not agent-VM infrastructure. Near-miss candidate only.
2. CrewAI CVE batch — CVE-2026-92206 (ZDI unpatched zero-day) + 8 others,
   pre-window: agent framework, not agent-VM infra. Lane-adjacent.
3. CVE-2026-100721 — vm2 sandbox escape via custom-resolver auth bypass
   (StackFlag, pre-window): marginal-lane vm2 precedent (47686/92956/93603,
   all flagged-only) holds.
4. OpenAI Agents API public beta (Sep 10, pre-window) — no news value this
   window.
5. OpenAI DevDay persistent-agent "O" leak rumor — no contact this pass.

Also surfaced, not counted: prior flagged-only items silent this window.

Stale-version rule compliant; Surveyor B grepped the last 3 watch docs for
recrawls before classifying — no false first-sightings.

## Verdict

**No new in-window in-lane launches this window; the sandbox-infrastructure
lane stays quiet.** The C67 story is now first-party-corroborated (grade
upgrade filed above with the Sep-7 filing correction) — the in-lane
hosted-agent-coding entry stands, strengthened. Vendor lanes: 9/9 unchanged.

Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (recrawl contact —
quiet count reset), C67 (in-window corroboration contact — FIRST-PARTY-
CORROBORATED, not a quiet pass); C26 CLOSED; C12 OPEN (AgentComputer still
no egress policy). Aged out (staying out): C66 (zero hits), Heapjack/
Overpatch (recrawl contact, no new facts), GitLab proxy escape
(CVE-2026-85706, recrawl contact), Dextr AI (zero hits). Re-fold-path gap
still open.
