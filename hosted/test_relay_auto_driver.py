#!/usr/bin/env python3
"""S1 auto-driver tests (issue #1721): ``hosted/relay_auto_driver.py``.

Covers the acceptance: the tick-all-tenants loop drives the REAL R3
wiring (``drive_tenant``) with a fake producer (``read_fn`` seam) —
down readings suspend, ok readings are cheap no-ops; the stale-probe
loud note (D-AC-2); skip-vs-applied watermark accounting (F-AC-7);
one tenant's broken instrument never wedges the sweep (D-AC-3); the
fleet-journal tick notes (D-AC-4); and the D-PP-2 protocol conformance
fixtures — the apply-phase convergence cases replayed against a
non-file ``WiringStore`` implementation, proving the protocol is a real
boundary rather than a leaky abstraction over the JSON store.

Style: plain functions + small builders, mirroring
``test_relay_tenant_wiring.py``. Every test asserts a concrete
transition or record — none pass vacuously (each was neuter-verified:
it fails on the pre-fix behavior and passes with the fix; see the
module docstring notes per test).
"""

import copy
import json
import os
import stat
import threading
import time

import pytest

from hosted import relay_auto_driver as driver
from hosted import relay_path_state as rps
from hosted import relay_tenant_wiring as wiring
from hosted import tenant_status as ts

NOW = 1790000000.0  # fixed tick instant for deterministic watermarks/ids


# ---------------------------------------------------------------------------
# Builders


def _arc(box_id="box-a", code="live", created_at="2026-10-01T00:00:00Z",
         **kw):
    kw.setdefault("relay_reachable", True)
    kw.setdefault("provider_running", True)
    return ts.BoxArc(box_id=box_id, created_at=created_at, code=code, **kw)


def _reading(state, sub_code=None, probe="path_ok", journal="active"):
    return {
        "vm_id": "box-a",
        "state": state,
        "sub_code": sub_code,
        "reason": "test reading",
        "probe": probe,
        "journal": journal,
    }


def _down(sub_code):
    return _reading(rps.STATE_DOWN, sub_code=sub_code, probe="relay_defect")


def _ok():
    return _reading(rps.STATE_OK)


def _tenant_record(boxes, tenant_id="tnt_test"):
    return ts.TenantRecord(
        tenant_id=tenant_id,
        stage=2,
        approvals_url="https://approve.example/a/tnt_test",
        boxes={b.box_id: b for b in boxes},
    )


def _wired_store(tmp_path, tenants):
    """Concrete store wrapped in the protocol adapter, pre-populated."""
    store = ts.TenantStore(str(tmp_path / "tenants.json"))
    for tenant_id, boxes in tenants.items():
        store.create(_tenant_record(boxes, tenant_id))
    return wiring.TenantFileWiringStore(store)


def _fresh_probe(vm_id):
    return {"ts": NOW - 10.0, "vm_id": vm_id, "outcome": "path_ok"}


