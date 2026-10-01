"""Hermetic tests for harness/harness-auth-probe.

Fixtures simulate the three external actors without mitmproxy or the real
muse CLI:
  - fake `muse` CLI (a python script): honors the probe's child-env contract
    (META_API_KEY placeholder, proxy env forced, NO_PROXY stripped), sends
    GET+POST with an Authorization header through the proxy, exits per
    FAKE_MUSE_MODE.
  - echo server: records the full request it receives (method, raw path,
    full header set, sha256 of the body) to a JSONL log — the same wire
    contract as harness/echo-fixture.py; the probe asserts the swapped
    Authorization shape and that the hsurr: placeholder reached no
    recorded field (GitHub #157).
  - swap proxy: minimal forward HTTP proxy; in "swap" mode rewrites
    "Bearer hsurr:gate-dummy" -> "Bearer <swapped>" (the proxy's job), in
    "passthrough" mode forwards untouched.
  - confirmd stub: DenyHandler answers over TLS with confirmd's own 403
    denial shape (HTTP 403 + "forbidden: <reason>" body + "confirmd/1"
    Server header), in lockstep with confirm/confirmd.py _auth/_deny;
    PROBE_CONFIRMD_URL is scheme-agnostic in tests (production uses https).

Two extra fake-muse modes pin the provision vehicle's filesystem isolation
(GitHub #156): `baked-key-only` authenticates from a baked
~/.config/muse/auth.json under HOME (the masked failure the scrubbed HOME
closes), and `dump-env` records the environment the vehicle actually ran in
so the tests can assert the scrubbed-HOME contract and the teardown.
"""

import http.client
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest

HARNESS = os.path.dirname(os.path.abspath(__file__))
PROBE = os.path.join(HARNESS, "harness-auth-probe")
PLACEHOLDER = "hsurr:gate-dummy"
SWAPPED = "DUMMY-SWAPPED-PUBLIC"

