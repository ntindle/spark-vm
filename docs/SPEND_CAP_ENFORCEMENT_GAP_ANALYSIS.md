# Spend-cap enforcement gap analysis (#851 S5 / #908)

Vision-vs-state of the hosted product's spend-cap enforcement: what must
exist for caps to actually bind — a spend ledger, a pre-provision check,
and a destroy-on-budget-exceed worker — versus what exists today.
**Pinned to main `28aa003`** for all in-repo claims. Plane claims inherit
the 2026-10-05 control-plane read recorded in
`docs/METERING_BILLING_GAP_ANALYSIS.md` (zero `meter` refs in
`control-plane/worker.py`, zero metering endpoints in
`docs/CONTROL_PLANE_API_REFERENCE.md`) — no separate plane read was
performed this turn, and no spend ledger was found in that read's scope.

Gap classes reuse the lane vocabulary: `[BUILD]` exists nowhere, build it;
`[DESIGN]` design exists, code does not; `[POLICY]` needs an operator
decision first.

## The vision (as written)

Five sources define the lane:

1. **`#908`** (p2, the build issue): pre-provision cap check (per-tenant
   and per-org monthly burn), a spend ledger with cost attribution
   (provision records; the reimage-attribution residual in
   `docs/HOSTED_GAP_ANALYSIS.md` §3 is the same ledger), and a
   destroy/suspend-on-budget-exceed worker. Acceptance: provision is
   refused when caps would break; budget breach destroys/suspends boxes
   and is audited.
2. **#908's two user corrections (ntindle, 2026-10-03)** — standing
   decisions, not re-litigated here: (a) budget-exceed **destroys**, not
   suspends — on Fly, suspend = storage-only billing
   (`docs/FLY_DRIVER_RESEARCH.md` F2), so suspending does not stop spend;
   (b) the pre-provision check's balance source is gated on the
   billing-provider choice — **the check must name its source of truth or
   it cannot ship**.
3. **The 2026-09-24 billing ruling** (`NEEDS_USER.md`): normal Stripe page,
   card required up front, no free tier; agent purchases are API-driven
   (metered/credit packs purchasable with an API key); the loop's own
   H4 policy is **$5/run max, $25/month max** with loop-side enforcement.
4. **`docs/PRICING_THINKING.md`**: paid tiers are flat monthly (Tier 1
   ~$9–19, Tier 2 ~$29–49), always-on, no session clock — and, in its own
   words, "on flat monthly tiers there is no variable spend to cap — the
   spend cap only bites on the metered GPU add-on and any future usage
   add-ons, so don't oversell it." The buyer story the tiers must ship
   includes per-box spend cap, cost alerts, and a kill switch; "Cost
   controls are a feature the paid tier sells." The stopped/cold
   retention tier (C15) is named but unpriced ("all TBD").
5. **`docs/METERING_BILLING_GAP_ANALYSIS.md` D-M3/F-M8**: the spend ledger
   is #908's own scoped deliverable, not a metering-lane prerequisite.
   Coarse enforcement on provision records is not blocked on the
   metering lane; the metering lane adds the *precision* (suspended/idle
   distinction, live burn) the fine-grained acceptance needs.

## The state (verified on `28aa003`)

- **F-C1 `[BUILD]` — no spend ledger.** Zero hits for `spend_ledger` /
  `monthly_burn` in `*.py`/`*.sh`; the only `budget_exceed` substring hits
  are browser-driver's per-call `call_budget_exceeded`, unrelated to the
  hosted spend lane. The ledger #908 names exists nowhere.
- **F-C2 `[BUILD]` — no cap check, and no hook point.** Provisioning
  itself is unbuilt (`#905` Fly driver, `#906` claim→provision
  orchestrator open), so the pre-provision check has nowhere to live
  yet. The check's natural home is #906's provision decision path — the
  orchestrator owns "retry vs destroy-on-failure" already; the cap
  refusal is the same decision with a billing reason.
- **F-C3 `[BUILD]` — no exceed worker.** Nothing watches burn against
  caps; nothing destroys on breach.
