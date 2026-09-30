"""Tests for issue #27: manager-owned hook event-file rotation.

Covers rotate_event_file + _maybe_rotate_event_file in bin/muse-job:

  - The trigger is size only, evaluated by the manager. Hooks never call
    it; the agent's only lever is appending lines.
  - Terminal `done` claims are re-seeded byte-identical into the head of
    the fresh file, so a rotated-out genuine done keeps paging every pass
    instead of becoming a silent burial (the #23 B1/B3 class).
  - Rename-based atomicity w.r.t. concurrent O_APPEND hook writes: a hook
    that opened its fd before the rename lands in the archive, one that
    opens after lands in the fresh file -- every line in exactly one file,
    never lost, never duplicated.
  - Fail-closed refusals: symlinked event file, symlinked EVENTS_DIR,
    malformed uuid, missing file; and restore-on-failure when the archive
    can't be read after the rename.
  - Composition with the 30-day disk sweep: rotated archives never match
    an active job's skip name and are pruned by mtime like any old file.
"""
import glob
import importlib.machinery
import importlib.util
import json
import os
import sys
import threading

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")
SWEEP_PATH = os.path.join(os.path.dirname(__file__), "..", "bin",
                          "muse-job-sweep")

SID = "testsession01"


def load_script(name, path):
    """Import an extensionless script by explicit loader."""
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    """Import bin/muse-job with HOME pointed at an isolated tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_rotate", CLI_PATH)


@pytest.fixture()
def small_threshold(cli, monkeypatch):
    """Lower the rotation threshold so fixtures stay small."""
    monkeypatch.setattr(cli, "_EVENT_ROTATE_BYTES", 512)
    return cli


def event_path(cli, sid=SID):
    return os.path.join(cli.EVENTS_DIR, sid + ".jsonl")


def write_lines(cli, lines, sid=SID):
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    with open(event_path(cli, sid), "wb") as f:
        for line in lines:
            f.write(line if line.endswith(b"\n") else line + b"\n")


def done_line(i, sid=SID):
    return json.dumps({"ts": 1000 + i, "event": "stop", "session_id": sid,
                       "state": "done", "detail": "d%d" % i, "cwd": "/w",
                       "turn_id": i}).encode()


def idle_line(i, sid=SID):
    return json.dumps({"ts": 1000 + i, "event": "stop", "session_id": sid,
                       "state": "idle", "detail": "x%d" % i, "cwd": "/w",
                       "turn_id": i}).encode()


def hook_append(cli, line, sid=SID):
    """Append one line the way the hooks do: O_APPEND by name per event."""
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    fd = os.open(event_path(cli, sid),
                 os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line if line.endswith(b"\n") else line + b"\n")
    finally:
        os.close(fd)


def all_event_files(cli, sid=SID):
    return sorted(glob.glob(event_path(cli, sid) + "*"))


def read_lines(p):
    with open(p, "rb") as f:
        return [l for l in (r.rstrip(b"\n") for r in f) if l]


# --- trigger / no-op -----------------------------------------------------

def test_below_threshold_is_noop(small_threshold):
    cli = small_threshold
    lines = [idle_line(i) for i in range(2)]
    write_lines(cli, lines)
    assert cli.rotate_event_file(SID) is False
    assert all_event_files(cli) == [event_path(cli)]
    assert read_lines(event_path(cli)) == [l.rstrip(b"\n") for l in lines]


def test_missing_file_and_bad_uuid_are_noops(small_threshold):
    cli = small_threshold
    assert cli.rotate_event_file(SID) is False
    assert cli.rotate_event_file("../evil") is False
    assert cli.rotate_event_file("") is False
    assert cli.rotate_event_file(None) is False


# --- archive + done re-seeding ---------------------------------------------

def write_over_threshold(cli, lines, sid=SID):
    """Write lines plus idle filler so the file exceeds the rotation
    threshold. Returns the filler lines (all non-done)."""
    filler = []
    size = sum(len(l) + 1 for l in lines)
    i = 0
    while size <= cli._EVENT_ROTATE_BYTES:
        line = idle_line(9000 + i)
        filler.append(line)
        size += len(line) + 1
        i += 1
    write_lines(cli, lines + filler, sid)
    return filler


def test_rotate_archives_and_reseeds_dones_byte_identical(small_threshold):
    cli = small_threshold
    dones = [done_line(0), done_line(1)]
    others = [idle_line(10), b"not json at all",
              json.dumps(["not", "a", "dict"]).encode(),
              json.dumps({"state": "done-but-a-string"}).encode()]
    original = dones[:1] + others[:2] + dones[1:] + others[2:]
    filler = write_over_threshold(cli, original)
    assert cli.rotate_event_file(SID) is True

    files = all_event_files(cli)
    assert len(files) == 2
    archived = [f for f in files if f != event_path(cli)][0]
    assert archived.endswith(".rot")
    # The archive holds every original line, byte-identical.
    full_original = original + filler
    assert read_lines(archived) == [l.rstrip(b"\n") for l in full_original]
    # The fresh file holds exactly the done lines, byte-identical, in order.
    assert read_lines(event_path(cli)) == [l.rstrip(b"\n") for l in dones]


def test_done_claims_still_triage_after_rotation(small_threshold):
    """The re-seeded claims satisfy the same predicate done_events uses."""
    cli = small_threshold
    write_lines(cli, [idle_line(i) for i in range(6)] + [done_line(7)])
    before = cli.done_events(SID, 9999)
    assert cli.rotate_event_file(SID) is True
    after = cli.done_events(SID, 9999)
    assert len(before) == len(after) == 1
    assert after[0][0]["detail"] == "d7"


def test_rotate_without_dones_leaves_empty_fresh_file(small_threshold):
    cli = small_threshold
    write_lines(cli, [idle_line(i) for i in range(20)])
    assert cli.rotate_event_file(SID) is True
    assert read_lines(event_path(cli)) == []
    assert len(all_event_files(cli)) == 2


# --- atomicity w.r.t. concurrent hook appends -------------------------------

def test_reseed_race_with_hook_append(small_threshold, monkeypatch):
    """A hook appending inside the rename -> re-seed window lands intact in
    the fresh file. Regression: the re-seed fd must be O_APPEND -- with a
    plain O_WRONLY fd its writes land at offset 0 and clobber the racing
    hook's line mid-file, tearing it."""
    cli = small_threshold
    write_over_threshold(cli, [done_line(0), idle_line(1)])
    raced = idle_line(4242)
    real_extract = cli._done_lines_of

    def extract_then_append(path):
        hook_append(cli, raced)  # opens by name: lands in the fresh file
        return real_extract(path)

    monkeypatch.setattr(cli, "_done_lines_of", extract_then_append)
    assert cli.rotate_event_file(SID) is True
    fresh = read_lines(event_path(cli))
    assert sorted(fresh) == sorted([done_line(0).rstrip(b"\n"),
                                    raced.rstrip(b"\n")])
    for raw in fresh:
        json.loads(raw)  # every line parses: nothing torn


