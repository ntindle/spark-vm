#!/usr/bin/env python3
"""Relay-liveness probe-cadence driver, S5 (issue #1725, #1711 remainder).

Design: ``docs/RELAY_LIVENESS_AUTO_CADENCE_GAP_ANALYSIS.md`` (D-AC-1,
D-AC-2 dependency, F-AC-2). Stdlib-only. This module is the probe half
of the auto-cadence story: it calls
``relay_path_state.maybe_probe`` for each tenant's live anchor on the
probe cadence, with caller-supplied bundles, honoring the D-RL2-2
stand-down.

- D-AC-1 — one clock: the probe cadence IS the drive cadence, the
  same ``RELAY_PROBE_CADENCE_S`` knob ``relay_path_state.cadence_s()``
  reads. ``maybe_probe`` itself decides "due"; a tick that is not due
  is a cheap no-op (the reading is recomposed, nothing probed).
- D-RL2-2 — stand-down: ``provider_state_fn`` + ``has_post_live_arc``
  feed ``maybe_probe``'s ``cadence_decision``; ``suspended``/
  ``destroyed`` or no post-``live`` arc stands down, recorded
  observably (``stand_down=True``), never silent.
- F-AC-2 / D-RL2-3 — bundle supply: bundles are caller-supplied per
  probe via ``bundle_fn(tenant_id, vm_id) -> dict | None``. This
  module invents NO persisted bundle store; a due tick with no bundle
  is noted (mirroring ``maybe_probe``'s "R2b never fetches bundles"
  interim honesty), not a failure. The default supplier returns None
  — the dark-instrument steady state, loud by design until the
  deployer wires a supplier.
- Observability (the loop's own): every tick writes
  ``{tenant_id, tick_at, probed, stand_down, failed, reason, notes}``
  to the per-tenant probe watermark — a sidecar next to the tenant
  store via ``hosted.relay_tick_sidecar`` — and appends one
  probe-note event per tenant to the fleet event journal. The probe
  loop's death mode is S4's fail-visible story: a dead probe loop
  shows as missing/stale probe watermarks, distinct from the drive
  watermark — so the S1 tick's stale-probe note can tell "probe loop
  dead" from "driver dead".

The S1 auto-driver (``hosted/relay_auto_driver``) consumes the probe
history this module produces; its scheduled packaging is
``hosted/relay-probe-driver.{service,timer}`` (#1837) — inert until
the operator enables it past the #1724 gate. Until a scheduled probe
source runs, S1's loud-stale ticks are the steady state by design
(D-AC-2).
"""

import time
import uuid
from typing import Callable, Dict, List, Optional, Tuple

from hosted import relay_path_state as rps
from hosted import relay_tenant_wiring as wiring
from hosted import relay_tick_sidecar as sidecar

# Probe-tick watermark sidecar name: <tenant-store-path> + this suffix.
# Distinct from the drive watermark (``.relay-tick-watermarks.json``):
# the probe loop's death mode must read as a missing/stale PROBE
# watermark, not as drive trouble (S4's fail-visible story).
PROBE_WATERMARK_SUFFIX = ".relay-probe-watermarks.json"

# Deterministic namespace for probe-note event ids (uuid5): re-running
# the same tick (same tenant + tick instant) journal-dedups to a no-op
# via append_events' (box_id, event_id) dedup — the same discipline as
# the S1 tick notes.
_EVENT_NS = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "https://github.com/ntindle/spark-vm/hosted/relay-probe-driver",
)

_EVENT_SCHEMA = "fleet-event/1"

# maybe_probe's stand-down reason vocabulary (relay_path_state.
# cadence_decision): "stand-down: provider state is ..." /
# "stand-down: no post-live arc ...". The driver classifies the tick
# off this prefix — maybe_probe owns the decision; the driver only
# labels it observably.
_STAND_DOWN_PREFIX = "stand-down"

# maybe_probe's due-but-no-bundle reason fragment (D-RL2-3 interim
# honesty: "R2b never fetches bundles").
_NO_BUNDLE_FRAGMENT = "no connection bundle supplied"


def probe_watermark_path_for(store_path: str) -> str:
    """Sidecar path for the per-tenant last-probe-tick watermarks."""
    return store_path + PROBE_WATERMARK_SUFFIX


def _no_bundle_supplier(tenant_id: str, vm_id: str) -> None:
    """Default bundle supplier: the dark-instrument steady state.

    Returns None — a due tick is noted LOUD (the deployer has not
    wired a bundle supplier yet), mirroring maybe_probe's "R2b never
    fetches bundles" interim honesty. The loop must not invent a
    persisted bundle store (D-RL2-3); the supplier is the deployer's
    seam.
    """
    return None


