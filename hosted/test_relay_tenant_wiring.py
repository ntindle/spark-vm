#!/usr/bin/env python3
"""R3 producer-wiring tests (issue #1416): ``hosted/relay_tenant_wiring.py``.

Covers the acceptance: anchor selection (multi-box, non-anchor readings
ignored), down -> suspension with the §3 sub-code in detail + latch,
degraded -> no suspension, nested-suspension emit rule (relay-down only,
never relay-failure), the recovery pair order, the blind re-emit guard,
lost-recovery re-drive, stale relay_reachable resync, the delivery
semantics (crash-between-events interleaving safety), and the read/apply
split (anchor re-selection from the fresh record, reads outside the store
lock, no-anchor and anchor-instrument-failure behavior).

Style: plain functions + small builders, mirroring
``test_tenant_status.py``. Every test asserts a concrete state
transition — none pass vacuously (each was neuter-verified: it fails on
the pre-fix behavior and passes with the fix; see the module docstring
notes per test).
"""

import ast
import contextlib
import pathlib

import pytest

from hosted import relay_path_state as rps
from hosted import relay_tenant_wiring as wiring
from hosted import tenant_status as ts


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


def _degraded():
    return _reading(rps.STATE_DEGRADED, probe=None, journal="idle")


def _tenant_record(boxes, tenant_id="tnt_test"):
    return ts.TenantRecord(
        tenant_id=tenant_id,
        stage=2,
        approvals_url="https://approve.example/a/tnt_test",
        boxes={b.box_id: b for b in boxes},
    )


# ---------------------------------------------------------------------------
# Anchor selection (TENANT_STATUS_ENDPOINT.md §7/G7)


def test_anchor_selects_first_live_box():
    # The box whose arc first reached live is the tenant-driving one.
    # Neuter check: picking newest-created (min -> max) fails this.
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    assert wiring.select_live_anchor([b, a]) is a
    assert wiring.select_live_anchor([a, b]) is a


def test_anchor_tiebreak_is_deterministic():
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", created_at="2026-10-01T00:00:00Z")
    assert wiring.select_live_anchor([b, a]) is a  # box-id lexical


def test_anchor_ignores_malformed_created_at():
    # A corrupt timestamp never wins the anchor while a healthy
    # candidate exists (#1467 fail-safe, earliest-wins direction).
    good = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    bad = _arc("box-b", created_at="not-a-timestamp")
    assert wiring.select_live_anchor([bad, good]) is good


def test_anchor_none_without_post_live_arc():
    assert wiring.select_live_anchor([_arc("box-a", code="provisioning",
                                           relay_reachable=False,
                                           provider_running=False)]) is None
    assert wiring.select_live_anchor([]) is None


def test_anchor_excludes_dead_and_terminal_arcs():
    # box-unhealthy (arc over) must not hold the anchor while another
    # box carries the live arc; terminal codes never candidate.
    dead = _arc("box-a", code="box-unhealthy",
                detail="box-unhealthy: smoke-1",
                created_at="2026-10-01T00:00:00Z")
    live = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    denied = _arc("box-c", code="human-denied",
                  created_at="2026-09-30T00:00:00Z")
    assert wiring.select_live_anchor([dead, live, denied]) is live


def test_anchor_survives_suspension_of_anchor_box():
    # The anchor is historical-first and stable: while the anchor box's
    # own suspension is up, its recovery keeps being driven (no wedge),
    # and the second box's readings stay operator-surface.
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    ts.apply_event(a, "relay-down", detail="cert")
    assert a.code == "connection-unreachable"
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    assert wiring.select_live_anchor([a, b]) is a


def test_anchor_reprovision_carve_out():
    # Rule-7 restart: the anchor's new session is at provisioning — not
    # a candidate — so the anchor passes without pinning the endpoint.
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    ts.apply_event(a, "operator-reprovision")
    assert a.code == "provisioning"
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    assert wiring.select_live_anchor([a, b]) is b
    assert wiring.select_live_anchor([a]) is None


