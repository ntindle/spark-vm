"""Tests for muse-job --version (docs/VERSIONING.md).

Run from the repo root:  python3 -m pytest muse-job/tests/test_version.py -q
"""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys

CLI_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job"))
REPO = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".."))


def load_cli():
    sys.modules.pop("muse_job_cli_version", None)
    loader = importlib.machinery.SourceFileLoader(
        "muse_job_cli_version", CLI_PATH)
    spec = importlib.util.spec_from_loader("muse_job_cli_version", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["muse_job_cli_version"] = mod
    loader.exec_module(mod)
    return mod


def _repo_version():
    with open(os.path.join(REPO, "VERSION")) as f:
        return f.read().strip()


def test_version_constant_matches_repo():
    mod = load_cli()
    assert mod.SPARKVM_VERSION == _repo_version()
    assert mod.SPARKVM_VERSION != "0.0.0-unknown"


def test_version_flag_prints_repo_version(monkeypatch, capsys):
    mod = load_cli()
    monkeypatch.setattr(sys, "argv", ["muse-job", "--version"])
    assert mod.main() == 0
    assert capsys.readouterr().out.strip() == _repo_version()


def test_version_short_flag(monkeypatch, capsys):
    mod = load_cli()
    monkeypatch.setattr(sys, "argv", ["muse-job", "-V"])
    assert mod.main() == 0
    assert capsys.readouterr().out.strip() == _repo_version()


def test_version_flag_subprocess():
    """The real entry path (python3 bin/muse-job --version) must work."""
    r = subprocess.run([sys.executable, CLI_PATH, "--version"],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == _repo_version()


def test_broken_reader_never_breaks_startup(tmp_path):
    """A syntax-broken sparkvm_version.py must not break the CLI import —
    the bootstrap's except Exception is the best-effort contract."""
    import importlib.util

    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "sparkvm_version.py").write_text("def broken(:\n")
    (repo / "VERSION").write_text("9.9.9\n")
    bin_dir = repo / "muse-job" / "bin"
    bin_dir.mkdir(parents=True)
    cli_copy = bin_dir / "muse-job"
    cli_copy.write_bytes(open(CLI_PATH, "rb").read())

    name = "muse_job_cli_broken_reader"
    sys.modules.pop(name, None)
    # Evict any cached reader: the snippet must re-import the broken file,
    # not reuse a good copy cached by an earlier test module.
    sys.modules.pop("sparkvm_version", None)
    loader = importlib.machinery.SourceFileLoader(name, str(cli_copy))
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)  # must not raise
    assert mod.SPARKVM_VERSION == "0.0.0-unknown"
