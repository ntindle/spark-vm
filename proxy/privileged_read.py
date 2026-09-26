#!/usr/bin/env python3
"""One open discipline for privileged reads (issues #144/#299/#300/#372).

Extracted from proxy/build_ca_bundle.py::_privileged_read (#372) and now
shared: safe_install.py routes its --src read through it (issue #413), so
the privileged-read family converges on one open discipline instead of
accumulating per-path hardening.

The discipline, atomically at open time:

- ``os.open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK)``: a symlink at the
  path fails with ELOOP instead of being read through (issue #144). A
  dangling symlink also fails -- that is a broken/attacked deploy, not a
  first deploy, so it fails closed rather than skipping silently.
- ``os.fstat`` the raw fd before the first read: non-regular files (FIFO,
  directory, ...) are refused (issue #144); a planted FIFO would otherwise
  block the privileged read forever, so the open is O_NONBLOCK and the
  fstat happens before fdopen.
- ``st.st_nlink > 1`` is refused: a hardlink IS a regular file, so
  O_NOFOLLOW + S_ISREG do not stop it -- an attacker could hardlink a
  root-readable file into the read path. Refuse independent of the
  fs.protected_hardlinks sysctl (issue #299).
- The read is capped at ``max_bytes`` (issue #300): the privileged
  process never reads an unbounded input, so growth after the stat check
  (a racing writer appending) cannot exceed the cap either.

``on_missing`` is a zero-arg callable invoked when the path is absent; it
must raise SystemExit -- the swapd CA passes its loud first-deploy skip;
--sys passes a fail-closed refusal (a missing system bundle is not a
first-deploy state). A non-raising on_missing is a caller bug: fail closed
explicitly rather than falling through to an unbound-fd NameError.
"""
import errno
import os
import stat
import sys

# Default read cap: 1 MiB. The CA-bundle use is ~200 KiB; the safe_install
# --src use (deploy inputs: allow/deny lists, sudoers fragments) is
# smaller. Callers with a different bound pass max_bytes explicitly.
DEFAULT_MAX_BYTES = 1 << 20


def _fail(msg):
    sys.stderr.write("privileged_read: refusing: %s\n" % msg)
    raise SystemExit(2)


def privileged_read(path, on_missing, max_bytes=DEFAULT_MAX_BYTES):
    """Read path as a privileged process, refusing hostile inputs.

    See the module docstring for the full discipline. Returns bytes.
    Raises SystemExit(2) on refusal, or whatever on_missing raises on a
    missing path.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        on_missing()  # raises SystemExit -- raced away between check and open
        # A non-raising on_missing is a caller bug: fail closed explicitly
        # rather than falling through to an unbound-fd NameError.
        raise SystemExit(1)  # unreachable by contract
    except OSError as e:
        if e.errno == errno.ELOOP:
            _fail("%s is a symlink -- refusing to read through it "
                  "(issue #144)" % path)
        raise
    # fstat the raw fd before fdopen: fdopen on a directory raises
    # IsADirectoryError, and a FIFO open would block without O_NONBLOCK.
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        _fail("%s is not a regular file -- refusing to read it "
              "(issue #144)" % path)
    if st.st_nlink > 1:
        # A hardlink IS a regular file, so O_NOFOLLOW + S_ISREG do not stop
        # it: an attacker could hardlink a root-readable file into the read
        # path. Refuse independent of the fs.protected_hardlinks sysctl
        # (issue #299).
        os.close(fd)
        _fail("%s is a hardlink (nlink=%d) -- refusing to read it "
              "(issue #299)" % (path, st.st_nlink))
    with os.fdopen(fd, "rb") as f:
        data = f.read(max_bytes + 1)
    if len(data) > max_bytes:
        _fail("%s is %d bytes (cap %d) -- refusing to read it into a "
              "privileged process (issue #300)"
              % (path, len(data), max_bytes))
    return data
