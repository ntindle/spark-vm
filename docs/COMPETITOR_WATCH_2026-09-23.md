# Competitor watch — 2026-09-23

Delta-only update against the overnight baseline
(`docs/COMPETITOR_WATCH_2026-09-22_OVERNIGHT.md`). Survey window
**2026-09-23 ~01:55 → 02:25 CDT**; two read-only surveyors (read-only
fetches and searches; no logins, no writes): (A) vendor-page re-reads of
the tracked set (reads ~01:57–02:10 CDT), (B) open-web market-news scan
(~01:56–02:08 CDT) plus a vendor-docs verification.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **VENDOR-ATTESTED** = confirmed against the
vendor's own *served infrastructure* (fetched artifact/installer/API
response) rather than a vendor doc-page assertion — a stricter
claim than VERIFIED, used only when we fetched the thing itself.
**THIRD-PARTY** = reported by press/third-party sources.
**INFERRED** = my characterization, labeled as such.
**UNVERIFIABLE** = no public source exists to check against.

## 1. The tracked set — quiet since the overnight baseline (8/8 NO-CHANGE, all VERIFIED)

- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~01:57).
- **Daytona** — changelog top entry still **SEP 22 2026 / V0.215.0**
  (**VERIFIED**: https://www.daytona.io/changelog, ~01:57).
- **E2B** — pricing unchanged: Hobby free + $100 one-time credit, Pro
  $150/mo, Enterprise custom ($3,000/mo estimator floor); per-second table
  tops $0.000014/s per vCPU (**VERIFIED**: https://e2b.dev/pricing,
  ~01:57).
- **boat.dev** — rate card unchanged: small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h**; stopped free;
  25 free-hour trial (**VERIFIED**: https://docs.boat.dev/pricing,
  ~01:57).
- **Docker Sandboxes** — release notes still top out at **2026-09-15**
  (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~01:57).
- **TermSquad** — tiers still **$9/$19/$29/$49**; BYO-AI stance intact
  (**VERIFIED**: https://termsquad.com/, ~01:57).
- **DigitalOcean Managed Agents** — product page unchanged (Public
  Preview; hero "under a couple of seconds" / "about 200 milliseconds";
  Tool Playground, scheduled/webhook triggers); docs index still
  "Last verified 21 Sep 2026" (**VERIFIED**:
  https://www.digitalocean.com/products/managed-agents and
  https://docs.digitalocean.com/products/managed-agents/, ~02:07).
- **AgentComputer** — pricing unchanged (CPU $0.07/CPU-hour, memory
  $0.04375/GB-hour, hot storage $0.000683/GB-hour, cold
  $0.000027/GB-hour); still **no stated egress policy** — C12 stands
  (**VERIFIED**: https://www.agentcomputer.ai/pricing, ~01:57).

## 2. Deltas — the standing C32 ask is closed; one new vendor pricing datapoint

### 2a. C32 CLOSED: Vercel Sandbox 64 GB default — CONFIRMED (VERIFIED)

The overnight pass's carried ask — whether Vercel's own pages confirm
the THIRD-PARTY blog claim that default sandbox storage moved 32→64 GB —
is now **answered affirmatively**, independently by both surveyors this
pass. The vendor changelog (https://vercel.com/changelog, read ~02:12
CDT) carries **no** default-storage entry (only the already-recorded
Drives public beta) — the confirmation is in the vendor's own pricing
docs, not the changelog.

**VERIFIED** (https://vercel.com/docs/sandbox/pricing, page metadata
`last_updated: 2026-09-10`, read ~02:05 and ~02:15 CDT): under
"Quotas and limits / Resource limits", verbatim: *"Each sandbox created
with Sandbox SDK 3.0.0 or above, or from a custom image, is
automatically provisioned **64 GB of ephemeral NVMe storage**.
Sandboxes created with **runtimes (deprecated) receive 32 GB**."* The
per-plan quota table shows Disk size **64 GB** for Hobby/Pro/Enterprise.

So the 32→64 GB claim was real all along: 32 GB survives only on the
deprecated runtime path. The overnight watch's UNVERIFIABLE qualifier is
retired. Corpus impact (folded in this same PR per the primary-source
verification convention): the Vercel field-table row now carries the
64 GB default, and the Drives datapoint below joins the same
"Watch update — 2026-09-23" corpus section.

### 2b. Vercel Sandbox Drives: pricing detail — new VERIFIED datapoint

The same vendor page completes the Sept 22 Drives public-beta datapoint
with real numbers (**VERIFIED**, same read): Drive Storage
$0.05/GB-month (Pro/Enterprise; Hobby gets 15 GB lifetime); Drive Reads
$0.0015/GB (Hobby 30 GB/mo); Drive Writes $0.004/GB (Hobby 30 GB/mo);
max 4 drives per run; default drive 1 TiB (1 GiB on Hobby); 16 TiB max
per drive; sandbox **downloads are free** (outbound + exposed-port
traffic billable); Pro sandbox usage charges against the **$20/month
credit**; session caps 45 min (Hobby) / 24 h (Pro/Enterprise);
concurrency 10 (Hobby) / 10,000 (Pro/Enterprise).

Color for the corpus's "where spark-vm wins/lags" framing (persistent
disk as a first-class, metered sandbox feature — the same direction as
Boxd's persistent-machine thesis and spark-vm's own persistent-VM
positioning), now with concrete price anchoring instead of a launch-post
headline. Not a design change.

### 2c. Firecrawl $75M Series B — THIRD-PARTY, adjacent investor color

Firecrawl raised a **$75M Series B** led by Smash Capital
(Altos Ventures, Nexus Venture Partners, Y Combinator, Freestyle,
Offline Ventures participating; announced ~Sept 22, reported by
finsmes.com and techstartups.com roundups — **THIRD-PARTY**), launching
alongside **Alexandria**, an agent-facing data library over Firecrawl's
indexes plus paid provider agreements. Anomaly worth noting: runtimewire
cites an SEC Form D showing **$82M** of preferred stock sold (Aug 31)
against the announced $75M — unexplained.

This is agent *data plumbing*, not a sandbox/VM competitor — filed here
as investor-signal color only, not a corpus entry. If agent-tooling
capital flow becomes a corpus question on a later consolidation, this is
the starting datapoint.

## 3. Standing items / carry-forwards

- **C14 (#47 resume-latency target):** still OPEN — needs our own
  measured provider baseline; the operator per-run Fly spend-cap
  decision is still owed (NEEDS_USER.md). No new benchmark-grade input
  this pass.
- **C29 (Boxd):** watch continues at routine cadence; no new signal.
- **C26 (DO watch):** quiet this pass; vendor pages unchanged.
- **C12, C10:** stand, unchanged.
- **Cloudflare Sandbox:** no new signal; deprioritized retained.
- **Next pass's ask:** routine tracked-set re-reads; watch Vercel's
  sandbox docs for Drives beta-terms evolution toward GA.

---

*Corpus note:* per the delta-only convention, watch docs record deltas
against the previous pass and the corpus changes only via
consolidation or primary-source verification. This pass carries two
primary-source VERIFIED items (C32's 64 GB confirmation, Drives pricing)
— both fold into the corpus's new "Watch update — 2026-09-23" section
in this same PR, provenance-labeled. The Firecrawl note stays in this
watch doc. The two surveyor captures are archived verbatim in the
loop's `agent_notes/` (workspace-only), not the repo.
