# Competitor watch — 2026-09-23 (late midday)

Delta-only update against the midday pass
(`docs/COMPETITOR_WATCH_2026-09-23_MIDDAY.md`). Survey window
**2026-09-23 ~11:54 → 12:00 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the tracked set (reads ~11:56 CDT), (B) Vercel Drives GA watch plus
open-web market-news scan plus open-verification retries (~11:54–11:58
CDT). Surveyor captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260923-1154.md`), not the repo.

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

Every baseline value from the MIDDAY pass (its ~10:56–10:58 CDT
vendor-page reads) verified identical on the vendor's own page,
reads ~11:56 CDT:

- **Daytona** — changelog top entry still **V0.216.0** (Sep 23 2026,
  "Confine Dockerfile COPY sources to the build context")
  (**VERIFIED**: https://www.daytona.io/changelog, ~11:56).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits, C34 corpus-folded) (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~11:56).
- **Microsandbox** — **v0.7.1** still the newest release (vendor repo
  /releases list page read directly — no v0.7.2)
  (**VERIFIED**: https://github.com/superradcompany/microsandbox/releases, ~11:56).
- **E2B** — pricing identical (Hobby FREE $100 one-time credit / Pro
  $150-mo / per-second usage rates unchanged)
  (**VERIFIED**: https://e2b.dev/pricing, ~11:56).
- **boat.dev** — pricing identical (small $0.018/h, default $0.036/h,
  large $0.072/h, xlarge $0.200/h; plans unchanged)
  (**VERIFIED**: https://docs.boat.dev/pricing, ~11:56).
- **TermSquad** — pricing identical (Starter $9 / Builder $19 / Power
  $29 / Ultra $49 per month; all always-on)
  (**VERIFIED**: https://termsquad.com/, ~11:56).
- **DigitalOcean** — droplet pricing identical (Basic Droplets $4–$96,
  per-second billing from Jan 1 2026, unchanged)
  (**VERIFIED**: https://www.digitalocean.com/pricing/droplets, ~11:56).
- **AgentComputer** — pricing identical ($0.07/CPU-hour,
  $0.04375/GB-hour memory)
  (**VERIFIED**: https://www.agentcomputer.ai/pricing, ~11:56).

Zero fetch failures this pass; no UNVERIFIED items.

## 2. Vercel Drives GA watch — still beta (eighth consecutive no-change pass)

The Drives pricing page reads identically to the midday pass
(**VERIFIED**: https://vercel.com/docs/sandbox/pricing, ~11:56 CDT):
`last_updated` still **2026-09-10**; terms unchanged ($0.05/GB-month
storage on Pro/Enterprise — 15 GB lifetime on Hobby; $0.0015/GB reads,
$0.004/GB writes; max 4 drives/run; 1 TiB default / 16 TiB max per
drive; downloads free; session caps 45min/24h; concurrency 10/10,000).
Vercel changelog newest entries are 22 Sep — **no entries dated
2026-09-23, no Drives GA movement**.

Wrinkle (INFERRED, not a feature change): the changelog sitemap now
dates the "Drives for Vercel Sandbox are now in public beta" entry
2026-09-23, where a crawl ~5h earlier dated it 2026-09-22. The
pricing page itself is byte-identical in all tracked terms
(`last_updated` 2026-09-10 unchanged), so this reads as a
re-publish/re-date of the changelog entry, not a Drives GA move. The
no-change streak stands at eight consecutive passes.

## 3. Market news (48h window)

### 3a. Open verification asks — one closed, one refined, one owed

- **C35 (Docker Sandboxes 0.42.0 CVE pair)** — **CLOSED this run:**
  the pair was read on Docker's OWN security-announcements page
  (**VERIFIED**: https://docs.docker.com/security/security-announcements/,
  ~11:58 CDT) — CVE-2026-77179 (Critical, virtio-fs symlink-follow →
  macOS workspace escape, 0.28.0–<0.42.0) and CVE-2026-79994 (High,
  AF_UNIX socket-relay TOCTOU, 0.37.0–<0.42.0), both fixed in 0.42.0
  (Sep 7). Matches the GitHub mirror characterization exactly, and —
  importantly — matches the corpus's standing VERIFIED section
  (`docs/COMPETITOR_ANALYSIS.md`, from the 2026-09-19 consolidation
  pass) with **no factual drift**. No corpus fold needed: the
  corpus's characterization stands confirmed. The corroborating
  third-party color (CISA assesses exploitation as "none"; neither CVE
  in KEV as of Sep 16) stays watch-doc-level only, not corpus.
- **C26 (DO Managed Agents pricing)** — refined, not closed: the
  vendor docs page now loads
  (**VERIFIED**: docs.digitalocean.com/products/managed-agents/agent-harness-runtime/,
  "Generated on 23 Sep 2026" — confirms public-preview availability
  (21 Sep 2026) and features), but the dollar figures do NOT appear in
  the fetched content; they live in a "Details" (features/pricing/
  availability/limits) sub-section that did not render. Pricing
  therefore stands **THIRD-PARTY via DO's own BusinessWire press
  release** (vendor-authored, syndicated copy): $0.044/vCPU-hour active
  CPU, $0.0095/GB-hour memory, $0.005/GiB-month snapshots. New
  pass-to-pass ask: locate the vendor docs' Details/pricing sub-page.
- **Automaid own page** — still missing after a retry (only
  third-party coverage: itbrief.asia). New adjacent color this pass:
  Automaid is pitching an "AI hub for agents that keep working"
  (Singapore, per itbrief.asia ~2 days old — per-agent cloud
  environments for files/code, Browser Use for web interaction,
  Gmail/Slack triggers, MCP). Classified adjacent (ops/automation
  hub), not an in-lane raw agent-VM product — own-page verification
  remains owed.

### 3b. Adjacent re-checks — no new facts

- **Andon Pion** — no new hits in window.
- **Huawei Open Agentic Cloud** — no new hits in window.
- **OpenAI "Managed Agents" DevDay note** — still rumor: no NEW
  vendor confirmation. TestingCatalog (Alexey Shabanov) code-find
  reporting + press speculation; OpenAI's own site confirms only the
  DevDay date/venue (Sep 29, Fort Mason).
- E2B / Daytona / Modal / Fly.io / RunPod / Brev — quiet in window
  (Daytona hits were re-syndicated 2018-era press releases).

### 3c. In-lane launches

**No new in-lane launches this pass.** The DigitalOcean Managed
Agents public preview (2026-09-22) remains the newest in-lane event
and was already filed (09:54 pass); nothing new has launched since.
This pass resumes the explicit no-new-launch reading against that
filed baseline.

## 4. No corpus fold this pass

C35's vendor verification confirms — rather than changes — the
corpus's standing VERIFIED characterization, so no fold is owed. C26
pricing stays THIRD-PARTY; the Automaid hub note is adjacent and
unverified. No new competitors to add to the canonical corpus. No new
C-numbers.
Next pass's ask: routine tracked-set re-reads; Vercel Drives GA
watch continues (ninth no-change pass incoming if quiet); locate the
DO Managed Agents docs Details/pricing sub-page; Automaid own-page
verification still owed.