def _journal_rows(estate_dir):
    path = os.path.join(estate_dir, "events.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ---------------------------------------------------------------------------
# Tick-all loop against the real wiring


def test_tick_all_drives_down_reading_through_real_wiring(tmp_path):
    # Two tenants, one down one ok: the down tenant's anchor suspends
    # (rule 6, real wiring), the ok tenant is a cheap no-op. Neuter
    # check: bypassing drive_tenant (report fabricated) leaves the
    # record live and fails the suspension assertion.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-a")],
    })
    estate = tmp_path / "estate"
    estate.mkdir()
    wm = str(tmp_path / "tenants.json.relay-tick-watermarks.json")

    def read_fn(vm_id):
        return _down("relay")

    summary = driver.tick_all_tenants(
        store, watermark_path=wm, journal_store_dir=str(estate),
        read_fn=read_fn, now=NOW, latest_probe_fn=_fresh_probe,
    )
    rec_a = summary["tenants"]["tnt-a"]
    assert rec_a["applied"] is True
    assert rec_a["events"] == 1
    assert rec_a["failed"] is False
    assert rec_a["stale_probe"] is False
    rec_b = summary["tenants"]["tnt-b"]
    assert rec_b["applied"] is True
    assert rec_b["events"] == 1
    # The real wiring ran: each anchor's arc suspended with the latch.
    for tid in ("tnt-a", "tnt-b"):
        raw = store.get(tid)
        assert raw.boxes["box-a"].code == "connection-unreachable"
        assert raw.boxes["box-a"].latched == "live"

    # Watermark sidecar: per-tenant last-tick records, tick instant pinned.
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert marks["tnt-a"]["tick_at"] == summary["tick_at"]
    assert marks["tnt-a"]["applied"] is True
    assert marks["tnt-b"]["applied"] is True
    assert set(marks["tnt-a"]) >= {
        "tenant_id", "tick_at", "applied", "events", "notes",
    }

    # Journal: one tick-note event per tenant, standard shape.
    rows = _journal_rows(str(estate))
    assert len(rows) == 2
    outcomes = set()
    for row in rows:
        assert row["schema"] == "fleet-event/1"
        assert row["kind"] == "relay-tick"
        assert row["trigger"] == "scheduled"
        assert row["source"] == "relay-auto-driver"
        # box_id is the anchor box (both tenants' anchor is box-a).
        assert row["box_id"] == "box-a"
        outcomes.add(row["outcome"])
    assert outcomes == {"applied"}

    # Deterministic event ids: re-ticking the same instant dedups.
    driver.tick_all_tenants(
        store, watermark_path=wm, journal_store_dir=str(estate),
        read_fn=read_fn, now=NOW, latest_probe_fn=_fresh_probe,
    )
    assert len(_journal_rows(str(estate))) == 2


def test_ok_reading_tick_is_cheap_noop(tmp_path):
    # No new reading: the re-plan emits nothing observable, the tick
    # still watermarks (observability is per-tick, not per-change).
    # Neuter check: counting a no-event tick as applied fails.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    wm = str(tmp_path / "wm.json")
    for _ in range(2):
        summary = driver.tick_all_tenants(
            store, watermark_path=wm, read_fn=lambda vm_id: _ok(),
            now=NOW, latest_probe_fn=_fresh_probe,
        )
    rec = summary["tenants"]["tnt-a"]
    assert rec["applied"] is False
    assert rec["events"] == 0
    assert rec["skipped"] is False
    raw = store.get("tnt-a")
    assert raw.boxes["box-a"].code == "live"
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert marks["tnt-a"]["tick_at"] == summary["tick_at"]


def test_stale_probe_noted_loud_and_still_drives(tmp_path):
    # D-AC-2: no probe history -> LOUD note, and the tick drives
    # anyway (drive-only; the probe loop is S5's problem). Neuter
    # check: _stale_probe_note always returning (False, None) drops
    # the LOUD line and fails.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    estate = tmp_path / "estate"
    estate.mkdir()
    wm = str(tmp_path / "wm.json")
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, journal_store_dir=str(estate),
        read_fn=lambda vm_id: _down("relay"), now=NOW,
        latest_probe_fn=lambda vm_id: None,
    )
    rec = summary["tenants"]["tnt-a"]
    assert rec["stale_probe"] is True
    assert any(n.startswith("LOUD:") for n in rec["notes"])
    # Still drove: the down reading suspended the anchor.
    assert rec["applied"] is True
    raw = store.get("tnt-a")
    assert raw.boxes["box-a"].code == "connection-unreachable"
    rows = _journal_rows(str(estate))
    assert len(rows) == 1
    assert rows[0]["outcome"] == "applied"
    assert "LOUD:" in rows[0]["note"]


def test_stale_probe_age_threshold(tmp_path):
    # Older than 2x cadence -> stale; within -> fresh. The cadence is
    # the shipped 300s default (D-AC-1: same knob as the probe).
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    wm = str(tmp_path / "wm.json")
    old = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=lambda vm_id: {"ts": NOW - 10_000.0},
    )
    assert old["tenants"]["tnt-a"]["stale_probe"] is True
    fresh = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=lambda vm_id: {"ts": NOW - 10.0},
    )
    assert fresh["tenants"]["tnt-a"]["stale_probe"] is False


