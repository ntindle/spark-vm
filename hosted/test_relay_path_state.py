#!/usr/bin/env python3
"""Tests for the relay_path_state producer contract (R2b, #1415).

Run: ``python3 -m pytest hosted/`` from the repo root.
"""

import json
import os
import time

import pytest

from hosted import relay_dial_prober as prober
from hosted import relay_liveness as rl
from hosted import relay_path_state as rps

NOW = 1_758_000_000.0
VM = "vm-r2b-1"


@pytest.fixture()
def history(tmp_path, monkeypatch):
    path = str(tmp_path / "probe-history.jsonl")
    monkeypatch.setenv("RELAY_PROBE_HISTORY", path)
    return path


@pytest.fixture()
def journal(tmp_path, monkeypatch):
    path = str(tmp_path / "journal.jsonl")
    monkeypatch.setenv("RELAY_SESSION_JOURNAL", path)
    return path


def _frame(**over):
    f = {
        "session_id": "sess-1",
        "vm_id": VM,
        "opened_at": NOW - 600,
        "last_bytes_at": NOW - 10,
        "closed_at": None,
        "close_cause": None,
        "hostkey_verified": True,
        "bytes_in": 42,
        "bytes_out": 7,
    }
    f.update(over)
    return f


def _record(history, outcomes, ts=NOW):
    for i, outcome in enumerate(outcomes):
        rps._record_outcome(
            history, VM, outcome, {"elapsed_ms": 12}, now=ts + i
        )


# ---------------------------------------------------------------------------
# map_reading — the §5 mapping matrix
# ---------------------------------------------------------------------------


def test_map_path_ok_plus_active_journal_is_ok():
    state, sub, reason = rps.map_reading(
        probe_outcome=prober.PATH_OK, journal_state="active"
    )
    assert (state, sub) == ("ok", None)
    assert "corroboration" in reason


def test_map_path_ok_without_fresh_journal_is_degraded():
    for journal_state in ("idle", "closed", None):
        state, sub, reason = rps.map_reading(
            probe_outcome=prober.PATH_OK, journal_state=journal_state
        )
        assert state == "degraded", journal_state
        assert sub is None
        assert "corroboration" in reason


def test_map_defects_are_down_with_sub_code():
    cases = [
        (prober.RELAY_DEFECT, "relay"),
        (prober.CERT_DEFECT, "cert"),
        (prober.BOX_LEG_DEFECT, "box-leg"),
    ]
    for outcome, sub_code in cases:
        # A defect is positive evidence — the journal never softens it.
        for journal_state in ("active", "idle", "closed", None):
            state, sub, _reason = rps.map_reading(
                probe_outcome=outcome, journal_state=journal_state
            )
            assert (state, sub) == ("down", sub_code), (outcome, journal_state)


def test_map_provider_not_running_is_degraded_no_subcode():
    state, sub, reason = rps.map_reading(
        probe_outcome=prober.PROVIDER_NOT_RUNNING, journal_state="active"
    )
    assert state == "degraded"
    assert sub is None
    assert "not a liveness question" in reason


def test_map_never_probed_is_degraded_never_ok():
    state, sub, _reason = rps.map_reading(
        probe_outcome=None, journal_state="active"
    )
    assert state == "degraded"
    assert sub is None


def test_map_unknown_outcome_fails_closed_to_degraded():
    state, sub, _reason = rps.map_reading(
        probe_outcome="mystery-outcome", journal_state="active"
    )
    assert state == "degraded"
    assert sub is None


# ---------------------------------------------------------------------------
# relay_path_state — history + journal composition, flapping
# ---------------------------------------------------------------------------


def test_state_ok_needs_probe_and_active_journal(history, journal):
    rl.emit_frame(**_frame())
    _record(history, [prober.PATH_OK])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "ok"
    assert reading["sub_code"] is None
    assert reading["probe"] == prober.PATH_OK
    assert reading["journal"] == "active"


def test_state_degraded_when_journal_stale(history, journal):
    rl.emit_frame(**_frame(last_bytes_at=NOW - 400))  # idle: > 300 s
    _record(history, [prober.PATH_OK])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "degraded"
    assert reading["journal"] == "idle"


def test_state_degraded_when_journal_dark(history, journal):
    _record(history, [prober.PATH_OK])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "degraded"
    assert reading["journal"] is None
    assert "dark" in reading["reason"]


