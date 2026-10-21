#!/usr/bin/env python3
"""Relay-liveness auto-cadence driver, S1 (issues #1721, #1711 remainder).

Design: ``docs/RELAY_LIVENESS_AUTO_CADENCE_GAP_ANALYSIS.md`` (D-AC-1..D-AC-5,
F-AC-1..F-AC-7). Stdlib-only. This module is the in-repo sync test truth:
it ticks every tenant's R3 wiring
(``hosted/relay_tenant_wiring.drive_tenant``) on the probe cadence.

- D-AC-1 — one clock: the drive cadence IS the probe cadence, the same
  ``RELAY_PROBE_CADENCE_S`` knob ``relay_path_state.cadence_s()`` reads.
  A tick that finds no new reading is a cheap no-op: the wiring's
  re-plan on the fresh record emits nothing observable (idempotent).
- D-AC-2 — drive-only: the driver consumes existing probe history and
  never probes. If the newest probe for the anchor is older than 2x
  cadence at tick time (or missing/unreadable), the tick notes it LOUD
  and drives anyway — the fail-visible forcing function, not a defect.
- D-AC-3 — overlap-safe, not overlap-prevented: ticks are bounded and
  the apply phase is idempotent under the store lock (concurrent ticks
  converge); no leader election, no per-box flock. One tenant's broken
  instrument never wedges the sweep — its tick fails loud and the
  driver moves on.
- D-AC-4 — observability is a watermark + journal, not stdout: every
  tick writes ``{tenant_id, tick_at, applied, events, notes}`` (+ the
  F-AC-7 skip/stale/failed accounting) to the per-tenant last-tick
  watermark — a sidecar JSON next to the tenant store on the
  self-hosted path — and appends one tick-note event per tenant to the
  fleet event journal (the G17 consumer contract). "Anchor moved"
  skips are convergence, not driving: they count separately and never
  read as applied.
- D-AC-5 — this module is parameterized over the ``WiringStore``
  protocol; the S2 plane port reuses this exact tick logic against the
  worker's async D1 (the port is async, this module stays sync by
  design). The fcntl file lock is the in-repo implementation of the
  store boundary.

The ``--tick`` CLI in ``relay_tenant_wiring.py`` stays the
manual/override path — untouched.
"""

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

try:
    import fcntl
except ImportError:  # non-Linux platforms; the estate is Linux
    fcntl = None

from hosted import relay_path_state as rps
from hosted import relay_tenant_wiring as wiring
from hosted import relay_tick_sidecar as sidecar

# Test-compat aliases: the lane's test suite reaches these private names
# (pre-factoring surface). Production code below calls through
# ``sidecar.*`` (late-bound, so monkeypatching ``sidecar.*`` intercepts);
# these aliases exist only so the existing tests keep passing unchanged.
_atomic_write_json_0600 = sidecar.atomic_write_json_0600
_write_watermark_bulk = sidecar.write_sidecar_bulk
_scrub_note = sidecar.scrub_note
_CORRUPT_SIDECAR_LOUD = sidecar.CORRUPT_SIDECAR_LOUD

# D-AC-2: probe history older than this multiple of the cadence at tick
# time is noted LOUD (fail-visible) instead of probed.
STALE_PROBE_FACTOR = 2.0

# Watermark sidecar name: <tenant-store-path> + this suffix (F-AC-5 —
# "a local sidecar next to the tenant store" on the self-hosted path).
WATERMARK_SUFFIX = ".relay-tick-watermarks.json"

# Deterministic namespace for tick-note event ids (uuid5): re-running
# the same tick (same tenant + tick instant) journal-dedups to a no-op
# via append_events' (box_id, event_id) dedup.
_EVENT_NS = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://github.com/ntindle/spark-vm/hosted/relay-auto-driver"
)

_EVENT_SCHEMA = "fleet-event/1"


def watermark_path_for(store_path: str) -> str:
    """Sidecar path for the per-tenant last-tick watermarks."""
    return store_path + WATERMARK_SUFFIX


