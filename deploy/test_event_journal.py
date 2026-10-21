"""Tests for deploy/event-journal.sh (issue #1649, S2 box-side event journal).

Run from the repo root:  python3 -m pytest deploy/test_event_journal.py -q
"""

import json
import os
import re
import subprocess
import uuid

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LIB = os.path.join(REPO, "deploy", "event-journal.sh")
AUTO_DEPLOY = os.path.join(REPO, "deploy", "auto-deploy.sh")


def run_bash(code, env_extra=None, cwd=REPO):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", "-c", code], cwd=cwd, env=env,
        capture_output=True, text=True, timeout=60,
    )


def emit_snippet(journal_dir, *emits, extra_env=None):
    """Source the lib with EVENT_JOURNAL pointed at a tmp dir, run emits."""
    journal = os.path.join(journal_dir, "update-events.jsonl")
    body = "; ".join(emits)
    env = {"EVENT_JOURNAL": journal}
    env.update(extra_env or {})
    # The dev environment may leak SPARKVM_BOX_ID; clear it unless the test
    # explicitly provides one, so the null-box_id assertion is deterministic.
    prefix = "" if (extra_env and "SPARKVM_BOX_ID" in extra_env) else "unset SPARKVM_BOX_ID; "
    code = prefix + f"source {LIB}; {body}"
    r = run_bash(code, env_extra=env)
    rows = []
    if os.path.exists(journal):
        with open(journal) as f:
            rows = [json.loads(line) for line in f if line.strip()]
    return r, rows


def test_lib_exists_and_is_sourced_library():
    assert os.path.exists(LIB)
    with open(LIB) as f:
        head = f.read(2000)
    assert "event_emit" in head
    assert "no main dispatcher" in head or "functions only" in head


def test_emit_writes_standard_shape_row(tmp_path):
    r, rows = emit_snippet(
        str(tmp_path),
        'event_emit auto-deploy repo deploy started ",\\"from\\":\\"abc123\\",\\"to\\":\\"def456\\""',
    )
    assert r.returncode == 0, r.stderr
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "auto-deploy"
    assert row["component"] == "repo"
    assert row["kind"] == "deploy"
    assert row["outcome"] == "started"
    assert row["from"] == "abc123" and row["to"] == "def456"
    # Fixed S2-shape fields.
    assert row["attested"] is False
    assert row["rollout"] is None
    assert row["received_at"] is None
    assert row["session_epoch"] is None
    assert row["box_id"] is None  # collector stamps from pull context (§2)
    assert row["trigger"] == "scheduled"  # §3 legacy-line default
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", row["emitted_at"])
    # UUIDv7: version nibble 7, RFC 9562 variant bits.
    eid = uuid.UUID(row["event_id"])
    assert eid.version == 7


def test_event_ids_time_ordered_and_unique(tmp_path):
    emits = [
        'event_emit auto-deploy repo deploy started ""' for _ in range(20)
    ]
    r, rows = emit_snippet(str(tmp_path), *emits)
    assert r.returncode == 0, r.stderr
    ids = [row["event_id"] for row in rows]
    assert len(set(ids)) == 20
    assert ids == sorted(ids), "UUIDv7 rows must sort in emission order"


def test_trigger_override_replaces_default(tmp_path):
    r, rows = emit_snippet(
        str(tmp_path),
        'event_emit auto-deploy repo deploy succeeded ",\\"trigger\\":\\"manual\\""',
    )
    assert r.returncode == 0, r.stderr
    assert rows[0]["trigger"] == "manual"


def test_box_id_from_env(tmp_path):
    r, rows = emit_snippet(
        str(tmp_path),
        'event_emit auto-deploy repo check noop ""',
        extra_env={"SPARKVM_BOX_ID": "tower"},
    )
    assert r.returncode == 0, r.stderr
    assert rows[0]["box_id"] == "tower"


@pytest.mark.parametrize("bad_args", [
    "bogus repo deploy started",
    "auto-deploy bogus deploy started",
    "auto-deploy repo bogus started",
    "auto-deploy repo deploy bogus",
    "auto-deploy repo deploy",  # missing outcome
])
def test_invalid_enums_fail_loud_write_nothing(tmp_path, bad_args):
    r, rows = emit_snippet(str(tmp_path), f"event_emit {bad_args}")
    # Never fails the run (set -e callers), but LOUD on stderr and writes nothing.
    assert r.returncode == 0
    assert "[event-journal] INVALID" in r.stderr
    assert rows == []


