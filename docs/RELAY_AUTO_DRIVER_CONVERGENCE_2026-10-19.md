# Relay auto-driver lane — convergence analysis

Vision-vs-state of the relay-liveness auto-cadence driver lane (#1711),
pinned to main `9c85d9a5` (post-#1743). This is the convergence pin the
[original gap analysis](RELAY_LIVENESS_AUTO_CADENCE_GAP_ANALYSIS.md)
(2026-10-18, #1711) forecast: S1 and S3 have shipped since; S2, S4, S5
remain. Nothing here re-files what the slice map already tracks — the
findings below are what a fresh deep-read of the SHIPPED S1/S3 code
turned up that the slice map did not.

## 1. State table

| Slice | Issue | State at `9c85d9a5` |
|---|---|---|
| S1 in-repo auto-driver module (`tick_all_tenants`, watermark sidecar, journal notes) | #1721 | **Shipped** — PR #1737 squash-merged |
| S1 security hardening (symlink-refusing sidecar write + lock) | **Shipped** — PR #1742 squash-merged |
| S3 self-hosted packaging (sweep CLI, systemd units, ops guide) | #1723 | **Shipped** — PR #1743 squash-merged (this turn) |
| S2 plane async port + cron trigger + verifier | #1722 (p2) | Open — the hosted-lane half of the driver |
| S4 staleness alert on the driver watermark | #1724 (p3) | Open — **the enablement gate**: the S3 timer ships disabled until this lands (D-AC-6 sequencing, [ops guide](RELAY_AUTO_DRIVER_OPERATIONS.md) §1) |
| S5 probe-loop driver (`maybe_probe` on cadence, caller-supplied bundles) | #1725 (p2) | Open — D-AC-2's loud-stale steady state persists until this ships |
| Doc-honesty splits from #1711 | #1712, #1713 | Closed |
| `_drive_box` dead code | #1733 (p3) | Open |
| Journal-note bidi controls (#1738), sidecar O(tenants²) rewrite (#1739), sibling symlink-plant class (#1740), sidecar read/write asymmetry (#1741) | p3s | Open |

## 2. Findings (new this read; F-AC-8–F-AC-11)

- **F-AC-8 — corrupt watermark sidecar restarts from empty, silently.**
  `_update_watermark` (`hosted/relay_auto_driver.py`) catches
  `(OSError, ValueError)` on the sidecar read and restarts from `{}` —
  but its own docstring promises the corruption is "noted by the
  caller via the record's notes". The function returns `None` and
  signals nothing, so no caller CAN note it: the history loss is
  silent, contradicting the docstring and the D-AC-4 "fail-visible"
  discipline. (Staleness self-heals — the current tenant's record is
  written fresh — but the operator never learns the sidecar was
  corrupt.)
- **F-AC-9 — the watermark sidecar never prunes deleted tenants.**
  `tick_all_tenants` writes a record even when the tenant vanished
  mid-sweep (`rec is None` → a `noop` record with the "vanished" note),
  and no sweep ever deletes records for tenants that no longer exist.
  The sidecar grows unboundedly, and S4's staleness rule (#1724) will
  evaluate phantom tenants — a staleness alert on a deleted tenant is
  a false positive waiting for a rule that reads the sidecar naively.
- **F-AC-10 — the driver's journal-append bound is fleet-scale, not
  tick-scale.** `_append_journal_note` → `fleet.events.append_events`
  runs under `journal_lock(store_dir)`, which raises `JournalLockError`
  after a bounded wait — but the bound is the fleet default of 300 s
  (`fleet/events.py:684`), not a tick-scale timeout. A wedged journal
  lock stalls the sweep up to 300 s per tenant behind the wedge before
  the error surfaces (already noted LOUD on the record with sweeping
  continuing — the leg fails visible, not silent; the gap is only the
  bound's scale). `append_events` takes no timeout parameter today, so
  the driver's journal leg cannot request a tighter bound without a
  signature change.
- **F-AC-11 — journal `box_id` falls back to `tenant_id`, undocumented.**
  `_tick_event` sets `box_id = anchor_box_id if ... is not None else
  tenant_id`. A no-live-anchor tick journals an event whose `box_id` is
  a tenant id — a phantom box row for any journal consumer that joins
  on box identity (the G17 consumer contract is box-scoped). This is a
  decision that was never pinned; D-AC-4's observability section is
  silent on it.

## 3. Decisions (continuing the D-AC series)

- **D-AC-7 — corrupt-watermark silence is a doc-and-signal bug, not a
  design.** Either `_update_watermark` returns a corruption flag the
  caller notes LOUD on the record (preferred — restores D-AC-4
  fail-visible), or the docstring's "noted by the caller" claim is
  struck. Filed as #1744.
- **D-AC-8 — deleted tenants prune from the sidecar.** The sweep
  deletes sidecar records for tenants absent from `store.tenant_ids()`
  (a prune pass, not a per-tick delete), so S4 never evaluates
  phantoms. Filed as #1745.
- **D-AC-9 — journal-append gets a tick-scale timeout.** Thread a
  timeout parameter through `append_events` into
  `journal_lock(store_dir, timeout_s=...)` so `_append_journal_note`
  can request a tick-scale bound (not the fleet 300 s default); on
  timeout the tick notes it LOUD and moves on (the journal is
  secondary observability per D-AC-4). Filed as #1746.
- **D-AC-10 — no-anchor ticks journal with an explicit tenant scope.**
  `_tick_event` keeps the `box_id=tenant_id` fallback but the docstring
  pins it as the documented tenant-scoped convention, with the G17
  consumer contract amended to treat `component="relay" +
  subcomponent="auto-driver"` events as tenant-scoped when `box_id`
  equals `tenant_id`. Filed as #1747 (doc pin, small).

## 4. What this analysis deliberately does not do

- Re-slice S2/S4/S5: their issue bodies stand; this turn only
  re-pinned their state and the S4 enablement gate.
- Re-litigate D-AC-1–D-AC-6: the shipped code honors them (verified
  against the merged heads; the one exception is F-AC-8's docstring
  claim, handled above).
- Touch the timer: it ships disabled, and stays disabled until #1724.

## 5. D-AC-11 — the D-AC-7 "corrupt" scope pin (2026-10-21, #1843)

The D-AC-7 fail-visible contract as shipped by PR #1840 only named
the unparseable case. **Decision:** the corrupt class extends to
valid JSON whose per-tenant values are not record dicts
(`{"tnt-a": "garbage"}`) — the same whole-sidecar restart-from-empty +
LOUD note as the unparseable path, per the D-AC-4 fail-visible
discipline. Rationale: a garbage value cannot feed the S4 staleness
rule (#1724) or ride the bulk merge as ground truth; garbage for
unprobed tenants persisted silently (the hole #1843 filed — practical
impact was low because probed tenants' records overwrite, but the
contract had a shape hole). Whole-sidecar restart was chosen over
surgical per-value quarantine: quarantine cannot be fail-visible —
dropping only garbage values either silently discards the bad tenant's
history (a D-AC-4 violation) or needs a per-tenant LOUD mechanism that
does not exist in the note model; the sidecar is a single JSON
document with no per-tenant integrity boundary, so "corrupt" is a
document-level property, and D-AC-7 already accepted exactly this cost
for the unparseable case. The check is deliberately "is every value
a dict", not a field whitelist: records gain fields over time and
the read must not reject a newer writer's record-field extensions.
The stated invariant is narrower than "any future shape": all sidecar
values are per-tenant records, so a future top-level metadata key
(e.g. a `"_schema"` value) WILL trip the corrupt path — that is the
intended fail-visible behavior, not a false positive. Pin lands in
`read_sidecar_marks` + one new test
(`test_corrupt_watermark_sidecar_garbage_values_restarts_empty`,
neuter-verified). Closes #1843.
