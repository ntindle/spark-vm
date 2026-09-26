"""Tests for scripts/bounded_http.py (issue #471) and the daemons' adoption.

Run from the repo root:  python3 -m pytest scripts/test_bounded_http.py -q

Style mirrors confirm/test_confirmd.py's M8ServerHardeningTests (issue
#77 M8): socketpair-based, polling for thread completion, no mock
theater — the pool discipline is exercised through the real
process_request/process_request_thread paths.
"""

import importlib.util
import os
import socket
import socketserver
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bounded_http  # noqa: E402
from bounded_http import BoundedThreadingHTTPServer  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _SmallPool(BoundedThreadingHTTPServer):
    """Per-daemon tuning mechanism: max_threads is a subclass attribute."""

    max_threads = 2


class _TinyPool(BoundedThreadingHTTPServer):
    max_threads = 1


class BoundedHttpTests(unittest.TestCase):
    """The shared helper's pool discipline, on its own terms."""

    def _make_server(self, cls=_SmallPool):
        srv = cls(("127.0.0.1", 0), socketserver.BaseRequestHandler)
        self.addCleanup(srv.server_close)
        return srv

    def test_defaults(self):
        """Sane out-of-the-box numbers: 64 threads, 10s handshake timeout."""
        self.assertEqual(BoundedThreadingHTTPServer.max_threads, 64)
        self.assertEqual(BoundedThreadingHTTPServer.socket_timeout, 10)

    def test_over_cap_connection_closed_not_queued(self):
        """When the pool is full the connection is closed immediately —
        fail closed, not queued unboundedly."""
        srv = self._make_server(_TinyPool)
        srv._slots.acquire()  # drain the single slot
        client, accepted = socket.socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        threads_before = threading.active_count()
        with mock.patch.object(srv, "handle_error"):
            srv.process_request(accepted, ("127.0.0.1", 0))
        time.sleep(0.2)
        self.assertEqual(threading.active_count(), threads_before)
        self.assertEqual(accepted.fileno(), -1)
        srv._slots.release()  # restore for cleanup

    def test_slot_released_after_request(self):
        """A completed request returns its pool slot."""
        srv = self._make_server()
        calls = []

        def fake_finish(request, client_address):
            calls.append(1)

        with mock.patch.object(srv, "finish_request", fake_finish), \
             mock.patch.object(srv, "handle_error"):
            client, accepted = socket.socketpair()
            self.addCleanup(client.close)
            srv.process_request(accepted, ("127.0.0.1", 0))
            for _ in range(100):
                if calls:
                    break
                time.sleep(0.02)
        self.assertEqual(len(calls), 1)
        for _ in range(100):
            if srv._slots._value == 2:
                break
            time.sleep(0.02)
        else:
            self.fail("handler thread never released its pool slot")
        self.assertTrue(srv._slots.acquire(blocking=False))
        self.assertTrue(srv._slots.acquire(blocking=False))
        self.assertFalse(srv._slots.acquire(blocking=False))
        srv._slots.release()
        srv._slots.release()

    def test_thread_start_failure_releases_slot(self):
        """A thread-creation failure must not permanently drain the pool —
        otherwise the mitigation itself turns a transient resource crunch
        into a hard outage."""
        srv = self._make_server(_TinyPool)
        client, accepted = socket.socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        with mock.patch("threading.Thread",
                        side_effect=RuntimeError("can't start new thread")), \
             mock.patch.object(srv, "handle_error"):
            srv.process_request(accepted, ("127.0.0.1", 0))
        self.assertTrue(srv._slots.acquire(blocking=False))
        srv._slots.release()
        self.assertEqual(accepted.fileno(), -1)

    def test_failed_start_never_parks_dead_thread(self):
        """B1 convergence (from PR #469's Architecture review):
        ThreadingMixIn registers the new thread in _threads BEFORE
        start(). If start() raises, the dead thread must not break a
        later server_close() with RuntimeError. Daemon threads (this
        server's default) are never tracked, so pin the property with
        daemon_threads=False — the only configuration where
        registration happens at all."""
        srv = self._make_server(_TinyPool)
        srv.daemon_threads = False  # force _threads registration
        real_thread = threading.Thread

        def boom(*a, **k):
            th = real_thread(*a, **k)
            def fail():
                raise RuntimeError("can't start new thread")
            th.start = fail
            return th

        client, accepted = socket.socketpair()
        self.addCleanup(client.close)
        with mock.patch("threading.Thread", boom), \
             mock.patch.object(srv, "handle_error"):
            srv.process_request(accepted, ("127.0.0.1", 0))
        # server_close must stay clean despite the never-started thread.
        srv.server_close()
        self.assertTrue(srv._slots.acquire(blocking=False))
        srv._slots.release()

    def test_slot_released_when_shutdown_request_raises(self):
        """A raise in shutdown_request must not permanently burn a pool
        slot — the mitigation must not become the DoS. The raise still
        surfaces on the handler thread; only the slot release is
        guaranteed."""
        srv = self._make_server(_TinyPool)
        client, accepted = socket.socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        seen = []
        old_hook = threading.excepthook
        threading.excepthook = lambda args: seen.append(args.exc_value)
        self.addCleanup(setattr, threading, "excepthook", old_hook)
        with mock.patch.object(srv, "finish_request", lambda r, a: None), \
             mock.patch.object(srv, "shutdown_request",
                               side_effect=RuntimeError("boom")):
            srv.process_request(accepted, ("127.0.0.1", 0))
            for _ in range(100):
                if srv._slots._value == 1:
                    break
                time.sleep(0.02)
            else:
                self.fail("pool slot was not released when shutdown_request "
                          "raised")
        for _ in range(100):
            if seen:
                break
            time.sleep(0.02)
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], RuntimeError)
        self.assertTrue(srv._slots.acquire(blocking=False))
        srv._slots.release()

    def test_handler_threads_registered_for_block_on_close(self):
        """process_request preserves ThreadingMixIn's lifecycle
        bookkeeping: with block_on_close, handler threads land in
        srv._threads so server_close() waits for them."""
        srv = self._make_server()
        srv.daemon_threads = False  # _Threads only tracks non-daemon threads
        self.assertTrue(srv.block_on_close)
        started = threading.Event()
        release = threading.Event()

        def fake_finish(request, client_address):
            started.set()
            release.wait(10)

        with mock.patch.object(srv, "finish_request", fake_finish):
            client, accepted = socket.socketpair()
            self.addCleanup(client.close)
            self.addCleanup(accepted.close)
            srv.process_request(accepted, ("127.0.0.1", 0))
            self.assertTrue(started.wait(5), "handler thread never started")
            for _ in range(100):
                if any(t.is_alive() for t in srv._threads):
                    break
                time.sleep(0.05)
            else:
                self.fail("handler thread was not registered in srv._threads")
            release.set()

    def test_plain_request_skips_handshake(self):
        """A non-TLS request has no do_handshake — the handshake step is
        skipped and the request is finished normally."""
        srv = self._make_server(_TinyPool)
        client, accepted = socket.socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        finished = []
        with mock.patch.object(srv, "finish_request",
                               lambda r, a: finished.append(r)), \
             mock.patch.object(srv, "shutdown_request",
                               lambda r: accepted.close()):
            srv.process_request_thread(accepted, ("127.0.0.1", 0))
        self.assertEqual(finished, [accepted])

    def test_tls_like_request_gets_handshake_with_timeout(self):
        """A request carrying do_handshake (deferred TLS) gets the socket
        timeout applied BEFORE the handshake runs — the ordering is the
        whole point of the deferral."""
        srv = self._make_server(_TinyPool)
        events = []

        class FakeTLSRequest:
            def settimeout(self, t):
                events.append(("settimeout", t))

            def do_handshake(self):
                events.append(("do_handshake",))

        req = FakeTLSRequest()
        finished = []
        with mock.patch.object(srv, "finish_request",
                               lambda r, a: finished.append(r)), \
             mock.patch.object(srv, "shutdown_request", lambda r: None):
            srv.process_request_thread(req, ("127.0.0.1", 0))
        self.assertEqual(events, [("settimeout", srv.socket_timeout),
                                  ("do_handshake",)])
        self.assertEqual(finished, [req])

    def test_handshake_timeout_prefers_handler_class(self):
        """The pre-handshake timeout is read off the configured handler
        class — the same attribute StreamRequestHandler.setup() honors —
        never a module global (Architecture review B2). A handler
        without the attribute falls back to socket_timeout."""

        class TimeoutHandler(socketserver.BaseRequestHandler):
            timeout = 7

        class PlainHandler(socketserver.BaseRequestHandler):
            pass

        def run_case(handler_cls, expected):
            srv = BoundedThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
            self.addCleanup(srv.server_close)
            events = []

            class FakeTLSRequest:
                def settimeout(self, t):
                    events.append(("settimeout", t))

                def do_handshake(self):
                    events.append(("do_handshake",))

            req = FakeTLSRequest()
            with mock.patch.object(srv, "finish_request",
                                   lambda r, a: None), \
                 mock.patch.object(srv, "shutdown_request", lambda r: None):
                srv.process_request_thread(req, ("127.0.0.1", 0))
            self.assertEqual(events, [("settimeout", expected),
                                      ("do_handshake",)])

        run_case(TimeoutHandler, 7)
        run_case(PlainHandler, BoundedThreadingHTTPServer.socket_timeout)

    def test_stalled_handshake_releases_slot(self):
        """A handshake that raises (stalled peer, cut off by the socket
        timeout) still releases its pool slot via handle_error + finally."""
        srv = self._make_server(_TinyPool)

        class StalledTLSRequest:
            def settimeout(self, t):
                pass

            def do_handshake(self):
                raise socket.timeout("timed out")

        req = StalledTLSRequest()
        errors = []
        with mock.patch.object(srv, "handle_error",
                               lambda r, a: errors.append((r, a))), \
             mock.patch.object(srv, "shutdown_request", lambda r: None):
            # Drive the thread path directly with a drained slot (the
            # slot discipline is what matters here).
            srv._slots.acquire()
            srv.process_request_thread(req, ("127.0.0.1", 0))
        self.assertEqual(len(errors), 1)
        self.assertTrue(srv._slots.acquire(blocking=False))
        srv._slots.release()


