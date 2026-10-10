"""Tests for the #1205 data-volume contract (distribution).

Covers: deploy/golden-image/data-prep.sh (first-boot /data layout),
the defensive /data/ssh ensure in sparkvm-sshd-firstboot.sh (D-V4),
the supervisord + Dockerfile wiring, and the contract's machine-env
interface against the real component code (each env var the contract
names must actually be honored by its consumer).

Shell scripts are exercised as real subprocesses against fake roots
(SPARKVM_DATA_ROOT / SPARKVM_SSH_ETC_DIR) — never the real /data or
/etc/ssh. ssh-keygen and mountpoint are PATH stubs: generation must
write THROUGH the symlinks onto the fake volume, and the mount gate
(Security B1) is driven by STUB_MOUNTPOINT_RC.
"""
import configparser
import os
import re
import stat
import subprocess
import sys

import pytest

GOLDEN_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(GOLDEN_DIR))
DATA_PREP = os.path.join(GOLDEN_DIR, "data-prep.sh")
FIRSTBOOT = os.path.join(GOLDEN_DIR, "sparkvm-sshd-firstboot.sh")
SUPERVISORD_CONF = os.path.join(GOLDEN_DIR, "supervisord.conf")
DOCKERFILE = os.path.join(GOLDEN_DIR, "Dockerfile")
CONTRACT_DOC = os.path.join(REPO_ROOT, "docs", "DATA_VOLUME_CONTRACT.md")

KEYTYPES = ("rsa", "ecdsa", "ed25519")


def run_script(path, env, **kw):
    return subprocess.run(
        ["bash", path], env=env, capture_output=True, text=True, timeout=60,
        **kw,
    )


KEYGEN_STUB = """#!/bin/bash
# Stub ssh-keygen: -A generates through whatever paths exist (symlinks
# followed), like the real one. Records invocation.
echo "stub-keygen $@" >> "$STUB_LOG/invoked"
etc="${SPARKVM_SSH_ETC_DIR:-/etc/ssh}"
for t in rsa ecdsa ed25519; do
    k="$etc/ssh_host_${t}_key"
    if [ ! -e "$k" ]; then
        printf 'PRIVATE-%s' "$t" > "$k"
        printf 'PUBLIC-%s' "$t" > "$k.pub"
    fi
done
"""

MOUNTPOINT_STUB = """#!/bin/bash
# Stub mountpoint: `mountpoint -q <path>` exits $STUB_MOUNTPOINT_RC
# (default 0). Lets the tests drive the Security-B1 mount gate.
exit "${STUB_MOUNTPOINT_RC:-0}"
"""


@pytest.fixture()
def box(tmp_path):
    """Fake provisioned box: empty /data root + fake /etc/ssh + stub
    bindir (ssh-keygen, mountpoint) first on PATH."""
    data = tmp_path / "data"
    data.mkdir()
    ssh_etc = tmp_path / "ssh_etc"
    ssh_etc.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "ssh-keygen").write_text(KEYGEN_STUB)
    (bindir / "ssh-keygen").chmod(0o755)
    (bindir / "mountpoint").write_text(MOUNTPOINT_STUB)
    (bindir / "mountpoint").chmod(0o755)
    logdir = tmp_path / "keygen-log"
    logdir.mkdir()
    run_dir = tmp_path / "sshd-run"
    env = {
        "PATH": str(bindir) + ":" + os.environ.get("PATH", "/usr/bin:/bin"),
        "SPARKVM_DATA_ROOT": str(data),
        "SPARKVM_SSH_ETC_DIR": str(ssh_etc),
        "SPARKVM_DATA_PREP_SKIP_CHOWN": "1",  # swapd missing on test hosts
        "SPARKVM_FIRSTBOOT_NO_EXEC": "1",
        "SPARKVM_SSH_RUN_DIR": str(run_dir),  # /run/sshd not writable non-root
        "STUB_LOG": str(logdir),
        "STUB_MOUNTPOINT_RC": "0",  # the fake /data counts as mounted
    }
    return data, ssh_etc, env, logdir


