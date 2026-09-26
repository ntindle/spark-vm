#!/usr/bin/env python3
"""Write a file as root without ever writing *through* a symlink (deploy.sh).

deploy.sh runs privileged writes into /home/swapd, which the swapd account
can write. cp/tee/chown/chmod all follow symlinks: a swapd-level attacker who
planted e.g. ``/home/swapd/ssrf.deny -> /etc/passwd`` would get the next
(unattended, root) deploy to write through it -- and ``chown swapd:swapd``
would hand them the target. Same class as #91 (fixed for the secrets dirs by
``enforce_secrets_dir.py``) and #128 (grants.json).

Empirically verified on this box's coreutils:
  - ``install`` and ``mv -f`` REPLACE a destination symlink (unlink+create),
    so deploy.sh steps 1/2 (install) and 6 (sudoers mv) are already safe;
  - ``cp src dst``, ``tee [-a] dst``, ``chown`` and ``chmod`` FOLLOW it.

This helper covers the rest. It is race-free and substitution-proof:

- ``os.lstat`` refuses an existing symlink at DEST loudly (fail closed --
  a symlink at a root-write destination is an attack indicator);
- the parent directory is then pinned with an ``O_DIRECTORY | O_NOFOLLOW``
  dirfd, and from that point nothing is re-addressed by bare path;
- content stages into a fresh 0700 staging directory with a 128-bit
  random name inside the pinned parent (``O_CREAT | O_EXCL`` temp,
  ``fchown``/``fchmod`` on the open fd) -- unpredictable names defeat the
  #333 pre-creation deploy-DoS (a collision is retried, then fail closed);
- a single ``renameat`` (write) or ``linkat`` (create-only) installs it.

A swapd-level attacker with write on the parent directory cannot substitute
the staged temp: it is never visible in the parent-dir path namespace, and
the install addresses it by (dirfd, name) (issue #301). A racing reader sees
the old file or the new file, never a truncated one.

Deliberate, documented tradeoff: a symlink planted at DEST between the lstat
pre-check and the install is atomically *replaced* by the rename rather than
failing loudly -- the rename never writes *through* a symlink, so the unsafe
outcome is impossible; only the loudness differs from the old ELOOP path.

Usage:
    safe_install.py [--src PATH | --stdin] [--create-only]
                    [--owner NAME] [--group NAME] [--mode OCTAL] DEST

  --src PATH     copy these bytes into DEST (DEST is replaced atomically)
  --stdin        copy stdin into DEST (DEST is replaced atomically)
  --create-only  create DEST with the content only if absent (atomic link);
                 when DEST already exists the content is left alone but
                 owner/mode are still enforced.
  (no content flags)  open the existing DEST and enforce owner/mode only.
"""
import argparse
import errno
import os
import pwd
import grp
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from privileged_read import DEFAULT_MAX_BYTES, privileged_read


def _fail(msg):
    sys.stderr.write("safe_install: refusing: %s\n" % msg)
    raise SystemExit(2)


# Staging-dir name entropy: 128 random bits. The parent dir is attacker-
# writable (the threat model -- /home/swapd), so a predictable
# ".safe_install.<pid>.<n>.d" name let the attacker pre-create colliding
# dirs and force the fail-closed EEXIST abort on every deploy (deploy DoS,
# issue #333). Random names make pre-creation infeasible; the EEXIST
# fail-closed path survives only as an attack indicator (issue #333) and
# is retried a bounded number of times before refusing.
_STAGE_CREATE_RETRIES = 5


# --src reads are privileged (deploy.sh runs as root): route them through
# the shared open discipline (issues #144/#299/#300/#372, #413) instead of
# a plain open() -- a symlink planted at --src used to be followed and its
# bytes installed to a privileged destination by a privileged process.
# The cap is the discipline's shared default (deploy inputs: allow/deny
# lists, sudoers fragments -- all far smaller).
_MAX_SRC_BYTES = DEFAULT_MAX_BYTES


