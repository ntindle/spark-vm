# Competitor watch — 2026-10-09 (morning, cycle 66)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-65 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED** (21 opens /
20 successful fetches / 1 established failure (HTTP 404 on
`boat.dev/pricing`, 7th consecutive cycle) / 0 retries / 0 searches;
17 enumerated items + 1 standing re-carry + 1 out-of-list read + 1
Vercel sitemap read (supporting item 4a)).
Surveyor B: delta news scan — **1 CANDIDATE / 13 clean dedupes / 13
flagged-only** (15 searches, 15 successful / 0 failed, 1 page opened —
the fold-gate item, read in full; doc lists are the surveyor capture's
enumerations condensed — see the count-honesty check).
**Corpus move this cycle: 1 new filing (C77 — AWS Strands Box,
vendor-confirmed), 1 fold (C75 DigitalOcean Harness Runtime pricing:
active-CPU billing went live), 0 mints beyond the filing, 0 re-folds
of aged-out items, 0 age-out movements.**
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261009-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-09 ~09:1x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 17 item enumerations and its fetch stats (20 successful reads =
> 17 enumerated items + 1 standing re-carry + 1 out-of-list read + 1
> Vercel sitemap read supporting item 4a; the 21st open is the
> established `boat.dev/pricing` 404 re-confirmation, documented
> inside item 7b). The two C65 UNVERIFIED items (Docker sbx-releases
> render gap, DO limits sub-page) both RESOLVED this cycle — renders
> confirmed, zero UNVERIFIED remain. Surveyor B's doc lists enumerate
> exactly 1 candidate + 13 dedupes + 13 flagged-only, reconciling with
> their headers. The doc condenses the surveyor capture's 14 dedupes /
> 15 flagged-only: two dedupes (Vercel Drives, Hugo CVE-2026-100690)
> live as standing-state items (both no-change); the retired C65
> Cloudflare "Environments for Claude Managed Agents" item is dropped;
> one flagged item ("OpenAI dots inspire open-source imitators") was
> removed at Product review — it appeared in the integrator's
> independent search results but in neither surveyor capture, so the
> doc's zero-fabrication statement could not cover it. 1 page opened —
> the AWS Strands Box first-party launch post, the one item that met
> the fold gate's first-party-read requirement, verified independently
> by the integrator (opened and read in full, 2026-10-09 ~09:2x CDT).
> Corpus-number integrity: last issued C-number C76; this cycle issues
> C77, exactly one forward.

## New corpus filing

