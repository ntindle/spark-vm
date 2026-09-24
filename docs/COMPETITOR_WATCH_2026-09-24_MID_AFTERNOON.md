# Competitor watch — 2026-09-24 (mid afternoon)

Delta-only update against the early-afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-24_EARLY_AFTERNOON.md`). Survey window
**2026-09-24 ~14:56–15:15 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set; (B) the carried asks (C36/C41/C43/C44 re-verifications
+ OpenAI Agents API GA check + C45 follow-ups), the queued trends, plus
an open-web in-lane news scan. Surveyor captures live in the loop's
`agent_notes/` workspace (`surveyor-a/b-20260924-1455.md`), not the
repo.

Evidence labels used by the watch passes: **VERIFIED** = read on a
vendor's own page, doc, or repo this run. **VENDOR-VERIFIED** =
confirmed on the vendor's own page, docs, or changelog read this run
(corpus field-table usage). **THIRD-PARTY** = press/third-party
sources. **snippet-only** = seen only via search snippet. **INFERRED** =
my characterization. **UNVERIFIED** = a public page exists but could not
be fetched this run (never reported as NO-CHANGE). **VERIFIED absent** =
the vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 7/8 VERIFIED NO-CHANGE, one UNVERIFIED

No tracked surface moved this pass: zero pricing or feature deltas in
the window. Seven of eight read clean on the vendors' own pages;
DigitalOcean's pricing docs could not be fetched (see below), so it is
not claimed as no-change.

- **Daytona — VERIFIED NO-CHANGE.** Changelog
  (https://www.daytona.io/changelog) still topped by the SEP 24 entries
  V0.216.1 (API key organization ID + CLI update warning fix) +
  V0.216.2 (CLI login through WorkOS), then SEP 23 / V0.216.0. No
  V0.216.3+ follow-ups.
- **Docker Sandboxes — VERIFIED NO-CHANGE.** Release notes
  (https://docs.docker.com/ai/sandboxes/release-notes/) still top out
  **2026-09-21** (v3 kits); next entry 2026-09-15. Nothing dated
  09-22/09-23/09-24.
- **Microsandbox — VERIFIED NO-CHANGE.** Releases
  (https://github.com/superradcompany/microsandbox/releases) still top
  out **v0.7.3** ("chore: release v0.7.3 by @toksdotdev in #1646";
  changelog "v0.7.2...v0.7.3"), with v0.7.1 immediately below. No
  v0.7.4+.
- **E2B — VERIFIED NO-CHANGE.** Pricing (https://e2b.dev/pricing):
  Hobby FREE $100 one-time credit / 1h sessions / 20 concurrent; Pro
  $150/mo / 24h sessions / 100 concurrent (expandable to 1,100);
  per-second table $0.000014/s for 1 vCPU. All match.
- **boat.dev (Boat) — VERIFIED NO-CHANGE.** Pricing
  (https://docs.boat.dev/pricing): small $0.018 / default $0.036 /
  large $0.072 / xlarge $0.200 per sandbox hour; per-second billing;
  stopped sandboxes free; 25 free trial hours — all match.
  **GEOGRAPHY ASK RESOLVED — re-VERIFIED on the vendor page.** The
  midday FAQ datapoint was located verbatim on https://boat.dev/ this
  run: *"Where do sandboxes run? In the EU: Germany, Finland, and
  France. Your data and snapshots stay there."* The three-pass carried
  retry is dropped; the midday fold stands re-VERIFIED.
- **TermSquad — VERIFIED NO-CHANGE.** Plan table
  (https://termsquad.com/): Starter $9/mo 2 vCPU/4 GB/40 GB SSD NVMe;
  Builder $19/mo 4 vCPU/8 GB/75 GB; Power $29/mo 6 vCPU/12 GB/100 GB;
  Ultra $49/mo 8 vCPU/24 GB/200 GB. All match.
- **AgentComputer — VERIFIED NO-CHANGE.** Pricing
  (https://www.agentcomputer.ai/pricing): $0.07/CPU-hour,
  $0.04375/GB-hour, hot storage $0.000683/GB-hour (running), cold
  storage $0.000027/GB-hour (stopped); Enterprise tier present. All
  match.
- **DigitalOcean Managed Agents — UNVERIFIED this pass.** The vendor
  pricing docs could not be fetched in the survey window (one fetch
  attempt failed; not claimed as no-change per the evidence rules).
  Third-party coverage (BusinessWire 9/22 investor release,
  subagentic.ai 9/23) still shows $0.044/vCPU-hour active-CPU billing,
  $0.0095/GB-hour memory, $0.005/GiB-month snapshots — no move
  indicated, but these are not the vendor page. The **"Last verified
  22 Sep 2026"** stamp re-check carries to the next pass.

## 2. Carried asks — C36, C41, C43, C44 all unchanged; no OpenAI GA

- **C36 Google Agent Substrate — VERIFIED unchanged.** The Google
  Cloud blog
  (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."* No new
  9/24 launch news.
- **C41 Alibaba FC Agent Sandbox — VERIFIED unchanged.** The
  aliyun-fc/fc-docs pay-as-you-go page title confirms the exact pinned
  HEAD `39b6c3a20ec4597cceda497a4d8badf5384e2022` (matches the folded
  `39b6c3a`); every folded value matches value-for-value. The
  Snapshot-pricing section (last pass's queued awareness flag) was read
  in full this run and is now fully specified (see §5, corpus action
  1).
- **C43 Google Gemini Agent Environment — VERIFIED unchanged.** The
  vendor's own Gemini API docs
  (https://ai.google.dev/gemini-api/docs/agent-environment) still show
  the folded surface verbatim; footer still: *"Preview status:
  Environments and managed agents are in preview."* No GA move.
- **C44 Google Gemini Enterprise Agent Platform sandboxes GA —
  VERIFIED unchanged.** The vendor's own release notes
  (https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
  show latest entry September 22, 2026; the September 09, 2026 GA entry
  stands verbatim. No Sept 23–24 entries.
- **OpenAI Agents API — still public beta, no GA (VERIFIED absent).**
  This run read **OpenAI's own changelog** and confirmed the Sept 10
  entry still reads *"Released the Agents API in public beta"* — a
  fresh first-party read that re-confirms the noon pass's
  VENDOR-VERIFIED dating (the early-afternoon pass read a
  third-party mirror); still no GA move.
- **C45 Docker Cloud Sandboxes — no new moves since the fold.** The
  GlobeNewswire wire adds the launch venue *"WeAreDevelopers North
  America"* (THIRD-PARTY); docs.docker.com frames local + cloud
  together and all folded values match; the local release notes still
  top 2026-09-21. No follow-up moves, pricing changes, or region news
  dated 9/24. (Optional garnish, §5 corpus action 2.)
- **Deprecated-row sunset convention — still proposed-not-codified.**
  No new deprecated-row activity (C40 ~8 passes into the proposed
  14-pass retention). Not codified unilaterally — pending corpus-owner
  approval.
- **Vercel Drives GA watch — out of this pass's scope.** Per the P49
  decision it moved to once-daily (morning pass). Next check: tomorrow
  morning. (Surveyor B opportunistically re-read the pricing page and
  changelog this pass anyway: `last_updated: 2026-09-10` not moved;
  Drives still public beta, VENDOR-VERIFIED; no 9/23–24 sandbox
  changelog entries.)

## 3. Queued trends — all hold, none move in-lane

- **"Agentic cloud" two-vendor framing — STAYS QUEUED (adjacent).**
  No new vendor-issued pages for Alibaba "Agent Native Cloud" or
  Huawei "Open Agentic Cloud" sandbox sign-up surfaces surfaced this
  run. Framing-level only; no C-number.
- **Tencent Cloud DataBuddy (Sept 22) — stays adjacent-watch.** No
  new vendor-issued sandbox sign-up surface confirmed; trial portal
  re-attempt not owed this pass (morning pass owns the retry
  cadence). Lane tension stands, recorded not resolved.
- Evening-pass vetting holds: namesake-collision warning stands
  (Guava's "Daytona" voice model is unrelated to Daytona sandboxes).

## 4. News scan — no in-lane launches dated 2026-09-24

No new agent-VM / sandbox / hosted-agent-infra launches, pricing
moves, or funding dated 2026-09-24 from Daytona, E2B, Modal, Fly
Machines, Northflank, Railway, Render, Koyeb, or HuggingFace.
Adjacent color only, no folds: Darktrace Signal Labs, Feedzai Farol,
Pine Labs × Google Cloud, Hedera IDTrust, a dev.to E2B piece.
**"Lizard" (surfaced in the dev.to piece) has no verifiable vendor
surface and name-collides with Lizard Squad — no corpus entry at
all**, per the recommendation against phantom-provider entries (the
C40 precedent).

## 5. Corpus actions

1. **C41 Snapshot-pricing fold.** The queued awareness flag from the
   early-afternoon pass (§2) is now fully specified on the vendor
   page: Snapshot Storage Usage = Memory Specification × 2 + Disk
   Specification, charged at the Disk Unit Price for the storage
   Duration. Folded into the C41 field-table row + a "Watch update —
   2026-09-24 (mid afternoon)" section, per the C32/C37/C38/C39/C40/
   C41/C42/C43/C44 precedents.
2. **C45 garnish (optional, folded).** GlobeNewswire's launch-venue
   datapoint *"WeAreDevelopers North America"* folded as THIRD-PARTY
   color in the C45 watch-update section — a single line, no row
   change.
3. **Watch-doc naming convention admits `_MID_AFTERNOON`.** The
   09:54 pass took `_AFTERNOON`, the early-afternoon pass took
   `_EARLY_AFTERNOON`; this ~15:00 pass reads honestly as mid
   afternoon (the 2026-09-23 `_MID_AFTERNOON` precedent exists). Same
   amendment practice as the `_NOON` / `_EARLY_AFTERNOON` admissions.
4. **Boat geography retry closed.** The EU-only DE/FI/FR datapoint is
   re-VERIFIED verbatim on the vendor FAQ; the carried retry is
   dropped (the midday fold stands).
5. **No other corpus changes.** Tracked set 7/8 quiet + 1 UNVERIFIED;
   C36/C43/C44 unchanged; OpenAI Agents API stays public beta (dating
   upgraded to VENDOR-VERIFIED); deprecated-row sunset convention
   still proposed-not-codified.

## 6. Corpus actions carried forward

- Next passes: routine tracked-set re-reads; C36/C41/C43/C44
  re-verify; **DigitalOcean "Last verified 22 Sep 2026" stamp
  re-check** (vendor docs could not be fetched this pass — owed, not
  carried on a streak); the "agentic cloud" framing trend stays
  queued; Tencent DataBuddy stays adjacent-watch; deprecated-row
  sunset convention still proposed-not-codified.
- Morning pass: Vercel Drives GA watch (daily, per P49).

---

Surveyed 2026-09-24 ~14:56–15:15 CDT. Tracked set: 7/8 VERIFIED
NO-CHANGE, one UNVERIFIED (DigitalOcean docs — no-move not claimed;
stamp re-check owed next pass). **Resolved asks:** Boat EU geography
re-VERIFIED verbatim on the vendor FAQ (three-pass retry closed);
OpenAI Agents API Sep-10 public-beta dating re-confirmed
VENDOR-VERIFIED with a fresh read of OpenAI's own changelog (the noon
pass's upgrade already stood; still public beta, no GA).
C36/C41/C43/C44 unchanged; C45 no new moves. **Corpus folds:** C41
Snapshot-pricing line (fully specified this run) + C45
WeAreDevelopers-venue garnish (THIRD-PARTY); `_MID_AFTERNOON`
admitted to the watch-doc naming convention. News scan: no in-lane
launches, pricing moves, or funding dated 9/24.
