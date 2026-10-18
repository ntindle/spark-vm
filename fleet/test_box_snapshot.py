#!/usr/bin/env python3
"""Pin fleet/box_snapshot.py's contract (G16 / #607 S1).

box_snapshot.py is the box-side emitter for the fleet version inventory:
it derives {repo_commit, gate.frozen, gate.answer_age_s, image_version}
from state the updaters already maintain and hands the S1 collector
(fleet/inventory.py collect) an honest snapshot — unknown fields are null
with a note, never invented, never a crash. The module's headline
contract is "never raises and never writes outside --out".

fleet/test_inventory.py has only three producer-contract subprocess calls
for this emitter (git-head emission, bad checkout, --out + --frozen);
everything below pins the emitter's own edge behaviors, split in two
layers:

1. Unit pins: the private helpers are imported (importlib, no sys.path
   surgery — fleet/ has no __init__.py by repo convention) and exercised
   directly. box_snapshot.py performs no import-time side effects.
2. CLI pins: main() is exercised through the real subprocess, never
   imported, matching test_inventory.py's convention.

All state lives under tmp dirs; no test writes outside --out and no test
depends on the wall clock beyond "age_s is small for a just-written
status file".
"""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone

FLEET = os.path.dirname(os.path.abspath(__file__))
BOX_SNAPSHOT = os.path.join(FLEET, "box_snapshot.py")


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "box_snapshot_under_test", BOX_SNAPSHOT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


box_snapshot = _load_module()


def run_snapshot(*argv, cwd=None):
    return subprocess.run(
        [sys.executable, BOX_SNAPSHOT, *argv],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)


def write_gate_status(path, state="live", generated_at=None, extra=None):
    payload = {"generated_at": generated_at, "answer": {"state": state}}
    if extra:
        payload.update(extra)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def parse_stdout(proc):
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# ---------------------------------------------------------------------------
# _parse_generated_at
# ---------------------------------------------------------------------------

def test_parse_generated_at_z_suffix():
    dt, note = box_snapshot._parse_generated_at("2026-01-02T03:04:05Z")
    assert note is None
    assert dt == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_parse_generated_at_lowercase_z_and_whitespace():
    dt, note = box_snapshot._parse_generated_at("  2026-01-02T03:04:05z  ")
    assert note is None
    assert dt == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_parse_generated_at_offset_kept():
    dt, note = box_snapshot._parse_generated_at("2026-01-02T05:04:05+02:00")
    assert note is None
    assert dt.utcoffset() == timedelta(hours=2)
    assert dt.astimezone(timezone.utc).hour == 3


def test_parse_generated_at_naive_assumed_utc():
    dt, note = box_snapshot._parse_generated_at("2026-01-02T03:04:05")
    assert note is None
    assert dt.tzinfo == timezone.utc


def test_parse_generated_at_missing_empty_unparseable():
    for bad in (None, "", "   ", 123, "not-a-date", "2026-13-99T99:99:99Z"):
        dt, note = box_snapshot._parse_generated_at(bad)
        assert dt is None
        assert isinstance(note, str) and note, bad


# ---------------------------------------------------------------------------
# _read_gate_status
# ---------------------------------------------------------------------------

def test_read_gate_status_missing_file(tmp_path):
    frozen, age, gen_at, note = box_snapshot._read_gate_status(
        str(tmp_path / "nope.json"))
    assert (frozen, age) == (None, None)
    assert "not present" in note


def test_read_gate_status_bad_json_never_raises(tmp_path):
    p = tmp_path / "status.json"
    p.write_text("{not json", encoding="utf-8")
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert (frozen, age) == (None, None)
    assert "unreadable" in note  # proves the except branch was taken


def test_read_gate_status_unreadable_variants(tmp_path):
    # Both hit the "unreadable" branch through different errnos:
    # a directory (IsADirectoryError ⊂ OSError) and undecodable bytes
    # (UnicodeDecodeError ⊂ ValueError).
    directory_note = box_snapshot._read_gate_status(str(tmp_path))[3]
    assert "unreadable" in directory_note
    p = tmp_path / "status.json"
    p.write_bytes(b"\xff\xfe{not utf-8")
    _, _, _, bytes_note = box_snapshot._read_gate_status(str(p))
    assert "unreadable" in bytes_note


