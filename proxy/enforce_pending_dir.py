#!/usr/bin/env python3
"""Create and enforce the confirmd pending/ filing directory (issue #1167).

Finding 50's owner-identifies-requester invariant needs
<CONFIRM_DIR>/pending to be a setgid directory owned by the filing
principals' shared group (root:approval-filers, mode 2770). mkdir(2)
drops S_ISGID even for root, so confirm-request's makedirs can never
establish this — the deploy step must.

Called by proxy/deploy.sh [4e/7] under sudo (the parent dir is created
first as swapd, so confirmd's own makedirs for answered//consumed keep
working):

    sudo -u swapd mkdir -p "$APPROVALS"
    sudo python3 proxy/enforce_pending_dir.py --create \
        --owner root --group approval-filers --mode 2770 \
        "$APPROVALS/pending"

Symlink discipline (the same as proxy/enforce_secrets_dir.py): never
chown/chmod *through* a symlink. The leaf is lstat-checked — a symlink
leaf is a loud refusal — every ancestor component is lstat-checked too
(a swapd-level attacker must not be able to redirect the deploy into a
system tree via a symlinked parent), then the leaf is opened with
O_NOFOLLOW | O_DIRECTORY and fchown/fchmod act on the open fd, not the
path. With --create, missing ancestors are created with os.mkdir one
component at a time (never makedirs through a symlink); without
--create a missing leaf is a loud refusal.

A WARNING goes to stderr whenever the enforcement repaired drift.
Refusal is a loud nonzero exit; deploy.sh runs with set -e, so the
deploy stops instead of leaving a half-secured directory.
"""
import argparse
import grp
import os
import pwd
import stat
import sys


def _fail(path, reason):
    sys.stderr.write("enforce_pending_dir: refusing %s: %s\n"
                     % (path, reason))
    raise SystemExit(1)


def _resolve_ids(owner, group):
    try:
        uid = pwd.getpwnam(owner).pw_uid
    except KeyError:
        _fail(owner, "no such user")
    try:
        gid = grp.getgrnam(group).gr_gid
    except KeyError:
        _fail(group, "no such group")
    return uid, gid


def _parse_mode(text):
    try:
        mode = int(text, 8)
    except (TypeError, ValueError):
        _fail(text, "mode must be octal, e.g. 2770")
    if not 0 <= mode <= 0o7777:
        _fail(text, "mode out of range 0000..7777")
    return mode


def _ensure_parents(path, create):
    """Walk the ancestor components of an absolute path.

    Every existing ancestor must be a real directory — a symlink
    ancestor is a loud refusal, never followed. Missing ancestors are
    created with os.mkdir one component at a time when `create` is
    true, a loud refusal otherwise.
    """
    parts = path.split(os.sep)
    cur = os.sep
    for part in parts[1:-1]:
        if not part:
            continue  # tolerate doubled slashes
        cur = os.path.join(cur, part)
        try:
            st = os.lstat(cur)
        except FileNotFoundError:
            if not create:
                _fail(cur, "ancestor does not exist "
                           "(pass --create to create it)")
            try:
                os.mkdir(cur, 0o755)
            except FileExistsError:
                pass  # raced with a parallel deploy; re-check below
            st = os.lstat(cur)
        except OSError as e:
            _fail(cur, "cannot lstat ancestor: %s" % e)
        if stat.S_ISLNK(st.st_mode):
            _fail(cur, "ancestor is a symlink — refusing to build "
                       "through it")
        if not stat.S_ISDIR(st.st_mode):
            _fail(cur, "ancestor is not a directory")


def enforce(path, owner, group, mode, create):
    """Enforce owner:group and mode on the leaf directory.

    Returns (before, after) owner:group:mode strings for audit; prints
    a WARNING to stderr when the enforcement changed anything.
    """
    path = os.path.normpath(path)
    if not os.path.isabs(path):
        _fail(path, "path must be absolute")
    uid, gid = _resolve_ids(owner, group)
    mode = _parse_mode(mode)
    # Ancestors first: never mkdir the leaf through a symlinked parent.
    _ensure_parents(path, create)
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        st = None
    except OSError as e:
        _fail(path, "cannot lstat: %s" % e)
    if st is None:
        if not create:
            _fail(path, "does not exist (pass --create to create it)")
        try:
            # Tight until the fchmod below sets the real mode.
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass  # raced with a parallel deploy; enforce what is there
        st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode):
        _fail(path, "is a symlink — refusing to enforce through it")
    if not stat.S_ISDIR(st.st_mode):
        _fail(path, "exists but is not a directory")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as e:
        _fail(path, "cannot O_NOFOLLOW-open (swapped under us?): %s" % e)
    try:
        os.fchown(fd, uid, gid)
        os.fchmod(fd, mode)
    finally:
        os.close(fd)
    before = "%s:%s:%o" % (pwd.getpwuid(st.st_uid).pw_name,
                           grp.getgrgid(st.st_gid).gr_name,
                           stat.S_IMODE(st.st_mode))
    after = "%s:%s:%o" % (owner, group, mode)
    if before != after:
        sys.stderr.write(
            "WARNING: %s was %s before enforcement (repaired to %s)\n"
            % (path, before, after))
    return before, after


def main(argv):
    ap = argparse.ArgumentParser(
        description="Create and enforce the confirmd pending/ filing "
                    "directory (issue #1167).")
    ap.add_argument("path", help="absolute path of the pending directory")
    ap.add_argument("--owner", default="root")
    ap.add_argument("--group", default="approval-filers")
    ap.add_argument("--mode", default="2770",
                    help="octal mode, e.g. 2770")
    ap.add_argument("--create", action="store_true",
                    help="create the directory (and missing ancestors) "
                         "when absent")
    args = ap.parse_args(argv)
    enforce(args.path, args.owner, args.group, args.mode, args.create)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