def test_anchor_moved_skip_counted_separately(tmp_path):
    # F-AC-7: an anchor-moved tick is convergence, not driving — it
    # must never read as applied. Neuter check: applied = events > 0
    # without the skip flag fails the skipped assertion.
    inner = ts.TenantStore(str(tmp_path / "tenants.json"))
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    inner.create(_tenant_record([a, b]))
    store = wiring.TenantFileWiringStore(inner)
    wm = str(tmp_path / "wm.json")

    def read_and_move(vm_id):
        if vm_id == "box-a":
            rec = inner.get("tnt_test")
            rec.boxes["box-a"].code = "provisioning"
            inner.save(rec)
        return _down("cert")

    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=read_and_move, now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    rec = summary["tenants"]["tnt_test"]
    assert rec["applied"] is False
    assert rec["skipped"] is True
    assert rec["events"] == 0
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert marks["tnt_test"]["skipped"] is True
    assert marks["tnt_test"]["applied"] is False


def test_broken_anchor_instrument_does_not_wedge_sweep(tmp_path):
    # D-AC-3: one tenant's broken instrument fails its tick LOUD; the
    # sweep continues. Neuter check: letting the exception propagate
    # fails the sweep-completes assertion.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-a")],
    })
    wm = str(tmp_path / "wm.json")

    calls = {"n": 0}

    def read_fn(vm_id):
        calls["n"] += 1
        # tnt-a is ticked first (sorted tenant ids); fail only it.
        if calls["n"] == 1:
            raise RuntimeError("instrument exploded")
        return _ok()

    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=read_fn, now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    rec_a = summary["tenants"]["tnt-a"]
    assert rec_a["failed"] is True
    assert rec_a["applied"] is False
    assert any("LOUD:" in n for n in rec_a["notes"])
    # The sweep continued: tnt-b ticked and watermarked.
    rec_b = summary["tenants"]["tnt-b"]
    assert rec_b["failed"] is False
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert set(marks) == {"tnt-a", "tnt-b"}


def test_watermark_sidecar_is_atomic_0600(tmp_path):
    # The sidecar is operator-readable state: 0600, valid JSON, and a
    # symlink at the destination fails loud instead of redirecting.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    wm = str(tmp_path / "wm.json")
    driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    mode = stat.S_IMODE(os.stat(wm).st_mode)
    assert mode == 0o600
    with open(wm, encoding="utf-8") as fh:
        assert json.load(fh)["tnt-a"]["tenant_id"] == "tnt-a"

    link = str(tmp_path / "link.json")
    os.symlink(wm, link)
    with pytest.raises(OSError):
        driver._atomic_write_json_0600(link, {"x": 1})


def test_journal_disabled_by_default(tmp_path):
    # No journal dir -> no journal touch, watermark still lands.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    wm = str(tmp_path / "wm.json")
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    assert summary["tenants"]["tnt-a"]["applied"] is False
    assert not os.path.exists(str(tmp_path / "estate" / "events.jsonl"))


# ---------------------------------------------------------------------------
# Store-protocol seam


def test_adapter_implements_protocol_over_concrete_store(tmp_path):
    # TenantFileWiringStore is the in-repo WiringStore: tenant_ids,
    # get, and read_modify_write all delegate to the concrete store
    # (this is the single sanctioned _mutate call — #1734's
    # drive_tenant half).
    inner = ts.TenantStore(str(tmp_path / "tenants.json"))
    inner.create(_tenant_record([_arc("box-a")], "tnt-a"))
    inner.create(_tenant_record([_arc("box-a")], "tnt-b"))
    adapter = wiring.TenantFileWiringStore(inner)
    assert adapter.tenant_ids() == ["tnt-a", "tnt-b"]
    assert adapter.get("tnt-a").tenant_id == "tnt-a"
    assert adapter.get("missing") is None
    seen = []

    def fn(rec):
        seen.append(rec.tenant_id)

    reread = adapter.read_modify_write("tnt-a", fn)
    assert seen == ["tnt-a"]
    assert reread.tenant_id == "tnt-a"


