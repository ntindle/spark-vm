"""Tests for cred-ui/install.sh (issue #85).

The credential web UI must not run from the working checkout: install.sh
copies the runtime set into a fixed install directory (and the systemd user
unit alongside it), failing closed before any mutation when a source file
is missing.

Run from the repo root:  python3 -m pytest cred-ui/tests/test_cred_ui_install.py -q
"""

import os
import re
import shutil
import subprocess
import sys

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

RUNTIME_FILES = [
    "cred-ui.py",
    "index.html",
    "credvalidate.py",
    "bounded_http.py",
    "sparkvm_version.py",
    "VERSION",
]

REPO_SOURCES = {
    "cred-ui.py": os.path.join("cred-ui", "cred-ui.py"),
    "index.html": os.path.join("cred-ui", "index.html"),
    "credvalidate.py": os.path.join("credlib", "credvalidate.py"),
    "bounded_http.py": os.path.join("scripts", "bounded_http.py"),
    "sparkvm_version.py": os.path.join("scripts", "sparkvm_version.py"),
    "VERSION": "VERSION",
}


def _run_install(repo_root, install_dir, unit_dir, extra_env=None):
    env = dict(os.environ)
    env["CRED_UI_INSTALL_DIR"] = str(install_dir)
    env["SYSTEMD_USER_DIR"] = str(unit_dir)
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", os.path.join(repo_root, "cred-ui", "install.sh")],
        capture_output=True, text=True, timeout=60, env=env,
    )


def test_install_populates_fixed_location(tmp_path):
    """install.sh lands the whole runtime set + unit, byte-identical."""
    install_dir = tmp_path / "install"
    unit_dir = tmp_path / "units"
    r = _run_install(REPO, install_dir, unit_dir)
    assert r.returncode == 0, r.stderr + r.stdout
    for name in RUNTIME_FILES:
        got = install_dir / name
        assert got.is_file(), "missing installed file: %s" % name
        want = open(os.path.join(REPO, REPO_SOURCES[name]), "rb").read()
        assert got.read_bytes() == want, "content drift: %s" % name
    unit = unit_dir / "cred-ui.service"
    assert unit.is_file(), "unit not installed"
    assert unit.read_bytes() == open(
        os.path.join(REPO, "cred-ui", "cred-ui.service"), "rb").read()


def test_install_fails_closed_on_missing_file(tmp_path):
    """A partial repo aborts with no mutation — the install dir is not
    even created. Non-vacuous: the full tree installs cleanly (above)."""
    fake = tmp_path / "fakerepo"
    for src in list(REPO_SOURCES.values()) + [
            os.path.join("cred-ui", "install.sh"),
            os.path.join("cred-ui", "cred-ui.service")]:
        if src == os.path.join("cred-ui", "index.html"):
            continue  # the pruned file
        dst = fake / src
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(REPO, src), dst)
    install_dir = tmp_path / "install"
    unit_dir = tmp_path / "units"
    r = _run_install(str(fake), install_dir, unit_dir)
    assert r.returncode != 0, "install succeeded on a pruned repo"
    assert "index.html" in r.stderr, r.stderr
    assert not install_dir.exists(), "install dir created despite failure"
    assert not unit_dir.exists(), "unit dir created despite failure"


def test_install_fails_closed_on_syntax_error(tmp_path):
    """The in-memory syntax gate must abort the install before any
    mutation when a shipped .py file does not compile."""
    fake = tmp_path / "fakerepo"
    for src in list(REPO_SOURCES.values()) + [
            os.path.join("cred-ui", "install.sh"),
            os.path.join("cred-ui", "cred-ui.service")]:
        dst = fake / src
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(REPO, src), dst)
    (fake / "scripts" / "bounded_http.py").write_text("def broken(:\n")
    install_dir = tmp_path / "install"
    r = _run_install(str(fake), install_dir, tmp_path / "units")
    assert r.returncode != 0, "install accepted a syntactically broken helper"
    assert "syntax check failed" in r.stderr, r.stderr
    assert not install_dir.exists(), "install dir created despite failure"


