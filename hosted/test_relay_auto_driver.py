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
import tempfile
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
    wm = driver.watermark_path_for(str(tmp_path / "tenants.json"))

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


def test_stale_probe_age_threshold(tmp_path, monkeypatch):
    # Older than 2x cadence -> stale; within -> fresh. The cadence is
    # pinned (D-AC-1: the same knob the probe reads).
    monkeypatch.setenv("RELAY_PROBE_CADENCE_S", "300")
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


def test_store_get_raising_does_not_wedge_sweep(tmp_path):
    # Engineering B1: the fault boundary covers the whole per-tenant
    # body — a store.get raising for one tenant (file deleted
    # mid-sweep) becomes a failed=True LOUD record, not a sweep abort.
    # Neuter check: moving store.get back outside the try lets the
    # FileNotFoundError propagate and fails the sweep-completes
    # assertion.
    inner = ts.TenantStore(str(tmp_path / "tenants.json"))
    inner.create(_tenant_record([_arc("box-a")], "tnt-a"))
    inner.create(_tenant_record([_arc("box-a")], "tnt-b"))

    class FlakyGetStore(wiring.TenantFileWiringStore):
        def get(self, tenant_id):
            if tenant_id == "tnt-a":
                raise FileNotFoundError("store file deleted mid-sweep")
            return super().get(tenant_id)

    store = FlakyGetStore(inner)
    wm = str(tmp_path / "wm.json")
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    rec_a = summary["tenants"]["tnt-a"]
    assert rec_a["failed"] is True
    assert rec_a["applied"] is False
    assert any("LOUD:" in n for n in rec_a["notes"])
    # tnt-b ticked normally through the same sweep.
    assert summary["tenants"]["tnt-b"]["failed"] is False


def test_unreadable_probe_history_noted_loud(tmp_path):
    # D-AC-2's third branch: latest_probe_fn raising (history lock
    # wedged) is fail-visible, not fail-dead — the tick still drives.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    wm = str(tmp_path / "wm.json")

    def boom(vm_id):
        raise OSError("history lock wedged")

    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _down("relay"),
        now=NOW, latest_probe_fn=boom,
    )
    rec = summary["tenants"]["tnt-a"]
    assert rec["stale_probe"] is True
    assert any("LOUD:" in n and "unreadable" in n for n in rec["notes"])
    assert rec["applied"] is True


def test_vanished_tenant_mid_sweep_is_noted_not_failed(tmp_path):
    # Benign race: listed by tenant_ids(), gone by get(). No tick ran,
    # so failed=False — and the note must not claim a skip (QA-3).
    class GhostStore:
        def tenant_ids(self):
            return ["ghost"]

        def get(self, tenant_id):
            return None

        def read_modify_write(self, tenant_id, fn):
            raise AssertionError("must not drive a vanished tenant")

    wm = str(tmp_path / "wm.json")
    summary = driver.tick_all_tenants(
        GhostStore(), watermark_path=wm, read_fn=lambda vm_id: _ok(),
        now=NOW, latest_probe_fn=_fresh_probe,
    )
    rec = summary["tenants"]["ghost"]
    assert rec["failed"] is False
    assert rec["applied"] is False
    assert rec["skipped"] is False
    assert any("vanished mid-sweep" in n for n in rec["notes"])
    assert not any("skipped" in n for n in rec["notes"])


