"""Hermetic tests for harness/install-gate-fixture.sh.

The installer ships test seams for exactly this purpose
(CRED_STORE_SET_INFERENCE, CRED_REGISTRY_SET_INFERENCE,
INFERENCE_HOSTS_ALLOW, SUDO_PREFIX, HARNESS_GATE_ECHO_LOG): fake writer
executables, an empty sudo prefix, a temp hosts.allow, and a temp echo
log. The installer starts the REAL harness/echo-fixture.py and runs the
REAL harness/harness-auth-probe in gate mode; the only fakes are the
muse CLI vehicle (PROBE_MUSE_BIN, honoring the probe's child-env
contract) and the swap proxy (swapping hsurr:gate-dummy like the real
one), plus a stub confirmd. The happy-path assertion on the echo log
proves the swapped credential reached the origin end to end.

Nothing here touches the live credential store, registry, or hosts file.
"""

import json
import os
import subprocess
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALLER = os.path.join(HERE, "install-gate-fixture.sh")

# The public dummy the installer must install. Keep in sync with
# FIXTURE_DUMMY in install-gate-fixture.sh.
INSTALLER_DUMMY = "GATE-FIXTURE-DUMMY-NOT-A-SECRET"
KEY_NAME = "gate-dummy"
PLACEHOLDER = "hsurr:" + KEY_NAME

# Fake muse CLI vehicle: honors the canonical probe's child-env contract
# (META_API_KEY placeholder, forced proxy env) and sends one GET through
# the proxy carrying the placeholder Bearer header, like the real CLI.
FAKE_MUSE = """#!/usr/bin/env python3
import os, sys, urllib.request
base = None
for i, a in enumerate(sys.argv):
    if a == "--base-url" and i + 1 < len(sys.argv):
        base = sys.argv[i + 1]
proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
placeholder = os.environ.get("META_API_KEY", "")
req = urllib.request.Request(
    base.rstrip("/") + "/", method="GET",
    headers={"Authorization": "Bearer " + placeholder})
opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
try:
    with opener.open(req, timeout=5) as resp:
        resp.read()
except Exception as e:  # noqa: BLE001 -- stub only
    sys.stderr.write("fake-muse: %r\\n" % (e,))
    sys.exit(3)
sys.exit(0)
"""


