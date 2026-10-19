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

import errno
import json
import os
import tempfile
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


def _now_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _scrub_note(text: str) -> str:
    """Strip control characters from a journal note (fail-closed typing)."""
    if not isinstance(text, str):
        text = str(text)
    return "".join(
        ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 0x20
    )


def _atomic_write_json_0600(path: str, obj: dict) -> None:
    """Write *obj* as JSON to *path* atomically, mode 0600.

    Temp file (O_EXCL via mkstemp, 0600 by construction) + fsync +
    os.replace. A symlink AT the destination fails loud instead of
    redirecting the watermark into an arbitrary file.
    """
    if os.path.islink(path):
        raise OSError("refusing to write through symlink: %r" % (path,))
    parent = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=".tmp-relay-ticks-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _open_sidecar_lock(lock_path: str):
    """Open the watermark sidecar lock without following symlinks.

    The lock serializes the sidecar's read-modify-write across
    processes. A pre-planted symlink at the lock path would silently
    move the flock onto another file (lock-desync across sweep
    processes, or a lock-DoS via a permanently-held lock) — the same
    plant class the gate lane pins O_NOFOLLOW for (#1720). O_NOFOLLOW
    refuses the plant loudly (ELOOP); the caller's observability
    handler turns that into a LOUD record, never a silent wedge.
    """
    flags = os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW
    fd = os.open(lock_path, flags, 0o600)
    try:
        return os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise


def _read_sidecar_nofollow(path: str) -> dict:
    """Read the JSON sidecar without following symlinks (#1741).

    The write path (``_atomic_write_json_0600``) refuses a symlink at the
    destination loudly; the read pins the same discipline so a
    pre-planted symlink cannot influence which bytes feed the
    read-modify-write merge. O_NOFOLLOW refuses the plant with ELOOP
    (fail-loud); a missing file is still FileNotFoundError (the normal
    first run).
    """
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        fh = os.fdopen(fd, "r", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with fh:
        return json.load(fh)


def _update_watermark(path: str, tenant_id: str, record: dict) -> bool:
    """Read-modify-write the watermark sidecar under a sidecar lock.

    Corrupt/unparseable sidecar content restarts from empty — a corrupt
    watermark is observability damage, never a reason to skip the tick
    (staleness self-heals: the current tenant record is written fresh).

    Returns True when the sidecar was corrupt/unparseable and history
    restarted from empty, so the caller can note it LOUD on the record
    (D-AC-7 fail-visible); False otherwise — a clean read, or a missing
    file (the normal first run: no history to lose).

    #1741: a symlink at the sidecar path is a plant, not corruption —
    ELOOP from the O_NOFOLLOW read is re-raised loud (same as the
    write-path refusal), never restarted-from-empty over.
    """
    lock_path = path + ".lock"
    corrupt = False
    with _open_sidecar_lock(lock_path) as lf:
        if fcntl is not None:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            try:
                marks = _read_sidecar_nofollow(path)
                if not isinstance(marks, dict):
                    raise ValueError("sidecar content is not a JSON object")
            except FileNotFoundError:
                # Normal first run: no history to lose, nothing to say.
                marks = {}
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    # #1741: symlink plant — refuse loud, like the
                    # write path. A plant must never be restarted
                    # from empty over (that would silently discard
                    # the evidence of the plant). errno is preserved
                    # so a handler can distinguish a plant from a
                    # disk error programmatically.
                    raise OSError(
                        errno.ELOOP,
                        "refusing to read watermark through symlink: %r"
                        % (path,),
                    ) from exc
                # Corrupt/unreadable content: restart from empty, but
                # fail-visible per D-AC-7 — the caller notes it LOUD.
                marks = {}
                corrupt = True
            except ValueError:
                # Corrupt/unreadable content: restart from empty, but
                # fail-visible per D-AC-7 — the caller notes it LOUD.
                marks = {}
                corrupt = True
            marks[tenant_id] = record
            _atomic_write_json_0600(path, marks)
        finally:
            if fcntl is not None:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    return corrupt


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
        "box_id": anchor_box_id if anchor_box_id is not None else tenant_id,
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
        "note": _scrub_note(note),
    }


def _append_journal_note(journal_store_dir: str, event: dict) -> Optional[str]:
    """Append one tick-note event to the fleet event journal.

    Returns an error string (not raised): the watermark is the primary
    S4 input, the journal is secondary — a wedged journal must not
    wedge the wiring sweep. The fleet ``events`` module is imported
    lazily so this module stays import-light; it is stdlib-only, so
    the import never leaves the stdlib boundary.
    """
    try:
        from fleet import events as fleet_events

        _, _, err = fleet_events.append_events(journal_store_dir, [event])
        return err
    except Exception as exc:  # noqa: BLE001 — journal is secondary
        return "journal append failed: %s: %s" % (type(exc).__name__, exc)


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
    S5's problem, #1725). Until S5 ships, loud-stale ticks are the
    steady state by design.
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
    ``failed=True`` on the tenant's own record).
    """
    tick_at = time.time() if now is None else now
    tick_iso = _now_iso(tick_at)
    cadence_s = rps.cadence_s()
    if box_to_vm is None:

        def box_to_vm(box_id: str) -> str:
            return box_id

    if latest_probe_fn is None:
        latest_probe_fn = rps.latest_probe

    tenants: Dict[str, dict] = {}
    errors: List[dict] = []
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
        try:
            sidecar_corrupt = _update_watermark(watermark_path, tenant_id, record)
            if sidecar_corrupt:
                # F-AC-8 / D-AC-7: the sidecar was corrupt/unparseable and
                # restarted from empty — history for other tenants was lost.
                # Note it LOUD on the record (persisted and journaled),
                # never silent; staleness self-heals from this tick onward.
                record["notes"].append(
                    "LOUD: watermark sidecar was corrupt/unparseable — "
                    "restarted from empty; prior per-tenant last-tick "
                    "history lost, staleness self-heals from this tick"
                )
                _update_watermark(watermark_path, tenant_id, record)
            if journal_store_dir is not None:
                event = _tick_event(
                    tenant_id=tenant_id,
                    anchor_box_id=anchor_box_id,
                    tick_iso=tick_iso,
                    record=record,
                )
                journal_err = _append_journal_note(journal_store_dir, event)
                if journal_err is not None:
                    # Secondary observability only: note it on the
                    # record (the watermark already landed) and keep
                    # sweeping.
                    record["notes"].append(journal_err)
                    _update_watermark(watermark_path, tenant_id, record)
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

    return {
        "tick_at": tick_iso,
        "cadence_s": cadence_s,
        "tenants": tenants,
        "errors": errors,
    }