def test_non_anchor_readings_never_applied(tmp_path):
    # drive_tenant: the anchor's down reading suspends; the non-anchor
    # box's down reading is observed for the operator surface and never
    # touches its arc. Neuter check: applying every box's reading fails
    # the box-b assertions.
    store = ts.TenantStore(str(tmp_path / "tenants.json"))
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    store.create(_tenant_record([a, b]))
    reads = {"box-a": _down("cert"), "box-b": _down("relay")}
    report = wiring.drive_tenant(store, "tnt_test",
                                 read_fn=lambda vm_id: reads[vm_id])
    assert report["anchor_box_id"] == "box-a"
    by_box = {r["box_id"]: r for r in report["boxes"]}
    assert by_box["box-a"]["events"] == ["relay-down(detail='cert')"]
    assert by_box["box-b"]["events"] == []
    assert by_box["box-b"]["reading"]["sub_code"] == "relay"
    assert any("operator surface" in n for n in by_box["box-b"]["notes"])
    # Persisted state: only the anchor moved.
    rec = store.get("tnt_test")
    assert rec.boxes["box-a"].code == "connection-unreachable"
    assert rec.boxes["box-a"].detail == "cert"
    assert rec.boxes["box-b"].code == "live"
    assert rec.boxes["box-b"].relay_reachable is True


def test_non_anchor_instrument_failure_does_not_kill_anchor_tick(tmp_path):
    store = ts.TenantStore(str(tmp_path / "tenants.json"))
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    store.create(_tenant_record([a, b]))

    def flaky(vm_id):
        if vm_id == "box-b":
            raise rps.HistoryLockError("wedged")
        return _down("box-leg")

    report = wiring.drive_tenant(store, "tnt_test", read_fn=flaky)
    by_box = {r["box_id"]: r for r in report["boxes"]}
    assert by_box["box-a"]["events"] == ["relay-down(detail='box-leg')"]
    assert by_box["box-b"]["reading"] is None
    assert any("wedged" in n for n in by_box["box-b"]["notes"])
    rec = store.get("tnt_test")
    assert rec.boxes["box-a"].code == "connection-unreachable"


# ---------------------------------------------------------------------------
# has_post_live_arc — the tenant layer's R2b answer


@pytest.mark.parametrize("code,detail,expected", [
    ("live", None, True),
    ("waiting-on-approval", None, True),
    ("approved", None, True),
    ("connection-unreachable", None, True),
    ("stuck", None, True),
    ("maintenance", None, True),
    ("human-denied", None, True),
    ("provisioning", None, False),
    ("provisioning-failed", None, False),
    # box-unhealthy: the stack-deploy detail marks the pre-live path.
    ("box-unhealthy", "stack-deploy:swap-proxy", False),
    ("box-unhealthy", "box-unhealthy: smoke-1", True),
    ("box-unhealthy", "box-unhealthy: provider-dead", True),
])
def test_has_post_live_arc(code, detail, expected):
    arc = _arc(code=code, detail=detail)
    assert wiring.has_post_live_arc(arc) is expected


# ---------------------------------------------------------------------------
# Down readings: rule-6 entry with the sub-code in detail (D-RL34-4)


@pytest.mark.parametrize("sub_code", ["relay", "cert", "box-leg"])
@pytest.mark.parametrize("start", ["live", "waiting-on-approval", "approved"])
def test_down_enters_suspension_with_subcode_in_detail(start, sub_code):
    # Neuter check: the pre-R3 _suspend_on_relay_down (detail="relay-down")
    # fails the detail assertion.
    arc = _arc(code=start)
    events, _ = wiring.plan_events(arc, _down(sub_code))
    assert events == [("relay-down", {"detail": sub_code})]
    emitted = wiring._emit(arc, events)
    assert emitted == ["relay-down(detail=%r)" % sub_code]
    assert arc.code == "connection-unreachable"
    assert arc.detail == sub_code  # NOT the literal "relay-down"
    assert arc.latched == start
    assert arc.relay_reachable is False


def test_down_without_subcode_suspends_as_unclassified():
    # Defensive: the §5 contract guarantees a sub-code on down; a
    # missing one is a broken-producer signal. The down evidence is
    # still real, so rule 6 fires — but the wiring never invents a
    # classification: no detail kwarg, the tenant layer's generic
    # "relay-down" default marks the entry unclassified, and the
    # anomaly rides the notes loud.
    arc = _arc()
    events, notes = wiring.plan_events(arc, _reading(rps.STATE_DOWN))
    assert events == [("relay-down", {})]
    assert any("sub-code" in n for n in notes)
    wiring._emit(arc, events)
    assert arc.code == "connection-unreachable"
    assert arc.detail == "relay-down"  # generic default: unclassified
    assert arc.latched == "live"
    assert arc.relay_reachable is False


