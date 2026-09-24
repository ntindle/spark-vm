# Competitor watch — 2026-09-24 (late evening)

Delta-only update against the evening pass
(`docs/COMPETITOR_WATCH_2026-09-24_EVENING.md`). Survey window
**2026-09-24 ~10:56–11:20 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set; (B) the carried asks (Vercel Drives GA watch, C36/C41/C43
re-verifications), primary-source vetting of the evening pass's three
queued fold candidates, plus an open-web in-lane news scan. Surveyor
captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-1054.md`), not the repo.

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

All reads within the survey window (~10:57–11:05 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The full-quiet streak, re-opened at one by the evening pass
after the afternoon pass's Daytona move, advances to **two** this pass.

- **Daytona — VERIFIED NO-CHANGE.** Changelog
  (https://www.daytona.io/changelog) is still topped by **SEP 24 /
  V0.216.2** ("CLI login through WorkOS"), with SEP 24 / V0.216.1
  ("API key organization ID and CLI update warning fix") second and
  SEP 23 / V0.216.0 third — exactly the evening baseline. No V0.216.3+
  follow-ups.
- **Docker Sandboxes — VERIFIED NO-CHANGE.** Release notes
  (https://docs.docker.com/ai/sandboxes/release-notes/) still top out
  **2026-09-21** (v3 kits); next entry 2026-09-15. Nothing dated
  09-22/09-23/09-24. (The notes now name CVE-2026-77179/79994 in the
  0.42.0 entry — the corpus already carries this from the 2026-09-19
  evening amendment, so no row change.)
- **Microsandbox — VERIFIED NO-CHANGE.** Releases
  (https://github.com/superradcompany/microsandbox/releases) still top
  out **v0.7.1**; next release v0.7.0.
- **E2B — VERIFIED NO-CHANGE.** Pricing (https://e2b.dev/pricing):
  Hobby free with $100 one-time credit / 1h sessions / 20 concurrent;
  Pro $150/mo / 24h sessions / 100 concurrent (expandable to 1,100);
  per-second table $0.000014/s for 1 vCPU. All match baseline.
- **boat.dev (Boat) — VERIFIED NO-CHANGE.** Pricing
  (https://docs.boat.dev/pricing): rate table small $0.018 / default
  $0.036 / large $0.072 / xlarge $0.200 per sandbox hour; per-second
  billing; stopped sandboxes free; 25 free trial hours — all match.
- **TermSquad — VERIFIED NO-CHANGE.** Plan table
  (https://termsquad.com/): Starter $9/mo 2 vCPU/4 GB/40 GB SSD NVMe;
  Builder $19/mo 4 vCPU/8 GB/75 GB; Power $29/mo 6 vCPU/12 GB/100 GB;
  Ultra $49/mo 8 vCPU/24 GB/200 GB. All match.
- **AgentComputer — VERIFIED NO-CHANGE.** Pricing
  (https://www.agentcomputer.ai/pricing): $0.07/CPU-hour,
  $0.04375/GB-hour, hot storage $0.000683/GB-hour (running), cold
  storage $0.000027/GB-hour (stopped); Enterprise tier present. All match.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE.** Pricing docs
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/):
  stamp still **"Last verified 22 Sep 2026"**; CPU $0.044/vCPU-hour,
  memory $0.0095/GB-hour, session storage $0.05/GiB-month;
  snapshots/checkpoints $0.05/GiB-month; BYOT $0.05/GiB-month. All match.

## 2. Carried asks — Drives, C36, C41, C43, plus Boxd / C42 / Upstash

- **Vercel Drives GA watch — VERIFIED NO-CHANGE, 25th consecutive
  no-change pass.** Pricing page
  (https://vercel.com/docs/sandbox/pricing) still `last_updated:
  2026-09-10`; all baseline values match (Drive Storage 15 GB lifetime
  Hobby / $0.05/GB-month Pro+Enterprise; reads $0.0015/GB; writes
  $0.004/GB; ≤4 drives per sandbox; 1 TiB default / 1 GiB Hobby; 16 TiB
  max; session caps 45min/24h; concurrency 10/10,000). Sandbox changelog
  (https://vercel.com/changelog) still carries the Drives public-beta
  entry at its 2026-09-23 date; the newest 2026-09-24 entry is "Vercel
  Connect now supports TanStack AI" — adjacent, not in-lane. **Still
  public beta, NOT GA** — no GA move, no fold. **This is the last
  hourly Drives pass — per the P49 decision (§5), the GA watch moves
  to once-daily (morning pass) from here.**
- **C36 Google Agent Substrate — VERIFIED unchanged this pass.** The
  Google Cloud blog
  (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."* No new
  datapoints on the page.
- **C41 Alibaba FC Agent Sandbox billing — VERIFIED unchanged.** The
  aliyun-fc/fc-docs pay-as-you-go page title confirms the exact pinned
  HEAD `39b6c3a20ec4597cceda497a4d8badf5384e2022` (matches the folded
  `39b6c3a`); all folded values match value-for-value (invite-only
  preview; active/light/deep hibernation; 15 GiB disk free allowance on
  active + light; Eco 0.00936/vCPU-h + 0.004608/GiB-h; Std
  0.01224/0.006012; Pro 0.01872/0.009360; disk 0.00031896 mainland /
  0.00025308 outside USD/GiB-h; per-second billing). No re-fold.
- **C43 Google Gemini Agent Environment — VERIFIED unchanged.** The
  vendor's own Gemini API docs
  (https://ai.google.dev/gemini-api/docs/agent-environment) still show
  the folded surface: managed Linux sandboxes for agents,
  `environment_id` reuse, git sources, network allowlists, credential
  references, pre-installed Ubuntu toolchains. No re-fold.
- **Boxd rate card (C29) — VERIFIED NO-CHANGE** on
  https://boxd.sh/pricing: €0.049/vCPU-hour running, €0.015/GiB-hour
  resident RAM, €0.0001/GiB-hour disk written; €30 free credits; vCPU
  billed only while running; hibernated = disk only; standby = RAM +
  disk.
- **Namespace Devboxes (C42) — VERIFIED NO-CHANGE** on the vendor's
  own docs (https://namespace.so/docs/devbox/agents): Linux/macOS
  devboxes; ephemeral devboxes; Pool API; `devbox exec` / `logs` /
  `upload`; `network_policy.egress_domains`; secrets via Namespace
  vault; Claude Managed Agents / Cursor Cloud Agents / Devin native
  integrations. No pricing published in the surveyed docs.
- **Upstash Box pricing — NO CHANGE.** Vendor's own comparison
  (https://upstash.com/blog/ai-agent-sandbox-providers-compared-2026):
  $0.10/$0.20/$0.40 per active CPU-hour (small 2 vCPU / medium 4 /
  large 8); free tier 10 boxes, 5 CPU-h/mo, $1 LLM budget, no card;
  keep-alive flat $8/$16/$32; paused $0 compute + $0.10/GB-mo storage.
  All match folded datapoints.
- **Deprecated-row sunset convention — still proposed-not-codified.**
  No new evidence this pass (C40 is ~5–6 passes into the proposed
  14-pass retention). Not codified unilaterally — pending
  corpus-owner approval (see §5).

## 3. The evening pass's three fold candidates — resolved this pass

1. **Google Computer Use + Shell sandboxes GA (Sept 9) — MEETS THE
   PRIMARY-SOURCE BAR → folded as C44.** VENDOR-VERIFIED on Google's
   own release notes
   (https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes),
   under "September 09, 2026": *"Computer Use and Shell sandboxes in
   Gemini Enterprise Agent Platform are now generally available (GA)."*
   Shell sandboxes run untrusted shell commands, install packages, and
   manipulate files in an isolated Linux container via direct `/exec`
   API calls; the same entry ships VPC Service Controls & Private
   Service Connect, CMEK (Cloud KMS, disk + snapshot checkpoints), and
   **pause/resume for sandboxes** — deschedule compute for idle
   sandboxes while preserving filesystem state and connection identity,
   resume in seconds. That is an **idle-suspend economics datapoint**,
   convergent with Agent Substrate's zero-idle posture and DO's
   305 ms resume claim — filed at the vendor layer (VENDOR-VERIFIED,
   not THIRD-PARTY). In-lane: a third Google agent-sandbox surface
   alongside C36 (GKE-side open-source runtime) and C43
   (Gemini-API-side Environments). Corpus action: **new C44**.
2. **Docker Sandboxes CVEs CVE-2026-77179 / CVE-2026-79994 — NO FOLD;
   same pair the 2026-09-23 ~11:54 pass already closed.** VENDOR-VERIFIED
   on Docker's own
   [security-announcements page](https://docs.docker.com/security/security-announcements/):
   "Docker Sandboxes 0.42.0 security update: CVE-2026-77179 and
   CVE-2026-79994" — fixed September 7 in 0.42.0; CVE-2026-77179
   Critical (macOS virtio-fs symlink follow, 0.28.0 ≤ v < 0.42.0);
   CVE-2026-79994 High (unix-socket-relay TOCTOU, 0.37.0 ≤ v < 0.42.0);
   workaround: clone mode, avoid read-write host mounts. Sameship
   check against the corpus (watch-update 2026-09-23 midday, §3a):
   CVE numbers, severities, fix version, dates all match — **not a
   distinct or newer pair; no new corpus entry.** The corpus already
   records that the release notes now name both CVEs (2026-09-19
   evening amendment), so the surveyor's "stale oddity" flag needs no
   correction.
3. **Alibaba "Agent Native Cloud" + Huawei "Open Agentic Cloud"
   two-vendor framing trend — STAYS QUEUED, adjacent.** Huawei is
   VENDOR-VERIFIED on huawei.com
   (https://www.huawei.com/en/news/2026/9/hc-agentic-infra-industry-ai,
   read this run): Sept 18 keynote "The Agentic Cloud for the Agentic
   World"; *"Huawei Cloud is committed to building an **open agentic
   cloud**, with open infrastructure to power AI, an open platform to
   support enterprises in effectively developing and using agents, and
   an open industry ecosystem"*; AICS commercial China Sept 30 /
   ex-China Nov 30; AgentArts 100+ enterprises, openJiuwen
   open-source edition; Context Memory Storage; "Agentic Infra"
   serving 3,500 customers claimed. Alibaba remains THIRD-PARTY (no
   vendor-own page found; all coverage is Media-Outreach syndication
   of the Sept 22 Apsara Conference: three layers AI Native Cloud
   (model) / Agent Native Cloud (harness) / Context Engine (context);
   AgentCore; Agent Security Center; 67% Agent Context
   token-reduction claim). Lane verdict: **adjacent-watch, not
   in-lane** — both are managed-agent-platform / agentic-stack
   framings; neither announces sandbox execution infra. The
   two-vendor "agentic cloud" framing trend is real (Huawei verified
   on its own page), but it doesn't clear the in-lane bar and takes
   no C-number. Kept queued as adjacent trend color.

Evening-pass vetting holds: OpenAI Agents API availability stays
THIRD-PARTY (live on vendor docs; public-beta dating only on a
community mirror); Tencent DataBuddy stays adjacent-watch (lane
tension recorded, not recoded). Namesake-collision warning stands:
Guava's "Daytona" voice model is unrelated to Daytona sandboxes.

## 4. Corpus actions

1. **C44 fold** — new field-table row + new "Watch update —
   2026-09-24 (late evening)" section in
   `docs/COMPETITOR_ANALYSIS.md`, per the C32/C37/C38/C39/C40/C41/C42
   precedent (explicit queued candidate verified on a primary
   source — the #82-pattern reach-back).
2. **Watch-review nit adoption** (the 20:54 turn's deferred nits,
   adopted at this pass's convenience):
   - (a) C36 "recent color" sentences labeling — **checked, resolved**:
     every C36 claim in the shipped corpus and watch docs already
     carries a convention label (VENDOR-CONFIRMED on the blog terms,
     THIRD-PARTY on the Filestore pricing color); no unlabeled C36
     sentences exist in any shipped doc.
   - (b) **Adopted**: the 2026-09-23 late-night README watch-table row
     naming Upstash Box as a "future-vetting candidate" now
     cross-references that it is already filed as **C31** — dedupe
     at vetting time, no double-file.
   - (c) YC 301 redirect — **already adopted** (tracked-set Boat row
     and deprecated C40 pointer row both cite the VERIFIED
     `/companies/ascii` → 301 → `/companies/boat`); no new edit.
   - (d) **Adopted**: the EU-only DE/FI/FR geography datapoint
     (Germany, Finland, France — FAQ verbatim, midday pass) is folded
     from the deprecated C40 pointer row into the tracked-set Boat
     row's feature cell.
   - (e) Deprecated-row sunset convention — **deliberately not
     adopted**: codifying it would be a unilateral rule adoption;
     it stays proposed-not-codified pending corpus-owner approval
     (recorded explicitly so the deferral is a decision, not an
     oversight).
   - (f) **Adopted**: the C40 rename watch-update section's YC-slug
     parenthetical ("the slug existed ~2 weeks ago") understated the
     live evidence — it now notes the slug still live-resolves to
     the Boat page via 301 (VERIFIED 2026-09-24 midday), matching
     the tracked-set row.
3. **Docker CVE corpus state — no action.** Confirmed the closed pair
   is the same pair; the corpus already records the vendor-notes
   naming both CVEs.

## 5. P49 decision — long-quiet carried-ask cadence (decided this turn)

P49 (filed by the 10:27 turn's evening-competitor-watch Product
review) asked a future strategy/meta turn to decide: keep the hourly
pass for high-signal asks only and downgrade long-quiet carried asks
(e.g. the Drives GA watch) to a lower cadence, or keep the full set
hourly with an explicit "ritual cost" note.

**Decision: the Vercel Drives GA watch moves to once-daily (checked
in the morning pass), effective immediately.** Rationale: 25
consecutive no-change passes on a vendor lifecycle event that moves
at quarterly cadence; the hourly re-read is ritual, and P49 named the
risk honestly. Tracked-set re-reads and carried C-item
re-verifications stay hourly — they are the high-signal core of the
pass. The F64 novel-yield advisory (flag if novel moves fall below
~1 per 4 slots) is untouched: this pass yielded one corpus move (C44),
so the yield is healthy.

## 6. News scan — adjacent color only, no in-lane moves dated 2026-09-24

- Meta Connect 2026 coverage of Muse's Sentinel-VM security
  architecture — consumer agent product, out-of-lane
  (explainx.ai).
- Modal $15B / Baseten $26B funding talks (Sept 23,
  Bloomberg/Reuters) — already in corpus; talks only, dated 9/23.
- DigitalOcean Managed Agents (Sept 22, BusinessWire/Morningstar
  recirc) — already in the tracked set.
- Daytona "agent-agnostic infrastructure" PR Newswire recirculation —
  out-of-window 2024-era copy, excluded per precedent.
- Prior-pass color stands (Island $400M Series F adjacent; Tencent
  DataBuddy adjacent-watch; OpenAI Agents API THIRD-PARTY).

## 7. Corpus actions carried forward

- Morning pass: Vercel Drives GA watch (now daily).
- Next passes: routine tracked-set re-reads; C36/C41/C43 re-verifies;
  the "agentic cloud" framing trend stays queued (Huawei half
  VENDOR-VERIFIED, Alibaba half THIRD-PARTY, adjacent); OpenAI
  Agents API availability vetting (THIRD-PARTY); deprecated-row
  sunset convention still proposed-not-codified.

---

Surveyed 2026-09-24 ~10:56–11:20 CDT. Tracked set 8/8 quiet (streak
2). Drives beta, 25th pass (now daily). C36/C41/C43 unchanged. **C44
new — Google Computer Use + Shell sandboxes GA (VENDOR-VERIFIED).**
Docker CVE pair = the already-closed pair (no fold). Agentic-cloud
trend stays queued (adjacent). No in-lane launches, pricing moves, or
funding dated 2026-09-24.
