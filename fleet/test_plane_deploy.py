"""Hermetic tests for fleet/plane_deploy.py (issue #1287, S4 deploy driver).

Two layers, matching the module's shape:
- Subprocess tests exercise the CLI exactly as the operator runs it
  (dry-run plans, D-RC-5 refusals, fail-closed pin reads). These need no
  deployer.
- In-process tests import the module and inject a fake DEPLOYER — the
  only honest way to exercise the Cloudflare push seam (the default
  deployer fails closed by design).

Each test gets its own --store temp dir. Non-vacuity: key behaviors are
mutation-verified (see inline comments naming the neuter that must flip
the test).
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_CLI = os.path.join(_HERE, "plane_deploy.py")
_INV_CLI = os.path.join(_HERE, "plane_inventory.py")
_STORE_TIMEOUT_S = 60

_SHA_A = "aa" * 32
_SHA_B = "bb" * 32

sys.path.insert(0, _HERE)
import plane_deploy  # noqa: E402  (seam injection needs the module object)


def _run(cli, store, *argv):
    cmd = [sys.executable, cli, "--store", store, *argv]
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=_STORE_TIMEOUT_S)


def _inv(store, *argv):
    return _run(_INV_CLI, store, *argv)


def _cli(store, *argv):
    return _run(_CLI, store, *argv)


@pytest.fixture()
def store():
    with tempfile.TemporaryDirectory(prefix="plane-deploy-") as d:
        yield d


def _json(proc):
    return json.loads(proc.stdout)


def _register_release(store, plane_id="plane-1", template="w@v1",
                      deployment_id="dep-1", sha=_SHA_A):
    assert _inv(store, "register", "--plane-id", plane_id,
                "--tenant-id", "t1").returncode == 0
    assert _inv(store, "release", "--template", template,
                "--deployment-id", deployment_id,
                "--worker-sha256", sha).returncode == 0


def _journal_lines(store, name="planes_journal.jsonl"):
    path = os.path.join(store, name)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [ln for ln in fh if ln.strip()]


def _plant_plane_record(store, plane_id, **overrides):
    """Simulate the S2 promotion writer: hand-write a /3 journal record +
    a consistent snapshot (the divergence check compares the two)."""
    rec = {
        "schema": "plane-inventory-record/3",
        "plane_id": plane_id,
        "tenant_id": "t1",
        "template_version": "w@v1",
        "channel": "stable",
        "status": "healthy",
        "observed_at": "2026-10-11T12:00:00+00:00",
        "reporter": "operator",
        "notes": "",
        "last_known_good": None,
        "deployment_id": None,
        "worker_sha256": None,
    }
    rec.update(overrides)
    with open(os.path.join(store, "planes_journal.jsonl"), "a",
              encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    snap_path = os.path.join(store, "planes.json")
    planes = {}
    if os.path.exists(snap_path):
        with open(snap_path, "r", encoding="utf-8") as fh:
            planes = json.load(fh)["planes"]
    planes[plane_id] = rec
    with open(snap_path, "w", encoding="utf-8") as fh:
        json.dump({"schema": "plane-inventory-snapshot/1", "planes": planes},
                  fh, sort_keys=True)
    return rec


def _plant_waves(store, live_wave, assignments):
    with open(os.path.join(store, "waves.json"), "w",
              encoding="utf-8") as fh:
        json.dump({
            "schema": "plane-controller-waves/1",
            "live_wave": live_wave,
            "assignments": assignments,
            "updated_at": "2026-10-11T12:00:00+00:00",
            "reporter": "operator",
            "notes": "",
        }, fh, sort_keys=True)


def _lkg(template="w@v1", deployment_id="dep-1", sha=_SHA_A):
    return {
        "template_version": template,
        "deployment_id": deployment_id,
        "worker_sha256": sha,
        "recorded_at": "2026-10-11T12:00:00+00:00",
    }


# --------------------------------------------------------------------------
# Subprocess: dry-run, gates, fail-closed reads (no deployer needed)
# --------------------------------------------------------------------------

def test_deploy_dry_run_prints_plan_and_writes_nothing(store):
    # Neuter: removing the dry-run early return must flip the journal
    # assertion (the real path would fail closed on the missing deployer,
    # rc 2 instead of 0).
    _register_release(store)
    before = _journal_lines(store)
    assert len(before) == 1  # the register record
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 0, p.stderr
    plan = _json(p)
    assert plan["dry_run"] is True
    assert plan["action"] == "deploy"
    assert plan["deployment_id"] == "dep-1"
    assert plan["worker_sha256"] == _SHA_A
    assert plan["gates"] == {"frozen": False, "live_wave": None,
                             "in_live_wave": True}
    # No journal write, no cost event, no freeze file from a dry run.
    assert _journal_lines(store) == before
    assert _journal_lines(store, "costs.jsonl") == []
    assert not os.path.exists(os.path.join(store, "freeze.json"))


def test_deploy_unregistered_plane_fails_closed(store):
    _register_release(store, plane_id="plane-9")
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 2
    assert "not registered" in p.stderr


def test_deploy_missing_release_fails_closed_never_floating(store):
    # Neuter: falling back to "latest" (or skipping the release read)
    # must flip this — the driver must never deploy a floating target.
    assert _inv(store, "register", "--plane-id", "plane-1",
                "--tenant-id", "t1").returncode == 0
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v9",
             "--dry-run")
    assert p.returncode == 2
    assert "no pinned release" in p.stderr


def test_deploy_without_deployer_fails_closed_and_writes_nothing(store):
    # The default deployer is fail-closed by design: with no Cloudflare
    # wiring, a real deploy refuses before any journal or cost write.
    _register_release(store)
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1")
    assert p.returncode == 2
    assert "no deployer configured" in p.stderr
    assert len(_journal_lines(store)) == 1
    assert _journal_lines(store, "costs.jsonl") == []


def test_freeze_on_refuses_deploy_and_rollback(store):
    # Neuter: deleting the _read_freeze call in _gates must flip both
    # refusal assertions below.
    _register_release(store)
    assert _cli(store, "freeze", "--on", "--notes", "drill").returncode == 0
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 2
    assert "frozen" in p.stderr
    p = _cli(store, "rollback", "--plane-id", "plane-1", "--dry-run")
    assert p.returncode == 2
    assert "frozen" in p.stderr
    assert _cli(store, "freeze", "--off").returncode == 0
    assert _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
                "--dry-run").returncode == 0


def test_freeze_roundtrip_file_contract(store):
    assert _cli(store, "freeze", "--on").returncode == 0
    with open(os.path.join(store, "freeze.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    assert data["schema"] == "plane-controller-freeze/1"
    assert data["frozen"] is True
    assert data["reporter"] == "operator"
    assert _cli(store, "freeze", "--off").returncode == 0
    with open(os.path.join(store, "freeze.json"), encoding="utf-8") as fh:
        assert json.load(fh)["frozen"] is False


def test_freeze_corrupt_fails_closed(store):
    # A tampered freeze file must never silently unfreeze the controller.
    _register_release(store)
    with open(os.path.join(store, "freeze.json"), "w",
              encoding="utf-8") as fh:
        json.dump({"schema": "plane-controller-freeze/1", "frozen": "yes"},
                  fh)
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 2
    assert "refusing deploys" in p.stderr


def test_wave_out_of_wave_refused_in_wave_allowed(store):
    # Neuter: making _read_waves always return (None, {}) must flip the
    # plane-2 refusal.
    _register_release(store, plane_id="plane-1")
    assert _inv(store, "register", "--plane-id", "plane-2",
                "--tenant-id", "t1").returncode == 0
    _plant_waves(store, 2, {"plane-1": 2})
    p = _cli(store, "deploy", "--plane-id", "plane-2", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 2
    assert "not in the live wave 2" in p.stderr
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 0, p.stderr
    assert _json(p)["gates"]["live_wave"] == 2


def test_no_waves_file_means_no_wave_constraint(store):
    _register_release(store)
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 0, p.stderr


def test_waves_live_wave_null_means_no_constraint(store):
    _register_release(store)
    _plant_waves(store, None, {})
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 0, p.stderr


def test_waves_corrupt_fails_closed(store):
    _register_release(store)
    _plant_waves(store, "two", {"plane-1": "two"})
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 2
    assert "refusing deploys" in p.stderr


def test_waves_boolean_assignment_fails_closed_not_wave_one(store):
    # JSON true == 1 in Python: a boolean assignment must not pass as
    # wave 1 — the corrupt-waves philosophy fails closed instead.
    _register_release(store)
    _plant_waves(store, 1, {"plane-1": True})
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 2
    assert "refusing deploys" in p.stderr


def test_waves_live_wave_bool_fails_closed(store):
    # The bool-is-int-subclass trap on live_wave itself: dedicated guard,
    # so it gets its own pin. The assignment is a clean int on purpose —
    # without the live_wave guard, `1 == True` would admit the plane.
    # Neuter: deleting the bool guard in _read_waves must flip this.
    _register_release(store)
    _plant_waves(store, True, {"plane-1": 1})
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 2
    assert "refusing deploys" in p.stderr


def test_deploy_retired_plane_refused(store):
    # The controller must not promote into retired planes: the driver
    # refuses the push (S1's inventory `deploy` keeps the intentional
    # resurrect semantics — the operator records the rejoin there first).
    # Neuter: deleting the retired check must flip this (silent resurrect
    # + push, rc 0).
    _register_release(store)
    assert _inv(store, "retire", "--plane-id", "plane-1").returncode == 0
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 2
    assert "retired" in p.stderr


def test_rollback_retired_plane_refused(store):
    _register_release(store)
    _plant_plane_record(store, "plane-1", last_known_good=_lkg())
    assert _inv(store, "retire", "--plane-id", "plane-1").returncode == 0
    p = _cli(store, "rollback", "--plane-id", "plane-1", "--dry-run")
    assert p.returncode == 2
    assert "retired" in p.stderr


def test_retired_refusal_precedes_freeze_gate(store):
    # Refusal precedence: on a retired plane in a frozen store, the
    # operator must hear "retired" (the actual blocker), not "frozen".
    # Neuter: moving the retired check after _gates flips this to
    # "frozen".
    _register_release(store)
    assert _inv(store, "retire", "--plane-id", "plane-1").returncode == 0
    assert _cli(store, "freeze", "--on").returncode == 0
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1",
             "--dry-run")
    assert p.returncode == 2
    assert "retired" in p.stderr, p.stderr
    assert "frozen" not in p.stderr
    p = _cli(store, "rollback", "--plane-id", "plane-1", "--dry-run")
    assert p.returncode == 2
    assert "retired" in p.stderr, p.stderr
    assert "frozen" not in p.stderr


def test_rollback_snapshot_divergence_fails_closed(store):
    # The advisory's threat model: a tampered last_known_good in the
    # snapshot must fail closed via the journal-as-truth discipline the
    # driver inherits — never become a rollback target.
    _register_release(store)
    _plant_plane_record(store, "plane-1", last_known_good=_lkg())
    snap_path = os.path.join(store, "planes.json")
    with open(snap_path, "r", encoding="utf-8") as fh:
        snap = json.load(fh)
    snap["planes"]["plane-1"]["last_known_good"]["worker_sha256"] = "dd" * 32
    with open(snap_path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, sort_keys=True)
    p = _cli(store, "rollback", "--plane-id", "plane-1", "--dry-run")
    assert p.returncode == 2
    assert "divergence" in p.stderr


def test_rollback_no_pin_fails_closed(store):
    _register_release(store)
    p = _cli(store, "rollback", "--plane-id", "plane-1", "--dry-run")
    assert p.returncode == 2
    assert "no last_known_good" in p.stderr


def test_rollback_pin_without_matching_release_fails_closed(store):
    # Advisory #1287/6107295238: a pin with no release record is a
    # floating identity — refuse.
    _register_release(store)
    _plant_plane_record(store, "plane-1", last_known_good=_lkg("w@v9"))
    p = _cli(store, "rollback", "--plane-id", "plane-1", "--dry-run")
    assert p.returncode == 2
    assert "no pinned release" in p.stderr


def test_rollback_pin_release_mismatch_fails_closed(store):
    # Neuter: deleting the pin-vs-release field comparison must flip
    # this — a stale pin must never become a deploy target.
    _register_release(store)
    _plant_plane_record(store, "plane-1",
                        last_known_good=_lkg("w@v1", "dep-1", _SHA_B))
    p = _cli(store, "rollback", "--plane-id", "plane-1", "--dry-run")
    assert p.returncode == 2
    assert "refusing rollback" in p.stderr


def test_rollback_dry_run_prints_plan_and_writes_nothing(store):
    _register_release(store)
    _plant_plane_record(store, "plane-1", last_known_good=_lkg())
    before = _journal_lines(store)
    p = _cli(store, "rollback", "--plane-id", "plane-1", "--dry-run")
    assert p.returncode == 0, p.stderr
    plan = _json(p)
    assert plan["dry_run"] is True
    assert plan["action"] == "rollback"
    assert plan["template_version"] == "w@v1"
    assert plan["deployment_id"] == "dep-1"
    assert _journal_lines(store) == before
    assert _journal_lines(store, "costs.jsonl") == []


# --------------------------------------------------------------------------
# In-process: the deployer seam (fake DEPLOYER injected)
# --------------------------------------------------------------------------

def _fake_deployer_factory(observed_sha=_SHA_A, duration_s=12.5, exc=None):
    def fake(plane_id, deployment_id, worker_sha256):
        if exc is not None:
            raise exc
        assert deployment_id == "dep-1"
        assert worker_sha256 == _SHA_A
        return {"worker_sha256_observed": observed_sha,
                "duration_s": duration_s}
    return fake


@pytest.fixture()
def wired_store(store, monkeypatch):
    _register_release(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        _fake_deployer_factory())
    return store


def _plane_record(store, plane_id="plane-1"):
    with open(os.path.join(store, "planes.json"), encoding="utf-8") as fh:
        return json.load(fh)["planes"][plane_id]


def _cost_events(store):
    return [json.loads(ln) for ln in _journal_lines(store, "costs.jsonl")]


def test_deploy_happy_path_writes_artifact_join_and_cost(wired_store,
                                                        monkeypatch):
    # Neuters: (a) dropping the sha comparison in _run_deployer flips the
    # record assertions via _SHA_B below; (b) deleting the
    # append_cost_event call flips the cost assertion; (c) writing the
    # record without deployment_id/worker_sha256 flips the join
    # assertion (F-RC-10).
    store = wired_store
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        _fake_deployer_factory(duration_s=12.5))
    rc = plane_deploy.main(["--store", store, "deploy",
                            "--plane-id", "plane-1", "--template", "w@v1",
                            "--cost-usd", "0.02", "--notes", "wave 2"])
    assert rc == 0
    rec = _plane_record(store)
    assert rec["template_version"] == "w@v1"
    assert rec["deployment_id"] == "dep-1"      # F-RC-10 artifact join
    assert rec["worker_sha256"] == _SHA_A
    assert rec["schema"] == "plane-inventory-record/3"
    assert rec["status"] == "healthy"
    costs = _cost_events(store)
    assert len(costs) == 1
    assert costs[0]["event"] == "update"        # D-RC-6 first writer
    assert costs[0]["duration_s"] == 12.5       # deployer's reported duration
    assert costs[0]["cost_usd"] == 0.02
    assert costs[0]["plane_id"] == "plane-1"


def test_deploy_preserves_last_known_good(store, monkeypatch):
    # Writer contract: only the S2 promotion step writes the pin — the
    # driver carries it through untouched.
    _register_release(store)
    pin = _lkg()
    _plant_plane_record(store, "plane-1", last_known_good=pin)
    monkeypatch.setattr(plane_deploy, "DEPLOYER", _fake_deployer_factory())
    rc = plane_deploy.main(["--store", store, "deploy",
                            "--plane-id", "plane-1", "--template", "w@v1"])
    assert rc == 0
    assert _plane_record(store)["last_known_good"] == pin


def test_deploy_sha_mismatch_fails_closed_no_writes(store, monkeypatch):
    # The digest that lands must equal the pinned digest — otherwise
    # nothing is recorded and no cost event is emitted.
    _register_release(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        _fake_deployer_factory(observed_sha=_SHA_B))
    with pytest.raises(SystemExit) as ei:
        plane_deploy.main(["--store", store, "deploy",
                           "--plane-id", "plane-1", "--template", "w@v1"])
    assert ei.value.code == 2
    assert len(_journal_lines(store)) == 1  # register record only
    assert _cost_events(store) == []


def test_deploy_malformed_observed_sha_fails_closed(store, monkeypatch,
                                                   capsys):
    # The assertion on stderr pins the malformed-digest check itself, not
    # just fail-closed-ness (the mismatch path fails closed identically).
    _register_release(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        _fake_deployer_factory(observed_sha="not-a-sha"))
    with pytest.raises(SystemExit) as ei:
        plane_deploy.main(["--store", store, "deploy",
                           "--plane-id", "plane-1", "--template", "w@v1"])
    assert ei.value.code == 2
    assert "malformed" in capsys.readouterr().err
    assert len(_journal_lines(store)) == 1


def test_deployer_exception_fails_closed_no_writes(store, monkeypatch):
    _register_release(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        _fake_deployer_factory(exc=RuntimeError("boom")))
    with pytest.raises(SystemExit) as ei:
        plane_deploy.main(["--store", store, "deploy",
                           "--plane-id", "plane-1", "--template", "w@v1"])
    assert ei.value.code == 2
    assert len(_journal_lines(store)) == 1
    assert _cost_events(store) == []


@pytest.mark.parametrize("bad_duration", ["garbage", float("inf"), -5])
def test_deployer_bad_duration_fails_closed(store, monkeypatch,
                                             bad_duration):
    # A deployer-reported duration that is not a finite non-negative
    # number must not enter the D-MT5 ledger — fail closed, nothing
    # recorded. (check_nonneg_number rejects non-numeric, non-finite,
    # and negative alike.)
    _register_release(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        _fake_deployer_factory(duration_s=bad_duration))
    with pytest.raises(SystemExit) as ei:
        plane_deploy.main(["--store", store, "deploy",
                           "--plane-id", "plane-1", "--template", "w@v1"])
    assert ei.value.code == 2
    assert len(_journal_lines(store)) == 1
    assert _cost_events(store) == []


def test_deploy_flag_duration_wins_over_deployer(store, monkeypatch):
    _register_release(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        _fake_deployer_factory(duration_s=12.5))
    rc = plane_deploy.main(["--store", store, "deploy",
                            "--plane-id", "plane-1", "--template", "w@v1",
                            "--duration-s", "30"])
    assert rc == 0
    assert _cost_events(store)[0]["duration_s"] == 30.0


def test_rollback_happy_path(store, monkeypatch):
    _register_release(store)
    _plant_plane_record(store, "plane-1", template_version="w@v2",
                        last_known_good=_lkg("w@v1"))
    monkeypatch.setattr(plane_deploy, "DEPLOYER", _fake_deployer_factory())
    rc = plane_deploy.main(["--store", store, "rollback",
                            "--plane-id", "plane-1", "--cost-usd", "0.01"])
    assert rc == 0
    rec = _plane_record(store)
    assert rec["template_version"] == "w@v1"    # the pin's template
    assert rec["deployment_id"] == "dep-1"
    assert rec["worker_sha256"] == _SHA_A
    assert rec["last_known_good"] == _lkg("w@v1")  # pin preserved, not cleared
    costs = _cost_events(store)
    assert len(costs) == 1
    assert costs[0]["event"] == "rollback"
    assert costs[0]["cost_usd"] == 0.01


def test_deploy_status_degraded_recorded(store, monkeypatch):
    # --status is user-facing CLI surface on deploy: the recorded status
    # must be the operator's claim, not the default.
    _register_release(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER", _fake_deployer_factory())
    rc = plane_deploy.main(["--store", store, "deploy",
                            "--plane-id", "plane-1", "--template", "w@v1",
                            "--status", "degraded"])
    assert rc == 0
    assert _plane_record(store)["status"] == "degraded"
