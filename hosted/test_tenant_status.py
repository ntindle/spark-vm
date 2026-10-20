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
    MAX_DETAIL_BYTES,
    OPERATOR_ONLY,
    STATUS_CODES,
    TERMINAL_CODES,
    BoxArc,
    TenantRecord,
    TenantStatusError,
    TenantStatusService,
    TenantStore,
    TransitionError,
    _CORRUPT_LATCH_RANK,
    _DUMMY_VERIFY_KEY,
    _QUARANTINE_KIND_BOX,
    _QUARANTINE_KIND_ENVELOPE,
    _QUARANTINE_KIND_HOLD,
    _effective_rank,
    _find_quarantine_signal,
    _hold_quarantine_entry,
    _now_plus_iso,
    _quarantine_entry_kind,
    _quarantine_surface,
    apply_event,
    canonical_poll_message,
    created_epoch,
    human_key_for,
    live_entry_ready,
    scrub_detail,
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


def _live_session(store, tenant_id, token):
    # #1783: hand-set a LIVE magic-link session — the token AND a future
    # expiry, mirroring mint_session_token's contract. (A token alone is
    # a dead session: find_by_session_token fail-closes on it.)
    rec = store.get(tenant_id)
    rec.session_token = token
    rec.session_expires_at = _now_plus_iso(TenantStore.SESSION_TOKEN_TTL_S)
    store.save(rec)


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


def test_1463_issue_repro_smoke_failure_during_suspension_updates_latch():
    # #1463 repro, verified on pristine: live -> relay-failure ->
    # smoke-report-failed raised "TransitionError: illegal transition:
    # 'connection-unreachable' -> 'box-unhealthy'" — the signal most
    # likely to matter on recovery was lost to any producer that did not
    # retry. The arc-advancing event now routes through the latch-swap
    # path: the displayed code never changes during the suspension, and
    # recovery restores the updated latch.
    arc = _live_arc()
    apply_event(arc, "relay-failure")
    apply_event(arc, "smoke-report-failed", check="relay-dial")
    assert arc.code == "connection-unreachable"
    assert arc.latched == "box-unhealthy"
    assert arc.latched_detail == "box-unhealthy: relay-dial"
    apply_event(arc, "relay-recovered")
    assert arc.code == "box-unhealthy"
    assert arc.detail == "box-unhealthy: relay-dial"
    assert arc.latched is None


def test_1463_gate_and_pilot_verdicts_during_suspension_update_latch():
    # The other two non-approval arc-advancing events route the same way.
    for event, target in (
        ("gate-policy-misfire", "policy-misfire"),
        ("pilot-no-gated-action", "no-gated-action"),
    ):
        arc = _live_arc()
        apply_event(arc, "relay-failure")
        apply_event(arc, event)
        assert arc.code == "connection-unreachable"
        assert arc.latched == target
        apply_event(arc, "relay-recovered")
        assert arc.code == target
        assert arc.latched is None


def test_1463_latch_swap_moves_licensed_from_latched_code():
    # The §2 table licenses from the latched code, not the suspension:
    # pilot-no-gated-action is unlicensed from waiting-on-approval (rule 3
    # never lists it), so it raises TransitionError with the arc state
    # untouched — never dropped, never partially applied.
    arc = _live_arc()
    apply_event(arc, "approval-filed", check="gate-1")
    assert arc.code == "waiting-on-approval"
    apply_event(arc, "relay-failure")
    assert arc.latched == "waiting-on-approval"
    before = (arc.code, arc.detail, arc.latched, arc.latched_detail)
    with pytest.raises(TransitionError):
        apply_event(arc, "pilot-no-gated-action")
    assert (arc.code, arc.detail, arc.latched, arc.latched_detail) == before
    # Sanity: an event licensed from the latched code still routes.
    apply_event(arc, "smoke-report-failed", check="gate-1")
    assert arc.latched == "box-unhealthy"
    apply_event(arc, "relay-recovered")
    assert arc.code == "box-unhealthy"


def test_1463_suspensions_are_mutually_exclusive():
    # One latch per arc: entering a second latch-holding state while
    # latched raises TransitionError, state preserved. The message pins
    # the mutual-exclusion rule explicitly (fails on pristine, which used
    # per-entry messages that never named the rule).
    live = dict(code="live", status_updated_at="2026-09-29T10:05:00Z",
                provider_running=True, relay_reachable=True)
    # relay-failure during stuck / maintenance
    for entry in ("operator-mark-stuck", "maintenance-started"):
        arc = _arc(**live)
        apply_event(arc, entry, operation="reimage")
        before = (arc.code, arc.detail, arc.latched, arc.latched_detail)
        with pytest.raises(TransitionError, match="mutually exclusive"):
            apply_event(arc, "relay-failure")
        assert (arc.code, arc.detail, arc.latched, arc.latched_detail) == before
    # operator-mark-stuck / maintenance-started during connection-unreachable
    arc = _arc(**live)
    apply_event(arc, "relay-failure")
    before = (arc.code, arc.detail, arc.latched, arc.latched_detail)
    with pytest.raises(TransitionError, match="mutually exclusive"):
        apply_event(arc, "operator-mark-stuck")
    with pytest.raises(TransitionError, match="mutually exclusive"):
        apply_event(arc, "maintenance-started", operation="reimage")
    assert (arc.code, arc.detail, arc.latched, arc.latched_detail) == before
    # maintenance-started during stuck
    arc = _arc(**live)
    apply_event(arc, "operator-mark-stuck")
    before = (arc.code, arc.detail, arc.latched, arc.latched_detail)
    with pytest.raises(TransitionError, match="mutually exclusive"):
        apply_event(arc, "maintenance-started", operation="reimage")
    assert (arc.code, arc.detail, arc.latched, arc.latched_detail) == before
    # Negative pins: the mutual-exclusion message must only appear when a
    # latch is actually held. From latch-less codes the guards keep their
    # plain entry-rule messages (verified against the pre-pin wording).
    arc = _arc()  # provisioning
    with pytest.raises(TransitionError) as excinfo:
        apply_event(arc, "relay-failure")
    assert "no arc to suspend" in str(excinfo.value)
    assert "mutually exclusive" not in str(excinfo.value)
    for entry in ("operator-mark-stuck", "maintenance-started"):
        arc = _arc(code="waiting-on-approval",
                   status_updated_at="2026-09-29T10:05:00Z")
        with pytest.raises(TransitionError) as excinfo:
            apply_event(arc, entry, operation="reimage")
        assert "mutually exclusive" not in str(excinfo.value)


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


# ---------------------------------------------------------------------------
# #1786 — the suspension's served status_updated_at moves only when its
# served body moves; latch-routed events advance the latch's own clock
# (latched_status_updated_at) instead of the shared field.


def _suspended_arc(monkeypatch, **kw):
    """A relay-suspended arc with a deterministic clock.

    Suspension enters at 10:01:00Z; the caller re-points _now_iso before
    each subsequent event. kw overrides the live-arc fixture (e.g.
    code="approved" for the rejected-latch-event test).
    """
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:00:00Z")
    kw.setdefault("code", "live")
    arc = _arc(status_updated_at="2026-09-29T09:55:00Z",
               provider_running=True, relay_reachable=True, **kw)
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:01:00Z")
    apply_event(arc, "relay-failure", detail="relay-down")
    assert arc.code == "connection-unreachable"
    assert arc.latched == kw["code"]
    return arc


def test_1786_latch_routed_event_keeps_served_suspension_timestamp(monkeypatch):
    # The issue's own repro shape: a latch-routed event must not move
    # the suspension's served (code, detail, status_updated_at).
    arc = _suspended_arc(monkeypatch)
    assert arc.status_updated_at == "2026-09-29T10:01:00Z"
    # The latch's own clock starts at the arc's update time at entry.
    assert arc.latched_status_updated_at == "2026-09-29T09:55:00Z"
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:02:00Z")
    apply_event(arc, "approval-filed", check="gate-1")
    assert arc.code == "connection-unreachable"
    assert arc.detail == "relay-down"
    assert arc.status_updated_at == "2026-09-29T10:01:00Z"
    # ...while the latch advanced on its own clock.
    assert arc.latched == "waiting-on-approval"
    assert arc.latched_detail == "filed-approval: gate-1"
    assert arc.latched_status_updated_at == "2026-09-29T10:02:00Z"


