# Competitor watch — 2026-09-23 (mid-evening)

Delta-only update against the early-evening pass
(`docs/COMPETITOR_WATCH_2026-09-23_EARLY_EVENING.md`). Survey window
**2026-09-23 ~17:55–18:15 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set, (B) Vercel Drives GA watch plus Boxd/C36 checks plus an
open-web market-news scan. Surveyor captures live in the loop's
`agent_notes/` workspace (`surveyor-a/b-20260923-1754.md`), not the repo.

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

## 1. The tracked set — one material change (7/8 VERIFIED NO-CHANGE, 1/8 VERIFIED CHANGE)

All reads within the survey window; all values below VERIFIED on the
vendor's own page unless noted:

- **Daytona** — VERIFIED NO-CHANGE: changelog still topped by
  **SEP 23 2026 / V0.216.0** ("Confine Dockerfile COPY sources to the
  build context" — Python, Ruby, TypeScript SDKs); no new entry today;
  V0.215.0 (SEP 22) still second. (https://www.daytona.io/changelog)
- **Docker Sandboxes** — VERIFIED NO-CHANGE: release notes still top out
  **2026-09-21** (v3 kits).
  (https://docs.docker.com/ai/sandboxes/release-notes/)
- **Microsandbox** — VERIFIED NO-CHANGE: top release still **v0.7.1**
  (npm provenance + flush-policy patch series).
  (https://github.com/superradcompany/microsandbox/releases)
- **E2B** — VERIFIED NO-CHANGE: per-second vCPU table still tops
  **$0.000014/s** (1 vCPU); tiers unchanged (Hobby FREE + $100 one-time
  credit, Pro $150/mo + usage, Enterprise custom). (https://e2b.dev/pricing)
- **boat.dev** — VERIFIED NO-CHANGE: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h** (xlarge needs a
  $100 plan or higher); "A stopped sandbox costs nothing"; trial still
  25 free hours. (https://docs.boat.dev/pricing)
- **TermSquad** — VERIFIED NO-CHANGE: Starter **$9/mo** (2 vCPU / 4 GB),
  Builder **$19/mo** (4 / 8), Power **$29/mo** (6 / 12), Ultra
  **$49/mo** (8 / 24 / 200). ("Every feature, on every plan"; AI
  subscriptions/usage not included.)
- **AgentComputer** — VERIFIED NO-CHANGE: $0.07 per CPU-hour,
  $0.04375 per GB-hour memory, $0.000683 / $0.000027 per GB-hour
  hot/cold storage; Enterprise custom tier present.

### 1b. DigitalOcean Managed Agents — VERIFIED CHANGE (pricing docs URL now fetchable)

The pricing docs URL that was UNVERIFIED last pass fetched cleanly this
run (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/
— the page carries a "Last verified 22 Sep 2026" stamp). CPU
($0.044/vCPU-hour) and memory ($0.0095/GB-hour) VERIFIED against the
corpus. Two deltas vs the corpus:

- **The 10× snapshot-rate discrepancy resolves on the primary source.**
  The docs page still bills snapshots/checkpoints at **$0.05 per GiB-month**
  and still carries the "Last verified 22 Sep 2026" stamp (the page was
  UNVERIFIED last pass; the mid-afternoon pass read it live and carried
  the discrepancy as a caveat). So: the docs figure stands, and the
  corpus's $0.005/GiB-month syndicated-release figure is retired. Corpus
  fold in `docs/COMPETITOR_ANALYSIS.md` below (C32 precedent).
- **CPU-billing footnote re-verified.** "Active CPU billing is coming
  soon. Until then, you will be billed at 25% of the vCPUs allocated to
  your sandbox. Paused sessions incur no compute charges." — already
  folded at mid-afternoon; what this pass changes is the *per-entry
  paragraph's* "zero while waiting" framing, now explicitly qualified:
  zero holds only for paused sessions; a waiting-but-live sandbox costs
  25% of allocation until active-CPU metering ships. C14 input
  discipline: DO's headline rate is aspirational until the metering
  arrives.

Also re-verified on the docs page this pass (already folded at
mid-afternoon, confirmed again live): CPU $0.044/vCPU-hour, memory
$0.0095/GB-hour, session storage (volumes) $0.05/GiB-month (peak),
BYOT templates $0.05/GiB-month, public egress $0.01/GiB, positive
prepaid balance required with no per-product spend limit, sandbox
shapes mars-1vcpu-1gb through mars-16vcpu-32gb.

## 2. Vercel Drives GA watch — NO-CHANGE (12th consecutive pass)

Pricing page VERIFIED (https://vercel.com/docs/sandbox/pricing):
`last_updated: 2026-09-10` (unchanged); the related-links block still
carries the entry title "Drives for Vercel Sandbox are now in public
beta" — no GA language anywhere on the page; rates and limits identical
to baseline. Changelog VERIFIED (https://vercel.com/changelog, full
read): newest entries dated **2026-09-22** (GPT-6 Sol/Luna and Claude
Opus 5.5 on AI Gateway, Vercel Connect → Microsoft Teams, billable
duration + CPU minutes in deployments, MiMo V2.6, TypeSafe clients +
HTTP API for Jev); **no entries dated 2026-09-23**; nothing mentioning
Drives or Sandbox GA. Drives remain public beta.

## 3. Adjacent vendors — quiet

- **Boxd (C29)** — rate card unchanged on the vendor FAQ (verbatim):
  "€0.049 per vCPU-hour while a machine runs, €0.015 per GiB-hour of
  RAM it actually has resident while running or in standby, and
  €0.0001 per GiB-hour of disk you have written to"; "Every new
  account starts with €30 of free credits." VERIFIED: https://boxd.sh.
  Docs pricing page UNVERIFIED this pass (tool-side fetch failure —
  the raw docs URL itself 404s for automated fetchers this pass, so it
  is not link-checked; no change implied); docs.boxd.sh/quickstart
  re-read clean and consistent with prior folds (machines, forks in
  under 200 ms, snapshots, checkpoints, MCP server install, self-hosted).
  No new funding or product announcements (`since=2026-09-01` search —
  the €2M pre-seed remains the latest item).
- **Google Agent Substrate on GKE (C36)** — no new vendor or press
  datapoints since the 16:00 CDT vendor-confirm fold; search
  (`since=2026-09-23`) surfaced only the known items (Cloud-blog
  announcement, itbrief.co.uk coverage, itbrief.com.au Filestore piece
  already folded).

## 4. In-lane news scan — no launch / GA / funding / pricing move in-window

Open-web scan over ~15:55–18:00 CDT: nothing new in-lane. Results were
all pre-window (DO "Managed Agents" public preview 2026-09-22 and the
Baseten × Blaxel acquisition are already folded; OpenAI Agents API
public beta already known). No tracked vendor moved today.

## Corpus fold

One corpus action this pass (primary-source-verification fold, C32
precedent; full pass record in this doc §1b): `docs/COMPETITOR_ANALYSIS.md`
bottom watch-update section "## Watch update — 2026-09-23 (mid-evening):
C26 discrepancy resolved on vendor docs" — the C26 field-table row's
$0.005/GiB-month snapshots figure is replaced by the **$0.05/GiB-month
VERIFIED** vendor-docs figure (page last verified 2026-09-22); the
per-entry paragraph's "zero while waiting" read is qualified by the
re-verified active-CPU-billing footnote (already folded mid-afternoon —
25% of allocation until active billing ships; paused sessions free);
the mid-afternoon fold's storage/egress/BYOT/prepaid/shape figures are
re-verified live and carried forward.
