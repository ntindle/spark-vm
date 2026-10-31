# Competitor watch — 2026-10-31 (morning, cycle 82)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-81 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED** (20 opens /
19 successful fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 23rd consecutive cycle — one re-check only per
the standing rule; the 404 is the evidence)). The two A-lane deltas:
(1) Vercel changelog dated sitemap **1471 → 1483** — twelve new
dated entries above the baseline top (four dated 2026-10-30, eight
dated 2026-10-29), none Sandbox-titled — sitemap bookkeeping per
the C71 precedent, count reconciling exactly (+12 = 4 + 8); (2)
boat.dev pricing **stamp-only regen** (footer stamp 2026-10-28 →
2026-10-31) with zero figure change — a tracked-field movement, no
content delta. Surveyor B (delegated subagent, read-only): bounded
news scan — **4 CANDIDATES claimed / 17 clean dedupes / 12
flagged-only** (15 searches, all successful; 0 pages opened — no
first-party grading open was available to that lane, so candidates
needing first-party confirmation are said so rather than graded
from snippets).
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still unclosed —
Bloomberg's October 30 two-tranche report explicitly says the round
"has not closed"; PitchBook still marks Series G
"Rumor/Speculation"; Forge's October 20 Series G/G-1 rows at
$29.02B post-money are unchanged; no S-1);
**C12 OPEN** (82nd consecutive first-party AgentComputer read —
still no egress pricing line).
**Corpus move this cycle: 3 filings + 3 folds + 2 watch-doc dated
deltas; 0 age-out movements.** Last-issued C-number: C94 (was C91).
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261031-0910.md` plus
`hidden_files/agent_notes/integrator-reads-20261031-0910.md` (the
loop owner's own full-page first-party reads, recorded the same
cycle per the 2026-10-15 lesson; loop working notes in the goal
workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-31 ~09:1x–~10:5x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9). Its open accounting also reconciles
> (18 anchor opens, all successful first-try, plus 1 established-404
> re-check plus 1 releases-page open for item 3 = 20 opens, 19
> successful). Surveyor B's capture enumerates 4 candidates + 17
> dedupes + 12 flagged-only, reconciling with its header and search
> stats (15 successful searches; 0 opens — and the capture does not
> claim first-party docs were re-read this pass). The integrator's
> corpus-grep correction (see below) reduces B's 4 claimed
> candidates to 3 filings + 1 dedupe: Prime Sandboxes GA is already
> filed as C48, so B's candidate 2 is a rediscovery, not a filing.
> Numbering note: B's capture suggested C92–C95 with Prime as C93;
> with Prime deduped the integrator assigns C92 Tenki, C93 Claude
> Code CVE, C94 GitLab CVE. The 3 filings + 3 folds + 2 watch-doc
> dated deltas are the integration's corpus move.

## Corpus moves: filings

**Tenki Sandbox by Tenki Cloud — filed C92 (VENDOR-VERIFIED,
first-party tenki.cloud/products/sandbox read in full).** Disposable
full Linux VMs for AI agents and untrusted code, provisioned from
custom images in under a second — sandbox disks mount directly from
a dedicated Ceph storage cluster instead of being provisioned from
the compute node's local drive. Full VM support for Docker, system
packages, and background services; typed templates with
repo/dependencies/build steps built into reusable images, plus
snapshots (templates do not currently accept Dockerfiles); x86
Linux VMs driven by CLI or Go/TypeScript/Python SDKs; connections
via SSH, streamed shell output, and exposed preview URLs, tunneled
with no public IPs or open ports required. Pause stops compute
charges and preserves memory and durable files (/home/tenki,
volumes) while /tmp is cleared; a non-sticky session auto-pauses at
its maximum duration, but a running sandbox is otherwise not paused
for inactivity. Usage is metered per second across CPU, memory, and
disk; the first 5 GiB of disk is included; the product page itself
publishes no rates. Parent company Luxor Technology, SOC 2 Type II
program (B-lane texture from the tenki.cloud homepage/docs, not
graded from the product page). Third-party texture only, not
first-party: the Agent37 comparison (checked October 10, 2026)
matches E2B to the digit ($0.000014 per vCPU-second, $0.0000045 per
GiB-second) — do not cite as vendor pricing.
spark-vm relevance: another sub-second-boot VM entrant competing
directly on the fast-start axis spark-vm's own story targets, with
a Ceph-backed provisioning trick worth noting against spark-vm's
image story; the pause-preserves-memory semantics rhyme with
spark-vm's persistent-box story.

**Claude Code sandbox escape, CVE-2026-39861 — filed C93 (adjacent,
VENDOR-VERIFIED mechanism).** First-party GHSA-vp62-r36r-9xqp read
in full: Claude Code's sandbox did not prevent sandboxed processes
from creating symlinks pointing outside the workspace; when Claude
Code subsequently wrote to a path within such a symlink, its
unsandboxed process followed the symlink and wrote to the target
location outside the workspace without prompting the user for
confirmation — neither the sandboxed command nor the unsandboxed
app could independently write outside the workspace, but their
combination could write to arbitrary locations, potentially leading
to code execution outside the sandbox. Reliable exploitation
required untrusted content in the context window (prompt injection).
Users on standard auto-update received the fix automatically;
manual updaters are advised to update. Reporter credit:
hackerone.com/philts. CVE ID, affected versions (< 2.1.64), and
patched version (2.1.64) come from the canonical GitHub Advisory
Database page for GHSA-vp62-r36r-9xqp (Published Apr 20, 2026;
advisory-database publication Apr 21, 2026; updated Apr 27, 2026);
CVSS 4.0 7.7 comes from the NVD record, which lists the GHSA URL
as the Vendor Advisory. Date honesty, corrected in review: the
repo-path GHSA fetch rendered a stripped body without metadata,
which the integrator over-generalized into "no date visible" —
the canonical page does carry the April publication date, so the
filing is dated April 2026, and B-lane's "disclosed October 26,
2026" conflicts with that publication date and is rejected, not
merely uncorroborated.
spark-vm relevance: the symlink-following-across-processes shape is
the exact class spark-vm's own sandbox boundary must refuse —
validate at resolution time, not just creation time
(TOCTOU-adjacent), and never let an unsandboxed helper follow a
sandbox-created link without re-validation.

**GitLab AI Gateway prompt-template sandbox escape, CVE-2026-90970
— filed C94 (adjacent, VENDOR-VERIFIED).** First-party GitLab AI
Gateway critical patch release page (19.2.4, 19.3.2, 19.4.1), read
via the live browser because docs.gitlab.com blocks text fetch:
"Improper Neutralization issue in custom flow prompt template
impacts AI Gateway" — an authenticated user with Duo Agent Platform
access could escape the prompt template sandbox through a specially
crafted flow configuration and execute arbitrary commands on the AI
Gateway; Critical, CVSS 9.9; affected all versions from 18.1.6
before 19.2.4, 19.3 before 19.3.2, and 19.4 before 19.4.1; fixed in
19.2.4, 19.3.2, and 19.4.1; reporter credit invisiblemeerkat.
Date honesty: the first-party page carries no visible publication
date, so the filing dates nothing — third-party reports of the
advisory converge on October 2, 2026, with no in-the-wild
exploitation at disclosure (CISA: none) and GitLab-hosted gateways
already protected, both third-party-attributed. Second CVSS 9.9
template-engine escape in the same Duo component in eight months
(CVE-2026-1868, February 2026, per third-party reports of GitLab's
February advisory — not graded first-party this cycle).
spark-vm relevance: template engines are code, not text — any
spark-vm surface that renders operator- or agent-supplied templates
must treat the sandbox as the only boundary and assume it will be
probed; the repeat-in-eight-months pattern is the argument for a
regression test that crafts a hostile flow config, not just a patch.

## Integrator correction: B-lane candidate 2 is a rediscovery, not a filing

**Prime Sandboxes GA (Prime Intellect) — NOT re-filed; dedupe
against C48.** Surveyor B's second candidate (Prime Sandboxes
general availability, ~30M sandboxes in pre-release use, 1,024
concurrent sandboxes per account at launch, launch pricing through
December 22, 2026) is already in the corpus as C48 — launch
~2026-09-23, vendor-verified 2026-09-25 from the vendor's own GA
post ("Today, Prime Sandboxes enter general availability. … with
~30M sandboxes created so far"), including the same launch-pricing
expiry and the same ~1/3-of-rivals claim. B's "missed by cycles
80–81" is scan history, not corpus history: the item was filed
five weeks before those cycles. No new C-number, no row change.
(Pattern note, second cycle running: B-lane candidate claims need
a corpus-grep check before filing — cycle 81's Agent37
rediscovery was the same class.)

## Corpus moves: folds

**C90 Akamai Agent Sandbox — advances THIRD-PARTY →
VENDOR-VERIFIED.** The vendor-issued GlobeNewswire release
(Cambridge, Mass., October 27, 2026), read in full via
stockwatch.com syndication of the GlobeNewswire wire,
confirms the launch: "Akamai Agent Sandbox gives developers a
secure place to run both" — agents run on Akamai Functions, and the
code they write runs in its own isolated environment, sequestered
from the agent's runtime; delivered as an open-source component of
the Spin framework, it uses WebAssembly isolation to set limits on
compute, memory, outbound connections, and system capabilities;
available in beta via the Spin SDK. Provenance precision: the
"denied by default" outbound detail and the intermittent
roughly-one-minute-step limit do NOT appear in the release text and
stay attributed to the converging third-party reports in the C90
row, not upgraded to vendor claims. The C90 row fold records the
advancement with that attribution intact.

**C91 InstaBox by InsForge — advances THIRD-PARTY single-source →
VENDOR-VERIFIED (first-party instabox.sh/docs read in full).**
Firecracker microVM, Debian 13, 4 vCPUs / 8 GiB by default, 16 GiB
root disk, 20 GiB persistent /data disk; default agent-browser
template (Debian, Docker, Node.js, Bun, Python, Go, Rust, OpenJDK
21, desktop + Chromium); plans Free $0, Pro $20/month + usage,
Builder $100/month + usage, Team $500/month + usage; usage vCPU
$0.004/vCPU-hour, memory $0.00225/GiB-hour, storage
$0.00011/GiB-hour, egress $0.02/GiB, runtime billed per second
while running; free plan 1 machine, 5 snapshots, 200 GiB stored
data, 30-minute fixed idle pause, 480-minute max run; paid sizes
up to 32 vCPU / 64 GiB (Team). CORRECTION to the C91 filing: the
free tier is 1 machine per current docs, not 5 — the 5-machine
figure was early-beta (third-party discrepancy notes agree the
docs are authoritative). The C91 row fold records the advancement
and the correction together, so the filing's stale figure does not
stand uncorrected.

**Docker Sandboxes row — Harbor stable arrival fold (no new
C-number, per the C52 ecosystem-integration precedent).** The
first-party Docker blog post (published 2026-10-14, updated
2026-10-29), read in full, now states the Harbor integration "is
available on Harbor's stable release" with
`uv tool install --upgrade "harbor[sbx]>=0.25.0"`. This closes the
C-78-B1 carry: the October 23 stable arrival never appeared on the
sbx release-notes page (A-lane, zero "Harbor" matches, newest
v0.50.0 dated 2026-10-26) because Harbor is a separate product's
release — the Docker blog itself was updated October 29 to the
stable line. A's "NOT ARRIVED" verdict is scoped to the
release-notes page and is not contradicted; B's stable-arrival
claim is confirmed against the first-party blog. The Docker row
fold records the arrival.

## Watch-doc deltas (no new C-numbers)

**Vercel changelog dated sitemap 1471 → 1483 (+12).** Twelve new
dated entries sit above the cycle-81-recorded top entry, and the
count reconciles exactly (+12 = 4 + 8). Four dated **2026-10-30**:
"Data Cache is moving to Runtime Cache"; "Vercel Daemons can now
call services with bindings"; "Ling 3.1 Flash 1019 now available on
AI Gateway for free"; "Add liveness checks to your Daemons". Eight
dated **2026-10-29**: "Strix now supports Vercel AI Gateway"; "IP
geolocation now covers more visitors at higher resolution"; "Vercel
Flags starts 7x faster and no longer extends function duration";
"Node.js 26 LTS is now Generally Available on Vercel"; "Vercel
Connect adds webhook triggers for more providers"; "Control AI
crawlers and assistants separately in Vercel Firewall"; "Vercel
Plugin is now available in Antigravity"; "Mistral Large 4 updated
weights and lower pricing on AI Gateway". None of the twelve titles
mentions Sandbox — sitemap bookkeeping per the C71 precedent.
Re-date notes (existing entries, not counted as new): "The fx
adapter now runs the harness on the host" now sits dated
2026-10-29 (was 2026-10-27 in C81); "Vercel Agent can now validate
alerts before paging" now sits dated 2026-10-28 (was 2026-10-27 in
C81, 2026-10-26 in C80) — a third dating for the same entry, now a
pattern to watch, not a one-off.

**boat.dev pricing stamp-only regen (2026-10-28 → 2026-10-31).**
The page footer now reads Updated: 2026-10-31T01:29:09.936Z (was
2026-10-28T06:58:06.805Z in C81) with every figure verbatim
unchanged (small $0.018 / default $0.036 / large $0.072 / xlarge
$0.200 per hour; plans $20/mo → 100 at once, $100/mo → 300,
$500/mo → 1,000, $2000/mo → 2,000; first plan 7-day free trial; "A
stopped sandbox costs nothing"; "Network traffic. boat does not
bill egress."; the "Compared to others" Freestyle row intact).
Graded DELTA by Surveyor A as a tracked-field movement; the
integrator grades novelty as none — a regen with zero content
change, recorded here as bookkeeping so the next cycle's stamp
comparison has a clean baseline. A third consecutive regen next
cycle would confirm a ~3-day cadence (2026-10-25 → 2026-10-28 →
2026-10-31).

## Dated confirmations (not counted in the 2)

**Hugo CVE cluster CVE-2026-109595 / CVE-2026-109596 /
CVE-2026-109597 — bar UNMET, do not file.** The gohugoio
first-party GHSA list page
(`github.com/gohugoio/hugo/security/advisories`) was opened in
full this cycle: 10 entries, top GHSA-r73q-gwx2-fpxm Oct 13, 2026;
a page-wide find for the shared CVE stem `10959` returned zero
matches. The cluster remains third-party-only; the
file-on-first-party-GHSA bar is unmet. B-lane's cluster carry is
resolved by this A-lane read, not carried. Hugo CVE-2026-100690
likewise still has no first-party GHSA entry.

**Docker Harbor on the sbx release-notes page — scoped
confirmation.** "Harbor" appears nowhere on the docs.docker.com
Sandboxes release notes page (page-wide find, zero matches, read
2026-10-31); the newest entry remains v0.50.0 dated 2026-10-26.
This does NOT contradict the Harbor stable-arrival fold above —
the arrival lives on the Docker blog (a separate product's release
surface), not the sbx release notes. Recorded here so the next
cycle does not re-litigate the scope difference.

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten's round is still
  talks, not a close: Bloomberg's October 30, 2026 report of a
  proposed two-tranche ~$2B round at $26B then $30B, Sands Capital
  expected to lead, explicitly says the round "has not closed",
  terms "remain under negotiation", and neither Baseten nor Sands
  commented. PitchBook still lists Series G (September 22, 2026)
  as "Rumor/Speculation"; Forge's October 20, 2026 Series G/G-1
  rows at $29.02B post-money are unchanged; no S-1. Per the FILE
  ON CLOSE rule this is a strong lead, not a filing. Hand to the
  next cycle's A-lane (HIGH priority): this is the closest the
  trigger has come — verify via a Baseten announcement, reputable
  press confirmation of a close, or a filing; if confirmed, C11
  advances. Arm stays armed.
- **C12 — OPEN (82nd consecutive first-party read).**
  AgentComputer publishes no egress pricing line.
- **Modal egress billing — EFFECTIVE 2026-10-01.** All tracked
  fields read verbatim this cycle; first bill including egress
  still postured for November 1, 2026 — the next cycle (Nov 2) is
  the first read after that date; watch for any billing-posture or
  banner change.
- **C76 advancement chain — unchanged.** pwn.ai Part 2 still
  unpublished (Part 00/Part 01 stand); VerCellBreak still
  third-party-only (Threadlinqs revalidated October 28, 2026,
  ACTIVE/HIGH, no CVE, no vendor patch); Vercel KVM zero-day
  technical write-up still pending (CVE-2026-99999 stands).
- **C77 Strands Box — still macOS-only** (developer preview,
  macOS 15+ on Apple silicon; Linux planned, Windows on radar, no
  date). **C78 MS Execution Containers — Intune/Entra still
  "coming soon".** **C88 Kiro — CLI 3.0 still not confirmed
  landed** ("planned for the end of October" per October 13–17
  sources; re-check next cycle — now overdue). **Perplexity SPACE
  — no Part II, no partner-pricing movement.**
- **Docker $250 new-account credit — expired October 31, 2026.**
  No longer a live texture next cycle.

## Flagged, not filed

B-lane flagged-only items below the bar, noted to avoid
re-discovery: Mintive (agent identity, $7M seed announced October
29, 2026, $11M total, Cowboy Ventures-led — MCP/LLM gateways and
agent identity, no sandbox product); Infisical Series B ($40M at
$600M, announced October 27, 2026, Elad Gil-led — credential
brokering for agents, no sandbox product); Agentic-seL4 research
project (University of Surrey-led, £3.2M ARIA grant, announced
October 22, 2026 — mathematically verified sandbox research, no
vendor product); Tencent Cloud ADP 4.0 / Claw Mode (enterprise
AgentOps platform with an internal cloud sandbox, no standalone
sandbox product or pricing); Prime Inference (Prime Intellect
model serving, distinct from Prime Sandboxes); VAST Agent Sandbox
Foundation Stack, Chainguard Secure Workspaces, and Microsoft
LiteBox v0.1.0 (adjacent carries, unchanged from cycle 81).

## Carries for the next cycle

- Vercel sitemap: watch whether the validate-alerts entry re-dates
  a fourth time and whether the fx-adapter entry settles on
  2026-10-29.
- boat.dev pricing stamp: a third consecutive regen confirms a
  ~3-day cadence; figures have not moved through any of them.
- Modal first bill including egress (postured November 1, 2026):
  the next cycle is the first read after that date.
- C11 Baseten close watch stays HIGH priority; Kiro CLI 3.0
  landing check is now overdue; Hugo CVE cluster +
  CVE-2026-100690 first-party GHSA bars stand; pwn.ai Part 2 and
  VerCellBreak watches continue.
- Next cycle's last-issued C-number is C94; the next filing takes
  C95.
