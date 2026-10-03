# Box-provisioning gap analysis: hosted box provisioning from signup (#851)

**Vision vs current state.** Statuses pinned to this repo at main `74f3e76`
(#532 uid-aware idle gate, 2026-10-03). The control plane (`sparkvm-control`
worker) lives outside this repo; plane-side facts below are pinned to the
2026-10-02 read documented in the #847/#849 analyses, not to a repo commit.
Doc-first; honesty rules apply (`docs/POSITIONING.md`): everything below is
**current state and work to do**, not promises.

This is the #851 slice of the hosted build queue. #847 (phone-home) and #849
(phone approvals) got the same treatment; #850 (credential vending) has its
own analysis (`docs/CREDENTIAL_VENDING_GAP_ANALYSIS.md`). Related vision
material: `docs/HOSTED_GAP_ANALYSIS.md` (signup→box pipeline) and
`docs/HOSTED_SIGNUP_ONBOARDING.md` §6–§8.

## 1. The vision (#851 — verbatim acceptance)

> Waitlist → invite → provision: turning a signup into a running box.
> Covers the provisioning path (Fly Machines initially, within the
> $5/run / $25/month caps for loop-provisioned machines), initial pairing,
> and handoff to the dashboard.
>
> Acceptance:
> - Invited user gets a box **without manual operator steps**.
> - Box **auto-enrolls via the pairing flow** and appears in the dashboard.
> - **Spend caps enforced.**

## 2. Current state