def test_degraded_readings_never_fire_rule6():
    # F-RL34-5: degraded (flapping / never-probed / stand-down) carries
    # sub_code None and is operator-surface only — no events, no arc
    # touch. Neuter check: emitting relay-down here would suspend.
    for reading in (
        _degraded(),
        _reading(rps.STATE_DEGRADED, probe="provider_not_running"),
    ):
        assert reading["sub_code"] is None
        arc = _arc()
        events, _ = wiring.plan_events(arc, reading)
        assert events == []
        wiring._emit(arc, events)
        assert arc.code == "live"
        assert arc.relay_reachable is True
        assert arc.detail is None


def test_unrecognized_state_treated_as_degraded():
    arc = _arc()
    events, notes = wiring.plan_events(arc, _reading("bogus"))
    assert events == []
    assert any("bogus" in n for n in notes)


# ---------------------------------------------------------------------------
# Nested suspensions (F-RL34-3): relay-down only, never relay-failure


@pytest.mark.parametrize("start", ["stuck", "maintenance",
                                   "connection-unreachable"])
def test_nested_down_emits_relay_down_only(start):
    # relay-failure raises TransitionError in latch-holding states
    # (verified against tenant_status below); the wiring must never
    # emit it there — relay-down is the boolean flip. Neuter check: a
    # plan emitting relay-failure fails at _emit with TransitionError.
    if start == "stuck":
        arc = _arc()
        ts.apply_event(arc, "operator-mark-stuck")
    elif start == "maintenance":
        arc = _arc()
        ts.apply_event(arc, "maintenance-started", operation="reimage")
    else:
        arc = _arc()
        ts.apply_event(arc, "relay-down", detail="relay")
    assert arc.code == start
    events, _ = wiring.plan_events(arc, _down("cert"))
    assert events == [("relay-down", {})]
    assert all(e != "relay-failure" for e, _ in events)
    wiring._emit(arc, events)  # must not raise
    assert arc.code == start  # boolean flip only — no new suspension
    assert arc.relay_reachable is False


def test_relay_failure_raises_in_latch_holding_states():
    # The F-RL34-3 premise, verified against the tenant layer: the
    # wiring's nested rule exists because this raises.
    arc = _arc()
    ts.apply_event(arc, "operator-mark-stuck")
    with pytest.raises(ts.TransitionError):
        ts.apply_event(arc, "relay-failure", detail="cert")
    arc = _arc()
    ts.apply_event(arc, "maintenance-started", operation="reimage")
    with pytest.raises(ts.TransitionError):
        ts.apply_event(arc, "relay-failure", detail="cert")


def test_relay_down_at_provisioning_is_boolean_only():
    arc = _arc(code="provisioning", relay_reachable=False,
               provider_running=False)
    events, _ = wiring.plan_events(arc, _down("relay"))
    assert events == [("relay-down", {})]
    wiring._emit(arc, events)
    assert arc.code == "provisioning"  # rule 1(a) hold
    assert arc.relay_reachable is False


# ---------------------------------------------------------------------------
# Recovery: the ordered pair (D-RL34-3)


def test_recovery_emits_reachable_before_recovered():
    # Neuter check: swapping the pair order fails the events assertion.
    arc = _arc()
    wiring._emit(arc, wiring.plan_events(arc, _down("cert"))[0])
    assert arc.code == "connection-unreachable"
    events, _ = wiring.plan_events(arc, _ok())
    assert [e for e, _ in events] == ["relay-reachable", "relay-recovered"]
    wiring._emit(arc, events)
    assert arc.code == "live"
    assert arc.latched is None
    assert arc.relay_reachable is True


def test_crash_between_pair_leaves_no_stale_false():
    # Interleaving-safety proof (D-RL34-3a): the boolean restore runs
    # FIRST, so a crash between the two events leaves "boolean honest,
    # suspension retained" — never a stale False — and the next ok
    # reading re-drives the pair to convergence.
    arc = _arc()
    wiring._emit(arc, wiring.plan_events(arc, _down("cert"))[0])
    events, _ = wiring.plan_events(arc, _ok())
    wiring._emit(arc, events[:1])  # crash after the first event
    assert arc.relay_reachable is True  # no stale False, by ordering
    assert arc.code == "connection-unreachable"  # suspension retained
    assert arc.latched == "live"
    # Re-drive on the next ok reading converges.
    events2, _ = wiring.plan_events(arc, _ok())
    assert [e for e, _ in events2] == ["relay-reachable", "relay-recovered"]
    wiring._emit(arc, events2)
    assert arc.code == "live"
    assert arc.latched is None