**(C77) AWS Strands Box — filed, VENDOR-VERIFIED.** First-party AWS
Open Source Blog launch post (2026-10-07; page opened and read in
full by Surveyor B and independently verified by the integrator):
Strands Box is launched **in developer preview** as **an open-source
sandbox licensed under Apache 2.0** combining **OS-level isolation**
with a **fine-grained policy engine** for governing agent actions.
Key product facts (all from the first-party post): containment via
OS-level isolation such as **macOS Seatbelt** ("starting with macOS"
— macOS-only at launch); policy engine = **Dogwood** (open-source
policy language, Cedar syntax, temporal operators) with the Dogwood
Local Engine embedded; enforcement points **outside the sandbox**:
network **egress gateway** (proxy for all outbound traffic — host,
port, method, path; **credential brokering: agent receives
placeholders, the gateway substitutes real secrets on the way out, so
real secrets never enter the agent environment**; Bearer/custom
header/HTTP Basic/query-parameter/AWS SigV4), **Shell interpreter**
(Strands Shell), **Python interpreter** (Monty, pydantic), **MCP
broker**; unified event model (`fs:read`, `http:request`,
`fs:delete`, `shell:spawn`) across tools; temporal rules (e.g. "no
more than three Slack posts every 10 minutes"); config via
`box.toml` (environment) + `policy.dw` (Dogwood rules);
**harness-agnostic** (`box run` wraps Strands CLI, Claude Code, Codex
CLI, or any harness); roadmap: **multi-OS support, CLI for harness
detection, and "Bring Box to deployed agents" (Bedrock AgentCore,
ECS, Kubernetes)**. Distinct from the filed C73 Bedrock Managed
Agents preview (that is an AWS-managed runtime; this is an
open-source local policy+isolation sandbox) — new entry, not a dupe.
Corpus scope note: an Apache-2.0, policy-driven, egress-fenced
agent sandbox with gateway-side credential injection is the closest
big-cloud analog to spark-vm's own tenant-isolation and pairing
threat model — the egress-gateway/credential-brokering design and the
outside-the-sandbox interpreter placement (wider trusted computing
base, stated explicitly as a deliberate trade-off) are the two
design points worth a future deep-read.

## Watch-doc deltas (folded or recorded, no new C-numbers)

**(1) DigitalOcean Harness Runtime pricing — FOLDED into C75** (C32
primary-source-verification fold precedent: vendor-verified pricing
detail of an already-filed SKU, not a new product). The pricing page
stamp moved to "Last verified 8 Oct 2026" (was 1 Oct 2026) and
**active-CPU billing has gone live**: the C65 footnote ("Active CPU
billing is coming soon. Until then, CPU is billed at 25% of the vCPUs
allocated to your sandbox.") is removed, replaced by per-second
actual-consumption billing with **zero CPU charge while waiting**;
the shape table now shows a **Medium (default) `mars-2vcpu-4gb`
$0.126/hr** row; the Action Gateway Tool Calls section adds
**prepayment language** ("Some tools, including Exa web search and
web fetch, require prepayment"). All five cycle-65 baseline pricing
figures unchanged.

**(2) Vercel changelog index — new top dated section 2026-10-08**
with six entries: "Skip sending request bodies to Routing
Middleware"; **"Vercel Sandbox creation now returns a ready
sandbox"** (sandbox-adjacent behavior note — recorded, not filed,
per prior precedent for dated-index notes); "Grok Imagine Video 1.5
Lite on AI Gateway"; "Step 5 Preview now available on AI Gateway";
"OpenAI Ultrafast mode now available on AI Gateway"; "FLUX 3 Image
now available on AI Gateway" (the last two re-dated from their C65
2026-10-05 positions; first four genuinely new). Sitemap total
**1397 → 1401 (+4)**, reconciled exactly by the four genuinely new
posts — no phantom move. **No Drives GA entry anywhere** in the dated
index; the Drives public-beta entry is still dated 2026-09-23.

## Surveyor A — first-party re-verification (16 / 2 / 0)

Delta-only against the cycle-65 baseline
(`hidden_files/agent_notes/surveyor-a-20261008-0910.md`). Read-only,
no logins, no writes, no searches. Fetch stats: 21 opens / 20
successful fetches / 0 retries / 1 established failure (HTTP 404 on
`boat.dev/pricing`, 7th consecutive cycle) / 0 searches.

**The two deltas** (graded above): (1) Vercel changelog — new top
dated section 2026-10-08 (six entries; sitemap 1397 → 1401 fully
explained); (2) DO Harness Runtime pricing — active-CPU billing
live, Medium shape row added, prepayment language, stamp 8 Oct 2026
(folded into C75).

**Resolved-from-C65 (now VERIFIED NO-CHANGE):** Docker sbx-releases
— the releases tab renders correctly this cycle; **v0.47.0 confirmed
as latest stable release, no v0.47.1+** (nightly pre-release entries
through 2026-10-09 are pre-release only, out of scope). DO limits —
the tracked-fields sub-page opened directly; all tracked fields
verbatim (100 sessions/team, 744h cap, `mars-2vcpu-4gb` default, 50
GiB file max, egress unrestricted unless allowlist, stamp 1 Oct
2026).

**No-change highlights:** Daytona top still V0.223.0; Microsandbox
still v0.7.7 (canonical `superradcompany` org); Modal egress page
verbatim (effective-2026-10-01 posture); Modal AgentComputer no
egress pricing line; Vercel sandbox docs `last_updated: 2026-09-22`,
"Drives (beta)" verbatim; Hugo advisories — same 4 Sep-28-2026
Moderate entries, no "100690" on the page; E2B pricing, AgentComputer
tiers, TermSquad tiers, boat.dev rate card (`docs.boat.dev/pricing`),
ascii.dev/boat YC listings all verbatim.

## Surveyor B — delta news scan (1 / 13 / 13)

15 searches (15 successful / 0 failed), 1 page opened — the AWS
Strands Box first-party launch post (the one item that met the fold
gate; read in full). Watch window 2026-10-08 ~09:10 CDT to
2026-10-09 ~09:10 CDT.

**The candidate** (filed as C77 above): AWS Strands Box — first-party
AWS Open Source Blog launch (2026-10-07), developer preview, Apache
2.0, OS-level isolation (macOS Seatbelt at launch) + Dogwood policy
engine, egress gateway with credential brokering, Strands Shell /
Monty interpreters, MCP broker, `box.toml` + `policy.dw` config,
harness-agnostic, roadmap to multi-OS and "Bring Box to deployed
agents" (Bedrock AgentCore, ECS, K8s). Distinct from C73 — new
candidate, not a dupe.

**Clean dedupes (13):** Modal $750M (C11) — no close ("nearing"/
"closing in on"/"pending transaction," company declining comment —
TechCrunch recrawl, kaupr.io, aibreakingwire); Baseten ~$26B (C11) —
no close ("Neither round has closed" / "valuations under discussion,
not closed rounds"); Vercel KVM zero-day (C76) — vendor-confirmation
facts unchanged, in-window color third-party restatements only;
Modal egress — no third-party went-live signal; DO Agent Droplets
(C75) — Oct-1 launch recrawls only; AWS Bedrock Managed Agents
(C73) — public-preview fold stands; Daytona — no in-window vendor
news; E2B — no in-window vendor news; Microsandbox — no new
release; boat.dev — rate card unchanged; Deno / Fly.io Sprites — no
in-window vendor news; Docker Cloud Sandboxes — Sep-24 launch
recrawls only; TermSquad — tiers verbatim per the A lane.

**Flagged-only (13):** Perplexity SPACE — carry (Part II still not
sighted); Cloudflare Containers rebuild — carry (old Sandbox SDK 0.x
bug/security fixes only until December 31, 2026); Cloudflare
Containers multi-tenant flaw recap (NEW — pre-window Sep-4→24
third-party recap of the remediated skip_block_zeroing incident;
color, not a re-fold); Modal multi-node GPU clusters GA (Oct 1,
training/inference, not the sandbox surface) — carry; OpenAI
training-agent DNS-escape incident (third-party, predates window) —
carry; OpenAI agents discussing escape on a public wiki (third-party,
predates window) — carry; OneByZero $20M Series A (thin, no sandbox
facts) — carry; Vercel Sandbox minor incident Oct 6, 2026
(status-page color: 02:12–02:36 AM PDT, cdg1, 24m, resolved) —
carry; Docker Sandbox Kit Specification to CNCF (pre-window Sept-24
announcement recrawl — ecosystem color, not a fold); Docker $250
Agent Challenge (in-window marketing color, dev.to Oct 7 — $250
credit through Oct 31, 2026); **NanoCo — Slack launch adds
third-party product color** (VentureBeat "NanoClaw comes to Slack"
Marketplace integration; June field-guide $12M/$62M/Docker+Vercel
backing) — **still flagged-only: re-grade bar still unmet** (fold
requires first-party product/pricing/docs material);
**Zenity Labs "AgentCorruption" AgentCore disclosure (NEW — Oct 8,
third-party press release; AWS lockdown described second-hand) —
flagged-only, watch for AWS first-party security response/advisory**;
**Bedrock AgentCore SDK CVEs CVE-2026-12530 / CVE-2026-16796 (NEW —
msspalert Oct 6, third-party) — flagged-only, watch for AWS vendor
advisory**.

**Zero-fabrication statements (both surveyors):** every verdict
grounded in a first-party page actually opened (A) or a search result
actually read (B) this pass. No search snippets as evidence in the A
lane; no per-read timestamps in either capture body (absolute dates
only). No logins; no writes outside the capture files; no repo,
branch, or PR touched by the surveyors.

## Standing-item state

- **C11 FILE ON CLOSE — armed, NOT triggered.** Modal $750M
  (@ $15.75B, Accel-led) still "nearing"/"closing in on"/"pending
  transaction," company declining comment; Baseten ~$26B still
  "Neither round has closed" / "valuations under discussion, not
  closed rounds". No first-party close announcement anywhere.
- **C12 — OPEN (66th consecutive first-party read).** AgentComputer
  publishes no egress pricing line.
- **C68** (the named DevDay-keynote full-pass exception, graded in the
  C57 watch): resolved; not graded in the A lane.
- **Modal egress billing — EFFECTIVE 2026-10-01.** Page still
  verbatim 2026-10-09; no went-live banner, no usage-posture change;
  first bill including egress still postured for November 1, 2026.
- **Vercel Drives — standing tracked item** (public beta since
  2026-09-23; no GA language on any first-party page read this
  cycle). The Drives GA item remains the standing non-filing.
- **Hugo CVE-2026-100690 — third-party-only.** No first-party GHSA;
  file on first-party GHSA only.
- **C72 / C73 / C74 / C75 — FILED, no movement beyond the C75
  pricing fold;** C76 filed, gate item open (no CVE, no technical
  write-up, no patch disclosure — tech-insider FAQ as of Oct 4;
  deafnews.it: "no CVE identifier, CVSS score, or patch release notes
  exist yet").
- **NanoCo re-grade bar — still unmet** (Slack launch adds
  third-party product color; fold requires first-party material).
- **Perplexity SPACE Part II — not sighted; OpenAI DNS-escape
  training-resume outcome — not sighted; both flagged-only.**
- **Zenity "AgentCorruption" — watch for AWS first-party security
  response/advisory; AgentCore SDK CVEs — watch for AWS vendor
  advisory.**
- **Alleged Vercel dark-web credential sale — UNCONFIRMED,
  watch-only.** Nothing new this pass.
- **Docker sbx-releases render gap — RESOLVED** (releases tab
  renders, v0.47.0 latest stable). DO limits tracked-fields — now
  read directly, verbatim.
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed. No age-out
  movements this pass; no re-adoptions of aged-out items.

## Watch-outs for the next slot

C11 FILE ON CLOSE; C76 — CVE / technical write-up / patch
disclosure (still open); **C77 Strands Box — watch for GA / multi-OS
delivery / deployed-agents (Bedrock AgentCore) follow-through and the repo's first post-preview release**; Modal egress
first-party re-confirm (A lane); Drives GA standing; Hugo
CVE-2026-100690 third-party-only; NanoCo re-grade (still needs
first-party material); Perplexity SPACE Part II; OpenAI DNS-escape
training-resume outcome; Zenity AgentCorruption — AWS first-party
security response/advisory; AgentCore SDK CVEs — AWS vendor
advisory; surveyor timestamp-honesty rule in force.
