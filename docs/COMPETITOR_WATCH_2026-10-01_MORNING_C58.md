# Competitor watch — 2026-10-01 (morning, cycle 58)

**Two-surveyor pass — MODAL-EGRESS NAMED-EXCEPTION FULL PASS** (per P85
semantics: named full-pass exceptions grade at the next scheduled daily
strategy slot; today's slot grades Modal's Oct-1 egress-billing
effectiveness). Surveyor A: first-party vendor re-verification against
the cycle-57 baseline — **14 VERIFIED NO-CHANGE, 3 VERIFIED DELTA, 0
UNVERIFIED** (23 opens / 22 successes / 1 retry / 1 corrected failure /
0 searches; 17 enumerated items + 1 standing re-carry + 1 out-of-list
read + 3 supplementary opens). Surveyor B: delta news scan —
**2 CANDIDATES / 17 clean dedupes / 3 flagged-only** (16 searches, 0
pages opened — both candidates carry vendor confirmation in
first-party/company-issued snippets). **Corpus move this cycle: Modal
egress effectiveness GRADED (in-effect, uneventful go-live); C72–C74
FILED (all vendor-confirmed).** Captures:
`hidden_files/agent_notes/surveyor-a-20261001-0910.md`,
`hidden_files/agent_notes/surveyor-b-20261001-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-01 ~09:1x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (14
> VERIFIED NO-CHANGE, 3 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 17 item enumerations and its fetch stats (22 successful reads =
> 17 enumerated items + 1 standing re-carry + 1 out-of-list read + 3
> supplementary successful opens, all documented separately).
> Surveyor B's header (2 CANDIDATES / 17 clean dedupes / 3
> flagged-only) reconciles with its 2 candidate + 17 dedupe + 3
> flagged-only enumerations; its 0 page opens were sufficient because
> both candidates carry vendor confirmation in the snippets.
>
> **Integrator note — the Modal exception is graded.** Today is the
> effective date. Surveyor A's first-party read of Modal's
> network-egress billing page (today, 2026-10-01) finds the page
> **verbatim unchanged** from the pre-effective posture — "Starting
> October 1, 2026, Modal charges for network egress."; Starter 1 TiB
> / Team 10 TiB / Enterprise 100 TiB per billing cycle; overage
> $0.04/GiB; "Your first bill including egress arrives on November 1,
> 2026."; Volumes I/O excluded. The page now reads as
> **live-in-effect per its own stated timeline** (the effective date
> has arrived), but there is no went-live banner, no wording change,
> no usage/billing-posture change — an uneventful go-live, and no
> third-party go-live news surfaced in the B lane. This retires the
> standing pre-effective posture line: the Modal field-table row
> carries a dated in-effect note, no new C-number.
>
> **Integrator note — three new corpus filings, all vendor-confirmed.**
> **C72** (MongoDB Atlas Agent Engine — launched Sept 29, 2026 at
> Investor Day; unified execution, memory, and governance layer for
> production AI agents; public preview available "today"; field-table
> row added), **C73** (Amazon Bedrock Managed Agents, OpenAI-powered
> — VENDOR-CONFIRMED on Amazon's own announcement page; caveat: the
> original announcement is April 28, 2026 and predates the window;
> the Sept-29 in-window event is the DevDay re-announcement; filed on
> the vendor-confirmed service, not the recap alone), **C74** (Vercel
> Sandbox now supports Secure Compute — first-party dated Vercel
> changelog entry 2026-09-30; capability addition on the tracked
> sandbox surface, not a new SKU). See the corpus "Watch update —
> 2026-10-01 (morning, cycle 58)" section for all three.
>
> **Integrator note — the Vercel "eve" novelty watch is RETIRED as
> corpus-known.** Launched June 17, 2026 at Vercel Ship (London) —
> The Register / techtimes / dev.to coverage; Apache-2.0; "Next.js
> for agents" filesystem-first framework; the corpus row (~321) has
> carried it since the 2026-09-18 pm watch. Surveyor A's
> first-party dated changelog sitemap carries "Grok 4.7 now available
> on AI Gateway, fx, and **eve**" (dated 2026-09-21) — a first-party
> eve mention on the changelog surface; adoption color only, no new
> filing.
>
> **Integrator note — watch-doc deltas, no new C-numbers.**
> (1) **Docker Sandboxes release notes** (new top entry 2026-09-28:
> secret commands execute from a fresh temporary directory on the
> host; `--on-timeout restart` timeout action; `--kit-arg`/
> `--kit-args-file` passthrough; llmman v0.1.418; Linux arm64
> 16-CPU-per-sandbox cap; `balanced` network preset can fetch
> Playwright binaries from `cdn.playwright.dev`; guest-kernel crash
> recovery; writable `/etc/hosts`; experimental outbound UDP
> following sandbox network policy). Design color: the outbound-UDP
> note is egress-fencing-thesis color — UDP egress now gated by
> sandbox network policy. (2) **Microsandbox v0.7.5** (gen-two CBOR
> op parity; `--no-stdin` for exec/run; denied HTTP/HTTPS egress now
> answered 403 — egress-policy color; fork naming). (3)
> **DigitalOcean Harness Runtime limits re-carry** (refresh to "Last
> verified 1 Oct 2026": the 100-session line now reads "depending on
> your resource tier"; Agent Droplets allow unlimited agents; 744
> h/month session cap; default sandbox `mars-2vcpu-4gb`; 50 GiB file
> max; "Sandbox egress is unrestricted unless the environment spec
> sets an allowlist" — egress-posture color vs the egress-fencing
> thesis; webhook lifecycle notifications unsupported; private VPC
> resources/peering and VPC-scoped model access keys unsupported).

Delta-only against the cycle-57 pass (PR #750's
`docs/COMPETITOR_WATCH_2026-09-30_MORNING_C57.md`). Read-only, no
logins, no writes.

## Modal egress-billing effectiveness grade (named exception, effective 2026-10-01)

The standing item for three cycles was "pre-effective posture
confirmed, re-confirm post-effective-date". First-party evidence
(surveyor A, read today 2026-10-01):

- The page reads **verbatim unchanged** from the pre-effective
  posture: "Starting October 1, 2026, Modal charges for network
  egress."; Starter 1 TiB / Team 10 TiB / Enterprise 100 TiB
  included per billing cycle; "Egress beyond the included amount is
  billed at $0.04 per GiB."; "Starting October 1, 2026, egress is
  charged. Your first bill including egress arrives on November 1,
  2026."; "Reads from and writes to Modal Volumes do not count as
  network egress."
- **Grade: IN-EFFECT, UNEVENTFUL.** The page now reads as live per
  its own stated timeline (the effective date has arrived). No
  separate went-live banner, no wording change, no usage or
  billing-posture change; the first-bill posture (November 1, 2026)
  stands. No third-party go-live news in the B lane (one dev.to
  rate-audit, 14 hours old, still treats egress as pre-billing
  unknown — "not sufficiently itemized... We treat it as an unknown,
  not as zero").
- Corpus impact: the pre-effective standing line is retired. The
  Modal field-table row carries a dated in-effect note (no new
  C-number): spark-vm's provider comparison now has a live Modal
  egress datapoint — $0.04/GiB against DigitalOcean harness-runtime's
  $0.01/GiB public egress; AgentComputer's C12 stays open (no
  first-party egress line anywhere in the corpus).

## Surveyor A — first-party vendor re-verification (mtime-bounded)

**14 VERIFIED NO-CHANGE, 3 VERIFIED DELTA, 0 UNVERIFIED.**

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still SEP 29
   2026 / V0.220.0 ("Sandbox queue timeout and spot eviction
   errors"); SEP 26 2026 / V0.218.0 second, verbatim unchanged;
   still no V0.219.x on the page.
2. **Docker Sandboxes release notes — VERIFIED DELTA.** New top entry
   2026-09-28 (see the integrator note above for the full delta).
   The C57 top entry (2026-09-22) is now second, verbatim unchanged;
   2026-09-21 v3-kits and 2026-09-15 entries unchanged below it.
3. **Microsandbox releases — VERIFIED DELTA.** New top release
   **v0.7.5** (Features #1669 gen-two CBOR op parity, #1688 CLI
   `--no-stdin`, #1489 denied HTTP/HTTPS egress answered 403, #1606
   published-port TCP accept queue, #1708 fork naming; Fixes
   #1674/#1607/#1690/#1698/#1697/#1700/#1706/#1694; Docs #1699;
   Maintenance #1673; released by @toksdotdev in #1711). v0.7.4
   (full C57 body intact) second, v0.7.3 third. Note: the canonical
   URL now renders under the `superradcompany` org ("Releases ·
   superradcompany/microsandbox") — a redirect of the canonical slug,
   page otherwise normal.
4. **Vercel (three pages).**
   a. **Changelog index — VERIFIED DELTA.** The JS-rendered index now
      tops out at 6 entries dated 2026-09-30 (per the first-party
      dated sitemap `vercel.com/changelog/sitemap.md`): "Vercel
      Agent now installs private packages from npm and custom
      registries"; "AI Gateway adds Browserbase Search and Fetch
      tools"; "Edge Requests are now called CDN Requests";
      **"Vercel Sandbox now supports Secure Compute"**;
      "Ling 3.1 Flash is now available on AI Gateway"; "Vercel CDN
      no longer caches responses with Vary: Cookie". Three further
      entries dated 2026-09-29; the baseline's 28 September
      section is now dated 2026-09-28 in the sitemap (same 3
      entries, same order). **No Drives GA entry anywhere in the
      dated index.** The sandbox-adjacent delta — the Secure Compute
      entry — is filed as C74.
   b. **Sandbox docs — VERIFIED NO-CHANGE.** Front matter still
      `last_updated: 2026-09-22`; Features list shows "Drives
      (beta)" verbatim. Related-link chrome carries page links
      including two eve.dev links ("Security Model", "Sandbox") —
      chrome, not a tracked-field change.
   c. **Drives Private Beta changelog page — VERIFIED NO-CHANGE.**
      Title "Drives for Vercel Sandbox in Private Beta"; beta
      install lines; "Sign up here to join the waitlist"; no GA
      language.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures verbatim ($0.044/vCPU-hour; $0.0095/GB-hour;
   Session Storage $0.05/GiB-month; Public Internet Egress
   $0.01/GiB; Snapshots and Checkpoints $0.05/GiB-month). ("Active
   CPU billing is coming soon. Until then, you will be billed at 25%
   of the vCPUs allocated to your sandbox.")
6. **Modal network-egress billing — VERIFIED NO-CHANGE (in-effect
   per the effectiveness grade above).** See the grading section.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (7a–7d).**
   a. E2B pricing — Hobby FREE ("$100 one-time usage credit"), Pro
      $150/month, Enterprise CUSTOM; 1 vCPU $0.000014/s, 2 vCPU
      [Default] $0.000028/s.
   b. boat.dev pricing — small $0.018 / default $0.036 / large
      $0.072 / xlarge $0.200 per hour; plans $20/mo → 100 at once,
      $100/mo → 300, $500/mo → 1,000, $2000/mo → 2,000; Trial: 25
      free hours. Note: `boat.dev/pricing` now returns HTTP 404;
      the homepage's canonical "Pricing docs" link resolves to
      `docs.boat.dev/pricing` ("Pricing & Limits"), where the
      figures are verbatim unchanged — a URL consolidation, not a
      pricing change.
   c. TermSquad homepage — tiers unchanged: Starter $9/month,
      Builder $19/month, Power $29/month, Ultra $49/month.
   d. AgentComputer pricing — CPU $0.07/CPU-hour, Memory
      $0.04375/GB-hour, Hot Storage $0.000683/GB-hour (running),
      Cold Storage $0.000027/GB-hour (stopped). No first-party
      egress pricing line — **C12 stays OPEN (58th consecutive
      first-party read).**
8. **Boat legacy domains — VERIFIED NO-CHANGE (8a–8d, canonical
   set).** `ascii.dev` and `box.ascii.dev` both serve the Boat
   homepage natively (no redirect); the two Y Combinator company
   pages both render the Boat listing natively.
9. **Hugo advisories — VERIFIED NO-CHANGE.** Top entries still the 4
   Sep-28-2026 Moderate advisories in baseline order; render capped
   at exactly 10 entries; no "100690" anywhere. CVE-2026-100690
   remains third-party-only — file on first-party GHSA only.

(a) **Standing re-carry, excluded from totals — DELTA.** See the
integrator note above for the full DigitalOcean-limits refresh.

(4-extra, out-of-list read, excluded from totals): the public-beta
Drives detail page still renders "Drives for Vercel Sandbox are now
available in public beta on Hobby, Pro, and Enterprise" with iad1
Drive pricing verbatim — unchanged since the C56 observation; the
dated sitemap confirms 2026-09-23, consistent with public beta.
Not a Drives GA — the standing tracked item is GA, unmet.

## Surveyor B — delta news scan (snippet level)

**2 CANDIDATES / 17 clean dedupes / 3 flagged-only** (16 searches, 0
pages opened — both candidates carry vendor confirmation in
first-party/company-issued snippets).

**CANDIDATES (both vendor-confirmed, filed as C72–C73):**

1. **C72 — MongoDB Atlas Agent Engine.** Company-issued PR Newswire
   release (MongoDB, Inc., NASDAQ: MDB), dated September 29, 2026:
   launched at its Investor Day at the Nasdaq MarketSite in New York
   City — "a unified execution, memory, and governance layer for
   production AI agents." "Atlas Agent Engine is available today in
   public preview. New and existing Atlas customers can get started
   at agentengine.mongodb.com." Consumption-based pricing for Atlas
   Agent Runtime and Atlas Agent Memory; usage draws on customers'
   existing Atlas commitments. Retrieval powered by MongoDB Voyage
   AI (embedding/reranking); memory and governance layers adoptable
   independently of the runtime; model- and framework-agnostic.
   Corollary color (same release): MongoDB 9.0 launched the same day
   — adjacent infra, not filed. New agent-runtime surface in the
   corpus lane; in-window (Sept 29). C57 flagged-only gate MET
   (single LinkedIn claim → company-issued release).
2. **C73 — Amazon Bedrock Managed Agents (OpenAI-powered).**
   VENDOR-CONFIRMED on Amazon's own aboutamazon.com announcement
   page: "April 28, 2026: Today, we are announcing a major expansion
   of our partnership with OpenAI... three new offerings, all in
   limited preview: OpenAI models on Amazon Bedrock... Codex on
   Amazon Bedrock... Amazon Bedrock Managed Agents, powered by
   OpenAI: an optimized experience for building production-ready AI
   agents with OpenAI frontier models on AWS." Re-announced in the
   OpenAI DevDay 2026 keynote (Sept 29, 2026) — the in-window event
   (OpenAI's own recap + third-party keynote coverage: OpenAI models
   + Codex harness + Bedrock AgentCore, IAM-role identities, human
   approval gates, CloudTrail logging, data stays in AWS; Salesforce
   named as early customer — third-party color). **Caveat carried
   into the fold:** the original announcement predates the window;
   the Sept-29 in-window event is the DevDay re-announcement. Filed
   on the vendor-confirmed service, not the recap alone. C57
   flagged-only gate MET (recap mention → first-party AWS page).

**Clean dedupes (representative):** C11 — Modal $750M / $15.75B
still "nearing"/"closing in on" ("The deal has not closed, and Modal
declined to comment" — FILE-ON-CLOSE gate unmet); C11 — Baseten
~$26B ("Neither round has closed, and terms could still shift" —
gate unmet); Modal egress went-live signal (none — pre-effective
docs mirrored on GitHub; a dev.to rate-audit 14 hours old still
treats egress as pre-billing unknown: "not sufficiently
itemized... We treat it as an unknown, not as zero"); Vercel Drives
GA (no GA language; Vercel Weekly 2026-09-28: "Drives for Vercel
Sandbox are now in public beta" — public beta since 2026-09-23
stands); Vercel "eve" novelty (RESOLVED as corpus-known — launched
June 17, 2026 at Vercel Ship London; corpus row already carries it;
adoption color only — "How Vercel Built a Superagent with eve" event,
"Agent workshop: Building Agents with eve" — below bar); Hugo
CVE-2026-100690 (third-party analysis only — thehackerwire: CVE
received Sep 26, analyzed Sep 29, modified Sep 30; no first-party
GHSA — gate unmet); NanoCo (no first-party sandbox/compute
announcement — Mar-13 Docker partnership, May-20 $12M seed, August
releases are recrawls; re-grade bar unmet); Daytona / E2B /
Microsandbox / boat.dev / TermSquad / DigitalOcean / Cloudflare
(no in-window first-party deltas — recrawls or silence; the
devops-daily "8 Managed Agent Runtimes Compared" 2026-09-28 is a
third-party comparison piece — below bar); Docker (Sep-24 Cloud
Sandboxes launch recrawls only); pre-window sweeps (CoreWeave May
2026, Blitzy 2026-09-14, Snowflake Cortex Sept-01 — no new
movement); the alleged Vercel dark-web credential sale (still
unconfirmed — undercodenews fact-checker: breach-confirmed FALSE,
credential validity FALSE; plus a new qualification that the
listing may be recycled information from the earlier incident —
the do-not-conflate-with-April-2026 rule holds even harder;
watch-only).

**Flagged-only (3):**

1. **Cloudflare Containers/Sandboxes cross-tenant disk-block flaw
   (disclosed ~2026-09-27).** A shared `dm-thin` storage pool
   skipped zeroing reused 64 KiB blocks; a Workers Paid customer
   could potentially read residual bytes from other customers'
   containers. Reported via HackerOne on September 4, 2026 by Oren
   Yomtov (Accomplish); Cloudflare merged a runtime fix the same
   day; fleet-wide remediation (disk retirement, cache clearing)
   completed September 19, 2026; no customer action required; no
   CVE assigned; no evidence of exploitation. Third-party
   disclosure of an already-remediated vendor flaw — lane-relevant
   isolation color (residual-data isolation is the same class
   spark-vm's sandbox design answers), below the corpus-fold bar.
2. **Modal July customer-data compromise (third-party,
   single-source).** tradersunion.com: "Modal Labs disclosed a
   customer data compromise in July linked to client-side code
   vulnerabilities, not flaws in its own systems." No vendor page
   observed — below bar until a first-party/Modal source confirms.
3. **Bedrock Managed Agents limited→public preview state change
   (third-party).** neoteo.com (1 day old): "AWS and OpenAI
   announced Amazon Bedrock Managed Agents in limited preview on
   April 28, 2026. AWS's current developer guide labels the service
   a public preview." The C73 fold is met on the vendor page; this
   detail needs a first-party AWS developer-guide read before the
   corpus carries it.

## Standing-item state

- **C11 FILE ON CLOSE — armed.** Modal $750M and Baseten ~$26B both
  still unclosed ("nearing"/"closing in on").
- **C12 — OPEN (58th consecutive first-party read).** AgentComputer
  still publishes no egress pricing line.
- **C68 — RESOLVED (filed cycle 57).** Not graded this pass.
- **Modal egress billing — EFFECTIVE 2026-10-01 (today).**
  Effectiveness graded: in-effect per its own stated timeline,
  verbatim-unchanged wording, uneventful; first bill including
  egress still postured for November 1, 2026. No went-live banner,
  no third-party go-live news.
- **Vercel Drives GA — standing tracked item** (public beta since
  2026-09-23; no GA language on any first-party page this cycle).
- **Vercel "eve" — novelty watch RETIRED as corpus-known.**
  Launched June 17, 2026; corpus row carries it; adoption color only.
- **Prime Sandboxes — FILED (C48, vendor-verified 2026-09-25).**
- **NanoCo re-grade bar — unmet.** File only on a first-party
  sandbox/compute announcement.
- **Hugo CVE-2026-100690 — third-party-only.** File on first-party
  GHSA only.
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.

## Watch-outs for the next slot

C72/C73 fold details (Bedrock limited→public preview state change
needs a first-party AWS developer-guide read; Modal July compromise
needs vendor confirmation); C11 FILE ON CLOSE; Drives GA standing;
Hugo CVE-2026-100690 third-party-only; NanoCo re-grade bar; the
Cloudflare cross-tenant disk-block disclosure stays watch color
(remediated, no CVE, no exploitation evidence); surveyor
timestamp-honesty rule in force.
