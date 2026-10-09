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
import sys

import pytest

GOLDEN_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(GOLDEN_DIR))
DOCKERFILE = os.path.join(GOLDEN_DIR, "Dockerfile")
SUPERVISORD_CONF = os.path.join(GOLDEN_DIR, "supervisord.conf")
BUILD_IMAGE = os.path.join(GOLDEN_DIR, "build-image.sh")
WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "golden-image.yml")
RELEASE_WORKFLOW = os.path.join(REPO_ROOT, ".github", "workflows", "release.yml")
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


def _dockerfile_run_blocks():
    """Split the Dockerfile into RUN instruction blocks (a RUN starts at a
    line beginning with RUN and continues through backslash-continued lines)."""
    blocks, current = [], None
    for line in _dockerfile_text().splitlines():
        if re.match(r"\s*RUN\s", line):
            current = [line]
            blocks.append(current)
        elif current is not None and current[-1].rstrip().endswith("\\"):
            current.append(line)
        else:
            current = None
    return ["\n".join(b) for b in blocks]


def test_dockerfile_removes_package_generated_host_keys():
    """openssh-server's postinst generates host keys at package-install time
    (inside the docker build). Without an explicit removal, every machine
    provisioned from the image would share one host keypair and the
    firstboot wrapper would be a permanent no-op. The removal must be in
    the recipe text itself — the scan is the backstop, not the design —
    and in the SAME RUN block as the sshd config write, so a future edit
    cannot detach it into a separate layer."""
    assert "rm -f /etc/ssh/ssh_host_" in _dockerfile_text()
    sshd_blocks = [
        b for b in _dockerfile_run_blocks() if "sshd_config.d/sparkvm.conf" in b
    ]
    assert len(sshd_blocks) == 1, "expected exactly one sshd-config RUN block"
    assert "rm -f /etc/ssh/ssh_host_" in sshd_blocks[0]


def test_dockerignore_excludes_git():
    """The build context must not bake the git history into the image
    (bloat + history disclosure). The D-P1 pin comes from git metadata at
    build time (build-image.sh), never from the baked tree."""
    with open(os.path.join(REPO_ROOT, ".dockerignore"), encoding="utf-8") as f:
        text = f.read()
    assert re.search(r"^\.git\s*$", text, re.M)


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


def test_dockerfile_copies_host_generated_manifest():
    """The manifest is generated on the host (build-image.sh / CI) and
    COPY'd in — it cannot be generated in-image (the build context excludes
    .git, and the generator needs git metadata to name the SHA). The
    in-image preflight stays."""
    text = _dockerfile_text()
    assert "COPY deploy/golden-image/image-manifest.json /etc/sparkvm/image-manifest.json" in text
    assert "generate-image-manifest.sh" not in text
    assert "check-image-manifest.sh" in text


