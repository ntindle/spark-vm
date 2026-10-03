# Competitor watch — 2026-10-03 (morning, cycle 60)

**Two-surveyor pass — PRE-SCREEN-TRIGGERED FULL PASS** (per the P77
holding-pattern ruling: the morning pre-screen found a corpus move —
a DigitalOcean Harness Runtime pricing-page expansion on the A lane
— so the full two-surveyor watch runs). Surveyor A: first-party
vendor re-verification against the cycle-59 baseline — **16 VERIFIED
NO-CHANGE, 1 VERIFIED DELTA, 0 UNVERIFIED** (21 opens / 19 successes /
0 retries / 2 corrected failures / 0 searches; 17 enumerated items +
1 standing re-carry + 1 out-of-list read). Surveyor B: delta news
scan — **0 CANDIDATES / 20 clean dedupes / 4 flagged-only** (16
searches, 0 pages opened — nothing met the fold gate, so no
vendor-confirmation open was needed). **Corpus move this cycle: the
DigitalOcean Agent Droplets packaging (C75, filed cycle 59 from the
company-issued Oct-1 release) is now surfaced first-party** —
DigitalOcean's own Harness Runtime pricing page now carries the
Agent Droplets plans with dollar pricing (Pro $50 with 15% usage
discount, Team $200 with 20%), plus a new BYOT custom-template section ($0.05/GiB-month — the figure itself was already filed 2026-09-26, the section is new), Action Gateway / Model Inference
sections, and a sandbox-shape price table. Folded into the C75
corpus row as a vendor-verified first-party fold (C32 precedent).
Captures:
`hidden_files/agent_notes/surveyor-a-20261003-0910.md`,
`hidden_files/agent_notes/surveyor-b-20261003-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-03 ~09:1x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 1 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 17 item enumerations and its fetch stats (19 successful reads =
> 17 enumerated items + 1 standing re-carry + 1 out-of-list read,
> all documented separately; the 2 failures were HTTP 404s — the
> established `boat.dev/pricing` 404 and the moved DigitalOcean
> pricing URL — each corrected via a vendor-owned path). Surveyor
> B's header (0 CANDIDATES / 20 clean dedupes / 4 flagged-only)
> reconciles with its 1-candidate-empty + 20 dedupe + 4
> flagged-only enumerations; its 0 page opens were sufficient
> because nothing met the fold gate.
>
> **Integrator note — the DO first-party fold (VENDOR-VERIFIED).**
> The DigitalOcean Harness Runtime pricing page is materially
> expanded since cycle 59: new **Agent Droplets** plan/packaging
> sections (Pro $50/15%, Team $200/20%, usage-discount table, cost
> examples, fair use — the C75-filed Oct-1 packaging move now
> surfacing first-party with dollar figures), a new **Custom
> Sandbox Templates (BYOT)** section ($0.05/GiB-month — the figure was already filed 2026-09-26), new
> **Action Gateway Tool Calls** and **Model Inference** sections,
> and a sandbox-shape price table (XSmall `mars-1vcpu-1gb`
> $0.0535/hr through XLarge `mars-16vcpu-32gb` $1.008/hr). All five
> metered figures stand verbatim ($0.044/vCPU-hour, $0.0095/GB-hour,
> Session Storage $0.05/GiB-month, Public Internet Egress $0.01/GiB,
> Snapshots and Checkpoints $0.05/GiB-month; the "Last verified 1
> Oct 2026" stamp intact). The C59 timing caveat (publication hour
> vs the C58 scan boundary) is RETIRED — the packaging is now
> confirmed on DigitalOcean's own page. Per the C32
> primary-source-verification fold precedent, this is folded into
> the C75 corpus row + a "Watch update — 2026-10-03 (morning,
> cycle 60)" corpus section, not a new C-number. **URL migration
> watch-note:** the previous-canonical Managed Agents pricing path
> (`/managed-agents/details/pricing/`) now returns HTTP 404;
> pricing and limits now live under
> `/managed-agents/agent-harness-runtime/details/` — the next
> slot's URL list carries the new path.
>
> **Integrator note — watch-doc deltas (no new C-numbers).** The
> single A-lane delta is the DO page expansion above. The B lane
> produced no candidates this cycle — its one near-miss class is
> the flagged-only Modal multi-node GPU clusters GA (company-issued
> Oct 1 — training/inference compute with gang scheduling + RDMA,
> not the sandbox surface; predates window on the effective date).
> Surveyor B's other flagged items: a Daytona "OpenHands
> demo / agent-agnostic middleware" PR-syndication recrawl (date
> unpinable — no in-window vendor confirmation); the Cloudflare
> Containers rebuild carry (new recap color: a prebuilt
> `cloudflare/debian-trixie` image — Debian Trixie Slim + Node.js
> 24.20.0 LTS); the Bedrock limited→public preview state change
> (still third-party-only — the first-party AWS developer-guide read
> remains outstanding).

Delta-only against the cycle-59 pass (PR #861's
`docs/COMPETITOR_WATCH_2026-10-02_MORNING_C59.md`). Read-only, no
logins, no writes.

## Surveyor A — first-party vendor re-verification (mtime-bounded)

**16 VERIFIED NO-CHANGE, 1 VERIFIED DELTA, 0 UNVERIFIED.**

1. **Daytona changelog — VERIFIED NO-CHANGE.** Top entry still SEP 29
   2026 / V0.220.0 ("Sandbox queue timeout and spot eviction
   errors"), verbatim; SEP 26 2026 / V0.218.0 second, verbatim.
   Still no V0.219.x on the page.
2. **Docker Sandboxes release notes — VERIFIED NO-CHANGE.** Top entry
   still 2026-09-28 (secret-command fresh-tmp-dir execution;
   `--on-timeout restart`; `--kit-arg`/`--kit-args-file`
   passthrough; llmman v0.1.418; Linux arm64 16-CPU-per-sandbox
   cap; `balanced` preset fetching Playwright binaries from
   `cdn.playwright.dev`; guest-kernel crash recovery; writable
   `/etc/hosts`; experimental outbound UDP under sandbox network
   policy), verbatim; 2026-09-22 / 2026-09-21 / 2026-09-15 entries
   below unchanged. No new entry above 2026-09-28.
3. **Microsandbox releases — VERIFIED NO-CHANGE.** Top release still
   v0.7.6 (maintenance body intact: "chore: refresh lockfiles after
   v0.7.5" #1715, "chore(release): bump microsandbox to 0.7.6"
   #1721); v0.7.5 (full C59 body intact) second, v0.7.4 third. No
   new release above v0.7.6. The canonical URL still renders under
   the `superradcompany` org.
4. **Vercel (three pages).**
   a. **Changelog index — VERIFIED NO-CHANGE.** The first-party dated
      sitemap (`vercel.com/changelog/sitemap.md`, still 1386 total
      posts) still tops out at the three 2026-10-01 entries from the
      C59 baseline ("Speed Insights deprecates First Input Delay on
      November 1st"; "Laya decision model now available on AI
      Gateway, free through October 31"; "Microsoft AI models are now
      available on AI Gateway") — no entries dated 2026-10-02 or
      2026-10-03. The 2026-09-30 set (6, incl. "Vercel Sandbox now
      supports Secure Compute"), 2026-09-29, and 2026-09-28 sections
      are unchanged, same order. **No Drives GA entry anywhere in
      the dated index**; the public-beta entry is still dated
      2026-09-23.
   b. **Sandbox docs — VERIFIED NO-CHANGE.** Front matter still
      `last_updated: 2026-09-22`; Features list shows "Drives (beta)"
      verbatim. Related-link chrome still carries the two eve.dev
      links — chrome, not a tracked-field change.
   c. **Drives Private Beta changelog page — VERIFIED NO-CHANGE.**
      Title "Drives for Vercel Sandbox in Private Beta"; beta install
      lines (`@vercel/sandbox@beta`, `sandbox@beta`); "Sign up here
      to join the waitlist"; no GA language.
5. **DigitalOcean Harness Runtime pricing — VERIFIED DELTA.** All five
   baseline figures verbatim ($0.044/vCPU-hour; $0.0095/GB-hour;
   Session Storage $0.05/GiB-month; Public Internet Egress $0.01/GiB;
   Snapshots and Checkpoints $0.05/GiB-month), the active-CPU footnote
   ("Active CPU billing is coming soon. Until then, CPU is billed at
   25% of the vCPUs allocated to your sandbox.") verbatim, and the
   "Last verified 1 Oct 2026" stamp intact. Material page change since
   C59: the page is substantially expanded — new **Agent Droplets**
   plan/packaging sections (Pro $50/15%, Team $200/20%,
   usage-discount table, cost examples, fair use — the C75-filed
   packaging move now surfacing first-party), a new **Custom Sandbox
   Templates (BYOT)** section ($0.05/GiB-month — the figure was already filed 2026-09-26), new **Action Gateway
   Tool Calls** and **Model Inference** sections, and a sandbox-shape
   price table (XSmall `mars-1vcpu-1gb` $0.0535/hr through XLarge
   `mars-16vcpu-32gb` $1.008/hr). URL migration note: the old
   canonical `/managed-agents/details/pricing/` now returns HTTP 404;
   the page lives at
   `/managed-agents/agent-harness-runtime/details/pricing/`.
   **Filing note for the integrator:** capability/pricing figures
   unchanged — the delta is first-party surfacing of the
   already-filed C75 packaging plus a BYOT storage SKU; folded as a
   vendor-verified corpus fold.
6. **Modal network-egress billing — VERIFIED NO-CHANGE.** The page
   reads verbatim, unchanged: "Starting October 1, 2026, Modal
   charges for network egress."; Starter 1 TiB / Team 10 TiB /
   Enterprise 100 TiB included per billing cycle; "Egress beyond the
   included amount is billed at $0.04 per GiB."; "Starting October 1,
   2026, egress is charged. Your first bill including egress arrives
   on November 1, 2026."; "Reads from and writes to Modal Volumes do
   not count as network egress." Still no went-live banner or usage
   wording change — live-in-effect per the C58 effectiveness grade,
   two days post-effective.
7. **E2B / boat.dev / TermSquad / AgentComputer — VERIFIED NO-CHANGE
   (7a–7d).**
   a. E2B pricing — Hobby FREE ("$100 one-time usage credit"), Pro
      $150/month, Enterprise CUSTOM; 1 vCPU $0.000014/s, 2 vCPU
      [Default] $0.000028/s.
   b. boat.dev pricing — `boat.dev/pricing` still returns HTTP 404;
      the homepage's canonical "Pricing docs" link resolves to
      `docs.boat.dev/pricing` ("Pricing & Limits"), where the figures
      are verbatim unchanged: small $0.018 / default $0.036 / large
      $0.072 / xlarge $0.200 per hour; plans $20/mo → 100 at once,
      $100/mo → 300, $500/mo → 1,000, $2000/mo → 2,000; Trial: 25
      free hours.
   c. TermSquad homepage — tiers unchanged: Starter $9/month (2 vCPU
      / 4 GB RAM / 40 GB SSD NVMe), Builder $19/month (4 / 8 GB /
      75 GB), Power $29/month (6 / 12 GB / 100 GB), Ultra $49/month
      (8 / 24 GB / 200 GB).
   d. AgentComputer pricing — CPU $0.07 per CPU-hour, Memory
      $0.04375 per GB-hour, Hot Storage $0.000683 per GB-hour
      (running), Cold Storage $0.000027 per GB-hour (stopped). No
      first-party egress pricing line — **C12 stays OPEN (60th
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

(a) **Standing re-carry, excluded from totals — VERIFIED NO-CHANGE.**
DigitalOcean Harness Runtime limits page still shows "Last verified
1 Oct 2026"; 100 sessions per team "depending on your resource
tier"; Agent Droplets plans allow unlimited agents (fair use);
monthly active compute cap 744 hours per session; default sandbox
`mars-2vcpu-4gb`; 50 GiB maximum file size; "Sandbox egress is
unrestricted unless the environment spec sets an allowlist";
webhook lifecycle notifications not supported; live preview not
available; private VPC resources/peering not supported; VPC-scoped
model access keys not supported. All verbatim against the C59
re-carry.

## Additional out-of-list read (4-extra, excluded from header totals)

`vercel.com/changelog/drives-for-vercel-sandbox-are-now-in-public-
beta` still renders "Drives for Vercel Sandbox are now available in
public beta on Hobby, Pro, and Enterprise" with iad1 Drive pricing
verbatim (storage $0.05 per GB-month, reads $0.0015 per GB, writes
$0.004 per GB; Hobby includes 15 GB storage + 30 GB each of
reads/writes per month) — unchanged since the C56 observation. No GA
language; the dated sitemap still dates it 2026-09-23 (public beta,
not GA). Not a Drives GA — the standing tracked item is GA, unmet.

## Surveyor B — delta news scan (mtime-bounded)

**0 CANDIDATES / 20 clean dedupes / 4 flagged-only** — 16
browser_search calls, 0 pages opened (snippet level throughout;
nothing met the fold gate).

**Clean dedupes (20):** C11 — Modal $750M / $15.75B still
"nearing"/"closing in on" (recrawls through today; Modal declined to
comment — FILE-ON-CLOSE gate unmet); C11 — Baseten ~$26B still "in
talks"/"under discussion" (metirai, saastr, analyticsinsight:
"Neither round has closed" — gate unmet); Modal egress billing
went-live signal — none observed; Vercel Drives GA — no GA language
(public beta since 2026-09-23 stands); Vercel "eve" — retired as
corpus-known, nothing new; Hugo CVE-2026-100690 — still
third-party-only; NanoCo — partnership color only (no new facts —
re-grade bar unmet); Daytona — no in-window vendor news; E2B — no
in-window vendor news; Microsandbox — no release news beyond v0.7.6
(corpus baseline); boat.dev — no new vendor news; TermSquad — no new
news; DigitalOcean Managed Agents / Harness Runtime — third-party
recaps of the Sept-22 public preview (corpus-known); Cloudflare
cross-tenant disk-block disclosure — recap color only (remediation
confirmed complete Sept 19; no CVE; no exploitation evidence —
stays watch color); Docker Cloud Sandboxes — Sep-24 launch recrawls
only (corpus-known); C72 / C73 / C74 — third-party recaps of filed
items (filed — dedupe); alleged Vercel dark-web credential sale —
still unconfirmed (one Register item traces to the April Context.ai
incident — do-not-conflate stands; watch-only); Cloudflare Sandboxes
GA language — traces to the 2026-04-13 first-party post
(pre-window, corpus-era); pre-window sweeps (CoreWeave, Blitzy,
Snowflake Cortex Agents — no new movement).

**Flagged-only (4):**

1. **Modal multi-node GPU clusters GA (Oct 1, 2026, company-issued
   via runtimewire).** Gang scheduling + RDMA, per-second billing,
   single Python decorator. Vendor-confirmed but training/inference
   compute, not the sandbox surface; effective-date predates the
   window.
2. **Daytona "OpenHands demo / agent-agnostic middleware" PR
   syndication recrawl.** Date unpinable (one syndication carries a
   stale parse timestamp); no in-window vendor confirmation.
3. **Cloudflare Containers rebuild (~Sept 30, first-party) — carry.**
   New recap color: a prebuilt `cloudflare/debian-trixie` image
   (Debian Trixie Slim + Node.js 24.20.0 LTS). Still predates the
   window; per the in-window filing rule, no C-number.
4. **Bedrock Managed Agents limited→public preview state change —
   still third-party-only (carry).** neoteo.com: "AWS's current
   developer guide labels the service a public preview." The C73
   fold is secure on the vendor page; the detail still needs a
   first-party AWS developer-guide read. No change this cycle.

## Standing-item state

- **C11 FILE ON CLOSE — armed.** Modal $750M and Baseten ~$26B both
  still unclosed ("nearing"/"closing in on"/"in talks"/"under
  discussion").
- **C12 — OPEN (60th consecutive first-party read).** AgentComputer
  still publishes no egress pricing line.
- **C68 — RESOLVED (filed cycle 57).** Not graded this pass.
- **Modal egress billing — EFFECTIVE 2026-10-01.** Two-days-
  post-effective first-party read: still verbatim, no went-live
  banner, no usage-posture change; first bill including egress still
  postured for November 1, 2026. No third-party go-live signal in
  the B lane.
- **Vercel Drives GA — standing tracked item** (public beta since
  2026-09-23; no GA language on any first-party page this cycle).
- **Vercel "eve" — novelty watch RETIRED as corpus-known.**
  Launched June 17, 2026; corpus row carries it; adoption color
  only.
- **Prime Sandboxes — FILED (C48, vendor-verified 2026-09-25).**
- **C72 / C73 / C74 / C75 — FILED.** Third-party recaps are clean
  dedupes; C75 now carries a first-party pricing fold this cycle.
- **NanoCo re-grade bar — unmet.** Partnership color only.
- **Hugo CVE-2026-100690 — third-party-only.** File on first-party
  GHSA only.
- **Alleged Vercel dark-web credential sale — UNCONFIRMED,
  watch-only.** Fact-checker holds (breach-confirmed FALSE,
  credential validity FALSE); do-not-conflate with April-2026.
- **Cloudflare cross-tenant disk-block disclosure — watch color
  only.** Remediation confirmed complete September 19, 2026; no
  CVE; no exploitation evidence.
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed. No
  age-outs this pass; no re-folds; C11 quiet stays 0/3.

## Watch-outs for the next slot

The next slot's A-lane URL list carries the new DigitalOcean path
(`/managed-agents/agent-harness-runtime/details/pricing/` and
`/limits/`) — the old `/managed-agents/details/pricing/` 404s.
Bedrock limited→public preview state change — first-party AWS
developer-guide read still outstanding; C11 FILE ON CLOSE; Modal
egress first-party re-confirm; Drives GA standing; Hugo
CVE-2026-100690 third-party-only; NanoCo re-grade bar; the
Cloudflare disk-block disclosure stays watch color; the Modal
multi-node GPU clusters GA (~Oct 1) sits outside the sandbox
surface — re-grade only if sandbox-adjacent facts land; surveyor
timestamp-honesty rule in force.
