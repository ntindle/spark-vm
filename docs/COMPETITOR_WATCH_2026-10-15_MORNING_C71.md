# Competitor watch — 2026-10-15 (morning, cycle 71)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-70 baseline —
**17 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 1 UNVERIFIED** (21 opens /
19 first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 12th consecutive cycle — recovery declined per the
standing rule) / 1 transport failure (Hugo advisories page, empty
response body on HTTP 200 — NOT retried by the surveyor; the integrator
re-read it successfully during the watch and downgrades this item to
VERIFIED NO-CHANGE, see below) / 12 URL-recovery searches, never used
as evidence). The A-lane delta is sitemap bookkeeping only (Vercel
changelog dated sitemap 1411 → 1413; two new non-sandbox entries) — no
sandbox-adjacent novelty. Surveyor B: delta news scan —
**0 CANDIDATES / 15 clean dedupes / 20 flagged-only** (15 searches, 15
successful / 0 failed, 1 page opened — the Perplexity SPACE routing
post, opened to rule out the tracked SPACE Part II; it is not Part II,
and it is this cycle's strongest in-window first-party item, filed as
C84 below). **C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still in
talks); C76 NOT advanced; C77 NOT advanced. **Corpus move this cycle:
2 new filings (C84, C85), 2 folds (3 folded items), watch-doc
deltas.** Captures:
`hidden_files/agent_notes/surveyor-a|b-20261015-0910.md` +
`hidden_files/agent_notes/integrator-reads-20261015-0910.md` (the
integrator's E2B Secrets, Agent37 pricing-blog, and Hugo-advisories
full-page reads — provenance for the VENDOR-VERIFIED claims no
surveyor capture covers). Loop working notes, in the goal workspace
— not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-15 ~09:1x–~10:4x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (17
> VERIFIED NO-CHANGE, 1 DELTA, 1 UNVERIFIED) reconciles exactly with
> its 18 item enumerations and its fetch stats (19 successful fetches
> + 1 established 404 + 1 transport-failure open = 21 opens; the 4b
> second render is one of the 19 successful fetches, and the Hugo
> empty-body fetch is the transport-failure open). The
> integrator's Hugo advisories re-read (this cycle, successful,
> single first-try fetch) resolves the UNVERIFIED item to VERIFIED
> NO-CHANGE — the effective A-lane score is 18 VERIFIED NO-CHANGE, 1
> VERIFIED DELTA, 0 UNVERIFIED. Surveyor B's capture enumerates
> exactly 0 candidates + 15 dedupes + 20 flagged-only, reconciling
> with its header and search stats. Corpus-number integrity: last
> issued C-number C83; this cycle issues C84, C85 — exactly two
> forward.

## Corpus moves: filings + folds

**(C84) Perplexity — "How SPACE routes requests to the right sandbox
execution" — new filing, VENDOR-VERIFIED (adjacent/research).**
First-party perplexity.ai hub blog post (published 2026-10-14 per the
blog index, opened and read in full this cycle): a deep-dive on
SPACE's signed execution-identity routing. SPACE binds each request
to the right sandbox execution with identity checks and signed
routes: short-lived Ed25519 capabilities binding sandbox / execution /
placement; bridge endpoint verification over VSOCK to `spaced-guest`
inside the Firecracker microVM; stream epoch binding across resume.
Routing passes through `node-api` → `sbx-manager` → Unix socket →
`spaced-host` bridge → VSOCK → `spaced-guest`. Stated reliability:
"millions of executions per day, each protected by a unique
cryptographic identity, with an error rate below 0.0002% and zero
dropped connections." The post's "Industry comparison" section
(implementations checked October 8, 2026) makes substantive
cross-vendor security claims: NVIDIA OpenShell has comparable
execution-selection binding; E2B's inbound proxy "selects the logical
sandbox and port without an expected execution identity for receiver
comparison"; CubeSandbox repairs routes on resume but lacks
per-incarnation expected identity. **This is NOT the tracked SPACE
Part II** (no Part II label; the C54 "Escaping SPACE: Part I" row
was the red-team evaluation — this is the routing-design companion
piece; Part II stays unmet). spark-vm relevance: the closest public
design doc for per-incarnation execution identity on a production
sandbox fleet — directly comparable to spark-vm's own sandbox
routing/session-resume design; the stale-placement / snapshot-resume
misrouting problem class is one the hosted lane's phone-home and
session semantics must rule out.

