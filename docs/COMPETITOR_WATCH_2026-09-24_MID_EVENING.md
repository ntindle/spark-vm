# Competitor watch — 2026-09-24 (mid evening)

Delta-only update against the late-afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-24_LATE_AFTERNOON.md`). Survey window
**2026-09-24 ~17:00–17:12 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of half the tracked set (Daytona, Docker Sandboxes, E2B, boat.dev);
(B) the other half (Microsandbox, TermSquad, AgentComputer,
DigitalOcean Managed Agents) plus the carried asks (DigitalOcean
pricing-page fetch retry + 'Last verified 22 Sep 2026' stamp re-check;
OpenAI Agents API GA check) and an open-web in-lane news scan.
Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-1654.md`), not the repo. `_MID_EVENING`
carries the 2026-09-23 precedent.

Evidence labels used by the watch passes: **VERIFIED** = read on a
vendor's own page, doc, or repo this run. **VENDOR-VERIFIED** =
confirmed on the vendor's own page, docs, or changelog read this run
(corpus field-table usage). **THIRD-PARTY** = press/third-party
sources. **snippet-only** = seen only via search snippet. **INFERRED** =
my characterization. **UNVERIFIED** = a public page exists but could not
be fetched this run (never reported as NO-CHANGE). **VERIFIED absent** =
the vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 7/8 VERIFIED NO-CHANGE, DigitalOcean pricing re-verified on the vendor's own release

Seven of eight tracked surfaces read clean with zero pricing or
feature deltas in the window; the eighth (DigitalOcean Managed Agents)
had its pricing re-verified on the vendor's own press release — the
vendor product doc itself was not re-fetched this run, so the freshness
stamp stays a carried ask. boat.dev pricing is VERIFIED; its product-news
surface could not be located (UNVERIFIED on that sub-item only).

