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

Exit codes: 0 ok (or loud first-deploy skip), 2 symlink/missing-source
refusal (fail closed), 1 other error.
"""
import argparse
import errno
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safe_install import safe_install

DEFAULT_SYS_BUNDLE = "/etc/ssl/certs/ca-certificates.crt"
DEFAULT_CA = "/home/swapd/.mitmproxy/mitmproxy-ca-cert.pem"
DEFAULT_DEST = "/usr/local/share/with-proxy-ca/ca-bundle.crt"


def _fail(msg):
    sys.stderr.write("build_ca_bundle: refusing: %s\n" % msg)
    raise SystemExit(2)


def _warn(msg):
    sys.stderr.write("build_ca_bundle: WARNING: %s\n" % msg)


def read_ca_bytes(ca_path):
    """Read the swapd-controlled CA cert, refusing symlinks atomically.

    ``O_NOFOLLOW`` makes the refusal part of the open itself: a symlink
    planted at *ca_path* (by swapd, or by anyone racing the deploy) fails
    with ELOOP instead of being read through. A dangling symlink also
    fails here — that is a broken/attacked deploy, not a first deploy,
    so it fails closed rather than skipping silently.
    """
    try:
        fd = os.open(ca_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        if e.errno == errno.ELOOP:
            _fail("%s is a symlink -- refusing to read through it "
                  "(issue #144)" % ca_path)
        raise
    with os.fdopen(fd, "rb") as f:
        return f.read()


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
        if args.ca_only:
            _fail("%s missing -- the jail trust store needs the swapd CA"
                  % args.ca)
        _warn("%s missing (first deploy?) -- skipping CA bundle; re-run "
              "after the proxy has started once" % args.ca)
        return 0

    content = (read_ca_bytes(args.ca) if args.ca_only
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
