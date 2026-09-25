# Competitor watch — 2026-09-25 (post-night)

Delta-only update against the 2026-09-25 night pass
(`docs/COMPETITOR_WATCH_2026-09-25_NIGHT.md`). Survey window
**2026-09-25 ~07:56–08:05 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check; (B) an open-web in-lane
news scan dated 2026-09-25. Vercel Drives NOT re-checked this pass
(P49 once-daily morning cadence — checked the 2026-09-25 morning
pass, next the 2026-09-26 morning pass). Surveyor captures live in
the loop's `agent_notes/` workspace
(`surveyor-a-20260925-0754.md`, `surveyor-b-20260925-0754.md`), not
the repo. `_POST_NIGHT` is collision-free on origin/main's watch-doc
list for this date
(MORNING/LATE_MORNING/MIDDAY/AFTERNOON/EVENING/NIGHT/PREDAWN/POST_MIDNIGHT
taken — precedent family: `COMPETITOR_WATCH_2026-09-25_POST_MIDNIGHT.md`).

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
  the Sep-24 **Docker Cloud Sandboxes** launch (corpus-filed as
  **C45**) still has not surfaced on the docs release-notes page,
  even though Docker's own press page for it is now live (§2).
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

## 2. Corpus folds — C45 evidence upgrade; C50 new; C51 new

**C45 garnish (Docker Cloud Sandboxes — vendor press page now live,
VENDOR-VERIFIED).** Docker's own press page for the Sep-24 Cloud
Sandboxes launch —
https://www.docker.com/press-release/cloud-sandboxes-extending-secure-ai-agent-isolation-beyond-the-laptop/
— was read in full this run (VENDOR-VERIFIED; datelined "PALO ALTO,
Calif. – September 24, 2026"; launched at WeAreDevelopers North
America; "available now"). Verbatim additions beyond the existing
**C45** row: "Boot up in low hundreds of milliseconds. Docker Cloud
Sandboxes are ready to go instantly, with secrets, policy, MCP
gateways, and agent configuration already built in"; "Compute scales
from 1 to 16 vCPUs and is fully managed by Docker"; Kits-as-standard-OCI
with Docker's commitment to submitting the Kits specification to
the CNCF. This upgrades C45's launch-availability and boot-time
claims to vendor-page grade; the docs release-notes page still does
not carry the launch (tracked-set note above).

**C50 new — Microsoft Copilot Managed Runtime public preview
(THIRD-PARTY, Sep-25-dated, in-lane adjacent).** Alongside the Sep-25
Copilot revamp (Home/Code/Autopilot), Microsoft placed Copilot
Managed Runtime into public preview: enterprise-grade hosting that
"runs code inside the Microsoft 365 tenant boundary under IT
governance, with sharing, live data connections and access from
anywhere" (unite.ai, dated Sep 25, 2026 — THIRD-PARTY; Reuters
dated 2026-09-25; petri.com; geekwire.com all read this run).
The runtime already powers apps built in Copilot Cowork, Copilot
Code and Copilot Studio and "is opening it to third-party tooling
and professional developers through an SDK and command-line
interface that support project scaffolding, data connections and
typed TypeScript services". Code "runs in a sandboxed environment
and can be hosted within a customer's Microsoft 365 tenant"
(petri.com). **Why in-lane:** a new hosted-agent-execution surface
from Microsoft — tenant-boundary code hosting + SDK/CLI for
third-party developers — competitive pressure on the "run my agent
somewhere safe" problem. Filed adjacent (enterprise packaging, not
developer sandbox infra); grade upgrades to VENDOR-VERIFIED when a
Microsoft announcement page is read.