def test_corrupt_watermark_sidecar_restarts_empty(tmp_path):
    # F-AC-8 / D-AC-7: a corrupt sidecar is observability damage, never a
    # reason to skip the tick — the write restarts from empty and the tick
    # lands — but the corruption is fail-visible: the ticking tenant's
    # record carries a LOUD note, persisted in the sidecar and riding the
    # journal event.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    wm = str(tmp_path / "wm.json")
    with open(wm, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    estate = tmp_path / "estate"
    estate.mkdir()
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, journal_store_dir=str(estate),
        read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    rec = summary["tenants"]["tnt-a"]
    assert rec["applied"] is False
    assert any(
        n.startswith("LOUD:") and "corrupt" in n for n in rec["notes"]
    ), rec["notes"]
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert marks["tnt-a"]["tenant_id"] == "tnt-a"
    assert any(
        n.startswith("LOUD:") and "corrupt" in n for n in marks["tnt-a"]["notes"]
    ), marks["tnt-a"]["notes"]
    rows = _journal_rows(str(estate))
    assert len(rows) == 1
    assert rows[0]["kind"] == "relay-tick"
    assert "LOUD:" in rows[0]["note"]
    assert "corrupt" in rows[0]["note"]


def test_missing_watermark_sidecar_first_run_is_silent(tmp_path):
    # The normal first run has no sidecar yet: no history exists to lose,
    # so no LOUD corruption note is emitted — only genuinely corrupt
    # content gets the loud treatment (neuter: folding the missing-file
    # case into the corrupt flag fails this test).
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    wm = str(tmp_path / "wm.json")  # never created
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    rec = summary["tenants"]["tnt-a"]
    assert not any(
        n.startswith("LOUD:") and "corrupt" in n for n in rec["notes"]
    ), rec["notes"]
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert marks["tnt-a"]["tenant_id"] == "tnt-a"


def test_observability_failure_does_not_wedge_sweep(tmp_path):
    # Engineering A2: a watermark write failure (missing parent dir)
    # is fail-soft — the tenant was already driven; the sweep continues
    # and the failure surfaces LOUD in the summary's errors.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-a")],
    })
    wm = str(tmp_path / "no-such-dir" / "wm.json")
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    assert set(summary["tenants"]) == {"tnt-a", "tnt-b"}
    assert len(summary["errors"]) == 2
    assert all(e["tenant_id"] in ("tnt-a", "tnt-b") for e in summary["errors"])
    for tid in ("tnt-a", "tnt-b"):
        rec = summary["tenants"][tid]
        assert rec["failed"] is False  # the drive itself worked
        assert any("observability failed" in n for n in rec["notes"])


def test_watermark_path_for_appends_suffix():
    assert driver.watermark_path_for("/x/tenants.json") == \
        "/x/tenants.json.relay-tick-watermarks.json"


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
    # "relay-down(detail=...)". Neuter check: breaking the store-lock
    # atomicity (both threads load the live record before either saves)
    # makes both reports carry the detail form.
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

    with tempfile.TemporaryDirectory() as td:
        wm = os.path.join(td, "wm.json")
        summary = driver.tick_all_tenants(
            store, watermark_path=wm,
            read_fn=lambda vm_id: _down("box-leg"), now=NOW,
            latest_probe_fn=_fresh_probe,
        )
    rec = summary["tenants"]["tnt-z"]
    assert rec["applied"] is True
    assert store.get("tnt-z").boxes["box-a"].code == "connection-unreachable"


def test_watermark_lock_refuses_symlink_plant(tmp_path):
    # F1 (security sweep 20261018-2259): the sidecar lock serializes
    # read-modify-write across sweep processes — a pre-planted symlink
    # at the lock path must not silently move the flock onto another
    # file (lock-desync / lock-DoS). The tick refuses loudly
    # (fail-visible through the observability handler), the drive
    # itself still works, and the sweep is not wedged.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    wm = str(tmp_path / "wm.json")
    victim = str(tmp_path / "victim.lock")
    with open(victim, "w", encoding="utf-8") as fh:
        fh.write("victim")
    os.symlink(victim, wm + ".lock")
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    rec = summary["tenants"]["tnt-a"]
    assert rec["failed"] is False  # the drive itself worked
    assert any("observability failed" in n for n in rec["notes"])
    assert len(summary["errors"]) == 1
    assert summary["errors"][0]["tenant_id"] == "tnt-a"
    # The victim file was never flocked through: no lock sibling was
    # created behind the plant, and the real watermark was not written.
    assert not os.path.exists(wm)
    with open(victim, encoding="utf-8") as fh:
        assert fh.read() == "victim"


