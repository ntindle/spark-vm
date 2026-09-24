# Competitor watch — 2026-09-24 (evening)

Delta-only update against the afternoon pass
(`docs/COMPETITOR_WATCH_2026-09-24_AFTERNOON.md`). Survey window
**2026-09-24 ~09:56–10:16 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set plus the Vercel Drives GA watch and the C36/C41/C43
re-verifications; (B) an open-web in-lane news scan plus vetting of the
afternoon pass's carried positions. Surveyor captures live in the
loop's `agent_notes/` workspace
(`surveyor-a/b-20260924-0954.md`), not the repo.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) or company-issued announcement — a stricter claim than
VERIFIED, used only when we fetched the thing itself. **THIRD-PARTY** =
reported by press/third-party sources, including vendor-announcement text
read on a syndicated copy rather than the vendor's own page.
**snippet-only** = a THIRD-PARTY sub-state: seen only via search
snippet or aggregator digest this run, not fetched and read — no
stronger claim than its source's blurb. **INFERRED** = my
characterization, labeled as such. **UNVERIFIABLE** = no public source
exists to check against. **UNVERIFIED** = a public page exists but
could not be fetched this run (never reported as NO-CHANGE).
**VERIFIED absent** = the vendor's own page was read this run and the
item is confirmed not present on it.

## 1. The tracked set — 8/8 VERIFIED NO-CHANGE

All reads within the survey window (~09:59–10:07 CDT); all values below
VERIFIED on the vendor's own page. Zero fetch failures — nothing labeled
UNVERIFIED. The afternoon pass ended the eleven-pass full-quiet streak
on Daytona's two SEP 24 changelog entries; nothing has moved since, so
this pass is fully quiet again — a new streak opens at one.

