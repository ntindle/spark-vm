# Competitor watch — 2026-09-25 (post midnight)

Delta-only update against the 2026-09-24 post-overnight pass
(`docs/COMPETITOR_WATCH_2026-09-24_POST_OVERNIGHT.md`). Survey window
**2026-09-25 ~00:56–01:05 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the full tracked set (Daytona changelog + pricing, Docker Sandboxes
release-notes page, E2B, boat.dev pricing, Microsandbox, TermSquad,
AgentComputer, DigitalOcean Managed Agents — news only); (B) the carried
asks (C26 docs-pricing miss, C37 Freestyle Pro fee, OpenAI Agents API
GA watch, C36/C41/C43/C44, Tensorlake) and an open-web in-lane news
scan dated 2026-09-25. Surveyor captures live in the loop's
`agent_notes/` workspace (`surveyor-tracked/a-20260925-0054.md`), not
the repo. `_POST_MIDNIGHT` is the first 2026-09-25 pass, admitted per
the 2026-09-23 `_LATE_NIGHT` / `_POST_MID_EVENING` / `_OVERNIGHT`
precedent family (verified collision-free against origin/main's
watch-doc list).

Evidence labels used by the watch passes: **VERIFIED** = read on a
vendor's own page, doc, or repo this run. **VENDOR-VERIFIED** =
confirmed on the vendor's own page, docs, or changelog read this run
(corpus field-table usage). **THIRD-PARTY** = press/third-party
sources. **snippet-only** = seen only via search snippet. **INFERRED** =
my characterization. **UNVERIFIED** = a public page exists but could not
be fetched this run (never reported as NO-CHANGE). **VERIFIED absent** =
the vendor's own page was read this run and the item is confirmed not
present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

Zero pricing/feature deltas across the whole set. **Zero fetch
failures** this pass — all 8 surfaces opened directly on vendor-owned
pages.