def _probe_event(
    *, tenant_id: str, vm_id, tick_iso: str, record: dict
) -> dict:
    """One standard-shape fleet event (``fleet-event/1``) for the probe tick.

    The journal is the G17 consumer contract: ``kind``/``outcome`` are
    the machine-readable signal, the LOUD lines (when present) ride in
    ``note``. The event id is deterministic over (tenant, tick
    instant) so a retried tick dedups instead of double-journaling.

    Outcome vocabulary note: a wedge-degraded not-due tick
    (``probed=False`` with a history-wedge WARNING folded into the
    reason) lands in the ``noop`` bucket — ``stand_down`` stays False
    and the warning rides the free-text note. Machine consumers
    cannot distinguish degraded-noop from clean-noop; that is a known
    limitation of the 4-bucket vocabulary, not a misclassification.
    """
    outcome = (
        "failed"
        if record["failed"]
        else "probed"
        if record["probed"]
        else "stand-down"
        if record["stand_down"]
        else "noop"
    )
    note = "; ".join(record["notes"]) if record["notes"] else (
        "relay probe-driver tick: %s (%s)" % (outcome, record["reason"])
    )
    return {
        "schema": _EVENT_SCHEMA,
        "event_id": str(
            uuid.uuid5(_EVENT_NS, "relay-probe|%s|%s" % (tenant_id, tick_iso))
        ),
        # box_id is operator-displayed alongside the note; a bidi-laden
        # vm id would reach the same surfaces, so it gets the same
        # scrub (ids are operator-configured, but the scrub is one line
        # and closes the producer-side hole completely).
        "box_id": (
            sidecar.scrub_note(vm_id)
            if vm_id is not None
            else sidecar.scrub_note(tenant_id)
        ),
        "session_epoch": None,
        "emitted_at": tick_iso,
        "received_at": tick_iso,
        "source": "relay-probe-driver",
        "component": "relay",
        "subcomponent": "probe-driver",
        "subcomponents": None,
        "kind": "relay-probe",
        "outcome": outcome,
        "from": None,
        "to": None,
        "from_version": None,
        "to_version": None,
        "phase": None,
        "window": None,
        "rollout": None,
        "trigger": "scheduled",
        "attested": False,
        "note": sidecar.scrub_note(note),
    }


def probe_one_tenant(
    store: wiring.WiringStore,
    tenant_id: str,
    *,
    tick_at: float,
    tick_iso: str,
    provider_state_fn: Callable[[str, str], str],
    post_live_fn: Callable[[str, str], bool],
    bundle_fn: Optional[Callable[[str, str], Optional[dict]]] = None,
    box_to_vm: Optional[Callable[[str], str]] = None,
    history: Optional[str] = None,
    journal_timeout_s: Optional[float] = None,
) -> Tuple[dict, Optional[str]]:
    """Run one probe tick for a tenant. Returns (record, vm_id).

    ``provider_state_fn(tenant_id, vm_id)`` returns the H4 provider
    state string for the anchor's box; ``post_live_fn(tenant_id,
    vm_id)`` is the tenant layer's post-``live`` answer;
    ``bundle_fn(tenant_id, vm_id)`` supplies the probe bundle or None
    (D-RL2-3 — caller-supplied, never persisted; the default supplier
    returns None, the dark-instrument steady state).

    Never raises for per-tenant conditions: every ``Exception`` from
    the store read, the anchor selection, the supplier calls, or the
    probe itself becomes a ``failed=True`` LOUD record (fail-visible,
    D-AC-3 — one tenant never wedges the sweep). Only ``BaseException``
    (KeyboardInterrupt/SystemExit) escapes; those are the operator's,
    not the tick's. (``maybe_probe`` itself never raises for history
    wedges — those degrade to ``probed=False`` with the wedge folded
    into ``reason``.)
    """
    notes: List[str] = []
    vm_id: Optional[str] = None
    probed = False
    stand_down = False
    failed = False
    reason = ""

    if bundle_fn is None:
        bundle_fn = _no_bundle_supplier
    if box_to_vm is None:
        def box_to_vm(box_id: str) -> str:
            return box_id

    try:
        rec = store.get(tenant_id)
        if rec is None:
            # Benign race: the tenant was deleted between tenant_ids()
            # and get(). Not a failure — the next sweep re-lists.
            notes.append(
                "tenant record vanished mid-sweep — no probe run, "
                "next sweep re-lists"
            )
        else:
            anchor = wiring.select_live_anchor(list(rec.boxes.values()))
            if anchor is None:
                notes.append(
                    "no live-anchor box — nothing to probe"
                )
            else:
                vm_id = box_to_vm(anchor.box_id)
                bundle = bundle_fn(tenant_id, vm_id)
                result = rps.maybe_probe(
                    vm_id,
                    provider_state_fn=lambda: provider_state_fn(
                        tenant_id, vm_id),
                    has_post_live_arc=post_live_fn(tenant_id, vm_id),
                    bundle=bundle,
                    now=tick_at,
                    history=history,
                    journal_timeout_s=journal_timeout_s,
                )
                probed = bool(result["probed"])
                reason = str(result.get("reason") or "")
                stand_down = (not probed) and reason.startswith(
                    _STAND_DOWN_PREFIX)
                if (not probed and bundle is None
                        and _NO_BUNDLE_FRAGMENT in reason):
                    notes.append(
                        "LOUD: probe due for %s but no bundle supplied "
                        "(bundle_fn returned None) — R2b never fetches "
                        "bundles (D-RL2-3); wire a bundle supplier or "
                        "the instrument stays dark" % (vm_id,)
                    )
    except Exception as exc:  # noqa: BLE001 — fail-visible per tenant
        failed = True
        notes.append(
            "LOUD: probe tick failed for tenant %r: %s: %s — probe "
            "history untouched, next tick retries"
            % (tenant_id, type(exc).__name__, exc)
        )

    record = {
        "tenant_id": tenant_id,
        "tick_at": tick_iso,
        "probed": probed,
        "stand_down": stand_down,
        "failed": failed,
        "reason": reason,
        "notes": notes,
    }
    return record, vm_id


