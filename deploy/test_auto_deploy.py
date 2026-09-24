"""Tests for deploy/auto-deploy.sh + deploy/components.conf (issue #22).

Run from the repo root:  python3 -m pytest deploy/test_auto_deploy.py -q
"""

import os
import re
import socket
import subprocess
import threading

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO, "deploy", "auto-deploy.sh")


def run_bash(code, env_extra=None, cwd=REPO):
    """Run bash -c code with the updater env overrides applied."""
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", "-c", code], cwd=cwd, env=env,
        capture_output=True, text=True, timeout=60,
    )


def source_and(code, env_extra=None):
    """Source auto-deploy.sh (functions only) then run code."""
    return run_bash(
        "export AUTO_DEPLOY_NO_MAIN=1; source ./deploy/auto-deploy.sh; " + code,
        env_extra=env_extra,
    )


def make_fixture_repo(tmp_path):
    """Temp git repo with commits touching each deployable component."""
    repo = tmp_path / "fixture"
    repo.mkdir()
    run = lambda *a: subprocess.run(a, cwd=repo, check=True, capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    run("git", "config", "commit.gpgsign", "false")
    (repo / "proxy").mkdir(); (repo / "confirm").mkdir()
    (repo / "cred-ui").mkdir(); (repo / "docs").mkdir()
    (repo / "proxy" / "a.py").write_text("a")
    (repo / "confirm" / "b.py").write_text("b")
    (repo / "cred-ui" / "c.py").write_text("c")
    (repo / "docs" / "d.md").write_text("d")
    run("git", "add", "."); run("git", "commit", "-qm", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True).stdout.strip()
    (repo / "proxy" / "a.py").write_text("a2")
    (repo / "confirm" / "b.py").write_text("b2")
    run("git", "add", "."); run("git", "commit", "-qm", "touch proxy+confirm")
    mid = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                         capture_output=True, text=True).stdout.strip()
    (repo / "docs" / "d.md").write_text("d2")
    run("git", "add", "."); run("git", "commit", "-qm", "docs only")
    docs_only = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                               capture_output=True, text=True).stdout.strip()
    return str(repo), base, mid, docs_only


# --- manifest ---------------------------------------------------------------

def test_manifest_valid():
    """Every component has paths/services/health/gate; prefixes exist; no overlap."""
    r = source_and(r'''
set -e
for c in "${COMPONENTS[@]}"; do
    [ -n "$(get_arr "$c" paths)" ] || { echo "no paths: $c"; exit 1; }
    [ -n "$(get_str "$c" tests)" ] || { echo "no tests: $c"; exit 1; }
    nsvc=$(get_arr "$c" services | grep -c . || true)
    nusr=$(get_arr "$c" user_services | grep -c . || true)
    [ $((nsvc + nusr)) -gt 0 ] || { echo "no services: $c"; exit 1; }
    get_arr "$c" services | grep -q . && get_arr "$c" services | grep -qv '\.service$' && { echo "bad unit: $c"; exit 1; } || true
    get_arr "$c" user_services | grep -q . && get_arr "$c" user_services | grep -qv '\.service$' && { echo "bad user unit: $c"; exit 1; } || true
    while IFS= read -r h; do
        echo "$h" | grep -Eq '^tcp:[^:]+:[0-9]+$' || { echo "bad health: $c $h"; exit 1; }
    done < <(get_arr "$c" health)
    while IFS= read -r p; do
        [ -e "REPOROOT/$p" ] || [ -d "REPOROOT/${p%/}" ] || { echo "prefix missing: $c $p"; exit 1; }
    done < <(get_arr "$c" paths)
done
# no path prefix claimed by two components (checked in test_manifest_no_path_overlap)
echo MANIFEST_OK
'''.replace("REPOROOT", REPO))
    assert "MANIFEST_OK" in r.stdout, r.stderr + r.stdout


def test_manifest_no_path_overlap():
    """Directory prefixes must be claimed by exactly one component (ambiguous
    deploy mapping otherwise). Exact-file entries (no trailing slash) MAY be
    shared — e.g. VERSION is claimed by both proxy and cred-ui so a
    version-only release refreshes every component that reports it; the
    change->component mapping stays deterministic."""
    r = source_and(r'''
set -e
tmp=$(mktemp); tmp2=$(mktemp)
for c in "${COMPONENTS[@]}"; do get_arr "$c" paths; done | grep '/$' | sort >"$tmp"
sort -u "$tmp" >"$tmp2"
cmp -s "$tmp" "$tmp2" || { echo "DIR-OVERLAP"; diff "$tmp" "$tmp2"; exit 1; }
# the deliberate exact-file sharing is documented, not accidental
[ "$(for c in "${COMPONENTS[@]}"; do get_arr "$c" paths; done | grep -cx '^VERSION$')" = 2 ]
echo NO_OVERLAP
''')
    assert "NO_OVERLAP" in r.stdout, r.stderr + r.stdout


def test_component_name_mapping():
    """cred-ui (hyphen) resolves to cred_ui_* vars."""
    r = source_and('get_arr cred-ui paths')
    assert r.returncode == 0, r.stderr
    assert "cred-ui/" in r.stdout


