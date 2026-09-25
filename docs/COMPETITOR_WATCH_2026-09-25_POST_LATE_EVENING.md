# Competitor watch — 2026-09-25 (post late-evening)

Delta-only update against the 2026-09-25 late-evening pass
(`docs/COMPETITOR_WATCH_2026-09-25_LATE_EVENING.md`). Survey window
**2026-09-25 ~16:24–17:05 CDT** — the 15:54 slot's run authored this pass
then died before bookkeeping (its original surveyor captures were lost),
so the adopting run re-read the full tracked set + C44 live in that
window per P43 (captures named below); two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check; (B) an open-web in-lane
news scan dated 2026-09-25 + the C54/C56/C52 carried asks. Vercel
Drives NOT re-checked this pass (P49 once-daily morning cadence —
next the 2026-09-26 morning pass). Surveyor captures live in the
loop's `agent_notes/` workspace (`surveyor-a-20260925-1654.md`,
`surveyor-b-20260925-1654.md`), not the repo. `_POST_LATE_EVENING`
is collision-free on origin/main's watch-doc list for this date
(`_POST_MID_EVENING` precedent family on 2026-09-23/24).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **snippet-level** = seen only
via search snippet. **UNVERIFIED** = a public page exists but could
not be fetched this run (never reported as NO-CHANGE). **VERIFIED
absent** = the vendor's own page was read this run and the item is
confirmed not present on it.

## 1. The tracked set — 9/9 VERIFIED NO-CHANGE (DO pricing subpage UNVERIFIED→resolved)

Zero pricing/feature deltas on any vendor page read this run. **Zero
fetch failures** — all 9 tracked reads + 1 heading check returned
clean page text.