def _random_stage_name():
    return ".safe_install.%s.d" % os.urandom(16).hex()


# Name of the staged temp *inside* the staging dir. The staging dir is
# private per install, so a fixed name is safe; it is still addressed by
# (dirfd, name), never by path.
_TMP_NAME = ".tmp"


def _lstat_name(parent_fd, name):
    try:
        return os.lstat(name, dir_fd=parent_fd)
    except FileNotFoundError:
        return None


def _stage(parent_fd, content, owner, group, mode, dest):
    """Stage content into a fresh 0700 staging dir; return (stage_fd, name).

    The staging dir has a random name (128 bits, issue #333) and is
    created ``O_EXCL``-style (``mkdir`` fails EEXIST on collision --
    retried a bounded number of times, then fail closed), and the temp
    inside is ``O_CREAT | O_EXCL | O_NOFOLLOW``. Both are addressed by
    dirfd from here on.
    """
    for _ in range(_STAGE_CREATE_RETRIES):
        stage = _random_stage_name()
        try:
            os.mkdir(stage, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            continue  # astronomically unlikely; try a fresh random name
        break
    else:
        _fail("staging dir collision after %d retries -- refusing"
              % _STAGE_CREATE_RETRIES)
    stage_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                       dir_fd=parent_fd)
    try:
        # Identity check: mkdir -> open resolves the staging dir BY NAME
        # through the (possibly attacker-writable) parent. An attacker who
        # won that microsecond race (rename the real dir away, mkdir their
        # own) would own stage_fd's dir and could substitute the temp
        # downstream. Fail closed unless the opened dir is ours: owned by
        # us and mode 0700 (an attacker's replacement can never be
        # euid-owned). (Security round-2 review, PR #332.)
        st = os.fstat(stage_fd)
        if st.st_uid != os.geteuid() or stat.S_IMODE(st.st_mode) != 0o700:
            _fail("staging dir %s failed identity check -- refusing" % stage)
        try:
            fd = os.open(_TMP_NAME,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=stage_fd)
        except FileExistsError:
            _fail("staged temp already exists -- refusing (collision)")
        try:
            _write_all(fd, content)
            _enforce(fd, dest, owner, group, mode)
        finally:
            os.close(fd)
    except BaseException:
        # Unlink the staged temp BEFORE rmdir: without this, a failure in
        # _write_all/_enforce left ".tmp" behind and the rmdir died with
        # ENOTEMPTY (silently ignored), littering ".safe_install.*" staging
        # dirs in the deploy parent (issue #335). With the temp gone the
        # rmdir succeeds and the parent is left clean.
        try:
            os.unlink(_TMP_NAME, dir_fd=stage_fd)
        except OSError:
            pass
        os.close(stage_fd)
        try:
            os.rmdir(stage, dir_fd=parent_fd)
        except OSError:
            pass
        raise
    return stage_fd, stage


def _install_staged(stage_fd, parent_fd, name, create_only):
    """Install the staged temp at (parent_fd, name). Return True if installed.

    The source is addressed as (stage_fd, _TMP_NAME): even an attacker with
    write on the parent directory cannot substitute it, because it is never
    re-resolved through the path namespace.
    """
    if create_only:
        # os.link fails EEXIST when the destination already exists: atomic
        # create-only semantics, matching the old O_EXCL path.
        try:
            os.link(_TMP_NAME, name, src_dir_fd=stage_fd,
                    dst_dir_fd=parent_fd)
        except FileExistsError:
            return False  # someone else installed it; caller enforces
        return True
    # renameat(2) is atomic and never follows the destination: readers see
    # old or new bytes, never partial.
    os.rename(_TMP_NAME, name, src_dir_fd=stage_fd, dst_dir_fd=parent_fd)
    return True