FAKE_MUSE = r'''#!/usr/bin/env python3
"""Fake muse CLI: mimics the wire contract the probe depends on."""
import os, sys, time, urllib.parse, urllib.request
mode = os.environ.get("FAKE_MUSE_MODE", "ok")
if mode == "sleep":
    time.sleep(30)
    sys.exit(0)
if mode == "hang-after-request":
    pass  # falls through to send requests, then sleeps below
if mode == "cli-fails":
    sys.exit(3)
if mode == "dump-env":
    # Observability hook for the #156 vehicle-env contract: records the
    # environment the probe actually handed the vehicle, then exits 0.
    import json as _json
    home = os.environ.get("HOME", "")
    with open(os.environ["FAKE_MUSE_ENV_DUMP"], "w") as f:
        _json.dump({
            "HOME": home,
            "XDG_CONFIG_HOME": os.environ.get("XDG_CONFIG_HOME"),
            "XDG_DATA_HOME": os.environ.get("XDG_DATA_HOME"),
            "XDG_STATE_HOME": os.environ.get("XDG_STATE_HOME"),
            "XDG_CACHE_HOME": os.environ.get("XDG_CACHE_HOME"),
            "home_exists": os.path.isdir(home),
            "home_empty": os.path.isdir(home) and not os.listdir(home),
            "META_API_KEY": os.environ.get("META_API_KEY"),
        }, f)
    sys.exit(0)
if mode == "baked-key-only":
    # GitHub #156: simulates a CLI that authenticates from a credential
    # file baked into the image (~/.config/muse/auth.json) instead of the
    # injected env placeholder. The placeholder path is broken here on
    # purpose (META_API_KEY is unset): if the vehicle can see the ambient
    # HOME, this exits 0 and the probe certifies a broken injected path.
    import json as _json
    auth = os.path.join(os.environ.get("HOME", "/nonexistent"),
                        ".config", "muse", "auth.json")
    try:
        with open(auth) as f:
            _json.load(f)["providers"]["meta"]["api_key"]
    except Exception:
        sys.exit(3)  # no baked credential visible: cannot authenticate
    sys.exit(0)      # baked credential present: the masked failure
# env contract the probe promises its child
assert os.environ.get("META_API_KEY", "").startswith("hsurr:"), "no placeholder key"
assert os.environ.get("HTTPS_PROXY", "").startswith("http://127.0.0.1"), "no proxy routing"
assert "NO_PROXY" not in os.environ and "no_proxy" not in os.environ, "bypass list present"
key = os.environ["META_API_KEY"]
argv = sys.argv
base = argv[argv.index("--base-url") + 1]
scheme = "Token " if mode == "bad-scheme" else "Bearer "
headers = {"Authorization": scheme + key, "X-Request-Id": "gate-fixture-benign"}
paths = ["/muse-code/models", "/responses"]
if mode == "duplicate":
    paths = [p for p in paths for _ in (0, 1)]  # each request twice, like CLI retries
if mode == "leak-header":
    # GitHub #157: the placeholder leaves through a second channel while
    # the Authorization header is correctly swapped — the gate must fail.
    headers["X-Api-Key"] = key
if mode == "leak-query":
    # GitHub #157: the placeholder leaves in the query string.
    paths = ["/responses?api_key=" + key]
if mode == "leak-query-encoded":
    # GitHub #157: the placeholder percent-encoded in the query string
    # (the standard urlencode output every mainstream client produces)
    # must also fail the gate.
    paths = ["/responses?api_key=" + urllib.parse.quote(key, safe="")]
if mode == "leak-dup-header":
    # GitHub #157: duplicate X-Api-Key headers, the second carrying the
    # placeholder — the fixture must join them (RFC 9110 section 5.3) so
    # the probe's scan sees the leak. urllib collapses duplicate headers,
    # so this mode drives the proxy with http.client directly.
    import http.client as _httpc
    from urllib.parse import urlsplit as _urlsplit
    _proxy = _urlsplit(os.environ.get("HTTPS_PROXY", ""))
    _target = _urlsplit(base)
    for _path in ("/muse-code/models", "/responses"):
        _conn = _httpc.HTTPConnection(_proxy.hostname, _proxy.port or 80,
                                      timeout=5)
        _conn.putrequest("POST" if _path == "/responses" else "GET",
                         base.rstrip("/") + _path,
                         skip_host=True, skip_accept_encoding=True)
        _conn.putheader("Host", _target.netloc)
        _conn.putheader("Authorization", scheme + key)
        _conn.putheader("X-Request-Id", "gate-fixture-benign")
        _conn.putheader("X-Api-Key", "benign-first")
        _conn.putheader("X-Api-Key", key)
        _body = b"{}" if _path == "/responses" else None
        if _body is not None:
            _conn.putheader("Content-Length", str(len(_body)))
        _conn.endheaders(_body)
        try:
            _conn.getresponse().read()
        except Exception:
            pass  # the fixture's body is not a completion; delivery counts
        _conn.close()
    sys.exit(0)
if mode != "no-request":
    for path in paths:
        req = urllib.request.Request(base.rstrip("/") + path, headers=headers,
                                     data=b"{}" if path == "/responses" else None)
        try:
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            pass  # the echo fixture's body is not a completion; header delivery is what counts
if mode in ("hang-after-request",):
    time.sleep(30)  # delivered valid requests, then hung: the gate must fail this
if mode == "corrupt-log":
    # Valid requests delivered, then the echo log gains a corrupt line inside
    # this run's window: the probe must fail closed, not misparse.
    with open(os.environ["PROBE_ECHO_LOG"], "a") as f:
        f.write("this is not json\n")
sys.exit(0)
'''