class _SwapProxyHandler(BaseHTTPRequestHandler):
    """Loopback forward proxy swapping the placeholder Bearer header.

    swap=False simulates a broken swap (the placeholder reaches the
    origin unswapped): the probe's wire-shape assertion must fail.
    """

    swap = True

    def do_GET(self):
        # self.path is the absolute URI for proxy requests.
        target = urllib.parse.urlsplit(self.path)
        auth = self.headers.get("Authorization")
        if self.swap and auth == "Bearer " + PLACEHOLDER:
            auth = "Bearer " + INSTALLER_DUMMY
        fwd = urllib.request.Request(
            "http://%s%s" % (target.netloc, target.path or "/"),
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
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
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
    """Fake writers + temp hosts.allow/log + stub proxy/confirmd + fake muse."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    store_file = tmp_path / "cred-store.txt"
    registry_file = tmp_path / "registry.txt"
    allow_file = tmp_path / "inference-hosts.allow"
    echo_log = tmp_path / "echo.log"

    # Fake narrow writer: store writer reads the value on stdin.
    (bin_dir / "fake-store-writer").write_text(
        "#!/bin/sh\ncat > \"$FAKE_STORE_FILE\"\n")
    # Fake registry writer: appends "verb args..." lines.
    (bin_dir / "fake-registry-writer").write_text(
        "#!/bin/sh\necho \"$*\" >> \"$FAKE_REGISTRY_FILE\"\n")
    # Fake muse CLI vehicle honoring the probe's child-env contract.
    (bin_dir / "fake-muse").write_text(FAKE_MUSE)
    for f in ("fake-store-writer", "fake-registry-writer", "fake-muse"):
        os.chmod(bin_dir / f, 0o755)

    proxy = _serve(_SwapProxyHandler, swap=True)
    confirmd = _serve(_ConfirmdHandler)

    env = dict(os.environ)
    env.update({
        "CRED_STORE_SET_INFERENCE": str(bin_dir / "fake-store-writer"),
        "CRED_REGISTRY_SET_INFERENCE": str(bin_dir / "fake-registry-writer"),
        "INFERENCE_HOSTS_ALLOW": str(allow_file),
        "SUDO_PREFIX": "",
        "HARNESS_GATE_ECHO_LOG": str(echo_log),
        "PROBE_PROXY": "http://127.0.0.1:%d" % proxy.server_address[1],
        "PROBE_MUSE_BIN": str(bin_dir / "fake-muse"),
        "PROBE_CONFIRMD_URL":
            "http://127.0.0.1:%d" % confirmd.server_address[1],
        "FAKE_STORE_FILE": str(store_file),
        "FAKE_REGISTRY_FILE": str(registry_file),
        # PATH must not leak a real `muse` anywhere; the probe takes the
        # absolute fake path, but keep the seam honest anyway.
        "PATH": str(bin_dir) + ":/usr/bin:/bin",
    })
    yield env, store_file, registry_file, allow_file, echo_log, proxy
    proxy.shutdown()
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
    env, store_file, registry_file, allow_file, echo_log, _proxy = stack
    proc = _run_installer(env)
    assert proc.returncode == 0, proc.stderr.decode()
    # Store writer received exactly the public dummy on stdin.
    assert store_file.read_text() == INSTALLER_DUMMY
    # Registry writer saw the placement registration and the host bind.
    lines = registry_file.read_text().splitlines()
    # The placement value carries its double quotes verbatim, per the
    # registry writer's own protocol.
    assert 'set gate-dummy access_token "bearer_header"' in lines
    assert "add-host gate-dummy 127.0.0.1" in lines
    # Echo host allowlisted exactly once.
    assert allow_file.read_text().splitlines() == ["127.0.0.1"]
    # The swapped credential reached the echo origin: end-to-end proof
    # the installer wired the fixture correctly.
    records = [json.loads(l) for l in echo_log.read_text().splitlines()
               if l.strip()]
    assert records, "echo log is empty: no request reached the fixture"
    assert all(r["authorization"] == "Bearer " + INSTALLER_DUMMY
               for r in records)
    assert not any(PLACEHOLDER in r["authorization"] for r in records)


def test_installer_idempotent(stack):
    env, store_file, registry_file, allow_file, echo_log, _proxy = stack
    assert _run_installer(env).returncode == 0
    assert _run_installer(env).returncode == 0
    # Second run must not duplicate the host entry.
    assert allow_file.read_text().splitlines() == ["127.0.0.1"]


def test_installer_missing_writer_fails(stack):
    env, *_ = stack
    env["CRED_STORE_SET_INFERENCE"] = "/nonexistent/writer"
    proc = _run_installer(env)
    assert proc.returncode == 2
    assert b"CRED_STORE_SET_INFERENCE" in proc.stderr


def test_installer_missing_echo_fixture_fails(stack):
    env, *_ = stack
    env["ECHO_FIXTURE"] = "/nonexistent/echo-fixture.py"
    proc = _run_installer(env)
    assert proc.returncode == 2
    assert b"ECHO_FIXTURE" in proc.stderr


def test_installer_probe_failure_propagates(stack):
    env, store_file, registry_file, allow_file, echo_log, proxy = stack
    # Broken swap: the placeholder reaches the origin unswapped, so the
    # probe's wire-shape assertion fails and the install must fail.
    proxy.RequestHandlerClass.swap = False
    try:
        proc = _run_installer(env)
    finally:
        proxy.RequestHandlerClass.swap = True
    assert proc.returncode != 0
    # The fixture writes still happened (the failure is the verification,
    # not the install).
    assert store_file.read_text() == INSTALLER_DUMMY
