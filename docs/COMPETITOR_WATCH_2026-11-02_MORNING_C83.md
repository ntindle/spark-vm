# Competitor watch — 2026-11-02 (morning, cycle 83)

**P77 PRE-SCREEN-TRIGGERED FULL PASS.** Pre-screen (light novelty
screen: full A-chain first-party re-read + bounded B-lane news scan):
A-lane **17 VERIFIED NO-CHANGE, 1 VERIFIED DELTA (count-field
bookkeeping only)** (19 opens / 18 successful fetches / 0 retries /
1 established 404 (`boat.dev/pricing`, 24th consecutive cycle — one
re-check only per the standing rule; the 404 is the evidence)); B-lane
**4 CANDIDATES** (9 searches, all successful; 0 pages opened — no
first-party grading open was available to that lane, so candidates
needing first-party confirmation are said so rather than graded from
snippets). The single A-lane delta (Vercel changelog sitemap 1483 →
1484, one new Flags entry dated 2026-11-02, no Sandbox title) is
sitemap bookkeeping per the C71 precedent, not a corpus move on its
own; the CORPUS MOVE verdict rests on the B-lane candidates. The
integrator then graded all four candidates first-party (plus the
pre-screen's Hugo re-grade question) before any filing.
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$2B two-tranche round
still "has not closed" / "terms are not final" in November 1–2
restatements of the October 30 Bloomberg report; Forge's October 20
Series G/G-1 rows at $29.02B unchanged; the S-1 hits this scan are
Base Electron Corp., a different company; no Baseten S-1);
**C12 OPEN** (83rd consecutive first-party AgentComputer read —
still no egress pricing line).
**Corpus move this cycle: 5 filings + 0 folds + 1 watch-doc dated
delta; 0 age-out movements.** Last-issued C-number: C99 (was C94).
Captures:
`hidden_files/agent_notes/2026-11-02-competitor-prescreen.md` plus
`hidden_files/agent_notes/integrator-reads-20261102-0910.md` (the
loop owner's own full-page first-party reads, recorded the same
cycle per the 2026-10-15 lesson; loop working notes in the goal
workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-11-02 ~09:1x–~10:5x CST).
>
> **Count-honesty check:** the pre-screen's self-reported A header (17
> VERIFIED NO-CHANGE, 1 DELTA) reconciles exactly with its 18 item
> enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b, 7c, 7d, 8a,
> 8b, 8c, 8d, 9). Its open accounting also reconciles (18 anchor
> opens, all successful first-try, plus 1 established-404 re-check =
> 19 opens, 18 successful). The pre-screen's B lane enumerates 4
> candidates + 10 clean dedupes + 5 flagged-only, reconciling with
> its header and search stats (9 successful searches; 0 opens — and
> the capture does not claim first-party docs were re-read in that
> lane). Count unit note: those are bullets, not items — one clean-dedupe
> bullet covers three vendors (Tenki / Prime / Agent37), one flagged-only
> bullet covers three products (Abra / DeepSeek Super-Agent / Wysera),
> and C11 appears in both buckets intentionally (clean dedupe + flagged-only
> strong lead), so a future reader should not "correct" the arithmetic.
> The integrator's grading converts all 4 B candidates to
> filings and adds a fifth filing from the pre-screen's Hugo re-grade
> question (see below); the B lane's flagged-only CVE-2026-120313
> stays below the bar and is not filed. Numbering note: the
> pre-screen suggested C95–C98 for its four candidates; the
> integrator assigns C95 Copilot, C96 Google ACE, C97 Beta9 pair,
> C98 Prefab, and C99 to the Hugo pair from the re-grade question.

## Corpus moves: filings