def test_install_rejects_unparseable_version(tmp_path):
    """VERSION is the deployed UI's version stamp — an unparseable one
    must fail the install, not ship a UI that reports 0.0.0-unknown."""
    fake = tmp_path / "fakerepo"
    for src in list(REPO_SOURCES.values()) + [
            os.path.join("cred-ui", "install.sh"),
            os.path.join("cred-ui", "cred-ui.service")]:
        dst = fake / src
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(REPO, src), dst)
    (fake / "VERSION").write_text("not-a-version\n")
    r = _run_install(str(fake), tmp_path / "install", tmp_path / "units")
    assert r.returncode != 0, "install accepted an unparseable VERSION"
    assert not (tmp_path / "install").exists()


def test_installed_copy_reports_shipped_version(tmp_path):
    """The installed cred-ui.py resolves the shipped VERSION walking up
    from the install dir (docs/VERSIONING.md) — the version-only deploy
    path depends on this, since nothing is synced from the checkout."""
    install_dir = tmp_path / "install"
    unit_dir = tmp_path / "units"
    r = _run_install(REPO, install_dir, unit_dir)
    assert r.returncode == 0, r.stderr + r.stdout
    probe = (
        "import importlib.util, sys;"
        "path = sys.argv[1];"
        "spec = importlib.util.spec_from_loader('credui_installed', loader=None);"
        "mod = importlib.util.module_from_spec(spec);"
        "mod.__dict__['__file__'] = path;"
        "exec(compile(open(path, encoding='utf-8').read(), path, 'exec'), mod.__dict__);"
        "print(mod.SPARKVM_VERSION)"
    )
    r2 = subprocess.run(
        [sys.executable, "-c", probe, str(install_dir / "cred-ui.py")],
        capture_output=True, text=True, timeout=60,
        # Hermetic: the installed copy must resolve its helpers from the
        # install dir itself, not from the repo checkout on sys.path.
        env={"PATH": os.environ["PATH"]},
    )
    assert r2.returncode == 0, r2.stderr
    want = open(os.path.join(REPO, "VERSION"), encoding="utf-8").read().strip()
    assert r2.stdout.strip() == want, \
        "installed copy reports %r, want shipped VERSION %r" % (
            r2.stdout.strip(), want)
    assert want != "0.0.0-unknown"


def test_installed_copy_prefers_own_helpers(tmp_path):
    """Security NB4: the install dir is self-contained — its own helpers
    must win over a ../scripts shadow, so nothing outside the install dir
    can substitute the server the UI runs. The same holds for the shared
    validation contract (issue #706): a ../credlib shadow must not win
    over the staged copy."""
    install_dir = tmp_path / "install"
    unit_dir = tmp_path / "units"
    r = _run_install(REPO, install_dir, unit_dir)
    assert r.returncode == 0, r.stderr + r.stdout
    # Shadows at the old checkout-relative lookup locations.
    shadow = install_dir.parent / "scripts"
    shadow.mkdir()
    (shadow / "bounded_http.py").write_text("SHADOW_MARKER = True\n")
    credlib_shadow = install_dir.parent / "credlib"
    credlib_shadow.mkdir()
    (credlib_shadow / "credvalidate.py").write_text("SHADOW_MARKER = True\n")
    probe = (
        "import importlib.util, sys;"
        "path = sys.argv[1];"
        "spec = importlib.util.spec_from_loader('credui_shadow', loader=None);"
        "mod = importlib.util.module_from_spec(spec);"
        "mod.__dict__['__file__'] = path;"
        "exec(compile(open(path, encoding='utf-8').read(), path, 'exec'), mod.__dict__);"
        "import bounded_http;"
        "import credvalidate;"
        "print(bounded_http.__file__);"
        "print(credvalidate.__file__)"
    )
    r2 = subprocess.run(
        [sys.executable, "-c", probe, str(install_dir / "cred-ui.py")],
        capture_output=True, text=True, timeout=60,
        env={"PATH": os.environ["PATH"]},
    )
    assert r2.returncode == 0, r2.stderr
    lines = r2.stdout.strip().splitlines()
    assert lines[0] == str(install_dir / "bounded_http.py"), \
        "shadow ../scripts/bounded_http.py took precedence: %s" % lines[0]
    assert lines[1] == str(install_dir / "credvalidate.py"), \
        "shadow ../credlib/credvalidate.py took precedence: %s" % lines[1]


