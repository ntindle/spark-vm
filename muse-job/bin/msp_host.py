#!/usr/bin/env python3
"""msp_host.py -- MSP (Muse Session Protocol) serve-host client.

Stdlib-only transport implementing issue #221, the foundation of the #228
muse-job v2 migration (drive jobs over MSP instead of scraping a tmux TUI).

One MSPHost spawns and owns a single `muse serve` process, speaks NDJSON
JSON-RPC 2.0 over its stdio, and runs the initialize/initialized handshake
(`initialize` with clientInfo, then the `initialized` notification -- the
step whose absence made post-handshake calls fail with `Not initialized`
in the 2026-09-17 investigation). On top of the transport it provides:

- JSON-RPC 2.0 request/response correlation by id (`call`),
- fire-and-forget notifications (`notify`),
- server->client notification dispatch to subscribers (`subscribe`),
- server->client request routing to handlers (`set_request_handler`,
  e.g. `approval/request`, `userInput/request`),
- schema-bundle fingerprint pinning that fails loud when the binary is
  upgraded under us (`schema_fingerprint` / `verify_schema_fingerprint`),
- reconnect semantics: the serve host is stateless w.r.t. jobs (sessions
  are durable server-side), so a dead host is re-spawned and re-handshaked
  (`reconnect`); subscriptions and request handlers survive the re-attach.

Message validation in this slice is structural: the JSON-RPC envelope is
checked (`jsonrpc == "2.0"`, sane id/method/params shapes) and malformed
frames are counted, never fatal to the reader. Full per-message validation
against the exported schema bundle is an explicit next slice on #221.

Security and trust
------------------
MSPHost is a pass-through transport: it performs NO redaction or
scrubbing. `call()` results (including `session/read` transcripts),
notification payloads, `ServerError.data`, `subscriber_errors` exception
arguments, and the `log_path` stderr file may all contain real secret
values. The serve binary runs with the operator's full privileges and is
fully trusted -- it sees every handler result and every transcript.
Callers must never log `call()` results or route them into agent-visible
paths; secret policy (`hsurr:<name>` placeholders, proxy-side swaps) is
enforced above this layer. `serve_argv` is trusted as given (executed
directly, never through a shell). `log_path` is opened with O_NOFOLLOW
(a symlink is refused, fail-closed, before the serve host spawns) and a
pre-existing regular file is tightened to mode 0o600, because serve
stderr can carry secrets -- creation mode alone does not protect a file
that already exists. Non-regular log targets (e.g. /dev/null) are left
as-is. Parent-directory races on `log_path` are outside the threat model
(same caveat as the rest of the on-box operator surface).

Threading: one reader thread owns stdout. `call` blocks on a condition;
subscriber callbacks and request handlers run ON the reader thread, so
they must be quick and non-blocking (hand expensive work to your own
thread/queue). A subscriber that raises does not kill the reader -- the
exception is recorded on `subscriber_errors` and the dispatch continues.
`call`/`notify`/`reconnect` raise MSPError when invoked from a callback
or handler: re-entrant dispatch would deadlock, so they fail loud.

Wire notes (verified 2026-09-21 against muse 1.3.0 on spark-vm, per #221):
transport is NDJSON over stdio; `clientInfo.name` must match
`^[a-z0-9_]+$`. The `initialize` params below carry only what #221
documents (clientInfo); if the binary demands more, its error response
says so and the params grow -- fail loud, don't guess.
"""

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import threading
import time

CLIENT_NAME_RE = re.compile(r"^[a-z0-9_]+$")

# Provenance for the schema pin (issue #221): `muse schema
# generate-json-schema` against muse 1.3.0 on spark-vm, 2026-09-21. The
# issue records only a truncated prefix, so no full value is pinned here;
# the pin is enforced through the `expected_schema_fingerprint` parameter,
# whose value is recorded from the deployment binary (see
# `export_schema`). Kept as documentation, not as an enforceable value.
SCHEMA_FINGERPRINT_VERIFIED_PREFIX = "sha256:7469c9e3"

_JSONRPC = "2.0"
# JSON-RPC reserved error codes we may synthesize client-side.
_ERR_METHOD_NOT_FOUND = -32601

# Largest NDJSON frame we will ever emit. Real protocol params are small
# dicts; a frame over this is a caller bug, and refusing it BEFORE taking
# the write lock keeps one giant params from parking _send (and everyone
# waiting on the write lock, including close()) on a wedged child.
_MAX_SEND_FRAME_BYTES = 4 * 1024 * 1024