def test_gate_commands_cover_all_component_test_files():
    """The pre-deploy gate is the last check before root-adjacent installs,
    so every test module under a component's dir must be referenced by that
    component's gate command. Arch review 2026-09-23 found four proxy test
    files (test_safe_install, test_build_ca_bundle, test_enforce_secrets_dir,
    test_validation_conformance), confirm's test_push_queue.py, and the whole
    cred-ui/tests/ dir had silently drifted out of the gates: a green gate
    said nothing about them. A file counts as covered when its repo-relative
    path — or a parent dir that pytest would collect — appears in the gate.
    """
    component_dirs = {
        "proxy": ["proxy"],
        "confirm": ["confirm"],
        "cred-ui": ["cred-ui"],
    }
    missing = []
    for component, dirs in component_dirs.items():
        r = source_and(f'get_str {component} tests')
        assert r.returncode == 0, r.stderr
        # Token-based matching, not substring: the bare word "proxy" appears
        # in every proxy gate, so a substring check would vacuous-pass.
        tokens = set(re.findall(r'[^\s"\'=;]+', r.stdout))
        for d in dirs:
            comp_dir = os.path.join(REPO, d)
            for dirpath, _dirnames, filenames in os.walk(comp_dir):
                for fn in sorted(filenames):
                    if not (fn.startswith("test_") and fn.endswith(".py")):
                        continue
                    rel = os.path.relpath(os.path.join(dirpath, fn), REPO)
                    # covered by exact path ("proxy/test_x.py") or by a parent
                    # dir ("cred-ui/tests/") that pytest would collect.
                    parts = rel.split(os.sep)
                    covered = rel in tokens or any(
                        "/".join(parts[:i]) + "/" in tokens
                        for i in range(1, len(parts))
                    )
                    if not covered:
                        missing.append(f"{component}: {rel} not in gate")
    assert not missing, "gate-coverage drift:\n" + "\n".join(missing)


def test_proxy_install_paths_cover_deploy_sh_writes():
    """Every file proxy/deploy.sh installs must be rollback-restorable.
    Security-review regression: /etc/sudoers.d/swapd, the CA bundle, and
    grants.json were missing from proxy_install_paths, so a rollback after a
    failed deploy would have left the NEW sudoers live while everything else
    reverted — the exact half-state rollback exists to prevent."""
    r = source_and('get_arr proxy install_paths')
    assert r.returncode == 0, r.stderr
    listed = {line.strip() for line in r.stdout.splitlines() if line.strip()}
    required = {
        "/home/swapd/grants.json",
        "/etc/sudoers.d/swapd",
        "/usr/local/share/with-proxy-ca/ca-bundle.crt",
        "/etc/logrotate.d/swap-proxy",  # QA follow-up: deploy.sh writes
        # it (line 177) but the required set never checked it
    }
    missing = required - listed
    assert not missing, "missing from proxy_install_paths: %s" % sorted(missing)
    # Non-vacuous: deploy.sh really does write those targets.
    with open(os.path.join(REPO, "proxy", "deploy.sh")) as f:
        body = f.read()
    for t in required:
        assert t in body, "deploy.sh no longer writes %s (test is stale)" % t
    # Issue #108: the literal system paths are env-redirectable so the
    # test suite can point them at tmp instead of the host. Pin that the
    # override actually takes effect on the expanded array.
    r = source_and('get_arr proxy install_paths',
                   env_extra={"SUDOERS_D_SWAPD": "/tmp/fake-sudoers"})
    assert r.returncode == 0, r.stderr
    lines = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    assert "/tmp/fake-sudoers" in lines
    assert "/etc/sudoers.d/swapd" not in lines
    # Issue #108 (QA follow-up): no literal system path may sneak back
    # into proxy_install_paths without an env redirect — under full
    # redirection every expanded entry must live under the redirected
    # roots, so a future literal addition fails loudly instead of
    # touching the host on a deployed box (silently on root CI).
    roots = ("/tmp/t/swapd", "/tmp/t/bin", "/tmp/t/sysd",
             "/tmp/t/sudoers", "/tmp/t/ca", "/tmp/t/logrotate")
    r = source_and('get_arr proxy install_paths', env_extra={
        "SWAPD_HOME": roots[0], "BIN_DIR": roots[1], "SYSTEMD_DIR": roots[2],
        "SUDOERS_D_SWAPD": roots[3], "WITH_PROXY_CA_BUNDLE": roots[4],
        "LOGROTATE_SWAP_PROXY": roots[5]})
    assert r.returncode == 0, r.stderr
    lines = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    unredirected = [p for p in lines if not p.startswith(("/tmp/t/",))]
    assert not unredirected, \
        "unredirected literal system paths: %s" % unredirected


# --- change mapping ----------------------------------------------------------

def test_map_changed_files(tmp_path):
    repo, base, mid, docs_only = make_fixture_repo(tmp_path)
    r = run_bash("./deploy/auto-deploy.sh map %s %s" % (base, mid),
                 env_extra={"UPDATER_REPO": repo})
    assert r.returncode == 0, r.stderr
    got = set(r.stdout.split())
    assert got == {"proxy", "confirm"}, got


def test_map_pull_only_change(tmp_path):
    """A docs-only change maps to no deployable component."""
    repo, base, mid, docs_only = make_fixture_repo(tmp_path)
    r = run_bash("./deploy/auto-deploy.sh map %s %s" % (mid, docs_only),
                 env_extra={"UPDATER_REPO": repo})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""


# --- pending_range contract ----------------------------------------------------

def _make_pinned_fixture(tmp_path):
    """Bare origin + cloned updater repo with PINNED_UPSTREAM env matching."""
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "--bare"], cwd=origin, check=True)
    repo, base, mid, docs_only = make_fixture_repo(tmp_path)
    run = lambda *a: subprocess.run(a, cwd=repo, check=True, capture_output=True)
    run("git", "remote", "add", "origin", str(origin))
    run("git", "push", "-q", "origin", "HEAD:main")
    subprocess.run(["git", "--git-dir", str(origin), "symbolic-ref",
                    "HEAD", "refs/heads/main"], check=True)
    updater = tmp_path / "updater"
    subprocess.run(["git", "clone", "-q", str(origin), str(updater)], check=True)
    state = tmp_path / "state"
    state.mkdir()
    env = {
        "AUTO_DEPLOY_NO_MAIN": "1",
        "UPDATER_REPO": str(updater),
        "UPDATER_STATE_DIR": str(state),
        "PINNED_UPSTREAM": str(origin),
        "SKIP_SYSTEMCTL": "1",
        "SKIP_SUDO": "1",
    }
    return updater, state, env, base, mid, docs_only


