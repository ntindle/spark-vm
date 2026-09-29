# Tenant-box update trust model (G13 / #555)

**Status:** designed (the trust decision), not built. Resolves G13 (#555)
from the tenant-box update-channel analysis (`HOSTED_GAP_ANALYSIS.md` §13)
and answers the G13 half of the tenant-fleet gate in
`ROLLOUT_CONTROLLER_DESIGN.md` §6 ("the tenant-fleet instantiation
additionally waits on G13 and H11" — H11 shipped as PR #341; this doc
closes the G13 half).

**The question (§13):** "Design who authorizes updates on a tenant's box
(operator? tenant Muse? automatic within policy?), where the audit trail
lands (attributable per §11), and how the installed-copy discipline
survives a tenant Muse with shell on the box."

**What G11 already decided (bounds this doc, does not repeat it):**
`UPDATE_CHANNEL_POLICY.md` picks rolling reimage with tenant-state
migration as the single renewal path — no in-place updater is built for
tenant boxes. Its residual, in its own words: "the reimage path needs
only the reprovision-attribution half — who authorized the reimage, and
the audit landing (per-tenant, per §11 attribution)... The full G13
trust design is still owed for whatever privileged reimage path the
operator holds." This doc is that design.

**Trust anchors assumed (not re-decided):**

- The golden-image invariant: every running tenant box is exactly some
  gate-checked image (`image_version` = repo SHA,
  `docs/GOLDEN_IMAGE_GATE_PROCEDURE.md`).
- H11's layer split (shipped, PR #341): per-tenant box; the tenant holds
  root inside the guest; the operator owns the layer below (H11 Q4,
  decided 2026-09-24: the operator holds root on the outer enforcement
  layer — egress fencing, secret swapping, metering, updater enforcement;
  the tenant/agent gets contained root-equivalent inside their guest).
- The `maintenance` producer rule (G12): the 13th tenant-status code is
  written (enter/exit) by the control-plane update scheduler — never the
  provider driver, never the Muse.

## 1. The authorization chain

Who can move a tenant box from image N to image N+1 — four authorized
actors, everything else explicitly excluded:

1. **The operator — release registration.** Nothing is deployable until
   it is registered in the release registry
   (`(component, version, channel, image_version)`); registration is the
   human decision point (`ROLLOUT_CONTROLLER_DESIGN.md` §2). On the
   security channel, registration must carry the advisory reference.
   Every reimage chains back to a registration record with an actor
   identity on it — this is the single authorization the whole chain
   inherits.
2. **The fleet controller — automatic within registered policy.** Wave
   assignment, health-gated promotion, soak windows, canary
   (`ROLLOUT_CONTROLLER_DESIGN.md` §3–§4). The controller authorizes
   *when* a wave moves, never *what* is deployable — deployability comes
   only from the registry. No human per wave is the point of the fleet
   layer; the human decision happened at registration.
3. **The operator again — the emergency surface.** `fleet freeze` /
   `unfreeze` (global, fleet-wide, release-independent), `fleet halt` /
   `fleet promote` (manual override of a stuck or suspect rollout). The
   freeze must propagate through the G18 channel faster than the box-side
   gate interval (`ROLLOUT_CONTROLLER_DESIGN.md` §5); a partitioned
   controller means the fleet holds — fail-closed — rather than drifting.
4. **The control-plane scheduler — execution.** The scheduler owns the
   `maintenance` enter/exit writes (G12 producer rule) and triggers the
   reimage primitive: detach state → boot new image → migrate from
   new-image tooling → reattach (G11 mechanics). Reimage-for-update never
   surfaces as `provisioning` and never restarts the 10-minute clock
   (G11's funnel-attribution decision).

Explicitly **not** authorized:

- **The tenant Muse** — zero authorization over the update path: it
  cannot trigger, schedule, defer, veto, or approve a reimage. A veto is
  a denial-of-update primitive — a tenant that can veto security updates
  holds the fleet hostage — and consent-gated updates re-create the
  consent surface the reimage decision deliberately avoided. The tenant's
  protections are deferral-by-arc (scheduled updates never interrupt a
  running arc — G11/G15) and visibility (no silent updates — G12), not
  consent.
- **The box itself** — a box reports its version and health; it never
  authorizes. For tenant boxes there is no in-place updater at all (G11):
  the `auto-deploy` and `sparkvm-toolset-update` timers are excluded from
  tenant golden images (G11's forward guard — the day one lands in the
  image, the no-in-place-path decision dies silently).
- **Merge-to-main alone** — `ROLLOUT_CONTROLLER_DESIGN.md` §5's honest
  corollary: on fleet-managed boxes the "anyone who can merge to main
  can execute code on the box" primitive narrows to "can merge to main
  *and* register the release". Registration is the second key.

## 2. Where the audit trail lands

**On the control plane — never on the tenant box.** The tenant holds
root inside the guest (H11): any audit line written to the box is
forgeable by the tenant Muse. The authoritative record is the control
plane's JSONL journal, the same discipline as the controller's own
journal (`ROLLOUT_CONTROLLER_DESIGN.md` §2).

Records (per reimage, per box):

- `registration` — release id, channel, advisory ref (security
  channel), registering actor identity, timestamp, policy ref.
- `wave_assignment` — box → wave, canary flag, manifest version.
- `promotion` — wave *k* → *k+1*, gate evidence refs (G17 aggregate,
  G16 inventory), controller pinned-identity fingerprint.
- `reimage` — box id, image N → N+1, the authorizing registration ref,
  wave, migration outcome, G17 outcome-event ref.
- `maintenance` — enter/exit with the latched arc code (G12); the
  10-minute clock is neither paused nor restarted (G11).
- `freeze` / `halt` / `unfreeze` / `promote` — global vs per-rollout,
  operator actor identity.

Attribution rules — the §11 honesty treatment applied to the update
plane:

- Every line carries the authorizing actor's identity — the pinned
  provisioned operator key's fingerprint, never a bare name — and the
  registration ref it chains to. This is
  the #14 lesson (proxy approvals carry requester/job attribution)
  carried into the update plane: an unattributed reimage is an
  unaccountable one. (The identity primitive is
  `ROLLOUT_CONTROLLER_DESIGN.md` §5's provisioned trust root: "the box
  learns the controller's identity at install/provision time (pinned in
  operator-deployed config)" — one key, pinned at provision time,
  fingerprint in every record. The controller's journal identity is that
  same pinned identity, stable across restarts; an ephemeral instance id
  in the authoritative audit journal would be useless after the fact.)
- No phantom entries: a reimage that was deferred, skipped (arc-busy,
  suspended, unhealthy — G11's scheduling constraint), or never started
  gets a `deferred` / `skipped` line with the reason — never a silent
  absence, never an invented success. This is the #16 lesson (phantom
  swaps when the second half of an operation fails): the journal records
  what happened, including "did not happen, and why".
- Failed maintenance is recorded with the same attribution, and the box
  moves to `box-unhealthy` with `detail: maintenance-failed: <check>`
  (G12): a maintenance that breaks the box is a broken box, on the
  record.

The tenant Muse may read its own box's update history — visibility is
the G12 promise — but only through the control plane's read surface,
never a box-side journal. Retention and the access policy are filed as
G19 (§5).

## 3. The tenant Muse with shell — threat by threat

H11's layer split is the frame: the tenant holds root inside the guest;
the operator owns the layer below. The reimage primitive lives entirely
in the layer below (provisioner + control plane). Threat by threat:

- **T1 — the tenant triggers a reimage.** No trigger surface is
  tenant-reachable. The reimage is initiated by the control-plane
  scheduler; the box accepts no update instructions from the tenant
  side. On tenant boxes the wave gate applies to reimage *approval*
  consumed by the scheduler, not by the box
  (`ROLLOUT_CONTROLLER_DESIGN.md` §5) — a tenant box polling anything
  learns nothing actionable and changes nothing. G18's transport design
  must keep it that way: for tenant fleets the gate channel is
  scheduler-facing.
- **T2 — the tenant forges health/gate events to promote a bad release
  or halt a good one.** `ROLLOUT_CONTROLLER_DESIGN.md` §6 names this
  "Event authenticity (G13)": canary gates consume self-reported events.
  **Requirement (this doc's answer): tenant-fleet gates consume only
  box-identity-attested G17 events.** The attestation mechanism — how a
  box proves its identity on the event — is the G17/G18 implementers'
  lane; the trust rule is: unattested events may be logged, never
  gate-consumed. The same rule covers the gate's other self-reported
  input: `ROLLOUT_CONTROLLER_DESIGN.md` §4's promotion gate also consumes
  G16 inventory, and a tenant Muse with shell can forge the box's
  self-reported `image_version` (`/etc/sparkvm/image-manifest.json` is
  tenant-root-writable). Gate-consumed inventory must come from the
  provisioner's per-box record (G11 S1's source of truth) or be
  box-identity-attested like G17 events — raw box self-report may be
  logged, never gate-consumed. The operator estate (trusted boxes, one
  operator) may start without attestation; the hosted tenant fleet may
  not.
- **T3 — the tenant poisons the migration.** The migration runs from the
  *new* image's tooling, forward-only (G11), and it is a data transform —
  tenant *code* does not execute during the maintenance window. The
  migration's *input* is tenant data, which is attacker-influenced:
  input-hardening of migration tooling is filed as G20 (§5). This is
  defense-in-depth, not a trust hole: a poisoned migration breaks the
  tenant's own box — which the tenant already owns, they hold root — it
  cannot escape the reimage primitive to touch another tenant's box or
  the control plane, because the primitive is provisioner-side and
  per-box. The migration's execution boundary is named here so G20 has
  it: migration executes inside the *new guest* only — never on the
  provisioner host. Its network surface is closed during the maintenance
  window; its only provisioner channel is a declared result-report
  (success/failure + attested identity). Migration tooling processing
  attacker-influenced tenant data on the provisioner host would be the
  privilege-boundary crossing this design forbids.
- **T4 — the tenant vetoes a security update.** No consent gate exists
  (§1). Deferral is arc-scoped only: a tenant mid-arc defers even a
  critical CVE until the arc ends — `ROLLOUT_CONTROLLER_DESIGN.md` §7's
  never-interrupt-an-arc holds on the security channel too, and security
  waves land on arc boundaries. The staged-rollout delay of security
  patches is the explicit tradeoff the expedited channel compresses,
  not afterthought. A never-ending arc is not a de-facto veto either:
  `ROLLOUT_CONTROLLER_DESIGN.md` §4's max-wait (the rollout waits for
  the operator and pages — `fleet promote` is the documented manual
  escape) is the backstop that bounds arc deferral.
