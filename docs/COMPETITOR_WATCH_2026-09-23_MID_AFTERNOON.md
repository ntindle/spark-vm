# Competitor watch — 2026-09-23 (mid-afternoon)

Delta-only update against the early-afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-23_EARLY_AFTERNOON.md`). Survey window
**2026-09-23 ~13:54 → 14:05 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the tracked set (reads ~13:56–13:59 CDT), (B) Vercel Drives GA watch
plus open-web market-news scan (~13:56–14:03 CDT). Surveyor captures
live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260923-1354.md`), not the repo. The C26 docs-pricing
read and the C30 vendor-post read were performed by the authoring turn
via live browser ~14:05–14:15 CDT, after the surveyor window.

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

## 1. The tracked set — fully quiet (8/8 NO-CHANGE, all VERIFIED)

Every baseline value from the EARLY_AFTERNOON pass (its ~12:57 CDT
vendor-page reads) verified identical on the vendor's own page,
reads ~13:56–13:59 CDT:

- **Daytona** — changelog top entry still **V0.216.0** (Sep 23 2026,
  "Confine Dockerfile COPY sources to the build context")
  (**VERIFIED**: https://www.daytona.io/changelog, ~13:56).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits, C34 corpus-folded) (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~13:56).
- **Microsandbox** — **v0.7.1** still the newest release (vendor repo
  /releases list page read directly — no v0.7.2)
  (**VERIFIED**: https://github.com/superradcompany/microsandbox/releases, ~13:56).
- **E2B** — pricing identical (Hobby FREE $100 one-time credit / Pro
  $150-mo / per-second usage rates unchanged)
  (**VERIFIED**: https://e2b.dev/pricing, ~13:57).
- **boat.dev** — pricing identical (small $0.018/h, default $0.036/h,
  large $0.072/h, xlarge $0.200/h; plans unchanged)
  (**VERIFIED**: https://docs.boat.dev/pricing, ~13:57).
- **TermSquad** — pricing identical (Starter $9 / Builder $19 / Power
  $29 / Ultra $49 per month; all always-on)
  (**VERIFIED**: https://termsquad.com/, ~13:58).
- **DigitalOcean** — droplet pricing identical (Basic Droplets $4–$96,
  per-second billing from Jan 1 2026, unchanged)
  (**VERIFIED**: https://www.digitalocean.com/pricing/droplets, ~13:58).
- **AgentComputer** — pricing identical ($0.07/CPU-hour,
  $0.04375/GB-hour memory)
  (**VERIFIED**: https://www.agentcomputer.ai/pricing, ~13:59).

Zero fetch failures this pass; no UNVERIFIED items.

## 2. Vercel Drives GA watch — still beta (tenth consecutive no-change pass)

The Drives pricing page reads identically to the early-afternoon pass
(**VERIFIED**: https://vercel.com/docs/sandbox/pricing, ~13:56 CDT):
`last_updated` still **2026-09-10**; terms unchanged ($0.05/GB-month
storage on Pro/Enterprise — 15 GB lifetime on Hobby; $0.0015/GB reads,
$0.004/GB writes; max 4 drives/run; 1 TiB default / 16 TiB max per
drive; downloads free; session caps 45min/24h; concurrency 10/10,000).
The changelog entry still reads "now available in public beta"
(https://vercel.com/changelog/drives-for-vercel-sandbox-are-now-in-public-beta,
~13:57 CDT) — **no GA movement**. Adjacent snippet-only: `@vercel/sandbox` CHANGELOG
4.4.0 adds Drives support — SDK packaging of the beta feature, not GA
evidence.

Sitemap-date caution (INFERRED, method note): the changelog sitemap
dated the beta entry 2026-09-22 on an in-between snippet crawl and
reads 2026-09-23 again on this pass's live read — the flip-flop
continues. The field's authoritativeness remains unproven, so no
inference is built on it either way. The no-change streak stands at
ten consecutive passes.

## 3. Market news (48h window)

### 3a. C26 CLOSED — DO Managed Agents pricing now VERIFIED on vendor docs

The vendor docs' Details/pricing sub-page was reached read-only this
run (**VERIFIED**: https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/,
"Last verified 22 Sep 2026"):

- CPU: **$0.044/vCPU-hour**, per-second on actual CPU consumed —
  footnote: "Active CPU billing is coming soon. Until then, you will
  be billed at 25% of the vCPUs allocated to your sandbox."
- Memory: **$0.0095/GB-hour** on peak memory used.
- Session storage (volumes): $0.05/GiB-month (peak). Public internet
  egress: $0.01/GiB. Custom sandbox templates (BYOT): $0.05/GiB-month.
- Sandbox shapes (full-allocation hourly): XSmall `mars-1vcpu-1gb`
  $0.0535/hr; Small `mars-2vcpu-2gb` $0.107/hr; Medium (default)
  `mars-2vcpu-4gb` $0.126/hr; Large `mars-4vcpu-8gb` $0.252/hr;
  XLarge `mars-16vcpu-32gb` $1.008/hr.
- Paused sessions incur no compute charges; retained checkpoints keep
  accruing storage charges while paused (including at $0 prepaid
  balance). Positive prepaid balance required; no per-session spend
  limit. Action Gateway tool calls (incl. Exa web search/fetch) need
  prepayment and draw the shared balance.

**Material discrepancy, flagged not folded:** the vendor docs price
snapshots/checkpoints at **$0.05/GiB-month** while the launch press
release (syndicated Business Wire) says **$0.005/GiB-month** — 10×
apart. CPU ($0.044) and memory ($0.0095) agree across both sources.
The corpus fold carries the docs figure with this caveat attached;
either the docs or the release is wrong. Next watch ask: re-check the
snapshot rate if the docs page is re-dated.

C26 is closed — the ask was vendor-docs dollar pricing, and we have
it. Corpus-folded (see `docs/COMPETITOR_ANALYSIS.md`, the new bottom
"Watch update — 2026-09-23 (mid-afternoon)" section, plus the retired
"OPEN — watch continues" qualifier on the C26 section header).

### 3b. C30 layer upgrade — OpenAI Agents API beta now vendor-confirmed

The public beta (announced 2026-09-10, per third-party coverage of the
vendor launch; the post body carries no visible date) is now confirmed on
OpenAI's own launch post — **VERIFIED** read on the vendor's own blog this
run (https://openai.com/index/introducing-the-agents-api/, ~14:15 CDT):
"Today, we're introducing the Agents API in public beta," naming nine
sandbox partners with first-class integrations: "Blaxel, Cloudflare,
Daytona, DigitalOcean, E2B, Modal, Oracle, Runloop, and Vercel" — so three
of the eight tracked vendors (Daytona, DigitalOcean, E2B) are
OpenAI-anointed sandbox providers. The
post also confirms the environment choice: "an OpenAI-managed sandbox,
on your own infrastructure, or with one of our sandbox partners."
Corpus-folded as a vendor-confirmation update on C30 (no new
C-number; the filing existed — only the provenance layer moved).

Separately, still rumor: the "Managed Agents" unveil at DevDay 2026
(Sep 29) — press/rumor only, no OpenAI vendor confirmation. The AWS
Bedrock "Managed Agents, powered by OpenAI" item is an April 28
limited preview — separate and older.

### 3c. New-to-watch: Google Agent Substrate on GKE (C36)

Previously unfiled, outside the 48h window (~Sep 17): Google's
open-source agent-sandbox runtime (Cloud Hypervisor microVMs or
gVisor; <500 ms resume; 500+ suspend/resume activations/sec; 1,000+
dormant agents/host; network gateway) is now offered to GKE customers
for non-production workloads, with production GA support via
allowlist; early design partner Nous Research (Hermes). The
open-source runtime predates this filing (a prior operator-side
evaluation; record outside this corpus) — the GKE packaging is the new
competitive angle.
**THIRD-PARTY** (itbrief.co.uk); vendor verification owed. Filed as
corpus-adjacent new-to-watch, not a tracked-provider row (hyperscaler
offering a sandbox runtime on its own substrate, not a standalone
agent-VM product). Corpus note added under C36.

### 3d. In-lane launches

**No new in-lane launches in the 48h window.** The DigitalOcean
Managed Agents public preview (2026-09-22) remains the newest in-lane
event and was already filed; nothing new has launched since. The
§3b/§3c items are vendor-confirmation and new-to-watch, not launches.

### 3e. Adjacent re-checks — no new facts

- **Automaid** — still no own-page launch announcement at
  automaid.it.com or elsewhere; coverage remains THIRD-PARTY-only
  (itbrief.asia, afritechbizhub; Medium account snippet-only, no
  launch post). Baseline holds.
- **Andon Pion** (launched 09-14) — no in-window movement; baseline
  holds (research-preview waitlist, Andonos overseers).
- **Huawei Open Agentic Cloud** — no new vendor product facts
  in-window. New THIRD-PARTY analyst takes (bytevyte on the "open"
  claim, reframed.co on enterprise-infra-over-models) plus one new
  detail from the same coverage: AICS commercially available in China
  Sep 30, global Nov 30. No new vendor facts.
- E2B / Daytona / Modal / Fly.io / RunPod / Brev — quiet in window.
- Borderline color: WSO2 Agent Manager GA (~Sep 20, open
  agent-governance control plane incl. sandboxed runtime — outside
  window, adjacent only); Upstash "AI Agent Sandboxes Compared: 15
  Providers" (~Sep 17, competitor-published cost table — color only).

## 4. Corpus folds this pass

- **C26 CLOSED + folded**: DigitalOcean Managed Agents pricing is now
  vendor-verified on the docs pricing page ($0.044 active-CPU vCPU-hour
  per-second once active billing ships; until then a 25%-of-allocated
  interim rate; $0.0095/GB-hour memory; shape table; pause semantics).
  The 10× snapshot-rate discrepancy ($0.05 docs vs $0.005 release)
  is carried as an explicit caveat, not folded as fact. The corpus
  fold is the new bottom "Watch update — 2026-09-23 (mid-afternoon)"
  section plus the retired "OPEN — watch continues" qualifier on the
  C26 section header.
- **C30 folded (layer upgrade)**: OpenAI Agents API public beta is now
  vendor-confirmed (OpenAI's own blog) — the corpus C30 section's
  provenance moves from third-party-archive to vendor-confirmed; the
  nine-partner list stands, unchanged.
- **C36 new**: Google Agent Substrate on GKE filed as corpus-adjacent
  new-to-watch (THIRD-PARTY, vendor verification owed).
- No other rows touched: 8/8 tracked providers NO-CHANGE, Drives still
  beta, Automaid/Andon/Huawei baselines hold.
Next pass's ask: routine tracked-set re-reads; Drives GA watch
continues (eleventh no-change pass incoming if quiet); re-check the DO
snapshot rate if the docs page is re-dated; vendor verification owed
on C36.
