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


@pytest.mark.parametrize("bad", ["inf", "1e999"])
def test_stale_hours_nonfinite_rejected(store, bad):
    # +inf is the dangerous mirror of the NaN case: it evades `<= 0`
    # (inf > 0) and would silently mark every record fresh, vacating the
    # D-RC-4 freshness bound the S2 promotion gate rests on.
    # Neuter: reverting the isfinite guard to the bare isnan check must
    # flip both cases (they return 0 pre-fix).
    p = _run(store, "census", "--stale-hours", bad)
    assert p.returncode == 2
    assert "positive number" in p.stderr
    p = _run(store, "stale", "--expected", "worker-template@v1",
             "--stale-hours", bad)
    assert p.returncode == 2
    assert "positive number" in p.stderr


def test_stale_hours_huge_finite_fails_closed(store):
    # The sink-level guard: 1e308 is finite to argparse (passes the CLI
    # boundary) but overflows stale_hours*3600 to inf inside
    # is_record_fresh — the same vacuous gate as +inf via a different
    # path. census must fail closed (loud exit 2), never report the
    # estate eligible on a vacuous window.
    # Neuter: without the is_record_fresh sink guard this census exits 0.
    assert _run(store, "register", "--plane-id", "plane-1",
                "--tenant-id", "t").returncode == 0
    p = _run(store, "census", "--stale-hours", "1e308")
    assert p.returncode == 2
    assert "internal error" in p.stderr


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


_SHA256_A = "ab" * 32
_SHA256_B = "cd" * 32


def _release(store, template="worker-template@abc1234", channel="stable",
              deployment_id="dpl_8f3a2b", sha256=_SHA256_A, notes=""):
    argv = ["release", "--template", template, "--channel", channel,
            "--deployment-id", deployment_id, "--worker-sha256", sha256]
    if notes:
        argv += ["--notes", notes]
    return _run(store, *argv)


def test_release_roundtrip(store):
    p = _release(store)
    assert p.returncode == 0, p.stderr
    assert _json(p)["deployment_id"] == "dpl_8f3a2b"

    p = _run(store, "release-show", "--template", "worker-template@abc1234")
    assert p.returncode == 0, p.stderr
    rec = _json(p)
    assert rec["worker_sha256"] == _SHA256_A
    assert rec["channel"] == "stable"
    assert rec["schema"] == "plane-template-release/1"

    p = _run(store, "releases")
    assert p.returncode == 0, p.stderr
    rows = _json(p)["releases"]
    assert len(rows) == 1
    assert rows[0]["template_version"] == "worker-template@abc1234"


def test_release_is_immutable(store):
    # Non-vacuity neuter: removing the re-release gate lets a second pin
    # silently overwrite the first — the whole D-RC-2 "one identity scheme"
    # guarantee collapses.
    assert _release(store).returncode == 0
    p = _release(store, deployment_id="dpl_9999", sha256=_SHA256_B)
    assert p.returncode == 2
    assert "already released" in p.stderr
    # Even an identical re-release is refused (no silent no-ops).
    p = _release(store)
    assert p.returncode == 2


def test_release_rejects_bad_pin_inputs(store):
    assert _release(store, sha256="zz" * 32).returncode == 2
    assert _release(store, sha256="ab" * 31).returncode == 2
    # Uppercase hex is a second spelling of the same pin — rejected.
    assert _release(store, sha256="AB" * 32).returncode == 2
    # Python's `$` matches before a trailing newline: a newline-poisoned
    # pin would exit 0 and could never hex-match the S4 driver's digest.
    # Non-vacuity neuter: `\\A...\\Z` back to `^...$` accepts the newline.
    assert _release(store, sha256=_SHA256_A + "\n").returncode == 2
    assert _release(store, deployment_id="has whitespace").returncode == 2
    assert _release(store, deployment_id="dpl_2\n").returncode == 2
    assert _release(store, deployment_id="").returncode == 2


def test_release_show_unknown_template_fails_closed(store):
    # The S4 driver must never deploy a template with no pinned manifest.
    p = _run(store, "release-show", "--template", "never-released")
    assert p.returncode == 2
    assert "no pinned release" in p.stderr


def test_releases_channel_filter(store):
    assert _release(store, template="t-canary", channel="canary").returncode == 0
    assert _release(store, template="t-stable", channel="stable").returncode == 0
    p = _run(store, "releases", "--channel", "canary")
    rows = _json(p)["releases"]
    assert [r["template_version"] for r in rows] == ["t-canary"]


def test_releases_snapshot_divergence_fails_closed(store):
    # The pinned manifest is the rollout's trust root: a forged pin in
    # releases.json must fail closed, never deploy.
    assert _release(store).returncode == 0
    snap_path = os.path.join(store, "releases.json")
    with open(snap_path, "r", encoding="utf-8") as fh:
        snap = json.load(fh)
    snap["releases"]["worker-template@abc1234"]["worker_sha256"] = _SHA256_B
    with open(snap_path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh)

    p = _run(store, "release-show", "--template", "worker-template@abc1234")
    assert p.returncode == 2
    assert "divergence" in p.stderr
    p = _run(store, "releases")
    assert p.returncode == 2
    assert "divergence" in p.stderr


