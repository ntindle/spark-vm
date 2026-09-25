# Competitor watch — 2026-09-25 (night)

Delta-only update against the 2026-09-25 evening pass
(`docs/COMPETITOR_WATCH_2026-09-25_EVENING.md`). Survey window
**2026-09-25 ~07:25–07:35 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check; (B) an open-web in-lane
news scan dated 2026-09-25. Vercel Drives NOT re-checked this pass
(P49 once-daily morning cadence — checked the 2026-09-25 morning
pass, next the 2026-09-26 morning pass). Surveyor captures live in
the loop's `agent_notes/` workspace
(`surveyor-a-20260925-0724.md`, `surveyor-b-20260925-0724.md`), not
the repo. `_NIGHT` is collision-free on origin/main's watch-doc
list for this date
(MORNING/LATE_MORNING/MIDDAY/AFTERNOON/EVENING/PREDAWN/POST_MIDNIGHT
taken).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **snippet-level** = seen only
via search snippet. **UNVERIFIED** = a public page exists but could
not be fetched this run (never reported as NO-CHANGE). **VERIFIED
absent** = the vendor's own page was read this run and the item is
confirmed not present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

Zero pricing/feature deltas across the whole set. **Zero fetch
failures** this pass — all 11 URLs opened on vendor-owned pages.

