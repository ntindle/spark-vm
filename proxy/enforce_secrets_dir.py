#!/usr/bin/env python3
"""Enforce 0700 swapd-only ownership on the secrets dirs (issue #91).

Called by proxy/deploy.sh [4c/7] under sudo, once per directory:

    sudo python3 proxy/enforce_secrets_dir.py /home/swapd/secrets \\
        /home/swapd/inference-secrets

Never chown/chmod *through* a symlink: both follow symlinks, and a
swapd-level attacker who planted `<dir> -> /etc` would otherwise get the
next (unattended) deploy to hand them ownership of a system directory.
Refusal is loud (nonzero exit) and race-free: lstat checks the type,
then os.open with O_NOFOLLOW + O_DIRECTORY fails with ELOOP if the path
was swapped to a symlink in between, and fchown/fchmod act on the open
fd, not the path.
"""
import os
import pwd
import stat
import sys

OWNER = "swapd"
MODE = 0o700


def _fail(path, reason):
    sys.stderr.write("enforce_secrets_dir: refusing %s: %s\n" % (path, reason))
    raise SystemExit(1)


def enforce(path, owner=OWNER, mode=MODE):
    """Enforce owner:mode on an existing directory, refusing symlinks.

    Returns (before, after) owner:mode strings for audit; prints a WARNING
    to stderr when the enforcement changed anything.
    """
    st = os.lstat(path)
    if not stat.S_ISDIR(st.st_mode):
        _fail(path, "not a directory (symlink refused)" if stat.S_ISLNK(st.st_mode)
              else "not a directory")
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        u = pwd.getpwnam(owner)
        os.fchown(fd, u.pw_uid, u.pw_gid)
        os.fchmod(fd, mode)
    finally:
        os.close(fd)
    before = "%s:%o" % (pwd.getpwuid(st.st_uid).pw_name, stat.S_IMODE(st.st_mode))
    after = "%s:%o" % (owner, mode)
    if before != after:
        sys.stderr.write(
            "WARNING: %s was %s before enforcement (repaired to %s)\n"
            % (path, before, after))
    return before, after


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: enforce_secrets_dir.py <dir> [dir...]\n")
        return 2
    for path in argv[1:]:
        enforce(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
