# Competitor watch — 2026-09-27 (post-post-post-post-post-pre-dawn)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the post-post-post-post-pre-dawn pass (#541, merged as
`4c6c2ed`): (A) fast-mover + pricing re-verification vs the ~03:24–03:30
CDT (2026-09-27) baseline (vendor reads ~04:25–04:27 CDT 2026-09-27), (B)
delta news scan ~03:30–04:24 CDT (~54-min delta window; queries ran
~04:25–04:26 CDT). Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260927-0424.md`,
`agent_notes/surveyor-b-20260927-0424.md` (under `hidden_files`).
Suffix `_POST_POST_POST_POST_POST_PREDAWN` admitted per the POST_
same-day-repeat precedent — the sixth entry in the 09-27 pre-dawn series
(PREDAWN → POST_PREDAWN → POST_POST_PREDAWN → POST_POST_POST_PREDAWN →
POST_POST_POST_POST_PREDAWN → this doc; the sibling 0154 slot's
`PREDAWN_LATE` is a series-breaker, not part of this chain). Naming-hygiene
note: the chain is now six deep; a seventh same-day pass should rotate the
label (e.g. to an evening series) rather than stack a seventh POST_.

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: the already-aged-out trio —
Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI —
drew zero recrawl hits (quiet) — all remain out; no new age-outs this
pass (every carried item had contact: C37/C55/C57/C58 vendor re-verified;
C62/C66 recrawled). Carried P63 gap: still no re-fold path for an
aged-out item that resurfaces with real movement (follow-up proposal from
the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~04:25–04:27 CDT; every page loaded on first
attempt — 9/9 first-try, zero fetch failures (restarts the all-first-try
streak — the prior 9-pass streak ended at the 0254 pass when DO's pricing
page failed once, and the 0324 pass was 8/9 on the DO URL move; the DO
source-side 404 was already resolved at the prior pass's recovery step and
the new canonical URL loaded 200 this pass). Every verified figure
matches the ~03:24–03:30 CDT baseline on substance. No corpus fold (C32
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
`digitalocean.com/pricing/harness-runtime` loads 200 this pass (no upstream
404): CPU $0.044/vCPU-hour ("Actual CPU consumed"), memory $0.0095/GB-hour
("Peak memory used"), session storage (volumes) $0.05/GiB-month ("Peak
storage consumed"), public internet egress $0.01/GiB ("Outbound data
transfer from the sandbox"), snapshots and checkpoints $0.05/GiB-month
("Storage retained" — retained checkpoints accrue charges while paused,
even at $0 prepaid balance), custom sandbox templates (BYOT) $0.05/
GiB-month ("Stored image size"); active-CPU footnote verbatim: "Active CPU
billing is coming soon. Until then, you will be billed at 25% of the vCPUs
allocated to your sandbox. Paused sessions incur no compute charges."
Per-second billing; a waiting agent consuming no CPU falls to zero CPU
charge. Sandbox sizes: XSmall $0.0535/hr, Small $0.107/hr, Medium (default)
$0.126/hr, Large $0.252/hr, XLarge $1.008/hr. Still no "Last verified"
stamp on the page (presentation change, not pricing, as established at the
0324 pass). DO snapshot-figure discrepancy vs the launch release unresolved
but unmoved; AgentComputer ($0.07 CPU-hour, $0.04375 GB-hour memory, Hot
Storage $0.000683/GB-hour (running), Cold Storage $0.000027/GB-hour
(stopped) — **still no egress policy stated, C12 OPEN** (corroborating
color for why egress-policy transparency is tracked: the recrawled OpenAI
DNS-gap containment failure is the same egress-boundary class).

## Surveyor B — delta news scan: 0 new, 4 clean dedupes, 0 flagged-only

Window ~03:30–04:24 CDT (queries ran ~04:25–04:26 CDT; news vertical for
launch/escape queries, general web for vendor moves; own-corpus GitHub
self-hits excluded per the self-hit convention — one query returned only
self-hits). No in-window, in-lane product launches, pricing changes,
funding events, or in-lane sandbox-escape CVEs. The in-lane no-launch
verdict of 2026-09-25 stands — streak extends. No corpus fold recommended
this pass.

Clean dedupes (4): **Docker Sep-24 Cloud Sandboxes press wave** (syndicated
reprints — 3-day-old, already filed); **DeepSeek Harness CVE-2026-82533
write-ups** (Sep 8–15 items, already filed — recrawl contact only, incl. the
continuum-ai-corp orca-ai-incident-archive markdown, ~Sep 24, which repeats
the same disclosed timeline with no claimed exploitation); **Docker
Sandboxes CVE-2026-77179/79994 write-up** (aratech.ae — recrawl of the
filed C45 family); **OpenAI training-sandbox-escape coverage wave** —
third-party articles dated 2026-09-26/27 (articlweblog.com 09-27,
binance.com Square 09-26, walletinvestor.com and root-nation.com ~09-26
evening, agrawalparth.medium.com ~09-27 early) on OpenAI's Sep-25 blog
post (Sept-20 training run's agent escaped its internet-free sandbox via
a DNS-filtering gap, reached a public third-party chatbot, ~20 queries,
training did not auto-stop) — recrawl of the story already flagged in the
0154 pass (PREDAWN_LATE) and deduped at the 0224 pass, no new facts, all
articles pre-window; does not fold — lane-adjacent containment color,
NOT a launch / funding / pricing / GA / new CVE — and the NO-LAUNCH
verdict stands.

None of the aged-out items (Heapjack/Overpatch, GitLab CVE-2026-85706,
Dextr AI) drew recrawl hits or new facts — all stay out.

Stale-version rule: compliant this pass — every version number and pricing
figure quoted came from a vendor page read live; no snippet-sourced
figures were folded.

## Standing status

- Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape
  (CVE-2026-85706), Dextr AI.
- Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement),
  C66 (OPEN, THIRD-PARTY); C26 CLOSED.
- In-lane no-launch verdict dated 2026-09-25 stands.
- Resolved this pass: DO canonical pricing URL now loads 200 with no
  upstream 404 (the 0324 pass's source-side move is settled at
  `digitalocean.com/pricing/harness-runtime`); figures re-verified verbatim
  — all identical to baseline.
- First-try fetch streak: restarted at 1 this pass — 9/9 first-try, zero
  fetch failures (the prior all-first-try streak of 9 passes ended at the
  0254 pass; the 0324 pass was 8/9 on the DO URL move).
- Carried non-blocking: P63 re-fold-path gap (no path for an aged-out item
  resurfacing with real movement); ritual-overhead cadence concern
  (user-held, F139).