def test_watermark_read_refuses_symlink_plant(tmp_path):
    # #1741: the sidecar read must pin the same O_NOFOLLOW discipline
    # the write path has — a pre-planted symlink at the sidecar path
    # must not feed the plant's bytes into the read-modify-write
    # merge. The read refuses loud (ELOOP -> OSError naming the
    # plant); the victim file is untouched and no watermark lands.
    # Neuter-verified: with plain open(path, "r") the read follows
    # the link and merges the plant's bytes; the OSError that does
    # surface then names the WRITE path, failing the match below.
    wm = str(tmp_path / "wm.json")
    victim = str(tmp_path / "victim.json")
    with open(victim, "w", encoding="utf-8") as fh:
        json.dump({"attacker": {"seed": "poison"}}, fh)
    os.symlink(victim, wm)
    with pytest.raises(OSError, match="refusing to read watermark through symlink"):
        driver._update_watermark(wm, "tnt-a", {"ok": True})
    # The plant never influenced the merge: the victim holds only the
    # attacker's bytes, and the sidecar path is still the plant (no
    # real watermark was written through it).
    with open(victim, encoding="utf-8") as fh:
        assert json.load(fh) == {"attacker": {"seed": "poison"}}
    assert os.path.islink(wm)


# ---------------------------------------------------------------------------
# #1738 — bidi / zero-width display spoofing in journal notes
# ---------------------------------------------------------------------------

_BIDI_OVERRIDES = [chr(cp) for cp in range(0x202A, 0x202E + 1)]
_ISOLATES = [chr(cp) for cp in range(0x2066, 0x2069 + 1)]
_ZERO_WIDTH = ["\u200b", "\u200c", "\u200d", "\ufeff"]


def test_scrub_strips_bidi_overrides():
    # #1738: bidi override controls survived the Cc-only scrub
    # (ord >= 0x20) and could reorder displayed journal text.
    for bidi in _BIDI_OVERRIDES:
        scrubbed = driver._scrub_note("probe stale " + bidi + "ok")
        assert bidi not in scrubbed, hex(ord(bidi))
        assert scrubbed == "probe stale ok"


def test_scrub_strips_zero_width_isolates_and_bom():
    # #1738: zero-width controls, directional isolates, and the BOM
    # are all Cf and must not reach the journal.
    note = "a" + "".join(_ZERO_WIDTH + _ISOLATES) + "b"
    assert driver._scrub_note(note) == "ab"


def test_scrub_strips_rest_of_cf_class():
    # #1738: the fix strips the whole Cf class, not just the
    # enumerated spoofing set — soft hyphen (U+00AD) is display-
    # invisible and has no place in a journal note either.
    assert driver._scrub_note("up\u00addate") == "update"


def test_scrub_keeps_newline_tab_printable_and_emoji():
    # The Cf strip must not eat the two legitimate controls or
    # ordinary text — including non-BMP printable characters.
    note = "line one\nline two\tcolumn \U0001f916"
    assert driver._scrub_note(note) == note


def test_scrub_note_drops_variation_selectors():
    # #1776: the relay lane moves with the fleet scrub — Mn variation
    # selectors are dropped by explicit range (category Mn, not Cf).
    assert driver._scrub_note("a\uFE00b") == "ab"      # VS1
    assert driver._scrub_note("a\uFE0Fb") == "ab"      # VS16
    assert driver._scrub_note("a\U000E0100b") == "ab"  # VS17
    assert driver._scrub_note("a\U000E01EFb") == "ab"  # VS256


def test_scrub_note_keeps_combining_marks():
    # The #1776 drop is range-exact: combining diacritics (the rest of
    # Mn) are legitimate text and pass through.
    assert driver._scrub_note("caf\u0301") == "caf\u0301"


def test_scrub_still_strips_c0_controls():
    # Regression guard on the pre-#1738 behavior: C0 controls other
    # than \n / \t stay stripped.
    assert driver._scrub_note("a\x00b\x07c\x1bd") == "abcd"
    assert driver._scrub_note("a\nb\tc") == "a\nb\tc"


