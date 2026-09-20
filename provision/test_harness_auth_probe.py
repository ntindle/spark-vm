#!/usr/bin/env python3
"""Hermetic tests for provision/harness-auth-probe.

No live services, no network, no real credentials: every test stands up
stub servers on loopback (a swapping forward proxy, an echo server, a
confirmd stand-in) and runs the probe against them with stdin closed.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "harness-auth-probe")
PLACEHOLDER = "hsurr:llm-api"
# The stub proxy's stand-in for the swapped-in credential. This MUST be the
# same value install-gate-fixture.sh installs (FIXTURE_DUMMY there) -- the
# dummy is public by design, and the two files drift silently if the values
# ever diverge. (The probe itself only ever sees the placeholder name.)
FIXTURE_DUMMY = "GATE-FIXTURE-DUMMY-NOT-A-SECRET"


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _EchoHandler(BaseHTTPRequestHandler):
    """Echoes received request headers back as JSON (the gate fixture)."""

    status_override = 200

    def do_GET(self):
        body = json.dumps(
            {"headers": {k: v for k, v in self.headers.items()}}).encode()
        self.send_response(self.status_override)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class _SwapProxyHandler(BaseHTTPRequestHandler):
    """Minimal forward proxy that swaps the placeholder Bearer header,
    mimicking the inference proxy's bearer_header placement, then
    forwards to the echo server."""

    echo_port = None
    swap = True

    def do_GET(self):
        # self.path is the absolute URI for proxy requests.
        target = urllib.parse.urlsplit(self.path)
        auth = self.headers.get("Authorization")
        if self.swap and auth == "Bearer " + PLACEHOLDER:
            auth = "Bearer " + FIXTURE_DUMMY
        fwd = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.echo_port, target.path or "/"),
            headers={"Authorization": auth, "Accept": "application/json"},
            method="GET",
        )
        try:
            # Bypass any ambient HTTP(S)_PROXY: the stub forwards on
            # loopback directly, exactly like the real deployment's
            # proxy-bypass for local fixtures.
            no_proxy = urllib.request.build_opener(
                urllib.request.ProxyHandler({}))
            with no_proxy.open(fwd, timeout=5) as resp:
                status, body = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            # Relay the upstream's answer faithfully (the real proxy
            # relays upstream statuses too): a 401 here must reach the
            # probe as a 401, not a 502.
            status, body = e.code, e.read()
        except Exception as e:  # noqa: BLE001 -- test stub
            self.send_error(502, str(e))
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class _ConfirmdHandler(BaseHTTPRequestHandler):
    """Stand-in for confirmd's auth gate: answers, but refuses strangers."""

    def do_GET(self):
        if self.path == "/api/version":
            body = b'{"error":"forbidden"}'
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass


class _HangHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Never answer: exercises the probe's internal deadline.
        threading.Event().wait(30)

    def log_message(self, *a):
        pass


class _ConfigurableEchoHandler(BaseHTTPRequestHandler):
    """Echo stand-in with a canned body, for negative parse paths."""
    body = b""
    content_type = "application/json"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", self.content_type)
        self.send_header("Content-Length", str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *a):
        pass


class _ConfirmdStatusHandler(BaseHTTPRequestHandler):
    """confirmd stand-in answering any configured status."""
    status = 200

    def do_GET(self):
        body = b'{"error":"boom"}' if self.status >= 500 else b'{"version":"x"}'
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _serve(handler_cls, **attrs):
    for k, v in attrs.items():
        setattr(handler_cls, k, v)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


@pytest.fixture()
def echo():
    srv = _serve(_EchoHandler)
    yield srv
    srv.shutdown()


@pytest.fixture()
def confirmd():
    srv = _serve(_ConfirmdHandler)
    yield srv
    srv.shutdown()


def _run_probe(env_extra):
    env = dict(os.environ)
    env.update(env_extra)
    # The harness contract: stdin closed.
    proc = subprocess.run(
        [sys.executable, PROBE],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        env=env,
    )
    try:
        report = json.loads(proc.stdout.decode())
    except ValueError:
        report = None
    return proc, report


def _base_env(echo, confirmd, proxy_port):
    return {
        "HARNESS_INFERENCE_PROXY": "http://127.0.0.1:%d" % proxy_port,
        "HARNESS_PROBE_UPSTREAM": "http://127.0.0.1:%d" % echo.server_address[1],
        "HARNESS_PROBE_PATH": "/headers",
        "HARNESS_CONFIRMD_URL": "http://127.0.0.1:%d" % confirmd.server_address[1],
    }


def test_all_green(echo, confirmd):
    proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=True)
    try:
        proc, report = _run_probe(_base_env(echo, confirmd, proxy.server_address[1]))
    finally:
        proxy.shutdown()
    assert proc.returncode == 0, proc.stderr.decode()
    assert report["ok"] is True
    assert report["checks"]["inference"]["ok"] is True
    assert report["checks"]["inference"]["detail"]["swapped_authorization_seen"] is True
    assert report["checks"]["confirmd"]["ok"] is True
    # confirmd's 403 auth-gate answer counts as "answers"
    assert report["checks"]["confirmd"]["detail"]["status"] == 403