def test_1786_rejected_latch_event_restores_suspension_state(monkeypatch):
    # approved is arc-terminal, so approval-filed from the latch is
    # illegal: the recursive raise must leave the suspension — and the
    # latch's clock — exactly as they were (fail-closed).
    arc = _suspended_arc(monkeypatch, code="approved")
    before = (arc.code, arc.detail, arc.status_updated_at,
              arc.latched, arc.latched_detail, arc.latched_status_updated_at)
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:02:00Z")
    with pytest.raises(TransitionError):
        apply_event(arc, "approval-filed", check="gate-1")
    assert (arc.code, arc.detail, arc.status_updated_at,
            arc.latched, arc.latched_detail,
            arc.latched_status_updated_at) == before


def test_1786_relay_recovered_clears_latch_clock(monkeypatch):
    arc = _suspended_arc(monkeypatch)
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:02:00Z")
    apply_event(arc, "approval-filed", check="gate-1")
    assert arc.latched_status_updated_at == "2026-09-29T10:02:00Z"
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:03:00Z")
    apply_event(arc, "relay-recovered")
    assert arc.code == "waiting-on-approval"
    assert arc.latched is None
    assert arc.latched_status_updated_at == ""
    # The served body changed (suspension -> latch), so the fresh bump
    # is licensed by bump-iff-served-body-changed.
    assert arc.status_updated_at == "2026-09-29T10:03:00Z"


def test_1786_latched_status_updated_at_persists_through_store(store, monkeypatch):
    arc = _suspended_arc(monkeypatch)
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:02:00Z")
    apply_event(arc, "approval-filed", check="gate-1")
    rec = _tenant(tenant_id="tnt_1786", boxes={"box-1": arc})
    store.create(rec)
    loaded = store.get("tnt_1786")
    assert loaded.boxes["box-1"].latched_status_updated_at == \
        "2026-09-29T10:02:00Z"


def test_1786_relay_down_entry_sets_latch_clock(monkeypatch):
    # Engineering B1: the R3 production path (relay-down event) creates
    # the latch through _suspend_on_relay_down, not relay-failure — the
    # latch clock must be set there too, never left "" while a latch is
    # held.
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:00:00Z")
    arc = _arc(code="live", provider_running=True, relay_reachable=True,
               status_updated_at="2026-09-29T09:55:00Z")
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:01:00Z")
    apply_event(arc, "relay-down", detail="relay")
    assert arc.code == "connection-unreachable"
    assert arc.latched == "live"
    assert arc.latched_status_updated_at == "2026-09-29T09:55:00Z"


def test_1786_same_second_latch_advance_still_records(monkeypatch):
    # Engineering B2: _now_iso is second-resolution — a suspension entry
    # and a latch advance in the same wall-clock second must still
    # record the advance (body-based detection, not clock compare).
    monkeypatch.setattr(tenant_status, "_now_iso",
                        lambda: "2026-09-29T10:01:00Z")
    arc = _arc(code="live", provider_running=True, relay_reachable=True,
               status_updated_at="2026-09-29T09:55:00Z")
    apply_event(arc, "relay-failure", detail="relay-down")
    apply_event(arc, "approval-filed", check="gate-1")  # same second
    assert arc.status_updated_at == "2026-09-29T10:01:00Z"  # served: stable
    assert arc.latched == "waiting-on-approval"
    assert arc.latched_status_updated_at == "2026-09-29T10:01:00Z"


def test_1786_all_latch_clear_paths_reset_latch_clock(monkeypatch):
    # Engineering B3: every latch exit resets the latch clock with the
    # latch — not just relay-recovered.
    def _stuck_arc():
        arc = _arc(code="live", provider_running=True, relay_reachable=True,
                   status_updated_at="2026-09-29T09:55:00Z")
        apply_event(arc, "operator-mark-stuck")
        assert arc.latched == "live"
        assert arc.latched_status_updated_at == "2026-09-29T09:55:00Z"
        return arc

    def _maintenance_arc():
        arc = _arc(code="live", provider_running=True, relay_reachable=True,
                   status_updated_at="2026-09-29T09:55:00Z")
        apply_event(arc, "maintenance-started", operation="scheduled-update")
        assert arc.latched == "live"
        assert arc.latched_status_updated_at == "2026-09-29T09:55:00Z"
        return arc

    arc = _stuck_arc()
    apply_event(arc, "stuck-cleared")
    assert arc.latched is None
    assert arc.latched_status_updated_at == ""

    arc = _maintenance_arc()
    apply_event(arc, "maintenance-completed")
    assert arc.latched is None
    assert arc.latched_status_updated_at == ""

    arc = _maintenance_arc()
    apply_event(arc, "maintenance-failed", check="img-pull")
    assert arc.code == "box-unhealthy"
    assert arc.latched is None
    assert arc.latched_status_updated_at == ""

    arc = _stuck_arc()
    apply_event(arc, "operator-reprovision")
    assert arc.code == "provisioning"
    assert arc.latched is None
    assert arc.latched_status_updated_at == ""


def test_1786_pre_fix_persisted_record_loads_without_latch_clock():
    # Records persisted before the field existed omit the key — the
    # constructor default ("") heals them on load.
    raw = {"boxes": {"box-1": {"created_at": "2026-09-29T10:00:00Z",
                               "status_updated_at": "2026-09-29T10:01:00Z"}}}
    rec = TenantStore._to_record("tnt_1786", raw)
    assert rec.boxes["box-1"].latched_status_updated_at == ""


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
    rec = _tenant()
    store.create(rec)
    _live_session(store, "tnt_test1", "sess-abc")
    rec2 = store.get("tnt_test1")
    rec2.boxes = {}
    store.save(rec2)
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-abc"})
    assert status == 200
    assert body["status"] == "provisioning"
    assert "held: box deleted pre-live" in body["detail"]


def test_404_no_boxes_and_no_hold(store):
    rec = _tenant()
    rec.boxes = {}
    store.create(rec)  # last_reported stays None — nothing to hold
    _live_session(store, "tnt_test1", "sess-abc")
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-abc"})
    assert status == 404 and body["error"] == "no_servable_tenant_record"


# ---------------------------------------------------------------------------
# §1 — auth: 401/404 behavior


def _seeded(store):
    rec = _tenant(muse_public_key="ssh-ed25519 AAAAtest")
    store.create(rec)
    _live_session(store, "tnt_test1", "sess-abc")
    return store.get("tnt_test1")


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
    rec = _tenant(stage=1, approvals_url=None)
    store.create(rec)
    _live_session(store, "tnt_test1", "sess-abc")
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-abc"})
    assert status == 404 and body["error"] == "no_servable_tenant_record"


def test_404_deleted_tenant(store):
    rec = _tenant(deleted=True)
    store.create(rec)
    _live_session(store, "tnt_test1", "sess-abc")
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


# ---------------------------------------------------------------------------
# #1783 — magic-link session is TTL-bound, not a forever-bearer


def test_mint_session_token_sets_one_hour_expiry(store):
    store.create(_tenant())
    token = store.mint_session_token("tnt_test1")
    rec = store.get("tnt_test1")
    assert rec.session_token == token
    assert rec.session_expires_at is not None
    expires = created_epoch(rec.session_expires_at)
    assert expires is not None
    skew = expires - time.time()
    # minted expiry ~TTL in the future (bounded above too — not 1970, not 2099)
    assert 3590 < skew < 3610
    # a freshly minted token authenticates
    assert store.find_by_session_token(token) is not None


def test_session_token_expiry_survives_round_trip(store, store_path):
    store.create(_tenant())
    token = store.mint_session_token("tnt_test1")
    persisted = json.load(open(store_path))["tenants"]["tnt_test1"]
    assert persisted["session_expires_at"] == store.get("tnt_test1").session_expires_at
    assert store.find_by_session_token(token) is not None


def test_expired_session_token_denied(store):
    # #1783: an expired token authenticates nobody — 401, re-mint via signup.
    store.create(_tenant())
    token = store.mint_session_token("tnt_test1")
    rec = store.get("tnt_test1")
    rec.session_expires_at = _now_plus_iso(-1)  # one second ago
    store.save(rec)
    assert store.find_by_session_token(token) is None
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=%s" % token})
    assert status == 401 and body["error"] == "unauthorized"


def test_pre_fix_session_without_expiry_denied(store):
    # #1783 fail-closed: a pre-fix record (token, no expiry key) is a dead
    # session — never grandfathered into the new world.
    store.create(_tenant())
    token = store.mint_session_token("tnt_test1")
    raw = json.load(open(store.path))["tenants"]["tnt_test1"]
    del raw["session_expires_at"]
    raw["session_token"] = token
    doc = json.load(open(store.path))
    doc["tenants"]["tnt_test1"] = raw
    json.dump(doc, open(store.path, "w"))
    assert store.find_by_session_token(token) is None
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=%s" % token})
    assert status == 401 and body["error"] == "unauthorized"


