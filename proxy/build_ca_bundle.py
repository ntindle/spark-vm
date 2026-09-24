#!/usr/bin/env python3
"""Build/install the with-proxy CA bundle without following swapd-planted symlinks.

GitHub issue #144 (severity: medium). The swapd CA source,
``/home/swapd/.mitmproxy/mitmproxy-ca-cert.pem``, lives in swapd-writable
space. The old ``deploy.sh`` step 4b ran, as root::

    sudo sh -c 'cat /etc/ssl/certs/ca-certificates.crt /home/swapd/.mitmproxy/mitmproxy-ca-cert.pem > /usr/local/share/with-proxy-ca/ca-bundle.crt'

``cat`` follows symlinks: a swapd-level attacker who replaced the CA cert
with a symlink to ``/etc/shadow`` (or any root-readable file) got the next
unattended root deploy to ``cat`` it into a world-readable bundle — a
local info-disclosure primitive under the #91/#128/#143 threat model.
``jail/build.sh`` had the same-class instance (``cp`` of the same source
into a world-readable ``/tmp`` staging file, then into the jail).

This helper fixes the *read* side the way ``safe_install.py`` fixed the
write side: the CA source is opened with ``O_NOFOLLOW``, so a symlink is
refused atomically with the open (``ELOOP``) — there is no
check-then-read TOCTOU window. The system CA bundle is a root-controlled
path and is read normally. The destination write goes through
``safe_install.safe_install``, which refuses symlink destinations and
enforces owner/mode on the open fd.

Modes:
  default            concatenate system bundle + swapd CA into DEST
                     (deploy.sh step 4b). A missing swapd CA is a legitimate
                     first-deploy state: skip LOUDLY, exit 0.
  --ca-only          write just the swapd CA bytes into DEST (jail trust
                     store). A missing CA is an error (the jail needs it).

Usage:
    build_ca_bundle.py [--dest PATH] [--ca-only] [--ca PATH] [--sys PATH]
                       [--owner NAME] [--group NAME] [--mode OCTAL]

Exit codes: 0 ok (or loud first-deploy skip), 2 symlink / hardlink /
non-regular / oversize / missing-source refusal (fail closed), 1 other error.
"""
import argparse
import errno
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safe_install import safe_install

DEFAULT_SYS_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"
DEFAULT_CA = "/home/swapd/.mitmproxy/mitmproxy-ca-cert.pem"
DEFAULT_DEST = "/usr/local/share/with-proxy-ca/ca-bundle.crt"

# A real mitmproxy CA cert is ~1-2 KiB. Cap the privileged read at 1 MiB:
# the CA path is swapd-writable, and an uncapped read lets a swapd-level
# attacker park a multi-GB (or sparse) regular file there for the root
# deploy to swallow whole into RAM (OOM) and into the world-readable
# bundle (disk-fill). The read is capped, so growth after the stat check
# cannot exceed it either (issue #300).
_MAX_CA_BYTES = 1 << 20


def _fail(msg):
    sys.stderr.write("build_ca_bundle: refusing: %s\n" % msg)
    raise SystemExit(2)


def _warn(msg):
    sys.stderr.write("build_ca_bundle: WARNING: %s\n" % msg)


def _missing_ca(ca_path, ca_only):
    if ca_only:
        _fail("%s missing -- the jail trust store needs the swapd CA"
              % ca_path)
    _warn("%s missing (first deploy?) -- skipping CA bundle; re-run "
          "after the proxy has started once" % ca_path)
    raise SystemExit(0)


def read_ca_bytes(ca_path, ca_only=False):
    """Read the swapd-controlled CA cert, refusing hostile inputs atomically.

    ``O_NOFOLLOW`` makes the symlink refusal part of the open itself: a
    symlink planted at *ca_path* (by swapd, or by anyone racing the deploy)
    fails with ELOOP instead of being read through. A dangling symlink also
    fails here — that is a broken/attacked deploy, not a first deploy,
    so it fails closed rather than skipping silently. Non-regular files
    (FIFO, directory, ...) are refused too: a planted FIFO would otherwise
    block the privileged read forever, so the open is ``O_NONBLOCK`` and
    the fd is fstat-checked before the first read (non-blocking is a
    no-op for regular files). Hardlinks are refused via ``st_nlink > 1``
    (a hardlink IS a regular file, so the symlink checks do not stop it;
    issue #299), independent of the ``fs.protected_hardlinks`` sysctl. The
    read itself is capped at 1 MiB (issue #300): a real CA cert is ~1-2 KiB,
    and the cap is enforced on the read, so post-stat growth cannot exceed
    it either.
    """
    try:
        fd = os.open(ca_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        _missing_ca(ca_path, ca_only)  # raced away between check and open
    except OSError as e:
        if e.errno == errno.ELOOP:
            _fail("%s is a symlink -- refusing to read through it "
                  "(issue #144)" % ca_path)
        raise
    # fstat the raw fd before fdopen: fdopen on a directory raises
    # IsADirectoryError, and a FIFO open would block without O_NONBLOCK.
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        _fail("%s is not a regular file -- refusing to read it "
              "(issue #144)" % ca_path)
    if st.st_nlink > 1:
        # A hardlink IS a regular file, so O_NOFOLLOW + S_ISREG do not stop
        # it: a swapd-level attacker could hardlink a root-readable file
        # into the CA path. Refuse independent of the fs.protected_hardlinks
        # sysctl (issue #299).
        os.close(fd)
        _fail("%s is a hardlink (nlink=%d) -- refusing to read it "
              "(issue #299)" % (ca_path, st.st_nlink))
    with os.fdopen(fd, "rb") as f:
        data = f.read(_MAX_CA_BYTES + 1)
    if len(data) > _MAX_CA_BYTES:
        _fail("%s is %d bytes (cap %d) -- refusing to read it into the "
              "privileged bundle (issue #300)"
              % (ca_path, len(data), _MAX_CA_BYTES))
    return data


def build_bundle(sys_path, ca_path):
    """System bundle bytes + swapd CA bytes."""
    with open(sys_path, "rb") as f:  # root-controlled path; no follow risk
        system = f.read()
    return system + read_ca_bytes(ca_path)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ca-only", action="store_true",
                    help="install just the swapd CA bytes, not the bundle")
    ap.add_argument("--ca", default=DEFAULT_CA,
                    help="swapd CA source path (default: %(default)s)")
    ap.add_argument("--sys", default=DEFAULT_SYS_BUNDLE,
                    help="system CA bundle (default: %(default)s)")
    ap.add_argument("--dest", default=DEFAULT_DEST,
                    help="destination path (default: %(default)s)")
    ap.add_argument("--owner", default="root", help="owner user (default: root)")
    ap.add_argument("--group", default="root", help="owner group (default: root)")
    ap.add_argument("--mode", default="0644",
                    help="octal mode to enforce (default: 0644)")
    args = ap.parse_args(argv)

    if not os.path.lexists(args.ca):
        _missing_ca(args.ca, args.ca_only)

    content = (read_ca_bytes(args.ca, ca_only=args.ca_only)
               if args.ca_only
               else build_bundle(args.sys, args.ca))
    try:
        result = safe_install(args.dest, content, owner=args.owner,
                              group=args.group, mode=int(args.mode, 8))
    except (OSError, KeyError) as e:
        sys.stderr.write("build_ca_bundle: %s: %s\n" % (args.dest, e))
        return 1
    sys.stderr.write("build_ca_bundle: %s: %s\n" % (args.dest, result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