- **F-C4 `[DESIGN]` — the action is decided, the notice is not.** The
  user's 2026-10-03 correction settles destroy-over-suspend (F2: suspend
  doesn't stop spend). But #908's scope names no pre-destroy notice:
  with destroy as the action, a tenant's box — and its files — vanish
  on breach with no warning in the current scope. That contradicts the
  lane's own positioning (`PRICING_THINKING.md`: "Suspend loses *uptime*,
  never *files*" — destroy loses both) unless the breach path warns
  first. The notice is the missing half of the destroy decision. (The
  notice rides the H14 push plane as a tenant-incident push — see D-C3.
  It does *not* ride #849: that lane is a per-action consent flow
  (approve/deny), not a unilateral-notification channel.)
- **F-C5 `[DESIGN]` — two enforcement domains, one issue.** #908's
  "per-tenant and per-org monthly burn" reads as operator-side cost
  control (protecting Fly margin on flat tiers — the operator pays per
  machine-hour while the tenant pays flat), while `PRICING_THINKING.md`'s
  "per-box spend cap" is the tenant-facing buyer story (bites on metered
  add-ons), and the 2026-09-24 ruling adds a third shape: API-driven
  metered/credit packs for agent purchases. #908 never says which domain
  its caps serve. The H4 $5/run / $25/month policy is the loop's own
  instance of the operator-side domain — decided and enforced
  loop-side — the loop-scope precedent for operator-side enforcement.
- **F-C6 `[POLICY]` — cap values have no source.** Neither #908 nor the
  pricing doc says where a cap number comes from: operator-set per-tier
  margin-derived defaults? tenant-set? org-set? The plan catalog the
  tenant-facing caps would hang off does not exist.
- **F-C7 `[DESIGN]` — the balance source of truth is unpinned.**
  The user's gate stands: the check must name its source of truth.
  Candidates are Stripe (human lane) and an internal credit-pack ledger
  (agent lane); nothing in the repo names either as the check's source.
