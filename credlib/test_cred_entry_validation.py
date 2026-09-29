"""Tests for reserved-entry-name rejection in the `cred` CLI (issue #675).

The narrow writer (proxy/cred-registry-set) guards RESERVED_ENTRIES =
("allowed_hosts", "allowed_methods", "allowed_paths", "grants") on both
its creation path (check_entry, finding 34b) and its legacy management
path (check_entry_legacy). The CLI must reject them up front too (#150:
no frontend-accepts / writer-rejects drift) — `cred register --entry
allowed_hosts` used to pass the CLI and die at the writer, and
`cred unregister --entry grants` used to pass the legacy gate while the
writer's check_entry_legacy rejected it.

Run from the repo root:  python3 -m pytest credlib/test_cred_entry_validation.py -q
"""

import importlib.util
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


cred = _load_cred()

RESERVED = ("allowed_hosts", "allowed_methods", "allowed_paths", "grants")


@pytest.mark.parametrize("name", RESERVED)
def test_check_entry_rejects_reserved(name):
    """Creation path: reserved entry names die in the CLI, not the writer."""
    with pytest.raises(cred.CredentialError):
        cred.check_entry(name)


def test_check_entry_accepts_ordinary_names():
    assert cred.check_entry("access_token") == "access_token"
    assert cred.check_entry("a" * 64) == "a" * 64


@pytest.mark.parametrize("name", RESERVED)
def test_check_entry_legacy_rejects_reserved(name):
    """Management path mirrors the writer's check_entry_legacy (finding 34b)."""
    with pytest.raises(cred.CredentialError):
        cred.check_entry_legacy(name)


def test_check_entry_legacy_still_tolerates_long_names():
    """Legacy tolerance is charset-only: a pre-#150 long name stays usable."""
    long_name = "n" * 100
    assert cred.check_entry_legacy(long_name) == long_name


def _never_called(*args, **kwargs):
    raise AssertionError("writer must not be invoked for a reserved entry")


def test_cmd_register_rejects_reserved_before_writer(monkeypatch):
    """`cred register x --entry grants` fails before any sudo writer call."""
    monkeypatch.setattr(cred, "run_as_swapd", _never_called)
    with pytest.raises(cred.CredentialError, match="reserved"):
        cred.cmd_register(["x", "--entry", "grants"])


def test_cmd_unregister_rejects_reserved_before_writer(monkeypatch):
    """`cred unregister x --entry allowed_hosts` fails before any sudo call."""
    monkeypatch.setattr(cred, "run_as_swapd", _never_called)
    with pytest.raises(cred.CredentialError, match="reserved"):
        cred.cmd_unregister(["x", "--entry", "allowed_hosts"])
