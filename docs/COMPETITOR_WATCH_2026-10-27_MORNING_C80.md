# Competitor watch — 2026-10-27 (morning, cycle 80)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-79 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED** (22 opens /
21 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 21st consecutive cycle — recovery declined per the
standing rule) / 1 wrong-anchor recovery open — the Vercel Drives
public-beta changelog page was opened in error for item 4c; no verdict
graded on it, and the correct private-beta anchor was then opened and
graded — / 2 follow-up opens for the Daytona Series B post). The two
A-lane deltas: (1) Docker Sandboxes **v0.49.2 + v0.50.0** (v0.50.0:
configurable kit host mounts, persistent kit volumes across updates
and sandbox recreation, cloud sandbox inspection, plus
host-execution/credential/workspace-copy hardening; v0.49.2: the
eMudhra CA-compromise response — Go 1.27.3, bundled llmman 0.1.571,
template images rebuilt with updated CA certificates); (2) Vercel
changelog dated sitemap **1448 → 1457** — eight new dated entries
above the baseline top, all dated 2026-10-26, two Sandbox-titled —
sitemap bookkeeping per the C71 precedent. Surveyor B (delegated
subagent, read-only): bounded delta news scan — **0 CANDIDATES / 14
clean dedupes / 7 flagged-only** (17 searches, all successful; 0
pages opened — no first-party grading open was available: the
site:daytona.io query returned zero results, and the Hugo GHSA ID
was truncated in the CVE-record snippet, so it went to the A-lane as
a lead rather than a graded re-check).
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still talks-only —
PitchBook Series G dated 2026-09-22 still "Rumor/Speculation"; latest
confirmed round remains the June $13B Series F; no S-1 — accessipos:
"Baseten still hasn't filed an S-1"; the Bloomberg 2026-10-22
two-tranche texture is now carried in the C11 gate — the June Series
F $1.5B was completed in two tranches at $11B then $13B valuations,
led by Altimeter, Conviction and Spark — texture on the already-closed
round, not a new round; DeFiLlama's $19.7B figure (as of Oct 26) is a
third-party estimate, not a close);
**C12 OPEN** (80th consecutive first-party AgentComputer read — still
no egress pricing line).
**Corpus move this cycle: 0 filings + 2 folds + 2 watch-doc dated
deltas; 0 age-out movements.** Last-issued C-number: C89 (unchanged).
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261027-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-27 ~09:1x–~10:0x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9). Fetch-stat note (integrator flag, not a
> verdict change): the capture's fetch stats read 22 opens / 21
> successful first-try fetches, but its itemized open breakdown
> accounts for 21 opens (18 anchor opens — 17 successful + 1
> established 404 — plus 1 wrong-anchor recovery open plus 2
> follow-up opens) — one successful open is unitemized in the
> capture. All 18 enumerations are individually graded with quoted
> anchors, so no verdict rests on the unitemized open; the next cycle
> should itemize every open. Surveyor B's capture enumerates exactly
> 0 candidates + 14 dedupes + 7 flagged-only, reconciling with its
> header and search stats (17 successful searches; 0 opens — and the
> capture does not claim first-party docs were re-read this pass,
> closing the cycle-79 capture-hygiene nit). The two folds and the
> two watch-doc dated deltas are the integration's corpus move — 0
> filings + 2 folds + 2 watch-doc dated deltas. Corpus-number
> integrity: last issued C-number C89 (cycle 76); this cycle issues
> none.

## Corpus moves: folds

