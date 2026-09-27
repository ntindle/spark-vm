# Competitor watch — 2026-09-27 (post-post-pre-dawn)

Two-surveyor pass, delta-only against the pre-dawn-late pass (#531, slot
0154, PR open at write time): (A) fast-mover + pricing re-verification vs
the ~01:57–01:58 CDT (2026-09-27) baseline (vendor reads ~02:25–02:26 CDT
2026-09-27), (B) delta news scan ~01:40–02:26 CDT (~46-min delta window).
Read-only, no logins, no writes. Captures:
`agent_notes/surveyor-a/b-20260927-0224.md` (under `hidden_files`).
Suffix `_POST_POST_PREDAWN` admitted per the POST_ same-day-repeat
precedent — the third entry in the 09-27 pre-dawn series (PREDAWN → POST_PREDAWN
→ POST_POST_PREDAWN; the sibling 0154 slot's `PREDAWN_LATE` is a series-breaker,
not part of this chain).

**Corpus aging pipeline — adopted this pass (15th-rotation-audit proposal
P63):** N consecutive quiet passes (default 3) → age-out with a mandatory
one-notice line in the pass doc naming the aged item, so the fold stays
auditable; no silent drops. A quiet pass = a pass with no new information,
movement, or recrawl-mention of the item; vendor re-verification contact
counts as contact, not a quiet pass. This pass applies the rule: the
already-aged-out trio — Heapjack/Overpatch, GitLab proxy escape
(CVE-2026-85706), Dextr AI — are all still quiet (no recrawl hits in either
surveyor's scan); the notice line under "Standing status" below keeps the
fold auditable. No new age-outs this pass: every carried item had contact
(C37/C55/C57/C58 vendor re-verified; C62/C66 recrawled).

## Surveyor A — fast movers + pricing: 9/9 VENDOR-VERIFIED NO-CHANGE

All 9 vendor pages re-read live ~02:25–02:26 CDT; every page loaded on first
attempt — all-first-try streak extends to 9, zero retries, zero fetch failures.
(The canonical `docs.boat.dev/pricing` URL lesson from the 0124 pass carries
forward — no 404 artifact this pass.)

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
$20/$100/$500/$2000 tiers); TermSquad ($9 (2 vCPU/4 GB/40 GB) / $19 (4/8/75)
/ $29 (6/12/100) / $49 (8/24/200); BYO-AI FAQ intact); DigitalOcean Managed
Agents ("Last verified 22 Sep 2026" stamp unchanged; $0.044/vCPU-hour CPU,
$0.0095/GB-hour peak memory, session storage $0.05/GiB-month, egress
$0.01/GiB, snapshots/checkpoints $0.05/GiB-month, custom templates
$0.05/GiB-month; active-CPU footnote intact; the standing snapshot-figure
discrepancy vs the launch release is unresolved but unmoved); AgentComputer
($0.07 CPU-hour, $0.04375 GB-hour memory, Hot Storage $0.000683/GB-hour
(running), Cold Storage $0.000027/GB-hour (stopped) — **still no egress
policy stated, C12 OPEN**).

## Surveyor B — delta news scan: 0 new, 10 clean dedupes, 14 flagged-only

Quiet ~01:40–02:26 CDT window. No in-window, in-lane product launches,
pricing changes, funding events, or in-lane sandbox-escape CVEs. The
in-lane no-launch verdict of 2026-09-25 stands — streak extends. No corpus
fold recommended this pass.

Clean dedupes (10): **Docker Sep-24 Cloud Sandboxes press wave** (adtmag,
The Register, syndicated reprints); **Modal $15B raise talks** (Sep 23/26);
**DeepSeek Harness CVE-2026-82533 write-ups**; **Docker Sandboxes
CVE-2026-77179/79994**; **Codex sandbox-escape disclosures**; Encore×E2B
blog; FastGPT v4.16.0 sandbox guidance; **Upstash 15-provider comparison**;
**Boxd $2M pre-seed**; OpenAI training-sandbox-escape press (already
flagged in the 0154 pass — recrawl).

Flagged-only (new to the scan but failing lane/window bars — NOT filed):

- **OpenAI persistent agent "O" at DevDay** (Medium rumor ~19:25 CDT Sep 26
  — out-of-window, third-party-only, adjacent-not-in-lane).
- **Daytona v0.171.0 article** (stale recrawl of an older version;
  V0.218.0 already on file — no version quoted from the snippet; stale-version
  rule compliant).
- **Modal $2.5B-valuation / $355M-Series-C recrawls** (Feb/May 2026 items).
- **Runloop Devboxes PR reprint** (3047 days old).
- **Nscale $3.36B** (out-of-window, lane-drift).
- **Go.AI $85M** (Sep 22 — out-of-window, lane-drift).
- **Raindrop $50M** (lane-drift).
- **Agent-security / funding trackers** (directory/editorial, no product move).
- **Three older Vercel-Sandbox commentary pieces** (pre-window recrawls).

Recrawl notes: own-corpus COMPETITOR_WATCH docs dominated several result
sets (self-hits, not reportable — surveyor B read the 0154 capture first,
kept self-hits out of the dedupe list). None of the aged-out items
(Heapjack/Overpatch, GitLab CVE-2026-85706, Dextr AI) appeared.

Stale-version rule: compliant this pass — every version number quoted came
from a vendor page read live; the one snippet-sourced version (Daytona
v0.171.0) was explicitly not folded.

## Standing status

- **In-lane no-launch verdict (2026-09-25): stands — streak extends.**
- **No new C-numbers this pass.** No corpus fold.
- Aged out (staying out — P63 mandatory one-notice line): Heapjack/Overpatch,
  GitLab proxy escape (CVE-2026-85706), Dextr AI — all three still quiet
  (no recrawl hits in either surveyor's scan); no new age-outs.
- Carried: C37, C55, C57, C58 (pricing vendor-verified), C62 (no movement),
  C66 (OPEN, THIRD-PARTY); C26 CLOSED; C12 OPEN (AgentComputer still no
  egress policy).
- Timestamps: all surveyor reads this pass carry truthful local times in
  the capture files (integrity-corrective from the 0124 pass — no
  fabrication).
