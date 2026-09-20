#!/usr/bin/env python3
"""echo-fixture.py — the gate fixture's echo origin (R2).

A tiny HTTP server for harness/install-gate-fixture.sh. For every request
it appends one JSONL record {"method","path","authorization"} to the log
at ECHO_FIXTURE_LOG and answers 200 with an empty JSON object. It exists
only to prove the swap path: the canonical probe
(harness/harness-auth-probe, gate mode) asserts the swapped Authorization
header reached the origin and the hsurr:<name> placeholder never did.

The record format matches the hermetic echo server in
harness/test_probe.py, so the fixture's production behavior and the
probe's tested behavior are the same wire contract.

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

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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
            auth = self.headers.get("Authorization", "")
            rec = {"method": self.command, "path": self.path,
                   "authorization": auth}
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
