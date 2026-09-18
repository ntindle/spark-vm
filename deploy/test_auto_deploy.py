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
    r = source_and(r'''
set -e
tmp=$(mktemp); tmp2=$(mktemp)
for c in "${COMPONENTS[@]}"; do get_arr "$c" paths; done | sort >"$tmp"
sort -u "$tmp" >"$tmp2"
cmp -s "$tmp" "$tmp2" || { echo "OVERLAP"; diff "$tmp" "$tmp2"; exit 1; }
echo NO_OVERLAP
''')
    assert "NO_OVERLAP" in r.stdout, r.stderr + r.stdout


def test_component_name_mapping():
    """cred-ui (hyphen) resolves to cred_ui_* vars."""
    r = source_and('get_arr cred-ui paths')
    assert r.returncode == 0, r.stderr
    assert "cred-ui/" in r.stdout


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
    }
    missing = required - listed
    assert not missing, "missing from proxy_install_paths: %s" % sorted(missing)
    # Non-vacuous: deploy.sh really does write those targets.
    with open(os.path.join(REPO, "proxy", "deploy.sh")) as f:
        body = f.read()
    for t in required:
        assert t in body, "deploy.sh no longer writes %s (test is stale)" % t


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
    for d in (swapd, bindir, sysd):
        d.mkdir(parents=True)
    (swapd / "swap_addon.py").write_text("OLD ADDON")
    (bindir / "with-proxy").write_text("OLD PROXY")
    (sysd / "swap-proxy.service").write_text("OLD UNIT")
    env = {
        "UPDATER_STATE_DIR": str(state),
        "SWAPD_HOME": str(swapd),
        "BIN_DIR": str(bindir),
        "SYSTEMD_DIR": str(sysd),
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
    # a file that did not exist is recorded as ABSENT
    assert re.search(r"^ABSENT .*grant-writer$", manifest, re.M)

    # mutate the installed files, then roll back
    (swapd / "swap_addon.py").write_text("NEW ADDON")
    (bindir / "with-proxy").write_text("NEW PROXY")
    r = source_and("restore_snapshot %s" % snap, env_extra=env)
    assert r.returncode == 0, r.stderr + r.stdout
    assert (swapd / "swap_addon.py").read_text() == "OLD ADDON"
    assert (bindir / "with-proxy").read_text() == "OLD PROXY"
    assert (sysd / "swap-proxy.service").read_text() == "OLD UNIT"


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
    r = run_bash("command -v shellcheck >/dev/null && "
                 "shellcheck -S warning deploy/auto-deploy.sh proxy/deploy.sh "
                 "|| echo NO_SHELLCHECK")
    if "NO_SHELLCHECK" not in r.stdout:
        assert r.returncode == 0, r.stdout + r.stderr
