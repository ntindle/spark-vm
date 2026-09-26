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


def _health_check_stub(entries):
    """Run health_check with the manifest/network edges stubbed so only
    the tcp:HOST:PORT parsing is exercised (#323)."""
    script = r'''
set -e
SKIP_SYSTEMCTL=1
get_arr() { if [ "$2" = health ]; then printf '%s\n' "$HEALTH_ENTRIES"; fi; }
resolve_health_host() { echo "RESOLVE:$1" >&2; printf '%s\n' "$1"; }
tcp_ok() { echo "TCPCALL:$1:$2"; return 0; }
log() { echo "LOG:$*"; }
health_check fake-component && echo HEALTH_OK
'''
    return source_and(script, env_extra={"HEALTH_ENTRIES": entries})


def test_health_check_parses_ipv4_and_tailnet():
    """tcp:HOST:PORT splits on the trailing :digits port; TAILNET still
    flows through resolve_health_host (#323)."""
    r = _health_check_stub("tcp:127.0.0.1:8443\ntcp:TAILNET:8443")
    assert r.returncode == 0, r.stderr + r.stdout
    assert "TCPCALL:127.0.0.1:8443" in r.stdout, r.stdout
    assert "TCPCALL:TAILNET:8443" in r.stdout, r.stdout
    assert "RESOLVE:TAILNET" in r.stderr, r.stderr
    assert "HEALTH_OK" in r.stdout, r.stdout


def test_health_check_rejects_malformed_tcp_entry():
    """Non-numeric or missing ports fail closed with a clear log line
    instead of feeding a mangled host/port to tcp_ok (#323)."""
    for bad in ("tcp:host:", "tcp:host:abc", "tcp:host", "tcp::8080"):
        r = _health_check_stub(bad)
        assert r.returncode != 0, "%s should fail: %s" % (bad, r.stdout)
        assert "malformed tcp check" in r.stdout, r.stdout
        assert "TCPCALL" not in r.stdout, r.stdout


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
    # A real git clone: install_component re-runs the checkout-sync
    # preconditions before the destructive sync (issue #324), and those fail
    # closed on a non-git directory.
    subprocess.run(["git", "clone", "-q", str(tmp_path / "origin"), str(checkout)],
                   check=True, capture_output=True)
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


def test_install_component_rechecks_checkout_before_clobber(tmp_path):
    """Issue #324: an operator edit to the working checkout between the
    pre-deploy gate and the install must fail closed, not be silently
    clobbered. The gate check passes on the clean tree; the operator edit
    lands; the install must refuse and leave the operator's file untouched.
    Non-vacuous: the pre-fix install_component had no re-check, so the edit
    would be clobbered and the sync would succeed (returncode 0)."""
    updater, state, env, base, mid, docs_only = _make_pinned_fixture(tmp_path)
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "origin"), str(checkout)],
                   check=True, capture_output=True)
    (updater / "cred-ui" / "cred-ui.py").write_text("# ui v2")
    (updater / "VERSION").write_text("9.9.9\n")
    new = _commit_all(updater, "cred-ui + VERSION")
    env2 = {"UPDATER_STATE_DIR": str(state),
            "UPDATER_REPO": str(updater),
            "WORKING_CHECKOUT": str(checkout),
            "SKIP_SUDO": "1",
            "AUTO_DEPLOY_NO_MAIN": "1"}
    # the gate phase passes on the clean tree
    r = source_and("check_checkout_sync_ready cred-ui cred-ui %s" % new,
                   env_extra=env2)
    assert r.returncode == 0, r.stdout + r.stderr
    # the operator edits the working checkout in the gate->install window
    (checkout / "cred-ui" / "cred-ui.py").write_text("# OPERATOR EDIT")
    r = source_and("install_component cred-ui %s" % new, env_extra=env2)
    assert r.returncode == 2, \
        "must fail closed with the pre-destruction code (2), not install-failure (1): " \
        + r.stdout + r.stderr
    # the operator's edit is NOT clobbered; the new commit is NOT installed
    assert (checkout / "cred-ui" / "cred-ui.py").read_text() == "# OPERATOR EDIT"


def test_cmd_deploy_checkout_dirty_rolls_back_without_blocking(tmp_path):
    """Issue #324, caller branch (QA review blockers 1+2): cmd_deploy with
    two components. compa installs first — its install step mutates its
    deployed file AND dirties compb's working subtree, simulating another
    job editing the checkout in the gate->install window. compb's
    pre-destruction re-check then fails. The deploy must fail, roll compa's
    file back from snapshot, NOT write blocked-commit, and audit both
    checkout-dirty and rolled-back. The box (including the checkout subtree)
    returns to its exact pre-deploy state.
    """
    import json
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", "--bare"], cwd=origin, check=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    run = lambda *a: subprocess.run(a, cwd=repo, check=True,
                                   capture_output=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    run("git", "config", "commit.gpgsign", "false")
    (repo / "compa").mkdir()
    (repo / "compb").mkdir()
    (repo / "compa" / "f.py").write_text("a1")
    (repo / "compb" / "f.py").write_text("b1")
    (repo / "VERSION").write_text("1.0.0\n")
    run("git", "add", ".")
    run("git", "commit", "-qm", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True).stdout.strip()
    run("git", "remote", "add", "origin", str(origin))
    run("git", "push", "-q", "origin", "HEAD:main")
    subprocess.run(["git", "--git-dir", str(origin), "symbolic-ref",
                    "HEAD", "refs/heads/main"], check=True)
    updater = tmp_path / "updater"
    subprocess.run(["git", "clone", "-q", str(origin), str(updater)],
                   check=True)
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "clone", "-q", str(origin), str(checkout)],
                   check=True)
    (repo / "compa" / "f.py").write_text("a2")
    (repo / "compb" / "f.py").write_text("b2")
    (repo / "VERSION").write_text("1.0.1\n")
    run("git", "add", ".")
    run("git", "commit", "-qm", "touch compa+compb")
    run("git", "push", "-q", "origin", "HEAD:main")

    tconf = tmp_path / "t.conf"
    tconf.write_text(
        'COMPONENTS=(compa compb)\n'
        'compa_paths=("compa/")\n'
        'compa_services=()\n'
        'compa_user_services=()\n'
        'compa_tests="true"\n'
        'compa_health=()\n'
        "compa_install='printf \"NEW\" > \"$COMPA_FILE\"; printf \"dirty\" > \"$WORKING_CHECKOUT/compb/f.py\"'\n"
        'compa_install_unit=""\n'
        'compa_checkout_sync=""\n'
        'compa_install_paths=("$COMPA_FILE")\n'
        'compb_paths=("compb/")\n'
        'compb_services=()\n'
        'compb_user_services=()\n'
        'compb_tests="true"\n'
        'compb_health=()\n'
        'compb_install=""\n'
        'compb_install_unit=""\n'
        'compb_checkout_sync="compb"\n'
        'compb_install_paths=()\n'
    )

    compa_file = tmp_path / "compa.dat"
    compa_file.write_text("OLD")
    state = tmp_path / "state"
    state.mkdir()
    (state / "deployed-commit").write_text(base + "\n")

    env = {
        "AUTO_DEPLOY_NO_MAIN": "1",
        "UPDATER_REPO": str(updater),
        "UPDATER_STATE_DIR": str(state),
        "UPDATER_COMPONENTS_CONF": str(tconf),
        "WORKING_CHECKOUT": str(checkout),
        "COMPA_FILE": str(compa_file),
        "PINNED_UPSTREAM": str(origin),
        "SKIP_SYSTEMCTL": "1",
        "SKIP_SUDO": "1",
    }
    r = source_and("cmd_deploy", env_extra=env)
    assert r.returncode == 1, r.stdout + r.stderr

    # the commit is not blocked, the watermark is untouched ...
    assert not (state / "blocked-commit").exists()
    assert (state / "deployed-commit").read_text().strip() == base
    # ... both audit signals fired, as valid JSON ...
    audit_lines = (state / "audit.log").read_text().strip().splitlines()
    assert audit_lines, "audit log must not be empty"
    events = [json.loads(line) for line in audit_lines]
    results = [e.get("result") for e in events]
    assert "checkout-dirty" in results, results
    assert "rolled-back" in results, results
    # ... the earlier component's file was restored from snapshot ...
    assert compa_file.read_text() == "OLD"
    # ... and the checkout subtree is back to its pre-deploy state
    # (the rollback restores the snapshot, which predates the mid-window
    # edit — the box must be exactly pre-deploy so the next tick retries
    # cleanly).
    assert (checkout / "compb" / "f.py").read_text() == "b1"