def test_read_gate_status_deeply_nested_json_never_raises(tmp_path):
    # The module catches RecursionError explicitly to keep the "never
    # raises" contract; this test must actually trigger it. Empirically
    # (Python 3.12, recursion limit 1000) depth 2000 still parses fine
    # and only ~10000+ raises — so 20000, well above on every supported
    # Python. Asserting "unreadable" in the note proves the except
    # branch was taken rather than the answer-missing path.
    p = tmp_path / "status.json"
    p.write_text('{"a":' * 20000 + "1" + "}" * 20000, encoding="utf-8")
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert (frozen, age) == (None, None)
    assert "unreadable" in note


def test_read_gate_status_non_string_generated_at(tmp_path):
    # A non-string generated_at (JSON number here) nulls only the age;
    # the good state still yields frozen.
    p = tmp_path / "status.json"
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": 123, "answer": {"state": "live"}}, fh)
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert frozen is False
    assert age is None
    assert isinstance(note, str) and note


def test_read_gate_status_non_object_payload(tmp_path):
    p = tmp_path / "status.json"
    p.write_text("[1, 2]", encoding="utf-8")
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert (frozen, age) == (None, None)
    assert "not a JSON object" in note


def test_read_gate_status_frozen_and_live(tmp_path):
    now = datetime.now(timezone.utc).isoformat()
    for state, want in (("frozen", True), ("live", False)):
        p = tmp_path / ("s-%s.json" % state)
        write_gate_status(p, state=state, generated_at=now)
        frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
        assert frozen is want, state
        assert age is not None and 0 <= age < 300, state
        assert note is None, (state, note)


def test_read_gate_status_unknown_state_nulls_only_frozen(tmp_path):
    # Per-field nulls: a bad state nulls frozen but the good timestamp
    # still yields an age.
    p = tmp_path / "status.json"
    write_gate_status(p, state="FROZEN",  # case-sensitive: unknown
                      generated_at=datetime.now(timezone.utc).isoformat())
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert frozen is None
    assert age is not None and 0 <= age < 300
    assert "not frozen/live" in note


def test_read_gate_status_bad_timestamp_nulls_only_age(tmp_path):
    # The mirror: a bad timestamp nulls age but the good state still
    # yields frozen.
    p = tmp_path / "status.json"
    write_gate_status(p, state="live", generated_at="yesterday-ish")
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert frozen is False
    assert age is None
    assert "unparseable" in note


def test_read_gate_status_future_timestamp_floors_zero_with_note(tmp_path):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    p = tmp_path / "status.json"
    write_gate_status(p, state="frozen", generated_at=future)
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert frozen is True
    assert age == 0  # floored, not negative
    assert "in the future" in note and "floored at 0" in note


def test_read_gate_status_missing_answer_noted(tmp_path):
    p = tmp_path / "status.json"
    with open(p, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat()},
                  fh)
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert frozen is None
    assert age is not None
    assert "answer missing" in note


def test_read_gate_status_surfaces_generated_at_iso(tmp_path):
    # D-SC-2 (#1660): the hook's timestamp is surfaced (normalized to
    # ISO-8601, aware UTC), not discarded, so the collector can recompute
    # the true gate age instead of trusting the emit-time age.
    p = tmp_path / "status.json"
    write_gate_status(p, state="live",
                      generated_at="2026-10-18T12:00:00Z")
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert frozen is False
    assert age is not None
    parsed = datetime.fromisoformat(gen_at)
    assert parsed == datetime(2026, 10, 18, 12, 0, 0,
                              tzinfo=timezone.utc), gen_at


def test_read_gate_status_unparseable_generated_at_nulls_only_age(tmp_path):
    # A bad timestamp nulls the age AND the surfaced generated_at, but
    # never the frozen field (per-field independence, #1660).
    p = tmp_path / "status.json"
    write_gate_status(p, state="frozen", generated_at="not-a-timestamp")
    frozen, age, gen_at, note = box_snapshot._read_gate_status(str(p))
    assert frozen is True
    assert age is None
    assert gen_at is None
    assert "unparseable" in note


