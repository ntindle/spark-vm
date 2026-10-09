"""Hermetic tests for the bdrive socket-directory hardening (#169).

Covers browser-driver/bdrive/socket_dir.py (bind-unit derivation,
0710/0770 prepare discipline, fail-closed directory hygiene,
SO_PEERCRED exact-uid peer checks, dirfd-pinned + O_NOFOLLOW path
resolution) and the config.py additions (socket_dir, client_uids).

Stdlib + pytest only. Uses socket.socketpair() for the peer-cred
checks — local unix sockets, no network. Everything runs as the
current user in tmp dirs.
"""

import grp
import os
import pwd
import socket
import stat
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bdrive import config as C
from bdrive import socket_dir as S


@pytest.fixture(autouse=True)
def _restore_sys_path():
    before = list(sys.path)
    before_mods = set(sys.modules)
    yield
    sys.path[:] = before
    for name in list(sys.modules):
        if name not in before_mods and name.startswith("bdrive"):
            del sys.modules[name]


@pytest.fixture()
def tmpbase(tmp_path):
    d = tmp_path / "base"
    d.mkdir()
    return str(d)


ME = pwd.getpwuid(os.getuid()).pw_name
MY_GROUP = grp.getgrgid(os.getgid()).gr_name

# ---------------------------------------------------------------------------
# socket_dir_for: the directory is the bind unit (#169 req 1)
# ---------------------------------------------------------------------------


def test_socket_dir_for_derives_directory():
    assert S.socket_dir_for("/run/bdrive/bdrive.sock") == "/run/bdrive"


def test_socket_dir_for_rejects_relative():
    with pytest.raises(S.SocketDirError):
        S.socket_dir_for("relative/bdrive.sock")


def test_config_socket_dir_derived():
    cfg = C.load_config(env={})
    assert cfg.socket_dir == "/run/bdrive"
    cfg2 = C.load_config(env={"BDRIVE_SOCKET": "/tmp/x/b.sock"})
    assert cfg2.socket_dir == "/tmp/x"


# ---------------------------------------------------------------------------
# client_uids: exact uids, never a range (#169 req 3)
# ---------------------------------------------------------------------------


def test_config_client_uids_default_empty():
    cfg = C.load_config(env={})
    assert cfg.client_uids == frozenset()


def test_config_client_uids_parsed():
    cfg = C.load_config(env={"BDRIVE_CLIENT_UIDS": "2000001, 2000002"})
    assert cfg.client_uids == frozenset({2000001, 2000002})


def test_config_client_uids_rejects_garbage():
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_CLIENT_UIDS": "2000001-2000002"})
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_CLIENT_UIDS": "abc"})
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_CLIENT_UIDS": "-1"})


def test_serve_preflight_refuses_empty_uids():
    cfg = C.load_config(env={})
    with pytest.raises(S.SocketDirError):
        S.serve_preflight(cfg)


# ---------------------------------------------------------------------------
# prepare_socket_dir / check_socket_dir (#169 reqs 1, 5, 6)
# ---------------------------------------------------------------------------


def test_prepare_creates_dir_0710(tmp_path):
    sock = str(tmp_path / "run" / "bdrive" / "bdrive.sock")
    got = S.prepare_socket_dir(sock, ME, MY_GROUP)
    st = os.stat(os.path.dirname(sock))
    assert got == os.path.dirname(sock)
    assert stat.S_IMODE(st.st_mode) == 0o710
    assert st.st_uid == os.getuid()
    assert st.st_gid == os.getgid()


def test_prepare_hardens_existing_socket(tmp_path):
    d = tmp_path / "bdrive"
    d.mkdir()
    sock = str(d / "bdrive.sock")
    s = socket.socket(socket.AF_UNIX)
    try:
        s.bind(sock)
        S.prepare_socket_dir(sock, ME, MY_GROUP)
        st = os.stat(sock)
        assert stat.S_IMODE(st.st_mode) == 0o770
    finally:
        s.close()


