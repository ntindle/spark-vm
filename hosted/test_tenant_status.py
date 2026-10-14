#!/usr/bin/env python3
"""Contract fixtures for hosted/tenant_status.py (G3 implementation slice S1).

Per ``docs/TENANT_STATUS_ENDPOINT.md`` §6, S1 ships contract tests asserting:
the §2 vocabulary spelling, the §2 transition rules (no backwards moves),
the 401/404 auth behavior of §1, and the operator-only codes' missing
``human_key`` — plus the G8 write-if-absent/re-read guarantees and the
§8 rule-1 multi-box selection.
"""

import json
import os
import sys
import tempfile
import threading
import time
import hashlib
import urllib.request
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tenant_status
from tenant_status import (
    OPERATOR_ONLY,
    STATUS_CODES,
    TERMINAL_CODES,
    BoxArc,
    TenantRecord,
    TenantStatusError,
    TenantStatusService,
    TenantStore,
    TransitionError,
    _DUMMY_VERIFY_KEY,
    apply_event,
    canonical_poll_message,
    human_key_for,
    live_entry_ready,
    select_reported,
    status_response,
)

# ---------------------------------------------------------------------------
# fixtures


def _arc(**kw):
    kw.setdefault("box_id", "box-1")
    kw.setdefault("created_at", "2026-09-29T10:00:00Z")
    kw.setdefault("status_updated_at", "2026-09-29T10:00:00Z")
    return BoxArc(**kw)


def _tenant(**kw):
    kw.setdefault("tenant_id", "tnt_test1")
    kw.setdefault("stage", 2)
    kw.setdefault("approvals_url", "https://approve.example/a/tnt_test1")
    kw.setdefault("boxes", {"box-1": _arc()})
    return TenantRecord(**kw)


@pytest.fixture()
def store_path(tmp_path):
    return str(tmp_path / "tenants.json")


@pytest.fixture()
def store(store_path):
    return TenantStore(store_path)


def _stub_verify(message: bytes, signature: bytes, public_key: str) -> bool:
    # Stub for the injected ed25519 primitive: a valid signature is
    # b"sig:" + the canonical message; the public key is carried so tests
    # prove the verifier receives the record's linked key.
    return signature == b"sig:" + message and public_key.startswith("ssh-ed25519")


class _RecordingVerify:
    """Wraps a verify stub, recording every (message, signature, public_key) call.

    Test-only — do not copy into production: recording real (message,
    signature, public_key) triples outside a test would be a
    secret-handling hazard.

    Lets a test pin the verification *mechanism* (verification ran, and
    against which key) rather than just the request's outcome.
    """

    def __init__(self, inner):
        self.inner = inner
        self.calls = []

    def __call__(self, message, signature, public_key):
        self.calls.append((message, signature, public_key))
        return self.inner(message, signature, public_key)


def _service(store, verify=_stub_verify):
    return TenantStatusService(store, verify)


def _signed_headers(tenant_id, ts=None):
    ts = str(ts if ts is not None else int(time.time()))
    msg = canonical_poll_message(tenant_id, ts)
    return {
        "x-tenant-id": tenant_id,
        "x-signature-ts": ts,
        "x-signature": __import__("base64").b64encode(b"sig:" + msg).decode(),
    }


# ---------------------------------------------------------------------------
# §2 — vocabulary spelling


def test_vocabulary_is_exactly_the_13_codes():
    assert STATUS_CODES == frozenset(
        {
            "provisioning",
            "live",
            "waiting-on-approval",
            "approved",
            "box-unhealthy",
            "connection-unreachable",
            "policy-misfire",
            "no-gated-action",
            "human-denied",
            "human-drop-off",
            "stuck",
            "provisioning-failed",
            "maintenance",
        }
    )


def test_operator_only_codes_carry_no_human_key():
    assert OPERATOR_ONLY == {"policy-misfire", "no-gated-action"}
    for code in OPERATOR_ONLY:
        assert human_key_for(code) is None
    for code in STATUS_CODES - OPERATOR_ONLY:
        assert human_key_for(code) == code


# ---------------------------------------------------------------------------
# §2 — transition rules


def test_provisioning_live_entry_needs_the_and_combine():
    arc = _arc()
    apply_event(arc, "provider-running")
    assert arc.code == "provisioning"  # relay not reachable yet — held
    assert not live_entry_ready(arc)
    apply_event(arc, "relay-reachable")
    assert arc.code == "live"
    assert live_entry_ready(arc)


def test_no_backwards_moves():
    from tenant_status import _move

    arc = _arc(code="live", status_updated_at="2026-09-29T10:05:00Z")
    with pytest.raises(TransitionError):
        _move(arc, "provisioning")  # rule-7 restarts are the only regressions
    # stuck has no generic exit — only stuck-cleared (to the latch) or a
    # rule-7 reprovision
    arc2 = _arc(code="stuck", latched="live", status_updated_at="2026-09-29T10:05:00Z")
    with pytest.raises(TransitionError):
        _move(arc2, "live")


def test_rule_1_failure_modes():
    arc = _arc()
    apply_event(arc, "provisioning-terminal-failure")
    assert arc.code == "provisioning-failed"
    arc2 = _arc()
    apply_event(arc2, "stack-deploy-failed", stage="swap-proxy")
    assert arc2.code == "box-unhealthy"
    assert arc2.detail == "stack-deploy:swap-proxy"