class EchoHandler(BaseHTTPRequestHandler):
    """Mirror of harness/echo-fixture.py's handler (same wire contract).

    Keep the two in lockstep: the fixture is what the real gate runs,
    this is what the probe's hermetic tests assert against.
    """
    log_path = None

    def _handle(self):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0  # malformed framing: still record headers/path, no body
        if length < 0:
            length = 0
        body = self.rfile.read(length) if length else b""
        headers = {}
        for name, value in self.headers.items():
            # Join duplicates per RFC 9110 section 5.3 instead of
            # first-wins: a placeholder in a second same-name header is
            # still a leak the probe must see (GitHub #157).
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
        try:  # same clamp as the record builders: never die on bad framing
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            length = 0
        length = max(length, 0)
        body = self.rfile.read(length) if length else None
        headers = {}
        for k, v in self.headers.items():
            if k.lower() in ("host", "proxy-connection", "connection"):
                continue
            if k.lower() == "authorization" and self.mode == "swap":
                v = v.replace(f"Bearer {self.placeholder}", f"Bearer {self.swapped}")
            # Join duplicates (RFC 9110 section 5.3) — dropping them would
            # hide a duplicate-header leak from the echo fixture (#157).
            headers[k] = headers[k] + ", " + v if k in headers else v
        headers["Host"] = parts.netloc
        # Forward origin-form incl. the query string (the real forward
        # proxy does; dropping it here would hide query-channel leaks —
        # GitHub #157's leak-query vehicle mode depends on this).
        target = parts.path or "/"
        if parts.query:
            target += "?" + parts.query
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


class OkHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class DenyHandler(BaseHTTPRequestHandler):
    """Mimics confirmd's own _deny contract (confirm/confirmd.py): HTTP 403,
    body "forbidden: <reason>", Server header whose first token is exactly
    "confirmd/1". The probe asserts exactly this shape (GitHub #160) — keep
    this fixture in lockstep with confirmd's _deny if that contract ever
    changes."""
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
    confirmd = serve(DenyHandler)
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


_NEUTRALIZED = ("HTTPS_PROXY", "HTTP_PROXY", "https_proxy", "http_proxy",
                "NO_PROXY", "no_proxy")


@contextmanager
def neutralized_env():
    """Pop ambient proxy/bypass vars for the duration: keep the suite
    hermetic even where the runner's env has proxies set. Never
    permanently mutates the test process env."""
    saved = {}
    for var in _NEUTRALIZED:
        if var in os.environ:
            saved[var] = os.environ.pop(var)
    try:
        yield
    finally:
        os.environ.update(saved)


def probe_env(fixtures, tmp_path, mode="gate", extra_env=None):
    """The probe's full child env (also reused by the SIGTERM test's Popen)."""
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
    if extra_env:
        env.update(extra_env)
    if mode == "provision":
        env.pop("PROBE_ECHO_LOG", None)
        env.pop("PROBE_EXPECTED_SWAPPED", None)
        env["PROBE_KEY_NAME"] = "llm-api"
    return env


def run_probe(fixtures, tmp_path, mode="gate", extra_env=None, argv_extra=(),
              stdin=None):
    """stdin=None -> subprocess.DEVNULL; otherwise the given fd is passed
    through (used by the never-reads-stdin test with an unwritten pipe)."""
    env = probe_env(fixtures, tmp_path, mode=mode, extra_env=extra_env)
    stdin = subprocess.DEVNULL if stdin is None else stdin
    t0 = time.monotonic()
    with neutralized_env():
        proc = subprocess.run(
            [sys.executable, PROBE, "--mode", mode, *argv_extra],
            env={**os.environ, **env},
            stdin=stdin,
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


def test_gate_placeholder_leak_via_header_fails(fixtures, tmp_path):
    # GitHub #157: a CLI that swaps Authorization correctly but leaks the
    # placeholder through a second header must FAIL the gate — the old
    # Authorization-only assertion passed this.
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"FAKE_MUSE_MODE": "leak-header"})
    assert proc.returncode == 1
    assert "never reach the origin in any recorded field" in proc.stderr
    assert "header 'x-api-key'" in proc.stderr


