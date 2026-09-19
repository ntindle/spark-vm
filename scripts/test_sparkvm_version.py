"""Tests for scripts/sparkvm_version.py.

Run from the repo root:  python3 -m pytest scripts/test_sparkvm_version.py -q
"""

import os
import subprocess
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from sparkvm_version import (  # noqa: E402
    UNKNOWN,
    find_version_file,
    sparkvm_version,
    sparkvm_version_strict,
)


def test_repo_version_is_valid_semver():
    v = sparkvm_version_strict(REPO)
    assert v == open(os.path.join(REPO, "VERSION")).read().strip()
    assert v != UNKNOWN


def test_walk_up_finds_repo_version_from_deep_dir(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    # A VERSION placed two levels up is found from the deep dir.
    (tmp_path / "VERSION").write_text("1.2.3\n")
    assert find_version_file(str(deep)) == str(tmp_path / "VERSION")
    assert sparkvm_version(str(deep)) == "1.2.3"


def test_missing_version_returns_unknown(tmp_path):
    assert sparkvm_version(str(tmp_path)) == UNKNOWN


def test_invalid_version_returns_unknown(tmp_path):
    (tmp_path / "VERSION").write_text("not-a-version\n")
    assert sparkvm_version(str(tmp_path)) == UNKNOWN
    with pytest.raises(ValueError):
        sparkvm_version_strict(str(tmp_path))


@pytest.mark.parametrize("bad", ["1.2", "1.2.3.4", "v1.2.3", "01.2.3", "1.2.3-", ""])
def test_strict_rejects_non_semver(tmp_path, bad):
    (tmp_path / "VERSION").write_text(bad + "\n")
    assert sparkvm_version(str(tmp_path)) == UNKNOWN
    with pytest.raises(ValueError):
        sparkvm_version_strict(str(tmp_path))


@pytest.mark.parametrize("good", ["0.1.0", "1.0.0-rc.1", "2.3.4+build.5", "10.20.30"])
def test_strict_accepts_semver(tmp_path, good):
    (tmp_path / "VERSION").write_text("  %s  \n" % good)  # whitespace tolerated
    assert sparkvm_version_strict(str(tmp_path)) == good


def test_cli_check_passes_on_repo():
    r = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "sparkvm_version.py"),
         "--check"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == sparkvm_version_strict(REPO)


def test_cli_check_fails_on_bad_version(monkeypatch):
    import sparkvm_version as sv

    def _bad(start=None):
        raise ValueError("bogus")

    monkeypatch.setattr(sv, "sparkvm_version_strict", _bad)
    assert sv.main(["--check"]) == 1