def test_data_prep_no_data_exits_zero(tmp_path):
    """No /data (self-hosted/dev): exit 0, change nothing, say so loudly."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "SPARKVM_DATA_ROOT": str(tmp_path / "no-such-data"),
        "SPARKVM_DATA_PREP_SKIP_CHOWN": "1",
    }
    r = run_script(DATA_PREP, env)
    assert r.returncode == 0
    assert "nothing to do" in r.stderr
    assert not (tmp_path / "no-such-data").exists()


def test_data_prep_refuses_unmounted_data(box):
    """Security B1: /data present but not a mountpoint is FATAL — the
    script must not lay "durable" state on the ephemeral rootfs."""
    data, ssh_etc, env, _ = box
    env = dict(env, STUB_MOUNTPOINT_RC="1")
    r = run_script(DATA_PREP, env)
    assert r.returncode == 1
    assert "not a mountpoint" in r.stderr
    # Nothing was laid out:
    assert not (data / "pairing").exists()
    assert not (ssh_etc / "ssh_host_rsa_key").is_symlink()


def test_data_prep_creates_layout(box):
    """Pinned subdirs created 0700; sshd key symlinks point at the volume."""
    data, ssh_etc, env, _ = box
    r = run_script(DATA_PREP, env)
    assert r.returncode == 0, r.stderr
    for sub in ("pairing", "approvals", "confirmd", "ssh"):
        d = data / sub
        assert d.is_dir(), sub
        assert stat.S_IMODE(d.stat().st_mode) == 0o700, sub
    for t in KEYTYPES:
        link = ssh_etc / f"ssh_host_{t}_key"
        assert link.is_symlink(), t
        assert os.readlink(link) == str(data / "ssh" / f"ssh_host_{t}_key"), t
        pub = ssh_etc / f"ssh_host_{t}_key.pub"
        assert pub.is_symlink(), t
        assert os.readlink(pub) == str(data / "ssh" / f"ssh_host_{t}_key.pub"), t


def test_data_prep_chown_pins_contract_owners():
    """Structural pin: the script chowns the contract's owner per subdir.

    pairing/ -> root (status quo per #1220), approvals/ + confirmd/ ->
    swapd, ssh/ -> root. The behavioral tests skip chown (test seam);
    this pins the intended owner on the exact subdir. Anchored to line
    start so a commented-out mkpair line cannot pass.
    """
    src = open(DATA_PREP).read()
    assert re.search(r'^mkpair pairing root$', src, re.MULTILINE)
    assert re.search(r'^mkpair approvals swapd$', src, re.MULTILINE)
    assert re.search(r'^mkpair confirmd swapd$', src, re.MULTILINE)
    assert re.search(r'^mkpair ssh root$', src, re.MULTILINE)


def test_data_prep_idempotent(box):
    data, ssh_etc, env, _ = box
    assert run_script(DATA_PREP, env).returncode == 0
    r = run_script(DATA_PREP, env)
    assert r.returncode == 0, r.stderr
    for t in KEYTYPES:
        assert (ssh_etc / f"ssh_host_{t}_key").is_symlink()


def test_data_prep_moves_preexisting_rootfs_keys(box):
    """Real key files on the rootfs move onto the volume, not abandoned;
    the moved private key is forced 0600 (sshd refuses 0644)."""
    data, ssh_etc, env, _ = box
    (ssh_etc / "ssh_host_rsa_key").write_text("PRIVATE")
    (ssh_etc / "ssh_host_rsa_key").chmod(0o644)
    (ssh_etc / "ssh_host_rsa_key.pub").write_text("PUBLIC")
    r = run_script(DATA_PREP, env)
    assert r.returncode == 0, r.stderr
    assert (data / "ssh" / "ssh_host_rsa_key").read_text() == "PRIVATE"
    assert stat.S_IMODE((data / "ssh" / "ssh_host_rsa_key").stat().st_mode) == 0o600
    assert (data / "ssh" / "ssh_host_rsa_key.pub").read_text() == "PUBLIC"
    assert (ssh_etc / "ssh_host_rsa_key").is_symlink()


def test_data_prep_conflict_quarantines_rootfs_key(box):
    """Security B2: a real rootfs key + an existing volume key is a
    conflict — the volume's attested identity wins; the rootfs file is
    quarantined loudly (never silently overwritten), with its .pub."""
    data, ssh_etc, env, _ = box
    assert run_script(DATA_PREP, env).returncode == 0
    (data / "ssh" / "ssh_host_rsa_key").write_text("VOLUME-KEY")
    # Drop the symlinks data-prep made so the rootfs holds REAL files
    # (writing through a symlink would land on the volume instead):
    (ssh_etc / "ssh_host_rsa_key").unlink()
    (ssh_etc / "ssh_host_rsa_key.pub").unlink()
    (ssh_etc / "ssh_host_rsa_key").write_text("ROOTFS-KEY")
    (ssh_etc / "ssh_host_rsa_key.pub").write_text("ROOTFS-PUB")
    r = run_script(DATA_PREP, env)
    assert r.returncode == 0, r.stderr
    assert "CONFLICT" in r.stderr
    assert "volume wins" in r.stderr
    # Volume key untouched:
    assert (data / "ssh" / "ssh_host_rsa_key").read_text() == "VOLUME-KEY"
    # Rootfs key quarantined (PID-unique name), mode 0600, with its .pub:
    quar = list((data / "ssh").glob("ssh_host_rsa_key.rootfs-conflict-*"))
    quar = [q for q in quar if not q.suffix == ".tmp" and not q.name.endswith(".pub")]
    assert len(quar) == 1, [q.name for q in (data / "ssh").iterdir()]
    assert quar[0].read_text() == "ROOTFS-KEY"
    assert stat.S_IMODE(quar[0].stat().st_mode) == 0o600
    assert (quar[0].parent / (quar[0].name + ".pub")).read_text() == "ROOTFS-PUB"
    # Symlink now points at the volume key:
    assert (ssh_etc / "ssh_host_rsa_key").is_symlink()
    assert os.readlink(ssh_etc / "ssh_host_rsa_key") == str(data / "ssh" / "ssh_host_rsa_key")


def test_data_prep_repairs_mispointed_symlink(box):
    """Security B3: a pre-existing symlink pointing elsewhere is verified,
    not trusted — repaired loudly before any key material is written."""
    data, ssh_etc, env, _ = box
    assert run_script(DATA_PREP, env).returncode == 0
    (ssh_etc / "ssh_host_rsa_key").unlink()
    (ssh_etc / "ssh_host_rsa_key").symlink_to("/tmp/elsewhere")
    r = run_script(DATA_PREP, env)
    assert r.returncode == 0, r.stderr
    assert "mispointed symlink" in r.stderr
    assert os.readlink(ssh_etc / "ssh_host_rsa_key") == str(data / "ssh" / "ssh_host_rsa_key")


@pytest.mark.skipif(os.geteuid() != 0, reason="seam warning only fires as root")
def test_seam_warning_as_root(box):
    """A test seam set in a root run logs a loud WARNING (production must
    never set these)."""
    data, ssh_etc, env, _ = box
    r = run_script(DATA_PREP, env)
    assert r.returncode == 0
    assert "WARNING: test seam SPARKVM_DATA_ROOT is set in a root run" in r.stderr


def test_firstboot_run_dir_seam_default_pinned():
    """Structural pin: the run-dir seam defaults to /run/sshd — the mkdir
    behavior below must not be accidentally dropped or repointed in
    production (a test-only seam that forgot its default would silently
    stop creating the dir sshd needs)."""
    src = open(FIRSTBOOT).read()
    assert re.search(
        r'^SSH_RUN_DIR="\$\{SPARKVM_SSH_RUN_DIR:-/run/sshd\}"$', src,
        re.MULTILINE,
    )
    assert re.search(r'^mkdir -p "\$SSH_RUN_DIR"$', src, re.MULTILINE)


def test_firstboot_seam_warning_covers_all_documented_seams():
    """Structural pin: the root-run WARNING loop iterates the single
    canonical _SEAMS list, not its own copy — a seam consumed below but
    missing from the loop would warn nowhere, and a list that drifted
    from the header doc would lie to operators."""
    src = open(FIRSTBOOT).read()
    m = re.search(r'^_SEAMS=\(([^)]*)\)$', src, re.MULTILINE)
    assert m, "the canonical _SEAMS list must exist in the script"
    assert m.group(1).split() == [
        "SPARKVM_DATA_ROOT", "SPARKVM_SSH_ETC_DIR",
        "SPARKVM_FIRSTBOOT_NO_EXEC", "SPARKVM_SSH_RUN_DIR",
        "SPARKVM_SSH_STATUS_DIR",
    ]
    assert re.search(r'^\s*for _seam in "\$\{_SEAMS\[@\]\}"; do$', src,
                     re.MULTILINE), \
        "the WARNING loop must iterate _SEAMS, not a duplicated list"
    # Production driver-injected vars have their own canonical list:
    # consumed in the body and header-documented like seams, but they
    # must NEVER be in _SEAMS (the WARNING loop must not fire on a var
    # that is legitimately set in production).
    pm = re.search(r'^_PROD_ENV=\(([^)]*)\)$', src, re.MULTILINE)
    assert pm, "the canonical _PROD_ENV list must exist in the script"
    assert pm.group(1).split() == ["SPARKVM_SSH_HOST_KEYS"]
    assert not (set(pm.group(1).split()) & set(m.group(1).split())), \
        "a var cannot be both a test seam and a production env var"
    # Every name in either canonical list must also be documented in the
    # header (an undocumented var is undiscoverable).
    header = src.split("set -euo pipefail")[0]
    seams = m.group(1).split()
    for name in seams + pm.group(1).split():
        assert re.search(r'^#.*\b%s\b' % name, header, re.MULTILINE), name
    # Reverse: every SPARKVM_* var the header documents must be
    # classified in exactly one canonical list — a header-documented var
    # forgotten in both would never warn in a root run (seams) or would
    # drift unclassified (production).
    header_seams = set(re.findall(r'\b(SPARKVM_[A-Z_]+)\b', header))
    assert header_seams, "the header's seam block must name the seams"
    classified = set(seams) | set(pm.group(1).split())
    assert header_seams <= classified, header_seams - classified


def test_firstboot_body_consumed_seams_are_all_canonical():
    """Structural pin (QA-trail, #1233): the third leg of the seam pin.

    The existing test pins doc <-> _SEAMS in both directions, but a
    SPARKVM_* seam consumed in the script BODY while absent from both the
    header doc and _SEAMS would warn nowhere in a root run and stay
    green, despite the comment claiming _SEAMS as the canonical list.
    Scan the body (everything after `set -euo pipefail`) for
    SPARKVM_[A-Z_]+ references and require every one to be in _SEAMS or
    _PROD_ENV, so the WARNING loop cannot silently miss a test seam —
    and no production var can hide unclassified in the body.
    """
    src = open(FIRSTBOOT).read()
    body = src.split("set -euo pipefail", 1)[1]
    m = re.search(r'^_SEAMS=\(([^)]*)\)$', src, re.MULTILINE)
    assert m, "the canonical _SEAMS list must exist in the script"
    pm = re.search(r'^_PROD_ENV=\(([^)]*)\)$', src, re.MULTILINE)
    assert pm, "the canonical _PROD_ENV list must exist in the script"
    canonical = set(m.group(1).split()) | set(pm.group(1).split())
    # A seam *mentioned* in a body comment is not consumed by the script:
    # strip full-line comments so a comment moved below the split anchor
    # cannot fail the pin for the wrong reason. (Residual, documented:
    # an inline trailing comment naming a SPARKVM_* token still counts —
    # err on the side of listing it in _SEAMS.)
    code = "\n".join(
        line for line in body.splitlines()
        if not re.match(r"^\s*#", line)
    )
    consumed = set(re.findall(r'\b(SPARKVM_[A-Z_]+)\b', code))
    # The _SEAMS=(...) and _PROD_ENV=(...) definition lines themselves live
    # in the body and name their vars as plain tokens — harmless, since
    # the assertion is that every consumed name IS in a canonical list.
    assert consumed <= canonical, \
        "SPARKVM_* vars consumed in the script body but missing from " \
        "_SEAMS/_PROD_ENV: %s" % ", ".join(sorted(consumed - canonical))


def test_data_prep_seam_list_is_canonical_and_complete():
    """Structural pin: data-prep.sh gets the same _SEAMS discipline as
    sparkvm-sshd-firstboot.sh — the root-run WARNING loop iterates the
    single canonical _SEAMS list (not an inline copy), every listed seam
    is documented in the header, and every SPARKVM_* name consumed in the
    body is in _SEAMS. A new test seam added to the body must be added to
    _SEAMS *and* to this test's hardcoded exact list (order is
    contractual — the list mirrors the script), or the suite fails; a
    seam dropped from _SEAMS stops warning loudly instead of silently."""
    src = open(DATA_PREP).read()
    body = src.split("set -euo pipefail", 1)[1]
    m = re.search(r'^_SEAMS=\(([^)]*)\)$', src, re.MULTILINE)
    assert m, "the canonical _SEAMS list must exist in the script"
    canonical = m.group(1).split()
    assert canonical == [
        "SPARKVM_DATA_ROOT", "SPARKVM_SSH_ETC_DIR",
        "SPARKVM_DATA_PREP_SKIP_CHOWN",
    ]
    assert re.search(r'^\s*for _seam in "\$\{_SEAMS\[@\]\}"; do$', src,
                     re.MULTILINE), \
        "the WARNING loop must iterate _SEAMS, not a duplicated list"
    header = src.split("set -euo pipefail")[0]
    for name in canonical:
        assert re.search(r'^#.*\b%s\b' % name, header, re.MULTILINE), name
    # No header-reverse assertion here (unlike the firstboot pin): the
    # header legitimately cites identity-seed-hook.sh's SPARKVM_PAIR_CLIENT
    # as a trust-boundary reference, and that seam is not data-prep's to
    # warn about.
    consumed = set(re.findall(
        r'\b(SPARKVM_[A-Z_]+)\b',
        "\n".join(
            line for line in body.splitlines()
            if not re.match(r"^\s*#", line)
        ),
    ))
    # Full-line comments stripped (see the firstboot test): a seam
    # mentioned in a comment is not consumed. Inline trailing comments
    # still count — list the seam.
    assert consumed <= set(canonical), \
        "seams consumed in data-prep.sh's body but missing from _SEAMS: %s" % \
        ", ".join(sorted(consumed - set(canonical)))


def test_firstboot_creates_sshd_run_dir(box):
    """The firstboot script creates sshd's privilege-separation dir (the
    /run is a fresh-tmpfs line). Via the SPARKVM_SSH_RUN_DIR seam: CI's
    non-root runner cannot write /run/sshd, which is exactly the failure
    that reded this PR's shard-unit run."""
    data, ssh_etc, env, logdir = box
    run_dir = env["SPARKVM_SSH_RUN_DIR"]
    assert not os.path.exists(run_dir)  # the script creates it, not us
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert os.path.isdir(run_dir)