def test_scrub_fail_closed_typing():
    # Non-str input is stringified, never dropped silently.
    assert driver._scrub_note(None) == "None"
    assert driver._scrub_note(42) == "42"


def test_tick_event_note_is_scrubbed():
    # End to end: a hostile producer note riding through _tick_event
    # lands in the journal event with the spoofing characters gone.
    hostile = "stale probe\u202e (reversed!)\u200bok"
    ev = driver._tick_event(
        tenant_id="tnt-a", anchor_box_id=None, tick_iso="2026-10-19T00:00:00+00:00",
        record={"failed": False, "applied": True, "skipped": False,
                "events": 1, "notes": [hostile]},
    )
    assert "\u202e" not in ev["note"] and "\u200b" not in ev["note"]
    assert ev["note"] == "stale probe (reversed!)ok"


def test_scrub_strips_surrogates():
    # Cs: a lone surrogate is never valid text (str.encode('utf-8')
    # raises), so the scrub eats it rather than trusting every
    # downstream writer to escape it.
    assert driver._scrub_note("ok\ud800done") == "okdone"  # true lone surrogate
    assert driver._scrub_note("ok\ud800\udc00done") == "okdone"  # pair halves


def test_scrub_strips_c1_controls_and_del():
    # Security round-1: C1 CSI (U+009B) is a live terminal-escape
    # introducer on ECMA-48 terminals — the pre-#1738 scrub kept C1
    # (ord >= 0x20), so "terminal-escape injection is handled" was
    # only true for 7-bit ESC. The whole Cc class goes now.
    # the CSI introducer is gone; the printable payload stays (a
    # payload without an introducer is inert text).
    assert driver._scrub_note("a\u009b2Jb") == "a2Jb"  # C1 CSI + sequence
    assert driver._scrub_note("a\u0085b") == "ab"  # NEL
    assert driver._scrub_note("a\x7fb") == "ab"  # DEL


def test_scrub_strips_line_paragraph_separators():
    # Security round-1: U+2028/U+2029 are line terminators on
    # JS-rendered surfaces — a hostile note could forge journal lines.
    assert driver._scrub_note("a\u2028b\u2029c") == "abc"


def test_tick_event_box_id_is_scrubbed():
    # box_id rides the same operator displays as the note, so it
    # gets the same scrub.
    ev = driver._tick_event(
        tenant_id="tnt-\u202ea", anchor_box_id=None,
        tick_iso="2026-10-19T00:00:00+00:00",
        record={"failed": False, "applied": True, "skipped": False,
                "events": 1, "notes": []},
    )
    assert ev["box_id"] == "tnt-a"


# ---------------------------------------------------------------------------
# #1739 — one watermark read-modify-write per sweep (not per tenant)
# ---------------------------------------------------------------------------


def test_bulk_watermark_single_write_per_sweep(tmp_path, monkeypatch):
    # #1739: one sweep over N tenants performs exactly ONE watermark
    # sidecar write. The old per-tenant _update_watermark re-read the
    # entire sidecar JSON and rewrote it atomically for every tenant —
    # N full read-modify-write cycles of a file holding N records
    # (O(N^2) JSON IO on the probe cadence). Neuter check: the
    # pre-#1739 per-tenant loop calls _atomic_write_json_0600 three
    # times for three tenants, failing the == 1 assertion.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-b")],
        "tnt-c": [_arc("box-c")],
    })
    wm = str(tmp_path / "wm.json")
    writes = []
    real_write = driver._atomic_write_json_0600

    def counting_write(path, obj):
        if os.path.abspath(path) == os.path.abspath(wm):
            writes.append(path)
        return real_write(path, obj)

    monkeypatch.setattr(driver, "_atomic_write_json_0600", counting_write)
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    assert len(writes) == 1, writes
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert sorted(marks) == ["tnt-a", "tnt-b", "tnt-c"]
    for tid in ("tnt-a", "tnt-b", "tnt-c"):
        assert marks[tid]["tenant_id"] == tid
        assert summary["tenants"][tid]["tenant_id"] == tid
        assert summary["tenants"][tid]["failed"] is False
    assert summary["errors"] == []