**Daytona Series B — grade advancement THIRD-PARTY → VENDOR-VERIFIED
(first-party post read in full by Surveyor A this cycle).** The
cycle-79 lead is resolved: the first-party post exists at
`https://www.daytona.io/dotfiles/daytona-raises-60m-series-b-to-build-the-agent-cloud`
("Daytona Raises $60M Series B to Build the Agent Cloud", OCT 20
2026, Ivan Burazin, CEO & Co-Founder), read in full: "Today we're
announcing a $60M Series B at a $1B valuation, led by FirstMark
Growth, bringing our total funding to $91M"; angels Patrick Collison
(Stripe), Tobi Lütke (Shopify), Aravind Srinivas (Perplexity), Eric
Yuan (Zoom), Olivier Pomel (Datadog), Adam D'Angelo (Quora), Brendan
Foody (Mercor); strategic investors Qualcomm Ventures, Samsung Next,
Okta Ventures; "Since January, Daytona's revenue has grown
approximately 25×, with average month-over-month net revenue
retention of approximately 135%"; "Agent Execution Cloud" framing —
"the execution layer: computers, browsers, storage, and anything else
an agent needs"; "the only provider with Linux, Windows, macOS, and
GPU sandboxes on one platform." New texture vs the C89 filing (THIRD-PARTY, genznewz.com 2026-10-23,
citing Dealroom): the Series A was $24M, also FirstMark-led, closed
February 2026; Snorkel alone has provisioned 1M+ sandboxes (carried
third-party texture from C79). Recorded as a vendor-verified
advancement (no new C-number) per the C88 precedent. C89's grade in
the corpus row advances THIRD-PARTY → VENDOR-VERIFIED.

**Docker Sandboxes v0.49.2 + v0.50.0 — dated-delta fold into the
Docker Sandboxes row (VENDOR-VERIFIED, first-party release notes).**
Two new releases since the cycle-79 baseline (v0.49.1 top,
2026-10-20). New top **2026-10-26 / v0.50.0**: "adds configurable kit
host mounts, preserves persistent kit volumes across updates and
sandbox recreation, and adds cloud sandbox inspection. It also
strengthens host-execution, credential, and workspace-copy
protections." Headline items: `sbx cp` rejects symlinks escaping a
sandbox workspace (including via alternate host paths, macOS
`/private/tmp`, Linux bind mounts); host Git commands no longer run
programs configured by a sandbox through the workspace `.git`
directory; browser/clipboard/self-update helpers run only from
trusted system locations; local source kits reused only when digests
match recorded builds; Git kit references reject ambiguous paths,
non-ASCII hostnames, and SSH transport syntax; MCP OAuth blocks
cross-origin credential redirects; `--mount HOST:SANDBOX_PATH` for
`host-mount@1` kit-declared mounts; persistent kit volumes retain
data across kit updates and sandbox removal/recreation; `sbx --cloud
inspect <id|name>`; Gordon clears **Approve all** / **Always allow**
grants on resume; HTTP network rules support query-parameter
restrictions. Second **2026-10-21 / v0.49.2**: "updates Go and
bundled dependencies as part of Docker's response to the eMudhra
certificate authority compromise" — Go 1.27.3, bundled llmman 0.1.571;
built-in template images rebuilt with updated CA certificates;
mitigation paths (recreate with `--pull always`, or update CA
certificates in existing sandboxes). Recorded as a watch-doc dated
delta and row fold (no new C-number) per the C32/C69 version-bump
precedent. The v0.50.0 hardening is a security-relevant release for
the sandbox surface — still a fold, not a new C-number, on this
evidence alone; the v0.49.2 eMudhra item is remediation, not a Docker
vulnerability.

## Watch-doc deltas (no new C-numbers)