def test_install_component_rechecks_version_before_clobber(tmp_path):
    """Issue #324, VERSION branch of the same re-check: an uncommitted edit
    to the working checkout's root VERSION (which travels with every sync)
    must also fail the install closed before the VERSION sync step."""
    updater, state, env, base, mid, docs_only = _make_pinned_fixture(tmp_path)
    checkout = tmp_path / "checkout"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "origin"), str(checkout)],
                   check=True, capture_output=True)
    (checkout / "VERSION").write_text("1.2.3\n")
    subprocess.run(["git", "-C", str(checkout), "add", "VERSION"], check=True,
                   capture_output=True)
    subprocess.run(["git", "-C", str(checkout), "-c", "user.email=t@t",
                    "-c", "user.name=t", "-c", "commit.gpgsign=false",
                    "commit", "-qm", "operator VERSION"], check=True,
                   capture_output=True)
    (updater / "cred-ui" / "cred-ui.py").write_text("# ui v2")
    (updater / "VERSION").write_text("9.9.9\n")
    new = _commit_all(updater, "cred-ui + VERSION")
    env2 = {"UPDATER_STATE_DIR": str(state),
            "UPDATER_REPO": str(updater),
            "WORKING_CHECKOUT": str(checkout),
            "SKIP_SUDO": "1",
            "AUTO_DEPLOY_NO_MAIN": "1"}
    # operator edits VERSION in the gate->install window
    (checkout / "VERSION").write_text("0.0.0-operator\n")
    r = source_and("install_component cred-ui %s" % new, env_extra=env2)
    assert r.returncode == 2, \
        "must fail closed with the pre-destruction code (2): " \
        + r.stdout + r.stderr
    assert (checkout / "VERSION").read_text() == "0.0.0-operator\n"


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
    # Issue #302: a box with no recorded extra-inputs digest (fresh state
    # dir) forces one proxy deploy to converge it. This test pins the
    # steady-state pull-only path, so pre-record the digest the way a prior
    # successful proxy deploy would have. SWAPD_HOME points at tmp — no CA
    # exists there, which is the steady-state digest for this fixture.
    swapd = tmp_path / "swapd"
    env = dict(env, SWAPD_HOME=str(swapd))
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; record_extra_inputs proxy",
                 env_extra=env, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
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


# --- issue #325: manual rollback marks the rolled-back commit blocked --------

def _manual_rollback_env(tmp_path):
    """Minimal state dir + snapshot for exercising cmd_rollback.

    The fake component tcomp has no services, user services, health
    checks, or install step, so reload/restart/health are no-ops under
    SKIP_SYSTEMCTL=1; SWAPD_HOME carries no VERSION file so the deployed
    version re-derives to the "unknown" fallback.
    """
    state = tmp_path / "state"
    swapd = tmp_path / "swapd"
    swapd.mkdir(parents=True)
    snap = state / "snapshots" / "snap1"
    snap.mkdir(parents=True)
    tconf = tmp_path / "t.conf"
    tconf.write_text(
        'COMPONENTS=(tcomp)\n'
        'tcomp_paths=("tcomp/")\n'
        'tcomp_services=()\n'
        'tcomp_user_services=()\n'
        'tcomp_tests="true"\n'
        'tcomp_health=()\n'
        'tcomp_install=""\n'
        'tcomp_install_paths=()\n'
    )
    env = {
        "UPDATER_STATE_DIR": str(state),
        "UPDATER_COMPONENTS_CONF": str(tconf),
        "SWAPD_HOME": str(swapd),
        "SKIP_SYSTEMCTL": "1",
        "SKIP_SUDO": "1",
        "AUTO_DEPLOY_NO_MAIN": "1",
    }
    return state, snap, env


def _arm_snapshot(state, snap, old, bad):
    """Arm a snapshot rewinding bad -> old: the watermark sits at the bad
    (deployed) commit, the snapshot's FROM_COMMIT at the good one, and the
    snapshot's COMPONENTS names the fake component. Empty MANIFEST means
    restore_snapshot has nothing to copy back (rc 0)."""
    (snap / "FROM_COMMIT").write_text(old + "\n")
    (snap / "COMPONENTS").write_text("tcomp\n")
    (snap / "MANIFEST").write_text("")
    (state / "deployed-commit").write_text(bad + "\n")


