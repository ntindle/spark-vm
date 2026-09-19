"""Hermetic tests for harness/harness-auth-probe.

Fixtures simulate the three external actors without mitmproxy or the real
muse CLI:
  - fake `muse` CLI (a python script): honors the probe's child-env contract
    (META_API_KEY placeholder, proxy env forced, NO_PROXY stripped), sends
    GET+POST with an Authorization header through the proxy, exits per
    FAKE_MUSE_MODE.
  - echo server: records every Authorization header it receives to a JSONL log.
  - swap proxy: minimal forward HTTP proxy; in "swap" mode rewrites
    "Bearer hsurr:gate-dummy" -> "Bearer <swapped>" (the proxy's job), in
    "passthrough" mode forwards untouched.
  - confirmd stub: plain HTTP 200 (PROBE_CONFIRMD_URL is scheme-agnostic in
    tests; production uses https).
"""

import http.client
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

HARNESS = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HARNESS, "harness-auth-probe")
PLACEHOLDER = "hsurr:gate-dummy"
SWAPPED = "DUMMY-SWAPPED-PUBLIC"

FAKE_MUSE = r'''#!/usr/bin/env python3
"""Fake muse CLI: mimics the wire contract the probe depends on."""
import os, sys, time, urllib.request
mode = os.environ.get("FAKE_MUSE_MODE", "ok")
if mode == "sleep":
    time.sleep(30)
    sys.exit(0)
if mode == "cli-fails":
    sys.exit(3)
# env contract the probe promises its child
assert os.environ.get("META_API_KEY", "").startswith("hsurr:"), "no placeholder key"
assert os.environ.get("HTTPS_PROXY", "").startswith("http://127.0.0.1"), "no proxy routing"
assert "NO_PROXY" not in os.environ and "no_proxy" not in os.environ, "bypass list present"
key = os.environ["META_API_KEY"]
argv = sys.argv
base = argv[argv.index("--base-url") + 1]
scheme = "Token " if mode == "bad-scheme" else "Bearer "
headers = {"Authorization": scheme + key}
if mode != "no-request":
    for path in ("/muse-code/models", "/responses"):
        req = urllib.request.Request(base.rstrip("/") + path, headers=headers,
                                     data=b"{}" if path == "/responses" else None)
        try:
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            pass  # the echo fixture's body is not a completion; header delivery is what counts
sys.exit(0)
'''


class EchoHandler(BaseHTTPRequestHandler):
    log_path = None

    def _handle(self):
        auth = self.headers.get("Authorization", "")
        rec = {"method": self.command, "path": self.path, "authorization": auth}
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _handle
    do_POST = _handle

    def log_message(self, *a):
        pass


class SwapHandler(BaseHTTPRequestHandler):
    """Minimal forward proxy. mode=swap rewrites the placeholder (the proxy's
    job); mode=passthrough forwards untouched (simulates a broken swap)."""
    mode = "swap"
    placeholder = PLACEHOLDER
    swapped = SWAPPED

    def _handle(self):
        parts = urlsplit(self.path)  # absolute URI from the client
        target_host, target_port = parts.hostname, parts.port or 80
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None
        headers = {}
        for k, v in self.headers.items():
            if k.lower() in ("host", "proxy-connection", "connection"):
                continue
            if k.lower() == "authorization" and self.mode == "swap":
                v = v.replace(f"Bearer {self.placeholder}", f"Bearer {self.swapped}")
            headers[k] = v
        headers["Host"] = parts.netloc
        conn = http.client.HTTPConnection(target_host, target_port, timeout=5)
        conn.request(self.command, parts.path or "/", body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() in ("transfer-encoding", "connection"):
                continue
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        conn.close()

    do_GET = _handle
    do_POST = _handle

    def log_message(self, *a):
        pass


class OkHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def serve(handler_cls, **attrs):
    for k, v in attrs.items():
        setattr(handler_cls, k, v)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def fixtures(tmp_path):
    echo_log = str(tmp_path / "echo.jsonl")
    open(echo_log, "w").close()
    echo = serve(EchoHandler, log_path=echo_log)
    swap = serve(SwapHandler)
    confirmd = serve(OkHandler)
    muse = tmp_path / "muse"
    muse.write_text(FAKE_MUSE)
    muse.chmod(0o755)
    yield {
        "echo_log": echo_log,
        "echo_url": f"http://127.0.0.1:{echo.server_port}",
        "proxy_url": f"http://127.0.0.1:{swap.server_port}",
        "confirmd_url": f"http://127.0.0.1:{confirmd.server_port}",
        "muse": str(muse),
        "swap_handler": SwapHandler,
    }
    for srv in (echo, swap, confirmd):
        srv.shutdown()


def run_probe(fixtures, tmp_path, mode="gate", extra_env=None, argv_extra=()):
    env = {
        "PATH": os.path.dirname(fixtures["muse"]) + os.pathsep + os.environ.get("PATH", ""),
        "PROBE_MUSE_BIN": "muse",
        "PROBE_PROXY": fixtures["proxy_url"],
        "PROBE_BASE_URL": fixtures["echo_url"],
        "PROBE_KEY_NAME": "gate-dummy",
        "PROBE_ECHO_LOG": fixtures["echo_log"],
        "PROBE_EXPECTED_SWAPPED": SWAPPED,
        "PROBE_CONFIRMD_URL": fixtures["confirmd_url"],
        "FAKE_MUSE_MODE": "ok",
    }
    # Keep the test hermetic even where the ambient env has proxies set.
    for var in ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy",
                "NO_PROXY", "no_proxy"):
        os.environ.pop(var, None)
    if extra_env:
        env.update(extra_env)
    if mode == "provision":
        env.pop("PROBE_ECHO_LOG", None)
        env.pop("PROBE_EXPECTED_SWAPPED", None)
        env["PROBE_KEY_NAME"] = "llm-api"
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, PROBE, "--mode", mode, *argv_extra],
        env={**os.environ, **env},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=60, text=True,
    )
    return proc, time.monotonic() - t0