def test_check_socket_dir_allows_empty_and_socket_only(tmp_path):
    d = str(tmp_path)
    S.check_socket_dir(d, "bdrive.sock")  # empty: daemon recreates it
    (tmp_path / "bdrive.sock").touch()
    S.check_socket_dir(d, "bdrive.sock")  # exactly the socket: fine


def test_check_socket_dir_fails_closed_on_stray_entries(tmp_path):
    (tmp_path / "daemon.pid").touch()
    with pytest.raises(S.SocketDirError):
        S.check_socket_dir(str(tmp_path), "bdrive.sock")


def test_prepare_fails_closed_on_stray_entries(tmp_path):
    d = tmp_path / "bdrive"
    d.mkdir()
    (d / "daemon.log").touch()
    with pytest.raises(S.SocketDirError):
        S.prepare_socket_dir(str(d / "bdrive.sock"), ME, MY_GROUP)


def test_prepare_rejects_unknown_user(tmp_path):
    with pytest.raises(S.SocketDirError):
        S.prepare_socket_dir(str(tmp_path / "b.sock"),
                             "no-such-user-xyz", MY_GROUP)


def test_prepare_rejects_unknown_group(tmp_path):
    with pytest.raises(S.SocketDirError):
        S.prepare_socket_dir(str(tmp_path / "b.sock"), ME,
                             "no-such-group-xyz")


# ---------------------------------------------------------------------------
# peer_uid_ok: SO_PEERCRED exact-uid match (#169 req 3)
# ---------------------------------------------------------------------------


def _pair():
    a, b = socket.socketpair(socket.AF_UNIX)
    return a, b


def test_peer_uid_ok_accepts_exact_uid():
    a, b = _pair()
    try:
        assert S.peer_uid_ok(a, frozenset({os.getuid()})) is True
    finally:
        a.close()
        b.close()


def test_peer_uid_ok_rejects_wrong_uid():
    a, b = _pair()
    try:
        assert S.peer_uid_ok(a, frozenset({os.getuid() + 1})) is False
    finally:
        a.close()
        b.close()


def test_peer_uid_ok_rejects_range_member():
    # A range check would admit jail root; the helper never matches
    # ranges — only exact membership.
    a, b = _pair()
    try:
        assert S.peer_uid_ok(a, frozenset({2000000, 2000001})) is False
    finally:
        a.close()
        b.close()


def test_peer_uid_ok_empty_allowed_is_deny():
    a, b = _pair()
    try:
        assert S.peer_uid_ok(a, frozenset()) is False
    finally:
        a.close()
        b.close()


def test_peer_uid_ok_closed_socket_is_deny():
    a, b = _pair()
    a.close()
    try:
        assert S.peer_uid_ok(a, frozenset({os.getuid()})) is False
    finally:
        b.close()


# ---------------------------------------------------------------------------
# resolve_within / create_within: dirfd pinning + O_NOFOLLOW (#169 req 4)
# ---------------------------------------------------------------------------


def test_resolve_within_resolves_real_file(tmpbase):
    sub = os.path.join(tmpbase, "sub")
    os.mkdir(sub)
    target = os.path.join(sub, "f.txt")
    with open(target, "w") as f:
        f.write("x")
    assert S.resolve_within(tmpbase, os.path.join("sub", "f.txt")) == target


def test_resolve_within_rejects_dotdot(tmpbase):
    with pytest.raises(S.PathTraversalError):
        S.resolve_within(tmpbase, "../etc/passwd")
    with pytest.raises(S.PathTraversalError):
        S.resolve_within(tmpbase, "sub/../../etc/passwd")


def test_resolve_within_rejects_absolute(tmpbase):
    with pytest.raises(S.PathTraversalError):
        S.resolve_within(tmpbase, "/etc/passwd")


