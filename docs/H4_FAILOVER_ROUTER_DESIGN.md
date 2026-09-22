# H4 failover-router design

Closes **C21** (competitor follow-up from the 2026-09-22 C19/C20
consolidation §2.3; feeds **#47/H4**). Epho's lesson, from their
Product Hunt launch: "Sandbox providers are not very reliable, which
means you need to figure out a multi-provider strategy to avoid
failures" — and they "take[] care of automatic fallbacks across
different providers" (see `docs/COMPETITOR_C19_C20_BRIG_EPHO.md` §2).
Epho proves the market need for the layer **above** the adapter:
something that keeps a session alive across provider failures.
This doc designs that layer for our stack.

## 1. What the router is and isn't

The **failover router** is control-plane software, not a driver.
`harness/provider_iface.py` is explicit about the split: drivers own
the per-box lifecycle; the control plane owns idle detection, wave
orchestration, and billing. Failover is wave orchestration: when a
tenant's box fails in a way the driver itself cannot recover, the
control plane moves the *session* to another provider's box.

Definitions:

- **Box** — one provider-native VM, one `vm_id`, one
  `ProviderDriver`, one lifecycle (`ProviderState`). Boxes die;
  drivers know when.
- **Session** — control-plane-owned: `session_id`, `tenant_id`,
  the `ProvisionSpec` that created it, the tenant's disk data, the
  approvals history, the connection bundle the tenant's Muse pins.
  Sessions survive boxes. Epho's "a durable chat's conversation
  outlives the machine it ran on" is the model.

What the router is not:

- Not a verb on `provider_iface` — the C21 filing is explicit: the
  capability axes are the router's *inputs*, not another verb.
- Not the idle path: `suspend()`/`dial()` wake-wait is H13's
  idle economics, not failover. A suspended session is healthy; the
  router only acts on *failure*.
- Not a billing design (that's H13/H5), not the sentinel (H5), and
  not the H11 multi-tenancy answer. Like `provider_iface` itself,
  this design is **provisional on H11**: it assumes one lifecycle per
  tenant box. If H11 answers per-tenant *processes*, the session
  model here gets revised together with the interface.

## 2. Trigger taxonomy: what fails over, what doesn't

The router classifies before it acts. Most failures do **not**
fail over — in-place recovery is cheaper and the interface's error
taxonomy already names the recoverable ones:

| Signal | Router action | Why |
|---|---|---|
| `WAKE_TIMEOUT` (wake accepted, still in flight) | Poll and retry in place | rec 2: the wake is still in flight, not failed |
| `WAKE_FAILED` (attempt ended, box back in `SUSPENDED`) | Retry `dial()` in place | rec 2: the box is *back in SUSPENDED* — the failure is diagnosed, not a provider outage |
| `ErrorKind.FAILED` where the driver **accepts** retry (`FAILED → PROVISIONING` is legal) | Re-provision on the same driver | The transition table permits it; the driver believes recovery is possible |
| `ErrorKind.FAILED` where the driver **declines** retry | **Fail over** | The driver's verdict that its own recovery is impossible is the cleanest failover trigger we have |
| `PROVISION_FAILED` after the driver's own retries | **Fail over** to the next provider | Provision is per-provider; nothing on this box ever existed |
| `Health.DEGRADED` | No action (monitoring only) | Degraded is orthogonal to lifecycle; a degraded box is still the tenant's box |
| Provider-level outage (mgmt endpoint down, region-wide failure — detected at the control plane, not via `status()`) | **Fail over** | `status()` itself is unreachable; in-place recovery is undefined |
| `STOPPED` / unexpected `STOPPING` | Wake via `dial()` in place | rec 1: `dial()` on a stopped box starts it through the wake path — never an error |

The rule of thumb: **fail over only when the driver cannot or will
not recover the box itself.** A `FAILED` driver that declines
retry is the contract-level equivalent of Epho's "provider is not
very reliable" — and it's machine-readable, no heuristics needed.

## 3. Which verbs the router drives

The router never touches provider APIs directly; it drives only the
shipped `provider_iface` verbs, in this order for a failover:

1. **`status()`** (source driver) — classify. Confirm `FAILED`
   (declined retry) or detect the outage.
2. **`snapshot()`** (source driver, best effort) — if the source
   box is reachable at all, capture a fresh provider-native
   snapshot. If unreachable, skip: the session restores from the
   control-plane backup (§4), never blocks on a dead box.
3. **`provision()`** (target driver, new `vm_id`) — with the
   session's stored `ProvisionSpec`. The target's `ProvisionResult`
   carries its own `capabilities` — the router records, does not
   trust blindly.
4. **`attest_network_isolation()`** (target driver) — **mandatory,
   fail-closed.** The router calls `assert_isolated()` before the
   tenant is ever told about the new box. Failover never lands a
   tenant on an un-attested box (H3 §6). If attestation fails, the
   target is scored out and the router proceeds to the next
   candidate — this is Brig's policy-downgrade refusal applied to
   failover (see C22).
5. **Restore** — §4's cross-provider session-state restore
   contract (not a verb: the contract below).
6. **`dial()`** (target driver) — bounded-blocking wake-wait;
   verifies the restored box actually opens a stream. A restored
   box that won't dial is a failed failover — the router treats it
   like any provision failure and moves to the next candidate.
7. **`ssh_info()`** (target driver) — re-queried unconditionally.
   Even on a non-park target, the endpoint/fingerprint may differ;
   the control plane pushes a new connection bundle to the tenant's
   Muse. The fingerprint is attested over the authenticated
   provisioning channel — pinning is preserved, never blind TOFU
   (H3 §6). On `wake_reprovisions` targets this re-query is
   already the contract's requirement; failover makes it universal.
8. **`destroy()`** (source driver) — after the new box is attested,
   restored, and dialed. Source cleanup is last, never first: a
   failed restore must not strand the tenant with *no* box while
   the source still had recoverable disk. The source's `RetentionInfo`
   (C15) tells billing what to charge until destroy lands.

Verbs the router does **not** drive: `suspend()` (idle path, H13),
`provision` with a *changed* spec (failover restores the same
shape; changing shape is an upgrade, a different operation).

## 4. The cross-provider session-state restore contract

This is the missing design the C20 consolidation named: **VM-snapshot
restore is not portable across providers.** A Fly snapshot cannot
boot a RunPod pod. So the session cannot ride the provider's own
snapshot mechanism across the failover — and the design must say
what it rides instead.

### 4.1 What "session state" actually is

Three layers, with different portability:

1. **Tenant disk data** — the data volume contents: home
   directory, installed tooling, the agent's working files. Portable
   *as data* (it is just bytes on a disk); not portable as a VM
   image. **This is the layer failover restores.**
2. **VM memory** — never portable across providers, and rarely
   within one (`memory_resume` is `COLD_ONLY` on the reference Fly
   shape; the 15 GB reference shape exceeds Fly's ≤4 GB suspend
   cap). The interface's disk-persistence-only guarantee is the
   contract: failover is always a **cold** restore of memory.
   Callers must not promise otherwise — this aligns with #177's
   memory-preservation semantics (disk guaranteed, memory
   shape-dependent), extended across the provider boundary to
   "memory never survives failover."
3. **Control-plane session record** — `session_id`, `tenant_id`,
   the `ProvisionSpec`, the approvals history, the pinned
   connection bundle. Never touches a provider; follows the session
   trivially. The approvals plane (confirmd) is control-plane state:
   pending/terminal approval records ride the session record, not
   the box (with the known scale-out limit #194 names).

### 4.2 The restore mechanism: control-plane-owned portable backups

The design decision: **the router restores from
control-plane-owned portable backups, not from provider snapshots.**

Rationale: requiring every driver to implement a portable
export/import verb pushes provider-specific image surgery into the
interface — the exact complexity `provider_iface` was written to
avoid (drivers stay thin; the control plane owns orchestration).
Instead:

- The control plane keeps the last N portable backups of each
  tenant's data volume in provider-neutral storage (object store;
  format: a plain disk-image or file tree, encrypted at rest —
  the encryption and key story is H5/H9's, not this doc's).
- Backup cadence is H13's idle-economics decision (continuous for
  running boxes is expensive; the floor is "every suspend writes
  one"), but the *format and location* are fixed here: backups
  live outside every provider, keyed by `session_id`.
- Failover restore = `provision(target)` → import the latest
  portable backup into the new box's data volume → re-run tenant
  bootstrap → `dial()` to verify.

Provider-native `snapshot()` keeps its job: **same-provider**
recovery (wake retry, same-driver re-provision after a declined
retry). The portable backup is the cross-provider path. Both are
disk-data mechanisms; neither carries memory.

### 4.3 The bootstrap precondition (H19)

Restore is meaningless without the tenant environment: the H19
provision-time credential-install injector must be **idempotent**,
because failover re-runs it on a box it never provisioned. This is
not a new requirement — `wake_reprovisions` (park-style backends)
already demands bootstrap idempotency and `ssh_info()` re-query
after every wake. Failover universalizes that demand: **every
target is treated like a park-style backend on first restore.**
The router's restore sequence is literally the park wake sequence:
provision → import data → re-run bootstrap → re-query `ssh_info`
→ `dial` to verify. Designing the router this way means the H4
contract work already done *is* the failover restore path —
failover adds orchestration, not new per-box mechanics.

### 4.4 Session continuity surfaces

- **Streams** (#178): desktop/terminal streams do not migrate;
  they re-attach. The session record carries stream-ownership, so
  after failover the tenant's client re-establishes streams against
  the new box. The old box's streams die with it.
- **Approvals**: pending approval requests survive via the
  control-plane record; the tenant's Muse sees the same pending
  set after failover, bound to the new `vm_id`.
- **Sentinel** (H5): watches the `session_id`, never the `vm_id`.
  A failover is a sentinel-visible event (box changed under a live
  session), not an anomaly to alert on.
- **Billing**: the old box bills (per its `RetentionInfo`) until
  `destroy()` lands; the new box bills from provision. The
  control plane, not the router, owns the invoice math — but the
  router guarantees the ordering (serve-then-destroy) that makes
  the math honest: the tenant is never billed for zero boxes, and
  never double-billed for two live boxes past the restore window.

## 5. How the capability axes pick the fallback target

C21's filing is explicit: *the axes are the router's inputs, not
another verb.* Target selection is a scoring pass over the
registered drivers' per-shape capabilities:

**Hard filters** (a candidate failing any is out):

- Driver not in outage (control-plane health, not `status()`).
- `public_ingress` attestable — the driver must have a passing
  attestation history; failover never probes an untrusted driver
  with a live tenant.
- Shape fit: candidate's shape meets or exceeds the session's
  `ProvisionSpec` (cpus, ram_gb, disk_gb; `gpu_class`
  compatible — the open descriptor from `GPU_PATH_RESEARCH.md`,
  matched as strings, not enums).

**Scoring** (ordered, first match wins ties):

1. `supports_suspend` — if the session's idle policy is
   suspend-based (H13), prefer targets that support it. A
   non-suspend target is *allowed* with a documented downgrade:
   the session's idle story becomes park-on-demand, and the
   tenant is told so. Fail-closed would strand the tenant; the
   downgrade is explicit, like Brig's (C22).
2. `wake_reprovisions` — park-style targets score lower but are
   valid; the router already runs the bootstrap+requery sequence
   for every restore (§4.3), so a park target costs nothing extra
   mechanically.
3. Same region as the source, then same provider family — latency
   and data-sovereignty tiebreakers, operator-configurable.
4. `max_suspend_memory_gb` / `memory_resume` — informational for
   cross-provider (memory never survives); decisive only for the
   same-provider re-provision branch, where a `FULL` target can
   attempt a warm path.

**Failover loops are bounded.** The router attempts at most N
targets (operator-set, default 3), then parks the session in a
diagnosed failure state with the session record intact — a human
(or the H11-era operator tooling) picks up from a complete
record, not from a half-migrated mess. Split-brain (old box
unexpectedly alive after the new box serves) resolves by
serve-then-destroy ordering: the old box is destroyed once the new
box is attested, restored, and dialed; if the old box revives
later, it is an orphan and the control plane destroys it on sight
(keyed by `session_id`, which it no longer owns).

## 6. What this teaches the open-source track

The router orchestration is control-plane (hosted), but two
artifacts are pure open source:

1. **The portable session-state backup format** (§4.2) — a
   provider-neutral, encrypted tenant-data backup keyed by
   `session_id`. Self-hosted operators get driver-to-driver
   migration for free: export from Fly, import to a local box, the
   same format, no router required.
2. **The trigger taxonomy** (§2) — the classification of
   `WAKE_FAILED` vs declined-retry `FAILED` vs provider outage is
   a runbook any operator can apply by hand, router or not.

Both-supported default honored: nothing in this design requires
the hosted control plane to be useful.

## 7. Open questions (not this doc's to answer)

- **H11**: per-box vs per-process multi-tenancy changes the
  session model; this doc is written against per-box and is
  revised together with `provider_iface` if H11 lands otherwise.
- **H13**: the portable-backup cadence and the suspend-economics
  default that feeds target scoring (`supports_suspend`
  preference) are idle-economics decisions.
- **H19**: bootstrap idempotency is the restore precondition; the
  injector's contract must state it explicitly.
- **H5/H9**: backup encryption keys and the tenant-identity story
  for the session record.
- **#47 sub-items** (#177–#180): the pause/resume, stream-ownership,
  idle-policy, and stopped-state semantics being defined there are
  the surfaces failover must preserve; this doc assumes their
  control-plane answers and should be re-checked against them as
  they land.

---

*Design doc for C21. Conventions: VERIFIED = read on a vendor's own
page/doc/repo; THIRD-PARTY = press or third-party sources (Epho
claims in §1 are THIRD-PARTY per the C19/C20 consolidation);
INFERRED = labeled as such. Code references are to
`harness/provider_iface.py` as merged (PR #183).*
