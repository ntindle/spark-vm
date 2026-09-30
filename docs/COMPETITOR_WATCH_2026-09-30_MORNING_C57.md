# Competitor watch — 2026-09-30 (morning, cycle 57)

**Two-surveyor pass — C68 NAMED-EXCEPTION FULL PASS** (per P85 semantics:
named full-pass exceptions grade at the next scheduled daily strategy
slot). Surveyor A: first-party vendor re-verification against the
cycle-56 baseline — **16 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 0
UNVERIFIED** (20 opens / 19 successes / 1 retry / 1 corrected 404 —
a superseded Hugo org-level mirror path — / 0 searches; 17 enumerated
items + 1 standing re-carry + 1 out-of-list read). Surveyor B: delta
news scan with the C68 DevDay-keynote grading as the centerpiece —
**3 CANDIDATES / 17 clean dedupes / 4 flagged-only** (18 searches, 1
page opened — OpenAI's official DevDay recap on community.openai.com,
2026-09-29). **Corpus move this cycle: C68 RESOLVED (keynote graded
6 CONFIRMED / 1 PARTIALLY-CONFIRMED), C69–C71 FILED (all
vendor-confirmed).** Captures:
`hidden_files/agent_notes/surveyor-a-20260930-0910.md`,
`hidden_files/agent_notes/surveyor-b-20260930-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-09-30 ~09:1x–09:2x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 1 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 17 item enumerations and its fetch stats (20 opens = 17
> enumerated items + 1 standing re-carry + 1 out-of-list read + 1
> corrected failed open, documented separately). Surveyor B's header
> (3 CANDIDATES / 17 clean dedupes / 4 flagged-only) reconciles with
> its 3 candidate + 17 dedupe + 4 flagged-only enumerations; its 1
> page open was the vendor recap that grounds all three candidates.
>
> **Integrator note — C68 is RESOLVED and filed.** The pre-keynote
> predictions held as never-file-pre-keynote color through C56 are
> now graded against the actual keynote output (vendor evidence:
> OpenAI's official "DevDay 2026 announcements and developer
> resources" recap post on community.openai.com, posted 2026-09-29,
> plus OpenAI's own "Introducing dots" announcement). See the grading
> table below. The C68 never-file-pre-keynote standing line is
> retired.
>
> **Integrator note — three new corpus entries, all vendor-confirmed.**
> **C69** (OpenAI Agents API public beta + computer use), **C70**
> (OpenAI Dots), **C71** (OpenAI Codex Cloud) are folded into the
> corpus (field-table rows + new "Watch update — 2026-09-30 (morning,
> cycle 57)" section in `docs/COMPETITOR_ANALYSIS.md`) under the C32
> primary-source-verification fold precedent. OpenAI is now a direct
> operator in the agent-compute lane — this is the biggest corpus move
> of the cycle.
>
> **Integrator note — Daytona V0.220.0 is a watch-doc delta, not a
> corpus fold.** "Sandbox queue timeout and spot eviction errors" is a
> minor changelog delta (no new product, no pricing change); it is
> recorded here and not folded as a field-table change. Design color:
> capacity-constrained provisioning error taxonomy — relevant to H4's
> live-provider provisioning (the 2026-09-24 $5/run, $25/month spend
> caps make preemption/timeout behavior a real cost-surface question).

Delta-only against the cycle-56 pass (PR #697's
`docs/COMPETITOR_WATCH_2026-09-29_MORNING_C56.md`). Read-only, no
logins, no writes.

## C68 — DevDay keynote grading (2026-09-29 ~12pm CT, Fort Mason)

Grading the seven pre-keynote predictions against the actual keynote.
Vendor evidence: OpenAI's official DevDay 2026 recap (2026-09-29)
unless otherwise noted.

| # | Pre-keynote prediction | Grade | Evidence |
|---|---|---|---|
| 1 | "Dots" | **CONFIRMED** | "**Dots** are persistent agents with connected apps and their own cloud computer." OpenAI's own "Introducing dots" (2026-09-29): built to handle everything, powered by GPT-6 Astra, own cloud computer, learn from feedback, work around the clock, connect to 4,000+ apps. Rollout: Pro and Business Premium in eligible markets; Enterprise/Edu/Healthcare admin-enabled beta. |
| 2 | "ChatGPT Space" | **CONFIRMED** | "**ChatGPT Space** gives teams and agents a shared place for files and project context." CNBC live blog: Space lets teammates and OpenAI's dots agents work together. |
| 3 | "GPT-6.1 Sol" | **CONFIRMED** | "**GPT-6.1 Sol** improves coding and computer use, with standard token prices at one-fifth of Astra's." Reuters/CNBC: "major upgrade" across professional work, computer use, and agentic coding, one week after GPT-6 Sol. |
| 4 | "Agents API" | **CONFIRMED** | "The **Agents API** is in public beta, with hosted execution, memory, tools, and multi-agent support." "**Computer use** in the Agents API lets agents operate software through its UI." Corroborated by `openai/openai-cookbook` sandbox examples (application-managed + webhook-managed sandbox provisioning across docker, digitalocean, cloudflare, modal, vercel, e2b, daytona, blaxel, runloop, OCI). |
| 5 | "Ultra Fast" | **CONFIRMED** | "**Ultrafast** is a paid speed tier" — up to 8× faster token generation in Codex, 6× in the API (up to 300 tokens/second in Codex). Astra available now; Sol coming soon. |
| 6 | GPT-6.1 "Astra" cancellation | **CONFIRMED** | Reuters/CNBC (2026-09-29): "On Monday [2026-09-28], OpenAI announced it decided to pull its plans to launch GPT-6.1 Astra because the model did not meet its safety standards." Announced 2026-09-28 (day before the keynote), not on the DevDay stage. |
| 7 | "o" always-on-agent leak | **PARTIALLY-CONFIRMED** | Substance CONFIRMED (the always-on agent launched — as **Dots**, each with its own cloud computer). The leaked name **"o" is REFUTED** (rumor grading: "the agent is named dots, not o"). |

**Grade tallies: 6 CONFIRMED, 1 PARTIALLY-CONFIRMED, 0 REFUTED, 0
UNCONFIRMED. C68 RESOLVED.**

**Corpus impact:** OpenAI now sells a managed agent runtime with
hosted execution (Agents API public beta), operates always-on agent
compute (Dots), and runs cloud execution for coding agents (Codex
Cloud). The `openai-cookbook` sandbox-examples list (docker,
digitalocean, cloudflare, modal, vercel, e2b, daytona, blaxel,
runloop, OCI) is the explicit integration seam: the Agents API's
application-managed sandbox provisioning is where a spark-vm
OpenSandbox adapter would slot in — design color for H4's
OpenSandbox-adapter discussions. spark-vm's differentiators against
vendor-run compute stand: a real VM the operator owns, per-action
human approvals (confirmd), the credential-proxy pattern (swapd),
tailnet-first networking — none of which a vendor-run cloud computer
gives the operator. Also noted (not filed): OpenClaw enterprise
harness was briefly mentioned on the keynote stage (per OpenAI's own
recap).

## Surveyor A — first-party vendor re-verification (mtime-bounded)

**16 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 0 UNVERIFIED.** Zero
fabrications; every verdict grounded in a first-party page read.

1. **Daytona changelog — VERIFIED DELTA.** New top entry: SEP 29 2026 /
   V0.220.0 ("Sandbox queue timeout and spot eviction errors"):
   "Daytona 0.220.0 adds a queue timeout for sandbox creation and
   reports queue-timeout and spot-eviction failures as distinct
   errors in the SDKs and CLI." (Tags: SDK, CLI.) The C56 top entry
   (SEP 26 2026 / V0.218.0) is now second, verbatim unchanged. No
   V0.219.x on the page (list jumps V0.220.0 → V0.218.0).
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Still
   tops out 2026-09-22 ("Improved sandbox moves and support for
   private kit images in cloud sandboxes"); the 2026-09-21 v3-kits
   entry verbatim unchanged, followed by the 2026-09-15 entry.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Top release still
   v0.7.4 with its full body intact; v0.7.3 still second. No v0.7.5+
   on the page.
4. **Vercel — ALL NO-CHANGE.**
   a. **Changelog index — VERIFIED NO-CHANGE.** The "28 September"
      section still carries the baseline's 3 entries in the same
      order; rendered window covers 28, 27, 25 September (24
      September outside the visible truncation, same as before).
      No Drives GA entry anywhere in it.
   b. **Sandbox docs — VERIFIED NO-CHANGE.** Still `last_updated:
      2026-09-22` with "Drives (beta)" verbatim in the Features
      list; related-link chrome unchanged (page chrome, not a
      tracked-field change).
   c. **Drives Private Beta changelog page — VERIFIED NO-CHANGE.**
      Title still "Drives for Vercel Sandbox in Private Beta";
      beta install lines; waitlist sign-up live; no GA language.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.** All
   five figures verbatim ($0.044/vCPU-hour, $0.0095/GB-hour, session
   storage $0.05/GiB-month, egress $0.01/GiB, snapshots
   $0.05/GiB-month); the "Last verified 22 Sep 2026" stamp
   unchanged.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** "Starting
   October 1, 2026, Modal charges for network egress"; Starter 1 TiB
   / Team 10 TiB / Enterprise 100 TiB per billing cycle; overage
   $0.04/GiB; first bill including egress arrives November 1, 2026;
   Volumes excluded. No went-live-early signals — page still reads
   as pre-effective (effective 2026-10-01, one calendar day after
   this read). **Re-confirm post-effective-date** with first-party
   reads only.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (7a–7d).**
   a. E2B pricing — Hobby FREE ($100 one-time usage credit), Pro
      $150/month, Enterprise custom; 1 vCPU $0.000014/s, default 2
      vCPU $0.000028/s.
   b. boat.dev pricing — `small` $0.018 / `default` $0.036 /
      `large` $0.072 / `xlarge` $0.200 per hour; plans $20/mo → 100,
      $100/mo → 300, $500/mo → 1,000, $2000/mo → 2,000 sandboxes at
      once; trial 25 free hours; all verbatim unchanged.
   c. TermSquad homepage — tiers unchanged: Starter $9/month,
      Builder $19/month, Power $29/month, Ultra $49/month.
   d. AgentComputer pricing — CPU $0.07/CPU-hour, Memory
      $0.04375/GB-hour, Hot Storage $0.000683/GB-hour (running),
      Cold Storage $0.000027/GB-hour (stopped); still **no
      first-party egress pricing line — C12 stays OPEN (57th
      consecutive first-party read)**.
8. **Boat legacy domains — VERIFIED NO-CHANGE (8a–8d, canonical
   set).** `ascii.dev` and `box.ascii.dev` both serve the Boat
   homepage natively (no redirect); the two Y Combinator company
   pages both render the Boat listing natively.
9. **Hugo advisories — VERIFIED NO-CHANGE.** Top entries still the 4
   Sep-28 Moderate advisories in baseline order; render capped at
   exactly 10; no "100690" anywhere. CVE-2026-100690 remains
   third-party-only — file on first-party GHSA only. (The org-level
   mirror path `github.com/gohugoio/security/advisories` now 404s;
   the canonical `github.com/gohugoio/hugo/security/advisories`
   page renders normally.)

(a) **Standing re-carry, excluded from totals:** DigitalOcean
limits page — still "Last verified 21 Sep 2026" with verbatim
"You can run up to 100 sessions at once per team depending on your
tier."

(4-extra, out-of-list read, excluded from totals): the public-beta
Drives detail page still renders "Drives for Vercel Sandbox are now
available in public beta on Hobby, Pro, and Enterprise" with iad1
pricing — unchanged since C56; not a Drives GA (the standing tracked
item is GA, unmet).

## Surveyor B — delta news scan (snippet level)

**3 CANDIDATES / 17 clean dedupes / 4 flagged-only** (fifty-second
straight B-lane scan with the quiet-streak broken by the C68
exception's vendor-confirmed filings).

**CANDIDATES (all vendor-confirmed, filed as C69–C71):**

1. **C69 — OpenAI Agents API (public beta) + computer use.** "The
   Agents API is in public beta, with hosted execution, memory,
   tools, and multi-agent support"; "Computer use in the Agents API
   lets agents operate software through its UI" (OpenAI DevDay
   recap, 2026-09-29). Corroborated by `openai/openai-cookbook`
   sandbox examples: application-managed and webhook-managed
   sandbox provisioning across docker, digitalocean, cloudflare,
   modal, vercel, e2b, daytona, blaxel, runloop, and OCI. OpenAI now
   sells a managed agent runtime with hosted execution environments
   for agents — directly comparable to the tracked sandbox
   providers.
2. **C70 — OpenAI Dots.** "Dots are persistent agents with connected
   apps and their own cloud computer" (OpenAI recap, 2026-09-29);
   OpenAI's "Introducing dots" (2026-09-29): each dot runs on GPT-6
   Astra, gets its own cloud computer and browser, connects to
   4,000+ apps; one dot included with Pro/Business Premium. OpenAI
   is now a direct operator of always-on agent compute.
3. **C71 — OpenAI Codex Cloud.** "Codex Cloud runs tasks while your
   laptop is closed, with access across devices" (OpenAI recap,
   2026-09-29); alongside Code Review, Codex Security Cloud, and
   the CLI `/agents` view. A developer-agent cloud compute surface
   from OpenAI.

**Clean dedupes (representative):** C11 — Modal $750M/"$15.75B"
still "nearing"/"closing in on" ("The deal has not closed, and
Modal declined to comment" — FILE-ON-CLOSE gate unmet); C11 —
Baseten ~$26B ("Neither round has closed, and terms could still
shift" — gate unmet); Vercel Drives GA (no GA language; public beta
since 2026-09-23 stands; vercel/sandbox SDK CHANGELOG shows Drives
support landing in @vercel/sandbox 3.3.0 / CLI 4.4.0 — SDK
support, not GA); NanoCo (no first-party sandbox/compute
announcement — NanoClaw×Docker partnership recrawl
2026-03-13, NanoClaw 2.0×Vercel/OneCLI recrawl, $12M seed dated
2026-05-20; re-grade bar unmet); Hugo CVE-2026-100690
(third-party analysis only — thehackerwire: Hugo v0.161.0–v0.165.0
Node.js permission-model symlink escape, fixed in v0.166.0; no
first-party GHSA — gate unmet); AgentComputer (no new news);
Prime Sandboxes C48 (no new facts — AlphaSignal ~2026-09-23
recrawl; third-party X-sourced "NVIDIA Vera CPU hardware" color
is infra hardware, below bar); Docker Cloud Sandboxes (2026-09-24
launch recrawls only); Daytona / E2B / Microsandbox / boat.dev /
TermSquad / DigitalOcean / Cloudflare / Modal-egress (no
in-window deltas — recrawls or silence); Snowflake Cortex Agents
sandbox tools (2026-09-01, pre-window); CoreWeave Sandboxes (May
2026, pre-window); Blitzy Sandbox (2026-09-14, pre-window — a
free-trial offering, not infra); devops-daily "8 Managed Agent
Runtimes Compared" (2026-09-28, third-party comparison piece —
below bar).

**Flagged-only (4):**

1. **Alleged Vercel dark-web credential sale (2026-09-27/28).**
   SOCRadar dark-web report via DailyDarkWeb, relayed by
   undercodenews.com: a threat actor allegedly offers Vercel access
   keys, source code, database access, and employee-level API/NPM/
   GitHub tokens. **Gate unmet:** listing unverified; no Vercel
   confirmation. Watch-only — do-not-conflate with the April-2026
   breach.
2. **MongoDB Atlas Agent Engine (alleged 2026-09-29 launch).**
   Third-party LinkedIn analysis claims MongoDB "officially
   launched the Atlas Agent Engine on September 29" — unified
   execution, memory, and governance for agents on corporate
   databases. **Gate unmet:** single LinkedIn claim, no
   first-party/vendor confirmation. Below bar until a MongoDB page
   confirms.
3. **Vercel "eve" — new agent-framework surface.** First-party
   mention in `vercel/vercel-plugin`
   `skills/knowledge-update/SKILL.md`: "eve: Vercel's
   filesystem-first framework for durable AI agents... durable
   sessions, tools, skills, connections, channels, sandboxes,
   subagents, schedules, evals, and frontend clients. Public docs:
   `https://eve.dev/docs`". **Gate unmet:** novelty/recency
   unconfirmed — not a dated vendor launch announcement.
