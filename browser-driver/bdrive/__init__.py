"""bdrive — the fixed browser-driving service for spark-vm.

``bdrive`` is the *hands* in ``browser-driver/SPEC.md``: it moves the
mouse and types keys per a fixed, narrow action protocol. It has no
judgment and no browsing logic; the on-box agent (``obox``, a later
slice) does the deciding.

This package currently holds the transport-agnostic protocol layer
(SPEC §4–§5): action vocabulary, request validation, receipt semantics,
``ref_scope`` lifecycle, and the observation schema. It knows nothing
about Playwright, sockets, or the box — the execution backend and the
unix-socket daemon are the next slices (see ``browser-driver/README.md``).

``bdrive.socket_dir`` pins the daemon-side socket-directory hardening
for the planned jail bind-mount (GitHub #169): the socket's directory
as the bind unit, ``SO_PEERCRED`` exact-uid peer checks, 0710/0770
directory/socket discipline, fail-closed directory hygiene, and
dirfd-pinned + ``O_NOFOLLOW`` daemon-side path resolution.
"""