def test_malformed_session_expiry_denied(store):
    # #1783 fail-closed: a hand-corrupted expiry is not a live session —
    # unparseable reads as expired, never as immortal.
    store.create(_tenant())
    token = store.mint_session_token("tnt_test1")
    for bad in ("not-a-time", "2099-13-99T99:99:99Z", "", 42, None):
        rec = store.get("tnt_test1")
        rec.session_expires_at = bad
        store.save(rec)
        assert store.find_by_session_token(token) is None, bad


def test_non_string_session_token_denied(store, store_path):
    # #1792: a hostile hand-crafted record carrying a non-string
    # session_token must fail closed to "no match" (401) — never 500
    # out of the auth path via compare_digest's TypeError. The expiry
    # is kept live so the type guard, not the TTL, is what denies.
    store.create(_tenant())
    live_expiry = store.get("tnt_test1").session_expires_at or _now_plus_iso(3600)
    for bad in (42, 4.2, None, True, ["sess-abc"], {"t": "sess-abc"}):
        doc = json.load(open(store_path))
        doc["tenants"]["tnt_test1"]["session_token"] = bad
        doc["tenants"]["tnt_test1"]["session_expires_at"] = live_expiry
        json.dump(doc, open(store_path, "w"))
        assert store.find_by_session_token("sess-abc") is None, bad
        status, body = _service(store).handle_get(
            "/tenant/status", {"cookie": "session=sess-abc"})
        assert status == 401 and body["error"] == "unauthorized", bad
    # the str path is untouched: a real minted token still authenticates
    token = store.mint_session_token("tnt_test1")
    assert store.find_by_session_token(token) is not None


def test_remint_refreshes_session_token_and_expiry(store):
    # The single-live-token discipline: re-minting replaces the token AND
    # its expiry; the old token stops authenticating immediately.
    store.create(_tenant())
    token1 = store.mint_session_token("tnt_test1")
    token2 = store.mint_session_token("tnt_test1")
    rec = store.get("tnt_test1")
    assert token2 != token1
    # the expiry is TTL-bound on the re-mint too (same-second re-mint may
    # share the 1s-resolution instant — the property is that it is live)
    assert created_epoch(rec.session_expires_at) > time.time()
    assert store.find_by_session_token(token1) is None
    assert store.find_by_session_token(token2) is not None


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


# ---------------------------------------------------------------------------
# #1464: corrupt suspension latch — construction gate + fail-closed selection

_SUSPENSION_CODES = ("stuck", "connection-unreachable", "maintenance")


def _corrupt_latch_arc(latched_value, **kw):
    """Simulate the #1464 corrupt shape: a suspension code whose latch is
    missing or is itself a suspension code.

    The constructor rejects this shape for new data (#1464 half 1), so
    corrupt state is simulated through the one remaining channel — the
    dataclass fields are mutable after construction (and a pre-fix build
    could have persisted such a record).
    """
    kw.setdefault("box_id", "box-corrupt")
    arc = _arc(code="connection-unreachable", latched="live", **kw)
    arc.latched = latched_value
    return arc


def test_post_init_rejects_suspension_valued_latch():
    # The issue's exact repro shape: every suspension-latched combination
    # is rejected at construction, with the issue number in the message.
    for code in _SUSPENSION_CODES:
        for latch in _SUSPENSION_CODES:
            with pytest.raises(TenantStatusError) as ei:
                _arc(code=code, latched=latch)
            # QA round-1 N3: re-pin the message-substring the old
            # fail-loud test carried — the corruption names the latch.
            assert "#1464" in str(ei.value) and "latched" in str(ei.value)
    # Non-suspension latches still construct fine (incl. the legitimate
    # suspension entries, and the no-latch suspension shape selection
    # now degrades on instead of rejecting).
    _arc(code="connection-unreachable", latched="live")
    _arc(code="stuck", latched="waiting-on-approval")
    _arc(code="connection-unreachable", latched=None)


def test_effective_rank_bottom_for_corrupt_latch():
    healthy = _live_arc(box_id="box-healthy")
    for latched_value in (None, *_SUSPENSION_CODES):
        corrupt = _corrupt_latch_arc(latched_value)
        rank = _effective_rank(corrupt)
        # Below every healthy family (0 non-terminal, 1 terminal): the
        # corrupt arc can never win while a healthy candidate exists.
        assert rank > _effective_rank(healthy)
        assert rank > _effective_rank(_arc(code="approved"))
    # A healthy suspension arc still compares by its latched code.
    assert _effective_rank(_arc(code="stuck", latched="live")) == (
        0,
        0,
    )  # rank of "live"


def test_effective_rank_bottom_for_unknown_latch():
    # QA round-1: a latch mutated post-construction to a non-vocabulary
    # code is corrupt the same way — selection must not raise KeyError
    # out of _SELECTION_RANK.
    healthy = _live_arc(box_id="box-healthy")
    arc = _arc(code="stuck", latched="live", box_id="box-corrupt")
    arc.latched = "bogus-not-a-code"
    assert _effective_rank(arc) == (2, 0)
    assert select_reported([arc, healthy]).box_id == "box-healthy"


def test_selection_skips_corrupt_arc_for_healthy_candidate():
    healthy = _live_arc(box_id="box-healthy")
    corrupt = _corrupt_latch_arc("stuck")
    # Corrupt first in the list on purpose: min() must not pick it.
    assert select_reported([corrupt, healthy]).box_id == "box-healthy"
    # A latchless suspension is skipped the same way (was: TenantStatusError
    # out of selection).
    latchless = _corrupt_latch_arc(None)
    assert select_reported([latchless, healthy]).box_id == "box-healthy"


def test_selection_all_corrupt_still_serves_valid_code():
    # No healthy candidate: the endpoint must still serve a valid §2 code
    # (the suspension itself) instead of dropping the connection.
    corrupt = _corrupt_latch_arc("stuck", box_id="box-c1")
    reported = select_reported([corrupt])
    assert reported.code in STATUS_CODES
    rec = _tenant(boxes={"box-c1": corrupt})
    body = status_response(rec)
    assert body["status"] in STATUS_CODES


def test_store_create_and_response_withstand_corrupt_arc(store):
    # The issue's "blocks all its writes" half: create() used to raise
    # KeyError out of _save_record -> select_reported. The in-memory
    # record carries the corrupt arc (the pre-gate state); the write path
    # and the endpoint both degrade instead of raising.
    healthy = _live_arc(box_id="box-healthy")
    corrupt = _corrupt_latch_arc("stuck", box_id="box-corrupt")
    rec = _tenant(boxes={"box-healthy": healthy, "box-corrupt": corrupt})
    store.create(rec)  # was: KeyError 'stuck'
    body = status_response(rec)
    assert body["status"] == "live"  # the healthy arc is what serves
    # The hold snapshot also holds the healthy arc, not the corrupt one.
    assert rec.last_reported["code"] == "live"


# ---------------------------------------------------------------------------
# #1509 — load-time quarantine for pre-#1464 corrupt suspension latches
#
# Closes the residual test_legacy_corrupt_record_fails_loud_at_load pinned:
# a record persisted by a pre-#1464 build (suspension-valued latch in the
# JSON) is no longer bricked at load. Quarantine was chosen over heal
# deliberately — see the _to_record comment for the reasoning (a healed
# latchless suspension is a silently unrecoverable state, and read-path
# rewriting destroys the operator's only triage evidence).


def _legacy_corrupt_raw(tenant_id="tnt_legacy", box_id="box-1", **box_over):
    """One tenant as persisted by a pre-#1464 build: the box's latch is a
    suspension code (corrupt by construction)."""
    box = {
        "created_at": "2026-10-14T00:00:00Z",
        "code": "connection-unreachable",
        "status_updated_at": "2026-10-14T00:00:00Z",
        "detail": None,
        "latched": "stuck",  # the pre-fix corruption
        "latched_detail": None,
        "provider_running": False,
        "relay_reachable": False,
        "session": 1,
    }
    box.update(box_over)
    return {
        "version": 1,
        "tenants": {
            tenant_id: {
                "stage": 2,
                "approvals_url": f"https://approve.example/a/{tenant_id}",
                "boxes": {box_id: box},
            }
        },
    }


def _write_raw(store_path, raw):
    with open(store_path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh)