**GitHub Copilot cloud sandboxes — filed C95 (VENDOR-VERIFIED,
first-party GitHub changelog + docs read in full).** GitHub's
October 28, 2026 changelog entry ("Work from anywhere with a new,
connected Copilot cloud experience") makes the connected Copilot
cloud experience AND cloud sandboxes "both generally available on
paid Copilot plans," rollout starting October 28: by default every
session runs in a cloud sandbox on GitHub-managed infrastructure
(fast start, snapshot resume, no one-hour limit on total running
session time), and "Billing for cloud sandbox usage begins in
November 2026," drawing from the now-shared dollar-based Actions
entitlement. The first-party docs page "Product usage included with
each plan" pins the figures the changelog does not state: included
compute $12 Free / $18 Pro / $18 Team / $300 Enterprise Cloud per
month, with "Cloud sandbox compute and memory" drawing from it —
paid plans only; the Free $12 Actions entitlement does not unlock
cloud sandboxes.
Corpus context: C50 covers the tenant-scoped Managed Runtime and the
corpus carries JetBrains local-sandbox controls, but not this
cloud-sandbox GA + billing item — no dedupe collision. spark-vm
relevance: the largest developer platform just made "agent sessions
run in the vendor's cloud sandbox by default, billed against a shared
compute pool" the normal shape — spark-vm's hosted story competes
against that default, not against a self-hosted install; the shared
pool (CI minutes and sandbox minutes drawing down one allowance) is
the pricing shape to beat or match.

**Google Agent Compute Engine — filed C96 (VENDOR-VERIFIED,
first-party Google Cloud blog posts read in full via read-only
live-browser read).** "Introducing Agent Compute Engine and expanding agent governance" and the deep dive "Inside Agent Compute Engine:
Building the compute foundation for the agentic era," both dated
October 22, 2026: a purpose-built, fully managed compute service
that "already powers Gemini as an agent for work tasks," giving every
agent its own hardware-isolated microVM — own guest kernel and root
access behind a Cloud Hypervisor boundary, dedicated vTPM, "one
agent per VM, no exceptions," no shared kernels, block storage, or
devices — with checkpoint, restore, clone, migrate, and branching
as core capabilities, and credentials held outside the guest (Titanium
IPU silicon-rooted defense-in-depth; service credentials injected at
egress by the Agent Gateway; the microVM holds only an ephemeral,
short-lived identity). Preview is "in the coming months" (sign-up for
updates) — no firm preview date and no ACE pricing appear in either
post. Sibling Agent Substrate is the open-source, hardened sandbox
architecture that powers ACE, "try on GKE today," already in partner
use (Nous Research multi-tenant agents). Integrator corrections to
third-party summaries, all from the first-party pages: the deep dive
is dated October 22, not October 23 — there is no October 23 version;
Substrate is NOT evaluation/non-production only, that characterization
is rejected; the 200,000-agent / 500-activations-per-second /
sub-500ms figures appear in NEITHER post and are NOT asserted (the
posts' quantified figures are partner-reported Substrate results:
Anthropic 300% more coding sessions for Claude Code, Databricks 2.5x
more coding tasks with 70% less human supervision for Agent Bricks —
attributed as such, never as ACE benchmarks). spark-vm relevance:
another major cloud vendor in 2026 to converge on microVMs (not
containers) as the agent primitive, with credentials-outside-the-guest
as the headline security property — spark-vm's isolation story must
answer "why is your boundary as strong as a per-agent microVM with
no credentials inside," and the checkpoint/clone/migrate session
model is the bar for spark-vm's own suspend/resume story.

**Beta9 sandbox escapes — CVE-2026-120306 + CVE-2026-120307 —
filed C97 as a pair (VENDOR-VERIFIED with a stated scoping limit,
first-party release + fix commit read in full).** Both CVEs published
November 1, 2026, both CVSS 3.1 9.9 (AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H
per the CVE record, JFrog CNA), both fixed in worker 0.1.756.
The 120307 vulnerability mechanism below is CVE-record-attributed (see
the scoping limit at the end of this filing); the 120306 mechanism is
first-party-verified. CVE-2026-120306: Beta9 build sandbox escape via chroot-only isolation
— Buildah RUN steps ran with `BUILDAH_ISOLATION=chroot`, keeping the
worker pod's PID/network/IPC/user namespaces as uid 0 with
CAP_DAC_OVERRIDE, so `/proc/1/root` (the worker container's filesystem)
was writable. CVE-2026-120307: container escape via unvalidated
sandbox file paths — the sandbox file API joined tenant paths onto
worker paths, allowing read/write/list/delete on the hosting worker
as root, including other tenants' files; a read-only proof downloaded
the worker pod's Kubernetes service-account token, bound to
cluster-admin in shipped remote-node manifests. First-party evidence:
the worker-0.1.756 release page names commit `a28bf12` ("Handle
sandbox edge cases (#1897)") as its commit, and the commit diff
confirms the 120306 mechanism fix (`BUILDAH_ISOLATION=chroot` →
`oci`) plus volume-mount validation and workspace-ownership checks.
Scoping limit, stated honestly: the text render of the commit diff
did not surface the `os.OpenRoot` hunk the CVE record describes for
120307, so the 120307 fix mechanism is CVE-record-attributed while
the fix commit/release and the 120306 mechanism are
first-party-verified. spark-vm relevance: two textbook
"the sandbox boundary was a string operation, not a boundary" failures
in one vendor on one day — path-join-then-check (prefix check before
`filepath.Join` cleans `..`) and isolation-mode-as-a-default
(chroot because nobody passed a flag) are both failure classes
spark-vm's own file-serving and build paths must be audited against,
and a service-account token bound to cluster-admin turns any worker
escape into a cluster escape.

**Prefab UI Generative UI sandbox escape — CVE-2026-120338 —
filed C98 (VENDOR-VERIFIED with a stated advisory gap, first-party
release + fix commit read in full).** Published November 1, 2026;
affected prefab-ui 0.14.0–0.20.2; fixed in 0.21.0 (shipped October 26,
2026, six days before publication, per third-party reports — the
release page render states no date, so no first-party release date
is asserted). The optional Generative UI sandbox runs caller-supplied
Python in Pyodide inside a Deno subprocess; versions 0.14.0–0.20.2
launched Deno with unrestricted `--allow-read` / `--allow-write` /
`--allow-net` and left the `Deno` API on the JavaScript global, so
supplied code could read and write host files as the server OS user
and persist execution (CVE-record detail: via a `.pth` file in site-packages); the usual
remote path is FastMCP's `GenerativeUI` provider. CVSS 10.0 in the
unauthenticated FastMCP scenario (FastMCP defaults to no auth), 9.9
for an authenticated tool caller; Generative UI is opt-in and the
host must have Deno installed. First-party evidence: the v0.21.0
release includes #538 "Refresh dependencies and fix renderer and
sandbox regressions" (the release notes do NOT label it a security
fix), and fix commit 030f074 (PR #538) states the fix precisely —
Deno filesystem and network permissions revoked after startup and
before accepting code, permission prompts disabled, bootstrap network
limited to cdn.jsdelivr.net — and corrects the old overclaim ("WASM
execution alone does not establish a host security boundary").
Advisory gap: the GHSA page GHSA-595q-jv4r-q7j9 returns HTTP 404 on
text fetch (consistent with third-party reports that it was not
publicly accessible) — this filing does NOT rest on the advisory; it
rests on the first-party release + fix commit, with range/CVSS from
the CVE record. spark-vm relevance: the "documented as a sandbox,
implemented as a subprocess with full permissions" pattern — a
sandbox claim in docs is not a boundary, and any spark-vm surface
that executes model-written code must have its permission set
demonstrated, not described.

**Hugo theme file-read pair — CVE-2026-109595 + CVE-2026-109596 —
filed C99 as a pair (VENDOR-VERIFIED; cycle-82 "bar unmet"
CORRECTED, first-party advisories + NVD records read in full).**
Both published October 12, 2026 (NVD), both Moderate, both fixed in
Hugo v0.167.0. CVE-2026-109595 (CWE-22, CVSS 4.0
AV:L/AC:L/AT:N/PR:N/UI:A/VC:H): Hugo 0.84.0–0.167.0 path traversal via
ESBuild's fallback resolver in js.Build / js.Batch / css.Build — a
theme ships a relative import or symlink pointing outside the project
and the file content is bundled into published JavaScript or CSS.
CVE-2026-109596 (CWE-59, same CVSS 4.0 vector): Hugo 0.162.0–0.167.0
improper link resolution via nested-mount ancestor directories — a
symlink at a virtual ancestor directory lets `resources.Match` list
and publish local files during builds. The cycle-82 bar test (search
the first-party GHSA list rendering for the CVE string) was the wrong
test: GitHub advisory pages do not print CVE IDs, and the Sep 28 GHSA
entries predated cycle 82 — the C82 test failed on the rendering, not
on absence. The correct tie is
NVD: each CVE's NVD record lists its first-party advisory as a
reference (109595 → GHSA-r4xx-89rf-5424; 109596 → GHSA-6c8w-mpp8-9w47),
and the two mapped advisory texts match their NVD descriptions in
substance (the third Sep 28 advisory, css.Sass, was also read in full
first-party but has no CVE mapping). Cluster
scope correction: CVE-2026-109597 is NOT a sandbox item — its NVD
record ties it to GHSA-wcpj-vcvm-j4pg, a stored-XSS-via-heading-ID
issue (CWE-79) — so it is NOT filed; and the css.Sass advisory
GHSA-3jfr-vjcq-7jvf maps to NONE of the three CVEs, so it stays
CVE-unmapped and is NOT filed. Note the literal GHSA ID renders as
`GHSA-r4xx-89rf-5424` on both GitHub and NVD — transcribed as
rendered. spark-vm relevance: the theme-is-a-supply-chain lesson in
miniature — a build that bundles third-party-authored files must
treat every import resolution as untrusted input, and the
"fallback resolver with no notion of the project root" is exactly
how a documented boundary silently stops being one.

## Corpus moves: folds

None this cycle. No prior row advanced grade and no prior row was
corrected in place, except the C99 bar-correction narrative above
(which files new rows rather than folding an old one).

## Watch-doc dated deltas

- **Vercel changelog sitemap 1483 → 1484** (+1). The single new dated
  entry above the cycle-82 top block: "Evaluate Vercel Flags from
  another project without sharing SDK keys." dated 2026-11-02. No new
  Sandbox-titled entry. The fx-adapter harness entry has settled on
  2026-10-29 and the validate-alerts entry on 2026-10-28 — no fourth
  re-date for either. Bookkeeping per the C71 precedent.

## Dated confirmations (not counted in the 1 delta)

- **boat.dev pricing stamp UNCHANGED** (footer still
  2026-10-31T01:29:09.936Z) — no third consecutive ~3-day regen has
  arrived yet (next due ~2026-11-03 on the old cadence); all figures
  unchanged; `boat.dev/pricing` still HTTP 404 (24th consecutive
  cycle).
- **Modal egress-billing page UNCHANGED after the November 1, 2026
  first-bill date** — still future-tense wording ("Your first bill
  including egress arrives on November 1, 2026"), no went-live
  banner, no wording change. Modal remains live-in-effect per the
  C58 effectiveness grade; the page simply has not been updated
  past the date.
- **Docker Harbor stable still NOT on the release-notes page**
  ("Harbor" zero matches); newest entry still v0.50.0 dated
  2026-10-26.
- **Docker $250 new-account credit EXPIRED October 31, 2026** —
  texture drop, not a filing; no longer restated as live.
- **C11 Baseten arm still unclosed** (see header); **C12
  AgentComputer egress pricing still absent** (83rd consecutive
  read); Kiro CLI 3.0 still unconfirmed (latest sighted 2.31.0,
  October 13); pwn.ai Part 2 still unpublished; Vercel first-party
  KVM zero-day write-up still pending; VerCellBreak still
  third-party-only (no CVE, no Vercel patch).
- **Flagged-only, below the bar:** CVE-2026-120313 (Network-AI path
  traversal, CVSS 7.5, single traversal in a non-agent-sandbox
  product); ReqRes Agent Sandbox (mock REST API, no execution
  environment); Abra / DeepSeek Super-Agent / Wysera (agent products,
  no sandbox product). Noted only to avoid re-discovery.

## Carries for next cycle

- C11 watch stays HIGH priority: the Bloomberg two-tranche report is
  the closest the trigger has come; re-check for a confirmed close
  or S-1 next cycle.
- Google ACE November 9, 2026 "AI Infrastructure Future" event watch
  (further architecture detail expected); ACE preview-date and
  pricing watch (neither in the October 22 posts).
- boat.dev pricing stamp: watch for a third regen (~2026-11-03 on the
  old cadence) or confirmation the regen cadence has
  ended.
- Vercel sitemap: watch whether the validate-alerts / fx-adapter
  entries re-date again; both have now settled for one cycle.
- Modal: watch whether the egress-billing page is ever updated past
  the November 1, 2026 first-bill wording.
- pwn.ai Part 2 watch continues; VerCellBreak watch continues; Kiro
  CLI 3.0 landing check continues; Hugo CVE-2026-100690
  first-party GHSA bar stands (still no first-party entry).
- Docker canonical row still carries the $250 credit line — fold the
  October 31 expiry note into that row next cycle (recorded here as a
  dated confirmation this cycle, not as a fold).
- Next cycle's last-issued C-number: C99.
