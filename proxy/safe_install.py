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

This helper covers the rest. It is race-free: ``os.lstat`` refuses an
existing symlink loudly (fail closed -- a symlink at a root-write destination
is an attack indicator), then the file is opened with ``O_NOFOLLOW`` so a
symlink planted between the check and the open fails with ELOOP instead of
being written through, and ``fchown``/``fchmod`` act on the open fd, never
the path.

Usage:
    safe_install.py [--src PATH | --stdin] [--create-only]
                    [--owner NAME] [--group NAME] [--mode OCTAL] DEST

  --src PATH     copy these bytes into DEST (DEST is truncated first)
  --stdin        copy stdin into DEST (DEST is truncated first)
  --create-only  create DEST with the content only if absent (O_EXCL); when
                 DEST already exists the content is left alone but owner/mode
                 are still enforced. The check-and-create is one privileged
                 step, so it does not depend on the caller's traverse rights
                 over the parent dir (deploy.sh's old ``[ -f ]`` guard ran
                 unprivileged and misfired when /home/swapd was not
                 traversable).
  (no content flags)  open the existing DEST and enforce owner/mode only.
"""
import argparse
import errno
import os
import pwd
import grp
import stat
import sys


def _fail(msg):
    sys.stderr.write("safe_install: refusing: %s\n" % msg)
    raise SystemExit(2)


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
    try:
        st = os.lstat(dest)
    except FileNotFoundError:
        st = None
    if st is not None and stat.S_ISLNK(st.st_mode):
        _fail("%s is a symlink -- refusing to write through it" % dest)

    flags = os.O_WRONLY | os.O_NOFOLLOW
    if content is not None:
        if create_only:
            # Atomic check-and-create: O_EXCL makes the create fail if DEST
            # appeared between the lstat and the open; EEXIST falls through
            # to the enforce-only path below.
            try:
                fd = os.open(dest, flags | os.O_CREAT | os.O_EXCL, 0o600)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                fd = None
            if fd is not None:
                try:
                    _write_all(fd, content)
                    _enforce(fd, dest, owner, group, mode)
                finally:
                    os.close(fd)
                return "created"
            # else: someone else created it; enforce on the existing file.
        else:
            fd = os.open(dest, flags | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                _write_all(fd, content)
                _enforce(fd, dest, owner, group, mode)
            finally:
                os.close(fd)
            return "written"
    # Enforce-only (or create-only when the file already existed).
    try:
        fd = os.open(dest, flags)
    except OSError as e:
        if e.errno == errno.ELOOP:
            _fail("%s became a symlink between check and open" % dest)
        raise
    try:
        _enforce(fd, dest, owner, group, mode)
    finally:
        os.close(fd)
    return "enforced"


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
        with open(args.src, "rb") as f:
            content = f.read()
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
