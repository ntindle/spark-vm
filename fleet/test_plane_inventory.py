"""Hermetic tests for fleet/plane_inventory.py (issue #1261 S1).

The suite exercises the CLIs through subprocess (never through imports),
mirroring the box-inventory suite's convention. Each test gets its own
--store temp dir. Non-vacuity: key behaviors are mutation-verified (see
inline comments naming the neuter that must flip the test).
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_CLI = os.path.join(_HERE, "plane_inventory.py")
_STORE_TIMEOUT_S = 60


def _run(store, *argv):
    cmd = [sys.executable, _CLI, "--store", store, *argv]
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=_STORE_TIMEOUT_S
    )


@pytest.fixture()
def store():
    with tempfile.TemporaryDirectory(prefix="plane-inventory-") as d:
        yield d


def _json(proc):
    return json.loads(proc.stdout)


def test_register_deploy_census_roundtrip(store):
    p = _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "tenant-a")
    assert p.returncode == 0, p.stderr
    assert _json(p)["status"] == "provisioning"

    p = _run(store, "deploy", "--plane-id", "plane-1", "--template", "worker-template@abc1234")
    assert p.returncode == 0, p.stderr
    assert _json(p)["template_version"] == "worker-template@abc1234"

    p = _run(store, "census")
    assert p.returncode == 0, p.stderr
    body = _json(p)
    assert body["eligible"] == 1
    assert body["excluded"] == []
    assert body["census"] == [
        {"template_version": "worker-template@abc1234", "planes": 1, "pct": 100.0}
    ]


def test_register_duplicate_fails_closed(store):
    p = _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "tenant-a")
    assert p.returncode == 0, p.stderr
    p = _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "tenant-b")
    assert p.returncode == 2
    assert "already registered" in p.stderr


def test_deploy_unknown_plane_fails_closed(store):
    # Non-vacuity neuter: removing the registration gate here lets this
    # command silently create a plane row mid-rollout; the test pins it.
    p = _run(store, "deploy", "--plane-id", "ghost", "--template", "v1")
    assert p.returncode == 2
    assert "not registered" in p.stderr


def test_stale_reports_version_mismatch_and_exit_1(store):
    for pid, tmpl in (("plane-1", "worker-template@new"), ("plane-2", "worker-template@old")):
        assert _run(store, "register", "--plane-id", pid, "--tenant-id", "t").returncode == 0
        assert _run(store, "deploy", "--plane-id", pid, "--template", tmpl).returncode == 0
    p = _run(store, "stale", "--expected", "worker-template@new")
    assert p.returncode == 1  # not converged
    body = _json(p)
    assert body["count"] == 1
    assert body["not_converged"][0]["plane_id"] == "plane-2"
    assert body["not_converged"][0]["reason"] == "version-mismatch"

    # Non-vacuity neuter: `!=` flipped to `==` in cmd_stale reports the
    # converged plane instead; both assertions below catch it.
    p = _run(store, "deploy", "--plane-id", "plane-2", "--template", "worker-template@new")
    assert p.returncode == 0
    p = _run(store, "stale", "--expected", "worker-template@new")
    assert p.returncode == 0
    assert _json(p)["count"] == 0


def test_stale_window_excludes_fresh_records_never_includes_retired(store):
    assert _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "t").returncode == 0
    assert _run(store, "retire", "--plane-id", "plane-1").returncode == 0
    p = _run(store, "census")
    body = _json(p)
    assert body["eligible"] == 0
    # Retired planes are excluded from the denominator but disclosed.
    assert body["excluded"] == [{"plane_id": "plane-1", "reason": "retired"}]
    p = _run(store, "stale", "--expected", "worker-template@new")
    body = _json(p)
    # The retired plane is listed (controller must not promote into it).
    assert body["not_converged"][0] == {
        "plane_id": "plane-1",
        "reason": "retired",
        "template_version": None,
    }


def test_id_and_template_grammar_rejects(store):
    p = _run(store, "register", "--plane-id", "../escape", "--tenant-id", "t")
    assert p.returncode == 2
    p = _run(store, "register", "--plane-id", "ok", "--tenant-id", "t",
             "--template", "has whitespace")
    assert p.returncode == 2


def test_cost_journal_and_dmt5_summary(store):
    assert _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "t").returncode == 0
    assert _run(store, "register", "--plane-id", "plane-2", "--tenant-id", "t").returncode == 0
    for pid, ev, secs, usd in (
        ("plane-1", "provision", 300, 0.42),
        ("plane-1", "update", 120, 0.07),
        ("plane-1", "update", 130, 0.08),
        ("plane-2", "update", 110, 0.06),
    ):
        p = _run(store, "cost", "--plane-id", pid, "--event", ev,
                 "--duration-s", str(secs), "--cost-usd", str(usd))
        assert p.returncode == 0, p.stderr

    p = _run(store, "cost-summary")
    assert p.returncode == 0, p.stderr
    body = _json(p)
    assert body["planes"] == 2
    assert body["by_event"]["provision"]["count"] == 1
    assert body["by_event"]["provision"]["cost_usd_total"] == 0.42
    assert body["by_event"]["update"]["count"] == 3
    # D-MT5 measurement: recurring update+rollback cost, provision excluded.
    # Non-vacuity neuter: including provision here yields 0.63 instead of 0.21.
    assert body["recurring_cost_usd_total"] == 0.21
    assert body["by_event"]["update"]["duration_s_median"] == 120.0
    assert body["per_plane"]["plane-1"]["update"]["count"] == 2

    # --plane-id filters.
    p = _run(store, "cost-summary", "--plane-id", "plane-2")
    assert _json(p)["planes"] == 1


def test_cost_negative_and_unknown_plane_fail_closed(store):
    assert _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "t").returncode == 0
    p = _run(store, "cost", "--plane-id", "plane-1", "--event", "update",
             "--cost-usd", "-1")
    assert p.returncode == 2
    p = _run(store, "cost", "--plane-id", "ghost", "--event", "update")
    assert p.returncode == 2


def test_cost_rejects_nonfinite(store):
    # Non-vacuity: pre-fix, `inf`/`1e999` were accepted and poisoned the
    # D-MT5 recurring total with Infinity (not strict JSON). Both must
    # fail closed at the ledger boundary.
    assert _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "t").returncode == 0
    for bad in ("inf", "-inf", "1e999", "nan"):
        p = _run(store, "cost", "--plane-id", "plane-1", "--event", "update",
                 "--cost-usd", bad)
        assert p.returncode == 2, bad
        p = _run(store, "cost", "--plane-id", "plane-1", "--event", "update",
                 "--duration-s", bad)
        assert p.returncode == 2, bad


def test_snapshot_journal_divergence_fails_closed(store):
    # Regression pin for the tampered-snapshot false-green: hand-editing
    # planes.json to a converged state while the journal still records the
    # old template must fail closed (exit 2), never present a green stale.
    assert _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "t").returncode == 0
    assert _run(store, "deploy", "--plane-id", "plane-1",
                "--template", "worker-template@old").returncode == 0
    snap_path = os.path.join(store, "planes.json")
    with open(snap_path, "r", encoding="utf-8") as fh:
        snap = json.load(fh)
    from datetime import datetime, timezone
    snap["planes"]["plane-1"]["template_version"] = "worker-template@new"
    snap["planes"]["plane-1"]["observed_at"] = datetime.now(timezone.utc).isoformat()
    with open(snap_path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh)

    # Pre-fix this returned exit 0, count 0 (false green).
    p = _run(store, "stale", "--expected", "worker-template@new")
    assert p.returncode == 2
    assert "divergence" in p.stderr
    p = _run(store, "census")
    assert p.returncode == 2
    assert "divergence" in p.stderr


def test_null_snapshot_fails_closed(store):
    # A `null` planes.json is structural corruption, not an empty store:
    # pre-fix, census exited 0 and stale exited 0/"all converged".
    assert _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "t").returncode == 0
    snap_path = os.path.join(store, "planes.json")
    with open(snap_path, "w", encoding="utf-8") as fh:
        fh.write("null\n")
    p = _run(store, "census")
    assert p.returncode == 2
    assert "corrupt" in p.stderr
    p = _run(store, "stale", "--expected", "worker-template@new")
    assert p.returncode == 2
    assert "corrupt" in p.stderr


def test_stale_hours_nan_rejected(store):
    # NaN evades a bare `<= 0` guard (nan <= 0 is False) and would
    # silently mark every record stale.
    p = _run(store, "census", "--stale-hours", "nan")
    assert p.returncode == 2


def test_cost_events_survive_snapshot_republish(store):
    # The cost journal is append-only and independent of planes.json.
    assert _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "t").returncode == 0
    assert _run(store, "cost", "--plane-id", "plane-1", "--event", "provision",
                "--duration-s", "60", "--cost-usd", "0.10").returncode == 0
    # A later deploy republishes the snapshot; the cost journal must be intact.
    assert _run(store, "deploy", "--plane-id", "plane-1", "--template", "v2").returncode == 0
    body = _json(_run(store, "cost-summary"))
    assert body["by_event"]["provision"]["count"] == 1


def test_store_files_are_created(store):
    assert _run(store, "register", "--plane-id", "plane-1", "--tenant-id", "t").returncode == 0
    assert os.path.isfile(os.path.join(store, "planes.json"))
    assert os.path.isfile(os.path.join(store, "planes_journal.jsonl"))


def test_help_exits_zero():
    p = subprocess.run([sys.executable, _CLI, "--help"], capture_output=True,
                       text=True, timeout=_STORE_TIMEOUT_S)
    assert p.returncode == 0
    assert "register" in p.stdout