def test_gate_hook_producer_enums_accepted(tmp_path):
    # #1649 S2 slice 3: the G18 gate-hook tick is a first-class producer —
    # source=gate-hook, component=gate (the gate channel's own rows).
    r, rows = emit_snippet(
        str(tmp_path),
        'event_emit gate-hook gate gate-answer succeeded ",\\"trigger\\":\\"gate\\""',
        'event_emit gate-hook gate gate-answer skipped-frozen ",\\"trigger\\":\\"gate\\""',
    )
    assert r.returncode == 0, r.stderr
    assert "[event-journal] INVALID" not in r.stderr
    assert len(rows) == 2
    assert [row["outcome"] for row in rows] == ["succeeded", "skipped-frozen"]
    assert all(row["source"] == "gate-hook" for row in rows)
    assert all(row["component"] == "gate" for row in rows)
    assert all(row["kind"] == "gate-answer" for row in rows)
    assert all(row["trigger"] == "gate" for row in rows)


def test_unset_journal_is_silent_noop(tmp_path):
    r = run_bash(f"unset EVENT_JOURNAL; source {LIB}; event_emit auto-deploy repo deploy started")
    assert r.returncode == 0
    assert "[event-journal] INVALID" not in r.stderr


def test_unwritable_journal_never_fails_run(tmp_path):
    # Slice 5 (#1649): configured-but-unwritable is LOUD — a broken journal
    # must not read as a quiet box on the gate-consumed feed. rc stays 0
    # (set -e callers never die on a broken journal).
    r, rows = emit_snippet(
        "/proc/definitely-not-here",
        "event_emit auto-deploy repo deploy started",
    )
    assert r.returncode == 0
    assert rows == []
    assert "[event-journal] JOURNAL UNWRITABLE" in r.stderr
    assert "journal='/proc/definitely-not-here/update-events.jsonl'" in r.stderr
    assert "source=auto-deploy component=repo kind=deploy outcome=started" in r.stderr


def test_directory_as_journal_is_loud(tmp_path):
    # Appending to a directory fails — same loud contract as an unwritable path.
    r = run_bash(
        f"EVENT_JOURNAL={tmp_path}; source {LIB}; "
        "event_emit auto-deploy repo deploy started"
    )
    assert r.returncode == 0
    assert "[event-journal] JOURNAL UNWRITABLE" in r.stderr


def test_writable_journal_stays_silent(tmp_path):
    # A working journal produces no [event-journal] stderr line at all —
    # the loud note fires only on configured-but-unwritable.
    r, rows = emit_snippet(
        str(tmp_path),
        'event_emit auto-deploy repo deploy started ""',
    )
    assert r.returncode == 0, r.stderr
    assert "[event-journal]" not in r.stderr
    assert len(rows) == 1


def test_bounded_discipline(tmp_path):
    journal = os.path.join(str(tmp_path), "update-events.jsonl")
    with open(journal, "w") as f:
        for i in range(12001):
            f.write('{"event_id":"pad-%d"}\n' % i)
    r, rows = emit_snippet(
        str(tmp_path),
        'event_emit auto-deploy repo deploy started ""',
    )
    assert r.returncode == 0, r.stderr
    assert len(rows) == 10000
    # Newest row survived the trim; the journal stayed append-ordered.
    assert rows[-1]["outcome"] == "started"
    assert rows[0]["event_id"] == "pad-2002"


def test_box_id_json_escaped(tmp_path):
    r, rows = emit_snippet(
        str(tmp_path),
        'event_emit auto-deploy repo check noop ""',
        extra_env={"SPARKVM_BOX_ID": 'box"with\\quote'},
    )
    assert r.returncode == 0, r.stderr
    assert rows[0]["box_id"] == 'box"with\\quote'


def test_box_id_control_chars_escaped_round_trip(tmp_path):
    # A newline/tab/CR in an operator-set box id must not split the JSONL
    # row, and the value must round-trip exactly (JSON escapes, not silent
    # stripping — the identity is preserved).
    journal = os.path.join(str(tmp_path), "update-events.jsonl")
    original = "box\nwith\ttab and \r CR"
    r, rows = emit_snippet(
        str(tmp_path),
        'event_emit auto-deploy repo check noop ""',
        extra_env={"SPARKVM_BOX_ID": original},
    )
    assert r.returncode == 0, r.stderr
    assert rows[0]["box_id"] == original
    with open(journal, "rb") as f:
        raw_lines = [l for l in f.read().split(b"\n") if l.strip()]
    assert len(raw_lines) == 1  # still one physical line
    assert json.loads(raw_lines[0])["box_id"] == original


def test_journal_created_with_restrictive_perms(tmp_path):
    # The sink enforces 0600 on the file it creates, independent of the
    # caller's umask (the state dir must not be world-readable).
    journal = os.path.join(str(tmp_path), "update-events.jsonl")
    old_umask = os.umask(0o022)
    try:
        r, rows = emit_snippet(str(tmp_path), 'event_emit auto-deploy repo check noop ""')
    finally:
        os.umask(old_umask)
    assert r.returncode == 0, r.stderr
    assert len(rows) == 1
    assert oct(os.stat(journal).st_mode & 0o777) == "0o600"


