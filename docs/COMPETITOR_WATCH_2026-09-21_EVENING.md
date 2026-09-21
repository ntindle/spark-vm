# Competitor watch — evening pass, 2026-09-21

Delta-only update against the afternoon baseline
(`docs/COMPETITOR_WATCH_2026-09-21_AFTERNOON.md`). Survey window
**2026-09-21 ~14:54 → ~17:54 CDT**; reads ~17:55–18:10 CDT, two
read-only surveyors (read-only fetches and searches; no logins, no
writes).

Summary: **quiet window — zero in-window deltas** across the full
tracked set (no launches, acquisitions, pricing changes, releases, or
partner moves). One pre-window miss surfaced by this pass:
**h-sandbox / "Harakiri Sandbox"**, an open-source self-hosted sandbox
control plane that launched publicly on 2026-09-09 and was absent from
the baseline — filed as watch item **C18** in BACKLOG.md. Raw captures
in the loop's `agent_notes/` (workspace-only), not the repo.

Conventions: **VERIFIED** = read on a vendor's own page, doc, or repo
this run (link inline). **THIRD-PARTY** = reported by press/third-party
sources. **INFERRED** = my characterization, labeled as such.

## 1. The tracked set — quiet since the 2026-09-21 afternoon baseline

No in-window change detected across the full tracked set:

