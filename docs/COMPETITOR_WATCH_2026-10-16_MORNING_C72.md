# Competitor watch — 2026-10-16 (morning, cycle 72)

**Two-surveyor pass — P77 PRE-SCREEN-TRIGGERED FULL PASS.** Surveyor A:
first-party vendor re-verification against the cycle-71 baseline —
**16 VERIFIED NO-CHANGE, 2 VERIFIED DELTAS, 0 UNVERIFIED** (21 opens /
20 successful first-try fetches / 0 retries / 1 established 404
(`boat.dev/pricing`, 13th consecutive cycle — recovery declined per the
standing rule) / 6 URL-recovery searches, never used as evidence).
A-lane deltas: Docker Sandboxes v0.48.0 (dated 2026-10-13) and the
Vercel changelog dated sitemap (1413 → 1425 — the new 2026-10-15
section includes **"Vercel Drives is now generally available"**).
Surveyor B: bounded delta news scan — **2 CANDIDATES / 13 clean
dedupes / 16 flagged-only** (15 searches, 15 successful / 0 failed;
3 pages opened and read in full, 3 successful / 0 failed).
**C11 FILE-ON-CLOSE NOT TRIGGERED** (Baseten ~$26B still in talks);
**C76 ADVANCED** (technical write-up published + upstream fix merged
into Linux mainline Oct 14; CVE still pending per Vercel's Oct 14
disclosure); **C77 NOT advanced**; **C12 OPEN** (72nd consecutive
first-party AgentComputer read — still no egress pricing).
**Corpus move this cycle: 2 new filings (C86, C87), 2 folds,
watch-doc deltas.** Captures:
`hidden_files/agent_notes/surveyor-a|b-20261016-0910.md` (loop working
notes, in the goal workspace — not part of this repo).

> **Timestamp provenance note:** the standing rule (no per-read times
> in capture bodies) held this cycle. All verdicts below are
> mtime-bounded (integrator-checked, 2026-10-16 ~09:1x–~10:3x CDT).
>
> **Count-honesty check:** surveyor A's self-reported header (16
> VERIFIED NO-CHANGE, 2 DELTAS, 0 UNVERIFIED) reconciles exactly with
> its 18 item enumerations (1, 2, 3, 4a, 4b, 4c, 5a, 5b, 6, 7a, 7b,
> 7c, 7d, 8a, 8b, 8c, 8d, 9) plus its 1 out-of-list read (the Drives
> GA page — evidence for the 4a delta), and with its fetch stats (20
> successful fetches + 1 established 404 = 21 opens). Surveyor B's
> capture enumerates exactly 2 candidates + 13 dedupes + 16
> flagged-only, reconciling with its header and search stats
> (15/15 successful searches; 3/3 successful opens). Corpus-number
> integrity: last issued C-number C85; this cycle issues C86, C87 —
> exactly two forward.

## Corpus moves: filings + folds

**(C86) Vercel — "Vercel Drives is now generally available" — new
filing, VENDOR-VERIFIED.** First-party dated changelog sitemap
(`vercel.com/changelog/sitemap.md`, read in full this cycle): Total
posts **1425** (was 1413); new dated section 2026-10-15 (12 entries),
headlined by "[Vercel Drives is now generally available]" (dated
2026-10-15). The linked GA page
(`vercel.com/changelog/vercel-drives-is-now-generally-available`,
read in full): "Vercel Drives is now generally available for Vercel
Sandbox on Hobby, Pro, and Enterprise." A Drive is persistent storage
mounted as a directory in a Vercel Sandbox; files remain available
after the sandbox stops, so later runs and other sandboxes can access
them by mounting the same Drive. NEW capability vs the beta pages:
**Drive forks** — "You can also fork a Drive into independent
writable Drives. Forks inherit the source Drive's data, region, and
maximum size, then store their own changes. Parallel workers can
start with the same files and make changes without affecting the
original or one another." A companion first-party blog
(`vercel.com/blog/introducing-vercel-drives-persistent-storage-for-agents`,
read in full by surveyor B this cycle): "It is now generally
available for Vercel Sandbox." / "now generally available for Vercel
Sandbox on all plans"; drives default 1 TiB (1 GiB on Hobby), up to
16 TiB; "Forking is generally available." **This closes the
long-standing "Vercel Drives GA" tracked item** (carried since the
2026-09-23 public-beta filing; the standing GA gate is met by
explicit first-party "generally available" language on the tracked
sandbox surface). spark-vm relevance: Vercel's persistent-storage
story graduates on the tracked sandbox surface; drive forking
(parallel workers from a shared saved workspace, changes isolated
from the original and each other) is directly comparable to
spark-vm's snapshot/fork semantics — a first-party reference for
the hosted lane's workspace-persistence design. The sandbox-docs
Features list now links "Drives" with no "(beta)" qualifier,
consistent with GA — the "(beta)" label-rendering watch item is
retired by this filing.