def test_pending_range_return_contract(tmp_path):
    """pending_range: 0 = range on stdout; 1 = nothing to do; 2 = error.
    Regression: the `range="$(pending_range)"; rc=$?` form was dead code
    under set -e — the shell exited inside the assignment, so the rc=1/2
    branches (quiet blocked head, precheck alert+audit) were unreachable and
    the common up-to-date tick reported a FAILED oneshot."""
    updater, state, env, base, mid, docs_only = _make_pinned_fixture(tmp_path)
    head = subprocess.run(["git", "rev-parse", "origin/main"], cwd=updater,
                          check=True, capture_output=True, text=True).stdout.strip()
    assert docs_only == head  # main carries all three fixture commits

    def sourced(code):
        return run_bash("export AUTO_DEPLOY_NO_MAIN=1; source ./deploy/auto-deploy.sh; "
                        + code, env_extra=env, cwd=REPO)

    # behind: rc=0, prints "old new" (base -> docs_only covers a deployable change)
    (state / "deployed-commit").write_text(base + "\n")
    r = sourced('if range="$(pending_range)"; then rc=0; else rc=$?; fi; '
                'echo "RC=$rc RANGE=$range"')
    assert "RC=0 RANGE=%s %s" % (base, docs_only) in r.stdout, r.stdout + r.stderr

    # up-to-date: rc=1 — and the real cmd_check must exit 0, not die in the assignment
    (state / "deployed-commit").write_text(docs_only + "\n")
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; cmd_check; echo CHECK_OK",
                 env_extra=env, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "CHECK_OK" in r.stdout

    # blocked head: rc=1, stays quiet
    (state / "blocked-commit").write_text(docs_only + "\n")
    (state / "deployed-commit").write_text(base + "\n")
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; cmd_check; echo CHECK_OK",
                 env_extra=env, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "CHECK_OK" in r.stdout
    (state / "blocked-commit").unlink()

    # garbage watermark: rc=2 — the precheck branch must alert AND audit
    (state / "deployed-commit").write_text("not-a-sha\n")
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; "
                 "if cmd_deploy; then rc=0; else rc=$?; fi; echo DEPLOY_RC=$rc",
                 env_extra=env, cwd=REPO)
    assert "DEPLOY_RC=1" in r.stdout, r.stdout + r.stderr
    assert (state / "last-failure").exists(), "precheck-fail never alerted"
    audit = (state / "audit.log").read_text()
    assert '"result":"precheck-fail"' in audit, audit


# --- upstream pinning ----------------------------------------------------------

def test_pinned_upstream_refuses_rewired_origin(tmp_path):
    repo = tmp_path / "evil"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "origin",
                    "https://example.com/evil/spark-vm.git"], cwd=repo, check=True)
    r = source_and("check_upstream_pinned",
                   env_extra={"UPDATER_REPO": str(repo)})
    assert r.returncode != 0
    assert "refusing to deploy" in r.stdout + r.stderr


def test_pinned_upstream_accepts_pinned(tmp_path):
    repo = tmp_path / "good"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "remote", "add", "origin",
                    "https://github.com/ntindle/spark-vm"], cwd=repo, check=True)
    r = source_and("check_upstream_pinned",
                   env_extra={"UPDATER_REPO": str(repo)})
    assert r.returncode == 0, r.stdout + r.stderr


# --- snapshot / rollback -------------------------------------------------------

