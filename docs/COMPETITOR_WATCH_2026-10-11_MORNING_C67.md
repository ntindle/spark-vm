# Competitor watch — 2026-10-11 (morning, cycle 67)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-66 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED** (21 opens /
20 successful fetches / 1 established failure (HTTP 404 on
`boat.dev/pricing`, 8th consecutive cycle) / 0 retries / 6
URL-recovery searches, never used as evidence; 18 enumerated items +
1 out-of-list read (4-extra, public-beta Drives page) + 1 out-of-list
outlink misfire (DO availability page, excluded from totals)).
Surveyor B: delta news scan — **0 CANDIDATES / 10 clean dedupes / 16
flagged-only** (bounded scan; doc lists mirror the surveyor capture's
enumerations 1:1 — see the count-honesty check).
**Corpus move this cycle: 0 new filings, 0 folds, 0 mints, 0 re-folds
of aged-out items, 0 age-out movements.** The A-lane deltas
(Microsandbox v0.7.8, Vercel changelog 2026-10-09 section) are
recorded as watch-doc deltas per precedent, not filings.
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261011-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (stat-certified by the integrator from the capture
> mtimes, 2026-10-11 ~09:1x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations and its fetch stats (20 successful reads =
> 18 enumerated items (including 5b, the directly opened limits
> canonical) + 1 out-of-list 4-extra read + 1 out-of-list
> DO-availability-page misfire; the 21st open is the established
> `boat.dev/pricing` 404 re-confirmation, documented inside item 7b). Surveyor B's doc lists enumerate exactly 0
> candidates + 10 dedupes + 16 flagged-only, reconciling with their
> headers and mirroring the surveyor capture's enumerations 1:1.
> Corpus-number integrity: last issued C-number C77; this cycle issues
> none — zero forward.

## A-lane deltas (watch-doc deltas, not filings)

**Microsandbox v0.7.8 — new top release** (first-party
`github.com/superradcompany/microsandbox/releases`, read in full).
Above v0.7.7; canonical URL unchanged. Features: scoped secret
substitution to specific header fields (#1639), `--mount-disk` on
`msb restore` (#1733), runtime-owned detached jobs (#1774), opt-in
application certificate trust helper (#1782), port ranges in
published ports (#1776), filesystem state limits for snapshots
(#1751). Fixes (10): SQLite locks on Linux identity checks, cached
paths after Windows renames, live memory resizes, truncated hpack
rejection, storage cleanup + snapshot recovery, relay keepalive on
arena close, disk restores that would silently drop host mounts
refused, Windows cleanup + usage accounting, disk-only
snapshot-archive restores, shared cleanup + managed-job CI repair.
Deps: libkrun 0.1.41. Maintenance: lockfile refresh after v0.7.7,
bump to 0.7.8 (#1777); full changelog `v0.7.7...v0.7.8`. Per the
v0.7.5/v0.7.6/v0.7.7 precedent: a maintenance/feature release in the
established rapid cadence — recorded, no new C-number, no
sandbox-surface structural move.

**Vercel changelog 2026-10-09 section — new** (first-party
`vercel.com/changelog`, dated index). Five entries: "Agents can now
buy domains with the Vercel CLI"; "New Pro teams now default to
30-day deployment retention"; "Deployment Storage billing begins for
existing Pro teams" (Oct 23); "Microsoft Decision-1 now available on
AI Gateway"; "Liquid AI's d1 is available on AI Gateway". None is
sandbox-adjacent; recorded-not-filed. The JS-rendered index now
renders the newest entries natively (the C59 partial-render caveat
no longer applies to the top section). **No Drives GA entry anywhere
in the dated index.**

**Docker v0.47.0 date reconciliation (not a delta).** Surveyor B
sighted the first-party `docs.docker.com/ai/sandboxes/release-notes/`
page dating v0.47.0 to 2026-10-05 — not in the C66 baseline but dated
Oct 5, outside the fold-gate window. Surveyor A's releases-tab read
this cycle confirms v0.47.0 as the latest STABLE block with no
v0.47.1+ — the sighting corroborates the A-lane standing verdict,
not a change.

## B-lane (0 candidates)

**C11 FILE ON CLOSE — armed, NOT triggered.** Modal $750M (Accel,
$15.75B) and Baseten ~$26B both still "nearing"/"closing in on"/
"neither round has closed" across all recrawled sources. No
company-issued close announcement anywhere this pass.

**Clean dedupes (10):** C11 Modal (no close — language unchanged);
C11 Baseten (no close); C76 Vercel KVM zero-day (no CVE, no
technical write-up, no patch as of the Oct 4–6 third-party FAQs —
gate still open); Vercel Drives (no GA language); DO Agent Droplets
(Oct-1 launch recrawls only, public preview posture); Daytona (no
vendor news newer than V0.223.0, Oct 7); E2B (third-party noise only);
Hugo CVE-2026-100690 (gate unmet — first-party advisories page shows
only sibling GHSAs, surveyor-A-verified); NanoCo (no first-party
product/pricing/docs material); AgentCore SDK CVEs (no new AWS
vendor advisory in window; the June bulletin pre-dates).

**Flagged-only (16):** two C66 watch items now resolved — (1)
OpenAI training-agent DNS-escape: third-party recaps of OpenAI's
report confirm fresh-run-not-resume with no resume date, broader
tool-use pause holds; (2) Zenity "AgentCorruption": AWS spokesperson
disputes the vulnerability characterization (Dark Reading), Zenity
says fully mitigated (Oct 9), no AWS bulletin sighted. Carries:
Perplexity SPACE Part II, Docker $250 Agent Challenge, Docker
Sandbox Kit CNCF spec, Vercel Secure Compute (pre-window), Modal
egress billing — no third-party went-live signal, Vercel Oct-6
sandbox minor incident, OneByZero $20M Series A (carry, thin), NanoCo
re-grade watch, Cloudflare Containers rebuild, Cloudflare
cross-tenant flaw (pre-window incident recap), Modal multi-node GPU
clusters GA (training/inference compute, not the sandbox surface),
alleged Vercel dark-web credential sale (UNCONFIRMED), Modal July
compromise (resolved/watch-only), NVIDIA open agent safety platform
(third-party recount of the OpenShell policy layer + Sentry on
BlueField-4 DPU — below fold).

## Standing-item state

- **C11 FILE ON CLOSE — armed, gate NOT triggered** (67th
  pre-screen cycle; both arms still unclosed).
- **C76 gate (CVE / technical write-up / patch disclosure) — NOT
  advanced.** No CVE in public databases, no write-up, no patch.
- **Vercel Drives GA — standing tracked, not filed.** No GA language
  on any first-party page (private-beta page, public-beta page,
  sandbox docs `last_updated: 2026-09-22`, dated changelog index —
  all still pre-GA).
- **C12 — OPEN (67th consecutive first-party read).** AgentComputer
  publishes no egress pricing line.
- **Modal egress billing — EFFECTIVE 2026-10-01.** First-party page
  tracked fields verbatim; no went-live banner; first bill including
  egress still postured for November 1, 2026. The usage-visibility
  section carries expanded detail (daily breakdown, per-App leaders,
  CLI/SDK billing commands) — observed-but-unverified vs baseline
  (no verbatim record), not graded.
- **Hugo CVE-2026-100690 — third-party-only** (file on first-party
  gohugoio GHSA only).
- **NanoCo re-grade bar — still unmet** (no first-party material).
- **Perplexity SPACE — flagged-only carry; watch for Part II.**
- **C72 / C73 / C74 / C75 — FILED, no movement;** C76 filed, gate
  item open. C73 fold stands (Bedrock Managed Agents preview).
- **C77 Strands Box — filed, no movement** (no post-preview repo
  release, GA, or AgentCore follow-through sighted this pass).
- **DigitalOcean URL-host watch-note:** pricing + limits canonicals
  at `docs.digitalocean.com/.../details/pricing/` and
  `.../details/limits/`; the pricing page's own "Limits" link now
  resolves to the regional availability page (generated 10 Oct 2026)
  — next slot uses the direct limits canonical (as this one did).
- **Aged out stay out:** C29, C45, C56, C66, C67, C62, Heapjack/
  Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed. No
  age-out movements this pass; no re-folds.

## Zero-fabrication statement

Surveyor A's verdicts are grounded in first-party pages actually
opened this pass (captured in `surveyor-a-20261011-0910.md`; zero
search snippets used as evidence). Surveyor B's items are grounded in
observed search-result snippets with source + date context, except
the Docker v0.47.0 date (first-party docs page, opened by Surveyor B
per its capture); no fold-gate candidate appeared, so no B-lane page
needed a full read. This doc's enumerations reconcile 1:1 with both
capture headers. No repo, branch, or PR beyond this watch doc was
edited, merged, pushed, rebased, or otherwise touched. Nothing here
is launch-directed; no pricing-as-commitment copy (P3 gate
unaffected).