def test_releases_null_snapshot_fails_closed(store):
    assert _release(store).returncode == 0
    with open(os.path.join(store, "releases.json"), "w", encoding="utf-8") as fh:
        fh.write("null\n")
    p = _run(store, "releases")
    assert p.returncode == 2
    assert "corrupt" in p.stderr


def test_last_known_good_none_by_default_and_not_written_by_deploy(store):
    # Writer contract: only the S2 promotion step writes last_known_good.
    # deploy must never set it (neuter: setting it in cmd_deploy makes the
    # last recorded observation the rollback target — wrong by design).
    assert _run(store, "register", "--plane-id", "plane-1",
                "--tenant-id", "t").returncode == 0
    assert _run(store, "deploy", "--plane-id", "plane-1",
                "--template", "worker-template@v2").returncode == 0
    snap_path = os.path.join(store, "planes.json")
    with open(snap_path, "r", encoding="utf-8") as fh:
        rec = json.load(fh)["planes"]["plane-1"]
    assert rec["last_known_good"] is None
    assert rec["schema"] == "plane-inventory-record/3"


def test_last_known_good_preserved_by_deploy_and_retire(store):
    # A promotion-written pin must survive later observation records.
    assert _run(store, "register", "--plane-id", "plane-1",
                "--tenant-id", "t").returncode == 0
    snap_path = os.path.join(store, "planes.json")
    pin = {"template_version": "worker-template@v1", "deployment_id": "dpl_1",
           "worker_sha256": _SHA256_A, "recorded_at": "2026-10-11T00:00:00+00:00"}
    journal_path = os.path.join(store, "planes_journal.jsonl")
    for path in (snap_path, journal_path):
        if path == journal_path:
            with open(path, "r", encoding="utf-8") as fh:
                lines = [json.loads(line) for line in fh if line.strip()]
            lines[-1]["last_known_good"] = pin
            with open(path, "w", encoding="utf-8") as fh:
                for line in lines:
                    fh.write(json.dumps(line, sort_keys=True) + "\n")
        else:
            with open(path, "r", encoding="utf-8") as fh:
                snap = json.load(fh)
            snap["planes"]["plane-1"]["last_known_good"] = pin
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(snap, fh)

    assert _run(store, "deploy", "--plane-id", "plane-1",
                "--template", "worker-template@v2").returncode == 0
    assert _run(store, "retire", "--plane-id", "plane-1").returncode == 0
    with open(snap_path, "r", encoding="utf-8") as fh:
        rec = json.load(fh)["planes"]["plane-1"]
    assert rec["last_known_good"] == pin


def test_last_known_good_covered_by_divergence_check(store):
    # A tampered rollback pin must fail closed like a tampered template.
    assert _run(store, "register", "--plane-id", "plane-1",
                "--tenant-id", "t").returncode == 0
    snap_path = os.path.join(store, "planes.json")
    with open(snap_path, "r", encoding="utf-8") as fh:
        snap = json.load(fh)
    snap["planes"]["plane-1"]["last_known_good"] = {
        "template_version": "worker-template@evil", "deployment_id": "dpl_x",
        "worker_sha256": _SHA256_B, "recorded_at": "2026-10-11T00:00:00+00:00"}
    with open(snap_path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh)
    p = _run(store, "stale", "--expected", "worker-template@new")
    assert p.returncode == 2
    assert "divergence" in p.stderr


def test_release_after_snapshot_delete_fails_closed(store):
    # Deleting releases.json must not silently re-open pinning: the
    # missing-snapshot path replays the journal and fails closed when it
    # is non-empty (neuter: returning {} without verifying lets a
    # different pin through and the journal silently holds two pins).
    assert _release(store).returncode == 0
    os.unlink(os.path.join(store, "releases.json"))

    p = _release(store)
    assert p.returncode == 2
    assert "divergence" in p.stderr
    p = _release(store, deployment_id="dpl_other", sha256=_SHA256_B)
    assert p.returncode == 2
    assert "divergence" in p.stderr
    p = _run(store, "releases")
    assert p.returncode == 2
    assert "divergence" in p.stderr
    p = _run(store, "release-show", "--template", "worker-template@abc1234")
    assert p.returncode == 2
    assert "divergence" in p.stderr


def test_register_after_snapshot_delete_fails_closed(store):
    # Deleting planes.json must not silently re-open registration: the
    # missing-snapshot path replays the journal and fails closed when it
    # is non-empty (neuter: returning {} without verifying lets the second
    # register through and the journal silently holds two registration
    # rows for plane-1).
    assert _run(store, "register", "--plane-id", "plane-1",
                "--tenant-id", "t").returncode == 0
    os.unlink(os.path.join(store, "planes.json"))

    p = _run(store, "register", "--plane-id", "plane-1",
             "--tenant-id", "t")
    assert p.returncode == 2
    assert "divergence" in p.stderr
    p = _run(store, "stale", "--expected", "worker-template@new")
    assert p.returncode == 2
    assert "divergence" in p.stderr

    # Control: a genuinely fresh store (no journal rows either) still
    # registers fine — the verify is a no-op on an empty journal.
    with tempfile.TemporaryDirectory(prefix="plane-inventory-fresh-") as fresh:
        assert _run(fresh, "register", "--plane-id", "plane-1",
                    "--tenant-id", "t").returncode == 0