- **Daytona — VERIFIED NO-CHANGE** (changelog:
  https://www.daytona.io/changelog; pricing:
  https://www.daytona.io/pricing). Newest changelog entries still the
  SEP 24 2026 pair (V0.216.1 "API key organization ID and CLI update
  warning fix"; V0.216.2 "CLI login through WorkOS"); no September 25
  entry. Pricing verbatim: compute $0.0504/h per vCPU, memory
  $0.0162/h per GiB, storage $0.000108/h per GiB; GPU preemptible
  ladder B300 $4.08/h down to RTX 4090 $0.57/h; Windows
  $0.0858/vCPU/h; "$200 in free compute included"; "All billing is
  calculated per second."
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Newest dated
  heading still *2026-09-21* (v3 OCI kits). No Sep 24/25 entries —
  the vendor press release for the Sep-24 **Docker Cloud Sandboxes**
  launch (§4, in-lane; already corpus-filed as **C45**) has still
  not surfaced on the docs release-notes page.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby FREE
  + $100 one-time credit; Pro $150/mo; per-second ladder $0.000014/s
  per vCPU unchanged.
- **boat.dev — VERIFIED NO-CHANGE**
  (https://docs.boat.dev/pricing). Sizes $0.018/$0.036/$0.072/$0.200
  per hour; plans $20/$100/$500/$2000 per month; trial (25 free
  hours, 2 sandboxes) unchanged.
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Latest
  still **v0.7.3** (#1646); no newer release visible.
- **TermSquad — VERIFIED NO-CHANGE**
  (https://termsquad.com/pricing). Tiers $9/$19/$29/$49 unchanged;
  "AI subscriptions and usage are not included."
- **AgentComputer — VERIFIED NO-CHANGE**
  (https://www.agentcomputer.ai/pricing). CPU $0.07/CPU-hour, Memory
  $0.04375/GB-hour, Hot $0.000683/GB-hour, Cold $0.000027/GB-hour —
  unchanged.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE** (docs page:
  https://docs.digitalocean.com/products/managed-agents/ — stamp
  still "Last verified 21 Sep 2026"; pricing subpage:
  https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/
  — stamp "Last verified 22 Sep 2026", CPU $0.044/vCPU-hour, memory
  $0.0095/GB-hour, egress $0.01/GiB; both C26 conflicts unchanged
  and still verbatim: the $0.05 per GiB-month rate appears on all
  three of the "Session Storage (Volumes)", "Snapshots and
  Checkpoints", and BYOT lines with no reconciliation, and "Active
  CPU billing is coming soon. Until then, you will be billed at 25%
  of the vCPUs allocated to your sandbox" still conflicts with the
  body copy's present-tense per-second active-compute billing.
  Watched lines, not hourly re-verification targets.)

## 2. Corpus folds — none (candidate dropped: already folded)

Surveyor B's scan surfaced one fold candidate — the DigitalOcean
Managed Agents public-preview launch detail (IR press release,
investors.digitalocean.com, Sep 22, 2026, **VERIFIED** read this
run: hardware-isolated microVM harness runtime, pause/resume/fork,
auto-pause stops CPU+memory charges, resume-from-pause 305 ms,
**$0.044/vCPU-hour active CPU** per-second, **$0.0095/GB-hour**
memory, **$0.005/GiB-month** snapshots on the IR surface, 16,000+
MCP tools via Action Gateway, runs Claude Code/Codex CLI/OpenCode
unmodified, customers OpenHands/Qencode/Amplitude, "up to 37% lower
TCO" claim vs an unnamed "leading independent sandbox provider") —
but **every one of these facts is already in the C26 deep-dive**
(pricing, 305 ms, 37% TCO, Action Gateway, customers, the $0.005
vs $0.05 snapshot conflict and its correction history). **Fold
dropped as a duplicate of C26 — no corpus action this pass.**

## 3. Carried asks

- **C37 — Pro fee still structurally omitted (carry).** Not
  re-checked this pass (page structurally omits plan fees —
  unchanged across every pass).
- **C44 — newest heading still September 24, 2026**
  (https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes,
  VENDOR-VERIFIED). Newest heading: **September 24, 2026** ("Gemini
  3.8 Live" GA; "Muse Spark 1.3 from Meta" Preview). **No September
  25, 2026 entry exists (VERIFIED absent).** Next older: September
  22 (empty Feature placeholder). (This pass re-checked the real
  Google page live, superseding the evening pass's deferral of the C44 check to the morning pass.)
- **Vercel Drives — not checked** (P49 once-daily morning cadence —
  checked the 2026-09-25 morning pass; next the 2026-09-26 morning
  pass).

## 4. In-lane news scan — Sep 25, 2026 context

**No new Sep-25-dated in-lane product launches, GA announcements,
pricing changes, or M&A found.** The window's in-lane news is
effectively empty; the headline of the week remains Docker Cloud
Sandboxes (Sep 24, already corpus-filed as **C45**).

- **Microsoft Copilot revamp (Sep 25, THIRD-PARTY)** — announced
  this window (Reuters article read in full this run): unified
  Copilot app with Home/Code/Autopilot; "Code" builds apps from
  natural language and per a Substack summary (snippet-level) the
  development "takes place in a sandbox by default" with the
  finished product "hosted inside the organization's tenant";
  Autopilot (always-on Scout revamp) in private preview end of
  month; usage-based billing for Cowork/Code/Autopilot. **Adjacent
  color only** — enterprise agent/product packaging, not developer
  sandbox infra — but it extends Microsoft's hosted-agent execution
  surface (sandbox-by-default builds + tenant hosting +
  identity/permissions per agent), i.e. competitive pressure on the
  "run my agent somewhere safe" problem. Watch-only; no corpus
  fold (adjacent).
- **Gemini API managed agents digest lead (snippet-level, date
  unverified)** — aiagentstore.ai weekly digest (week of Sep 25)
  claims a new `antigravity-preview-09-2026` harness plus
  Files/Credentials APIs "that move data in and out of an agent
  sandbox". Watch lead only: no firm publish date, no vendor
  source — do not treat as Sep-25 news.
- **DeepSeek DSec Harness desktop "leak" (biggo.com, ~12h)** —
  claims update-source code in the official GitHub repo, but the
  headline itself admits "No Formal Announcement Yet", and no
  deepseek.com page or deepseek-ai repo surfaced this run (only
  third-party wrapper repos). **Out — UNVERIFIED single source,
  deliberately not filed.** Sep-24–25 press recrawls of the arXiv
  paper (C49) are commentary on the same publication; nothing new.
- **Baseten/Blaxel M&A** — THIRD-PARTY (beri.net) stays
  third-party. The vendor announcement (Baseten Business Wire,
  Sep 10) is 15 days out of window; no new vendor full-page source
  surfaced this run. Adjacent flag only.
- **Out of lane / stale exclusions:** ABNewswire Feb-2026 launches
  recrawled under Sep-25 dates (OpenClaw Direct, Optivian AI sales
  agents — excluded as misdated); Daytona SDK dependency bumps
  (ex_daytona v0.2.0 Sep 1, computesdk/langchain/mastra dep updates
  — stale); e2b-dev PR #1749 (~7 days, SDK internals); datalayer
  code-sandboxes 1.9.0 (Sep 14, hobby project); Meta Muse VM
  filesystem export (explainx.ai Sep-25 blog — consumer
  personal-agent feature, not vendor-verified); Modal Runloop —
  no fresh vendor news; Salesforce outcome-based pricing / Anthropic
  1GW datacenter / Qualcomm–AWS $60B / GPT-6 Sol + Claude Opus 5.5
  inference price cuts (inference pricing, not execution infra).

**Net:** full-quiet pass. Tracked set 8/8 NO-CHANGE, zero fetch
failures. **No corpus fold** (the one in-lane fold candidate
dedupes to the already-filed C26 deep-dive). C44 still no Sep-25
heading. Microsoft Copilot revamp is adjacent watch color only.
Vercel Drives next the 2026-09-26 morning pass.

## Resolving asks for the next pass

- C26: conflicts unchanged (10× snapshots-only + active-CPU timing)
  — watched lines, not hourly re-verification targets.
- C48: resolved to VENDOR-VERIFIED; next watch is pricing or
  post-promo terms, not evidence grade.
- C49: resolved to PRIMARY-SOURCE-VERIFIED; the paper is now a
  scale/safety citation, not an ask.
- C37: stays carried (page structurally omits plan fees).
- C44: next check the Sep 25 heading arrival (Sep 24 remains
  newest).
- Vercel Drives: not checked (P49 — next the 2026-09-26 morning
  pass).
- Carried adjacent: Baseten/Blaxel M&A (THIRD-PARTY — upgrade grade
  only if a full-page vendor source is read); Gemini
  antigravity-preview-09-2026 digest lead (needs vendor source +
  firm date before filing anything); Microsoft Copilot revamp
  (watch-only adjacent).