4. **Amazon Bedrock Managed Agents (OpenAI-powered).** Appears in
   OpenAI's official DevDay recap (2026-09-29): "runs
   OpenAI-powered agents inside AWS". **Gap:** first-party AWS page
   not yet read — needs vendor-page confirmation at fold before any
   filing.

## Standing-item state

- **C11 FILE ON CLOSE — armed.** Modal $750M and Baseten ~$26B both
  still unclosed.
- **C12 — OPEN (57th consecutive first-party read).** AgentComputer
  still publishes no egress pricing line.
- **C68 — RESOLVED (filed this pass).** Keynote graded 6 CONFIRMED /
  1 PARTIALLY-CONFIRMED; the "o"-name leak is refuted, its substance
  confirmed as Dots.
- **Modal egress billing — effective 2026-10-01** (one calendar day
  after this read). First-party re-confirm post-effective-date —
  the next scheduled daily slot grades effectiveness.
- **Vercel Drives GA — standing tracked item** (public beta since
  2026-09-23; no GA language).
- **Prime Sandboxes — FILED (C48, vendor-verified 2026-09-25).**
- **NanoCo re-grade bar — unmet.** File only on a first-party
  sandbox/compute announcement.
- **Hugo CVE-2026-100690 — third-party-only.** File on first-party
  GHSA only.
- **Daytona V0.220.0** (SEP 29 2026, "Sandbox queue timeout and spot
  eviction errors") — watch-doc delta only.
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.

## Watch-outs for the next slot

Modal egress billing effective 2026-10-01 — the named-exception
full pass tomorrow grades first-party effectiveness (not just
pre-effective posture); C11 FILE ON CLOSE; Drives GA standing
tracked item; Vercel "eve" novelty watch; Amazon Bedrock Managed
Agents and MongoDB Atlas Agent Engine need first-party page reads
before any filing; Hugo CVE-2026-100690 third-party-only (file on
first-party GHSA only); NanoCo first-party sandbox/compute
announcement is the re-grade bar; the alleged Vercel dark-web
credential sale stays watch-only (do-not-conflate with the
April-2026 breach); surveyor timestamp-honesty rule in force.
