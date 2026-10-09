"""Socket-directory hardening for the bdrive daemon (GitHub #169).

Implements the code-side halves of #169's six path-validation
requirements for the planned jail bind-mount of the daemon socket:

1. The socket's *directory* (``/run/bdrive``) is the bind unit, never
   the socket file alone — file bind mounts go stale when the daemon
   recreates the socket, and unlink+bind races are exactly the
   CVE-2026-79994 shape. :func:`socket_dir_for` derives the directory
   from the configured socket path; ``bdrive.service`` binds the
   directory.
2. ``RuntimeDirectoryPreserve=yes`` lives in ``bdrive.service``
   (checked in beside this module) so a restart never wedges the
   jail's view — the daemon recreates only the socket file.
3. :func:`peer_uid_ok` applies ``SO_PEERCRED`` on every accepted
   connection and matches the *exact* numeric mapped uid of the
   jail's ``muse`` user (2000000 + the container uid, resolved at
   daemon install from the jail's ``uid_map`` — ``jail/build.sh`` does
   not pin the guest uid, so a range check would also admit jail
   root; never match the range), and ``obox`` later. Kernel-provided,
   no TOCTOU.
4. The daemon never resolves a client-supplied listen/connect path —
   the socket path comes from daemon config (``bdrive.config`` keeps
   it env-scoped via ``BDRIVE_SOCKET``; that must survive). Any other
   daemon-side path taken from the action protocol (downloads,
   profile dirs) must be resolved with dirfd pinning + ``O_NOFOLLOW``
   — :func:`resolve_within` is that mechanism, pinned before the
   execution backend exists.
5. :func:`prepare_socket_dir` creates ``/run/bdrive`` 0710 owned by
   the service user with group = exactly the client group (traverse,
   no list), and :func:`harden_socket_file` chowns the socket itself
   to the client group at 0770 — it must be called immediately after
   ``bind()``, because the fresh socket inode is born owned by the
   daemon's own uid:gid with a umask-derived mode (without the call
   the jail's client group cannot connect on first boot). So the
   jail's accepted uid can reach the listener but enumerate nothing,
   and the jail's *other* mapped uids (jail root = host 2000000)
   cannot reach it at all.
6. :func:`check_socket_dir` fails closed if the directory contains
   anything but the socket file — no pidfiles, logs, or other daemon
   state where the jail's accepted uid could read them; the daemon
   owns the directory with no group write, so the jail can never
   plant symlinks there.

Stdlib only. Fail loud (:class:`SocketDirError`), never as a
mysteriously misbehaving daemon.
"""

import errno
import grp
import os
import pwd
import socket
import stat
import struct

DIR_MODE = 0o710
SOCKET_MODE = 0o770


class SocketDirError(ValueError):
    """A socket-directory invariant is violated — fail closed."""


class PathTraversalError(SocketDirError):
    """A daemon-side path escaped its base directory or hit a symlink."""


def socket_dir_for(socket_path):
    """The bind-mount unit for a socket path: its directory (#169 req 1).

    Rejects degenerate paths — ``socket_dir_for("/")`` returning ``"/"``
    would let ``prepare_socket_dir`` chown/chmod the filesystem root
    before the hygiene check fails closed.
    """
    if not isinstance(socket_path, str) or not socket_path.startswith("/"):
        raise SocketDirError(
            "socket path must be absolute, got %r" % (socket_path,))
    dir_path = os.path.dirname(socket_path)
    if not os.path.basename(socket_path) or dir_path in ("", "/"):
        raise SocketDirError(
            "socket path %r has no usable directory component"
            % (socket_path,))
    return dir_path


def _resolve_user(name):
    try:
        return pwd.getpwnam(name).pw_uid
    except KeyError:
        raise SocketDirError("service user %r does not exist" % (name,))


def _resolve_group(name):
    try:
        return grp.getgrnam(name).gr_gid
    except KeyError:
        raise SocketDirError("client group %r does not exist" % (name,))