def test_gate_placeholder_leak_via_query_fails(fixtures, tmp_path):
    # GitHub #157: the placeholder in the query string must fail the gate.
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"FAKE_MUSE_MODE": "leak-query"})
    assert proc.returncode == 1
    assert "never reach the origin in any recorded field" in proc.stderr
    assert "request path" in proc.stderr


def test_gate_placeholder_leak_via_encoded_query_fails(fixtures, tmp_path):
    # GitHub #157: the standard percent-encoding (what urlencode produces)
    # must not evade the scan.
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"FAKE_MUSE_MODE": "leak-query-encoded"})
    assert proc.returncode == 1
    assert "never reach the origin in any recorded field" in proc.stderr
    assert "request path (percent-decoded)" in proc.stderr


def test_gate_placeholder_leak_via_duplicate_header_fails(fixtures, tmp_path):
    # GitHub #157: a placeholder in a second same-name header must fail
    # the gate — the fixture joins duplicates (RFC 9110 section 5.3).
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"FAKE_MUSE_MODE": "leak-dup-header"})
    assert proc.returncode == 1
    assert "never reach the origin in any recorded field" in proc.stderr
    assert "header 'x-api-key'" in proc.stderr


def test_gate_records_carry_full_request_shape(fixtures, tmp_path):
    # The echo record is the gate's evidence: the full header set, the raw
    # path, and the body hash. Pin the shape so a future fixture change
    # can't silently shrink what the probe asserts on.
    proc, _ = run_probe(fixtures, tmp_path)
    assert proc.returncode == 0, proc.stderr
    with open(fixtures["echo_log"]) as f:
        records = [json.loads(line) for line in f if line.strip()]
    assert records, "no records in the echo log"
    get_rec = next(r for r in records if r["method"] == "GET")
    post_rec = next(r for r in records if r["method"] == "POST")
    for rec in (get_rec, post_rec):
        assert rec["headers"]["authorization"] == f"Bearer {SWAPPED}"
        assert rec["headers"]["x-request-id"] == "gate-fixture-benign"
        assert rec["authorization"] == f"Bearer {SWAPPED}"
    assert get_rec["body_sha256"] == ""  # no body on the GET
    assert post_rec["body_sha256"] == hashlib.sha256(b"{}").hexdigest()
    assert post_rec["path"] == "/responses"


def test_echo_records_malformed_content_length(fixtures, tmp_path):
    # Engineering review (PR #818): a malformed or negative Content-Length
    # must not traceback and silently drop the record — the gate's
    # evidence recorder still records the headers/path (no body).
    port = int(fixtures["echo_url"].rsplit(":", 1)[1])
    for raw_length in ("abc", "-5"):
        sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        try:
            sock.sendall(
                ("POST /responses HTTP/1.0\r\n"
                 "Host: gate-fixture\r\n"
                 f"Content-Length: {raw_length}\r\n"
                 "Connection: close\r\n\r\n").encode())
            resp = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
        finally:
            sock.close()
        assert resp.split(b"\r\n", 1)[0].endswith(b"200 OK"), resp[:60]
    with open(fixtures["echo_log"]) as f:
        records = [json.loads(line) for line in f if line.strip()]
    assert len(records) == 2
    for rec in records:
        assert rec["method"] == "POST"
        assert rec["path"] == "/responses"
        assert rec["body_sha256"] == ""  # no body read on bad framing


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
    env = {"PATH": os.environ.get("PATH", "")}
    p = subprocess.run([sys.executable, PROBE, "--mode", "bogus"],
                       stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=30, env={**os.environ, **env})
    assert p.returncode == 2


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


def test_probe_never_reads_stdin(fixtures, tmp_path):
    # An open-but-never-written pipe as stdin: any read by the probe or its
    # child would block forever and trip the subprocess timeout (60s). The
    # probe completing proves nothing ever read stdin — the R1 §5 contract.
    r, w = os.pipe()
    try:
        proc, _ = run_probe(fixtures, tmp_path, stdin=r)
    finally:
        os.close(r)
        os.close(w)
    assert proc.returncode == 0, proc.stderr


