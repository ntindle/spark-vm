"""Regression tests for issue #147.

cmd_get mapped EVERY non-zero exit of `sudo -u swapd cred-store-get` to
"credential 'x' not set" (exit 3): permission errors, I/O errors, a
broken store dir, or a sudoers denial all presented as "missing" and told
the user to overwrite a secret that may well exist. The fix keeps
"not set" (exit 3) only for a genuine ENOENT on the expected store file —
every other reader failure is loud (exit 1). Same contract as #148.
"""
import importlib.machinery
import importlib.util
import os
import sys

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "cred")


def load_script(name, path):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def cli():
    return load_script("cred_cli_gettest", CLI_PATH)


class _Proc:
    def __init__(self, returncode, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _swapd_result(monkeypatch, cli, proc):
    monkeypatch.setattr(cli, "run_as_swapd",
                        lambda argv, input_bytes=None: proc)


def test_missing_credential_is_not_set(cli, monkeypatch, capsys):
    # The one honest "not set": cat reports ENOENT on the expected path.
    err = ("cat: /home/swapd/secrets/mykey: "
           "No such file or directory\n")
    _swapd_result(monkeypatch, cli, _Proc(1, b"", err.encode()))
    assert cli.main(["get", "mykey"]) == 3
    out = capsys.readouterr()
    assert "not set" in out.err
    assert "cred set mykey" in out.err


def test_permission_denied_is_loud(cli, monkeypatch, capsys):
    # An unreadable secret must never present as "not set".
    err = ("cat: /home/swapd/secrets/mykey: Permission denied\n")
    _swapd_result(monkeypatch, cli, _Proc(1, b"", err.encode()))
    assert cli.main(["get", "mykey"]) == 1
    out = capsys.readouterr()
    assert "cred get failed" in out.err
    assert "not set" not in out.err


def test_sudoers_denial_is_loud(cli, monkeypatch, capsys):
    # A wrong sudoers entry must never present as "not set".
    err = ("Sorry, user hatch is not allowed to execute "
           "'/usr/local/bin/cred-store-get mykey' as swapd on host.\n")
    _swapd_result(monkeypatch, cli, _Proc(1, b"", err.encode()))
    assert cli.main(["get", "mykey"]) == 1
    assert "cred get failed" in capsys.readouterr().err


def test_foreign_locale_fails_closed_to_loud(cli, monkeypatch, capsys):
    # The ENOENT match is English-worded; a foreign locale must land in the
    # loud branch (safe-biased), never in "not set".
    err = ("cat: /home/swapd/secrets/mykey: Datei oder Verzeichnis nicht "
           "gefunden\n")
    _swapd_result(monkeypatch, cli, _Proc(1, b"", err.encode()))
    assert cli.main(["get", "mykey"]) == 1
    assert "cred get failed" in capsys.readouterr().err


def test_enoent_on_foreign_path_is_loud(cli, monkeypatch, capsys):
    # The ENOENT match is anchored on OUR path: another tool's
    # "No such file or directory" must not false-positive into "not set".
    err = "cat: /etc/something/else: No such file or directory\n"
    _swapd_result(monkeypatch, cli, _Proc(1, b"", err.encode()))
    assert cli.main(["get", "mykey"]) == 1
    assert "cred get failed" in capsys.readouterr().err


def test_empty_stderr_is_loud(cli, monkeypatch, capsys):
    # A bare non-zero exit with no diagnostics is still a reader failure,
    # never "not set".
    _swapd_result(monkeypatch, cli, _Proc(1, b"", b""))
    assert cli.main(["get", "mykey"]) == 1
    out = capsys.readouterr()
    assert "cred-store-get exited 1" in out.err
    assert "not set" not in out.err


def test_success_still_prints_value(cli, monkeypatch, capsys):
    # The read path is unchanged when the reader succeeds.
    _swapd_result(monkeypatch, cli, _Proc(0, b"s3cr3t-value", b""))
    assert cli.main(["get", "mykey"]) == 0
    assert capsys.readouterr().out == "s3cr3t-value"
