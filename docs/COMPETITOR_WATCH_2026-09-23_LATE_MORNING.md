# Competitor watch — 2026-09-23 (late morning)

Delta-only update against the night pass
(`docs/COMPETITOR_WATCH_2026-09-23_NIGHT.md`). Survey window
**2026-09-23 ~09:54 → 10:05 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads
of the tracked set (reads ~09:55–10:00 CDT), (B) Vercel Drives GA
watch plus open-web market-news scan (~09:54–10:05 CDT). Surveyor
captures live in the loop's `agent_notes/` workspace
(`surveyor-a/b-20260923-0954.md`), not the repo.

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

Every baseline value from the NIGHT pass (its ~08:57–08:59 CDT
vendor-page reads) verified identical on the vendor's own page,
reads ~09:55–10:00 CDT:

- **Daytona** — changelog top entry still **V0.216.0** (SEP 23 2026,
  "Confine Dockerfile COPY sources to the build context" — Python,
  Ruby, TypeScript SDKs); V0.215.0 (SEP 22) still second
  (**VERIFIED**: https://www.daytona.io/changelog, ~09:55).
- **Docker Sandboxes** — release notes still top out **2026-09-21**
  (v3 kits, C34 corpus-folded) (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~09:56).
- **Microsandbox** — **v0.7.1** still the newest release (vendor repo
  release page + fresh ~4–14h-old search results show no v0.7.2)
  (**VERIFIED**: https://github.com/superradcompany/microsandbox/releases/tag/v0.7.1, ~09:56).
- **E2B** — pricing identical (Hobby FREE $100 one-time credit / Pro
  $150-mo / per-second usage rates unchanged)
  (**VERIFIED**: https://e2b.dev/pricing, ~09:57).
- **boat.dev** — pricing identical (small $0.018/h, default $0.036/h,
  large $0.072/h, xlarge $0.200/h; plans unchanged)
  (**VERIFIED**: https://docs.boat.dev/pricing, ~09:57).
- **TermSquad** — pricing identical (Starter $9 / Builder $19 / Power
  $29 / Ultra $49 per month; all always-on)
  (**VERIFIED**: https://termsquad.com/, ~09:58).
- **DigitalOcean** — droplet pricing identical (per-second billing,
  v5 Droplets still advertised)
  (**VERIFIED**: https://www.digitalocean.com/pricing/droplets, ~09:59).
- **AgentComputer** — pricing identical ($0.07/CPU-hour,
  $0.04375/GB-hour memory)
  (**VERIFIED**: https://www.agentcomputer.ai/pricing, ~10:00).

One fetch caveat: Microsandbox's latest-release status is inferred
from the v0.7.1 tag page plus fresh search results (no newer tag
sighted); the /releases/latest list page was not read directly this
run — the NO-CHANGE verdict stands on the tag + search evidence, and
the next pass's ask includes reading the list page itself.

### 1b. Docker Sandboxes 0.42.0 CVE pair — filed C35 (THIRD-PARTY only)

Surveyor A surfaced third-party claims (severitydaily.com,
brocker.org, hacklido.com; a docs-mirror carrying a Docker security
announcement dated Sep 15, 2026) that Docker Sandboxes **0.42.0**
(Sep 7, 2026) fixed **CVE-2026-77179** (Critical — virtio-fs macOS
workspace escape) and **CVE-2026-79994** (High — Unix socket
TOCTOU). The vendor's own security page was not read this run, so
these are **THIRD-PARTY / snippet-only** — filed as **C35** with
vendor-verification owed. (**INFERRED** lane judgment) If confirmed,
they would be the first publicly-documented guest-escape CVEs in a
directly-tracked sandbox product this window — relevant to
spark-vm's jail/worker threat model — but until the vendor page is
read they change nothing in the corpus.

## 2. Vercel Drives GA watch — NO-CHANGE (sixth consecutive no-change pass)

- Pricing page `last_updated: 2026-09-10` — UNCHANGED; every tracked
  term identical (storage $0.05/GB-month Pro/Ent, Hobby 15 GB
  lifetime; reads $0.0015/GB; writes $0.004/GB; max 4 drives/run;
  1 TiB default (1 GiB Hobby); 16 TiB max/drive; downloads free;
  session caps 45min/24h; concurrency 10/10,000)
  (**VERIFIED**: https://vercel.com/docs/sandbox/pricing, ~09:56).
- Vercel changelog: newest entries dated **22 Sep 2026** — nothing
  dated 2026-09-23. The 22 Sep entries include "Drives for Vercel
  Sandbox are now in **public beta**" (up to 16 TiB, usage-based
  pricing). **No Drives beta→GA movement.**
- **Verdict: NO-CHANGE — sixth consecutive no-change pass.**

## 3. Market news (48h window)

### 3a. DigitalOcean Managed Agents public preview — pricing now published (THIRD-PARTY)

The 2026-09-22 public-preview launch (filed **C26**) now carries
published pricing — **resolving C26's open pricing ask at
THIRD-PARTY level** (vendor-docs verification still owed):

- CPU billed per actual-consumption second at
  **$0.044/vCPU-hour**; memory **$0.0095/GB-hour**; snapshots
  **$0.005/GiB-month**; pause stops CPU+memory charges, retained
  storage still billable; **$5 credit** for new users.
- The harness shape is unchanged from prior passes: Harness
  Runtime (each agent session in a dedicated Firecracker microVM
  with own compute+filesystem, built-in Chromium, coding sandbox;
  pause/resume/fork lifecycle APIs; auto-pause on idle) + Action
  Gateway (16,000+ tools across 500+ providers
  on one managed MCP endpoint; credentials brokered at execution,
  never reach model or sandbox; human-in-loop approval for
  sensitive actions).
- Harnesses run unmodified: Claude Code, Codex CLI, OpenCode,
  Hermes, LangGraph, bring-your-own OCI images; collaborative
  sessions; integrated with DO Inference (75+ models).

(**INFERRED** lane judgment) In-lane — managed agent execution on
idle-pausing persistent microVMs with per-second dollar pricing is
the closest direct competitor to spark-vm's hosted-agent-machine
thesis. Competitive price point to hold: **$0.044/vCPU-hour
active-CPU billing** (under Vercel Sandbox's $0.128 active
vCPU-hour). Provenance: THIRD-PARTY (press-release syndication +
digest; the vendor launch blog and product docs were not fetched
directly this run) — so no corpus fold for the pricing yet; the
watch table and this doc carry it as watch color with the
vendor-verification caveat intact.

### 3b. Adjacent — unchanged

- **Automaid** — still THIRD-PARTY-only (aggregator digests, no
  own-page).
- **Andon Pion** — no new facts.
- **Huawei Open Agentic Cloud** — still THIRD-PARTY (no vendor
  page).
- **OpenAI "Managed Agents" DevDay note** — remains ~16-day-old
  THIRD-PARTY context, watch color only.
- E2B / Daytona / Modal / Fly.io / RunPod / Brev — no launches,
  GAs, or pricing announcements in window. Railway `code` is
  ~46 days old; Docker sbx GA was Jan 30, 2026 — not new.

### 3c. In-lane launches

**YES — this pass breaks the recent streak: DigitalOcean Managed
Agents public preview (2026-09-22) is an in-lane launch**
(managed agent-harness execution on persistent, idle-pausing
Firecracker microVMs + 16k-tool MCP gateway, now with published
per-second pricing). It is explicitly a **public preview, not a
GA** — so no in-lane *GA* this window. (Prior streak: four
consecutive passes with an explicit in-lane no-launch verdict —
afternoon → evening → late evening → night.)

## 4. No corpus fold this pass

Nothing vendor-verified this pass shifts spark-vm's positioning:
the DO Managed Agents pricing is THIRD-PARTY (C26's pricing ask
resolved at THIRD-PARTY level; vendor verification owed before a
corpus fold) and the Docker CVE pair is C35 (THIRD-PARTY,
vendor-verification owed). No new competitors to add to the
canonical corpus. No new C-numbers beyond C35.
Next pass's ask: routine tracked-set re-reads (plus the
Microsandbox /releases/latest list page); Vercel Drives GA watch
continues (seventh no-change pass incoming if quiet); verify the
DO Managed Agents pricing against the vendor's own docs page;
verify the Docker 0.42.0 CVE pair against Docker's own security
announcement.