def test_resolve_within_rejects_symlink_in_chain(tmpbase):
    real = os.path.join(tmpbase, "real")
    os.mkdir(real)
    os.symlink(real, os.path.join(tmpbase, "link"))
    with open(os.path.join(real, "f.txt"), "w") as f:
        f.write("x")
    with pytest.raises(S.PathTraversalError):
        S.resolve_within(tmpbase, os.path.join("link", "f.txt"))


def test_resolve_within_rejects_symlink_target(tmpbase):
    outside = os.path.join(tmpbase, "outside.txt")
    with open(outside, "w") as f:
        f.write("secret")
    os.symlink(outside, os.path.join(tmpbase, "evil.txt"))
    with pytest.raises(S.PathTraversalError):
        S.resolve_within(tmpbase, "evil.txt")


def test_resolve_within_symlink_swap_race(tmpbase):
    # The classic TOCTOU: check-then-open is replaced by a single
    # O_NOFOLLOW open under the pinned parent, so a symlink swapped in
    # after validation is still refused.
    sub = os.path.join(tmpbase, "sub")
    os.mkdir(sub)
    target = os.path.join(sub, "f.txt")
    with open(target, "w") as f:
        f.write("x")
    assert S.resolve_within(tmpbase, os.path.join("sub", "f.txt")) == target
    os.unlink(target)
    os.symlink(os.path.join(tmpbase, "nowhere"), target)
    with pytest.raises(S.PathTraversalError):
        S.resolve_within(tmpbase, os.path.join("sub", "f.txt"))


def test_create_within_creates_race_free(tmpbase):
    fd = S.create_within(tmpbase, "new.txt")
    try:
        os.write(fd, b"hello")
    finally:
        os.close(fd)
    with open(os.path.join(tmpbase, "new.txt")) as f:
        assert f.read() == "hello"


def test_create_within_refuses_existing_symlink(tmpbase):
    # O_EXCL fires on the symlink name itself (EEXIST) without ever
    # following it — the attack is defeated; per the error taxonomy it
    # surfaces as an ordinary collision, not the attack type.
    outside = os.path.join(tmpbase, "outside.txt")
    with open(outside, "w") as f:
        f.write("secret")
    os.symlink(outside, os.path.join(tmpbase, "evil.txt"))
    with pytest.raises(S.SocketDirError) as ei:
        S.create_within(tmpbase, "evil.txt")
    assert not isinstance(ei.value, S.PathTraversalError)
    # The target outside the base was not clobbered.
    with open(outside) as f:
        assert f.read() == "secret"


def test_create_within_refuses_dotdot(tmpbase):
    with pytest.raises(S.PathTraversalError):
        S.create_within(tmpbase, "../escape.txt")


def test_create_within_refuses_nul(tmpbase):
    with pytest.raises(S.PathTraversalError):
        S.create_within(tmpbase, "a\x00b")


# ---------------------------------------------------------------------------
# Round-1 review findings (blockers 1-4 + non-blocking gaps)
# ---------------------------------------------------------------------------


def test_socket_dir_for_rejects_degenerate_paths():
    with pytest.raises(S.SocketDirError):
        S.socket_dir_for("/")
    with pytest.raises(S.SocketDirError):
        S.socket_dir_for("/bdrive.sock")
    with pytest.raises(S.SocketDirError):
        S.socket_dir_for("//")


def test_config_socket_dir_rejects_degenerate():
    cfg = C.load_config(env={"BDRIVE_SOCKET": "/"})
    with pytest.raises(S.SocketDirError):
        cfg.socket_dir


def test_check_socket_dir_rejects_symlink_named_as_socket(tmp_path):
    # The symlink's target lives OUTSIDE the checked dir, so the only
    # possible failure is the symlink check itself — not the
    # unexpected-entries check.
    outside_base = tmp_path / "outside_base"
    outside_base.mkdir()
    target = outside_base / "target"
    target.mkdir()
    sockdir = tmp_path / "sockdir"
    sockdir.mkdir()
    os.symlink(str(target), str(sockdir / "bdrive.sock"))
    with pytest.raises(S.SocketDirError) as ei:
        S.check_socket_dir(str(sockdir), "bdrive.sock")
    assert "symlink" in str(ei.value)


