#!/usr/bin/env python3
"""S5 probe-driver tests (issue #1725): ``hosted/relay_probe_driver.py``.

Covers the acceptance: probe history advances on the cadence while a
post-``live`` arc exists (the REAL ``maybe_probe`` with a stubbed dial
prober); stand-down on suspended/destroyed and on no post-``live`` arc
(D-RL2-2); the F-AC-2 bundle-supply fork — bundles are caller-supplied
via ``bundle_fn``, never persisted (D-RL2-3 audit pin); one tenant's
broken supplier never wedges the sweep (D-AC-3); the probe watermark
sidecar + fleet-journal probe notes (the loop's own observability).

Style: plain functions + small builders, mirroring
``test_relay_auto_driver.py``. Every test asserts a concrete
transition or record — none pass vacuously (each was neuter-verified:
it fails with the behavior neutered and passes with the fix).
"""

import json
import os

from hosted import relay_path_state as rps
from hosted import relay_probe_driver as probe
from hosted import relay_tenant_wiring as wiring
from hosted import relay_tick_sidecar as sidecar
from hosted import tenant_status as ts
import hosted.relay_dial_prober as prober

NOW = 1790000000.0  # fixed tick instant for deterministic watermarks/ids


# ---------------------------------------------------------------------------
# Builders (mirroring test_relay_auto_driver.py)


def _arc(box_id="box-a", code="live", created_at="2026-10-01T00:00:00Z",
         **kw):
    kw.setdefault("relay_reachable", True)
    kw.setdefault("provider_running", True)
    return ts.BoxArc(box_id=box_id, created_at=created_at, code=code, **kw)


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


def _suppliers(state="running", post_live=True, bundle=None):
    """(provider_state_fn, post_live_fn, bundle_fn) test triple."""
    return (
        lambda tid, vm: state,
        lambda tid, vm: post_live,
        lambda tid, vm: dict(bundle) if bundle is not None else None,
    )


class _FakeResult:
    def __init__(self, outcome, elapsed_ms=7):
        self.outcome = outcome
        self.detail = {"elapsed_ms": elapsed_ms}


class _StubProber:
    """Context manager swapping relay_dial_prober.probe for a fake."""

    def __init__(self, outcome=prober.PATH_OK):
        self.outcome = outcome
        self.calls = []

    def __enter__(self):
        real = prober.probe
        calls = self.calls
        outcome = self.outcome

        def fake_probe(vm_id, *, relay_host, relay_port,
                       pinned_fingerprint, provider_state_fn):
            calls.append({
                "vm_id": vm_id,
                "relay_host": relay_host,
                "relay_port": relay_port,
                "pinned_fingerprint": pinned_fingerprint,
            })
            return _FakeResult(outcome)

        prober.probe = fake_probe
        self._real = real
        return self

    def __exit__(self, *exc):
        prober.probe = self._real
        return False


