"""Hermetic tests for harness/muse-gate-shim.py (GitHub #1715).

The build gate's CLI vehicle is a shipped repo file, so it gets shipped
tests. Fixtures simulate the swap proxy + echo origin without mitmproxy or
the real muse CLI, mirroring harness/test_probe.py's wire contract
(EchoHandler is the same record shape as harness/echo-fixture.py; the
swap proxy rewrites the placeholder exactly like the inference proxy's
resolve step).

The headline test runs the REAL harness-auth-probe in gate mode with
PROBE_MUSE_BIN pointing at the REAL shipped shim -- the exact scenario
#1715 proved impossible before (probe demanded the baked real CLI the
recipe deliberately omits).
"""

import hashlib
import http.client
import json
import os
import subprocess
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SHIM = os.path.join(HERE, "muse-gate-shim.py")
PROBE = os.path.join(HERE, "harness-auth-probe")
ECHO_FIXTURE = os.path.join(HERE, "echo-fixture.py")

PLACEHOLDER = "hsurr:gate-dummy"
SWAPPED = "DUMMY-SWAPPED-PUBLIC"


class _EchoHandler(BaseHTTPRequestHandler):
    """Same record shape as harness/echo-fixture.py (kept in lockstep)."""
    log_path = None
    status = 200

    def _handle(self):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        length = max(length, 0)
        body = self.rfile.read(length) if length else b""
        headers = {}
        for name, value in self.headers.items():
            key = name.lower()
            headers[key] = headers[key] + ", " + value if key in headers else value
        rec = {
            "method": self.command,
            "path": self.path,
            "authorization": self.headers.get("Authorization", ""),
            "headers": headers,
            "body_sha256": hashlib.sha256(body).hexdigest() if body else "",
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        data = b"{}"
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = _handle
    do_POST = _handle

    def log_message(self, *a):
        pass


class _RedirectEcho(_EchoHandler):
    """302s to the redirect target -- the shim must NOT follow."""
    redirect_to = None
    seen = 0

    def do_POST(self):
        type(self).seen += 1
        self.send_response(302)
        self.send_header("Location", self.redirect_to)
        self.send_header("Content-Length", "0")
        self.end_headers()


class _SinkHandler(BaseHTTPRequestHandler):
    seen = 0

    def do_POST(self):
        type(self).seen += 1
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


class _SwapProxy(BaseHTTPRequestHandler):
    """Minimal forward proxy: swap mode rewrites the placeholder (the
    inference proxy's job); every request is forwarded origin-form."""
    swap = True
    seen_auths = []

    def _handle(self):
        parts = urlsplit(self.path)  # absolute URI from the client
        target_host, target_port = parts.hostname, parts.port or 80
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        length = max(length, 0)
        body = self.rfile.read(length) if length else None
        headers = {}
        for k, v in self.headers.items():
            if k.lower() in ("host", "proxy-connection", "connection"):
                continue
            if k.lower() == "authorization" and self.swap:
                v = v.replace(f"Bearer {PLACEHOLDER}", f"Bearer {SWAPPED}")
            headers[k] = headers[k] + ", " + v if k in headers else v
        headers["Host"] = parts.netloc
        target = parts.path or "/"
        if parts.query:
            target += "?" + parts.query
        type(self).seen_auths.append(self.headers.get("Authorization", ""))
        conn = http.client.HTTPConnection(target_host, target_port, timeout=5)
        conn.request(self.command, target, body=body, headers=headers)
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


class _DenyHandler(BaseHTTPRequestHandler):
    """confirmd's own 403 denial shape (GitHub #160), lockstep with the
    contract harness-auth-probe asserts."""
    server_version = "confirmd/1"
    reason = "self-peer"

    def do_GET(self):
        body = ("forbidden: %s\n" % self.reason).encode()
        self.send_response(403)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _serve(handler_cls, **attrs):
    for attr, val in attrs.items():
        setattr(handler_cls, attr, val)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.fixture()
def lane(tmp_path):
    """swap proxy + echo origin + child-env for the shim."""
    echo_log = tmp_path / "echo.log"
    echo_log.write_text("")
    _SwapProxy.seen_auths = []
    echo = _serve(_EchoHandler, log_path=str(echo_log))
    proxy = _serve(_SwapProxy)
    env = dict(os.environ)
    env.update({
        "META_API_KEY": PLACEHOLDER,
        "HTTPS_PROXY": "http://127.0.0.1:%d" % proxy.server_address[1],
        "HTTP_PROXY": "http://127.0.0.1:%d" % proxy.server_address[1],
        "https_proxy": "http://127.0.0.1:%d" % proxy.server_address[1],
        "http_proxy": "http://127.0.0.1:%d" % proxy.server_address[1],
    })
    env.pop("NO_PROXY", None)
    env.pop("no_proxy", None)
    yield env, echo, proxy, echo_log
    echo.shutdown()
    proxy.shutdown()


def _run_shim(env, args, stdin_data=None, timeout=20):
    return subprocess.run(
        [sys.executable, SHIM] + args,
        stdin=subprocess.DEVNULL if stdin_data is None else None,
        input=stdin_data,
        capture_output=True, text=True, timeout=timeout, env=env,
    )


def _shim_args(echo):
    return ["exec", "--provider", "meta",
            "--base-url", "http://127.0.0.1:%d" % echo.server_address[1],
            "--reasoning-effort", "minimal", "ping"]


def _records(echo_log):
    with open(echo_log) as f:
        return [json.loads(line) for line in f if line.strip()]


def test_shim_happy_path(lane):
    env, echo, proxy, echo_log = lane
    p = _run_shim(env, _shim_args(echo))
    assert p.returncode == 0, p.stderr
    recs = _records(echo_log)
    assert len(recs) == 1, recs
    rec = recs[0]
    # Through the proxy: the origin saw the SWAPPED value, and the proxy
    # observed the raw placeholder on the wire (the swap it must perform).
    assert rec["method"] == "POST"
    assert rec["path"] == "/responses"
    assert rec["authorization"] == "Bearer " + SWAPPED
    assert _SwapProxy.seen_auths == ["Bearer " + PLACEHOLDER]
    # The placeholder reaches no other recorded field (GitHub #157 class).
    blob = json.dumps(rec)
    assert PLACEHOLDER not in blob.replace("Bearer " + SWAPPED, "")
    # Body is the static shape: no env-derived content.
    assert rec["body_sha256"] == hashlib.sha256(
        json.dumps({"input": "ping"}).encode()).hexdigest()


def test_shim_never_reads_stdin(lane):
    env, echo, proxy, echo_log = lane
    # Even with the placeholder on stdin, it must not reach the request --
    # neither the body nor any header.
    p = _run_shim(env, _shim_args(echo),
                  stdin_data="META_API_KEY=" + PLACEHOLDER + "\n")
    assert p.returncode == 0, p.stderr
    recs = _records(echo_log)
    assert len(recs) == 1
    assert recs[0]["body_sha256"] == hashlib.sha256(
        json.dumps({"input": "ping"}).encode()).hexdigest()
    assert recs[0]["authorization"] == "Bearer " + SWAPPED


def test_shim_missing_key_fails_closed(lane):
    env, echo, proxy, echo_log = lane
    env = dict(env)
    del env["META_API_KEY"]
    p = _run_shim(env, _shim_args(echo))
    assert p.returncode == 2
    assert _records(echo_log) == []


def test_shim_non_placeholder_key_fails_closed(lane):
    env, echo, proxy, echo_log = lane
    env = dict(env)
    env["META_API_KEY"] = "a-real-looking-key"
    p = _run_shim(env, _shim_args(echo))
    assert p.returncode == 2
    assert "a-real-looking-key" not in p.stderr  # never echoed
    assert _records(echo_log) == []


def test_shim_proxy_bypass_fails_closed(lane):
    env, echo, proxy, echo_log = lane
    env = dict(env)
    env["NO_PROXY"] = "127.0.0.1"
    p = _run_shim(env, _shim_args(echo))
    assert p.returncode == 2
    assert _records(echo_log) == []


def test_shim_missing_proxy_env_fails_closed(lane):
    # B1 (#1715 Security): absent proxy env must not become a silent
    # direct connect that exits 0 -- the vehicle only ever proves the
    # path THROUGH the swapping proxy.
    env, echo, proxy, echo_log = lane
    env = dict(env)
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        env.pop(var, None)
    p = _run_shim(env, _shim_args(echo))
    assert p.returncode == 2
    assert _records(echo_log) == []


def test_shim_request_method_env_cannot_defeat_proxy(lane):
    # B1 (#1715 Security): urllib's ambient discovery pops the uppercase
    # HTTP_PROXY entry when REQUEST_METHOD is set (CVE-2016-1000110 CGI
    # rule); with no lowercase http_proxy to re-add it, an empty
    # ProxyHandler() silently connects DIRECT and exits 0 -- certifying
    # a swap path it never used. The pinned proxies dict reads HTTP_PROXY
    # explicitly, so routing stays through the swapping proxy.
    env, echo, proxy, echo_log = lane
    env = dict(env)
    for var in ("HTTPS_PROXY", "https_proxy", "http_proxy"):
        env.pop(var, None)  # uppercase HTTP_PROXY only, like a CGI-ish env
    env["REQUEST_METHOD"] = "GET"
    _SwapProxy.seen_auths = []
    p = _run_shim(env, _shim_args(echo))
    assert p.returncode == 0, p.stderr
    recs = _records(echo_log)
    assert len(recs) == 1
    assert recs[0]["authorization"] == "Bearer " + SWAPPED
    assert _SwapProxy.seen_auths == ["Bearer " + PLACEHOLDER]


def test_shim_wrong_argv_fails_closed(lane):
    env, echo, proxy, echo_log = lane
    base = "http://127.0.0.1:%d" % echo.server_address[1]
    for args in (
        ["chat", "ping"],                                # wrong subcommand
        ["exec", "--provider", "meta", "ping"],         # missing --base-url
        ["exec", "--provider", "meta", "--base-url", base,
         "--reasoning-effort", "minimal"],              # missing prompt
        ["exec", "--provider", "anthropic", "--base-url", base,
         "--reasoning-effort", "minimal", "ping"],      # wrong provider
        ["exec", "--provider", "meta", "--base-url", base,
         "--reasoning-effort", "minimal", "ping", "extra"],  # extra positional
        ["exec", "--provider", "meta", "--base-url", base,
         "--reasoning-effort", "minimal", "ping", "--evil"],  # extra flag
        ["exec", "--provider", "meta", "--base-url", base,
         "--reasoning-effort", "maximal", "ping"],  # wrong effort value
        ["exec", "--provider", "meta", "--base-url", base,
         "--reasoning-effort", "minimal", "ping", "--"],  # trailing flag
    ):
        p = _run_shim(env, args)
        assert p.returncode == 2, (args, p.returncode, p.stderr)
    assert _records(echo_log) == []


def test_shim_non_2xx_fails_closed(lane):
    env, echo, proxy, echo_log = lane
    echo.shutdown()
    broken = _serve(_EchoHandler, log_path=str(echo_log), status=500)
    try:
        p = _run_shim(env, ["exec", "--provider", "meta",
                            "--base-url", "http://127.0.0.1:%d"
                            % broken.server_address[1],
                            "--reasoning-effort", "minimal", "ping"])
        assert p.returncode == 3
    finally:
        broken.shutdown()


def test_shim_redirect_fails_closed(lane):
    env, echo, proxy, echo_log = lane
    sink = _serve(_SinkHandler)
    try:
        _RedirectEcho.seen = 0
        _SinkHandler.seen = 0
        redirector = _serve(_RedirectEcho, log_path=str(echo_log),
                            redirect_to="http://127.0.0.1:%d/captured"
                            % sink.server_address[1])
        try:
            p = _run_shim(env, ["exec", "--provider", "meta",
                                "--base-url", "http://127.0.0.1:%d"
                                % redirector.server_address[1],
                                "--reasoning-effort", "minimal", "ping"])
            assert p.returncode == 3
            assert _RedirectEcho.seen == 1
            assert _SinkHandler.seen == 0, "shim followed a redirect"
        finally:
            redirector.shutdown()
    finally:
        sink.shutdown()


def test_probe_gate_with_shipped_shim_end_to_end(tmp_path):
    """#1715's headline: the REAL probe in gate mode, driven by the REAL
    shipped shim through a swapping proxy -- exit 0, the exact scenario
    that was impossible before (probe demanded the baked real CLI)."""
    echo_log = tmp_path / "echo.log"
    echo_log.write_text("")
    _SwapProxy.seen_auths = []
    echo = _serve(_EchoHandler, log_path=str(echo_log))
    proxy = _serve(_SwapProxy)
    confirmd = _serve(_DenyHandler)
    env = dict(os.environ)
    env.update({
        "PROBE_MODE": "gate",
        "PROBE_BASE_URL": "http://127.0.0.1:%d" % echo.server_address[1],
        "PROBE_ECHO_LOG": str(echo_log),
        "PROBE_EXPECTED_SWAPPED": SWAPPED,
        "PROBE_KEY_NAME": "gate-dummy",
        "PROBE_PROXY": "http://127.0.0.1:%d" % proxy.server_address[1],
        "PROBE_MUSE_BIN": SHIM,  # the installer sets this; assert it works
        "PROBE_CONFIRMD_URL": "http://127.0.0.1:%d"
                               % confirmd.server_address[1],
    })
    try:
        p = subprocess.run([sys.executable, PROBE],
                           stdin=subprocess.DEVNULL,
                           capture_output=True, text=True,
                           timeout=30, env=env)
        assert p.returncode == 0, p.stderr
        recs = _records(echo_log)
        assert len(recs) == 1
        assert recs[0]["authorization"] == "Bearer " + SWAPPED
    finally:
        echo.shutdown()
        proxy.shutdown()
        confirmd.shutdown()
