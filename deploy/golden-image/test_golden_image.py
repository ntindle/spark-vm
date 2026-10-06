"""Tests for the golden-image producer (#1087, F-P1).

Covers the recipe (Dockerfile), the daemon set (supervisord.conf), the
build driver (build-image.sh), and the CI job (.github/workflows/golden-image.yml).
Every test that asserts a refusal also proves the refusal is non-vacuous:
the same invocation against a conforming fixture must succeed.
"""
import configparser
import json
import os
import re
import shutil
import subprocess

import pytest

GOLDEN_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(GOLDEN_DIR))
DOCKERFILE = os.path.join(GOLDEN_DIR, "Dockerfile")
SUPERVISORD_CONF = os.path.join(GOLDEN_DIR, "supervisord.conf")
BUILD_IMAGE = os.path.join(GOLDEN_DIR, "build-image.sh")
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "golden-image.yml")
SCAN_SCRIPT = os.path.join(REPO_ROOT, "harness", "scan-baked-secrets.sh")


def _dockerfile_text():
    with open(DOCKERFILE, encoding="utf-8") as f:
        return f.read()


# --- recipe (Dockerfile) -------------------------------------------------------


def test_dockerfile_no_latest_tags():
    """No image reference may float on :latest — every layer pins forward."""
    found = 0
    for line in _dockerfile_text().splitlines():
        m = re.match(r"\s*FROM\s+(\S+)", line, re.IGNORECASE)
        if m:
            found += 1
            assert ":latest" not in m.group(1).lower(), line
    assert found >= 1, "no FROM lines found — the test would pass vacuously"


def test_dockerfile_requires_pin_args():
    """SPARKVM_VERSION/SPARKVM_SHA build args exist and the recipe fails
    closed when the pin is empty (D-P1)."""
    text = _dockerfile_text()
    assert re.search(r"^ARG SPARKVM_VERSION=", text, re.M)
    assert re.search(r"^ARG SPARKVM_SHA=", text, re.M)
    # fail-closed RUN checks for both pins
    assert 'test -n "$SPARKVM_SHA"' in text
    assert 'test "$SPARKVM_VERSION" != ""' in text


def test_dockerfile_recipe_default_matches_tree_version():
    """The recipe's ARG SPARKVM_VERSION default must equal the tree's VERSION:
    a recipe that defaults to a different version than the tree being baked
    is a silent pin (build-image.sh checks this too; the Dockerfile is the
    second line of defense)."""
    m = re.search(r"^ARG SPARKVM_VERSION=(\S+)", _dockerfile_text(), re.M)
    assert m, "ARG SPARKVM_VERSION default missing"
    with open(os.path.join(REPO_ROOT, "VERSION"), encoding="utf-8") as f:
        assert m.group(1) == f.read().strip()


def test_dockerfile_oci_labels():
    text = _dockerfile_text()
    for label in (
        "org.opencontainers.image.title",
        "org.opencontainers.image.version",
        "org.opencontainers.image.revision",
    ):
        assert label in text, label
    # the version/revision labels must record the pin args, not literals
    assert 'org.opencontainers.image.version="$SPARKVM_VERSION"' in text
    assert 'org.opencontainers.image.revision="$SPARKVM_SHA"' in text


def test_dockerfile_runs_gate_tooling():
    """The recipe generates + preflights the manifest and installs the gate
    fixture — the D-P1 artifact and the gate procedure's fixture step."""
    text = _dockerfile_text()
    assert "harness/generate-image-manifest.sh" in text
    assert "harness/check-image-manifest.sh" in text
    assert "harness/install-gate-fixture.sh" in text
    assert "proxy/deploy.sh --no-restart" in text


# --- daemon set (supervisord.conf) ----------------------------------------------


def _supervisord():
    cfg = configparser.ConfigParser()
    cfg.read(SUPERVISORD_CONF)
    return cfg


def test_supervisord_program_set():
    cfg = _supervisord()
    programs = {s.split(":", 1)[1] for s in cfg.sections() if s.startswith("program:")}
    assert programs == {
        "sshd",
        "swap-proxy",
        "swap-inference",
        "confirmd",
        "cred-ui",
        "cua-stack",
        "cua-bridge",
        "cua-keepalive",
    }, programs


def test_supervisord_privilege_split():
    """The full program→user mapping: sshd is the ONLY root program; the
    proxy daemons run as swapd (mirroring the systemd units), the UI/CUA
    stack as agent. A daemon that silently runs as root widens the image's
    privilege surface — checking only a subset would let one through."""
    cfg = _supervisord()
    expected = {
        "sshd": "root",
        "swap-proxy": "swapd",
        "swap-inference": "swapd",
        "confirmd": "swapd",
        "cred-ui": "agent",
        "cua-stack": "agent",
        "cua-bridge": "agent",
        "cua-keepalive": "agent",
    }
    programs = {
        s.split(":", 1)[1]: cfg[s].get("user")
        for s in cfg.sections()
        if s.startswith("program:")
    }
    assert programs == expected, programs


