# Competitor watch — 2026-10-14 (morning, cycle 70)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS + C11 NAMED-EXCEPTION
FILING.** Surveyor A: first-party vendor re-verification against the
cycle-69 baseline — **16 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0
UNVERIFIED** (20 opens / 19 first-try fetches / 0 retries / 1
established 404 (`boat.dev/pricing`, 11th consecutive cycle — recovery
declined per the standing rule) / 8 URL-recovery searches, never used
as evidence). Surveyor B: delta news scan — **0 CANDIDATES / 16 clean
dedupes / 25 flagged-only** (15 searches, 15 successful / 0 failed, 0
page opens — no fold-gate candidate) **+ C11 FILE-ON-CLOSE TRIGGERED on
Modal** ($750M Series D closed, first-party announced 2026-10-14).
**Corpus move this cycle: 4 new filings (C80, C81, C82, C83), 1 fold,
1 watch-doc delta.** Captures:
`hidden_files/agent_notes/surveyor-a|b-20261014-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-14 ~09:4x–~11:3x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTAs, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations and its fetch stats (19 successful fetches
> + 1 established 404 re-confirmation = 20 opens; 8 URL-recovery
> searches used for navigation only). Surveyor B's capture enumerates
> exactly 0 candidates + 16 dedupes + 25 flagged-only, reconciling with
> its header and search stats. Corpus-number integrity: last issued
> C-number C79; this cycle issues C80, C81, C82, C83 — exactly four
> forward.

## Corpus moves: filings + fold

**(C80) Modal $750M Series D — CLOSED, new filing, VENDOR-VERIFIED.**
First-party modal.com blog "Modal crosses $1B in Annualized Run Rate
and raises $750M Series D" (published 2026-10-14, page opened and read
in full): "we've raised a $750M Series D at a $15.75B post-money
valuation. Accel led the round. Kleiner Perkins joined, and all of
our existing investors participated, including Menlo Ventures, General
Catalyst, Redpoint, Lux Capital, Amplify Partners, and Bain Capital
Ventures." Corroborated by Axios (Chris Metinko) via Techmeme
2026-10-14 ("raised a $750M Series D led by Accel at a $15.75B
post-money valuation, taking its total funding to $1.2B"). This is
the **C11 FILE ON CLOSE gate firing on the Modal arm** — the
September talks are a closed round; the Baseten ~$26B arm remains
unclosed ("Neither round has closed"). spark-vm relevance: the
highest-funded direct sandbox competitor just tripled its valuation
in four months ($4.65B at the May $355M raise per third-party reporting already in the corpus row) on
sandbox-adjacent revenue growth — pricing and feature velocity
pressure on every sandbox vendor, including spark-vm's hosted lane.

**Modal fold — Series D blog first-party figures + VM Sandboxes GA
language (VENDOR-VERIFIED, folded into the Modal corpus row per the
C32 primary-source-verification fold precedent; no new C-number
beyond C80).** The same 2026-10-14 first-party blog carries new
scale figures: Modal "recently crossed $1B in annualized run rate"
(15x year-over-year; usage tripled since the Series C five months
ago); Sandboxes are "a $300M run rate product just on its own"; "close
to 3 billion sandboxes" spun up, scaling to "a million concurrent".
**GA-language bar advanced:** the blog states "With Sandboxes,
virtual machines are now generally available" — the 2026-10-13
"Runtime Roundup" blog (C69 fold) carried no explicit GA language for
VM Sandboxes; this one does, so the corpus isolation table's
"launched product" note graduates to first-party GA. Also
first-party-confirmed in the same post: multi-node training launched
("one decorator gives you a fully RDMA-connected cluster"; confirms
the Oct 7–9 Runtime keynote items) and Sandbox Sidecars shape
unchanged.

**(C81) Vercel Sandbox — "creation now returns a ready sandbox"
— new filing, VENDOR-VERIFIED.** First-party dated Vercel changelog
sitemap + index (read in full): the 2026-10-08 entry "Vercel Sandbox
creation now returns a ready sandbox". Sandbox-adjacent capability
refinement, filed per the C74 precedent (sandbox-adjacent changelog
entry). **Provenance note:** this entry was recorded in the C66 docs index
(Oct-8 dated section, six entries — recorded, not filed) but absent
from the C69 baseline's dated index — either removed and re-added, or
the C69 sitemap read missed it; it is absent from the corpus table as
recorded. spark-vm relevance: ready-on-create positioning —
Vercel is competing on sandbox creation latency / ready state, the
same startup-latency axis spark-vm's own fast-start story targets.

**(C82) Agent37 (YC F26) — new filing, FOUNDER-ATTESTED.** The B lane
flagged the founder's own Launch HN post; reconciled in A-lane (page
opened and read in full): Vishnu's launch post
(`news.ycombinator.com/item?id=50059096`, 2026-10-12) — "I'm Vishnu
from Agent37 (https://agent37.com). We build sandboxes for running AI
agents at under 10% of the cost of most sandbox providers." Stated
unit economics: customers average **$0.37/month per sandbox**; free
plan offered; free-sandbox infra cost $0.05–$0.10/user/month. Cost
levers (founder's words): burst-aware CPU/RAM management, hosts on
Hetzner/OVH instead of hyperscalers, gVisor for utilization + fast
boot (tradeoff stated: gVisor sandboxes don't support Docker-in-Docker
or Android emulators), RAM-optimized host sizing; full VM sandboxes
for Docker workloads at a higher price. This resolves the C69
"third-party-only, thin provenance" grading (which had only the
dev.to piece) — the founder's own words clear the provenance bar.
Launch date 2026-10-12 is pre-window for this slot; filed as an
A-lane reconciliation per the B-lane flag. spark-vm relevance: a
cost-optimized sandbox entrant publishing explicit per-sandbox unit
economics — the cheapest stated sandbox cost in the corpus, a pricing
data point for spark-vm's hosted-lane cost story.

**(C83) AWS security bulletin 2026-073-AWS — new filing,
VENDOR-VERIFIED.** The B lane flagged this pre-window first-party
bulletin as "likely already in corpus" — it was not (corpus grep
negative), so it is reconciled and filed here. First-party AWS
security bulletin detail page (opened and read in full): bulletin
2026-073-AWS (Important, published 2026-08-04 10:00 AM PDT) covers
**CVE-2026-18830** — insufficient input validation in the Amazon
Bedrock AgentCore harness InvokeHarness API: "an authenticated user
[could] execute configured tools while bypassing model invocation and
associated security controls" — when the most recent message in an
InvokeHarness request contained a tool-use content block, the agent
event loop dispatched the named tool directly, without model
mediation. Impact limited to the tools configured on the harness.
Impacted: InvokeHarness API prior to July 31, 2026. Resolution:
server-side input validation rejecting caller-supplied tool-use
content blocks in the final message; fully addressed in the
AWS-managed service; no customer action required. Reported by Aviyam
Ivgi and Hedi Ingber (coordinated disclosure). Third-party trackers
rate it CVSS v4.0 8.6 (The Hacker News recap). spark-vm relevance:
the model-bypass tool-dispatch hazard class — a harness must never
dispatch tools on caller-supplied tool-use blocks without model
mediation; swapd's boundary posture treats all harness inputs as
untrusted by construction.

## A-lane delta (watch-doc delta, not a filing)

**Hugo GHSA-r73q-gwx2-fpxm — new top advisory** (first-party
gohugoio advisories page, read in full): "Theme-defined
module.replacements bypass mount restrictions and widen the Node.js
read sandbox" (published Oct 13, 2026, Moderate). The 4 Sep-28
advisories move to positions 2–5 in the page's baseline order. No
"100690" anywhere on the page — CVE-2026-100690 remains
third-party-only (file on first-party GHSA only). Recorded as a
tracked-list change; not a competitor move.

## B lane (0 candidates; C11 TRIGGERED)

**C11 FILE ON CLOSE — TRIGGERED on Modal** ($750M Series D closed,
first-party modal.com announcement 2026-10-14, Axios/Techmeme
corroborated — filed as C80 above). **Baseten ~$26B — still unclosed**
(analyticsinsight recrawl: "Neither round has closed, and the funding
amounts remain undisclosed").

**Clean dedupes (16):** C11 Baseten (no close); C76 Vercel KVM
zero-day (no CVE, no write-up, no patch, no confirmed exploitation as
of October 13, 2026 — gate still open; the VerCellBreak disclosure
below is a distinct mechanism, not an advancement); C77 Strands Box
(still developer preview, macOS Apple-silicon only; AgentCore/ECS/K8s
deployment "future goals"); DO Agent Droplets (Oct-1 launch recrawls
only, public preview posture); Vercel Drives (no GA language —
public beta stands); Daytona (no in-window vendor news newer than
V0.224.0); E2B (third-party noise only); Docker Sandboxes (Sept-24
launch color only); Modal egress billing (no went-live signal —
first-party re-confirm remains Surveyor A's lane; verbatim); Zenity
"AgentCorruption" (AWS still disputes characterization; Zenity says
fully mitigated, no account-boundary crossing — unchanged from C68);
OpenAI training-agent DNS-escape (pause holds; the affected run is
"permanently discontinued"; no resume date); Perplexity SPACE (Part I
only; "Part II will explore the models' attack strategies in greater
detail" — still upcoming); NanoCo (March-vintage coverage only —
re-grade bar still unmet); Hugo CVE-2026-100690 (no sightings this
pass — still third-party-only); AgentCore SDK CVEs (recaps restate
the BeyondTrust Sept-28 pair and the C79 2026-127-AWS pair; no NEW
AWS advisory this pass); Modal multi-node clusters GA (first-party
confirmation again in the Series D blog — dedupe against the
corpus fold).

**Flagged-only (25):** VerCellBreak / TL-2026-3425 — NEW in-window
third-party security disclosure (AIR Security, first published
2026-10-13): an AIA-extension certificate-validation-chain technique
exfiltrating data from Vercel Sandbox despite domain allowlists
(compromised agent embeds stolen data in the Authority Information
Access URL of a crafted client certificate; the allowlisted server
fetches it during chain validation); Vercel classifies it as
longstanding, no patch yet, no CVE, no in-the-wild exploitation.
Third-party-only (deafnews.it, threadlinqs) — flagged-only, NOT a
C76 advancement (different mechanism); watch for first-party/CVE
movement. tomtunguz 2026 Theory AI Survey — sandbox share among 259
teams writing code with agents: Cloudflare 62%, Vercel 17%, Modal
16%, E2B 12%, Daytona 9% (third-party survey — adjacent color).
Anthropic Model Hardware Standard (MHS) research preview (adjacent,
robotics). Vercel vgpu open-source (adjacent, WebGPU). Google
EnvHarness (Apache-2.0, research-adjacent). Cloudflare Dynamic Workers
open beta (third-party coverage of a first-party beta — A-lane may
verify GA progression). plimsoll Show HN (third-party micro-launch —
thin provenance). Agent37 (reconciled in-lane this cycle — filed as
C82). Daytona clients v0.224.0 (2026-10-12, per-call region
selection + Python async-PTY fix — pre-window, reconciled against
the A-lane V0.224.0 read; no new corpus content). AWS bulletin
2026-073-AWS (reconciled in-lane this cycle — filed as C83).
Perplexity SPACE Part II (still unsighted). OpenAI DNS-escape resume
outcome (still no date). Strands Box follow-through (still preview).
AgentCore SDK CVEs — any NEW AWS advisory beyond 2026-127-AWS
(none). NanoCo re-grade (still needs first-party material). Hugo
CVE-2026-100690 (third-party-only). Vercel Sandbox minor incident
Oct 6 (carry). Docker $250 Agent Challenge (through 2026-10-31).
Docker Sandbox Kit CNCF spec (plan, not news). Alleged Vercel
dark-web credential sale (UNCONFIRMED). Modal July compromise
(resolved/watch-only). Modal VM Sandboxes GA + Sidecars (folded
above). Microsoft Execution Containers 1.0 GA (C78 filed; no new
news this pass). devops-daily unverified GA claims ("Google Agent
Runtime GA" / "Microsoft Foundry hosted agents GA" —
third-party-only).

## Standing-item state

- **C11 FILE ON CLOSE — Modal arm FILED (C80, closed 2026-10-14);
  Baseten ~$26B arm still armed** (still unclosed).
- **C12 — OPEN (70th consecutive first-party read).**
  AgentComputer publishes no egress pricing line.
- **C76 gate (CVE / technical write-up / patch disclosure) — NOT
  advanced.** No CVE, no write-up, no patch as of October 13, 2026.
  (VerCellBreak is a distinct mechanism — not an advancement.)
- **C77 Strands Box — filed, no movement** (no post-preview repo
  release, GA, or AgentCore follow-through).
- **C78 Microsoft Execution Containers — filed, no movement.**
- **C79 AWS bulletin 2026-127-AWS — filed, no movement.**
- **C80 Modal Series D close — filed this cycle** (vendor-verified,
  2026-10-14).
- **C81 Vercel "ready sandbox" changelog entry — filed this cycle**
  (vendor-verified, dated 2026-10-08).
- **C82 Agent37 — filed this cycle** (founder-attested, launch
  2026-10-12).
- **C83 AWS bulletin 2026-073-AWS — filed this cycle**
  (vendor-verified; pre-window 2026-08-04, reconciled from the B
  lane).
- **Modal egress billing — EFFECTIVE 2026-10-01.** First-party page
  tracked fields verbatim; first bill including egress still
  postured for November 1, 2026.
- **Vercel Drives GA — standing tracked, not filed.** No GA language
  on any first-party page (private-beta page, public-beta page,
  sandbox docs `last_updated: 2026-09-22`, dated changelog index —
  all still pre-GA).
- **Hugo CVE-2026-100690 — third-party-only** (file on first-party
  gohugoio GHSA only). New GHSA-r73q-gwx2-fpxm recorded as a
  watch-doc delta.
- **NanoCo re-grade bar — still unmet** (no first-party material).
- **Perplexity SPACE — flagged-only carry; watch for Part II.**
- **C72 / C73 / C74 / C75 — FILED, no movement;** C76 filed, gate
  item open. C73 fold stands (Bedrock Managed Agents preview).
- **DO pricing stamp moved "Last verified 8 Oct 2026" → "13 Oct
  2026"** (stamp text only, not a figure change — C60 precedent;
  vendor re-attested the figures; figures verbatim).
- **Vercel changelog sitemap: 1401 → 1411.** The dated index
  gained a 2026-10-12 section (1 entry: Muse Wonder on AI Gateway)
  and a 2026-10-13 section (4 AI Gateway entries) above the C69
  baseline, and the 2026-10-08 section (1 sandbox entry) reappeared
  after its C69 absence; the per-post composition of the +10 delta is
  not fully enumerated. Last resolved state stands (C66: 1397→1401
  math).
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed. No
  age-out movements this pass; no re-folds.

## Zero-fabrication statement

Every verdict above is grounded in a first-party page actually
opened in this pass (A lane: 20 opens — 19 first-try fetches + 1
established HTTP-404 on `boat.dev/pricing`, 11th consecutive cycle;
the 8 URL-recovery searches were navigation-only, never evidence)
or in an observed search-result snippet cited with its source and
date context (B lane: 15 searches, 15 successful / 0 failed, 0 page
opens — no fold-gate candidate; the C11 Modal-close trigger was
additionally vendor-verified by the integrator on the first-party
modal.com blog, read in full; the C82 Agent37 reconciliation and the
C83 AWS bulletin reconciliation were each verified by opening and
reading the first-party page in full). No page demanded auth; no
logins were performed. No repo, branch, or PR was touched except as
described in the ship path below.

**Ship path:** isolated worktree
`repo-strategy-compwatch-20261014-0910` (goal level; removed
post-merge per P20); Data-API push; draft PR opened pre-review;
adversarial review (Product + Architecture, routing-table for
research/analysis); CI on the exact head; squash-merge in dependency
order per the playbook's ship rules.