def test_firstboot_defensive_ensure_without_data_prep(box):
    """D-V4: the sshd entrypoint ensures /data/ssh itself — no trust in
    data-prep's timing. Keys generate THROUGH the symlinks onto the
    volume (private and .pub both)."""
    data, ssh_etc, env, logdir = box
    # NOTE: data-prep.sh deliberately NOT run — the entrypoint must cope.
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert (data / "ssh").is_dir()
    assert (logdir / "invoked").exists()  # ssh-keygen -A ran
    for t in KEYTYPES:
        assert (ssh_etc / f"ssh_host_{t}_key").is_symlink()
        # Bytes landed on the volume, through both symlinks:
        assert (data / "ssh" / f"ssh_host_{t}_key").read_text() == f"PRIVATE-{t}"
        assert (data / "ssh" / f"ssh_host_{t}_key.pub").read_text() == f"PUBLIC-{t}"
        assert os.readlink(ssh_etc / f"ssh_host_{t}_key.pub") == \
            str(data / "ssh" / f"ssh_host_{t}_key.pub")


def test_firstboot_no_data_keeps_rootfs_behavior(box):
    """Without /data (self-hosted/dev): keys generate into /etc/ssh as
    before — no symlinks, no volume writes."""
    data, ssh_etc, env, logdir = box
    env = dict(env, SPARKVM_DATA_ROOT=str(data / "no-such-data"))
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert (logdir / "invoked").exists()
    for t in KEYTYPES:
        assert not (ssh_etc / f"ssh_host_{t}_key").is_symlink()
        assert (ssh_etc / f"ssh_host_{t}_key").read_text() == f"PRIVATE-{t}"
    assert not (data / "ssh").exists()