def test_supervisord_no_public_listener():
    """supervisord's own inet HTTP server must stay absent — the recipe's
    control surface is the services, not the supervisor."""
    cfg = _supervisord()
    assert not any(s.startswith("inet_http_server") for s in cfg.sections())


def _unit_exec_start(unit_file):
    """Read a systemd unit's ExecStart verbatim — the source of truth the
    supervisord conf must mirror."""
    with open(os.path.join(REPO_ROOT, unit_file), encoding="utf-8") as f:
        for line in f:
            m = re.match(r"ExecStart=(.+)", line.strip())
            if m:
                return m.group(1).strip()
    raise AssertionError(f"no ExecStart in {unit_file}")


def test_supervisord_commands_mirror_units():
    """The supervisord commands must contain the units' ExecStart verbatim —
    if a unit changes and the conf doesn't (the exact silent divergence
    this guards), the test fails."""
    cfg = _supervisord()
    for prog, unit in (
        ("swap-proxy", "proxy/swap-proxy.service"),
        ("swap-inference", "proxy/swap-inference.service"),
        ("confirmd", "confirm/confirmd.service"),
    ):
        exec_start = _unit_exec_start(unit)
        cmd = cfg[f"program:{prog}"]["command"]
        assert exec_start in cmd, f"{prog}: unit ExecStart not mirrored in supervisord command"


# --- build driver (build-image.sh) ----------------------------------------------
#
# The driver builds from REPO_OVERRIDE when set; the fixtures below assemble
# a scratch git repo carrying the real driver inputs (Dockerfile with the
# real ARG default, the real version checker, the real manifest scripts).


def _scratch_repo(tmp_path, version="0.6.0", dirty=False):
    repo = tmp_path / "scratch"
    (repo / "deploy" / "golden-image").mkdir(parents=True)
    (repo / "harness").mkdir()
    (repo / "scripts").mkdir()
    shutil.copy(DOCKERFILE, repo / "deploy" / "golden-image" / "Dockerfile")
    for name in ("generate-image-manifest.sh", "check-image-manifest.sh"):
        shutil.copy(os.path.join(REPO_ROOT, "harness", name), repo / "harness" / name)
    shutil.copy(
        os.path.join(REPO_ROOT, "scripts", "sparkvm_version.py"),
        repo / "scripts" / "sparkvm_version.py",
    )
    (repo / "VERSION").write_text(version + "\n", encoding="utf-8")
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True, env=env)
    if dirty:
        (repo / "UNCOMMITTED").write_text("dirty", encoding="utf-8")
    return repo, env


def _run_driver(repo, *args):
    env = dict(os.environ, REPO_OVERRIDE=str(repo))
    return subprocess.run(
        ["bash", BUILD_IMAGE, *args],
        capture_output=True, text=True, env=env, timeout=120,
    )


def test_build_image_refuses_dirty_tree(tmp_path):
    """A dirty tree must refuse: baking it under a clean SHA would lie to
    the injector preflight (the manifest generator's own rule)."""
    repo, _ = _scratch_repo(tmp_path, dirty=True)
    r = _run_driver(repo, "--preflight-only")
    assert r.returncode != 0
    assert "uncommitted changes" in r.stderr


def test_build_image_preflight_passes_clean_tree(tmp_path):
    """The same invocation against a conforming tree succeeds — the dirty
    refusal above is not vacuous."""
    repo, _ = _scratch_repo(tmp_path)
    r = _run_driver(repo, "--preflight-only")
    assert r.returncode == 0, r.stderr
    assert "preflight-only — OK" in r.stdout


def test_build_image_refuses_recipe_version_drift(tmp_path):
    """The recipe's ARG default must agree with the tree VERSION: a silent
    drift between the two is a pin violation (D-P1)."""
    repo, _ = _scratch_repo(tmp_path, version="9.9.9")
    r = _run_driver(repo, "--preflight-only")
    assert r.returncode != 0
    assert "recipe ARG default" in r.stderr


def test_build_image_refuses_non_semver_version(tmp_path):
    repo, _ = _scratch_repo(tmp_path, version="not-a-version")
    r = _run_driver(repo, "--preflight-only")
    assert r.returncode != 0
    assert "not valid semver" in r.stderr