def _pins_conf():
    pins = {}
    with open(os.path.join(REPO_ROOT, "scripts", "self_update_pins.conf"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = (p.strip() for p in line.split("=", 1))
            pins[k] = v
    return pins


def test_recipe_pins_match_pins_conf():
    """The recipe's tool pins must equal scripts/self_update_pins.conf —
    the pins are bumped deliberately with a changelog note, and the recipe
    follows the same discipline instead of drifting."""
    pins = _pins_conf()
    text = _dockerfile_text()
    m = re.search(r"^ARG CUA_DRIVER_VERSION=(\S+)", text, re.M)
    assert m, "ARG CUA_DRIVER_VERSION default missing"
    assert m.group(1) == pins["cua-driver"], (m.group(1), pins["cua-driver"])
    assert f'"playwright=={pins["playwright"]}"' in text


def test_build_image_stages_context_manifest(tmp_path):
    """The driver stages the manifest into the build context before docker
    runs (the recipe COPYs it in) and arranges its removal so the tree stays
    clean for the next run."""
    with open(BUILD_IMAGE, encoding="utf-8") as f:
        lines = f.read().splitlines()
    assert any("deploy/golden-image/image-manifest.json" in l for l in lines)
    trap_line = next(
        i for i, l in enumerate(lines) if "trap cleanup_context_manifest EXIT" in l
    )
    gen_line = next(
        i for i, l in enumerate(lines)
        if 'generate-image-manifest.sh" --out "$CONTEXT_MANIFEST"' in l
    )
    assert trap_line < gen_line, "cleanup trap must precede manifest generation"


def test_build_image_refuses_duplicate_recipe_default(tmp_path):
    """Two defaulted ARG SPARKVM_VERSION lines make the effective default
    ambiguous (the first wins silently) — the driver must refuse."""
    def add_dup(src, dst):
        with open(src, encoding="utf-8") as f:
            t = f.read()
        with open(dst, "w", encoding="utf-8") as f:
            f.write(t + "\nARG SPARKVM_VERSION=0.0.0\n")
    repo, _ = _scratch_repo(tmp_path, dockerfile_transform=add_dup)
    r = _run_driver(repo, "--preflight-only")
    assert r.returncode != 0
    assert "exactly one" in r.stderr


def test_dockerfile_runs_gate_tooling():
    """The recipe preflights the baked manifest and installs the gate
    fixture — the D-P1 artifact and the gate procedure's fixture step.
    (The manifest is generated on the host and COPY'd in — see
    test_dockerfile_copies_host_generated_manifest.)"""
    text = _dockerfile_text()
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
        "identity-seed",
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
    """The full program→user mapping: sshd is the only root *daemon*; the
    proxy daemons run as swapd (mirroring the systemd units), the UI/CUA
    stack as agent. identity-seed is the second root program, deliberately:
    it writes machine-identity state (the pairing enrollment) before any
    tenant user exists, and it is a one-shot (autorestart=false, exits) —
    not a persistent root daemon — so a daemon that silently runs as root
    still fails this pin. Checking only a subset would let one through."""
    cfg = _supervisord()
    expected = {
        "identity-seed": "root",
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


def _tree_version():
    with open(os.path.join(REPO_ROOT, "VERSION"), encoding="utf-8") as f:
        return f.read().strip()


def _scratch_repo(tmp_path, version=None, dirty=False, dockerfile_transform=None):
    if version is None:
        # The fixture carries the real driver inputs (the real Dockerfile
        # with its real ARG default), so it must also carry the real tree
        # version — a hardcoded old VERSION would drift from the recipe
        # default on every release bump and trip the driver's D-P1
        # refuse-on-drift check.
        version = _tree_version()
    repo = tmp_path / "scratch"
    (repo / "deploy" / "golden-image").mkdir(parents=True)
    (repo / "harness").mkdir()
    (repo / "scripts").mkdir()
    if dockerfile_transform is None:
        shutil.copy(DOCKERFILE, repo / "deploy" / "golden-image" / "Dockerfile")
    else:
        dockerfile_transform(DOCKERFILE, repo / "deploy" / "golden-image" / "Dockerfile")
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
    assert record["built_from_version"] == _tree_version()
    assert record["automated_gate_steps"]["step0_manifest_preflight"] == "pass"
    scan = record["automated_gate_steps"]["step0b_baked_secrets_scan"]
    assert scan["target"] == "not-run"  # static path: honestly not run
    assert record["interactive_gate"]["verdict"] == "not-run"
    assert record["interactive_gate"]["status"] == "pending"
    assert record["interface_gaps"], "the record must name its open interfaces"
    # #1111: the skeleton honestly marks the unpushed state — the digest is
    # stamped at publish time, never at emit time.
    assert record["build"]["image_digest"] is None
    # the sibling manifest generated alongside must preflight (the driver
    # already ran check-image-manifest.sh; this pins the sibling naming)
    assert os.path.isfile(str(out).replace(".json", ".manifest.json"))


# --- publish-step digest recording (#1111) -----------------------------------------


def _fake_docker_bin(tmp_path):
    """A hermetic docker(1): `inspect` prints the RepoDigest canned in
    FAKE_REPODIGEST (empty = the daemon never resolved the ref) and logs
    its argv to FAKE_DOCKER_ARGV_LOG when set (so tests can prove WHICH
    ref was inspected, not just that inspect ran)."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    (bindir / "docker").write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "inspect" ]; then\n'
        '  if [ -n "$FAKE_DOCKER_ARGV_LOG" ]; then\n'
        '    printf "%s\\n" "$*" >> "$FAKE_DOCKER_ARGV_LOG"\n'
        "  fi\n"
        '  printf "%s\\n" "$FAKE_REPODIGEST"\n'
        "  exit 0\n"
        "fi\n"
        'echo "fake docker: unexpected args: $*" >&2\n'
        "exit 1\n",
        encoding="utf-8",
    )
    os.chmod(bindir / "docker", 0o755)
    return bindir


def _path_without_docker():
    """The ambient PATH minus any component holding an executable `docker`
    — lets a test prove the missing-docker fail-closed path hermetically,
    even on a box that has a real docker installed."""
    parts = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        try:
            if os.access(os.path.join(d, "docker"), os.X_OK):
                continue
        except OSError:
            pass
        parts.append(d)
    return os.pathsep.join(parts)


def _shadow_bin_without_docker(tmp_path):
    """A bindir shadowing every PATH executable *except* `docker`.

    `_path_without_docker()` removes whole PATH components that hold a
    real docker — but on hosts where docker shares a directory with the
    tools the test itself needs (CI runners: docker and bash both live
    in /usr/bin), the filtered PATH can no longer launch `bash`, let
    alone the `git` the script's preflight needs. Instead of leaving the
    bindir empty, symlink every executable found on the ambient PATH
    except `docker` itself (first PATH hit wins, mirroring lookup
    order). `docker` stays truly unresolvable while bash/git/python3
    keep working, so the missing-docker fail-closed path is proven
    hermetically on any host layout.
    """
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            if name == "docker" or (bindir / name).exists():
                continue
            src = os.path.join(d, name)
            try:
                if os.path.isdir(src) or not os.access(src, os.X_OK):
                    continue
                os.symlink(src, bindir / name)
            except OSError:
                pass
    return bindir


def _run_record(tmp_path, repo, repodigest, record_path, image_ref, *extra,
                no_docker=False):
    """Run build-image.sh --record-pushed-digest with a fake docker on PATH
    (or no docker at all when no_docker=True)."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    if no_docker:
        # No docker anywhere: the bindir shadows every PATH executable
        # except docker itself, and every PATH component holding a real
        # docker is filtered out.
        _shadow_bin_without_docker(tmp_path)
        path = str(bindir) + os.pathsep + _path_without_docker()
    else:
        _fake_docker_bin(tmp_path)
        path = str(bindir) + os.pathsep + os.environ["PATH"]
    argv_log = tmp_path / "docker-argv.log"
    if argv_log.exists():
        argv_log.unlink()
    env = dict(
        os.environ,
        REPO_OVERRIDE=str(repo),
        PATH=path,
        FAKE_REPODIGEST=repodigest,
        FAKE_DOCKER_ARGV_LOG=str(argv_log),
    )
    return subprocess.run(
        ["bash", BUILD_IMAGE, "--record-pushed-digest", str(record_path),
         image_ref, *extra],
        capture_output=True, text=True, env=env, timeout=120,
    )


def _inspected_ref(tmp_path):
    """The ref the fake docker was asked to inspect (last argv token)."""
    lines = (tmp_path / "docker-argv.log").read_text(encoding="utf-8").splitlines()
    assert lines, "docker inspect was never called"
    return lines[-1].split()[-1]


def _emit_completed_gate(tmp_path):
    """A scratch repo + a gate record skeleton marked as a completed pass
    (the publish step presumes the interactive gate already ran). The
    completed-pass vocabulary is shared with harness/pin_image.py's
    _check_gate_record — status "complete", verdict "pass"."""
    repo, _ = _scratch_repo(tmp_path)
    out = tmp_path / "gate-record.json"
    r = _run_driver(repo, "--gate-record-out", str(out))
    assert r.returncode == 0, r.stderr
    with open(out, encoding="utf-8") as f:
        record = json.load(f)
    record["interactive_gate"]["status"] = "complete"
    record["interactive_gate"]["verdict"] = "pass"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    return repo, out


_DIGEST_A = "sha256:" + "ab" * 32
_DIGEST_B = "sha256:" + "cd" * 32
_REF = "registry.fly.io/myapp/sparkvm-golden:0.6.0+deadbeefcafe"


def _image_digest(record_path):
    with open(record_path, encoding="utf-8") as f:
        return json.load(f)["build"]["image_digest"]


def test_record_pushed_digest_stamps_gate_record(tmp_path):
    """The publish step records the digest the registry produced — resolved
    through the daemon, never pasted by the operator, and OF the pushed
    ref (the fake docker logs its argv; a script that inspected the wrong
    ref would fail here)."""
    repo, record = _emit_completed_gate(tmp_path)
    r = _run_record(tmp_path, repo, f"registry.fly.io/myapp/sparkvm-golden@{_DIGEST_A}",
                     record, _REF)
    assert r.returncode == 0, r.stderr
    assert _DIGEST_A in r.stdout
    assert _image_digest(record) == _DIGEST_A
    assert _inspected_ref(tmp_path) == _REF


def test_record_pushed_digest_is_idempotent(tmp_path):
    """Re-recording the same digest is a no-op, not an error."""
    repo, record = _emit_completed_gate(tmp_path)
    repodigest = f"registry.fly.io/myapp/sparkvm-golden@{_DIGEST_A}"
    assert _run_record(tmp_path, repo, repodigest, record, _REF).returncode == 0
    r = _run_record(tmp_path, repo, repodigest, record, _REF)
    assert r.returncode == 0, r.stderr
    assert "idempotent" in r.stdout
    assert _image_digest(record) == _DIGEST_A


def test_record_pushed_digest_refuses_overwrite_without_force(tmp_path):
    """A recorded digest is write-once: a different digest refuses unless
    --force names the re-push case explicitly."""
    repo, record = _emit_completed_gate(tmp_path)
    assert _run_record(tmp_path, repo, f"x@{_DIGEST_A}", record, _REF).returncode == 0
    r = _run_record(tmp_path, repo, f"x@{_DIGEST_B}", record, _REF)
    assert r.returncode != 0
    assert "--force" in r.stderr
    assert _image_digest(record) == _DIGEST_A  # refused, not clobbered
    r = _run_record(tmp_path, repo, f"x@{_DIGEST_B}", record, _REF, "--force")
    assert r.returncode == 0, r.stderr
    assert _image_digest(record) == _DIGEST_B


def test_record_pushed_digest_fails_when_ref_unpushed(tmp_path):
    """An empty RepoDigests (the daemon never resolved the ref) fails
    closed instead of recording nothing."""
    repo, record = _emit_completed_gate(tmp_path)
    r = _run_record(tmp_path, repo, "", record, _REF)
    assert r.returncode != 0
    assert "RepoDigests" in r.stderr
    assert _image_digest(record) is None  # failed, not half-written


def test_record_pushed_digest_rejects_malformed_digest(tmp_path):
    """A non-strict digest from the daemon never lands in the trust record."""
    repo, record = _emit_completed_gate(tmp_path)
    r = _run_record(tmp_path, repo, "registry.fly.io/x@sha256:ZZZ", record, _REF)
    assert r.returncode != 0
    assert "not a strict sha256 digest" in r.stderr
    assert _image_digest(record) is None


def test_record_pushed_digest_refuses_skeleton(tmp_path):
    """Publish presumes a completed gate: stamping a skeleton (or a refused
    gate) is meaningless to the pin cross-check and looks authoritative."""
    repo, _ = _scratch_repo(tmp_path)
    out = tmp_path / "gate-record.json"
    assert _run_driver(repo, "--gate-record-out", str(out)).returncode == 0
    r = _run_record(tmp_path, repo, f"x@{_DIGEST_A}", out, _REF)
    assert r.returncode != 0
    assert "completed gate" in r.stderr
    assert _image_digest(out) is None


def test_record_pushed_digest_rejects_non_gate_record(tmp_path):
    """A JSON file that is not a gate record is never stamped."""
    repo, _ = _scratch_repo(tmp_path)
    other = tmp_path / "other.json"
    other.write_text('{"schema": "something-else"}', encoding="utf-8")
    r = _run_record(tmp_path, repo, f"x@{_DIGEST_A}", other, _REF)
    assert r.returncode != 0
    assert "not a sparkvm/golden-image-gate-record@1 record" in r.stderr


def test_record_pushed_digest_refuses_wrong_tree_record(tmp_path):
    """The tree is the pin: a record naming another build's image_version
    refuses, so a digest can never be stamped onto the wrong record."""
    repo, record = _emit_completed_gate(tmp_path)
    with open(record, encoding="utf-8") as f:
        rec = json.load(f)
    rec["image_version"] = "0" * 40
    with open(record, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2)
    r = _run_record(tmp_path, repo, f"x@{_DIGEST_A}", record, _REF)
    assert r.returncode != 0
    assert "image_version" in r.stderr
    assert _image_digest(record) is None


def test_record_pushed_digest_fails_without_docker(tmp_path):
    """No docker on the host fails closed — the digest cannot be resolved
    from the registry, so nothing is recorded."""
    repo, record = _emit_completed_gate(tmp_path)
    r = _run_record(tmp_path, repo, f"x@{_DIGEST_A}", record, _REF,
                     no_docker=True)
    assert r.returncode != 0
    assert "docker not found" in r.stderr
    assert _image_digest(record) is None


def test_record_pushed_digest_refuses_missing_build_section(tmp_path):
    """A gate record whose build section is not an object is never
    stamped — the trust record's shape is part of the contract."""
    repo, record = _emit_completed_gate(tmp_path)
    with open(record, encoding="utf-8") as f:
        rec = json.load(f)
    rec["build"] = None
    with open(record, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2)
    r = _run_record(tmp_path, repo, f"x@{_DIGEST_A}", record, _REF)
    assert r.returncode != 0
    assert "no build section" in r.stderr
    with open(record, encoding="utf-8") as f:
        assert json.load(f)["build"] is None  # refused, not repaired


def test_record_pushed_digest_bad_directory_fails_clean(tmp_path):
    """A write failure fails closed with the tool's clean ERROR contract,
    not a raw traceback. (The .tmp path is blocked by a directory here —
    deterministic without permission games, and works as root.)"""
    repo, record = _emit_completed_gate(tmp_path)
    (tmp_path / "gate-record.json.tmp").mkdir()
    r = _run_record(tmp_path, repo, f"x@{_DIGEST_A}", record, _REF)
    assert r.returncode != 0
    assert "build-image: ERROR: cannot write gate record" in r.stderr
    assert "Traceback" not in r.stderr
    assert _image_digest(record) is None


def test_record_mode_refuses_preflight_combination(tmp_path):
    """--record-pushed-digest is standalone: combined with --preflight-only
    the stamp would be silently dropped while rc stayed 0."""
    repo, _ = _scratch_repo(tmp_path)
    r = _run_driver(repo, "--preflight-only",
                    "--record-pushed-digest", "rec.json", _REF)
    assert r.returncode != 0
    assert "cannot be combined" in r.stderr


def test_force_requires_record_mode(tmp_path):
    """--force is meaningless outside the record mode — silently ignoring
    it would mask an operator typo."""
    repo, _ = _scratch_repo(tmp_path)
    r = _run_driver(repo, "--preflight-only", "--force")
    assert r.returncode != 0
    assert "--force only applies to --record-pushed-digest" in r.stderr


def test_completed_gate_vocabulary_agrees_with_pin_image(tmp_path):
    """The record mode's completed-pass predicate and pin_image's
    _check_gate_record must agree on every (status, verdict) shape — a
    drift means no record can travel the publish → pin pipeline (E1:
    the old "gate" vocabulary could never satisfy the pin tool)."""
    sys.path.insert(0, os.path.join(REPO_ROOT, "harness"))
    import pin_image
    repo, _ = _scratch_repo(tmp_path)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    corpus = [
        ({"status": "complete", "verdict": "pass"}, True),
        ({"status": "pending", "verdict": "not-run"}, False),  # skeleton
        ({"status": "complete", "verdict": "gate"}, False),  # old vocabulary
        ({"status": "pending", "verdict": "pass"}, False),
        ({"status": "complete", "verdict": "no-pass"}, False),
        (None, False),
    ]
    for interactive, expect_accept in corpus:
        out = tmp_path / "gate-record.json"
        assert _run_driver(repo, "--gate-record-out", str(out)).returncode == 0
        with open(out, encoding="utf-8") as f:
            record = json.load(f)
        record["interactive_gate"] = interactive
        with open(out, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        rr = _run_record(tmp_path, repo, f"x@{_DIGEST_A}", out, _REF)
        script_accepts = rr.returncode == 0 and _image_digest(out) == _DIGEST_A
        try:
            pin_image._check_gate_record(record, head, "drift-test")
            pin_accepts = True
        except pin_image.PinnedImageError:
            pin_accepts = False
        assert script_accepts == pin_accepts == expect_accept, (
            interactive, rr.stderr[-300:] if rr.stderr else "")


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


def _release_workflow_text():
    with open(RELEASE_WORKFLOW, encoding="utf-8") as f:
        return f.read()


def test_workflow_exists_and_builds_on_release_tags():
    """The v* tag trigger must exist structurally — asserting the prose
    comment alone would pass with the trigger deleted."""
    text = _workflow_text()
    assert re.search(r"tags:\s*\[\s*\"v\*\"\s*\]", text), "v* tag trigger missing"


def test_workflow_callable_from_release_workflow():
    """#1176: the release workflow pushes the v* tag with GITHUB_TOKEN,
    which never triggers workflow runs, so the tag trigger alone could
    never fire this gate on a real release (zero runs across v0.5.0–v0.7.0).
    release.yml calls this workflow via workflow_call in the same run, so
    the workflow_call trigger must exist structurally. The release tag is
    passed explicitly as the `tag` input from the release job's own
    checkout — never re-derived from the caller's main tip, which may
    already be past the release commit when a second release bump queues
    behind the concurrency group. Both sides are pinned: deleting the
    trigger, the input, the pin step, or the caller wiring fails this
    test."""
    text = _workflow_text()
    release = _release_workflow_text()
    # Callee side (golden-image.yml).
    assert re.search(r"(?m)^\s*workflow_call:\s*$", text), "workflow_call trigger missing"
    assert re.search(r"(?m)^\s*tag:\s*$", text), "workflow_call tag input missing"
    assert 'github.event_name == \'workflow_call\'' in text, "release-tree pin step missing"
    assert "${{ inputs.tag }}" in text, "pin step must check out the workflow_call tag input"
    assert "fetch-tags: true" in text, "tag fetch missing (checkout cannot see the release tag)"
    # Caller side (release.yml).
    assert "uses: ./.github/workflows/golden-image.yml" in release, "release.yml no longer calls the gate"
    assert "needs: release" in release, "gate job must run after the release job"
    assert "needs.release.outputs.tag" in release, "gate job must consume the release job's tag output"
    assert "steps.tag.outputs.tag" in release, "release job must expose the cut tag as an output"


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
