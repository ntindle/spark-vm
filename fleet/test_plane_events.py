"""Hermetic tests for the S5 plane update-event journal (issue #1288).

Stage-1 scope only: the operator-observed event journal for the plane
layer — deploy started/landed/deferred/failed/rolled-back events —
with three named producers ((a) the operator's `event` entry, (b) the
S4 driver's lifecycle emission, (c) the S1 `deploy` landing record),
the `events` read path ("what happened in the last window?"), and the
S2 promotion gate consuming unresolved deploy-failed events as a
bad-signal refusal per D-RC-4. Stage 2 (plane-signed health events) is
doc-only: no code, no tests.

Two layers, matching the lane's conventions:
- Subprocess tests exercise the CLIs exactly as the operator runs them.
- In-process tests import the modules for the deployer seam (fake
  DEPLOYER) and the append_plane_event validation paths.

Each test gets its own --store temp dir. Non-vacuity: key behaviors are
mutation-verified (see inline comments naming the neuter that must flip
the test).
"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_INV_CLI = os.path.join(_HERE, "plane_inventory.py")
_DEPLOY_CLI = os.path.join(_HERE, "plane_deploy.py")
_WAVES_CLI = os.path.join(_HERE, "plane_waves.py")
_STORE_TIMEOUT_S = 60

_SHA_A = "aa" * 32
_SHA_B = "bb" * 32

sys.path.insert(0, _HERE)
import plane_deploy  # noqa: E402  (seam injection needs the module object)
import plane_inventory  # noqa: E402
import plane_waves  # noqa: E402


def _run(cli, store, *argv):
    cmd = [sys.executable, cli, "--store", store, *argv]
    return subprocess.run(cmd, capture_output=True, text=True,
                          timeout=_STORE_TIMEOUT_S)


def _inv(store, *argv):
    return _run(_INV_CLI, store, *argv)


def _cli(store, *argv):
    return _run(_DEPLOY_CLI, store, *argv)


def _waves(store, *argv):
    return _run(_WAVES_CLI, store, *argv)


@pytest.fixture()
def store():
    with tempfile.TemporaryDirectory(prefix="plane-events-") as d:
        yield d


def _json(proc):
    return json.loads(proc.stdout)


def _release(store, template="w@v1", sha=_SHA_A, deployment_id="dep-1"):
    assert _inv(store, "release", "--template", template, "--channel",
                "stable", "--deployment-id", deployment_id,
                "--worker-sha256", sha).returncode == 0


def _setup(store, plane_id="plane-1", template="w@v1", sha=_SHA_A,
           deployment_id="dep-1"):
    assert _inv(store, "register", "--plane-id", plane_id,
                "--tenant-id", "t1").returncode == 0
    _release(store, template, sha, deployment_id)


def _events(store, *argv):
    p = _inv(store, "events", *argv)
    assert p.returncode == 0, p.stderr
    return _json(p)["events"]


def _kinds(store, *argv):
    return [e["kind"] for e in _events(store, *argv)]


# --- Stage-1 producer (a): the operator's own entry ------------------------


def test_event_cli_appends_and_reads_back(store):
    _setup(store)
    before = datetime.now(timezone.utc)
    p = _inv(store, "event", "--plane-id", "plane-1", "--kind",
             "deploy-deferred", "--template", "w@v1", "--notes", "holding")
    assert p.returncode == 0, p.stderr
    (ev,) = _events(store)
    assert ev["schema"] == "plane-event/1"
    assert ev["plane_id"] == "plane-1"
    assert ev["kind"] == "deploy-deferred"
    assert ev["template_version"] == "w@v1"
    assert ev["reporter"] == "operator"
    assert ev["notes"] == "holding"
    # observed_at is stamped by the writer (collector-side), not the caller.
    observed = datetime.fromisoformat(ev["observed_at"])
    assert before <= observed <= datetime.now(timezone.utc)
    # Neuter: dropping the observed_at stamp must flip this (the reader
    # fails closed on the missing field).


def test_event_kind_vocabulary_closed_cli(store):
    _setup(store)
    p = _inv(store, "event", "--plane-id", "plane-1", "--kind", "nope")
    assert p.returncode != 0


def test_event_cli_rejects_deploy_started(store):
    # M1 (#1348 review): deploy-started is the S4 driver's alone — the
    # operator's entry refuses it, so a stray operator-emitted started
    # can never become "latest" and silently clear the gate's
    # bad-signal. (The shared writer still accepts it: the driver is a
    # legitimate producer.)
    _setup(store)
    p = _inv(store, "event", "--plane-id", "plane-1", "--kind",
             "deploy-started")
    assert p.returncode != 0
    assert _kinds(store) == []


def test_event_kind_vocabulary_closed_api(store):
    _setup(store)
    # The argparse choices= also guards, but the shared writer must not
    # depend on the CLI layer for the closed vocabulary.
    with pytest.raises(SystemExit):
        plane_inventory.append_plane_event(store, "plane-1", "deployed")
    # Neuter: removing the kind check in append_plane_event must flip this.


def test_event_requires_registered_plane(store):
    p = _inv(store, "event", "--plane-id", "ghost", "--kind",
             "deploy-deferred")
    assert p.returncode == 2
    assert "not registered" in p.stderr


def test_observed_at_never_backfilled(store):
    # There is no flag or argument that sets observed_at: the discipline
    # "never backfilled from a plane claim" is structural, not advisory.
    p = _inv(store, "event", "--help")
    assert p.returncode == 0
    assert "--observed-at" not in p.stdout
    assert "observed_at" not in p.stdout
    # Neuter: adding an --observed-at passthrough must flip this.


def test_event_field_grammars(store):
    _setup(store)
    # Bad template / deployment-id / sha256 fail closed at the boundary.
    assert _inv(store, "event", "--plane-id", "plane-1", "--kind",
                "deploy-failed", "--template", "has space").returncode == 2
    assert _inv(store, "event", "--plane-id", "plane-1", "--kind",
                "deploy-failed", "--worker-sha256",
                "ZZ" * 32).returncode == 2
    assert _kinds(store) == []


# --- Stage-1 producer (c): the S1 deploy landing record --------------------


def test_s1_deploy_emits_deploy_landed(store):
    _setup(store)
    assert _inv(store, "deploy", "--plane-id", "plane-1", "--template",
                "w@v1", "--notes", "manual landing").returncode == 0
    (ev,) = _events(store)
    assert ev["kind"] == "deploy-landed"
    assert ev["template_version"] == "w@v1"
    assert ev["notes"] == "manual landing"
    # Neuter: removing the append_plane_event call in S1 cmd_deploy must
    # flip this (the journal would be empty).


def _driver_main(store, *argv):
    """In-process driver invocation — sees the monkeypatched DEPLOYER.

    (The driver runs in a subprocess nowhere in this file: subprocess
    tests are for dry-run/gates only, per the lane's convention. A
    monkeypatched DEPLOYER is invisible across a process boundary.)
    Returns main()'s rc; _fail paths raise SystemExit.
    """
    return plane_deploy.main(["--store", store, *argv])


def test_s1_deploy_carries_artifact_identity(store, monkeypatch):
    _setup(store)
    # The S4 driver wrote the artifact identity into the record (F-RC-10);
    # the S1 deploy preserves it and the landing event carries it.
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        lambda pid, did, sha: {"worker_sha256_observed": sha})
    assert _driver_main(store, "deploy", "--plane-id", "plane-1",
                        "--template", "w@v1") == 0
    assert _inv(store, "deploy", "--plane-id", "plane-1",
                "--template", "w@v1").returncode == 0
    landed = [e for e in _events(store) if e["kind"] == "deploy-landed"]
    assert landed, "expected deploy-landed events"
    assert landed[-1]["deployment_id"] == "dep-1"
    assert landed[-1]["worker_sha256"] == _SHA_A


# --- Stage-1 producer (b): the S4 driver lifecycle -------------------------


def test_driver_lifecycle_started_then_landed(store, monkeypatch):
    _setup(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        lambda pid, did, sha: {"worker_sha256_observed": sha,
                                              "duration_s": 2.0})
    assert _driver_main(store, "deploy", "--plane-id", "plane-1",
                        "--template", "w@v1", "--notes", "wave 1") == 0
    kinds = _kinds(store)
    assert kinds == ["deploy-started", "deploy-landed"], kinds
    started, landed = _events(store)
    assert started["template_version"] == "w@v1"
    assert started["deployment_id"] == "dep-1"
    assert started["worker_sha256"] == _SHA_A
    assert landed["template_version"] == "w@v1"
    assert landed["notes"] == "wave 1"
    # started precedes landed in journal (append) order.
    assert started["observed_at"] <= landed["observed_at"]
    # Neuter: deleting the deploy-started emission in cmd_deploy must
    # flip this (kinds would be ["deploy-landed"]).


def test_driver_failure_emits_deploy_failed(store, monkeypatch, capsys):
    _setup(store)

    def _boom(pid, did, sha):
        raise RuntimeError("wrangler exploded")

    monkeypatch.setattr(plane_deploy, "DEPLOYER", _boom)
    with pytest.raises(SystemExit) as ei:
        _driver_main(store, "deploy", "--plane-id", "plane-1",
                     "--template", "w@v1")
    assert ei.value.code == 2
    assert "wrangler exploded" in capsys.readouterr().err
    kinds = _kinds(store)
    assert kinds == ["deploy-started", "deploy-failed"], kinds
    failed = _events(store)[-1]
    assert "wrangler exploded" in failed["notes"]
    assert failed["template_version"] == "w@v1"
    # Nothing landed: no plane record was written for the failed push.
    rec = plane_inventory.read_planes(store)["plane-1"]
    assert rec["status"] == "provisioning"
    # Neuter: restoring _run_deployer's old _fail-on-error behavior (no
    # _DeployerFailure) must flip this — the failure would exit before
    # any event is written.


def test_driver_unconfigured_emits_failed(store):
    # No deployer wired: the attempt still leaves a complete lifecycle
    # trace (started -> failed), and the operator hears the same message.
    _setup(store)
    p = _cli(store, "deploy", "--plane-id", "plane-1", "--template", "w@v1")
    assert p.returncode == 2
    assert "no deployer configured" in p.stderr
    assert _kinds(store) == ["deploy-started", "deploy-failed"]


def test_driver_systemexit_deployer_emits_failed_and_blocks(store,
                                                            monkeypatch):
    # B1 (#1348 review): a wired deployer that exits itself (SystemExit —
    # argparse/click wrappers do this) must still leave a terminal
    # event. Without the `except SystemExit` handler the journal would
    # dangle at deploy-started and the S2 gate would not see the
    # failure — promotion could proceed after a known-failed push.
    _assign_and_land(store)

    def _exits(pid, did, sha):
        raise SystemExit(3)

    monkeypatch.setattr(plane_deploy, "DEPLOYER", _exits)
    with pytest.raises(SystemExit) as ei:
        _driver_main(store, "deploy", "--plane-id", "plane-1",
                     "--template", "w@v1")
    assert ei.value.code == 3
    assert _kinds(store)[-2:] == ["deploy-started", "deploy-failed"]
    assert "exited with code 3" in _events(store)[-1]["notes"]
    p = _waves(store, "promote")
    assert p.returncode != 0
    assert "bad-signal" in p.stderr
    # Neuter: deleting the `except SystemExit` handler in cmd_deploy
    # must flip this (the journal would dangle at deploy-started and
    # promote would succeed).


def test_driver_dry_run_writes_no_events(store, monkeypatch):
    _setup(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        lambda pid, did, sha: {"worker_sha256_observed": sha})
    assert _cli(store, "deploy", "--plane-id", "plane-1", "--template",
                "w@v1", "--dry-run").returncode == 0
    assert not os.path.exists(os.path.join(store, "plane_events.jsonl"))


def test_driver_rollback_failure_emits_deploy_failed(store, monkeypatch):
    # Rollback needs a last_known_good pin: run the full wave flow first
    # (this also exercises the gate's happy path — no unresolved
    # failures, so promote succeeds).
    _setup(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        lambda pid, did, sha: {"worker_sha256_observed": sha})
    assert _waves(store, "assign", "--template", "w@v1",
                  "--buckets", "1").returncode == 0
    assert _driver_main(store, "deploy", "--plane-id", "plane-1",
                        "--template", "w@v1") == 0
    assert _waves(store, "promote").returncode == 0
    _release(store, "w@v2", _SHA_B, "dep-2")
    assert _waves(store, "assign", "--template", "w@v2",
                  "--buckets", "1").returncode == 0
    assert _driver_main(store, "deploy", "--plane-id", "plane-1",
                        "--template", "w@v2") == 0

    def _boom(pid, did, sha):
        raise RuntimeError("rollback push exploded")

    monkeypatch.setattr(plane_deploy, "DEPLOYER", _boom)
    with pytest.raises(SystemExit) as ei:
        _driver_main(store, "rollback", "--plane-id", "plane-1")
    assert ei.value.code == 2
    kinds = _kinds(store)
    assert kinds[-1] == "deploy-failed", kinds
    failed = _events(store)[-1]
    assert "rollback attempt failed" in failed["notes"]
    assert "rollback push exploded" in failed["notes"]


def test_driver_rollback_success_emits_rolled_back(store, monkeypatch):
    _setup(store)
    monkeypatch.setattr(plane_deploy, "DEPLOYER",
                        lambda pid, did, sha: {"worker_sha256_observed": sha})
    assert _waves(store, "assign", "--template", "w@v1",
                  "--buckets", "1").returncode == 0
    assert _driver_main(store, "deploy", "--plane-id", "plane-1",
                        "--template", "w@v1") == 0
    assert _waves(store, "promote").returncode == 0
    _release(store, "w@v2", _SHA_B, "dep-2")
    assert _waves(store, "assign", "--template", "w@v2",
                  "--buckets", "1").returncode == 0
    assert _driver_main(store, "deploy", "--plane-id", "plane-1",
                        "--template", "w@v2") == 0
    assert _driver_main(store, "rollback", "--plane-id", "plane-1") == 0
    kinds = _kinds(store)
    assert kinds[-1] == "rolled-back", kinds
    rolled = _events(store)[-1]
    assert rolled["template_version"] == "w@v1"
    assert rolled["worker_sha256"] == _SHA_A


# --- The `events` read path -------------------------------------------------


def test_events_query_filters(store):
    _setup(store)
    assert _inv(store, "deploy", "--plane-id", "plane-1", "--template",
                "w@v1").returncode == 0
    assert _inv(store, "event", "--plane-id", "plane-1", "--kind",
                "deploy-deferred", "--notes", "hold").returncode == 0
    assert _inv(store, "register", "--plane-id", "plane-2",
                "--tenant-id", "t2").returncode == 0
    assert _inv(store, "event", "--plane-id", "plane-2", "--kind",
                "deploy-failed", "--notes", "oops").returncode == 0
    assert len(_events(store)) == 3
    assert len(_events(store, "--plane-id", "plane-1")) == 2
    assert len(_events(store, "--kind", "deploy-failed")) == 1
    assert len(_events(store, "--kind", "deploy-landed",
                       "--plane-id", "plane-1")) == 1
    # --since-hours 1 keeps today's events; a zero-ish window keeps none.
    assert len(_events(store, "--since-hours", "1")) == 3
    assert len(_events(store, "--since-hours", "0.000001")) == 0
    p = _inv(store, "events", "--kind", "bogus")
    assert p.returncode == 2


# --- S2 gate consumption (D-RC-4) -------------------------------------------


def _assign_and_land(store, template="w@v1"):
    _setup(store, template=template)
    assert _waves(store, "assign", "--template", template,
                  "--buckets", "1").returncode == 0
    assert _inv(store, "deploy", "--plane-id", "plane-1", "--template",
                template).returncode == 0


def test_gate_refuses_unresolved_failure(store):
    _assign_and_land(store)
    assert _inv(store, "event", "--plane-id", "plane-1", "--kind",
                "deploy-failed", "--template", "w@v1",
                "--notes", "smoke failed").returncode == 0
    p = _waves(store, "promote")
    assert p.returncode != 0
    assert "bad-signal" in p.stderr
    assert "deploy-failed" in p.stderr
    # Neuter: deleting the _unresolved_deploy_failures check in
    # _wave_gate must flip this (promote would succeed).


def test_gate_cleared_by_fresh_landing(store):
    _assign_and_land(store)
    assert _inv(store, "event", "--plane-id", "plane-1", "--kind",
                "deploy-failed", "--template", "w@v1").returncode == 0
    assert _waves(store, "promote").returncode != 0
    # The operator-correctable path: re-record the landing (S1 producer
    # (c)) and promotion proceeds.
    assert _inv(store, "deploy", "--plane-id", "plane-1", "--template",
                "w@v1").returncode == 0
    assert _waves(store, "promote").returncode == 0
    # Neuter: S1 cmd_deploy not emitting deploy-landed must flip this
    # (the gate would still see the failure as latest).


def test_gate_ignores_pre_wave_failure(store):
    # A failure from an earlier rollout never blocks a fresh wave: the
    # event window starts when the wave went live.
    _setup(store)
    assert _inv(store, "event", "--plane-id", "plane-1", "--kind",
                "deploy-failed", "--notes", "old rollout").returncode == 0
    assert _waves(store, "assign", "--template", "w@v1",
                  "--buckets", "1").returncode == 0
    assert _inv(store, "deploy", "--plane-id", "plane-1", "--template",
                "w@v1").returncode == 0
    assert _waves(store, "promote").returncode == 0


def test_gate_missing_journal_is_no_signal(store):
    # D-RC-6: missing events do not block promotion (pre-S5 stores).
    _assign_and_land(store)
    os.unlink(os.path.join(store, "plane_events.jsonl"))
    assert _waves(store, "promote").returncode == 0


def test_gate_deferred_and_rolled_back_do_not_block(store):
    _assign_and_land(store)
    assert _inv(store, "event", "--plane-id", "plane-1", "--kind",
                "deploy-deferred", "--notes", "operator hold").returncode == 0
    assert _inv(store, "event", "--plane-id", "plane-1", "--kind",
                "rolled-back", "--template", "w@v1").returncode == 0
    assert _waves(store, "promote").returncode == 0


def test_corrupt_event_line_fails_closed(store):
    _setup(store)
    assert _inv(store, "deploy", "--plane-id", "plane-1", "--template",
                "w@v1").returncode == 0
    with open(os.path.join(store, "plane_events.jsonl"), "a",
              encoding="utf-8") as fh:
        fh.write("this is not json\n")
    assert _inv(store, "events").returncode == 2
    assert _waves(store, "assign", "--template", "w@v1",
                  "--buckets", "1").returncode == 0
    # The gate consumes the journal: corruption fails closed, never
    # launders into an empty history.
    assert _waves(store, "promote").returncode != 0