def test_appends_around_rotate_no_loss_no_dup(small_threshold):
    """Batch, rotate, batch: every line in exactly one file (dones twice
    by design: archive + re-seeded fresh)."""
    cli = small_threshold
    batch1 = [idle_line(i) for i in range(5)] + [done_line(100)]
    for line in batch1:
        hook_append(cli, line)
    assert cli.rotate_event_file(SID) is True
    batch2 = [idle_line(1000 + i) for i in range(5)] + [done_line(200)]
    for line in batch2:
        hook_append(cli, line)

    files = all_event_files(cli)
    assert len(files) == 2
    archived = [f for f in files if f != event_path(cli)][0]
    got = read_lines(archived) + read_lines(event_path(cli))
    expected = ([l.rstrip(b"\n") for l in batch1]          # archive: all
                + [done_line(100).rstrip(b"\n")]           # re-seeded
                + [l.rstrip(b"\n") for l in batch2])       # fresh: new only
    assert sorted(got) == sorted(expected)


def test_concurrent_appends_survive_rotates(small_threshold):
    """Hook-style appends racing rotations: no non-done line is ever lost
    or duplicated; every done surfaces at least once."""
    cli = small_threshold
    stop = threading.Event()
    errors = []

    def worker(base):
        try:
            i = 0
            while not stop.is_set():
                hook_append(cli, idle_line(base + i))
                if i % 10 == 0:
                    hook_append(cli, done_line(base + i))
                i += 1
        except Exception as e:  # pragma: no cover - must not happen
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(b * 100000,))
               for b in range(4)]
    for t in threads:
        t.start()
    for _ in range(6):
        cli.rotate_event_file(SID)
    stop.set()
    for t in threads:
        t.join()
    assert not errors

    counts = {}
    done_seen = set()
    for p in all_event_files(cli):
        for raw in read_lines(p):
            obj = json.loads(raw)
            key = (obj["detail"], obj["turn_id"])
            if obj["state"] == "done":
                done_seen.add(key)
            else:
                counts[key] = counts.get(key, 0) + 1
    assert counts, "no lines survived the rotation storm"
    assert all(c == 1 for c in counts.values()), \
        "a non-done line was lost or duplicated"
    assert done_seen, "done claims vanished"