def test_rule_2_approval_arc():
    arc = _arc()
    apply_event(arc, "provider-running")
    apply_event(arc, "relay-reachable")
    apply_event(arc, "approval-filed", check="gate-1")
    assert arc.code == "waiting-on-approval"
    assert arc.detail == "filed-approval: gate-1"
    apply_event(arc, "approval-granted")
    assert arc.code == "approved"
    assert arc.detail is None  # terminal codes carry no detail


def test_rule_3_denial_and_dropoff():
    for event, code in (("approval-denied", "human-denied"), ("approval-expired", "human-drop-off")):
        arc = _arc()
        apply_event(arc, "provider-running")
        apply_event(arc, "relay-reachable")
        apply_event(arc, "approval-filed")
        apply_event(arc, event)
        assert arc.code == code


def test_rule_5_operator_only_codes_are_end_states():
    arc = _arc(code="live", status_updated_at="2026-09-29T10:05:00Z")
    apply_event(arc, "gate-policy-misfire")
    assert arc.code == "policy-misfire"
    with pytest.raises(TransitionError):
        apply_event(arc, "approval-filed")  # never progressing
    arc2 = _arc(code="live", status_updated_at="2026-09-29T10:05:00Z")
    apply_event(arc2, "pilot-no-gated-action")
    assert arc2.code == "no-gated-action"


def test_rule_6_relay_suspension_latches_and_re_evaluates():
    # A post-live arc has provider_running=True (it entered live via the
    # §4 AND-combine); the fixture pins that invariant so the
    # relay-recovered provider re-check (#1462) sees a live provider.
    arc = _arc(code="live", status_updated_at="2026-09-29T10:05:00Z",
               provider_running=True, relay_reachable=True)
    apply_event(arc, "relay-failure")
    assert arc.code == "connection-unreachable"
    assert arc.latched == "live"
    # Arc-advancing events during the suspension update the latch...
    apply_event(arc, "approval-filed", check="gate-1")
    assert arc.code == "connection-unreachable"  # ...never the displayed code
    assert arc.latched == "waiting-on-approval"
    # ...and recovery re-evaluates to the updated latch.
    apply_event(arc, "relay-recovered")
    assert arc.code == "waiting-on-approval"
    assert arc.detail == "filed-approval: gate-1"


def test_rule_6_not_entered_pre_live():
    arc = _arc()  # provisioning
    with pytest.raises(TransitionError):
        apply_event(arc, "relay-failure")


def test_rule_7_session_restart_carve_outs():
    for start in ("box-unhealthy", "provisioning-failed", "live", "approved", "stuck"):
        arc = _arc(
            code=start,
            status_updated_at="2026-09-29T10:05:00Z",
            session=1,
            detail="box-unhealthy: old" if start == "box-unhealthy" else None,
            latched="live" if start == "stuck" else None,
            provider_running=True,
            relay_reachable=True,
        )
        apply_event(arc, "operator-reprovision")
        assert arc.code == "provisioning"
        assert arc.session == 2
        assert arc.status_updated_at  # reset — the 10-minute clock restarts
        assert arc.detail is None
        assert arc.latched is None and arc.latched_detail is None
        assert not arc.provider_running and not arc.relay_reachable
    # Not licensed from anywhere else (e.g. mid-arc waiting-on-approval).
    arc = _arc(code="waiting-on-approval", status_updated_at="2026-09-29T10:05:00Z")
    with pytest.raises(TransitionError):
        apply_event(arc, "operator-reprovision")


def test_rule_8_maintenance_latch():
    # Post-live invariant (see the rule-6 test above): the provider was
    # running and the relay reachable when the arc went live, so the
    # maintenance-completed liveness re-check restores the latch.
    arc = _arc(code="live", status_updated_at="2026-09-29T10:05:00Z",
               provider_running=True, relay_reachable=True)
    apply_event(arc, "maintenance-started", operation="reimage-for-update")
    assert arc.code == "maintenance"
    assert arc.detail == "maintenance: reimage-for-update"
    assert arc.latched == "live"
    apply_event(arc, "maintenance-completed")
    assert arc.code == "live"  # returns the latch; arc neither advanced nor restarted


def test_rule_8_maintenance_only_from_live_or_approved():
    arc = _arc()  # provisioning
    with pytest.raises(TransitionError):
        apply_event(arc, "maintenance-started")


def test_rule_8_maintenance_failure():
    arc = _arc(code="approved", status_updated_at="2026-09-29T10:05:00Z")
    apply_event(arc, "maintenance-started")
    assert arc.latched == "approved"  # latch set at maintenance entry
    apply_event(arc, "maintenance-failed", check="disk-resize")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "maintenance-failed: disk-resize"
    assert arc.latched is None and arc.latched_detail is None  # exit clears the latch


def test_smoke_report_failed_detail_format():
    # The §2-named "box-unhealthy: <check>" detail format, pinned.
    arc = _arc(code="live", status_updated_at="2026-09-29T10:05:00Z")
    apply_event(arc, "smoke-report-failed", check="relay-dial")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: relay-dial"


def test_rule_6_suspension_from_approval_arc_and_approved():
    for start in ("waiting-on-approval", "approved"):
        # Post-live invariant (see the rule-6 test above): the provider
        # was running when the arc went post-live.
        arc = _arc(code=start, status_updated_at="2026-09-29T10:05:00Z",
                   provider_running=True, relay_reachable=True)
        apply_event(arc, "relay-failure")
        assert arc.code == "connection-unreachable"
        assert arc.latched == start
        apply_event(arc, "relay-recovered")
        assert arc.code == start
        assert arc.latched is None


# ---------------------------------------------------------------------------
# Liveness-loss transitions (#1461 / #1462) + fresh-arc timestamp (#1468)


