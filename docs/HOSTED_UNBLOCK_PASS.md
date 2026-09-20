# Hosted unblock pass — 2026-09-19

A one-shot audit of every hosted backlog item with a stated operator blocker
against the current operator decisions in `NEEDS_USER.md`. Blockers the
operator has already resolved are converted into actionable loop work; the
genuinely blocked remainder gets a one-line operator decision packet each.
This pass is loop output only — it changes no operator decisions.

Date of audit: 2026-09-19. Operator-decision register checked: `NEEDS_USER.md`
(all 2026-09-18 decisions; Fly token connected and verified; BYO Tailscale;
operator-run sentinel with tailnet-identity m2m auth; both-supported push;
no-free-tier card-upfront trial; Pages + small Fly machine hosting;
`sparkvm.dev` owned; MIT license; GitHub `workflow`-scope token).

## Stale blockers → converted into work

- **H4 — Fly driver (provisioning automation).** Blocker WAS "provider choice +
  API credentials"; both resolved 2026-09-18 (Fly.io chosen; `custom.flyio`
  token verified, org slug `personal`). → UNBLOCKED. The driver is real loop
  work now: a Fly Machines API driver behind the H3 provider-agnostic interface
  (signup doc §6, PR #24: `provision/status/dial/ssh_info/destroy` +
  `public_ingress: false` network clause) **plus** the PR #40 contract
  extensions (`suspended`/`waking` states, async `dial()` wake semantics,
  open `gpu_class` shape descriptor, suspend-vs-park distinction) — the
  re-filed scope must include these, not just the base H3 interface, because
  H13's wake-on-dial design depends on them. Note:
  a `hourly/fly-driver-20260919-0825` branch exists but is uncommitted and
  unpushed — the implementing turn should rebase/seed rather than duplicate.
  Spend gate: real API calls cost real money — first runs dry-run only; the
  operator decision packet below covers the live-execution spend cap.
- **H9 — Hosted identity service implementation.** Blocker WAS "operator
  decides tailnet shape + abuse controls". Tailnet shape decided (BYO
  Tailscale); abuse controls decided in principle (card-on-file trial, no free
  tier — rate-limit/verification details are loop design, not operator
  decisions). → UNBLOCKED as a tailnet-shape-conformant design refresh first:
  rewrite `HOSTED_SIGNUP_ONBOARDING.md` §4 (Identity linking) and the
  Tailscale paragraphs of §6 (control-plane-minted auth keys / per-tenant
  tailnets — they contradict the BYO decision) plus §11 item 2 (Tailnet
  shape), and the identity-service plan, against BYO Tailscale
  (ed25519 + human-fingerprint approval, tailnet as the
  trust substrate), then implement cert issuance / fingerprint verification /
  rate-limited re-link. No new operator decision needed to start.
- **H11 — Multi-tenancy audit.** Blocker WAS "who operates the sentinel + auth
  direction". Both decided (operator runs it on an always-on box; tailnet
  identity, m2m auth for the agent). The three hard questions (swap-proxy
  trust boundary vs tenant workloads, tailnet fail-open/fail-closed
  semantics, who holds root on a tenant box) are *design* questions — loop
  work, not operator decisions. → UNBLOCKED. It still gates H5/H12/H13, but
  it can start now. Note: the audit's recommendation on who holds root on a
  tenant box comes back to the operator for sign-off (policy call, not a
  settled loop decision).
- **H5 — Hosted sentinel integration design.** Same resolution as H11
  (sentinel placement + auth direction decided). → UNBLOCKED; design can
  start, contingent on H11's isolation-story answer as sequencing.
- **H14 — Push service implementation.** Blocker WAS "H2 VAPID operator
  decision". Decided (VAPID keypair operator-generated; portable component,
  both-supported). H2 itself shipped (PR #48 merged). → UNBLOCKED **in two
  parts**: (a) the standalone push service with enqueue/retry — fully
  unblocked now; (b) the confirmd approval-created hook + per-tenant
  subscription scoping — gated on H10/H11's tenant model (the H2 follow-up
  line records this explicitly), so the hook doesn't get built against
  single-tenant semantics the audit will retrofit.
- **H10 — confirmd multi-tenant approvals.** Backlog says "schema alignment,
  not a sequencing dependency" — no operator blocker. → UNBLOCKED now;
  sequencing-friendly (can parallelize with H11) **on the provisional
  assumption that tenant attribution keys on tailnet identity (the BYO
  decision)**; H11's audit validates or corrects that substrate.
- **H16 — Hosted org-policy layer.** New item; no operator blocker — design
  document is loop work. → UNBLOCKED as design.

## Genuinely blocked — one-line operator decision packets

- **R7 beta pilot cohort:** name 3–5 peer Muses (not contributors) plus their
  boxes, and confirm a human will answer confirmd approvals within ≤5 min
  during pilot sessions.
- **H4 live-API execution:** set a per-run spend cap (and a dedicated Fly org
  or label if needed) for loop-provisioned machines before H4 runs against
  the live API — dry-run only until then.
- **H15 live hosted front end:** when the control-plane Fly machine is up and
  the sparkvm.dev front door is deployed, say so and the loop wires the
  waitlist/signup surface live (waitlist ops doc PR #68 is the runbook —
  precondition: PR #68 is open at audit time, so H15's wiring turn needs the
  runbook merged onto main, not sitting on a branch).
- **Billing provider:** keep parked; the loop will flag when the H3/H15
  design work lands and needs a provider name.
- **H12/H13:** not operator-blocked — design-blocked on H11 (audit output);
  no packet needed. H13 additionally assumes H4's `suspended`/`waking` +
  async-`dial()` contract ships with the Fly driver.

## Backlog updates to apply by this pass (goal workspace, not this branch —
the loop owns BACKLOG.md directly; this branch carries only the audit doc)

- H4: stale "BLOCKED on user" line retired; re-filed as the Fly driver task
  (H3 interface per signup doc §6/PR #24 **plus** PR #40 contract extensions,
  dry-run-first) with the operator spend-cap packet.
- H9: re-filed as "tailnet-shape-conformant design refresh" (BYO model),
  then implementation; no operator gate.
- H11/H5: marked unblocked (sentinel decision), design questions explicit;
  H11's root-holding recommendation comes back to the operator for sign-off.
- H14: marked unblocked post-H2 **in two parts**: (a) standalone
  enqueue/retry service — unblocked now; (b) approval-created hook +
  per-tenant subscription scoping — gated on H10/H11's tenant model.
- H10: marked parallelizable with H11 **on the provisional tailnet-identity
  attribution assumption**.
- H16: marked design-first, unblocked.
- H12/H13: left gated on H11 (dependency, not operator); H13 additionally
  assumes H4's contract extensions ship with the Fly driver.
- H6: stays the living vision doc; its H9–H15 child items got the updates
  above.
