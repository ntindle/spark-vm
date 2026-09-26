# Competitor watch — 2026-09-26 (late evening)

Two-surveyor pass, delta-only against the evening pass (#503,
slot 1624/1654, merged as `27acc35`): (A) fast-mover + pricing
re-verification vs the ~16:24 CDT baseline (~17:25–17:30 CDT), (B) delta
news scan ~16:40–17:30 CDT. Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260926-1724.md`,
`agent_notes/surveyor-b-20260926-1724.md` (under `hidden_files/`).
Suffix `_LATE_EVENING` admitted per the 2026-09-24 suffix-admission
precedent (the `_EARLY_AFTERNOON`/`_MID_AFTERNOON`/`_LATE_AFTERNOON`/
`_EVENING` chain) — 17:3x CDT is genuinely late evening.

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

All nine vendor fetches succeeded first try — zero fetch failures, zero
UNVERIFIED grades (eighth consecutive all-first-try pass for this set).

1. **Daytona changelog** (`daytona.io/changelog`, read ~17:25 CDT) —
   newest still **SEP 26 2026 / V0.218.0** ("KVM sandbox parameter and
   CLI WorkOS application"). No V0.219.0, no 27-Sep entry.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated
   heading still **2026-09-22**.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September**; Sandbox entries: "Vercel Sandbox now supports
   memory observability" (25 Sep), "Drives for Vercel Sandbox are now
   in public beta" (23 Sep). Nothing dated 26 September in any lane.
   Drives not re-checked per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads
this pass): E2B (Hobby FREE / $100 one-time usage credit, Pro
$150/month, $0.000014/s per vCPU); boat.dev (small $0.018 / default
$0.036 / large $0.072 / xlarge $0.200 per hour, 25 free trial hours;
stopped sandbox costs nothing); TermSquad ($9/$19/$29/$49 tiers,
BYO-AI intact); DigitalOcean Managed Agents (public preview,
active-CPU footnote intact; per-second billing; $0.044/vCPU-hour,
$0.0095/GB-hour, snapshots $0.05/GiB-month); AgentComputer
($0.07 CPU-h, $0.04375 GB-h, hot $0.000683 / stopped $0.000027
storage, still no egress policy stated — C12 stands).

## Surveyor B — delta news scan: 0 new, 8 clean dedupes, 7 flagged-only

Quiet window. No in-window, in-lane launches, pricing changes, or
in-lane CVEs. Every corpus-absent candidate failed the window or lane
bar.

Clean dedupes: Cloudflare sandbox-escape disclosure = **C55**; Docker
CVE-2026-77179/79994 recrawl = filed Docker row; vm2
CVE-2026-47686 recap = already flagged-only; Docker Sandboxes press
wave = filed row; thehackerwire CVE-2026-100589 = **C66**; OpenClaw
CVE-2026-100585/100579 = already flagged-only (adjacent, kept separate
from C66); Daytona changelog V0.218.0 (no newer entry); third-party
pricing recaps (corroborate filed figures only).

Flagged-only (new to corpus but failing lane/window bars):

1. **CVE-2026-92937** (vm2 3.11.6, Promise call/apply → host error sanitize bypass, fixed 3.11.7; stackflag.com THIRD-PARTY, ~1 day old) — distinct from CVE-2026-47686 and CVE-2026-92956; adjacent JS-sandbox lane, not VM/sandbox-product lane. NOT filed.
2. **Two new OpenClaw vulncheck advisories** (MCP-config, session-reset)
   — adjacent harness lane, third-party-only; kept strictly separate
   from 100585/100579 and from **C66** (CVE-2026-100589). NOT filed.
3. **BAND×Docker Sandboxes Sep-24 integration color** — out of window.
   NOT filed.
4. **Meta Muse VM-export note** — adjacent lane + out of window.
   NOT filed.
5. **Leap0 vendor-pricing corroboration** — leap0.dev homepage carries
   rates matching the third-party list ($0.0504/vCPU-hr,
   $0.0162/GB-hr; free during public preview). The surveyor's read was
   search-cache-dated (92 days), so this pass treated it as
   corroboration only — **but this run's own in-window vendor-primary
   read (§C58 closure) supersedes it: C58 is folded to the corpus
   below.** NOT a new C-number either way.
6. **Freestyle Pro $500/mo claim** — tokencost/upstash list Freestyle
   only at usage rates ($0.04032/vCPU-hr); no $500/mo tier confirmed
   anywhere, no vendor-primary movement. **C37's "Pro fee VERIFIED
   absent" stands.** NOT filed.

## C58 closure — Leap0 pricing now vendor-primary (corpus fold)

**In-window VENDOR-PRIMARY read** of the Leap0 vendor homepage
(`https://leap0.dev/`, read live ~17:30 CDT 2026-09-26 — the vendor's
own served infrastructure, per the C29 boxd.sh precedent):

> "Free during public preview — no credit card required. The rates
> below apply when billing goes live."
>
> per vCPU — **$0.0504 / hour** ($0.00001400 / second)
> per GB — **$0.0162 / GB · hour** ($0.00000450 / GB · second)

The **"no published pricing" qualifier is RETIRED** — the vendor's own
page publishes the rates (preview-free with rates-effective-on-billing
terms), matching the third-party baponi list verbatim. **Folded into
the canonical corpus this pass** (primary-source-verification fold —
the sanctioned exception per the C32/C34 precedent): C58 field-table
row upgraded + new "Watch update — 2026-09-26 (late evening)" section
in `docs/COMPETITOR_ANALYSIS.md`.

Observation (directional only, not filed): the per-vCPU-second figure
($0.00001400/s) is exactly E2B's $0.000014/s — per-second CPU pricing
is converging across vendors at this grain.

## Verdict

**In-lane no-launch verdict dated 2026-09-25 stands — streak
continues.** No new C-numbers. The window's only movement was the C58
pricing closure (vendor-primary, in-window) — everything else was
press recrawls of already-filed items, adjacent-lane CVEs, or
third-party-only rumors graded per bar.

## Deep-scan queue

Heapjack/Overpatch + GitLab proxy escape remain queued — no new
coverage surfaced in this pass (Heapjack/Overpatch recrawls are all
Sep 15–21: generalanalysis Sep 15 disclosure, devops.com, techgig,
dev.to, grabtheaxe; researcher Oren Yomtov / Accomplish, reported to
OpenAI Aug 12, fixed in 8 days, CLI 0.149.0 / Desktop 26.818.21641
minimums, no exploitation in the wild).

Carried: C37, C55, C57, C58 (pricing now vendor-verified), C62 (no movement), C66 — all OPEN; C66 stays THIRD-PARTY; C26 CLOSED-resolved.
