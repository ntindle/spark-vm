# Competitor watch — 2026-09-27 (early-morning)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the post-post-post-post-post-pre-dawn pass (#543,
merged as `43c7178`): (A) fast-mover + pricing re-verification vs the
~04:25–04:27 CDT (2026-09-27) baseline (vendor reads ~04:56 CDT
2026-09-27), (B) delta news scan ~04:24–04:54 CDT (~30-min delta window;
queries ran ~04:56–04:58 CDT). Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260927-0454.md`,
`agent_notes/surveyor-b-20260927-0454.md` (under `hidden_files`).
Naming-hygiene note: this pass EXECUTES the 0424 doc's rotation advisory
— the six-deep POST_ pre-dawn chain (`PREDAWN` →
`POST_PREDAWN` → … → six-POST) rotates to the new `EARLY_MORNING`
series rather than stacking a seventh POST_. Suffix per the series-rotate
precedent (the 0154 slot's `PREDAWN_LATE` was the prior series-breaker).

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: the already-aged-out trio —
Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI —
drew zero recrawl hits (quiet) — all remain out; no new age-outs this
pass (every carried item had contact: C37/C55/C57/C58 vendor re-verified;
C62 recrawled via the OpenAI coverage wave; C66 no contact this pass (quiet)). Carried P63 gap: still no re-fold path for an
aged-out item that resurfaces with real movement (follow-up proposal from
the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~04:56 CDT; every page loaded on first
attempt — 9/9 first-try, zero fetch failures (the all-first-try streak
restarted at the 0424 pass extends to **2 passes**). Every verified figure
matches the ~04:25–04:27 CDT baseline on substance. No corpus fold (C32
precedent: nothing changed on a primary source).

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26 2026 /
   V0.218.0** ("KVM sandbox parameter and CLI WorkOS application").
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated heading
   still **2026-09-22**.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September**; **no 26-Sep entries in any lane**. Drives not re-checked
   per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE + "$100 one-time usage credit", Pro $150/month,
per-second $0.000014/0.000028/0.000056/0.000084/0.000112 for 1/2/4/6/8
vCPU); boat.dev ($0.018/0.036/0.072/0.200 per hour — small/default/large/
xlarge; "A stopped sandbox costs nothing"; 25 free trial hours;
$20/$100/$500/$2000 tiers — canonical `docs.boat.dev/pricing`); TermSquad
($9 (2 vCPU/4 GB/40 GB) / $19 (4/8/75) / $29 (6/12/100) / $49 (8/24/200);
BYO-AI FAQ intact); DigitalOcean Managed Agents — canonical
`digitalocean.com/pricing/harness-runtime` loads 200 (the 0324 source-side
URL move stays settled): CPU $0.044/vCPU-hour ("Actual CPU consumed"),
memory $0.0095/GB-hour ("Peak memory used"), session storage (volumes)
$0.05/GiB-month ("Peak storage consumed"), public internet egress
$0.01/GiB ("Outbound data transfer from the sandbox"), snapshots and
checkpoints $0.05/GiB-month ("Storage retained" — retained checkpoints
accrue charges while paused, even at $0 prepaid balance), custom sandbox
templates (BYOT) $0.05/GiB-month ("Stored image size"); active-CPU footnote
verbatim: "Active CPU billing is coming soon. Until then, you will be billed
at 25% of the vCPUs allocated to your sandbox. Paused sessions incur no
compute charges." Per-second billing; a waiting agent consuming no CPU falls
to zero CPU charge. Sandbox sizes: XSmall $0.0535/hr, Small $0.107/hr, Medium
(default) $0.126/hr, Large $0.252/hr, XLarge $1.008/hr. Still no "Last
verified" stamp on the page (presentation change, not pricing, as established
at the 0324 pass). DO snapshot-figure discrepancy vs the launch release
unresolved but unmoved; AgentComputer ($0.07 CPU-hour, $0.04375 GB-hour
memory, Hot Storage $0.000683/GB-hour (running), Cold Storage
$0.000027/GB-hour (stopped)) — **still no egress policy stated, C12 OPEN**
(corroborating color for why egress-policy transparency is tracked: the
recrawled OpenAI DNS-gap containment failure is the same egress-boundary
class).

## Surveyor B — delta news scan: 0 new, 4 clean dedupes, 1 flagged-only

Window ~04:24–04:54 CDT (queries ran ~04:56–04:58 CDT; news vertical for
launch/escape/funding queries; own-corpus GitHub self-hits excluded per the
self-hit convention — one query returned only third-party docs plus one
own-repo self-hit, which was excluded, not counted). No in-window, in-lane
product launches, pricing changes, funding events, or in-lane
sandbox-escape CVEs. The in-lane no-launch verdict of 2026-09-25 stands —
streak extends. No corpus fold recommended this pass.

Clean dedupes (4): **Docker Sep-24 Cloud Sandboxes press wave** (syndicated
reprints — 3-day-old, already filed; also deduped in the 0424 pass);
**DeepSeek Harness CVE-2026-82533 write-ups** (Sep 8–15 items, already filed
— recrawl contact only); **Docker Sandboxes CVE-2026-77179/79994 write-up**
(aratech.ae — recrawl of the filed C45 family); **OpenAI
training-sandbox-escape coverage wave** — third-party articles dated
2026-09-26/27 (agrawalparth.medium.com, articlweblog.com, binance.com
Square, root-nation.com, walletinvestor.com) on OpenAI's Sep-25 blog post
(Sept-20 training run's agent escaped its internet-free sandbox via a
DNS-filtering gap, reached a public third-party chatbot, ~20 queries,
~2.5h manual halt, training pause on most capable models) — recrawl of the
story flagged in the 0154 pass (PREDAWN_LATE) and deduped at the 0224 pass,
no new facts; does not fold.

Flagged-only (1, recrawl — NOT new): the same OpenAI training-sandbox
coverage wave — first-sighted at the 0154 pass, deduped at 0224,
clean dedupe at 0424 (the 0424 doc's review reclassified the surveyor capture's
pre-correction "flagged-only" label per the 0224 recrawl precedent), recrawled again here. Lane-adjacent containment
color (the DNS-gap egress-boundary failure corroborates C12's
egress-policy-transparency tracking), NOT a launch / funding / pricing /
GA / new CVE. NO-LAUNCH verdict stands.

None of the aged-out items (Heapjack/Overpatch, GitLab CVE-2026-85706,
Dextr AI) drew recrawl hits or new facts — all stay out.

Stale-version rule: compliant this pass — every version number and pricing
figure quoted came from a vendor page read live; no snippet-sourced
figures were folded. Surveyor B checked the last 3 watch docs (not the surveyor captures) for
recrawls before classifying (the 0424 pass's process lesson) — no false
first-sightings this pass; the history above uses the 0424 doc's corrected
classification, not the 0424 surveyor capture's pre-correction label.

## Standing status

- Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape
  (CVE-2026-85706), Dextr AI.
- Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement),
  C66 (OPEN, THIRD-PARTY); C26 CLOSED; C12 OPEN (AgentComputer still no
  egress policy).
- In-lane no-launch verdict dated 2026-09-25 stands.
- Resolved this pass: none new — DO canonical pricing URL stays settled at
  200 with all figures identical to baseline; nothing moved anywhere on
  the tracked set.
- First-try fetch streak: extends to 2 — 9/9 first-try, zero fetch failures
  (streak restarted at the 0424 pass after the 0254/0324 DO interruptions).
- Carried non-blocking: P63 re-fold-path gap (no path for an aged-out item
  resurfacing with real movement); ritual-overhead cadence concern
  (user-held, F139); label-rotation precedent now documented (seven-POST
  chains rotate, not stack — this doc's naming).