def echo_auths(path):
    with open(path) as f:
        return [json.loads(line).get("authorization", "")
                for line in f if line.strip()]


def test_gate_pass(fixtures, tmp_path):
    proc, _ = run_probe(fixtures, tmp_path)
    assert proc.returncode == 0, proc.stderr
    auths = echo_auths(fixtures["echo_log"])
    assert len(auths) >= 2  # catalog GET + POST, like the real CLI
    assert all(a == f"Bearer {SWAPPED}" for a in auths)


def test_gate_no_swap_fails(fixtures, tmp_path):
    fixtures["swap_handler"].mode = "passthrough"
    try:
        proc, _ = run_probe(fixtures, tmp_path)
    finally:
        fixtures["swap_handler"].mode = "swap"
    assert proc.returncode == 1
    assert "hsurr:gate-dummy" in open(fixtures["echo_log"]).read()
    assert "placeholder" in proc.stderr and "never reach the origin" in proc.stderr


def test_gate_no_records_fails_closed(fixtures, tmp_path):
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"FAKE_MUSE_MODE": "no-request"})
    assert proc.returncode == 1
    assert "no requests reached the echo fixture" in proc.stderr


def test_gate_bad_wire_shape_fails(fixtures, tmp_path):
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"FAKE_MUSE_MODE": "bad-scheme"})
    assert proc.returncode == 1
    assert "wire-shape" in proc.stderr


def test_gate_cli_timeout_fails_fast(fixtures, tmp_path):
    proc, dt = run_probe(fixtures, tmp_path,
                         extra_env={"FAKE_MUSE_MODE": "sleep"})
    assert proc.returncode == 1
    assert dt < 15, f"probe hung {dt:.1f}s instead of using its internal timeout"


def test_provision_pass(fixtures, tmp_path):
    proc, _ = run_probe(fixtures, tmp_path, mode="provision")
    assert proc.returncode == 0, proc.stderr


def test_provision_cli_failure_fails(fixtures, tmp_path):
    proc, _ = run_probe(fixtures, tmp_path, mode="provision",
                        extra_env={"FAKE_MUSE_MODE": "cli-fails"})
    assert proc.returncode == 1
    assert "did not accept the swapped credential" in proc.stderr


def test_confirmd_down_fails(fixtures, tmp_path):
    proc, _ = run_probe(
        fixtures, tmp_path,
        extra_env={"PROBE_CONFIRMD_URL": f"http://127.0.0.1:{free_port()}"})
    assert proc.returncode == 1
    assert "confirmd did not answer" in proc.stderr


def test_missing_muse_fails_closed(fixtures, tmp_path):
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"PROBE_MUSE_BIN": "/nonexistent/muse-probe-test"})
    assert proc.returncode == 3
    assert "not found" in proc.stderr


def test_bad_mode_usage_error(fixtures, tmp_path):
    proc, _ = run_probe(fixtures, tmp_path, argv_extra=[])
    # argparse path: pass the bad mode directly
    env = {"PATH": os.environ.get("PATH", "")}
    p = subprocess.run([sys.executable, PROBE, "--mode", "bogus"],
                       stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=30, env={**os.environ, **env})
    assert p.returncode == 2
    assert proc.returncode == 0  # sanity: the fixture run itself was fine


def test_gate_missing_fixture_config_usage_error(fixtures, tmp_path):
    env = {
        "PATH": os.path.dirname(fixtures["muse"]) + os.pathsep + os.environ.get("PATH", ""),
        "PROBE_MUSE_BIN": "muse",
        "PROBE_PROXY": fixtures["proxy_url"],
        "PROBE_BASE_URL": fixtures["echo_url"],
        "PROBE_CONFIRMD_URL": fixtures["confirmd_url"],
    }
    p = subprocess.run([sys.executable, PROBE, "--mode", "gate"],
                       stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=30, env={**os.environ, **env})
    assert p.returncode == 2
    assert "PROBE_ECHO_LOG" in p.stderr


def test_provision_missing_base_url_usage_error(fixtures, tmp_path):
    env = {
        "PATH": os.path.dirname(fixtures["muse"]) + os.pathsep + os.environ.get("PATH", ""),
        "PROBE_MUSE_BIN": "muse",
        "PROBE_PROXY": fixtures["proxy_url"],
        "PROBE_CONFIRMD_URL": fixtures["confirmd_url"],
    }
    p = subprocess.run([sys.executable, PROBE, "--mode", "provision"],
                       stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=30, env={**os.environ, **env})
    assert p.returncode == 2
    assert "PROBE_BASE_URL" in p.stderr


def test_probe_never_blocks_on_stdin(fixtures, tmp_path):
    # stdin closed AND stdin=DEVNULL both complete: the probe never prompts.
    proc, _ = run_probe(fixtures, tmp_path)
    assert proc.returncode == 0
    assert "OK (gate mode" in proc.stderr
