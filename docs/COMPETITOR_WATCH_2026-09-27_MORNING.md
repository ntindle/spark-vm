# Competitor watch — 2026-09-27 (morning)

Two-surveyor pass (both read-only subagents, dispatched in parallel),
delta-only against the early-morning pass (#544, merged as `b593e66`): (A)
fast-mover + pricing re-verification vs the ~04:56 CDT (2026-09-27) baseline
(vendor reads ~05:55 CDT 2026-09-27), (B) delta news scan ~04:54–05:54 CDT
(~60-min delta window; queries ran ~05:55–05:56 CDT). Read-only, no logins,
no writes. Captures: `agent_notes/surveyor-a-20260927-0554.md`,
`agent_notes/surveyor-b-20260927-0554.md` (under `hidden_files`).

Naming-hygiene note: this pass continues the label rotation the 0454 pass
started — the six-deep POST_ pre-dawn chain rotated to the `EARLY_MORNING`
series, and this pass rotates the series forward to `MORNING` (chains
rotate, not stack). If a third same-day pass lands, it rotates again (a
later morning label) rather than reusing or POST_-stacking.

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: the already-aged-out trio —
Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI —
drew zero recrawl hits (quiet) — all remain out; no new age-outs this
pass (C37/C55/C57/C58 vendor re-verified; C62 drew no in-window contact —
P63 quiet pass 1; C66 drew no in-window contact — P63 quiet pass 2, after
the quiet pass counted at 0454; neither reaches the 3-pass threshold).
Carried P63 gap: still no re-fold path for an
aged-out item that resurfaces with real movement (follow-up proposal from
the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~05:55 CDT; every page loaded on first
attempt — 9/9 first-try, zero fetch failures (the all-first-try streak
restarted at the 0424 pass extends to **3 passes**). Every verified figure
matches the ~04:56 CDT baseline on substance. No corpus fold (C32
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
   per P49 (daily cadence — next due 2026-09-28).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE + "$100 one-time usage credit", Pro $150/month,
per-second $0.000014/0.000028/0.000056/0.000084/0.000112 for 1/2/4/6/8
vCPU); boat.dev ($0.018/0.036/0.072/0.200 per hour — small/default/large/
xlarge; "A stopped sandbox costs nothing"; 25 free trial hours;
$20/$100/$500/$2000/mo — canonical `docs.boat.dev/pricing`); TermSquad
($9 (2 vCPU/4 GB/40 GB) / $19 (4/8/75) / $29 (6/12/100) / $49 (8/24/200);
BYO-AI FAQ intact); DigitalOcean Managed Agents — canonical
`digitalocean.com/pricing/harness-runtime` loads 200 (the 0324 source-side
URL move stays settled): CPU $0.044/vCPU-hour, memory $0.0095/GB-hour,
session storage (volumes) $0.05/GiB-month, sizes
$0.0535/$0.107/$0.126/$0.252/$1.008 per hr, egress $0.01/GiB,
snapshots/checkpoints $0.05/GiB-month, BYOT $0.05/GiB-month, 25%-of-allocated
active-CPU footnote intact — still no "Last verified" stamp;
AgentComputer.ai ($0.07/CPU-hour, $0.04375/GB-hour, Hot Storage
$0.000683/GB-hour, Cold Storage $0.000027/GB-hour; no egress-policy line —
C12 stays OPEN).

## Surveyor B — delta news scan: 0 new / 4 clean dedupes / 1 flagged-only

Queries ran ~05:55–05:56 CDT; the corpus was checked for recrawls before
classification (the 0424 pass's process lesson — no false first-sightings).
No in-window, in-lane product launches, pricing changes, funding events,
or in-lane sandbox-escape CVEs. Own-corpus self-hits excluded.

**Clean dedupes (4):**
1. Docker Sep-24 Cloud Sandboxes press wave — Forkast recrawl (dated
   2026-09-25 8:18 PM UTC) — same launch already filed; the 0454 pass
   deduped syndicated reprints of this wave. Filed, recrawl contact only,
   pre-window.
2. OpenAI DevDay persistent-agent "O" leak rumor (AI Engineering / Medium,
   ~21:25 CDT Sep 26) — already filed in the pre-dawn chain and recrawled
   as out-of-window, third-party-only; unconfirmed rumor, no new facts.
   Distinct from C62 (the offline-training-sandbox escape incident). NOT a
   launch; the no-launch verdict stands.
3. DigitalOcean Managed Agents launch — Marketwire/TradingView syndicated
   press-release reprints ("Last Updated: 10 hours ago") — the Sep-22/23
   launch, pricing already vendor-verified in the tracked set. Filed,
   recrawl contact only, no new facts.
4. CVE-2026-80521 (AF_UNIX UAF container-escape, DepthFirst) — third-party
   write-ups (tech-insider.org, Cyber Recaps Sep 23–24 digests) — already
   filed in `COMPETITOR_WATCH_2026-09-26_MID_AFTERNOON.md` and
   `COMPETITOR_WATCH_2026-09-27_PREDAWN.md`; recrawl contact only, no new
   facts, pre-window.

**Flagged-only (1), NOT folded:**
- CVE-2026-43503 "DirtyClone" — a new Kubernetes container-escape PoC
  surfaced ~Sep 25 (raesene/vuln_pocs; Rafael David Tinoco). The CVE itself
  is a June 2026 disclosure (CVSS 8.8, page-cache corruption via netfilter
  TEE / `__pskb_copy_fclone()`); the ~Sep-25 PoC is also pre-window.
  Lane-adjacent kernel-escape color (container-sandbox relevance: Docker's
  default seccomp blocks `unshare(CLONE_NEWUSER)`; stock K8s has no default
  seccomp, so the K8s chain works) — but not a new CVE and not a
  vendor/product story. Not folded; carried as a near-miss candidate only
  if a future pass sees fresh movement. (Not eligible for P63 — never
  filed.)

**Also surfaced, not counted (old or out-of-lane):** Daytona $24M Series A
(Feb 2026 — filed history); Meta Muse / "Muse Secure VM" (Sep 9 —
consumer agent product, pre-window); TermSquad always-on cloud computer
launch (Sep 15 — pre-window, tracked-set vendor); Baseten acquires Blaxel
(Sep 14 — pre-window); E2B pricing lifecycle blog + OpenAI Agents API
pricing comparison — third-party pricing recaps, no vendor-page changes,
no fold (C32 precedent); aged-out trio zero hits.

**Standing verdicts:**
- No corpus fold this pass (C32 precedent). **No new C-numbers.**
- In-lane no-launch verdict dated 2026-09-25 stands — streak extends.
- Stale-version rule compliant.
- Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement —
  quiet pass 1), C66 (OPEN, THIRD-PARTY — quiet pass 2); C26 CLOSED; C12
  OPEN (AgentComputer still no egress policy).
- DO snapshot-figure discrepancy unresolved but unmoved.
- Carried non-blocking: P63 re-fold-path gap (no path for an aged-out item
  resurfacing with real movement); ritual-overhead cadence concern
  (user-held, F139); label-rotation precedent now documented (six-deep POST_
  chains rotate, not stack — this doc's naming; MORNING is the rotation's
  second series label after EARLY_MORNING).