def test_manual_rollback_blocks_rolled_back_commit(tmp_path):
    """Issue #325: a manual rollback must mark the rolled-back commit
    blocked so the next timer tick does not redeploy it.

    The rolled-back commit is the pre-rollback watermark (the deployed
    head); the audit line records both sides of the rewind and the block
    decision.
    """
    import json
    state, snap, env = _manual_rollback_env(tmp_path)
    old, bad = "a" * 40, "b" * 40
    _arm_snapshot(state, snap, old, bad)
    r = source_and("cmd_rollback", env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (state / "deployed-commit").read_text().strip() == old
    assert (state / "blocked-commit").read_text().strip() == bad
    audit = (state / "audit.log").read_text()
    entry = json.loads([l for l in audit.splitlines()
                        if '"event":"rollback"' in l][-1])
    assert entry["result"] == "manual-rollback"
    assert entry["to"] == old
    assert entry["rolled_back_from"] == bad
    assert entry["blocked"] == bad


def test_manual_rollback_no_block_flag(tmp_path):
    """Issue #325 (b): --no-block is the investigate-not-condemn escape
    hatch — the watermark still rewinds, but nothing is marked blocked."""
    state, snap, env = _manual_rollback_env(tmp_path)
    old, bad = "a" * 40, "b" * 40
    _arm_snapshot(state, snap, old, bad)
    r = source_and("cmd_rollback --no-block", env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (state / "deployed-commit").read_text().strip() == old
    assert not (state / "blocked-commit").exists()


def test_manual_rollback_noop_watermark_writes_no_block(tmp_path):
    """Issue #325: when the watermark is already at FROM_COMMIT (nothing
    was ever deployed past it), there is no bad commit to block. Writing
    `from` would pin the updater on its own watermark head, so the
    rollback must skip the mark and say why — not block blindly."""
    state, snap, env = _manual_rollback_env(tmp_path)
    old = "a" * 40
    _arm_snapshot(state, snap, old, old)  # watermark == FROM_COMMIT
    r = source_and("cmd_rollback", env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (state / "blocked-commit").exists()
    assert "not marking a commit blocked" in r.stdout + r.stderr

    # Missing watermark entirely: same skip, no failure.
    (state / "deployed-commit").unlink()
    r = source_and("cmd_rollback", env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (state / "blocked-commit").exists()
    assert (state / "deployed-commit").read_text().strip() == old


def test_manual_rollback_rejects_unknown_flags(tmp_path):
    """An unrecognized rollback flag fails loud instead of silently
    doing the default (blocked) rollback."""
    state, snap, env = _manual_rollback_env(tmp_path)
    _arm_snapshot(state, snap, "a" * 40, "b" * 40)
    r = source_and("cmd_rollback --block", env_extra=env)
    assert r.returncode != 0
    # watermark untouched, nothing blocked: the rollback did not run
    assert (state / "deployed-commit").read_text().strip() == "b" * 40
    assert not (state / "blocked-commit").exists()


def test_status_reports_how_to_clear_block(tmp_path):
    """Issue #325 (a): `status` shows the blocked commit and the exact
    command to clear it (re-deploy-the-same-tree after a manual fix)."""
    state, snap, env = _manual_rollback_env(tmp_path)
    (state / "blocked-commit").write_text("b" * 40 + "\n")
    r = source_and("cmd_status", env_extra=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "b" * 40 in r.stdout
    assert 'rm "%s"' % (state / "blocked-commit") in r.stdout


# --- host-side extra inputs (issue #302) ------------------------------------

def _extra_inputs_env(tmp_path):
    """Temp SWAPD_HOME + state dir; CA cert written under it. Returns
    (env_extra, ca_path, state_dir)."""
    swapd = tmp_path / "swapd"
    ca_dir = swapd / ".mitmproxy"
    ca_dir.mkdir(parents=True)
    ca = ca_dir / "mitmproxy-ca-cert.pem"
    state = tmp_path / "state"
    state.mkdir()
    # SKIP_SUDO=1: the digest read routes through sudo_run (the deploy-
    # privilege wrapper); unit tests must exercise the wrapper contract,
    # never a real sudo.
    env = {"SWAPD_HOME": str(swapd), "UPDATER_STATE_DIR": str(state),
           "SKIP_SUDO": "1"}
    return env, ca, state


def test_extra_inputs_hash_deterministic_and_content_sensitive(tmp_path):
    """The digest is stable for identical bytes and changes when they do."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"fake-ca-bytes")
    r1 = source_and("extra_inputs_hash proxy", env_extra=env)
    r2 = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r1.returncode == 0, r1.stderr
    assert r1.stdout.strip() == r2.stdout.strip()
    ca.write_bytes(b"fake-ca-bytes-rotated")
    r3 = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r3.returncode == 0, r3.stderr
    assert r3.stdout.strip() != r1.stdout.strip()


def test_extra_inputs_changed_first_run_then_converges(tmp_path):
    """No record yet -> changed (first tick redeploys once); after recording
    the digest the same bytes are not changed."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"fake-ca-bytes")
    r = source_and("extra_inputs_changed proxy", env_extra=env)
    assert r.returncode == 0, "missing record must count as changed: " + r.stderr
    r = source_and("record_extra_inputs proxy && extra_inputs_changed proxy",
                   env_extra=env)
    assert r.returncode == 1, "recorded digest must converge: " + r.stdout + r.stderr


def test_extra_inputs_changed_detects_rotation(tmp_path):
    """A CA rotation with no code change flips changed on the next tick."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"fake-ca-bytes")
    r = source_and("record_extra_inputs proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    ca.write_bytes(b"fake-ca-bytes-rotated")
    r = source_and("extra_inputs_changed proxy", env_extra=env)
    assert r.returncode == 0, "rotated CA must force a proxy redeploy"
    r = source_and("record_extra_inputs proxy && extra_inputs_changed proxy",
                   env_extra=env)
    assert r.returncode == 1, "post-deploy record must converge again"


def test_extra_inputs_changed_detects_first_generation(tmp_path):
    """Missing CA -> digest of 'missing'; the CA appearing later is a change."""
    env, ca, state = _extra_inputs_env(tmp_path)
    r = source_and("record_extra_inputs proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    r = source_and("extra_inputs_changed proxy", env_extra=env)
    assert r.returncode == 1, "stable absence must not redeploy every tick"
    ca.write_bytes(b"first-run-ca")
    r = source_and("extra_inputs_changed proxy", env_extra=env)
    assert r.returncode == 0, "first-run CA generation must force a proxy redeploy"


def test_extra_inputs_changed_never_for_components_without_extra_paths(tmp_path):
    """Components that declare no extra_paths never change on this path —
    a missing state record must not cause spurious redeploys."""
    env, ca, state = _extra_inputs_env(tmp_path)
    for comp in ("confirm", "cred-ui"):
        r = source_and("extra_inputs_changed %s" % comp, env_extra=env)
        assert r.returncode == 1, "%s has no extra_paths: %s" % (comp, r.stderr)
        assert "unknown component" not in r.stderr
    # and recording is a no-op for them (no state file created)
    r = source_and("record_extra_inputs confirm", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert not (state / "extra-inputs-hash").exists()


def test_extra_inputs_record_writes_single_digest_line(tmp_path):
    """record_extra_inputs writes one '<component>=<digest>' line without
    tearing or clobbering (atomicity comes from the write-tmp + rename in
    the implementation, which a single-threaded test cannot prove)."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"fake-ca-bytes")
    r = source_and("record_extra_inputs proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    rec = state / "extra-inputs-hash"
    assert rec.exists()
    lines = rec.read_text().splitlines()
    assert len(lines) == 1 and lines[0].startswith("proxy=")


def test_extra_inputs_state_file_not_world_readable(tmp_path):
    """umask 077 at the top of auto-deploy.sh keeps the state dir private —
    the record lives next to the watermark and must inherit that."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"fake-ca-bytes")
    r = source_and("record_extra_inputs proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    mode = (state / "extra-inputs-hash").stat().st_mode & 0o777
    assert mode & 0o077 == 0, "world/group readable: %o" % mode


def test_extra_paths_redirect_with_swapd_home(tmp_path):
    """Issue #108: the extra path must honor $SWAPD_HOME redirection so the
    suite never touches the live host."""
    env, ca, state = _extra_inputs_env(tmp_path)
    r = source_and("get_arr proxy extra_paths", env_extra=env)
    assert r.returncode == 0, r.stderr
    got = r.stdout.strip().splitlines()
    assert got == ["%s/.mitmproxy/mitmproxy-ca-cert.pem" % env["SWAPD_HOME"]], got


def test_deploy_sh_honors_with_proxy_ca_bundle():
    """Issue #303: deploy.sh must honor WITH_PROXY_CA_BUNDLE (components.conf
    advertises it as env-overridable); the default keeps the old literal so
    the install-paths coverage pin stays green."""
    with open(os.path.join(REPO, "proxy", "deploy.sh")) as f:
        body = f.read()
    assert "${WITH_PROXY_CA_BUNDLE:-/usr/local/share/with-proxy-ca/ca-bundle.crt}" in body, \
        "deploy.sh does not honor WITH_PROXY_CA_BUNDLE"
    assert "/usr/local/share/with-proxy-ca/ca-bundle.crt" in body, \
        "default literal missing — the install-paths pin would go stale"
    assert "--dest /usr/local/share/with-proxy-ca/ca-bundle.crt" not in body, \
        "hardcoded --dest literal still present alongside the env override"


# --- synthesized zero-width range (issue #302, Security review B1) --------

def _converged_ca_fixture(tmp_path, ca_bytes=b"fake-ca-bytes"):
    """Pinned fixture at head (watermark == origin/main, no pending range)
    with a recorded extra-inputs digest — the steady state. Returns
    (updater, state, env, ca)."""
    updater, state, env, base, mid, docs_only = _make_pinned_fixture(tmp_path)
    (state / "deployed-commit").write_text(docs_only + "\n")
    swapd = tmp_path / "swapd"
    ca_dir = swapd / ".mitmproxy"
    ca_dir.mkdir(parents=True)
    ca = ca_dir / "mitmproxy-ca-cert.pem"
    ca.write_bytes(ca_bytes)
    env = dict(env, SWAPD_HOME=str(swapd))
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; record_extra_inputs proxy",
                 env_extra=env, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    return updater, state, env, ca


def test_cmd_deploy_forces_proxy_on_ca_rotation_with_no_new_commits(tmp_path):
    """Issue #302's central case (Security review B1): watermark ==
    origin/main (no pending commits) but the CA rotated. cmd_deploy must
    NOT take the quiet noop path — it must synthesize a zero-width range
    and attempt the proxy deploy. The fixture repo has no proxy test
    files, so the proxy gate fails fast; the gate-fail audit line is the
    observable proof the deploy path (not the noop path) ran. No install
    step runs — gates come first."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    ca.write_bytes(b"fake-ca-bytes-rotated")  # rotation, zero new commits
    # No set -e: the expected gate-fail rc must not abort before the echo.
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "host-side inputs changed with no new commits" in out, out
    assert "CMD_RC=1" in r.stdout, out  # gate-fail, not a quiet 0
    # proxy is in the attempted deploy set (confirm joins via the shared
    # proxy-confirm install unit and its gate runs first alphabetically).
    assert re.search(r"components: .*\bproxy\b", out), out
    audit = (state / "audit.log").read_text()
    assert '"result":"noop"' not in audit, audit
    assert '"result":"gate-fail"' in audit, audit


def test_cmd_deploy_stays_quiet_when_ca_unchanged_and_no_new_commits(tmp_path):
    """Contrast: no rotation and no new commits — the tick stays on the
    quiet noop path (no synthesized deploy, no gate run)."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "host-side inputs changed with no new commits" not in out, out
    assert "CMD_RC=0" in r.stdout, out
    audit = (state / "audit.log").read_text()
    assert '"result":"noop"' in audit, audit
    assert '"result":"gate-fail"' not in audit, audit


def test_cmd_deploy_blocked_head_ignores_ca_rotation(tmp_path):
    """A blocked head (post-rollback) stays quiet even when the CA rotates:
    retrying the same rolled-back head would re-run the same failing
    install, and the rollback already audited + alerted."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    head = subprocess.run(["git", "rev-parse", "origin/main"], cwd=updater,
                          check=True, capture_output=True, text=True).stdout.strip()
    (state / "blocked-commit").write_text(head + "\n")
    ca.write_bytes(b"fake-ca-bytes-rotated")
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "host-side inputs changed with no new commits" not in out, out
    assert "CMD_RC=0" in r.stdout, out
    assert not (state / "audit.log").exists() or \
        '"result":"gate-fail"' not in (state / "audit.log").read_text()


# --- forced-deploy dampening (Security review B2) ----------------------------

def test_extra_inputs_forced_deploy_dampens_repeated_churn(tmp_path):
    """The CA path is swapd-writable: without dampening, rewriting CA bytes
    would force a full gated redeploy on every 10-minute tick. The first
    forced deploy records a timestamp; churn inside the window is damped
    (and the digest is NOT converged on a damped tick, so the change is
    still picked up once the window passes)."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"v1")
    r = source_and("record_extra_inputs proxy 1 && extra_inputs_changed proxy",
                   env_extra=env)
    assert r.returncode == 1, "recorded digest must converge: " + r.stdout + r.stderr
    assert "proxy_last_forced=" in (state / "extra-inputs-hash").read_text()
    ca.write_bytes(b"v2")  # churn inside the dampening window
    before = (state / "extra-inputs-hash").read_text()
    r = source_and("extra_inputs_changed proxy", env_extra=env)
    assert r.returncode == 1, "churn inside the window must be damped"
    assert "skipping" in (r.stdout + r.stderr), r.stdout + r.stderr
    after = (state / "extra-inputs-hash").read_text()
    assert before == after, "damped tick must not converge the digest"


def test_extra_inputs_forced_deploy_fires_again_after_window(tmp_path):
    """After the dampening window passes, a changed digest forces a deploy
    again. The timestamp is backdated instead of sleeping."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"v1")
    r = source_and("record_extra_inputs proxy 1", env_extra=env)
    assert r.returncode == 0, r.stderr
    rec = state / "extra-inputs-hash"
    rec.write_text(re.sub(r"^proxy_last_forced=.*$",
                          "proxy_last_forced=1", rec.read_text(),
                          flags=re.M))
    ca.write_bytes(b"v2")
    r = source_and("extra_inputs_changed proxy", env_extra=env)
    assert r.returncode == 0, \
        "change after the window must force again: " + r.stdout + r.stderr


def test_extra_inputs_nonforced_record_keeps_forced_timestamp(tmp_path):
    """Nit (3) reversal of the old re-baseline contract: a normal
    (non-forced) successful deploy must NOT drop the forced timestamp —
    the old code stripped it on every successful record, so any version
    deploy including the component silently reset the dampening window
    and re-armed the swapd-churn retry loop (Security review nit). The
    dampening epoch is now refreshed only by a forced deploy itself."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"v1")
    r = source_and("record_extra_inputs proxy 1", env_extra=env)
    assert r.returncode == 0, r.stderr
    before = (state / "extra-inputs-hash").read_text()
    m_before = re.search(r"^proxy_last_forced=(\d+)$", before, flags=re.M)
    assert m_before, before
    r = source_and("record_extra_inputs proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    after = (state / "extra-inputs-hash").read_text()
    m_after = re.search(r"^proxy_last_forced=(\d+)$", after, flags=re.M)
    assert m_after, "unforced record must keep the epoch line: " + after
    assert m_after.group(1) == m_before.group(1), \
        "unforced record must not refresh the epoch: " + after


# --- FIFO guard (Security review B3) ------------------------------------------

def test_extra_inputs_hash_never_blocks_on_fifo(tmp_path):
    """The CA path is swapd-writable; a planted FIFO must not hang the
    deploy tick (the old sha256sum-on-open would block while the tick held
    the single-flight lock; the helper opens O_NONBLOCK and refuses
    non-regular files at the open). A FIFO hashes as nonregular — which
    still counts as a change vs a real CA."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"real-ca")
    r = source_and("record_extra_inputs proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    ca.unlink()
    os.mkfifo(ca)
    r = run_bash(
        "export AUTO_DEPLOY_NO_MAIN=1; source ./deploy/auto-deploy.sh; "
        "timeout 10 bash -c 'export AUTO_DEPLOY_NO_MAIN=1; "
        "source ./deploy/auto-deploy.sh; "
        "extra_inputs_changed proxy'; echo CHANGED_RC=$?",
        env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CHANGED_RC=0" in r.stdout, \
        "FIFO at the CA path must count as a change without hanging: " + out


# --- privileged atomic read (Security review: TOCTOU + wrong-privilege) -----

def _hash_read(path, cap=1048576):
    """Direct invocation of the digest-read helper
    (deploy/extra_inputs_hash_read.py)."""
    r = subprocess.run(
        ["python3", os.path.join(REPO, "deploy", "extra_inputs_hash_read.py"),
         str(path), str(cap)],
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_extra_inputs_hash_read_helper_content_contract(tmp_path):
    """The helper's content line is a deterministic 64-hex digest that is
    content-sensitive: identical bytes hash identically, changed bytes
    hash differently."""
    f = tmp_path / "ca.pem"
    f.write_bytes(b"fake-ca-bytes")
    h1 = _hash_read(f)
    assert re.fullmatch(r"[0-9a-f]{64}", h1), h1
    assert _hash_read(f) == h1, "identical bytes must hash identically"
    f.write_bytes(b"fake-ca-bytes-rotated")
    assert _hash_read(f) != h1, "changed bytes must hash differently"


def test_extra_inputs_hash_read_helper_refuses_nonregular(tmp_path):
    """Symlink (live or dangling), FIFO, directory, and hardlink all hash
    as nonregular — the refusal is part of the open itself (O_NOFOLLOW),
    so there is no check-to-read window for a swapd-level writer to race,
    and a planted FIFO can never block the read."""
    real = tmp_path / "real.pem"
    real.write_bytes(b"real")
    link = tmp_path / "link.pem"
    link.symlink_to(real)
    assert _hash_read(link) == "nonregular", "live symlink must not be followed"
    dangling = tmp_path / "dangling.pem"
    dangling.symlink_to(tmp_path / "nope")
    assert _hash_read(dangling) == "nonregular", "dangling symlink is nonregular"
    fifo = tmp_path / "fifo.pem"
    os.mkfifo(fifo)
    assert _hash_read(fifo) == "nonregular", "FIFO must not be opened for read"
    assert _hash_read(tmp_path) == "nonregular", "directory must not be read"
    hard = tmp_path / "hard.pem"
    os.link(real, hard)
    assert _hash_read(hard) == "nonregular", \
        "hardlink refused like the deploy path (issue #299 discipline)"
    assert _hash_read(tmp_path / "absent.pem") == "missing"


def test_extra_inputs_hash_read_helper_honors_cap(tmp_path):
    """The cap is single-sourced from the shell's EXTRA_INPUTS_HASH_MAX_BYTES
    via argv: only the first <cap> bytes are hashed, but the full file size
    is folded in so growth past the cap still flips the digest."""
    a = tmp_path / "a.bin"
    a.write_bytes(b"x" * 10 + b"y" * 90)
    b = tmp_path / "b.bin"
    b.write_bytes(b"x" * 10 + b"z" * 90)
    assert _hash_read(a, cap=10) == _hash_read(b, cap=10), \
        "bytes past the cap must not affect the digest"
    c = tmp_path / "c.bin"
    c.write_bytes(b"x" * 10 + b"y" * 190)
    assert _hash_read(c, cap=10) != _hash_read(a, cap=10), \
        "growth past the cap must still flip the digest (size folded in)"


def test_extra_inputs_hash_reads_through_sudo_run(tmp_path):
    """Security BLOCKING 2: the digest read must go through sudo_run (the
    deploy-privilege wrapper), not a bare shell read — every other consumer
    of the path reads privileged, so the digest must too. Override sudo_run
    with a marker-emitting passthrough (marker to stderr, so the digest
    material on stdout stays clean) and assert the marker appears."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"fake-ca-bytes")
    r = source_and(
        "sudo_run() { echo SUDO_RUN_MARKER >&2; \"$@\"; }; "
        "extra_inputs_hash proxy",
        env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "SUDO_RUN_MARKER" in r.stderr, \
        "extra_inputs_hash must route the read through sudo_run"
    assert re.fullmatch(r"[0-9a-f]{64}", r.stdout.strip()), r.stdout


def test_extra_inputs_symlink_never_followed_through_shell_path(tmp_path):
    """Through the shell path: a symlink at the CA path hashes differently
    from the content it points at — i.e. it is refused, not followed. The
    deploy path fail-closes on symlinks, so following would hand a
    swapd-level writer a 1-bit change oracle on any root-readable file the
    link points at."""
    env, ca, state = _extra_inputs_env(tmp_path)
    target = tmp_path / "real-target.pem"
    target.write_bytes(b"real-ca")
    ca.symlink_to(target)
    r1 = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r1.returncode == 0, r1.stderr
    ca.unlink()
    ca.write_bytes(b"real-ca")
    r2 = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r2.returncode == 0, r2.stderr
    assert r1.stdout.strip() != r2.stdout.strip(), \
        "symlink must hash differently from the content it points at"


def test_extra_inputs_hash_missing_helper_fails_loud(tmp_path):
    """A stale installed copy (init not re-run since the helper was added)
    must fail LOUD, not silently hash everything as a constant digest —
    silent degradation would switch off rotation detection (#302's whole
    purpose) with zero alerting."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"fake-ca-bytes")
    r = source_and("SCRIPT_DIR=/nonexistent-dir; extra_inputs_hash proxy",
                   env_extra=env)
    assert r.returncode != 0, "missing helper must fail, not degrade"
    assert "extra_inputs_hash_read.py" in r.stderr


def test_extra_inputs_changed_degrades_clean_on_missing_helper(tmp_path):
    """Missing helper + recorded digest must NOT count as changed: h=""
    would mismatch the recorded digest and force an hourly full redeploy
    that can never converge (record_extra_inputs aborts under set -e on
    the same missing helper). QA review: the tick invokes
    extra_inputs_changed as an `if` condition (errexit off), so the test
    reproduces that context — a top-level call under the sourced script's
    `set -e` would just abort the shell instead of exercising the
    h="" fall-through."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"fake-ca-bytes")
    r = source_and("record_extra_inputs proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    r = source_and("SCRIPT_DIR=/nonexistent-dir; "
                   "if extra_inputs_changed proxy; then echo CHANGED; "
                   "else echo UNCHANGED; fi",
                   env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "UNCHANGED" in r.stdout, \
        "missing helper must degrade to not-changed: " + r.stdout + r.stderr


def test_cmd_status_tolerates_missing_helper(tmp_path):
    """cmd_status is diagnostic: a broken digest read must degrade to an
    ERROR line, not abort the whole status output."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set -e; "
                 "SCRIPT_DIR=/nonexistent-dir; cmd_status; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=0" in r.stdout, out
    assert "extra-inputs(proxy): ERROR" in out, out


def test_cmd_deploy_forced_failure_never_blocks_head(tmp_path):
    """Engineering review: a failed same-commit (extra-inputs-forced)
    deploy must not mark HEAD blocked — the commit is fine, so the next
    tick retries instead of wedging the box until the next code change.
    Gates are stubbed to pass (a fake python3 first on PATH); the proxy
    install then fails (no proxy/deploy.sh in the fixture repo),
    exercising the do_rollback no_block path. The forced snapshot also
    gets its own '-extra-inputs' dir instead of clobbering the commit's
    own snapshot."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake_py = bindir / "python3"
    fake_py.write_text("#!/bin/sh\nexit 0\n")
    fake_py.chmod(0o755)
    env = dict(env, PATH=str(bindir) + os.pathsep + os.environ["PATH"])
    ca.write_bytes(b"fake-ca-bytes-rotated")  # rotation, zero new commits
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=1" in r.stdout, out
    assert not (state / "blocked-commit").exists(), \
        "a failed forced deploy must not block HEAD: " + out
    audit = (state / "audit.log").read_text()
    assert '"result":"deploy-fail"' in audit, audit
    assert '"result":"rolled-back"' in audit, audit
    assert '"trigger":"extra-inputs"' in audit, audit
    snaps = [d for d in (state / "snapshots").iterdir() if d.is_dir()]
    assert any(d.name.endswith("-extra-inputs") for d in snaps), \
        "forced snapshot needs its own dir: %s" % [d.name for d in snaps]


def test_cmd_deploy_forced_gate_fail_audit_has_trigger(tmp_path):
    """The audit trail must not masquerade a same-commit forced deploy as
    a version deploy: the gate-fail line carries trigger=extra-inputs."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    ca.write_bytes(b"fake-ca-bytes-rotated")
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=1" in r.stdout, out
    audit = (state / "audit.log").read_text()
    assert '"result":"gate-fail"' in audit, audit
    assert '"trigger":"extra-inputs"' in audit, audit
    assert not (state / "blocked-commit").exists()


def test_cmd_check_reports_extra_inputs_on_quiet_tick(tmp_path):
    """cmd_check stays honest: on an up-to-date tick with a rotated CA it
    reports that deploy would force-redeploy the proxy (Engineering
    review: check must not claim 'nothing would deploy' when deploy
    would)."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    ca.write_bytes(b"fake-ca-bytes-rotated")
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; cmd_check; echo CHECK_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CHECK_RC=0" in r.stdout, out
    assert "deploy would force-redeploy it" in out, out


def test_cmd_status_shows_extra_inputs_state(tmp_path):
    """cmd_status surfaces the recorded vs current extra-inputs digests so
    a proxy redeploy with an unchanged watermark is explainable (QA
    review)."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; cmd_status",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "extra-inputs(proxy): in sync" in out, out
    ca.write_bytes(b"fake-ca-bytes-rotated")
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; cmd_status",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "extra-inputs(proxy): CHANGED" in out, out


def test_cmd_status_on_fresh_state_dir_without_extra_inputs_record(tmp_path):
    """Engineering review B1: cmd_status must not abort (exit 2 under
    set -euo pipefail) when the extra-inputs state file does not exist —
    reachable after init before the first successful proxy deploy, or
    after any state-dir wipe. The sed read in cmd_status is now guarded
    like extra_inputs_changed's; assert exit 0 and the CHANGED line."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    (state / "extra-inputs-hash").unlink()
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set -e; cmd_status; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=0" in r.stdout, out
    assert "extra-inputs(proxy): CHANGED" in out, out


# --- Security-review round 2 (BLOCKING 1): failed forced deploys dampened ---

def test_extra_inputs_failed_forced_deploy_dampens_retry(tmp_path):
    """Security review BLOCKING 1: dampening must apply to failed forced
    deploys too. A swapd-level writer plants a persistently-failing input
    (e.g. a symlink at the CA path that build_ca_bundle.py fail-closes on);
    without attempt-time dampening the deploy/rollback churns on every
    10-minute tick forever. The fix records the attempt at decision time —
    the digest stays unconverged, so the retry still happens after the
    window passes. The gate-fail here stands in for the persistently-failing
    input (fixture repo has no proxy test files)."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    rec = state / "extra-inputs-hash"
    pre_rotation = rec.read_text()
    ca.write_bytes(b"fake-ca-bytes-rotated")  # rotation, zero new commits
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=1" in r.stdout, out  # gate-fail, not a quiet noop
    audit = (state / "audit.log").read_text()
    gate_fails_before = audit.count('"result":"gate-fail"')
    assert gate_fails_before >= 1, audit
    post = rec.read_text()
    assert "proxy_last_forced=" in post, \
        "the attempt must be recorded even though the deploy failed: " + out
    assert pre_rotation in post, \
        "a failed deploy must NOT converge the digest: " + post
    # The very next tick is damped — no new forced deploy, quiet rc=0.
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=0" in r.stdout, out
    assert "skipping" in out, out
    audit = (state / "audit.log").read_text()
    assert audit.count('"result":"gate-fail"') == gate_fails_before, \
        "damped tick must not attempt another forced deploy: " + audit
    # ... but the retry is preserved: once the window passes, the still-
    # unconverged digest forces the deploy again.
    rec.write_text(re.sub(r"^proxy_last_forced=.*$", "proxy_last_forced=1",
                          post, flags=re.M))
    r = source_and("extra_inputs_changed proxy", env_extra=env)
    assert r.returncode == 0, \
        "unconverged digest must force again after the window: " + r.stdout + r.stderr


def test_note_forced_attempt_records_timestamp_without_converging(tmp_path):
    """note_forced_attempt (BLOCKING 1 fix) records the attempt epoch
    without converging the digest, and is a no-op for components that
    declare no extra_paths."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"v1")
    r = source_and("note_forced_attempt proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    txt = (state / "extra-inputs-hash").read_text()
    assert "proxy_last_forced=" in txt, txt
    assert not re.search(r"^proxy=[0-9a-f]{64}$", txt, flags=re.M), \
        "attempt must not converge the digest: " + txt
    r = source_and("note_forced_attempt confirm", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "confirm_last_forced" not in (state / "extra-inputs-hash").read_text()


# --- Security-review round 2 (BLOCKING 2): bounded hashing -------------------

def test_extra_inputs_hash_caps_read_at_1mib(tmp_path):
    """Security review BLOCKING 2: the CA path is swapd-writable; hashing
    must be bounded or a sparse multi-GB plant stalls the tick while it
    holds the single-flight lock. Only the first
    EXTRA_INPUTS_HASH_MAX_BYTES are hashed, with the file size folded in —
    so pure growth past the cap still flips the digest."""
    env, ca, state = _extra_inputs_env(tmp_path)
    cap = 1048576
    ca.write_bytes(b"A" * cap + b"B" * 1024)
    r = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    h1 = r.stdout.strip()
    # Bytes past the cap are not hashed ...
    ca.write_bytes(b"A" * cap + b"C" * 1024)
    r = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == h1, "bytes past the cap must not flip the digest"
    # ... but bytes inside the cap are ...
    ca.write_bytes(b"Z" + b"A" * (cap - 1) + b"B" * 1024)
    r = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() != h1, "bytes inside the cap must flip the digest"
    # ... and pure growth (same prefix, larger size) is detected via the
    # folded-in size.
    ca.write_bytes(b"A" * cap + b"B" * 2048)
    r = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() != h1, "size growth must flip the digest"


def test_extra_inputs_hash_sparse_huge_file_completes(tmp_path):
    """A 50 GiB sparse plant (truncate is instant) must hash in bounded
    time — no multi-GB read while holding the tick lock."""
    env, ca, state = _extra_inputs_env(tmp_path)
    subprocess.run(["truncate", "-s", "50G", str(ca)], check=True)
    r = source_and("extra_inputs_hash proxy; echo HASH_OK", env_extra=env)
    assert r.returncode == 0, r.stderr
    assert "HASH_OK" in r.stdout, r.stdout + r.stderr


def test_extra_inputs_hash_treats_symlink_as_unreadable(tmp_path):
    """Security review: symlinks are not followed. build_ca_bundle.py
    fail-closes on symlinks, so a symlinked CA can never converge — and
    following it would hand a swapd writer a 1-bit/hour change oracle on
    any root-readable file the link points at. A symlinked CA hashes as
    'unreadable'; retargeting it does not flip the digest."""
    env, ca, state = _extra_inputs_env(tmp_path)
    ca.write_bytes(b"real-ca")
    r = source_and("record_extra_inputs proxy", env_extra=env)
    assert r.returncode == 0, r.stderr
    target = tmp_path / "target1"
    target.write_bytes(b"target-one-bytes")
    ca.unlink()
    ca.symlink_to(target)
    r = source_and("extra_inputs_changed proxy", env_extra=env)
    assert r.returncode == 0, "symlinked CA must count as changed: " + r.stderr
    r1 = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r1.returncode == 0, r1.stderr
    target2 = tmp_path / "target2"
    target2.write_bytes(b"completely-different-bytes")
    ca.unlink()
    ca.symlink_to(target2)
    r2 = source_and("extra_inputs_hash proxy", env_extra=env)
    assert r2.returncode == 0, r2.stderr
    assert r1.stdout.strip() == r2.stdout.strip(), \
        "symlink retarget must not flip the digest (no change oracle)"


# --- Security-review round 2 (BLOCKING 3): export the override ---------------

def test_components_conf_exports_with_proxy_ca_bundle(tmp_path):
    """Issue #303 follow-up (Security review BLOCKING 3): components.conf
    must export WITH_PROXY_CA_BUNDLE so a set-but-not-exported override
    propagates into the child shell running proxy/deploy.sh. Otherwise
    snapshot/rollback covers the override path while deploy.sh silently
    writes the default — split-brain coverage of exactly the artifact
    #303 exists to guarantee."""
    env, ca, state = _extra_inputs_env(tmp_path)
    # Default: the child sees the default literal.
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; source ./deploy/auto-deploy.sh; "
                 "bash -c 'echo CHILD_VAL=$WITH_PROXY_CA_BUNDLE'",
                 env_extra=env, cwd=REPO)
    assert "CHILD_VAL=/usr/local/share/with-proxy-ca/ca-bundle.crt" in r.stdout, \
        r.stdout + r.stderr
    # Set-but-not-exported override: the child must still see it.
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; source ./deploy/auto-deploy.sh; "
                 "WITH_PROXY_CA_BUNDLE=/tmp/custom-bundle.crt; "
                 "bash -c 'echo CHILD_VAL=$WITH_PROXY_CA_BUNDLE'",
                 env_extra=env, cwd=REPO)
    assert "CHILD_VAL=/tmp/custom-bundle.crt" in r.stdout, \
        r.stdout + r.stderr


# --- Engineering-review nit 3: pin the successful forced-deploy wiring ------

def test_cmd_deploy_successful_forced_deploy_wiring(tmp_path):
    """Engineering review: pin the successful forced deploy's wiring end to
    end (a stub component with passing gate/install via a custom manifest):
    the synthesized zero-width deploy runs, the ok audit line carries
    trigger=extra-inputs, the forced timestamp is recorded, the snapshot
    uses the -extra-inputs dir, and the watermark is untouched."""
    updater, state, env, base, mid, docs_only = _make_pinned_fixture(tmp_path)
    (state / "deployed-commit").write_text(docs_only + "\n")
    swapd = tmp_path / "swapd"
    ca_dir = swapd / ".mitmproxy"
    ca_dir.mkdir(parents=True)
    ca = ca_dir / "mitmproxy-ca-cert.pem"
    ca.write_bytes(b"fake-ca")
    env = dict(env, SWAPD_HOME=str(swapd))
    tconf = tmp_path / "stub.conf"
    tconf.write_text(
        'COMPONENTS=(stub)\n'
        'stub_paths=("docs/")\n'
        'stub_services=()\n'
        'stub_user_services=()\n'
        'stub_tests="true"\n'
        'stub_health=()\n'
        'stub_install="true"\n'
        'stub_install_unit=""\n'
        'stub_checkout_sync=""\n'
        'stub_install_paths=()\n'
        'stub_extra_paths=("$SWAPD_HOME/.mitmproxy/mitmproxy-ca-cert.pem")\n'
    )
    env = dict(env, UPDATER_COMPONENTS_CONF=str(tconf))
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; record_extra_inputs stub",
                 env_extra=env, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    ca.write_bytes(b"fake-ca-rotated")  # rotation, zero new commits
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=0" in r.stdout, out
    assert "host-side inputs changed with no new commits" in out, out
    audit = (state / "audit.log").read_text()
    assert re.search(r'"result":"ok".*"trigger":"extra-inputs"', audit), audit
    rec = (state / "extra-inputs-hash").read_text()
    assert "stub_last_forced=" in rec, rec
    assert re.search(r"^stub=[0-9a-f]{64}$", rec, flags=re.M), \
        "successful forced deploy must converge the digest: " + rec
    snaps = [d for d in (state / "snapshots").iterdir() if d.is_dir()]
    assert any(d.name.endswith("-extra-inputs") for d in snaps), \
        "forced snapshot needs its own dir: %s" % [d.name for d in snaps]
    assert (state / "deployed-commit").read_text().strip() == docs_only, \
        "zero-width deploy must not advance the watermark"


# --- extra-inputs review nits (distribution): trigger tagging, rollback ----
# --- reconciliation, _last_forced preservation -----------------------------

def _forced_stub_fixture(tmp_path, ca_bytes=b"fake-ca"):
    """Stub component (passing gate/install, extra_paths on a tmp CA file)
    pinned at head with a converged digest — the rig for forced-deploy and
    rollback tests. Returns (updater, state, env, ca, base, docs_only)."""
    updater, state, env, base, mid, docs_only = _make_pinned_fixture(tmp_path)
    (state / "deployed-commit").write_text(docs_only + "\n")
    swapd = tmp_path / "swapd"
    ca_dir = swapd / ".mitmproxy"
    ca_dir.mkdir(parents=True)
    ca = ca_dir / "mitmproxy-ca-cert.pem"
    ca.write_bytes(ca_bytes)
    installed = swapd / "installed.txt"
    installed.write_text("installed")
    (swapd / "VERSION").write_text("0.9.9-test\n")
    env = dict(env, SWAPD_HOME=str(swapd))
    tconf = tmp_path / "stub.conf"
    tconf.write_text(
        'COMPONENTS=(stub)\n'
        'stub_paths=("docs/")\n'
        'stub_services=()\n'
        'stub_user_services=()\n'
        'stub_tests="true"\n'
        'stub_health=()\n'
        'stub_install="true"\n'
        'stub_install_unit=""\n'
        'stub_checkout_sync=""\n'
        'stub_install_paths=("$SWAPD_HOME/installed.txt")\n'
        'stub_extra_paths=("$SWAPD_HOME/.mitmproxy/mitmproxy-ca-cert.pem")\n'
    )
    env = dict(env, UPDATER_COMPONENTS_CONF=str(tconf))
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; record_extra_inputs stub",
                 env_extra=env, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    return updater, state, env, ca, base, docs_only


def _forced_audit_line(audit, result):
    m = re.search(r'\{[^{}]*"result":"%s"[^{}]*\}' % re.escape(result), audit)
    assert m, "expected a %s audit line: %s" % (result, audit)
    return m.group(0)


def test_cmd_deploy_forced_snapshot_fail_audit_has_trigger(tmp_path):
    """Nit (1): on a same-commit forced deploy, the snapshot-fail audit line
    must carry trigger=extra-inputs — it previously masqueraded as a version
    deploy. mkdir is overridden to fail only under the snapshots dir."""
    updater, state, env, ca, base, docs_only = _forced_stub_fixture(tmp_path)
    ca.write_bytes(b"fake-ca-rotated")  # rotation, zero new commits
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; "
                 "mkdir() { case \"$*\" in *snapshots*) return 1;; *) command mkdir \"$@\";; esac; }; "
                 "set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=1" in r.stdout, out
    audit = (state / "audit.log").read_text()
    line = _forced_audit_line(audit, "snapshot-fail")
    assert '"trigger":"extra-inputs"' in line, \
        "snapshot-fail line must carry the trigger: " + line


def test_cmd_deploy_forced_reload_fail_audit_has_trigger(tmp_path):
    """Nit (1): the reload-fail audit line must carry trigger=extra-inputs.
    (reload_and_enable unconditionally returns 0 today, so the override
    exercises the audit construction on that path.)"""
    updater, state, env, ca, base, docs_only = _forced_stub_fixture(tmp_path)
    ca.write_bytes(b"fake-ca-rotated")  # rotation, zero new commits
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; "
                 "reload_and_enable() { return 1; }; "
                 "set +e; cmd_deploy; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=1" in r.stdout, out
    audit = (state / "audit.log").read_text()
    line = _forced_audit_line(audit, "reload-fail")
    assert '"trigger":"extra-inputs"' in line, \
        "reload-fail line must carry the trigger: " + line


def test_record_extra_inputs_preserves_last_forced_on_unforced_deploy(tmp_path):
    """Nit (3): a successful non-forced deploy must not clear the
    _last_forced dampening epoch — the old code stripped it on every
    successful record, so any version deploy including the component
    silently re-armed the swapd-churn retry loop."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    rec = state / "extra-inputs-hash"
    before = rec.read_text()
    assert re.search(r"^proxy=[0-9a-f]{64}$", before, flags=re.M), before
    rec.write_text(before + "proxy_last_forced=1234567890\n")
    ca.write_bytes(b"fake-ca-bytes-changed")
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; record_extra_inputs proxy 0",
                 env_extra=env, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    after = rec.read_text()
    assert "proxy_last_forced=1234567890" in after, \
        "unforced record must preserve the dampening epoch: " + after
    assert after.count("proxy_last_forced=") == 1, after
    assert len(re.findall(r"^proxy=", after, flags=re.M)) == 1, \
        "digest line must not duplicate: " + after
    m = re.search(r"^proxy=([0-9a-f]{64})$", after, flags=re.M)
    assert m, "digest must converge on success: " + after
    fresh = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                     "source ./deploy/auto-deploy.sh; extra_inputs_hash proxy",
                     env_extra=env, cwd=REPO).stdout.strip()
    assert m.group(1) == fresh, "digest must match on-disk inputs"


def test_record_extra_inputs_forced_updates_last_forced(tmp_path):
    """Contrast pin: a forced deploy DOES refresh the _last_forced epoch."""
    updater, state, env, ca = _converged_ca_fixture(tmp_path)
    rec = state / "extra-inputs-hash"
    rec.write_text(rec.read_text() + "proxy_last_forced=1234567890\n")
    r = run_bash("set -e; export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; record_extra_inputs proxy 1",
                 env_extra=env, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr
    after = rec.read_text()
    assert "proxy_last_forced=1234567890" not in after, after
    m = re.search(r"^proxy_last_forced=(\d+)$", after, flags=re.M)
    assert m, "forced record must write a fresh epoch: " + after
    assert int(m.group(1)) > 1234567890, after


def test_cmd_rollback_reconciles_extra_inputs_state(tmp_path):
    """Nit (2): a manual rollback restores the component files, but the
    recorded extra-inputs digest is post-deploy. cmd_rollback must
    reconcile it to the on-disk reality (and preserve _last_forced) —
    otherwise the next tick compares rolled-back reality against the stale
    digest and force-redeploys the rolled-back component."""
    updater, state, env, ca, base, docs_only = _forced_stub_fixture(tmp_path)
    rec = state / "extra-inputs-hash"
    stale = rec.read_text()
    assert re.search(r"^stub=[0-9a-f]{64}$", stale, flags=re.M), stale
    rec.write_text(stale + "stub_last_forced=1234567890\n")
    # Reality drifts from the record (snapshot restored an extra-input
    # path, or the operator changed it between deploy and rollback).
    ca.write_bytes(b"fake-ca-post-rollback")
    snapdir = state / "snapshots" / docs_only
    snapdir.mkdir(parents=True)
    (snapdir / "FROM_COMMIT").write_text(base + "\n")
    (snapdir / "COMPONENTS").write_text("stub\n")
    (snapdir / "MANIFEST").write_text("ABSENT /tmp/spark-vm-rollback-test-absent\n")
    r = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                 "source ./deploy/auto-deploy.sh; set -e; cmd_rollback; echo CMD_RC=$?",
                 env_extra=env, cwd=REPO)
    out = r.stdout + r.stderr
    assert "CMD_RC=0" in r.stdout, out
    audit = (state / "audit.log").read_text()
    assert '"result":"manual-rollback"' in audit, audit
    after = rec.read_text()
    fresh = run_bash("export AUTO_DEPLOY_NO_MAIN=1; "
                     "source ./deploy/auto-deploy.sh; extra_inputs_hash stub",
                     env_extra=env, cwd=REPO).stdout.strip()
    assert re.search(r"^stub=%s$" % re.escape(fresh), after, flags=re.M), \
        "digest must be reconciled to on-disk reality: " + after
    assert "stub_last_forced=1234567890" in after, \
        "rollback must preserve the dampening epoch: " + after


# --- issue #457: trigger-tag invariant --------------------------------------

def _shell_function_body_lines(name):
    """Extract a top-level shell function body from auto-deploy.sh.

    Terminates at the first column-0 `}`; callers add anchor assertions
    so a future nested lone-`}` truncating the extraction fails loudly
    instead of silently weakening the invariant.
    """
    lines = open(SCRIPT).read().splitlines()
    start = next(i for i, l in enumerate(lines)
                 if l.startswith(name + "() {"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "}")
    return lines[start + 1:end]


def test_cmd_deploy_all_deploy_audit_lines_carry_trigger_tag():
    """Issue #457 (QA + Security review): every `audit 'deploy'` line in the
    deploy path must carry the trigger tag — `"$trig"` inside cmd_deploy,
    `"$atrig"` inside do_rollback (its 7th arg, which every call site must
    pass as `"$trig"`). Without the tag, a forced extra-inputs deploy (or
    its rollback) masquerades as a version deploy in the audit trail.
    Source-level invariant: covers all current lines AND future regressions
    without an e2e test per failure path. The pull-only line is exempt: it
    never deploys, so its result is self-describing and cannot masquerade."""
    deploy_lines = _shell_function_body_lines("cmd_deploy")
    rollback_lines = _shell_function_body_lines("do_rollback")
    # Anchor assertions: the extractor must have seen the whole function,
    # or a future edit could truncate coverage silently.
    assert any('"result":"ok"' in l for l in deploy_lines), \
        "cmd_deploy extraction truncated — anchor 'ok' line missing"
    assert any('"result":"rolled-back"' in l for l in rollback_lines), \
        "do_rollback extraction truncated — anchor 'rolled-back' missing"

    def audit_deploy_lines(lines):
        return [l for l in lines
                if re.search(r"""\baudit\s+["']deploy["']""", l)]

    deploy_audit = audit_deploy_lines(deploy_lines)
    rollback_audit = audit_deploy_lines(rollback_lines)
    assert deploy_audit and rollback_audit, \
        "no audit 'deploy' lines found — extractor stale?"

    untagged = [l.strip() for l in deploy_audit
                if '"$trig"' not in l
                and '"result":"pull-only"' not in l]
    assert not untagged, (
        "cmd_deploy audit 'deploy' lines missing the \"$trig\" "
        "trigger tag:\n" + "\n".join(untagged))

    # do_rollback carries the tag as its 7th positional arg ($atrig).
    untagged_rb = [l.strip() for l in rollback_audit
                   if '"$atrig"' not in l]
    assert not untagged_rb, (
        "do_rollback audit 'deploy' lines missing the \"$atrig\" "
        "trigger tag:\n" + "\n".join(untagged_rb))

    # Every do_rollback call site inside cmd_deploy must pass "$trig" as
    # the 7th arg, or the tag never reaches the audit line.
    call_sites = [l for l in deploy_lines
                  if re.search(r"""\bdo_rollback\s""", l)
                  and not l.lstrip().startswith("#")]
    assert call_sites, "no do_rollback call sites found in cmd_deploy?"
    missing_trig = [l.strip() for l in call_sites if '"$trig"' not in l]
    assert not missing_trig, (
        "do_rollback call sites not passing \"$trig\":\n"
        + "\n".join(missing_trig))