class DaemonAdoptionTests(unittest.TestCase):
    """cred-ui and waitlistd actually use the shared helper (issue #471)."""

    @classmethod
    def setUpClass(cls):
        repo = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), ".."))
        cls.cred_ui = _load("cred_ui_471",
                            os.path.join(repo, "cred-ui", "cred-ui.py"))
        cls.waitlistd = _load("waitlistd_471",
                              os.path.join(repo, "site", "waitlistd.py"))

    def test_cred_ui_uses_shared_bounded_server(self):
        """cred-ui's main() constructs the shared bounded server, not the
        bare ThreadingHTTPServer."""
        import inspect
        self.assertIs(self.cred_ui.BoundedThreadingHTTPServer,
                      bounded_http.BoundedThreadingHTTPServer)
        src = inspect.getsource(self.cred_ui.main)
        self.assertIn("BoundedThreadingHTTPServer((BIND, PORT), Handler)", src)
        self.assertNotIn("srv = ThreadingHTTPServer((BIND, PORT), Handler)",
                         src)

    def test_cred_ui_keeps_socket_timeout(self):
        """cred-ui already had Handler.timeout = 10 (issue #282) — the
        pool bound is the new half, and it must not have regressed."""
        self.assertEqual(self.cred_ui.Handler.timeout, 10)

    def test_waitlistd_uses_shared_bounded_server(self):
        """waitlistd's main() constructs the shared bounded server."""
        import inspect
        self.assertIs(self.waitlistd.BoundedThreadingHTTPServer,
                      bounded_http.BoundedThreadingHTTPServer)
        src = inspect.getsource(self.waitlistd.main)
        self.assertIn("BoundedThreadingHTTPServer((bind, port), _Handler)",
                      src)
        self.assertNotIn("httpd = ThreadingHTTPServer((bind, port), _Handler)",
                         src)

    def test_waitlistd_gains_socket_timeout(self):
        """waitlistd had NO socket timeout before #471 — a stalled
        headers/body read pinned a handler thread forever. Now bounded
        like its siblings."""
        self.assertEqual(self.waitlistd._Handler.timeout, 10)

    def test_waitlistd_live_smoke_on_bounded_server(self):
        """waitlistd's handler actually serves through the bounded server
        (a real request against an ephemeral port)."""
        import http.client
        import tempfile
        tmp = tempfile.mkdtemp(prefix="waitlistd-471-")
        svc = self.waitlistd.WaitlistService(
            tmp, "00" * 32, "https://waitlist.example.invalid")
        self.waitlistd._Handler.service = svc
        self.addCleanup(setattr, self.waitlistd._Handler, "service", None)
        httpd = self.waitlistd.BoundedThreadingHTTPServer(
            ("127.0.0.1", 0), self.waitlistd._Handler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        self.addCleanup(httpd.shutdown)
        self.addCleanup(httpd.server_close)
        port = httpd.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        self.addCleanup(conn.close)
        conn.request("GET", "/waitlist/form")
        resp = conn.getresponse()
        self.assertIn(resp.status, (200, 302, 404))
        resp.read()


if __name__ == "__main__":
    unittest.main()
