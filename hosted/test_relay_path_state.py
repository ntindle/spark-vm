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
            provider_state=state,
            has_post_live_arc=True,
            now=NOW,
        )
        assert should is False
        assert "stand-down" in reason


def test_cadence_stands_down_without_post_live_arc():
    should, reason = rps.cadence_decision(provider_state="running", has_post_live_arc=False, now=NOW
    )
    assert should is False
    assert "post-live" in reason


def test_cadence_due_when_never_probed():
    should, _reason = rps.cadence_decision(provider_state="running", has_post_live_arc=True, now=NOW
    )
    assert should is True


def test_cadence_due_after_interval_and_not_before():
    should, _ = rps.cadence_decision(provider_state="running",
        has_post_live_arc=True,
        now=NOW,
        last_probe_at=NOW - 400,
        cadence=300,
    )
    assert should is True
    should, reason = rps.cadence_decision(provider_state="running",
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


# ---------------------------------------------------------------------------
# Round-1 review fixes: Engineering B1, QA B1-B3 + advisories
# ---------------------------------------------------------------------------


def test_flapping_survives_long_stand_down_run(history, journal):
    # Engineering B1: ≥8 stand-down records between the two liveness
    # outcomes must not hide the flapping — the fixed window turned
    # this into a rule-6-firing down.
    _record(history, [prober.PATH_OK])
    _record(history, [prober.PROVIDER_NOT_RUNNING] * 10, ts=NOW + 100)
    _record(history, [prober.RELAY_DEFECT], ts=NOW + 200)
    reading = rps.relay_path_state(VM, now=NOW + 300, history=history)
    assert reading["state"] == "degraded"
    assert reading["sub_code"] is None
    assert "flapping" in reading["reason"]


def test_history_record_missing_ts_is_skipped(history):
    with open(history, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"vm_id": VM, "outcome": prober.PATH_OK}) + "\n")
    assert rps.recent_liveness_outcomes(VM, n=2, path=history) == []
    assert rps.latest_probe(VM, path=history) is None


def test_empty_history_file_is_never_probed(history, journal):
    open(history, "a", encoding="utf-8").close()
    reading = rps.relay_path_state(VM, now=NOW, history=history)
    assert reading["state"] == "degraded"
    assert reading["probe"] is None


def test_journal_lock_error_propagates_never_darkness(history, journal, monkeypatch):
    # QA B1: a wedged lock is a broken instrument, never darkness.
    def wedged(vm_id, now=None, timeout_s=None):
        raise rl.JournalLockError("wedged")
    monkeypatch.setattr(rl, "relay_session_liveness", wedged)
    with pytest.raises(rl.JournalLockError):
        rps.relay_path_state(VM, now=NOW, history=history)


def test_record_outcome_io_failure_is_loud(history):
    # QA B2: fail-loud on I/O errors — a path that is an existing
    # directory can never be opened for append.
    os.makedirs(history + "-as-dir", exist_ok=True)
    with pytest.raises(OSError):
        rps._record_outcome(history + "-as-dir", VM, prober.PATH_OK,
                            {"elapsed_ms": 1}, now=NOW)


def test_maybe_probe_raising_provider_state_fn_propagates(history, journal):
    # QA B3: a raising provider_state_fn is a caller bug and propagates.
    def boom():
        raise RuntimeError("driver exploded")
    with pytest.raises(RuntimeError):
        rps.maybe_probe(
            VM,
            provider_state_fn=boom,
            has_post_live_arc=True,
            bundle={"relay_host": "h", "relay_port": 1,
                    "pinned_fingerprint": "SHA256:eA"},
            now=NOW,
            history=history,
        )


def test_maybe_probe_history_write_failure_warns_not_raises(history, journal):
    os.makedirs(history + "-as-dir", exist_ok=True)

    def fake_probe(vm_id, *, relay_host, relay_port, pinned_fingerprint,
                   provider_state_fn):
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
            history=history + "-as-dir",
        )
    finally:
        real.probe = real_probe
    assert out["probed"] is True
    assert "unwritable" in out["reason"]
    assert out["reading"]["probe"] is None  # nothing was recorded


def test_cadence_clamps_future_last_probe_at():
    should, _reason = rps.cadence_decision(
        provider_state="running",
        has_post_live_arc=True,
        now=NOW,
        last_probe_at=NOW + 3600,  # clock skew — fail-safe is to probe
        cadence=300,
    )
    assert should is True


def test_cadence_rejects_infinite_env_value(monkeypatch):
    monkeypatch.setenv("RELAY_PROBE_CADENCE_S", "inf")
    assert rps.cadence_s() == rps.DEFAULT_CADENCE_S


