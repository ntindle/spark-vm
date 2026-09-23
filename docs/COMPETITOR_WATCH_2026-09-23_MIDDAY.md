# Competitor watch — 2026-09-23 (midday)

Delta-only update against the late-morning pass
(`docs/COMPETITOR_WATCH_2026-09-23_LATE_MORNING.md`). Survey window
**2026-09-23 ~10:54 → 11:05 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the tracked set (reads ~10:56–10:58 CDT), (B) Vercel Drives GA
watch plus open-web market-news scan (~10:54–11:05 CDT). Surveyor
captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260923-1054.md`), not the repo.

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

Every baseline value from the LATE-MORNING pass (its ~09:55–10:00 CDT
vendor-page reads) verified identical on the vendor's own page,
reads ~10:56–10:58 CDT:

- **Daytona** — changelog top entry still **V0.216.0** (Sep 23 2026,
  "Confine Dockerfile COPY sources to the build context" — Python,
  Ruby, TypeScript SDKs); V0.215.0 (Sep 22) still second
  (**VERIFIED**: https://www.daytona.io/changelog, ~10:56).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits, C34 corpus-folded) (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~10:57).
- **Microsandbox** — **v0.7.1** still the newest release (vendor repo
  /releases list page read directly this pass — no v0.7.2)
  (**VERIFIED**: https://github.com/superradcompany/microsandbox/releases, ~10:57).
- **E2B** — pricing identical (Hobby FREE $100 one-time credit / Pro
  $150-mo / per-second usage rates unchanged)
  (**VERIFIED**: https://e2b.dev/pricing, ~10:57).
- **boat.dev** — pricing identical (small $0.018/h, default $0.036/h,
  large $0.072/h, xlarge $0.200/h; plans unchanged)
  (**VERIFIED**: https://docs.boat.dev/pricing, ~10:57).
- **TermSquad** — pricing identical (Starter $9 / Builder $19 / Power
  $29 / Ultra $49 per month; all always-on)
  (**VERIFIED**: https://termsquad.com/, ~10:58).
- **DigitalOcean** — droplet pricing identical (Basic Droplets $4–$96,
  per-second billing from Jan 1 2026, unchanged)
  (**VERIFIED**: https://www.digitalocean.com/pricing/droplets, ~10:58).
- **AgentComputer** — pricing identical ($0.07/CPU-hour,
  $0.04375/GB-hour memory)
  (**VERIFIED**: https://www.agentcomputer.ai/pricing, ~10:58).

Zero fetch failures this pass; no UNVERIFIED items.

## 2. Vercel Drives GA watch — still beta (seventh consecutive no-change pass)

The Drives pricing page reads identically to the late-morning pass
(**VERIFIED**: https://vercel.com/docs/sandbox/pricing, ~10:55 CDT):
`last_updated` still **2026-09-10**; terms unchanged ($0.05/GB-month
storage on Pro/Enterprise — 15 GB lifetime on Hobby; $0.0015/GB reads,
$0.004/GB writes; max 4 drives/run; 1 TiB default / 16 TiB max per
drive; downloads free; session caps 45min/24h; concurrency 10/10,000).
Vercel changelog newest entries are 22 Sep (AI Gateway models,
Connect Teams, billing display) — **no entries dated 2026-09-23, no
Drives GA movement**.

## 3. Market news (48h window)

### 3a. Open verification asks — still owed

- **C26 (DO Managed Agents pricing)** — vendor verification **failed
  again this run**: the direct fetch of
  `docs.digitalocean.com/products/agents/overview/` hit a
  browser-service error and was not retried via another channel. The
  numbers ($0.044/vCPU-hour active, $0.0095/GB-hour,
  $0.005/GiB-month snapshots, $5 new-user credit) stand as
  **THIRD-PARTY** from the late-morning pass. A successful
  vendor-docs read remains the pass-to-pass ask.
- **C35 (Docker Sandboxes 0.42.0 CVE pair)** — still **THIRD-PARTY**,
  but better corroborated: the Docker docs security-announcements
  page could not be fetched directly, so contents were confirmed via
  a GitHub mirror of that page plus 7 corroborating third-party
  writeups. Verbatim match on the characterization: CVE-2026-77179
  (Critical 9.4, virtio-fs symlink escape, macOS, 0.28.0–<0.42.0)
  and CVE-2026-79994 (High 8.7, UDS socket-relay TOCTOU,
  0.37.0–<0.42.0), both fixed in 0.42.0 (released Sep 7; advisory
  Sep 15). **New corroborating color:** 0.43.0 is now the latest
  release (Sep 15) on the Docker Desktop for Mac line — distinct
  from the Docker Sandboxes docs release-notes line in §1, whose
  top-out remains 2026-09-21; CISA assesses exploitation as "none"; neither
  CVE is in KEV as of Sep 16. Vendor verification against Docker's
  own security announcement remains owed before any corpus fold.

### 3b. Adjacent re-checks — no new facts

- **Automaid** — no new facts (still third-party-only; aggregator
  digests, no own page).
- **Andon Pion** — no new facts.
- **Huawei Open Agentic Cloud** — no new facts (only stale 2025
  telecom whitepapers).
- **OpenAI "Managed Agents" DevDay note** — still THIRD-PARTY
  context. New adjacent platform color (not the Managed Agents
  unveiling itself): TestingCatalog (2026-09-22/23) reports OpenAI
  Platforms are getting "Free, Prototype, Accelerate" plans ahead of
  DevDay (9/29, Fort Mason).
- E2B / Daytona / Modal / Fly.io / RunPod / Brev — no launches,
  GAs, or pricing announcements in window.

### 3c. In-lane launches

**No new in-lane launches this pass.** The DigitalOcean Managed
Agents public preview (2026-09-22) was already the late-morning
pass's in-lane launch verdict (public preview, not GA); nothing new
has launched since. This pass resumes the explicit no-new-launch
reading against that filed baseline.

## 4. No corpus fold this pass

Nothing vendor-verified this pass shifts spark-vm's positioning: the
DO Managed Agents pricing remains THIRD-PARTY (C26, vendor
verification owed) and the Docker CVE pair remains C35 (THIRD-PARTY,
vendor verification owed — the new 0.43.0 / CISA / KEV color is
corroborating third-party detail, not a vendor confirmation). No new
competitors to add to the canonical corpus. No new C-numbers.
Next pass's ask: routine tracked-set re-reads; Vercel Drives GA
watch continues (eighth no-change pass incoming if quiet); verify
the DO Managed Agents pricing against the vendor's own docs page
(retry the docs fetch); verify the Docker 0.42.0 CVE pair against
Docker's own security announcement.
