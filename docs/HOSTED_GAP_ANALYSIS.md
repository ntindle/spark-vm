# Hosted gap analysis: vision vs repo state

Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below is
**current state and work to do**, not promises. Statuses are pinned to the
repo as of this commit; open strategy PRs (#24–#26, #28–#30) are cited where
the vision they describe is already written down.

## The hosted vision in one paragraph

Another Muse discovers spark-vm (copy prompt / musebook / README),
signs up, links identity (their ed25519 keypair + the human approving a
fingerprint), gets a box provisioned on cloud infra, is handed short-lived
SSH certs, keeps secrets behind the swap proxy, approves sensitive actions
on their phone (push), and the human watches a signed audit log shipped to
the sentinel. Signup doc: PR #24 (`docs/HOSTED_SIGNUP_ONBOARDING.md`).
Positioning: PR #28 (`docs/POSITIONING.md`). Pricing thinking: PR #30
(`docs/PRICING_THINKING.md`).

Pipeline stages: **discover → signup → identity → provision → box →
sentinel → push → app.**

## Stage-by-stage: vision vs state

Legend for *gap class*: `[BLOCKER]` nothing exists and the stage cannot
function without it; `[PARTIAL]` exists but incomplete or wrong layer;
`[DESIGN]` design exists, implementation does not; `[POLICY]` needs an
operator (user) decision before code is the right move.

### 1. Discover — mostly there

| Vision | Current state |
|---|---|
| A Muse can find spark-vm and understand it in 30 seconds | README hero + copy prompt (PR #28), `docs/POSITIONING.md` copy bank (PR #28, open), `docs/RESEARCH_AGENT_SANDBOX_ADOPTION.md` (PR #25, open), `docs/COMPETITOR_ANALYSIS.md` (PR #26, open) |

No new gaps. Risk: the discover story references four open docs PRs — the
repo's front page leads with *shipped* components, so discover stays green
even if those stay unmerged. **Verdict: no gap.**

### 2. Signup — design done, implementation untouched, operator decisions outstanding

| Vision | Current state |
|---|---|
| Muse-facing signup: discover → enroll keypair → human approves fingerprint → account | Design doc PR #24 (open), §1–§11. No code: no signup endpoint, no enrollment flow, no email/magic-link sender |
| Abuse-resistant onboarding | Signup doc §11.7 names the risk (email-only invites spam VMs); operator decision outstanding — see NEEDS_USER.md "Abuse controls" |
| Identity linking UX | H3 follow-up in backlog: re-link email must show the new fingerprint prominently + be rate-limited |

**Gaps:**
- `[DESIGN]` H3 implementation not started; starts only after the operator
  decides tailnet shape + abuse controls (NEEDS_USER.md). Tracked: new
  item H9 below (identity service) + H15 (signup web UI).
- `[POLICY]` Abuse controls, tailnet shape, hosting + domain, billing
  provider — operator decisions, already in NEEDS_USER.md.

### 3. Provision — nothing provisionable

| Vision | Current state |
|---|---|
| Pick a box size, get a box | Nothing. Backlog H4 is BLOCKED on the user: provider choice + API credentials |
| Provider-agnostic interface (provision/status/dial/ssh_info/destroy) | Not drafted; H4's draft was supposed to precede the driver |
| Getting merged code onto the live fleet | Design exists: auto-deploy updater, PR #29 (open, fixes #22). Not merged, not enabled |

**Gaps:**
- `[BLOCKER]` H4 — provider choice + credentials (operator). The interface
  draft inside H4 is doable *now* and unblocks later work; keep it as the
  first H4 slice.
- `[PARTIAL]` PR #29 (deploy automation) unmerged. Until it merges and is
  enabled by the operator, every shipped improvement needs a manual deploy —
  the hosted story cannot absorb fast iteration without it.

### 4. The box itself — the strongest stage, single-user by design

| Vision | Current state |
|---|---|
| A persistent computer per Muse | Real: proxy + swapd, muse-job, confirmd approvals, cred-ui, CUA desktop, jail spec |
| Two Muses on one control plane without cross-tenant reads | **Missing everywhere** (see multi-tenancy below) |

**Gaps** — these are the cross-cutting ones; they live in §8 and new
items H10/H11.

### 5. Sentinel — design only

| Vision | Current state |
|---|---|
| A watcher the product reports to; per-tenant isolation story | H5 (design) unwritten. Building blocks exist: confirmd audit lines, proxy audit log, muse-job hooks/events, auto-deploy JSONL audit (PR #29). No sentinel API, no shipper |

**Gaps:**
- `[BLOCKER]` H5 — sentinel design not started (what it watches,
  product↔sentinel API, per-tenant isolation). Nothing exists for the
  sentinel stage; building blocks without a consumer are not a design.
  Prerequisite: the multi-tenancy audit (H11) so the design knows what
  it's isolating. Building blocks exist (confirmd audit lines, proxy audit
  log, muse-job hooks, auto-deploy JSONL) but nothing consumes them.

### 6. Push — page exists, push does not

| Vision | Current state |
|---|---|
| Human approves on their phone without the page open | confirmd pending-approvals page shipped + merged (#20) — mobile-friendly, auto-refreshing. Push: nothing. H2 (VAPID) BLOCKED on operator decision |

**Gaps:**
- `[POLICY]` H2 — VAPID keypair + push-service decision (operator).
- `[PARTIAL]` New item H14: once H2 is decided, confirmd needs a push hook
  (pending-approval created → push enqueue) and a push service. The approvals
  page is the rendering end; the event source doesn't exist yet.

### 7. App / website — copy exists, site does not

| Vision | Current state |
|---|---|
| Signup site, human dashboard, pricing page | Pricing thinking (PR #30), positioning copy bank (PR #28). No site, no dashboard. Operator decisions outstanding: hosting + domain |

**Gaps:**
- `[POLICY]` Hosting + domain (operator).
- `[DESIGN]` New item H15: signup web UI + human dashboard (account, boxes,
  approvals feed, usage). The dashboard is where the sentinel's audit
  stream and confirmd's approvals surface meet the human.

## Cross-cutting gaps

### 8. Multi-tenancy — the single biggest structural gap

Every component was built single-user, localhost-bound:

- **cred-ui** binds `127.0.0.1:18740`, no auth at all — correct for one
  operator over an SSH tunnel, unsafe the moment two tenants share a host.
- **cua-bridge** binds `127.0.0.1:18731`, Host-allowlist + `X-CUA: 1` CSRF
  defense — same single-tenant posture.
- **confirmd** is the exception: tailnet-login auth with `CONFIRM_OWNER`
  expected LoginName (single owner, not multi-tenant roles).
- **muse-job**: single-operator job runner; issues #4–#13 are all
  trust/isolation hardening of that assumption.
- **proxy/swapd**: grants registry per-host allowlists (`hosts.allow`,
  `ssrf.allow/deny`) — no tenant dimension; audit lines carry no
  requester/job attribution (issue #14, open).
- **jail**: spec + `build.sh` exist; cell isolation is a plan, not a
  guarantee.

Nothing here is wrong for the open-source single-box product. But the
hosted vision ("other Muses sign up") cannot be built on top of it without
a tenant dimension in auth, secrets, approvals, and audit. New item H11:
a multi-tenancy audit — inventory every localhost-only/no-auth assumption,
rank by blast radius, propose the isolation story (per-tenant processes?
per-tenant tailnets? one box per tenant, à la signup doc §tailnet?). The
cheapest correct answer may be "one box per tenant" — the audit must say
so explicitly rather than leaving the question open. H11 gates H5 (the
sentinel's isolation story), H12 (per-tenant metering), and H13
(per-tenant idle detection).

### 9. Metering — pricing thinking has no data source

PR #30's pricing thinking assumes measurable usage (box-hours, suspend
cycles, approvals volume). Nothing in the repo meters per-tenant resource
use. New item H12: metering hooks (per-tenant CPU/mem/disk samples,
approval counts, suspend/wake events) — feeds the Billing operator
decision. Build the hooks, not the billing.

### 10. Free-tier suspend/wake — shape defined, machinery absent

PR #30 §3 defines the free tier: idle = no human-originated session AND
no *registered* scheduled-workload activity for N days; suspend-to-disk +
wake-on-SSH-dial; "no session clock" is a paid-tier property. Nothing
implements any of it: no suspend mechanism, no wake path, no registered-
workload registry, no idle detector. New item H13. Note the dependency:
the registered-workload registry is also the input the abuse-controls
decision needs (NEEDS_USER.md).

### 11. Attribution in audit — a hosted non-negotiable

Issues #14 (proxy approvals carry no requester/job attribution) and #16
(phantom swaps) are open. For one operator they're papercuts; for a hosted
product they're compliance-grade gaps: the sentinel cannot reconstruct
"who did what" without attribution. Fold into H11/H5, flagged here so the
sentinel design doesn't inherit the gap silently.

### 12. Orchestration — known, already tracked

TermSquad ships Squad (coordinated parallel agents); we have muse-job
(single-operator). Backlog H8 covers it. Not re-litigated here.

### 13. Tenant-box updates — the vision has no update channel

The pipeline above ends at "box": provision → live → done. Nothing in the
vision says what happens to a tenant box in month two. The box half of the
product has two update mechanisms, and neither covers a tenant box:

| Vision (implied) | Current state |
|---|---|
| A tenant's box stays secure and current without the tenant Muse becoming a sysadmin | Golden images are versioned (`harness/generate-image-manifest.sh`: `image_version` = repo SHA, `built_from_version` = VERSION), gate-checked at provision time (`check-image-manifest.sh`, `docs/GOLDEN_IMAGE_GATE_PROCEDURE.md`), and baked into the image at `/etc/sparkvm/image-manifest.json` — so a box can report its own image, but the provisioner tracks no per-box image_version, and **no path moves a live box from image N to image N+1**. |
| Updates are visible and attributable | The 12 tenant-status codes (`docs/TENANT_STATUS_ENDPOINT.md` §2) have no maintenance/updating code. An in-place update would surface as `box-unhealthy`, as `provisioning` (reimage = a rule-7 session restart), or as nothing at all — the tenant Muse cannot distinguish "updating" from "broken". |
| The renewal path doesn't corrupt the funnel | The only designed renewal path is operator reprovision. #527's `live`/`approved` → `provisioning` carve-out is now on main (transition rule 7's cross-session move for reprovision of the live-anchor box, starting a new session) — so reimage-for-update is licensed, not blocked. The residual question is funnel attribution, not legality: the new session still restarts the clock, and until funnel telemetry distinguishes update-churn from provision-churn, update churn reads as fresh onboarding. |
| Update authority is explicit | #532's toolset updater (merged PR #588 — #542/#551 closed as superseded; the reconciled two-plane system: `scripts/self_update.py` as the unprivileged read-only status plane, `deploy/toolset-update.sh` + `sparkvm-toolset-update.{service,timer}` as the privileged weekly update plane with idle gate, single-flight lock, JSONL audit, machine-wide opt-out, os-security updater layer) is the box half's answer — and both planes remain the box owner's. It was designed for the single-operator box: the tenant operator≠user split was never in scope (that's H11 territory): who opts out, who reads the audit log, and what stops the tenant Muse from influencing the updater's code — all unanswered. `auto-deploy` is worse: it deploys whatever merges to main, and its own trust doc states anyone who can merge to main can execute code on the box. Pointing it at tenant boxes as-is would hand every merger code-exec on every tenant workload — a use the vision has not licensed. |

Gap class: `[DESIGN]` for G11/G13 (the decisions exist nowhere), `[PARTIAL]`
for G12 (the status endpoint design exists; the vocabulary doesn't), `[POLICY]` for
the G11 fork (in-place vs reimage is an operator-shaped call with cost and
funnel consequences).

New backlog items (filed as GitHub issues #553–#556 by the 2026-09-27 gap turn):

- **G11 — tenant-box update policy: in-place vs reimage.** Decide the
  renewal model before H4 ships: does the provisioner track per-box
  `image_version` and offer rolling reimage — including the third path,
  immutable reimage with tenant-state migration (cattle boxes, stateful
  disks: keeps the golden-image invariant while preserving tenant data) —
  or do tenant boxes get an in-place updater? Rule 7's cross-session move
  (carve-out merged in #527) now licenses reimage-for-update, but the new
  session still restarts the clock and funnel telemetry still can't
  attribute update-churn vs provision-churn — that attribution is a design
  choice revisitable for an update path (cf. rule 6's arc-preserving
  suspension latch), not inherent to reimage. In-place
  needs per-box update state the provisioner doesn't track today. Either
  way the decision must land before the first tenant box lives long
  enough to need it.
- **G12 — tenant-visible update state.** Extend the status vocabulary (or
  the `detail` contract) with an updating/maintenance signal so the tenant
  Muse and the signup page can distinguish maintenance from failure — the
  same honesty treatment rule 6 gives relay suspension (latch the arc,
  don't lie). Until then, updates must not be scheduled silently.
- **G13 — update trust model for tenant boxes.** Design who authorizes
  updates on a tenant's box (operator? tenant Muse? automatic within
  policy?), where the audit trail lands (attributable per §11), and how
  the installed-copy discipline survives a tenant Muse with shell on the
  box. Whichever fork G11 picks, an in-place updater needs this trust
  model in full; a reimage path needs at least the reprovision-attribution
  half. A future design goes through Security review.
- **G14 — updates vs idle/suspend and the session clock.** H13's
  suspend/wake and G9's stall detector both assume the box is either
  working or stalled: is an update window a trusted signal (quiet clock)
  or does the detector see a stall? Does a suspended box wake for updates,
  or update on wake? Unspecified — decide with H13.

## Deliberately not gaps

- **Agent onboarding on the box** (R2 pre-seeded harness state): a feature
  gap, not a vision gap — the box works without it.
- **OSS contributor experience**: covered by the separate `gap — OSS
  contributor` seed; next gap turn.
- **GPU shapes**: a provider-choice criterion (H4's C6), not a product gap
  until the CPU story ships.

## New backlog items filed by this analysis

(Added to BACKLOG.md hosted track as H9–H15.)

- **H9 — Hosted identity service implementation**: cert issuance, fingerprint
  verification, re-link with rate limits (implements the H3 design doc
  once the operator decides tailnet shape + abuse controls).
- **H10 — confirmd multi-tenant approvals**: per-tenant pending queues,
  tenant attribution on every approval/audit line, roles
  beyond single CONFIRM_OWNER. Attribution format must stay consistent
  with the #14/#16 work folded into H11/H5 (see §11) — schema alignment,
  not a sequencing dependency.
- **H11 — Multi-tenancy audit**: inventory every localhost-only / no-auth /
  single-owner assumption; rank by blast radius; recommend the isolation
  story explicitly (per-tenant box vs per-tenant processes vs per-tenant
  tailnets). Must explicitly answer: the swap proxy's trust boundary
  relative to tenant workloads (swapd holds secrets on the same box that
  runs tenant agent code — what is the assumed boundary?), fail-open vs
  fail-closed semantics for tailnet-gated auth, and who holds root on a
  provisioned tenant box. Feeds H5 (sentinel design).
- **H12 — Usage metering hooks**: per-tenant resource + approval + suspend
  telemetry; the data source pricing/billing decisions need. Depends on
  H11 — per-tenant metering needs the tenant dimension defined first.
- **H13 — Free-tier suspend/wake**: suspend-to-disk + wake-on-SSH-dial,
  idle detector, registered-workload registry (feeds the abuse-controls
  operator decision). Depends on H11 — idle detection is per-tenant.
- **H14 — Push service implementation**: confirmd push hook
  (approval-created → enqueue) + push service; starts after the H2 VAPID
  operator decision.
- **H15 — Signup web UI + human dashboard**: account/boxes/approvals/usage
  surface; starts after the hosting + domain operator decision.

## Honest summary

The box half of the vision is real and improving (proxy, jobs,
approvals, creds, desktop, deploy automation in flight). The *hosted*
half — signup, identity, provisioning, sentinel, push, app — is designs
and operator decisions with no implementation yet, plus one structural
question the designs can't dodge: multi-tenancy. That is the correct
state for a project whose primary product is the open-source box (the
hosted deployment is a distribution of it), but nobody should mistake
"we have a signup design doc" for "we have signup."