def test_main_emits_gate_generated_at(tmp_path):
    # End-to-end: the snapshot's gate.generated_at carries the hook's
    # timestamp (#1660 acceptance).
    p = tmp_path / "status.json"
    write_gate_status(p, state="live",
                      generated_at="2026-10-18T12:00:00Z")
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(p))
    snap = parse_stdout(proc)
    assert snap["gate"]["generated_at"] == \
        "2026-10-18T12:00:00+00:00", snap["gate"]
    assert snap["gate"]["answer_age_s"] >= 0


# ---------------------------------------------------------------------------
# _git_head
# ---------------------------------------------------------------------------

def test_git_head_missing_checkout(tmp_path):
    commit, note = box_snapshot._git_head(str(tmp_path / "nope"))
    assert commit is None
    assert "not present" in note


def test_git_head_non_git_dir_note_names_first_stderr_line(tmp_path):
    # git rev-parse exits nonzero with a first stderr line; the note
    # carries that line, not the "['exit 128']" repr (FOLLOW-fleet2).
    # The wording is not asserted verbatim — git localizes it.
    commit, note = box_snapshot._git_head(str(tmp_path))
    assert commit is None
    assert note.startswith("git rev-parse failed: "), note
    assert "['exit" not in note


def test_git_head_silent_git_uses_exit_code(tmp_path, monkeypatch):
    # A git that fails silently must still produce a usable note: the
    # exit code, not an empty detail.
    bindir = tmp_path / "bin"
    bindir.mkdir()
    git = bindir / "git"
    git.write_text("#!/bin/sh\nexit 128\n", encoding="utf-8")
    git.chmod(git.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(bindir))
    commit, note = box_snapshot._git_head(str(tmp_path))
    assert commit is None
    assert note == "git rev-parse failed: exit 128", note


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------

def test_main_stdout_schema(tmp_path):
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(tmp_path / "nope.json"))
    snap = parse_stdout(proc)
    assert set(snap) == {"repo_commit", "gate", "arc_active",
                         "image_version", "note", "emitted_at"}
    assert snap["repo_commit"] is None
    assert set(snap["gate"]) == {"frozen", "answer_age_s", "generated_at"}
    assert snap["gate"] == {"frozen": None, "answer_age_s": None,
                            "generated_at": None}
    assert snap["arc_active"] is None  # the G15 hook's slice, not S1's
    assert snap["image_version"] is None
    assert isinstance(snap["note"], str) and snap["note"]
    datetime.fromisoformat(snap["emitted_at"])  # parseable ISO


def test_main_image_version_passthrough(tmp_path):
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(tmp_path / "nope.json"),
                        "--image-version", "2026.10.16")
    assert parse_stdout(proc)["image_version"] == "2026.10.16"


def test_main_frozen_flag_overrides_gate_file(tmp_path):
    p = tmp_path / "status.json"
    write_gate_status(p, state="live",
                      generated_at=datetime.now(timezone.utc).isoformat())
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(p), "--frozen", "frozen")
    snap = parse_stdout(proc)
    assert snap["gate"]["frozen"] is True  # file said "live"
    # The file also carried a fresh generated_at; a consulted gate file
    # would yield a small-int answer_age_s. None proves the file was
    # skipped, not read.
    assert snap["gate"]["answer_age_s"] is None
    assert "gate status" not in (snap["note"] or "")


def test_main_frozen_unfrozen_flag_overrides_gate_file(tmp_path):
    p = tmp_path / "status.json"
    write_gate_status(p, state="frozen",
                      generated_at=datetime.now(timezone.utc).isoformat())
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(p), "--frozen", "unfrozen")
    snap = parse_stdout(proc)
    assert snap["gate"]["frozen"] is False  # file said "frozen"
    assert snap["gate"]["answer_age_s"] is None  # file skipped
    assert "gate status" not in (snap["note"] or "")