def _journal_rows(estate_dir):
    path = os.path.join(estate_dir, "events.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# ---------------------------------------------------------------------------
# probe_one_tenant


def test_probe_due_probes_with_supplied_bundle(tmp_path):
    # Due tick + supplied bundle: the REAL maybe_probe dials (stubbed
    # prober), the outcome lands in probe history, probed=True.
    # Neuter check: maybe_probe never called (bundle dropped) leaves
    # probed False and history empty.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    hist = str(tmp_path / "hist.jsonl")
    bundle = {"relay_host": "h", "relay_port": 1,
              "pinned_fingerprint": "SHA256:eA"}
    with _StubProber() as stub:
        record, vm_id = probe.probe_one_tenant(
            store, "tnt-a", tick_at=NOW, tick_iso="t",
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: dict(bundle),
            history=hist,
        )
    assert vm_id == "box-a"
    assert record["probed"] is True
    assert record["stand_down"] is False
    assert record["failed"] is False
    assert len(stub.calls) == 1
    assert stub.calls[0]["pinned_fingerprint"] == "SHA256:eA"
    latest = rps.latest_probe("box-a", path=hist)
    assert latest is not None
    assert latest["outcome"] == prober.PATH_OK
    assert abs(latest["ts"] - NOW) < 1


def test_probe_due_without_bundle_is_loud_not_failed(tmp_path):
    # D-RL2-3: due + bundle_fn None — the tick does NOT probe and does
    # NOT fail; the LOUD note names the missing supplier. The
    # dark-instrument steady state, loud by design.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    hist = str(tmp_path / "hist.jsonl")
    with _StubProber() as stub:
        record, _ = probe.probe_one_tenant(
            store, "tnt-a", tick_at=NOW, tick_iso="t",
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: None,
            history=hist,
        )
    assert record["probed"] is False
    assert record["failed"] is False
    assert stub.calls == []
    assert any("LOUD" in n and "bundle" in n for n in record["notes"]), \
        record["notes"]
    assert rps.latest_probe("box-a", path=hist) is None


def test_probe_stand_down_suspended(tmp_path):
    # D-RL2-2: provider suspended — stand down, observably, prober
    # never called.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    hist = str(tmp_path / "hist.jsonl")
    with _StubProber() as stub:
        record, _ = probe.probe_one_tenant(
            store, "tnt-a", tick_at=NOW, tick_iso="t",
            provider_state_fn=lambda tid, vm: "suspended",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: {"relay_host": "h", "relay_port": 1,
                                       "pinned_fingerprint": "x"},
            history=hist,
        )
    assert record["probed"] is False
    assert record["stand_down"] is True
    assert record["failed"] is False
    assert record["reason"].startswith("stand-down")
    assert stub.calls == []


def test_probe_stand_down_destroyed(tmp_path):
    # D-RL2-2: provider destroyed — the second stand-down state, same
    # observable contract as suspended. Neuter check: dropping
    # "destroyed" from _STAND_DOWN_STATES flips stand_down False and
    # fails this test.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    hist = str(tmp_path / "hist.jsonl")
    with _StubProber() as stub:
        record, _ = probe.probe_one_tenant(
            store, "tnt-a", tick_at=NOW, tick_iso="t",
            provider_state_fn=lambda tid, vm: "destroyed",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: {"relay_host": "h", "relay_port": 1,
                                       "pinned_fingerprint": "x"},
            history=hist,
        )
    assert record["probed"] is False
    assert record["stand_down"] is True
    assert record["failed"] is False
    assert record["reason"].startswith("stand-down")
    assert stub.calls == []


def test_probe_stand_down_no_post_live_arc(tmp_path):
    # D-RL2-2: no post-`live` arc — stand down, prober never called.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    with _StubProber() as stub:
        record, _ = probe.probe_one_tenant(
            store, "tnt-a", tick_at=NOW, tick_iso="t",
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: False,
            history=str(tmp_path / "hist.jsonl"),
        )
    assert record["probed"] is False
    assert record["stand_down"] is True
    assert "no post-live arc" in record["reason"]
    assert stub.calls == []


def test_probe_not_due_is_cheap_noop(tmp_path):
    # D-AC-1: a fresh probe in history — maybe_probe says not due, no
    # dial, probed=False, stand_down=False (a noop, not a stand-down).
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    hist = str(tmp_path / "hist.jsonl")
    with _StubProber():
        first, _ = probe.probe_one_tenant(
            store, "tnt-a", tick_at=NOW, tick_iso="t",
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: {"relay_host": "h", "relay_port": 1,
                                       "pinned_fingerprint": "x"},
            history=hist,
        )
    assert first["probed"] is True
    with _StubProber() as stub:
        second, _ = probe.probe_one_tenant(
            store, "tnt-a", tick_at=NOW + 60, tick_iso="t",
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: {"relay_host": "h", "relay_port": 1,
                                       "pinned_fingerprint": "x"},
            history=hist,
        )
    assert second["probed"] is False
    assert second["stand_down"] is False
    assert second["failed"] is False
    assert stub.calls == []
    assert "next probe in" in second["reason"]


def test_probe_no_live_anchor_probes_nothing(tmp_path):
    # Tenant with no live anchor: nothing to probe, not a failure.
    store = _wired_store(tmp_path, {"tnt-a": []})
    with _StubProber() as stub:
        record, vm_id = probe.probe_one_tenant(
            store, "tnt-a", tick_at=NOW, tick_iso="t",
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: True,
            history=str(tmp_path / "hist.jsonl"),
        )
    assert vm_id is None
    assert record["probed"] is False
    assert record["failed"] is False
    assert any("no live-anchor" in n for n in record["notes"])
    assert stub.calls == []


def test_probe_supplier_raise_fails_loud(tmp_path):
    # A raising provider_state_fn is a caller bug per maybe_probe's
    # contract — the tick fails LOUD, the sweep (tested below) moves
    # on. Neuter check: without the try/except the raise escapes.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    def bad_state(tid, vm):
        raise RuntimeError("H4 exploded")
    record, _ = probe.probe_one_tenant(
        store, "tnt-a", tick_at=NOW, tick_iso="t",
        provider_state_fn=bad_state,
        post_live_fn=lambda tid, vm: True,
        history=str(tmp_path / "hist.jsonl"),
    )
    assert record["failed"] is True
    assert record["probed"] is False
    assert any("LOUD" in n and "H4 exploded" in n
               for n in record["notes"]), record["notes"]


def test_probe_bundle_fn_raise_fails_loud(tmp_path):
    # A raising bundle_fn likewise fails the tenant loud, not the
    # sweep — the bundle supplier is caller code.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    def bad_bundle(tid, vm):
        raise KeyError("no bundle row")
    record, _ = probe.probe_one_tenant(
        store, "tnt-a", tick_at=NOW, tick_iso="t",
        provider_state_fn=lambda tid, vm: "running",
        post_live_fn=lambda tid, vm: True,
        bundle_fn=bad_bundle,
        history=str(tmp_path / "hist.jsonl"),
    )
    assert record["failed"] is True
    assert any("no bundle row" in n for n in record["notes"])


def test_probe_malformed_bundle_fails_loud(tmp_path):
    # A bundle missing keys dies inside maybe_probe (KeyError on
    # bundle["relay_host"]) — contained as failed=True LOUD, never a
    # sweep wedge. Neuter check: without the broad except the KeyError
    # escapes probe_one_tenant.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    with _StubProber() as stub:
        record, _ = probe.probe_one_tenant(
            store, "tnt-a", tick_at=NOW, tick_iso="t",
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: {"relay_host": "h"},  # missing keys
            history=str(tmp_path / "hist.jsonl"),
        )
    assert record["failed"] is True
    assert record["probed"] is False
    assert any("LOUD" in n for n in record["notes"]), record["notes"]
    assert stub.calls == []


def test_probe_tenant_vanished_mid_sweep(tmp_path):
    # Benign race: get() returns None — noted, not failed.
    class _Gone:
        def tenant_ids(self):
            return ["tnt-gone"]
        def get(self, tid):
            return None
    record, vm_id = probe.probe_one_tenant(
        _Gone(), "tnt-gone", tick_at=NOW, tick_iso="t",
        provider_state_fn=lambda tid, vm: "running",
        post_live_fn=lambda tid, vm: True,
    )
    assert record["failed"] is False
    assert record["probed"] is False
    assert any("vanished" in n for n in record["notes"])


# ---------------------------------------------------------------------------
# probe_all_tenants: watermark + journal


def test_probe_all_writes_watermark_and_journals(tmp_path):
    # Two tenants: both probed (stubbed dial), the probe watermark
    # sidecar holds both records, the fleet journal holds two
    # relay-probe events with deterministic ids.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-b")],
    })
    wm = str(tmp_path / "wm.json")
    estate = tmp_path / "estate"
    estate.mkdir()
    hist = str(tmp_path / "hist.jsonl")
    bundle = {"relay_host": "h", "relay_port": 1,
              "pinned_fingerprint": "SHA256:eA"}
    with _StubProber():
        summary = probe.probe_all_tenants(
            store, watermark_path=wm, journal_store_dir=str(estate),
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: dict(bundle),
            history=hist, now=NOW,
        )
    assert summary["errors"] == []
    assert summary["cadence_s"] == rps.cadence_s()
    for tid in ("tnt-a", "tnt-b"):
        rec = summary["tenants"][tid]
        assert rec["probed"] is True
        assert rec["failed"] is False
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert sorted(marks) == ["tnt-a", "tnt-b"]
    for tid in ("tnt-a", "tnt-b"):
        assert marks[tid]["probed"] is True
        assert marks[tid]["tick_at"] == summary["tick_at"]
    rows = _journal_rows(str(estate))
    assert len(rows) == 2
    for row in rows:
        assert row["kind"] == "relay-probe"
        assert row["outcome"] == "probed"
        assert row["source"] == "relay-probe-driver"
        assert row["subcomponent"] == "probe-driver"
    # Deterministic event ids: same (tenant, tick) re-run dedups.
    with _StubProber():
        summary2 = probe.probe_all_tenants(
            store, watermark_path=str(tmp_path / "wm2.json"),
            journal_store_dir=str(estate),
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: dict(bundle),
            history=hist, now=NOW,
        )
    rows2 = _journal_rows(str(estate))
    # The re-run dedups to a no-op: still exactly 2 journal rows.
    assert len(rows2) == 2
    ids = [r["event_id"] for r in rows + rows2[-2:]]
    assert ids[0] == ids[2] and ids[1] == ids[3]