class FakeWiringStore:
    """In-memory WiringStore (D-PP-2 conformance fixture).

    Implements the protocol with its own threading lock — no JSON
    file, no fcntl. If drive_tenant secretly depends on the concrete
    store (a second private reach), these tests fail: that is the
    point.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._recs = {}

    def create(self, rec):
        with self._lock:
            self._recs[rec.tenant_id] = copy.deepcopy(rec)

    def put(self, tenant_id, rec):
        """Test-only: replace the stored record (simulates a mover)."""
        with self._lock:
            self._recs[tenant_id] = copy.deepcopy(rec)

    # -- WiringStore protocol --
    def get(self, tenant_id):
        with self._lock:
            rec = self._recs.get(tenant_id)
            return None if rec is None else copy.deepcopy(rec)

    def read_modify_write(self, tenant_id, fn):
        with self._lock:
            rec = self._recs.get(tenant_id)
            if rec is None:
                raise ts.TenantStatusError("no tenant record: %r" % (tenant_id,))
            working = copy.deepcopy(rec)
            fn(working)
            self._recs[tenant_id] = working
            return copy.deepcopy(working)

    def tenant_ids(self):
        with self._lock:
            return sorted(self._recs)


def test_protocol_concurrent_ticks_converge():
    # D-PP-2: the apply-phase convergence case replayed against the
    # protocol — two overlapping ticks on the same tenant converge to
    # ONE rule-6 entry, never corrupt. The loser re-selects the anchor
    # from the fresh (now suspended) record inside the store lock: its
    # re-plan takes the already-suspended branch — the detail-less
    # boolean-flip form "relay-down", never a second
    # "relay-down(detail=...)". Neuter check: dropping the apply-phase
    # re-selection guard makes both reports carry the detail form.
    store = FakeWiringStore()
    store.create(_tenant_record([_arc("box-a")], "tnt-x"))

    def slow_down(vm_id):
        time.sleep(0.05)  # force the read phases to overlap
        return _down("relay")

    reports = []
    errors = []

    def tick():
        try:
            reports.append(
                wiring.drive_tenant(store, "tnt-x", read_fn=slow_down)
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=tick) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors
    assert len(reports) == 2
    forms = sorted(
        event
        for report in reports
        for box in report["boxes"]
        for event in box.get("events", [])
    )
    # Exactly one rule-6 entry (the detail form); the loser's re-plan
    # on the fresh suspended record is the idempotent boolean flip
    # (D-AC-3/D-RL34-3a) — state no-op, never a second suspension.
    assert forms == ["relay-down", "relay-down(detail='relay')"]
    final = store.get("tnt-x")
    assert final.boxes["box-a"].code == "connection-unreachable"
    assert final.boxes["box-a"].detail == "relay"
    assert final.boxes["box-a"].latched == "live"
    assert final.boxes["box-a"].relay_reachable is False


def test_protocol_anchor_moved_skip():
    # D-PP-2: the anchor-moved skip replayed against the protocol —
    # the stale reading is never applied through a non-file store.
    store = FakeWiringStore()
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    store.create(_tenant_record([a, b], "tnt-y"))

    def read_and_move(vm_id):
        if vm_id == "box-a":
            rec = store.get("tnt-y")
            rec.boxes["box-a"].code = "provisioning"
            store.put("tnt-y", rec)
        return _down("cert")

    report = wiring.drive_tenant(store, "tnt-y", read_fn=read_and_move)
    by_box = {r["box_id"]: r for r in report["boxes"]}
    assert by_box["box-a"]["events"] == []
    assert any("next tick" in n for n in by_box["box-a"]["notes"])
    final = store.get("tnt-y")
    assert final.boxes["box-a"].code == "provisioning"
    assert final.boxes["box-a"].relay_reachable is True


def test_tick_all_tenants_drives_protocol_store():
    # The driver itself is protocol-pure: it ticks a non-file store.
    store = FakeWiringStore()
    store.create(_tenant_record([_arc("box-a")], "tnt-z"))
    import tempfile as _tf

    with _tf.TemporaryDirectory() as td:
        wm = os.path.join(td, "wm.json")
        summary = driver.tick_all_tenants(
            store, watermark_path=wm,
            read_fn=lambda vm_id: _down("box-leg"), now=NOW,
            latest_probe_fn=_fresh_probe,
        )
    rec = summary["tenants"]["tnt-z"]
    assert rec["applied"] is True
    assert store.get("tnt-z").boxes["box-a"].code == "connection-unreachable"
