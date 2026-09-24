# Competitor watch — 2026-09-23 (early night)

Delta-only update against the post-mid-evening pass
(`docs/COMPETITOR_WATCH_2026-09-23_POST_MID_EVENING.md`). Survey window
**2026-09-23 ~19:56–20:10 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set, (B) Vercel Drives GA watch plus Boxd/C36/Automaid checks
plus a lane-drift check and an open-web market-news scan. Surveyor captures
live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260923-1954.md`), not the repo.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) rather than a vendor doc-page assertion — a stricter claim
than VERIFIED, used only when we fetched the thing itself.
**THIRD-PARTY** = reported by press/third-party sources, including
vendor-announcement text read on a syndicated copy (e.g. a Business
Wire release) rather than the vendor's own page.
**snippet-only** = a THIRD-PARTY sub-state: seen only via search
snippet or aggregator digest this run, not fetched and read — no
stronger claim than its source's blurb.
**INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.
**UNVERIFIED** = a public page exists but could not be fetched this
run (never reported as NO-CHANGE).

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

All reads within the survey window; all values below VERIFIED on the
vendor's own page. No fetch failures on the tracked set this pass —
nothing labeled UNVERIFIED. The C26 figures carry forward unchanged for
the third consecutive pass (DO page stamp still "Last verified 22 Sep
2026"; snapshots/checkpoints $0.05/GiB-month; active-CPU-billing footnote
intact — VERIFIED on the docs pricing sub-page this run, not carried).

- **Daytona** — VERIFIED NO-CHANGE: changelog still topped by
  **SEP 23 2026 / V0.216.0** ("Confine Dockerfile COPY sources to the
  build context" — Python, Ruby, TypeScript SDKs); no new entry today.
  (https://www.daytona.io/changelog)
- **Docker Sandboxes** — VERIFIED NO-CHANGE: release notes still top out
  **2026-09-21** (v3 kits: OCI-based packages combining an agent
  workload with reusable mixins for tools, configuration, credentials,
  network access, and agent instructions).
  (https://docs.docker.com/ai/sandboxes/release-notes/)
- **Microsandbox** — VERIFIED NO-CHANGE: top release still **v0.7.1**
  (npm provenance + guest filesystem flush-policy patch series).
  (https://github.com/superradcompany/microsandbox/releases)
- **E2B** — VERIFIED NO-CHANGE: pricing tiers unchanged (Hobby free with
  $100 one-time credit / sessions up to 1 hour; Pro $150/month /
  24-hour sessions, 100 concurrent sandboxes expandable to 1,100;
  per-second table $0.000014/s).
  (https://e2b.dev/pricing)
- **boat.dev** — VERIFIED NO-CHANGE: rate table unchanged (small
  $0.018 / default $0.036 / large $0.072 / xlarge $0.200 per sandbox
  hour (INFERRED phrasing — the vendor states per-second machine-time
  billing: "A stopped sandbox costs nothing"); 25 free trial hours).
  (https://docs.boat.dev/pricing)
- **TermSquad** — VERIFIED NO-CHANGE: plan table unchanged (Starter
  $9/mo 2 vCPU/4 GB/40 GB … Ultra $49/mo 8 vCPU/24 GB/200 GB; BYOK FAQ
  unchanged).
  (https://termsquad.com/)
- **AgentComputer** — VERIFIED NO-CHANGE: pay-as-you-go table unchanged
  ($0.07/CPU-hour, $0.04375/GB-hour, hot storage $0.000683/GB-hour
  running, cold $0.000027/GB-hour stopped).
  (https://www.agentcomputer.ai/pricing)
- **DigitalOcean Managed Agents** — VERIFIED NO-CHANGE: pricing docs
  sub-page stamp still **"Last verified 22 Sep 2026"**; CPU
  $0.044/vCPU-hour, memory $0.0095/GB-hour, session storage
  $0.05/GiB-month; snapshots/checkpoints $0.05/GiB-month (the
  mid-evening C26 resolution stands — read live again this pass, not
  carried); active-CPU-billing footnote intact ("Active CPU billing is
  coming soon. Until then, you will be billed at 25% of the vCPUs
  allocated … Paused sessions incur no compute charges"); BYOT
  $0.05/GiB-month; egress $0.01/GiB.
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/)

## 2. Adjacent checks

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (14th consecutive
  no-change pass).** Pricing page `last_updated` still **2026-09-10**;
  the related-links section still lists "Drives for Vercel Sandbox are
  now in public beta" (no GA move); rate table and quotas identical to
  the last pass. Web search surfaced no Vercel Sandbox changelog entries
  dated 2026-09-23 — the newest sandbox items are the routing-18x-faster
  note (~Sept 8) and Cursor Cloud Agents on Self-Hosted Machines, both
  already-known.
  (https://vercel.com/docs/sandbox/pricing)
- **Boxd (C29) — VERIFIED NO-CHANGE on the rate card.** The pricing FAQ
  is verbatim unchanged (€0.049/vCPU-hour, €0.015/GiB-hour resident RAM
  while running/standby, €0.0001/GiB-hour written disk, €30 new-account
  credits). Own-page blog posts are engineering content (automations
  that sleep, forked-microVM deep dive), no pricing/product move. The
  ~Sept 17–21 $2M pre-seed funding news is THIRD-PARTY and already
  recorded (C29 corpus entry: BlueYard lead, OVNI/Antler/S20/Script
  Capital + angels, announced ~Sept 16) — dedupe, not a new fact.
  **docs.boxd.sh/quickstart was NOT re-checked this run — UNVERIFIED
  for that page specifically this pass** (browser-service fetch gate;
  honestly labeled, never NO-CHANGE).
  (https://boxd.sh)
- **C36 Google Agent Substrate — VERIFIED NO-CHANGE on the vendor
  axis.** No GA move, no production-terms change, no new design
  partners in 2026-09-23 coverage; the Google Cloud blog announcement
  itself dates to the May 2026 launch. Context only
  (snippet-only/THIRD-PARTY): a sunstoneinstitute/worklode research doc
  notes the kagent-dev/substrate fork's README calls itself "currently
  in early development… not ready for production use" — third-party
  ecosystems are extending Substrate, but the vendor story is unchanged.
- **Automaid — own-page verification STILL owed.** The own-page fetch
  failed this run (~19:58 CDT, browser-service fetch error) —
  UNVERIFIED, not NO-CHANGE. Web search turns up only spammy Medium SEO
  comment bait and a SourceForge listing describing Automaid as an
  online booking/operations tool for maid-service businesses — nothing
  resembling a VM-for-agents launch announcement. The third-party "AI
  hub" claim stays **UNVERIFIED**: a gap hardened, not contradicted —
  no vendor own-page evidence for it this run, and nothing in
  third-party results supports it either.
- **Lane-drift: Tencent Cloud DataBuddy — NOT IN-LANE.** The launch is
  THIRD-PARTY (PRNewswire syndicated copies, dated Sept. 23, 2026): a
  "fully managed, agent-native Data + AI workbench" with an Agent
  Runtime layer "engineered to enable enterprises to run their AI
  agents with governance, auditability and data controls built in."
  That is governance of data-pipeline agents inside a workbench, not
  sandbox/VM compute for agents. Available in China/Thailand/SK/
  Indonesia with Europe/North America rollouts ongoing. Stays a
  lane-drift watch item, not a competitor.

## 3. Market-news scan

No in-lane launch/GA/funding/pricing move today beyond what is already
tracked. The one genuinely in-lane launch in the window — DigitalOcean
Managed Agents (public preview, microVM Harness Runtime + Action
Gateway + Inference Engine, already in the tracked set) — carries only
THIRD-PARTY coverage dated 2026-09-22 (BusinessWire carrying DO's own
announcement text); the vendor's own docs were read live in §1.
Adjacent but NOT in-lane: WSO2 Agent Manager GA (2026-09-21,
governance control plane with a sandboxed runtime inside the platform —
governance, not VM compute); DataAgent $10M pre-seed launch today
(agents that fix production faults inside customer K8s — ops agents,
not agent sandbox compute); Arga $10M seed (~late Aug,
training-environment sandboxes). No moves today from E2B, Modal,
Cloudflare, Fly.io, Docker, Microsandbox, Runloop, Blaxel, Oracle in
2026-09-23 coverage.

## 4. Fold decision

No corpus fold this pass. The precedent (C32 primary-source-verification
fold, C35 close-only) holds: nothing changed on a primary source, so
there is nothing to fold and nothing to close. The two UNVERIFIED pages
(Boxd quickstart, Automaid own page) are asks for the next pass, not
findings.

## 5. Verdict

In-lane: **quiet.** Eighth consecutive quiet tracked-set pass (the
seventh full one since the mid-afternoon C36/C26 fold); 14th
consecutive quiet Vercel Drives pass; no GA moves, no pricing moves,
no in-lane launches today. Automaid's own page remains the single
open verification debt.

## Next-pass asks

- Re-attempt own-page fetch of https://automaid.it.com (failed this
  run) and docs.boxd.sh/quickstart (not re-checked this run) — both
  UNVERIFIED for today's pass.
- Routine tracked-set re-reads; Vercel Drives GA watch (15th pass).
- Keep Tencent Cloud DataBuddy on the lane-drift watch list; still not
  VM-for-agents.
