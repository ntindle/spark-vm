"""Hermetic tests for harness/install-gate-fixture.sh.

The installer ships test seams for exactly this purpose
(CRED_STORE_SET_INFERENCE, CRED_REGISTRY_SET_INFERENCE,
INFERENCE_HOSTS_ALLOW, INFERENCE_SSRF_ALLOW, INFERENCE_SECRETS_DIR,
INFERENCE_REGISTRY_FILE, SUDO_PREFIX, HARNESS_GATE_ECHO_LOG).

The fakes replicate the production contracts they stand in for (not
just the happy path):

- Fake store writer: the real proxy/cred-store-set-inference hardcodes
  the credential filename -- the inference proxy holds exactly one
  credential (finding 31) -- so the fake writes stdin to
  ``$INFERENCE_SECRETS_DIR/llm-api`` regardless of any name. A
  regression that renamed the fixture credential would leave the fake
  proxy with no ``llm-api`` file and the happy-path test would fail,
  exactly like the real ``unknown-credential`` refusal.
- Fake registry writer: maintains the real JSON schema
  (``{"<name>": {"<entry>": {"placement": ...}, "allowed_hosts": [...]}}``,
  placement parsed with json.loads, hosts deduped) so the installer's
  fail-closed guard reads a faithful registry.
- Fake swap proxy: resolves ``secrets[name]`` from the fake secrets dir
  files (filename = credential name), mirroring
  ``proxy/swap_addon.py`` ``_resolve`` -- an unknown name leaves the
  placeholder untouched, like the real ``unknown-credential`` refusal.
  The egress-guard half has no hermetic equivalent; instead the tests
  assert the installer populates the inference SSRF allow file
  (idempotently), which is the installer's side of that contract.

The installer starts the REAL harness/echo-fixture.py and runs the REAL
harness/harness-auth-probe in gate mode; the only other fakes are the
muse CLI vehicle (PROBE_MUSE_BIN, honoring the probe's child-env
contract) and a stub confirmd. The happy-path assertion on the echo log
proves the swapped credential reached the origin end to end.

Nothing here touches the live credential store, registry, or allowlist
files.
"""

import json
import os
import re
import subprocess
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALLER = os.path.join(HERE, "install-gate-fixture.sh")

# The public dummy the installer must install, and the inference
# proxy's single fixed credential name. Keep both in sync with
# FIXTURE_DUMMY / KEY_NAME in install-gate-fixture.sh.
INSTALLER_DUMMY = "GATE-FIXTURE-DUMMY-NOT-A-SECRET"
KEY_NAME = "llm-api"
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

# Fake store writer: mirrors the real writer's fixed-name contract --
# the value on stdin always lands in $INFERENCE_SECRETS_DIR/llm-api.
FAKE_STORE_WRITER = """#!/bin/sh
# Mirror proxy/cred-store-set-inference: the name is fixed, the
# inference proxy holds exactly one credential (finding 31).
cat > "$INFERENCE_SECRETS_DIR/llm-api"
"""

# Fake registry writer: mirrors proxy/cred-registry-set's JSON schema
# for the verbs the installer uses (placement via json.loads, hosts
# deduped) so the installer's fail-closed guard reads a faithful file.
FAKE_REGISTRY_WRITER = """#!/usr/bin/env python3
import json, os, sys
reg_path = os.environ["FAKE_REGISTRY_FILE"]
reg = {}
if os.path.exists(reg_path):
    with open(reg_path, encoding="utf-8") as f:
        reg = json.load(f)
args = sys.argv[1:]
if args[0] == "set":
    _, name, entry, pjson = args
    reg.setdefault(name, {})[entry] = {"placement": json.loads(pjson)}
elif args[0] == "add-host":
    _, name, host = args
    hosts = reg.setdefault(name, {}).setdefault("allowed_hosts", [])
    if host not in hosts:
        hosts.append(host)
else:
    sys.stderr.write("fake-registry-writer: unsupported verb %r\\n" % (args[0],))
    sys.exit(2)
with open(reg_path, "w", encoding="utf-8") as f:
    json.dump(reg, f, indent=2, sort_keys=True)
    f.write("\\n")
"""