def check_socket_dir(dir_path, socket_name):
    """Fail closed unless the dir holds at most the socket file (#169 req 6).

    ``socket_name`` is the socket file's basename (e.g. ``bdrive.sock``).
    The directory may be empty (daemon recreates the socket on start —
    that is the whole point of req 1/2) or contain exactly the socket
    file. Anything else — pidfiles, logs, symlinks the jail could have
    planted — is a hard failure.
    """
    try:
        entries = os.listdir(dir_path)
    except OSError as exc:
        raise SocketDirError(
            "cannot list socket dir %r: %s" % (dir_path, exc))
    for e in entries:
        try:
            st = os.lstat(os.path.join(dir_path, e))
        except OSError as exc:
            raise SocketDirError(
                "cannot stat socket dir entry %r: %s" % (e, exc))
        if stat.S_ISLNK(st.st_mode):
            raise SocketDirError(
                "socket dir %r holds symlink %r — refusing to serve"
                % (dir_path, e))
    unexpected = [e for e in entries if e != socket_name]
    if unexpected:
        raise SocketDirError(
            "socket dir %r holds unexpected entries %r — refusing to "
            "serve (only the socket file may live here)" % (
                dir_path, sorted(unexpected)))


def prepare_socket_dir(socket_path, service_user, client_group,
                       dir_mode=DIR_MODE, socket_mode=SOCKET_MODE):
    """Create/harden the socket directory (#169 reqs 1, 5, 6).

    Creates ``dirname(socket_path)`` (0710, owned by ``service_user``,
    group ``client_group`` — traverse, no list), fails closed on
    unexpected directory entries, and sets the socket file itself to
    0770 when it already exists. Returns the directory path.

    Call once at daemon start, before ``bind()``.
    """
    dir_path = socket_dir_for(socket_path)
    uid = _resolve_user(service_user)
    gid = _resolve_group(client_group)
    try:
        os.makedirs(dir_path, mode=dir_mode, exist_ok=True)
    except OSError as exc:
        raise SocketDirError(
            "cannot create socket dir %r: %s" % (dir_path, exc))
    # makedirs no-ops when dir_path is a symlink to a directory —
    # never harden through it (that would chmod/chown the target).
    try:
        dir_is_link = stat.S_ISLNK(os.lstat(dir_path).st_mode)
    except OSError as exc:
        raise SocketDirError(
            "cannot stat socket dir %r: %s" % (dir_path, exc))
    if dir_is_link:
        raise SocketDirError(
            "socket dir %r is a symlink — refusing to harden through it"
            % (dir_path,))
    # makedirs ignores mode on existing dirs — pin it explicitly.
    try:
        os.chown(dir_path, uid, gid)
        os.chmod(dir_path, dir_mode)
    except OSError as exc:
        raise SocketDirError(
            "cannot harden socket dir %r: %s" % (dir_path, exc))
    check_socket_dir(dir_path, os.path.basename(socket_path))
    if os.path.exists(socket_path):
        harden_socket_file(socket_path, service_user, client_group,
                           socket_mode=socket_mode)
    return dir_path


def harden_socket_file(socket_path, service_user, client_group,
                       socket_mode=SOCKET_MODE):
    """Chown/chmod the socket file itself (#169 req 5).

    The daemon must call this immediately after bind(): the socket
    inode is created by bind() owned by the daemon's own uid:gid with
    a umask-derived mode, so without this the jail's client group
    cannot connect (and the mode is not 0770). Fail closed on error.
    """
    uid = _resolve_user(service_user)
    gid = _resolve_group(client_group)
    try:
        os.chown(socket_path, uid, gid)
        os.chmod(socket_path, socket_mode)
    except OSError as exc:
        raise SocketDirError(
            "cannot harden socket file %r: %s" % (socket_path, exc))


def peer_uid_ok(conn, allowed_uids):
    """SO_PEERCRED peer check for an accepted unix-socket connection.

    Returns True only when the kernel-reported peer uid is an *exact*
    member of ``allowed_uids`` — never a range (#169 req 3). A
    getsockopt failure returns False (fail closed: the peer is
    rejected); deciding what to log is the daemon's job.
    """
    if not allowed_uids:
        return False
    try:
        raw = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                              struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", raw)
    except (OSError, struct.error):
        return False
    return uid in allowed_uids


def serve_preflight(cfg):
    """Daemon-start gate: refuse to serve without accepted client uids.

    #169 req 3 resolves the exact mapped uids at daemon install (from
    the jail's ``uid_map``); a config with no accepted uids must never
    silently serve every peer. Returns the hardened socket directory.
    """
    if not cfg.client_uids:
        raise SocketDirError(
            "BDRIVE_CLIENT_UIDS lists no accepted client uids — refusing "
            "to serve (resolve the jail's mapped agent uid from its "
            "uid_map at install time; never match a uid range)")
    return prepare_socket_dir(cfg.socket_path, cfg.service_user,
                              cfg.client_group)