def test_legacy_corrupt_record_loads_and_quarantines(store, store_path):
    # The old pinned residual (fail-loud at load) is closed by this fix:
    # the legacy record loads, the corrupt arc is quarantined (never
    # served, never selected), and the raw entry is preserved verbatim.
    _write_raw(store_path, _legacy_corrupt_raw())
    rec = store.get("tnt_legacy")  # was: TenantStatusError naming #1464
    assert rec.boxes == {}
    q = rec.quarantined["box-1"]
    assert q["latched"] == "stuck"
    assert q["code"] == "connection-unreachable"
    assert q["raw"]["latched"] == "stuck"  # verbatim, never rewritten
    # The quarantine is load-derived, never persisted as such.
    persisted = json.load(open(store_path))["tenants"]["tnt_legacy"]
    assert "quarantined" not in persisted
    assert persisted["boxes"]["box-1"]["latched"] == "stuck"


def test_quarantine_serves_healthy_arcs_with_signal(store, store_path):
    # The tenant serves again over its healthy arcs; the served body
    # carries the operator-visible quarantine signal.
    raw = _legacy_corrupt_raw(box_id="box-1")
    raw["tenants"]["tnt_legacy"]["boxes"]["box-2"] = {
        "created_at": "2026-10-15T00:00:00Z",
        "code": "live",
        "status_updated_at": "2026-10-15T00:00:00Z",
        "detail": None,
        "latched": None,
        "latched_detail": None,
        "provider_running": True,
        "relay_reachable": True,
        "session": 1,
    }
    _write_raw(store_path, raw)
    rec = store.get("tnt_legacy")
    assert set(rec.boxes) == {"box-2"}
    body = status_response(rec)
    assert body["status"] == "live"
    (entry,) = body["quarantine"]
    assert entry["box_id"] == "box-1"
    assert entry["latched"] == "stuck"
    assert "#1464" in entry["reason"]


def test_two_corrupt_arcs_both_signaled(store, store_path):
    # QA round-1 N4: two corrupt arcs + one healthy — both are cut and
    # both are signaled (sorted), the healthy arc still serves.
    raw = _legacy_corrupt_raw(box_id="box-1")
    raw["tenants"]["tnt_legacy"]["boxes"]["box-0"] = dict(
        raw["tenants"]["tnt_legacy"]["boxes"]["box-1"], latched="maintenance"
    )
    raw["tenants"]["tnt_legacy"]["boxes"]["box-2"] = {
        "created_at": "2026-10-15T00:00:00Z",
        "code": "live",
        "status_updated_at": "2026-10-15T00:00:00Z",
        "detail": None,
        "latched": None,
        "latched_detail": None,
        "provider_running": True,
        "relay_reachable": True,
        "session": 1,
    }
    _write_raw(store_path, raw)
    rec = store.get("tnt_legacy")
    assert set(rec.boxes) == {"box-2"}
    body = status_response(rec)
    assert body["status"] == "live"
    assert [e["box_id"] for e in body["quarantine"]] == ["box-0", "box-1"]
    assert [e["latched"] for e in body["quarantine"]] == [
        "maintenance", "stuck"]


def test_quarantine_verbatim_round_trip(store, store_path):
    # A store write (the _mutate/_save_record cycle) must not drop or
    # rewrite the quarantined entry: it round-trips dict-equal (key order
    # ignored), and the next load re-derives the quarantine.
    _write_raw(store_path, _legacy_corrupt_raw())
    before = json.load(open(store_path))["tenants"]["tnt_legacy"]["boxes"]
    rec = store.get("tnt_legacy")
    store.save(rec)
    after = json.load(open(store_path))["tenants"]["tnt_legacy"]["boxes"]
    assert after == before  # byte-identical under the dict compare
    rec2 = store.get("tnt_legacy")  # re-derived, never sticky
    assert set(rec2.quarantined) == {"box-1"}


def test_quarantine_surface_scrubs_hostile_box_id(store, store_path):
    # The box id is free-form (box-chosen at enrollment): a hostile one
    # must not reach the served quarantine surface raw. Unit-asserted on
    # the surface builder (the all-corrupt endpoint path is covered by
    # test_all_corrupt_tenant_404s_with_quarantine_signal).
    nasty = "kitchen-pi\x1b[2K\r\n" + "x" * 300
    _write_raw(store_path, _legacy_corrupt_raw(box_id=nasty))
    rec = store.get("tnt_legacy")
    (entry,) = _quarantine_surface(rec.quarantined)
    served_id = entry["box_id"]
    assert "\x1b" not in served_id and "\r" not in served_id
    assert "\n" not in served_id
    assert len(served_id.encode("utf-8")) <= 64
    assert served_id.startswith("kitchen-pi[2K")


def test_all_corrupt_tenant_404s_with_quarantine_signal(store, store_path):
    # No healthy arcs and no hold: fail-closed 404, but never
    # bricked-silent — the quarantine signal rides on the 404 body.
    _write_raw(store_path, _legacy_corrupt_raw())
    _live_session(store, "tnt_legacy", "sess-quar")
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-quar"})
    assert status == 404
    assert body["error"] == "no_servable_tenant_record"
    (entry,) = body["quarantine"]
    assert entry["box_id"] == "box-1" and entry["latched"] == "stuck"


def test_quarantine_signal_rides_the_hold_path(store, store_path):
    # Engineering round-1 coverage gap / QA round-1 BLOCKING 1: an
    # all-quarantined tenant WITH a §8 hold serves the hold over HTTP
    # (200) plus the quarantine signal — the hold is not a silent cover
    # for the cut arcs.
    raw = _legacy_corrupt_raw()
    raw["tenants"]["tnt_legacy"]["last_reported"] = {
        "code": "live",
        "status_updated_at": "2026-10-14T00:00:00Z",
        "detail": "live: ok",
    }
    _write_raw(store_path, raw)
    _live_session(store, "tnt_legacy", "sess-hold")
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-hold"})
    assert status == 200
    assert body["status"] == "live"
    assert "held: box deleted pre-live" in body["detail"]
    (entry,) = body["quarantine"]
    assert entry["box_id"] == "box-1" and entry["latched"] == "stuck"


def test_quarantine_surface_tolerates_non_str_raw_code(store, store_path):
    # A hand-corrupted JSON store could carry "code": 42 on the corrupt
    # box — the served surface must not raise TypeError on it.
    _write_raw(store_path, _legacy_corrupt_raw(box_id="box-1", code=42))
    rec = store.get("tnt_legacy")
    assert set(rec.quarantined) == {"box-1"}
    (entry,) = _quarantine_surface(rec.quarantined)
    assert entry["code"] is None
    assert entry["latched"] == "stuck"


def test_quarantine_survives_operator_mutation(store, store_path):
    # An operator write (approvals-URL rotation here) persists the
    # quarantined arc instead of dropping it — on both the save() and
    # the _mutate() write paths (QA round-1 N4).
    _write_raw(store_path, _legacy_corrupt_raw())
    rec = store.get("tnt_legacy")
    rec.approvals_url = "https://approve.example/rotated"
    store.save(rec)
    store.rotate_approvals_url(
        "tnt_legacy", "https://approve.example/rotated-2",
        reason="qa-probe",
    )
    persisted = json.load(open(store_path))["tenants"]["tnt_legacy"]
    assert persisted["approvals_url"] == "https://approve.example/rotated-2"
    assert persisted["boxes"]["box-1"]["latched"] == "stuck"
    assert set(store.get("tnt_legacy").quarantined) == {"box-1"}


def test_quarantine_scope_extended_beyond_1509_shape(store, store_path):
    # #1784 supersedes the old surgical scope: a non-vocabulary code
    # WITHOUT the suspension latch no longer fails loud at load — it is
    # quarantined like every other construction failure (fail-closed:
    # never served, never selected, surfaced as code None). The old
    # fail-loud expectation ("the #1510 residual is not smuggled through
    # this path") is retired by the #1784 extension.
    _write_raw(
        store_path,
        _legacy_corrupt_raw(box_id="box-1", code="bogus-not-a-code",
                           latched=None),
    )
    rec = store.get("tnt_legacy")  # was: pytest.raises(TenantStatusError)
    assert rec.boxes == {}
    q = rec.quarantined["box-1"]
    assert q["raw"]["code"] == "bogus-not-a-code"
    assert "not a §2 status code" in q["reason"]
    (entry,) = _quarantine_surface(rec.quarantined)
    assert entry["code"] is None