| Vision element | Current state |
|---|---|
| Waitlist → invite | **Ships.** `site/waitlistd.py` + `site/waitlist_invites.py` (invite waves, claim POST records the claim and emits the `claimed` funnel event, reconcile paths). Landing live at `sparkvm.dev/waitlist`. |
| Invite → provision trigger | **Nothing.** `waitlist_invites.py`'s own docstring says "the signup-era provisioning surface reads the claim stream" — aspirational: no consumer of the claim stream exists, and no claim→provision orchestrator is anywhere in the repo. |
| Provision (provider driver) | **Contract only.** `harness/provider_iface.py` is the executable H4 interface (`provision`/`status`/`suspend`/`dial`/`ssh_info`/`destroy`/`snapshot`, state model, wake-reprovisions axes). **No driver implements it.** (Stale-claim correction: `docs/HOSTED_GAP_ANALYSIS.md` §3 says the interface is "not drafted" — it was drafted after that doc; this doc supersedes that row.) |
| Fly research | **Done, unacted.** `docs/FLY_DRIVER_RESEARCH.md`: Fly Machines chosen; golden image recommended, exec-install alternative documented; no systemd/cloud-init on Fly; suspend-vs-park mapping done. `custom.flyio` token connected and verified (org `personal`) since 2026-09-18. |
| Initial pairing | **Half.** #844 shipped the pairing flow (box-local ed25519 keygen, 8-char pairing code, human approval, PoP challenge, 24h Bearer <redacted>) and #846 shipped token rotation; `pairing/` client exists. But the flow is **human-approved by design** — nothing in it auto-enrolls a box the plane just provisioned (see G51.3). |
| Appears in the dashboard | **Half.** #845 shipped the authenticated fleet dashboard; #864 shipped the box-side heartbeat sender (cron, `{ok:true}`-gated, flock-serialized). A provisioned box that runs the heartbeat appears — but the dashboard row comes from the **pairing/enrollment row**; no provision-time registration path exists, and the orchestrator's job is to make pairing→enrollment complete (G51.2/G51.3), not to build a second registration path. |
| Spend caps enforced | **Decision only.** 2026-09-24 user decision: $5/run max, $25/month max, auto-destroy at slot end — for *loop*-provisioned machines. The *hosted* provisioning path has **no cap check, no spend ledger, and no destroy-on-budget-exceed** anywhere (see G51.5). |
| Provision-time identity/credentials | **Partial.** #134 (open) is the provision-time credential-install injector (runs against the provider interface). Unresolved: how the box learns its box_id + plane URL at first boot — Fly has no cloud-init (F1), so seeding must go through machine-config env, the image entrypoint, or the exec-install path (see §5 sketch). |
| Tenant access to the box | **Design exists, operator trust step pending.** Tenant SSH is designed to ride the relay (`docs/RELAY_LIVENESS_DESIGN.md`, #486) with host-key pinning via the H4 provider-interface `ssh_info()` verb (attested fingerprint in the connection bundle, no blind TOFU). The standing user blocker is the **loop's own dev-box SSH to the hosted box failing host-key verification** — blocking #843's owner bootstrap and #851's box-side work — now logged in NEEDS_USER.md (see §4). |

## 3. Gaps

- **`[BLOCKER]` G51.1 — no Fly driver implementing `provider_iface`.**
  No code in the repo calls the Machines API — no machine create/start/
  suspend/destroy, no volume attach, no golden-image build, no non-systemd
  supervision design built (FLY_DRIVER_RESEARCH's open item 2 remains open).
  The `custom.flyio` token has been verified for two weeks; the blocker is
  build work, not access. Filed as a new issue (see §6).
- **`[BLOCKER]` G51.2 — no claim→provision orchestrator.**
  The pieces at both ends ship (claim stream → `claimed` events;
  provider interface; pairing; dashboard) but nothing wires them: an
  orchestrator must consume claims, call `provision()`, run the seeding +
  credential install (per #850's S5 routing), trigger the plane-attested
  pairing (G51.3), ensure pairing→enrollment completes so the dashboard
  row appears (no separate registration path), and emit
  funnel/provisioning events. It also owns the provision lifecycle —
  retry vs destroy-on-failure, and crash-safe re-run: #898's actual lesson
  is **commit→emit + idempotent reconcile** (the claim POST commits the
  `signed_up` row *before* emitting `claimed`), not emit-then-commit —
  and the dangerous provisioning window is its own: `provision()`
  succeeds (money spent, box exists) → orchestrator crashes before
  recording → retry provisions a **second box**. "Idempotent re-run" is
  unexpressible against the current contract: `ProvisionSpec` has no
  idempotency key and no claim reference — the provision path needs
  claim-binding (an idempotency key on `ProvisionSpec` or driver-level
  dedupe keyed by claim id). Three design decisions come first, in this
  order: (1) **orchestrator placement** — in-repo loop cron vs the plane
  Worker (the claim store lives in `WAITLIST_DATA` rows.jsonl today;
  the production form posts to the control-plane origin, not deployable
  yet — placement decides the claim store's home too); (2) **tenant_id
  sourcing** — `ProvisionSpec` requires `tenant_id` fail-closed, but a
  claim names an email/invite (H3 identity-linking ordering dependency);
  (3) the idempotency-key contract piece (scoped into #905/#906). Filed
  as a new issue.
- **`[DESIGN]` G51.3 — auto-pairing approval for plane-provisioned boxes.**
  #844's pairing requires a *human* to approve the 8-char code (typed
  bootstrap code `approved_by='bootstrap'` per the #844 ship record covers
  only the fresh-database case). #851's "without manual operator steps"
  acceptance fails if every new box waits for a human click. The missing
  design is **plane-attested approval** — but "the plane knows it
  provisioned box X" is knowledge, not authentication: pairing init carries
  a *box-generated* keypair the plane cannot pre-know, so an auto-approve
  on recognition alone is an approval-forgery path (anyone reaching the
  pairing endpoint could mint a keypair, claim box X's identity, and get
  approved). The mechanism that closes it: a **provision-time single-use
  pairing attestation token**, injected through G51.4's seeding channel
  (the only plane→box authenticated channel at provision time), presented
  as a new pairing-init field, validated against and consumed from the
  provision record, bound to the invite. The approval record carries the
  typed reason (e.g. `approved_by='provision-orchestrator'`) — never the
  human pairing-code path. Why this doesn't undermine #844's trust model:
  for hosted boxes the human fingerprint ceremony was unverifiable anyway
  (a hosted box has no screen the tenant can read), so attestation from
  the provisioning party is the sound trust root; BYO/self-hosted boxes
  keep the human ceremony. Alternatives considered and rejected: shipping
  a pre-shared long-lived pairing secret (replays after image extraction),
  device-flow polling against the plane (needs the same auth bootstrap it
  replaces), and human-in-the-loop for all boxes (fails the acceptance).
  Filed as a new issue.
- **`[PARTIAL]` G51.4 — first-boot identity seeding without cloud-init.**
  FLY_DRIVER_RESEARCH F1: no cloud-init on Fly. The env-var contract is
  pinned once and must be honored by **both** image paths: `SPARKVM_BOX_ID`,
  `SPARKVM_PLANE_URL`, and G51.3's single-use pairing attestation token,
  delivered via machine-config env at create (the only plane→box
  authenticated channel at provision time) and read by a first-boot hook —
  golden-image entrypoint and exec-install `/data` path alike. The box
  fails closed (no enroll, loud log) when the identity vars are absent,
  never invents an identity. This gap is **identity seeding only**:
  credential delivery is #850's settled S5 (plane-side first mint at
  provisioning, vend bootstrap taking over after pairing with the
  post-pairing box-Bearer <redacted> auth per G50.2) — NOT a second box-side
  credential-install shape, and NOT box-side install before pairing (no
  Bearer <redacted> exists pre-pairing, and #850 explicitly rejected two
  delivery shapes). Tracked under the driver issue (G51.1), not a separate
  issue; #134's credential-install injector consumes the vend contract, not
  this seeding channel.
- **`[PARTIAL]` G51.5 — spend-cap enforcement is a decision, not a
  mechanism.** The $5/run / $25/month caps are loop-provisioned-machine
  policy with loop-side enforcement; the hosted path needs: a pre-provision
  cap check (per-tenant and per-org monthly burn — whose source of truth
  gates this on the still-open billing-provider choice in NEEDS_USER.md),
  a spend ledger (provision records with cost attribution —
  HOSTED_GAP_ANALYSIS's reimage-attribution residual is the same ledger),
  and a **destroy**-on-budget-exceed worker (on Fly, suspend = storage-only
  billing per F2, so suspend doesn't stop spend). Filed as a new issue.

## 4. Explicitly NOT this turn's work

- **spark-vm box SSH host-key verification failure (standing user
  blocker):** the loop's dev-box SSH to the hosted box fails host-key
  verification — blocking #843's owner bootstrap (needs box token over
  SSH) and #851's box-side work. The loop must not auto-accept host keys;
  the user is the trust root for box host identity. **Logged in
  NEEDS_USER.md this turn** (resurrecting the lapsed P113 record — the
  repo-turn addition proposed in BACKLOG.md F325 lapsed and the item
  "remained on the run-report surface only"; F340 confirms the standing
  blocker). Distinguished from the tenant path: tenant SSH is designed
  (relay + `ssh_info()` attested fingerprint pinning, no blind TOFU) —
  this item is the operator/loop access path.
- **The plane half of provisioning** (`sparkvm-control` worker): like the
  #846 plane half, it lives outside this repo; the in-repo contract
  (G51.2/G51.3 specs) is pinned here first, plane workspace work follows.
- **Golden-image CI pipeline**: R2's image-build work; the exec-install
  alternative (F1b) lets G51.1 proceed in parallel.
- **#853/#854** (terminal streams, desktop SFU): later queue items.

## 5. Sketch (not spec): how the pieces could meet

1. `waitlist_invites.py` claim POST already writes the claim row and emits
   `claimed`. The orchestrator (G51.2) polls/scans unprovisioned claims.
2. Orchestrator calls `driver.provision(spec)` with the golden-image (or
   exec-install) path, seeding identity via machine-config env (G51.4) and
   enforcing the spend cap pre-check (G51.5).
3. The box's first-boot hook reads the seeded identity (box_id, plane
   URL) and the single-use pairing attestation token (G51.4), then runs
   pairing `init` presenting the token. The plane validates and consumes
   the token against the provision record and auto-approves with the
   typed reason (G51.3) — auto-approval happens *only on token
   presentation*, never on recognition alone. Credential delivery then
   follows #850's S5: plane-side first mint at provisioning, vend
   bootstrap taking over after pairing.
4. Box starts the #864 heartbeat loop; the dashboard (#845) shows the box
   once pairing/enrollment lands per G51.3 — "appears in the dashboard"
   with no operator step.
5. `driver.destroy()` on budget-exceed or user-cancel, with the spend
   ledger as the audit trail.

## 6. Gaps filed

- G51.1 → #905 (Fly driver implementation)
- G51.2 → #906 (claim→provision orchestrator)
- G51.3 → #907 (plane-attested pairing auto-approval design)
- G51.5 → #908 (spend-cap enforcement mechanism)
- G51.4 rides #905 (the driver issue); relates to #134 (open)

*Review-corrected design notes (2026-10-03 ~03:3x CDT):* the adversarial
review found the first draft's G51.3 unsafe (auto-approve-on-recognition
is an approval-forgery path — corrected to the single-use attestation
token above), its G51.4/G51.5 contradicting the settled #850 S5
credential routing (corrected: identity seeding only), and its G51.2
citing #898 backwards (corrected to commit→emit + reconcile, plus the
claim-binding idempotency contract gap). The four filed issues were
annotated with the same corrections at ship time.