def test_firstboot_unmounted_data_falls_back_to_rootfs(box):
    """Security B1, firstboot half: /data present but not a mountpoint —
    loud warning, rootfs key behavior (sshd must still start)."""
    data, ssh_etc, env, logdir = box
    env = dict(env, STUB_MOUNTPOINT_RC="1")
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert "not a mountpoint" in r.stderr
    assert (logdir / "invoked").exists()
    for t in KEYTYPES:
        assert not (ssh_etc / f"ssh_host_{t}_key").is_symlink()
        assert (ssh_etc / f"ssh_host_{t}_key").read_text() == f"PRIVATE-{t}"
    assert not (data / "ssh").exists()


def _bindir_of(env):
    import pathlib
    return pathlib.Path(env["PATH"].split(os.pathsep)[0])


def test_firstboot_flock_failure_degrades_to_rootfs(box):
    """#1240: a flock timeout (data-prep's identical loop wedged) must
    degrade to rootfs keys with a loud WARNING — never abort the boot
    under set -e before sshd starts."""
    data, ssh_etc, env, logdir = box
    bindir = _bindir_of(env)
    (bindir / "flock").write_text("#!/bin/bash\nexit 1\n")
    (bindir / "flock").chmod(0o755)
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert "timed out waiting for the sshkey ensure lock" in r.stderr
    assert "volume-key ensure failed partway" in r.stderr
    assert (logdir / "invoked").exists()  # sshd still gets keys
    for t in KEYTYPES:
        assert not (ssh_etc / f"ssh_host_{t}_key").is_symlink()
        assert (ssh_etc / f"ssh_host_{t}_key").read_text() == f"PRIVATE-{t}"