def _live_arc(**kw):
    """A live arc in the consistent post-entry state (provider running,
    relay reachable — the §4 AND-combine inputs that admitted it)."""
    kw.setdefault("code", "live")
    kw.setdefault("status_updated_at", "2026-09-29T10:05:00Z")
    kw.setdefault("provider_running", True)
    kw.setdefault("relay_reachable", True)
    return _arc(**kw)


def test_provider_dead_demotes_post_live_arcs_to_box_unhealthy():
    # #1461: a dead box after live is box-unhealthy (rules 1/2/4), with
    # the provider-death sub-code in detail — not sticky-live.
    for start in ("live", "waiting-on-approval", "approved"):
        arc = _live_arc(code=start)
        apply_event(arc, "provider-dead")
        assert arc.code == "box-unhealthy"
        assert arc.detail == "box-unhealthy: provider-dead"
        assert arc.provider_running is False


def test_provider_dead_at_provisioning_holds_per_rule_1a():
    # Reachability failure at provisioning holds (no bundle handed out)
    # until the driver reports terminal failure — never a demotion.
    arc = _arc()  # provisioning
    apply_event(arc, "provider-dead")
    assert arc.code == "provisioning"
    assert arc.provider_running is False


def test_provider_dead_leaves_terminal_and_operator_codes_alone():
    # A verdict already ended the arc; provider death never rewrites it.
    for start in ("human-denied", "human-drop-off", "provisioning-failed",
                  "policy-misfire", "no-gated-action", "box-unhealthy"):
        arc = _arc(code=start, status_updated_at="2026-09-29T10:05:00Z")
        apply_event(arc, "provider-dead")
        assert arc.code == start


def test_relay_down_suspends_post_live_arcs():
    # #1461, relay half: relay/cert-path failure is rule 6's suspension,
    # not box-unhealthy — with the sub-code in detail.
    for start in ("live", "waiting-on-approval", "approved"):
        arc = _live_arc(code=start)
        apply_event(arc, "relay-down")
        assert arc.code == "connection-unreachable"
        assert arc.latched == start
        assert arc.detail == "relay-down"
        assert arc.relay_reachable is False


def test_relay_down_at_provisioning_holds_per_rule_1a():
    arc = _arc()  # provisioning
    apply_event(arc, "relay-down")
    assert arc.code == "provisioning"
    assert arc.relay_reachable is False


def test_provider_dead_during_suspension_updates_the_latch():
    # #1462 repro: live -> relay-failure -> provider-dead ->
    # relay-recovered must NOT restore live with a dead provider.
    arc = _live_arc()
    apply_event(arc, "relay-failure")
    assert arc.code == "connection-unreachable"
    apply_event(arc, "provider-dead")
    assert arc.code == "connection-unreachable"  # still showing suspension
    assert arc.latched == "box-unhealthy"
    assert arc.latched_detail == "box-unhealthy: provider-dead"
    apply_event(arc, "relay-recovered")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: provider-dead"
    assert arc.latched is None


def test_relay_recovered_rechecks_provider_as_backstop():
    # #1462 backstop: a suspension record persisted before the fix (latch
    # still live, provider already dead) demotes on recovery instead of
    # restoring a live code the dead provider no longer supports.
    arc = _live_arc(code="connection-unreachable", latched="live",
                    provider_running=False)
    apply_event(arc, "relay-recovered")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: provider-dead"


def test_relay_failure_reentry_while_suspended_refreshes_detail():
    # relay-down suspends; the instrument's relay-failure for the same
    # outage is a duplicate suspension signal, not an error.
    arc = _live_arc()
    apply_event(arc, "relay-down")
    assert arc.code == "connection-unreachable"
    apply_event(arc, "relay-failure", detail="cert-expired")
    assert arc.code == "connection-unreachable"
    assert arc.latched == "live"  # first suspension entry owns the latch
    assert arc.detail == "cert-expired"
    # A detail-less re-entry keeps the existing detail.
    apply_event(arc, "relay-failure")
    assert arc.detail == "cert-expired"


def test_fresh_arc_defaults_status_updated_at_to_created_at():
    # #1468: a fresh arc that has never transitioned must not serve "".
    arc = BoxArc(box_id="b", created_at="2026-09-29T10:00:00Z")
    assert arc.status_updated_at == "2026-09-29T10:00:00Z"
    body = status_response(_tenant(boxes={"b": arc}))
    assert body["status_updated_at"] == "2026-09-29T10:00:00Z"
    # An explicit empty value (pre-fix persisted shape) heals the same way.
    arc2 = BoxArc(box_id="b", created_at="2026-09-29T10:00:00Z",
                  status_updated_at="")
    assert arc2.status_updated_at == "2026-09-29T10:00:00Z"


# ---------------------------------------------------------------------------
# Round-2 review fixes: stuck/maintenance exits, timestamped refresh,
# hold matrix, backstop breadth, store round-trips, end-to-end path


def test_provider_dead_during_stuck_demotes_on_clear():
    # Review B1 (Engineering): the stuck exit re-evaluates the latch —
    # provider death discovered while stuck demotes on clear.
    arc = _live_arc()
    apply_event(arc, "operator-mark-stuck")
    assert arc.code == "stuck"
    apply_event(arc, "provider-dead")
    assert arc.code == "stuck"  # still showing stuck
    assert arc.latched == "box-unhealthy"  # flip-time latch update
    apply_event(arc, "stuck-cleared")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: provider-dead"
    assert arc.latched is None


