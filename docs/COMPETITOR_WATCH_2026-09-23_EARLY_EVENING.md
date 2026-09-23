# Competitor watch — 2026-09-23 (early evening)

Delta-only update against the late-afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-23_LATE_AFTERNOON.md`). Survey window
**2026-09-23 ~16:55 → 17:06 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set (reads ~16:56–16:58 CDT), (B) Vercel Drives GA watch plus
open-web market-news scan (vendor pricing/changelog reads ~16:56–17:00
CDT). The itbrief.com.au Filestore piece below was re-fetched and read
by the author directly ~17:06 CDT. Surveyor captures live in
the loop's `agent_notes/` workspace (`surveyor-a/b-20260923-1654.md`),
not the repo. (Surveyor B's capture claims an itbrief read at ~17:10
CDT — impossible, since the surveyor completed at 16:59 CDT; the
author's own re-fetch supersedes that timestamp.)

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) rather than a vendor doc-page assertion — a stricter
claim than VERIFIED, used only when we fetched the thing itself.
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

## 1. The tracked set — no changes detected (7/8 VERIFIED NO-CHANGE, 1/8 UNVERIFIED)

Reads ~16:56–16:58 CDT; all values below VERIFIED on the vendor's own
page unless noted:

- **Daytona** — changelog top entry still **SEP 23 2026 / V0.216.0 —
  "Confine Dockerfile COPY sources to the build context"** (Python,
  Ruby, TypeScript SDKs); V0.215.0 (SEP 22) still second (**VERIFIED**:
  https://www.daytona.io/changelog).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits, quoted from the vendor page: "`sbx mcp catalog` has been
  removed", "Sandboxes now recover when the guest kernel crashes",
  "Experimental outbound UDP now follows sandbox network policy");
  next entry still 2026-09-15
  (**VERIFIED**: https://docs.docker.com/ai/sandboxes/release-notes/).
- **Microsandbox** — top release still **v0.7.1** (npm provenance +
  flush-policy patch series); no newer release this window
  (**VERIFIED**: https://github.com/superradcompany/microsandbox/releases).
- **E2B** — pricing unchanged: Hobby **FREE / $100 of usage in
  credits** ("$100 one-time usage credit"), Pro **$150/month**,
  Enterprise **CUSTOM** ($3,000/mo minimum); per-second table still tops
  **$0.000014/s** per vCPU (**VERIFIED**: https://e2b.dev/pricing).
- **boat.dev** — rate card unchanged: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h** (xlarge needs a
  $100 plan or higher); "A stopped sandbox costs nothing"; trial still
  25 free hours, 2 sandboxes at once, small and default only, until
  first payment (**VERIFIED**: https://docs.boat.dev/pricing).
- **TermSquad** — tiers still Starter **$9/month** (2 vCPU / 4 GB),
  Builder **$19/month** (4 / 8), Power **$29/month** (6 / 12), Ultra
  **$49/month** (8 / 24); BYO-AI stance intact (**VERIFIED**:
  https://termsquad.com/).
- **AgentComputer** — pricing table identical (CPU **$0.07**/CPU-hour,
  memory **$0.04375**/GB-hour, hot **$0.000683**/GB-hour, cold
  **$0.000027**/GB-hour; Enterprise Custom); still **no stated egress
  policy** — C12 stands (**VERIFIED**:
  https://www.agentcomputer.ai/pricing).
- **DigitalOcean Managed Agents** — **UNVERIFIED this pass** (NOT a
  NO-CHANGE claim): the main docs page fetched fine (Public Preview;
  "Last verified 21 Sep 2026") but carries no pricing figures, and the
  Harness Runtime "Details" pricing sub-page link did not extract —
  the surveyor could not locate its URL without guessing, so this
  morning's C26 baselines ($0.044/vCPU-hour active CPU,
  $0.0095/GB-hour memory; the flagged **10× snapshot-rate discrepancy**:
  $0.05/GiB-month on docs vs $0.005 in the launch-release text) could
  not be re-checked on the vendor's own docs this run. **Standing
  facts unchanged at the THIRD-PARTY layer**: the BusinessWire release
  (Morningstar, 2026-09-22) still states $0.044/$0.0095 with snapshots
  at **$0.005/GiB-month** — consistent with the release-text side of
  the discrepancy. Next pass's ask: re-extract the pricing sub-page
  URL from the docs nav and re-verify both figures (the discrepancy is
  now the standing C26 watch item, not a one-time observation).

## 2. Vercel Drives GA watch — NO-CHANGE (eleventh consecutive)

The standing follow-up ask (does Drives move toward GA?) is answered in
the negative for the **eleventh consecutive pass** (2026-09-23):
`vercel.com/docs/sandbox/pricing` still shows `last_updated:
2026-09-10`, every baseline term verifies identical (Drive Storage 15
GB lifetime Hobby / $0.05/GB-month Pro+Enterprise; Reads 30 GB/mo then
$0.0015/GB; Writes 30 GB/mo then $0.004/GB; max 4 drives/run; default
1 TiB (1 GiB Hobby); 16 TiB max/drive; 64 GB ephemeral NVMe on SDK
≥3.0.0/custom image; session caps 45 min / 24 h; concurrency 10 /
10,000), and the changelog's Drives entry still reads verbatim
*"Drives for Vercel Sandbox are now available in public beta on Hobby,
Pro, and Enterprise"* — no GA date, no SLA terms, no GA language
(**VERIFIED**, pricing page re-read ~16:56, changelog re-read
~16:58–17:00 CDT). The vendor
changelog carries no entries dated 2026-09-23. **Provenance hygiene
note**: the prior pass's "09-23 re-date" of the Drives beta entry does
not hold this pass — the sitemap and the rendered changelog now both
date the entry 2026-09-22. The entry itself is stable; the date field
flipped again (re-publish, not a GA move — the same non-evidence
verdict as the prior date flips).

## 3. Market news — same-lane color, no in-lane launches

### 3a. Filestore agent volumes for AI (Google) — THIRD-PARTY pricing color, folded under C36

Surfaced this pass via itbrief.com.au (~Sep 19, **THIRD-PARTY**,
re-fetched and read by the author ~17:06 CDT —
https://itbrief.com.au/story/google-cloud-launches-filestore-agent-volumes-for-ai;
grep-clean across prior `agent_notes/`): Google Cloud has launched
Filestore agent volumes for AI agent workloads — managed isolated
per-agent persistent workspaces auto-allocated and attached in
milliseconds at sandbox start on GKE, working with Agent Substrate on
GKE and GKE Agent Sandbox, RW-many + POSIX locking for multi-agent
collaboration, non-production for now with production via allowlist.
This is Google's Drives-analogue landing in the GKE lane.

**Corpus fold (THIRD-PARTY layer, under C36):** the mechanics above
were already folded at the vendor level from Google's own Cloud-blog
announcement (C36 VENDOR-CONFIRMED: "optional Filestore agent volumes
(NFS/RWX/POSIX, ms attach)"). What this piece adds — and what the
vendor fold says nothing about — is the **pricing model**: pay-per-use
based on storage capacity consumed, with automatic lifecycle tiering
for inactive workspace data, framed explicitly as an idle-capacity
economics play (short-lived/intermittent agent sessions, many
dormant agents). That's a *pricing-model* fact on the corpus's core
competitive axis, folded at the THIRD-PARTY layer (press account,
not vendor docs — no vendor dollar figure exists yet). Recorded in
`docs/COMPETITOR_ANALYSIS.md` as a new bottom watch-update section.

### 3b. hdosys/herdr-sandbox (snippet-only)

A Windows-local coding-agent sandbox CLI surfaced in search results
(**snippet-only**): local-only, not a lane competitor. Clarifying
name note: this is a different "Herdr" from the Vercel Sandbox
*Herdr* plugin the morning watch tracked — no relationship. Noted for
completeness; no file.

### 3c. Explicit in-lane no-launch verdict

No new launches, GAs, pricing moves, or funding in this window for
Daytona, E2B, Docker, Vercel Sandbox, Microsandbox, boat.dev,
TermSquad, DigitalOcean Managed Agents, AgentComputerAI, Google Agent
Substrate/GKE, Boxd, Upstash Box, Runloop, Modal, Northflank, WSO2,
Herdr, Blaxel, or the OpenAI Agents API sandbox partners. The most
recent in-lane launch verdict stands: DO Managed Agents public preview
(already filed); Google Agent Substrate-on-GKE is VENDOR-CONFIRMED
(C36) and now baseline.

## 4. Carry-forward

- **C26**: mid-afternoon CLOSED C26 (pricing verified) and flagged the
  snapshot-rate discrepancy as the standing watch item (docs
  $0.05/GiB-month vs release text $0.005) — it is not a one-time
  observation. Next pass must re-extract the pricing sub-page URL from
  the docs nav and re-verify both figures on the vendor docs.
- **C29** (Boxd): no new facts this pass; watch continues.
- **C36**: vendor-confirmed; the Filestore agent volumes pricing model
  (pay-per-use capacity + automatic lifecycle tiering for inactive
  workspace data) is now folded at the THIRD-PARTY layer in the new
  "Watch update — 2026-09-23 (early-evening)" corpus section — no new
  C-number needed (the filing existed; only pricing color is new).
- **Drives GA watch**: eleventh consecutive no-change pass; keep
  watching.
