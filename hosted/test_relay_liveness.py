#!/usr/bin/env python3
"""Tests for the relay session-liveness journal (R1, #486).

Run: ``python3 -m pytest hosted/`` from the repo root.
"""

import json
import os
import time

import pytest

import relay_liveness as rl

NOW = 1_758_000_000.0


def frame(**over):
    f = {
        "session_id": "sess-1",
        "vm_id": "vm-1",
        "opened_at": NOW - 600,
        "last_bytes_at": NOW - 10,
        "closed_at": None,
        "close_cause": None,
        "hostkey_verified": True,
        "bytes_in": 42,
        "bytes_out": 7,
    }
    f.update(over)
    return f


@pytest.fixture()
def journal(tmp_path, monkeypatch):
    path = str(tmp_path / "journal.jsonl")
    monkeypatch.setenv("RELAY_SESSION_JOURNAL", path)
    return path


# ---------------------------------------------------------------------------
# Schema validation (§2 — metadata only, never payload)


def test_valid_frame_passes():
    rl.validate_frame(frame())


def test_unknown_key_rejected_never_payload():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(payload_b64="aGVsbG8="))


def test_missing_required_rejected():
    bad = frame()
    del bad["session_id"]
    with pytest.raises(ValueError):
        rl.validate_frame(bad)


def test_bad_close_cause_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(closed_at=NOW, close_cause="mystery"))


def test_closed_requires_cause():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(closed_at=NOW, close_cause=None))


def test_open_must_not_carry_cause():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(closed_at=None, close_cause="client_closed"))


def test_negative_counter_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(bytes_in=-1))


def test_last_bytes_before_open_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(opened_at=NOW, last_bytes_at=NOW - 5))


def test_hostkey_verified_must_be_bool():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(hostkey_verified="yes"))


# ---------------------------------------------------------------------------
# Emission + prober exclusion