def _split_rel(rel_path):
    """Split a relative path into safe components, or fail closed."""
    if not isinstance(rel_path, str) or not rel_path:
        raise PathTraversalError("path must be a non-empty string")
    if "\x00" in rel_path:
        raise PathTraversalError("path contains NUL byte")
    if os.path.isabs(rel_path):
        raise PathTraversalError(
            "absolute path %r not allowed" % (rel_path,))
    parts = rel_path.split(os.sep)
    if any(p in ("", ".", "..") for p in parts):
        raise PathTraversalError(
            "path %r escapes or is empty" % (rel_path,))
    return parts


def _pin_parent(base_dir, parts):
    """Open every component but the last, dirfd-pinned, no symlinks.

    Returns ``(parent_fd, final_name)``; the caller owns ``parent_fd``
    and must close it. Every intermediate component is opened
    ``O_DIRECTORY | O_NOFOLLOW`` from the previous fd, so a symlink
    planted anywhere in the chain fails closed with ELOOP instead of
    being followed.
    """
    try:
        dir_fd = os.open(base_dir, os.O_RDONLY | os.O_NOFOLLOW
                         | os.O_DIRECTORY)
    except OSError as exc:
        raise PathTraversalError(
            "cannot pin base dir %r: %s" % (base_dir, exc))
    try:
        for part in parts[:-1]:
            try:
                child = os.open(part, os.O_RDONLY | os.O_NOFOLLOW
                                | os.O_DIRECTORY, dir_fd=dir_fd)
            except OSError as exc:
                raise PathTraversalError(
                    "component %r not a real directory: %s" % (part, exc))
            os.close(dir_fd)
            dir_fd = child
    except BaseException:
        os.close(dir_fd)
        raise
    return dir_fd, parts[-1]


def resolve_within(base_dir, rel_path):
    """Resolve an existing daemon-side path under ``base_dir``.

    #169 req 4: the parent chain is walked dirfd-pinned with
    ``O_NOFOLLOW`` (:func:`_pin_parent`); the final component is
    opened ``O_NOFOLLOW`` too, so a symlink at any level fails
    closed instead of being followed. Returns the resolved absolute
    path.

    NOTE: the pin holds only for the duration of this call — the
    return value is a path string, not the pinned fd. The backend
    must use the result immediately; a component swapped between this
    return and the backend's own open reintroduces the TOCTOU this
    module was built to kill. (An fd-returning variant is planned
    when the execution backend lands.)

    The execution backend uses this for every daemon-side path taken
    from the action protocol (downloads, profile dirs) — the socket
    path itself is never client-supplied and never passes through
    here. For creating new files, use :func:`create_within`.
    """
    parts = _split_rel(rel_path)
    parent_fd, name = _pin_parent(base_dir, parts)
    try:
        try:
            target = os.open(name, os.O_RDONLY | os.O_NOFOLLOW,
                             dir_fd=parent_fd)
        except OSError as exc:
            raise PathTraversalError(
                "final component %r of %r unusable: %s" % (
                    name, rel_path, exc))
        os.close(target)
    finally:
        os.close(parent_fd)
    return os.path.join(base_dir, *parts)


def create_within(base_dir, rel_path, mode=0o600, flags=os.O_WRONLY):
    """Create a daemon-side file under ``base_dir``, race-free.

    The parent chain is dirfd-pinned (:func:`_pin_parent`); the final
    component is created with ``O_CREAT | O_EXCL | O_NOFOLLOW`` under
    the pinned parent, so a symlink planted at the target name fails
    closed instead of being followed. Returns the open fd (caller
    owns it). ``flags`` may add e.g. ``os.O_APPEND``; ``O_CREAT``,
    ``O_EXCL`` and ``O_NOFOLLOW`` are always forced.
    """
    parts = _split_rel(rel_path)
    parent_fd, name = _pin_parent(base_dir, parts)
    try:
        return os.open(name, flags | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                       mode, dir_fd=parent_fd)
    except OSError as exc:
        # O_EXCL is always forced, so a benign re-create of an existing
        # name lands here — it must not wear the attack label. The
        # execution backend treats PathTraversalError as a symlink
        # attack; EEXIST is an ordinary collision.
        if exc.errno == errno.EEXIST:
            raise SocketDirError(
                "cannot create %r: already exists" % (rel_path,))
        raise PathTraversalError(
            "cannot create %r: %s" % (rel_path, exc))
    finally:
        os.close(parent_fd)