def probe_all_tenants(
    store: wiring.WiringStore,
    *,
    watermark_path: str,
    journal_store_dir=None,
    provider_state_fn: Callable[[str, str], str],
    post_live_fn: Callable[[str, str], bool],
    bundle_fn: Optional[Callable[[str, str], Optional[dict]]] = None,
    box_to_vm: Optional[Callable[[str], str]] = None,
    history: Optional[str] = None,
    journal_timeout_s: Optional[float] = None,
    now: Optional[float] = None,
) -> dict:
    """Probe every tenant's live anchor once (S5 probe driver, #1725).

    ``store`` is any ``WiringStore``; ``watermark_path`` is the
    sidecar JSON the per-tenant last-probe-tick records land in
    (``probe_watermark_path_for(store_path)`` for the in-repo file
    store). ``journal_store_dir`` (optional) is the fleet estate store
    dir whose ``events.jsonl`` receives one probe-note event per
    tenant.

    Returns ``{"tick_at", "cadence_s", "tenants": {tenant_id: record},
    "errors": [...]}`` — ``errors`` carries per-tenant observability
    failures (watermark/journal), never probe failures (those are
    ``failed=True`` on the tenant's own record), plus at most one
    sweep-level entry (``tenant_id`` None) when the probe-watermark
    sidecar itself is unreadable (ELOOP plant, #1838), or when the
    single locked bulk write after the probe loop fails (lock-path
    ELOOP plant, disk-full, permission — #1842): the bulk write is
    sweep-level, so its failure is one sweep-level entry, never N
    per-tenant ones. One sidecar-level fault is one sweep-level
    entry, never N per-tenant ones.

    Raise contract: ``store.tenant_ids()`` raising (e.g. a corrupt
    tenant store) propagates — a store the sweep cannot even list is
    an operator-level failure, not a per-tenant condition; the
    scheduled entrypoint turns it into its exit-2 "sweep could not
    run" (the S1 sweep's contract), never a silent partial summary.

    The watermark sidecar gets exactly ONE read-modify-write per sweep
    (#1739 discipline): per-tenant records are collected in memory and
    merged in a single locked write after the probe loop.
    """
    tick_at = time.time() if now is None else now
    tick_iso = sidecar.now_iso(tick_at)
    cadence_s = rps.cadence_s()
    if box_to_vm is None:
        def box_to_vm(box_id: str) -> str:
            return box_id

    # Pre-loop hint read: the corrupt flag must be known BEFORE the
    # journal events are built, because the D-AC-7 LOUD corruption
    # note rides the journaled probe-note. This read is only the hint;
    # the authoritative merge is the single locked read-modify-write
    # after the probe loop, so a concurrent sweeper's records are
    # merged, never lost.
    try:
        _, wm_corrupt = sidecar.read_sidecar_marks(watermark_path)
        wm_read_exc = None
    except OSError as exc:
        # read_sidecar_marks raises OSError only for errno.ELOOP: a
        # symlink plant at the sidecar path (#1741). Defer it to the
        # sweep-level handler below (#1838): one sidecar-level fault is
        # one sweep-level errors[] entry, never N per-tenant ones. The
        # sweep still probes every tenant — the watermark simply does
        # not persist this sweep.
        wm_corrupt = False
        wm_read_exc = exc

    tenants: Dict[str, dict] = {}
    errors: List[dict] = []
    pending_writes: Dict[str, dict] = {}
    for tenant_id in store.tenant_ids():
        record, vm_id = probe_one_tenant(
            store,
            tenant_id,
            tick_at=tick_at,
            tick_iso=tick_iso,
            provider_state_fn=provider_state_fn,
            post_live_fn=post_live_fn,
            bundle_fn=bundle_fn,
            box_to_vm=box_to_vm,
            history=history,
            journal_timeout_s=journal_timeout_s,
        )
        # #1838: the per-tenant watermark/journal legs run only when the
        # sidecar itself was readable. A sidecar-level fault (wm_read_exc,
        # the ELOOP plant above) skips these legs for the WHOLE sweep —
        # the single sweep-level errors[] entry appended after the loop
        # is the honest signal, not N per-tenant ones. The probe loop
        # still ran every tenant above.
        if wm_read_exc is None:
            try:
                if wm_corrupt:
                    # D-AC-7: the sidecar was corrupt/unparseable and
                    # restarts from empty — history for every tenant was
                    # lost, so every record this sweep carries the LOUD
                    # note. Appended before the journal event is built, so
                    # it rides the journaled probe-note; staleness
                    # self-heals from this tick onward.
                    record["notes"].append(sidecar.CORRUPT_SIDECAR_LOUD)
                if journal_store_dir is not None:
                    event = _probe_event(
                        tenant_id=tenant_id,
                        vm_id=vm_id,
                        tick_iso=tick_iso,
                        record=record,
                    )
                    journal_err = sidecar.append_journal_note(
                        journal_store_dir, event)
                    if journal_err is not None:
                        # Secondary observability only: note it on the
                        # record and keep sweeping — the record is
                        # collected below and the single bulk write
                        # persists the final notes.
                        record["notes"].append(journal_err)
                pending_writes[tenant_id] = record
            except Exception as exc:  # noqa: BLE001 — observability never wedges the sweep
                # The tenant was already probed; only its observability
                # failed. Note LOUD on the returned record and keep
                # sweeping — S4's staleness rule reads a missing watermark
                # as probe-loop trouble, which is the honest signal for a
                # disk-full/permission failure.
                record["notes"].append(
                    "LOUD: probe observability failed for tenant %r: %s: %s"
                    % (tenant_id, type(exc).__name__, exc)
                )
                errors.append(
                    {
                        "tenant_id": tenant_id,
                        "error": "%s: %s" % (type(exc).__name__, exc),
                    }
                )
        tenants[tenant_id] = record

    if wm_read_exc is not None:
        # #1838: the sidecar-level fault is ONE sweep-level condition —
        # a single errors[] entry (tenant_id None: not attributable to
        # any tenant), not N per-tenant ones. The per-tenant
        # watermark/journal legs were skipped for the whole sweep above;
        # the S4 staleness rule reads the missing watermark as
        # probe-loop trouble, which is the honest signal.
        errors.append(
            {
                "tenant_id": None,
                "error": (
                    "LOUD: sweep probe-watermark sidecar unreadable "
                    "(%s: %s) — per-tenant watermark/journal legs "
                    "skipped for the whole sweep"
                    % (type(wm_read_exc).__name__, wm_read_exc)
                ),
            }
        )

    # The single locked read-modify-write for the whole sweep. The
    # mid-sweep-corruption case (pre-loop hint clean, fresh read inside
    # the RMW corrupt) is handled INSIDE write_sidecar_bulk: the LOUD
    # note is appended to every record before the merge, so it lands in
    # the sidecar and the returned summary.
    if wm_read_exc is None and pending_writes:
        try:
            sidecar.write_sidecar_bulk(
                watermark_path, pending_writes,
                corrupt_note=sidecar.CORRUPT_SIDECAR_LOUD,
                already_noted=wm_corrupt,
            )
        except Exception as exc:  # noqa: BLE001 — observability never wedges the sweep
            # #1842: the bulk write is sweep-level, so its failure is ONE
            # sweep-level errors[] entry (tenant_id None) — the #1838
            # hoisting extended from the read path to the write path. A
            # lock-path ELOOP plant is the same fault class as the
            # sidecar-read ELOOP: one sidecar-level fault is one
            # sweep-level entry, never N per-tenant ones. The LOUD notes
            # stay on every tenant's own record (fail-visible per tenant)
            # — only the errors[] signal is hoisted.
            for tid, rec in pending_writes.items():
                rec["notes"].append(
                    "LOUD: probe observability failed for tenant %r: %s: %s"
                    % (tid, type(exc).__name__, exc)
                )
            errors.append(
                {
                    "tenant_id": None,
                    "error": (
                        "LOUD: sweep probe-watermark sidecar bulk write "
                        "failed (%s: %s) — per-tenant watermark records "
                        "carry the LOUD note" % (type(exc).__name__, exc)
                    ),
                }
            )

    return {
        "tick_at": tick_iso,
        "cadence_s": cadence_s,
        "tenants": tenants,
        "errors": errors,
    }