def test_swapped_order_would_leave_stale_false():
    # Why the order is pinned: recovering the suspension BEFORE the
    # boolean restore, then crashing, exits the suspension with
    # relay_reachable=False — the stale-False poison the wiring's
    # ordering exists to prevent. (Tenant-layer property, pinned here
    # as the rationale for D-RL34-3's order.)
    arc = _arc()
    wiring._emit(arc, wiring.plan_events(arc, _down("cert"))[0])
    ts.apply_event(arc, "relay-reachable")
    ts.apply_event(arc, "relay-recovered")
    assert arc.code == "live" and arc.relay_reachable is True
    # Now the dangerous order, crashed between events:
    arc2 = _arc()
    wiring._emit(arc2, wiring.plan_events(arc2, _down("cert"))[0])
    ts.apply_event(arc2, "relay-recovered")  # exit first...
    # ...crash before relay-reachable:
    assert arc2.code == "live"
    assert arc2.relay_reachable is False  # stale False — the poison


def test_blind_recovered_reemit_is_guarded():
    # After a successful recovery the guard (suspension active + latch)
    # no longer holds, so an ok reading plans nothing — the wiring
    # never blind-retries relay-recovered. Neuter check: a plan that
    # emits relay-recovered unconditionally fails at _emit.
    arc = _arc()
    wiring._emit(arc, wiring.plan_events(arc, _down("cert"))[0])
    events, _ = wiring.plan_events(arc, _ok())
    wiring._emit(arc, events)
    assert arc.code == "live"
    events2, _ = wiring.plan_events(arc, _ok())
    assert events2 == []
    wiring._emit(arc, events2)  # nothing to emit — no TransitionError
    # The guard exists because the tenant layer raises past it:
    with pytest.raises(ts.TransitionError):
        ts.apply_event(arc, "relay-recovered")


def test_lost_recovery_redrives_statelessly():
    # A lost relay-recovered (emitted but never delivered) cannot wedge
    # the suspension: every ok-while-suspended tick re-emits the pair.
    arc = _arc()
    wiring._emit(arc, wiring.plan_events(arc, _down("box-leg"))[0])
    events, _ = wiring.plan_events(arc, _ok())
    wiring._emit(arc, [events[0]])  # relay-recovered lost in transit
    assert arc.code == "connection-unreachable"
    events2, _ = wiring.plan_events(arc, _ok())
    assert [e for e, _ in events2] == ["relay-reachable", "relay-recovered"]
    wiring._emit(arc, events2)
    assert arc.code == "live"
    assert arc.latched is None
    assert arc.relay_reachable is True


def test_corrupt_suspension_without_latch_restores_boolean_only():
    # relay-recovered would raise TransitionError with no latch — the
    # wiring restores the boolean and leaves the exit to the operator.
    arc = _arc(code="connection-unreachable", latched=None,
               relay_reachable=False)
    # (latched=None with a suspension code is constructible here only
    # via the explicit kwarg — the store quarantines the persisted
    # shape; the wiring still must not raise the tick.)
    events, notes = wiring.plan_events(arc, _ok())
    assert [e for e, _ in events] == ["relay-reachable"]
    assert any("no latch" in n for n in notes)
    wiring._emit(arc, events)
    assert arc.relay_reachable is True
    assert arc.code == "connection-unreachable"


def test_stale_relay_reachable_resync():
    # F-RL34-4: an ok reading with a stale False and no suspension
    # restores the boolean — the value _re_evaluate_latch_on_exit's
    # backstop reads. No suspension entered, nothing raised.
    arc = _arc(relay_reachable=False)
    events, notes = wiring.plan_events(arc, _ok())
    assert [e for e, _ in events] == ["relay-reachable"]
    assert any("resync" in n for n in notes)
    wiring._emit(arc, events)
    assert arc.code == "live"
    assert arc.relay_reachable is True


def test_resync_inside_stuck_keeps_backstop_honest():
    # Down during stuck flips the boolean; the later ok resyncs it, so
    # a subsequent stuck-cleared re-evaluates against a fresh True.
    arc = _arc()
    ts.apply_event(arc, "operator-mark-stuck")
    wiring._emit(arc, wiring.plan_events(arc, _down("relay"))[0])
    assert arc.relay_reachable is False
    events, _ = wiring.plan_events(arc, _ok())
    wiring._emit(arc, events)
    assert arc.relay_reachable is True
    ts.apply_event(arc, "stuck-cleared")
    assert arc.code == "live"  # backstop saw an honest True