def test_https_confirmd_unverified_tls(echo, confirmd):
    pytest.importorskip("cryptography")
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import datetime
    import ssl
    import tempfile

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "probe-test")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    with tempfile.NamedTemporaryFile(
            suffix=".pem", delete=False) as kf, tempfile.NamedTemporaryFile(
            suffix=".pem", delete=False) as cf:
        kf.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))
        cf.write(cert.public_bytes(serialization.Encoding.PEM))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cf.name, kf.name)
    # Wrapping after serve_forever started is benign: it replaces the
    # listening socket object in place (same fd, selector unaffected) and
    # no connection can exist yet -- the probe only runs below.
    confirmd.socket = ctx.wrap_socket(confirmd.socket, server_side=True)
    try:
        proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=True)
        try:
            env = _base_env(echo, confirmd, proxy.server_address[1])
            env["HARNESS_CONFIRMD_URL"] = "https://127.0.0.1:%d" % confirmd.server_address[1]
            proc, report = _run_probe(env)
        finally:
            proxy.shutdown()
    finally:
        os.unlink(kf.name)
        os.unlink(cf.name)
    assert proc.returncode == 0, proc.stderr.decode()
    assert report["checks"]["confirmd"]["ok"] is True


def test_proxy_down_fails_inference(echo, confirmd):
    dead_port = _free_port()
    proc, report = _run_probe(_base_env(echo, confirmd, dead_port))
    assert proc.returncode == 1
    assert report["ok"] is False
    assert report["checks"]["inference"]["ok"] is False
    assert report["checks"]["confirmd"]["ok"] is True


def test_unswapped_placeholder_fails(echo, confirmd):
    proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=False)
    try:
        proc, report = _run_probe(_base_env(echo, confirmd, proxy.server_address[1]))
    finally:
        proxy.shutdown()
    assert proc.returncode == 1
    detail = report["checks"]["inference"]["detail"]
    assert report["checks"]["inference"]["ok"] is False
    assert "UNSWAPPED" in detail.get("error", "")


def test_confirmd_down_fails_check(echo):
    proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=True)
    try:
        env = {
            "HARNESS_INFERENCE_PROXY": "http://127.0.0.1:%d" % proxy.server_address[1],
            "HARNESS_PROBE_UPSTREAM": "http://127.0.0.1:%d" % echo.server_address[1],
            "HARNESS_PROBE_PATH": "/headers",
            "HARNESS_CONFIRMD_URL": "http://127.0.0.1:%d" % _free_port(),
        }
        proc, report = _run_probe(env)
    finally:
        proxy.shutdown()
    assert proc.returncode == 1
    assert report["checks"]["inference"]["ok"] is True
    assert report["checks"]["confirmd"]["ok"] is False


def test_auth_accepted_mode(echo, confirmd):
    proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=True)
    try:
        env = _base_env(echo, confirmd, proxy.server_address[1])
        env["HARNESS_PROBE_EXPECT"] = "auth-accepted"
        # /headers returns 200 through the echo stub: not 401/403 => pass.
        proc, report = _run_probe(env)
        assert proc.returncode == 0, proc.stderr.decode()
        assert report["checks"]["inference"]["ok"] is True

        # A 401 from the upstream means the swapped credential was refused.
        _EchoHandler.status_override = 401
        try:
            proc, report = _run_probe(env)
        finally:
            _EchoHandler.status_override = 200
        assert proc.returncode == 1
        assert "refused" in report["checks"]["inference"]["detail"]["error"]
    finally:
        proxy.shutdown()


def test_tty_stdin_refused(echo, confirmd):
    import pty
    master, slave = pty.openpty()
    try:
        proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=True)
        try:
            env = dict(os.environ)
            env.update(_base_env(echo, confirmd, proxy.server_address[1]))
            proc = subprocess.run(
                [sys.executable, PROBE],
                stdin=slave,  # a TTY: the probe must refuse
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                env=env,
            )
        finally:
            proxy.shutdown()
    finally:
        os.close(master)
        os.close(slave)
    assert proc.returncode == 2
    assert b"TTY" in proc.stderr


def test_internal_deadline(echo, confirmd):
    hang = _serve(_HangHandler)
    try:
        # The hang server stands in for the proxy itself: the probe's
        # request never gets a response, so the internal deadline must
        # fire (exit 3) well before the per-request timeout.
        env = _base_env(echo, confirmd, hang.server_address[1])
        env["HARNESS_DEADLINE_S"] = "1"
        env["HARNESS_HTTP_TIMEOUT_S"] = "25"
        proc, report = _run_probe(env)
    finally:
        hang.shutdown()
    assert proc.returncode == 3
    assert report["checks"]["deadline"]["ok"] is False