def test_provider_dead_during_maintenance_demotes_on_complete():
    arc = _live_arc()
    apply_event(arc, "maintenance-started", operation="reimage-for-update")
    assert arc.code == "maintenance"
    apply_event(arc, "provider-dead")
    assert arc.latched == "box-unhealthy"
    apply_event(arc, "maintenance-completed")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: provider-dead"
    assert arc.latched is None


def test_stuck_clear_backstop_heals_stale_record():
    # Exit-time backstop: a stuck record persisted before the fix (latch
    # still live, provider already dead) demotes on clear.
    arc = _live_arc(code="stuck", latched="live", provider_running=False)
    apply_event(arc, "stuck-cleared")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: provider-dead"


def test_maintenance_complete_backstop_heals_stale_record():
    arc = _live_arc(code="maintenance", latched="approved",
                    provider_running=False)
    apply_event(arc, "maintenance-completed")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: provider-dead"


def test_relay_down_during_stuck_converts_exit_to_suspension():
    # The relay is down at clear time: the honest code is the rule-6
    # suspension with the latch preserved, not the latch itself.
    arc = _live_arc()
    apply_event(arc, "operator-mark-stuck")
    apply_event(arc, "relay-down")
    assert arc.code == "stuck"  # relay-down is boolean-only during stuck
    apply_event(arc, "stuck-cleared")
    assert arc.code == "connection-unreachable"
    assert arc.latched == "live"  # preserved for a later relay-recovered
    assert arc.detail == "relay-down"
    apply_event(arc, "relay-recovered")
    assert arc.code == "live"
    assert arc.latched is None


def test_relay_down_during_maintenance_converts_exit_to_suspension():
    arc = _live_arc()
    apply_event(arc, "maintenance-started", operation="reimage-for-update")
    apply_event(arc, "relay-down")
    apply_event(arc, "maintenance-completed")
    assert arc.code == "connection-unreachable"
    assert arc.latched == "live"
    apply_event(arc, "relay-recovered")
    assert arc.code == "live"


def test_approval_on_provider_demoted_suspension_is_rejected():
    # Review B2 (Engineering): advancing a dead box is rejected — the
    # human tap fails closed, state preserved, operator path is
    # reprovision. Pre-fix the tap succeeded and wrongly restored a
    # live-ish code.
    arc = _live_arc()
    apply_event(arc, "relay-failure")
    apply_event(arc, "provider-dead")
    assert arc.latched == "box-unhealthy"
    with pytest.raises(TransitionError):
        apply_event(arc, "approval-filed", check="gate-1")
    assert arc.code == "connection-unreachable"
    assert arc.latched == "box-unhealthy"
    assert arc.latched_detail == "box-unhealthy: provider-dead"


def test_relay_failure_reentry_bumps_timestamp_on_detail_change(monkeypatch):
    # Review B3 (Engineering) / QA-1: a detail that actually changes bumps
    # status_updated_at (the served body changed); a detail-less re-entry
    # or one repeating the current detail is a pure no-op.
    arc = _live_arc()
    apply_event(arc, "relay-failure", detail="relay-down")
    before = arc.status_updated_at
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T11:00:00Z")
    apply_event(arc, "relay-failure", detail="cert-expired")
    assert arc.detail == "cert-expired"
    assert arc.status_updated_at == "2026-09-29T11:00:00Z"
    assert arc.status_updated_at != before
    # Repeating the current detail: no bump.
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T12:00:00Z")
    apply_event(arc, "relay-failure", detail="cert-expired")
    assert arc.status_updated_at == "2026-09-29T11:00:00Z"
    # Detail-less re-entry: no bump.
    apply_event(arc, "relay-failure")
    assert arc.status_updated_at == "2026-09-29T11:00:00Z"


def test_relay_down_hold_matrix():
    # QA-3a/3b: relay-down is boolean-only on terminal/operator codes,
    # on box-unhealthy, and while already suspended (no-op on code, latch,
    # and detail — it carries no detail to refresh with).
    for start in ("human-denied", "human-drop-off", "provisioning-failed",
                  "policy-misfire", "no-gated-action", "box-unhealthy"):
        arc = _arc(code=start, status_updated_at="2026-09-29T10:05:00Z",
                   detail="box-unhealthy: relay-dial"
                   if start == "box-unhealthy" else None)
        apply_event(arc, "relay-down")
        assert arc.code == start
        assert arc.relay_reachable is False
    arc = _live_arc()
    apply_event(arc, "relay-failure", detail="cert-expired")
    apply_event(arc, "relay-down")
    assert arc.code == "connection-unreachable"
    assert arc.latched == "live"
    assert arc.detail == "cert-expired"  # untouched by the boolean flip


def test_provider_dead_on_suspended_terminal_latch_preserves_verdict():
    # QA-3c: a verdict already ended the arc — provider death never
    # rewrites it, and recovery restores the verdict.
    arc = _live_arc()
    apply_event(arc, "relay-failure")
    apply_event(arc, "approval-filed", check="gate-1")
    apply_event(arc, "approval-denied")
    assert arc.latched == "human-denied"
    apply_event(arc, "provider-dead")
    assert arc.latched == "human-denied"  # verdict wins over demotion
    apply_event(arc, "relay-recovered")
    assert arc.code == "human-denied"


def test_provider_dead_on_box_unhealthy_preserves_detail():
    # QA-3d: an already-unhealthy arc keeps its existing sub-code.
    arc = _live_arc()
    apply_event(arc, "smoke-report-failed", check="relay-dial")
    assert arc.detail == "box-unhealthy: relay-dial"
    apply_event(arc, "provider-dead")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: relay-dial"