def test_quarantine_both_bad_stays_fail_closed(store, store_path):
    # Both-bad: suspension-valued latch (quarantine trigger) plus a
    # non-vocabulary code (would fail construction). The arc is
    # quarantined — the bad code is swallowed into quarantine,
    # fail-closed: never served, never selected, surfaced as code None.
    _write_raw(
        store_path,
        _legacy_corrupt_raw(box_id="box-1", code="bogus-not-a-code"),
    )
    rec = store.get("tnt_legacy")  # no raise — the bad code never reaches it
    assert rec.boxes == {}
    assert set(rec.quarantined) == {"box-1"}
    (entry,) = _quarantine_surface(rec.quarantined)
    assert entry["code"] is None
    assert entry["latched"] == "stuck"
    assert "corrupt suspension latch" in entry["reason"]


# ---------------------------------------------------------------------------
# #1510 — fail-closed selection for invalid post-construction `code` shapes


def test_effective_rank_bottom_for_unknown_code():
    # The issue's exact repro: code is mutable post-construction, and
    # every engine write goes through check_code, so a non-vocabulary
    # code is constructible in-process only. Selection must bottom-rank
    # it (the #1464 corrupt family) instead of raising KeyError out of
    # _SELECTION_RANK. (Pre-fix: KeyError 'bogus-not-a-code'.)
    healthy = _live_arc(box_id="box-healthy")
    arc = _arc(code="live", box_id="box-corrupt")
    arc.code = "bogus-not-a-code"
    assert _effective_rank(arc) == _CORRUPT_LATCH_RANK == (2, 0)
    # Never selected while a healthy candidate exists; a KeyError used
    # to take down the whole selection here.
    assert select_reported([arc, healthy]).box_id == "box-healthy"
    # Below even terminal candidates: corrupt loses to everything.
    assert _effective_rank(arc) > _effective_rank(_arc(code="approved"))


def test_effective_rank_bottom_for_non_str_code():
    # Engineering round-1 nit: a non-str code (post-construction mutation
    # to 42, or an unhashable {}) bottom-ranks instead of raising
    # KeyError/TypeError out of the membership tests.
    healthy = _live_arc(box_id="box-healthy")
    for bad_code in (42, 4.5, {}):
        arc = _arc(code="live", box_id="box-corrupt")
        arc.code = bad_code
        assert _effective_rank(arc) == _CORRUPT_LATCH_RANK
        assert select_reported([arc, healthy]).box_id == "box-healthy"


def test_selection_all_unknown_codes_still_selects(store):
    # Every arc corrupt by post-construction code mutation: selection
    # itself no longer raises KeyError — the corrupt family is still
    # served as the only candidate (the serve boundary's human_key_for
    # check_code still fails loud on non-vocabulary codes, per its own
    # §3 contract: `status` must be a §2 code).
    arc = _arc(code="live", box_id="box-c1")
    arc.code = "bogus-not-a-code"
    assert select_reported([arc]).box_id == "box-c1"  # was: KeyError
    # And the write path survives it: _save_record -> select_reported
    # used to raise KeyError before persisting. The record persists with
    # the mutated code; the NEXT load quarantines the arc at the
    # construction boundary (#1784 — the old fail-loud-at-load pin is
    # retired: one bad box dict must never brick the tenant again).
    store.create(_tenant(boxes={"box-c1": arc}, tenant_id="tnt_bad"))
    rec = store.get("tnt_bad")
    assert rec.boxes == {}
    # The box is quarantined — and so is the §8 hold the create path
    # minted from the corrupt in-memory arc (non-vocabulary code): the
    # hold sanitizer catches it at the next load, fail-closed.
    assert set(rec.quarantined) == {"box-c1", "#last_reported"}


def test_latch_swap_path_stays_fail_loud(store):
    # Deliberate residual, pinned: applying an approval event to a
    # latchless suspension still raises at the mutation point — the
    # human's decision is never silently dropped. Selection failing
    # closed does not mean the engine swallows the event.
    arc = _corrupt_latch_arc(None)
    with pytest.raises(TenantStatusError):
        apply_event(arc, "approval-filed", check="gate-1")


# ---------------------------------------------------------------------------
# #1466 — endpoint-side detail scrub (construction-time, byte-capped)


def test_detail_scrubs_producer_control_chars():
    # A hostile/buggy producer's ANSI escapes and line breaks in the
    # event kwargs must not reach the human-rendered detail.
    arc = _arc()
    apply_event(
        arc, "stack-deploy-failed", stage="build\x1b[31mRED\r\ninjected"
    )
    assert arc.detail == "stack-deploy:build[31mREDinjected"
    assert not any(ord(c) < 0x20 or 0x7F <= ord(c) <= 0x9F for c in arc.detail)


def test_detail_byte_cap_ellipsis_codepoint_safe():
    # An unbounded producer substring is cut to MAX_DETAIL_BYTES UTF-8
    # bytes with an ellipsis, never splitting a code point.
    pad = "é" * 300  # 2 bytes each — 600 bytes of producer text
    arc = _arc()
    apply_event(arc, "smoke-report-failed", check=pad)
    encoded = arc.detail.encode("utf-8")
    assert len(encoded) <= MAX_DETAIL_BYTES
    assert arc.detail.endswith("…")
    # Decodes cleanly (no split code point) and keeps the sub-code prefix.
    arc.detail.encode("utf-8").decode("utf-8")
    assert arc.detail.startswith("box-unhealthy: ")


def test_detail_non_str_kwarg_fails_closed():
    # A non-str detail kwarg from a hostile producer fails loud at the
    # construction boundary — never stringified silently into the
    # served surface.
    arc = _arc(code="live")
    with pytest.raises(TypeError):
        apply_event(arc, "relay-failure", detail={"not": "a str"})


def test_serve_scrubs_box_id_suffix():
    # The §3 multi-box "@ box=<box-name>" suffix interpolates the
    # free-form box id into the served detail — the assembled surface
    # is scrubbed at serve time, not just the stored arc detail.
    nasty = "kitchen-pi\x1b[2K\r\n" + "x" * 300
    # Newer created_at so this arc wins selection and its detail is served;
    # same code as the other arc so the rank ties and recency decides.
    arc = _arc(
        box_id=nasty,
        code="provisioning",
        detail="provisioning: ok",
        created_at="2026-09-29T11:00:00Z",
    )
    body = status_response(_tenant(boxes={"a": arc, "b": _arc(box_id="b")}))
    served = body["detail"]
    assert "\x1b" not in served and "\r" not in served and "\n" not in served
    assert len(served.encode("utf-8")) <= MAX_DETAIL_BYTES
    assert "provisioning: ok" in served
    # The disambiguating suffix survives the scrub (Security round-1 B1):
    # the hostile box id is truncated to its own budget, never dropped.
    assert " @ box=kitchen-pi[2K" in served
    assert served.endswith("…")


def test_hostile_detail_cannot_crowd_out_box_suffix():
    # Security round-1 BLOCKING 1: a hostile 256-byte detail must not
    # crowd the "@ box=" disambiguator out of the byte budget — during
    # multi-box onboarding the human must always see which box a status
    # belongs to. Both arcs share the code so the rank ties and the
    # victim's newer created_at wins selection.
    victim = _arc(box_id="victim-box", created_at="2026-09-29T11:00:00Z")
    apply_event(victim, "stack-deploy-failed", stage="z" * 300)
    other = _arc(box_id="b", created_at="2026-09-29T10:00:00Z")
    apply_event(other, "stack-deploy-failed", stage="short")
    assert len(victim.detail.encode("utf-8")) <= MAX_DETAIL_BYTES
    body = status_response(_tenant(boxes={"a": victim, "b": other}))
    served = body["detail"]
    assert len(served.encode("utf-8")) <= MAX_DETAIL_BYTES
    assert served.endswith(" @ box=victim-box")


def test_constructor_scrubs_persisted_detail():
    # A record persisted by a pre-fix writer carries raw detail in the
    # JSON — the constructor scrub heals it on the load path, so the
    # store never re-serves unscrubbed text.
    arc = BoxArc(
        box_id="box-1",
        created_at="2026-10-15T00:00:00Z",
        detail="box-unhealthy: \x1b[31mRED",
        latched_detail="y" * 400,
    )
    assert arc.detail == "box-unhealthy: [31mRED"
    assert arc.latched_detail.endswith("…")
    assert len(arc.latched_detail.encode("utf-8")) <= 256


# ---------------------------------------------------------------------------
# #1467 — newest-wins compares parsed instants, not inverted strings


def test_created_at_fractional_newest_wins():
    # The issue's exact repro: "2026-09-29T10:00:00Z" vs
    # "2026-09-29T10:00:00.5Z" — the old complement-inversion picked the
    # OLDER arc; the parsed-instant key picks the newer one.
    older = _arc(box_id="a", created_at="2026-09-29T10:00:00Z")
    newer = _arc(box_id="b", created_at="2026-09-29T10:00:00.5Z")
    assert select_reported([older, newer]).box_id == "b"
    assert select_reported([newer, older]).box_id == "b"


