"""Tests for cred-ui's version reporting (docs/VERSIONING.md).

Run from the repo root:  python3 -m pytest cred-ui/tests/test_cred_ui_version.py -q
"""

import importlib.util
import os
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.fixture
def _clean_reader_import():
    """Isolate the reader import: evict any cached/broken sparkvm_version and
    put the real repo scripts dir first. (Defense-in-depth: muse-job's
    broken-reader test used to leave a tmp scripts dir at sys.path[0]; it
    restores state itself now, but ordering against any other sys.path
    mutator still can't be assumed.) Restores on exit."""
    import sys as _sys
    saved_path = list(_sys.path)
    saved_mod = _sys.modules.pop("sparkvm_version", None)
    _sys.path.insert(0, os.path.join(REPO, "scripts"))
    try:
        yield
    finally:
        _sys.path[:] = saved_path
        if saved_mod is not None:
            _sys.modules["sparkvm_version"] = saved_mod
        else:
            _sys.modules.pop("sparkvm_version", None)


@pytest.fixture
def cred_ui(_clean_reader_import):
    return _load_cred_ui()


def _load_cred_ui():
    path = os.path.join(REPO, "cred-ui", "cred-ui.py")
    spec = importlib.util.spec_from_loader("credui", loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__dict__["__file__"] = path  # the bootstrap walks up from __file__
    src = open(path, encoding="utf-8").read()
    # Load the whole module (the class is named Handler, not CredHandler;
    # an older split-marker was a no-op and the full load is what these
    # tests need). main() is guarded by __name__ so nothing runs.
    code = compile(src, path, "exec")
    exec(code, mod.__dict__)
    return mod


def test_version_matches_repo_version(cred_ui):
    """cred-ui reports the single-source repo VERSION, not a copy."""
    expected = open(os.path.join(REPO, "VERSION"), encoding="utf-8").read().strip()
    assert cred_ui.SPARKVM_VERSION == expected


def test_api_version_payload_shape(cred_ui):
    """The /api/version payload has the documented service+version shape."""
    payload = {"service": "cred-ui", "version": cred_ui.SPARKVM_VERSION}
    assert set(payload) == {"service", "version"}
    assert payload["service"] == "cred-ui"
    assert payload["version"] == cred_ui.SPARKVM_VERSION