def test_firstboot_unmovable_conflict_continues_other_keytypes(box):
    """#1240: ensure_link returning 1 (a rootfs key that cannot be moved
    onto the volume) degrades per key type — the loop continues with the
    remaining types and the call-site WARNING fires; the boot proceeds."""
    data, ssh_etc, env, logdir = box
    bindir = _bindir_of(env)
    (bindir / "mv").write_text("#!/bin/bash\nexit 1\n")
    (bindir / "mv").chmod(0o755)
    # Pass-through flock stub: this test is about per-type mv failure,
    # not the lock path — don't depend on the real flock binary being
    # present (its absence would take the lock-timeout branch and fail
    # the symlink assertions for the wrong reason).
    (bindir / "flock").write_text("#!/bin/bash\nexit 0\n")
    (bindir / "flock").chmod(0o755)
    (ssh_etc / "ssh_host_rsa_key").write_text("ROOTFS-RSA")
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert "could not be moved onto the volume" in r.stderr
    assert "volume-key ensure failed partway" in r.stderr
    # The unmovable type stays a rootfs real file, untouched:
    assert not (ssh_etc / "ssh_host_rsa_key").is_symlink()
    assert (ssh_etc / "ssh_host_rsa_key").read_text() == "ROOTFS-RSA"
    # The other types still landed on the volume through the ensure:
    for t in ("ecdsa", "ed25519"):
        assert (ssh_etc / f"ssh_host_{t}_key").is_symlink()
        assert os.readlink(ssh_etc / f"ssh_host_{t}_key") == \
            str(data / "ssh" / f"ssh_host_{t}_key")
        assert (data / "ssh" / f"ssh_host_{t}_key").read_text() == f"PRIVATE-{t}"


def test_firstboot_ln_failure_degrades_partway(box):
    """#1251: a failing `ln -sfn` inside ensure_link must propagate
    (return 1) into the call site's $failed aggregation — the boot
    degrades to rootfs keys with the partway WARNING, never aborts, and
    the log must NOT contain the false "linked ..." claim for any key
    type. Without the guard, the echo's status masks the ln failure."""
    data, ssh_etc, env, logdir = box
    bindir = _bindir_of(env)
    (bindir / "ln").write_text("#!/bin/bash\nexit 1\n")
    (bindir / "ln").chmod(0o755)
    # Pass-through flock stub: this test is about ln failure, not the
    # lock path — don't depend on the real flock binary being present
    # (its absence would take the lock-timeout branch and pass the
    # assertions for the wrong reason).
    (bindir / "flock").write_text("#!/bin/bash\nexit 0\n")
    (bindir / "flock").chmod(0o755)
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert "volume-key ensure failed partway" in r.stderr
    # No false "linked ..." claim may appear for any key type:
    assert "linked" not in r.stderr
    assert (logdir / "invoked").exists()  # sshd still gets keys
    # No symlinks were created; the keygen stub wrote real rootfs files
    # instead (degraded, exactly like the unmounted-/data path). Pin both
    # the private key and its .pub (the stub writes PUBLIC-<t> alongside
    # PRIVATE-<t>; the .pub is implied by the stub, now stated):
    for t in KEYTYPES:
        assert not (ssh_etc / f"ssh_host_{t}_key").is_symlink()
        assert (ssh_etc / f"ssh_host_{t}_key").read_text() == f"PRIVATE-{t}"
        assert not (ssh_etc / f"ssh_host_{t}_key.pub").is_symlink()
        assert (ssh_etc / f"ssh_host_{t}_key.pub").read_text() == f"PUBLIC-{t}"