def _load_probe_module():
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("harness_auth_probe", PROBE)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_internal_budgets_fit_self_enforced_wall_clock():
    # Deterministic pin: per mode, the worst-case internal budgets must stay
    # under the probe's own self-enforced wall-clock budget (GitHub #158) —
    # the wall clock is the hard bound even when the invoker forgets the
    # external wrapper.
    mod = _load_probe_module()
    assert mod.CLI_TIMEOUT_S_GATE + mod.CONFIRMD_TIMEOUT_S < mod.WALL_CLOCK_S_GATE
    assert (mod.CLI_TIMEOUT_S_PROVISION + mod.CONFIRMD_TIMEOUT_S
            < mod.WALL_CLOCK_S_PROVISION)


def test_gate_wall_clock_is_the_r1_10s_cap():
    # The R1 §5 contract pins a 10-second cap for the gate invocation; the
    # probe now enforces it itself instead of depending on the invoker.
    mod = _load_probe_module()
    assert mod.WALL_CLOCK_S_GATE == 10.0


def test_provision_cli_budget_longer_than_gate():
    # GitHub #159: a real provider (TLS, cold model endpoint, inference
    # latency) can exceed the gate's 6s on a healthy box.
    mod = _load_probe_module()
    assert mod.CLI_TIMEOUT_S_PROVISION > mod.CLI_TIMEOUT_S_GATE


def test_self_enforced_wall_clock_fires(fixtures, tmp_path):
    # GitHub #158: no external `timeout` wrapper in play — a hanging CLI
    # must still terminate inside the documented exit contract (exit 1,
    # named), never hang or die with a bare 124.
    proc, dt = run_probe(fixtures, tmp_path,
                         extra_env={"FAKE_MUSE_MODE": "sleep",
                                    "PROBE_WALL_CLOCK_S": "2"})
    assert proc.returncode == 1
    assert "wall-clock budget expired after 2s" in proc.stderr
    assert dt < 15, f"probe ran {dt:.1f}s past its own wall-clock budget"