class _SwapProxyHandler(BaseHTTPRequestHandler):
    """Loopback forward proxy resolving secrets[name] like the real one.

    Mirrors proxy/swap_addon.py _resolve: the credential name is taken
    from the ``hsurr:<name>`` placeholder and looked up as a file in the
    secrets dir. An unknown name leaves the placeholder untouched (the
    real unknown-credential refusal). swap=False simulates a broken swap
    at the transport level instead.
    """

    swap = True
    secrets_dir = None

    def do_GET(self):
        # self.path is the absolute URI for proxy requests.
        target = urllib.parse.urlsplit(self.path)
        auth = self.headers.get("Authorization")
        if self.swap and auth and auth.startswith("Bearer hsurr:"):
            name = auth[len("Bearer hsurr:"):]
            # Mirror the writers' name validation; never a path.
            if re.match(r"^[A-Za-z0-9_-]+$", name):
                secret_path = os.path.join(self.secrets_dir, name)
                if os.path.isfile(secret_path):
                    with open(secret_path, encoding="utf-8") as f:
                        auth = "Bearer " + f.read()
            # else: unknown credential -- placeholder passes through
            # unswapped, exactly like _resolve's refusal.
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
    """Fake writers + temp secrets/registry/allowlists/log + stub proxy."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    secrets_dir = tmp_path / "inference-secrets"
    secrets_dir.mkdir()
    registry_file = tmp_path / "inference-registry.json"
    allow_file = tmp_path / "inference-hosts.allow"
    ssrf_allow_file = tmp_path / "inference-ssrf.allow"
    echo_log = tmp_path / "echo.log"

    (bin_dir / "fake-store-writer").write_text(FAKE_STORE_WRITER)
    (bin_dir / "fake-registry-writer").write_text(FAKE_REGISTRY_WRITER)
    (bin_dir / "fake-muse").write_text(FAKE_MUSE)
    # Fake sudo: asserts the production privilege argv (-u swapd), then
    # execs the remaining argv directly, so a test can exercise the
    # installer's default SUDO_PREFIX value end to end.
    (bin_dir / "sudo").write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" != \"-u\" ] || [ \"$2\" != \"swapd\" ]; then\n"
        "  echo \"fake-sudo: expected '-u swapd', got: $1 $2\" >&2\n"
        "  exit 99\n"
        "fi\n"
        "shift 2\n"
        "exec \"$@\"\n")
    for f in ("fake-store-writer", "fake-registry-writer", "fake-muse",
              "sudo"):
        os.chmod(bin_dir / f, 0o755)

    proxy = _serve(_SwapProxyHandler, swap=True,
                   secrets_dir=str(secrets_dir))
    confirmd = _serve(_ConfirmdHandler)

    env = dict(os.environ)
    env.update({
        "CRED_STORE_SET_INFERENCE": str(bin_dir / "fake-store-writer"),
        "CRED_REGISTRY_SET_INFERENCE": str(bin_dir / "fake-registry-writer"),
        "INFERENCE_HOSTS_ALLOW": str(allow_file),
        "INFERENCE_SSRF_ALLOW": str(ssrf_allow_file),
        "INFERENCE_SECRETS_DIR": str(secrets_dir),
        "INFERENCE_REGISTRY_FILE": str(registry_file),
        "SUDO_PREFIX": "",
        "HARNESS_GATE_ECHO_LOG": str(echo_log),
        "PROBE_PROXY": "http://127.0.0.1:%d" % proxy.server_address[1],
        "PROBE_MUSE_BIN": str(bin_dir / "fake-muse"),
        "PROBE_CONFIRMD_URL":
            "http://127.0.0.1:%d" % confirmd.server_address[1],
        "FAKE_REGISTRY_FILE": str(registry_file),
        # PATH must not leak a real `muse` anywhere; the probe takes the
        # absolute fake path, but keep the seam honest anyway.
        "PATH": str(bin_dir) + ":/usr/bin:/bin",
    })
    yield (env, secrets_dir, registry_file, allow_file, ssrf_allow_file,
           echo_log, proxy)
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


def _registry(registry_file):
    with open(registry_file, encoding="utf-8") as f:
        return json.load(f)


def test_installer_happy_path(stack):
    (env, secrets_dir, registry_file, allow_file, ssrf_allow_file,
     echo_log, _proxy) = stack
    proc = _run_installer(env)
    assert proc.returncode == 0, proc.stderr.decode()
    # Store writer received exactly the public dummy on stdin, filed
    # under the proxy's single fixed credential name.
    assert (secrets_dir / KEY_NAME).read_text() == INSTALLER_DUMMY
    # Registry holds the placement and the echo-host binding.
    reg = _registry(registry_file)
    assert reg[KEY_NAME]["access_token"] == {"placement": "bearer_header"}
    assert reg[KEY_NAME]["allowed_hosts"] == ["127.0.0.1"]
    # Echo host allowlisted for swapping, exactly once...
    assert allow_file.read_text().splitlines() == ["127.0.0.1"]
    # ...and exempted from the inference SSRF guard, exactly once.
    assert ssrf_allow_file.read_text().splitlines() == ["127.0.0.1"]
    # The swapped credential reached the echo origin: end-to-end proof
    # the installer wired the fixture correctly. (If the installer used
    # any other credential name, the fake proxy's secrets[name] lookup
    # would miss -- mirroring the real unknown-credential refusal --
    # and this assertion would fail.)
    records = [json.loads(l) for l in echo_log.read_text().splitlines()
               if l.strip()]
    assert records, "echo log is empty: no request reached the fixture"
    assert all(r["authorization"] == "Bearer " + INSTALLER_DUMMY
               for r in records)
    assert not any(PLACEHOLDER in r["authorization"] for r in records)


def test_installer_idempotent(stack):
    (env, secrets_dir, registry_file, allow_file, ssrf_allow_file,
     echo_log, _proxy) = stack
    assert _run_installer(env).returncode == 0
    # Second run: the guard must recognize the previous fixture run
    # (dummy + fixture binding) and reinstall instead of refusing.
    proc = _run_installer(env)
    assert proc.returncode == 0, proc.stderr.decode()
    # Second run must not duplicate any allowlist entry or binding.
    assert allow_file.read_text().splitlines() == ["127.0.0.1"]
    assert ssrf_allow_file.read_text().splitlines() == ["127.0.0.1"]
    assert _registry(registry_file)[KEY_NAME]["allowed_hosts"] == ["127.0.0.1"]
    assert (secrets_dir / KEY_NAME).read_text() == INSTALLER_DUMMY


def test_installer_refuses_real_credential(stack):
    (env, secrets_dir, registry_file, allow_file, ssrf_allow_file,
     echo_log, _proxy) = stack
    # A real tenant credential lives in the store; the registry shows no
    # fixture binding (the injector unbound it when the key landed).
    (secrets_dir / KEY_NAME).write_text("REAL-KEY-SENTINEL")
    proc = _run_installer(env)
    assert proc.returncode == 2
    assert b"refusing" in proc.stderr
    assert b"real inference credential" in proc.stderr
    # Fail-closed: nothing was written anywhere.
    assert (secrets_dir / KEY_NAME).read_text() == "REAL-KEY-SENTINEL"
    assert not registry_file.exists()
    assert not allow_file.exists()
    assert not ssrf_allow_file.exists()


def test_installer_reinstalls_previous_fixture(stack):
    (env, secrets_dir, registry_file, allow_file, ssrf_allow_file,
     echo_log, _proxy) = stack
    # Previous gate run: dummy stored, fixture binding in the registry.
    (secrets_dir / KEY_NAME).write_text(INSTALLER_DUMMY)
    registry_file.write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": ["127.0.0.1"],
        }
    }))
    proc = _run_installer(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert b"previous fixture run detected" in proc.stdout


def test_installer_repairs_missing_trailing_newline(stack):
    (env, secrets_dir, registry_file, allow_file, ssrf_allow_file,
     echo_log, _proxy) = stack
    # Pre-existing SSRF allow file without a trailing newline: the
    # append must not merge lines (od-verified printf '\n' path).
    with open(ssrf_allow_file, "w", encoding="utf-8") as f:
        f.write("10.0.0.1")
    proc = _run_installer(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert ssrf_allow_file.read_text().splitlines() == ["10.0.0.1", "127.0.0.1"]


def test_installer_privilege_prefix(stack):
    # Exercises the production default SUDO_PREFIX ("sudo -u swapd")
    # through the fake sudo, which asserts the -u swapd argv. A
    # privilege-path breakage is fail-closed (sudo error -> set -e ->
    # nonzero exit), so this pins the argv rather than the behavior.
    (env, secrets_dir, registry_file, allow_file, ssrf_allow_file,
     echo_log, _proxy) = stack
    env["SUDO_PREFIX"] = "sudo -u swapd"
    proc = _run_installer(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert (secrets_dir / KEY_NAME).read_text() == INSTALLER_DUMMY
    assert ssrf_allow_file.read_text().splitlines() == ["127.0.0.1"]


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
    (env, secrets_dir, registry_file, allow_file, ssrf_allow_file,
     echo_log, proxy) = stack
    # Broken swap: the placeholder reaches the origin unswapped, so the
    # probe's wire-shape assertion fails and the install must fail.
    proxy.RequestHandlerClass.swap = False
    try:
        proc = _run_installer(env)
    finally:
        proxy.RequestHandlerClass.swap = True
    assert proc.returncode != 0
    # The failure is genuinely the wire-shape assertion, not an
    # incidental error: the unswapped placeholder reached the echo
    # origin.
    assert PLACEHOLDER in echo_log.read_text()
    # The fixture writes still happened (the failure is the verification,
    # not the install).
    assert (secrets_dir / KEY_NAME).read_text() == INSTALLER_DUMMY