def test_prepare_refuses_symlinked_socket_dir(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    os.chmod(str(real), 0o755)
    link = tmp_path / "link"
    os.symlink(str(real), str(link))
    with pytest.raises(S.SocketDirError):
        S.prepare_socket_dir(str(link / "bdrive.sock"), ME, MY_GROUP)
    # The real dir was not hardened through the link: mode untouched.
    st = os.stat(str(real))
    assert stat.S_IMODE(st.st_mode) == 0o755


def test_resolve_within_rejects_symlinked_base(tmpbase):
    real = os.path.join(tmpbase, "real")
    os.mkdir(real)
    with open(os.path.join(real, "f.txt"), "w") as f:
        f.write("x")
    link = os.path.join(tmpbase, "link")
    os.symlink(real, link)
    with pytest.raises(S.PathTraversalError):
        S.resolve_within(link, "f.txt")


def test_create_within_rejects_symlinked_base(tmpbase):
    real = os.path.join(tmpbase, "real")
    os.mkdir(real)
    link = os.path.join(tmpbase, "link")
    os.symlink(real, link)
    with pytest.raises(S.PathTraversalError):
        S.create_within(link, "f.txt")


def test_create_within_eexist_is_not_attack_type(tmpbase):
    with open(os.path.join(tmpbase, "exists.txt"), "w") as f:
        f.write("x")
    with pytest.raises(S.SocketDirError) as ei:
        S.create_within(tmpbase, "exists.txt")
    assert not isinstance(ei.value, S.PathTraversalError)
    assert "already exists" in str(ei.value)


def test_config_client_uids_rejects_unicode_digits():
    # "\u00b2".isdigit() is True but int() raises — must surface as
    # ConfigError, never escape the fail-loud contract.
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_CLIENT_UIDS": "²"})
    with pytest.raises(C.ConfigError):
        C.load_config(env={"BDRIVE_CLIENT_UIDS": "2000001, -5"})


def test_harden_socket_file_sets_group_and_mode(tmp_path):
    # Fresh bind(): the inode is born with the ambient uid:gid and a
    # umask-derived mode. Harden it to a WRONG state first so the test
    # proves harden_socket_file() actually changes the file (under the
    # ambient umask 0007 a fresh bind is already 0770, which would make
    # the mode assertion vacuous). The gid half runs wherever the
    # process may chown to another group (root, or a second group
    # membership); the mode half runs everywhere.
    if os.geteuid() == 0:
        other_gid = grp.getgrnam("nogroup").gr_gid
    else:
        others = [g for g in os.getgroups() if g != os.getgid()]
        other_gid = others[0] if others else None
    d = tmp_path / "bdrive"
    d.mkdir()
    sock = str(d / "bdrive.sock")
    s = socket.socket(socket.AF_UNIX)
    try:
        s.bind(sock)
        if other_gid is not None and other_gid != os.getgid():
            os.chown(sock, os.getuid(), other_gid)
        os.chmod(sock, 0o755)
        st = os.stat(sock)
        assert stat.S_IMODE(st.st_mode) == 0o755
        if other_gid is not None and other_gid != os.getgid():
            assert st.st_gid == other_gid
        S.harden_socket_file(sock, ME, MY_GROUP)
        st = os.stat(sock)
        assert stat.S_IMODE(st.st_mode) == 0o770
        assert st.st_uid == os.getuid()
        assert st.st_gid == os.getgid()
    finally:
        s.close()


def test_harden_socket_file_rejects_unknown_user(tmp_path):
    d = tmp_path / "bdrive"
    d.mkdir()
    sock = str(d / "bdrive.sock")
    s = socket.socket(socket.AF_UNIX)
    try:
        s.bind(sock)
        with pytest.raises(S.SocketDirError):
            S.harden_socket_file(sock, "no-such-user-xyz", MY_GROUP)
    finally:
        s.close()