def test_created_at_offset_equivalence():
    # Same instant in two spellings must tie and fall through to box-id
    # lexical — not misorder on string length. (The old
    # complement-inversion picked "b-box" here: at the first differing
    # character "2" inverts smaller than "0".)
    a = _arc(box_id="b-box", created_at="2026-09-29T12:00:00+02:00")
    b = _arc(box_id="a-box", created_at="2026-09-29T10:00:00Z")
    assert select_reported([a, b]).box_id == "a-box"
    # And a genuinely later instant still wins regardless of format.
    c = _arc(box_id="c-box", created_at="2026-09-29T12:00:01+02:00")
    assert select_reported([a, c]).box_id == "c-box"


def test_created_at_unparseable_sorts_oldest():
    # A malformed created_at can never outrank a real timestamp, and two
    # malformed records still order deterministically by box id.
    real = _arc(box_id="b", created_at="2026-09-29T10:00:00Z")
    junk = _arc(box_id="a", created_at="not-a-timestamp")
    assert select_reported([junk, real]).box_id == "b"
    junk2 = _arc(box_id="c", created_at=None)
    assert select_reported([junk, junk2]).box_id == "a"


def test_created_at_naive_treated_as_utc():
    # A naive timestamp reads as UTC (not local time): it ties with the
    # same instant's Z spelling, and the tie falls through to box-id
    # lexical. (The old inversion hit the exact prefix bug here — the
    # 19-char naive string is a prefix of the 20-char Z spelling, so
    # min() picked the naive arc instead of tying.)
    naive = _arc(box_id="b-box", created_at="2026-09-29T10:00:00")
    zoned = _arc(box_id="a-box", created_at="2026-09-29T10:00:00Z")
    assert select_reported([naive, zoned]).box_id == "a-box"
    # And a later naive instant still wins outright.
    later = _arc(box_id="c-box", created_at="2026-09-29T10:00:01")
    assert select_reported([zoned, later]).box_id == "c-box"


def test_scrub_detail_strips_lone_surrogates():
    # Engineering round-1 BLOCKING 1: the persisted store is JSON on
    # disk, and json.loads happily produces lone surrogates from
    # "\ud800" escapes — so scrub_detail must strip them, never raise.
    # A raise here would brick the tenant at load (the #1509 failure
    # mode the constructor healing exists to avoid).
    assert scrub_detail("a\ud800b") == "ab"
    assert scrub_detail("\udc00\udfff") == ""
    arc = BoxArc(
        box_id="box-1",
        created_at="2026-10-15T00:00:00Z",
        detail="pre-fix \ud800 raw",
    )
    assert arc.detail == "pre-fix  raw"


def test_hold_branch_scrubs_prefixed_last_reported():
    # Engineering round-1 BLOCKING 2: status_response's no-arcs hold
    # branch is a third serve assembly point — a pre-fix persisted
    # last_reported.detail (raw producer text) must be scrubbed and
    # capped at serve time, not served raw forever.
    raw_detail = "box-unhealthy: \x1b[31mRED" + "y" * 400
    rec = TenantRecord(
        tenant_id="tnt_hold",
        stage=2,
        approvals_url="https://approve.example/a/tnt_hold",
        boxes={},
        last_reported={
            "code": "box-unhealthy",
            "status_updated_at": "2026-10-15T00:00:00Z",
            "detail": raw_detail,
        },
    )
    body = status_response(rec)
    served = body["detail"]
    assert "\x1b" not in served
    assert len(served.encode("utf-8")) <= MAX_DETAIL_BYTES
    # The hostile prior is truncated (ellipsis), but the endpoint-minted
    # hold note — the safety-relevant part — survives intact at the end.
    assert served.endswith("… — held: box deleted pre-live")
    assert "held: box deleted pre-live" in served


def test_detail_truncation_never_splits_four_byte_char():
    # QA round-1 nit 3: a 4-byte char straddling the byte boundary is
    # dropped whole — the result stays byte-exact and decodes cleanly.
    pad = "x" * 253 + "𐍈"  # 253 + 4 = 257 bytes: the char must go
    out = scrub_detail(pad)
    assert out == "x" * 253 + "…"
    assert len(out.encode("utf-8")) == MAX_DETAIL_BYTES
    out.encode("utf-8").decode("utf-8")


def test_created_at_extra_fraction_digits_truncate_deterministically():
    # QA round-1 nit 3: >6 fractional digits are truncated to
    # microseconds by fromisoformat (deterministic, not rejected) —
    # ordering still follows the instant.
    a = _arc(box_id="a", created_at="2026-09-29T10:00:00.123456789Z")
    b = _arc(box_id="b", created_at="2026-09-29T10:00:00.123456Z")
    # Same microsecond instant -> tie -> box-id lexical.
    assert select_reported([b, a]).box_id == "a"
    c = _arc(box_id="c", created_at="2026-09-29T10:00:00.123457Z")
    assert select_reported([a, c]).box_id == "c"


def test_touch_leaves_arc_untouched_on_hostile_detail():
    # Security round-1 N1 / QA round-1 nit 2: a hostile non-str detail
    # kwarg fails closed with the arc untouched — never half-mutated.
    arc = _arc(code="live", detail="live-detail")
    with pytest.raises(TypeError):
        apply_event(arc, "relay-failure", detail=["not", "a", "str"])
    assert arc.code == "live"
    assert arc.detail == "live-detail"


# ---------------------------------------------------------------------------
# #1465 — signed-request replay: an observed (tenant_id, ts, signature)
# triple must be single-use inside SIGNATURE_WINDOW_S; a replay gets 401
# and the caller re-polls with a fresh timestamp.


def test_1465_replay_of_identical_triple_rejected(store):
    _seeded(store)
    svc = _service(store)
    headers = _signed_headers("tnt_test1")
    status, _ = svc.handle_get("/tenant/status", headers)
    assert status == 200
    # The exact observed triple, replayed within the window: 401.
    status, body = svc.handle_get("/tenant/status", headers)
    assert status == 401 and body["error"] == "unauthorized"


def test_1465_fresh_timestamp_resigns_and_accepts(store):
    # The ledger keys the exact triple, not the tenant: a fresh ts means a
    # fresh signature, and the poller keeps working.
    _seeded(store)
    svc = _service(store)
    ts0 = int(time.time())
    assert svc.handle_get("/tenant/status", _signed_headers("tnt_test1", ts=ts0))[0] == 200
    assert svc.handle_get("/tenant/status", _signed_headers("tnt_test1", ts=ts0 + 1))[0] == 200


def test_1465_invalid_signature_never_poisoned(store):
    # Only VERIFIED requests enter the ledger: a garbage triple for
    # (tenant_id, ts) must not block the real caller's later request.
    _seeded(store)
    svc = _service(store)
    ts0 = int(time.time())
    bad = _signed_headers("tnt_test1", ts=ts0)
    bad["x-signature"] = "aGVsbG8="  # valid base64, wrong signature
    assert svc.handle_get("/tenant/status", bad)[0] == 401
    assert svc._seen == {}  # the ledger holds no unverified entries
    assert svc.handle_get("/tenant/status", _signed_headers("tnt_test1", ts=ts0))[0] == 200


def test_1465_expired_entry_evicted_not_sticky(store):
    # Ledger entries live at most the freshness window: an entry older
    # than SIGNATURE_WINDOW_S is evicted on the next verified request, so
    # nothing haunts the tenant after its own window lapses.
    _seeded(store)
    svc = _service(store)
    ts0 = int(time.time()) - 200  # inside the 300s window
    assert svc.handle_get("/tenant/status", _signed_headers("tnt_test1", ts=ts0))[0] == 200
    assert svc.handle_get("/tenant/status", _signed_headers("tnt_test1", ts=ts0))[0] == 401
    for fp in list(svc._seen):
        svc._seen[fp] = time.time() - 301  # age the ledger entry past the window
    assert len(svc._seen) == 1
    assert svc.handle_get("/tenant/status", _signed_headers("tnt_test1", ts=ts0 + 1))[0] == 200
    assert svc._seen and all(
        seen_at > time.time() - 301 for seen_at in svc._seen.values()
    )