# ---------------------------------------------------------------------------
# Constants track the tenant layer (no silent drift)


def test_wiring_constants_track_tenant_layer():
    assert wiring._RULE6_ENTRY_CODES == ts._LIVENESS_DEMOTE_CODES
    assert rps.SUBCODES == frozenset({"relay", "cert", "box-leg"})


# ---------------------------------------------------------------------------
# End-to-end tick against a real store


def test_drive_tenant_tick_persists_across_ticks(tmp_path):
    store = ts.TenantStore(str(tmp_path / "tenants.json"))
    store.create(_tenant_record([_arc("box-a",
                                     created_at="2026-10-01T00:00:00Z")]))
    reads = {"box-a": _down("cert")}
    report = wiring.drive_tenant(store, "tnt_test",
                                 read_fn=lambda vm_id: reads[vm_id])
    assert report["anchor_box_id"] == "box-a"
    assert report["boxes"][0]["reading"]["state"] == "down"
    rec = store.get("tnt_test")
    assert rec.boxes["box-a"].code == "connection-unreachable"
    assert rec.boxes["box-a"].latched == "live"
    # Recovery tick.
    reads["box-a"] = _ok()
    report2 = wiring.drive_tenant(store, "tnt_test",
                                  read_fn=lambda vm_id: reads[vm_id])
    assert report2["boxes"][0]["events"] == ["relay-reachable",
                                            "relay-recovered"]
    rec2 = store.get("tnt_test")
    assert rec2.boxes["box-a"].code == "live"
    assert rec2.boxes["box-a"].latched is None
    assert rec2.boxes["box-a"].relay_reachable is True


# ---------------------------------------------------------------------------
# Read/apply split — the tick never holds the store's exclusive lock
# across producer I/O; the apply phase re-selects the anchor from the
# fresh record.


def test_anchor_change_between_read_and_apply_skips(tmp_path):
    # The read phase selected box-a as anchor, but the record moved
    # before the apply phase: the stale reading must NOT be applied —
    # the tick skips, and the next tick (with box-b as anchor)
    # converges. Neuter check: disabling the apply-phase re-selection
    # guard applies the stale reading to the reprovisioned box-a and
    # fails the skip assertion.
    store = ts.TenantStore(str(tmp_path / "tenants.json"))
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    store.create(_tenant_record([a, b]))

    def read_and_move(vm_id):
        if vm_id == "box-a":
            # Runs in the read phase, before the apply phase's _mutate:
            # the anchor moves to box-b.
            rec = store.get("tnt_test")
            rec.boxes["box-a"].code = "provisioning"
            store.save(rec)
        return _down("cert")

    report = wiring.drive_tenant(store, "tnt_test", read_fn=read_and_move)
    assert report["anchor_box_id"] == "box-a"  # the read-phase anchor
    by_box = {r["box_id"]: r for r in report["boxes"]}
    assert by_box["box-a"]["events"] == []  # stale anchor: skipped
    assert any("next tick" in n for n in by_box["box-a"]["notes"])
    # The stale reading was never applied: box-a kept the moved code,
    # box-b (read as non-anchor) was untouched.
    rec = store.get("tnt_test")
    assert rec.boxes["box-a"].code == "provisioning"
    assert rec.boxes["box-a"].relay_reachable is True
    assert rec.boxes["box-b"].code == "live"
    assert rec.boxes["box-b"].relay_reachable is True
    # Next tick converges: box-b is the anchor now, its reading drives.
    report2 = wiring.drive_tenant(store, "tnt_test",
                                  read_fn=lambda vm_id: _down("relay"))
    by2 = {r["box_id"]: r for r in report2["boxes"]}
    assert report2["anchor_box_id"] == "box-b"
    assert by2["box-b"]["events"] == ["relay-down(detail='relay')"]
    rec2 = store.get("tnt_test")
    assert rec2.boxes["box-b"].code == "connection-unreachable"


