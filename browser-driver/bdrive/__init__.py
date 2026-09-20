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
"""