def test_external_sigterm_is_classified(fixtures, tmp_path):
    # An invoker that still wraps the probe in `timeout 10` sends SIGTERM;
    # the probe must classify it (exit 1, named) instead of dying silently.
    env = probe_env(fixtures, tmp_path, extra_env={"FAKE_MUSE_MODE": "sleep"})
    with neutralized_env():
        proc = subprocess.Popen(
            [sys.executable, PROBE, "--mode", "gate"],
            env={**os.environ, **env},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(1.0)  # let the probe arm its handlers before the kill
        proc.send_signal(signal.SIGTERM)
        _, err = proc.communicate(timeout=30)
    assert proc.returncode == 1, err
    assert "terminated externally" in err


def test_provision_cli_timeout_is_slowness_not_rejection(fixtures, tmp_path):
    # GitHub #159: provision-mode slowness must never be misdiagnosed as a
    # bad credential. PROBE_CLI_TIMEOUT_S shrinks the budget for the test;
    # production keeps the 25s default.
    proc, dt = run_probe(fixtures, tmp_path, mode="provision",
                         extra_env={"FAKE_MUSE_MODE": "sleep",
                                    "PROBE_CLI_TIMEOUT_S": "2"})
    assert proc.returncode == 1
    assert "timed out" in proc.stderr
    assert "not proof" in proc.stderr
    assert "did not accept the swapped credential" not in proc.stderr
    assert dt < 15


def test_provision_vehicle_cannot_ride_a_baked_credential(fixtures, tmp_path):
    # GitHub #156 regression: the ambient HOME carries a baked
    # ~/.config/muse/auth.json and the injected placeholder path is broken
    # (the fake CLI authenticates from the file only). Pre-fix the vehicle
    # inherited HOME and the probe certified the box; now the vehicle runs
    # under a fresh empty HOME, sees no credential, and the check fails.
    ambient = tmp_path / "ambient-home"
    (ambient / ".config" / "muse").mkdir(parents=True)
    (ambient / ".config" / "muse" / "auth.json").write_text(
        '{"providers": {"meta": {"api_key": "sk-baked-leak"}}}')
    proc, _ = run_probe(fixtures, tmp_path, mode="provision",
                        extra_env={"FAKE_MUSE_MODE": "baked-key-only",
                                   "HOME": str(ambient)})
    assert proc.returncode == 1
    assert "did not accept the swapped credential" in proc.stderr


def test_provision_vehicle_runs_under_scrubbed_home(fixtures, tmp_path):
    # GitHub #156: the provision vehicle must authenticate ONLY through
    # the injected env placeholder — never through ambient filesystem
    # credentials. The fake CLI dumps the environment it actually ran in;
    # the test pins the scrubbed-HOME contract and the teardown.
    dump = tmp_path / "env-dump.json"
    ambient = tmp_path / "ambient-home"
    (ambient / ".config").mkdir(parents=True)
    proc, _ = run_probe(fixtures, tmp_path, mode="provision",
                        extra_env={"FAKE_MUSE_MODE": "dump-env",
                                   "FAKE_MUSE_ENV_DUMP": str(dump),
                                   "HOME": str(ambient),
                                   "XDG_CONFIG_HOME": str(ambient / ".config")})
    assert proc.returncode == 0, proc.stderr
    info = json.loads(dump.read_text())
    assert info["HOME"] != str(ambient), "vehicle inherited the ambient HOME"
    assert info["home_exists"] and info["home_empty"]
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME",
                "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        assert info[var] is None, f"{var} leaked into the vehicle env"
    assert info["META_API_KEY"] == "hsurr:llm-api"
    # the scrubbed dir is torn down after the vehicle runs
    assert not os.path.exists(info["HOME"])


def test_provision_scrubbed_home_creation_failure_fails_closed(monkeypatch):
    # If the scrubbed HOME cannot be created, the probe must fail closed
    # (exit 3, environment) — never run the vehicle under the ambient HOME.
    mod = _load_probe_module()

    def _boom(proxy, key_name):
        raise OSError("no space left on device")

    monkeypatch.setattr(mod, "_scrubbed_vehicle_env", _boom)
    rc = mod.check_provision("muse", "http://127.0.0.1:9",
                             "http://127.0.0.1:18081", "llm-api", 5)
    assert rc == 3


def test_budget_env_rejects_nonfinite_and_nonpositive(monkeypatch):
    # Engineering round-1 blocker: inf/nan/absurd overrides must exit 2
    # with a named message, never a traceback from setitimer. Huge-but-
    # finite values are capped at 3600s.
    mod = _load_probe_module()
    for raw in ("banana", "inf", "-inf", "nan", "-3", "0"):
        monkeypatch.setenv("PROBE_WALL_CLOCK_S", raw)
        with pytest.raises(SystemExit) as ei:
            mod._budget_env("PROBE_WALL_CLOCK_S", 10.0)
        assert ei.value.code == 2, raw
    monkeypatch.setenv("PROBE_WALL_CLOCK_S", "1e308")
    assert mod._budget_env("PROBE_WALL_CLOCK_S", 10.0) == 3600.0
    monkeypatch.delenv("PROBE_WALL_CLOCK_S", raising=False)
    assert mod._budget_env("PROBE_WALL_CLOCK_S", 10.0) == 10.0


def test_wall_clock_wins_over_cli_budget(fixtures, tmp_path):
    # The wall clock is the hard bound: even a CLI budget longer than the
    # wall clock cannot outrun it.
    proc, dt = run_probe(fixtures, tmp_path,
                         extra_env={"FAKE_MUSE_MODE": "sleep",
                                    "PROBE_CLI_TIMEOUT_S": "60",
                                    "PROBE_WALL_CLOCK_S": "2"})
    assert proc.returncode == 1
    assert "wall-clock budget expired after 2s" in proc.stderr
    assert dt < 15


def test_invalid_wall_clock_override_is_usage_error(fixtures, tmp_path):
    # End-to-end: the invalid override exits 2 before any network work.
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"PROBE_WALL_CLOCK_S": "nan"})
    assert proc.returncode == 2
    assert "must be a positive finite number of seconds" in proc.stderr