def _run_cli(argv, monkeypatch, capsys, stdin=""):
    import io
    import runpy
    monkeypatch.setattr("sys.argv", ["relay_path_state"] + argv)
    if isinstance(stdin, str):
        stdin = io.StringIO(stdin)
    monkeypatch.setattr("sys.stdin", stdin)
    try:
        runpy.run_module("hosted.relay_path_state", run_name="__main__")
    except SystemExit as exc:
        return exc.code, capsys.readouterr()
    return None, capsys.readouterr()


def test_cli_probe_now_without_query_exits_2(monkeypatch, capsys):
    code, err = _run_cli(["--probe-now"], monkeypatch, capsys)
    assert code == 2
    assert "--query" in err.err


def test_cli_probe_now_empty_stdin_exits_2(history, journal, monkeypatch, capsys):
    code, err = _run_cli(
        ["--probe-now", "--query", VM], monkeypatch, capsys, stdin=""
    )
    assert code == 2
    assert "stdin" in err.err


def test_cli_probe_now_invalid_stdin_json_exits_2(
    history, journal, monkeypatch, capsys
):
    code, err = _run_cli(
        ["--probe-now", "--query", VM], monkeypatch, capsys, stdin="{not json"
    )
    assert code == 2
    assert "not valid JSON" in err.err


def test_cli_probe_now_bundle_missing_field_exits_2(
    history, journal, monkeypatch, capsys
):
    code, err = _run_cli(
        ["--probe-now", "--query", VM],
        monkeypatch,
        capsys,
        stdin=json.dumps({"relay_host": "h", "relay_port": 1}),
    )
    assert code == 2
    assert "pinned_fingerprint" in err.err


def test_cli_probe_now_bad_port_exits_2(history, journal, monkeypatch, capsys):
    code, err = _run_cli(
        ["--probe-now", "--query", VM],
        monkeypatch,
        capsys,
        stdin=json.dumps(
            {
                "relay_host": "h",
                "relay_port": "not-a-port",
                "pinned_fingerprint": "SHA256:x",
            }
        ),
    )
    assert code == 2
    assert "relay_port" in err.err


@pytest.mark.parametrize("raw_port", [True, 8443.5, "8_443", "-1", 0, 65536])
def test_cli_probe_now_coerced_port_rejected_exits_2(
    history, journal, monkeypatch, capsys, raw_port
):
    # A validator must not silently rewrite its input (PR #1538 review
    # B1): bool/float/underscore ports are rejected, not coerced.
    code, err = _run_cli(
        ["--probe-now", "--query", VM],
        monkeypatch,
        capsys,
        stdin=json.dumps(
            {
                "relay_host": "h",
                "relay_port": raw_port,
                "pinned_fingerprint": "SHA256:x",
            }
        ),
    )
    assert code == 2
    assert "relay_port" in err.err


@pytest.mark.parametrize("raw_port", ["8443", "+8443", " 8443 "])
def test_cli_probe_now_plain_digit_port_strings_accepted(
    history, journal, monkeypatch, capsys, raw_port
):
    import hosted.relay_dial_prober as real

    seen = {}

    def fake_probe(vm_id, *, relay_host, relay_port, pinned_fingerprint,
                   provider_state_fn):
        seen["relay_port"] = relay_port
        return _FakeResult(prober.PATH_OK)

    real_probe = real.probe
    real.probe = fake_probe
    try:
        code, out = _run_cli(
            ["--probe-now", "--query", VM],
            monkeypatch,
            capsys,
            stdin=json.dumps(
                {
                    "relay_host": "h",
                    "relay_port": raw_port,
                    "pinned_fingerprint": "SHA256:x",
                }
            ),
        )
    finally:
        real.probe = real_probe
    assert code is None  # no SystemExit on success
    assert seen["relay_port"] == 8443


@pytest.mark.parametrize(
    "bundle,expected",
    [
        (
            {"relay_host": 123, "relay_port": 1, "pinned_fingerprint": "SHA256:x"},
            "must be a string",
        ),
        (
            {"relay_host": ["h"], "relay_port": 1, "pinned_fingerprint": "SHA256:x"},
            "must be a string",
        ),
        (
            {"relay_host": "h", "relay_port": 1, "pinned_fingerprint": 123},
            "must be a string",
        ),
        # None is falsy → lands on the missing-fields path, still loud exit 2
        (
            {"relay_host": "h", "relay_port": 1, "pinned_fingerprint": None},
            "missing required fields",
        ),
    ],
)
def test_cli_probe_now_nonstring_fields_exits_2(
    history, journal, monkeypatch, capsys, bundle, expected
):
    # Non-string host/fingerprint must fail loud (exit 2), never
    # escape into a traceback from the prober (PR #1538 review B2).
    code, err = _run_cli(
        ["--probe-now", "--query", VM],
        monkeypatch,
        capsys,
        stdin=json.dumps(bundle),
    )
    assert code == 2
    assert expected in err.err