def test_install_mid_copy_failure_leaves_live_set_untouched(tmp_path):
    """A failure DURING the copy phase (after every gate passed) must not
    mutate the live install. The old direct-copy implementation wrote
    straight into the live dir with `cp --remove-destination`, which unlinks
    the live destination BEFORE reading the source — so an unreadable source
    mid-copy deleted the live file outright (and replaced earlier ones). The
    staged install assembles everything before publishing, so the live set
    stays byte-identical. Non-vacuous: against a direct-copy install.sh this
    test fails — the live index.html is gone when the unreadable source
    aborts the copy."""
    # Permission-based unreadability is invisible to root (root bypasses
    # file permission checks), so this test needs a non-root invoker —
    # the same guard the harness install-gate suite uses. CI and the
    # post-ship venv run non-root, where the pin holds.
    if os.geteuid() == 0:
        pytest.skip("needs a non-root invoker: root reads 000 files")
    install_dir = tmp_path / "install"
    unit_dir = tmp_path / "units"
    r = _run_install(REPO, install_dir, unit_dir)
    assert r.returncode == 0, r.stderr + r.stdout
    # Sentinel: the live set we must not disturb.
    sentinels = {p: p.read_bytes() for p in install_dir.iterdir()}
    assert len(sentinels) == 5, "expected the 5 runtime files, got %s" % (
        sorted(p.name for p in sentinels),)
    # A fake repo whose sources pass every gate but fail mid-copy:
    # index.html is presence-checked yet never syntax-checked or parsed,
    # so an unreadable index.html aborts the copy after the staged set is
    # otherwise complete.
    fake = tmp_path / "fakerepo"
    for src in list(REPO_SOURCES.values()) + [
            os.path.join("cred-ui", "install.sh"),
            os.path.join("cred-ui", "cred-ui.service")]:
        dst = fake / src
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(os.path.join(REPO, src), dst)
    (fake / "cred-ui" / "index.html").chmod(0o000)
    try:
        r = _run_install(str(fake), install_dir, unit_dir)
    finally:
        (fake / "cred-ui" / "index.html").chmod(0o644)
    assert r.returncode != 0, "install succeeded with an unreadable source"
    for p, want in sentinels.items():
        assert p.read_bytes() == want, \
            "live file mutated on failed install: %s" % p.name
    # No staging residue next to the install dir.
    leftovers = [p for p in install_dir.parent.iterdir()
                 if p.name.startswith(install_dir.name + ".staging.")]
    assert not leftovers, "staging residue: %s" % leftovers


def test_install_leaves_no_staging_residue_on_success(tmp_path):
    """A successful install leaves no staging directory behind: the
    install dir holds exactly the runtime set, and nothing staging-shaped
    sits next to it."""
    install_dir = tmp_path / "install"
    unit_dir = tmp_path / "units"
    r = _run_install(REPO, install_dir, unit_dir)
    assert r.returncode == 0, r.stderr + r.stdout
    assert sorted(p.name for p in install_dir.iterdir()) == sorted(RUNTIME_FILES)
    leftovers = [p for p in install_dir.parent.iterdir()
                 if p.name.startswith(install_dir.name + ".staging.")]
    assert not leftovers, "staging residue: %s" % leftovers