def test_gate_cli_hang_after_request_fails(fixtures, tmp_path):
    # Regression test for the gate-mode hang hole: a CLI vehicle that
    # delivers valid requests and then hangs must FAIL the gate (R1 §5:
    # hang = fail), not ride the delivered records to exit 0.
    proc, dt = run_probe(fixtures, tmp_path,
                         extra_env={"FAKE_MUSE_MODE": "hang-after-request"})
    assert proc.returncode == 1
    assert "timed out" in proc.stderr
    assert dt < 15


def test_gate_ignores_stale_records(fixtures, tmp_path):
    # Records from a previous run already in the echo log must not affect
    # this run's verdict (the since_size logic).
    with open(fixtures["echo_log"], "a") as f:
        f.write(json.dumps({"authorization": "Bearer STALE-GARBAGE"}) + "\n")
        f.write("not json at all\n")  # stale corruption must also be ignored
    proc, _ = run_probe(fixtures, tmp_path)
    assert proc.returncode == 0, proc.stderr


def test_gate_unreachable_base_url_fails_closed(fixtures, tmp_path):
    proc, _ = run_probe(
        fixtures, tmp_path,
        extra_env={"PROBE_BASE_URL": f"http://127.0.0.1:{free_port()}"})
    assert proc.returncode == 1
    assert "no requests reached the echo fixture" in proc.stderr



def test_gate_duplicate_records_pass(fixtures, tmp_path):
    # CLI retries produce duplicate in-window records; all carry the swapped
    # value, so the gate must still pass.
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"FAKE_MUSE_MODE": "duplicate"})
    assert proc.returncode == 0, proc.stderr
    assert len(echo_auths(fixtures["echo_log"])) >= 4


def test_gate_unreadable_echo_log_fails_closed(fixtures, tmp_path):
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"PROBE_ECHO_LOG": str(tmp_path)})
    assert proc.returncode == 3
    assert "cannot read echo log" in proc.stderr


def test_gate_corrupt_echo_log_fails_closed(fixtures, tmp_path):
    proc, _ = run_probe(fixtures, tmp_path,
                        extra_env={"FAKE_MUSE_MODE": "corrupt-log"})
    assert proc.returncode == 3
    assert "non-JSON" in proc.stderr


def _tls_confirmd_server(tmp_path, handler=DenyHandler):
    if shutil.which("openssl") is None:
        pytest.skip("openssl not available for the self-signed test cert")
    key, cert = str(tmp_path / "c.key"), str(tmp_path / "c.crt")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048",
                    "-keyout", key, "-out", cert, "-days", "1", "-nodes",
                    "-subj", "/CN=127.0.0.1"],
                   check=True, capture_output=True, timeout=60)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_confirmd_https_self_signed_passes(fixtures, tmp_path):
    # The production confirmd path: HTTPS with a self-signed cert, answering
    # with confirmd's own 403 denial shape. This is the only test exercising
    # the probe's HTTPSHandler(context) + CERT_NONE wiring against the
    # deny-shape assertion — without it, "hardening" the context would break
    # production while the suite stays green.
    srv = _tls_confirmd_server(tmp_path)
    try:
        url = f"https://127.0.0.1:{srv.server_port}"
        proc, _ = run_probe(fixtures, tmp_path,
                            extra_env={"PROBE_CONFIRMD_URL": url})
    finally:
        srv.shutdown()
    assert proc.returncode == 0, proc.stderr
    assert "misbinding check ok" in proc.stderr