def test_journal_append_tightens_loose_perms(tmp_path):
    # #1858: the sink tightens 0600 on the append path too — a pre-existing
    # world-readable journal (operator error, restored backup, shared
    # image) must not stay loose after an emit.
    journal = os.path.join(str(tmp_path), "update-events.jsonl")
    with open(journal, "w") as f:
        f.write("")
    os.chmod(journal, 0o644)
    assert oct(os.stat(journal).st_mode & 0o777) == "0o644"
    r, rows = emit_snippet(str(tmp_path),
                           'event_emit auto-deploy repo check noop ""')
    assert r.returncode == 0, r.stderr
    assert len(rows) == 1
    assert oct(os.stat(journal).st_mode & 0o777) == "0o600"


# --- auto-deploy.sh wiring: every outcome pivot emits a journal row --------

# (audit event, audit result fragment) -> expected (kind, outcome) in the
# journal row emitted on the line(s) following the audit call.
WIRING = [
    ("'deploy'", '"result":"deploy-fail"', "deploy", "failed"),
    ("'deploy'", '"result":"rollback-failed"', "rollback", "rollback-failed"),
    ("'deploy'", '"result":"rolled-back"', "deploy", "rolled-back"),
    ("'deploy'", '"result":"ok"', "deploy", "succeeded"),
    ("'deploy'", '"result":"snapshot-fail"', "deploy", "precheck-fail"),
    ("'deploy'", '"result":"gate-fail"', "deploy", "precheck-fail"),
    ("'deploy'", '"result":"precheck-fail"', "deploy", "precheck-fail"),
    ("'check'", '"result":"fleet-freeze"', "check", "skipped-frozen"),
    ("'check'", '"result":"wave-not-live"', "check", "skipped-frozen"),
    ("'check'", '"result":"deferred-arc"', "check", "deferred-arc"),
    ("'check'", '"result":"precheck-fail"', "check", "precheck-fail"),
]


def _emit_after_audit(lines, audit_idx):
    """Find the event_emit line belonging to the audit at lines[audit_idx]."""
    for j in range(audit_idx + 1, min(audit_idx + 4, len(lines))):
        stripped = lines[j].strip()
        if stripped.startswith("audit "):
            break  # a different audit site, not ours
        if stripped.startswith("event_emit "):
            return stripped
    return None


def test_auto_deploy_sources_journal_lib():
    with open(AUTO_DEPLOY) as f:
        src = f.read()
    assert 'source "$SCRIPT_DIR/event-journal.sh"' in src
    assert ": \"${EVENT_JOURNAL:=$UPDATER_STATE_DIR/update-events.jsonl}\"" in src


def test_cmd_init_installs_journal_lib():
    # The timer runs the INSTALLED copy ($UPDATER_STATE_DIR/bin); a top-level
    # source of event-journal.sh under set -e dies on every tick unless
    # cmd_init installs the lib (same discipline as arc_probe.sh).
    with open(AUTO_DEPLOY) as f:
        src = f.read()
    assert 'install -m 0644 "$SCRIPT_DIR/event-journal.sh" "$INSTALLED_BIN/event-journal.sh"' in src


@pytest.mark.parametrize("event,result,kind,outcome", WIRING)
def test_auto_deploy_outcome_pivots_emit(event, result, kind, outcome):
    with open(AUTO_DEPLOY) as f:
        lines = f.readlines()
    found = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("audit ") and event in line and result in line:
            emit_line = _emit_after_audit(lines, i)
            assert emit_line is not None, (
                f"audit {event} {result} at line {i+1} has no following event_emit"
            )
            assert f" {kind} {outcome} " in f" {emit_line} ", (
                f"line {i+1}: expected kind/outcome {kind}/{outcome}, got: {emit_line}"
            )
            found += 1
    assert found >= 1, f"no audit site found for {event} {result}"


def test_auto_deploy_emits_deploy_started():
    with open(AUTO_DEPLOY) as f:
        src = f.read()
    assert "event_emit auto-deploy repo deploy started" in src


def test_wired_emit_lines_are_set_e_safe():
    # Every event_emit call in auto-deploy.sh must be safe under set -e:
    # event_emit always returns 0 (invalid enums print loud + write nothing).
    with open(AUTO_DEPLOY) as f:
        lines = f.readlines()
    emit_lines = [l for l in lines if l.strip().startswith("event_emit ")]
    assert len(emit_lines) >= 12
    for line in emit_lines:
        assert "|| true" not in line, (
            "event_emit must be set-e-safe by contract, not by || true: " + line
        )
