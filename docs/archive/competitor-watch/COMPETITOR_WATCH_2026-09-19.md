> **Archived 2026-09-19.** This watch pass's deltas were consolidated into `docs/COMPETITOR_ANALYSIS.md` (the 2026-09-19 night + morning + midday watch update); the original doc is preserved verbatim below. Supersedes the corresponding watch-pass PR #64, which should be closed as superseded.

# Competitor watch — 2026-09-19 (night pass)

Delta-only update against the 2026-09-18 ~16:00 CDT baseline
(`docs/COMPETITOR_WATCH_2026-09-18.md`; its §7 deltas are staged for
consolidation in PR #54, still open). Surveyed 2026-09-18 ~23:57 →
2026-09-19 ~00:30 CDT.

Summary: quiet night. No new launches, pricing changes, or partner moves
across the set. Three items are new to the corpus: (1) a pre-window item the
Sep-15-onward scan missed — **Cloudflare × Cursor (Sep 2)**,
customer-controlled execution for Cursor Cloud Agents on Cloudflare
Sandboxes; (2) a baseline spec completion — **TermSquad Power tier = 6
vCPU** (the pm pass recorded only three vCPU values for four tiers); (3) a
small provider-switch signal — **FastGPT v4.16.0 deprecates its E2B sandbox
provider**. WSO2 GA reception is wire syndication only (C10 stays open);
Baseten/Blaxel: nothing shipped (C11 stays open); OpenAI partners: nine,
unchanged (C9); AgentComputer: unchanged, egress still undocumented —
**C12 narrows to egress-only, confirmed**.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo this
run (link inline). **INFERRED** = third-party characterization, labeled as
such. "No change detected" is reported explicitly.

## 1. Cloudflare × Cursor (Sep 2) — new to the corpus, pre-window

The evening pass scanned Sep 15 → Sep 18 only, so this Sep 2 move never
entered the corpus. It belongs there: it is a major vendor playing the
customer-controlled-execution card.

- **VERIFIED (Cloudflare's own press release, Sep 2, 2026):**
  [Cursor Cloud Agents on Cloudflare Sandboxes](https://www.cloudflare.com/press/press-releases/2026/cloudflare-expands-support-for-ai-coding-agents-with-cursor-cloud-agents-on-cloudflare-sandboxes/) —
  Cursor Cloud Agents' tool work (terminal, filesystem, browser) can execute
  inside **Cloudflare Sandboxes in the customer's own Cloudflare account**,
  while Cursor keeps the agent loop (inference, planning, orchestration) via
  Cursor Self-Hosted Machines. Connectivity: outbound HTTPS from the worker
  to Cursor's backend; Cursor needs no inbound access into the customer
  network. The release frames it as a pattern, not a one-off: "builds on
  Cloudflare's work with other leading AI agent platforms, including Devin
  Outposts and Claude Managed Agents."
- **Implication:** the customer-controlled-execution thesis now has a
  big-vendor execution-layer play — execution inside the customer's own
  Cloudflare account, which rhymes uncomfortably with "your own computer,"
  so do not pitch control as the differentiator. The axes Cloudflare ×
  Cursor does not contest are **persistence** (their sandboxes are ephemeral
  execution-layer containers; "stays yours" survives) and the **approval
  loop**. Note the mirror for the hosted vision: spark-vm hosted is also
  converging toward provider-infra-customer-scoped execution, so the hosted
  differentiation story cannot rest on account-scoping either. Candidate
  one-line note for `docs/POSITIONING.md`, reworded around persistence +
  approval loop.

## 2. TermSquad (C1) — baseline spec completion; no product change

- **VERIFIED (termsquad.com/pricing, refetched this run):** $9/$19/$29/$49
  unchanged. Full spec, completing the pm pass's partial "2/4/8" vCPU record:
  Starter $9 = **2 vCPU** / 4 GB / 40 GB; Builder $19 = **4** / 8 GB / 75 GB;
  **Power $29 = 6 vCPU / 12 GB / 100 GB**; Ultra $49 = **8** / 24 GB /
  200 GB NVMe. "AI subscriptions and usage are not included" still explicit.
  Session model unchanged: BYO-agents + Squad Memory + Squad Debate +
  TermSquad Guard (runaway-workload protection). Still no isolation
  whitepaper, no agent-as-customer story.
- **FAQ reorganization, no product signal:** the FAQ now surfaces
  stop-behavior, backup/restore, and multi-region (America / Europe /
  Asia-Oceania) answers. The substance (managed backups/restores, conditional;
  multi-region choice) was already in `COMPETITOR_ANALYSIS.md` — this is doc
  depth, not a move.
- **Watch-method gap (record for future passes):** TermSquad routes product
  updates to x.com/trytermsquad, which is login-gated for read-only
  fetches — the worker could not confirm "no new announcement" there
  without auth. The no-new-announcement call covers the open web only.
- No new open-web announcement since the baseline. C1 watch continues.

## 3. WSO2 Agent Manager (C10) — reception: wire syndication only

- **INFERRED (wire republication, Sep 16–18):** GA coverage remains
  wire-syndication of the Sep 15 announcement — [TechGig
  (Sep 18)](https://techgig.com/news/ai/wso2-launches-open-source-agent-manager-for-ai-governance/134337159),
  arabianbusinessweek / menews247 / uaenews247 / channelpostmea (Sep 16).
  No independent developer reaction found.
- **Wire-claimed traction details (INFERRED, vendor-sourced — claims to
  verify, not adoption evidence):** Forrester Agent Control Plane Landscape
  Q2 2026 inclusion; AI Tech Awards 2026 "Best Innovation in Open Source
  AI"; Agentic AI Foundation membership; OpenID Foundation whitepaper
  co-authorship. Keep these as a watch item for corroboration.
- **Technical corroboration (VERIFIED, vendor repo):** [wso2/agent-manager
  #1390](https://github.com/wso2/agent-manager/pull/1390) (OTel ingestion on
  VM installs) confirms the sandbox **NetworkPolicy `except` list** exists
  in the wild — consistent with the evening pass's k8s-pod + NetworkPolicy
  egress pinning.
- Next milestone: webinar Sep 29. **C10 stays open.**

## 4. Baseten/Blaxel (C11) — nothing shipped; C11 stays open

- **VERIFIED (GitHub API):** no `blaxel-ai/sandbox` releases after v0.2.59
  (Sep 18); latest commit Sep 18
  (`5ff134e` "process: preserve severity and trace ids of structured output
  lines"). Minor, no product.
- **INFERRED:** Baseten's only post-acquisition product news is a Google
  Cloud Marketplace launch + Hybrid Mode early access — not a
  code-execution offering. **C11 stays open.**

## 5. OpenAI Agents API (C9) — nine partners, unchanged

- **INFERRED (third-party recaps):** still Blaxel, Cloudflare, Daytona,
  DigitalOcean, E2B, Modal, Oracle, Runloop, Vercel. Beta terms unchanged
  (1h inactive deletion, US-only residency, no ZDR even self-hosted). No
  adoption figures disclosed. C9 stands.

## 6. AgentComputer (C12) — no change; egress-only gap confirmed

- **VERIFIED (GitHub API):** `AgentComputerAI/computer-host` and
  `-computer-guest` untouched since 2026-04-30; both still 2 stars, no GitHub
  releases, no declared license field. Last commit: "chore: rename org
  getcompanion-ai → AgentComputerAI" — the org's prior name suggests the
  product was formerly "Companion" (color for future searches).
- **VERIFIED (vendor pages refetched tonight by the research worker):**
  pricing and docs unchanged; egress policy still undocumented on public pages.
- **C12 narrows to egress-only, confirmed:** hypervisor, persistence,
  pricing, and tier placement are now covered on primary evidence; the only
  open item is the egress posture.

## 7. FastGPT v4.16.0 (Sep 14) — small provider-switch signal

- **INFERRED (PR Newswire recap of FastGPT's upgrade guidance, Sep 14):**
  v4.16.0 deprecates the E2B sandbox-provider config; existing E2B users
  must switch to `opensandbox` or `sealosdevbox` providers, and remove
  `AGENT_SANDBOX_E2B_API_KEY`. New sandbox tuning vars: CPU (default 1),
  memory (2048 MiB), storage (1 GiB), auto-suspend 60 min, auto-archive
  7 days.
- Small directional signal, one line for the next consolidation: an OSS
  agent-platform deprecating E2B as a sandbox provider suggests the
  task-scoped sandbox defaults are less sticky than their partner logos
  imply. Not a backlog item.

## 8. What changes for the strategy docs / backlog

- **C1:** spec completed (Power = 6 vCPU); watch continues. Watch-method
  note filed above (x.com/trytermsquad login-gated).
- **C9:** unchanged.
- **C10:** stays open; Sep 29 webinar is the next milestone; reception still
  wire-only; vendor-sourced traction claims logged for corroboration.
- **C11:** stays open; nothing shipped.
- **C12:** egress-only confirmed.
- **Positioning note (candidate, not a backlog item):** customer-controlled
  execution is converging as a vendor pitch (Cloudflare × Cursor, WSO2
  sovereign — §1, §3 — plus VMware Private AI Cloud: deny-by-default Tanzu
  sandboxes + isolated credential store, announced at VMware Explore 2026
  ~Sep 1 — INFERRED, third-party via hostingdiscussion / nextplatform /
  siliconangle). spark-vm's claim in that conversation is persistence +
  approval loop + OSS, not control alone (see §1 implication).
- **Watch-window record (methodology):** this pass's pre-window finds
  (Cloudflare × Cursor, Sep 2; FastGPT v4.16.0, Sep 14) came from an ad-hoc
  reach-back past the evening pass's Sep-15 left edge. The corpus has no
  declared left edge or reach-back policy — the next pass should either
  declare the corpus left edge explicitly (e.g. 2026-09-02) or add a
  scheduled deep-scan cadence, so "no change detected" reads as "scanned"
  rather than "never looked."
- **Consolidation note:** this pass's deltas queue behind PR #54's still-
  open consolidation; a future consolidation folds both.

## Sources

Primary: [Cloudflare press release (Sep 2,
2026)](https://www.cloudflare.com/press/press-releases/2026/cloudflare-expands-support-for-ai-coding-agents-with-cursor-cloud-agents-on-cloudflare-sandboxes/);
[termsquad.com/pricing](https://termsquad.com/pricing) (refetched this run);
GitHub API: `blaxel-ai/sandbox` (releases, commits), `AgentComputerAI/
computer-host`, `AgentComputerAI/computer-guest` (commits, metadata);
[wso2/agent-manager #1390](https://github.com/wso2/agent-manager/pull/1390).
Third-party (INFERRED): TechGig / arabianbusinessweek / menews247 /
uaenews247 / channelpostmea on WSO2 GA; runtimewire, cellcog,
aicraftjournal on Agents API terms; TechDefused / Dealroom on Baseten;
morningstar PR Newswire on FastGPT v4.16.0; hostingdiscussion, nextplatform,
siliconangle, stocktitan/Broadcom media kit on VMware Private AI Cloud /
AgentMinder (announced ~Sep 1, 2026); dev.to + Medium on Cloudflare × Cursor.