def test_confirmd_redirect_fails_closed(fixtures, tmp_path):
    # The check is always same-host: a 3xx from the answering process must
    # fail closed, not be followed to an arbitrary Location. The redirect
    # target serves the exact confirmd deny shape — without the no-redirect
    # handler the probe would follow the redirect and PASS, so this test
    # fails on any code that drops the handler (non-vacuous).
    deny_srv = _tls_confirmd_server(tmp_path, handler=DenyHandler)

    class RedirectHandler(BaseHTTPRequestHandler):
        target = None

        def do_GET(self):
            body = b"moved"
            self.send_response(302)
            self.send_header("Location",
                             f"https://127.0.0.1:{self.target}/")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    RedirectHandler.target = deny_srv.server_port
    redir_srv = _tls_confirmd_server(tmp_path, handler=RedirectHandler)
    try:
        url = f"https://127.0.0.1:{redir_srv.server_port}"
        proc, _ = run_probe(fixtures, tmp_path,
                            extra_env={"PROBE_CONFIRMD_URL": url})
    finally:
        redir_srv.shutdown()
        deny_srv.shutdown()
    assert proc.returncode == 1
    assert "does not behave like confirmd" in proc.stderr


def test_confirmd_port_grabber_200_fails(fixtures, tmp_path):
    # GitHub #160: a process merely listening on the confirmd port and
    # answering 200 must NOT certify the approvals path.
    srv = _tls_confirmd_server(tmp_path, handler=OkHandler)
    try:
        url = f"https://127.0.0.1:{srv.server_port}"
        proc, _ = run_probe(fixtures, tmp_path,
                            extra_env={"PROBE_CONFIRMD_URL": url})
    finally:
        srv.shutdown()
    assert proc.returncode == 1
    assert "does not behave like confirmd" in proc.stderr


def test_confirmd_403_wrong_body_fails(fixtures, tmp_path):
    # A 403 alone is not confirmd's denial: the denial body must be confirmd's
    # own "forbidden: <reason>" shape.
    class WrongBodyDeny(DenyHandler):
        def do_GET(self):
            body = b"access denied\n"
            self.send_response(403)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = _tls_confirmd_server(tmp_path, handler=WrongBodyDeny)
    try:
        url = f"https://127.0.0.1:{srv.server_port}"
        proc, _ = run_probe(fixtures, tmp_path,
                            extra_env={"PROBE_CONFIRMD_URL": url})
    finally:
        srv.shutdown()
    assert proc.returncode == 1
    assert "does not behave like confirmd" in proc.stderr


def test_confirmd_right_body_wrong_server_header_fails(fixtures, tmp_path):
    # The Server header assertion is non-vacuous: the right denial body
    # under a foreign Server header must fail.
    class WrongServerHeaderDeny(BaseHTTPRequestHandler):
        # default server_version ("BaseHTTP/0.6"), no confirmd/1 marker
        def do_GET(self):
            body = b"forbidden: self-peer\n"
            self.send_response(403)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = _tls_confirmd_server(tmp_path, handler=WrongServerHeaderDeny)
    try:
        url = f"https://127.0.0.1:{srv.server_port}"
        proc, _ = run_probe(fixtures, tmp_path,
                            extra_env={"PROBE_CONFIRMD_URL": url})
    finally:
        srv.shutdown()
    assert proc.returncode == 1
    assert "does not behave like confirmd" in proc.stderr


def test_confirmd_deny_reason_vocabulary_passes(fixtures, tmp_path):
    # The probe accepts confirmd's full known deny-reason vocabulary, not
    # just the self-peer reason the box itself always sees.
    class OtherReasonDeny(DenyHandler):
        reason = "not-a-tailnet-node"

    srv = _tls_confirmd_server(tmp_path, handler=OtherReasonDeny)
    try:
        url = f"https://127.0.0.1:{srv.server_port}"
        proc, _ = run_probe(fixtures, tmp_path,
                            extra_env={"PROBE_CONFIRMD_URL": url})
    finally:
        srv.shutdown()
    assert proc.returncode == 0, proc.stderr
    assert "misbinding check ok" in proc.stderr