def test_main_frozen_flag_normalizes_case_and_whitespace(tmp_path):
    p = tmp_path / "status.json"
    write_gate_status(p, state="frozen",
                      generated_at=datetime.now(timezone.utc).isoformat())
    for raw, want in (("  FROZEN  ", True), ("TRUE", True),
                      ("0", False), ("no", False)):
        proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                            "--gate-status", str(p), "--frozen", raw)
        snap = parse_stdout(proc)
        assert snap["gate"]["frozen"] is want, raw
        assert snap["gate"]["answer_age_s"] is None, raw


def test_main_frozen_typo_falls_through_to_gate_file(tmp_path):
    # A garbage --frozen value is noted but must not kill the S1b
    # visibility loop: the gate file still supplies frozen.
    p = tmp_path / "status.json"
    write_gate_status(p, state="frozen",
                      generated_at=datetime.now(timezone.utc).isoformat())
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(p), "--frozen", "froze")
    snap = parse_stdout(proc)
    assert "unrecognized --frozen value" in snap["note"]
    assert snap["gate"]["frozen"] is True  # fell through to the file


def test_main_gate_file_feeds_frozen_and_age(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    subprocess.run(["git", "-C", str(checkout), "-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-q", "--allow-empty",
                    "-m", "x"], check=True)
    p = tmp_path / "status.json"
    write_gate_status(p, state="frozen",
                      generated_at=datetime.now(timezone.utc).isoformat())
    proc = run_snapshot("--checkout", str(checkout),
                        "--gate-status", str(p))
    snap = parse_stdout(proc)
    assert snap["repo_commit"] and len(snap["repo_commit"]) == 40
    assert snap["gate"]["frozen"] is True
    assert snap["gate"]["answer_age_s"] is not None
    assert 0 <= snap["gate"]["answer_age_s"] < 300
    assert snap["note"] is None  # clean status file -> no notes


def test_main_garbage_gate_file_never_raises(tmp_path):
    p = tmp_path / "status.json"
    p.write_text("{nope", encoding="utf-8")
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(p))
    snap = parse_stdout(proc)
    assert snap["gate"] == {"frozen": None, "answer_age_s": None,
                            "generated_at": None}
    assert isinstance(snap["note"], str) and snap["note"]


def test_main_out_file_written_stdout_empty(tmp_path):
    out = tmp_path / "snap.json"
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(tmp_path / "nope.json"),
                        "--out", str(out))
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert set(snap) == {"repo_commit", "gate", "arc_active",
                         "image_version", "note", "emitted_at"}


def test_main_out_write_failure_is_exit_2(tmp_path):
    # --out under a directory that does not exist: the module reports
    # loudly (exit 2 + stderr) instead of crashing or inventing data.
    out = tmp_path / "no-such-dir" / "snap.json"
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(tmp_path / "nope.json"),
                        "--out", str(out))
    assert proc.returncode == 2
    assert "error: cannot write" in proc.stderr


def test_main_out_to_directory_is_exit_2(tmp_path):
    # Same OSError clause, different errno: --out pointing at an
    # existing directory.
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(tmp_path / "nope.json"),
                        "--out", str(tmp_path))
    assert proc.returncode == 2
    assert "error: cannot write" in proc.stderr


def test_main_unknown_flag_is_exit_2(tmp_path):
    # argparse's noisiest edge of the "never crashes" contract: an
    # unknown flag exits 2 with usage on stderr, never a traceback.
    proc = run_snapshot("--bogus")
    assert proc.returncode == 2
    assert "unrecognized arguments" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_main_writes_nothing_outside_out(tmp_path):
    # Smoke for the "never writes outside --out" half of the contract:
    # the module's only write path is open(args.out), so a no---out run
    # with cwd set to an empty tmp dir must leave that dir empty. (It
    # cannot prove nothing was written to other dirs — the claim is
    # bounded by the code's single write call, read and confirmed.)
    proc = run_snapshot("--checkout", str(tmp_path / "nope"),
                        "--gate-status", str(tmp_path / "nope.json"),
                        cwd=str(tmp_path))
    assert proc.returncode == 0, proc.stderr
    assert os.listdir(tmp_path) == []
