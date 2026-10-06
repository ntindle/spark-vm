# Competitor watch — 2026-10-06 (morning, cycle 63)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-62 baseline —
**14 VERIFIED NO-CHANGE, 3 VERIFIED DELTA, 0 UNVERIFIED** (20 opens /
19 successes / 1 established failure / 0 retries / 0 searches; 17
enumerated items + 1 standing re-carry + 1 out-of-list read). Surveyor
B: delta news scan — **1 CANDIDATE / 15 clean dedupes / 6 flagged-only**
(18 searches, 1 page opened — the fold-gate item). **Corpus move this
cycle: Amazon Bedrock Managed Agents public-preview state change
VENDOR-VERIFIED (first-party, fold into C73 per the C32
primary-source-verification fold precedent — no new C-number).**
Watch-doc deltas: Daytona V0.222.0, Microsandbox v0.7.7, Vercel
changelog sitemap count-field move. Captures:
`hidden_files/agent_notes/surveyor-a-20261006-0910.md`,
`hidden_files/agent_notes/surveyor-b-20261006-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-06 ~09:1x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (14
> VERIFIED NO-CHANGE, 3 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 17 item enumerations and its fetch stats (19 successful reads =
> 17 enumerated items + 1 standing re-carry + 1 out-of-list read; the
> 20th open is the established `boat.dev/pricing` 404
> re-confirmation, documented inside item 7b). Surveyor B's header
> (1 CANDIDATE / 15 clean dedupes / 6 flagged-only) reconciles with
> its 1 candidate + 15 dedupe + 6 flagged-only enumerations; its 1
> page open (the AWS News Blog weekly roundup) was required by the
> fold gate before grading the Bedrock public-preview state change.
>
> **Integrator note — the Bedrock public-preview state change is
> VENDOR-VERIFIED (fold, not a mint).** The standing flagged-only
> question from cycles 59–62 (limited vs public preview — third-party
> sources disagreed: neoteo.com carried an April-28-2026 "limited
> preview" origin and "AWS's current developer guide labels the
> service a public preview", while webpronews/oossa carried the
> Sep-29 DevDay "limited preview" posture) is now settled
> first-party: the AWS News Blog "AWS Weekly Roundup (October 5,
> 2026)" — aws.amazon.com, page opened and read in full — states
> verbatim "we announced a **public preview of Amazon Bedrock
> Managed Agents** powered by OpenAI". The service launch itself was
> filed cycle 58 (C73, Sept-29 DevDay re-announcement); this is a
> vendor-verified detail fold into the C73 corpus row per the C32
> precedent, not a new C-number. The DevDay announcement (Sep 29)
> predates the watch window, but the first-party public-preview
> posture is confirmed in-window (Oct-5 AWS blog) — the C60/C62
> timing caveat applies by analogy and is retired the same way.
> The cycle-62 "first-party AWS developer-guide read outstanding"
> watch-out is now satisfied via the News Blog rather than the dev
> guide; the C73 row's "carry" note is retired.
>
> **Integrator note — watch-doc deltas, no new C-numbers.**
> (1) **Daytona V0.222.0** (dated OCT 05 2026: "PTY keepalive pings
> and Android sandbox class removal" — removes the android sandbox
> class from the API client, keeps PTY sessions alive with WebSocket
> pings, cleans up temp files after downloads in the Go SDK and
> CLI; SEP 29 V0.220.0 now second, SEP 26 V0.218.0 third; no
> V0.219.x / V0.221.x on the page). Per the V0.220.0 precedent (cycle
> 57): a minor changelog delta (no new product, no pricing change),
> recorded here and not folded as a field-table change. Design
> color: a sandbox class removed from the API surface — product
> coverage reduction, the mirror image of the launch-time deltas.
> (2) **Microsandbox v0.7.7** (Maintenance: lockfile refresh #1723,
> release bump #1760; Breaking: build(ruby)! parallelize builds
> #1728; Features: HTTP CONNECT outbound proxy #1508, disable guest
> clock sync #1707, storage cache cleanup + usage reports + CLI
> polish #1637, command tree depth/display controls #1759,
> filesystem DAX support + optional init binary #1661; ~17 Fixes
> incl. secret-leak prevention #1756, libkrunfw to Linux 6.12.111
> #1740, TCP-response drain #1726; Performance: reduced paused-sandbox
> host CPU #1755). Per the v0.7.5/v0.7.6 precedent: recorded here,
> not a corpus mint. Design color: HTTP CONNECT outbound proxy is
> egress-fencing-thesis color (a vendor blessing of proxied egress
> as a first-class feature); reduced paused-sandbox host CPU is
> pause-cost color — idle-sandbox cost surface keeps tightening.
> (3) **Vercel changelog sitemap count-field move** (1386 → 1387
> total posts) with no new dated entry visible in the 2026 window
> shown — the dated tops are unchanged (still the three 2026-10-01
> entries; no 2026-10-02 through 2026-10-05 entries; no Drives GA
> anywhere; public-beta entry still 2026-09-23). Recorded as an
> anomaly, not a filing (nothing visible to file); next slot
> re-checks whether a new dated entry appears.
>
> **Integrator note — flagged-item bookkeeping.** The Cloudflare
> Containers/Sandboxes cross-tenant patch flagged item is CLOSED this
> cycle: every in-window item traces to the Sep-4-reported /
> Sep-19-remediated Oren Yomtov (Accomplish) dm-thin
> `skip_block_zeroing` incident (first-party Cloudflare Sep-24 blog;
> no exploitation evidence; no CVE) — restatement confirmed,
> nothing genuinely new. New flagged-only item: a third-party "Vercel
> KVM Zero-Day: $50K Bounty, No CVE Yet" report (tech-insider.org,
> KVM-level bug reportedly bypassing Firecracker-level mitigation,
> Vercel HackerOne bounty up to $50,000 confirmed) — third-party
> only, no vendor confirmation, no CVE; flagged-only, watch color.
> The shared Firecracker-on-KVM exposure angle is sandbox-relevant
> but stays watch-only until a vendor or CVE confirms it.

Delta-only against the cycle-62 pass
(`hidden_files/agent_notes/surveyor-a|b-20261005-0910.md`, against
`docs/COMPETITOR_WATCH_2026-10-03_MORNING_C60.md`). Read-only, no
logins, no writes.

## Surveyor A — first-party re-verification (14 / 3 / 0)

1. **Daytona changelog — VERIFIED DELTA.** New top entry: OCT 05
   2026 / V0.222.0 ("PTY keepalive pings and Android sandbox class
   removal" — removes the android sandbox class from the API client,
   keeps PTY sessions alive with WebSocket pings, cleans up temp
   files after downloads in the Go SDK and CLI). Baseline
   SEP 29 2026 / V0.220.0 ("Sandbox queue timeout and spot eviction
   errors") is now second; SEP 26 2026 / V0.218.0 third. Still no
   V0.219.x / V0.221.x on the page — the new release jumped straight
   to V0.222.0.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Top
   dated block still 2026-09-28 with the baseline items verbatim
   (secret-command fresh-tmp-dir execution; `--on-timeout restart`;
   `--kit-arg`/`--kit-args-file` passthrough; kit skills-dir writes;
   llmman v0.1.418; Linux arm64 16-CPU-per-sandbox cap; `balanced`
   preset fetching Playwright binaries from `cdn.playwright.dev`;
   guest-kernel crash recovery; writable `/etc/hosts`; experimental
   outbound UDP under sandbox network policy), then 2026-09-22,
   2026-09-21, 2026-09-15 unchanged. No new dated block above
   2026-09-28. (This cycle the date headers rendered normally — the
   cycle-62 render caveat did not recur.)
3. **Microsandbox releases — VERIFIED DELTA.** New top release
   v0.7.7. Body: Maintenance ("chore: refresh lockfiles after v0.7.6"
   #1723, "chore(release): bump microsandbox to 0.7.7" #1760);
   Breaking changes (build(ruby)!: parallelize builds #1728);
   Features (HTTP CONNECT outbound proxy #1508; option to disable
   guest clock sync #1707; storage cache cleanup, usage reports, CLI
   polish #1637; command tree depth and display controls #1759;
   filesystem DAX support and optional init binary #1661); Fixes
   (remove sandbox that never started #1724; drain TCP responses
   before closing #1726; create SFTP files as session user #1713;
   nat64_prefixes utoipa schema #1729; regenerate image VMDK
   descriptor on archive import #1712; update libkrunfw to Linux
   6.12.111 #1740; report symlinked bind mount roots #1734; apply
   exec limits before switching users #1746; publish ports without
   host routes #1754; read restored resource targets while starting
   #1741; prevent secret leaks / correct adapter behavior #1756;
   include peer message in rejected operation errors #1757; accept
   reordered image metadata on archive import #1744; surface guest
   initialization failures #1758; support secret policy modification
   options (python) #1763; keep earlier dns answers bound to a
   domain #1747); Performance (reduce paused sandbox host cpu
   #1755); Dependencies; Build (allow deprecated fetch_update for
   rust 1.99 #1725). "Full Changelog: v0.7.6...v0.7.7". Baseline
   v0.7.6 (maintenance #1715/#1721) is now second. The canonical URL
   still renders under the `superradcompany` org.
4. **Vercel (three pages).**
   a. **Changelog index — VERIFIED DELTA.** Total posts moved
      1386 → 1387. The dated tops are unchanged: still the three
      2026-10-01 entries from the C61 baseline ("Speed Insights
      deprecates First Input Delay on November 1st"; "Laya decision
      model now available on AI Gateway, free through October 31";
      "Microsoft AI models are now available on AI Gateway") — no
      entries dated 2026-10-02, 2026-10-03, 2026-10-04, or
      2026-10-05. The 2026-09-30 set (6, incl. "Vercel Sandbox now
      supports Secure Compute"), 2026-09-29, and 2026-09-28 sections
      are unchanged, same order. **No Drives GA entry anywhere in the
      dated index**; the public-beta entry is still dated
      2026-09-23. Note: the +1 post is not visible as a new dated
      entry in the 2026 window shown — recorded as a count-field
      move; dated tops verified unchanged.
   b. **Sandbox docs — VERIFIED NO-CHANGE.** Front matter still
      `last_updated: 2026-09-22`; Features list shows "Drives (beta)"
      verbatim. Related-link chrome still carries the two eve.dev
      links — chrome, not a tracked-field change.
   c. **Drives Private Beta changelog page — VERIFIED NO-CHANGE.**
      Title "Drives for Vercel Sandbox in Private Beta"; beta install
      lines (`@vercel/sandbox@beta`, `sandbox@beta`); "Sign up here
      to join the waitlist"; no GA language.
   - *Out-of-list read (4-extra, excluded from totals):* the Drives
     public-beta page still renders "Drives for Vercel Sandbox are
     now available in public beta on Hobby, Pro, and Enterprise"
     with iad1 Drive pricing verbatim (storage $0.05 per GB-month,
     reads $0.0015 per GB, writes $0.004 per GB; Hobby includes 15
     GB storage + 30 GB each of reads/writes per month) — unchanged
     since the C56 observation. No GA language; the dated sitemap
     still dates it 2026-09-23. The standing tracked item is GA,
     unmet.
5. **DigitalOcean Harness Runtime pricing — VERIFIED NO-CHANGE.**
   Opened at the corpus canonical
   `docs.digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/`
   (the www.digitalocean.com host 404s for this path — established).
   All content matches the C62 baseline verbatim: all five figures
   ($0.044/vCPU-hour; $0.0095/GB-hour; Session Storage
   $0.05/GiB-month; Public Internet Egress $0.01/GiB; Snapshots and
   Checkpoints $0.05/GiB-month), the active-CPU footnote ("Active CPU
   billing is coming soon. Until then, CPU is billed at 25% of the
   vCPUs allocated to your sandbox.") verbatim, the "Last verified 1
   Oct 2026" stamp intact, and the full C60-expanded structure intact
   (Agent Droplets Pro $50/15%, Team $200/20%, usage-discount table,
   cost examples, fair use; Custom Sandbox Templates BYOT
   $0.05/GiB-month; Action Gateway Tool Calls; Model Inference;
   sandbox-shape price table XSmall `mars-1vcpu-1gb` $0.0535/hr
   through XLarge `mars-16vcpu-32gb` $1.008/hr).
   - *Standing re-carry (a, excluded from totals):* the Harness
     Runtime limits page (docs.digitalocean.com host) still shows
     "Last verified 1 Oct 2026"; 100 sessions per team "depending on
     your resource tier"; Agent Droplets plans allow unlimited agents
     (fair use); monthly active compute cap 744 hours per session;
     default sandbox `mars-2vcpu-4gb`; 50 GiB maximum file size;
     "Sandbox egress is unrestricted unless the environment spec
     sets an allowlist"; webhook lifecycle notifications not
     supported; live preview not available; private VPC
     resources/peering not supported; VPC-scoped model access keys
     not supported. All verbatim against the C62 re-carry.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** The page
   reads verbatim, unchanged: "Starting October 1, 2026, Modal
   charges for network egress."; Starter 1 TiB / Team 10 TiB /
   Enterprise 100 TiB included per billing cycle; "Egress beyond the
   included amount is billed at $0.04 per GiB."; "Starting October 1,
   2026, egress is charged. Your first bill including egress arrives
   on November 1, 2026."; "Reads from and writes to Modal Volumes do
   not count as network egress." Still no went-live banner or usage
   wording change — live-in-effect per the C58 effectiveness grade,
   five days post-effective.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (7a–7d).**
   a. E2B pricing — Hobby FREE ("$100 one-time usage credit"), Pro
      $150/month, Enterprise CUSTOM; 1 vCPU $0.000014/s, 2 vCPU
      [Default] $0.000028/s. Verbatim.
   b. boat.dev pricing — `boat.dev/pricing` still returns HTTP 404
      (fourth consecutive cycle confirmed); `docs.boat.dev/pricing`
      ("Pricing & Limits") figures verbatim unchanged: small $0.018
      / default $0.036 / large $0.072 / xlarge $0.200 per hour;
      plans $20/mo → 100 at once, $100/mo → 300, $500/mo → 1,000,
      $2000/mo → 2,000; Trial: 25 free hours. (Comparison tables and
      benchmark rows are additional page content; tracked figures
      unchanged.)
   c. TermSquad pricing — tiers unchanged: Starter $9/month (2 vCPU
      / 4 GB RAM / 40 GB SSD NVMe), Builder $19/month (4 / 8 GB /
      75 GB), Power $29/month (6 / 12 GB / 100 GB), Ultra $49/month
      (8 / 24 GB / 200 GB).
   d. AgentComputer pricing — CPU $0.07 per CPU-hour, Memory
      $0.04375 per GB-hour, Hot Storage $0.000683 per GB-hour
      (running), Cold Storage $0.000027 per GB-hour (stopped). No
      first-party egress pricing line — **C12 stays OPEN (63rd
      consecutive first-party read).**
8. **Boat legacy domains — VERIFIED NO-CHANGE (8a–8d, canonical
   set).** `ascii.dev` and `box.ascii.dev` both serve the Boat
   homepage natively (page title "boat: Cheapest, Most Powerful
   Sandboxes for Agents", identical content, no redirect); the two Y
   Combinator company pages (`/companies/ascii`, `/companies/boat`)
   both render the Boat listing natively ("Boat: The best cloud VMs
   for billions of agents", identical content).
9. **Hugo advisories — VERIFIED NO-CHANGE.** Top entries are the 4
   Sep-28-2026 Moderate advisories in baseline order (GHSA-3jfr-vjcq-
   7jvf css.Sass; GHSA-r4xx-89rf-5424 js.Build; GHSA-6c8w-mpp8-9w47
   nested-mount symlink; GHSA-wcpj-vcvm-j4pg stored XSS heading ID);
   render capped at exactly 10 entries; no "100690" anywhere on the
   page. CVE-2026-100690 remains third-party-only — file on
   first-party GHSA only. The canonical
   `github.com/gohugoio/hugo/security/advisories` page renders
   normally.

## Surveyor B — delta news scan (1 / 15 / 6)

### C11 FILE-ON-CLOSE gate — NOT triggered

- **Modal $750M @ $15.75B — still unclosed.** techcrunch.com
  (2026-09-28 original, recrawled): "nearing a $750 million funding
  round led by Accel"; kaupr.io (2026-09-30): "close to a US$750
  million round led by Accel... Modal Labs declined to comment";
  inshorts headline "raises $750 mn" but body "is set to raise" —
  headline/body split again, not a close. New in-window color:
  illustrated-ai.com calls Modal "reportedly nearing" and notes the
  platform "supports inference as well as training, agent sandboxes,
  notebooks, batch processing and serverless functions" —
  third-party analysis, not a close.
- **Baseten ~$26B — still unclosed.** justpaste.in/TechCrunch recrawl:
  "Baseten is nearing an infusion of capital at a $26 billion
  valuation, doubling what it was worth in June, Bloomberg
  reported"; analyticsinsight.net: "reportedly discussing funding
  rounds"; runtimewire.com: "Those are prospective private-market
  valuations, not cash raised or finalized prices." The
  siliconangle.com September-2025 $150M Series D stale hit remains
  ignored as such.

### CANDIDATES (1 — corpus move, detail fold into C73, not a new C-number)

1. **Bedrock Managed Agents limited→public preview state change —
   RESOLVED first-party.** The AWS News Blog "AWS Weekly Roundup"
   (aws.amazon.com, 2026-10-05, first-party — page opened to
   confirm): "Last week, we announced a **public preview of Amazon
   Bedrock Managed Agents** powered by OpenAI" — with the "public
   preview" link phrasing pointing to the service docs. This settles
   the standing flagged-only question (limited vs public preview):
   AWS itself postures the launch as public preview. In-window
   (2026-10-05 first-party post), vendor-confirmed (aws.amazon.com),
   and a sandbox/compute product fact — a corpus move. The product
   launch itself was already filed (C73, Sep-29 DevDay);
   **folded as a vendor-verified detail into the C73 corpus row per
   the C32 precedent, not a new C-number.** Note the C75-style
   integrator timing caveat: the DevDay announcement (Sep 29) is
   pre-window, but the first-party public-preview posture is
   confirmed in-window via the Oct-5 AWS blog.

### Clean dedupes (15)

1. **Modal egress billing went-live signal — none observed.** GitHub
   mirror (visheshgubrani/vod) of Modal's egress guide is
   pre-effective text ("Starting October 1, 2026, egress is
   charged. Your first bill including egress arrives on November 1,
   2026."). dev.to "Modal Serverless GPUs in Production" treats
   egress as "not sufficiently itemized... unknown, not as zero" —
   author analysis, not a go-live signal. devops-daily "8 Managed
   Agent Runtimes Compared" is product color. **First-party
   re-confirm remains Surveyor A's lane.**
2. **Vercel Drives GA — no GA language.** community.vercel.com "Vercel
   Weekly (2026-09-28)": "Drives for Vercel Sandbox are now in public
   beta" — unchanged; vercel.com/changelog public-beta page renders
   "now available in public beta on Hobby, Pro, and Enterprise."
   Public beta since 2026-09-23 stands.
3. **Daytona — no in-window vendor news.** Only the OpenHands PR
   syndication recrawls (retired pre-window — wire is Oct 31, 2024)
   and the Feb-2026 $24M Series A recrawl (startup-weekly.com).
   Third-party GitHub engineering (swcstudiospace/clippyos sandbox
   probe-timeout fix) — below fold.
4. **E2B — no in-window vendor news.** Only third-party engineering:
   e2b-dev/e2b #1749 (SDK-side default removal, v2 endpoints) is
   dev-process color; downstream users (tidebreak, pmoves-skills,
   brightwave-inc) — below fold.
5. **Microsandbox — nothing newer than v0.7.6.** The "Release v0.7.7"
   search hit is pieroproietti/oa-tools (an unrelated project).
   superradcompany results are release-process PRs (#1588 npm
   provenance, DEVELOPMENT.md recrawls); zerocore-ai/microsandbox is
   a fork. **v0.7.6 remains the corpus baseline** (the v0.7.7 move
   was established first-party in Surveyor A's lane).
6. **boat.dev — no new vendor news.** Third-party engineering only:
   amitgb14/conch boat.dev provider integration (trial-account
   mechanics: 2-hour free-trial life, sshEndpoint fallback, error
   codes billing_required/trial_auto_stop_required);
   starslingdev/hpc-sandbox-benchmarks driver-kit provider work
   (per-minute snapshots, delete-teardown behavior);
   zozo123/ariflow-swfactory fork-capability declaration (Sep 18,
   pre-window). Below fold.
7. **TermSquad — Sep-15 launch press recrawls only**
   (finance.minyanville.com marketer-media syndication);
   termsquad.com homepage unchanged. Nothing new.
8. **C75 — DigitalOcean Agent Droplets.** Third-party recaps of the
   company-issued 2026-10-01 release only: cryptorank.io / Forkast
   analysis ("Turns Agent Infrastructure Into a Commodity SKU"),
   businesswire + bizwire syndications. New color carried verbatim
   from the release: $5-in-credit free trial, hosted inference Kimi
   K3/GLM 5.3, "resume from a pause in about 300 milliseconds (in
   DigitalOcean testing)". **Filed — dedupe; no new vendor facts.**
9. **Docker Cloud Sandboxes — Sep-24 launch recrawls only.** The
   lifeboat.com "Critical Docker Sandboxes Flaw" piece is the
   corpus-known 77179/79994 disclosure (Sep 18, not new). No new
   vendor facts — **dedupe.**
10. **Alleged Vercel dark-web credential sale — still unconfirmed,
    watch-only.** New color: malware.news notes the April Vercel
    breach "is a rare case where ShinyHunters publicly denied
    involvement and said the real perpetrators were impersonating the
    brand"; gameworkerkim CTI report confirms the April-19
    Context.ai origin. All items still trace to the April-2026
    incident — **do-not-conflate stands; the new-sale claim remains
    unconfirmed.** cybersecuritynews / pulse.bot / prismor.dev items
    are April-2026 color.
11. **Hugo CVE-2026-100690 — still third-party-only.** No
    100690-specific GHSA anywhere this pass: gohugoio/hugo advisory
    results are the older sibling GHSAs (GHSA-8j34-9876-pvfq Windows
    cwd execution, cve.report 35166/44301 siblings); bigchange/hugo
    (a fork) shows no published advisories. Corpus baseline holds:
    TheHackerWire automated page, Sep 26. **Gate unmet — file on
    first-party GHSA only.**
12. **NanoCo — still framework/harness color; re-grade bar unmet.**
    New color: en.wedoany.com: "Israel's NanoCo Raises $12 Million
    Seed Round for NanoClaw, Rejects $20 Million Acquisition Offer";
    NanoClaw runs agents "inside micro-VMs via Docker sandboxes" —
    it is a **consumer** of sandbox infra, not a provider.
    venturebeat.com NanoClaw+Vercel+OneCLI partnership
    (approval-dialogs) stands. No sandbox-infrastructure facts.
13. **Pre-window sweeps — no new movement.** Snowflake:
    venturebeat.com Cortex AI Gateway dynamic model routing (up to 3x
    token-cost cut, vendor-tested) — agent-governance color,
    pre-window-era product lineage (July 2026 AI Gateway launch),
    not sandbox infra. No CoreWeave/Blitzy movement. yourstory /
    bizpreneurme Cortex Agents pieces are the Feb-2025
    public-preview-era recrawls.
14. **C72 / C74 — not sighted this pass; no movement.** (C73 carried
    under CANDIDATES above.)
15. **Vercel "eve" — retired as corpus-known.**
    community.vercel.com "How Vercel Built a Superagent with eve" —
    adoption color only.

### Flagged-only (6)

1. **Perplexity SPACE sandbox-escape research — carry, new
   first-party color.** Perplexity's own blog "How we engineer safer
   agents" (perplexity.ai/hub/blog): SPACE as "an ephemeral
   Firecracker microVM per task, credentials kept outside the
   sandbox, outbound traffic controlled at the node level," plus the
   "Escaping SPACE: Part I" red-team results (108 runs, zero VM-host
   escapes; partial-network DNS-spoofing/CDN-IP bypasses — the
   resilientcyber #116 nine-of-ten-platform bypass color stands: E2B,
   Vercel, Modal, Daytona, Fly.io Sprites, microsandbox, Deno named;
   NVIDIA OpenShell and Cloudflare Sandbox held). Still third-party
   research (plus Perplexity's own product blog), no CVE, no vendor
   confirmation from the named vendors — **flagged-only, watch
   color.**
2. **Cloudflare "Clef" decision models — carry, wider syndication.**
   Oct 1 launch now also carried by aiweekly.co (latency/benchmark
   recap: 209.3ms Clef vs 524.1ms Jev median; 38.8ms Clef-flash),
   dev.to hands-on (Workers AI unit pricing $0.24/M input Clef,
   $0.09/M Clef-flash), sloptvnews.com, theweightedaverage.com,
   datanorth.ai. metirai.com "Decision Models Wave" folds in
   Perplexity pplx-decider-v1-27b and AWS Strands Decider 2B — the
   AWS blog itself (Oct 5, in the opened page) names "Introducing
   Strands Decider" as "one of a new class of decision models...
   Strands Decider 2B is a small, open source, decision model." All
   lane-adjacent model weights, not a hosted sandbox product —
   **flagged-only. Re-adopt only if sandbox-adjacent facts land.**
3. **Cloudflare Containers/Sandboxes cross-tenant patch note —
   RESOLVED as restatement; flagged item closed.** Every in-window
   item this pass traces to the same incident: cyber.netsecops.io and
   nextbyte.live recrawls of the Sep-4-reported Oren Yomtov
   (Accomplish) dm-thin `skip_block_zeroing` incident — remediation
   complete September 19, 2026; no exploitation evidence; no CVE.
   **No genuinely-new cross-tenant disclosure observed.** The flagged
   item is closed this cycle; watch color continues.
4. **Vercel KVM zero-day — NEW flagged item, third-party, watch
   color.** tech-insider.org: "Vercel KVM Zero-Day: $50K Bounty, No
   CVE Yet [2026]" — a KVM-level bug "effectively bypasses"
   Firecracker-level mitigation; Vercel runs a public HackerOne
   bounty "up to $50,000 confirmed"; the piece notes the shared
   Firecracker-on-KVM stack means E2B, AWS Lambda/Fargate, Daytona
   and others "would need to evaluate its own exposure."
   Third-party only, no vendor confirmation from Vercel, no CVE.
   **Does not meet the fold gate; flagged-only, watch color.**
5. **Modal multi-node GPU clusters GA (Oct 1, 2026) — carry.**
   Vendor-confirmed (runtimewire, primary source Modal Newsroom) but
   training/inference compute with gang scheduling + RDMA — not the
   sandbox surface; effective-date predates the window. **Flagged
   with the predates-window caveat; carry.**
6. **Cloudflare Containers rebuild (~Sept 30, first-party) — carry,
   predates window.** durable_object scheduling policy, ~648ms median
   startup, `cloudflare/debian-trixie` prebuilt image (Debian Trixie
   Slim + Node.js 24.20.0 LTS), filesystem snapshots in public beta,
   Sandbox SDK 1.0. Per the in-window filing rule, no C-number —
   **carry forward.**

## Standing-item state

- **C11 FILE ON CLOSE — armed, gate NOT triggered.** Modal $750M and
  Baseten ~$26B both still unclosed ("nearing"/"closing in
  on"/"in talks"/"under discussion"/"prospective private-market
  valuations, not cash raised").
- **C12 — OPEN.** Nothing new this pass.
- **Modal egress billing — effective 2026-10-01.** No third-party
  went-live signal; first-party re-confirm is Surveyor A's lane.
- **Vercel Drives GA — standing tracked item** (public beta since
  2026-09-23; no GA language anywhere this pass).
- **Vercel "eve" — retired as corpus-known.**
- **NanoCo re-grade bar — unmet** (framework/harness color only).
- **Hugo CVE-2026-100690 — third-party-only** (file on first-party
  GHSA only).
- **C72 / C73 / C75 — FILED.** C75 recaps this cycle are clean
  dedupes. **C73 carries a new vendor-verified fold: the Oct-5
  first-party AWS confirmation of public-preview state.**
- **Alleged Vercel dark-web credential sale — UNCONFIRMED,
  watch-only.** Do-not-conflate with April-2026 (Context.ai) stands;
  ShinyHunters publicly denied involvement in the April sale.
- **Cloudflare cross-tenant disk-block disclosure — watch color;
  flagged-only #3 resolved as restatement this pass; flagged item
  closed.**
- **Vercel KVM zero-day — NEW flagged item** (third-party,
  tech-insider.org, no CVE, watch color).
- **Modal July compromise — resolved/watch-only;** no new facts.
- **Aged out stay out:** C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-outs this pass; no re-folds; C11 quiet stays 0/3.

## Watch-outs for the next slot

C11 FILE ON CLOSE; Modal egress first-party re-confirm (A lane);
Drives GA standing; Hugo CVE-2026-100690 third-party-only; NanoCo
re-grade bar; Perplexity SPACE wire (new first-party "How we engineer
safer agents" color); **Vercel KVM zero-day third-party report —
watch for vendor confirmation or CVE**; Cloudflare Clef
(lane-adjacent models — re-adopt only if sandbox-adjacent facts
land); Bedrock C73 public-preview fold (done this cycle);
Cloudflare Containers rebuild + Modal GPU-clusters GA carries
(predate window); Vercel sitemap 1386→1387 count anomaly — re-check
whether a new dated entry appears; surveyor timestamp-honesty rule in
force.