def test_relay_recovered_backstop_covers_approval_arc_and_approved():
    # QA-4: the backstop demotes waiting-on-approval / approved latches
    # too, not just live.
    for latch in ("waiting-on-approval", "approved"):
        arc = _live_arc(code="connection-unreachable", latched=latch,
                        provider_running=False)
        apply_event(arc, "relay-recovered")
        assert arc.code == "box-unhealthy"
        assert arc.detail == "box-unhealthy: provider-dead"


def test_relay_recovered_ignores_stale_relay_flag():
    # QA-4: the relay input is deliberately NOT re-checked — the
    # instrument's relay-recovered is authoritative for its own layer.
    # A stale relay_reachable=False at recovery does not block the latch.
    arc = _live_arc(code="connection-unreachable", latched="live",
                    provider_running=True, relay_reachable=False)
    apply_event(arc, "relay-recovered")
    assert arc.code == "live"


def test_relay_down_chain_demotes_on_recovery():
    # QA-5a: the relay-down entry chain demotes exactly like the
    # relay-failure entry chain.
    arc = _live_arc()
    apply_event(arc, "relay-down")
    assert arc.code == "connection-unreachable"
    apply_event(arc, "provider-dead")
    assert arc.latched == "box-unhealthy"
    apply_event(arc, "relay-recovered")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: provider-dead"


def test_latched_detail_round_trips_through_relay_down():
    # QA-5b: the filed-approval detail survives suspension and recovery.
    arc = _live_arc()
    apply_event(arc, "approval-filed", check="gate-1")
    assert arc.detail == "filed-approval: gate-1"
    apply_event(arc, "relay-down")
    assert arc.latched == "waiting-on-approval"
    assert arc.latched_detail == "filed-approval: gate-1"
    apply_event(arc, "relay-recovered")
    assert arc.code == "waiting-on-approval"
    assert arc.detail == "filed-approval: gate-1"


def test_latch_advance_then_provider_dead_demotes():
    # QA-5c: approval filed during suspension, then provider death —
    # the updated latch demotes, recovery returns box-unhealthy.
    arc = _live_arc()
    apply_event(arc, "relay-failure")
    apply_event(arc, "approval-filed", check="gate-1")
    assert arc.latched == "waiting-on-approval"
    apply_event(arc, "provider-dead")
    assert arc.latched == "box-unhealthy"
    apply_event(arc, "relay-recovered")
    assert arc.code == "box-unhealthy"


def test_relay_failure_to_relay_failure_reentry():
    # QA-5d: instrument-to-instrument re-entry refreshes detail and
    # preserves the latch + latched_detail.
    arc = _live_arc()
    apply_event(arc, "approval-filed", check="gate-1")
    apply_event(arc, "relay-failure", detail="cert-expired")
    assert arc.latched_detail == "filed-approval: gate-1"
    apply_event(arc, "relay-failure", detail="tcp-refused")
    assert arc.code == "connection-unreachable"
    assert arc.detail == "tcp-refused"
    assert arc.latched == "waiting-on-approval"
    assert arc.latched_detail == "filed-approval: gate-1"


def test_fresh_arc_heal_survives_store_round_trip(store, store_path):
    # QA-6a: the #1468 heal survives the served path — a pre-fix record
    # with status_updated_at="" (or the key missing) heals on read, and
    # the hold snapshot carries the healed timestamp.
    import json as _json

    raw = {
        "version": 1,
        "tenants": {
            "tnt_heal": {
                "stage": 2,
                "approvals_url": "https://approve.example/a/tnt_heal",
                "session_token": None,
                "muse_public_key": None,
                "muse_id": None,
                "deleted": False,
                "last_reported": None,
                "boxes": {
                    "box-1": {
                        "created_at": "2026-09-29T10:00:00Z",
                        "code": "provisioning",
                        "status_updated_at": "",
                        "detail": None,
                        "latched": None,
                        "latched_detail": None,
                        "provider_running": False,
                        "relay_reachable": False,
                        "session": 1,
                    },
                    "box-2": {
                        "created_at": "2026-09-29T10:01:00Z",
                        "code": "provisioning",
                        # status_updated_at key missing (older shape)
                        "detail": None,
                        "latched": None,
                        "latched_detail": None,
                        "provider_running": False,
                        "relay_reachable": False,
                        "session": 1,
                    },
                },
            }
        },
    }
    with open(store_path, "w", encoding="utf-8") as fh:
        _json.dump(raw, fh)
    rec = store.get("tnt_heal")
    assert rec.boxes["box-1"].status_updated_at == "2026-09-29T10:00:00Z"
    assert rec.boxes["box-2"].status_updated_at == "2026-09-29T10:01:00Z"
    store.save(rec)
    reread = store.get("tnt_heal")
    assert reread.last_reported["status_updated_at"] in (
        "2026-09-29T10:00:00Z", "2026-09-29T10:01:00Z")


def test_select_reported_ranks_demoted_latch():
    # QA-6b: a suspended arc with a demoted latch ranks as box-unhealthy
    # (3) — a provisioning box outranks it, a live box outranks it.
    suspended = _arc(code="connection-unreachable", latched="box-unhealthy",
                     box_id="a-box",
                     status_updated_at="2026-09-29T10:05:00Z")
    provisioning = _arc(code="provisioning", box_id="b-box",
                        status_updated_at="2026-09-29T10:05:00Z")
    assert select_reported([suspended, provisioning]) is provisioning
    live = _live_arc(box_id="c-box")
    assert select_reported([suspended, live]) is live


