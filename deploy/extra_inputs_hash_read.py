#!/usr/bin/env python3
"""Atomic read for auto-deploy's extra-inputs digest (issues #302, #144, #299).

extra_inputs_hash() in auto-deploy.sh hashes host-side (non-repo) input
files declared as <component>_extra_paths in components.conf. Those paths
are swapd-writable, so the read must not trust the filesystem: it runs
through this helper with the same open discipline as
proxy/privileged_read.py --

  os.open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK) + fstat before read

which closes both holes the old shell check-then-read had:

* symlink/FIFO swap between the `[ -L ]`/`[ -f ]` test and the `head`
  open: the refusal is part of the open itself (ELOOP), so there is no
  check-to-read window for a swapd-level writer to win;
* planted FIFO: O_NONBLOCK means the open cannot hang the tick while it
  holds the single-flight lock; the fstat gate then refuses it.

A hardlink is refused too (nlink > 1): a hardlink IS a regular file, so
the symlink gate does not stop it, and build_ca_bundle.py fail-closes on
hardlinks (issue #299) -- hashing one as content would record a digest
that can never converge on a successful deploy.

The helper is invoked via the script's sudo_run wrapper, so it reads at
the same privilege every other consumer of the path uses. That collapses
the old readability states to missing / non-regular / content: a
chmod-toggle by swapd can no longer flip the digest without changing the
bytes that the deploy path would actually read.

Protocol: one line on stdout, always; the exit status is always 0.
A read failure must never abort the deploy tick -- it just hashes as a
distinct state. stderr is left alone for tracebacks (the path is not
secret); stdout carries only the digest material.

  missing      -- path absent (or raced away before the open)
  nonregular   -- symlink (ELOOP), FIFO, directory, socket, hardlink
  unreadable   -- any other read error (EACCES, EIO, ...)
  <64 hex>     -- sha256 of (fstat size, bytes actually read, capped prefix)
                 for a regular file; the size + read-count are folded in so
                 growth past the cap still flips the digest

Only the first <cap> bytes are read into memory; the cap arrives as
argv[2] from the shell's EXTRA_INPUTS_HASH_MAX_BYTES, so the two stay
single-sourced at the call site.
"""
import errno
import hashlib
import os
import stat
import sys


def _emit(line):
    sys.stdout.write(line + "\n")


def main(argv):
    path = argv[1]
    cap = int(argv[2])
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        # Absent, or raced away before the open -- a legitimate state.
        _emit("missing")
        return 0
    except OSError as e:
        # ELOOP: symlink (live or dangling) -- refused by the open itself.
        _emit("nonregular" if e.errno == errno.ELOOP else "unreadable")
        return 0
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink > 1:
            _emit("nonregular")
            return 0
        with os.fdopen(fd, "rb") as f:
            data = f.read(cap + 1)
    except OSError:
        _emit("unreadable")
        return 0
    n = len(data)
    material = b"%d\n%d\n" % (st.st_size, n) + data[:cap]
    _emit(hashlib.sha256(material).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