def test_probe_all_broken_tenant_does_not_wedge_sweep(tmp_path):
    # D-AC-3: one tenant's raising supplier fails loud; the other
    # tenant still probes and the sweep completes.
    store = _wired_store(tmp_path, {
        "tnt-a": [_arc("box-a")],
        "tnt-b": [_arc("box-b")],
    })
    wm = str(tmp_path / "wm.json")
    hist = str(tmp_path / "hist.jsonl")
    def flaky_state(tid, vm):
        if tid == "tnt-a":
            raise RuntimeError("H4 exploded")
        return "running"
    bundle = {"relay_host": "h", "relay_port": 1,
              "pinned_fingerprint": "x"}
    with _StubProber():
        summary = probe.probe_all_tenants(
            store, watermark_path=wm,
            provider_state_fn=flaky_state,
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: dict(bundle),
            history=hist, now=NOW,
        )
    assert summary["tenants"]["tnt-a"]["failed"] is True
    assert summary["tenants"]["tnt-b"]["probed"] is True
    assert summary["errors"] == []
    with open(wm, encoding="utf-8") as fh:
        marks = json.load(fh)
    assert sorted(marks) == ["tnt-a", "tnt-b"]


def test_probe_bundle_never_persisted(tmp_path):
    # D-RL2-3 audit: the bundle's fingerprint must not land in any
    # file the tick writes — history holds outcomes only, the
    # watermark holds the tick record, the journal holds the note.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    wm = str(tmp_path / "wm.json")
    estate = tmp_path / "estate"
    estate.mkdir()
    hist = str(tmp_path / "hist.jsonl")
    canary = "SHA256:CANARY-FINGERPRINT-9f8e7d6c"
    bundle = {"relay_host": "relay.example", "relay_port": 8443,
              "pinned_fingerprint": canary}
    with _StubProber():
        probe.probe_all_tenants(
            store, watermark_path=wm, journal_store_dir=str(estate),
            provider_state_fn=lambda tid, vm: "running",
            post_live_fn=lambda tid, vm: True,
            bundle_fn=lambda tid, vm: dict(bundle),
            history=hist, now=NOW,
        )
    for root, _dirs, files in os.walk(tmp_path):
        for name in files:
            # The tenants.json store is operator config, out of scope
            # for the bundle audit (the bundle never came from it).
            if name == "tenants.json":
                continue
            path = os.path.join(root, name)
            with open(path, "rb") as fh:
                content = fh.read()
            assert canary.encode() not in content, path
            assert b"relay.example" not in content, path