def test_bulk_watermark_corrupt_notes_every_tenant(tmp_path):
    # #1739 deliberate change, pinned: the D-AC-7 LOUD corruption note
    # describes sidecar-level history loss, which hits every tenant
    # equally — so every record this sweep carries it. (The old
    # per-tenant writes noted it only on the first tenant's record, an
    # artifact of the incremental writes, not the contract.) The note
    # still rides every journaled tick-note, and the persisted sidecar
    # restarts from empty with exactly this sweep's tenants.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-b")],
    })
    wm = str(tmp_path / "wm.json")
    with open(wm, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    estate = tmp_path / "estate"
    estate.mkdir()
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, journal_store_dir=str(estate),
        read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    for tid in ("tnt-a", "tnt-b"):
        rec = summary["tenants"][tid]
        assert any(
            n.startswith("LOUD:") and "corrupt" in n for n in rec["notes"]
        ), rec["notes"]
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert sorted(marks) == ["tnt-a", "tnt-b"]
    rows = _journal_rows(str(estate))
    assert len(rows) == 2
    assert all(
        "LOUD:" in r["note"] and "corrupt" in r["note"] for r in rows
    )


def test_bulk_watermark_symlink_plant_still_drives(tmp_path):
    # #1741 preserved under the #1739 bulk write: a symlink plant at
    # the sidecar path fails loud per tenant, but the sweep still
    # drives every tenant (observability never wedges the sweep) and
    # writes nothing through the plant.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-b")],
    })
    wm = str(tmp_path / "wm.json")
    victim = str(tmp_path / "victim.json")
    with open(victim, "w", encoding="utf-8") as fh:
        json.dump({"attacker": {"seed": "poison"}}, fh)
    os.symlink(victim, wm)
    estate = tmp_path / "estate"
    estate.mkdir()
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, journal_store_dir=str(estate),
        read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    # Both tenants were driven (no drive failure), and each record
    # carries the LOUD observability failure naming the plant.
    for tid in ("tnt-a", "tnt-b"):
        rec = summary["tenants"][tid]
        assert rec["failed"] is False
        assert any(
            "observability failed" in n and "symlink" in n
            for n in rec["notes"]
        ), rec["notes"]
    assert len(summary["errors"]) == 2
    # Nothing was written through the plant: the victim is untouched
    # and the sidecar path is still the link.
    with open(victim, encoding="utf-8") as fh:
        assert json.load(fh) == {"attacker": {"seed": "poison"}}
    assert os.path.islink(wm)