def test_confirmd_url_not_derivable_without_tailscale():
    env = {
        # No HARNESS_CONFIRMD_URL and no tailscale on PATH: fail closed.
        "PATH": "/nonexistent",
        "HARNESS_INFERENCE_PROXY": "http://127.0.0.1:9",
    }
    proc = subprocess.run(
        [sys.executable, PROBE],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        env=env,
    )
    assert proc.returncode == 2
    assert b"HARNESS_CONFIRMD_URL" in proc.stderr


def test_bad_expect_is_misuse(echo, confirmd):
    # A typo'd HARNESS_PROBE_EXPECT is bad env (exit 2), not a failed
    # check (exit 1): a harness gate branching on exit codes must not
    # misclassify a config typo.
    proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=True)
    try:
        env = _base_env(echo, confirmd, proxy.server_address[1])
        env["HARNESS_PROBE_EXPECT"] = "ECHO"
        proc, _ = _run_probe(env)
    finally:
        proxy.shutdown()
    assert proc.returncode == 2
    assert b"HARNESS_PROBE_EXPECT" in proc.stderr


def test_bad_probe_path_is_misuse(echo, confirmd):
    # "headers" without a leading slash would build
    # "http://host:portheaders" and fail opaquely -- refuse loudly.
    proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=True)
    try:
        env = _base_env(echo, confirmd, proxy.server_address[1])
        env["HARNESS_PROBE_PATH"] = "headers"
        proc, _ = _run_probe(env)
    finally:
        proxy.shutdown()
    assert proc.returncode == 2
    assert b"HARNESS_PROBE_PATH" in proc.stderr


def test_closed_stdout_is_misuse(echo, confirmd):
    # Closed stdout must not produce a traceback with a misleading
    # exit code: fail loud as misuse (exit 2).
    def _close_stdout():
        os.close(1)

    proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=True)
    try:
        env = dict(os.environ)
        env.update(_base_env(echo, confirmd, proxy.server_address[1]))
        proc = subprocess.run(
            [sys.executable, PROBE],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,  # closed in the child by preexec_fn
            stderr=subprocess.PIPE,
            timeout=30,
            env=env,
            preexec_fn=_close_stdout,
        )
    finally:
        proxy.shutdown()
    assert proc.returncode == 2
    assert b"Traceback" not in proc.stderr
    assert b"stdout" in proc.stderr


def test_closed_stdin_proceeds(echo, confirmd):
    # Closed stdin (0<&-) is in-contract: it is not a TTY, so the probe
    # must run to completion, not crash on sys.stdin.isatty().
    def _close_stdin():
        os.close(0)

    proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1], swap=True)
    try:
        env = dict(os.environ)
        env.update(_base_env(echo, confirmd, proxy.server_address[1]))
        proc = subprocess.run(
            [sys.executable, PROBE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            env=env,
            preexec_fn=_close_stdin,
        )
    finally:
        proxy.shutdown()
    assert proc.returncode == 0, proc.stderr.decode()
    assert b"Traceback" not in proc.stderr


def test_echo_html_body_fails(echo, confirmd):
    html_echo = _serve(_ConfigurableEchoHandler,
                       body=b"<html>not json</html>",
                       content_type="text/html")
    try:
        proxy = _serve(_SwapProxyHandler,
                       echo_port=html_echo.server_address[1], swap=True)
        try:
            env = _base_env(echo, confirmd, proxy.server_address[1])
            proc, report = _run_probe(env)
        finally:
            proxy.shutdown()
    finally:
        html_echo.shutdown()
    assert proc.returncode == 1
    assert "did not return JSON" in report["checks"]["inference"]["detail"]["error"]


def test_echo_missing_headers_key_fails(echo, confirmd):
    json_echo = _serve(_ConfigurableEchoHandler, body=b'{"ok":true}')
    try:
        proxy = _serve(_SwapProxyHandler,
                       echo_port=json_echo.server_address[1], swap=True)
        try:
            env = _base_env(echo, confirmd, proxy.server_address[1])
            proc, report = _run_probe(env)
        finally:
            proxy.shutdown()
    finally:
        json_echo.shutdown()
    assert proc.returncode == 1
    # A JSON body with no "headers" key means no Authorization was seen.
    assert "saw no Authorization header" in report["checks"]["inference"]["detail"]["error"]


def test_confirmd_500_fails_check(echo, confirmd):
    # 5xx is "alive but broken": the approvals path is not up.
    broken = _serve(_ConfirmdStatusHandler, status=500)
    try:
        proxy = _serve(_SwapProxyHandler,
                       echo_port=echo.server_address[1], swap=True)
        try:
            env = _base_env(echo, confirmd, proxy.server_address[1])
            env["HARNESS_CONFIRMD_URL"] = "http://127.0.0.1:%d" % broken.server_address[1]
            proc, report = _run_probe(env)
        finally:
            proxy.shutdown()
    finally:
        broken.shutdown()
    assert proc.returncode == 1
    assert report["checks"]["inference"]["ok"] is True
    assert report["checks"]["confirmd"]["ok"] is False
    assert "not healthy" in report["checks"]["confirmd"]["detail"]["error"]