def test_end_to_end_live_entry_suspension_recovery():
    # QA-7: the real live-entry path (no synthetic post-live fixture) —
    # suspension + recovery restores live; provider death during
    # suspension demotes.
    arc = _arc()
    apply_event(arc, "provider-running")
    apply_event(arc, "relay-reachable")
    assert arc.code == "live"
    assert arc.provider_running and arc.relay_reachable
    apply_event(arc, "relay-failure")
    assert arc.code == "connection-unreachable"
    apply_event(arc, "relay-recovered")
    assert arc.code == "live"
    apply_event(arc, "relay-failure")
    apply_event(arc, "provider-dead")
    apply_event(arc, "relay-recovered")
    assert arc.code == "box-unhealthy"


def test_provider_dead_at_provisioning_then_recovery_still_enters_live():
    # Eng N4: provider death at provisioning holds (rule 1(a)); a later
    # provider recovery still admits live entry via the AND-combine.
    arc = _arc()
    apply_event(arc, "provider-dead")
    assert arc.code == "provisioning"
    apply_event(arc, "provider-running")
    apply_event(arc, "relay-reachable")
    assert arc.code == "live"


def test_approved_arc_stays_honest():
    # Rule 4: a failed smoke/harness check on an approved box may surface
    # as box-unhealthy — the poll stays honest about the stack.
    arc = _arc(code="approved", status_updated_at="2026-09-29T10:05:00Z")
    apply_event(arc, "smoke-report-failed", check="confirmd-ping")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: confirmd-ping"


def test_stuck_is_operator_set_with_clear_path():
    # Post-live invariant (see the rule-6 test above): the provider was
    # running and the relay reachable when the arc went live, so the
    # stuck-cleared liveness re-check restores the latch.
    arc = _arc(code="live", status_updated_at="2026-09-29T10:05:00Z",
               provider_running=True, relay_reachable=True)
    apply_event(arc, "operator-mark-stuck")
    assert arc.code == "stuck"
    apply_event(arc, "stuck-cleared")
    assert arc.code == "live"  # re-evaluates to the current arc code


def test_unknown_event_and_code_rejected():
    arc = _arc()
    with pytest.raises(TenantStatusError):
        apply_event(arc, "bogus-event")
    from tenant_status import UnknownCodeError

    with pytest.raises(UnknownCodeError):
        human_key_for("LIVE")


# ---------------------------------------------------------------------------
# G8 — approvals_url: write-if-absent + re-read, mint-once, re-entry reads.


def test_ensure_approvals_url_mints_once_and_reentry_is_a_read(store, store_path):
    rec = _tenant(approvals_url=None)
    store.create(rec)
    calls = []

    def mint():
        calls.append(1)
        return "https://approve.example/a/tnt_test1"

    rec1, minted1 = store.ensure_approvals_url("tnt_test1", mint)
    assert minted1 and rec1.approvals_url == "https://approve.example/a/tnt_test1"
    # Funnel re-entry at any stage: read path, the mint never runs again,
    # the stored URL is unchanged, and the lock-protected atomic rewrite
    # carries identical content (so re-entry serializes behind writers
    # without changing anything).
    before = _store_hash(store_path)
    rec2, minted2 = store.ensure_approvals_url("tnt_test1", mint)
    assert not minted2 and rec2.approvals_url == rec1.approvals_url
    assert _store_hash(store_path) == before
    assert len(calls) == 1