def test_state_down_on_lone_defect(history, journal):
    _record(history, [prober.CERT_DEFECT])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "down"
    assert reading["sub_code"] == "cert"


def test_flapping_ok_then_defect_is_degraded_not_down(history, journal):
    _record(history, [prober.PATH_OK, prober.RELAY_DEFECT])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "degraded"
    assert reading["sub_code"] is None
    assert "Flapping" in reading["reason"] or "flapping" in reading["reason"]


def test_flapping_defect_then_ok_is_degraded(history, journal):
    _record(history, [prober.BOX_LEG_DEFECT, prober.PATH_OK])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "degraded"


def test_agreeing_defects_stay_down(history, journal):
    _record(history, [prober.RELAY_DEFECT, prober.RELAY_DEFECT])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "down"
    assert reading["sub_code"] == "relay"


def test_disagreeing_defects_are_flapping_not_down(history, journal):
    # Both readings say "broken" but disagree on who to blame — the
    # blame is part of the reading, so this is flapping (suspect),
    # never a rule-6-firing down.
    _record(history, [prober.RELAY_DEFECT, prober.BOX_LEG_DEFECT])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "degraded"
    assert reading["sub_code"] is None
    assert "flapping" in reading["reason"]


def test_stand_down_report_never_counts_as_flapping(history, journal):
    _record(history, [prober.PATH_OK, prober.PROVIDER_NOT_RUNNING])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "degraded"
    assert "stand-down" in reading["reason"]


def test_never_probed_is_degraded(history, journal):
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "degraded"
    assert reading["probe"] is None


def test_reading_shape_is_json_serializable(history, journal):
    rl.emit_frame(**_frame())
    _record(history, [prober.PATH_OK])
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert set(reading) == {
        "vm_id",
        "state",
        "sub_code",
        "reason",
        "probe",
        "journal",
    }
    assert reading["state"] in rps.STATES
    json.dumps(reading)


# ---------------------------------------------------------------------------
# History store: corruption resilience, fingerprint exclusion
# ---------------------------------------------------------------------------


def test_history_skips_corrupt_and_unknown_lines(history):
    _record(history, [prober.PATH_OK])
    with open(history, "a", encoding="utf-8") as fh:
        fh.write("not json at all\n")
        fh.write(json.dumps({"vm_id": VM, "outcome": "nope"}) + "\n")
        fh.write(json.dumps(["not", "a", "dict"]) + "\n")
        fh.write(
            json.dumps({"vm_id": "other-vm", "outcome": prober.RELAY_DEFECT})
            + "\n"
        )
    assert rps.recent_liveness_outcomes(VM, n=2, path=history) == [prober.PATH_OK]
    assert rps.latest_probe(VM, path=history)["outcome"] == prober.PATH_OK


def test_history_records_outcomes_only_never_fingerprints(history):
    rps._record_outcome(
        history,
        VM,
        prober.PATH_OK,
        {"elapsed_ms": 5, "observed_fingerprint": "SHA256:abc"},
        now=NOW,
    )
    with open(history, encoding="utf-8") as fh:
        raw = fh.read()
    assert "fingerprint" not in raw  # D-RL2-3
    assert rps.latest_probe(VM, path=history)["outcome"] == prober.PATH_OK


def test_history_newest_first(history):
    _record(history, [prober.PATH_OK, prober.CERT_DEFECT])
    assert rps.recent_liveness_outcomes(VM, n=2, path=history) == [
        prober.CERT_DEFECT,
        prober.PATH_OK,
    ]


def test_stand_down_excluded_from_liveness_outcomes(history):
    _record(history, [prober.PATH_OK, prober.PROVIDER_NOT_RUNNING])
    assert rps.recent_liveness_outcomes(VM, n=2, path=history) == [prober.PATH_OK]
    # ...but latest_probe still reports the stand-down itself.
    assert (
        rps.latest_probe(VM, path=history)["outcome"]
        == prober.PROVIDER_NOT_RUNNING
    )


# ---------------------------------------------------------------------------
# cadence_decision
# ---------------------------------------------------------------------------


def test_cadence_stands_down_on_suspended_and_destroyed():
    for state in ("suspended", "destroyed"):
        should, reason = rps.cadence_decision(
            VM,
            provider_state=state,
            has_post_live_arc=True,
            now=NOW,
        )
        assert should is False
        assert "stand-down" in reason


