# Tenant-box update policy — `maintenance` channel (G11 + G12)

**Status:** decided (G11), specified (G12). Resolves backlog items G11
(#553) and G12 (#554) from the tenant-box update-channel analysis
(`HOSTED_GAP_ANALYSIS.md` §13); the update half of the fleet rollout
story (`FLEET_UPDATE_ROLLOUT_GAP_ANALYSIS.md`).

**The gap:** golden images are versioned (`image_version` = repo SHA,
baked at `/etc/sparkvm/image-manifest.json`, gate-checked at image build
(`docs/GOLDEN_IMAGE_GATE_PROCEDURE.md`), preflighted at provision), but the provisioner tracks no
per-box `image_version` and no path moves a live tenant box from image N
to image N+1 — the only designed renewal path is operator reprovision
(`TENANT_STATUS_ENDPOINT.md` transition rule 7), which restarts the
10-minute clock and reads in funnel telemetry as fresh onboarding. The
12 tenant-status codes have no maintenance/updating code, so an update
would surface as `box-unhealthy`, as `provisioning`, or as nothing at all.

## 1. G11 — the renewal-model decision

**Decision: provisioner-tracked per-box `image_version` + rolling reimage
with tenant-state migration.** Tenant boxes are cattle with stateful
disks — no in-place updater is built for tenant boxes.

Three forks were on the table (§13): (a) rolling reimage, (a3) immutable
reimage with tenant-state migration, (b) an in-place updater for tenant
boxes. This doc picks (a3) as the single renewal path.

### Why reimage, not in-place

1. **The golden-image invariant is the trust anchor.** A running box is a
   known, gate-checked image — provision-time gate (`check-image-
   manifest.sh`), `image_version` = repo SHA. An in-place updater is a
   second, never-tested package-diff discipline that lets a box drift
   into a state no image ever was. Reimage keeps the invariant: every
   running tenant box is always exactly some gate-checked image.
2. **An in-place updater is a live code-exec path on tenant workloads.**
   The update trust note on `auto-deploy` already says whoever merges to
   main can execute code on the box it points at — an in-place tenant
   updater turns every release into remote code execution on every tenant
   box, which the vision has not licensed. Reimage executes nothing on
   the running box; the new image is booted, not patched into the old.
   Forward guard: tenant golden images must exclude the
   `sparkvm-toolset-update.timer` / `auto-deploy.timer` units —
   `harness/` installs neither today, but the day someone adds one to
   the image build, the no-in-place-path decision dies silently.
3. **The #532 toolset updater stays single-operator-scoped.** `scripts/
   self_update.py` + `deploy/toolset-update.sh` were designed for the
   box owner (operator = user). The tenant operator≠user split is H11
   territory — who opts out, who reads the audit log, what stops the
   tenant Muse from influencing updater code are all unanswered there.
   Pointing the single-operator updater at tenant boxes answers none of
   them. Tenant boxes get no in-place path; the operator's own boxes
   keep the #532 updater.
4. **State survives without snowflaking.** Tenant data lives on a
   separate data disk (or data partition), not in the OS image. Reimage
   = gate-checked new image boots → data reattaches → a migration step
   runs from the *new* image's tooling. The box is disposable; the state
   is not. This is the (a3) third path: cattle boxes, stateful disks.

### Mechanics (what gets built, by whom)

- The **provisioner** tracks per-box `image_version` (extends the per-box
  record it already keeps for tenant state — a field addition, not a new
  store) and offers **rolling reimage** driven by the fleet layer's wave
  assignment (G15) and release gate (G18): detach state → boot new image
  → run migration from new-image tooling → reattach → flip traffic.
- Migration tooling ships **in the image** (the new image migrates the
  old state, never the reverse — forward-only, like a schema migration).
- Rollout cadence, wave assignment, freeze, and canary promotion are
  G15/G18's components, not this doc's; they consume the `maintenance`
  signal (§2) and this policy's mechanics.
- **Rollback** is reimage to the previous gate-checked image + state
  snapshot restore — the same primitives, not a second mechanism.

### Funnel attribution (G11's residual, answered)

Rule 7's session-restart semantics do **not** apply to scheduled updates:
the reimage is a new box session internally (smoke gates re-run), but the
endpoint's arc stays latched through `maintenance` and the 10-minute
clock is **not** restarted (cf. rule 6's arc-preserving suspension
latch). What changes is attribution: the poll serves `maintenance` with
`detail: maintenance: reimage-for-update` for the duration of the update
(see §2), and funnel telemetry (G17's reporting surface) is required to
distinguish update-churn from provision-churn by that signal — an update
must never be miscounted as fresh onboarding churn. The clock behavior is
not re-litigated; the counting is fixed. The clock keeps running during
maintenance — it is neither paused nor reset; expiry, if it lands
mid-update, applies to the latched arc code exactly as it would without
the update.

### What G11 bounds (but does not solve)

- **G13 (update trust model):** the reimage path needs only the
  reprovision-attribution half — who authorized the reimage, and the
  audit landing (per-tenant, per §11 attribution). No on-box update
  authority exists to design: nothing updates *in* a tenant box, so the
  "tenant Muse influences the updater" threat is out of scope by
  construction. The full G13 trust design is still owed for whatever
  privileged reimage path the operator holds.
- **G14 (updates vs idle/suspend, session clock):** decided with H13.
  This doc's one input: `maintenance` is a **trusted signal** — G9's
  stall detector must treat `maintenance` as a quiet-clock window and
  never relabel it `stuck` (same family as rule 6's suspension latch).
  Whether a suspended box wakes for updates or updates on wake is H13's
  call, not this doc's.

## 2. G12 — the `maintenance` signal

The tenant-status vocabulary gains a 13th code: **`maintenance`** —
"the box is under scheduled update/maintenance; the tenant's workload
is paused or moving, not broken." The tenant Muse and the signup page
can distinguish maintenance from failure — the same honesty treatment
rule 6 gives relay suspension: latch the arc, don't lie.

- **Producer:** the control plane's update scheduler / reimage
  orchestrator (a future G15/G18 component), never the provider driver
  and never the Muse. Like filing/grant/denial/expiry events, it is an
  input to the tenant layer, not a direct status write.
- **Entry:** from `live` or `approved` only — post-`live` arc codes with
  an arc to latch. Never entered from pre-`live` codes (no arc to
  maintain yet), never from `provisioning-failed`.
- **Exit:** on completion the endpoint returns the **latched** arc code
  (`live`, or `approved` for post-onboarding maintenance) — the update
  neither advances nor restarts the onboarding arc, and the 10-minute
  clock is unaffected. The reimage-for-update happens *inside*
  `maintenance`; the endpoint never shows `provisioning` for a
  scheduled update (that would lie about it being a fresh onboarding —
  the rule-7 carve-out stays for operator-initiated session restarts,
  not for scheduled updates).
- **Failure during maintenance:** the endpoint moves to `box-unhealthy`
  with `detail: maintenance-failed: <check>` — the honesty rule: a
  maintenance that breaks the box is a broken box.
- **Schema:** `detail` carries the operation —
  `maintenance: <operation>` (e.g. `maintenance: reimage-for-update`),
  with the §3 multi-box identity suffix (`@ box=<box-name>`) where
  §8's multi-box rule applies. `human_key` is present (`"maintenance"`) —
  the code is human-rendered; the exact sentence stays under
  `FIRST_TEN_MINUTES_SPEC.md` §4's ownership ("exact sentences … no
  paraphrasing"), like every other human-rendered code.
- **§8 multi-box selection:** `maintenance` compares by its **latched
  underlying arc code** (the suspension family: `stuck`,
  `connection-unreachable`, `maintenance`) — the maintenance itself
  neither promotes nor demotes the candidate.
- **Until the signal exists:** per G12's standing rule, updates must not
  be scheduled silently — no silent reimages before the scheduler can
  set and clear `maintenance`.
- **Scheduling constraint:** the scheduler only enters `maintenance` from
  quiescent codes (`live`, `approved`). A scheduled wave never interrupts
  an active onboarding arc: boxes in pre-`live` codes,
  `waiting-on-approval`, any suspension code (`stuck`,
  `connection-unreachable`), or `box-unhealthy` are skipped by the wave
  and retried next cycle — there is no permitted status representation
  for an update interrupting an arc, so the rollout must not create one.
  The retry cadence and wave-membership mechanics belong to G15's
  rollout design (#606); the constraint (never interrupt an arc) belongs
  here. Of the two named items, G15 owns the actual `maintenance`
  enter/exit writes around the reimage; G18 (#609) consumes the signal
  for release gating — neither may assume the other performs the writes.

## 3. Amendments made alongside this doc

`docs/TENANT_STATUS_ENDPOINT.md` is amended in the same change: §2
gains the 13th code + table row (count "12 codes" → "13 codes" in the
doc intro, the §2 vocabulary enumeration, and the §4 producer diagram), transition rule 8 (`maintenance` entry/exit/
failure), §3 `detail`/`human_key` contracts, §4 the producer row, §8
rule-1 the latched-code family. The amendments are mechanical —
vocabulary and rules, no behavior invented here that §2 above doesn't
name.

## 4. Non-goals (other items' lanes)

- Staged rollout, canary, promote-halt — G15 (#606).
- Fleet version inventory — G16 (#607).
- Central update-event reporting — G17 (#608, owns the update-vs-
  provision churn attribution requirement of §1).
- The fleet→box release-gating channel — G18 (#609).
- Suspend/wake interplay — H13; per-tenant queueing — H10.
- The exact signup-page sentence for `maintenance`:
  `FIRST_TEN_MINUTES_SPEC.md` §4 owns exact sentences ("no
  paraphrasing"), and no such sentence exists yet — adding it is a G12
  residual owed before S3 ships.
- The in-place updater some future reader wants: rejected by §1, not
  deferred — reopening it requires re-litigating the golden-image
  invariant, not a new ticket.

## 5. Build slices (for the distribution track, not this doc)

1. **S1 — provisioner per-box `image_version`:** the field on the
   per-box record + a read path (the box reports its own image today via
   `/etc/sparkvm/image-manifest.json`; the provisioner's copy is the
   source of truth for waves). Closes the "tracks no per-box
   image_version" half of G11.
2. **S2 — stateful-disk layout + reimage path:** data on a separate
   disk/partition; reimage = detach → boot new image → migrate from
   new-image tooling → reattach; snapshot before, rollback by
   reimage-to-previous + restore. The migration contract must define
   version-skipping (N→N+2), failed-migration semantics, and
   snapshot-retention policy.
3. **S3 — `maintenance` set/clear in the control plane:** the scheduler
   hook that enters/exits the code around S2's reimage, with the
   `detail: maintenance: reimage-for-update` contract from §2. (This is G12's
   implementation half — `distribution` track.)