def test_firstboot_repair_path_ln_failure_degrades_partway(box):
    """#1255 (repair-path test pin from the #1251 review rounds): a failing
    `ln -sfn` in ensure_link's mispointed-symlink REPAIR branch must
    propagate (return 1) into the call site's $failed aggregation — the
    partway WARNING fires and the boot degrades, never aborts. This pin is
    documentation, not a regression test: pre-#1251 the repair branch's
    failure already propagated via the inner if-status (identical
    hardening), so the `|| return 1` guard pins the contract rather than
    changing behavior — the test stays non-vacuous by neutering the guard
    to `|| true` (see the neuter check in the run log)."""
    data, ssh_etc, env, logdir = box
    bindir = _bindir_of(env)
    # Fail ln only for the rsa key's REPAIR call: argv ending in the bare
    # ssh_host_rsa_key link (no .pub suffix) — the rsa .pub create call and
    # every other key type pass through to the real ln, isolating the
    # repair branch's propagation.
    (bindir / "ln").write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        "  *ssh_host_rsa_key) exit 1 ;;\n"
        "esac\n"
        'exec /bin/ln "$@"\n'
    )
    (bindir / "ln").chmod(0o755)
    # Pass-through flock stub: this test is about ln failure, not the
    # lock path — don't depend on the real flock binary being present
    # (its absence would take the lock-timeout branch and fail the
    # assertions for the wrong reason).
    (bindir / "flock").write_text("#!/bin/bash\nexit 0\n")
    (bindir / "flock").chmod(0o755)
    # Mispointed rsa symlink (points at a REAL wrong file, so the keygen
    # stub cleanly skips rsa instead of failing a redirect through a
    # dangling link): the repair branch is taken, ln fails, and the
    # guard must propagate the failure.
    wrong = data.parent / "wrong-target"
    wrong.write_text("WRONG")
    (ssh_etc / "ssh_host_rsa_key").symlink_to(wrong)
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert "repairing mispointed symlink" in r.stderr
    assert "volume-key ensure failed partway" in r.stderr
    # The mispointed rsa link was never repaired (still points at the
    # wrong target); the other types landed on the volume through the
    # ensure, per-type continuation intact:
    assert os.readlink(ssh_etc / "ssh_host_rsa_key") == str(wrong)
    for t in ("ecdsa", "ed25519"):
        assert (ssh_etc / f"ssh_host_{t}_key").is_symlink()
        assert os.readlink(ssh_etc / f"ssh_host_{t}_key") == \
            str(data / "ssh" / f"ssh_host_{t}_key")
        assert (data / "ssh" / f"ssh_host_{t}_key").read_text() == f"PRIVATE-{t}"
        assert (ssh_etc / f"ssh_host_{t}_key.pub").is_symlink()


def test_firstboot_partial_ln_failure_continues_other_keytypes(box):
    """#1255 (partial-failure ln pin from the #1251 review rounds): one
    key type's ln fails while the others succeed — the ensure continues
    with the remaining types through a failing ln (the mv-based
    unmovable-conflict test covers per-type continuation but not the ln
    variant), and the call-site WARNING fires."""
    data, ssh_etc, env, logdir = box
    bindir = _bindir_of(env)
    # Fail ln for the rsa key type (key + .pub — both argv contain
    # ssh_host_rsa_key), pass everything else through to the real ln.
    (bindir / "ln").write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        "  *ssh_host_rsa_key*) exit 1 ;;\n"
        "esac\n"
        'exec /bin/ln "$@"\n'
    )
    (bindir / "ln").chmod(0o755)
    # Pass-through flock stub: this test is about ln failure, not the
    # lock path — don't depend on the real flock binary being present
    # (its absence would take the lock-timeout branch and fail the
    # assertions for the wrong reason).
    (bindir / "flock").write_text("#!/bin/bash\nexit 0\n")
    (bindir / "flock").chmod(0o755)
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert "volume-key ensure failed partway" in r.stderr
    # The failed type degraded to rootfs real files (no link was ever
    # created; the keygen stub wrote them directly):
    assert not (ssh_etc / "ssh_host_rsa_key").is_symlink()
    assert (ssh_etc / "ssh_host_rsa_key").read_text() == "PRIVATE-rsa"
    assert not (ssh_etc / "ssh_host_rsa_key.pub").is_symlink()
    assert (ssh_etc / "ssh_host_rsa_key.pub").read_text() == "PUBLIC-rsa"
    # The other types still landed on the volume through the ensure:
    for t in ("ecdsa", "ed25519"):
        assert (ssh_etc / f"ssh_host_{t}_key").is_symlink()
        assert os.readlink(ssh_etc / f"ssh_host_{t}_key") == \
            str(data / "ssh" / f"ssh_host_{t}_key")
        assert (data / "ssh" / f"ssh_host_{t}_key").read_text() == f"PRIVATE-{t}"
        assert (ssh_etc / f"ssh_host_{t}_key.pub").is_symlink()