def test_probe_watermark_path_for():
    assert probe.probe_watermark_path_for("/s/tenants.json") == \
        "/s/tenants.json.relay-probe-watermarks.json"


def test_probe_event_shape(tmp_path):
    # The journal event carries the fleet-event/1 contract fields the
    # G17 consumers read; the note is scrubbed.
    store = _wired_store(tmp_path, {"tnt-a": [_arc("box-a")]})
    estate = tmp_path / "estate"
    estate.mkdir()
    with _StubProber():
        probe.probe_all_tenants(
            store, watermark_path=str(tmp_path / "wm.json"),
            journal_store_dir=str(estate),
            provider_state_fn=lambda tid, vm: "suspended",
            post_live_fn=lambda tid, vm: True,
            history=str(tmp_path / "hist.jsonl"), now=NOW,
        )
    rows = _journal_rows(str(estate))
    assert len(rows) == 1
    row = rows[0]
    assert row["schema"] == "fleet-event/1"
    assert row["kind"] == "relay-probe"
    assert row["outcome"] == "stand-down"
    assert row["trigger"] == "scheduled"
    assert row["attested"] is False
    assert row["component"] == "relay"


def test_probe_watermark_symlink_plant_is_one_sweep_level_error(tmp_path):
    # #1838 (probe half): a symlink plant at the probe watermark
    # sidecar is ONE sweep-level condition — a single errors[] entry
    # (tenant_id None), never N per-tenant ones. The sweep still
    # probes every tenant (observability never wedges the sweep),
    # writes nothing through the plant, and the per-tenant records
    # carry no observability note (the sweep-level entry is the honest
    # signal; S4's staleness rule reads the missing watermark as
    # probe-loop trouble).
    # Neuter check: re-adding the per-tenant raise produces 2
    # errors[] entries and fails the single-entry assertion below.
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
    state_fn, post_live_fn, bundle_fn = _suppliers()
    summary = probe.probe_all_tenants(
        store, watermark_path=wm, journal_store_dir=str(estate),
        provider_state_fn=state_fn, post_live_fn=post_live_fn,
        bundle_fn=bundle_fn, history=str(tmp_path / "hist.jsonl"),
        now=NOW,
    )
    # Both tenants were probed (no probe failure) and carry no
    # observability note — the fault is not theirs.
    for tid in ("tnt-a", "tnt-b"):
        rec = summary["tenants"][tid]
        assert rec["failed"] is False
        assert not any("observability failed" in n for n in rec["notes"]), \
            rec["notes"]
    # Exactly one sweep-level errors[] entry naming the plant.
    assert len(summary["errors"]) == 1
    entry = summary["errors"][0]
    assert entry["tenant_id"] is None
    assert "LOUD" in entry["error"] and "symlink" in entry["error"], entry
    # Nothing was written through the plant: the victim is untouched
    # and the sidecar path is still the link.
    with open(victim, encoding="utf-8") as fh:
        assert json.load(fh) == {"attacker": {"seed": "poison"}}
    assert os.path.islink(wm)
