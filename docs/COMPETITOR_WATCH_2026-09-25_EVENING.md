# Competitor watch — 2026-09-25 (evening)

Delta-only update against the 2026-09-25 afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-25_AFTERNOON.md`). Survey window
**2026-09-25 ~06:26–06:31 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check; (B) the carried C37 ask
plus an open-web in-lane news scan dated 2026-09-25 (back-window Sep
23–24). Vercel Drives NOT re-checked this pass (P49 once-daily morning
cadence — next the 2026-09-26 morning pass). Surveyor captures live in
the loop's `agent_notes/` workspace
(`surveyor-a-20260925-0624.md`, `surveyor-b-20260925-0624.md`), not
the repo. `_EVENING` is collision-free on origin/main's watch-doc
list for this date
(MORNING/LATE_MORNING/MIDDAY/AFTERNOON/PREDAWN/POST_MIDNIGHT taken).

Evidence labels: **VERIFIED** = read on a vendor's own page, doc, or
repo this run. **VENDOR-VERIFIED** = confirmed on the vendor's own
page, docs, or changelog read this run (full page, not snippet).
**THIRD-PARTY** = press/third-party. **snippet-level** = seen only via
search snippet. **UNVERIFIED** = a public page exists but could not be
fetched this run (never reported as NO-CHANGE). **VERIFIED absent** =
the vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

Zero pricing/feature deltas across the whole set. **Zero fetch
failures** this pass — all 10 URLs opened on vendor-owned pages.

- **Daytona — VERIFIED NO-CHANGE** (changelog:
  https://www.daytona.io/changelog; pricing:
  https://www.daytona.io/pricing). Newest changelog entries still the
  SEP 24 2026 pair (V0.216.1 "API key organization ID and CLI update
  warning fix"; V0.216.2 "CLI login through WorkOS"); no September 25
  entry. Pricing verbatim: compute $0.0504/h per vCPU, memory
  $0.0162/h per GiB, GPU preemptible ladder B300 $4.08/h down to RTX
  4090 $0.57/h; "$200 in free compute included", "All billing is
  calculated per second."
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Newest dated
  heading still *2026-09-21* (v3 OCI kits). The vendor press release for
  the Sep-24 **Docker Cloud Sandboxes** launch (already corpus-filed as
  **C45**) has still not surfaced on the docs release-notes page
  (VERIFIED absent — third consecutive pass).
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
  still "Last verified 21 Sep 2026", public preview; pricing subpage:
  https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/
  — stamp "Last verified 22 Sep 2026", CPU $0.044/vCPU-hour, memory
  $0.0095/GB-hour, "Snapshots and Checkpoints … $0.05 per
  GiB-month"; both C26 conflicts unchanged: the $0.05 rate appears on
  both "Session Storage (Volumes)" and "Snapshots and Checkpoints"
  lines with no reconciliation text, and "Active CPU billing is
  coming soon. Until then, you will be billed at 25% of the vCPUs
  allocated to your sandbox" still conflicts with the IR page's
  present-tense active-CPU copy. Watched lines, not hourly
  re-verification targets.)

## 2. Corpus folds — none this pass

**No corpus fold; no new C-numbers.** The open-web scan surfaced three
in-lane items and all three dedupe to already-filed corpus entries:

- **Docker Cloud Sandboxes** — the 9/25 Help Net Security piece
  (THIRD-PARTY: "OCI-based Kits to package agents and their
  guardrails") is third-party re-telling of the Sep-24 launch already
  VENDOR-VERIFIED in **C45** — no new verifiable fact, no fold. The
  Register/ADTmag 9/24 corroboration predates this pass's window.
- **DigitalOcean Managed Agents public preview** — the
  investors.digitalocean.com release (9/22) and 9/21 docs release notes
  carry the $5 new-user credit, the 886 ms session-ready / 305 ms
  resume-to-ready vendor benchmarks, and the OpenHands/Qencode/
  Amplitude launch partners — all already in the **C26** row (the IR
  surface itself was read VENDOR-VERIFIED by the 9/25 morning pass).
  Grade not upgraded (snippet-level sighting of VENDOR-VERIFIED
  facts), no fold.
- **Prime Sandboxes GA** — the alpasignal.ai piece (~9/23,
  THIRD-PARTY: ~30M sandboxes in private rollout, launch rates,
  promo through Dec 22, CPU-only at GA) is a THIRD-PARTY downgrade of
  facts the afternoon pass already **VENDOR-VERIFIED at full-page
  grade** (**C48**) — no fold.

**Carried:** **C37** Pro fee VERIFIED absent on all public,
login-free surfaces this run — freestyle.sh/pricing read in full (the
usage-rate ladder and Free/Hobby/Pro *limits* table carry no plan
fees; the only dollar figure is Hobby $50/mo inside the FAQ example),
docs.freestyle.sh is a marketing stub with no pricing content, web
searches return nothing freestyle.sh-specific (`site:freestyle.sh`
zero results; results polluted by "Freestyle Solutions", a different
vendor). The ask stays open; the dashboard-signed-in check
(admin.freestyle.sh / Stripe checkout) remains owed and out of
anonymous reach. **C44** — no Sep-25 heading; newest heading remains
2026-09-21 (VERIFIED absent).

**Anti-chase note (for future passes):** Daytona's "agent-agnostic
infrastructure for sandboxing AI coding assistants" OpenHands demo is
recrawled-old PRNewswire syndication (page stamps 633–3045 days), not
a fresh announcement — do not re-open it.

Adjacent only (NOT corpus): Baseten acquires Blaxel (9/10,
out of window), AWS Bedrock AgentCore Runtime V2 GA (9/18, out of
window), Cloudflare Sandboxes + Cursor Cloud Agents (9/2, out of
window). Out of lane: OpenAI GPT-6 Sol/Luna + Claude Opus 5.5
inference price cuts (2026-09-22 — model pricing, not the agent-VM
lane).

## 3. Method notes

- Survey windows ~06:26–06:31 CDT; two read-only surveyors; no logins,
  no writes, no commits by surveyors (one capture file each in the
  loop's `agent_notes/` workspace).
- Vercel Drives NOT re-checked (P49 once-daily morning cadence — next
  the 2026-09-26 morning pass).