- **Daytona — VERIFIED NO-CHANGE.** Changelog
  (https://www.daytona.io/changelog) is still topped by **SEP 24 2026 /
  V0.216.2** ("CLI login through WorkOS"), with SEP 24 / V0.216.1
  ("API key organization ID and CLI update warning fix") second and
  SEP 23 / V0.216.0 third — exactly the afternoon baseline. No new
  entries.
- **Docker Sandboxes — VERIFIED NO-CHANGE.** Release notes
  (https://docs.docker.com/ai/sandboxes/release-notes/) still top out
  **2026-09-21** (v3 kits); next entry 2026-09-15. Nothing dated
  09-22/09-23/09-24.
- **Microsandbox — VERIFIED NO-CHANGE.** Releases
  (https://github.com/superradcompany/microsandbox/releases) still top
  out **v0.7.1**; next release v0.7.0.
- **E2B — VERIFIED NO-CHANGE.** Pricing (https://e2b.dev/pricing):
  Hobby free with $100 one-time credit / 1h sessions / 20 concurrent;
  Pro $150/mo / 24h sessions / 100 concurrent (expandable to 1,100);
  per-second table $0.000014/s for 1 vCPU. All match baseline.
- **boat.dev (Boat) — VERIFIED NO-CHANGE.** Pricing
  (https://docs.boat.dev/pricing): rate table small $0.018 / default
  $0.036 / large $0.072 / xlarge $0.200 per sandbox hour; per-second
  billing; stopped sandboxes free; 25 free trial hours — all match.
- **TermSquad — VERIFIED NO-CHANGE.** Plan table
  (https://termsquad.com/): Starter $9/mo 2 vCPU/4 GB/40 GB SSD NVMe;
  Builder $19/mo 4 vCPU/8 GB/75 GB; Power $29/mo 6 vCPU/12 GB/100 GB;
  Ultra $49/mo 8 vCPU/24 GB/200 GB. All match.
- **AgentComputer — VERIFIED NO-CHANGE.** Pricing
  (https://www.agentcomputer.ai/pricing): $0.07/CPU-hour,
  $0.04375/GB-hour, hot storage $0.000683/GB-hour (running), cold
  storage $0.000027/GB-hour (stopped). All match.
- **DigitalOcean Managed Agents — VERIFIED NO-CHANGE.** Pricing docs
  (https://docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/):
  stamp still **"Last verified 22 Sep 2026"**; CPU $0.044/vCPU-hour,
  memory $0.0095/GB-hour, session storage $0.05/GiB-month;
  snapshots/checkpoints $0.05/GiB-month; BYOT $0.05/GiB-month; egress
  $0.01/GiB; shapes mars-1vcpu-1gb–mars-16vcpu-32gb. All match.

## 2. Carried asks

- **Vercel Drives GA watch — VERIFIED NO-CHANGE (24th consecutive
  no-change pass).** Pricing page VERIFIED
  (https://vercel.com/docs/sandbox/pricing): `last_updated` still
  **2026-09-10**; all values match baseline (Drive Storage
  $0.05/GB-month; Reads $0.0015/GB; Writes $0.004/GB; up to 4 drives
  per sandbox, 1 TiB default / 1 GiB Hobby, 16 TiB max; downloads free;
  session caps 45min/24h; concurrency 10/10,000). The changelog page
  VERIFIED this run
  (https://vercel.com/changelog/drives-for-vercel-sandbox-are-now-in-public-beta):
  Drives remain in **public beta** on Hobby/Pro/Enterprise — no GA
  announcement, no pricing change. The 2026-09-24 changelog entries are
  adjacent (e.g. Vercel Connect / TanStack AI), not in-lane. **Still
  public beta, NOT GA** — no GA move, no fold.
- **C36 Google Agent Substrate — VERIFIED unchanged this pass.** The
  Google Cloud blog
  (https://cloud.google.com/blog/products/containers-kubernetes/agent-substrate-available-on-gke)
  carries the standing terms verbatim: *"Agent Substrate is open source
  and available to all GKE customers for non-production workloads. GA
  support for production is available via allowlist."* No new
  datapoints.
- **C41 Alibaba FC Agent Sandbox billing — VERIFIED unchanged.** The
  aliyun-fc/fc-docs pay-as-you-go page at HEAD (`39b6c3a`) matches the
  folded values value-for-value: invite-only preview; active/light/
  deep hibernation states; 15 GiB disk free allowance on active + light
  hibernation; Eco 0.00936/vCPU-h + 0.004608/GiB-h, Std
  0.01224/0.006012, Pro 0.01872/0.009360; disk 0.00031896 mainland /
  0.00025308 outside USD/GiB-h; per-second billing ("usage shorter than
  1 second is billed as 1 second"). HEAD commit is unchanged (`39b6c3a`).
  No re-fold.
- **C43 Google Gemini Agent Environment — VERIFIED unchanged.** The
  vendor's own Gemini API docs
  (https://ai.google.dev/gemini-api/docs/agent-environment) still show
  the folded surface: managed Linux sandboxes for agents,
  `environment_id` reuse, git sources, network allowlists, credential
  references, pre-installed Ubuntu toolchains. No re-fold.

## 3. New findings — none in-lane dated 2026-09-24; three fold candidates queued

No in-lane launches, GA moves, pricing moves, or funding dated
2026-09-24. The news scan surfaced three in-lane-adjacent candidates
that are **not folded this pass** — all sit below the corpus's
primary-source-verification bar (THIRD-PARTY / snippet-only), so they
are queued with their provenance intact rather than assigned C-numbers:

1. **Google Shell + Computer Use sandboxes GA (Sept 9 2026)** —
   snippet-only (Gemini Enterprise Agent Platform release notes via
   search snippet, not fetched): Shell sandboxes (isolated Linux
   container, /exec API), VPC Service Controls/PSC, CMEK. Source:
   https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes.
   Next pass: read the release notes directly; if VERIFIED, fold as a
   C-number sibling to C43/C36.
2. **Docker Sandboxes security advisory (Sept 15 2026)** — THIRD-PARTY
   (The Hacker News et al.): CVE-2026-77179 (Critical 9.4) +
   CVE-2026-79994 (High 8.7), macOS VM escape via virtio-fs symlink
   following; fixed in 0.42.0. Sources:
   http://thehackernews.com/2026/09/critical-docker-sandboxes-flaw-lets.html,
   https://www.redsecuretech.co.uk/blog/post/docker-sandboxes-escape-flaw-hits-macos/1525.
   Next pass: vendor advisory / release confirmation; if VERIFIED,
   fold as a security-posture note on the Docker row (a CVE in a
   tracked vendor is competitive color, not a launch).
3. **"Agentic cloud" framing trend (two-vendor)** — Alibaba's AgentCore
   + "Agent Native Cloud" roadmap at Apsara Conference (snippet-only,
   via aiagentstore.ai digest, Sept 24) plus Huawei's "Open Agentic
   Cloud" (Sept 18). Managed-agent platforms, not sandbox execution
   infra per se — adjacent-watch framing, recorded for the trend, not
   folded.
- **Namesake-collision warning (filed so it never lands in the
  corpus):** Guava (voice AI co.) launched a voice model literally
  named "Daytona" (Sept 23, BusinessWire) — unrelated to Daytona
  sandboxes. Source:
  https://lifestyle.thepointnews.com/story/882176/guava-launches-daytona-a-state-of-the-art-voice-model-alongside-an-open-benchmark-evaluating-voice-agent-performance/

Afternoon-pass positions all hold: OpenAI Agents API "opened to all
developers" stays **THIRD-PARTY** (no contradiction, no new movement);
Tencent DataBuddy stays **adjacent-watch** (Sept 22, no new movement);
the **deprecated-row sunset convention stays proposed-not-codified**
(no new evidence).

## 4. Corpus actions

1. **No fold this pass.** Tracked-set re-reads and carried-ask
   re-verifications are watch-doc records only, per the fold
   convention (no field-table change on NO-CHANGE).
2. **Three fold candidates queued** (§3) pending primary-source
   verification — a next pass may verify and fold with C-numbers; no
   C-number is assigned speculatively.
3. **No launches, pricing moves, or funding dated 2026-09-24** — none
   of today's adjacent items (Island $400M Series F, Alibaba
   AgentCore, Darktrace Signal Labs — see §5) meet the in-lane bar.

## 5. In-lane and adjacent news scan (2026-09-24, THIRD-PARTY unless noted)

**No in-lane sandbox-infra items dated 2026-09-24.** Today's items are
adjacent color, deliberately excluded from the corpus:

- **Island — $400M Series F at $6.4B valuation** (THIRD-PARTY, Reuters
  via syndicated copy): Dallas enterprise-browser security startup;
  framing explicitly cites rogue AI agents as the driver. Out-of-lane
  (secure browser), adjacent as another datapoint that agent-execution
  risk is now a funded category. Sources:
  https://northlandnewsradio.com/2026/09/24/ai-startup-island-valued-at-6-4-billion-in-latest-funding-round/,
  https://techstartups.com/2026/09/24/browser-security-startup-island-raises-400m-at-6-4b-valuation-to-defend-against-rogue-ai-agents/
- **Alibaba — AgentCore + "Agent Native Cloud" roadmap** (snippet-only,
  aiagentstore.ai digest; not fetched): full-stack agentic roadmap —
  AgentCore enterprise agent platform, Agent Context (up to 67% token
  reduction claimed), Agent Security Center. Managed-agent platform,
  adjacent-watch. Source: https://aiagentstore.ai/ai-agent-news/this-week
- **Darktrace launches Signal Labs** (THIRD-PARTY, GlobeNewswire via
  syndication): new research initiative for emerging AI agent risks;
  researches agents "inside safe, sandboxed environments" — methodology
  wording, not a product. Out-of-lane. Source:
  https://wkow.marketminute.com/article/gnwcq-2026-9-24-darktrace-launches-signal-labs-to-research-emerging-risks-of-enterprise-ai-agents

Deliberately dropped as out-of-lane or out-of-window: SoundHound OASYS
Edge (Sept 24, voice-agent edge architecture — out of lane); Modal /
Baseten funding talks (Sept 23, Bloomberg THIRD-PARTY — talks only);
Docker v3 kits are the standing baseline (2026-09-21); Vercel Sandbox
itself GA since Jan 2026 per third-party skill docs (not new).

## 6. Verdict

**8/8 tracked-set quiet; zero fetch failures; no in-lane moves dated
2026-09-24.** The full-quiet streak re-opens at one after the afternoon
pass's Daytona move. The Vercel Drives beta watch extends to **24
passes** with still no GA — the beta is now longer-lived than the whole
watch program's fast-moving window, and the streak arithmetic stays
honest: quiet means no vendor-page movement, not no market movement.
C36, C41, and C43 re-verified unchanged. Today's adjacent color
(Island's $400M raise on rogue-agent framing, Alibaba's "Agent Native
Cloud", Darktrace's Signal Labs) keeps pointing at agent-execution
risk as a funded category without producing an in-lane product move.
Three fold candidates are queued for primary-source verification
(Google Shell/Computer Use GA, the Docker Sandboxes CVEs, the
agentic-cloud framing trend) — none folded speculatively. The corpus
adds no C-numbers tonight; the watch's discipline is the finding.
