# Competitor watch — 2026-09-25 (mid-morning)

Delta-only update against the 2026-09-25 post-night pass
(`docs/COMPETITOR_WATCH_2026-09-25_POST_NIGHT.md`). Survey window
**2026-09-25 ~08:27–08:35 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set + C44 heading check; (B) an open-web in-lane
news scan dated 2026-09-25. Vercel Drives NOT re-checked this pass
(P49 once-daily morning cadence — next the 2026-09-26 morning pass).
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a-20260925-0824.md`, `surveyor-b-20260925-0824.md`), not
the repo. `_MID_MORNING` is collision-free on origin/main's watch-doc
list for this date (MORNING/LATE_MORNING/MIDDAY/AFTERNOON/EVENING/
NIGHT/PREDAWN/POST_MIDNIGHT/POST_NIGHT taken — precedent family:
`COMPETITOR_WATCH_2026-09-25_POST_NIGHT.md`).

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
  $0.0162/h per GiB, storage $0.000108/h per GiB (after first 5 free);
  GPU preemptible ladder B300 $4.08/h down to RTX 4090 $0.57/h;
  Windows $0.0858/vCPU/h; "$200 in free compute included"; "All
  billing is calculated per second."
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Newest dated
  heading still *2026-09-21* ("Docker Sandboxes now supports v3 kits:
  OCI-based packages…"); next older *2026-09-15*. The Sep-24
  **Docker Cloud Sandboxes** launch (corpus-filed as **C45**) still
  has not surfaced on the docs release-notes page, even though
  Docker's own press page and the Sandbox Kit Spec blog (new **C52**,
  §2) are both live.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby FREE
  + "$100 one-time usage credit" (sessions up to 1 hour, 20
  concurrent sandboxes); Pro $150/month (usage billed by the second,
  sessions up to 24 hours, 100 concurrent sandboxes expandable to
  1,100); per-second ladder 1 vCPU = $0.000014/s, 2 = $0.000028/s,
  4 = $0.000056/s, 6 = $0.000084/s, 8 = $0.000112/s.
- **boat.dev — VERIFIED NO-CHANGE**
  (https://docs.boat.dev/pricing). Sizes $0.018/$0.036/$0.072/$0.200
  per hour (small/default/large/xlarge); plans $20/$100/$500/$2000
  per month; Trial "25 free hours, 2 sandboxes at once"; "You pay for
  machine time, per second, only while a sandbox runs."
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Latest
  still **v0.7.3** (release commit #1646; "Full Changelog:
  v0.7.2...v0.7.3"). Next older v0.7.1, v0.7.0, v0.6.17.
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
  and still verbatim. Watched lines, not hourly re-verification
  targets.)

## 2. Corpus folds — C50 upgraded; C52 new; C53 new (adjacent)

**C50 evidence upgrade (Microsoft Copilot Managed Runtime — now
VENDOR-VERIFIED).** The carried ask from the post-night pass is met:
Microsoft's own announcement post —
https://blogs.microsoft.com/blog/2026/09/25/introducing-the-new-copilot-with-home-code-and-autopilot/
— was read in full this run (VENDOR-VERIFIED; Microsoft-owned,
URL-dated 2026/09/25; full-page read ~08:31 CDT). Verbatim additions
beyond the THIRD-PARTY row: "We're introducing **Microsoft Copilot
Managed Runtime**: hosting infrastructure that lets code run safely
right inside your company's Microsoft 365 environment. It's governed
by IT but easy for everyone else: share an app with teammates,
connect it to live data and access it from anywhere. This same
foundation enables apps built in Cowork, Code and Copilot Studio, and
we're opening it up to third-party and pro-code developers, too.
Copilot Managed Runtime is now in preview and will also be accessible
inside Code."; "Powered by the same underlying technology as GitHub
Copilot, Code runs in a sandboxed environment and can be hosted
securely within your tenant."; "Autopilot lives in your tenant with
its own identity, memory, computer and workspace"; "Cost management
in Agent 365 is expanding beyond Cowork and Work IQ APIs to include
Code and Copilot Managed Runtime, with support for agents built in
Microsoft Copilot Studio planned for October."; pricing: "Cowork,
Code, and Autopilot … all run on UBB" (usage-based billing). The
"public preview" framing carries: vendor page says "now in preview";
press (unite.ai, petri) called it public preview. Same post also
announces Code (Frontier end of September, broad availability coming
weeks, Premium/Pro preview later 2026), Autopilot (ex-Scout, private
preview expanding end of month), Home/Office-in-Copilot, FinOps for
AI, and Microsoft Ignite Nov 17–20. This upgrades **C50** to
vendor-page grade; the THIRD-PARTY qualifier is retired.

**C52 new — Docker Sandbox Kit Spec open-sourced + committed to CNCF
(VENDOR-VERIFIED, announced ~Sep 24).** Docker's own blog —
https://www.docker.com/blog/docker-sandbox-kit-spec-cncf/ — read in
full this run (VENDOR-VERIFIED). Companion to **C45** (Docker Cloud
Sandboxes, Sep-24). Verbatim: "Today at WeAreDevelopers, we announced
the Docker Sandbox Kit Spec, open source under Apache 2.0. A Kit
carries three things in one image: the agent, its tools, and a typed
list of everything it asks to reach, such as hosts, credentials, and
volumes. Because the list is part of the image, pinning the image
pins the agent and its requests together."; "Today, we're bringing
the spec to CNCF, under their neutral governance, just like we did
when the image format went to OCI."; "MCP gave agents a standard way
to talk to a tool. Kits give the ecosystem a standard way to publish
the whole arrangement: the agent, its tools, and what it asks to
reach, in one image anyone can pull."; "Docker Sandboxes is the first
runtime that enforces it. It should not be the only one, and under
CNCF governance, it will not be." Chris Aniszczyk (CNCF CTO): "By
delivering Sandbox Kits as standard OCI images, Docker is giving the
industry an open, repeatable way to package an AI agent, its tools,
and its guardrails as one artifact." Spec repo:
`docker/sandbox-kit-spec` (spec, capability pages, worked tour of a
real Kit — per the blog). Ecosystem collaborators named: AWS, Box,
Datadog, Dynatrace, JFrog, NanoClaw, OpenClaw, Palo Alto Networks,
Snyk. **Why in-lane:** an open agent-permission execution standard —
typed permission declarations (hosts, credentials, volumes, network
policy, ports, devices, skills paths) carried inside OCI images,
enforced by conforming runtimes. Date caveat: the vendor blog carries
no datestamp in-page and says "Today at WeAreDevelopers, we
announced…"; third-party coverage pins it to WeAreDevelopers North
America on/around 2026-09-24 (linux.com "1 day ago"; f-r-a-c daily
aggregate dated 2026-09-25) — filed as announced ~Sep 24,
surfaced/verified Sep 25. Follow-up lead: the docs.docker.com "Kits
v2" page (https://docs.docker.com/ai/sandboxes/customize/kits-v2/)
shows recent updates and was not fully read this run — candidate
follow-up read for Kits v2 mechanics.

**C53 new — Ando out of stealth + $20M raise (THIRD-PARTY, Sep-24,
filed adjacent).** TechCrunch 2026/09/24
(https://techcrunch.com/2026/09/24/ando-eyes-slack-as-it-builds-team-messaging-platform-for-humans-and-agents-to-work-together/),
corroborated by runtimewire.com (Sep 24) and aiagentstore.ai daily
(2026-09-25): "Her startup, Ando, on Thursday came out of stealth
with an app that sets out to do exactly that: It's a team messaging
platform designed for both human and AI workers."; "The app gives
agents their own identities and inboxes and lets them partake in
conversations as naturally as people can." Founder Sara Du (ex-Anthropic
MCP work, ex-Alloy Automation; Thiel Fellow): "Agents were treated as
apps you install even as they were becoming participants in the
team."; RuntimeWire: "Ando said on September 24th that it raised $20
million from Accel, Index Ventures and Emergence Capital";
"agent-agnostic, allowing teams to bring agents and harnesses they
already use, including Codex, Claude and Grokbot." **Why adjacent:**
agent participation infrastructure (identities, inboxes, permissions)
— relevant to the "where agents live and act" surface, but a
messaging-layer product, not a VM/sandbox/execution surface, so it
enters the corpus adjacent, not core. Sep 24 dateline (one day before
this pass's window); carried into Sep-25 coverage as an adjacent new
entrant.

- **Deliberately excluded this pass:** Baseten/Blaxel M&A — already
  THIRD-PARTY in corpus; no new vendor-page read this run → no grade
  upgrade (the beri.net Sep 24 FAQ is third-party advisory, not a new
  move). Gemini CLI v0.61.0-preview.1 (Sep 23 — agent-sandbox
  prompt-injection safeguards, just outside window). Dataiku Agent
  Management (Sep 24 — inventory/governance, not execution surface).
  Selangor/Google Cloud "Teraju AI" public-services sandbox (Sep 25
  dateline — government program, out of lane; stale-recrawl
  pattern). NanoClaw × Vercel × OneCLI partnership (Apr 2026, stale);
  NanoClaw Slack integration (~Aug 20, 2026, stale); Vercel Sandbox
  routing improvement (Sep 8, stale micro-improvement). Meta Muse for
  Mac "VM filesystem export" (Sep 25 update line on explainx.ai —
  snippet-level third-party, no vendor confirmation; watch, not
  filed). E2B, Daytona, Modal, Runloop, Vercel, boat.dev, TermSquad,
  AgentComputer, Microsandbox — **VERIFIED absent**: searched this
  run, no Sep-25-dated launch/price/availability move surfaced.
  DeepSeek DSec Harness "leak" (UNVERIFIED single source —
  standing instruction: not filed, not chased). OpenAI Agents API /
  DevDay Sep 29 (no new Sep-25 product facts; API changelog latest
  entry Sep 22). Out of lane: inference price cuts (GPT-6 Sol /
  Claude Opus 5.5), datacenter deals (Anthropic 1GW, Qualcomm–AWS),
  Salesforce outcome pricing, CARBONATO botnet (security incident),
  practitioner commentary with no new product facts.

**Net:** tracked set 8/8 NO-CHANGE, zero fetch failures. **Three
corpus moves: C50 evidence upgrade** (Microsoft Copilot Managed
Runtime — THIRD-PARTY → **VENDOR-VERIFIED**, Microsoft's own Sep-25
announcement post read in full); **C52** new (Docker Sandbox Kit Spec
open-sourced + committed to CNCF — **VENDOR-VERIFIED**, announced
~Sep 24); **C53** new (Ando out of stealth + $20M — THIRD-PARTY, filed
adjacent). C44 still no Sep-25 heading (VERIFIED absent). Vercel
Drives next the 2026-09-26 morning pass.

## Resolving asks for the next pass

- C26: conflicts unchanged (snapshots-only + active-CPU timing)
  — watched lines, not hourly re-verification targets.
- C48: resolved to VENDOR-VERIFIED; next watch is pricing or
  post-promo terms, not evidence grade.
- C49: resolved to PRIMARY-SOURCE-VERIFIED; the paper is now a
  scale/safety citation, not an ask.
- C50: **resolved** — upgraded to VENDOR-VERIFIED this pass; no
  further ask.
- C51: resolved (vendor + third-party date evidence); no ask.
- C37: stays carried (page structurally omits plan fees).
- C44: next check the Sep 25 heading arrival (Sep 24 remains
  newest — VERIFIED absent this pass).
- C52: follow-up lead — read the docs.docker.com "Kits v2" page for
  Kits v2 mechanics.
- C53: adjacent; no execution-surface ask — watch for Ando shipping
  agent-execution features.
- Vercel Drives: not checked (P49 — next the 2026-09-26 morning
  pass).
- Carried adjacent: Baseten/Blaxel M&A (THIRD-PARTY — upgrade grade
  only if a full-page vendor source is read).