def test_snapshot_and_rollback(tmp_path):
    state = tmp_path / "state"
    swapd = tmp_path / "swapd"
    bindir = tmp_path / "bin"
    sysd = tmp_path / "systemd"
    literals = tmp_path / "literals"
    for d in (swapd, bindir, sysd, literals):
        d.mkdir(parents=True)
    (swapd / "swap_addon.py").write_text("OLD ADDON")
    (bindir / "with-proxy").write_text("OLD PROXY")
    (sysd / "swap-proxy.service").write_text("OLD UNIT")
    # Issue #108: proxy_install_paths carries literal system paths
    # (/etc/sudoers.d/swapd, ...). On a deployed box the sudoers file
    # exists but is unreadable by the test user, so the real-path
    # snapshot dies in `cp -a` with Permission denied. Redirect the
    # literals at tmp via the components.conf env overrides — exactly
    # like SWAPD_HOME/BIN_DIR/SYSTEMD_DIR — so the suite never touches
    # the host. The redirected files double as snapshot/restore coverage
    # for the literal-path entries themselves.
    sudoers = literals / "sudoers.d" / "swapd"
    sudoers.parent.mkdir(parents=True)
    sudoers.write_text("OLD SUDOERS")
    ca = literals / "ca-bundle.crt"
    ca.write_text("OLD CA")
    logrotate = literals / "logrotate.d" / "swap-proxy"
    logrotate.parent.mkdir(parents=True)
    logrotate.write_text("OLD LOGROTATE")
    env = {
        "UPDATER_STATE_DIR": str(state),
        "SWAPD_HOME": str(swapd),
        "BIN_DIR": str(bindir),
        "SYSTEMD_DIR": str(sysd),
        "SUDOERS_D_SWAPD": str(sudoers),
        "WITH_PROXY_CA_BUNDLE": str(ca),
        "LOGROTATE_SWAP_PROXY": str(logrotate),
        "SKIP_SYSTEMCTL": "1",
        "SKIP_SUDO": "1",
        "AUTO_DEPLOY_NO_MAIN": "1",
    }
    snap = tmp_path / "snap"
    r = source_and("snapshot_component proxy %s && cat %s/MANIFEST" % (snap, snap),
                   env_extra=env)
    assert r.returncode == 0, r.stderr + r.stdout
    manifest = (snap / "MANIFEST").read_text()
    assert str(swapd / "swap_addon.py") in manifest
    # the redirected literal paths must be snapshot-covered, not ABSENT
    assert str(sudoers) in manifest
    assert str(ca) in manifest
    assert str(logrotate) in manifest
    # a file that did not exist is recorded as ABSENT
    assert re.search(r"^ABSENT .*grant-writer$", manifest, re.M)

    # mutate the installed files, then roll back
    (swapd / "swap_addon.py").write_text("NEW ADDON")
    (bindir / "with-proxy").write_text("NEW PROXY")
    sudoers.write_text("NEW SUDOERS")
    ca.write_text("NEW CA")
    r = source_and("restore_snapshot %s" % snap, env_extra=env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert (swapd / "swap_addon.py").read_text() == "OLD ADDON"
    assert (bindir / "with-proxy").read_text() == "OLD PROXY"
    assert (sysd / "swap-proxy.service").read_text() == "OLD UNIT"
    assert sudoers.read_text() == "OLD SUDOERS"
    assert ca.read_text() == "OLD CA"
    assert logrotate.read_text() == "OLD LOGROTATE"


def test_restore_absent_branch_skips_unstatable_paths(tmp_path):
    """restore_snapshot must not fail on ABSENT entries it cannot stat.

    Regression (CI on #39): the manifest carries literal system paths
    (/etc/sudoers.d/swapd, the CA bundle) recorded ABSENT; on the CI runner
    (non-root) their parent dirs are not stat-able, so `rm -f` died with
    Permission denied on a file that was never there and the whole rollback
    reported failure. restore_snapshot now checks existence first (through
    sudo_run, honoring the same privilege the removal would use) and skips
    what it cannot see. In production the timer runs privileged, so the check
    sees exactly what the removal would touch — no behavior change there.
    """
    if os.geteuid() == 0:
        pytest.skip("EACCES-on-stat only manifests for unprivileged users")
    snap = tmp_path / "snap"
    snap.mkdir()
    live = tmp_path / "live"
    live.mkdir()
    doomed = live / "doomed"
    doomed.write_text("x")
    blind = tmp_path / "blind"
    blind.mkdir()
    blind.chmod(0o000)
    try:
        (snap / "MANIFEST").write_text(
            "ABSENT %s\nABSENT %s/ghost\n" % (doomed, blind))
        r = source_and("restore_snapshot %s" % snap,
                       env_extra={"UPDATER_STATE_DIR": str(tmp_path),
                                  "SKIP_SUDO": "1",
                                  "AUTO_DEPLOY_NO_MAIN": "1"})
        assert r.returncode == 0, r.stdout + r.stderr
        # the present-but-absent-at-snapshot file must still be removed —
        # the fix must not become a blanket skip of the ABSENT branch
        assert not doomed.exists()
    finally:
        blind.chmod(0o755)


def test_restore_absent_branch_removes_dangling_symlink(tmp_path):
    """A dangling symlink at an ABSENT-recorded path must still be removed.

    Guard for the stat-check fix: `test -e` is false for dangling symlinks,
    so the existence gate needs the `test -L` disjunct — otherwise rollback
    would leave a deploy-created dangling symlink (e.g. in /etc/sudoers.d/)
    in place, regressing the old unconditional `rm -f` coverage. `rm -f`
    unlinks only the symlink, never its target.
    """
    snap = tmp_path / "snap"
    snap.mkdir()
    live = tmp_path / "live"
    live.mkdir()
    target = live / "real-target"
    target.write_text("x")
    link = live / "link"
    link.symlink_to(target)
    (snap / "MANIFEST").write_text("ABSENT %s\n" % link)
    target.unlink()  # dangle the link after recording it
    assert not link.exists() and os.path.islink(link)
    r = source_and("restore_snapshot %s" % snap,
                   env_extra={"UPDATER_STATE_DIR": str(tmp_path),
                              "SKIP_SUDO": "1",
                              "AUTO_DEPLOY_NO_MAIN": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert not os.path.islink(link), "dangling symlink must be unlinked"
    assert "removing" in r.stdout + r.stderr


def test_restore_absent_branch_preserves_live_symlink_target(tmp_path):
    """#104: `rm -f` unlinks only the symlink, never its target.

    `test_restore_absent_branch_removes_dangling_symlink` pins the
    `test -L` disjunct but deletes the target before restore, so the
    "removal never touches the target" claim rests on code reading
    alone. With a LIVE target behind the link at an ABSENT path: the
    link must be unlinked and the target must still hold its content.
    """
    snap = tmp_path / "snap"
    snap.mkdir()
    live = tmp_path / "live"
    live.mkdir()
    target = live / "real-target"
    target.write_text("x")
    link = live / "link"
    link.symlink_to(target)
    assert link.exists() and os.path.islink(link)  # live, not dangling
    (snap / "MANIFEST").write_text("ABSENT %s\n" % link)
    r = source_and("restore_snapshot %s" % snap,
                   env_extra={"UPDATER_STATE_DIR": str(tmp_path),
                              "SKIP_SUDO": "1",
                              "AUTO_DEPLOY_NO_MAIN": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert not os.path.islink(link), "symlink must be unlinked"
    assert target.read_text() == "x", "live target must be untouched"


def test_snapshot_restores_dangling_symlink(tmp_path):
    """#105: the snapshot-side existence hunk covers dangling symlinks.

    The snapshot writer's `test -L` disjunct (existence goes through
    sudo_stat_path) has no dedicated test — only the restore side was
    pinned. Round trip: snapshot a dangling symlink, replace it with a
    regular file (as a deploy would), restore, assert the dangling link
    comes back — not a file, not recorded ABSENT.
    """
    state = tmp_path / "state"
    swapd = tmp_path / "swapd"
    swapd.mkdir(parents=True)
    link = swapd / "swap_addon.py"
    link.symlink_to(swapd / "missing-target")
    assert os.path.islink(link) and not link.exists()
    literals = tmp_path / "literals"  # #108: never touch host literals
    env = {
        "UPDATER_STATE_DIR": str(state),
        "SWAPD_HOME": str(swapd),
        "BIN_DIR": str(tmp_path / "bin"),
        "SYSTEMD_DIR": str(tmp_path / "systemd"),
        "SUDOERS_D_SWAPD": str(literals / "sudoers.d" / "swapd"),
        "WITH_PROXY_CA_BUNDLE": str(literals / "ca-bundle.crt"),
        "LOGROTATE_SWAP_PROXY": str(literals / "logrotate.d" / "swap-proxy"),
        "SKIP_SYSTEMCTL": "1",
        "SKIP_SUDO": "1",
        "AUTO_DEPLOY_NO_MAIN": "1",
    }
    snap = tmp_path / "snap"
    r = source_and("snapshot_component proxy %s" % snap, env_extra=env)
    assert r.returncode == 0, r.stderr + r.stdout
    manifest = (snap / "MANIFEST").read_text()
    # not recorded ABSENT: the `test -L` disjunct keeps dangling symlinks
    # snapshot-covered (`test -e` is false for them)
    assert not re.search(r"^ABSENT .*swap_addon\.py$", manifest, re.M)
    assert str(link) in manifest
    # mutate: a deploy replaces the link with a real file
    link.unlink()
    link.write_text("NEW FILE")
    r = source_and("restore_snapshot %s" % snap, env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert os.path.islink(link) and not link.exists(), \
        "dangling symlink must be restored as a link"
    assert os.readlink(link) == str(swapd / "missing-target")


def test_sudo_stat_path_tristate(tmp_path):
    """sudo_stat_path returns 0/1/2 for present/absent/check-errored.

    Regression (#107): the old inline `sudo_run test -e/-L` collapsed
    "the check itself errored" into "absent". A fake sudo_run simulates
    the three outcomes.
    """
    f = tmp_path / "present"
    f.write_text("x")
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "no-such-target")
    r = source_and(r'''
chk() { if sudo_stat_path "$1"; then echo "rc=0"; else echo "rc=$?"; fi; }
chk "%s"
chk "%s"
chk "%s/no-such"
sudo_run() { echo "sudo: a password is required" >&2; return 1; }
chk "%s"
sudo_run() { return 2; }
chk "%s"
''' % (f, dangling, tmp_path, f, f), env_extra={"SKIP_SUDO": "1",
                                               "AUTO_DEPLOY_NO_MAIN": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    lines = [l for l in r.stdout.splitlines() if l.startswith("rc=")]
    assert lines == ["rc=0", "rc=0", "rc=1", "rc=2", "rc=2"], r.stdout


def test_restore_absent_empty_path_fails(tmp_path):
    """An `ABSENT ` line with an empty path is corrupt — fail loud (#103).

    The old code silently skipped it (both tests fail on "") and reported
    success. Matches the CHECKOUT-ABSENT guard's behavior.
    """
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "MANIFEST").write_text("ABSENT \n")
    r = source_and("restore_snapshot %s" % snap,
                   env_extra={"UPDATER_STATE_DIR": str(tmp_path),
                              "SKIP_SUDO": "1",
                              "AUTO_DEPLOY_NO_MAIN": "1"})
    assert r.returncode != 0, r.stdout + r.stderr
    assert "corrupt MANIFEST ABSENT line" in r.stdout + r.stderr


def test_snapshot_broken_sudo_fails_loud(tmp_path):
    """snapshot_component must not record ABSENT when sudo itself errors (#107).

    A broken-sudo production box makes every existence check fail; the old
    code recorded live files ABSENT (a corrupt manifest) and kept going.
    The snapshot is a pre-deploy gate — abort, don't write a lie.
    """
    state = tmp_path / "state"
    swapd = tmp_path / "swapd"
    for d in (state, swapd):
        d.mkdir(parents=True)
    (swapd / "swap_addon.py").write_text("LIVE")
    env = {
        "UPDATER_STATE_DIR": str(state),
        "SWAPD_HOME": str(swapd),
        "BIN_DIR": str(tmp_path / "bin"),
        "SYSTEMD_DIR": str(tmp_path / "systemd"),
        "SKIP_SYSTEMCTL": "1",
        "SKIP_SUDO": "1",
        "AUTO_DEPLOY_NO_MAIN": "1",
    }
    snap = tmp_path / "snap"
    r = source_and(r'''
set -e
sudo_run() { echo "sudo: cannot execute" >&2; return 1; }
if snapshot_component proxy "%s"; then echo SNAPSHOT_OK; else echo SNAPSHOT_FAILED; fi
''' % snap, env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SNAPSHOT_FAILED" in r.stdout, r.stdout + r.stderr
    assert "errored" in r.stdout + r.stderr
    # the snapshot died on the privilege check before any MANIFEST write,
    # so no live file may be recorded as ABSENT
    assert not (snap / "MANIFEST").exists()


def test_restore_broken_sudo_marks_failed(tmp_path):
    """restore_snapshot refuses to silently skip removal on a broken check (#107).

    With sudo failing, the old code skipped the rm and reported success.
    The rollback must report failure instead and keep restoring the rest:
    the manifest carries two ABSENT lines, and the loop must reach both.
    """
    snap = tmp_path / "snap"
    snap.mkdir()
    live = tmp_path / "live"
    live.mkdir()
    doomed = live / "doomed"
    doomed.write_text("x")
    doomed2 = live / "doomed2"
    doomed2.write_text("y")
    (snap / "MANIFEST").write_text("ABSENT %s\nABSENT %s\n" % (doomed, doomed2))
    r = source_and(r'''
set -e
sudo_run() { echo "sudo: cannot execute" >&2; return 1; }
if restore_snapshot "%s"; then echo RESTORE_OK; else echo RESTORE_FAILED; fi
''' % snap, env_extra={"UPDATER_STATE_DIR": str(tmp_path),
                       "SKIP_SUDO": "1",
                       "AUTO_DEPLOY_NO_MAIN": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RESTORE_FAILED" in r.stdout, r.stdout + r.stderr
    # the loop continued past the first errored entry to the second
    assert (r.stdout + r.stderr).count("refusing to skip removal silently") == 2
    # nothing was removed under a broken privilege check
    assert doomed.exists()
    assert doomed2.exists()


# --- health checks -------------------------------------------------------------

def test_tcp_ok_detects_listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]

    def serve():
        try:
            conn, _ = srv.accept()
            conn.close()
        except OSError:
            pass

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    r = source_and("tcp_ok 127.0.0.1 %d && echo TCP_OK" % port)
    assert "TCP_OK" in r.stdout, r.stderr
    srv.close()
    r = source_and("tcp_ok 127.0.0.1 %d && echo TCP_OK || echo TCP_DOWN" % port)
    assert "TCP_DOWN" in r.stdout, r.stderr


# --- audit -----------------------------------------------------------------------

def test_audit_appends_valid_json(tmp_path):
    state = tmp_path / "state"
    r = source_and(
        "audit 'deploy' ',\"result\":\"ok\",\"from\":\"aaa\",\"to\":\"bbb\"'",
        env_extra={"UPDATER_STATE_DIR": str(state)},
    )
    assert r.returncode == 0, r.stderr + r.stdout
    import json
    lines = (state / "audit.log").read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event"] == "deploy"
    assert entry["result"] == "ok"
    assert entry["from"] == "aaa" and entry["to"] == "bbb"
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", entry["ts"])


# --- deploy.sh flags -----------------------------------------------------------

def test_deploy_sh_help():
    r = run_bash("bash proxy/deploy.sh --help")
    assert r.returncode == 0, r.stderr
    assert "--no-restart" in r.stdout


def test_deploy_sh_rejects_unknown_flag():
    r = run_bash("bash proxy/deploy.sh --bogus")
    assert r.returncode != 0


def test_scripts_syntax():
    for f in ("deploy/auto-deploy.sh", "proxy/deploy.sh"):
        r = run_bash("bash -n " + f)
        assert r.returncode == 0, "%s: %s" % (f, r.stderr)
    # Gate on shellcheck warnings, not just syntax. Explicit skip (not a
    # silent pass) when shellcheck is absent — CI installs it, so a skip
    # there means the workflow's install step broke and should be noticed.
    if run_bash("command -v shellcheck").returncode != 0:
        pytest.skip("shellcheck not installed; syntax-only gate applied")
    r = run_bash("shellcheck -S warning deploy/auto-deploy.sh proxy/deploy.sh")
    assert r.returncode == 0, r.stdout + r.stderr


# --- version stamping (docs/VERSIONING.md) ------------------------------------

def test_version_paths_map_exactly():
    """VERSION (bare file entry) maps to proxy AND cred-ui — a version-only
    release must refresh every component that reports the version
    (docs/VERSIONING.md). docs/VERSIONING.md matches nothing — the
    exact-match rule for non-slash entries."""
    r = source_and('printf "VERSION\\ndocs/VERSIONING.md\\nproxy/swap_addon.py\\n"'
                   ' | components_for_files')
    assert r.returncode == 0, r.stderr
    assert sorted(r.stdout.split()) == ["cred-ui", "proxy"], r.stdout


def test_proxy_install_paths_cover_version_files():
    """VERSION + the reader must be rollback-restorable like every other file
    proxy/deploy.sh installs (same class as the sudoers regression)."""
    r = source_and('get_arr proxy install_paths')
    assert r.returncode == 0, r.stderr
    listed = {line.strip() for line in r.stdout.splitlines() if line.strip()}
    for t in ("/home/swapd/VERSION", "/home/swapd/sparkvm_version.py"):
        assert t in listed, "missing from proxy_install_paths: %s" % t
    # Non-vacuous: deploy.sh really does install those targets.
    with open(os.path.join(REPO, "proxy", "deploy.sh")) as f:
        body = f.read()
    assert "/home/swapd/VERSION" in body
    assert "/home/swapd/sparkvm_version.py" in body


def test_version_state_roundtrip(tmp_path):
    r = source_and('write_version 1.2.3; [ "$(deployed_version)" = 1.2.3 ] '
                   '&& echo VER_OK',
                   env_extra={"UPDATER_STATE_DIR": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VER_OK" in r.stdout
    assert (tmp_path / "deployed-version").read_text().strip() == "1.2.3"


def test_new_version_reads_real_value(tmp_path):
    """new_version() reports a real VERSION from the mirror — the previous
    deploy-version test only covered the no-VERSION "unknown" case, so a
    hardcoded `echo unknown` would have passed it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "VERSION").write_text("3.2.1\n")
    r = source_and('[ "$(new_version)" = 3.2.1 ] && echo REAL_OK',
                   env_extra={"UPDATER_REPO": str(repo)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "REAL_OK" in r.stdout


def test_sync_version_from_deployed(tmp_path):
    """sync_version_from_deployed: real value recorded, missing file ->
    unknown, hostile bytes sanitized to unknown (never raw into state)."""
    state = tmp_path / "state"
    swapd = tmp_path / "swapd"
    state.mkdir(); swapd.mkdir()
    env = {"UPDATER_STATE_DIR": str(state), "SWAPD_HOME": str(swapd)}
    (swapd / "VERSION").write_text("7.7.7\n")
    r = source_and('[ "$(sync_version_from_deployed)" = 7.7.7 ] && echo SYNC_OK',
                   env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SYNC_OK" in r.stdout
    assert (state / "deployed-version").read_text().strip() == "7.7.7"
    (swapd / "VERSION").write_text('9.9.9"}\n{"forged":1}\n')
    r = source_and('[ "$(sync_version_from_deployed)" = unknown ] && echo SAN_OK',
                   env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SAN_OK" in r.stdout
    assert (state / "deployed-version").read_text().strip() == "unknown"
    (swapd / "VERSION").unlink()
    r = source_and('[ "$(sync_version_from_deployed)" = unknown ] && echo MISS_OK',
                   env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MISS_OK" in r.stdout


def _commit_all(repo, msg):
    subprocess.run(["git", "add", "."], cwd=repo, check=True,
                   capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "-c", "commit.gpgsign=false", "commit", "-qm", msg],
                   cwd=repo, check=True, capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          check=True, capture_output=True,
                          text=True).stdout.strip()


def test_install_component_syncs_version_with_checkout(tmp_path):
    """A checkout-synced component's install also refreshes the root VERSION
    in the working checkout — otherwise a version-only deploy leaves
    cred-ui reporting the old release (QA regression)."""
    updater, state, env, base, mid, docs_only = _make_pinned_fixture(tmp_path)
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (updater / "cred-ui" / "cred-ui.py").write_text("# ui v2")
    (updater / "VERSION").write_text("9.9.9\n")
    new = _commit_all(updater, "cred-ui + VERSION")
    r = source_and("install_component cred-ui %s" % new,
                   env_extra={"UPDATER_STATE_DIR": str(state),
                              "UPDATER_REPO": str(updater),
                              "WORKING_CHECKOUT": str(checkout),
                              "SKIP_SUDO": "1",
                              "AUTO_DEPLOY_NO_MAIN": "1"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert (checkout / "cred-ui" / "cred-ui.py").read_text() == "# ui v2"
    assert (checkout / "VERSION").read_text() == "9.9.9\n"


def test_snapshot_restores_checkout_version(tmp_path):
    """The root VERSION file travels with checkout syncs, so it must be
    snapshotted and restored too — else rollback leaves new-VERSION under
    old code."""
    state = tmp_path / "state"
    checkout = tmp_path / "checkout"
    checkout_ui = checkout / "cred-ui"
    state.mkdir(); checkout_ui.mkdir(parents=True)
    (checkout_ui / "cred-ui.py").write_text("UI CODE")
    (checkout / "VERSION").write_text("1.1.1\n")
    env = {"UPDATER_STATE_DIR": str(state),
           "WORKING_CHECKOUT": str(checkout),
           "SKIP_SUDO": "1",
           "AUTO_DEPLOY_NO_MAIN": "1"}
    snap = tmp_path / "snap"
    r = source_and("snapshot_component cred-ui %s" % snap, env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    manifest = (snap / "MANIFEST").read_text()
    assert "CHECKOUT cred-ui VERSION" in manifest, manifest
    (checkout / "VERSION").write_text("2.2.2\n")
    r = source_and("restore_snapshot %s" % snap, env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (checkout / "VERSION").read_text() == "1.1.1\n"
    assert (checkout_ui / "cred-ui.py").read_text() == "UI CODE"


def test_version_state_defaults_unknown(tmp_path):
    r = source_and('[ "$(deployed_version)" = unknown ] && echo VER_UNKNOWN',
                   env_extra={"UPDATER_STATE_DIR": str(tmp_path)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "VER_UNKNOWN" in r.stdout


def test_clean_version_sanitizes_hostile_input():
    """clean_version: strict semver passes through, everything else —
    quotes, backslashes, newlines — becomes "unknown". VERSION is
    attacker-influenced (merged PRs, swapd-writable deployed copy) and is
    interpolated into audit JSON, so this is the injection boundary."""
    r = source_and(r'''
set -e
[ "$(clean_version '1.2.3')" = 1.2.3 ]
[ "$(clean_version '1.2.3-rc.1+b1')" = '1.2.3-rc.1+b1' ]
[ "$(clean_version 'bogus')" = unknown ]
[ "$(clean_version '1.2"')" = unknown ]
[ "$(clean_version "$(printf '1.2.3\n{"evil":1}')" )" = 1.2.3 ]
[ "$(clean_version '')" = unknown ]
echo CLEAN_OK
''')
    assert r.returncode == 0, r.stdout + r.stderr
    assert "CLEAN_OK" in r.stdout


def test_hostile_version_cannot_inject_audit(tmp_path):
    """A hostile VERSION in the mirror repo must not forge audit lines:
    new_version() sanitizes, and every audit.log line stays valid JSON with
    no forged result."""
    import json
    updater, state, env, base, mid, docs_only = _make_pinned_fixture(tmp_path)
    hostile = '1.2.3"}\n{"ts":"x","event":"deploy","result":"forged'
    (updater / "VERSION").write_text(hostile + "\n")
    r = source_and(
        '[ "$(new_version)" = unknown ] && '
        'audit deploy-test \',"v\":\"$(new_version)\"\' && echo AUDIT_OK',
        env_extra={"UPDATER_STATE_DIR": str(state),
                   "UPDATER_REPO": str(updater)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "AUDIT_OK" in r.stdout
    lines = (state / "audit.log").read_text().splitlines()
    assert lines, "no audit line written"
    for line in lines:
        obj = json.loads(line)  # raises if the hostile bytes broke the JSON
        assert obj.get("result") != "forged", line


def test_pull_only_deploy_records_version(tmp_path):
    """A pull-only deploy still records the deployed version and stamps the
    audit line with to_version/from_version (docs/VERSIONING.md)."""
    updater, state, env, base, mid, docs_only = _make_pinned_fixture(tmp_path)
    # Watermark at mid: the pending range (mid -> docs_only) is docs-only,
    # i.e. pull-only — no gates, installs, or health checks run.
    (state / "deployed-commit").write_text(mid + "\n")
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; cmd_deploy; echo DEPLOY_OK",
                 env_extra=env, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DEPLOY_OK" in r.stdout
    # The fixture repo has no VERSION file at its root.
    assert (state / "deployed-version").read_text().strip() == "unknown"
    audit = (state / "audit.log").read_text()
    assert '"result":"pull-only"' in audit, audit
    assert '"to_version":"unknown"' in audit, audit
    assert '"from_version":"unknown"' in audit, audit
    # Gate on shellcheck warnings, not just syntax. Explicit skip (not a
    # silent pass) when shellcheck is absent — CI installs it, so a skip
    # there means the workflow's install step broke and should be noticed.
    if run_bash("command -v shellcheck").returncode != 0:
        pytest.skip("shellcheck not installed; syntax-only gate applied")
    r = run_bash("shellcheck -S warning deploy/auto-deploy.sh proxy/deploy.sh")
    assert r.returncode == 0, r.stdout + r.stderr


# --- tailnet health token + updater drift ---------------------------------------

def test_resolve_health_host_passthrough():
    """Literal hosts are returned unchanged."""
    r = source_and('resolve_health_host 127.0.0.1')
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "127.0.0.1"


def test_resolve_health_host_tailnet(tmp_path):
    """TAILNET resolves via `tailscale ip -4` (first line, trimmed)."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "tailscale"
    fake.write_text('#!/bin/sh\nprintf "100.99.0.1\\nfd7a:x::1\\n"\n')
    fake.chmod(0o755)
    env = {"PATH": str(bindir) + os.pathsep + os.environ["PATH"]}
    r = source_and('resolve_health_host TAILNET', env_extra=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "100.99.0.1", r.stdout


def test_resolve_health_host_tailnet_unresolvable(tmp_path):
    """TAILNET with a failing tailscale yields empty -- the health check
    then fails closed with a clear message instead of probing a stale IP."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "tailscale"
    fake.write_text('#!/bin/sh\nexit 1\n')
    fake.chmod(0o755)
    env = {"PATH": str(bindir) + os.pathsep + os.environ["PATH"]}
    r = source_and('resolve_health_host TAILNET', env_extra=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "", r.stdout


def _drift_fixture(tmp_path, touch_deploy):
    """Mirror repo whose origin/main advanced past the recorded source
    commit; optionally with a deploy/ change in range."""
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    run = lambda *a: subprocess.run(a, cwd=mirror, check=True,
                                    capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    run("git", "config", "commit.gpgsign", "false")
    (mirror / "deploy").mkdir()
    (mirror / "deploy" / "auto-deploy.sh").write_text("v1")
    run("git", "add", ".")
    run("git", "commit", "-qm", "base")
    src = subprocess.run(["git", "rev-parse", "HEAD"], cwd=mirror,
                         capture_output=True, text=True).stdout.strip()
    if touch_deploy:
        (mirror / "deploy" / "auto-deploy.sh").write_text("v2")
    else:
        (mirror / "docs").mkdir()
        (mirror / "docs" / "note.md").write_text("n")
    run("git", "add", ".")
    run("git", "commit", "-qm", "advance")
    run("git", "update-ref", "refs/remotes/origin/main", "HEAD")
    state = tmp_path / "state"
    state.mkdir()
    (state / "updater-source-commit").write_text(src + "\n")
    return state, src


def test_check_updater_drift_warns(tmp_path):
    """origin/main with newer deploy/ changes than the recorded source
    commit produces the re-run-init warning."""
    state, _ = _drift_fixture(tmp_path, touch_deploy=True)
    r = source_and('check_updater_drift',
                   env_extra={"UPDATER_STATE_DIR": str(state),
                              "UPDATER_REPO": str(tmp_path / "mirror")})
    assert "WARNING: updater code is stale" in r.stderr, r.stderr + r.stdout
    assert "re-run './deploy/auto-deploy.sh init'" in r.stderr


def test_check_updater_drift_quiet_when_docs_only(tmp_path):
    """origin/main advanced but touched only docs -- no warning."""
    state, _ = _drift_fixture(tmp_path, touch_deploy=False)
    r = source_and('check_updater_drift',
                   env_extra={"UPDATER_STATE_DIR": str(state),
                              "UPDATER_REPO": str(tmp_path / "mirror")})
    assert r.returncode == 0, r.stderr
    assert "WARNING" not in r.stderr, r.stderr


def test_check_updater_drift_quiet_when_current(tmp_path):
    """Source commit == origin/main -- no warning."""
    state, _ = _drift_fixture(tmp_path, touch_deploy=True)
    cur = subprocess.run(["git", "rev-parse", "origin/main"],
                         cwd=tmp_path / "mirror",
                         capture_output=True, text=True).stdout.strip()
    (state / "updater-source-commit").write_text(cur + "\n")
    r = source_and('check_updater_drift',
                   env_extra={"UPDATER_STATE_DIR": str(state),
                              "UPDATER_REPO": str(tmp_path / "mirror")})
    assert r.returncode == 0, r.stderr
    assert "WARNING" not in r.stderr, r.stderr


def test_record_updater_source_records_checkout_head(tmp_path):
    """init's helper records the checkout's HEAD sha (40 hex)."""
    state = tmp_path / "state"
    state.mkdir()
    r = source_and('record_updater_source',
                   env_extra={"UPDATER_STATE_DIR": str(state)})
    assert r.returncode == 0, r.stderr
    recorded = (state / "updater-source-commit").read_text().strip()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    assert recorded == head and re.fullmatch(r"[0-9a-f]{40}", recorded)