def test_reads_run_outside_the_store_lock(tmp_path):
    # Every producer read — anchor and non-anchor — runs with the
    # store's exclusive lock released: the lock needs to serialize only
    # the apply step. Neuter check: holding the lock across the read
    # phase (the pre-split behavior) fails the held-during-read
    # assertion.
    store = ts.TenantStore(str(tmp_path / "tenants.json"))
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    store.create(_tenant_record([a, b]))

    orig_exclusive = store._exclusive
    lock_held = {"v": False}
    locked_during_read = []

    @contextlib.contextmanager
    def spy_exclusive():
        lock_held["v"] = True
        try:
            with orig_exclusive():
                yield
        finally:
            lock_held["v"] = False

    store._exclusive = spy_exclusive

    def spy_read(vm_id):
        locked_during_read.append((vm_id, lock_held["v"]))
        return _ok()

    try:
        report = wiring.drive_tenant(store, "tnt_test", read_fn=spy_read)
    finally:
        store._exclusive = orig_exclusive

    assert report["anchor_box_id"] == "box-a"
    assert {vm for vm, _ in locked_during_read} == {"box-a", "box-b"}
    assert all(not held for _, held in locked_during_read), \
        "producer reads must run with the store lock released"


def test_drive_tenant_no_anchor_candidate(tmp_path):
    # No box holds a candidate arc: anchor_box_id is None, every box
    # reports events == [] with the "no live-anchor box" note, and the
    # record is unchanged. Neuter check: widening the candidacy set
    # (e.g. treating provisioning as anchorable) selects a bogus
    # anchor, applies events, and fails the unchanged assertions.
    store = ts.TenantStore(str(tmp_path / "tenants.json"))
    a = _arc("box-a", code="provisioning",
             created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", code="box-unhealthy",
             created_at="2026-10-02T00:00:00Z")
    store.create(_tenant_record([a, b]))

    report = wiring.drive_tenant(store, "tnt_test",
                                 read_fn=lambda vm_id: _down("relay"))
    assert report["anchor_box_id"] is None
    assert len(report["boxes"]) == 2
    for r in report["boxes"]:
        assert r["events"] == []
        assert any("no live-anchor box" in n for n in r["notes"])
        assert r["reading"]["state"] == "down"
    rec = store.get("tnt_test")
    assert rec.boxes["box-a"].code == "provisioning"
    assert rec.boxes["box-b"].code == "box-unhealthy"
    assert rec.boxes["box-b"].relay_reachable is True


def test_anchor_read_fn_raise_propagates_leaves_record_untouched(tmp_path):
    # A broken anchor instrument is loud: the exception propagates out
    # of drive_tenant, and the record is untouched — the read phase ran
    # before the apply phase, so nothing was ever applied under the
    # lock. Neuter check: swallowing the anchor read's exception fails
    # the pytest.raises assertion.
    store = ts.TenantStore(str(tmp_path / "tenants.json"))
    store.create(_tenant_record([_arc("box-a",
                                      created_at="2026-10-01T00:00:00Z")]))

    def boom(vm_id):
        raise rps.HistoryLockError("journal wedged")

    with pytest.raises(rps.HistoryLockError):
        wiring.drive_tenant(store, "tnt_test", read_fn=boom)
    rec = store.get("tnt_test")
    assert rec.boxes["box-a"].code == "live"
    assert rec.boxes["box-a"].relay_reachable is True


# ---------------------------------------------------------------------------
# Anchor stickiness — an active rule-6 suspension keeps the anchor until
# it exits (blocker 3: reclaim must not orphan the recovery pair).


