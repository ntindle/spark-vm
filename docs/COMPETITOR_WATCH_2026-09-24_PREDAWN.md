# Competitor watch — 2026-09-24 (predawn)

Delta-only update against the midnight pass
(`docs/COMPETITOR_WATCH_2026-09-24_MIDNIGHT.md`). Survey window
**2026-09-24 ~01:55–02:03 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set plus the Vercel Drives GA watch, (B) the owed
follow-ups — Ascii Box own-site verification, Simular Sai pricing on
sai.work, Freestyle's pricing page, the Tensorlake pricing watch, C36's
GKE terms re-verification, wowza.com re-verification — plus an open-web
in-lane news scan. Surveyor captures live in the loop's `agent_notes/`
workspace (`surveyor-a/b-20260924-0154.md`), not the repo.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) or company-issued announcement — a stricter claim than
VERIFIED, used only when we fetched the thing itself. **THIRD-PARTY** =
reported by press/third-party sources, including vendor-announcement text
read on a syndicated copy rather than the vendor's own page.
**snippet-only** = a THIRD-PARTY sub-state: seen only via search
snippet or aggregator digest this run, not fetched and read — no
stronger claim than its source's blurb. **INFERRED** = my
characterization, labeled as such. **UNVERIFIABLE** = no public source
exists to check against. **UNVERIFIED** = a public page exists but
could not be fetched this run (never reported as NO-CHANGE).
**VERIFIED absent** = the vendor's own page was read this run and the
item is confirmed not present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

