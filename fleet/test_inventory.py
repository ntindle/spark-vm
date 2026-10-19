"""Tests for fleet/inventory.py and fleet/box_snapshot.py (G16 / #607 S1).

Run from the repo root:  python3 -m pytest fleet/test_inventory.py -q

All tests run locally with no network and no home-dir writes: per-box
estates and stores live under tmp dirs, and the CLIs are exercised through
subprocess, never imported. The two producer-contract tests additionally
shell the repo's real `scripts/self_update.py` and `deploy/auto-deploy.sh`
(hermetic in practice — no network, fast — but not in the strictest
sense). Time is controlled through the --staleness-hours flag (0 makes
every record stale, a large value makes all eligible) so no test depends
on the wall clock beyond "collect just ran".
"""

import json
import os
import hashlib
import re
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

FLEET = os.path.dirname(os.path.abspath(__file__))
INVENTORY = os.path.join(FLEET, "inventory.py")
BOX_SNAPSHOT = os.path.join(FLEET, "box_snapshot.py")

NOW = datetime.now(timezone.utc)
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
COMMIT_C = "c" * 40


def run_inventory(*argv):
    return subprocess.run(
        [sys.executable, INVENTORY, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def run_box_snapshot(*argv):
    return subprocess.run(
        [sys.executable, BOX_SNAPSHOT, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _status_json(generated_at=None, drift=0):
    return {
        "generated_at": (generated_at or NOW).isoformat(),
        "slice": "S1",
        "tools": [
            {"tool": "docker", "scope": "toolset", "installed": True,
             "version": "28.0.0", "pinned": "28.0.0", "drift": False,
             "note": ""},
            {"tool": "gh", "scope": "toolset", "installed": True,
             "version": "2.70.0", "pinned": "2.66.0", "drift": drift > 0,
             "note": ""},
        ],
        "pin_warnings": ["gh drifted"] * drift,
    }


def _audit_line(ts, event, frm, to, result="ok"):
    return {"ts": ts.isoformat(), "event": event, "component": "spark-vm",
            "phase": "deploy", "from": frm, "to": to, "result": result}


def _snapshot_json(commit, frozen=None, arc=None, image=None):
    return {"repo_commit": commit,
            "gate": {"frozen": frozen, "answer_age_s": 42},
            "arc_active": arc, "image_version": image,
            "note": None, "emitted_at": NOW.isoformat()}


@pytest.fixture()
def env():
    """(estate, store) tmp dirs; estate/<box>/ holds the three artifacts."""
    with tempfile.TemporaryDirectory() as root:
        estate = os.path.join(root, "estate")
        store = os.path.join(root, "store")
        os.makedirs(estate)
        yield estate, store


def _write_box(estate, box, status=None, audit=None, snapshot=None,
               raw_status=None, raw_snapshot=None):
    boxdir = os.path.join(estate, box)
    os.makedirs(boxdir, exist_ok=True)
    if raw_status is not None:
        with open(os.path.join(boxdir, "status.json"), "w") as fh:
            fh.write(raw_status)
    elif status is not None:
        with open(os.path.join(boxdir, "status.json"), "w") as fh:
            json.dump(status, fh)
    if audit is not None:
        with open(os.path.join(boxdir, "audit-tail.jsonl"), "w") as fh:
            for line in audit:
                fh.write(json.dumps(line) + "\n")
    if raw_snapshot is not None:
        with open(os.path.join(boxdir, "snapshot.json"), "w") as fh:
            fh.write(raw_snapshot)
    elif snapshot is not None:
        with open(os.path.join(boxdir, "snapshot.json"), "w") as fh:
            json.dump(snapshot, fh)


def _collect(env, boxes):
    estate, store = env
    for name, kw in boxes.items():
        _write_box(estate, name, **kw)
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    return estate, store


def _journal(store):
    with open(os.path.join(store, "journal.jsonl")) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _snapshot(store):
    with open(os.path.join(store, "snapshot.json")) as fh:
        return json.load(fh)


# --- collect -------------------------------------------------------------


def test_collect_ignores_dot_directories(env):
    # #1326: gate_sync.sh records per-box staleness in the estate's
    # .gate_sync_state/ dir; the collector must not census it as a
    # phantom box (the sync loop's own "$ESTATE"/*/ glob already
    # ignores dot-dirs — the collector must agree).
    estate, store = env
    state_dir = os.path.join(estate, ".gate_sync_state")
    os.makedirs(state_dir)
    with open(os.path.join(state_dir, "tower"), "w") as fh:
        fh.write("1760295600 scp-failed\n")
    _collect(env, {
        "tower": {"status": _status_json(), "audit": [],
                  "snapshot": _snapshot_json(COMMIT_A)},
    })
    records = _journal(store)
    assert {r["box_id"] for r in records} == {"tower"}
    assert ".gate_sync_state" not in _snapshot(store)["boxes"]


def test_collect_one_record_per_box(env):
    _collect(env, {
        "tower": {"status": _status_json(), "audit": [], "snapshot":
                  _snapshot_json(COMMIT_A)},
        "spark": {"status": _status_json(), "audit": [],
                  "snapshot": _snapshot_json(COMMIT_B)},
    })
    estate, store = env
    records = _journal(store)
    assert {r["box_id"] for r in records} == {"tower", "spark"}
    assert all(r["schema"] == "fleet-inventory-record/1" for r in records)
    assert all(r["reporter"] == "estate-collector-s1" for r in records)
    snap = _snapshot(store)
    assert snap["schema"] == "fleet-inventory-snapshot/1"
    assert set(snap["boxes"]) == {"tower", "spark"}
    assert snap["boxes"]["tower"]["versions"]["repo_commit"] == COMMIT_A


def test_collect_twice_appends_journal_and_latest_wins(env):
    estate, store = _collect(env, {
        "tower": {"status": _status_json(), "snapshot":
                  _snapshot_json(COMMIT_A)},
    })
    _write_box(estate, "tower", status=_status_json(),
               snapshot=_snapshot_json(COMMIT_B))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    records = [r for r in _journal(store) if r["box_id"] == "tower"]
    assert len(records) == 2
    assert _snapshot(store)["boxes"]["tower"]["versions"][
        "repo_commit"] == COMMIT_B


def test_collect_box_id_map(env):
    estate, store = env
    _write_box(estate, "ssh-alias-1", status=_status_json(),
               snapshot=_snapshot_json(COMMIT_A))
    mapping = os.path.join(estate, "ids.json")
    with open(mapping, "w") as fh:
        json.dump({"ssh-alias-1": "tower"}, fh)
    proc = run_inventory("collect", "--estate", estate, "--store", store,
                         "--box-id-map", mapping)
    assert proc.returncode == 0, proc.stderr
    assert set(_snapshot(store)["boxes"]) == {"tower"}


def test_collect_missing_artifacts_produce_nulls_not_failure(env):
    _collect(env, {"ghost": {}})
    estate, store = env
    record = _journal(store)[0]
    assert record["versions"]["repo_commit"] is None
    assert record["versions"]["toolset_pins"] is None
    assert record["last_tick_at"] == {"deploy": None, "toolset": None, "image": None}
    assert any("missing" in n for n in record["notes"])


def test_collect_malformed_status_does_not_sink_other_boxes(env):
    _collect(env, {
        "bad": {"raw_status": "{not json"},
        "good": {"status": _status_json(), "snapshot":
                 _snapshot_json(COMMIT_A)},
    })
    estate, store = env
    records = {r["box_id"]: r for r in _journal(store)}
    assert set(records) == {"bad", "good"}
    assert records["bad"]["versions"]["toolset_pins"] is None
    assert any("unreadable" in n for n in records["bad"]["notes"])


def test_collect_empty_estate_is_an_error(env):
    estate, store = env
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 2
    assert "no per-box directories" in proc.stderr


def test_collect_nonexistent_estate_is_an_error(env):
    estate, store = env
    proc = run_inventory("collect", "--estate",
                         os.path.join(estate, "nope"), "--store", store)
    assert proc.returncode == 2
    assert "does not exist" in proc.stderr


# --- record semantics ----------------------------------------------------


def test_snapshot_authoritative_on_audit_mismatch(env):
    """Audit claims to=B; box snapshot says A. A wins; box is suspect."""
    _collect(env, {"tower": {
        "status": _status_json(),
        "audit": [_audit_line(NOW, "deploy", COMMIT_A, COMMIT_B)],
        "snapshot": _snapshot_json(COMMIT_A),
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["versions"]["repo_commit"] == COMMIT_A
    assert record["suspect"] is True
    assert COMMIT_B in record["suspect_reason"]


def test_repo_commit_falls_back_to_audit_tail_without_snapshot(env):
    _collect(env, {"tower": {
        "status": _status_json(),
        "audit": [_audit_line(NOW, "deploy", COMMIT_A, COMMIT_B)],
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["versions"]["repo_commit"] == COMMIT_B
    assert record["suspect"] is False
    assert any("audit tail" in n for n in record["notes"])


def test_future_generated_at_is_flagged_not_dropped(env):
    future = NOW + timedelta(hours=2)
    _collect(env, {"tower": {"status": _status_json(generated_at=future),
                            "snapshot": _snapshot_json(COMMIT_A)}})
    estate, store = env
    record = _journal(store)[0]
    assert record["last_tick_at"]["toolset"] is not None  # kept
    assert any("future" in n for n in record["notes"])


def test_last_tick_at_picks_newest_deploy_event(env):
    older = NOW - timedelta(hours=3)
    _collect(env, {"tower": {
        "audit": [_audit_line(older, "deploy", COMMIT_A, COMMIT_A),
                  _audit_line(NOW, "rollback", COMMIT_B, COMMIT_A,
                              result="rolled-back"),
                  {"ts": NOW.isoformat(), "event": "note", "to": COMMIT_B}],
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["last_tick_at"]["deploy"] == NOW.isoformat()
    # the non-tick "note" event is ignored
    assert record["versions"]["repo_commit"] == COMMIT_A


def test_image_version_null_means_not_applicable(env):
    _collect(env, {"tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    estate, store = env
    assert _journal(store)[0]["versions"]["image_version"] is None


# --- inventory / census --------------------------------------------------


def test_inventory_census_math_and_table(env):
    _collect(env, {
        "a1": {"snapshot": _snapshot_json(COMMIT_A)},
        "a2": {"snapshot": _snapshot_json(COMMIT_A)},
        "b1": {"snapshot": _snapshot_json(COMMIT_B)},
    })
    estate, store = env
    proc = run_inventory("inventory", "--store", store,
                         "--staleness-hours", "999")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "census (eligible 3 of 3 boxes; 0 stale, excluded)" in out
    assert "2/3 boxes (66.7%)" in out
    assert "1/3 boxes (33.3%)" in out
    assert "a1" in out and "b1" in out


def test_inventory_staleness_excludes_and_reports(env):
    _collect(env, {
        "a1": {"snapshot": _snapshot_json(COMMIT_A)},
        "a2": {"snapshot": _snapshot_json(COMMIT_A)},
    })
    estate, store = env
    proc = run_inventory("inventory", "--store", store,
                         "--staleness-hours", "0")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "no eligible boxes in the staleness window" in out
    assert "stale boxes: a1, a2" in out


def test_inventory_box_history_newest_first(env):
    estate, store = _collect(env, {
        "tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    _write_box(estate, "tower", snapshot=_snapshot_json(COMMIT_B))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    proc = run_inventory("inventory", "--store", store, "--box", "tower")
    assert proc.returncode == 0, proc.stderr
    assert "2 observations, newest first" in proc.stdout
    first = proc.stdout.index(COMMIT_B[:12])
    second = proc.stdout.index(COMMIT_A[:12])
    assert first < second


def test_inventory_unknown_box_is_an_error(env):
    _collect(env, {"tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    estate, store = env
    proc = run_inventory("inventory", "--store", store, "--box", "nope")
    assert proc.returncode == 2
    assert "no records" in proc.stderr


def test_inventory_without_snapshot_is_an_error(env):
    estate, store = env
    proc = run_inventory("inventory", "--store", store)
    assert proc.returncode == 2
    assert "run collect first" in proc.stderr


# --- drift ---------------------------------------------------------------


def test_drift_classifies_rows(env):
    _collect(env, {
        "good": {"snapshot": _snapshot_json(COMMIT_A)},
        "unexplained": {"snapshot": _snapshot_json(COMMIT_B)},
        "held": {"snapshot": _snapshot_json(COMMIT_B, frozen=True)},
        "deferred": {"snapshot": _snapshot_json(COMMIT_B, arc=True)},
        "sus": {"status": _status_json(),
                "audit": [_audit_line(NOW, "deploy", COMMIT_A, "c" * 40)],
                "snapshot": _snapshot_json(COMMIT_B)},
    })
    estate, store = env
    proc = run_inventory("drift", "--store", store, "--expected", COMMIT_A,
                         "--staleness-hours", "999")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    # "sus" reported COMMIT_B (its audit/snapshot mismatch resolved to the
    # snapshot) which differs from --expected=COMMIT_A, so it drifts with
    # the suspect classification: 4 of 5.
    assert "4 of 5 eligible boxes differ" in out
    assert "good" not in out.split("differ from expected")[1]
    assert "unexplained" in out
    assert "policy-held (frozen)" in out
    assert "deferred (active tenant arc)" in out
    assert "suspect report" in out


def test_drift_majority_fallback_is_labeled(env):
    _collect(env, {
        "a1": {"snapshot": _snapshot_json(COMMIT_A)},
        "a2": {"snapshot": _snapshot_json(COMMIT_A)},
        "b1": {"snapshot": _snapshot_json(COMMIT_B)},
    })
    estate, store = env
    proc = run_inventory("drift", "--store", store,
                         "--staleness-hours", "999")
    assert proc.returncode == 0, proc.stderr
    assert "fleet majority" in proc.stdout
    assert "b1" in proc.stdout  # only the minority box drifts


# --- rebuild -------------------------------------------------------------


def test_rebuild_recovers_snapshot_from_journal(env):
    estate, store = _collect(env, {
        "tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    os.remove(os.path.join(store, "snapshot.json"))
    proc = run_inventory("rebuild", "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert _snapshot(store)["boxes"]["tower"]["versions"][
        "repo_commit"] == COMMIT_A


def test_rebuild_skips_malformed_journal_lines(env):
    estate, store = _collect(env, {
        "tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    with open(os.path.join(store, "journal.jsonl"), "a") as fh:
        fh.write("{broken\n")
        fh.write('{"not": "a record"}\n')
    proc = run_inventory("rebuild", "--store", store)
    assert proc.returncode == 0, proc.stderr
    snap = _snapshot(store)
    assert snap["malformed_lines_skipped"] == 2
    assert set(snap["boxes"]) == {"tower"}


def test_large_record_round_trips_whole_line(env):
    """A record bigger than one stdio block buffer (8 KB) must land in the
    journal as one complete line, never a torn multi-write line: the append
    path uses line buffering so each record is a single O_APPEND write."""
    estate, store = env
    big = "x" * 20000  # comfortably over the old 8 KB block buffer
    status = _status_json()
    status["padding_to_exceed_stdio_buffer"] = big
    _write_box(estate, "tower", status=status)
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    with open(os.path.join(store, "journal.jsonl"), "r") as fh:
        raw_lines = [line for line in fh if line.strip()]
    assert len(raw_lines) == 1
    assert len(raw_lines[0]) > 8192
    record = json.loads(raw_lines[0])
    assert record["versions"]["toolset_pins"]["padding_to_exceed_stdio_buffer"] == big
    # Rebuild replays the journal; the record must survive byte-identical.
    proc = run_inventory("rebuild", "--store", store)
    assert proc.returncode == 0, proc.stderr
    with open(os.path.join(store, "journal.jsonl"), "r") as fh:
        raw_lines2 = [line for line in fh if line.strip()]
    assert raw_lines2 == raw_lines
    assert _snapshot(store)["boxes"]["tower"]["versions"]["toolset_pins"][
        "padding_to_exceed_stdio_buffer"] == big


# --- FOLLOW-fleet6 (QA N1): previously-empirical regression pins -------


def test_collect_corrupt_box_snapshot_is_noted_not_fatal(env):
    """A corrupt box-side snapshot.json must not sink the collect: the
    box records with null versions plus a loud unreadable note."""
    _collect(env, {
        "bad": {"raw_snapshot": "{not json",
                "status": _status_json()},
        "good": {"snapshot": _snapshot_json(COMMIT_A)},
    })
    estate, store = env
    records = {r["box_id"]: r for r in _journal(store)}
    assert set(records) == {"bad", "good"}
    assert records["bad"]["versions"]["repo_commit"] is None
    assert any("snapshot.json unreadable" in n
               for n in records["bad"]["notes"])
    assert records["good"]["versions"]["repo_commit"] == COMMIT_A


def test_collect_non_object_box_snapshot_is_ignored(env):
    """Valid JSON that is not an object (a list here) is not a snapshot:
    ignored with the exact "not an object" note, not a crash."""
    _collect(env, {
        "bad": {"snapshot": ["not", "an", "object"],
                "status": _status_json()},
    })
    estate, store = env
    record = _journal(store)[0]
    assert record["versions"]["repo_commit"] is None
    assert "snapshot.json is not an object; ignored" in record["notes"]


def test_store_snapshot_corrupt_or_wrong_schema_is_exit_2(env):
    """A torn or hand-edited store snapshot must fail the readers with
    exit 2 (bad input), never a traceback or a silently empty fleet."""
    _collect(env, {"tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    estate, store = env
    snapshot_path = os.path.join(store, "snapshot.json")

    with open(snapshot_path, "w") as fh:
        fh.write("{corrupt")
    proc = run_inventory("inventory", "--store", store)
    assert proc.returncode == 2
    assert "run collect first" in proc.stderr

    with open(snapshot_path, "w") as fh:
        json.dump({"schema": "not-a-fleet-snapshot", "boxes": {}}, fh)
    proc = run_inventory("inventory", "--store", store)
    assert proc.returncode == 2
    assert "not a fleet inventory snapshot" in proc.stderr


def _estate_checksum(estate):
    """Content checksum of every file under the estate: the pull-only
    proof hashes contents (not mtimes), in deterministic order."""
    digest = hashlib.sha256()
    for dirpath, _dirnames, filenames in os.walk(estate):
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, estate)
            digest.update(rel.encode("utf-8") + b"\x00")
            with open(path, "rb") as fh:
                digest.update(fh.read())
            digest.update(b"\x00")
    return digest.hexdigest()


def test_collect_is_pull_only_on_the_estate(env):
    """collect reads the estate but must never write to it (the S1
    pull-only contract): a full content checksum of the estate is
    identical before and after."""
    estate, store = env
    _write_box(estate, "tower", status=_status_json(),
               snapshot=_snapshot_json(COMMIT_A))
    _write_box(estate, "spark", status=_status_json(),
               audit=[_audit_line(NOW, "deploy", COMMIT_A, COMMIT_B)])
    mapping = os.path.join(estate, "ids.json")
    with open(mapping, "w") as fh:
        json.dump({"spark": "spark"}, fh)
    before = _estate_checksum(estate)
    proc = run_inventory("collect", "--estate", estate, "--store", store,
                         "--box-id-map", mapping)
    assert proc.returncode == 0, proc.stderr
    assert _estate_checksum(estate) == before


# --- box_snapshot.py -----------------------------------------------------


def test_box_snapshot_emits_git_head(env):
    estate, store = env
    repo = os.path.join(estate, "fakerepo")
    os.makedirs(repo)
    subprocess.run(["git", "init", "-q", repo], check=True)
    subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"],
                   check=True)
    subprocess.run(["git", "-C", repo, "config", "user.name", "t"],
                   check=True)
    with open(os.path.join(repo, "f"), "w") as fh:
        fh.write("x")
    subprocess.run(["git", "-C", repo, "add", "f"], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-qm", "x"], check=True)
    head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          stdout=subprocess.PIPE, text=True,
                          check=True).stdout.strip()
    proc = run_box_snapshot("--checkout", repo)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["repo_commit"] == head


def test_box_snapshot_bad_checkout_is_null_with_note(env):
    estate, store = env
    proc = run_box_snapshot("--checkout", os.path.join(estate, "nope"))
    assert proc.returncode == 0, proc.stderr  # never raises
    payload = json.loads(proc.stdout)
    assert payload["repo_commit"] is None
    assert payload["note"] is not None
    assert payload["image_version"] is None


def test_box_snapshot_out_file_and_frozen_flag(env):
    estate, store = env
    out = os.path.join(estate, "snapshot.json")
    proc = run_box_snapshot("--checkout", estate, "--out", out,
                            "--frozen", "frozen")
    assert proc.returncode == 0, proc.stderr
    payload = json.load(open(out))
    assert payload["gate"]["frozen"] is True


# --- QA round-1 blockers (regressions) -----------------------------------


def test_collect_non_string_box_id_skipped_not_poisoned(env):
    """A box_id map producing a non-string box_id must not brick the
    store: the box is skipped loudly and later collects still work."""
    estate, store = env
    _write_box(estate, "ghost", status=_status_json(),
               snapshot=_snapshot_json(COMMIT_A))
    _write_box(estate, "real", status=_status_json(),
               snapshot=_snapshot_json(COMMIT_A))
    mapping = os.path.join(estate, "ids.json")
    with open(mapping, "w") as fh:
        json.dump({"ghost": ["x"]}, fh)
    proc = run_inventory("collect", "--estate", estate, "--store", store,
                         "--box-id-map", mapping)
    assert proc.returncode == 0, proc.stderr
    assert "non-string box_id" in proc.stderr
    assert set(_snapshot(store)["boxes"]) == {"real"}
    # The journal has no poison line: rebuild and a second collect both
    # still work.
    assert run_inventory("rebuild", "--store", store).returncode == 0
    proc = run_inventory("collect", "--estate", estate, "--store", store,
                         "--box-id-map", mapping)
    assert proc.returncode == 0, proc.stderr


def test_rebuild_counts_non_string_box_id_as_malformed(env):
    estate, store = _collect(env, {
        "tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    with open(os.path.join(store, "journal.jsonl"), "a") as fh:
        fh.write(json.dumps({"box_id": ["poison"], "schema": "x"}) + "\n")
    proc = run_inventory("rebuild", "--store", store)
    assert proc.returncode == 0, proc.stderr
    snap = _snapshot(store)
    assert snap["malformed_lines_skipped"] == 1
    assert set(snap["boxes"]) == {"tower"}


def test_rebuild_counts_shape_broken_record_as_malformed(env):
    estate, store = _collect(env, {
        "tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    bad = {"schema": "fleet-inventory-record/1", "box_id": "tampered",
           "observed_at": NOW.isoformat(), "versions": "tampered",
           "last_tick_at": {}, "gate": {}}
    with open(os.path.join(store, "journal.jsonl"), "a") as fh:
        fh.write(json.dumps(bad) + "\n")
    proc = run_inventory("rebuild", "--store", store)
    assert proc.returncode == 0, proc.stderr
    snap = _snapshot(store)
    assert snap["malformed_lines_skipped"] == 1
    assert set(snap["boxes"]) == {"tower"}
    # And the broken record never reaches the readers.
    proc = run_inventory("inventory", "--store", store,
                         "--staleness-hours", "999")
    assert proc.returncode == 0, proc.stderr


def test_staleness_window_nan_inf_negative_rejected(env):
    _collect(env, {"tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    estate, store = env
    for sub, flag in (("inventory", "nan"), ("inventory", "-1"),
                      ("drift", "inf")):
        proc = run_inventory(sub, "--store", store,
                             "--staleness-hours", flag)
        assert proc.returncode == 2, (sub, flag, proc.stderr)
        assert "staleness-hours" in proc.stderr


def test_drift_majority_tie_is_labeled_honestly(env):
    _collect(env, {
        "a1": {"snapshot": _snapshot_json(COMMIT_A)},
        "b1": {"snapshot": _snapshot_json(COMMIT_B)},
    })
    estate, store = env
    proc = run_inventory("drift", "--store", store,
                         "--staleness-hours", "999")
    assert proc.returncode == 0, proc.stderr
    assert "tie for majority" in proc.stdout
    assert "fleet majority)" not in proc.stdout  # never claims a majority
    assert "a1" in proc.stdout  # the non-picked side drifts


def test_malformed_audit_lines_are_noted_not_silent(env):
    estate, store = env
    boxdir = os.path.join(estate, "tower")
    os.makedirs(boxdir)
    with open(os.path.join(boxdir, "audit-tail.jsonl"), "w") as fh:
        fh.write(json.dumps(_audit_line(NOW, "deploy", COMMIT_A, COMMIT_A))
                 + "\n")
        fh.write("{corrupt\n")
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    record = _journal(store)[0]
    assert any("malformed line" in n for n in record["notes"])
    # The good deploy event still counts as the tick.
    assert record["last_tick_at"]["deploy"] is not None


# --- Architecture round-1 blockers (regressions) -------------------------


def test_record_schema_matches_design_section_4(env):
    """The S1 record must use the design's section-4 field names
    (toolset_pins, arc, gate.permitted_*, last_tick_at.image) — the
    append-only journal makes renames permanent, so they must be right
    before the first production record exists."""
    _collect(env, {"tower": {"status": _status_json(),
                            "snapshot": _snapshot_json(COMMIT_A)}})
    estate, store = env
    record = _journal(store)[0]
    assert set(record["versions"]) == {"repo_commit", "toolset_pins",
                                      "image_version"}
    assert set(record["last_tick_at"]) == {"deploy", "toolset", "image"}
    assert set(record["gate"]) == {"permitted_commit",
                                   "permitted_toolset_pin", "frozen",
                                   "answer_age_s", "generated_at"}
    assert record["gate"]["permitted_commit"] is None  # S1: G15's slice
    assert record["gate"]["permitted_toolset_pin"] is None
    assert "arc" in record and "arc_active" not in record
    # D-SC-1/D-SC-2 (#1660): the box's own emission timestamps ride the
    # record so readers can interpret the box-local signals honestly.
    assert "emitted_at" in record
    assert "generated_at" in record["gate"]


# --- D-SC-1/D-SC-2: box emission timestamps on the record (#1660) --------


def test_collect_carries_gate_generated_at_and_emitted_at(env):
    """End-to-end through the real box_snapshot.py: the record carries
    gate.generated_at (the hook's timestamp) plus the snapshot's
    emitted_at (box clock); observed_at stays the collector's receive
    time, so transport delay is computable."""
    estate, store = env
    gen = datetime.now(timezone.utc) - timedelta(seconds=60)
    gate_file = _gate_status_file(estate, state="live", generated_at=gen)
    snap = _snapshot_gate(["--checkout", estate, "--gate-status", gate_file])
    assert snap["gate"]["generated_at"] is not None  # box_snapshot half
    _write_box(estate, "tower", status=_status_json(), snapshot=snap)
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    record = _journal(store)[0]
    assert record["gate"]["generated_at"] == snap["gate"]["generated_at"]
    parsed = datetime.fromisoformat(record["gate"]["generated_at"])
    assert parsed.tzinfo is not None  # aware UTC: age recomputable
    assert record["emitted_at"] == snap["emitted_at"]
    observed = datetime.fromisoformat(record["observed_at"])
    emitted = datetime.fromisoformat(record["emitted_at"])
    assert observed >= emitted  # collector received after the box emitted
    assert not any("emitted_at" in n for n in record["notes"])


def test_collect_nulls_when_snapshot_lacks_timestamps(env):
    """Pre-#1660 snapshots carry neither field: the record holds nulls,
    not crashes, and no skew note fires on a missing emitted_at."""
    snap = _snapshot_json(COMMIT_A)  # gate has no generated_at key
    del snap["emitted_at"]
    _collect(env, {"tower": {"status": _status_json(), "snapshot": snap}})
    estate, store = env
    record = _journal(store)[0]
    assert record["gate"]["generated_at"] is None
    assert record["emitted_at"] is None
    assert not any("emitted_at" in n for n in record["notes"])


def test_collect_future_emitted_at_flagged_not_dropped(env):
    """A snapshot emitted_at beyond FUTURE_SKEW_TOLERANCE_S is clock
    skew, not an error: flagged in notes, kept as-is (D-SC-1)."""
    future = (datetime.now(timezone.utc)
              + timedelta(seconds=400)).isoformat()
    snap = _snapshot_json(COMMIT_A)
    snap["emitted_at"] = future
    _collect(env, {"tower": {"status": _status_json(), "snapshot": snap}})
    estate, store = env
    record = _journal(store)[0]
    assert record["emitted_at"] == future
    assert any("emitted_at is" in n and "in the future" in n
               for n in record["notes"]), record["notes"]


def test_collect_unparseable_emitted_at_noted_kept(env):
    """An unparseable emitted_at is said loudly and kept verbatim —
    the module never invents a timestamp (mirrors the status.json
    generated_at convention)."""
    snap = _snapshot_json(COMMIT_A)
    snap["emitted_at"] = "not-a-timestamp"
    _collect(env, {"tower": {"status": _status_json(), "snapshot": snap}})
    estate, store = env
    record = _journal(store)[0]
    assert record["emitted_at"] == "not-a-timestamp"
    assert any("no parseable emitted_at" in n
               for n in record["notes"]), record["notes"]


def test_doc_note_pins_answer_age_s_emit_time_convention():
    """The design note readers need: answer_age_s is the emit-time
    convenience; the true gate age is recomputed from generated_at."""
    with open(INVENTORY, encoding="utf-8") as fh:
        src = fh.read()
    assert "max(0, now - gate.generated_at)" in src
    assert "never from answer_age_s" in src


# --- #1632: per-box gate staleness on the fleet table -------------------


def test_inventory_table_renders_gate_age_column(env):
    """The fleet table's gate_age column (#1632, S1b slice): recomputed
    from gate.generated_at; a trailing `~` marks the emit-time
    answer_age_s fallback; n/a when uncomputable."""
    gen = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()

    def _snap(gate):
        return {"repo_commit": COMMIT_A, "gate": gate, "arc_active": None,
                "image_version": None, "note": None,
                "emitted_at": NOW.isoformat()}

    _collect(env, {
        "box-age": {"status": _status_json(),
                    "snapshot": _snap({"frozen": False, "answer_age_s": 5,
                                       "generated_at": gen})},
        "box-fallback": {"status": _status_json(),
                         "snapshot": _snap({"frozen": False,
                                            "answer_age_s": 42,
                                            "generated_at": None})},
        "box-none": {"status": _status_json(),
                     "snapshot": _snap({"frozen": None,
                                        "answer_age_s": None,
                                        "generated_at": None})},
    })
    estate, store = env
    proc = run_inventory("inventory", "--store", store,
                         "--staleness-hours", "24")
    assert proc.returncode == 0, proc.stderr
    rows = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"(\S+)\s+(\(no report\)|\S+)\s+(\S+)\s+"
                     r"(\S+)\s+(\S+)\s+(.*)$", line)
        if m and m.group(1).startswith("box-"):
            rows[m.group(1)] = m.groups()
    assert set(rows) == {"box-age", "box-fallback", "box-none"}, rows
    age = rows["box-age"][4]
    assert re.fullmatch(r"\d+s", age), age  # recomputed, no ~ marker
    assert 35 <= int(age[:-1]) <= 60, age
    assert rows["box-fallback"][4] == "42s~", rows["box-fallback"]
    assert rows["box-none"][4] == "n/a", rows["box-none"]
    # Product review B1: the `~` sigil's legend ships at the point of use.
    legend = "~ = gate age is the box's emit-time answer_age_s"
    assert any(legend in l for l in proc.stdout.splitlines()), \
        proc.stdout


def test_inventory_table_no_legend_without_emit_time_fallback(env):
    """The legend only prints when a row actually used the fallback —
    a table of fresh recomputations stays clean."""
    gen = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()
    snap = {"repo_commit": COMMIT_A,
            "gate": {"frozen": False, "answer_age_s": 5,
                     "generated_at": gen},
            "arc_active": None, "image_version": None,
            "note": None, "emitted_at": NOW.isoformat()}
    _collect(env, {"tower": {"status": _status_json(), "snapshot": snap}})
    estate, store = env
    proc = run_inventory("inventory", "--store", store,
                         "--staleness-hours", "24")
    assert proc.returncode == 0, proc.stderr
    assert not any(l.startswith("~ =") for l in proc.stdout.splitlines()), \
        proc.stdout


def test_inventory_table_gate_age_header_present(env):
    """The gate_age header is part of the table contract (the conformance
    test in test_api.py pins the column count)."""
    _collect(env, {"tower": {"status": _status_json(),
                             "snapshot": _snapshot_json(COMMIT_A)}})
    estate, store = env
    proc = run_inventory("inventory", "--store", store)
    assert proc.returncode == 0, proc.stderr
    header = next(l for l in proc.stdout.splitlines()
                  if l.startswith("box "))
    assert "gate_age" in header.split(), header


def test_check_event_does_not_shadow_deploy_claim(env):
    """False-negative case: a frequent `check` (no `to`) must not hide
    the older successful deploy's claim from the suspect cross-check."""
    earlier = NOW - timedelta(minutes=10)
    _collect(env, {"tower": {
        "audit": [_audit_line(earlier, "deploy", COMMIT_A, COMMIT_B),
                  _audit_line(NOW, "check", None, None, result="noop")],
        "snapshot": _snapshot_json(COMMIT_A),
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["versions"]["repo_commit"] == COMMIT_A
    assert record["suspect"] is True  # event said deployed B, box says A
    assert COMMIT_B in record["suspect_reason"]
    # Liveness still comes from the newest tick (the check).
    assert record["last_tick_at"]["deploy"] == NOW.isoformat()


def test_failed_deploy_claim_does_not_flag_suspect(env):
    """False-positive case: a failed deploy's `to` is an attempt, not a
    state claim — the honest box still on the old commit is not suspect."""
    _collect(env, {"tower": {
        "audit": [_audit_line(NOW, "deploy", COMMIT_A, COMMIT_B,
                              result="deploy-fail")],
        "snapshot": _snapshot_json(COMMIT_A),
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["suspect"] is False
    assert record["last_tick_at"]["deploy"] == NOW.isoformat()


def test_failed_claim_without_snapshot_leaves_unknown(env):
    """No snapshot + only a failed deploy claim: repo_commit is unknown,
    said loudly — never inferred from the failed attempt's `to`."""
    _collect(env, {"tower": {
        "audit": [_audit_line(NOW, "deploy", COMMIT_A, COMMIT_B,
                              result="deploy-fail")],
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["versions"]["repo_commit"] is None
    assert any("failed" in n and "unknown" in n for n in record["notes"])


def test_epoch_generated_at_parsed(env):
    """The real self_update.py emits an epoch int, not an ISO string —
    the toolset tick must land, not null out with a spurious note."""
    epoch = int(NOW.timestamp())
    status = _status_json()
    status["generated_at"] = epoch
    _collect(env, {"tower": {"status": status,
                            "snapshot": _snapshot_json(COMMIT_A)}})
    estate, store = env
    record = _journal(store)[0]
    tick = record["last_tick_at"]["toolset"]
    assert tick is not None
    assert abs(datetime.fromisoformat(tick).timestamp() - epoch) < 2
    assert not any("no parseable generated_at" in n
                   for n in record["notes"])


def test_real_self_update_status_shape_contract(env):
    """Contract test against the real producer: run the repo's own
    `scripts/self_update.py status --json` and collect it. Guards the
    silent-rot coupling — if the producer's shape drifts, this fails."""
    estate, store = env
    proc = subprocess.run(
        [sys.executable,
         os.path.join(FLEET, os.pardir, "scripts", "self_update.py"),
         "status", "--json"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        timeout=60)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert "generated_at" in payload and "tools" in payload
    boxdir = os.path.join(estate, "realbox")
    os.makedirs(boxdir)
    with open(os.path.join(boxdir, "status.json"), "w") as fh:
        fh.write(proc.stdout)
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    record = _journal(store)[0]
    assert record["versions"]["toolset_pins"] is not None
    assert record["last_tick_at"]["toolset"] is not None


def test_real_audit_log_shape_contract(env):
    """Contract test against the real `deploy/auto-deploy.sh` audit()
    field names: extract the function, emit one deploy line the way the
    script does, and verify the collector's claim logic reads it."""
    import re as _re
    root = os.path.abspath(os.path.join(FLEET, os.pardir))
    text = open(os.path.join(root, "deploy", "auto-deploy.sh"),
                encoding="utf-8").read()
    m = _re.search(r"^audit\(\) \{(.*?)^\}$", text, _re.M | _re.S)
    assert m, "audit() not found in auto-deploy.sh"
    estate, store = env
    funcfile = os.path.join(estate, "audit_fn.sh")
    open(funcfile, "w").write(m.group(0) + "\n")
    audit_log = os.path.join(estate, "audit.log")
    cmd = ("AUDIT_LOG=%r; source %r; "
           "audit deploy ',\"result\":\"ok\",\"from\":\"%s\",\"to\":\"%s\","
           "\"component\":\"spark-vm\",\"phase\":\"deploy\"'"
           % (audit_log, funcfile, COMMIT_A, COMMIT_B))
    proc = subprocess.run(["bash", "-c", cmd],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True)
    assert proc.returncode == 0, proc.stderr
    line = open(audit_log).read().strip()
    row = json.loads(line)
    assert row["event"] == "deploy" and row["result"] == "ok"
    assert row["to"] == COMMIT_B and row["from"] == COMMIT_A
    boxdir = os.path.join(estate, "realbox")
    os.makedirs(boxdir)
    open(os.path.join(boxdir, "audit-tail.jsonl"), "w").write(line + "\n")
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    record = _journal(store)[0]
    # Successful claim, no snapshot: audit fallback fires.
    assert record["versions"]["repo_commit"] == COMMIT_B
    assert record["last_tick_at"]["deploy"] is not None


def test_drift_expected_accepts_table_prefix(env):
    """The inventory table shows 12-char prefixes; copying one into
    `drift --expected` must match the box on it, not report false drift."""
    _collect(env, {
        "a1": {"snapshot": _snapshot_json(COMMIT_A)},
        "b1": {"snapshot": _snapshot_json(COMMIT_B)},
    })
    estate, store = env
    proc = run_inventory("drift", "--store", store,
                         "--expected", COMMIT_A[:12],
                         "--staleness-hours", "999")
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "1 of 2 eligible boxes differ" in out
    assert "a1" not in out.split("differ from expected")[1]
    assert "b1" in out


def test_failed_newer_claim_does_not_shadow_older_success(env):
    """A failed newer deploy attempt must not shadow the older successful
    claim in the suspect cross-check: [ok->B, fail->C], snapshot A is a
    genuine section-7 inconsistency (B claimed, A reported)."""
    earlier = NOW - timedelta(minutes=10)
    _collect(env, {"tower": {
        "audit": [_audit_line(earlier, "deploy", COMMIT_A, COMMIT_B),
                  _audit_line(NOW, "deploy", COMMIT_B, "c" * 40,
                              result="deploy-fail")],
        "snapshot": _snapshot_json(COMMIT_A),
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["suspect"] is True
    assert COMMIT_B in record["suspect_reason"]
    assert any("failed" in n and "successful claim" in n
               for n in record["notes"])


def test_failed_newer_claim_falls_back_to_older_success(env):
    """No snapshot: the audit fallback uses the newest *successful* claim
    even when a newer attempt failed — the failed `to` is never inferred."""
    earlier = NOW - timedelta(minutes=10)
    _collect(env, {"tower": {
        "audit": [_audit_line(earlier, "deploy", COMMIT_A, COMMIT_B),
                  _audit_line(NOW, "deploy", COMMIT_B, "c" * 40,
                              result="deploy-fail")],
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["versions"]["repo_commit"] == COMMIT_B
    assert record["suspect"] is False
    assert any("successful claim" in n for n in record["notes"])


def test_manual_rollback_claim_counts_as_successful(env):
    """A manual-rollback's `to` is the operator-restored commit — a real
    state claim, so it feeds the cross-check like ok/rolled-back."""
    _collect(env, {"tower": {
        "audit": [{"ts": NOW.isoformat(), "event": "rollback",
                   "result": "manual-rollback", "to": COMMIT_B,
                   "rolled_back_from": COMMIT_A}],
        "snapshot": _snapshot_json(COMMIT_A),
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["suspect"] is True
    assert COMMIT_B in record["suspect_reason"]


def test_pull_only_claim_counts_as_state(env):
    """A `pull-only` deploy advanced the watermark to `to` with nothing
    to install (e.g. docs-only release): the box is genuinely at `to`,
    so a matching snapshot is not suspect."""
    earlier = NOW - timedelta(minutes=10)
    _collect(env, {"tower": {
        "audit": [_audit_line(earlier, "deploy", COMMIT_A, COMMIT_B),
                  _audit_line(NOW, "deploy", COMMIT_B, "c" * 40,
                              result="pull-only")],
        "snapshot": _snapshot_json("c" * 40),
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["suspect"] is False
    assert record["versions"]["repo_commit"] == "c" * 40


def test_rollback_unhealthy_claim_counts_as_state(env):
    """A `rollback-unhealthy` restore landed and rewound the watermark to
    `to` (health degraded separately): the box is genuinely at `to`, so
    a matching snapshot is not suspect."""
    earlier = NOW - timedelta(minutes=10)
    _collect(env, {"tower": {
        "audit": [_audit_line(earlier, "deploy", COMMIT_A, COMMIT_B),
                  {"ts": NOW.isoformat(), "event": "rollback",
                   "result": "rollback-unhealthy", "to": COMMIT_A,
                   "rolled_back_from": COMMIT_B}],
        "snapshot": _snapshot_json(COMMIT_A),
    }})
    estate, store = env
    record = _journal(store)[0]
    assert record["suspect"] is False
    assert record["versions"]["repo_commit"] == COMMIT_A


# --- issue #716: concurrent rebuilds must not share the snapshot tmp ---


def test_concurrent_rebuilds_all_succeed(env):
    """Issue #716: overlapping rebuilds on one store must all succeed.

    With the old shared `snapshot.json.tmp` name, overlapping collects
    raced: one collect's os.replace() pulled the tmp path out from under
    another collect's still-open write, failing it with "cannot write
    snapshot" (~18% of rebuilds with 16 concurrent publishers on this
    box). Every rebuild now publishes through a process-unique tmp path,
    so 16 concurrent rebuilds all exit 0 and the final snapshot is valid.
    """
    estate, store = _collect(
        env, {"tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    procs = [subprocess.Popen(
        [sys.executable, INVENTORY, "rebuild", "--store", store],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(16)]
    for proc in procs:
        _out, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, \
            "concurrent rebuild failed: %s" % err.strip()
    snap = _snapshot(store)
    assert set(snap["boxes"]) == {"tower"}
    assert snap["boxes"]["tower"]["versions"]["repo_commit"] == COMMIT_A
    # Successful publishes consume their tmp via os.replace(): no
    # `snapshot.json.tmp*` files may be left behind.
    leftovers = [n for n in os.listdir(store)
                 if n.startswith("snapshot.json.tmp")]
    assert leftovers == []


def test_rebuild_sweeps_only_stale_snapshot_tmps(env):
    """Issue #716: crash-orphaned snapshot tmps are swept, live ones kept.

    Per-rebuild unique tmp paths mean a crash between the tmp write and
    os.replace() leaves a stale `snapshot.json.tmp.*` file instead of a
    torn snapshot. Rebuilds sweep tmp files older than one hour; a young
    tmp — a live writer's — is never touched.
    """
    estate, store = _collect(
        env, {"tower": {"snapshot": _snapshot_json(COMMIT_A)}})
    stale = os.path.join(store, "snapshot.json.tmp.424242.12345")
    fresh = os.path.join(store, "snapshot.json.tmp.31337.999")
    legacy = os.path.join(store, "snapshot.json.tmp")
    for path in (stale, fresh, legacy):
        with open(path, "w") as fh:
            fh.write("{}\n")
    old = time.time() - 7200  # 2h: past the 1h sweep gate
    os.utime(stale, (old, old))
    os.utime(legacy, (old, old))
    proc = run_inventory("rebuild", "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert not os.path.exists(stale)
    assert not os.path.exists(legacy)  # pre-#716 shared-name orphan
    assert os.path.exists(fresh)  # young: a live writer's tmp, untouched
    assert _snapshot(store)["boxes"]["tower"]["versions"][
        "repo_commit"] == COMMIT_A


# --- FOLLOW-fleet1..4 (carried review notes from PR #715) ------------------


def _import_fleet_module(name):
    if FLEET not in sys.path:
        sys.path.insert(0, FLEET)
    return __import__(name)


def test_box_sort_key_total_order_on_mixed_types():
    """FOLLOW-fleet1: the snapshot sort key is total-order on any key type
    (no TypeError), so a hand-poisoned snapshot can never crash the table
    with a bare traceback. JSON keys are always strings, so this pins the
    helper's contract rather than a reachable store state."""
    inventory = _import_fleet_module("inventory")
    items = list({1: "a", None: "b", "z": "c", (2, 3): "d"}.items())
    with pytest.raises(TypeError):
        sorted(items)  # the old key-less sort: not total-order
    ordered = sorted(items, key=inventory._box_sort_key)
    # str() coercion order: "(2, 3)" < "1" < "None" < "z"
    assert [value for _, value in ordered] == ["d", "a", "b", "c"]


def test_unexpected_inventory_failure_exits_2_not_traceback(monkeypatch,
                                                            capsys):
    """FOLLOW-fleet1 (exit-1 half): an unexpected internal failure in the
    render path reports exit 2 with a one-line message, never a bare
    traceback."""
    inventory = _import_fleet_module("inventory")

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(inventory, "cmd_inventory", _boom)
    rc = inventory.main(["inventory", "--store", "/nonexistent-store"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "boom" in captured.err
    assert "Traceback" not in captured.err


def test_box_snapshot_git_failure_note_has_no_list_repr(monkeypatch):
    """FOLLOW-fleet2: empty git stderr reports the exit code as plain
    text ("exit 128"), not the list repr "['exit 128']"; non-empty
    stderr still reports the first line."""
    box_snapshot = _import_fleet_module("box_snapshot")

    class _Silent:
        returncode = 128
        stdout = ""
        stderr = ""

    class _Loud:
        returncode = 128
        stdout = ""
        stderr = "fatal: not a git repository\nsecond line\n"

    monkeypatch.setattr(box_snapshot.subprocess, "run",
                        lambda *a, **k: _Silent())
    commit, note = box_snapshot._git_head("/tmp")
    assert commit is None
    assert note == "git rev-parse failed: exit 128", note

    monkeypatch.setattr(box_snapshot.subprocess, "run",
                        lambda *a, **k: _Loud())
    commit, note = box_snapshot._git_head("/tmp")
    assert note == "git rev-parse failed: fatal: not a git repository", note


def test_collect_message_pluralization_and_run_count(env):
    """FOLLOW-fleet3: the collect message pluralizes ("1 box" / "2 boxes")
    and reports this run's appended count separately from the total
    journal lines replayed."""
    estate, store = env
    _write_box(estate, "tower", status=_status_json(),
               snapshot=_snapshot_json(COMMIT_A))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "collected 1 box into" in proc.stdout, proc.stdout
    assert "1 appended this run" in proc.stdout, proc.stdout
    assert "1 journal lines replayed" in proc.stdout, proc.stdout

    _write_box(estate, "spare", status=_status_json(),
               snapshot=_snapshot_json(COMMIT_B))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "collected 2 boxes into" in proc.stdout, proc.stdout
    assert "2 appended this run" in proc.stdout, proc.stdout
    assert "3 journal lines replayed" in proc.stdout, proc.stdout


def test_inventory_long_box_id_keeps_columns_aligned(env):
    """FOLLOW-fleet4: a box id longer than the old fixed 24-char column
    must not push the other columns out of alignment (inventory and
    drift alike)."""
    long_id = "a-much-longer-box-name-that-exceeds-twenty-four-chars"
    assert len(long_id) > 24
    estate, store = _collect(env, {
        "tower": {"status": _status_json(),
                  "snapshot": _snapshot_json(COMMIT_A)},
        long_id: {"status": _status_json(),
                  "snapshot": _snapshot_json(COMMIT_B)},
    })
    proc = run_inventory("inventory", "--store", store)
    assert proc.returncode == 0, proc.stderr
    row_by_box = {}
    for line in proc.stdout.splitlines():
        if line.startswith("tower"):
            row_by_box["tower"] = line
        elif line.startswith(long_id):
            row_by_box[long_id] = line
    assert set(row_by_box) == {"tower", long_id}, proc.stdout
    assert (row_by_box["tower"].index(COMMIT_A[:12])
            == row_by_box[long_id].index(COMMIT_B[:12]))

    # Both boxes drift when the expected commit is one neither has: the
    # reason column must start at the same offset in both rows (a single
    # drift row would trivially satisfy any offset assertion, so the
    # two-row form is what pins the fix).
    drift = run_inventory("drift", "--store", store, "--expected", COMMIT_C)
    assert drift.returncode == 0, drift.stderr
    drows = [line for line in drift.stdout.splitlines()
             if line.startswith("  tower") or line.startswith("  " + long_id)]
    assert len(drows) == 2, drift.stdout
    offsets = {line.index("unexplained") for line in drows}
    assert len(offsets) == 1, drift.stdout


# --- audit-tail continuity (arch 20261004-1359) ----------------------------


def _watermarks(store):
    with open(os.path.join(store, "tail_watermarks.json")) as fh:
        return json.load(fh)


def _tail_lines(n, start=0):
    # Timestamps depend only on the line index, so _tail_lines(8)
    # extends _tail_lines(5) with byte-identical shared lines (the
    # overlap the continuity check looks for), while start=100 yields a
    # disjoint tail (the overflow simulation).
    base = NOW - timedelta(hours=1)
    return [_audit_line(base + timedelta(minutes=i), "deploy", COMMIT_A,
                       COMMIT_B, result="ok")
            for i in range(start, start + n)]


def test_tail_continuity_first_pull_establishes_silently(env):
    _collect(env, {"tower": {"status": _status_json(),
                             "audit": _tail_lines(5),
                             "snapshot": _snapshot_json(COMMIT_A)}})
    estate, store = env
    marks = _watermarks(store)
    assert set(marks) == {"tower"}
    with open(os.path.join(estate, "tower", "audit-tail.jsonl")) as fh:
        last = [line.strip() for line in fh if line.strip()][-1]
    assert marks["tower"]["tail_head_sha256"] == \
        hashlib.sha256(last.encode()).hexdigest()
    assert marks["tower"]["tail_lines"] == 5
    assert marks["tower"]["last_discontinuity_at"] is None


def test_tail_continuity_overlap_no_warning(env):
    estate, store = _collect(env, {"tower": {
        "status": _status_json(), "audit": _tail_lines(5),
        "snapshot": _snapshot_json(COMMIT_A)}})
    # Append lines (the operator's pull pattern: the tail grows); the
    # previous head is still inside the new tail -> windows overlap.
    _write_box(estate, "tower", audit=_tail_lines(8))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "discontinuity" not in proc.stderr
    marks = _watermarks(store)
    assert marks["tower"]["tail_lines"] == 8
    assert marks["tower"]["last_discontinuity_at"] is None


def test_tail_continuity_overflow_warns(env):
    estate, store = _collect(env, {"tower": {
        "status": _status_json(), "audit": _tail_lines(5),
        "snapshot": _snapshot_json(COMMIT_A)}})
    # Simulate overflow: the whole tail is replaced by lines the
    # previous pull never saw (more emitted between pulls than the tail
    # holds). The previous head is gone -> loud warning, collect still
    # succeeds, watermark re-establishes on the new tail.
    _write_box(estate, "tower",
               audit=_tail_lines(5, start=100))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "audit-tail discontinuity" in proc.stderr, proc.stderr
    assert "tower" in proc.stderr
    marks = _watermarks(store)
    assert marks["tower"]["tail_lines"] == 5
    assert marks["tower"]["last_discontinuity_at"] is not None
    # A third collect on the same tail is quiet again (the watermark
    # re-established; no repeated warning for one break).
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "discontinuity" not in proc.stderr


def test_tail_continuity_missing_tail_keeps_watermark(env):
    estate, store = _collect(env, {"tower": {
        "status": _status_json(), "audit": _tail_lines(5),
        "snapshot": _snapshot_json(COMMIT_A)}})
    before = _watermarks(store)
    os.unlink(os.path.join(estate, "tower", "audit-tail.jsonl"))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "discontinuity" not in proc.stderr
    assert _watermarks(store) == before


def test_tail_continuity_empty_tail_first_pull(env):
    _collect(env, {"tower": {"status": _status_json(), "audit": [],
                             "snapshot": _snapshot_json(COMMIT_A)}})
    _, store = env
    assert _watermarks(store) == {}


def test_tail_continuity_corrupt_watermark_reestablishes(env):
    estate, store = _collect(env, {"tower": {
        "status": _status_json(), "audit": _tail_lines(5),
        "snapshot": _snapshot_json(COMMIT_A)}})
    with open(os.path.join(store, "tail_watermarks.json"), "w") as fh:
        fh.write("not json {{{")
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "corrupt" in proc.stderr, proc.stderr
    marks = _watermarks(store)  # valid again
    assert set(marks) == {"tower"}


# --- audit-tail discontinuity, fifth S1 alert rule (#1006) ----------------


def _alerts(store):
    path = os.path.join(store, "alerts.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _expected_tail_discontinuity_id(box_id, prev_head):
    # Mirrors events._alert's id derivation: uuid5 over
    # rule|box_id|subcomponent|to|dedup_key, with subcomponent and to
    # empty for this rule.
    alert_ns = uuid.uuid5(
        uuid.NAMESPACE_URL,
        "https://github.com/ntindle/spark-vm/fleet/alerts")
    return str(uuid.uuid5(
        alert_ns, "tail-discontinuity|%s|||%s" % (box_id, prev_head)))


def test_tail_discontinuity_fires_page_class_alert(env):
    # #1006 remaining slice: the discontinuity promotes to a fifth S1
    # alert rule — the durable paging path (alerts.jsonl + watch), not
    # just the stderr warning.
    estate, store = _collect(env, {"tower": {
        "status": _status_json(), "audit": _tail_lines(5),
        "snapshot": _snapshot_json(COMMIT_A)}})
    assert _alerts(store) == []
    prev_head = _watermarks(store)["tower"]["tail_head_sha256"]
    # Simulate overflow: the whole tail is replaced by lines the
    # previous pull never saw.
    _write_box(estate, "tower", audit=_tail_lines(5, start=100))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "audit-tail discontinuity" in proc.stderr
    assert "1 tail-discontinuity alert(s) fired" in proc.stdout, proc.stdout
    rows = _alerts(store)
    assert len(rows) == 1, rows
    alert = rows[0]
    assert alert["schema"] == "fleet-alert/1"
    assert alert["rule"] == "tail-discontinuity"
    assert alert["box_id"] == "tower"
    assert alert["acked"] is False
    assert "discontinuity" in alert["detail"]
    assert "tower" in alert["detail"]
    # The dedup key is the lost window's head hash: one alert per
    # distinct lost window.
    assert alert["alert_id"] == _expected_tail_discontinuity_id(
        "tower", prev_head)
    # The paging path sees it: `events watch` exits 1 while the alert
    # is unacknowledged.
    watch = run_inventory("events", "watch", "--store", store)
    assert watch.returncode == 1, watch.stdout
    assert "tail-discontinuity" in watch.stdout


def test_tail_discontinuity_dedups_on_recollect(env):
    # Re-collection after a discontinuity never re-fires: the mark
    # already advanced, so the same lost window cannot page twice.
    estate, store = _collect(env, {"tower": {
        "status": _status_json(), "audit": _tail_lines(5),
        "snapshot": _snapshot_json(COMMIT_A)}})
    _write_box(estate, "tower", audit=_tail_lines(5, start=100))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert len(_alerts(store)) == 1
    # A third collect on the same tail is quiet again: no new warning,
    # no new alert row.
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "discontinuity" not in proc.stderr
    assert "tail-discontinuity alert(s) fired" not in proc.stdout
    assert len(_alerts(store)) == 1


def test_tail_discontinuity_second_break_refires(env):
    # A genuinely new overflow (a new lost window) fires a new alert —
    # each row is distinct evidence, deduped on the lost head hash.
    estate, store = _collect(env, {"tower": {
        "status": _status_json(), "audit": _tail_lines(5),
        "snapshot": _snapshot_json(COMMIT_A)}})
    _write_box(estate, "tower", audit=_tail_lines(5, start=100))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert len(_alerts(store)) == 1
    # A second, disjoint overflow: the re-established head is gone again.
    _write_box(estate, "tower", audit=_tail_lines(5, start=200))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "audit-tail discontinuity" in proc.stderr
    rows = _alerts(store)
    assert len(rows) == 2, rows
    assert rows[0]["alert_id"] != rows[1]["alert_id"]
    assert {r["rule"] for r in rows} == {"tail-discontinuity"}
    assert {r["box_id"] for r in rows} == {"tower"}


# --- tail-discontinuity test hardening (#1073, QA follow-ups to #1006) --


def test_tail_discontinuity_multi_box_fires_once(env):
    # #1073.1: one box discontinuous in a multi-box estate fires exactly
    # one alert, and the other box's watermark is left untouched — the
    # per-box marks are independent.
    estate, store = _collect(env, {
        "tower": {"status": _status_json(), "audit": _tail_lines(5),
                  "snapshot": _snapshot_json(COMMIT_A)},
        "desk": {"status": _status_json(), "audit": _tail_lines(5),
                 "snapshot": _snapshot_json(COMMIT_A)}})
    assert _alerts(store) == []
    desk_mark = _watermarks(store)["desk"]
    # Only tower overflows; desk's tail keeps overlapping.
    _write_box(estate, "tower", audit=_tail_lines(5, start=100))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "tower" in proc.stderr and "discontinuity" in proc.stderr
    rows = _alerts(store)
    assert len(rows) == 1, rows
    assert rows[0]["rule"] == "tail-discontinuity"
    assert rows[0]["box_id"] == "tower"
    # The other box's watermark keeps its head hash/lines (observed_at
    # advances on every pull by design — the continuity evidence is the
    # head hash, not the pull timestamp).
    after = _watermarks(store)["desk"]
    for key in ("tail_head_sha256", "tail_lines", "last_discontinuity_at"):
        assert after[key] == desk_mark[key], (key, after, desk_mark)


def test_same_collect_dual_fire_event_rule_and_discontinuity(env):
    # #1073.2: one collect where evaluate_alerts fires an event-journal
    # rule (rule 1, rollback-failed) AND check_tail_continuity fires a
    # discontinuity journals both alerts — each append runs under the
    # shared store journal lock, so the two writes never clobber each
    # other.
    estate, store = _collect(env, {"tower": {
        "status": _status_json(), "audit": _tail_lines(5),
        "snapshot": _snapshot_json(COMMIT_A)}})
    assert _alerts(store) == []
    failed = _audit_line(NOW - timedelta(minutes=55), "rollback",
                         COMMIT_A, COMMIT_B, result="rollback-failed")
    _write_box(estate, "tower",
               audit=_tail_lines(5, start=100) + [failed])
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    rows = _alerts(store)
    assert len(rows) == 2, rows
    by_rule = {r["rule"]: r for r in rows}
    assert set(by_rule) == {"rollback-failed", "tail-discontinuity"}
    assert by_rule["rollback-failed"]["box_id"] == "tower"
    assert by_rule["tail-discontinuity"]["box_id"] == "tower"
    assert by_rule["rollback-failed"]["alert_id"] != \
        by_rule["tail-discontinuity"]["alert_id"]
    assert all(r["acked"] is False for r in rows)


def test_tail_discontinuity_ack_lifecycle_new_alert_id(env):
    # #1073.3: ack a tail-discontinuity alert, then trigger a genuinely
    # new discontinuity — a new alert fires with a new alert_id. The
    # dedup key is the lost window's head hash, ack-independent, so the
    # ack never suppresses fresh evidence (rule 4's ack-gate does not
    # apply to rule 5).
    estate, store = _collect(env, {"tower": {
        "status": _status_json(), "audit": _tail_lines(5),
        "snapshot": _snapshot_json(COMMIT_A)}})
    _write_box(estate, "tower", audit=_tail_lines(5, start=100))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    first = _alerts(store)
    assert len(first) == 1
    ack = run_inventory("events", "ack", "--store", store,
                        "--alert-id", first[0]["alert_id"])
    assert ack.returncode == 0, ack.stderr
    # A second, disjoint overflow after the ack.
    _write_box(estate, "tower", audit=_tail_lines(5, start=200))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    rows = _alerts(store)
    assert len(rows) == 2, rows
    assert rows[0]["alert_id"] != rows[1]["alert_id"]
    assert rows[0]["acked"] is True
    assert rows[1]["acked"] is False
    assert rows[1]["rule"] == "tail-discontinuity"


# ---------------------------------------------------------------------------
# box_snapshot.py --gate-status (S1b visibility loop, #1325)
# ---------------------------------------------------------------------------

def _gate_status_file(tmpdir, state="live", generated_at=None, raw=None):
    path = os.path.join(tmpdir, "gate-status.json")
    if raw is not None:
        with open(path, "w") as fh:
            fh.write(raw)
        return path
    payload = {
        "schema_version": 1,
        "generated_at": (generated_at or datetime.now(timezone.utc)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "source": "gate_hook",
        "answer": {"state": state, "reason": "test"},
    }
    with open(path, "w") as fh:
        json.dump(payload, fh)
    return path


def _snapshot_gate(argv):
    proc = run_box_snapshot(*argv)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_box_snapshot_gate_status_frozen(tmp_path):
    gate = _gate_status_file(str(tmp_path), state="frozen")
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", gate])
    assert snap["gate"]["frozen"] is True
    assert isinstance(snap["gate"]["answer_age_s"], int)
    assert snap["gate"]["answer_age_s"] >= 0


def test_box_snapshot_gate_status_live(tmp_path):
    gate = _gate_status_file(str(tmp_path), state="live")
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", gate])
    assert snap["gate"]["frozen"] is False
    assert isinstance(snap["gate"]["answer_age_s"], int)


def test_box_snapshot_gate_status_answer_age(tmp_path):
    gen = datetime.now(timezone.utc) - timedelta(seconds=95)
    gate = _gate_status_file(str(tmp_path), state="live", generated_at=gen)
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", gate])
    # ~95s old; allow a few seconds of test overhead either way.
    assert 80 <= snap["gate"]["answer_age_s"] <= 120, snap["gate"]


def test_box_snapshot_gate_status_missing_file(tmp_path):
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status",
                           os.path.join(str(tmp_path), "nope.json")])
    assert snap["gate"]["frozen"] is None
    assert snap["gate"]["answer_age_s"] is None
    assert "not present" in (snap["note"] or "")


def test_box_snapshot_gate_status_corrupt_file(tmp_path):
    gate = _gate_status_file(str(tmp_path), raw="{not json")
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", gate])
    assert snap["gate"]["frozen"] is None
    assert snap["gate"]["answer_age_s"] is None
    assert "unreadable" in (snap["note"] or "")


def test_box_snapshot_gate_status_bad_state(tmp_path):
    gate = _gate_status_file(str(tmp_path), state="maybe")
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", gate])
    assert snap["gate"]["frozen"] is None
    assert "not frozen/live" in (snap["note"] or "")


def test_box_snapshot_frozen_flag_overrides_gate_status(tmp_path):
    gate = _gate_status_file(str(tmp_path), state="live")
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", gate, "--frozen", "frozen"])
    assert snap["gate"]["frozen"] is True
    # The explicit override wins; the file's age is not consulted.
    assert snap["gate"]["answer_age_s"] is None


def test_box_snapshot_gate_status_bad_timestamp_keeps_state(tmp_path):
    # Valid state + unparseable timestamp: the state is reported, only the
    # age is null (Engineering review blocking 1).
    path = os.path.join(str(tmp_path), "gate-status.json")
    payload = {
        "schema_version": 1,
        "generated_at": "not-a-timestamp",
        "source": "gate_hook",
        "answer": {"state": "frozen", "reason": "test"},
    }
    with open(path, "w") as fh:
        json.dump(payload, fh)
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", path])
    assert snap["gate"]["frozen"] is True
    assert snap["gate"]["answer_age_s"] is None
    assert "unparseable" in (snap["note"] or "")


def test_box_snapshot_gate_status_bad_state_keeps_age(tmp_path):
    # Bad state + good timestamp: the age is reported, only frozen is null
    # (Engineering review blocking 1, symmetric case).
    path = os.path.join(str(tmp_path), "gate-status.json")
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "source": "gate_hook",
        "answer": {"state": "maybe", "reason": "test"},
    }
    with open(path, "w") as fh:
        json.dump(payload, fh)
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", path])
    assert snap["gate"]["frozen"] is None
    assert isinstance(snap["gate"]["answer_age_s"], int)
    assert "not frozen/live" in (snap["note"] or "")


def test_box_snapshot_gate_status_non_dict_answer(tmp_path):
    path = os.path.join(str(tmp_path), "gate-status.json")
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "source": "gate_hook",
        "answer": "not-an-object",
    }
    with open(path, "w") as fh:
        json.dump(payload, fh)
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", path])
    assert snap["gate"]["frozen"] is None
    assert isinstance(snap["gate"]["answer_age_s"], int)
    assert "not an object" in (snap["note"] or "")


def test_box_snapshot_bogus_frozen_falls_through_to_gate_file(tmp_path):
    # A typo in --frozen is not an explicit flag: the gate file is still
    # consulted (QA review B2).
    gate = _gate_status_file(str(tmp_path), state="frozen")
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", gate,
                           "--frozen", "bogus"])
    assert snap["gate"]["frozen"] is True
    assert isinstance(snap["gate"]["answer_age_s"], int)
    assert "unrecognized --frozen value" in (snap["note"] or "")


def test_box_snapshot_frozen_unfrozen_overrides_frozen_file(tmp_path):
    # Reverse precedence: explicit --frozen unfrozen wins over a frozen file.
    gate = _gate_status_file(str(tmp_path), state="frozen")
    snap = _snapshot_gate(["--checkout", str(tmp_path),
                           "--gate-status", gate,
                           "--frozen", "unfrozen"])
    assert snap["gate"]["frozen"] is False
    assert snap["gate"]["answer_age_s"] is None


# --- correlated gate-stale, sixth S1 alert rule (G18 §7, #1631) ----------


def _stale_gate_snapshot(stale_seconds, frozen=False):
    gen = (NOW - timedelta(seconds=stale_seconds)).isoformat()
    return {"repo_commit": COMMIT_A,
            "gate": {"frozen": frozen, "answer_age_s": stale_seconds,
                     "generated_at": gen},
            "arc_active": None, "image_version": None,
            "note": None, "emitted_at": NOW.isoformat()}


def _expected_gate_stale_id(episode, stale_boxes):
    # Mirrors events._alert's id derivation: uuid5 over
    # rule|box_id|subcomponent|to|dedup_key — fleet-scoped, so box_id,
    # subcomponent and to are empty; the dedup key is the episode
    # number plus the sorted stale set joined on "|".
    alert_ns = uuid.uuid5(
        uuid.NAMESPACE_URL,
        "https://github.com/ntindle/spark-vm/fleet/alerts")
    return str(uuid.uuid5(
        alert_ns, "correlated-gate-stale||||ep%d|%s" % (
            episode, "|".join(sorted(stale_boxes)))))


def _gate_stale_watermark(store):
    with open(os.path.join(store, "gate_stale_watermark.json")) as fh:
        return json.load(fh)


def test_correlated_gate_stale_fires_fleet_scoped_alert(env):
    # Two boxes hold gate answers older than 2x the S1 TTL while a third
    # stays fresh: one fleet-scoped page, not one per box.
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-b": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(1800, frozen=True)},
        "box-c": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(60)},
    })
    rows = _alerts(store)
    assert len(rows) == 1, rows
    alert = rows[0]
    assert alert["schema"] == "fleet-alert/1"
    assert alert["rule"] == "correlated-gate-stale"
    assert alert["box_id"] is None  # fleet-scoped: no box owns the outage
    assert alert["acked"] is False
    assert "fleet gate sync outage" in alert["detail"]
    assert "box-a" in alert["detail"] and "box-b" in alert["detail"]
    assert "box-c" not in alert["detail"]
    assert alert["alert_id"] == _expected_gate_stale_id(1, ["box-a", "box-b"])
    # The paging path sees it: `events watch` exits 1 while the alert
    # is unacknowledged.
    watch = run_inventory("events", "watch", "--store", store)
    assert watch.returncode == 1, watch.stdout
    assert "correlated-gate-stale" in watch.stdout


def test_correlated_gate_stale_single_box_silent(env):
    # Below the correlation quorum: a lone stale box is a per-box row on
    # the inventory table, never a page.
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-b": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(60)},
    })
    assert _alerts(store) == []
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "correlated-gate-stale alert(s) fired" not in proc.stdout
    assert _alerts(store) == []


def test_correlated_gate_stale_same_episode_dedups(env):
    # The identical stale set on the next collect stays silent: one page
    # per outage, not per collect.
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-b": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
    })
    assert len(_alerts(store)) == 1
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "correlated-gate-stale alert(s) fired" not in proc.stdout
    assert len(_alerts(store)) == 1


def test_correlated_gate_stale_growth_refires(env):
    # A new box joining the outage is new evidence: the grown set pages
    # again under a new alert id (rule 2's #927 discipline, fleet-side).
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-b": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
    })
    assert len(_alerts(store)) == 1
    _write_box(estate, "box-c", status=_status_json(),
               snapshot=_stale_gate_snapshot(3600))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "1 correlated-gate-stale alert(s) fired" in proc.stdout
    rows = _alerts(store)
    assert len(rows) == 2, rows
    assert rows[1]["alert_id"] == _expected_gate_stale_id(
        2, ["box-a", "box-b", "box-c"])


def test_correlated_gate_stale_shrinkage_silent(env):
    # A box recovering out of the outage (quorum still held) narrows the
    # episode silently — the operator was already paged on the wider set.
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-b": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-c": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
    })
    assert len(_alerts(store)) == 1
    _write_box(estate, "box-c", status=_status_json(),
               snapshot=_stale_gate_snapshot(60))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "correlated-gate-stale alert(s) fired" not in proc.stdout
    assert len(_alerts(store)) == 1
    wm = _gate_stale_watermark(store)
    assert wm["stale_boxes"] == ["box-a", "box-b"]
    assert wm["episode"] == 1  # shrinkage keeps the episode number


def test_correlated_gate_stale_resolves_then_refires(env):
    # The stale set dropping below quorum resolves the episode; a later
    # re-outage of the same boxes is a new episode and pages again.
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-b": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
    })
    assert len(_alerts(store)) == 1
    for box in ("box-a", "box-b"):
        _write_box(estate, box, status=_status_json(),
                   snapshot=_stale_gate_snapshot(60))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "correlated-gate-stale alert(s) fired" not in proc.stdout
    assert len(_alerts(store)) == 1
    # The episode resolved but the counter persisted: the watermark is
    # still on disk with an empty box set.
    wm = _gate_stale_watermark(store)
    assert wm["stale_boxes"] == [] and wm["episode"] == 1
    for box in ("box-a", "box-b"):
        _write_box(estate, box, status=_status_json(),
                   snapshot=_stale_gate_snapshot(3600))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "1 correlated-gate-stale alert(s) fired" in proc.stdout
    rows = _alerts(store)
    assert len(rows) == 2, rows
    # New episode, new alert id — the re-outage pages again.
    assert rows[1]["alert_id"] == _expected_gate_stale_id(
        2, ["box-a", "box-b"])


def test_correlated_gate_stale_uncomputable_age_not_evidence(env):
    # Gate-unmanaged boxes (no gate answer at all) are missing evidence,
    # not a stale signal — even two of them never page.
    snap = {"repo_commit": COMMIT_A, "arc_active": None,
            "image_version": None, "note": None,
            "emitted_at": NOW.isoformat()}
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(), "snapshot": snap},
        "box-b": {"status": _status_json(), "snapshot": snap},
    })
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert _alerts(store) == []


def test_correlated_gate_stale_corrupt_watermark_fails_loud(env):
    # A corrupt watermark refuses the evaluation loudly (fail-visible,
    # the #1744 precedent) instead of resetting the episode counter to
    # zero — a paging rule must never fail silent on its own state.
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-b": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
    })
    assert len(_alerts(store)) == 1
    wm_path = os.path.join(store, "gate_stale_watermark.json")
    garbage = b"\x00\x01not json{{{{"
    with open(wm_path, "wb") as fh:
        fh.write(garbage)
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode != 0, (proc.returncode, proc.stdout)
    assert "gate-stale watermark" in proc.stderr, proc.stderr
    assert "corrupt" in proc.stderr, proc.stderr
    assert len(_alerts(store)) == 1  # no new page on a refused evaluation
    # The refusal never rewrites the file: the operator's evidence is
    # intact for inspection/backup.
    assert open(wm_path, "rb").read() == garbage


def test_correlated_gate_stale_wrong_schema_watermark_fails_loud(env):
    # Same loud refusal for a well-formed JSON file with the wrong
    # schema — episode identity cannot be reconstructed from it either.
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-b": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
    })
    assert len(_alerts(store)) == 1
    wm_path = os.path.join(store, "gate_stale_watermark.json")
    with open(wm_path, "w") as fh:
        json.dump({"schema": "something-else/9", "stale_boxes": ["x"]}, fh)
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode != 0, (proc.returncode, proc.stdout)
    assert "gate-stale watermark" in proc.stderr, proc.stderr
    assert len(_alerts(store)) == 1


def test_correlated_gate_stale_lost_watermark_no_double_page(env):
    # Crash-ordering regression: the alert journaled but the watermark
    # write was lost (simulated by deleting the file between collects).
    # The retry mints the same episode number, so the journal dedup —
    # not a second page — is the result, and the watermark is
    # re-established.
    estate, store = _collect(env, {
        "box-a": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
        "box-b": {"status": _status_json(),
                  "snapshot": _stale_gate_snapshot(3600)},
    })
    assert len(_alerts(store)) == 1
    os.unlink(os.path.join(store, "gate_stale_watermark.json"))
    proc = run_inventory("collect", "--estate", estate, "--store", store)
    assert proc.returncode == 0, proc.stderr
    assert "correlated-gate-stale alert(s) fired" not in proc.stdout
    assert len(_alerts(store)) == 1
    wm = _gate_stale_watermark(store)
    assert wm["stale_boxes"] == ["box-a", "box-b"]
    assert wm["episode"] == 1