- **Daytona — VERIFIED NO-CHANGE** (changelog:
  https://www.daytona.io/changelog; pricing:
  https://www.daytona.io/pricing). Newest changelog entries still the
  SEP 24 2026 pair (V0.216.1 "API key organization ID and CLI update
  warning fix"; V0.216.2 "CLI login through WorkOS"); no September 25
  entry — **VERIFIED absent**. Pricing watched lines verbatim,
  unchanged (compute $0.0504/h per vCPU, memory $0.0162/h per GiB,
  storage $0.000108/h per GiB; GPU preemptible ladder; Windows
  $0.0858/vCPU/h; "$200 in free compute included"; "All billing is
  calculated per second.").
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/, full-page
  read). Newest dated heading still `*2026-09-22*` ("Improved
  sandbox moves and support for private kit images in cloud
  sandboxes"); next heading `*2026-09-21*` (v3 kits). No newer
  heading. Note: the September 22, 2026 Gemini heading renders a bare
  "Feature" marker with no title in this fetch — pre-existing page
  quirk, not a change; the check is newest-heading date only.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby FREE
  + "$100 one-time usage credit"; Pro $150/month; Enterprise CUSTOM;
  per-second ladder 1 vCPU = $0.000014/s through 8 vCPU =
  $0.000112/s; "1B+ sandboxes started" — all watched lines verbatim.
- **boat.dev — VERIFIED NO-CHANGE** (https://docs.boat.dev/pricing).
  Sizes $0.018 / $0.036 / $0.072 / $0.200 per hour; plans
  $20/$100/$500/$2000 per month; trial 25 free hours; "Compared to
  others" table unchanged (Novita, Freestyle, exe.dev, E2B, Daytona,
  Blaxel, Codespaces, Cloudflare, Modal, Islo, Runloop, Vercel
  Sandbox).
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases).
  Latest release still v0.7.3 (top entry: "chore: release v0.7.3 by
  @toksdotdev in #1646"); next down v0.7.1, then v0.7.0.
- **TermSquad — VERIFIED NO-CHANGE**
  (https://termsquad.com/pricing). Tiers Starter $9 / Builder $19 /
  Power $29 / Ultra $49 USD per month; "AI subscriptions and usage
  are not included." — all watched lines verbatim.
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). CPU Time $0.07 per
  CPU-hour; Memory $0.04375 per GB-hour; Hot Storage $0.000683 per
  GB-hour (running); Cold Storage $0.000027 per GB-hour (stopped) —
  all watched lines verbatim.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE (docs page);
  pricing subpage UNVERIFIED→VERIFIED NO-CHANGE.** Docs main page
  (https://docs.digitalocean.com/products/managed-agents/) still
  "Last verified 21 Sep 2026"; Latest Updates top entry still 21
  September 2026 (public preview). Pricing subpage reached directly
  this run at the late-morning carried URL
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/)
  — fetched cleanly. Watched lines verbatim: CPU $0.044 per
  vCPU-hour (Actual CPU consumed); Memory $0.0095 per GB-hour (Peak
  memory used); Session Storage $0.05 per GiB-month; Snapshots and
  Checkpoints $0.05 per GiB-month; BYOT $0.05 per GiB-month; page
  stamp "Last verified 22 Sep 2026". The late-evening UNVERIFIED flag
  is retired — the discovery miss is resolved.

**C44 check — VERIFIED NO-CHANGE (separate from the tracked set):**
Google Gemini Enterprise Agent Platform release notes
(https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
newest heading still **September 24, 2026** (verbatim content:
Gemini 3.8 Live GA; Muse Spark 1.3 Preview); no September 25, 2026
heading — VERIFIED absent. Headings below: September 22, 21, 18, 17,
16, 15, 14, 10, September 09 (C44 Computer Use + Shell sandboxes GA
— wording unchanged). The name match with this loop's model family
remains coincidental color only.

## 2. In-lane moves — no new filings; no launches, no pricing changes

### Sep-25-dated items found — all THIRD-PARTY recaps, deliberately not filed

- **Forkast.news, 2026-09-25 8:18 PM UTC** — "Docker Launched Cloud
  Sandboxes: Containers Weren't Designed for AI Agent Isolation"
  (https://forkast.news/docker-launched-cloud-sandboxes-containers-werent-designed-for-ai-agent-isolation/)
  — THIRD-PARTY analysis of the already-filed Sep-24 Cloud Sandboxes
  launch. New color verbatim: microVM isolation "not Firecracker or
  libkrun; it is a cross-platform virtual machine monitor that runs
  natively on macOS, Windows, and Linux via each platform's native
  hypervisor." Recap — don't file.
- **how2shout.com (Sep 25)** — Docker Cloud Sandboxes pricing
  explainer (https://www.how2shout.com/news/docker-cloud-sandboxes-pricing-agents.html)
  — THIRD-PARTY. Newest granular rate-card detail seen anywhere:
  Micro $0.07/h (1 vCPU/2GiB) → Small $0.14 → Medium $0.28 → Large
  $0.56 → XL $1.12/h; per-second billing, nothing charged while
  paused; volumes/egress/public-image + Kit hosting free; BYO model
  key; $250 free credit "for a limited period." Recap of an
  already-filed launch (third-party-only granularity) — don't file.
- **webpronews.com (~20h ago, Sep 25)** — Cloud Sandboxes + Kit Spec
  recap (https://www.webpronews.com/dockers-microvm-sandboxes-give-ai-agents-room-to-run-without-breaking-everything/)
  — THIRD-PARTY, no new facts. Don't file.
- **DEV.to crosspost by alexcloudstar (~Sep 24/25)** —
  "Sandboxing AI-Generated Code: E2B vs Vercel Sandbox vs Modal vs
  Daytona in 2026"
  (https://dev.to/alexcloudstar/sandboxing-ai-generated-code-e2b-vs-vercel-sandbox-vs-modal-vs-daytona-in-2026-3c7g)
  — editorial comparison on existing rate cards; no new product
  facts. Don't file.

### Searched, nothing in-lane surfaced

- Daytona changelog/pricing dated Sep 25 (only old PR reprints
  recrawled); E2B; Modal (undated vendor blog marketing piece only);
  Runloop (old "Unveils Enterprise-Grade Sandboxes" PR reprints);
  Northflank (2020 seed-article noise); Firecrawl; Vercel Sandbox
  (old breach-via-Context.ai story recrawled — adjacent, out of
  date); Microsandbox; TermSquad; AgentComputer. **In-lane no-launch
  verdict dated 2026-09-25 stands.**

**Carried:** C54 full article-body read (Perplexity "Escaping SPACE"
— HTTP 403 upstream_access_rejected on the carried URL, same
bot-block as prior passes; the ~14:10 CDT real-browser
headline/subtitle/SEP-23/date/author verification remains the only
vendor confirmation); C56 vendor-primary verification of
CVE-2026-82533 (three searches — no DeepSeek advisory, no GitHub
Security Advisory, no official 0.1.2-alpha.2 release notes surfaced;
THIRD-PARTY corroboration widened — OX Research, VulnCheck as
assigning CNA, The Hacker News, Forkast.news, plus PIR-2026-0060;
fix timeline now multi-source: OX reported Aug 24 → patch commit Aug
25 → GitHub tag 0.1.2-alpha.1 Aug 27 → npm 0.1.2-alpha.2 Aug 30 → OX
retest Aug 30; third-party wrappers moved to 0.1.3-alpha.1 by Sep 6);
C52 Kits-v2 follow-up (Docker release-notes full-page read this pass:
no Sep-25 entry, newest still 2026-09-22; the Sep-21 heading documents
**v3 kits** — OCI-based packages combining agent workload + reusable
mixins for tools/config/credentials/network/agent-instructions; V2
kits remain supported; the "Learn more about kits" mechanics docs page
remains the unread lead); C37 Pro fee still structurally omitted
(watched lines); C44 newest heading still Sep 24 (no Sep-25 entry —
VERIFIED absent); C26 conflicts unchanged (watched lines); Vercel
Drives NOT re-checked (P49 — next the 2026-09-26 morning pass).