def test_emit_journaled(journal):
    assert rl.emit_frame(**frame()) == "journaled"
    with open(journal, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    assert len(rows) == 1
    assert rows[0]["session_id"] == "sess-1"
    assert rows[0]["vm_id"] == "vm-1"


def test_emit_invalid_frame_writes_nothing(journal):
    bad = frame()
    bad["payload"] = "x"
    with pytest.raises(ValueError):
        rl.emit_frame(**bad)
    assert not os.path.exists(journal)


def test_prober_frame_dropped_never_journaled(journal):
    assert rl.emit_frame(**frame(prober=True, session_id="probe-1")) == "dropped"
    assert not os.path.exists(journal)


def test_emit_missing_journal_dir_fails_loud(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "RELAY_SESSION_JOURNAL", str(tmp_path / "nope" / "journal.jsonl")
    )
    with pytest.raises(OSError):
        rl.emit_frame(**frame())


def test_journal_file_mode_0600(journal):
    rl.emit_frame(**frame())
    assert os.stat(journal).st_mode & 0o777 == 0o600


# ---------------------------------------------------------------------------
# Rotation — the journal's own contract (#376; unbounded = fail)


def test_rotation_bounds_total_footprint(journal, monkeypatch):
    monkeypatch.setattr(rl, "MAX_JOURNAL_BYTES", 200)
    monkeypatch.setattr(rl, "MAX_ROTATED", 2)
    for i in range(60):
        rl.emit_frame(**frame(session_id="sess-%d" % i))
    gens = [journal] + ["%s.%d" % (journal, g) for g in (1, 2)]
    assert not os.path.exists("%s.3" % journal), "generation .3 must not exist"
    total = sum(os.path.getsize(g) for g in gens if os.path.exists(g))
    assert total <= 3 * 200 + 4096, "total footprint must stay bounded"


def test_rotation_preserves_newest_frame(journal, monkeypatch):
    monkeypatch.setattr(rl, "MAX_JOURNAL_BYTES", 200)
    monkeypatch.setattr(rl, "MAX_ROTATED", 2)
    for i in range(60):
        rl.emit_frame(**frame(session_id="sess-%d" % i))
    assert rl.relay_session_liveness("vm-1", now=NOW)["session_id"] == "sess-59"


def test_rotation_evicts_oldest_frames(journal, monkeypatch):
    monkeypatch.setattr(rl, "MAX_JOURNAL_BYTES", 200)
    monkeypatch.setattr(rl, "MAX_ROTATED", 2)
    for i in range(60):
        rl.emit_frame(**frame(session_id="sess-%d" % i))
    seen = set()
    for fr, _gen in rl._iter_frames(journal):
        seen.add(fr["session_id"])
    assert "sess-0" not in seen, "oldest frames must be evicted"
    assert "sess-59" in seen


# ---------------------------------------------------------------------------
# The query surface — relay_session_liveness(vm_id)


def test_liveness_active(journal):
    rl.emit_frame(**frame())
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got == {
        "session_id": "sess-1",
        "state": "active",
        "last_bytes_at": NOW - 10,
        "hostkey_verified": True,
    }


def test_liveness_idle_past_threshold(journal):
    rl.emit_frame(**frame(last_bytes_at=NOW - 301))
    assert rl.relay_session_liveness("vm-1", now=NOW)["state"] == "idle"


def test_liveness_idle_boundary_stays_active(journal):
    rl.emit_frame(**frame(last_bytes_at=NOW - 300))
    assert rl.relay_session_liveness("vm-1", now=NOW)["state"] == "active"


def test_liveness_closed(journal):
    rl.emit_frame(
        **frame(
            opened_at=NOW - 3600,
            closed_at=NOW - 60,
            close_cause="idle_timeout",
            last_bytes_at=NOW - 61,
        )
    )
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got["state"] == "closed"


def test_liveness_hostkey_verified_surfaced(journal):
    rl.emit_frame(**frame(hostkey_verified=False))
    assert rl.relay_session_liveness("vm-1", now=NOW)["hostkey_verified"] is False


def test_liveness_newest_frame_wins(journal):
    rl.emit_frame(
        **frame(session_id="old", opened_at=NOW - 1200, last_bytes_at=NOW - 1000)
    )
    rl.emit_frame(
        **frame(session_id="new", opened_at=NOW - 600, last_bytes_at=NOW - 5)
    )
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got["session_id"] == "new"
    assert got["state"] == "active"


def test_liveness_unknown_vm_is_none(journal):
    rl.emit_frame(**frame())
    assert rl.relay_session_liveness("vm-9", now=NOW) is None


def test_liveness_missing_journal_is_none(tmp_path, monkeypatch):
    monkeypatch.setenv("RELAY_SESSION_JOURNAL", str(tmp_path / "absent.jsonl"))
    assert rl.relay_session_liveness("vm-1", now=NOW) is None


def test_liveness_missing_journal_dir_is_darkness_not_error(tmp_path, monkeypatch):
    # The module runs on machines where the journal dir was never
    # deployed (operator laptop, fresh control plane): darkness, not
    # an exception — the R3 consumer must never need to catch.
    monkeypatch.setenv(
        "RELAY_SESSION_JOURNAL", str(tmp_path / "never-deployed" / "j.jsonl")
    )
    assert rl.relay_session_liveness("vm-1", now=NOW) is None


def test_query_tolerates_non_utf8_bytes(journal):
    # A hand edit or disk-level corruption can leave undecodable bytes;
    # the "never fatal" guarantee must hold for them too.
    rl.emit_frame(**frame())
    with open(journal, "ab") as f:
        f.write(b'{"vm_id": "vm-1", "broken": \xff\xfe}\n')
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got is not None
    assert got["session_id"] == "sess-1"


def test_query_tolerates_torn_trailing_line(journal):
    rl.emit_frame(**frame())
    with open(journal, "a", encoding="utf-8") as f:
        f.write('{"session_id": "torn", "vm_id": "vm-1"')  # no newline, invalid
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got["session_id"] == "sess-1"


def test_bool_counter_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(bytes_in=True))


def test_tenant_id_must_be_str_when_present():
    with pytest.raises(ValueError):
        rl.validate_frame(frame(tenant_id=123))
    rl.validate_frame(frame(tenant_id="tenant-a"))


def test_closed_at_before_last_bytes_rejected():
    with pytest.raises(ValueError):
        rl.validate_frame(
            frame(
                closed_at=NOW - 100,
                close_cause="client_closed",
                last_bytes_at=NOW - 50,
            )
        )


def test_liveness_other_vm_frames_ignored(journal):
    rl.emit_frame(**frame(vm_id="vm-2", session_id="other"))
    got = rl.relay_session_liveness("vm-1", now=NOW)
    assert got is None
