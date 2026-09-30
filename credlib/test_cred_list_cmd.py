"""Regression tests for issue #148.

cmd_list treated ANY non-zero exit of `sudo -u swapd /usr/bin/ls <store>`
as "missing/empty store" (silent, exit 0): a wrong sudoers entry, an
unreadable store dir, or a failing ls all presented as "you have no
credentials" instead of an error. The fix distinguishes ENOENT on the
store path (silent, exit 0) from every other failure (loud, exit 1).
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
    return load_script("cred_cli_listtest", CLI_PATH)


class _Proc:
    def __init__(self, returncode, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _swapd_result(monkeypatch, cli, proc):
    monkeypatch.setattr(cli, "run_as_swapd",
                        lambda argv, input_bytes=None: proc)


def test_missing_store_is_silent(cli, monkeypatch, capsys):
    # First-run state: no store dir yet -> no output, exit 0.
    err = ("ls: cannot access '/home/swapd/secrets': "
           "No such file or directory\n")
    _swapd_result(monkeypatch, cli, _Proc(2, b"", err.encode()))
    assert cli.main(["list"]) == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""


def test_permission_denied_is_loud(cli, monkeypatch, capsys):
    # An unreadable store must never present as "no credentials".
    err = ("ls: cannot open directory '/home/swapd/secrets': "
           "Permission denied\n")
    _swapd_result(monkeypatch, cli, _Proc(2, b"", err.encode()))
    assert cli.main(["list"]) == 1
    assert "cred list failed" in capsys.readouterr().err


def test_sudoers_denial_is_loud(cli, monkeypatch, capsys):
    # A wrong sudoers entry must never present as "no credentials".
    err = ("Sorry, user hatch is not allowed to execute "
           "'/usr/bin/ls /home/swapd/secrets' as swapd on host.\n")
    _swapd_result(monkeypatch, cli, _Proc(1, b"", err.encode()))
    assert cli.main(["list"]) == 1
    assert "cred list failed" in capsys.readouterr().err


def test_foreign_locale_fails_closed_to_loud(cli, monkeypatch, capsys):
    # The ENOENT match is English-worded; a foreign locale must land in the
    # loud branch (safe-biased), never in the silent one.
    err = ("ls: Zugriff auf '/home/swapd/secrets' nicht möglich: "
           "Datei oder Verzeichnis nicht gefunden\n")
    _swapd_result(monkeypatch, cli, _Proc(2, b"", err.encode()))
    assert cli.main(["list"]) == 1
    assert "cred list failed" in capsys.readouterr().err


def test_success_prints_names(cli, monkeypatch, capsys):
    _swapd_result(monkeypatch, cli, _Proc(0, b"alpha\nbeta\n", b""))
    assert cli.main(["list"]) == 0
    assert capsys.readouterr().out == "alpha\nbeta\n"


def test_extra_args_rejected(cli, capsys):
    assert cli.main(["list", "extra"]) == 1
    assert "usage: cred list" in capsys.readouterr().err