def test_install_publish_failure_is_recoverable_by_rerun(tmp_path):
    """The publish loop is the mechanism behind the no-partial-file claim,
    and the script promises recovery ("re-run install.sh to complete")
    when publication fails mid-way. Pin both: a publish-phase failure must
    exit nonzero naming the re-run, and the re-run must complete the
    install. Non-vacuous: without the per-file publish loop there is no
    mid-publish failure mode to recover from — and the re-run half fails if
    publication is not idempotent."""
    # Permission-based failure needs a non-root invoker (same guard as the
    # mid-copy test: root bypasses directory permission checks).
    if os.geteuid() == 0:
        pytest.skip("needs a non-root invoker: root writes through 555 dirs")
    install_dir = tmp_path / "install"
    unit_dir = tmp_path / "units"
    unit_dir.mkdir()
    # The unit publish fails (unwritable dir); the 5 runtime publishes
    # succeed — the documented mixed state: new runtime, unit pending.
    unit_dir.chmod(0o555)
    try:
        r = _run_install(REPO, install_dir, unit_dir)
    finally:
        unit_dir.chmod(0o755)
    assert r.returncode != 0, "install succeeded with an unwritable unit dir"
    assert "re-run" in r.stderr, r.stderr
    for name in RUNTIME_FILES:
        got = install_dir / name
        assert got.is_file(), \
            "runtime file missing after partial publish: %s" % name
        want = open(os.path.join(REPO, REPO_SOURCES[name]), "rb").read()
        assert got.read_bytes() == want, "content drift: %s" % name
    assert not (unit_dir / "cred-ui.service").exists(), \
        "unit published despite the unwritable dir"
    # The promised recovery: re-run completes the install.
    r = _run_install(REPO, install_dir, unit_dir)
    assert r.returncode == 0, r.stderr + r.stdout
    unit = unit_dir / "cred-ui.service"
    assert unit.is_file(), "unit not installed after re-run"
    assert unit.read_bytes() == open(
        os.path.join(REPO, "cred-ui", "cred-ui.service"), "rb").read()
    leftovers = [p for p in install_dir.parent.iterdir()
                 if p.name.startswith(install_dir.name + ".staging.")]
    assert not leftovers, "staging residue: %s" % leftovers


def test_service_unit_points_at_install_default(tmp_path):
    """The unit hardcodes the production default install path; the deploy
    manifest must compute the same default — otherwise a deploy installs
    to one place while the service runs from another (split-brain)."""
    home = tmp_path / "home"
    home.mkdir()
    r = subprocess.run(
        ["bash", "-c",
         "unset CRED_UI_INSTALL_DIR SYSTEMD_USER_DIR; "
         "export AUTO_DEPLOY_NO_MAIN=1; "
         "source ./deploy/auto-deploy.sh >/dev/null 2>&1; "
         "printf '%s' \"$CRED_UI_INSTALL_DIR\""],
        cwd=REPO, capture_output=True, text=True, timeout=60,
        env={**os.environ, "HOME": str(home)},
    )
    assert r.returncode == 0, r.stderr
    default_dir = r.stdout
    # Parse ExecStart's script path from the unit and expand %h (systemd's
    # home-dir specifier, valid in user units).
    unit_text = open(os.path.join(REPO, "cred-ui", "cred-ui.service"),
                     encoding="utf-8").read()
    m = re.search(r"^ExecStart=\S+\s+(\S+)", unit_text, re.M)
    assert m, "no ExecStart path in cred-ui.service"
    unit_path = m.group(1).replace("%h", str(home))
    assert unit_path == os.path.join(default_dir, "cred-ui.py"), \
        "unit runs %r but the deploy default installs to %r" % (
            unit_path, default_dir)
    # Three-way agreement: install.sh's own default (the documented
    # manual-install path) must name the same location.
    ish = open(os.path.join(REPO, "cred-ui", "install.sh"),
               encoding="utf-8").read()
    m2 = re.search(
        r""": "\$\{CRED_UI_INSTALL_DIR:=\$\{HOME\}([^}]*)\}""", ish)
    assert m2, "install.sh no longer declares a ${HOME}-relative default"
    assert str(home) + m2.group(1) == default_dir, \
        "install.sh default %r disagrees with the deploy default %r" % (
            m2.group(1), default_dir)