def test_deploy_normalizes_legacy_record_to_lkg_none(store):
    # /1-era records carry no last_known_good key; deploy must stamp a
    # /2 record that carries the /2-mandated field (None until promotion
    # writes it), not a /2 record that omits it. Neuter: dropping the
    # setdefault leaves the field absent on the new record.
    assert _run(store, "register", "--plane-id", "plane-1",
                "--tenant-id", "t").returncode == 0
    snap_path = os.path.join(store, "planes.json")
    journal_path = os.path.join(store, "planes_journal.jsonl")
    with open(snap_path, "r", encoding="utf-8") as fh:
        snap = json.load(fh)
    rec = snap["planes"]["plane-1"]
    rec["schema"] = "plane-inventory-record/1"
    del rec["last_known_good"]
    with open(snap_path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh)
    with open(journal_path, "r", encoding="utf-8") as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    lines[-1]["schema"] = "plane-inventory-record/1"
    del lines[-1]["last_known_good"]
    with open(journal_path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line, sort_keys=True) + "\n")

    assert _run(store, "deploy", "--plane-id", "plane-1",
                "--template", "worker-template@v2").returncode == 0
    with open(snap_path, "r", encoding="utf-8") as fh:
        new_rec = json.load(fh)["planes"]["plane-1"]
    assert new_rec["schema"] == "plane-inventory-record/3"
    assert "last_known_good" in new_rec
    assert new_rec["last_known_good"] is None
    # /3-era keys normalize too: a /1 record has no artifact identity.
    assert new_rec["deployment_id"] is None
    assert new_rec["worker_sha256"] is None


def test_s1_deploy_and_retire_preserve_artifact_identity(store):
    # Writer contract (F-RC-10): ONLY the S4 driver writes
    # deployment_id/worker_sha256; the S1 deploy/retire commands preserve
    # them untouched. Neuter: dropping the setdefault-free preservation
    # (e.g. rebuilding the record without dict(prev)) wipes the join and
    # must flip this test.
    assert _run(store, "register", "--plane-id", "plane-1",
                "--tenant-id", "t").returncode == 0
    snap_path = os.path.join(store, "planes.json")
    journal_path = os.path.join(store, "planes_journal.jsonl")

    def _plant_artifact(deployment_id, worker_sha256):
        with open(snap_path, "r", encoding="utf-8") as fh:
            snap = json.load(fh)
        rec = snap["planes"]["plane-1"]
        rec["deployment_id"] = deployment_id
        rec["worker_sha256"] = worker_sha256
        with open(snap_path, "w", encoding="utf-8") as fh:
            json.dump(snap, fh)
        with open(journal_path, "r", encoding="utf-8") as fh:
            lines = [json.loads(line) for line in fh if line.strip()]
        lines[-1]["deployment_id"] = deployment_id
        lines[-1]["worker_sha256"] = worker_sha256
        with open(journal_path, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(json.dumps(line, sort_keys=True) + "\n")

    _plant_artifact("dep-9", "cc" * 32)
    assert _run(store, "deploy", "--plane-id", "plane-1",
                "--template", "worker-template@v2").returncode == 0
    with open(snap_path, "r", encoding="utf-8") as fh:
        rec = json.load(fh)["planes"]["plane-1"]
    assert rec["deployment_id"] == "dep-9"
    assert rec["worker_sha256"] == "cc" * 32
    assert rec["template_version"] == "worker-template@v2"
    assert _run(store, "retire", "--plane-id", "plane-1").returncode == 0
    with open(snap_path, "r", encoding="utf-8") as fh:
        rec = json.load(fh)["planes"]["plane-1"]
    assert rec["deployment_id"] == "dep-9"
    assert rec["worker_sha256"] == "cc" * 32
    assert rec["status"] == "retired"


def test_release_rejects_non_lowercase_channel(store):
    # #1343 item 5: D-RC-7 keys on the exact spelling "security" — a
    # miscapitalized channel (Security/SECURITY) passes the id grammar
    # but would silently travel normal waves, the bad failure direction,
    # so release refuses it at the boundary.
    # Neuter: deleting the lowercase check must flip the "Security"
    # assertion below.
    p = _release(store, channel="Security")
    assert p.returncode == 2
    assert "lowercase" in p.stderr
    p = _release(store, channel="SECURITY")
    assert p.returncode == 2
    assert "lowercase" in p.stderr
    p = _release(store, channel="Canary")
    assert p.returncode == 2
    # The exact spellings still pin releases.
    assert _release(store, channel="security").returncode == 0
    p = _release(store, template="t-stable-2", channel="stable",
                 deployment_id="dpl_stable2")
    assert p.returncode == 0, p.stderr
    assert _json(p)["channel"] == "stable"
