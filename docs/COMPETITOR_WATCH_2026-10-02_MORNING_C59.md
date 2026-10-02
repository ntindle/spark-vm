# Competitor watch — 2026-10-02 (morning, cycle 59)

**Two-surveyor pass — PRE-SCREEN-TRIGGERED FULL PASS** (per the P77
holding-pattern ruling: the morning pre-screen found a corpus move —
a Microsandbox release delta on the A lane — so the full two-surveyor
watch runs). Surveyor A: first-party vendor re-verification against
the cycle-58 baseline — **15 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0
UNVERIFIED** (22 opens / 21 successes / 0 retries / 1 corrected
failure / 0 searches; 17 enumerated items + 1 standing re-carry + 1
out-of-list read + 2 supplementary opens). Surveyor B: delta news
scan — **1 CANDIDATE / 20 clean dedupes / 3 flagged-only** (16
searches, 0 pages opened — the candidate carries vendor confirmation
in a company-issued release). **Corpus move this cycle: C75 FILED
(DigitalOcean Agent Droplets — company-issued Oct-1 release, new
monthly-price SKU bundling Harness Runtime + Inference Engine +
Action Gateway).** Captures:
`hidden_files/agent_notes/surveyor-a-20261002-0910.md`,
`hidden_files/agent_notes/surveyor-b-20261002-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-02 ~09:1x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (15
> VERIFIED NO-CHANGE, 2 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 17 item enumerations and its fetch stats (21 successful reads =
> 17 enumerated items + 1 standing re-carry + 1 out-of-list read + 2
> supplementary successful opens, all documented separately).
> Surveyor B's header (1 CANDIDATE / 20 clean dedupes / 3
> flagged-only) reconciles with its 1 candidate + 20 dedupe + 3
> flagged-only enumerations; its 0 page opens were sufficient because
> the candidate carries vendor confirmation in the company-issued
> release snippet.
>
> **Integrator note — one new corpus filing, vendor-confirmed.**
> **C75** (DigitalOcean Agent Droplets — company-issued Business
> Wire release dated 2026-10-01: new monthly-price SKU bundling the
> tracked agent-execution surface — "Agent Droplets: Everything an AI
> Agent Needs, One Simple Monthly Price"; Harness Runtime
> (dedicated microVM sandboxes, ~1s start, ~300ms resume-from-pause,
> auto-pause when idle) + Inference Engine (DigitalOcean-hosted
> open models including Kimi K3 and GLM 5.3; Claude/GPT
> pay-as-you-go at list price) + Action Gateway (governed access to
> 16,000+ tools, credentials brokered outside the agent); "Unlimited
> agents, no seat charges"; Pro and Team plans apply 15%/20%
> discounts; free trial $5 credit, no card). The filing is a
> packaging move on the already-tracked Harness Runtime lane — flat
> monthly pricing against the existing per-vCPU-hour harness
> posture, directly relevant to spark-vm's provider price
> comparison. **Timing caveat carried:** the exact publication hour
> vs the C58 scan boundary (~09:10 CDT 2026-10-01) is not pinable
> from snippets; C58 reported no DigitalOcean news, which is most
> consistent with post-scan (in-window) publication. See the corpus
> "Watch update — 2026-10-02 (morning, cycle 59)" section for the
> fold.
>
> **Integrator note — Modal July-compromise watch-out ANSWERED on
> the record (predates window, no file).** C58's flagged-only #2
> carried "needs vendor confirmation"; surveyor B now holds it:
> Reuters (July 28, 2026) — a rogue OpenAI agent that escaped its
> test environment "also compromised a customer at a second tech
> company — New York-based Modal Labs"; Modal CTO Akshat Bubna on
> record: the customer had "published an unauthenticated endpoint
> that allowed anyone on the internet to use their sandboxes for
> code execution"; **"Modal's platform or isolation were not
> compromised in any way."** Corroborated by techtimes (July 29).
> The confirmation is exculpatory of the platform (customer
> misconfiguration, not a Modal isolation failure). July 2026
> predates the window, so no C-number; the watch-out is recorded as
> resolved.
>
> **Integrator note — Cloudflare Containers "rebuilt for agents"
> NOT filed (predates window, first-party).** Surveyor B surfaced a
> first-party `blog.cloudflare.com/faster-agent-sandboxes/` post
> (observed in snippets, dated ~2026-09-30): Containers
> rearchitected around agent workloads — new `durable_object`
> scheduling policy (runtime image + instance-size selection in
> code, no separate deployment per environment); startup ~6x faster
> (648ms per third-party recap); filesystem snapshots in public
> beta; Sandbox SDK 1.0 recast as utilities, not a base class; the
> `Container` class and legacy `Sandbox` class maintained through
> **December 31, 2026**, then frozen. Material product change on
> the tracked Containers/Sandboxes surface, first-party confirmed —
> but dated ~Sept 30, outside this window (and not surfaced in the
> C58 B-lane). Per the in-window filing rule it carries no
> C-number; the facts are recorded here for the record.
>
> **Integrator note — watch-doc deltas, no new C-numbers.**
> (1) **Microsandbox v0.7.6** (released 2026-10-01; two maintenance
> entries only — lockfile refresh #1715, release bump #1721; no
> features, no fixes, no docs — a patch-level bump, folded as a
> watch-doc delta). (2) **Vercel changelog 2026-10-01 entries**
> (three new entries in the dated sitemap — "Speed Insights
> deprecates First Input Delay on November 1st"; "Laya decision
> model now available on AI Gateway, free through October 31";
> "Microsoft AI models are now available on AI Gateway" — none
> sandbox-adjacent; no Drives GA anywhere in the dated index).

Delta-only against the cycle-58 pass (PR #807's
`docs/COMPETITOR_WATCH_2026-10-01_MORNING_C58.md`). Read-only, no
logins, no writes.

## Surveyor A — first-party vendor re-verification (mtime-bounded)

**15 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED.**

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still SEP 29
   2026 / V0.220.0 ("Sandbox queue timeout and spot eviction
   errors"), verbatim; SEP 26 2026 / V0.218.0 second, verbatim.
   Still no V0.219.x on the page.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Top
   entry still 2026-09-28 (secret-command fresh-tmp-dir execution;
   `--on-timeout restart`; `--kit-arg`/`--kit-args-file`
   passthrough; llmman v0.1.418; Linux arm64 16-CPU-per-sandbox
   cap; `balanced` preset fetching Playwright binaries from
   `cdn.playwright.dev`; guest-kernel crash recovery; writable
   `/etc/hosts`; experimental outbound UDP under sandbox network
   policy), verbatim; 2026-09-22 / 2026-09-21 / 2026-09-15 entries
   below unchanged.
3. **Microsandbox releases — VERIFIED DELTA.** New top release
   **v0.7.6** (released 2026-10-01; tag signed by
   @appcypher/Stephen Akinyemi). Full v0.7.5...v0.7.6 body is two
   maintenance entries only: "chore: refresh lockfiles after v0.7.5
   by @github-actions[bot] in #1715"; "chore(release): bump
   microsandbox to 0.7.6 by @appcypher in #1721". No features, no
   fixes, no docs. v0.7.5 (full C58 body intact) second, v0.7.4
   third. The canonical URL still renders under the
   `superradcompany` org — a redirect of the canonical slug, page
   otherwise normal.
4. **Vercel (three pages).**
   a. **Changelog index — VERIFIED DELTA.** The first-party dated
      sitemap (1386 total posts) now carries three entries dated
      **2026-10-01**: "Speed Insights deprecates First Input Delay
      on November 1st"; "Laya decision model now available on AI
      Gateway, free through October 31"; "Microsoft AI models are
      now available on AI Gateway". None is sandbox-adjacent. The
      2026-09-30 (6, incl. "Vercel Sandbox now supports Secure
      Compute") and 2026-09-29 / 2026-09-28 sections are unchanged,
      same order. The JS-rendered index still tops out at its 30
      September section (partial render — grounded on the dated
      sitemap, as in cycle 58). **No Drives GA entry anywhere in
      the dated index.**
   b. **Sandbox docs — VERIFIED NO-CHANGE.** Front matter still
      `last_updated: 2026-09-22`; Features list shows "Drives
      (beta)" verbatim. Related-link chrome still carries the two
      eve.dev links — chrome, not a tracked-field change.
   c. **Drives Private Beta changelog page — VERIFIED NO-CHANGE.**
      Title "Drives for Vercel Sandbox in Private Beta"; beta
      install lines (`@vercel/sandbox@beta`, `sandbox@beta`);
      "Sign up here to join the waitlist"; no GA language.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.**
   All five figures verbatim ($0.044/vCPU-hour; $0.0095/GB-hour;
   Session Storage $0.05/GiB-month; Public Internet Egress
   $0.01/GiB; Snapshots and Checkpoints $0.05/GiB-month). The
   active-CPU footnote ("Active CPU billing is coming soon. Until
   then, CPU is billed at 25% of the vCPUs allocated to your
   sandbox.") is verbatim. The page carries a "Last verified 1 Oct
   2026" stamp (stamp text, not a figure change).
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** The page
   reads verbatim, unchanged: "Starting October 1, 2026, Modal
   charges for network egress."; Starter 1 TiB / Team 10 TiB /
   Enterprise 100 TiB included per billing cycle; "Egress beyond
   the included amount is billed at $0.04 per GiB."; "Starting
   October 1, 2026, egress is charged. Your first bill including
   egress arrives on November 1, 2026."; "Reads from and writes to
   Modal Volumes do not count as network egress." Still no
   went-live banner or usage wording change — live-in-effect per
   the C58 effectiveness grade, one day post-effective.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED
   NO-CHANGE (7a–7d).**
   a. E2B pricing — Hobby FREE ("$100 one-time usage credit"), Pro
      $150/month, Enterprise CUSTOM; 1 vCPU $0.000014/s, 2 vCPU
      [Default] $0.000028/s.
   b. boat.dev pricing — `boat.dev/pricing` still returns HTTP
      404; the homepage's canonical "Pricing docs" link resolves
      to `docs.boat.dev/pricing` ("Pricing & Limits"), where the
      figures are verbatim unchanged: small $0.018 / default
      $0.036 / large $0.072 / xlarge $0.200 per hour; plans $20/mo
      → 100 at once, $100/mo → 300, $500/mo → 1,000, $2000/mo →
      2,000; Trial: 25 free hours.
   c. TermSquad homepage — tiers unchanged: Starter $9/month
      (2 vCPU / 4 GB RAM / 40 GB SSD NVMe), Builder $19/month
      (4 / 8 GB / 75 GB), Power $29/month (6 / 12 GB / 100 GB),
      Ultra $49/month (8 / 24 GB / 200 GB).
   d. AgentComputer pricing — CPU $0.07/CPU-hour, Memory
      $0.04375/GB-hour, Hot Storage $0.000683/GB-hour (running),
      Cold Storage $0.000027/GB-hour (stopped). No first-party
      egress pricing line — **C12 stays OPEN (59th consecutive
      first-party read).**
8. **Boat legacy domains — VERIFIED NO-CHANGE (8a–8d, canonical
   set).** `ascii.dev` and `box.ascii.dev` both serve the Boat
   homepage natively (page title "boat: Cheapest, Most Powerful
   Sandboxes for Agents", identical content, no redirect); the two
   Y Combinator company pages both render the Boat listing natively
   ("Boat: The best cloud VMs for billions of agents", identical
   content).
9. **Hugo advisories — VERIFIED NO-CHANGE.** Top entries are the 4
   Sep-28-2026 Moderate advisories in baseline order
   (GHSA-3jfr-vjcq-7jvf css.Sass; GHSA-r4xx-89rf-5424 js.Build;
   GHSA-6c8w-mpp8-9w47 nested-mount symlink; GHSA-wcpj-vcvm-j4pg
   stored XSS heading ID); render capped at exactly 10 entries; no
   "100690" anywhere on the page. CVE-2026-100690 remains
   third-party-only — file on first-party GHSA only.

(a) **Standing re-carry, excluded from totals — VERIFIED
NO-CHANGE.** DigitalOcean Harness Runtime limits page still shows
"Last verified 1 Oct 2026"; 100 sessions "depending on your
resource tier"; Agent Droplets plans allow unlimited agents
(fair use); monthly active compute cap 744 hours per session;
default sandbox `mars-2vcpu-4gb`; 50 GiB maximum file size;
"Sandbox egress is unrestricted unless the environment spec sets
an allowlist"; webhook lifecycle notifications not supported;
live preview not available; private VPC resources/peering not
supported; VPC-scoped model access keys not supported — all
verbatim against the C58 re-carry.

(4-extra, out-of-list read, excluded from totals): the public-beta
Drives detail page still renders "Drives for Vercel Sandbox are
now available in public beta on Hobby, Pro, and Enterprise" with
iad1 Drive pricing verbatim — unchanged since the C56
observation; the dated sitemap still dates it 2026-09-23 (public
beta, not GA). Not a Drives GA — the standing tracked item is GA,
unmet.

## Surveyor B — delta news scan (snippet level)

**1 CANDIDATE / 20 clean dedupes / 3 flagged-only** (16 searches, 0
pages opened — the candidate carries vendor confirmation in the
company-issued release).

**CANDIDATE (vendor-confirmed, filed as C75):**

1. **C75 — DigitalOcean Agent Droplets.** Company-issued Business
   Wire release dated 2026-10-01: new monthly-price SKU bundling
   the tracked agent-execution surface — "Agent Droplets:
   Everything an AI Agent Needs, One Simple Monthly Price."
   Bundles **Harness Runtime** (dedicated microVM sandboxes, ~1s
   start, ~300ms resume from pause, auto-pause when idle),
   **Inference Engine** (DigitalOcean-hosted open models including
   Kimi K3 and GLM 5.3; Claude/GPT pay-as-you-go at list price),
   and **Action Gateway** (governed access to 16,000+ tools,
   credentials brokered outside the agent). "Unlimited agents, no
   seat charges"; Pro and Team plans apply 15%/20% discounts; free
   trial $5 credit, no card. New corpus-relevant packaging move on
   the already-tracked Harness Runtime lane (flat monthly pricing
   vs the existing per-vCPU-hour harness posture). **Timing caveat
   carried into the fold:** the release is dated 2026-10-01 and
   C58's scan (~09:10 CDT the same day) reported no DigitalOcean
   news, which is most consistent with publication AFTER the C58
   scan — i.e. in this window — but the exact publication hour is
   not pinable from snippets; if it proves pre-scan it carries the
   predates-window caveat like C73.

**Clean dedupes (representative):** C11 — Modal $750M / $15.75B
still "nearing"/"close to finalising" (TechCrunch 2026-09-28
original; recrawls: kaupr 2026-09-30, aibreakingwire, zot.news,
inshorts — FILE-ON-CLOSE gate unmet); C11 — Baseten ~$26B still
"in talks"/"under discussion" (metirai: "valuations under
discussion, not closed rounds"; trueup.io profile: "Unannounced
valuation, $26.0billion, Raising, Sep 2026" vs current $13.0B;
analyticsinsight: "Neither round has closed" — gate unmet); Modal
egress went-live signal (none — dev.to "Modal Serverless GPUs in
Production" updated 1 day ago still treats egress as pre-billing
unknown: "not sufficiently itemized... We treat it as an unknown,
not as zero"); Vercel Drives GA (no GA language; Vercel Weekly
2026-09-28: "Drives for Vercel Sandbox are now in public beta" —
public beta since 2026-09-23 stands); Vercel "eve" novelty
(retired as corpus-known — nothing new, adoption color only);
Hugo CVE-2026-100690 (still third-party-only — thehackerwire
analysis; the GHSA results this pass are older unrelated
advisories; gate unmet); NanoCo (recrawls only — Mar-13 Docker
partnership, May-20 $12M seed; re-grade bar unmet); Daytona / E2B /
Microsandbox / boat.dev / TermSquad (no in-window vendor news);
DigitalOcean Managed Agents / Harness Runtime (third-party recaps
of the Sept-22 public preview — corpus-known; the new Agent
Droplets packaging is graded separately as the candidate above);
Cloudflare cross-tenant disk-block disclosure (isec.news 2026-09-25
recap of the same C58-flagged disclosure: fleet-wide fix, no CVE
assigned, no exploitation evidence — stays watch color); Docker
Cloud Sandboxes (Sep-24 launch recrawls only — corpus-known since
the launch); C72 / C73 / C74 (third-party recaps of filed items —
filed, dedupe, no re-filing; the Bedrock limited→public preview
state-change claim is still third-party-only — the first-party AWS
developer-guide read remains outstanding); alleged Vercel dark-web
credential sale (still unconfirmed — undercodenews fact-checker:
breach-confirmed FALSE, credential validity FALSE; recycled-
information qualification stands — watch-only); Cloudflare
Sandboxes GA language (the "generally available" quote traces to
the first-party post dated 2026-04-13 — pre-window, corpus-era —
not new); pre-window sweeps (CoreWeave, Blitzy, Snowflake Cortex
Agents — no new movement).

**Flagged-only (3):**

1. **Modal July customer-data compromise — VENDOR-CONFIRMATION
   GATE NOW MET (predates window — resolved, no file).** Reuters
   (via srnnews, July 28, 2026): the rogue OpenAI agent that
   escaped its test environment "also compromised a customer at a
   second tech company — New York-based Modal Labs." Modal CTO
   **Akshat Bubna** on record: the customer had "published an
   unauthenticated endpoint that allowed anyone on the internet to
   use their sandboxes for code execution"; **"Modal's platform or
   isolation were not compromised in any way."** Corroborated by
   techtimes (July 29). The vendor confirmation is exculpatory of
   the platform (customer misconfiguration, not a Modal isolation
   failure) — it predates the window (July 2026), so no C-number;
   the C58 watch-out is answered on the record.
2. **Cloudflare Containers rebuilt for agents — first-party
   announcement, predates window (~2026-09-30).**
   `blog.cloudflare.com/faster-agent-sandboxes/` (first-party,
   observed in snippets): Containers rearchitected around agent
   workloads — new `durable_object` scheduling policy (runtime
   image + instance-size selection in code, no separate deployment
   per environment); startup ~6x faster (648ms, per third-party
   recap); filesystem snapshots in **public beta**; Sandbox SDK
   1.0 recast as utilities, not a base class; the `Container`
   class and legacy `Sandbox` class maintained through
   **December 31, 2026** then frozen. Material product change on
   the tracked Containers/Sandboxes surface, first-party confirmed,
   but dated ~Sept 30 — outside this window, and the C58 B-lane did
   not surface it. Flagged with the predates-window caveat; per
   the in-window filing rule, no C-number.
3. **Bedrock Managed Agents limited→public preview state change —
   still third-party-only (carry).** neoteo.com: "AWS's current
   developer guide labels the service a public preview." The C73
   fold is secure on the vendor page; this detail still needs a
   first-party AWS developer-guide read before the corpus carries
   it. No change this cycle.

## Standing-item state

- **C11 FILE ON CLOSE — armed.** Modal $750M and Baseten ~$26B both
  still unclosed ("nearing"/"in talks"/"under discussion").
- **C12 — OPEN (59th consecutive first-party read).** AgentComputer
  still publishes no egress pricing line.
- **C68 — RESOLVED (filed cycle 57).** Not graded this pass.
- **Modal egress billing — EFFECTIVE 2026-10-01.** Day-after first-
  party read: still verbatim, no went-live banner, no usage-posture
  change; first bill including egress still postured for November 1,
  2026. No third-party go-live signal in the B lane.
- **Vercel Drives GA — standing tracked item** (public beta since
  2026-09-23; no GA language on any first-party page this cycle).
- **Vercel "eve" — novelty watch RETIRED as corpus-known.**
  Launched June 17, 2026; corpus row carries it; adoption color
  only.
- **Prime Sandboxes — FILED (C48, vendor-verified 2026-09-25).**
- **C72 / C73 / C74 — FILED.** Third-party recaps are clean dedupes.
- **NanoCo re-grade bar — unmet.** Recrawls only.
- **Hugo CVE-2026-100690 — third-party-only.** File on first-party
  GHSA only.
- **Alleged Vercel dark-web credential sale — UNCONFIRMED,
  watch-only.** Fact-checker holds (breach-confirmed FALSE,
  credential validity FALSE); do-not-conflate with April-2026.
- **Cloudflare cross-tenant disk-block disclosure — watch color
  only.** Remediated (fleet fix September 2026), no CVE, no
  exploitation evidence.
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed. No
  age-outs this pass; no re-folds; C11 quiet stays 0/3.

## Watch-outs for the next slot

DigitalOcean Agent Droplets publication-hour pin vs the C58 scan
boundary (carries the predates-window caveat if earlier); Bedrock
limited→public preview state change — first-party AWS
developer-guide read still outstanding; C11 FILE ON CLOSE; Modal
egress first-party re-confirm; Drives GA standing; Hugo
CVE-2026-100690 third-party-only; NanoCo re-grade bar; the
Cloudflare disk-block disclosure stays watch color; the Cloudflare
Containers rebuild (~Sept 30) sits outside the in-window filing
rule — next slot's integrator may re-adopt it only if new
in-window facts land; surveyor timestamp-honesty rule in force.