**(C87) Perplexity — open-sources SPACE (Apache 2.0), announced
2026-10-15 — new filing, VENDOR-VERIFIED.** First-party
`perplexity.ai/hub/blog/open-sourcing-space` (read in full this
cycle): "Today, we're open-sourcing SPACE"; SPACE — "Sandboxed
Platform for Agentic Code Execution" — "has powered all Computer
sessions" since July and "handled millions of sandbox creations per
day"; sandbox creation "three to five times faster than with our
previous provider" on the same production traffic; each sandbox
"runs inside a small virtual machine with its own operating
system"; network and platform-held credentials managed outside the
sandbox; red-team disclosure restated (0/108 VM→host escapes;
network-restriction bypasses found and fixed, "neither identified
attack method succeeded in follow-up testing"). Launch partners,
same page: "Akamai has tested and launched SPACE on its cloud
platform"; "Crusoe is also partnering with Perplexity to add SPACE
to its Managed AI Services portfolio"; "CoreWeave has published
setup guidance for developers who want to deploy SPACE for
evaluation." **NOT the tracked SPACE Part II** (no Part II label
anywhere on the page or in coverage; this is an open-source
platform release, distinct from the C54 red-team evaluation and
the C84 routing disclosure — both carry over). spark-vm
relevance: the first open-source agent-sandbox platform release
from a tracked vendor at production scale — the SPACE platform
(Firecracker microVMs, platform-held credentials outside the
sandbox, operator-side red-teaming) is the closest public reference
architecture to spark-vm's own posture; the multi-operator launch
partners (Akamai, Crusoe, CoreWeave) are the first multi-cloud
operator traction for an in-lane open platform. Filed adjacent —
research/open-source, not a new hosted product.
> Date-honesty note: the fetched first-party page carries no
> visible publication date in the text; third-party recaps
> (siliconangle, runtimewire — "Published Oct 15th, 2026, 7:06pm
> CT") date the announcement 2026-10-15, consistent with
> search-metadata age. The filing is dated 2026-10-15 with this
> attribution recorded.

**C74 fold — "Vercel Connect now supports Secure Compute"
(2026-10-15).** First-party dated changelog sitemap entry
(2026-10-15, read this cycle): Secure Compute — Vercel's
private-networking surface (static IP egress + private AWS VPC
resource access via VPC peering, per the 2026-10-07 fold) — now
attached to the Vercel Connect integration-hub product, spreading
the private-networking posture beyond the sandbox surface itself.
Folded into the C74 row per the C32 primary-source-verification
fold precedent. spark-vm relevance: design color for the hosted
lane's egress posture — the private-networking surface is now a
platform-wide pattern at Vercel, not a sandbox-only feature.

**C76 fold — technical write-up published + upstream fix merged
into Linux mainline (CVE still pending).** First advancement since
the 2026-10-03 filing. Third-party: The Hacker News (Oct 15)
publishes the pwn.ai technical write-up ("PwnEscape"): specially
made network packets sent from inside a virtual machine → host
memory disclosure (~32 bytes/packet against Vercel production
sandboxes), host crash on researcher hardware; the researcher
frames it as a lab result — "not a claim of root command execution
in any vendor's production environment" (surveyor B read this
coverage). Upstream fix authored by Red Hat's Michael S. Tsirkin —
"applied to the net.git tree on October 8 and merged into Linus
Torvalds' mainline tree on October 14" (webpronews, ~14h old).
Vercel's October 14 disclosure states that **CVEs remain pending**
(cyberpress); the third-party identifier CVE-2026-99999 is NOT
confirmed — cyberpress explicitly cautions it "should not yet be
treated as independently confirmed." No Vercel first-party
write-up sighted. Folded into the C76 row (no new C-number — the
advancement is write-up + patch, not a new incident). spark-vm
relevance: the Firecracker-on-KVM exposure posture persists —
patch exists in mainline but no CVE assignment yet; the write-up
is the first public mechanism detail for the guest-to-host vector
Vercel confirmed Oct 6. Hypervisor-level remediation posture
belongs in spark-vm's own sandbox threat-model notes.

