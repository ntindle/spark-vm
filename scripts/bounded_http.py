"""Shared slow-loris-hardened HTTP server (issue #471).

`BoundedThreadingHTTPServer` is the bounded variant of
`http.server.ThreadingHTTPServer` used by spark-vm's HTTP daemons
(confirmd, cred-ui, waitlistd). `ThreadingHTTPServer` spawns one thread
per connection, so a peer that opens connections and never finishes
them grows the thread pool without bound; a peer that stalls the TLS
handshake pins the single `serve_forever` accept thread and starves
every client. This class closes both holes:

- the accept->thread fan-out is capped by a semaphore (`max_threads`
  in-flight handler threads); over-cap connections are closed
  immediately (fail closed), never queued.
- the TLS handshake never runs in the accept loop: daemons wrap their
  listening socket with `do_handshake_on_connect=False` and the
  handshake runs here, inside a bounded pool slot, cut off by
  `socket_timeout`.

The semaphore slot is released in `process_request_thread`'s `finally`
— even if `shutdown_request` raises — so the mitigation can never
become the DoS (a raise must not permanently burn one of the slots).
Thread-creation failure (the exhaustion case this pool guards against)
releases the slot, is logged via `handle_error`, and closes the
request, so a transient crunch can't drain the pool permanently.

`_threads` lifecycle bookkeeping is delegated to `ThreadingMixIn` (via
`super().process_request`) rather than copied — so future CPython
changes to the mixin propagate instead of silently diverging from a
forked body, and no socketserver-private import is needed.

Pairing: each daemon's `Handler` sets its own `timeout` (the per-read
idle bound `StreamRequestHandler.setup()` applies to the accepted
socket). The pre-handshake timeout below reads that same attribute off
the configured handler class — never a module global — so this server
stays reusable across daemons whose handlers are named differently
(`Handler`, `_Handler`, ...). A handler without the attribute falls
back to `socket_timeout`; the two agreeing means one number to reason
about. Neither is cumulative: a peer dripping >=1 byte per
timeout of headers/body can still pin a slot; 64 such peers saturate
the pool and shedding stays fail closed (connection dropped, state
stays file-backed so a retry succeeds). A cumulative per-connection
deadline is the long-term answer (issue #472).

stdlib only.
"""

import threading
from http.server import ThreadingHTTPServer


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    # Capacity model (confirmd's, kept as the default): confirmd's client
    # classes are the owner's browser and the agent proxy — expected peak
    # ~4 concurrent requests, so 64 threads is ~16x headroom. cred-ui
    # (localhost-only UI) and waitlistd (config-bound listener) share the
    # default. Per-daemon tuning is a SUBCLASS attribute
    # (`class _Server(BoundedThreadingHTTPServer): max_threads = 32`) —
    # assigning `srv.max_threads = N` after construction is a no-op (the
    # semaphore is sized in __init__).
    max_threads = 64

    # Socket-timeout fallback applied to the connection before a deferred
    # TLS handshake runs (process_request_thread). The handler class's
    # own `timeout` is preferred when present (same attribute
    # StreamRequestHandler.setup() honors); this is the backstop for
    # handlers that don't set one. Daemons keep both at 10.
    socket_timeout = 10

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._slots = threading.Semaphore(self.max_threads)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.close_request(request)
            return
        try:
            # Delegate thread creation, the daemon flag, and the
            # _threads/block_on_close lifecycle bookkeeping to
            # ThreadingMixIn — so future CPython changes to the mixin
            # propagate instead of silently diverging from a copied body.
            # self.process_request_thread below is still this class's
            # override (handshake deferral + slot release).
            super().process_request(request, client_address)
        except Exception:
            # Thread creation can fail under the same resource exhaustion
            # this pool guards against — log it, release the slot, and
            # close the request so a transient crunch can't drain the pool
            # permanently. Not re-raised: _handle_request_noblock would
            # log it a second time via handle_error.
            #
            # B1 convergence (from PR #469's Architecture review):
            # ThreadingMixIn.process_request registers the new thread in
            # _threads BEFORE start(). If start() itself raised, the dead
            # thread is now parked in the join list and a later
            # server_close() would raise RuntimeError joining a thread
            # that never started. Prune never-started entries here instead
            # (daemon threads — this server's default — are never
            # tracked, so this only matters for non-daemon
            # configurations; dropping already-finished threads is a
            # no-op since join would have returned immediately).
            threads = vars(self).get("_threads")
            if isinstance(threads, list):  # _Threads is a list subclass
                for t in list(threads):
                    if not t.is_alive():
                        try:
                            threads.remove(t)
                        except ValueError:
                            pass
            self.handle_error(request, client_address)
            self._slots.release()
            self.close_request(request)

    def process_request_thread(self, request, client_address):
        try:
            # The TLS handshake runs here, in the bounded handler thread
            # — never in the accept loop. Daemons wrap the listening
            # socket with do_handshake_on_connect=False, so a peer that
            # completes TCP and stalls the handshake burns one pool slot
            # (subject to fail-closed shedding) instead of pinning the
            # single serve_forever thread for every client. do_handshake()
            # honors the socket timeout, so a stalled handshake raises
            # socket.timeout and the slot is released below. Non-TLS
            # requests (plain-socket daemons like cred-ui and waitlistd)
            # have no do_handshake and skip this.
            do_handshake = getattr(request, "do_handshake", None)
            if do_handshake is not None:
                # Same attribute StreamRequestHandler.setup() honors, read
                # off the configured handler class — not a module global —
                # so this server stays reusable across daemons (#471).
                # An explicit None check (not `or`): a handler could set
                # timeout = 0 (non-blocking) and that must be honored.
                timeout = getattr(self.RequestHandlerClass, "timeout", None)
                request.settimeout(
                    timeout if timeout is not None else self.socket_timeout)
                do_handshake()
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            try:
                self.shutdown_request(request)
            finally:
                # Release the pool slot even if shutdown_request raises: a
                # raise here must never permanently burn one of the slots
                # (the mitigation must not become the DoS).
                self._slots.release()
