"""Tests for the bounded stdin read in the `cred` CLI (issue #149).

`cred set` pipes the secret to the swapd writer, which refuses values over
64 KiB — but the frontend used to `sys.stdin.read()` unbounded *before* the
writer ever saw the value, so a huge pipe ballooned the CLI's memory. The
frontend now reads at most 64 KiB + a 2-byte chomp margin + 1 sentinel byte
from stdin and refuses oversized input itself, with a byte (not character)
cap so multibyte UTF-8 can't slip past.

Run from the repo root:  python3 -m pytest credlib/test_cred_stdin_cap.py -q
"""

import importlib.util
import io
import os

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_cred():
    path = os.path.join(REPO, "cred")
    spec = importlib.util.spec_from_loader("cred_cli", loader=None)
    mod = importlib.util.module_from_spec(spec)
    src = open(path, encoding="utf-8").read()
    code = compile(src, path, "exec")
    exec(code, mod.__dict__)  # main() is __name__-guarded; nothing runs
    return mod


@pytest.fixture(scope="module")
def cred():
    return _load_cred()


def _piped_stdin(cred, data: bytes, monkeypatch):
    """Replace sys.stdin with a piped reader carrying `data` (binary)."""
    bio = io.BytesIO(data)
    fake = io.TextIOWrapper(bio, encoding="utf-8")
    monkeypatch.setattr(cred.sys, "stdin", fake)
    return bio


def test_cap_matches_writer(cred):
    # The frontend cap must mirror cred-store-set's max_bytes=65536 exactly.
    assert cred.SECRET_MAX_BYTES == 65536


def test_small_secret_chomps_one_newline(cred, monkeypatch):
    _piped_stdin(cred, b"hunter2\n", monkeypatch)
    assert cred.read_secret_stdin() == "hunter2"


def test_crlf_chomped(cred, monkeypatch):
    _piped_stdin(cred, b"hunter2\r\n", monkeypatch)
    assert cred.read_secret_stdin() == "hunter2"


def test_no_trailing_newline_returned_verbatim(cred, monkeypatch):
    _piped_stdin(cred, b"hunter2", monkeypatch)
    assert cred.read_secret_stdin() == "hunter2"


def test_interior_newlines_untouched(cred, monkeypatch):
    _piped_stdin(cred, b"line1\nline2\n\n", monkeypatch)
    assert cred.read_secret_stdin() == "line1\nline2\n"


def test_empty_stdin_returns_empty(cred, monkeypatch):
    _piped_stdin(cred, b"", monkeypatch)
    assert cred.read_secret_stdin() == ""


def test_huge_input_refused_without_ballooning(cred, monkeypatch):
    # 10 MiB on stdin: the old unbounded read would have buffered all of it.
    bio = _piped_stdin(cred, b"x" * (10 * 1024 * 1024), monkeypatch)
    with pytest.raises(cred.CredentialError, match="64 KiB"):
        cred.read_secret_stdin()
    # The reader pulled at most cap + 2-byte chomp margin + 1 sentinel byte.
    assert bio.tell() <= cred.SECRET_MAX_BYTES + 3


def test_exactly_cap_plus_newline_accepted(cred, monkeypatch):
    _piped_stdin(cred, b"s" * 65536 + b"\n", monkeypatch)
    assert cred.read_secret_stdin() == "s" * 65536


def test_exactly_cap_plus_crlf_accepted(cred, monkeypatch):
    _piped_stdin(cred, b"s" * 65536 + b"\r\n", monkeypatch)
    assert cred.read_secret_stdin() == "s" * 65536


def test_one_byte_over_cap_refused(cred, monkeypatch):
    _piped_stdin(cred, b"s" * 65537, monkeypatch)
    with pytest.raises(cred.CredentialError, match="64 KiB"):
        cred.read_secret_stdin()


def test_one_byte_over_cap_after_chomp_refused(cred, monkeypatch):
    # 65537 content bytes + the chomped newline: writer would refuse too.
    _piped_stdin(cred, b"s" * 65537 + b"\n", monkeypatch)
    with pytest.raises(cred.CredentialError, match="64 KiB"):
        cred.read_secret_stdin()


def test_byte_not_character_cap(cred, monkeypatch):
    # 65536 bytes of 2-byte UTF-8 = 32768 characters: a character cap would
    # wrongly accept this at "half the cap"; the byte cap accepts it for the
    # right reason (it is exactly 64 KiB of bytes).
    _piped_stdin(cred, "é".encode("utf-8") * 32768 + b"\n", monkeypatch)
    assert cred.read_secret_stdin() == "é" * 32768


def test_multibyte_over_cap_refused(cred, monkeypatch):
    # 65538 bytes of UTF-8: over the cap even though only 32769 characters.
    _piped_stdin(cred, "é".encode("utf-8") * 32769, monkeypatch)
    with pytest.raises(cred.CredentialError, match="64 KiB"):
        cred.read_secret_stdin()


def test_invalid_utf8_stdin_raises_unicode_decode_error(cred, monkeypatch):
    # Invalid UTF-8 is rejected by the strict decode — the pre-#149 code read
    # sys.stdin in text mode, which raises UnicodeDecodeError the same way;
    # the bounded byte-read preserves that behavior instead of replacing or
    # mangling undecodable bytes (QA-verified identical on the #149 review).
    _piped_stdin(cred, b"hunter2\xff\xfe\n", monkeypatch)
    with pytest.raises(UnicodeDecodeError):
        cred.read_secret_stdin()
