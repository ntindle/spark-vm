# Competitor watch — 2026-10-29 (morning, cycle 81)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-80 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTA, 0 UNVERIFIED** (21 opens /
20 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 22nd consecutive cycle — one re-check only per
the standing rule; the 404 is the evidence)). The two A-lane deltas:
(1) Vercel changelog dated sitemap **1457 → 1471** — fourteen new
dated entries above the baseline top (ten dated 2026-10-28, four
dated 2026-10-27), two of the 2026-10-28 titles Sandbox-titled,
plus one 2026-10-27 harness-adapter entry — sitemap bookkeeping per
the C71 precedent, count reconciling exactly (+14 = 10 + 4); (2)
boat.dev pricing **stamp-only regen** (footer stamp 2026-10-25 →
2026-10-28) with zero figure change — a tracked-field movement, no
content delta. Surveyor B (delegated subagent, read-only): bounded
delta news scan — **3 CANDIDATES claimed / clean dedupes /
flagged-only** (15 searches, all successful; 0 pages opened — no
first-party grading open was available to that lane, so candidates
needing first-party confirmation are said so rather than graded
from snippets).
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still unclosed —
no close announcement, no reputable press report of a close, no
S-1; the Forge Series G/G-1 data point dated 2026-10-20 at $29.02B
post-money is a strong lead only — PitchBook still marks Series G
"Rumor/Speculation" dated 2026-09-22, DeFiLlama still shows the
June Series F as the last round, and the rumored figure in the C11
trigger was ~$26B, not $29.02B — so the gate stays armed);
**C12 OPEN** (81st consecutive first-party AgentComputer read —
still no egress pricing line).
**Corpus move this cycle: 2 filings + 0 folds + 2 watch-doc dated
deltas; 0 age-out movements.** Last-issued C-number: C91 (was C89).
Captures:
`hidden_files/agent_notes/surveyor-a|b-20261029-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-29 ~09:1x–~10:3x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTA, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9). Its open accounting also reconciles
> this cycle (19 anchor opens — 18 successful + 1 established 404 —
> plus 1 releases-page open for item 3 plus 1 continuation re-read
> of the Microsandbox repo page = 21 opens), closing the cycle-80
> count-honesty nit (one successful open unitemized there).
> Surveyor B's capture enumerates 3 candidates + its dedupes +
> flagged-only items, reconciling with its header and search stats
> (15 successful searches; 0 opens — and the capture does not claim
> first-party docs were re-read this pass). The integrator's
> corpus-grep correction (see below) reduces B's 3 claimed
> candidates to 2 filings + 1 dedupe: Agent37 is already filed as
> C82, so B's candidate 3 is a rediscovery, not a filing. The 2
> filings + 2 watch-doc dated deltas are the integration's corpus
> move — 0 folds this cycle. Corpus-number integrity: last issued
> C-number C91 (this cycle issues C90, C91).

## Corpus moves: filings

**Akamai Agent Sandbox — filed C90 (THIRD-PARTY, first-party
verification pending).** Akamai Technologies introduced Akamai
Inference and Akamai Agent Sandbox on October 27, 2026 (reported
October 27–28, 2026 by SiliconANGLE via aiaffairs.com,
expresscomputer.in, 650group.com, aicybr.com — four third-party
reports converging on the same launch). Agent Sandbox runs
agent-generated JavaScript/Python inside an additional restricted
runtime built around WebAssembly isolation on Akamai Functions,
with resource and outbound-connection controls; the default network
policy blocks outbound access. Beta; no charge stated for the
sandbox preview; intermittent execution steps of roughly a minute,
with continuously running stateful agents a future capability.
Akamai previously appears in the corpus only as a SPACE launch
partner (C87 filing: "Akamai has tested and launched SPACE on its
cloud platform") — its own Agent Sandbox product is new corpus
material, not a SPACE texture. Grade is THIRD-PARTY because no
first-party Akamai announcement was opened this pass; the next
cycle's A-lane grades the first-party announcement before any
advancement. spark-vm relevance: a major CDN/edge vendor enters
the agent-sandbox lane with an edge/WebAssembly isolation shape —
distinct from the VM/container shapes that dominate the corpus —
and a default-deny outbound posture that rhymes with spark-vm's
own boundary thinking; the beta's intermittent-execution limit is
the shape to watch against spark-vm's persistent-box story.

**InstaBox by InsForge — filed C91 (THIRD-PARTY, single-source,
first-party verification pending).** A 4 vCPU / 8 GB Linux machine
booting in under a second, with computer use, snapshots,
persistence and public URLs; announced by CEO Hang Huang on
October 14, 2026; InsForge described as a Y Combinator P26 company
(cldnavi.com, single third-party source citing the CEO's X post
and instabox.sh). Single-source provenance is stated plainly here
rather than laundered: the filing rests on one third-party report,
and the next cycle's A-lane verifies first-party (instabox.sh)
before any advancement. Missed by cycle 80 (which reported no
in-lane entrant since October 23, 2026 — InstaBox predates that
window, so the cycle-80 "no entrant" line is corrected, not
contradicted: the entrant existed, the scan missed it).
spark-vm relevance: another YC agent-cloud entrant competing
squarely on the boot-latency axis (sub-second boot) that
spark-vm's own fast-start story targets; the 4 vCPU / 8 GB
shape is a directly comparable unit to spark-vm's box sizes.

## Integrator correction: B-lane candidate 3 is a rediscovery, not a filing

**Agent37 (YC F26) — NOT re-filed; dedupe against C82.** Surveyor
B's third candidate (Agent37, launched October 12, 2026, hosted
agent sandboxes at ~10% of rival costs) is already in the corpus
as C82 — founder-attested on the founder's own Launch HN post
(2026-10-12) with a vendor-verified pricing fold (2026-10-15,
first-party agent37.com pricing comparison, 2 vCPU / 4 GB basket
$4.76/month). B's aiweekly.co piece (October 13, 2026, citing the
same Launch HN post) adds no new product fact beyond the C82 row;
its "priced from about $4.94/month for 2 vCPU/4 GB" figure sits
against the first-party $4.76 for the same basket — a $0.18
third-party/first-party texture discrepancy, recorded here, not
resolved: the first-party $4.76 stands and the $4.94 is not folded
into the row. No new C-number, no row change. (Pattern note for
the next cycle: B-lane candidate claims need a corpus-grep check
before filing — the same class as the C83 reconciliation, where a
pre-window bulletin surfaced as "likely already in corpus" and
grep came back negative; here grep came back positive, so the
filing is declined.)

## Watch-doc deltas (no new C-numbers)

Two of the items below are this cycle's counted dated deltas
(Vercel sitemap, boat.dev regen); the Harbor and Hugo items are
dated confirmations, recorded here but not counted in the 2.

**Vercel changelog dated sitemap 1457 → 1471 (+14).** Fourteen new
dated entries sit above the cycle-80-recorded top entry, and the
count reconciles exactly (+14 = 10 + 4) — unlike cycle 80, no
deeper insertion is unaccounted for. Ten dated **2026-10-28**:
"Vercel CI is now in beta"; "Box Mount now runs in Vercel Sandbox";
"Vercel Container Registry now supports 2 GB compressed image
layers"; "Virtual models now available on AI Gateway"; "Run Paseo
agents on Vercel Sandbox"; "Particle-1 is now available on AI
Gateway"; "Agents can now enable Web Analytics and Observability
Plus with Vercel CLI"; "fx is now available in T3 Code"; "Vercel
Plugin now available in OpenCode"; "AI traffic insights now
available in Vercel Observability". Four dated **2026-10-27**:
"The fx adapter now runs the harness on the host"; "Deploy a
container from a plain Dockerfile"; "Vercel Agent sessions now cost
67% less"; "HarnessAgent now supports image inputs for all harness
adapters". Two of the ten 2026-10-28 titles mention Sandbox
("Box Mount now runs in Vercel Sandbox"; "Run Paseo agents on
Vercel Sandbox"), plus the 2026-10-27 harness-adapter entry —
changelog entries, not a sandbox-surface change, so bookkeeping
per the C71 precedent. Re-date note (not counted as new): "Vercel
Agent can now validate alerts before paging" now sits dated
2026-10-27; it was listed under 2026-10-26 in the C80 block — a
date revision on an existing entry. The C80 2026-10-26 block
otherwise sits intact directly below.

**boat.dev pricing stamp-only regen (2026-10-25 → 2026-10-28).**
The page footer now reads Updated: 2026-10-28T06:58:06.805Z (was
2026-10-25T05:53:37.223Z in C80) with every figure verbatim
unchanged (small $0.018 / default $0.036 / large $0.072 / xlarge
$0.200 per hour; plans $20/mo → 100 at once, $100/mo → 300,
$500/mo → 1,000, $2000/mo → 2,000; first plan 7-day free trial; "A
stopped sandbox costs nothing"; "Network traffic. boat does not
bill egress."; the "Compared to others" Freestyle row intact).
Graded DELTA by Surveyor A as a tracked-field movement; the
integrator grades novelty as none — a regen with zero content
change, recorded here as bookkeeping so the next cycle's stamp
comparison has a clean baseline.

**Docker Harbor stable still not arrived — dated-delta
confirmation.** The cycle-79 correction (the Harbor stable release
expected 2026-10-23 did not land) now extends to 2026-10-29:
"Harbor" appears nowhere on the docs.docker.com Sandboxes release
notes page (page-wide find, zero matches, read 2026-10-29); the
newest entry remains v0.50.0 dated 2026-10-26. Harbor remains
nightly-only as far as the release notes show. B-lane's Harbor
carry is resolved by this A-lane read, not carried. Re-check next
cycle; do not treat the October 23 stable arrival as landed.
> **Convention note (from the cycle-79 review):** a dated delta
> that corrects a prior dated delta's expectation without adding
> new vendor material counts as a dated delta, not a second fold —
> the Harbor line corrects the C80 expectation's date and adds no
> new vendor material, so it is recorded here as a dated
> confirmation, not a fold and not counted in this cycle's 2 dated
> deltas.

**Hugo CVE cluster CVE-2026-109595 / CVE-2026-109596 /
CVE-2026-109597 — bar UNMET, do not file (dated confirmation).**
The gohugoio first-party GHSA list page
(`github.com/gohugoio/hugo/security/advisories`) was opened in
full this cycle: 10 entries, top GHSA-r73q-gwx2-fpxm Oct 13, 2026;
a page-wide find for the shared CVE stem `10959` returned zero
matches — the first-party GHSA page does not carry any of the
three CVE IDs, and no new advisory entry has appeared since
Oct 13. The cluster remains third-party-only; the
file-on-first-party-GHSA bar is unmet. B-lane's cluster carry is
resolved by this A-lane read, not carried. The CVE-record-level
texture from cycle 80 (affected <0.167.0 / unaffected 0.167.0)
stands ungraded at the first-party level.

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  unclosed — no Baseten announcement, no reputable press report
  of a close, no S-1 filing (accessipos: "Baseten still hasn't
  filed an S-1"). Texture now carried in the gate: Forge's funding
  table lists Series G ($1.99B, $51.10/share) and Series G-1
  ($1.23B, $57.05/share), both dated October 20, 2026, at $29.02B
  post-money, investors undisclosed — but PitchBook still marks
  Series G "Rumor/Speculation" (September 22, 2026), DeFiLlama
  still shows Series F (June 22, 2026, $1.61B at $13B) as the last
  round, and the rumored figure in the C11 trigger was ~$26B, not
  $29.02B. Per the FILE ON CLOSE rule, the Forge table alone is
  NOT a confirmed close and is NOT filed. Hand to the next
  cycle's A-lane (high priority): verify via a Baseten
  announcement, reputable press, or a filing before treating
  Series G as closed; if confirmed, C11 advances. Arm stays armed.
  Carried texture: the June Series F $1.5B two-tranche completion
  ($11B then $13B, Altimeter/Conviction/Spark-led, Bloomberg
  2026-10-22) and DeFiLlama's $19.7B third-party estimate (as of
  Oct 28, 2026) both stand as texture on the closed round, not a
  new round.
- **C12 — OPEN (81st consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-29;
  tracked fields verbatim; first bill including egress still
  postured for November 1, 2026 — three days out, so the next
  cycle is the first post-bill read. No went-live banner; B-lane
  reconfirm: no posture change (charging began October 1, usage
  visible since September 1 but not charged that month).
  Texture: a one-core/1 GiB sandbox held 24h costs $3.98 before
  extras (theweightedaverage.com, October 19, 2026); Modal $750M
  Series D (C80, already filed) restated — dedupe.
- **Vercel Drives GA — FILED (C86).** No posture or pricing change
  on the GA surface this pass; the private-beta page is unchanged
  since the C77 corroboration fold.
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm Oct 13 Moderate). File-on-first-party-GHSA
  bar stands.
- **PwnEscape patch-adoption texture (C76).** New texture, not a
  corpus move: severitydaily.com disputes the CVE record's
  integrity justification — the kernel CNA scores CVE-2026-99999
  at 9.3 with prose describing host command execution, while
  pwn.ai's own write-up states "it is not a claim of root command
  execution in any vendor's production environment" (memory
  disclosure demonstrated on Vercel production sandboxes; crash
  and code execution on researcher-owned machines only).
  Red Hat/SUSE/Amazon score 8.8. Still no CISA KEV listing, no
  in-the-wild exploitation reported. Corpus C76 advancement chain
  unchanged; pwn.ai Part 2 still unpublished (the Part 00 intro's
  "findings land in a later post" still stands).
- **Vercel KVM zero-day technical write-up — still pending.**
  No Vercel-authored kernel write-up sighted; third-party
  write-ups only (tuxcare.com, blog.margrop.net, abchaudary.me,
  severitydaily.com). CVE-2026-99999, CVSS 9.3 (CNA) / 8.8
  (Red Hat, SUSE, Amazon), stands.
- **Baseten–Blaxel acquisition — old texture, dedupe.** Baseten
  acquired Blaxel per a September 10, 2026 businesswire release;
  Blaxel already appears in sandbox pricing comparisons; the
  acquisition predates cycle 80 and is not a new corpus item.

## Flagged but not filed

- **C89 first-party lead — STALE CARRY, corrected.** Surveyor B
  carried "Daytona founder blog post still not located" — that
  carry is stale: Surveyor A located and read the first-party
  post in full in cycle 80
  (`daytona.io/dotfiles/daytona-raises-60m-series-b-to-build-the-agent-cloud`,
  "Daytona Raises $60M Series B to Build the Agent Cloud", OCT 20
  2026, Ivan Burazin), and C89 advanced THIRD-PARTY →
  VENDOR-VERIFIED in the Daytona row. B's searches this pass
  simply did not surface the URL. Not carried; the next cycle
  should not re-raise it as unlocated.
- **VAST Agent Sandbox Foundation Stack (October 21, 2026, NVIDIA
  GTC Berlin) — adjacent, below the bar.** VAST Data + NVIDIA
  stack running NemoClaw agents in OpenShell sandboxes on the VAST
  AI OS, with zero-copy clones and VAST DataBase agent records
  (letsdatascience.com). Storage/state infrastructure around
  NVIDIA's OpenShell, not a new sandbox product or vendor — noted
  only so the next cycle does not re-discover it as an entrant.
- **Chainguard Secure Workspaces (October 16, 2026) — adjacent,
  needs an A-lane read.** Chainguard launched Secure Workspaces
  and Checks to constrain what coding agents can pull in and run
  (supply-chain angle, per dev.to digest citing InfoQ). B-lane
  does not file it on a digest mention alone; the A-lane may
  promote it if it reads this as in-lane agent-workspace product
  rather than supply-chain tooling.
- **Microsoft LiteBox v0.1.0 (tagged October 7, 2026) — adjacent,
  not an agent-VM product.** Rust library OS for isolating Linux
  apps (gVisor/Firecracker middle seat; 20 crates at v0.1.0). No
  agent product, no sandbox-as-a-service — below the bar; noted
  only to avoid re-discovery.
- **Kiro CLI 3.0 / V3-default flip — due end of October
  (carry).** Re-check next cycle whether CLI 3.0 landed and
  whether it changes any sandbox posture; CLI 2.31+
  `sandbox.json` headless carry already filed as C88 texture.
  CLI 2.34 (October 23, 2026) is non-sandbox (MCP elicitation,
  memory deletion, workflow controls).
- **VerCellBreak (TL-2026-3425)** — still third-party-only: no
  Vercel first-party comment published; no CVE; no vendor patch
  disclosed (Threadlinqs intel record: Severity HIGH, Status
  ACTIVE, first published 2026-10-13, last reviewed 2026-10-13,
  0 CVEs referenced). New texture: NSFOCUS published a case
  analysis on October 27, 2026 (four prerequisites,
  acme.com/evil.com walk-through) per the Threadlinqs timeline.
  Carry.
- **Zenity AgentCorruption — correction stands.** No CVE, no AWS
  bulletin; disclosure third-party-only; Zenity says the
  default-role permissions were substantially hardened on review
  September 29, 2026 and the issue fully mitigated October 9, 2026;
  AWS disputes the findings demonstrate a vulnerability (The
  Register, updated 2026-10-12; NeoTeo; CSO Online). The carried
  mitigation date **2026-09-29** is correct per Zenity's own labs
  post; the cycle-78 **2026-10-09** figure was the error. Carry.
- **Perplexity SPACE repo traction** — no Part II; no
  partner-pricing movement; E2B Compatibility Wrapper and
  multi-operator posture unchanged from C87 (Akamai launched,
  Crusoe adding, CoreWeave setup guidance). Third-party star
  counts conflict (820 as of October 16 per Forkast vs 1,149
  cited in cycle 80) — not chased; no movement. Carry.
- **Strands Box** — still macOS-only (multiple October sources
  restate: macOS 15 or later on Apple silicon only; Linux planned,
  Windows unsupported); the Lambda MicroVM deployment texture
  (builder.aws.com, 2026-10-07) is a third-party deployment, not
  a first-party platform-support change. Carry C77 as macOS-only
  until the A-lane grades the first-party table.
- **MS Execution Containers** — Intune/Entra still "coming soon"
  (first-party blogs.windows.com 2026-10-07; third-party
  summaries restate the same, no dates). New texture: Agent 365
  is GA (GCC October 1, 2026), and the October GA announcement
  sits awkwardly next to the earlier Build messaging that Intune
  could already configure MXC environments — the GA announcement
  is the current statement. Carry.
- **Modal VM Sandboxes** — GA stands; no new product/news
  movement this pass. Carry.
- **C79** — no new AWS advisory beyond 2026-127-AWS (carry). The
  BeyondTrust AgentCore SDK pair (CVE-2026-12530 / CVE-2026-16796,
  `install_packages()` RCE, fix SDK 1.18.1) is already in the
  corpus (C66 watch doc, 2026-10-09, third-party-only, no AWS
  advisory); new texture on the bulletin itself: agents imported
  with toolkit versions before 0.3.14 must be re-imported with
  the fixed release — upgrading alone does not remove the
  injected code.
- **Vercel sitemap entries** — non-sandbox bookkeeping only, apart
  from the two Sandbox-titled entries folded into the dated delta
  above (carry).
- **Boat homepage leaderboards** — marketing copy naming providers
  (carry).
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass.

## Aging

- No age-outs this pass. 2 filings, 0 folds. C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261029-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten Series G close verification (Forge G/G-1 $29.02B
post, dated 2026-10-20 — verify via announcement, reputable press,
or filing; if confirmed, C11 advances); C90 — Akamai Agent Sandbox
first-party announcement grading (advance THIRD-PARTY →
VENDOR-VERIFIED on a first-party read); C91 — InstaBox first-party
verification (instabox.sh; single-source filing until then); C82 —
Agent37 price texture ($4.94 third-party vs $4.76 first-party —
first-party stands unless a new first-party page moves it); C76 —
pwn.ai's promised Part 2 (the write-primitive-to-host-control
chain) + Vercel first-party KVM zero-day technical write-up
(distinct doc; still pending); C88 — Kiro CLI 3.0 / V3-default
flip (due end of October) + credential-brokering posture vs
swapd's edge; VerCellBreak first-party/CVE movement; SPACE
open-source follow-through (repo traction, second partner
announcements, partner pricing posture); Vercel Drives GA
follow-through (usage/pricing posture changes); Perplexity SPACE
Part II (still unmet); Strands Box multi-OS follow-through
(first-party table re-grade + the Lambda MicroVM deployment
texture); Hugo GHSA movement on CVE-2026-100690 + the
CVE-2026-109595/96/97 cluster (first-party grading stands
unmet — GHSA list carries none of the three IDs as of
2026-10-29); NanoCo re-grade (first-party bar); AgentCore SDK —
any NEW AWS advisory beyond 2026-127-AWS; Modal egress billing
post-Nov-1 (first bill arrives November 1 — the next cycle is the
first post-bill read); Zenity AgentCorruption CVE/bulletin;
Docker Agent Challenge through 2026-10-31 ($250 new-account
credit expires October 31); Modal VM Sandboxes progression;
Hopx/Beam/Tenki first-party material; Docker v0.50.x
follow-through + Harbor stable arrival re-check; Microsoft
Execution Containers enterprise-management follow-through; the
Vercel sitemap count field (1471 baseline); the dead
`vercel.com/docs/sandbox/features` URL (use `/docs/sandbox`);
Microsandbox releases now resolve under
`superradcompany/microsandbox`; Baseten Environment Network
follow-through (RL-env partner network — watch whether it grows a
sandbox surface); Chainguard Secure Workspaces A-lane read
(supply-chain tooling vs in-lane agent-workspace product).