def test_suspended_anchor_not_reclaimed_by_earlier_box(tmp_path):
    # Regression (#1416 blocker 3): box-a (first-created) reprovisioned
    # so the anchor passed to box-b; box-b's relay leg failed and it
    # suspended. When box-a's new session reaches live again, the anchor
    # must STAY box-b until its suspension exits — reclaiming it for
    # box-a would leave box-b's readings operator-surface-only forever
    # and wedge it connection-unreachable (delivery-semantics (c)).
    # Neuter check: earliest-created-among-all without the stickiness
    # rule reclaims the anchor to box-a in step 4 and box-b never
    # recovers.
    store = ts.TenantStore(str(tmp_path / "tenants.json"))
    a = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    b = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    store.create(_tenant_record([a, b]))

    # 1. Both live: anchor is the first-created, box-a.
    report = wiring.drive_tenant(store, "tnt_test",
                                 read_fn=lambda vm_id: _ok())
    assert report["anchor_box_id"] == "box-a"

    # 2. Box-a reprovisioned: anchor passes to box-b.
    rec = store.get("tnt_test")
    ts.apply_event(rec.boxes["box-a"], "operator-reprovision")
    store.save(rec)
    report = wiring.drive_tenant(store, "tnt_test",
                                 read_fn=lambda vm_id: _ok())
    assert report["anchor_box_id"] == "box-b"

    # 3. Box-b's relay leg fails: rule-6 suspension with the latch held.
    report = wiring.drive_tenant(
        store, "tnt_test",
        read_fn=lambda vm_id: _down("box-leg") if vm_id == "box-b" else _ok())
    assert report["anchor_box_id"] == "box-b"
    by_box = {r["box_id"]: r for r in report["boxes"]}
    assert by_box["box-b"]["events"] == ["relay-down(detail='box-leg')"]
    rec = store.get("tnt_test")
    assert rec.boxes["box-b"].code == "connection-unreachable"
    assert rec.boxes["box-b"].latched == "live"
    assert rec.boxes["box-b"].relay_reachable is False

    # 4. Box-a's new session reaches live: anchor STAYS box-b (sticky).
    rec = store.get("tnt_test")
    ts.apply_event(rec.boxes["box-a"], "provider-running")
    ts.apply_event(rec.boxes["box-a"], "relay-reachable")
    store.save(rec)
    rec = store.get("tnt_test")
    assert rec.boxes["box-a"].code == "live"
    report = wiring.drive_tenant(
        store, "tnt_test",
        read_fn=lambda vm_id: _down("box-leg") if vm_id == "box-b" else _ok())
    assert report["anchor_box_id"] == "box-b"  # not reclaimed by box-a
    by_box = {r["box_id"]: r for r in report["boxes"]}
    assert by_box["box-a"]["events"] == []  # operator surface only
    rec = store.get("tnt_test")
    assert rec.boxes["box-b"].code == "connection-unreachable"

    # 5. Box-b's relay recovers: its pair is driven — no wedge.
    report = wiring.drive_tenant(store, "tnt_test",
                                 read_fn=lambda vm_id: _ok())
    assert report["anchor_box_id"] == "box-b"
    by_box = {r["box_id"]: r for r in report["boxes"]}
    assert by_box["box-b"]["events"] == ["relay-reachable",
                                         "relay-recovered"]
    rec = store.get("tnt_test")
    assert rec.boxes["box-b"].code == "live"
    assert rec.boxes["box-b"].latched is None
    assert rec.boxes["box-b"].relay_reachable is True

    # 6. Suspension exited: anchor returns to the first-created, box-a.
    report = wiring.drive_tenant(store, "tnt_test",
                                 read_fn=lambda vm_id: _ok())
    assert report["anchor_box_id"] == "box-a"


def test_nested_down_with_differing_subcode_notes_both_legs():
    # A nested down whose sub-code differs from the arc's headline
    # detail gets a LOUD note naming both: the headline still names
    # the original leg while the current defect is a different leg
    # (the tick report's reading summary carries the current
    # sub-code). Neuter check: deleting the note block fails the
    # "different leg" assertion.
    arc = _arc()
    ts.apply_event(arc, "relay-down", detail="cert")
    assert arc.code == "connection-unreachable"
    events, notes = wiring.plan_events(arc, _down("box-leg"))
    assert events == [("relay-down", {})]
    assert any("different leg" in n and "cert" in n and "box-leg" in n
               for n in notes)
    # Same leg as the headline: no note.
    _, notes2 = wiring.plan_events(arc, _down("cert"))
    assert not any("different leg" in n for n in notes2)


# ---------------------------------------------------------------------------
# #1563 follow-ups (from the #1416 round-1 / narrow re-confirm reviews)


def test_down_with_foreign_subcode_suspends_as_unclassified():
    # #1563 item 1: a present-but-foreign sub-code (outside
    # relay_path_state.SUBCODES) rides the same path as the
    # missing-None case — the wiring never invents a classification:
    # no detail kwarg, the tenant layer's generic "relay-down"
    # default marks the entry unclassified, and the anomaly rides the
    # notes loud. Neuter check: the exact-equality
    # `events == [("relay-down", {})]` fails if a foreign sub-code is
    # passed through into detail.
    arc = _arc()
    events, notes = wiring.plan_events(
        arc, _reading(rps.STATE_DOWN, sub_code="bogus-leg"))
    assert events == [("relay-down", {})]
    assert any("sub-code" in n and "bogus-leg" in n for n in notes)
    wiring._emit(arc, events)
    assert arc.code == "connection-unreachable"
    assert arc.detail == "relay-down"  # generic default: unclassified
    assert arc.latched == "live"
    assert arc.relay_reachable is False