def _tick_event(
    *, tenant_id: str, anchor_box_id, tick_iso: str, record: dict
) -> dict:
    """One standard-shape fleet event (``fleet-event/1``) for the tick.

    The journal is the G17 consumer contract: ``kind``/``outcome`` are
    the machine-readable signal, the LOUD stale-probe line (when
    present) rides in ``note``. The event id is deterministic over
    (tenant, tick instant) so a retried tick dedups instead of
    double-journaling.
    """
    outcome = (
        "failed"
        if record["failed"]
        else "applied"
        if record["applied"]
        else "skipped"
        if record["skipped"]
        else "noop"
    )
    note = "; ".join(record["notes"]) if record["notes"] else (
        "relay auto-driver tick: %s (events=%d)"
        % (outcome, record["events"])
    )
    return {
        "schema": _EVENT_SCHEMA,
        "event_id": str(
            uuid.uuid5(_EVENT_NS, "relay-tick|%s|%s" % (tenant_id, tick_iso))
        ),
        # box_id is operator-displayed alongside the note; a bidi-laden
        # tenant id would reach the same surfaces, so it gets the same
        # scrub (ids are operator-configured, but the scrub is one line
        # and closes the producer-side hole completely).
        "box_id": (
            sidecar.scrub_note(anchor_box_id)
            if anchor_box_id is not None
            else sidecar.scrub_note(tenant_id)
        ),
        "session_epoch": None,
        "emitted_at": tick_iso,
        "received_at": tick_iso,
        "source": "relay-auto-driver",
        "component": "relay",
        "subcomponent": "auto-driver",
        "subcomponents": None,
        "kind": "relay-tick",
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


def _stale_probe_note(
    *,
    tenant_id: str,
    vm_id: str,
    tick_at: float,
    cadence_s: float,
    latest_probe_fn: Callable[[str], Optional[dict]],
) -> Tuple[bool, Optional[str]]:
    """D-AC-2: (stale: bool, note: Optional[str]) for the anchor's probe.

    Missing, unreadable, or older-than-2x-cadence probe history is
    noted LOUD — the tick drives anyway (drive-only; the probe loop is
    S5's, #1725). S5's scheduled packaging
    (``hosted/relay-probe-driver.{service,timer}``, #1837) ships but
    is inert until the operator enables it past the #1724 gate — until
    a scheduled probe source feeds probe history, loud-stale ticks are
    the steady state by design, and the missing piece is the enabled
    schedule, not the S5 module.
    """
    try:
        probe = latest_probe_fn(vm_id)
    except Exception as exc:  # noqa: BLE001 — fail-visible, not fail-dead
        return True, (
            "LOUD: probe history unreadable for %s (%s: %s) — "
            "drive-only tick, not probing (D-AC-2)" % (vm_id, type(exc).__name__, exc)
        )
    pts = probe.get("ts") if isinstance(probe, dict) else None
    if not isinstance(pts, (int, float)):
        return True, (
            "LOUD: no probe history for %s (tenant %s) — drive-only "
            "tick on a dark instrument, not probing (D-AC-2)" % (vm_id, tenant_id)
        )
    age = tick_at - pts
    if age > STALE_PROBE_FACTOR * cadence_s:
        return True, (
            "LOUD: probe history stale for %s — newest probe %.0fs old "
            "(> 2x cadence %.0fs); drive-only tick, not probing (D-AC-2)"
            % (vm_id, age, cadence_s)
        )
    return False, None


def _tick_one_tenant(
    store: wiring.WiringStore,
    tenant_id: str,
    *,
    tick_at: float,
    tick_iso: str,
    cadence_s: float,
    read_fn: Optional[Callable[[str], dict]],
    box_to_vm: Callable[[str], str],
    journal_timeout_s: Optional[float],
    latest_probe_fn: Callable[[str], Optional[dict]],
) -> Tuple[dict, Optional[str]]:
    """Run one auto tick for a tenant. Returns (record, anchor_box_id).

    Never raises for per-tenant conditions: every ``Exception`` from
    the store read, the anchor selection, the probe check, or the drive
    itself becomes a ``failed=True`` LOUD record (fail-visible, D-AC-3
    — one tenant never wedges the sweep). Only ``BaseException``
    (KeyboardInterrupt/SystemExit) escapes; those are the operator's,
    not the tick's.
    """
    notes: List[str] = []
    stale_probe = False
    anchor_box_id: Optional[str] = None
    failed = False
    applied = False
    skipped = False
    n_events = 0

    try:
        rec = store.get(tenant_id)
        if rec is None:
            # Benign race: the tenant was deleted between tenant_ids()
            # and get(). Not a failure — the next sweep re-lists.
            notes.append(
                "tenant record vanished mid-sweep — no tick run, "
                "next sweep re-lists"
            )
        else:
            anchor = wiring.select_live_anchor(list(rec.boxes.values()))
            if anchor is not None:
                anchor_box_id = anchor.box_id
                vm_id = box_to_vm(anchor_box_id)
                stale_probe, stale_note = _stale_probe_note(
                    tenant_id=tenant_id,
                    vm_id=vm_id,
                    tick_at=tick_at,
                    cadence_s=cadence_s,
                    latest_probe_fn=latest_probe_fn,
                )
                if stale_note is not None:
                    notes.append(stale_note)
            else:
                notes.append(
                    "no live-anchor box — readings observed, nothing driven"
                )

            report = wiring.drive_tenant(
                store,
                tenant_id,
                read_fn=read_fn,
                box_to_vm=box_to_vm,
                journal_timeout_s=journal_timeout_s,
            )
            # Attribute the tick to the drive's own anchor: the
            # pre-drive snapshot's anchor may have moved under us.
            anchor_box_id = report["anchor_box_id"] or anchor_box_id
            for box in report["boxes"]:
                n_events += len(box.get("events", []))
                for note in box.get("notes", []):
                    if note.startswith(wiring.ANCHOR_MOVED_NOTE):
                        skipped = True
            applied = n_events > 0
    except Exception as exc:  # noqa: BLE001 — fail-visible per tenant
        failed = True
        notes.append(
            "LOUD: tick failed for tenant %r: %s: %s — record untouched, "
            "next tick retries" % (tenant_id, type(exc).__name__, exc)
        )

    record = {
        "tenant_id": tenant_id,
        "tick_at": tick_iso,
        "applied": applied,
        "skipped": skipped and not applied,
        "events": n_events,
        "stale_probe": stale_probe,
        "failed": failed,
        "notes": notes,
    }
    return record, anchor_box_id


def tick_all_tenants(
    store: wiring.WiringStore,
    *,
    watermark_path: str,
    journal_store_dir=None,
    read_fn=None,
    box_to_vm=None,
    journal_timeout_s=None,
    now=None,
    latest_probe_fn=None,
) -> dict:
    """Tick every tenant's R3 wiring once (S1 auto-driver, #1721).

    ``store`` is any ``WiringStore``; ``watermark_path`` is the
    sidecar JSON the per-tenant last-tick records land in
    (``watermark_path_for(store_path)`` for the in-repo file store).
    ``journal_store_dir`` (optional) is the fleet estate store dir
    whose ``events.jsonl`` receives one tick-note event per tenant.

    Returns ``{"tick_at", "cadence_s", "tenants": {tenant_id: record},
    "errors": [...]}`` — ``errors`` carries per-tenant observability
    failures (watermark/journal), never drive failures (those are
    ``failed=True`` on the tenant's own record), plus at most one
    sweep-level entry (``tenant_id`` None) when the watermark sidecar
    itself is unreadable (ELOOP plant, #1838), or when the single
    locked bulk write after the drive loop fails (lock-path ELOOP
    plant, disk-full, permission — #1842): the bulk write is
    sweep-level, so its failure is one sweep-level entry, never N
    per-tenant ones. One sidecar-level fault is one sweep-level
    entry, never N per-tenant ones.

    The watermark sidecar gets exactly ONE read-modify-write per sweep
    (#1739): per-tenant records are collected in memory and merged in a
    single locked write after the drive loop, instead of one full
    read-modify-write per tenant (O(N^2) JSON IO on the probe cadence).
    """
    tick_at = time.time() if now is None else now
    tick_iso = sidecar.now_iso(tick_at)
    cadence_s = rps.cadence_s()
    if box_to_vm is None:

        def box_to_vm(box_id: str) -> str:
            return box_id

    if latest_probe_fn is None:
        latest_probe_fn = rps.latest_probe

    # #1739: read the sidecar once up front. The corrupt flag must be
    # known BEFORE the journal events are built, because the D-AC-7
    # LOUD corruption note rides the journaled tick-note (pinned by
    # test_corrupt_watermark_sidecar_restarts_empty). This read is only
    # the hint; the authoritative merge is the single locked
    # read-modify-write after the drive loop, so a concurrent sweeper's
    # records are merged, never lost.
    try:
        _, wm_corrupt = sidecar.read_sidecar_marks(watermark_path)
        wm_read_exc = None
    except OSError as exc:
        # sidecar.read_sidecar_marks raises OSError only for errno.ELOOP: a
        # symlink plant at the sidecar path (#1741). Defer it to the
        # sweep-level handler below (#1838): one sidecar-level fault is
        # one sweep-level errors[] entry, never N per-tenant ones. The
        # sweep still drives every tenant — the watermark simply does
        # not persist this sweep.
        wm_corrupt = False
        wm_read_exc = exc

    tenants: Dict[str, dict] = {}
    errors: List[dict] = []
    pending_writes: Dict[str, dict] = {}
    for tenant_id in store.tenant_ids():
        record, anchor_box_id = _tick_one_tenant(
            store,
            tenant_id,
            tick_at=tick_at,
            tick_iso=tick_iso,
            cadence_s=cadence_s,
            read_fn=read_fn,
            box_to_vm=box_to_vm,
            journal_timeout_s=journal_timeout_s,
            latest_probe_fn=latest_probe_fn,
        )
        # #1838: the per-tenant watermark/journal legs run only when the
        # sidecar itself was readable. A sidecar-level fault (wm_read_exc,
        # the ELOOP plant above) skips these legs for the WHOLE sweep —
        # the single sweep-level errors[] entry appended after the loop
        # is the honest signal, not N per-tenant ones. The drive loop
        # still ran every tenant above.
        if wm_read_exc is None:
            try:
                if wm_corrupt:
                    # F-AC-8 / D-AC-7: the sidecar was corrupt/unparseable
                    # and restarts from empty — history for every tenant
                    # was lost, so every record this sweep carries the
                    # LOUD note (the old per-tenant writes noted it only
                    # on the first tenant's record — an artifact of the
                    # incremental writes, not the contract). The note is
                    # appended before the journal event is built, so it
                    # rides the journaled tick-note; staleness self-heals
                    # from this tick onward.
                    record["notes"].append(sidecar.CORRUPT_SIDECAR_LOUD)
                if journal_store_dir is not None:
                    event = _tick_event(
                        tenant_id=tenant_id,
                        anchor_box_id=anchor_box_id,
                        tick_iso=tick_iso,
                        record=record,
                    )
                    journal_err = sidecar.append_journal_note(journal_store_dir, event)
                    if journal_err is not None:
                        # Secondary observability only: note it on the
                        # record and keep sweeping — the record is
                        # collected below and the single bulk write
                        # persists the final notes.
                        record["notes"].append(journal_err)
                pending_writes[tenant_id] = record
            except Exception as exc:  # noqa: BLE001 — observability never wedges the sweep
                # The tenant was already driven; only its observability
                # failed. Note LOUD on the returned record and keep
                # sweeping — the S4 staleness rule reads a missing watermark
                # as driver trouble, which is the honest signal for a
                # disk-full/permission failure.
                record["notes"].append(
                    "LOUD: tick observability failed for tenant %r: %s: %s"
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
        # the S4 staleness rule reads the missing watermark as driver
        # trouble, which is the honest signal.
        errors.append(
            {
                "tenant_id": None,
                "error": (
                    "LOUD: sweep watermark sidecar unreadable (%s: %s) — "
                    "per-tenant watermark/journal legs skipped for the "
                    "whole sweep" % (type(wm_read_exc).__name__, wm_read_exc)
                ),
            }
        )

    # #1739: the single locked read-modify-write for the whole sweep.
    # The mid-sweep-corruption case (pre-loop hint clean, fresh read
    # inside the RMW corrupt) is handled INSIDE _write_watermark_bulk:
    # the LOUD note is appended to every record before the merge, so it
    # lands in the sidecar and the returned summary. The journal events
    # were already built by then, so that note does not ride the
    # journal — only the pre-loop-corrupt note does.
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
            # stay on every tenant's own record (fail-visible per tenant,
            # D-AC-3) — only the errors[] signal is hoisted.
            for tid, rec in pending_writes.items():
                rec["notes"].append(
                    "LOUD: tick observability failed for tenant %r: %s: %s"
                    % (tid, type(exc).__name__, exc)
                )
            errors.append(
                {
                    "tenant_id": None,
                    "error": (
                        "LOUD: sweep watermark sidecar bulk write failed "
                        "(%s: %s) — per-tenant watermark records carry "
                        "the LOUD note" % (type(exc).__name__, exc)
                    ),
                }
            )

    return {
        "tick_at": tick_iso,
        "cadence_s": cadence_s,
        "tenants": tenants,
        "errors": errors,
    }