def test_store_lock_refuses_symlink_plant(store_path, tmp_path):
    # #1740: the <store>.lock sidecar serializes the approvals_url
    # write-if-absent ("exactly one mints") — a pre-planted symlink at
    # the lock path must fail loud (ELOOP), never silently move the
    # flock onto another file (lock-desync / lock-DoS would let two
    # concurrent stage-2 submissions both mint). Neuter-verified:
    # with plain open(..., "a") the create succeeds through the plant.
    store = TenantStore(store_path)
    victim = str(tmp_path / "victim.lock")
    with open(victim, "w", encoding="utf-8") as fh:
        fh.write("victim")
    os.symlink(victim, store_path + ".lock")
    with pytest.raises(OSError):
        store.create(_tenant())
    # The victim was never flocked through and no store file landed.
    with open(victim, encoding="utf-8") as fh:
        assert fh.read() == "victim"
    assert not os.path.lexists(store_path)


# ---------------------------------------------------------------------------
# #1784 — load quarantine for every box dict that fails construction,
# plus §8 hold-snapshot sanitization.
#
# #1509 quarantined only the suspension-valued-latch shape; any other
# malformed box dict (unhashable latch, missing created_at, unknown
# code, non-dict entry, non-str detail) still bricked the whole tenant
# at every read — and a corrupt last_reported KeyError'd in
# status_response's hold path before the quarantine signal could ride.


def _healthy_box_dict(**over):
    box = {
        "created_at": "2026-10-19T00:00:00Z",
        "code": "live",
        "status_updated_at": "2026-10-19T00:00:00Z",
        "detail": None,
        "latched": None,
        "latched_detail": None,
        "provider_running": True,
        "relay_reachable": True,
        "session": 1,
    }
    box.update(over)
    return box


def _raw_with_boxes(tenant_id="tnt_1784", boxes=None, **tenant_over):
    tenant = {"stage": 2, "approvals_url": "https://approve.example/a/x",
              "boxes": {} if boxes is None else boxes}
    tenant.update(tenant_over)
    return {"version": 1, "tenants": {tenant_id: tenant}}


def test_every_construction_failure_quarantines_not_bricks(store, store_path):
    # The four #1784 cases plus the non-dict / non-str-detail shapes:
    # the tenant loads, the healthy arc serves, every bad dict is cut
    # with its construction error as the reason — never a load raise.
    boxes = {
        "ok": _healthy_box_dict(),
        "unhashable-latch": _healthy_box_dict(latched=["stuck"]),
        "missing-created-at": {
            k: v for k, v in _healthy_box_dict().items()
            if k != "created_at"
        },
        "unknown-code": _healthy_box_dict(code=42),
        "non-dict-entry": "garbage",
        "non-str-detail": _healthy_box_dict(detail=42),
    }
    _write_raw(store_path, _raw_with_boxes(boxes=boxes))
    rec = store.get("tnt_1784")  # was: TypeError / UnknownCodeError
    assert set(rec.boxes) == {"ok"}
    assert set(rec.quarantined) == {
        "unhashable-latch", "missing-created-at", "unknown-code",
        "non-dict-entry", "non-str-detail",
    }
    reasons = {k: v["reason"] for k, v in rec.quarantined.items()}
    assert "unhashable type" in reasons["unhashable-latch"]
    assert "missing 1 required positional argument: 'created_at'" in reasons[
        "missing-created-at"]
    assert "not a §2 status code" in reasons["unknown-code"]
    assert "not a JSON object" in reasons["non-dict-entry"]
    assert "scrub_detail requires a str or None" in reasons["non-str-detail"]
    # Verbatim evidence is preserved for the operator.
    assert rec.quarantined["unknown-code"]["raw"]["code"] == 42
    assert rec.quarantined["non-dict-entry"]["raw"] == "garbage"
    # The healthy arc still serves, with the quarantine signal riding.
    body = status_response(rec)
    assert body["status"] == "live"
    assert len(body["quarantine"]) == 5


def test_general_quarantine_surface_bounds_and_scrubs_reason(store, store_path):
    # The construction error embeds box-controlled bytes (the hostile
    # code flows into check_code's message via {code!r}); the served
    # reason must be scrubbed (no C0/C1) and bounded.
    hostile = "live\x1b[2K\r\n" + "x" * 500
    _write_raw(store_path, _raw_with_boxes(
        boxes={"ok": _healthy_box_dict(),
               "hostile": _healthy_box_dict(code=hostile)}))
    rec = store.get("tnt_1784")
    (entry,) = [e for e in _quarantine_surface(rec.quarantined)
                if "hostile" in e["box_id"]]
    assert entry["code"] is None  # non-vocabulary code never surfaces raw
    assert "\x1b" not in entry["reason"] and "\r" not in entry["reason"]
    assert "\n" not in entry["reason"]
    assert len(entry["reason"].encode("utf-8")) <= 256


def test_corrupt_hold_dropped_with_quarantine_signal(store, store_path):
    # last_reported without a usable code: dropped to None at load, the
    # quarantine signal rides the fail-closed 404 (never a KeyError in
    # the hold path, never bricked-silent).
    raw = _raw_with_boxes(
        boxes={}, last_reported={"status_updated_at": "2026-10-19T00:00:00Z"})
    _write_raw(store_path, raw)
    rec = store.get("tnt_1784")
    assert rec.last_reported is None
    (entry,) = rec.quarantined.values()
    assert "#last_reported" in rec.quarantined
    assert "not a §2 status code" in entry["reason"]
    _live_session(store, "tnt_1784", "sess-hold1784")
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-hold1784"})
    assert status == 404
    assert body["error"] == "no_servable_tenant_record"
    (sig,) = body["quarantine"]
    assert sig["box_id"] == "#last_reported"


def test_corrupt_hold_non_dict_and_bad_timestamp(store, store_path):
    for bad_hold in (["not", "a", "dict"], {"code": "live"},
                     {"code": "live", "status_updated_at": 42}):
        _write_raw(store_path, _raw_with_boxes(
            boxes={}, last_reported=bad_hold))
        rec = store.get("tnt_1784")
        assert rec.last_reported is None
        assert "#last_reported" in rec.quarantined


def test_valid_and_absent_hold_untouched(store, store_path):
    # No hold (pre-first-write) and a valid hold both load cleanly with
    # no quarantine entries.
    _write_raw(store_path, _raw_with_boxes(boxes={"ok": _healthy_box_dict()}))
    rec = store.get("tnt_1784")
    assert rec.last_reported is None and rec.quarantined == {}
    _write_raw(store_path, _raw_with_boxes(
        boxes={}, last_reported={"code": "live",
                                 "status_updated_at": "2026-10-19T00:00:00Z",
                                 "detail": "d"}))
    rec = store.get("tnt_1784")
    assert rec.last_reported["code"] == "live" and rec.quarantined == {}
    assert status_response(rec)["status"] == "live"


def test_hold_and_box_quarantine_round_trip_verbatim(store, store_path):
    # The new quarantine entries round-trip verbatim through a save and
    # re-derive on the next load (the #1509 discipline, extended). Box
    # raws ride the boxes map; the hold's corrupt raw rides
    # last_reported itself (never the boxes map — Security round-1 B1).
    boxes = {
        "ok": _healthy_box_dict(),
        "bad": _healthy_box_dict(code=42),
        "nondict": [1, 2],
    }
    _write_raw(store_path, _raw_with_boxes(
        boxes=boxes, last_reported={"code": "bogus"}))
    rec = store.get("tnt_1784")
    store.save(rec)
    persisted = json.load(open(store_path))["tenants"]["tnt_1784"]
    assert "quarantined" not in persisted
    assert persisted["boxes"]["bad"]["code"] == 42
    assert persisted["boxes"]["nondict"] == [1, 2]
    assert "#last_reported" not in persisted["boxes"]
    # The corrupt hold was dropped at load; the save recomputed a fresh
    # hold from the healthy arc (the _save_record §8 refresh) and popped
    # the stale hold signal.
    assert persisted["last_reported"]["code"] == "live"
    rec2 = store.get("tnt_1784")
    assert set(rec2.quarantined) == {"bad", "nondict"}
    assert set(rec2.boxes) == {"ok"}
    assert rec2.quarantined["bad"]["raw"]["code"] == 42


def test_corrupt_hold_round_trips_verbatim_without_arcs(store, store_path):
    # No healthy arcs: no heal-recompute happens, so the corrupt hold
    # raw persists verbatim through last_reported and the signal
    # re-derives on every load (Security round-1 B3 — never silent
    # across a save cycle).
    _write_raw(store_path, _raw_with_boxes(
        boxes={}, last_reported=["not", "a", "dict"]))
    rec = store.get("tnt_1784")
    assert rec.last_reported is None
    store.save(rec)
    persisted = json.load(open(store_path))["tenants"]["tnt_1784"]
    assert persisted["last_reported"] == ["not", "a", "dict"]
    assert persisted["boxes"] == {}
    rec2 = store.get("tnt_1784")
    assert rec2.last_reported is None
    assert set(rec2.quarantined) == {"#last_reported"}
    assert rec2.quarantined["#last_reported"]["raw"] == ["not", "a", "dict"]
    # And the 404 still rides the signal after the save→load cycle.
    _live_session(store, "tnt_1784", "sess-rt")
    status, body = _service(store).handle_get(
        "/tenant/status", {"cookie": "session=sess-rt"})
    assert status == 404
    (sig,) = body["quarantine"]
    assert sig["box_id"] == "#last_reported"