- **T5 — the tenant steals the freeze.** Freeze is an operator-only
  surface (controller CLI / control-plane API under operator auth). The
  tenant's freeze-equivalent is the arc: an active arc already defers
  that box's wave. A tenant cannot freeze the fleet.
- **T6 — rollback to a vulnerable image.** Rollback is reimage to the
  previous gate-checked image + state snapshot restore (G11) — through
  the same authorization chain, against the *target* release's
  registration. A de-registered release is not deployable; the registry's
  deployability decision covers rollback targets exactly like forward
  targets.

## 4. Sibling relationships (no re-litigation)

- **G11/G12** (`UPDATE_CHANNEL_POLICY.md`) — decided and specified;
  this doc consumes them. The reimage-only renewal model is what makes
  §3 a bounded list: there is no on-box updater authority left to
  design.
- **G14** (updates vs idle/suspend, #556 — still open) — decided with
  H13; this doc's one input is the decided half, already given:
  `maintenance` is a trusted signal, a quiet-clock window for G9's
  stall detector, never relabeled `stuck`. The suspended-box half (does
  a suspended box wake for updates, or update on wake) stays with
  H13/#556.
- **G15/G16/G17/G18** (fleet rollout, #606–#609) — this doc states the
  trust *requirements* they must satisfy (§2's landing, §3 T2's
  attestation) without designing their transports. This doc releases
  the G13 half of §6's tenant-fleet gate; G16–G18 still gate the
  machinery.
- **H5 sentinel** — consumes the §2 journal as an update-plane signal
  source; it reads the control-plane journal, never box-side logs.
- **H10/H11** — waves scope per tenant (H11 released the gate); the §2
  journal is per-tenant by construction. H11's root-holding decision
  (Q4) is the premise §3 stands on.
- **The exact tenant-facing sentence for a reimage** — owned by
  `FIRST_TEN_MINUTES_SPEC.md` §4 ("no paraphrasing"), like G12's
  `maintenance` sentence residual.

## 5. Residuals — new backlog items

- **G19 — update-audit retention + tenant read-path access policy**
  (filed as issue #660): how long the control-plane update journal
  keeps per-box reimage records; who may read a tenant's own history
  (the tenant Muse's read surface, promised by G12's visibility rule);
  the privacy boundary between tenants (one tenant's journal never names
  another's).
- **G20 — migration-tooling input hardening** (filed as issue #661):
  tenant data is attacker-influenced input to the new image's migration
  step (§3 T3) — define the hardening bar (schema-validated migration
  inputs, failure semantics that land the box in `maintenance-failed`
  rather than a half-migrated state; §3 T3's execution boundary is part
  of the bar: migration runs guest-side only, never on the provisioner
  host).

## 6. Build slices (for the distribution/feature track, not this doc)

1. **S1 — control-plane update journal + schema:** the §2 JSONL journal
   with the attribution fields, per-tenant scoping, and
   registration-ref chaining. The journal exists before the scheduler
   does — decisions are auditable from day one.
2. **S2 — registration CLI + operator identity:** the second key that
   narrows merge-to-main (`fleet register` binds the registering
   actor's identity to the record). The registering operator's identity
   is the pinned provisioned operator key from §2's attribution rules —
   the same provisioned trust root `ROLLOUT_CONTROLLER_DESIGN.md` §5
   names: records carry the key fingerprint, and the controller's
   journal identity is that pinned identity, stable across restarts.
   No new identity system is invented here: one provisioned key,
   pinned at provision time, fingerprint in every record.
3. **S3 — attested event ingestion (the G17/G18 lane):** box-identity
   attestation on the events gates consume (§3 T2); unattested events
   are logged, never gate-consumed.

**Both-supported note:** the same primitives serve the self-hosted
operator's N-box estate — registration, the journal, the freeze — with
the operator as the only actor. The hosted delta is tenant scoping
(per-tenant waves, the tenant read path) and the attestation
requirement; the trust model degrades gracefully to the single-operator
case without a second design.