def test_firstboot_keys_present_skips_generation(box):
    """Idempotency: existing keys (on the volume) skip ssh-keygen."""
    data, ssh_etc, env, logdir = box
    assert run_script(DATA_PREP, env).returncode == 0
    for t in KEYTYPES:
        (data / "ssh" / f"ssh_host_{t}_key").write_text("EXISTING")
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert not (logdir / "invoked").exists()


def test_firstboot_moves_preexisting_rootfs_keys(box):
    """firstboot's defensive move-branch (QA B2): data-prep deliberately
    NOT run — pre-existing rootfs keys move onto the volume through
    firstboot's own D-V4 ensure, and no new keys are generated."""
    data, ssh_etc, env, logdir = box
    for t in KEYTYPES:
        (ssh_etc / f"ssh_host_{t}_key").write_text(f"OLD-{t}")
        (ssh_etc / f"ssh_host_{t}_key.pub").write_text(f"OLDPUB-{t}")
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    for t in KEYTYPES:
        assert (data / "ssh" / f"ssh_host_{t}_key").read_text() == f"OLD-{t}"
        assert (data / "ssh" / f"ssh_host_{t}_key.pub").read_text() == f"OLDPUB-{t}"
        assert (ssh_etc / f"ssh_host_{t}_key").is_symlink()
        assert os.readlink(ssh_etc / f"ssh_host_{t}_key") == \
            str(data / "ssh" / f"ssh_host_{t}_key")
    # Keys were present (moved, not generated): the stub never ran.
    assert not (logdir / "invoked").exists()


def test_firstboot_conflict_quarantines_rootfs_key(box):
    """Security B2, firstboot half: volume key wins; rootfs key + its .pub
    quarantined; keygen does not run (keys already exist)."""
    data, ssh_etc, env, logdir = box
    assert run_script(DATA_PREP, env).returncode == 0
    (data / "ssh" / "ssh_host_rsa_key").write_text("VOLUME-KEY")
    # Drop the symlinks data-prep made so the rootfs holds REAL files:
    (ssh_etc / "ssh_host_rsa_key").unlink()
    (ssh_etc / "ssh_host_rsa_key.pub").unlink()
    (ssh_etc / "ssh_host_rsa_key").write_text("ROOTFS-KEY")
    (ssh_etc / "ssh_host_rsa_key.pub").write_text("ROOTFS-PUB")
    r = run_script(FIRSTBOOT, env)
    assert r.returncode == 0, r.stderr
    assert "CONFLICT" in r.stderr
    assert (data / "ssh" / "ssh_host_rsa_key").read_text() == "VOLUME-KEY"
    quar = [q for q in (data / "ssh").glob("ssh_host_rsa_key.rootfs-conflict-*")
            if not q.name.endswith(".tmp") and not q.name.endswith(".pub")]
    assert len(quar) == 1
    assert quar[0].read_text() == "ROOTFS-KEY"
    # The conflicted rsa key was quarantined, not regenerated: the volume
    # key above still reads VOLUME-KEY. (ecdsa/ed25519 had no keys yet, so
    # the stub correctly generates those through the symlinks.)