**(C85) E2B Secrets — launched October 7, 2026 — new filing,
VENDOR-VERIFIED.** First-party e2b.dev resources/product page (read
in full this cycle): "E2B Secrets keeps credentials outside the
sandbox and injects them into the HTTPS request headers you
configure, so agents can call external services safely." Dated
October 7, 2026; pre-window but never folded (resolves the
cycle-70/71 B-lane flag). Filed per the C74 precedent (named
capability launch on a tracked vendor surface). The same read also
surfaces **E2B Embed** (September 30, 2026, first-party): "packages
the runtime and dashboard for one machine. Ship it with your product
and run sandboxes inside your customer's environment" — a
customer-environment packaging SKU adjacent to spark-vm's
self-hosted distribution story; noted, not separately filed.
spark-vm relevance: a sixth convergent credential-brokering datapoint
(credentials held outside the sandbox, injected at request time —
the same shape as spark-vm's host-side credential proxying);
the Secrets model is documented for spark-vm's secrets-posture
comparison.

**Agent37 fold — founder-published 15-provider pricing comparison
(VENDOR-VERIFIED, first-party agent37.com blog post, read in full
this cycle; folded into the C82 row, no new C-number).** "Sandbox
Pricing 2026: Cheapest Sandbox for AI Agents" (blog index "Last
Updated: 4 days ago"; provider pricing pages checked October 10,
2026): the same 2 vCPU / 4 GB RAM workload costs $4.76–$248.78/mo
across 15 providers. Full 730-hour row: Agent37 **$4.76**, Hetzner
$6.49 (marked unavailable at check), Northflank $48.66, AWS EC2
$55.85, Morph $73.00, Fly.io Sprites $120.09, Daytona $120.89, E2B
$120.89, Blaxel $120.89, Hopx $120.89, Cloudflare Sandbox $145.28,
Beam $165.83, Modal $173.71, Runloop $231.26, Vercel Sandbox
$248.78. Agent37's own rate anatomy: $0.80/vCPU + $0.70/GB RAM +
$0.09/GB disk per 730-hour month (2×$0.80 + 4×$0.70 + 4×$0.09 =
$4.76 for 730 running hours; 62h model ≈$0.73; stopped-all-month
disk ≈$0.36); performance instances cost 4x compute ($17.96/730h).
New provider names sighted in this third-party/Agent37-authored
comparison (flagged-only, NOT corpus rows): **Hopx** (matches E2B's
rates to the digit — $0.000014/vCPU-second, $0.0000045/GiB-second),
**Beam** (physical-core pricing: $0.0000375/physical-core-second —
one physical core = two vCPUs), **Tenki** ($120.89 — matches E2B's
rates to the digit; "left out of the chart until their pricing has
a longer track record"), **Prime Intellect** (launch pricing through
December 22, 2026: $65.70 for the baseline — consistent with the
C48 corpus row's promo-expiry note). spark-vm relevance: the
richest third-party-checked sandbox price ladder in the corpus to
date; the Agent37-per-sandbox unit economics ($0.37/mo customer
average at C82) now have a fully-worked rate table behind them; the
hosted lane's cost story keeps its cheapest-corpus-positioning
anchor against this 15-provider ladder.

**E2B row fold — Secrets + Embed (VENDOR-VERIFIED, same first-party
read as C85; folded per the C32 primary-source-verification fold
precedent; no new C-number beyond C85).** The E2B corpus row gains:
E2B Secrets (October 7, 2026 launch — credentials kept outside the
sandbox, injected into configured HTTPS request headers) and E2B
Embed (September 30, 2026 — runtime + dashboard packaged for one
machine, sandboxes inside the customer's environment). The Secrets
launch is the C85 filing; the Embed launch is folded detail, not a
separate filing.

**Watch-doc delta — Vercel changelog sitemap 1411 → 1413.** The
2026-10-14 section carries two non-sandbox entries ("Amazon S3 joins
the Vercel Marketplace"; "Nemotron 3.5 Lightning now available on AI
Gateway for free"); the 2026-10-13 / 2026-10-12 / 2026-10-08
sections unchanged; the sandbox-adjacent "Vercel Sandbox creation
now returns a ready sandbox" (2026-10-08) still present, unchanged;
**no Drives GA entry anywhere in the dated index**; the public-beta
entry is still dated 2026-09-23.

**Watch-doc delta — Hugo advisories re-verified (resolves the
A-lane UNVERIFIED).** The surveyor's transport failure (empty
response body on HTTP 200, not retried per instruction) left the
item UNVERIFIED; the integrator re-read the first-party advisories
page this cycle (single first-try fetch, successful): top entry
still GHSA-r73q-gwx2-fpxm ("Theme-defined module.replacements
bypass mount restrictions and widen the Node.js read sandbox"),
published Oct 13, 2026, Moderate; the four Sep-28 advisories
(GHSA-3jfr-vjcq-7jvf, GHSA-r4xx-89rf-5424, GHSA-6c8w-mpp8-9w47,
GHSA-wcpj-vcvm-j4pg) sit below in baseline order; 10 entries
total; **no "100690" anywhere** — CVE-2026-100690 remains
third-party-only; file on first-party GHSA only.

## Gates (unchanged)

- **C11 FILE ON CLOSE — NOT triggered.** Modal arm already filed
  (C80, cycle 70); Baseten ~$26B still framed as in-talks
  ("reportedly discussing"; "have not produced completed rounds").
  Arm stays armed.
- **C76 — NOT advanced.** No CVE, no full technical write-up, no
  patch as of October 13, 2026 (tech-insider.org FAQ, deafnews.it
  restatement). VerCellBreak (TL-2026-3425) stays a distinct
  third-party-only item: ACTIVE status, 0 CVEs referenced; "Vercel
  confirmed the vulnerability... but stated it does not yet have a
  patch and that remediation is technically complex."
- **C77 — NOT advanced.** Strands Box still developer preview,
  macOS Apple-silicon only; AgentCore/ECS/Kubernetes deployment
  "planned"/"future goals"; no new repo release.
- **C12 — OPEN (71st consecutive first-party read).**
  AgentComputer still publishes no egress pricing line.
- **Modal egress billing — EFFECTIVE 2026-10-01**, live-in-effect
  per the C58 effectiveness grade; tracked fields still verbatim;
  no went-live banner; first bill including egress still postured
  for November 1, 2026.
- **Vercel Drives GA — standing tracked, unmet.** No GA language
  on any first-party page this cycle. Observation carried for the
  next cycle: the Sandbox docs Features-list link label now renders
  as "Drives" without the "(beta)" qualifier present in the C70
  capture (front matter `last_updated: 2026-09-22` and the feature
  description unchanged; the related-pages block still links "Drives
  for Vercel Sandbox in Private Beta") — not folded, re-check next
  cycle.

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C76 — CVE / write-up /
patch disclosure; VerCellBreak first-party/CVE movement; Perplexity
SPACE Part II (distinct from this cycle's C84 routing piece);
Strands Box follow-through; Vercel Drives GA (+ the "(beta)" label
rendering re-check); Hugo CVE-2026-100690 third-party-only; NanoCo
re-grade (the NanoClaw+Eco PRNewswire syndication sighted this
cycle carries an unverified date — no re-grade bar met); AgentCore
SDK CVEs — any NEW AWS advisory beyond 2026-127-AWS; Modal VM
Sandboxes GA progression; Docker $250 Agent Challenge (through
2026-10-31); Microsoft Execution Containers follow-through since
the C78 filing; new provider names from the Agent37 ladder
(Hopx / Beam / Tenki) — file on first-party vendor material only;
surveyor timestamp-honesty rule in force.
