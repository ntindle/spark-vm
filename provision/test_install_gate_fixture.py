"""Hermetic tests for provision/install-gate-fixture.sh.

The installer ships test seams for exactly this purpose
(CRED_STORE_SET_INFERENCE, CRED_REGISTRY_SET_INFERENCE,
INFERENCE_HOSTS_ALLOW, SUDO_PREFIX, HARNESS_GATE_ECHO_HOST), so the suite
exercises them: fake writer executables, an empty sudo prefix, a temp
hosts.allow, and the same stub proxy/echo/confirmd servers as the probe
suite. The installer passes HARNESS_INFERENCE_PROXY and
HARNESS_CONFIRMD_URL through to the probe, so the stubs work unchanged.

Nothing here touches the live credential store, registry, or hosts file.
"""

import json
import os
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

INSTALLER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "install-gate-fixture.sh")

# The public dummy the installer must install. Keep in sync with
# FIXTURE_DUMMY in install-gate-fixture.sh.
INSTALLER_DUMMY = "GATE-FIXTURE-DUMMY-NOT-A-SECRET"


class _EchoHandler(BaseHTTPRequestHandler):
    """Echoes received request headers back as JSON (the gate fixture)."""

    def do_GET(self):
        body = json.dumps(
            {"headers": {k: v for k, v in self.headers.items()}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class _SwapProxyHandler(BaseHTTPRequestHandler):
    """Loopback forward proxy swapping the placeholder Bearer header."""

    echo_port = None
    placeholder = "hsurr:llm-api"

    def do_GET(self):
        # self.path is the absolute URI for proxy requests.
        target = urllib.parse.urlsplit(self.path)
        auth = self.headers.get("Authorization")
        if auth == "Bearer " + self.placeholder:
            auth = "Bearer " + INSTALLER_DUMMY
        fwd = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.echo_port, target.path or "/"),
            headers={"Authorization": auth},
            method="GET",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(fwd, timeout=10) as resp:
                body = resp.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:  # noqa: BLE001 -- stub only
            self.send_error(502, str(e))

    def log_message(self, *a):
        pass


class _ConfirmdHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"error":"forbidden"}'
        self.send_response(403)
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
def stack(tmp_path):
    """Fake writers + temp hosts.allow + stub servers. Yields the env."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    store_file = tmp_path / "cred-store.txt"
    registry_file = tmp_path / "registry.txt"
    allow_file = tmp_path / "inference-hosts.allow"

    # Fake narrow writer: store writer reads the value on stdin.
    (bin_dir / "fake-store-writer").write_text(
        "#!/bin/sh\ncat > \"$FAKE_STORE_FILE\"\n")
    # Fake registry writer: appends "verb args..." lines.
    (bin_dir / "fake-registry-writer").write_text(
        "#!/bin/sh\necho \"$*\" >> \"$FAKE_REGISTRY_FILE\"\n")
    for f in ("fake-store-writer", "fake-registry-writer"):
        os.chmod(bin_dir / f, 0o755)

    echo = _serve(_EchoHandler)
    confirmd = _serve(_ConfirmdHandler)
    proxy = _serve(_SwapProxyHandler, echo_port=echo.server_address[1])

    env = dict(os.environ)
    env.update({
        "CRED_STORE_SET_INFERENCE": str(bin_dir / "fake-store-writer"),
        "CRED_REGISTRY_SET_INFERENCE": str(bin_dir / "fake-registry-writer"),
        "INFERENCE_HOSTS_ALLOW": str(allow_file),
        "SUDO_PREFIX": "",
        "HARNESS_GATE_ECHO_HOST": "echo-fixture.invalid",
        "HARNESS_INFERENCE_PROXY":
            "http://127.0.0.1:%d" % proxy.server_address[1],
        "HARNESS_CONFIRMD_URL":
            "http://127.0.0.1:%d" % confirmd.server_address[1],
        "FAKE_STORE_FILE": str(store_file),
        "FAKE_REGISTRY_FILE": str(registry_file),
        # The stub proxy forwards to 127.0.0.1 directly, so any ambient
        # HTTP(S)_PROXY must not apply inside the test process's children.
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    })
    yield env, store_file, registry_file, allow_file
    proxy.shutdown()
    echo.shutdown()
    confirmd.shutdown()


def _run_installer(env):
    return subprocess.run(
        ["bash", INSTALLER],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        env=env,
    )


def test_installer_happy_path(stack):
    env, store_file, registry_file, allow_file = stack
    proc = _run_installer(env)
    assert proc.returncode == 0, proc.stderr.decode()
    # Store writer received exactly the public dummy on stdin.
    assert store_file.read_text() == INSTALLER_DUMMY
    # Registry writer saw the placement registration and the host bind.
    lines = registry_file.read_text().splitlines()
    # The placement value carries its double quotes verbatim, per the
    # registry writer's own protocol.
    assert 'set llm-api access_token "bearer_header"' in lines
    assert "add-host llm-api echo-fixture.invalid" in lines
    # Host allowlisted exactly once.
    assert allow_file.read_text().splitlines() == ["echo-fixture.invalid"]


def test_installer_idempotent(stack):
    env, store_file, registry_file, allow_file = stack
    assert _run_installer(env).returncode == 0
    assert _run_installer(env).returncode == 0
    # Second run must not duplicate the host entry.
    assert allow_file.read_text().splitlines() == ["echo-fixture.invalid"]


def test_installer_missing_writer_fails(stack):
    env, store_file, registry_file, allow_file = stack
    env["CRED_STORE_SET_INFERENCE"] = "/nonexistent/writer"
    proc = _run_installer(env)
    assert proc.returncode == 2
    assert b"CRED_STORE_SET_INFERENCE" in proc.stderr


def test_installer_probe_failure_propagates(stack):
    env, store_file, registry_file, allow_file = stack
    # Point the probe at a dead proxy: the fixture writes succeed, but the
    # final verification must fail the install.
    env["HARNESS_INFERENCE_PROXY"] = "http://127.0.0.1:9"
    proc = _run_installer(env)
    assert proc.returncode != 0