**Vercel changelog dated sitemap 1448 → 1457 (+9).** Eight new dated
entries sit above the cycle-79-recorded top entry; every dated
section beneath matches the C79 baseline record-for-record, all
dated 2026-10-26: "Discover 1000+ services on Vercel Connect from
the CLI"; "Run Scale AI's AgentEnv evals on Vercel Sandbox"; "Create
custom monitors in Vercel Observability"; "Vercel Agent can now
validate alerts before paging"; "Vercel Sandbox commands now support
stdin"; "Customizable widgets for project cards"; "GPT-6.1 Terra now
available on AI Gateway"; "Faster pnpm installs". Two of the eight
titles mention Sandbox ("Run Scale AI's AgentEnv evals on Vercel
Sandbox"; "Vercel Sandbox commands now support stdin") — changelog
entries, not a sandbox-surface change, so bookkeeping per the C71
precedent. The count rose by 9 while 8 new entries sit above the
baseline top — one additional entry was inserted deeper in the list
(not at the top; unlocated in this pass, not graded as a separate
delta — same pattern as C79).

**Docker Harbor stable still not arrived — dated-delta confirmation.**
The cycle-79 correction ("the Harbor stable release expected
2026-10-23 did not land by 2026-10-25") now extends to 2026-10-27:
"Harbor" appears nowhere on the docs.docker.com Sandboxes release
notes page (page-wide find, zero matches, read 2026-10-27); the
newest entry is v0.50.0 dated 2026-10-26. Harbor remains nightly-only
as far as the release notes show. Re-check next cycle; do not treat
the October 23 stable arrival as landed.
> **Convention note (from the cycle-79 review):** a dated delta that
> corrects a prior dated delta's expectation without adding new vendor
> material counts as a dated delta, not a second fold — the Harbor
> line corrects the C79 expectation's date and adds no new vendor
> material, so it is counted here as a dated delta, not a fold.

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  talks-only — PitchBook Series G dated 2026-09-22 still
  "Rumor/Speculation"; latest confirmed round remains the June
  $13B Series F; no first-party close announcement; no S-1 filing.
  Texture now carried in the gate: the June Series F $1.5B was
  completed in two tranches at $11B then $13B valuations, led by
  Altimeter, Conviction and Spark (Bloomberg 2026-10-22, via
  aiweekly.co / startupresearcher.com / convergedigest.com) —
  texture on the already-closed round, not a new round. DeFiLlama's
  estimated valuation $19.7B (as of Oct 26, 2026) is a third-party
  estimate, not a close. Third-party sizes for the round differ ($1.5B
  per Bloomberg vs $1.61B per DeFiLlama) — both third-party figures
  for the same closed round; neither changes the gate. Arm stays armed.
- **C12 — OPEN (80th consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-27;
  tracked fields verbatim; first bill including egress still
  postured for November 1, 2026. No went-live banner; B-lane
  reconfirm: no posture change (third-party pricing pages
  corroborate the corpus row verbatim; charging began October 1,
  usage visible since September 1 but not charged that month).
  Texture: Modal's $750M Series D (C80, already filed) restated
  with Sandboxes at a $300M annualized run rate and the company
  above $1B annualized (techstartups.com, 2026-10-15) — dedupe.
- **Vercel Drives GA — FILED (C86).** No posture or pricing change
  on the GA surface this pass; the private-beta page is unchanged
  since the C77 corroboration fold.
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm Oct 13 Moderate). VulnCheck remains the CVE
  assigner (cve.circl.lu record, published 2026-09-26, updated
  2026-09-30); the gohugoio GHSA-x3mx-cm49-8m9c still carries no
  CVE-2026-100690 identifier (verified by opening the page in
  cycle 78; no change signal this pass). File-on-first-party-GHSA
  bar stands.
- **PwnEscape patch-adoption texture (C76).** Debian DSA-6568-1
  delivers kernel 6.12.113 (Trixie); Debian 12 Bookworm still
  vulnerable; Ubuntu kernels still "under evaluation"; AlmaLinux
  8/9/10 all ship vulnerable code; NVD scoring pending. No CISA
  KEV entry (catalog version 2026-10-16), no in-the-wild
  exploitation reported. Texture: upstream fix commit
  6785011f8b16 (net.git 2026-10-08, mainline 2026-10-14); fixed
  releases 5.10.272 / 5.15.223 / 6.1.190 / 6.6.159 / 6.12.113 /
  6.18.57 / 7.2.11. The CVE-2026-99999 identifier is now carried in
  the CVE Program record (updated October 15, 2026), which
  partially retires the cycle-79 caution that it "should not yet be
  treated as independently confirmed" — the corpus's "CVSS 9.3
  Critical stands" line is the kernel-CNA score, not a Vercel
  confirmation. New texture: pwn.ai expects working exploits
  within weeks for weaker configurations, within a month for default
  hypervisor configurations. Deployment-only — not a corpus move.
- **pwn.ai Part 2 — still unpublished.** The pwn.ai write-up
  surfaced this pass is the Part 00 intro post
  (pwn.ai/blog/pwnescape, "Part 00: Intro"), which says the
  network-escape findings land "in a later post" — the
  write-primitive-to-host-control chain details are still held
  back for the follow-up. Gate item pending.
- **Vercel KVM zero-day technical write-up — still pending.**
  Vercel's 2026-10-14 findings report (filed 2026-10-21) still
  withholds kernel details ("Fixes are under private review and
  CVEs are pending"); third-party write-ups only (dev.to
  explainer, CSO Online, cyberpress.org, pbxscience.com,
  hwbusters.com). CVE-2026-99999, CVSS 9.3 Critical, stands.

## Flagged but not filed

- **New Hugo CVE cluster (CVE-2026-109595 / CVE-2026-109596 /
  CVE-2026-109597) — watch item, new texture, still not filed.**
  The cve.circl.lu record for CVE-2026-109595 (published
  2026-10-12, updated 2026-10-15) now lists a vendor-advisory
  reference to a gohugoio GitHub security advisory URL (truncated
  in the snippet) and states affected <0.167.0 / unaffected
  0.167.0 — which resolves the cycle-79 Tenable "no known solution"
  vs dossier "fixed v0.167.0" conflict toward fixed-in-v0.167.0 at
  the CVE-record level. But the GHSA ID is truncated in the snippet
  and no first-party GHSA page was opened this pass, so the
  first-party linkage is not yet graded. Hand to the next cycle's
  A-lane: locate the gohugoio GHSA for CVE-2026-109595/96/97 and
  grade it; if the GHSA carries the CVE IDs, the cluster meets the
  file-on-first-party-GHSA bar.
- **Baseten Environment Network launch — below the in-lane bar.**
  Baseten launched a vetted partner network on October 23, 2026 to
  help customers build custom RL environments for post-training
  (stockanalysis.com, citing Baseten). It is a first-party launch,
  but it is a partner network for RL environments on the
  inference/post-training side, not a sandbox or agent-VM product —
  below the corpus's in-lane bar. Not filed; the A-lane may promote
  it if it reads the launch differently.
- **Strands Box on aarch64 Linux inside Lambda MicroVMs — not a
  platform-support change.** builder.aws.com (2026-10-07): an AWS
  solutions architect built Box for aarch64 Linux and ran it inside
  Lambda MicroVMs (83 ms per box, 22.7 boxes/s per 1 GB VM). This
  is a third-party deployment report, not a first-party
  platform-support change; the first-party docs table was not
  re-verified this pass. Carry C77 as macOS-only until the A-lane
  grades the first-party table.
- **University of Surrey Agentic-seL4 research project — research,
  not a vendor.** £3.2M ARIA-funded project (announced October 22,
  2026, Universities of Surrey, Sheffield and Melbourne) to build a
  formally verified sandbox for AI agents. No product, no vendor,
  no launch — below the bar; noted here only so the next cycle does
  not re-discover it as a "new entrant".
- **TrueFoundry $19M / Mistlabs $26M** — adjacent (agent/LLMOps gateway, ambient consumer agent), not sandbox vendors (carry).
- **VerCellBreak (TL-2026-3425)** — still third-party-only: no
  Vercel first-party comment published; no CVE; no vendor patch
  disclosed (Threadlinqs intel record: Severity HIGH, Status
  ACTIVE, first published 2026-10-13, last reviewed 2026-10-13,
  0 CVEs referenced). New texture: AIR says Vercel judged the
  finding out of scope and declined the report; The Record
  (2026-10-13) reports Vercel said it needs time to work out a
  patch. Carry.
- **Zenity AgentCorruption — correction note (the cycle-79 review
  asked for this one-line correction).** No CVE, no AWS bulletin;
  disclosure third-party-only; Zenity says the default-role
  permissions were substantially hardened on review September 29,
  2026 and the issue fully mitigated October 9, 2026; AWS disputes
  the findings demonstrate a vulnerability (The Register, updated
  2026-10-12; NeoTeo; CSO Online). Correction: the carried
  mitigation date **2026-09-29** is correct per Zenity's own labs
  post (the final pre-publication review on September 29, 2026
  observed the substantial default-role hardening); October 9,
  2026 is when Zenity said the reported issue had been fully
  mitigated, not the mitigation date. The cycle-78 **2026-10-09**
  figure was the error; the corpus carries 2026-09-29 and stops
  flipping it. Consistent with the corpus's existing resolved
  carry.
- **Perplexity SPACE repo traction** — 1,149 stars / 84 forks
  (~2026-10-17) unchanged from the C78 filing; no Part II; no
  partner-pricing movement; E2B Compatibility Wrapper and
  multi-operator posture unchanged from C87; fourweekmba.com notes
  the October 15, 2026 post gives no pricing for the partner
  offerings, no date by which SPACE will be available to
  CoreWeave/Akamai/Crusoe customers, and no customer names. Carry.
- **Nightona fork note (carry)** — bex.co (2026-10-02) notes the
  June-2026 community fork of Daytona's frozen AGPL release —
  pre-existing, not new. (Label corrected per the cycle-79 review:
  the note first appeared in the C79 watch doc, so in C80 it is
  genuinely a carry.)
- **Strands Box** — still macOS-only (first-party docs table not
  re-verified this pass; third-party coverage confirms developer
  preview, macOS only, Linux planned, no dates); multi-OS
  expansion still a priority with no dates (carry).
- **MS Execution Containers** — Intune/Entra still "coming soon"
  (first-party blogs.windows.com 2026-10-07; third-party
  summaries restate the same). New texture: Agent 365 is GA (GCC
  October 1, 2026), and the October GA announcement sits awkwardly
  next to the earlier Build messaging that Intune could already
  configure MXC environments — the GA announcement is the current
  statement. Microsoft lists GitHub Copilot, OpenAI Codex,
  OpenClaw, Replit, LM Studio, NVIDIA OpenShell and Unsloth AI as
  already supporting MXC; Anthropic Claude Code, Perplexity and
  Manus named as coming (carry).
- **Modal VM Sandboxes** — GA stands; the "VM sandboxes in beta"
  phrasing in one third-party roundup is stale against the
  corpus's Oct-14 first-party GA filing (carry).
- **C79** — no new AWS advisory beyond 2026-127-AWS (carry). The
  BeyondTrust AgentCore SDK pair (CVE-2026-12530 /
  CVE-2026-16796, `install_packages()` RCE, fix SDK 1.18.1) is
  already in the corpus (C66 watch doc, 2026-10-09,
  third-party-only, no AWS advisory); new texture on the bulletin
  itself: agents imported with toolkit versions before 0.3.14 must
  be re-imported with the fixed release — upgrading alone does not
  remove the injected code.
- **Vercel sitemap entries** — non-sandbox bookkeeping only, apart
  from the two Sandbox-titled entries folded into the dated delta
  above (carry).
- **Boat homepage leaderboards** — marketing copy naming providers
  (carry).
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass.

## Aging

- No age-outs this pass. 0 filings, 2 folds. C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261027-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C89 — Daytona's
first-party Series B confirmation is now VENDOR-VERIFIED — watch the
pricing-posture follow-through; C76 — pwn.ai's promised Part 2
(the write-primitive-to-host-control chain) + stable-branch patch
adoption tracking + Vercel first-party KVM zero-day technical
write-up (distinct doc; still pending); C88 — Kiro
credential-brokering posture vs swapd's edge; VerCellBreak
first-party/CVE movement; SPACE open-source follow-through (repo
traction, second partner announcements, partner pricing posture);
Vercel Drives GA follow-through (usage/pricing posture changes);
Perplexity SPACE Part II (still unmet); Strands Box multi-OS
follow-through (first-party table re-grade + the Lambda MicroVM
deployment texture); Hugo GHSA movement on CVE-2026-100690 + the new
CVE-2026-109595/96/97 cluster (first-party grading pending — the
GHSA ID is truncated in the CVE-record snippet; the A-lane should
locate and open the gohugoio GHSA); NanoCo re-grade (first-party
bar); AgentCore SDK — any NEW AWS advisory beyond 2026-127-AWS;
Modal egress billing post-Nov-1 (first bill arrives November 1);
Zenity AgentCorruption CVE/bulletin; Docker Agent Challenge through
2026-10-31; Modal VM Sandboxes progression; Hopx/Beam/Tenki
first-party material; Docker v0.50.x follow-through + Harbor stable
arrival re-check; Microsoft Execution Containers enterprise-management
follow-through; the Vercel sitemap count field (1457 baseline);
the dead `vercel.com/docs/sandbox/features` URL (use
`/docs/sandbox`); Microsandbox releases now resolve under
`superradcompany/microsandbox`; Baseten Environment Network
follow-through (RL-env partner network — watch whether it grows a
sandbox surface); the A-lane open-itemization hygiene note (every
open itemized next cycle — see the count-honesty check above).