def test_concurrent_mints_linearize(store):
    # Real race: 8 threads hammer ensure_approvals_url through a barrier so
    # the load->check->save cycles genuinely interleave. The exclusive
    # lock must serialize them: exactly one minter, and every caller —
    # winner or loser — renders the stored URL.
    rec = _tenant(approvals_url=None)
    store.create(rec)
    barrier = threading.Barrier(8)
    results = {}

    def racer(i):
        barrier.wait(timeout=30)

        def mint():
            return f"https://racer{i}.example/u"

        rendered, minted = store.ensure_approvals_url("tnt_test1", mint)
        results[i] = (minted, rendered.approvals_url)

    threads = [threading.Thread(target=racer, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert all(not t.is_alive() for t in threads), "racer thread hung"
    assert len(results) == 8
    assert sum(1 for minted, _ in results.values() if minted) == 1
    stored = store.get("tnt_test1").approvals_url
    for minted, url in results.values():
        assert url == stored, "loser rendered a URL the record doesn't hold"


def test_rotation_is_operator_only_with_reason(store):
    rec = _tenant()
    store.create(rec)
    with pytest.raises(TenantStatusError):
        store.rotate_approvals_url("tnt_test1", "https://evil.example/", reason="")
    rotated = store.rotate_approvals_url(
        "tnt_test1", "https://approve.example/b/tnt_test1", reason="domain change"
    )
    assert rotated.approvals_url == "https://approve.example/b/tnt_test1"


# ---------------------------------------------------------------------------
# §8 rule-1 — multi-box selection


def test_rule_1_live_beats_provisioning():
    arcs = [
        _arc(box_id="old", created_at="2026-09-29T09:00:00Z", code="live",
             status_updated_at="2026-09-29T09:05:00Z"),
        _arc(box_id="new", created_at="2026-09-29T10:00:00Z", code="provisioning",
             status_updated_at="2026-09-29T10:00:00Z"),
    ]
    assert select_reported(arcs).box_id == "old"


def test_rule_1_terminal_participates_only_without_nonterminal():
    live = _arc(box_id="a", created_at="2026-09-29T09:00:00Z", code="live",
                status_updated_at="2026-09-29T09:05:00Z")
    approved = _arc(box_id="b", created_at="2026-09-29T10:00:00Z", code="approved",
                    status_updated_at="2026-09-29T10:05:00Z")
    assert select_reported([live, approved]).box_id == "a"  # progress wins
    failed = _arc(box_id="c", created_at="2026-09-29T08:00:00Z",
                  code="provisioning-failed", status_updated_at="2026-09-29T08:05:00Z")
    assert select_reported([approved, failed]).box_id == "b"  # newest terminal


def test_rule_1_suspension_compares_by_latched_code():
    suspended = _arc(box_id="s", created_at="2026-09-29T09:00:00Z",
                     code="connection-unreachable", latched="waiting-on-approval",
                     status_updated_at="2026-09-29T09:05:00Z")
    plain = _arc(box_id="p", created_at="2026-09-29T10:00:00Z",
                 code="provisioning", status_updated_at="2026-09-29T10:00:00Z")
    # waiting-on-approval (rank 1) outranks provisioning (rank 2) even when suspended
    assert select_reported([suspended, plain]).box_id == "s"


def test_rule_1_tie_breaks_newest_then_lexical():
    arcs = [
        _arc(box_id="b-box", created_at="2026-09-29T10:00:00Z"),
        _arc(box_id="a-box", created_at="2026-09-29T10:00:00Z"),
    ]
    assert select_reported(arcs).box_id == "a-box"
    arcs2 = [
        _arc(box_id="a-box", created_at="2026-09-29T09:00:00Z"),
        _arc(box_id="b-box", created_at="2026-09-29T10:00:00Z"),
    ]
    assert select_reported(arcs2).box_id == "b-box"


# ---------------------------------------------------------------------------
# §3 — response schema


def test_response_schema_single_box():
    rec = _tenant()
    body = status_response(rec)
    assert body["tenant_id"] == "tnt_test1"
    assert body["status"] == "provisioning"
    assert body["status_updated_at"] == "2026-09-29T10:00:00Z"
    assert body["approvals_url"] == "https://approve.example/a/tnt_test1"
    assert "detail" not in body  # no sub-decision on provisioning
    assert body["human_key"] == "provisioning"


def test_response_schema_multi_box_disambiguates_in_detail():
    rec = _tenant(boxes={
        "kitchen-pi": _arc(box_id="kitchen-pi", code="box-unhealthy",
                           detail="box-unhealthy: relay-dial-failed",
                           status_updated_at="2026-09-29T10:05:00Z"),
        "dev": _arc(box_id="dev", status_updated_at="2026-09-29T10:00:00Z"),
    })
    body = status_response(rec)
    assert body["status"] == "provisioning"  # rank 2 beats rank 3
    assert body["detail"] == "provisioning @ box=dev"


def test_response_omits_human_key_for_operator_codes():
    rec = _tenant(boxes={"box-1": _arc(code="policy-misfire",
                                      status_updated_at="2026-09-29T10:05:00Z")})
    body = status_response(rec)
    assert body["status"] == "policy-misfire"
    assert "human_key" not in body


def test_last_reported_snapshot_persisted_on_write(store):
    rec = _tenant()
    store.create(rec)
    assert store.get("tnt_test1").last_reported["code"] == "provisioning"


def test_empty_candidate_set_holds_last_reported(store):
    # §8 G7 rule 1: the leading box is deleted pre-live with no other
    # candidates — the endpoint holds the last reported code, with detail
    # noting the operator event.
    rec = _tenant()
    store.create(rec)
    rec2 = store.get("tnt_test1")
    rec2.boxes = {}
    store.save(rec2)
    body = status_response(store.get("tnt_test1"))
    assert body["status"] == "provisioning"
    assert body["status_updated_at"] == "2026-09-29T10:00:00Z"
    assert "held: box deleted pre-live" in body["detail"]
    assert body["human_key"] == "provisioning"


def test_endpoint_serves_hold_after_box_deletion(store):
    rec = _tenant(session_token="sess-abc")
    store.create(rec)
    rec2 = store.get("tnt_test1")
    rec2.boxes = {}
    store.save(rec2)
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-abc"})
    assert status == 200
    assert body["status"] == "provisioning"
    assert "held: box deleted pre-live" in body["detail"]


def test_404_no_boxes_and_no_hold(store):
    rec = _tenant(session_token="sess-abc")
    rec.boxes = {}
    store.create(rec)  # last_reported stays None — nothing to hold
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-abc"})
    assert status == 404 and body["error"] == "no_servable_tenant_record"


# ---------------------------------------------------------------------------
# §1 — auth: 401/404 behavior


def _seeded(store):
    rec = _tenant(session_token="sess-abc", muse_public_key="ssh-ed25519 AAAAtest")
    store.create(rec)
    return rec


def test_401_with_no_credential(store):
    _seeded(store)
    status, body = _service(store).handle_get("/tenant/status", {})
    assert status == 401 and body["error"] == "unauthorized"


def test_401_on_bad_signature(store):
    _seeded(store)
    headers = _signed_headers("tnt_test1")
    headers["x-signature"] = "aGVsbG8="  # valid base64, wrong signature
    status, _ = _service(store).handle_get("/tenant/status", headers)
    assert status == 401


def test_401_on_stale_timestamp(store):
    _seeded(store)
    headers = _signed_headers("tnt_test1", ts=int(time.time()) - 3600)
    status, _ = _service(store).handle_get("/tenant/status", headers)
    assert status == 401


def test_401_on_unknown_tenant(store):
    _seeded(store)
    headers = _signed_headers("tnt_nonexistent")
    status, _ = _service(store).handle_get("/tenant/status", headers)
    assert status == 401  # identity cannot be established


def test_401_nonexistent_tenant_with_wellformed_signature(store):
    # The timing-oracle regression test: verification must RUN even when
    # the tenant id names no record (the stub would accept this
    # signature), and the record check must still reject afterwards.
    # The call-recording stub pins the mechanism, not just the 401: a
    # skipped verification could never produce this call record.
    _seeded(store)
    headers = _signed_headers("tnt_nonexistent")
    recorder = _RecordingVerify(_stub_verify)
    status, _ = TenantStatusService(store, recorder).handle_get("/tenant/status", headers)
    assert status == 401

    assert len(recorder.calls) == 1
    message, signature, public_key = recorder.calls[0]
    # Verification ran against the dummy key — the tenant names no
    # record, so there is no linked key to verify against.
    assert public_key == _DUMMY_VERIFY_KEY
    assert message == canonical_poll_message("tnt_nonexistent", headers["x-signature-ts"])
    # The stub accepted this signature, so the 401 came from the record
    # check rejecting afterwards — not from a verify rejection.
    assert signature == b"sig:" + message


def test_401_malformed_base64_signature(store):
    _seeded(store)
    headers = _signed_headers("tnt_test1")
    headers["x-signature"] = "!!!not-base64!!!"
    status, _ = _service(store).handle_get("/tenant/status", headers)
    assert status == 401


def test_401_future_timestamp_beyond_window(store):
    _seeded(store)
    headers = _signed_headers("tnt_test1", ts=int(time.time()) + 3600)
    status, _ = _service(store).handle_get("/tenant/status", headers)
    assert status == 401


def test_stale_cookie_short_circuits_before_signed_side(store):
    # Auth precedence: a present session cookie is tried first; a stale
    # cookie yields 401 even when the signed headers are valid.
    _seeded(store)
    headers = _signed_headers("tnt_test1")
    headers["cookie"] = "session=wrong"
    status, _ = _service(store).handle_get("/tenant/status", headers)
    assert status == 401


def test_404_pre_stage_2_with_valid_cookie(store):
    rec = _tenant(stage=1, approvals_url=None, session_token="sess-abc")
    store.create(rec)
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-abc"})
    assert status == 404 and body["error"] == "no_servable_tenant_record"


def test_404_deleted_tenant(store):
    rec = _tenant(session_token="sess-abc", deleted=True)
    store.create(rec)
    status, _ = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-abc"})
    assert status == 404


def test_200_both_auth_sides(store):
    _seeded(store)
    svc = _service(store)
    status, body = svc.handle_get("/tenant/status", {"cookie": "session=sess-abc"})
    assert status == 200 and body["status"] == "provisioning"
    status, body = svc.handle_get("/tenant/status", _signed_headers("tnt_test1"))
    assert status == 200 and body["status"] == "provisioning"


def test_404_unknown_path(store):
    _seeded(store)
    status, _ = _service(store).handle_get("/tenant/other", _signed_headers("tnt_test1"))
    assert status == 404


def _store_hash(store_path):
    return hashlib.sha256(open(store_path, "rb").read()).hexdigest()


def test_get_never_writes(store, store_path):
    _seeded(store)
    before = _store_hash(store_path)
    svc = _service(store)
    for _ in range(5):
        svc.handle_get("/tenant/status", {"cookie": "session=sess-abc"})
        svc.handle_get("/tenant/status", _signed_headers("tnt_test1"))
        svc.handle_get("/tenant/status", {})  # 401s must not write either
    assert _store_hash(store_path) == before  # byte-identical, not just mtime


# ---------------------------------------------------------------------------
# live HTTP: socket wiring, no-store header, 405 on POST


@pytest.fixture()
def live_server(store):
    _seeded(store)
    from http.server import HTTPServer

    from tenant_status import TenantStatusHandler, TenantStatusService

    TenantStatusHandler.service = TenantStatusService(store, _stub_verify)
    httpd = HTTPServer(("127.0.0.1", 0), TenantStatusHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    thread.join()


def _req(url, headers=None, method="GET"):
    req = urllib.request.Request(url + "/tenant/status", headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_live_get_200_and_no_store(live_server):
    status, headers, raw = _req(live_server, {"Cookie": "session=sess-abc"})
    assert status == 200
    assert headers.get("Cache-Control") == "no-store"
    body = json.loads(raw)
    assert body["status"] == "provisioning"
    assert body["human_key"] == "provisioning"


def test_live_401_no_credential(live_server):
    status, headers, _ = _req(live_server)
    assert status == 401
    assert headers.get("Cache-Control") == "no-store"


def test_live_405_on_post(live_server):
    status, _, _ = _req(live_server, {"Cookie": "session=sess-abc"}, method="POST")
    assert status == 405


def test_live_get_never_writes(live_server, store, store_path):
    before = _store_hash(store_path)
    for _ in range(3):
        _req(live_server, {"Cookie": "session=sess-abc"})
        _req(live_server)
    assert _store_hash(store_path) == before


def test_serve_refuses_trusting_verify():
    from tenant_status import _fail_closed_self_test

    with pytest.raises(TenantStatusError):
        _fail_closed_self_test(lambda m, s, k: True)  # always-true stub: refuse
    _fail_closed_self_test(lambda m, s, k: False)  # unwired-style: fail-closed, fine

    def raising(m, s, k):
        raise RuntimeError("boom")

    _fail_closed_self_test(raising)  # a raising verifier fails closed too
