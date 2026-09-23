# Competitor watch — 2026-09-23 (early afternoon)

Delta-only update against the late-midday pass
(`docs/COMPETITOR_WATCH_2026-09-23_LATE_MIDDAY.md`). Survey window
**2026-09-23 ~12:54 → 13:02 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the tracked set (reads ~12:57–12:59 CDT), (B) Vercel Drives GA watch
plus open-web market-news scan (~12:54–13:02 CDT). Surveyor captures
live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260923-1254.md`), not the repo.

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

Every baseline value from the LATE_MIDDAY pass (its ~11:56 CDT
vendor-page reads) verified identical on the vendor's own page,
reads ~12:57–12:59 CDT:

- **Daytona** — changelog top entry still **V0.216.0** (Sep 23 2026,
  "Confine Dockerfile COPY sources to the build context")
  (**VERIFIED**: https://www.daytona.io/changelog, ~12:57).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits, C34 corpus-folded) (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~12:57).
- **Microsandbox** — **v0.7.1** still the newest release (vendor repo
  /releases list page read directly — no v0.7.2)
  (**VERIFIED**: https://github.com/superradcompany/microsandbox/releases, ~12:57).
- **E2B** — pricing identical (Hobby FREE $100 one-time credit / Pro
  $150-mo / per-second usage rates unchanged)
  (**VERIFIED**: https://e2b.dev/pricing, ~12:57).
- **boat.dev** — pricing identical (small $0.018/h, default $0.036/h,
  large $0.072/h, xlarge $0.200/h; plans unchanged)
  (**VERIFIED**: https://docs.boat.dev/pricing, ~12:57).
- **TermSquad** — pricing identical (Starter $9 / Builder $19 / Power
  $29 / Ultra $49 per month; all always-on)
  (**VERIFIED**: https://termsquad.com/, ~12:58).
- **DigitalOcean** — droplet pricing identical (Basic Droplets $4–$96,
  per-second billing from Jan 1 2026, unchanged)
  (**VERIFIED**: https://www.digitalocean.com/pricing/droplets, ~12:58).
- **AgentComputer** — pricing identical ($0.07/CPU-hour,
  $0.04375/GB-hour memory)
  (**VERIFIED**: https://www.agentcomputer.ai/pricing, ~12:58).

Zero fetch failures this pass; no UNVERIFIED items.

## 2. Vercel Drives GA watch — still beta (ninth consecutive no-change pass)

The Drives pricing page reads identically to the late-midday pass
(**VERIFIED**: https://vercel.com/docs/sandbox/pricing, ~12:56 CDT):
`last_updated` still **2026-09-10**; terms unchanged ($0.05/GB-month
storage on Pro/Enterprise — 15 GB lifetime on Hobby; $0.0015/GB reads,
$0.004/GB writes; max 4 drives/run; 1 TiB default / 16 TiB max per
drive; downloads free; session caps 45min/24h; concurrency 10/10,000).
The changelog entry still reads "now available in public beta" — **no
GA movement**.

Sitemap-date caution (INFERRED, method note): the changelog sitemap's
date for the public-beta entry now reads 2026-09-23 again, matching
the late-midday pass — but a crawl ~6h earlier dated it 09-22, so the
date is flip-flopping between reads. The prior pass's "09-22→09-23
re-publish" reading was plausible but the date is evidently not
authoritative; treat it as sitemap churn, not evidence of anything.
The no-change streak stands at nine consecutive passes.

## 3. Market news (48h window)

### 3a. Open verification asks — both still open

- **C26 (DO Managed Agents pricing)** — still open, one refinement:
  the dollar figures ($0.044/vCPU-hour active CPU, $0.0095/GB-hour
  memory, $0.005/GiB-month snapshots) are now confirmed read in full
  in DigitalOcean's own launch-release text, read on syndicated copies
  (marketnewsdesk / tradingview / morningstar) — vendor-authored copy,
  but a syndicated copy, so it stays **THIRD-PARTY** per convention.
  The vendor docs "Details" tile (features/pricing/availability/
  limits) exists on the docs landing page (**VERIFIED** this run,
  generated 23 Sep 2026), but its target sub-page could not be reached
  read-only. Next ask unchanged: locate the vendor docs'
  Details/pricing sub-page.
- **OpenAI "Managed Agents"** — still rumor: all coverage traces to
  TestingCatalog's Sep 7 report; no vendor confirmation this run.
- **Automaid own page** — still missing: their domain automaid.it.com
  was found via snippet from their own Medium account, but no
  own-page launch announcement surfaced. Third-party coverage only
  (itbrief.asia, afritechbizhub) for the "AI hub for agents that keep
  working" pitch — classified adjacent, not in-lane.

### 3b. Adjacent re-checks — no new facts

- **Andon Pion** (launched 09-14, pre-window) — no new movement.
- **Huawei Open Agentic Cloud** (09-18 coverage) — no new movement.
- E2B / Daytona / Modal / Fly.io / RunPod / Brev — quiet in window.

### 3c. In-lane launches

**No new in-lane launches this pass.** The DigitalOcean Managed
Agents public preview (2026-09-22) remains the newest in-lane event
and was already filed; nothing new has launched since. This pass
resumes the explicit no-new-launch reading against that filed
baseline — fifth consecutive pass with that verdict counting the
afternoon/evening/late-evening/night cadence through today.

## 4. No corpus fold this pass

Nothing vendor-verified shifted positioning: the tracked set is
8/8 NO-CHANGE, Drives stays beta, C26 stays THIRD-PARTY (syndicated
vendor copy is not a docs-page fold), the Automaid hub note stays
adjacent and unverified. No new competitors to add to the canonical
corpus. No new C-numbers.
Next pass's ask: routine tracked-set re-reads; Vercel Drives GA
watch continues (tenth no-change pass incoming if quiet); locate the
DO Managed Agents docs Details/pricing sub-page; Automaid own-page
verification still owed.
