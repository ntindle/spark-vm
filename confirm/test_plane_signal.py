"""Tests for the golden-image plane-push signal file (GitHub #1268).

Run with:
    python3 -m pytest confirm/test_plane_signal.py -q

Covers confirm/push.py's _image_plane_signal() (root-written signal file
the swapd push worker consults when it cannot read the pairing record
itself) and its precedence inside _plane_push_owner().

No network is touched; no root needed (the IMAGE_SIGNAL_OWNER_UID
constant is monkeypatched to the test runner's uid for the positive
path).
"""
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import push  # noqa: E402


def _write_signal(tmp_path, content, mode=0o644):
    p = tmp_path / "plane-push"
    p.write_text(content)
    os.chmod(str(p), mode)
    return str(p)


def _env(monkeypatch, tmp_path, **extra):
    monkeypatch.setenv("SPARKVM_PLANE_PUSH_FILE", str(tmp_path / "plane-push"))
    monkeypatch.delenv("SPARKVM_PLANE_PUSH", raising=False)
    # Point auto-detect at an empty dir so the record path is deterministic.
    empty = tmp_path / "pairing"
    empty.mkdir(exist_ok=True)
    monkeypatch.setenv("SVM_PAIR_DIR", str(empty))
    for k, v in extra.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(push, "IMAGE_SIGNAL_OWNER_UID", os.geteuid())


def test_signal_enrolled_true(tmp_path, monkeypatch):
    _write_signal(tmp_path, "1\n")
    _env(monkeypatch, tmp_path)
    assert push._image_plane_signal() is True


def test_signal_box_local_false(tmp_path, monkeypatch):
    _write_signal(tmp_path, "0\n")
    _env(monkeypatch, tmp_path)
    assert push._image_plane_signal() is False


def test_signal_truthy_spellings(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    for word, want in (("true", True), ("YES", True), ("no", False),
                       ("False", False)):
        _write_signal(tmp_path, word + "\n")
        assert push._image_plane_signal() is want, word


def test_signal_missing_file_is_none(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    assert push._image_plane_signal() is None


def test_signal_garbage_is_none_and_warns(tmp_path, monkeypatch, caplog):
    _write_signal(tmp_path, "maybe\n")
    _env(monkeypatch, tmp_path)
    with caplog.at_level("WARNING", logger="sparkvm.push"):
        assert push._image_plane_signal() is None
    assert "unparseable" in caplog.text


def test_signal_binary_content_is_none_and_warns(tmp_path, monkeypatch,
                                                 caplog):
    # Non-UTF-8 bytes must fail open through the unparseable path, not
    # raise UnicodeDecodeError out of the reader.
    p = tmp_path / "plane-push"
    p.write_bytes(b"\xff\xfe\x001\n")
    os.chmod(str(p), 0o644)
    _env(monkeypatch, tmp_path)
    with caplog.at_level("WARNING", logger="sparkvm.push"):
        assert push._image_plane_signal() is None
    assert "unparseable" in caplog.text


def test_signal_world_writable_rejected(tmp_path, monkeypatch, caplog):
    _write_signal(tmp_path, "1\n", mode=0o666)
    _env(monkeypatch, tmp_path)
    with caplog.at_level("WARNING", logger="sparkvm.push"):
        assert push._image_plane_signal() is None
    assert "unexpected owner/mode" in caplog.text


def test_signal_group_writable_rejected(tmp_path, monkeypatch):
    _write_signal(tmp_path, "1\n", mode=0o664)
    _env(monkeypatch, tmp_path)
    assert push._image_plane_signal() is None


def test_signal_wrong_owner_rejected(tmp_path, monkeypatch):
    _write_signal(tmp_path, "1\n")
    _env(monkeypatch, tmp_path)
    other = os.geteuid() + 1 if os.geteuid() != 2 ** 31 - 1 else 0
    monkeypatch.setattr(push, "IMAGE_SIGNAL_OWNER_UID", other)
    assert push._image_plane_signal() is None


def test_signal_symlink_rejected(tmp_path, monkeypatch, caplog):
    real = _write_signal(tmp_path, "1\n")
    link = tmp_path / "plane-push-link"
    os.symlink(real, str(link))
    _env(monkeypatch, tmp_path)
    with caplog.at_level("WARNING", logger="sparkvm.push"):
        assert push._image_plane_signal(str(link)) is None
    assert "symlink" in caplog.text


def test_signal_fifo_rejected(tmp_path, monkeypatch):
    fifo = tmp_path / "plane-push"
    os.mkfifo(str(fifo))
    _env(monkeypatch, tmp_path)
    assert push._image_plane_signal() is None


def test_signal_oversized_rejected(tmp_path, monkeypatch, caplog):
    _write_signal(tmp_path, "1" * (push.SIGNAL_MAX_BYTES + 8))
    _env(monkeypatch, tmp_path)
    with caplog.at_level("WARNING", logger="sparkvm.push"):
        assert push._image_plane_signal() is None
    assert "oversized" in caplog.text


def test_signal_file_path_override(tmp_path, monkeypatch):
    alt = tmp_path / "elsewhere" / "sig"
    alt.parent.mkdir()
    alt.write_text("1\n")
    os.chmod(str(alt), 0o644)
    monkeypatch.setenv("SPARKVM_PLANE_PUSH_FILE", str(alt))
    monkeypatch.delenv("SPARKVM_PLANE_PUSH", raising=False)
    monkeypatch.setattr(push, "IMAGE_SIGNAL_OWNER_UID", os.geteuid())
    assert push._image_plane_signal() is True


def test_owner_env_wins_over_signal(tmp_path, monkeypatch):
    _write_signal(tmp_path, "0\n")  # signal says box-local...
    _env(monkeypatch, tmp_path, SPARKVM_PLANE_PUSH="1")  # ...env wins
    assert push._plane_push_owner() is True
    _write_signal(tmp_path, "1\n")
    monkeypatch.setenv("SPARKVM_PLANE_PUSH", "0")
    assert push._plane_push_owner() is False


def test_owner_signal_beats_fail_open_record(tmp_path, monkeypatch):
    # No env knob, no enrollment record (empty SVM_PAIR_DIR) — the record
    # path alone would fail open to box-local; the signal stands down.
    _write_signal(tmp_path, "1\n")
    _env(monkeypatch, tmp_path)
    assert push._plane_push_owner() is True


def test_owner_no_signal_no_record_fails_open(tmp_path, monkeypatch):
    _env(monkeypatch, tmp_path)
    assert push._plane_push_owner() is False


def test_owner_bad_env_warns_then_signal_applies(tmp_path, monkeypatch,
                                                 caplog):
    _write_signal(tmp_path, "1\n")
    _env(monkeypatch, tmp_path, SPARKVM_PLANE_PUSH="bogus")
    monkeypatch.setattr(push, "_warned_bad_plane_env", False)
    with caplog.at_level("WARNING", logger="sparkvm.push"):
        assert push._plane_push_owner() is True
    assert "bad SPARKVM_PLANE_PUSH" in caplog.text


def test_signal_read_fresh_every_check(tmp_path, monkeypatch):
    # Runtime re-readability (#1268 scope note): a later enrollment
    # propagates without a worker restart once the file is written.
    _env(monkeypatch, tmp_path)
    assert push._plane_push_owner() is False
    _write_signal(tmp_path, "1\n")
    assert push._plane_push_owner() is True


def test_signal_file_must_not_be_a_directory(tmp_path, monkeypatch):
    d = tmp_path / "plane-push"
    d.mkdir()
    _env(monkeypatch, tmp_path)
    assert push._image_plane_signal() is None