# --- fail-closed refusals ----------------------------------------------------

def test_refuses_symlinked_event_file(small_threshold, tmp_path):
    cli = small_threshold
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    target = tmp_path / "real.jsonl"
    target.write_bytes(b"x" * 2048)
    os.symlink(str(target), event_path(cli))
    assert cli.rotate_event_file(SID) is False
    assert os.path.islink(event_path(cli))
    assert len(all_event_files(cli)) == 1  # no archive created


def test_refuses_symlinked_events_dir(small_threshold, tmp_path, monkeypatch):
    cli = small_threshold
    real = tmp_path / "real-events"
    real.mkdir()
    (real / (SID + ".jsonl")).write_bytes(b"x" * 2048)
    monkeypatch.setattr(cli, "EVENTS_DIR", str(tmp_path / "link-events"))
    os.symlink(str(real), str(tmp_path / "link-events"))
    assert cli.rotate_event_file(SID) is False


def test_restore_on_unreadable_archive(small_threshold, monkeypatch):
    """If the archive can't be read after the rename, the original file is
    restored -- a fresh file that silently dropped done claims is worse
    than no rotation."""
    cli = small_threshold
    lines = [done_line(0)] + [idle_line(i) for i in range(30)]
    write_lines(cli, lines)
    monkeypatch.setattr(cli, "_done_lines_of",
                        lambda path: (_ for _ in ()).throw(OSError("boom")))
    assert cli.rotate_event_file(SID) is False
    assert all_event_files(cli) == [event_path(cli)]
    assert read_lines(event_path(cli)) == [l.rstrip(b"\n") for l in lines]


# --- watch emission contract -------------------------------------------------

def test_maybe_rotate_emission_contract(small_threshold):
    """_maybe_rotate_event_file appends exactly one `events-rotated` event
    carrying the job key on rotation, and nothing when no rotation
    happens. Deleting the signal or the job key in the watch path breaks
    this test."""
    cli = small_threshold
    events = []
    assert cli._maybe_rotate_event_file(SID, "job-a", events) is False
    assert events == []
    write_lines(cli, [idle_line(i) for i in range(30)] + [done_line(9)])
    events = []
    assert cli._maybe_rotate_event_file(SID, "job-a", events) is True
    assert len(events) == 1
    assert events[0]["signal"] == "events-rotated"
    assert events[0]["job"] == "job-a"
    assert "4 MB" in events[0]["detail"]
    # Second pass: file is small again, nothing appended.
    events2 = []
    assert cli._maybe_rotate_event_file(SID, "job-a", events2) is False
    assert events2 == []


# --- sweep composition ---------------------------------------------------------

def test_rotated_archives_compose_with_sweep_prune(tmp_path):
    """A rotated archive never matches an active job's skip name, and the
    30-day prune removes it by mtime like any old file (issue #27: the
    sweep and rotation compose rather than fight)."""
    sweep = load_script("muse_job_sweep_test", SWEEP_PATH)
    evdir = tmp_path / "events"
    evdir.mkdir()
    live = evdir / (SID + ".jsonl")
    live.write_bytes(b"x" * 100)
    archived = evdir / (SID + ".jsonl.1727745600000000000.rot")
    archived.write_bytes(b"y" * 100)
    import time
    old = time.time() - 31 * 86400
    os.utime(archived, (old, old))
    os.utime(live, (old, old))  # even the live file is old...
    skip = {SID + ".jsonl", SID + ".json"}  # ...but active jobs are skipped
    sweep.prune_old(str(evdir), 30 * 86400, skip)
    assert not archived.exists()
    assert live.exists()
    assert str(archived) in sweep.summary["pruned"]
