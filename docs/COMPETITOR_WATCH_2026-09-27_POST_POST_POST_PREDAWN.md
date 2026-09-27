# Competitor watch — 2026-09-27 (post-post-post-pre-dawn)

Two-surveyor pass, delta-only against the post-post-pre-dawn pass (#533,
merged as `1c3c961`): (A) fast-mover + pricing re-verification vs the
~02:25–02:26 CDT (2026-09-27) baseline (vendor reads ~02:55–02:56 CDT
2026-09-27), (B) delta news scan ~02:26–02:57 CDT (~31-min delta window).
Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260927-0254.md`,
`agent_notes/surveyor-b-20260927-0254.md` (under `hidden_files`).
Suffix `_POST_POST_POST_PREDAWN` admitted per the POST_ same-day-repeat
precedent — the fourth entry in the 09-27 pre-dawn series (PREDAWN →
POST_PREDAWN → POST_POST_PREDAWN → POST_POST_POST_PREDAWN; the sibling 0154
slot's `PREDAWN_LATE` is a series-breaker, not part of this chain).

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: the already-aged-out trio —
Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI —
remain out: GitLab CVE-2026-85706 and Dextr AI drew zero recrawl hits
(quiet); Heapjack/Overpatch drew recrawl hits of the already-disclosed
facts (Codex-escape write-ups, same fixed facts, no new info) — recrawl
contact, no movement, stays aged out. No new age-outs this pass. Carried
P63 gap: still no re-fold path for an aged-out item that resurfaces with
real movement (filed as a follow-up proposal at the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

Eight vendor pages re-read live ~02:55–02:56 CDT; the ninth (DigitalOcean
Managed Agents pricing) failed its first fetch at the source and was
re-read live ~02:57 CDT by the worker (retry evidence in
`hidden_files/agent_notes/surveyor-a-retry-do-20260927-0254.md`) — the
all-first-try streak ends at 9 passes.
Every figure matches the 02:25–02:26 CDT baseline on substance.

1. **Daytona changelog** (`daytona.io/changelog`) — newest still **SEP 26 2026 /
   V0.218.0** ("KVM sandbox parameter and CLI WorkOS application"); SEP 25
   V0.217.0, SEP 24 V0.216.1 + V0.216.2, SEP 23 V0.216.0 all match baseline.
2. **Docker Sandboxes release notes**
   (`docs.docker.com/ai/sandboxes/release-notes/`) — newest dated heading
   still **2026-09-22**; next 2026-09-21 (v3 kits), then 2026-09-15.
3. **Microsandbox releases** — newest still **v0.7.3** (#1646;
   `github.com/superradcompany/microsandbox/releases`).
4. **Vercel changelog (Sandbox lane)** — newest date header still
   **25 September**; **no 26-Sep entries in any lane**. Newest Sandbox-lane
   entries: 25 Sep "memory observability"; 23 Sep "Drives public beta".
   Drives not re-checked per P49 (daily cadence).

Pricing parity — **all VENDOR-VERIFIED NO-CHANGE** (vendor-page reads this
pass): E2B (Hobby FREE + "$100 one-time usage credit", Pro $150/month,
per-second $0.000014/0.000028/0.000056/0.000084/0.000112 for 1/2/4/6/8
vCPU); boat.dev ($0.018/0.036/0.072/0.200 per hour — small/default/large/
xlarge; "A stopped sandbox costs nothing"; 25 free trial hours;
$20/$100/$500/$2000 tiers — canonical `docs.boat.dev/pricing`; `boat.dev/
pricing` still 404s); TermSquad ($9 (2 vCPU/4 GB/40 GB) / $19 (4/8/75) /
$29 (6/12/100) / $49 (8/24/200); BYO-AI FAQ intact); DigitalOcean Managed
Agents ("Last verified 22 Sep 2026" stamp unchanged; $0.044/vCPU-hour CPU,
$0.0095/GB-hour peak memory, session storage $0.05/GiB-month, egress
$0.01/GiB, snapshots/checkpoints $0.05/GiB-month, custom templates
$0.05/GiB-month; active-CPU footnote intact; the standing snapshot-figure
discrepancy vs the launch release is unresolved but unmoved); AgentComputer
($0.07 CPU-hour, $0.04375 GB-hour memory, Hot Storage $0.000683/GB-hour
(running), Cold Storage $0.000027/GB-hour (stopped) — **still no egress
policy stated, C12 OPEN**).

## Surveyor B — delta news scan: 0 new, 10 clean dedupes, 10 flagged-only

Quiet ~02:26–02:57 CDT window. No in-window, in-lane product launches,
pricing changes, funding events, or in-lane sandbox-escape CVEs. The
in-lane no-launch verdict of 2026-09-25 stands — streak extends. No corpus
fold recommended this pass.

Clean dedupes (10): **Docker Sep-24 Cloud Sandboxes press wave**;
**Modal $15B raise talks**; **DeepSeek Harness CVE-2026-82533 write-ups**;
**Docker Sandboxes CVE-2026-77179/79994**; **Codex Heapjack/Overpatch
disclosures**; Runloop Devboxes PR reprint; **Upstash 15-provider
comparison**; **Boxd $2M pre-seed**; Go.AI $85M; Nscale $3.36B.

Flagged-only (new to the scan but failing lane/window bars — NOT filed):

- **Sandlock release** (Multikernel, LinkedIn "shipped today" — borderline
  lane: process-based local sandbox, no VM; snippet-only; release-bump,
  not a launch; new to the corpus but not filed).
- **CVE-2026-47686** (vm2 sandbox-escape RCE, 9.9 — lane-drift: Node.js
  library, not agent-VM compute; third-party only).
- **Island $400M Series F at $6.4B** (Reuters, Sep 24 — out-of-window +
  adjacent: browser/agent control-plane security, not sandbox compute).
- **PicoJool $27.5M Series A** (Sep 24 — out-of-window + lane-drift:
  optical interconnect).
- **DigitalOcean Managed Agents third-party write-ups** (subagentic.ai,
  explainx.ai — out-of-window recrawls of the filed Sep 22 preview).
- **OpenAI "O" DevDay rumor recrawl** (out-of-window, third-party-only,
  adjacent-not-in-lane; already flagged in the 0224 pass).
- **Daytona "Agent-Agnostic Infrastructure" PR reprints** (3047 days old —
  stale recrawls).
- **Daytona $24M Series A recrawls** (Feb 2026 — out-of-window).
- **Nova "Daytona vs E2B" provider-decision doc** (third-party +
  out-of-window; watch color at best).
- **vercel/sandbox CHANGELOG snippet** (`@vercel/sandbox@3.4.0` —
  snippet-sourced version only; superseded by Surveyor A's live Vercel
  changelog read — no 26-Sep entries in any lane).

Stale-version rule: compliant this pass — every version number quoted came
from a vendor page read live; the two snippet-sourced versions (Sandlock,
vercel/sandbox@3.4.0) were explicitly not folded.

## Standing status

- Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape
  (CVE-2026-85706), Dextr AI.
- Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement),
  C66 (OPEN, THIRD-PARTY); C26 CLOSED.
- In-lane no-launch verdict dated 2026-09-25 stands.
- First-try fetch streak: ended at 9 passes (DO pricing failed once,
  re-verified on worker retry ~02:57 CDT — evidence note
  `hidden_files/agent_notes/surveyor-a-retry-do-20260927-0254.md`).