def test_write_watermark_bulk_notes_mid_sweep_corruption(tmp_path):
    # Unit contract for the mid-sweep-corruption path: when the fresh
    # read inside the bulk RMW finds a corrupt sidecar the caller had
    # NOT already noted, the LOUD note is appended inside the locked
    # RMW — so it lands in the persisted sidecar, not just in-memory.
    # (A past revision appended after the write returned; the note
    # never reached the disk.)
    wm = str(tmp_path / "wm.json")
    with open(wm, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    rec = {"tenant_id": "tnt-a", "notes": []}
    corrupt = driver._write_watermark_bulk(
        wm, {"tnt-a": rec},
        corrupt_note=driver._CORRUPT_SIDECAR_LOUD,
        already_noted=False,
    )
    assert corrupt is True
    assert driver._CORRUPT_SIDECAR_LOUD in rec["notes"]
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert driver._CORRUPT_SIDECAR_LOUD in marks["tnt-a"]["notes"]

    # already_noted=True: the caller's pre-loop note stands — no
    # duplicate appended by the bulk write.
    with open(wm, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    rec2 = {"tenant_id": "tnt-a", "notes": [driver._CORRUPT_SIDECAR_LOUD]}
    corrupt = driver._write_watermark_bulk(
        wm, {"tnt-a": rec2},
        corrupt_note=driver._CORRUPT_SIDECAR_LOUD,
        already_noted=True,
    )
    assert corrupt is True
    assert rec2["notes"].count(driver._CORRUPT_SIDECAR_LOUD) == 1


def test_bulk_watermark_mid_sweep_corruption_noted_on_disk(tmp_path, monkeypatch):
    # Tick-level mid-sweep corruption: the pre-loop hint read sees a
    # clean sidecar, but the fresh read inside the bulk RMW finds it
    # corrupt (concurrent writer / disk event between the two reads).
    # The LOUD note must land in the persisted sidecar AND the returned
    # records. It does NOT ride the journaled tick-notes — those were
    # built before the bulk write (documented divergence).
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-b")],
    })
    wm = str(tmp_path / "wm.json")
    with open(wm, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    estate = tmp_path / "estate"
    estate.mkdir()
    real_read = driver._read_watermark_marks
    calls = []

    def scripted_read(path):
        calls.append(path)
        if len(calls) == 1:
            return {}, False  # pre-loop hint: clean
        return real_read(path)  # bulk write's fresh read: corrupt

    monkeypatch.setattr(driver, "_read_watermark_marks", scripted_read)
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, journal_store_dir=str(estate),
        read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    assert len(calls) == 2
    for tid in ("tnt-a", "tnt-b"):
        rec = summary["tenants"][tid]
        assert any(
            n.startswith("LOUD:") and "corrupt" in n for n in rec["notes"]
        ), rec["notes"]
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert sorted(marks) == ["tnt-a", "tnt-b"]
    for tid in ("tnt-a", "tnt-b"):
        assert any(
            n.startswith("LOUD:") and "corrupt" in n
            for n in marks[tid]["notes"]
        ), marks[tid]["notes"]
    # The journal events were built before the bulk write saw the
    # corruption, so they do not carry the note.
    rows = _journal_rows(str(estate))
    assert len(rows) == 2
    assert all("corrupt" not in r["note"] for r in rows)


def test_bulk_watermark_write_failure_notes_every_tenant(tmp_path, monkeypatch):
    # A failed bulk write (disk full / permission) notes LOUD on every
    # tenant's record and keeps the sweep alive — observability never
    # wedges the sweep, and nothing is silently dropped.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-b")],
    })
    wm = str(tmp_path / "wm.json")
    real_write = driver._atomic_write_json_0600

    def failing_write(path, obj):
        if os.path.abspath(path) == os.path.abspath(wm):
            raise OSError("disk full (test)")
        return real_write(path, obj)

    monkeypatch.setattr(driver, "_atomic_write_json_0600", failing_write)
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    for tid in ("tnt-a", "tnt-b"):
        rec = summary["tenants"][tid]
        assert rec["failed"] is False  # the drive itself succeeded
        assert any(
            "observability failed" in n and "disk full" in n
            for n in rec["notes"]
        ), rec["notes"]
    assert len(summary["errors"]) == 2
    assert all(e["tenant_id"] in ("tnt-a", "tnt-b")
               for e in summary["errors"])


def test_bulk_watermark_merges_over_preseeded_sidecar(tmp_path):
    # QA suggestion 2: the "concurrent sweeper's records are merged,
    # never lost" claim, pinned. A valid sidecar pre-seeded with a
    # third tenant's record (as a concurrent sweep would have left it)
    # survives this sweep's bulk merge untouched.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-b")],
    })
    wm = str(tmp_path / "wm.json")
    preseed = {"tnt-z": {"tenant_id": "tnt-z", "tick_at": "old",
                         "notes": ["pre-existing"]}}
    with open(wm, "w", encoding="utf-8") as fh:
        json.dump(preseed, fh)
    summary = driver.tick_all_tenants(
        store, watermark_path=wm, read_fn=lambda vm_id: _ok(), now=NOW,
        latest_probe_fn=_fresh_probe,
    )
    assert summary["errors"] == []
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert marks["tnt-z"] == preseed["tnt-z"]
    assert sorted(marks) == ["tnt-a", "tnt-b", "tnt-z"]