def _teardown_stage(parent_fd, stage_fd, stage):
    """Remove the staging dir; never fail the install over cleanup."""
    try:
        try:
            os.unlink(_TMP_NAME, dir_fd=stage_fd)
        except FileNotFoundError:
            pass
    finally:
        os.close(stage_fd)
        try:
            os.rmdir(stage, dir_fd=parent_fd)
        except OSError:
            pass


def _enforce_at(parent_fd, name, dest, owner, group, mode):
    try:
        fd = os.open(name, os.O_WRONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except OSError as e:
        if e.errno == errno.ELOOP:
            _fail("%s became a symlink between check and open" % dest)
        raise
    try:
        _enforce(fd, dest, owner, group, mode)
    finally:
        os.close(fd)
    return "enforced"


def _resolve_owner(owner, group):
    uid = pwd.getpwnam(owner).pw_uid if owner else -1
    if group:
        gid = grp.getgrnam(group).gr_gid
    elif owner:
        gid = pwd.getpwnam(owner).pw_gid
    else:
        gid = -1
    return uid, gid


def safe_install(dest, content=None, create_only=False, owner=None,
                 group=None, mode=None):
    """Write content to dest (bytes or None) without following symlinks."""
    parent, name = os.path.split(os.path.abspath(dest))
    # Pin the parent dir by fd (O_NOFOLLOW: the parent itself must not be a
    # symlink). A renamed-away parent cannot redirect anything below.
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st = _lstat_name(parent_fd, name)
        if st is not None and stat.S_ISLNK(st.st_mode):
            _fail("%s is a symlink -- refusing to write through it" % dest)
        if content is not None:
            stage_fd, stage = _stage(parent_fd, content, owner, group, mode,
                                     dest)
            try:
                installed = _install_staged(stage_fd, parent_fd, name,
                                            create_only)
            finally:
                _teardown_stage(parent_fd, stage_fd, stage)
            if installed:
                return "created" if create_only else "written"
            # create_only lost the atomic race: someone else installed dest;
            # enforce on what landed.
        return _enforce_at(parent_fd, name, dest, owner, group, mode)
    finally:
        os.close(parent_fd)


def _write_all(fd, content):
    view = memoryview(content)
    while view:
        n = os.write(fd, view)
        view = view[n:]
    os.fsync(fd)


def _enforce(fd, dest, owner, group, mode):
    uid, gid = _resolve_owner(owner, group)
    if uid != -1 or gid != -1:
        os.fchown(fd, uid, gid)
    if mode is not None:
        os.fchmod(fd, mode)
    st = os.fstat(fd)
    sys.stderr.write(
        "safe_install: %s now %s:%o\n"
        % (dest, pwd.getpwuid(st.st_uid).pw_name, stat.S_IMODE(st.st_mode)))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--src", help="file whose bytes are written to DEST")
    src.add_argument("--stdin", action="store_true",
                     help="read the bytes from stdin")
    ap.add_argument("--create-only", action="store_true",
                     help="only write content when DEST does not exist")
    ap.add_argument("--owner", help="owner user name to enforce")
    ap.add_argument("--group", help="group name to enforce (default: owner's)")
    ap.add_argument("--mode", help="octal mode to enforce, e.g. 0600")
    ap.add_argument("dest", help="destination path")
    args = ap.parse_args(argv)

    content = None
    if args.src is not None:
        content = privileged_read(
            args.src,
            lambda: _fail("--src %s missing -- refusing" % args.src),
            max_bytes=_MAX_SRC_BYTES)
    elif args.stdin:
        content = sys.stdin.buffer.read()

    mode = int(args.mode, 8) if args.mode is not None else None
    try:
        result = safe_install(args.dest, content,
                              create_only=args.create_only,
                              owner=args.owner, group=args.group, mode=mode)
    except (OSError, KeyError) as e:
        sys.stderr.write("safe_install: %s: %s\n" % (args.dest, e))
        return 1
    sys.stderr.write("safe_install: %s: %s\n" % (args.dest, result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