- **Microsandbox** — top release still **v0.7.1** (**VERIFIED**:
  https://github.com/superradcompany/microsandbox/releases, ~18:00).
  No newer tag exists; the tag page renders no release timestamp, but
  v0.7.1 was already the baseline's top, so it predates or equals the
  baseline regardless — no in-window delta either way.
- **Docker Sandboxes** — release notes still top out at **0.43.0**
  (2026-09-15 block); no 0.44 (**VERIFIED**:
  https://docs.docker.com/ai/sandboxes/release-notes/, ~18:01). The
  ~weekly Sep-7 → Sep-15 cadence keeps 0.44 likely imminent — watch
  stays tight.
- **Daytona** — changelog still tops at **SEP 15 2026, v0.214.0**; no
  in-window entries (**VERIFIED**: https://www.daytona.io/changelog,
  ~18:01).
- **E2B** — no observed pricing or suspend/resume semantic change
  (**UNVERIFIABLE for the exact default rate this pass**: e2b.dev/pricing
  now renders a JS workload estimator instead of a static table —
  vCPU rows show 2 vCPU $0.000028/s, 4 vCPU $0.000056/s, 8 vCPU
  $0.000112/s with RAM cost additive and not visible in text
  extraction, so the 4 vCPU/8 GB default rate cannot be reconstructed
  from this fetch; no suspend/resume semantic language found on the
  page, sessions "up to 24 hours" on Pro). boat.dev's own comparison
  table (read today) still lists E2B **$0.331/h** default —
  **INFERRED** corroboration of no price move.
- **boat.dev** — rate card re-verified unchanged (**VERIFIED**:
  https://docs.boat.dev/pricing, ~18:02): small **$0.018/h**, default
  **$0.036/h**, large **$0.072/h**, xlarge **$0.200/h** ($100+ plan +
  operator capacity allocation), stopped = free, 25 free-hour trial,
  concurrency/starts table unchanged; the twelve-provider comparison
  table holds (E2B/Daytona/Blaxel **$0.331/h**, Modal **$0.476/h**,
  Vercel Sandbox **$0.682/h** at their own list prices).
- **TermSquad** — pricing tiers still $9/$19/$29/$49; no pricing or
  product change; latest coverage remains the Sep 15 launch press
  (**VERIFIED**: https://termsquad.com/, ~18:03).
- **WSO2 Agent Manager** — GA recaps still propagating through
  syndication (Stackademic recap plus IT News Africa Sep 20,
  menews247, dxbhappenings, valuespectrum, systemsdigest — all the same
  GA announcement, no new product move). Sep 29 webinar stays the
  trigger (C10) (**VERIFIED**: no delta).
- **Baseten / Blaxel** — Sep 10 acquisition (pre-window); nothing
  in-window. "Perpetual sandbox + model serving in one org" stays the
  sharpest commercial benchmark (C11 stands) (**VERIFIED**: no delta).
- **OpenAI Agents API sandbox partners** — still nine (Blaxel,
  Cloudflare, Daytona, DigitalOcean, E2B, Modal, Oracle, Runloop,
  Vercel) across official docs; no additions or departures (C9 stands)
  (**VERIFIED**; one independent blog's 7-item list is its own SDK-client
  subset, not an official change).
- **FastGPT** — v4.16.0 E2B-removal press-release syndication only
  (latest crawl Sep 20, pre-window); the Sep 14 consolidated guidance
  (E2B configs deprecated → migrate to OpenSandbox or Sealos Devbox)
  stands. No in-window follow-up release (**VERIFIED**: no delta).
- **Cloudflare × Cursor** — Sep 2 announcement only; no new moves
  (**VERIFIED**).
- **New entrants** — none in-window. One pre-window miss (see §2).

## 2. C18 — h-sandbox / "Harakiri Sandbox" (pre-window, missed by baseline)

**VERIFIED** (https://github.com/nabilblk/h-sandbox, read ~18:05):
self-hosted sandbox control plane for agent apps — HTTP API, TypeScript
SDK, CLI, dashboard; environments/templates/workspaces; a credential
vault with host-bound egress bindings and fake-env injection; and
**OpenSandbox as the execution adapter**. Public source launch was
**2026-09-09** (docs/release-notes/2026-09-09-public-launch.md), docs
last updated ~Sep 14 — both pre-window, so this is not an in-window
delta, but the baseline never listed it. Filed as watch item **C18**
in BACKLOG.md.

**INFERRED** — why it matters for spark-vm: this is the first
open-source competitor in the tracked set that pairs a control plane
with an egress-bound credential vault and a pluggable execution adapter
— the closest open-source shape to spark-vm's own swapd-proxy posture
plus the harness execution model. It belongs in the next corpus
consolidation pass (the credential-vault + host-bound-egress design is
directly comparable to spark-vm's secrets-posture doc and the R6 corpus
work), and its OpenSandbox adapter choice is data for the H4
provider-adapter discussions. No urgency: pre-window launch, docs stable
since Sep 14.

## 3. Standing items

- **C18** (h-sandbox watchlist add): **OPEN** — filed this pass;
  next corpus consolidation should evaluate it against the
  secrets-posture corpus and the H4 adapter question.
- **C12** (AgentComputer egress): stands, but **refined this pass
  (THIRD-PARTY)**: a third-party tools-directory review (dated
  2026-09-03, https://github.com/bradvin/agentfirst.directory —
  read this pass) confirms AgentComputer as a real product —
  persistent Ubuntu VMs for Claude/Codex agents, pay-as-you-go
  CPU/memory/hot/cold storage pricing at
  https://www.agentcomputer.ai/pricing — while finding no public
  network-egress policy either. The "unverifiable" posture is now a
  stronger negative result (a real product with real pricing and no
  stated egress policy), not a mystery-company one.
- **C14** (#47 resume-latency target): still **OPEN** — needs a measured
  boat.dev/provider resume baseline; live-API measurement awaits the
  operator per-run spend-cap decision (no movement).
- Carrying forward unchanged: C9 (OpenAI partners), C10 (WSO2 — Sep 29
  webinar is the next trigger), C11 (Baseten–Blaxel integration), C17
  (CLOSED — boat.dev table verified current, xlarge caveat stands as
  current vendor policy).

---

*Corpus note:* per the reach-back policy this pass is delta-only; no
corpus record changed. The two surveyor captures are archived verbatim
in the loop's `agent_notes/` (workspace-only), not the repo.