## Watch-doc deltas (no new C-numbers)

**Docker Sandboxes v0.48.0 (dated 2026-10-13, first-party release
notes read in full).** CLI refactored across all commands —
consistent terminal output + JSON/YAML formats, breaking flag
spellings (`--detached` → `--detach`; `--yes`/`-y` → `--force`/`-f`;
`--quiet`/`-q` → `--no-progress`; `--output` → `--format`;
`--env` → `--env-name`); structured output now snake_case (`sbx ls`
returns the array directly); managed Codex and Claude Desktop SSH
targets on macOS and Windows; additional v3 kit capabilities; kits
with startup commands addable to existing sandboxes; `SBX_AGENT`
env exposes the provisioned agent name; `sbx kit pack` hardening
(archive exclusions, no writes into the kit's `files/`, Windows 8.3
path handling). Recorded as a watch-doc dated delta (no new
C-number) per the C32/C69 version-bump precedent. Note: the SSH
targets and kit-startup-commands additions are sandbox-capability-
adjacent; the flag renames are operator-visible breaking changes
for scripted agent workflows.

**Vercel changelog dated sitemap 1413 → 1425.** The 2026-10-15
section accounts for the movement (12 entries): Drives GA (filed
C86); "Vercel Connect now supports Secure Compute" (folded to C74);
10 non-sandbox (Token Pass; Daemons public beta; AI Gateway model
launches; BYOC on AWS GA; Connect Enterprise-Managed Authorization;
MCP Events public beta; Python GA). The 2026-10-14, 2026-10-13,
2026-10-12, 2026-10-08 sections unchanged. No Drives beta-to-GA
language anywhere else on the sitemap; the public-beta entry still
dates 2026-09-23.

**Daytona third-party coverage, no movement.** undercodenews
fact-check piece on SDK v0.224.0 (Oct 12, region-aware sandbox
creation) — third-party release coverage, no vendor launch; the
first-party changelog still tops at V0.224.0 (A lane verified).

## Standing gates

- **C68:** resolved; not graded.
- **C11 FILE ON CLOSE — NOT triggered.** Baseten ~$26B round still
  "reportedly in talks" — "Neither round has closed, and the funding
  amounts remain undisclosed" (analyticsinsight.net, crawled <1h);
  "terms could still shift before either deal signs" (bytevyte).
  Arm stays armed.
- **C12 — OPEN (72nd consecutive first-party read).**
  AgentComputer publishes no egress pricing line (figures re-read
  verbatim: $0.07/CPU-hr, $0.04375/GB-hr memory,
  $0.000683/GB-hr hot storage, $0.000027/GB-hr cold storage).
- **Modal egress billing — EFFECTIVE 2026-10-01.** Read 2026-10-16;
  tracked fields verbatim; no went-live banner; first bill
  including egress still postured for November 1, 2026.