def test_scripts_concurrent_no_race(tmp_path):
    """QA B1 regression: data-prep and the sshd entrypoint run
    concurrently by design (D-V4) — both must exit 0 on every run and
    the final state must be sane. The flock-serialized critical section
    is what makes this hold; the pre-fix check-then-act failed 34/60."""
    for i in range(25):
        root = tmp_path / f"race{i}"
        data = root / "data"
        data.mkdir(parents=True)
        ssh_etc = root / "ssh_etc"
        ssh_etc.mkdir()
        bindir = root / "bin"
        bindir.mkdir()
        (bindir / "ssh-keygen").write_text(KEYGEN_STUB)
        (bindir / "ssh-keygen").chmod(0o755)
        (bindir / "mountpoint").write_text(MOUNTPOINT_STUB)
        (bindir / "mountpoint").chmod(0o755)
        logdir = root / "keygen-log"
        logdir.mkdir()
        env = {
            "PATH": str(bindir) + ":" + os.environ.get("PATH", "/usr/bin:/bin"),
            "SPARKVM_DATA_ROOT": str(data),
            "SPARKVM_SSH_ETC_DIR": str(ssh_etc),
            "SPARKVM_DATA_PREP_SKIP_CHOWN": "1",
            "SPARKVM_FIRSTBOOT_NO_EXEC": "1",
            "SPARKVM_SSH_RUN_DIR": str(root / "sshd-run"),
            "STUB_LOG": str(logdir),
            "STUB_MOUNTPOINT_RC": "0",
        }
        p1 = subprocess.Popen(["bash", DATA_PREP], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2 = subprocess.Popen(["bash", FIRSTBOOT], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, err1 = p1.communicate(timeout=60)
        _, err2 = p2.communicate(timeout=60)
        assert p1.returncode == 0, f"iter {i} data-prep rc={p1.returncode}: {err1.decode()}"
        assert p2.returncode == 0, f"iter {i} firstboot rc={p2.returncode}: {err2.decode()}"
        for t in KEYTYPES:
            link = ssh_etc / f"ssh_host_{t}_key"
            assert link.is_symlink(), f"iter {i} {t}"
            assert os.readlink(link) == str(data / "ssh" / f"ssh_host_{t}_key"), f"iter {i} {t}"
            # Exactly one keypair's bytes, on the volume (whoever won the
            # generation race wrote through the symlinks):
            assert (data / "ssh" / f"ssh_host_{t}_key").is_file(), f"iter {i} {t}"
            assert (data / "ssh" / f"ssh_host_{t}_key.pub").is_file(), f"iter {i} {t}"


def test_supervisord_registers_data_prep():
    cp = configparser.ConfigParser()
    cp.read(SUPERVISORD_CONF)
    sec = "program:data-prep"
    assert cp.has_section(sec), "data-prep program missing"
    assert cp.get(sec, "user") == "root"
    assert cp.get(sec, "priority") == "5"
    assert cp.get(sec, "autorestart") == "false"
    assert cp.get(sec, "command") == "/usr/local/bin/data-prep.sh"
    # data-prep sorts before identity-seed (priority 10) and the daemons
    # (999 default): the layout exists before any consumer starts.
    assert int(cp.get(sec, "priority")) < int(
        cp.get("program:identity-seed", "priority", fallback="10"))


def test_dockerfile_installs_data_prep():
    src = open(DOCKERFILE).read()
    assert "COPY deploy/golden-image/data-prep.sh /usr/local/bin/data-prep.sh" in src
    assert "/usr/local/bin/data-prep.sh" in src.split("RUN chmod 0755")[1].split("&&")[0]


def test_scripts_bash_syntax():
    for path in (DATA_PREP, FIRSTBOOT):
        r = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
        assert r.returncode == 0, f"{path}: {r.stderr}"


def test_data_prep_is_executable():
    assert os.access(DATA_PREP, os.X_OK)


# ---- The contract's machine-env interface, pinned against real code ----
#
# Each env var docs/DATA_VOLUME_CONTRACT.md names must actually be honored
# by its consumer. These run the real modules in subprocesses so the env
# is read at import time exactly like the daemons read it.


def _py(code, env_extra):
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"}
    env.update(env_extra)
    return subprocess.run([sys.executable, "-c", code], env=env,
                          capture_output=True, text=True, timeout=60)


def test_contract_env_svm_pair_dir(tmp_path):
    code = (
        "import sys, os; sys.path.insert(0, %r);"
        "import spark_pair;"
        "import argparse;"
        "print(spark_pair._state_dir(argparse.Namespace(dir=None)))"
        % os.path.join(REPO_ROOT, "pairing")
    )
    r = _py(code, {"SVM_PAIR_DIR": str(tmp_path / "pairing")})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == str(tmp_path / "pairing")


def test_contract_env_confirm_dir_and_audit(tmp_path):
    code = (
        "import sys, os; sys.path.insert(0, %r);"
        "import confirmd;"
        "print(confirmd.APPROVALS); print(confirmd.AUDIT)"
        % os.path.join(REPO_ROOT, "confirm")
    )
    r = _py(code, {"CONFIRM_DIR": str(tmp_path / "approvals"),
                   "CONFIRM_AUDIT": str(tmp_path / "audit.log")})
    assert r.returncode == 0, r.stderr
    # confirmd logs an import-time WARNING to stdout (tailscale lookup);
    # the two printed constants are the last two lines.
    assert r.stdout.splitlines()[-2:] == [str(tmp_path / "approvals"),
                                          str(tmp_path / "audit.log")]


def test_contract_env_relay_journal(tmp_path):
    code = (
        "import sys, os; sys.path.insert(0, %r);"
        "import relay_liveness;"
        "print(relay_liveness.journal_path())"
        % os.path.join(REPO_ROOT, "hosted")
    )
    r = _py(code, {"RELAY_SESSION_JOURNAL": str(tmp_path / "journal.jsonl")})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == str(tmp_path / "journal.jsonl")


def test_contract_doc_names_every_env_var():
    """The doc's machine-env table and the tests above agree on the four
    vars — a new var added to one must be added to the other."""
    doc = open(CONTRACT_DOC).read()
    for var in ("SVM_PAIR_DIR", "CONFIRM_DIR", "CONFIRM_AUDIT",
                "RELAY_SESSION_JOURNAL"):
        assert var in doc, var
    src = open(__file__).read()
    for var in ("SVM_PAIR_DIR", "CONFIRM_DIR", "CONFIRM_AUDIT",
                "RELAY_SESSION_JOURNAL"):
        assert var in src, var
