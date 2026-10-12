"""Hermetic tests for fleet/plane_waves.py (issue #1285, S2 wave machine).

Subprocess tests exercise the CLI exactly as the operator runs it
(assign/promote/halt/status/canary-tenants), against a scratch --store
per test — no live planes, per the issue's hermetic acceptance. A few
in-process tests cover the pin-shape validator and the idempotent pin
writer directly.

Each test gets its own --store temp dir. Non-vacuity: key behaviors are
mutation-verified (see inline comments naming the neuter that must flip
the test).
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_CLI = os.path.join(_HERE, "plane_waves.py")
_INV_CLI = os.path.join(_HERE, "plane_inventory.py")
_DEPLOY_CLI = os.path.join(_HERE, "plane_deploy.py")
_STORE_TIMEOUT_S = 60

_SHA_A = "aa" * 32
_SHA_B = "bb" * 32

sys.path.insert(0, _HERE)
import plane_deploy  # noqa: E402  (proves S2's waves.json satisfies S4's reader)
import plane_inventory  # noqa: E402  (reads the S1 store in assertions)
import plane_waves  # noqa: E402  (pin-shape unit tests)
import events  # noqa: E402  (lock-behavior tests hold the store lock directly)


def _run(cli, store, *argv):
    cmd = [sys.executable, cli, "--store", store, *argv]
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=_STORE_TIMEOUT_S)


def _inv(store, *argv):
    return _run(_INV_CLI, store, *argv)


def _cli(store, *argv):
    return _run(_CLI, store, *argv)


def _deploy_cli(store, *argv):
    return _run(_DEPLOY_CLI, store, *argv)


@pytest.fixture()
def store():
    with tempfile.TemporaryDirectory(prefix="plane-waves-") as d:
        yield d


def _json(proc):
    return json.loads(proc.stdout)


def _register(store, plane_id, tenant_id="t1", template=None):
    argv = ["register", "--plane-id", plane_id, "--tenant-id", tenant_id]
    if template:
        argv += ["--template", template]
    assert _inv(store, *argv).returncode == 0


def _release(store, template="w@v1", channel="stable", deployment_id="dep-1",
             sha=_SHA_A):
    assert _inv(store, "release", "--template", template, "--channel", channel,
                "--deployment-id", deployment_id,
                "--worker-sha256", sha).returncode == 0


def _deploy(store, plane_id, template, status="healthy"):
    assert _inv(store, "deploy", "--plane-id", plane_id, "--template", template,
                "--status", status).returncode == 0


def _waves_json(store):
    with open(os.path.join(store, "waves.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _expected_wave(plane_id, buckets):
    digest = hashlib.sha256(plane_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % buckets + 1


def _estate(store, n=6, canary_tenants=("ct1",)):
    """n planes across tenants; the named tenants canary-designated."""
    for i in range(n):
        tenant = f"ct{(i % 2) + 1}" if i < 2 else f"t{i}"
        _register(store, f"plane-{i}", tenant_id=tenant)
    for tenant in canary_tenants:
        assert _cli(store, "canary-tenants", "--add", tenant).returncode == 0


def test_assign_stable_waves(store):
    # Neuter: _wave_for_plane returning a constant must flip the
    # determinism assertions below.
    _estate(store, canary_tenants=("ct1", "ct2"))
    _release(store)
    p = _cli(store, "assign", "--template", "w@v1")
    assert p.returncode == 0
    out = _json(p)
    assert out["live_wave"] == 0
    assert out["buckets"] == 4
    assert out["channel"] == "stable"
    assignments = out["assignments"]
    # D-RC-3 tenant rule: wave 0 holds ONLY canary tenants' planes.
    assert {pid for pid, w in assignments.items() if w == 0} == {"plane-0", "plane-1"}
    for pid, wave in assignments.items():
        if wave != 0:
            assert wave == _expected_wave(pid, 4), pid
    # The S4 reader contract: S2's file must satisfy the driver's parser.
    live_wave, rd_assignments = plane_deploy._read_waves(store)
    assert live_wave == 0
    assert rd_assignments == assignments
    # Audit trail written.
    audit = os.path.join(store, "waves_journal.jsonl")
    assert os.path.exists(audit)
    actions = [json.loads(ln)["action"]
               for ln in open(audit, encoding="utf-8") if ln.strip()]
    assert "assign" in actions


def test_assign_security_compressed(store):
    # Neuter: forcing buckets=4 for security releases must flip the
    # wave-1 assertions below (D-RC-7).
    _estate(store)
    _release(store, template="w@sec", channel="security")
    p = _cli(store, "assign", "--template", "w@sec")
    assert p.returncode == 0
    out = _json(p)
    assert out["buckets"] == 1
    assignments = out["assignments"]
    non_canary = {pid for pid, w in assignments.items() if w != 0}
    assert non_canary
    assert all(w == 1 for pid, w in assignments.items() if pid in non_canary)
    # --buckets on a security release is refused, never silently widened.
    p = _cli(store, "assign", "--template", "w@sec", "--buckets", "2")
    assert p.returncode == 2
    assert "compressed" in p.stderr


def test_assign_single_plane_no_canary(store):
    # D-RC-3: a single-plane estate gets no automatic canary even when
    # its tenant is canary-designated — the plane is wave 1.
    _register(store, "plane-1", tenant_id="ct1")
    assert _cli(store, "canary-tenants", "--add", "ct1").returncode == 0
    _release(store)
    p = _cli(store, "assign", "--template", "w@v1")
    assert p.returncode == 0
    out = _json(p)
    assert out["assignments"] == {"plane-1": 1}
    assert out["live_wave"] == 1
    assert 0 not in out["assignments"].values()


def test_assign_skips_empty_canary(store):
    # No canary designations at all: the rollout opens at wave 1, not an
    # empty wave 0 the operator would promote through vacuously.
    for i in range(3):
        _register(store, f"plane-{i}", tenant_id=f"t{i}")
    _release(store)
    p = _cli(store, "assign", "--template", "w@v1")
    assert p.returncode == 0
    out = _json(p)
    assert 0 not in out["assignments"].values()
    assert out["live_wave"] == min(out["assignments"].values())


def test_assign_refuses_unpinned_template(store):
    _register(store, "plane-1", tenant_id="t1")
    p = _cli(store, "assign", "--template", "w@ghost")
    assert p.returncode == 2
    assert "no pinned release" in p.stderr


def test_assign_refuses_second_live_rollout(store):
    _register(store, "plane-1", tenant_id="t1")
    _release(store, template="w@v1")
    _release(store, template="w@v2", deployment_id="dep-2", sha=_SHA_B)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    p = _cli(store, "assign", "--template", "w@v2")
    assert p.returncode == 2
    assert "already live" in p.stderr or "live at wave" in p.stderr


def test_assign_refuses_while_frozen(store):
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _deploy_cli(store, "freeze", "--on").returncode == 0
    p = _cli(store, "assign", "--template", "w@v1")
    assert p.returncode == 2
    assert "frozen" in p.stderr
    assert _deploy_cli(store, "freeze", "--off").returncode == 0
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0


def test_assign_no_eligible_planes(store):
    _release(store)
    p = _cli(store, "assign", "--template", "w@v1")
    assert p.returncode == 2
    assert "no eligible planes" in p.stderr


def test_assign_retire_mid_assign_uses_fresh_inputs(store):
    # #1346: assign read the inventory outside the store lock and wrote
    # waves.json from the stale inputs — a retire landing between the
    # reads and the lock produced assignments naming a retired plane
    # (the downstream gates fail closed, so the blast radius was a
    # wasted assign + operator re-run, but waves.json contradicted the
    # inventory: a broken trust contract for the S4 reader). The inputs
    # are now read and the assignments computed inside the lock.
    # The seam retires plane-3 in the window the bug lived in: after the
    # pinned-release check, before the in-lock computation.
    # Neuters that must flip this test: (a) revert cmd_assign to the
    # pre-lock computation -> the retired plane appears in
    # waves.json; (b) skip the mid-assign retire -> assign succeeds and
    # includes plane-3.
    import contextlib
    from unittest import mock
    for i in range(4):
        _register(store, f"plane-{i}", tenant_id="t1")
    _release(store)
    real_lock = events.journal_lock
    retired = {"done": False}

    @contextlib.contextmanager
    def retiring_lock(store_dir, timeout_s=None):
        if not retired["done"]:
            retired["done"] = True
            assert _inv(store_dir, "retire", "--plane-id",
                        "plane-3").returncode == 0
        with real_lock(store_dir, timeout_s=timeout_s) as guard:
            yield guard

    with mock.patch.object(events, "journal_lock", retiring_lock):
        rc = plane_waves.cmd_assign(
            plane_waves.build_parser().parse_args(
                ["--store", store, "assign", "--template", "w@v1"]))
    assert rc == 0
    assert retired["done"]
    waves = _waves_json(store)
    assert "plane-3" not in waves["assignments"]
    assert set(waves["assignments"]) == {"plane-0", "plane-1", "plane-2"}
    journal_path = os.path.join(store, "waves_journal.jsonl")
    journal = [json.loads(ln) for ln in open(journal_path, encoding="utf-8")
               if ln.strip()]
    assign_recs = [r for r in journal if r["action"] == "assign"]
    assert assign_recs and assign_recs[-1]["planes"] == 3


def test_assign_buckets_bounds(store):
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1",
                "--buckets", "0").returncode == 2
    assert _cli(store, "assign", "--template", "w@v1",
                "--buckets", "9").returncode == 2
    assert _cli(store, "assign", "--template", "w@v1",
                "--buckets", "2").returncode == 0


def test_promote_full_rollout_to_complete(store):
    _estate(store, n=4, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    waves = _waves_json(store)
    canary = [pid for pid, w in waves["assignments"].items() if w == 0]
    rest = [pid for pid, w in waves["assignments"].items() if w != 0]
    assert canary == ["plane-0"]
    assert len(rest) == 3

    # Land the canary (operator-observed via the S1 deploy command).
    _deploy(store, "plane-0", "w@v1", status="healthy")
    p = _cli(store, "promote")
    assert p.returncode == 0, p.stderr
    out = _json(p)
    assert out["from_wave"] == 0
    next_wave = min(w for w in waves["assignments"].values() if w > 0)
    assert out["to_wave"] == next_wave
    assert out["pins_written"] == ["plane-0"]

    # F-RC-6: the promotion wrote the canary plane's rollback pin — from
    # the release record, never invented (advisory #1285/6107294719).
    rec = json.loads(_inv(store, "census").stdout)  # census keeps working
    assert rec["eligible"] == 4
    snap = plane_inventory.read_planes(store)
    pin = snap["plane-0"]["last_known_good"]
    assert pin["template_version"] == "w@v1"
    assert pin["deployment_id"] == "dep-1"
    assert pin["worker_sha256"] == _SHA_A
    assert pin["recorded_at"]  # ISO-8601 validated at write time
    # observed_at preserved: the pin write is not an observation.
    assert snap["plane-0"]["template_version"] == "w@v1"

    # Land the remaining waves, promote to completion.
    for pid in rest:
        _deploy(store, pid, "w@v1", status="healthy")
    for _ in range(1 + max(waves["assignments"].values())):
        waves = _waves_json(store)
        if waves["live_wave"] is None:
            break
        p = _cli(store, "promote")
        assert p.returncode == 0, p.stderr
    waves = _waves_json(store)
    assert waves["live_wave"] is None
    snap = plane_inventory.read_planes(store)
    for pid in rest:
        assert snap[pid]["last_known_good"]["template_version"] == "w@v1"


def test_promote_refuses_unconverged(store):
    # Neuter: _wave_gate forced to (True, ...) must flip this (D-RC-4).
    _estate(store, n=2, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    # plane-0 (canary) is still on the old template: the wave has not landed.
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "has not landed" in p.stderr
    assert _waves_json(store)["live_wave"] == 0


def test_promote_refuses_degraded(store):
    # Neuter: _wave_gate forced to (True, ...) must flip this (bad wave
    # signal is a refusal, not a promotion).
    _estate(store, n=2, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-0", "w@v1", status="degraded")
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "bad-signal" in p.stderr
    assert _waves_json(store)["live_wave"] == 0


def test_promote_refuses_stale_record(store):
    _estate(store, n=2, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-0", "w@v1", status="healthy")
    # A 3.6ms staleness window makes every record stale: the operator's
    # memory of the wave is too old to promote on.
    p = _cli(store, "promote", "--stale-hours", "0.000001")
    assert p.returncode == 2
    assert "stale-record" in p.stderr


def test_promote_fails_closed_retired_midrollout(store):
    _estate(store, n=2, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-0", "w@v1", status="healthy")
    assert _inv(store, "retire", "--plane-id", "plane-0").returncode == 0
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "retired" in p.stderr


def test_promote_refuses_frozen(store):
    _estate(store, n=2, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-0", "w@v1", status="healthy")
    assert _deploy_cli(store, "freeze", "--on").returncode == 0
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "frozen" in p.stderr
    assert _deploy_cli(store, "freeze", "--off").returncode == 0
    assert _cli(store, "promote").returncode == 0


def test_promote_needs_live_rollout(store):
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "no live rollout" in p.stderr


def test_halt_records_reason_and_stops(store):
    _estate(store, n=2, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-0", "w@v1", status="degraded")
    p = _cli(store, "halt", "--reason", "canary degraded on w@v1")
    assert p.returncode == 0, p.stderr
    out = _json(p)
    assert out["halted_at_wave"] == 0
    waves = _waves_json(store)
    assert waves["live_wave"] is None
    assert waves["halted"]["reason"] == "canary degraded on w@v1"
    assert waves["halted"]["wave"] == 0
    # Landed waves stay: the canary plane's record is untouched.
    assert plane_inventory.read_planes(store)["plane-0"]["status"] == "degraded"
    # A halted rollout refuses promotion...
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "halted" in p.stderr
    # ...but a fresh assign supersedes it (the fix ships as a new
    # template version; pins are immutable).
    _release(store, template="w@v2", deployment_id="dep-2", sha=_SHA_B)
    assert _cli(store, "assign", "--template", "w@v2").returncode == 0
    waves = _waves_json(store)
    assert waves["template_version"] == "w@v2"
    assert waves["halted"] is None


def test_halt_requires_live_rollout(store):
    p = _cli(store, "halt", "--reason", "nothing live")
    assert p.returncode == 2
    assert "no live rollout" in p.stderr


def test_halt_requires_reason(store):
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    p = _cli(store, "halt", "--reason", "   ")
    assert p.returncode == 2
    assert "reason" in p.stderr


def test_status_reports_rollout(store):
    _estate(store, n=3, canary_tenants=("ct1",))
    _release(store)
    p = _cli(store, "status")
    assert p.returncode == 0
    out = _json(p)
    assert out["rollout"] is None
    assert out["frozen"] is False
    assert out["canary_tenants"] == ["ct1"]
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    out = _json(_cli(store, "status"))
    rollout = out["rollout"]
    assert rollout["template_version"] == "w@v1"
    assert rollout["live_wave"] == 0
    assert rollout["halted"] is None
    assert rollout["waves"]["0"]["live"] is True
    assert rollout["waves"]["0"]["landed"] is False
    _deploy(store, "plane-0", "w@v1", status="healthy")
    out = _json(_cli(store, "status"))
    assert out["rollout"]["waves"]["0"]["landed"] is True
    assert _deploy_cli(store, "freeze", "--on").returncode == 0
    assert _json(_cli(store, "status"))["frozen"] is True


def test_canary_tenants_roundtrip(store):
    assert _json(_cli(store, "canary-tenants", "--list")) == {"canary_tenants": []}
    assert _cli(store, "canary-tenants", "--add", "ct1").returncode == 0
    assert _cli(store, "canary-tenants", "--add", "ct2").returncode == 0
    out = _json(_cli(store, "canary-tenants", "--list"))
    assert out == {"canary_tenants": ["ct1", "ct2"]}
    assert _cli(store, "canary-tenants", "--remove", "ct1").returncode == 0
    out = _json(_cli(store, "canary-tenants", "--list"))
    assert out == {"canary_tenants": ["ct2"]}
    # Bad tenant ids fail closed at the boundary.
    assert _cli(store, "canary-tenants", "--add", "no spaces").returncode == 2
    assert _cli(store, "canary-tenants", "--add", "ct1",
                "--remove", "ct2").returncode == 2


def test_s4_out_of_wave_refusal_against_s2_waves(store):
    # The writer contract in the other direction: S2's waves.json must
    # drive the S4 driver's out-of-wave refusal for the live wave.
    _estate(store, n=4, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    waves = _waves_json(store)
    other = next(pid for pid, w in waves["assignments"].items() if w != 0)
    p = _deploy_cli(store, "deploy", "--plane-id", other, "--template", "w@v1",
                    "--dry-run")
    assert p.returncode == 2
    assert "not in the live wave" in p.stderr
    canary = next(pid for pid, w in waves["assignments"].items() if w == 0)
    p = _deploy_cli(store, "deploy", "--plane-id", canary, "--template", "w@v1",
                    "--dry-run")
    assert p.returncode == 0


def test_pin_never_invented_without_release(store):
    # Advisory #1285/6107294719 (Security): the pin writer fails closed
    # when the template has no release record — it never invents a pin.
    # (Hand-written waves.json: S2's own file, schema-valid, referencing
    # an unpinned template.)
    _register(store, "plane-1", tenant_id="t1")
    _deploy(store, "plane-1", "w@ghost", status="healthy")
    waves = {
        "schema": "plane-controller-waves/1",
        "template_version": "w@ghost",
        "channel": "stable",
        "buckets": 4,
        "live_wave": 1,
        "halted": None,
        "assignments": {"plane-1": 1},
        "updated_at": "2026-10-11T20:00:00+00:00",
        "reporter": "operator",
        "notes": "",
    }
    with open(os.path.join(store, "waves.json"), "w",
              encoding="utf-8") as fh:
        json.dump(waves, fh)
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "no pinned release" in p.stderr


def test_pin_write_idempotent(store):
    # A second pin write for the same landing stamps nothing new: the
    # journal is append-only, so idempotency is "no new record".
    # (#1345: the stamper is the in-lock variant; the unit test holds
    # the store lock itself.)
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    _deploy(store, "plane-1", "w@v1", status="healthy")

    def _journal_lines():
        path = os.path.join(store, "planes_journal.jsonl")
        with open(path, encoding="utf-8") as fh:
            return [ln for ln in fh if ln.strip()]

    before = len(_journal_lines())
    with events.journal_lock(store):
        stamped = plane_waves._stamp_landed_pins_locked(store, ["plane-1"], "w@v1")
    assert stamped == ["plane-1"]
    assert len(_journal_lines()) == before + 1
    with events.journal_lock(store):
        stamped = plane_waves._stamp_landed_pins_locked(store, ["plane-1"], "w@v1")
    assert stamped == []
    assert len(_journal_lines()) == before + 1


def test_pin_shape_validation_unit():
    # Advisory #1285/6107294719 (QA): malformed pins fail at write time.
    good = {
        "template_version": "w@v1",
        "deployment_id": "dep-1",
        "worker_sha256": _SHA_A,
        "recorded_at": "2026-10-11T20:00:00+00:00",
    }
    assert plane_waves._check_pin_shape(dict(good)) == good
    bad = dict(good)
    del bad["worker_sha256"]
    with pytest.raises(SystemExit) as exc:
        plane_waves._check_pin_shape(bad)
    assert exc.value.code == 2
    bad = dict(good, recorded_at="not-a-time")
    with pytest.raises(SystemExit) as exc:
        plane_waves._check_pin_shape(bad)
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        plane_waves._check_pin_shape("nope")
    assert exc.value.code == 2


def test_waves_corrupt_fails_closed(store):
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    # A tampered waves file must never present a forged live wave.
    with open(os.path.join(store, "waves.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"schema": "plane-controller-waves/1",
                   "template_version": "w@v1", "channel": "stable",
                   "buckets": 4, "live_wave": True, "halted": None,
                   "assignments": {"plane-1": 1}}, fh)
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "waves file" in p.stderr


def test_waves_live_wave_outside_assignments_fails_closed(store):
    # Round-1 Engineering blocker: a live_wave naming no assigned wave
    # must fail closed — without this, promote gates over an empty plane
    # set, stamps nothing, and marks the rollout "complete".
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    waves = _waves_json(store)
    waves["live_wave"] = 9
    with open(os.path.join(store, "waves.json"), "w",
              encoding="utf-8") as fh:
        json.dump(waves, fh)
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "names no assigned wave" in p.stderr
    p = _cli(store, "status")
    assert p.returncode == 2
    assert "names no assigned wave" in p.stderr


def test_halt_promote_message_names_both_recoveries(store):
    # Round-1 Product blocker: the post-halt refusal must name the
    # false-alarm resume (re-assign the same template), not steer the
    # operator into minting a pointless new release.
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    assert _cli(store, "halt", "--reason", "false alarm drill").returncode == 0
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "false alarm" in p.stderr
    assert "new template version" in p.stderr


def test_promote_frozen_writes_no_pins(store):
    # Round-1 Security nit 4: frozen means nothing changes — the freeze
    # refusal lands before the gate and before any pin write.
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-1", "w@v1", status="healthy")
    journal = os.path.join(store, "planes_journal.jsonl")
    before = len([ln for ln in open(journal, encoding="utf-8") if ln.strip()])
    assert _deploy_cli(store, "freeze", "--on").returncode == 0
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "frozen" in p.stderr
    after = len([ln for ln in open(journal, encoding="utf-8") if ln.strip()])
    assert after == before


def test_promote_freeze_mid_promote_writes_no_pins(store):
    # #1345: the pin stamps must happen inside the store lock, after the
    # in-lock freeze check — a freeze landing between the pre-lock gate
    # and the lock acquisition must leave zero pins. (Previously the
    # pre-lock _stamp_landed_pins wrote them before the in-lock check
    # could refuse: the in-lock freeze check was authoritative for the
    # wave advance but not for the pins.)
    # Neuters that must flip this test: (a) revert _stamp_landed_pins_locked
    # to the pre-lock call -> pins present; (b) skip the mid-promote
    # freeze -> promote succeeds and pins are written.
    import contextlib
    from unittest import mock
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-1", "w@v1", status="healthy")
    real_lock = events.journal_lock
    frozen = {"done": False}

    @contextlib.contextmanager
    def freezing_lock(store_dir, timeout_s=None):
        # Freeze the store in the window the bug lived in: after the
        # pre-lock reads, before the critical section's lock acquisition.
        if not frozen["done"]:
            frozen["done"] = True
            with open(os.path.join(store_dir, "freeze.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"schema": "plane-controller-freeze/1",
                           "frozen": True,
                           "set_at": "2026-10-11T21:00:00+00:00",
                           "reporter": "operator",
                           "notes": "mid-promote freeze"}, fh)
        with real_lock(store_dir, timeout_s=timeout_s) as guard:
            yield guard

    with mock.patch.object(events, "journal_lock", freezing_lock):
        with pytest.raises(SystemExit) as exc:
            plane_waves.cmd_promote(
                plane_waves.build_parser().parse_args(
                    ["--store", store, "promote"]))
    assert exc.value.code == 2
    assert frozen["done"]
    rec = plane_inventory.read_planes(store)["plane-1"]
    assert rec["last_known_good"] is None
    # The rollout did not advance either.
    assert plane_waves._read_waves(store)["live_wave"] == 1


def test_canary_tenants_invalid_id_fails_closed(store):
    # Round-1 Security nit 2: the read path validates like the write
    # path — hand-edited garbage fails closed instead of silently never
    # matching.
    with open(os.path.join(store, "canary_tenants.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"schema": "plane-controller-canary-tenants/1",
                   "tenants": ["ok1", "bad id"],
                   "updated_at": "2026-10-11T12:00:00+00:00",
                   "reporter": "operator"}, fh)
    p = _cli(store, "canary-tenants", "--list")
    assert p.returncode == 2
    assert "canary tenant" in p.stderr


def test_promote_notes_append_not_overwrite(store):
    # Round-1 Product nit: promote --notes must not clobber assign-time
    # notes (the single-plane D-RC-3 flag lives there).
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    assert "single-plane estate" in _waves_json(store)["notes"]
    _deploy(store, "plane-1", "w@v1", status="healthy")
    p = _cli(store, "promote", "--notes", "operator witnessed")
    assert p.returncode == 0, p.stderr
    notes = _waves_json(store)["notes"]
    assert "single-plane estate" in notes
    assert "operator witnessed" in notes


def test_promote_reverify_catches_rollout_identity_change(store):
    # Round-1 Engineering blocker: the in-lock re-verify must compare
    # the rollout's identity (template + assignments), not just the
    # live wave — a wave file swapped mid-promote must not be absorbed.
    # (The tamper changes ONLY the template identity: assignments are
    # untouched, so the gate itself would pass — the identity check is
    # the only thing that can catch it.)
    import copy
    from unittest import mock
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-1", "w@v1", status="healthy")
    waves = plane_waves._read_waves(store)
    tampered = copy.deepcopy(waves)
    tampered["template_version"] = "w@v2"
    with mock.patch.object(plane_waves, "_read_waves",
                           side_effect=[waves, tampered]):
        with pytest.raises(SystemExit) as exc:
            plane_waves.cmd_promote(
                plane_waves.build_parser().parse_args(
                    ["--store", store, "promote"]))
    assert exc.value.code == 2


def test_corrupt_observed_at_fails_closed_loudly(store):
    # Round-1 Engineering blocker: a corrupt observed_at must fail
    # closed loudly (exit 2), never launder into a routine
    # "stale-record" wait-and-rerun refusal.
    rec = {
        "schema": "plane-inventory-record/3",
        "plane_id": "plane-1",
        "tenant_id": "t1",
        "template_version": "w@v1",
        "channel": "stable",
        "status": "healthy",
        "observed_at": None,
        "reporter": "operator",
        "notes": "",
        "last_known_good": None,
        "deployment_id": None,
        "worker_sha256": None,
    }
    with open(os.path.join(store, "planes_journal.jsonl"), "a",
              encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    with open(os.path.join(store, "planes.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"schema": "plane-inventory-snapshot/1",
                   "planes": {"plane-1": rec}}, fh, sort_keys=True)
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "stale-record" not in p.stderr
    assert "internal error" in p.stderr


def test_promote_refused_bad_signal_is_audited(store):
    # #1343 item 1: a promote refusal (bad-signal) must land in
    # waves_journal.jsonl — a refused promotion that does not lead to a
    # halt leaves no trace otherwise, and these are exactly the
    # wave-health signals the S5 reporting consumes.
    # Neuter: deleting the _audit_locked call on the refusal path must
    # flip the "promote_refused" assertion.
    _estate(store, n=2, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-0", "w@v1", status="degraded")
    p = _cli(store, "promote")
    assert p.returncode == 2
    assert "bad-signal" in p.stderr
    journal = [json.loads(ln) for ln in
               open(os.path.join(store, "waves_journal.jsonl"),
                    encoding="utf-8") if ln.strip()]
    refused = [r for r in journal if r["action"] == "promote_refused"]
    assert len(refused) == 1
    rec = refused[0]
    assert rec["template_version"] == "w@v1"
    assert rec["from_wave"] == 0
    assert "bad-signal" in rec["reason"]
    # Item 2: the refusal carries the staleness window it was gated on.
    assert rec["stale_hours"] == plane_inventory.DEFAULT_STALE_HOURS
    # The rollout did not advance: the audit is a trace, not a promotion.
    assert _waves_json(store)["live_wave"] == 0


def test_promote_refused_not_converged_is_audited(store):
    # #1343 item 1, second refusal class: not-converged refusals are
    # audited too, with the effective (explicit) staleness window.
    _estate(store, n=2, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    p = _cli(store, "promote", "--stale-hours", "5")
    assert p.returncode == 2
    assert "has not landed" in p.stderr
    journal = [json.loads(ln) for ln in
               open(os.path.join(store, "waves_journal.jsonl"),
                    encoding="utf-8") if ln.strip()]
    refused = [r for r in journal if r["action"] == "promote_refused"]
    assert len(refused) == 1
    assert refused[0]["stale_hours"] == 5.0
    assert "has not landed" in refused[0]["reason"]


def test_promote_audit_records_stale_hours(store):
    # #1343 item 2: the successful-promote audit records the staleness
    # window the wave was promoted on — default and explicit alike.
    # Neuter: dropping stale_hours from the promote audit must flip
    # both assertions below.
    _estate(store, n=2, canary_tenants=("ct1",))
    _release(store)
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    _deploy(store, "plane-0", "w@v1", status="healthy")
    assert _cli(store, "promote").returncode == 0

    def _journal():
        return [json.loads(ln) for ln in
                open(os.path.join(store, "waves_journal.jsonl"),
                     encoding="utf-8") if ln.strip()]

    promoted = [r for r in _journal() if r["action"] == "promote"]
    assert len(promoted) == 1
    assert promoted[0]["stale_hours"] == plane_inventory.DEFAULT_STALE_HOURS
    # Promote the rest of the rollout on an explicit window.
    waves = _waves_json(store)
    rest = [pid for pid, w in waves["assignments"].items() if w != 0]
    for pid in rest:
        _deploy(store, pid, "w@v1", status="healthy")
    while _waves_json(store)["live_wave"] is not None:
        assert _cli(store, "promote", "--stale-hours", "5").returncode == 0
    promoted = [r for r in _journal() if r["action"] == "promote"]
    assert len(promoted) >= 2
    assert promoted[-1]["stale_hours"] == 5.0


def test_assign_dry_run_writes_nothing(store):
    # #1343 item 3: --dry-run prints the would-be wave map and writes
    # nothing — no waves.json, no journal record.
    # Neuter: removing the dry-run early return must flip the
    # waves.json-absence assertion.
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    p = _cli(store, "assign", "--template", "w@v1", "--dry-run")
    assert p.returncode == 0, p.stderr
    out = _json(p)
    assert out["dry_run"] is True
    assert out["action"] == "assign"
    assert out["template_version"] == "w@v1"
    assert out["assignments"] == {"plane-1": 1}
    assert out["live_wave"] == 1
    assert not os.path.exists(os.path.join(store, "waves.json"))
    journal_path = os.path.join(store, "waves_journal.jsonl")
    actions = []
    if os.path.exists(journal_path):
        actions = [json.loads(ln)["action"] for ln in
                   open(journal_path, encoding="utf-8") if ln.strip()]
    assert "assign" not in actions
    # A real assign afterwards still works — the dry run changed nothing.
    p = _cli(store, "assign", "--template", "w@v1")
    assert p.returncode == 0, p.stderr
    assert _waves_json(store)["live_wave"] == 1


def test_assign_dry_run_refusals(store):
    # #1343 item 3: a dry run is a check, not a bypass — refusals fire
    # exactly as in a real assign.
    # Neuter: skipping the refusal checks in dry-run mode must flip the
    # frozen assertion (exit 0 instead of 2).
    _register(store, "plane-1", tenant_id="t1")
    _release(store)
    assert _deploy_cli(store, "freeze", "--on").returncode == 0
    p = _cli(store, "assign", "--template", "w@v1", "--dry-run")
    assert p.returncode == 2
    assert "frozen" in p.stderr
    assert not os.path.exists(os.path.join(store, "waves.json"))
    assert _deploy_cli(store, "freeze", "--off").returncode == 0
    assert _cli(store, "assign", "--template", "w@v1").returncode == 0
    p = _cli(store, "assign", "--template", "w@v1", "--dry-run")
    assert p.returncode == 2
    assert "live at wave" in p.stderr or "already live" in p.stderr


def test_assign_warns_on_degraded_planes(store):
    # #1343 item 4: assign warns (stderr, never stdout's JSON) when an
    # assigned plane is degraded — the wave cannot promote until it is
    # healthy or re-observed.
    # Neuter: deleting the warning print must flip the stderr assertion.
    _register(store, "plane-1", tenant_id="t1")
    _register(store, "plane-2", tenant_id="t2")
    _release(store)
    _deploy(store, "plane-2", "w@v1", status="degraded")
    p = _cli(store, "assign", "--template", "w@v1", "--dry-run")
    assert p.returncode == 0, p.stderr
    assert "warning" in p.stderr
    assert "plane-2" in p.stderr
    # stdout stays pure JSON — the warning goes to stderr.
    out = _json(p)
    assert out["dry_run"] is True
    assert out["degraded_planes"] == ["plane-2"]
    # And the warning fires on a real assign too (not dry-run-only).
    p = _cli(store, "assign", "--template", "w@v1")
    assert p.returncode == 0, p.stderr
    assert "warning" in p.stderr
    assert "plane-2" in p.stderr