- **Daytona — VERIFIED NO-CHANGE.** Changelog
  (https://www.daytona.io/changelog) still tops at SEP 24 2026
  V0.216.2 (CLI login through WorkOS) / V0.216.1 (API key organization
  ID + CLI update warning fix), then SEP 23 V0.216.0. No V0.216.3+.
  Pricing page unchanged value-for-value ($0.0504/vCPU-h, $0.0162/GiB-h,
  $200 free credit, per-second). No daytona.io product news dated
  2026-09-24.
- **Docker Sandboxes — VERIFIED NO-CHANGE (release-notes page).**
  (https://docs.docker.com/ai/sandboxes/release-notes/) still tops at
  **2026-09-21** (v3 kits); nothing dated 09-22/09-23/09-24. The
  Cloud Sandboxes GA-venue announcement (below) is a new-lane item, not
  a release-notes delta.
- **Microsandbox — VERIFIED NO-CHANGE.** Releases
  (https://github.com/superradcompany/microsandbox/releases) still top
  out **v0.7.3** (release PR #1646, changelog v0.7.2...v0.7.3); no
  v0.7.4. Python SDK still 0.6.18 (Sep 9, 2026). No 24h news.
- **E2B — VERIFIED NO-CHANGE.** https://e2b.dev/pricing and
  /docs/billing match baseline exactly: Hobby FREE + $100 one-time
  credit; Pro $150/mo; 1 vCPU $0.000014/s → 8 vCPU $0.000112/s. No
  product news dated 2026-09-24.
- **TermSquad — VERIFIED NO-CHANGE.** https://termsquad.com/ —
  same positioning ("Always-On Cloud Computer for AI Agents"); pricing
  unchanged ($9/mo entry; $29 mid; $49 Ultra). Today's re-syndication
  of the Sept 15 launch press release is the same content, not a new
  announcement.
- **AgentComputer — VERIFIED NO-CHANGE.** https://www.agentcomputer.ai/pricing
  — PAYG unchanged (CPU $0.07/CPU-hour; Memory $0.04375/GB-hour; Hot
  Storage $0.000683/GB-hour running; Cold Storage $0.000027/GB-hour
  stopped). No 24h news.
- **boat.dev — VERIFIED NO-CHANGE (pricing); product-news UNVERIFIED.**
  docs.boat.dev/pricing matches baseline exactly
  ($0.018/$0.036/$0.072/$0.200 per sandbox hour; $20/$100/$500/$2000
  plans; 25 free-hour trial). No changelog/blog surface located this
  run — no no-change claimed on product news.
- **DigitalOcean Managed Agents — pricing re-VERIFIED (press release);
  vendor product doc not re-fetched.** The carried ask (vendor pricing
  page fetch, failed twice) is resolved a different way: the vendor's
  own Sept 22 press release (Business Wire — paid wire, the vendor's own
  claims) publishes $0.044/vCPU-hour active CPU (per-second),
  $0.0095/GB-hour memory, $5 new-user credit — all matching C26's
  closed pricing exactly. Paused = no CPU/memory charges, retained
  storage billable. Public preview opened Sept 22, 2026 (private
  preview before); still preview, not GA. The pricing subpage itself was
  not re-fetched this run, so the "Last verified 22 Sep 2026" stamp
  re-check stays carried one more pass. (No contradiction in the
  THIRD-PARTY subagentic.ai "September 21, 2026" claim: the
  late-afternoon pass read that stamp on the vendor's *product doc*,
  which carries no pricing — the 22 Sep stamp belongs to the pricing
  subpage.) Syndicated $0.005/GiB-month snapshots vs docs
  $0.05/GiB-month: the discrepancy stays retired in favor of the docs
  figure (no new evidence either way this run).

## 2. Carried asks

- **DigitalOcean pricing-page fetch:** resolved as above — pricing
  confirmed on the vendor's own press release; vendor product-doc
  re-fetch (and the "Last verified 22 Sep 2026" stamp re-check) stays
  carried one more pass.
- **OpenAI Agents API GA check — VERIFIED NO-CHANGE.** Still public
  beta; GA VERIFIED absent. Fresh reads (public-beta announcement,
  Sept 10 2026) confirm no GA date given.
- **Vercel Drives:** not re-checked this pass (P49 once-daily morning
  cadence stands).

## 3. In-lane news scan (dated 2026-09-24)

- **Docker Cloud Sandboxes — onstage GA announcement at WeAreDevelopers
  North America** (THIRD-PARTY: GlobeNewswire wire 12:00 PM EDT;
  The Register / ADTmag same-day coverage): Docker president Mark
  Cavage announced the cloud tier "available today". Docker's own
  keynote blog (VENDOR-VERIFIED): "Docker Cloud Sandboxes are
  available today with pay-as-you-go pricing" and "For a limited time,
  new accounts can claim $250 in compute credit". Same keynote: next-gen
  Sandbox Kits are now standard OCI images; Docker committed to
  submitting the Kits specification to the CNCF; Nous Research demoed
  Hermes running as a first-class Kit onstage. The Register's pricing
  (THIRD-PARTY: Micro 1 vCPU/2 GB $0.07/hr → XL 16/32 $1.12/hr)
  corroborates the already-filed C45 table exactly. This is the GA-venue
  layer of the early-afternoon C45 move, not a new product.
- **Island raised $400M at $6.4B** (THIRD-PARTY: techstartups.com,
  announced Thursday 2026-09-24; Evolution Equity Partners leading) —
  browser-security / rogue-AI-agent defense. Adjacent lane, not a
  sandbox move; tracked as funding signal.
- **Modal Labs reportedly in talks to raise at ~$15B** (THIRD-PARTY:
  Bloomberg via Reuters, reported 2026-09-23) — adjacent-lane funding
  signal (raised $355M in May at $4.65B).
- **Darktrace Signal Labs launched Sept 24** (THIRD-PARTY) — research
  initiative on agentic-AI risk (agentic coding assistants manipulated
  via conversation-history tampering, disclosed to Anthropic/AWS/OpenAI).
  Adjacent-lane (agent security research), not a product move.

## 4. Corpus verdict

Two garnishes, no new entries:

- **C45 — GA-venue garnish (THIRD-PARTY venue + VENDOR-VERIFIED keynote
  blog).** The onstage announcement at WeAreDevelopers North America
  anchors the early-afternoon C45 fold; Kits-as-OCI-images + CNCF
  submission commitment + Hermes-as-first-class-Kit demo are new vendor
  facts. Pricing corroboration (The Register, THIRD-PARTY) matches the
  filed table — no row change.
- **C26 — pricing re-verified, stamp still carried.** Vendor press
  release confirms the closed pricing ($0.044/vCPU-hour, $0.0095/GB-hour,
  $5 credit); the $0.05/GiB-month docs snapshot figure stands. The
  pricing subpage's "Last verified 22 Sep 2026" stamp re-check stays
  carried one more pass (the THIRD-PARTY subagentic.ai September 21
  claim is not a contradiction — it matches the late-afternoon pass's
  own read on the vendor's *product doc*, which carries no pricing).
- C36, C41, C43, C44: no new moves this pass (last re-verified at the
  late-afternoon pass, ~16:20 CDT; nothing in the news scan touches
  them). No new corpus entries. Full-quiet streak on the tracked set:
  seven of eight VERIFIED quiet plus the DO pricing re-confirm — the
  quiet streak continues.