def test_gate_record_skeleton_schema(tmp_path):
    """--gate-record-out emits the schema the interactive gate completes:
    automated steps honestly marked, interactive steps pending."""
    repo, _ = _scratch_repo(tmp_path)
    out = tmp_path / "gate-record.json"
    r = _run_driver(repo, "--gate-record-out", str(out))
    assert r.returncode == 0, r.stderr
    with open(out, encoding="utf-8") as f:
        record = json.load(f)
    assert record["schema"] == "sparkvm/golden-image-gate-record@1"
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert record["image_version"] == head
    assert record["built_from_version"] == "0.6.0"
    assert record["automated_gate_steps"]["step0_manifest_preflight"] == "pass"
    scan = record["automated_gate_steps"]["step0b_baked_secrets_scan"]
    assert scan["target"] == "not-run"  # static path: honestly not run
    assert record["interactive_gate"]["verdict"] == "not-run"
    assert record["interactive_gate"]["status"] == "pending"
    assert record["interface_gaps"], "the record must name its open interfaces"
    # the sibling manifest generated alongside must preflight (the driver
    # already ran check-image-manifest.sh; this pins the sibling naming)
    assert os.path.isfile(str(out).replace(".json", ".manifest.json"))


# --- baked-secrets scan -----------------------------------------------------------


def test_scan_clean_on_real_tree():
    """The gate's Step 0b scan must not false-refuse on the repo tree itself
    (its own pattern file, test fixtures, regenerated artifacts). This is a
    false-positive guard, not a gate proxy: the real gate scans the BUILT
    IMAGE (CI's `docker run … scan-baked-secrets.sh /`, covered by
    test_workflow_runs_gate_subset), which is the only place build-time
    generated material (pip venvs, browser downloads, tarball contents)
    can appear."""
    r = subprocess.run(
        ["bash", SCAN_SCRIPT, REPO_ROOT],
        capture_output=True, text=True, timeout=300,
    )
    assert r.returncode == 0, r.stderr


def test_scan_refuses_baked_private_key(tmp_path):
    """The scan is not vacuous: the SAME invocation exits 0 on a clean dir
    and 1 once a baked private key appears."""
    victim = tmp_path / "leak"
    victim.mkdir()
    clean = subprocess.run(
        ["bash", SCAN_SCRIPT, str(victim)],
        capture_output=True, text=True, timeout=120,
    )
    assert clean.returncode == 0, clean.stderr
    # The PEM header is built by concatenation so this test file itself does
    # not trip the baked-secrets scan (the scan matches the literal pattern;
    # harness/test_baked_secrets_scan.py uses the same discipline).
    (victim / "id_rsa").write_text(
        "-----BEG" + "IN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        ["bash", SCAN_SCRIPT, str(victim)],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 1
    assert "HIT" in r.stdout


# --- CI job ------------------------------------------------------------------------


def _workflow_text():
    with open(WORKFLOW, encoding="utf-8") as f:
        return f.read()


def test_workflow_exists_and_builds_on_release_tags():
    """The v* tag trigger must exist structurally — asserting the prose
    comment alone would pass with the trigger deleted."""
    text = _workflow_text()
    assert re.search(r"tags:\s*\[\s*\"v\*\"\s*\]", text), "v* tag trigger missing"


def test_workflow_actions_sha_pinned():
    """Every third-party action must be SHA-pinned (repo convention —
    release.yml pins checkout to a full SHA)."""
    for line in _workflow_text().splitlines():
        m = re.search(r"uses:\s*(\S+)", line)
        if not m:
            continue
        ref = m.group(1)
        assert re.match(r"^[^@]+@[0-9a-f]{40}$", ref), f"unpinned action: {ref}"


def test_workflow_least_privilege_and_no_push():
    """contents:read only (the permissions block must carry nothing else);
    the CI job builds and scans but never pushes a registry — publishing
    stays an operator step after the interactive gate."""
    text = _workflow_text()
    m = re.search(r"^permissions:\s*\n((?:[ \t]+\S.*\n)+)", text, re.M)
    assert m, "top-level permissions block missing"
    keys = [line.split(":")[0].strip() for line in m.group(1).splitlines()]
    assert keys == ["contents"], f"permissions block must be contents-only, got {keys}"
    assert re.search(r"^\s+contents:\s*read\s*$", m.group(1), re.M)
    assert "docker push" not in text
    assert "push: true" not in text


def test_workflow_runs_gate_subset():
    """The CI job runs the automatable gate subset: the baked-secrets scan
    against the built image and the manifest preflight."""
    text = _workflow_text()
    assert "scan-baked-secrets.sh" in text
    assert "check-image-manifest.sh" in text
    assert "generate-image-manifest.sh" in text
