#!/usr/bin/env python3
"""echo-fixture.py — the gate fixture's echo origin (R2).

A tiny HTTP server for harness/install-gate-fixture.sh. For every request
it appends one JSONL record {"method","path","authorization","headers",
"body_sha256"} to the log at ECHO_FIXTURE_LOG and answers 200 with an
empty JSON object. It exists only to prove the swap path: the canonical
probe (harness/harness-auth-probe, gate mode) asserts the swapped
Authorization header reached the origin and the hsurr:<name> placeholder
never did — in ANY recorded field, not just the Authorization header
(GitHub #157). The full header set (names lowercased) and the raw path
(incl. the query string) are recorded so a placeholder leaking through a
second header, a query parameter, or the request line fails the gate;
the body is recorded only as a sha256 hex digest (never the content —
bodies can carry the swapped dummy value legitimately, and hashing keeps
the log free of secret-shaped material).

The record format matches the hermetic echo server in
harness/test_probe.py, so the fixture's production behavior and the
probe's tested behavior are the same wire contract. "authorization" is
kept as its own field (the exact-Bearer wire-shape assertion's canonical
field); "headers" is the full set including it.

Env:
  ECHO_FIXTURE_LOG   required — the JSONL log path (created if missing;
                     appended to if present; the probe reads only records
                     appended after its run starts).
  ECHO_FIXTURE_PORT  optional — bind port, default 0 (ephemeral).

Prints "PORT=<n>" as its first stdout line once bound (the installer's
readiness signal), then serves until killed. Binds 127.0.0.1 only — this
fixture must never be reachable off-box. It is started and killed by the
installer; it is not a service.
"""

import hashlib
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _record_request(handler):
    """Build the echo record for one request (GitHub #157 wire contract).

    Records the method, the raw path (query string included), the full
    header set with lowercased names (duplicate same-name headers joined
    with ", " per RFC 9110 section 5.3, so no occurrence is dropped), and
    a sha256 of the body (empty string when there is no body).
    "authorization" is also kept as its own field — the probe's
    exact-Bearer wire-shape assertion reads it directly, and the
    placeholder scan covers every recorded field.
    """
    try:
        length = int(handler.headers.get("Content-Length", 0) or 0)
    except ValueError:
        length = 0  # malformed framing: still record headers/path, no body
    if length < 0:
        length = 0
    body = handler.rfile.read(length) if length else b""
    headers = {}
    for name, value in handler.headers.items():
        # Join duplicates per RFC 9110 section 5.3 instead of
        # first-wins: a placeholder in a second same-name header is
        # still a leak the probe must see (GitHub #157).
        key = name.lower()
        headers[key] = headers[key] + ", " + value if key in headers else value
    return {
        "method": handler.command,
        "path": handler.path,
        "authorization": handler.headers.get("Authorization", ""),
        "headers": headers,
        "body_sha256": hashlib.sha256(body).hexdigest() if body else "",
    }


def main():
    log_path = os.environ.get("ECHO_FIXTURE_LOG")
    if not log_path:
        sys.stderr.write("echo-fixture: ECHO_FIXTURE_LOG is required\n")
        return 2
    try:
        port = int(os.environ.get("ECHO_FIXTURE_PORT", "0"))
    except ValueError:
        sys.stderr.write("echo-fixture: ECHO_FIXTURE_PORT is not a number\n")
        return 2

    class EchoHandler(BaseHTTPRequestHandler):
        def _handle(self):
            rec = _record_request(self)
            with open(log_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            body = b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = _handle
        do_POST = _handle

        def log_message(self, *args):  # keep stdout clean: PORT= is first
            pass

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), EchoHandler)
    except OSError as e:
        sys.stderr.write(f"echo-fixture: cannot bind 127.0.0.1:{port}: {e}\n")
        return 3
    print(f"PORT={srv.server_address[1]}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
