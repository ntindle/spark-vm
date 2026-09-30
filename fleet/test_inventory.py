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
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone

import pytest

FLEET = os.path.dirname(os.path.abspath(__file__))
INVENTORY = os.path.join(FLEET, "inventory.py")
BOX_SNAPSHOT = os.path.join(FLEET, "box_snapshot.py")

NOW = datetime.now(timezone.utc)
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40


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
                                   "answer_age_s"}
    assert record["gate"]["permitted_commit"] is None  # S1: G15's slice
    assert record["gate"]["permitted_toolset_pin"] is None
    assert "arc" in record and "arc_active" not in record


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