**C51 new — Gemini `antigravity-preview-09-2026` harness
(VENDOR-VERIFIED harness facts; THIRD-PARTY for the Sep-17 date).**
The digest lead carried from the night pass (gate: vendor source +
firm date) is now met. Vendor docs
(https://ai.google.dev/gemini-api/docs/antigravity-agent — read in
full this run): "The Antigravity agent is a general-purpose managed
agent on the Gemini API. A single API call gives you an agent that
reasons, executes code, manages files, and browses the web inside
your own secure Linux sandbox, hosted by Google"; "built with Gemini
3.8 Flash and uses the same harness as the Antigravity IDE"; code
sample: `agent = "antigravity-preview-09-2026"`, `environment =
"remote"`. Third-party (pondero.ai, dated 2026-09-24): "Google
released all three together in the antigravity-preview-09-2026
harness on September 17, 2026" — the Files API (upload data into the
agent's isolated Linux sandbox before a session, download files or
directories after) and the Credentials API ("lets the agent call
services the developer already has access to … without storing API
keys in the prompt or system instruction … secrets are injected at
runtime and the model never handles the raw credential values");
prior harness `antigravity-preview-05-2026` deprecated October 5,
2026. **Why in-lane:** Google's hosted-agent-sandbox surface is a
direct reference design for spark-vm — Google-hosted Linux sandbox,
Files/Credentials APIs for data in/out, runtime secret injection.
Filed as Sep-17/18-vintage evidence (not Sep-25 news); carried ask
closed.

## 3. Carried asks

- **C37 — Pro fee still structurally omitted (carry).** Not
  re-checked this pass (page structurally omits plan fees —
  unchanged across every pass).
- **C44 — newest heading still September 24, 2026**
  (https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes,
  VENDOR-VERIFIED). Newest heading: **September 24, 2026** ("Gemini
  3.8 Live" GA; "Muse Spark 1.3 from Meta" Preview). **No September
  25, 2026 entry exists (VERIFIED absent).** Next older: September
  22 (empty Feature placeholder).
- **Vercel Drives — not checked** (P49 once-daily morning cadence —
  checked the 2026-09-25 morning pass; next the 2026-09-26 morning
  pass).
- **C50 grade upgrade:** VENDOR-VERIFIED when a Microsoft
  announcement page is read (pending).

## 4. In-lane news scan — Sep 25, 2026 context

**One genuinely new Sep-25-dated in-lane move this pass** — Microsoft
Copilot Managed Runtime (see §2, **C50**). The rest of the window
is quiet.

- **DeepSeek DSec Harness "leak"** — deliberately unfetched per
  standing instruction; nothing new surfaced this slot.
- **Deliberately excluded this pass:** Cognitora.dev Show HN
  (date unknown; Product Hunt launch Sep 2025 — stale); Daytona
  "Agent-Agnostic Infrastructure" PR Newswire (recrawled old
  release, real story ~2025); explainx.ai DO Managed Agents piece
  ("Launched September 23, 2026" — all facts already in **C26**);
  itdigest.com weekly roundup (Sep-22 DO news recap — **C26**);
  implicator.ai Prime Intellect piece (219 days old — stale); DEV
  Community "Sandboxing AI-Generated Code" comparison (commentary,
  no new product facts); Medium Firecracker-sandbox build logs
  (practitioner writeups, not launches); Salesforce outcome-based
  pricing / Anthropic 1GW datacenter / Qualcomm–AWS $60B / GPT-6 Sol
  + Claude Opus 5.5 inference cuts (out of lane — inference pricing
  or non-exec infra); ABNewswire Feb-2026 misdated recrawls (none
  re-surfaced this slot).

**Net:** tracked set 8/8 NO-CHANGE, zero fetch failures. **Three
corpus moves:** C45 evidence upgrade (vendor press page
VENDOR-VERIFIED), **C50** new (Microsoft Copilot Managed Runtime —
Sep-25-dated), **C51** new (Gemini antigravity-preview-09-2026
harness — carried ask closed). C44 still no Sep-25 heading. Vercel
Drives next the 2026-09-26 morning pass.

## Resolving asks for the next pass

- C26: conflicts unchanged (snapshots-only + active-CPU timing)
  — watched lines, not hourly re-verification targets.
- C48: resolved to VENDOR-VERIFIED; next watch is pricing or
  post-promo terms, not evidence grade.
- C49: resolved to PRIMARY-SOURCE-VERIFIED; the paper is now a
  scale/safety citation, not an ask.
- C50: new this pass (THIRD-PARTY); grade upgrade to
  VENDOR-VERIFIED pending a Microsoft announcement-page read.
- C51: resolved (vendor + third-party date evidence); no ask.
- C37: stays carried (page structurally omits plan fees).
- C44: next check the Sep 25 heading arrival (Sep 24 remains
  newest).
- Vercel Drives: not checked (P49 — next the 2026-09-26 morning
  pass).
- Carried adjacent: Baseten/Blaxel M&A (THIRD-PARTY — upgrade grade
  only if a full-page vendor source is read).