- **Vercel Drives GA — NOW FILED (C86).** The tracked item is closed
  by the filing; no further GA re-check needed. The sandbox-docs
  "(beta)" label-rendering watch item is retired (consistent with
  GA).
- **NanoCo re-grade bar — unmet.** No new first-party vendor
  material.
- **Hugo CVE-2026-100690 — third-party-only.** First-party
  advisories re-verified in full (10 entries; top
  GHSA-r73q-gwx2-fpxm, Oct 13, Moderate; no 100690). File on
  first-party GHSA only.
- **VerCellBreak (TL-2026-3425) — third-party-only.** Status ACTIVE;
  "No vendor patch available as of 2026-10-13" (threadlinqs). No
  CVE referenced. NOT a C76 advancement (distinct mechanism,
  third-party only).
- **AgentCore SDK — no NEW AWS advisory** beyond 2026-127-AWS
  (Oct 6: CVE-2026-105812 / CVE-2026-106032; the BeyondTrust pair
  CVE-2026-12530/16796; AWS's Oct 13 statement to SC Media calls
  the Zenity AgentCorruption research "expected and documented
  behavior").
- **Docker $250 Agent Challenge — through 2026-10-31.** No new
  development; carry.
- **Modal VM Sandboxes GA — no progression** since the C80 fold
  (GA language already filed; follow-through color only).
- **Microsoft Execution Containers (C78) — no new movement**
  post-filing (SDK v1.0.0 stable Oct 7; Codex/Copilot/OpenClaw/
  Replit/LM Studio/Unsloth integrations; Claude Code forthcoming).
- **Hopx / Beam / Tenki — no new first-party vendor material.**
- **OpenAI training-agent DNS escape — pause holds.** No new
  sightings.
- **Perplexity SPACE Part II — still NOT sighted.** The OSS
  release (C87) is a separate first-party launch, not Part II.

## Flagged but not filed

- Perplexity SPACE OSS coverage texture (third-party): Akamai
  "tested and launched the platform in its own cloud" (mezha);
  median sandbox-creation latency 185 ms → 60 ms (tokenpost) —
  corroboration for C87, no separate mint.
- deployedbyai "The Deploy Log" — new third-party launch tracker
  sighting (sourced-to-vendor-page model, 1618 rows); useful
  provenance for future GA sightings; not a vendor.
- Zenity AgentCorruption — no vendor movement (AWS posture
  unchanged).
- Vercel $1M Sandbox challenge — carry (mentioned in the
  PwnEscape coverage; no first-party page read this pass).
- Modal July compromise — resolved/watch-only, carry.
- Cloudflare Containers agent rearchitecture (Sept 30 blog) —
  pre-window carry.
- "The Sandbox" blockchain-game + game-launch hits — name
  collision, out of scope.
- Aged-out stay out: C29, C45, C56, C66, C67, C62,
  Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI; C26 closed.
  No age-out movements this pass; no re-folds.

## Aging

- No age-outs this pass. No re-folds. C11 quiet stays 0/3.
- Full evidence in the surveyor captures
  (`hidden_files/agent_notes/surveyor-a|b-20261016-0910.md`, in the
  goal workspace).

## Watch-outs for the next slot

C11 — Baseten ~$26B close (still armed); C76 — CVE assignment
still pending (the remaining advancement) + first-party write-up
watch; VerCellBreak first-party/CVE movement; SPACE open-source
follow-through (repo traction, second partner announcements);
Vercel Drives GA follow-through (usage/pricing posture changes);
Perplexity SPACE Part II (still unmet); Strands Box multi-OS
follow-through; Hugo GHSA movement on CVE-2026-100690; NanoCo
re-grade (first-party bar); AgentCore SDK — any NEW AWS advisory
beyond 2026-127-AWS; Modal egress billing post-Nov-1; Zenity
AgentCorruption CVE/bulletin; Vercel PwnEscape first-party
write-up; Docker Agent Challenge through 2026-10-31; Modal VM
Sandboxes progression; Hopx/Beam/Tenki first-party material;
Docker v0.48.x follow-through.
