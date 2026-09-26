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

`_threads` lifecycle bookkeeping mirrors `ThreadingMixIn` exactly so
`server_close()` still honors `block_on_close`. The stdlib keeps that
registry in the private `socketserver._Threads`; this module imports it
under a comment for the same reason confirmd did before the promotion:
it is the exact thread-lifecycle contract this class preserves.

Pairing: each daemon's `Handler` sets its own `timeout` (the per-read
idle bound `StreamRequestHandler.setup()` applies to the accepted
socket). Keep `socket_timeout` equal to that number — one bound to
reason about. Neither is cumulative: a peer dripping >=1 byte per
timeout of headers/body can still pin a slot; 64 such peers saturate
the pool and shedding stays fail closed (connection dropped, state
stays file-backed so a retry succeeds). A cumulative per-connection
deadline is the long-term answer (issue #472).

stdlib only.
"""

import threading
from http.server import ThreadingHTTPServer

# socketserver-private, but this is the exact ThreadingMixIn
# thread-lifecycle contract BoundedThreadingHTTPServer preserves below.
from socketserver import _Threads


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    # Capacity model (confirmd's, kept as the default): confirmd's client
    # classes are the owner's browser and the agent proxy — expected peak
    # ~4 concurrent requests, so 64 threads is ~16x headroom. cred-ui
    # (localhost-only UI) and waitlistd (config-bound listener) share the
    # default; override per daemon with a subclass attribute if a
    # different ceiling is ever warranted.
    max_threads = 64

    # Socket timeout applied to the connection before a deferred TLS
    # handshake runs (process_request_thread). Keep equal to the
    # daemon's Handler.timeout (the per-read idle bound
    # StreamRequestHandler.setup() applies to the same socket).
    socket_timeout = 10

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._slots = threading.Semaphore(self.max_threads)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.close_request(request)
            return
        try:
            t = threading.Thread(
                target=self.process_request_thread,
                args=(request, client_address))
            t.daemon = self.daemon_threads
            t.start()
            if self.block_on_close:
                # Preserve ThreadingMixIn's thread-lifecycle contract: the
                # stock process_request registers the thread so
                # server_close honors block_on_close. Registered after
                # start() so a failed start never parks a dead thread in
                # the join list.
                vars(self).setdefault("_threads", _Threads())
                self._threads.append(t)
        except Exception:
            # Thread creation can fail under the same resource exhaustion
            # this pool guards against — log it, release the slot, and
            # close the request so a transient crunch can't drain the pool
            # permanently.
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
                request.settimeout(self.socket_timeout)
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