- **F-C8 `[DESIGN]` — breach alerting has no path.** #908 says breaches
  are "audited" but names no channel. The operator's money is at stake
  (page-class for the operator via the fleet alert pipeline, `#797`
  G23's fan-out target) and the tenant's box is about to be destroyed
  (notify-class for the tenant over the H14 push plane, G23-S3-style
  tenant-incident push). Neither is pinned.
- **F-C9 `[DESIGN]` — the projected-cost function is unowned.**
  "Provision refused when caps would break" needs the new box's
  projected monthly cost (tier → Fly size → $/mo plus add-ons). No
  component owns the plan→size→cost model; `#905` will know machine
  sizes but not plan prices.
- **F-C10 `[ATTRIBUTION]` — reimage restarts whose clock?**
  `HOSTED_GAP_ANALYSIS.md` §3's residual is about *funnel* attribution
  (update churn vs provision churn); the ledger needs the *spend*
  rule: a reimage is a new provision record, but the burn must attribute
  to the box lineage, not restart the clock per session — otherwise a
  tenant can reset their burn by reimaging.

## Decisions pinned (D-C series)

- **D-C1 — two-sided cap model.** #908's "per-tenant and per-org monthly
  burn" is the **operator side**: ceilings on the operator's Fly burn per
  tenant/org, protecting margin on flat tiers. The **tenant side** is the
  buyer story: per-box spend caps on metered add-ons (GPU) and
  credit-pack balances in the agent lane. The H4 $5/$25 policy is the
  operator side's already-shipped instance (loop scope). Build slices
  below serve the operator side first — it is the side #908's acceptance
  (provision refusal, destroy-on-breach) actually describes; H4 is the
  loop-scope precedent.
- **D-C2 — destroy on exceed stands** (user-decided 2026-10-03; F2).
  Not re-litigated. Suspend is not an enforcement action; it is a
  cost-optimization action owned by the idle/suspend lane (H13/G14).
- **D-C3 — pre-destroy notice + grace window.** Before the exceed worker
  destroys, the tenant gets a push notification over the H14 push plane
  — a G23-S3-style tenant-incident push (gated on G24's tenant read
  path, like S3 itself) — plus a dashboard banner (`#845`), then a grace
  window (duration `[POLICY]`) to top up or export. The destroy is still
  audited per #908's acceptance. This is what makes D-C2 compatible with
  the "never files" positioning: files are lost only after warning,
  never silently. #849 is explicitly *not* the notice channel: it is a
  per-action consent flow (approve/deny), and a unilateral destroy
  warning with no decision to make does not fit its model.
- **D-C4 — breach alerting is two-channel.** Operator: page-class through
  the fleet alert pipeline (`#797` G23 fan-out target — the operator's
  money is burning; G23's decision is literally operator push, so a
  budget-breach alert rule is additive, not a re-scope). Tenant:
  notify-class over the H14 push plane as a G23-S3-style tenant-incident
  push (gated on G24's tenant read path). Both write audit rows; the
  ledger is the record both channels cite.
- **D-C5 — lineage attribution.** Burn attributes to
  `(tenant, box_lineage_id)`; a reimage continues the lineage and does
  not restart the burn clock. The retry rule: #906 owns "retry vs
  destroy-on-failure" and idempotent re-run on orchestrator crash, so
  failed-provision attempts attribute to the *same* lineage as the retry
  chain — doomed-attempt burn counts toward the tenant's monthly
  aggregate (it is real Fly cost) — and provision-record ingestion is
  idempotent against #906's re-run (idempotency key on the
  claim/orchestrator attempt; append-mostly, no duplicates). Whether
  operator-caused failed attempts are absorbed by the operator or counted
  against the tenant is `[POLICY]` — the burn is real cost either way,
  but who eats it is not settled here. The
  funnel-attribution residual in `HOSTED_GAP_ANALYSIS.md` §3 stays
  separate (telemetry shape, not ledger shape).
- **D-C6 — the source-of-truth gate is load-bearing.** Per the user's
  2026-10-03 correction, the pre-provision check must name its balance
  source of truth or it cannot ship. For the operator-side slice (#1075)
  the source is named: the #1074 ledger (operator-written from provision
  records) plus the projected-cost function. The gate bites on the
  *tenant-side* extension — credit-pack balances in the agent lane —
  where the candidates (Stripe for the human lane, internal credit-pack
  ledger for the agent lane) stay `[POLICY]`-open. The slice is filed
  with the gate explicit, not silently buildable.

## Slices filed

Genuinely-new build slices (`#908` stays open as the lane tracker).
Build order: **#1074 first** (no upstream build dependency); **#1075**
and **#1076** read its schema; **#1077** is the independent `[POLICY]`
catalog.

- **#1074 — spend-ledger D1 schema + provision-record ingestion** — the ledger
  #908 names as its own deliverable: D1 table (tenant/org, box lineage,
  period, projected vs metered burn, cap refs), the provision-record
  write path (coarse source per D-M3), the D-C5 lineage rule. p2.
- **#1075 — pre-provision cap-check hook in #906's orchestrator** — refusal in
  the provision decision path (the orchestrator's existing
  retry-vs-destroy decision with a billing reason), the F-C9
  projected-cost function, operator-side caps per D-C1. **Gated on D-C6**
  (names its balance source of truth or does not ship). p2.
- **#1076 — exceed worker: destroy-on-breach** — burn watcher, D-C3
  notice+grace, D-C2 destroy, D-C4 two-channel alerting, ledger audit
  rows. p2.
- **#1077 — cap-value catalog `[POLICY]`** — where cap numbers come from:
  operator-side margin-derived per-tier defaults and tenant/org
  overrides; tenant-side plan add-on caps against the (nonexistent) plan
  catalog. p3; the build slices proceed on operator-set defaults until
  this lands.

## What this does not change

- D-M3/F-M8 stand: the ledger is #908's deliverable; coarse enforcement
  on provision records is not blocked on `#1047`/`#1048`.
- `#905` (Fly driver), `#906` (orchestrator), `#1047` (meter_agent),
  `#1048` (plane ingestion) keep their scopes; this lane consumes them,
  it does not re-scope them.
- The user's 2026-10-03 destroy correction stands (D-C2); the C15
  cold-retention pricing stays TBD and out of this lane.
- `#908` stays OPEN as the lane tracker until its slices land.
