"""Tests for issue #27: manager-owned hook event-file rotation.

Covers rotate_event_file + _maybe_rotate_event_file in bin/muse-job:

  - The trigger is size only, evaluated by the manager. Hooks never call
    it; the agent's only lever is appending lines.
  - Terminal `done` claims are re-seeded byte-identical into the head of
    the fresh file, so a rotated-out genuine done keeps paging every pass
    instead of becoming a silent burial (the #23 B1/B3 class).
  - Rename-based atomicity w.r.t. concurrent O_APPEND hook writes: a hook
    that opened its fd before the rename lands in the archive, one that
    opens after lands in the fresh file -- every non-done line in exactly
    one file, never lost, never duplicated (dones are intentionally in
    both: archive + re-seeded fresh, fail-loud).
  - Straggler tail sweep: a hook that opened pre-rename but wrote during
    extraction is re-seeded from the archive tail -- the no-burial
    invariant (every done in any archive is also in the live file) is
    pinned deterministically.
  - Fail-closed refusals: symlinked event file, symlinked EVENTS_DIR,
    malformed uuid, missing file; restore-on-failure (including
    post-rename open/write failures) leaves the original byte-identical.
  - The watch pass itself emits `events-rotated` (end-to-end test through
    cmd_watch, not just the helper).
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
    """Hook-style appends racing rotations: every appended non-done line
    appears exactly once across all files (loss AND duplication both fail
    this test -- the written set is recorded per worker); every done
    surfaces at least once (fail-loud re-seeding may duplicate dones)."""
    cli = small_threshold
    stop = threading.Event()
    errors = []
    written = set()
    written_lock = threading.Lock()

    def worker(base):
        try:
            i = 0
            while not stop.is_set():
                line = idle_line(base + i)
                hook_append(cli, line)
                with written_lock:
                    written.add(("idle", base + i))
                if i % 10 == 0:
                    dline = done_line(base + i)
                    hook_append(cli, dline)
                    with written_lock:
                        written.add(("done", base + i))
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

    from collections import Counter
    seen = Counter()
    done_seen = set()
    for p in all_event_files(cli):
        for raw in read_lines(p):
            obj = json.loads(raw)
            key = (obj["state"], obj["turn_id"])
            if obj["state"] == "done":
                done_seen.add(key)
            else:
                seen[key] += 1
    assert seen, "no lines survived the rotation storm"
    # Multiset equality against the recorded written set: a lost line is a
    # missing key, a duplicated line is a count of 2.
    assert seen == Counter({k: 1 for k in written if k[0] == "idle"}), \
        "a non-done line was lost or duplicated"
    written_dones = {k for k in written if k[0] == "done"}
    assert written_dones, "no dones were appended"
    assert written_dones <= done_seen, "a done claim vanished entirely"


def test_no_done_buried_in_archives(small_threshold, monkeypatch):
    """The no-burial invariant, pinned deterministically: every done line
    present in any archive must also be present in the live file.

    Simulates the straggler race -- a hook that opened its fd before the
    rename and lands its done in the archive after the initial extraction
    passed -- and asserts the tail sweep re-seeds it."""
    cli = small_threshold
    write_over_threshold(cli, [done_line(0), idle_line(1)])
    late = done_line(777)
    real_extract = cli._done_lines_of

    def extract_then_race(path, start=0):
        lines, end = real_extract(path, start)
        if start == 0:
            # Pre-rename fd, post-extraction write: lands in the archive
            # after the read cursor passed.
            with open(path, "ab") as f:
                f.write(late + b"\n")
        return lines, end

    monkeypatch.setattr(cli, "_done_lines_of", extract_then_race)
    assert cli.rotate_event_file(SID) is True
    live = read_lines(event_path(cli))
    assert late.rstrip(b"\n") in live
    # The full invariant over every archive on disk.
    live_set = set(live)
    for p in all_event_files(cli):
        if p == event_path(cli):
            continue
        for raw in read_lines(p):
            try:
                obj = json.loads(raw)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("state") == "done":
                assert raw in live_set, \
                    "done buried in archive %s" % os.path.basename(p)


def test_mid_line_fragment_at_cutoff_reseeded(small_threshold, monkeypatch):
    """A hook caught mid-write at the initial extraction's EOF leaves a
    trailing fragment; the cursor backs up and the tail sweep re-seeds the
    completed line (not skipped as malformed)."""
    cli = small_threshold
    filler = write_over_threshold(cli, [done_line(0)])
    real_extract = cli._done_lines_of
    late = done_line(888)
    state = {"torn": True}

    def extract_then_torn(path, start=0):
        lines, end = real_extract(path, start)
        if start == 0 and state["torn"]:
            state["torn"] = False
            # Append a PARTIAL line (no trailing newline): torn write.
            with open(path, "ab") as f:
                f.write(late[: len(late) // 2])
            # Complete it before the tail sweep runs, as a real
            # write() would within microseconds.
            with open(path, "ab") as f:
                f.write(late[len(late) // 2:] + b"\n")
        return lines, end

    monkeypatch.setattr(cli, "_done_lines_of", extract_then_torn)
    assert cli.rotate_event_file(SID) is True
    assert late.rstrip(b"\n") in read_lines(event_path(cli))


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
                        lambda path, start=0: (_ for _ in ()).throw(OSError("boom")))
    assert cli.rotate_event_file(SID) is False
    assert all_event_files(cli) == [event_path(cli)]
    assert read_lines(event_path(cli)) == [l.rstrip(b"\n") for l in lines]


def test_exact_threshold_does_not_rotate(small_threshold):
    """The trigger is strictly greater-than: a file exactly at the
    threshold is left alone (boundary pin)."""
    cli = small_threshold
    filler = []
    size = 0
    i = 0
    while size < cli._EVENT_ROTATE_BYTES:
        line = idle_line(7000 + i)
        filler.append(line)
        size += len(line) + 1
        i += 1
    # Trim or pad the last line so the file is EXACTLY the threshold.
    data = b"".join(l + b"\n" for l in filler)
    data = data[:cli._EVENT_ROTATE_BYTES]
    assert len(data) == cli._EVENT_ROTATE_BYTES
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    with open(event_path(cli), "wb") as f:
        f.write(data)
    assert cli.rotate_event_file(SID) is False
    assert all_event_files(cli) == [event_path(cli)]


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
    assert cli._rotate_threshold_label() in events[0]["detail"]
    # Second pass: file is small again, nothing appended.
    events2 = []
    assert cli._maybe_rotate_event_file(SID, "job-a", events2) is False
    assert events2 == []


def test_rotate_threshold_label_and_coupling(tmp_path, monkeypatch):
    """The threshold is 2x the scan window by construction (not a magic
    literal), and the operator-facing label renders from the constant so a
    threshold change can't silently lie in the signal text."""
    monkeypatch.setenv("HOME", str(tmp_path))
    mod = load_script("muse_job_rotate_label", CLI_PATH)
    assert mod._EVENT_ROTATE_BYTES == 2 * mod._EVENT_SCAN_MAX_BYTES
    assert mod._rotate_threshold_label() == "4 MB"