# Sentinel returned by _read_frame when a single frame exceeds
# max_frame_bytes: the serve host is treated as wedged (fail loud).
_FRAME_OVERRUN = object()

# Set on the reader thread while it dispatches. call()/notify()/
# reconnect() refuse to run there: re-entrant dispatch would deadlock --
# the response the re-entrant call waits for can only be dispatched by
# the same thread that would be blocked waiting for it.
_tls = threading.local()


class MSPError(Exception):
    """Base for all serve-host client errors."""


class HandshakeError(MSPError):
    """The initialize/initialized handshake failed."""


class HostDiedError(MSPError):
    """The serve process died (or was never successfully opened)."""


class RequestTimeoutError(MSPError):
    """A call got no response within its timeout."""


class SchemaMismatchError(MSPError):
    """The schema fingerprint does not match the pin (binary upgraded)."""


class ProtocolError(MSPError):
    """A structurally invalid frame or envelope was received/sent."""


class ServerError(MSPError):
    """The serve host answered a call with a JSON-RPC error."""

    def __init__(self, code, message, data=None):
        super().__init__(f"serve host error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


def schema_fingerprint(schema_bytes):
    """Fingerprint an exported schema bundle: ``sha256:<hex>``.

    Canonical form is the parsed JSON re-serialized with sorted keys and
    compact separators, UTF-8 encoded, then SHA-256. Canonicalizing (not
    hashing raw bytes) keeps the pin stable across insignificant
    whitespace/key-order differences in the exporter.
    """
    try:
        obj = json.loads(schema_bytes)
    except (ValueError, TypeError) as e:
        raise ValueError(f"schema bundle is not valid JSON: {e}")
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def export_schema(muse_argv=("muse",), timeout=30):
    """Run `muse schema generate-json-schema`; return the raw bytes."""
    argv = list(muse_argv) + ["schema", "generate-json-schema"]
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
    except OSError as e:
        raise MSPError(f"cannot run schema exporter {argv[0]!r}: {e}")
    except subprocess.TimeoutExpired:
        raise MSPError(
            f"schema exporter timed out after {timeout}s: {argv[0]!r}"
        )
    if p.returncode != 0:
        raise MSPError(
            f"schema exporter failed ({p.returncode}): "
            f"{p.stderr.decode('utf-8', 'replace')[:300]}"
        )
    return p.stdout


def verify_schema_fingerprint(schema_bytes, expected):
    """Raise SchemaMismatchError unless the fingerprint matches the pin."""
    actual = schema_fingerprint(schema_bytes)
    if actual != expected:
        raise SchemaMismatchError(
            f"schema fingerprint mismatch: got {actual}, expected "
            f"{expected} -- the serve binary was upgraded under us; "
            f"re-verify the wire shape before proceeding"
        )
    return actual


def _open_secret_log(path):
    """Open the serve-stderr log file, holding it to mode 0o600.

    Serve stderr can carry real secret values (see the module's Security
    and trust section). The file is opened with O_NOFOLLOW and validated
    with fstat on the resulting fd -- the check and the open are one
    syscall path, so there is no check-then-open TOCTOU window in which
    a planted symlink could be swapped in between. A symlink is refused
    fail-closed (ELOOP). O_NONBLOCK keeps a pre-planted FIFO from hanging
    the open forever: a reader-less FIFO fails fast with ENXIO (the #23 H5
    class the muse-job hooks already defend against). A pre-existing
    regular file that grants any group/other permission is tightened to
    0o600 (os.open's mode applies only at creation; without this,
    appending new secret bytes to an old 0644 log would leak them).
    Permissions are only ever revoked, never granted -- a 0400 file stays
    0400. Non-regular targets (e.g. /dev/null) are left alone.

    Returns the binary append-mode file object. Raises MSPError
    fail-closed (never leaves a half-opened fd): the caller must not
    spawn the serve host afterwards.
    """
    try:
        fd = os.open(
            path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_APPEND
            | os.O_NOFOLLOW
            | os.O_NONBLOCK,
            0o600,
        )
    except OSError as e:
        raise MSPError(
            f"log_path {path!r} refused (missing, unreadable, a symlink, "
            f"or a reader-less FIFO -- symlinks are never followed): {e}"
        ) from e
    try:
        st = os.fstat(fd)
        if stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode) & 0o077:
            os.fchmod(fd, 0o600)
            print(
                f"msp_host: WARNING: tightened {path!r} to mode 0o600 "
                f"(was {stat.S_IMODE(st.st_mode):04o}); serve stderr can "
                f"carry secret values",
                file=sys.stderr,
            )
        return os.fdopen(fd, "ab")
    except OSError as e:
        os.close(fd)
        raise MSPError(
            f"log_path {path!r} could not be validated after open: {e}"
        ) from e