def test_corrupt_boxes_envelope_quarantines_not_bricks(store, store_path):
    # Engineering round-1 B1: a non-dict boxes envelope (null, list)
    # quarantines the container instead of bricking the tenant with
    # AttributeError out of .items().
    for bad_envelope in (None, ["box-1"], "garbage"):
        tenant = {"stage": 2,
                  "approvals_url": "https://approve.example/a/x",
                  "boxes": bad_envelope,
                  "last_reported": {"code": "live",
                                    "status_updated_at": "2026-10-19T00:00:00Z",
                                    "detail": "d"}}
        _write_raw(store_path, {"version": 1, "tenants": {"tnt_1784": tenant}})
        rec = store.get("tnt_1784")  # was: AttributeError
        assert rec.boxes == {}
        (key,) = [k for k in rec.quarantined if k.startswith("#boxes")]
        assert "not a JSON object" in rec.quarantined[key]["reason"]
        assert rec.quarantined[key]["raw"] == bad_envelope
        # The valid hold still serves over the (empty) box set.
        assert status_response(rec)["status"] == "live"


def test_corrupt_envelope_round_trips_verbatim(store, store_path):
    # The corrupt envelope persists verbatim as the whole boxes value
    # and re-derives the signal on the next load.
    tenant = {"stage": 2, "approvals_url": "https://approve.example/a/x",
              "boxes": None}
    _write_raw(store_path, {"version": 1, "tenants": {"tnt_1784": tenant}})
    rec = store.get("tnt_1784")
    store.save(rec)
    persisted = json.load(open(store_path))["tenants"]["tnt_1784"]
    assert persisted["boxes"] is None
    rec2 = store.get("tnt_1784")
    assert any(k.startswith("#boxes") for k in rec2.quarantined)


def test_reserved_signal_key_squatted_by_real_box(store, store_path):
    # Security round-1 B1: a real box enrolled as "#last_reported" is
    # never dropped or destroyed — it flows through the normal box
    # path, and the hold signal takes a suffixed key.
    boxes = {
        "#last_reported": _healthy_box_dict(),
        "ok": _healthy_box_dict(),
    }
    _write_raw(store_path, _raw_with_boxes(
        boxes=boxes, last_reported={"code": "bogus"}))
    rec = store.get("tnt_1784")
    # The squatting box is a healthy arc, untouched.
    assert set(rec.boxes) == {"#last_reported", "ok"}
    hold_keys = [k for k in rec.quarantined if k.startswith("#last_reported")]
    assert hold_keys == ["#last_reported/2"]
    # The squatting box survives a save (no silent destruction).
    store.save(rec)
    persisted = json.load(open(store_path))["tenants"]["tnt_1784"]
    assert "#last_reported" in persisted["boxes"]
    assert persisted["boxes"]["#last_reported"]["code"] == "live"


def test_suffix_squat_box_id_not_treated_as_envelope_signal(store, store_path):
    # Security P92 re-confirm: box ids are free-form, so a hostile id can
    # squat a reserved key's SUFFIX ("#boxes/2") — the very key shape
    # _reserve_quarantine_key itself mints. Prefix inference would then
    # misclassify the squatter as the envelope signal and replace the
    # whole boxes container with its raw. Marker classification must not.
    boxes = {
        "ok": _healthy_box_dict(),
        "#boxes/2": _healthy_box_dict(code=42),
    }
    _write_raw(store_path, _raw_with_boxes(boxes=boxes))
    rec = store.get("tnt_1784")
    assert set(rec.boxes) == {"ok"}
    assert set(rec.quarantined) == {"#boxes/2"}
    store.save(rec)
    persisted = json.load(open(store_path))["tenants"]["tnt_1784"]
    # The container survives intact: the squatter's raw is one entry, not
    # the container itself.
    assert set(persisted["boxes"]) == {"ok", "#boxes/2"}
    assert persisted["boxes"]["ok"]["code"] == "live"
    assert persisted["boxes"]["#boxes/2"]["code"] == 42
    # The quarantine re-derives on the next load — evidence is not lost.
    rec2 = store.get("tnt_1784")
    assert set(rec2.quarantined) == {"#boxes/2"}


def test_suffix_squat_box_id_not_treated_as_hold_signal(store, store_path):
    # Same discipline for the hold signal: a bad box squatting
    # "#last_reported/2" must not have its raw persisted as last_reported.
    boxes = {
        "ok": _healthy_box_dict(),
        "#last_reported/2": _healthy_box_dict(code=42),
    }
    raw = _raw_with_boxes(
        boxes=boxes,
        last_reported={
            "code": "live",
            "status_updated_at": "2026-10-19T00:00:00Z",
            "detail": None,
        },
    )
    _write_raw(store_path, raw)
    rec = store.get("tnt_1784")
    assert set(rec.quarantined) == {"#last_reported/2"}
    store.save(rec)
    persisted = json.load(open(store_path))["tenants"]["tnt_1784"]
    assert set(persisted["boxes"]) == {"ok", "#last_reported/2"}
    assert persisted["boxes"]["#last_reported/2"]["code"] == 42
    # last_reported is the store's own snapshot, never the squatter's raw.
    assert persisted["last_reported"]["code"] == "live"
    assert persisted["last_reported"]["status_updated_at"] == (
        "2026-10-19T00:00:00Z"
    )


def test_hold_recompute_keeps_suffix_squat_box_evidence(store, store_path):
    # The _save_record stale-hold cleanup deletes only hold signals —
    # a bad box squatting "#last_reported/2" is box evidence, not a
    # signal, and survives the recompute.
    boxes = {
        "ok": _healthy_box_dict(),
        "#last_reported/2": _healthy_box_dict(code=42),
    }
    _write_raw(store_path, _raw_with_boxes(
        boxes=boxes, last_reported={"code": "bogus"}))
    rec = store.get("tnt_1784")
    assert set(rec.quarantined) == {"#last_reported/2", "#last_reported"}
    store.save(rec)
    persisted = json.load(open(store_path))["tenants"]["tnt_1784"]
    # The corrupt hold's signal is healed away; the squatter's evidence
    # is not.
    assert set(persisted["boxes"]) == {"ok", "#last_reported/2"}
    assert persisted["last_reported"]["code"] == "live"


def test_quarantine_kind_marker_classification(store, store_path):
    # The classifiers are marker-based, never prefix-based: a signal
    # entry is found by its kind marker even at a suffixed key, and an
    # unmarked (or garbage-marked) entry is never a signal — the
    # fail-closed default.
    assert _quarantine_entry_kind({}) == _QUARANTINE_KIND_BOX
    assert _quarantine_entry_kind(
        {"_quarantine_kind": "evil"}) == _QUARANTINE_KIND_BOX
    entry = _hold_quarantine_entry({"code": "bogus"}, "nope")
    assert _quarantine_entry_kind(entry) == _QUARANTINE_KIND_HOLD
    m = {"#last_reported/2": entry, "#boxes": {
        "_quarantine_kind": _QUARANTINE_KIND_BOX, "raw": {}}}
    assert _find_quarantine_signal(
        m, _QUARANTINE_KIND_HOLD) == "#last_reported/2"
    assert _find_quarantine_signal(
        m, _QUARANTINE_KIND_ENVELOPE) is None


def test_quarantine_surface_scrubs_latched(store, store_path):
    # Security round-1 B2: a hostile latched value on a non-#1509 entry
    # must not reach the served surface raw.
    hostile = "live\x1b[2K\r\nINJECTED"
    _write_raw(store_path, _raw_with_boxes(boxes={
        "ok": _healthy_box_dict(),
        "bad": _healthy_box_dict(latched=hostile, code=42),
    }))
    rec = store.get("tnt_1784")
    (entry,) = [e for e in _quarantine_surface(rec.quarantined)
                if e["box_id"] == "bad"]
    assert "\x1b" not in entry["latched"] and "\r" not in entry["latched"]
    assert "\n" not in entry["latched"]
    assert len(entry["latched"].encode("utf-8")) <= 64