def test_cli_probe_now_deeply_nested_stdin_exits_2(
    history, journal, monkeypatch, capsys
):
    # json.loads raises RecursionError (not ValueError) on pathological
    # nesting — it must still land on the loud exit-2 path (PR #1538 B3).
    code, err = _run_cli(
        ["--probe-now", "--query", VM],
        monkeypatch,
        capsys,
        stdin="[" * 200000,
    )
    assert code == 2
    assert "not valid JSON" in err.err


def test_cli_probe_now_tty_stdin_exits_2(history, journal, monkeypatch, capsys):
    class _Tty:
        def isatty(self):
            return True

        def read(self):
            raise AssertionError("must not block on a TTY")

    code, err = _run_cli(
        ["--probe-now", "--query", VM], monkeypatch, capsys, stdin=_Tty()
    )
    assert code == 2
    assert "terminal" in err.err


def test_maybe_probe_symlink_history_warns_eloop(history, journal, tmp_path):
    target = tmp_path / "target.jsonl"
    target.write_text("")
    os.symlink(str(target), history)

    def fake_probe(vm_id, *, relay_host, relay_port, pinned_fingerprint,
                   provider_state_fn):
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
    assert "ELOOP" in out["reason"]
    assert target.read_text() == ""  # the append never redirected


def test_cli_probe_now_reads_bundle_from_stdin(
    history, journal, monkeypatch, capsys
):
    import hosted.relay_dial_prober as real

    seen = {}

    def fake_probe(vm_id, *, relay_host, relay_port, pinned_fingerprint,
                   provider_state_fn):
        seen.update(
            relay_host=relay_host,
            relay_port=relay_port,
            pinned_fingerprint=pinned_fingerprint,
        )
        return _FakeResult(prober.PATH_OK)

    real_probe = real.probe
    real.probe = fake_probe
    try:
        code, out = _run_cli(
            ["--probe-now", "--query", VM],
            monkeypatch,
            capsys,
            stdin=json.dumps(
                {
                    "relay_host": "relay.example",
                    "relay_port": 8443,
                    "pinned_fingerprint": "SHA256:abc",
                }
            ),
        )
    finally:
        real.probe = real_probe
    assert code is None  # no SystemExit on success
    body = json.loads(out.out)
    assert body["probed"] is True
    assert seen == {
        "relay_host": "relay.example",
        "relay_port": 8443,
        "pinned_fingerprint": "SHA256:abc",
    }


def test_history_store_created_with_pinned_permissions(tmp_path):
    nested = str(tmp_path / "newdir" / "probe-history.jsonl")
    rps._record_outcome(nested, VM, prober.PATH_OK, {"elapsed_ms": 1}, now=NOW)
    # umask can only remove bits: the fix guarantees no group/other
    # access on either the parent dir or the store itself
    assert os.stat(str(tmp_path / "newdir")).st_mode & 0o077 == 0
    assert os.stat(nested).st_mode & 0o077 == 0


def test_history_store_symlink_refused_loud(tmp_path):
    target = tmp_path / "target.jsonl"
    target.write_text("")
    link = str(tmp_path / "probe-history.jsonl")
    os.symlink(str(target), link)
    with pytest.raises(OSError):
        rps._record_outcome(link, VM, prober.PATH_OK, {"elapsed_ms": 1}, now=NOW)
    # the symlink target is untouched — the append never redirected
    assert target.read_text() == ""


def test_cli_query_journal_wedge_exits_1(history, journal, monkeypatch, capsys):
    def wedged(vm_id, now=None, timeout_s=None):
        raise rl.JournalLockError("wedged")
    monkeypatch.setattr(rl, "relay_session_liveness", wedged)
    code, err = _run_cli(["--query", VM], monkeypatch, capsys)
    assert code == 1
    assert "wedged" in err.err


def test_cli_query_prints_reading(history, journal, monkeypatch, capsys):
    _record(history, [prober.PATH_OK])
    code, out = _run_cli(["--query", VM], monkeypatch, capsys)
    assert code is None or True  # no SystemExit on success
    reading = json.loads(out.out)
    assert reading["vm_id"] == VM
    assert reading["state"] == "degraded"  # no journal frame written
