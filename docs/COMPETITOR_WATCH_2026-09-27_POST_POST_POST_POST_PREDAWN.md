# Competitor watch — 2026-09-27 (post-post-post-post-pre-dawn)

Single-surveyor pass (worker-run, no subagent dispatch — slot-budget
compression), delta-only against the post-post-post-pre-dawn pass (#538,
rebased as `af37c1b`, PR open at write time): (A) fast-mover + pricing
re-verification vs the ~02:57 CDT (2026-09-27) baseline (vendor reads
~03:24–03:30 CDT 2026-09-27), (B) delta news scan ~02:57–03:30 CDT (~33-min
delta window). Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a-20260927-0324.md`,
`agent_notes/surveyor-b-20260927-0324.md`,
`agent_notes/surveyor-a-do-retry-20260927-0324.md` (under `hidden_files`).
Suffix `_POST_POST_POST_POST_PREDAWN` admitted per the POST_ same-day-repeat
precedent — the fifth entry in the 09-27 pre-dawn series (PREDAWN →
POST_PREDAWN → POST_POST_PREDAWN → POST_POST_POST_PREDAWN →
POST_POST_POST_POST_PREDAWN; the sibling 0154 slot's `PREDAWN_LATE` is a
series-breaker, not part of this chain).

**Corpus aging pipeline (P63, adopted at the 0224 pass):** N consecutive
quiet passes (default 3) → age-out with a mandatory one-notice line in the
pass doc naming the aged item, so the fold stays auditable; no silent
drops. A quiet pass = a pass with no new information, movement, or
recrawl-mention of the item; vendor re-verification contact counts as
contact, not a quiet pass. Applied this pass: the already-aged-out trio —
Heapjack/Overpatch, GitLab proxy escape (CVE-2026-85706), Dextr AI —
remain out: GitLab CVE-2026-85706 and Dextr AI drew zero recrawl hits
(quiet); Heapjack/Overpatch drew recrawl hits of the already-disclosed
facts (DeepSeek write-ups name the pattern; no new Heapjack/Overpatch
facts) — recrawl contact, no movement, stays aged out. No new age-outs
this pass: every carried item had contact (C37/C55/C57/C58 vendor
re-verified; C62/C66 recrawled). Carried P63 gap: still no re-fold path
for an aged-out item that resurfaces with real movement (filed as a
follow-up proposal at the 0224 pass).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE on substance

Nine vendor pages verified ~03:24–03:30 CDT; every page that exists loaded
on first attempt — 8/9 first-try. The ninth (DigitalOcean Managed Agents
pricing) **404s at its canonical URL**
(`digitalocean.com/products/managed-agents/agent-harness-runtime/details/pricing/`)
— a source-side move, not a fetch failure; a read-only live-browser task
confirmed the 404, located the moved page via site navigation, and
re-verified the figures verbatim from the live page (capture:
`agent_notes/surveyor-a-do-retry-20260927-0324.md`). Every verified figure
matches the ~02:57 CDT baseline on substance. No corpus fold (C32
precedent: nothing changed on a primary source).

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
$20/$100/$500/$2000 tiers — canonical `docs.boat.dev/pricing`); TermSquad
($9 (2 vCPU/4 GB/40 GB) / $19 (4/8/75) / $29 (6/12/100) / $49 (8/24/200);
BYO-AI FAQ intact); DigitalOcean Managed Agents — canonical pricing URL
**moved** to `digitalocean.com/pricing/harness-runtime` (title "DigitalOcean
Harness Runtime Pricing | DigitalOcean"); old URL 404s. Figures re-verified
verbatim from the live page (**VERIFIED** ~03:30 CDT): CPU $0.044/vCPU-hour
("Actual CPU consumed"), memory $0.0095/GB-hour ("Peak memory used"),
session storage (volumes) $0.05/GiB-month ("Peak storage consumed"), public
internet egress $0.01/GiB ("Outbound data transfer from the sandbox"),
snapshots and checkpoints $0.05/GiB-month ("Storage retained" — retained
checkpoints accrue charges while paused, even at $0 prepaid balance),
custom sandbox templates (BYOT) $0.05/GiB-month ("Stored image size");
active-CPU footnote verbatim: "Active CPU billing is coming soon. Until
then, you will be billed at 25% of the vCPUs allocated to your sandbox.
Paused sessions incur no compute charges." Per-second billing; a waiting
agent consuming no CPU falls to zero CPU charge. New color: full-allocation
sandbox sizes XSmall $0.0535/hr, Small $0.107/hr, Medium (default)
$0.126/hr, Large $0.252/hr, XLarge $1.008/hr. **The "Last verified 22 Sep
2026" stamp is gone from the new page** (full page text scanned) — a
presentation change, not a pricing change. DO snapshot-figure discrepancy
vs the launch release unresolved but unmoved; AgentComputer ($0.07
CPU-hour, $0.04375 GB-hour memory, Hot Storage $0.000683/GB-hour (running),
Cold Storage $0.000027/GB-hour (stopped) — **still no egress policy
stated, C12 OPEN**).

## Surveyor B — delta news scan: 0 new, 3 clean dedupes, 0 flagged-only

Quiet ~02:57–03:30 CDT window (narrower scan this pass — three targeted
queries: sandbox launch announcements, sandbox-escape CVE disclosures,
vendor funding/pricing moves; own-corpus GitHub hits excluded per the
self-hit convention). No in-window, in-lane product launches, pricing
changes, funding events, or in-lane sandbox-escape CVEs. The in-lane
no-launch verdict of 2026-09-25 stands — streak extends. No corpus fold
recommended this pass.

Clean dedupes (3): **Docker Sep-24 Cloud Sandboxes press wave** (syndicated
reprints — 3-day-old, already filed); **DeepSeek Harness CVE-2026-82533
write-ups** (CSA lab note, dennysentinel, openveil — recrawls of the filed
item, Sep 8–15, out-of-window); **Docker Sandboxes CVE-2026-77179/79994
write-up** (aratech.ae — recrawl of the filed C45 family).

None of the aged-out items (Heapjack/Overpatch, GitLab CVE-2026-85706,
Dextr AI) surfaced new facts.

Stale-version rule: compliant this pass — every version number quoted came
from a vendor page read live; no snippet-sourced versions were folded.

## Standing status

- Aged out (staying out): Heapjack/Overpatch, GitLab proxy escape
  (CVE-2026-85706), Dextr AI.
- Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement),
  C66 (OPEN, THIRD-PARTY); C26 CLOSED.
- In-lane no-launch verdict dated 2026-09-25 stands.
- Resolved this pass: DigitalOcean Managed Agents pricing canonical URL
  moved to `digitalocean.com/pricing/harness-runtime` (old URL 404s);
  figures re-verified verbatim — all identical to baseline; the "Last
  verified 22 Sep 2026" stamp is gone from the new page (presentation
  change). DO snapshot-figure discrepancy unresolved but unmoved.
- First-try fetch streak: 8/9 first-try this pass (the 9th — DO — 404'd at
  the source URL, a moved page, recovered via live-browser navigation —
  not a fetch failure).