def test_anchor_passes_to_healthy_box_over_latchless_suspension():
    # #1563 item 2: a latchless connection-unreachable is an anchor
    # candidate but never pins the anchor — the sticky pool is latched
    # suspensions only — so the healthy box keeps the anchor even
    # though the broken box is a candidate. Neuter check: if a
    # latchless suspension pinned like a latched one, box-b would
    # steal the anchor.
    healthy = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    broken = _arc("box-b", code="connection-unreachable",
                  created_at="2026-10-02T00:00:00Z",
                  relay_reachable=False)
    assert broken.latched is None  # corrupt suspension: no latch
    assert wiring.select_live_anchor([broken, healthy]) is healthy


def test_anchor_pins_on_latched_suspension_over_earlier_healthy():
    # Contrast for item 2: a LATCHED suspension pins the anchor even
    # when later-created — stickiness beats earliest-created. Together
    # with the previous test this pins the exact rule: only a
    # non-None latch joins the sticky pool.
    healthy = _arc("box-a", created_at="2026-10-01T00:00:00Z")
    suspended = _arc("box-b", code="connection-unreachable",
                     latched="live",
                     created_at="2026-10-02T00:00:00Z",
                     relay_reachable=False)
    assert wiring.select_live_anchor([suspended, healthy]) is suspended


def test_emitted_event_vocabulary_is_closed():
    # #1563 item 3: the wiring's emitted-event vocabulary is closed —
    # plan_events can only ever plan relay-down, relay-reachable, and
    # relay-recovered (the "no new status codes" acceptance item,
    # previously proved by inspection only). Static AST pin over every
    # events mutation channel: append/extend call sites with literal
    # event names are collected; any other mutation of `events`
    # (insert, +=, subscript assignment, rebind, a second assignment,
    # ...) fails loudly so a new event kind can't slip the pin.
    def _is_events_target(t):
        return ((isinstance(t, ast.Name) and t.id == "events")
                or (isinstance(t, ast.Subscript)
                    and isinstance(t.value, ast.Name)
                    and t.value.id == "events"))
    src = pathlib.Path(wiring.__file__).read_text()
    tree = ast.parse(src)
    names = set()
    assigns = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.AugAssign) and _is_events_target(node.target):
            raise AssertionError(
                "event-vocabulary pin: `events` augmented-assigned at "
                "line %d — extend this pin deliberately" % node.lineno)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = ([node.target] if isinstance(node, ast.AnnAssign)
                       else node.targets)
            for target in targets:
                if _is_events_target(target):
                    if isinstance(target, ast.Subscript):
                        raise AssertionError(
                            "event-vocabulary pin: `events[...]` "
                            "subscript assignment at line %d — extend "
                            "this pin deliberately" % node.lineno)
                    if getattr(node, "value", None) is not None:
                        assigns += 1
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "events"):
            attr = node.func.attr
            if attr == "append":
                first = node.args[0]
                assert (isinstance(first, ast.Tuple)
                        and isinstance(first.elts[0], ast.Constant)), (
                    "event-vocabulary pin: non-literal planned event at "
                    "line %d — extend this pin deliberately" % node.lineno)
                names.add(first.elts[0].value)
            elif (attr == "extend" and node.args
                    and isinstance(node.args[0], ast.List)):
                for elt in node.args[0].elts:
                    assert (isinstance(elt, ast.Tuple)
                            and isinstance(elt.elts[0], ast.Constant)), (
                        "event-vocabulary pin: non-literal planned event "
                        "at line %d — extend this pin deliberately"
                        % node.lineno)
                    names.add(elt.elts[0].value)
            else:
                raise AssertionError(
                    "event-vocabulary pin: `events.%s` call at line %d — "
                    "extend this pin deliberately" % (attr, node.lineno))
    assert assigns == 1, (
        "event-vocabulary pin: expected exactly one `events = ...` "
        "assignment, found %d" % assigns)
    assert names == {"relay-down", "relay-reachable", "relay-recovered"}


def test_anchor_latchless_earliest_created_still_wins():
    # QA nit 2 (round 1): pins the reworded select_live_anchor
    # docstring's caveat — a latchless suspension doesn't pin the
    # anchor, but it IS a candidate, so the earliest-created latchless
    # box still wins via earliest-created-among-all. Neuter check:
    # excluding latchless boxes from candidacy entirely makes the
    # healthy box win, failing this.
    broken = _arc("box-a", code="connection-unreachable",
                  created_at="2026-10-01T00:00:00Z",
                  relay_reachable=False)
    healthy = _arc("box-b", created_at="2026-10-02T00:00:00Z")
    assert broken.latched is None  # corrupt suspension: no latch
    assert wiring.select_live_anchor([healthy, broken]) is broken