All reads within the survey window (~01:55–02:00 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The **eighth full quiet 8/8 re-read pass since the
mid-afternoon fold**; values match the midnight pass exactly.

- **Daytona** — VERIFIED NO-CHANGE: changelog still topped by
  **SEP 23 2026 / V0.216.0** ("Confine Dockerfile COPY sources to the
  build context" — Python, Ruby, TypeScript SDKs); next entry below is
  SEP 22 / V0.215.0. No new entry today.
  (https://www.daytona.io/changelog)
- **Docker Sandboxes** — VERIFIED NO-CHANGE: release notes still top out
  **2026-09-21** (v3 kits: OCI-based packages combining an agent
  workload with reusable mixins for tools, configuration, credentials,
  network access, and agent instructions); nothing dated 09-22/09-23.
  (https://docs.docker.com/ai/sandboxes/release-notes/)
- **Microsandbox** — VERIFIED NO-CHANGE: top release still **v0.7.1**
  (explicit guest filesystem flush policies).
  (https://github.com/superradcompany/microsandbox/releases)
- **E2B** — VERIFIED NO-CHANGE: pricing tiers unchanged (Hobby free with
  $100 one-time credit / sessions up to 1 hour; Pro $150/month /
  24-hour sessions, 100 concurrent sandboxes expandable to 1,100;
  per-second table $0.000014/s).
  (https://e2b.dev/pricing)
- **boat.dev** — VERIFIED NO-CHANGE: rate table unchanged (small
  $0.018 / default $0.036 / large $0.072 / xlarge $0.200 per sandbox
  hour; per-second billing, stopped sandboxes free; 25 free trial
  hours).
  (https://docs.boat.dev/pricing)
- **TermSquad** — VERIFIED NO-CHANGE: plan table unchanged (Starter
  $9/mo 2 vCPU/4 GB/40 GB … Ultra $49/mo 8 vCPU/24 GB/200 GB).
  (https://termsquad.com/)
- **AgentComputer** — VERIFIED NO-CHANGE: pay-as-you-go table unchanged
  ($0.07/CPU-hour, $0.04375/GB-hour, hot storage $0.000683/GB-hour
  running, cold $0.000027/GB-hour stopped).
  (https://www.agentcomputer.ai/pricing)
- **DigitalOcean Managed Agents** — VERIFIED NO-CHANGE: pricing docs
  sub-page stamp still **"Last verified 22 Sep 2026"**; CPU
  $0.044/vCPU-hour, memory $0.0095/GB-hour, session storage
  $0.05/GiB-month; snapshots/checkpoints $0.05/GiB-month; BYOT
  $0.05/GiB-month; egress $0.01/GiB; shapes mars-1vcpu-1gb–mars-16vcpu-32gb.
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/)

Incidental sighting (no corpus action): Vercel's AI Gateway changelog
now lists "GPT-6 Sol and Luna" and "Claude Opus 5.5" (Sep 22) and
"Gemini 3.8 TTS" plus "Unlimited Vercel Blob stores" (Sep 23) —
adjacent inference-marketplace color, not in-lane.

## 2. Carried asks

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (19th consecutive
  no-change pass).** Pricing page VERIFIED
  (https://vercel.com/docs/sandbox/pricing): `last_updated` still
  **2026-09-10**; all values match baseline (Drive Storage
  $0.05/GB-month; Reads $0.0015/GB; Writes $0.004/GB; up to 4 drives
  per sandbox, 1 TiB default / 1 GiB Hobby, 16 TiB max; downloads free;
  session caps 45min/24h; concurrency 10/10,000). Changelog read this
  run (https://vercel.com/changelog): the "Drives for Vercel Sandbox
  are now in public beta" entry still carries its **2026-09-23 date**
  (the beta announcement surfacing as a re-dated entry — the INFERRED
  characterization stands across four passes); the newest 2026-09-24
  entry is "Vercel Connect now supports TanStack AI" — adjacent, not
  in-lane. **Still public beta, NOT GA** — no GA move, no fold.
  (https://vercel.com/changelog/drives-for-vercel-sandbox-are-now-in-public-beta)
- **C36 Google Agent Substrate — VERIFIED unchanged this pass.**
  The Google Cloud blog (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."* No new datapoints.
- **Ascii Box — own-site verification CLOSED, folds as C40** (see
  §4). The midnight pass's owed item: box.ascii.dev fetched and read
  this run (VERIFIED). **The product is branded "boat"**: "boat:
  Cheapest, Most Powerful Sandboxes for Agents" — persistent Ubuntu
  cloud VMs for agents; full VMs (Docker, systemd, databases, cron);
  60fps integrated desktop + browser; `boat` CLI
  (new/ssh/scp/exec/prompt/host/desktop/stop/resume); API + SDKs at
  docs.boat.dev; named snapshots, disk-level forking, port forwarding,
  secrets, teams, auto-stop. Pricing VERIFIED on the own page:
  "Plan required, from $20/mo" — "$20 plan = $20 of sandbox time";
  billed per second, only while running; **$0.036/hour for
  4 vCPU · 8 GB RAM · 50 GB**; 100 to 2,000 sandboxes by plan;
  $20 auto-refill packs; FAQ: "$20/mo is the account total, and it
  converts into 555 hours of machine time". EU-only DE/FI/FR VERIFIED
  in the FAQ ("Where do sandboxes run?" → Germany, Finland, France —
  "Your data and snapshots stay there"). Vendor-marketing caveat: the
  own page carries a comparison table (boat $0.036/h vs Freestyle
  $0.264/h, E2B/Daytona $0.331/h, Modal $0.476/h, Vercel Sandbox
  $0.682/h — treated as vendor marketing, not corpus datapoints). Note:
  the "boat" branding and the $0.036/h rate card overlap the tracked-set
  provider **boat.dev** (tracked rate table also quotes $0.036/h for the
  default tier) — an INFERRED possible rebrand/link between ASCII and
  boat.dev, flagged for the next pass, not folded as a claim.
  (https://box.ascii.dev)
- **Simular Sai pricing — partially resolved.** sai.work's own pages
  carry **NO pricing at all (VERIFIED absent this run)** — no pricing
  table, no figures, no pricing link on the homepage; CTA routes to
  sai.simular.ai. But the $50/$500 figures move UP in confidence: they
  are published on **simular.ai's own comparison pages** — Simular's
  own domain, VERIFIED this pass (not sai.work): Free (Explore, daily
  credits) / $50/month Pay as you go / $500/month Sai Unlimited /
  Enterprise custom. The $20/$200/$500 tiers stay **UNVERIFIED** —
  attributed to sai.work by dume.ai and TechInAsia (THIRD-PARTY only),
  not visible on any vendor-owned page this run. Fresh press color
  (Sept 23, THIRD-PARTY syndication): SaiFleet at ~$0.01/hour per Sai
  computer, 100-computer fleet under $1/hour. C39 field-table row
  updated to carry the refined confidence split.
- **Freestyle pricing — still NO-CHANGE.** freestyle.sh own homepage
  re-read this run (VERIFIED): no pricing link, no plan figures;
  "Start building" routes to the gated dash.freestyle.sh dashboard.
  The $50/$500 (Hobby/Pro) figures remain THIRD-PARTY only. The
  dashboard-probe standing ask carries.
- **Tensorlake pricing watch — answered (no page exists) + lane flag.**
  No published pricing page found; the closest own-site statement is
  Tensorlake's own benchmark blog: **$10 per 1k pages** ($0.01/page).
  Third-party echoes (THIRD-PARTY): $0.01/page pay-as-you-go, 100 free
  credits on signup. **Lane flag:** Tensorlake is a document-ingestion
  API (doc AI), not agent-sandbox infra — its C38 fold was framed on
  the "Sandboxes for AI Agents" headline, but the product reads as
  task-scoped document processing. Flagged for a future corpus
  lane-review; C38's fold stands this pass.
- **wowza.com re-verification — fetch loads, interactive owed.**
  `https://www.wowza.com` returned its full homepage content via the
  runner's text fetch this run (~02:03 CDT) — the prior-run connection
  resets cleared from our egress path. Caveat: this is a server-side
  fetch, not a real interactive browser render — the owed
  real-browser confirmation stands.

## 3. In-lane and adjacent news scan (2026-09-23/24, all THIRD-PARTY)

- **DigitalOcean Managed Agents — no corpus action.** The public
  preview launched 2026-09-22 is already recorded VERIFIED in the C26
  corpus deep-dive (vendor press release, Business Wire 2026-09-22 —
  paid wire = the vendor's own claims). The businesswire scan find was
  the same fact re-syndicated; dropped as a duplicate per the corpus's
  no-double-record rule.
- **Alibaba Cloud FC Agent Sandbox — new billing launch** (aliyun-fc/fc-docs
  on GitHub, ~6 days ago): Eco / Std / Pro editions, pay-as-you-go
  (unit price × run duration), hibernation tiers. In-lane-adjacent
  billing move; no corpus row yet (flagged for the next pass).
- **Bird.com — $450M debt financing** (Sept 23, THIRD-PARTY,
  JPMorgan-led): comms platform repositioning around "infrastructure
  for AI agents" (messaging/voice APIs as agent stack). Adjacent
  funding, not VM-for-agents.
- **Salesforce Agentforce repricing** (Sept 22, THIRD-PARTY): Agentforce
  1 retired Sept 3; new tiers Core $195 / Advanced $395 / Max $550 per
  user/month with Flex Credit allocations (500k / 1M / 2.75M per
  org/year); Industry Editions repricing "later this fall". Adjacent
  platform-pricing color.
- **Anthropic Consumer ToS update** (~Sept, THIRD-PARTY): explicitly
  prohibits using Claude subscriptions (Free/Pro/Max) with automated
  tools/bots/scripts/third-party apps including the Agent SDK — agent
  workloads pushed to API billing. Relevant to hosted-agent cost math,
  not a product move.
- Background carried: OpenAI Agents API public beta (Sept 10 —
  partnership lane: Cloudflare, DigitalOcean, E2B, Modal, Oracle,
  Runloop, Vercel among 9 partner sandboxes); Outerlimit $16M pre-seed
  (Sept 22 — zero-trust agent security, adjacent, from the midnight
  pass's scan).

## 4. Fold decision

Fold this pass, per the primary-source-verification and new-entry
precedents (C32, C37/C38, C39):

1. **C40 new — ASCII's "boat" (in-lane, persistent computer).**
   VERIFIED on box.ascii.dev this run: persistent Ubuntu VMs for
   agents with SSH/Docker/snapshots/disk-level forking, 60fps desktop,
   per-second billing; pricing VERIFIED on own page ($20/mo plan =
   $20 sandbox time, $0.036/h for 4vCPU/8GB/50GB); EU-only DE/FI/FR.
2. **C39 update — Sai pricing confidence split refined:** $50/mo PAYG
   and $500/mo Unlimited now VERIFIED on vendor-owned simular.ai
   (company domain, not sai.work); sai.work carries no pricing
   (VERIFIED absent); $20/$200/$500 tiers stay UNVERIFIED
   (THIRD-PARTY only).
3. Tensorlake lane-relevance flag recorded (§2), not folded; Alibaba
   FC Agent Sandbox billing flagged for the next pass.

No other in-window launches, GA moves, funding, or pricing moves dated
2026-09-24.

## 5. Verdict

**Eighth full quiet 8/8 tracked-set pass since the mid-afternoon
fold, two owed items closed.** The core is quiet; the Drives beta
streak extends to 19 passes; C36 unchanged. The Ascii Box verification
closed with a real fold: **C40 ASCII "boat"** enters the corpus as the
persistent-computer archetype with VERIFIED own-page pricing —
notably cheap at $0.036/h and EU-only, plus an INFERRED possible
rebrand link to the tracked-set boat.dev that the next pass should
resolve. C39's Sai pricing gets honest provenance: vendor-published
on the company domain, absent on sai.work, third-party everywhere
else. Next-pass asks:
resolve the boat/ASCII–boat.dev link, Alibaba FC Agent Sandbox
billing, Freestyle dashboard pricing, Vercel Drives GA watch (20th
pass), C36 standing watch, Tensorlake lane-review decision, wowza.com
interactive-browser confirmation.

## Next-pass asks

- boat.dev vs ASCII "boat": same company (rebrand) or coincidence?
  (INFERRED link — verify on primary sources.)
- Alibaba Cloud FC Agent Sandbox billing (Eco/Std/Pro): in-lane
  corpus candidacy.
- Freestyle: dash.freestyle.sh dashboard pricing path.
- Vercel Drives GA watch (20th pass).
- C36: GKE production-GA allowlist watch (standing).
- Tensorlake lane-review decision (document-ingestion API vs
  agent-sandbox corpus membership).
- wowza.com: interactive-browser confirmation (owed).
- Simular Sai: sai.work pricing page (still VERIFIED absent).