# --- watch-pass end-to-end -----------------------------------------------------

def test_watch_pass_emits_events_rotated(small_threshold, monkeypatch, capsys):
    """End to end through cmd_watch (not just the helper): a job whose
    event file exceeds the threshold gets exactly one `events-rotated`
    signal carrying the job key. Deleting the wiring in cmd_watch breaks
    this test; the helper-level contract test above does not."""
    import argparse
    import time
    cli = small_threshold
    slug = "rot-e2e"
    jd = os.path.join(cli.JOBS_DIR, slug)
    os.makedirs(jd, exist_ok=True)
    sid = "rote2esid01"
    job = {"slug": slug, "state": "active", "budget_hours": 8,
           "started_at": time.time() - 60,
           "session_uuid": sid,
           "session_started_at": time.time() - 60}
    with open(os.path.join(jd, "job.json"), "w") as f:
        json.dump(job, f)
    now = time.time()
    os.makedirs(cli.EVENTS_DIR, exist_ok=True)
    with open(os.path.join(cli.EVENTS_DIR, sid + ".jsonl"), "wb") as f:
        for i in range(30):
            evt = {"ts": now - 10 + i, "event": "stop", "session_id": sid,
                   "state": "idle", "detail": "e%d" % i, "cwd": "/w",
                   "turn_id": i}
            f.write(json.dumps(evt).encode() + b"\n")
        done = {"ts": now, "event": "stop", "session_id": sid,
                "state": "done", "detail": "e2e-done", "cwd": "/w",
                "turn_id": 999}
        f.write(json.dumps(done).encode() + b"\n")
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: True)
    cli.cmd_watch(argparse.Namespace())
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines()
             if l.strip()]
    rotated = [e for e in lines if e.get("signal") == "events-rotated"]
    assert len(rotated) == 1
    assert rotated[0]["job"] == slug
    assert cli._rotate_threshold_label() in rotated[0]["detail"]
    # The done claim survived into the fresh file and still triages.
    dones = cli.done_events(sid, now + 1)
    assert len(dones) == 1 and dones[0][0]["detail"] == "e2e-done"


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