- **Daytona — VERIFIED NO-CHANGE** (changelog:
  https://www.daytona.io/changelog; pricing:
  https://www.daytona.io/pricing). Top 3 still: SEP 24 V0.216.1,
  SEP 24 V0.216.2, SEP 23 V0.216.0 — no new entries. GPU ladder
  unchanged (B300 $4.08/h preemptible down to RTX 4090 $0.57/h);
  compute $0.0504/vCPU-h, mem $0.0162/GiB-h.
- **Docker Sandboxes — VERIFIED NO-CHANGE** (release-notes page:
  https://docs.docker.com/ai/sandboxes/release-notes/). Still tops at
  **2026-09-21** (v3 kits); nothing dated 09-22 through 09-25.
- **E2B — VERIFIED NO-CHANGE** (https://e2b.dev/pricing). Hobby
  free + $100 one-time credit; Pro $150/mo; per-second vCPU ladder
  unchanged.
- **boat.dev — VERIFIED NO-CHANGE** (pricing:
  https://docs.boat.dev/pricing). $0.018/$0.036/$0.072/$0.200 sizes,
  $20/$100/$500/$2000 plans, 25h trial — verbatim. Product-news retry
  stays retired (VERIFIED absent ×3).
- **Microsandbox — VERIFIED NO-CHANGE**
  (https://github.com/superradcompany/microsandbox/releases). Latest
  still **v0.7.3**.
- **TermSquad — VERIFIED NO-CHANGE** (https://termsquad.com/pricing).
  $9/$19/$29/$49 verbatim (2/4/6/8 vCPU, 4/8/12/24 GB,
  40/75/100/200 GB NVMe); "AI subscriptions and usage are not
  included" still explicit.
- **AgentComputer — VERIFIED NO-CHANGE, digit-for-digit**
  (https://agentcomputer.ai/pricing). $0.07 CPU-hr, $0.04375 GB-hr,
  $0.000683 hot, $0.000027 cold; Enterprise custom.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE** (docs page:
  still public preview, "Last verified 21 Sep 2026", no newer
  heading). Press-side rates unchanged: vendor's Sept 22 investor
  release still $0.044/vCPU-hr, $0.0095/GB-hr, $0.005/GiB-month — no
  newer rate announcement found.

## 2. Corpus folds

- **C41 — repo HEAD pin REVERTED, not moved again; digits unchanged.**
  VENDOR-VERIFIED via GitHub API this run: the official repo's HEAD is
  now back at the pre-overnight pin — the short `39b6c3a2` is the same
  commit as the previously recorded
  `39b6c3a20ec4597cceda497a4d8badf5384e2022` (2026-09-21), so this is a
  **revert** from `96ff8a8`, not a second forward move. All pricing
  digits re-read live at HEAD and unchanged: Eco 0.00936/vCPU-h +
  0.004608/GiB-h, Std 0.01224 / 0.006012, Pro 0.01872 / 0.009360,
  disk 0.00031896 (0.00025308 ex-mainland). Preview notice still
  invite-only, allowlisted-in-batches. Field-table row updated to
  record the revert (no phantom third position).
- **C9 — THIRD-PARTY pricing color.** Hosted-sandbox containers
  **$0.03–$1.92 per 20-min session** (1 GB–64 GB); ZDR inapplicable
  even with a self-hosted sandbox (finance.biggo.com). The ZDR line
  corroborates the corpus's existing no-ZDR characterization
  (already filed). OpenAI Agents API itself: still public beta —
  THIRD-PARTY ×3 this pass quoting the platform changelog
  ("Released the Agents API in public beta") and `client.beta.agents`;
  GA absence stays VENDOR-VERIFIED (carried from the post-overnight
  pass).
- **New-to-watch candidate (not yet a corpus entry): Google AX
  v0.3.0.** THIRD-PARTY (HN-noted): open-source (Apache-2.0) agent
  orchestrator built on Agent Substrate. Primary-source pass owed
  before it earns a C-number.
- **Grunz — flag only.** $100-once self-hosted coding agent (harness
  lane, not sandbox-shaped). Filed for the record, no corpus entry.
- **Not filed:** a rumored "GKE Agent Migration Tool" Sep 25
  announcement surfaces only on cointime.ai — UNVERIFIED, single
  source; left out of the corpus deliberately.

## 3. Carried asks (unchanged)

- **C37 — Pro fee still UNVERIFIED.** freestyle.sh/pricing re-read:
  still no Pro dollar line-item on public surfaces ("monthly fee is
  a commitment that doubles as usage credit"); Hobby $50 minimum
  re-confirmed verbatim (VENDOR-VERIFIED). Dashboard-signed-in
  check still owed.
- **C26 — 6th consecutive standalone-pricing miss.** Only the
  syndicated Business Wire release surfaced (quotes the retired
  $0.005 snapshot figure); the "Last verified 22 Sep 2026" docs
  pricing page stays unlocated. The misattribution hypothesis stays
  INFERRED — deliberately not rewritten on absence-of-evidence.
- **Tensorlake — no Sep-24/25 news** (stale comparison aggregators
  only; re-open stays owed). C46 pricing baseline stands.
- **C44 — VENDOR-VERIFIED unchanged** (newest release-note heading
  still September 22, 2026; Sep-9 sandboxes-GA and Sep-1
  metering-in-effect entries intact).
- **C36 — confirmed unchanged** (Cloud Blog text consistent with
  filed claims — 10x density, sub-500ms resume, Nous/Hermes).
- **C43 — confirmed unchanged** ("not billed during the preview
  period" verbatim present; page "Last updated 2026-09-24 UTC").
- **Vercel Drives** not re-checked (P49 once-daily morning cadence).
  **boat.dev product-news** retry stays RETIRED.
- **In-lane dated 9/25: no launches, no pricing moves, no funding
  rounds in-window** beyond the Google AX candidate and the Grunz
  flag above. DO Managed Agents writeup wave carries no new facts.

## 4. What this means for spark-vm

Nothing in this pass changes the product read: the tracked
sandbox-pricing floor is flat again (8/8), the Alibaba pay-as-you-go
preview's repo HEAD **reverted** to the pre-overnight pin
(`96ff8a8` → back to the same `39b6c3a…` commit, digits frozen —
the "second move" is a same-commit revert, disclosed as such), and
the lane's net-new energy is in orchestration tooling (AX v0.3.0)
rather than new sandbox product. Watch items for the next passes:
Google AX primary-source read, C37 signed-in dashboard check, C26
docs page (7th attempt).