def test_cadence_stands_down_without_post_live_arc():
    should, reason = rps.cadence_decision(
        VM, provider_state="running", has_post_live_arc=False, now=NOW
    )
    assert should is False
    assert "post-live" in reason


def test_cadence_due_when_never_probed():
    should, _reason = rps.cadence_decision(
        VM, provider_state="running", has_post_live_arc=True, now=NOW
    )
    assert should is True


def test_cadence_due_after_interval_and_not_before():
    should, _ = rps.cadence_decision(
        VM,
        provider_state="running",
        has_post_live_arc=True,
        now=NOW,
        last_probe_at=NOW - 400,
        cadence=300,
    )
    assert should is True
    should, reason = rps.cadence_decision(
        VM,
        provider_state="running",
        has_post_live_arc=True,
        now=NOW,
        last_probe_at=NOW - 10,
        cadence=300,
    )
    assert should is False
    assert "next probe in" in reason


def test_cadence_env_override_and_fail_closed_default(monkeypatch):
    monkeypatch.setenv("RELAY_PROBE_CADENCE_S", "60")
    assert rps.cadence_s() == 60.0
    monkeypatch.setenv("RELAY_PROBE_CADENCE_S", "garbage")
    assert rps.cadence_s() == rps.DEFAULT_CADENCE_S
    monkeypatch.setenv("RELAY_PROBE_CADENCE_S", "-5")
    assert rps.cadence_s() == rps.DEFAULT_CADENCE_S
    monkeypatch.delenv("RELAY_PROBE_CADENCE_S")
    assert rps.cadence_s() == 300.0


# ---------------------------------------------------------------------------
# maybe_probe — driver wiring
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, outcome):
        self.outcome = outcome
        self.detail = {"elapsed_ms": 9}


def test_maybe_probe_stands_down_without_probing(history, journal):
    calls = []

    def fake_probe(*a, **k):
        calls.append((a, k))
        return _FakeResult(prober.PATH_OK)

    import hosted.relay_dial_prober as real

    real_probe = real.probe
    real.probe = fake_probe
    try:
        out = rps.maybe_probe(
            VM,
            provider_state_fn=lambda: "suspended",
            has_post_live_arc=True,
            bundle={"relay_host": "h", "relay_port": 1,
                    "pinned_fingerprint": "SHA256:eA"},
            now=NOW,
            history=history,
        )
    finally:
        real.probe = real_probe
    assert out["probed"] is False
    assert calls == []
    assert out["reading"]["state"] == "degraded"


def test_maybe_probe_needs_a_bundle(history, journal):
    out = rps.maybe_probe(
        VM,
        provider_state_fn=lambda: "running",
        has_post_live_arc=True,
        bundle=None,
        now=NOW,
        history=history,
    )
    assert out["probed"] is False
    assert "never fetches bundles" in out["reason"]


def test_maybe_probe_records_outcome_and_reads_back(history, journal):
    rl.emit_frame(**_frame())

    def fake_probe(vm_id, *, relay_host, relay_port, pinned_fingerprint,
                   provider_state_fn):
        assert provider_state_fn() == "running"
        return _FakeResult(prober.PATH_OK)

    import hosted.relay_dial_prober as real

    real_probe = real.probe
    real.probe = fake_probe
    try:
        out = rps.maybe_probe(
            VM,
            provider_state_fn=lambda: "running",
            has_post_live_arc=True,
            bundle={"relay_host": "h", "relay_port": 1,
                    "pinned_fingerprint": "SHA256:eA"},
            now=NOW,
            history=history,
        )
    finally:
        real.probe = real_probe
    assert out["probed"] is True
    assert out["reading"]["state"] == "ok"
    assert out["reading"]["probe"] == prober.PATH_OK


def test_maybe_probe_not_due_skips_network(history, journal):
    _record(history, [prober.PATH_OK], ts=NOW - 10)

    def fake_probe(*a, **k):
        raise AssertionError("must not probe before the cadence elapses")

    import hosted.relay_dial_prober as real

    real_probe = real.probe
    real.probe = fake_probe
    try:
        out = rps.maybe_probe(
            VM,
            provider_state_fn=lambda: "running",
            has_post_live_arc=True,
            bundle={"relay_host": "h", "relay_port": 1,
                    "pinned_fingerprint": "SHA256:eA"},
            now=NOW,
            history=history,
            cadence=300,
        )
    finally:
        real.probe = real_probe
    assert out["probed"] is False
    assert "next probe in" in out["reason"]