class MSPHost:
    """Owns one `muse serve` process and its NDJSON JSON-RPC 2.0 session."""

    def __init__(
        self,
        serve_argv,
        *,
        client_name,
        client_version="0.0.0",
        log_path=None,
        expected_schema_fingerprint=None,
        verify_schema_on_open=False,
        request_timeout=30.0,
        kill_grace=5.0,
        send_timeout=10.0,
        max_frame_bytes=16 * 1024 * 1024,
    ):
        """
        serve_argv: e.g. ["muse", "serve"] (a list; first element is the
            binary -- never a shell string, so no shell-injection surface).
        client_name: must match ^[a-z0-9_]+$ (serve-side rule, see #221).
        log_path: the serve process's stderr goes here (the job log); None
            discards stderr. Created mode 0o600 (serve stderr can carry
            secrets); a pre-existing regular file with group/other
            permission bits is tightened to 0o600; a symlink at log_path
            is refused (fail-closed, no spawn). See the module's Security
            and trust section.
        expected_schema_fingerprint: "sha256:<hex>" pin; enforced at open()
            when verify_schema_on_open is true (exports the schema from
            serve_argv[0]). The full pin value is recorded from the
            deployment binary -- see SCHEMA_FINGERPRINT_VERIFIED_PREFIX.
        request_timeout: seconds to wait for a call's response (None is
            rejected).
        send_timeout: seconds to wait for one frame's stdin write/flush;
            on expiry the host is treated as dead (fail loud).
        max_frame_bytes: largest single NDJSON frame accepted from the
            serve host; an overrun frame treats the host as wedged
            (pending calls fail with HostDiedError).
        """
        if not serve_argv or not all(
            isinstance(a, str) and a for a in serve_argv
        ):
            raise ValueError("serve_argv must be a non-empty list of strings")
        if not isinstance(client_name, str) or not CLIENT_NAME_RE.match(
            client_name
        ):
            raise ValueError(
                f"client_name must match ^[a-z0-9_]+$, got {client_name!r}"
            )
        if request_timeout is None:
            raise ValueError("request_timeout=None is rejected; pass seconds")
        self._serve_argv = list(serve_argv)
        self._client_name = client_name
        self._client_version = client_version
        self._log_path = log_path
        self._expected_fp = expected_schema_fingerprint
        self._verify_schema = verify_schema_on_open
        self._default_timeout = float(request_timeout)
        self._kill_grace = float(kill_grace)
        self._send_timeout = float(send_timeout)
        self._max_frame_bytes = int(max_frame_bytes)

        self._proc = None
        self._reader = None
        self._closed = False
        self._opened = False
        self._dead = False
        # Generation token: incremented on every reconnect() so a stale
        # generation-1 write (or a straggler old reader thread) can never
        # emit bytes into the new serve process. Captured alongside slot
        # registration in call() and at reader-thread start; _send refuses
        # a mismatching generation.
        self._generation = 0
        self._id_counter = 0
        self._write_lock = threading.Lock()
        self._cond = threading.Condition()
        self._pending = {}  # id -> {"event": Event, "response": dict|None}
        self._subscribers = []  # (prefix, callback)
        self._request_handlers = {}
        self._log_fh = None
        self.stats = {
            "sent": 0,
            "received": 0,
            "malformed": 0,
            "unknown_id_responses": 0,
        }
        # Bounded record of subscriber exceptions (never raised to callers;
        # the reader thread must survive a bad subscriber).
        self.subscriber_errors = []

    def _record_subscriber_error(self, e):
        # Bounded: a chatty failing subscriber must not grow memory forever.
        self.subscriber_errors.append(e)
        del self.subscriber_errors[:-100]

    @staticmethod
    def _check_not_reader(what):
        if getattr(_tls, "in_reader", False):
            raise MSPError(
                f"{what} from a reader-thread callback or request handler "
                "would deadlock dispatch; hand the work to your own thread"
            )

    # -- lifecycle ------------------------------------------------------

    def open(self):
        """Spawn the serve host and run the initialize/initialized handshake.

        Raises HandshakeError (process reaped) if initialize fails, or
        SchemaMismatchError if the schema pin is enforced and mismatches.
        Calling open() twice is a bug and raises MSPError. If open()
        raises, the host is closed; retry with reconnect().
        """
        with self._cond:
            if self._opened:
                raise MSPError("open() called twice; use reconnect()")
            if self._closed:
                raise MSPError("host is closed")
        if self._verify_schema:
            if not self._expected_fp:
                raise MSPError(
                    "verify_schema_on_open needs expected_schema_fingerprint"
                )
            verify_schema_fingerprint(
                export_schema((self._serve_argv[0],)), self._expected_fp
            )
        try:
            if self._log_path:
                # Held to 0o600 / symlink-refused by _open_secret_log --
                # serve stderr can carry secret values (see Security and
                # trust). Raises MSPError fail-closed: no spawn happens.
                self._log_fh = _open_secret_log(self._log_path)
            else:
                self._log_fh = None
            stderr = self._log_fh if self._log_fh else subprocess.DEVNULL
            self._proc = subprocess.Popen(
                self._serve_argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                # No shell=True ever: argv is exec'd directly.
            )
        except OSError as e:
            self._close_log()
            raise MSPError(
                f"cannot spawn serve host {self._serve_argv[0]!r}: {e}"
            )
        self._dead = False
        self._reader = threading.Thread(
            target=self._reader_main, name="msp-reader", daemon=True
        )
        self._reader.start()
        try:
            try:
                result = self.call(
                    "initialize",
                    {
                        "clientInfo": {
                            "name": self._client_name,
                            "version": self._client_version,
                        }
                    },
                )
            except MSPError as e:
                raise HandshakeError(f"initialize failed: {e}")
            # The step the 2026-09-17 investigation missed: nothing else
            # works until the initialized notification is sent.
            try:
                self.notify("initialized", {})
            except MSPError as e:
                raise HandshakeError(f"initialized notification failed: {e}")
        except BaseException as e:
            # Includes KeyboardInterrupt: never orphan the child just
            # because the handshake was interrupted.
            self._abort_open(f"handshake failed: {e}")
            raise
        with self._cond:
            self._opened = True
        return result

    def _abort_open(self, _reason):
        # Best-effort teardown after a failed handshake; the reason is
        # carried by the exception the caller already has.
        try:
            self.close()
        except MSPError:
            pass

    def reconnect(self):
        """Re-spawn a dead host and re-run the handshake.

        Subscriptions and request handlers survive (they are instance
        state); in-flight calls from the dead generation fail with
        HostDiedError at close time. Sessions are durable server-side, so
        the new host re-attaches to the same session store. Calling
        reconnect() on a never-opened host behaves like open().
        """
        self._check_not_reader("reconnect()")
        self.close()
        with self._cond:
            self._closed = False
            self._opened = False
            self._dead = False
            self._pending = {}
            # New generation: stale writes from the dead generation (and
            # its straggler reader thread) can never address the new
            # process; _send refuses a mismatching generation.
            self._generation += 1
        return self.open()

    def close(self):
        """Idempotent: fail pending calls, terminate the process, join."""
        with self._cond:
            if self._closed:
                return
            self._closed = True
            self._dead = True
            pending = self._pending
            self._pending = {}
            self._cond.notify_all()
        for slot in pending.values():
            slot["response"] = HostDiedError("serve host is closed")
            slot["event"].set()
        # Null proc/reader under the write lock so an in-flight _send
        # either completes first or sees proc=None and fails loud --
        # never a torn-down object.
        with self._write_lock:
            proc, reader = self._proc, self._reader
            self._proc, self._reader = None, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=self._kill_grace)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=self._kill_grace)
                except subprocess.TimeoutExpired:
                    pass  # wedged child: abandon rather than hang close()
        if reader is not None and reader is not threading.current_thread():
            try:
                reader.join(timeout=self._kill_grace + 5)
            except RuntimeError:
                pass  # never-started thread: nothing to join
        self._close_log()

    def _close_log(self):
        fh, self._log_fh = self._log_fh, None
        if fh is not None:
            try:
                fh.close()
            except OSError:
                pass

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def is_alive(self):
        proc = self._proc
        return (
            proc is not None
            and not self._closed
            and not self._dead
            and proc.poll() is None
        )

    # -- requests / notifications ----------------------------------------

    def _next_id(self):
        with self._write_lock:
            self._id_counter += 1
            return self._id_counter

    def _send(self, obj, expected_gen=None):
        data = (json.dumps(obj) + "\n").encode("utf-8")
        if len(data) > _MAX_SEND_FRAME_BYTES:
            # Refused BEFORE taking the write lock: one giant params must
            # never park _send (and every lock waiter, including close())
            # on a wedged child's full pipe.
            raise ValueError(
                f"frame is {len(data)} bytes, over the "
                f"{_MAX_SEND_FRAME_BYTES}-byte cap; params must be small "
                "dicts"
            )
        # The actual stdin write/flush runs in a short-lived helper thread
        # joined with send_timeout. A wedged-but-alive child that never
        # drains its stdin would otherwise block this thread forever while
        # holding _write_lock, and close() could never acquire the lock to
        # terminate it. On expiry the host is treated as dead (fail loud);
        # the abandoned writer completing later is harmless -- the host is
        # gone anyway.
        written = threading.Event()
        write_error = []

        def _write(proc, payload):
            try:
                proc.stdin.write(payload)
                proc.stdin.flush()
            except Exception as e:  # BrokenPipeError, OSError, ValueError
                write_error.append(e)
            finally:
                written.set()

        with self._write_lock:
            # Read proc and generation under the write lock: close() nulls
            # proc under the same lock, so we never touch a torn-down
            # process object, and a stale generation never addresses the
            # new process after a reconnect().
            proc = self._proc
            if expected_gen is not None and expected_gen != self._generation:
                raise HostDiedError("superseded by reconnect")
            if proc is None or self._closed:
                raise HostDiedError("serve host is not open")
            if self._dead or proc.poll() is not None:
                self._dead = True
                raise HostDiedError("serve host process died")
            writer = threading.Thread(
                target=_write, args=(proc, data), daemon=True
            )
            writer.start()
            if not written.wait(self._send_timeout):
                self._dead = True
                raise HostDiedError(
                    f"send timed out after {self._send_timeout}s: serve "
                    "host is not draining its stdin"
                )
            if write_error:
                self._dead = True
                raise HostDiedError(
                    f"serve host pipe broke: {write_error[0]}"
                )
            self.stats["sent"] += 1

    def call(self, method, params=None, timeout=None):
        """JSON-RPC 2.0 request; return the result (or raise).

        Raises MSPError if called from a reader-thread callback or
        request handler (re-entrant dispatch would deadlock).

        Results are NOT redacted: see the module's Security and trust
        section before logging or displaying them.
        """
        self._check_not_reader("call()")
        if not isinstance(method, str) or not method:
            raise ValueError("method must be a non-empty string")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError("params must be a dict")
        req_id = self._next_id()
        slot = {"event": threading.Event(), "response": None}
        with self._cond:
            # Capture the generation with the slot: a call stalled here
            # across a reconnect() must not emit bytes into the new
            # process (its slot is failed at close() time anyway).
            gen = self._generation
            self._pending[req_id] = slot
        try:
            self._send(
                {"jsonrpc": _JSONRPC, "id": req_id, "method": method,
                 "params": params},
                expected_gen=gen,
            )
        except Exception:
            # _send can also raise TypeError for unserializable params;
            # the slot must not leak whatever the failure was.
            with self._cond:
                self._pending.pop(req_id, None)
            raise
        if not slot["event"].wait(
            self._default_timeout if timeout is None else timeout
        ):
            with self._cond:
                self._pending.pop(req_id, None)
            raise RequestTimeoutError(
                f"no response to {method!r} within "
                f"{self._default_timeout if timeout is None else timeout}s"
            )
        resp = slot["response"]
        if isinstance(resp, MSPError):
            raise resp
        if "error" in resp:
            err = resp["error"] or {}
            raise ServerError(
                err.get("code"), err.get("message"), err.get("data")
            )
        if "result" not in resp:
            raise ProtocolError(
                f"response to {method!r} has neither 'result' nor 'error'"
            )
        return resp["result"]

    def notify(self, method, params=None):
        """Fire-and-forget JSON-RPC 2.0 notification.

        Raises MSPError if called from a reader-thread callback or
        request handler (re-entrant dispatch would deadlock).

        Payloads are NOT redacted: see the module's Security and trust
        section before logging or displaying them.
        """
        self._check_not_reader("notify()")
        if not isinstance(method, str) or not method:
            raise ValueError("method must be a non-empty string")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError("params must be a dict")
        gen = self._generation
        self._send(
            {"jsonrpc": _JSONRPC, "method": method, "params": params},
            expected_gen=gen,
        )

    # -- server->client dispatch ------------------------------------------

    def subscribe(self, prefix, callback):
        """Dispatch server->client notifications to callback(notification).

        prefix matches the method itself or "<prefix>/..." (so "session"
        catches "session/changed"). Returns an unsubscribe callable.
        callback runs on the reader thread: keep it quick; exceptions are
        recorded on subscriber_errors, never raised. A callback must not
        call call()/notify()/reconnect() (raises MSPError -- re-entrant
        dispatch would deadlock); hand work to your own thread.
        Registration is not synchronized: subscribe before open() or
        from a single thread.

        Notifications are NOT redacted: see the module's Security and
        trust section before logging or displaying them.
        """
        if not isinstance(prefix, str) or not prefix:
            raise ValueError("prefix must be a non-empty string")
        if not callable(callback):
            raise ValueError("callback must be callable")
        entry = (prefix, callback)
        self._subscribers.append(entry)

        def unsubscribe():
            try:
                self._subscribers.remove(entry)
            except ValueError:
                pass

        return unsubscribe

    def set_request_handler(self, method, handler):
        """Route a server->client request method to handler(request)->result.

        A handler that raises produces a JSON-RPC error response to the
        server. With no handler registered, the client answers
        method-not-found -- failing loud rather than silently dropping (or
        auto-answering) a prompt the operator never saw. A handler must
        not call call()/notify()/reconnect() (raises MSPError -- re-entrant
        dispatch would deadlock); hand work to your own thread.
        Registration is not synchronized: register before open() or
        from a single thread.
        """
        if not isinstance(method, str) or not method:
            raise ValueError("method must be a non-empty string")
        if not callable(handler):
            raise ValueError("handler must be callable")
        self._request_handlers[method] = handler

    # -- reader ------------------------------------------------------------

    def _read_frame(self, proc, buf):
        """Read one NDJSON frame with a byte budget.

        buf is the reader thread's persistent byte buffer: leftover bytes
        after one frame's newline stay buffered for the next frame (never
        re-read, never dropped). Returns the frame bytes (no trailing
        newline), None on EOF (a short final line without a newline is
        returned as a frame), or _FRAME_OVERRUN when a single frame
        exceeds max_frame_bytes: the serve host is treated as wedged and
        the reader stops.
        """
        cap = self._max_frame_bytes
        while True:
            nl = buf.find(b"\n")
            if nl != -1:
                if nl > cap:
                    return _FRAME_OVERRUN
                frame = bytes(buf[:nl])
                del buf[: nl + 1]
                return frame
            if len(buf) > cap:
                return _FRAME_OVERRUN
            # read1, not read: BufferedReader.read(n) loops raw reads until
            # n bytes or EOF, which blocks forever on a live pipe holding
            # fewer than n bytes; read1 does at most one raw read and
            # returns what is available.
            chunk = proc.stdout.read1(65536)
            if not chunk:
                if buf:
                    frame = bytes(buf)
                    del buf[:]
                    return frame
                return None
            buf += chunk

    def _reader_main(self):
        _tls.in_reader = True
        # Bound before any early return: the finally below references gen.
        # This thread's generation: after a reconnect() the old reader may
        # survive close()'s join (a wedged child whose stdout pipe is held
        # open by an inherited fd never delivers EOF). Such a straggler
        # must not dispatch into, or poison the liveness of, the new
        # generation: its answers are refused by _send's generation check,
        # its loop breaks below, and its finally is generation-guarded.
        gen = self._generation
        try:
            proc = self._proc
            if proc is None:
                return
            read_buf = bytearray()  # this thread's frame buffer; _read_frame
            while True:             # keeps leftovers across frames
                if gen != self._generation:
                    break  # superseded by reconnect(); the new generation
                           # owns dispatch now
                frame = self._read_frame(proc, read_buf)
                if frame is None:
                    break
                if frame is _FRAME_OVERRUN:
                    self.stats["malformed"] += 1
                    self._record_subscriber_error(
                        MSPError(
                            "frame exceeded max_frame_bytes "
                            f"({self._max_frame_bytes}); treating serve "
                            "host as wedged"
                        )
                    )
                    break
                try:
                    line = frame.decode("utf-8").strip()
                except UnicodeDecodeError:
                    self.stats["malformed"] += 1
                    continue
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except ValueError:
                    self.stats["malformed"] += 1
                    continue
                self.stats["received"] += 1
                try:
                    self._dispatch(msg, gen)
                except Exception as e:  # never let dispatch kill the reader
                    self._record_subscriber_error(e)
        finally:
            _tls.in_reader = False
            # EOF or read error: the host is gone. Fail every pending call --
            # but only if this reader still owns the current generation. A
            # straggler from a superseded generation must not brick the live
            # host: the dead generation's slots were already failed by
            # close()'s swap, and the new generation has its own reader to
            # observe real deaths.
            with self._cond:
                if gen == self._generation:
                    self._dead = True
                    pending = self._pending
                    self._pending = {}
                    self._cond.notify_all()
                else:
                    pending = {}
            for slot in pending.values():
                slot["response"] = HostDiedError("serve host process died")
                slot["event"].set()

    def _dispatch(self, msg, gen):
        if not isinstance(msg, dict) or msg.get("jsonrpc") != _JSONRPC:
            self.stats["malformed"] += 1
            return
        method = msg.get("method")
        req_id = msg.get("id")
        if method is not None and req_id is not None:
            self._handle_server_request(msg, method, req_id, gen)
        elif method is not None:
            self._handle_notification(msg, method)
        elif req_id is not None:
            self._handle_response(msg, req_id)
        else:
            self.stats["malformed"] += 1

    def _handle_response(self, msg, req_id):
        with self._cond:
            slot = self._pending.pop(req_id, None)
        if slot is None:
            self.stats["unknown_id_responses"] += 1
            return
        slot["response"] = msg
        slot["event"].set()

    def _handle_notification(self, msg, method):
        if not isinstance(method, str):
            self.stats["malformed"] += 1
            return
        for prefix, callback in list(self._subscribers):
            if method == prefix or method.startswith(prefix + "/"):
                try:
                    callback(msg)
                except Exception as e:
                    self._record_subscriber_error(e)

    def _handle_server_request(self, msg, method, req_id, gen):
        handler = self._request_handlers.get(method)
        if handler is None:
            self._answer(req_id, gen, error={
                "code": _ERR_METHOD_NOT_FOUND,
                "message": f"no handler registered for {method!r}",
            })
            return
        try:
            result = handler(msg)
        except Exception as e:
            self._answer(req_id, gen, error={
                "code": -32000,
                "message": f"handler for {method!r} raised: {e}",
            })
            return
        try:
            json.dumps(result)
        except (TypeError, ValueError) as e:
            # A non-serializable result would raise inside _send and leave
            # the server hanging with no answer; fail loud instead.
            self._answer(req_id, gen, error={
                "code": -32603,
                "message": f"handler for {method!r} returned a "
                           f"non-JSON-serializable result: {e}",
            })
            return
        self._answer(req_id, gen, result=result)

    def _answer(self, req_id, gen, result=None, error=None):
        msg = {"jsonrpc": _JSONRPC, "id": req_id}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result
        try:
            self._send(msg, expected_gen=gen)
        except HostDiedError:
            pass  # the host is gone (or superseded); nothing left to answer


def main(argv):
    """Tiny smoke CLI: open a host, print initialize result, close."""
    import argparse

    ap = argparse.ArgumentParser(description="MSP serve-host smoke test")
    ap.add_argument("serve", nargs=argparse.REMAINDER,
                    help="serve argv after --, e.g. -- muse serve")
    ap.add_argument("--client-name", default="msp_smoke")
    ap.add_argument("--method", default=None,
                    help="optional extra method to call after handshake")
    args = ap.parse_args(argv)
    if not args.serve:
        ap.error("need serve argv after --")
    host = MSPHost(args.serve, client_name=args.client_name)
    with host:
        print(json.dumps({"initialize": "ok"}))
        if args.method:
            # Note: call() results are NOT redacted (see Security and
            # trust); don't paste this output where agents can read it.
            print(json.dumps({"result": host.call(args.method, {})}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
