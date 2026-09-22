"""Hermetic tests for harness/inject-provision-state.sh (R2 slice 3).

The injector ships test seams for exactly this purpose
(CRED_STORE_VERIFY_INFERENCE, CRED_REGISTRY_SET_INFERENCE,
INFERENCE_HOSTS_ALLOW, INFERENCE_SSRF_ALLOW, INFERENCE_SECRETS_DIR,
INFERENCE_REGISTRY_FILE, SUDO_PREFIX, INJECT_MANIFEST,
INJECT_MANIFEST_CHECK, INJECT_IMAGE_VERSION, SWAPD_CA_DIR,
INJECT_IDENTITY_DIR, INJECT_AGENT_USER, INJECT_AGENT_HOME,
INJECT_TENANT_ID, INJECT_TENANT_RECORD, HARNESS_PROBE_BIN).

The fakes replicate the production contracts they stand in for:

- Fake store verify writer: mirrors
  proxy/cred-store-verify-inference's exit-code contract -- 0 iff stdin
  byte-equals ``$INFERENCE_SECRETS_DIR/llm-api``, 1 on mismatch, 2 when
  the store file is missing. The injector's real-key assertion depends
  on all three outcomes (dummy-still-installed refusal, not-dummy
  acceptance, missing refusal).
- Fake registry writer: mirrors proxy/cred-registry-set's JSON schema
  and the idempotent ``remove-host`` verb (removes only when present,
  like the real one). The injector's teardown calls ``remove-host``;
  the tests assert the binding is gone afterwards.
- Fake sudo: asserts the production privilege argv (-u swapd), then
  enforces the injector's sudoers surface -- the two narrow writers and
  ``cat`` on the inference registry ONLY. The injector never appends to
  an allowlist and never lists the secrets dir, so ``tee`` and ``ls``
  are denied here (exit 98): a regressed injector that reached for
  them would fail loudly instead of being masked by a permissive fake.
  Notably there is NO store writer anywhere in the fake bin dir -- the
  injector must never write a credential value, and any attempt to do
  so has no binary to call (the fake sudo would deny it anyway).
- Fake muse CLI vehicle + fake swap proxy: same contract as the
  install-gate-fixture tests -- the vehicle sends one GET through the
  proxy carrying the placeholder Bearer header; the proxy resolves
  ``hsurr:<name>`` against the fake secrets dir, mirroring
  ``proxy/swap_addon.py`` ``_resolve``.
- Provider stub: the provision-mode "real provider". Records every
  Authorization header it receives and answers 200 (or 401 when the
  test wants a credential-acceptance failure). The happy-path assertion
  that the stub saw ``Bearer <real-key>`` -- and never the placeholder
  -- is the end-to-end proof the injected key was swapped in.
- Stub confirmd: answers 200 to the probe's liveness check.

The manifest preflight runs the REAL harness/check-image-manifest.sh
against a hand-written manifest with the real schema
(``sparkvm/golden-image-manifest@1``); the drift test flips
INJECT_IMAGE_VERSION instead.

Stdout carries exactly one JSON document (the inject report); all
progress and refusal diagnostics go to stderr.

Nothing here touches the live credential store, registry, allowlist
files, CA dir, or agent home.
"""

import getpass
import json
import os
import subprocess
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
INJECTOR = os.path.join(HERE, "inject-provision-state.sh")

# The public dummy the injector must prove is NOT installed, and the
# inference proxy's single fixed credential name. Keep both in sync with
# install-gate-fixture.sh.
INSTALLER_DUMMY = "GATE-FIXTURE-DUMMY-NOT-A-SECRET"
REAL_KEY = "REAL-TENANT-KEY-SENTINEL"
KEY_NAME = "llm-api"
PLACEHOLDER = "hsurr:" + KEY_NAME
ECHO_HOST = "127.0.0.1"
PROVIDER_HOST = "api.provider.example"
IMAGE_SHA = "0123456789abcdef" * 4  # 64 hex chars, a pinned image SHA

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

# Fake sudo: asserts the production privilege argv (-u swapd) and
# enforces the INJECTOR's sudoers surface -- the two narrow writers and
# `cat` on the inference registry, nothing else. `tee` (allowlist
# appends) and `ls` are deliberately denied: the injector must never
# need them, and a regression reaching for them must fail loudly here.
FAKE_SUDO = """#!/bin/sh
if [ "$1" != "-u" ] || [ "$2" != "swapd" ]; then
  echo "fake-sudo: expected '-u swapd', got: $1 $2" >&2
  exit 99
fi
shift 2
case "$1" in
  "$CRED_STORE_VERIFY_INFERENCE"|"$CRED_REGISTRY_SET_INFERENCE") ;;
  cat|/bin/cat|/usr/bin/cat)
    [ "$2" = "$INFERENCE_REGISTRY_FILE" ] || \
      { echo "fake-sudo: cat denied for $2" >&2; exit 98; } ;;
  *) echo "fake-sudo: denied: $1" >&2; exit 98 ;;
esac
if [ -n "${SUDO_CALL_LOG:-}" ]; then
  printf '%s\\n' "$*" >> "$SUDO_CALL_LOG"
fi
exec "$@"
"""

# Fake store verify writer: mirrors proxy/cred-store-verify-inference's
# exit-code contract only (blind compare, nothing revealed): 0 iff stdin
# byte-equals the stored llm-api, 1 on mismatch, 2 on a missing store
# file.
FAKE_STORE_VERIFY = """#!/bin/sh
tmp="$(mktemp)"
cat > "$tmp"
if [ ! -f "$INFERENCE_SECRETS_DIR/llm-api" ]; then
  rm -f "$tmp"
  exit 2
fi
if cmp -s "$tmp" "$INFERENCE_SECRETS_DIR/llm-api"; then
  rm -f "$tmp"
  exit 0
fi
rm -f "$tmp"
exit 1
"""

# Fake registry writer: mirrors proxy/cred-registry-set's JSON schema
# for the verbs the injector uses. remove-host is idempotent like the
# real one (removes only when present).
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
    placement = json.loads(pjson)
    reg.setdefault(name, {})[entry] = {"placement": placement}
elif args[0] == "add-host":
    _, name, host = args
    hosts = reg.setdefault(name, {}).setdefault("allowed_hosts", [])
    if host not in hosts:
        hosts.append(host)
elif args[0] == "remove-host":
    _, name, host = args
    entry = reg.get(name)
    if isinstance(entry, dict):
        hosts = entry.get("allowed_hosts")
        if isinstance(hosts, list) and host in hosts:
            hosts.remove(host)
            # The real writer prints to STDOUT on success; the fake
            # mirrors it so the suite guards the injector's one-JSON-
            # document stdout contract (any stdout leak breaks
            # json.loads on the report).
            print("unbound '%s' from host '%s'" % (name, host))
else:
    sys.stderr.write("fake-registry-writer: unsupported verb %r\\n" % (args[0],))
    sys.exit(2)
with open(reg_path, "w", encoding="utf-8") as f:
    json.dump(reg, f, indent=2, sort_keys=True)
    f.write("\\n")
"""


class _SwapProxyHandler(BaseHTTPRequestHandler):
    """Loopback forward proxy resolving secrets[name] like the real one."""

    secrets_dir = None

    def do_GET(self):
        target = urllib.parse.urlsplit(self.path)
        auth = self.headers.get("Authorization")
        if auth and auth.startswith("Bearer hsurr:"):
            name = auth[len("Bearer hsurr:"):]
            secret_path = os.path.join(self.secrets_dir, name)
            if os.path.isfile(secret_path):
                with open(secret_path, encoding="utf-8") as f:
                    auth = "Bearer " + f.read()
        fwd = urllib.request.Request(
            "http://%s%s" % (target.netloc, target.path or "/"),
            headers={"Authorization": auth},
            method="GET",
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(fwd, timeout=10) as resp:
                body = resp.read()
                status = resp.status
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.HTTPError as e:
            self.send_error(e.code, str(e))
        except Exception as e:  # noqa: BLE001 -- stub only
            self.send_error(502, str(e))

    def log_message(self, *a):
        pass


class _ProviderHandler(BaseHTTPRequestHandler):
    """The provision-mode 'real provider': records Authorization headers,
    answers 200 (or a configured failure status)."""

    auth_seen = None
    status = 200

    def do_GET(self):
        self.auth_seen.append(self.headers.get("Authorization"))
        body = b'{"ok": true}'
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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


def _manifest(sha):
    return {
        "schema": "sparkvm/golden-image-manifest@1",
        "image_version": sha,
        "built_from_version": "0.1.0",
        "baked": ["os, agent user, sshd config (key-only)"],
        "registry_paths": {
            "inference_registry": "/home/swapd/inference-registry.json",
            "inference_hosts": "/home/swapd/inference-hosts.allow",
            "inference_secrets": "/home/swapd/inference-secrets",
            "main_registry": "/home/swapd/credentials.json",
            "grants": "/home/swapd/grants.json",
        },
        "units": ["swap-proxy.service"],
        "injector_expect": {
            "manifest_schema": "sparkvm/golden-image-manifest@1",
            "probe_path": "harness/harness-auth-probe",
            "probe_modes": ["gate", "provision"],
            "key_placeholder_format": "hsurr:<name>",
        },
    }


@pytest.fixture()
def stack(tmp_path):
    """Fake writers + temp layout + stub proxy/provider/confirmd."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    secrets_dir = tmp_path / "inference-secrets"
    secrets_dir.mkdir()
    registry_file = tmp_path / "inference-registry.json"
    allow_file = tmp_path / "inference-hosts.allow"
    ssrf_allow_file = tmp_path / "inference-ssrf.allow"
    ca_dir = tmp_path / "mitmproxy"
    ca_dir.mkdir()
    (ca_dir / "mitmproxy-ca.pem").write_text("FAKE-CA-CERT-NOT-A-KEY\n")
    manifest_file = tmp_path / "image-manifest.json"
    manifest_file.write_text(json.dumps(_manifest(IMAGE_SHA)))
    agent_home = tmp_path / "agent-home"
    agent_home.mkdir()
    tenant_record = tmp_path / "tenant.json"
    provider_auth = []

    (bin_dir / "fake-store-verify").write_text(FAKE_STORE_VERIFY)
    (bin_dir / "fake-registry-writer").write_text(FAKE_REGISTRY_WRITER)
    (bin_dir / "fake-muse").write_text(FAKE_MUSE)
    (bin_dir / "sudo").write_text(FAKE_SUDO)
    for f in ("fake-store-verify", "fake-registry-writer", "fake-muse",
              "sudo"):
        os.chmod(bin_dir / f, 0o755)

    proxy = _serve(_SwapProxyHandler, secrets_dir=str(secrets_dir))
    provider = _serve(_ProviderHandler, auth_seen=provider_auth, status=200)
    confirmd = _serve(_ConfirmdHandler)

    env = dict(os.environ)
    env.update({
        "CRED_STORE_VERIFY_INFERENCE": str(bin_dir / "fake-store-verify"),
        "CRED_REGISTRY_SET_INFERENCE": str(bin_dir / "fake-registry-writer"),
        "INFERENCE_HOSTS_ALLOW": str(allow_file),
        "INFERENCE_SSRF_ALLOW": str(ssrf_allow_file),
        "INFERENCE_SECRETS_DIR": str(secrets_dir),
        "INFERENCE_REGISTRY_FILE": str(registry_file),
        "SUDO_PREFIX": "",
        "INJECT_IMAGE_VERSION": IMAGE_SHA,
        "INJECT_MANIFEST": str(manifest_file),
        "SWAPD_CA_DIR": str(ca_dir),
        "INJECT_AGENT_USER": getpass.getuser(),
        "INJECT_AGENT_HOME": str(agent_home),
        "INJECT_TENANT_RECORD": str(tenant_record),
        "PROBE_PROXY": "http://127.0.0.1:%d" % proxy.server_address[1],
        "PROBE_MUSE_BIN": str(bin_dir / "fake-muse"),
        "PROBE_BASE_URL":
            "http://127.0.0.1:%d" % provider.server_address[1],
        "PROBE_CONFIRMD_URL":
            "http://127.0.0.1:%d" % confirmd.server_address[1],
        "FAKE_REGISTRY_FILE": str(registry_file),
        "PATH": str(bin_dir) + ":/usr/bin:/bin",
    })
    # INJECT_IDENTITY_DIR / INJECT_TENANT_ID default to unset (deferred
    # steps); individual tests set them.
    env.pop("INJECT_IDENTITY_DIR", None)
    env.pop("INJECT_TENANT_ID", None)
    paths = {
        "secrets_dir": secrets_dir, "registry_file": registry_file,
        "allow_file": allow_file, "ssrf_allow_file": ssrf_allow_file,
        "ca_dir": ca_dir, "manifest_file": manifest_file,
        "agent_home": agent_home, "tenant_record": tenant_record,
        "bin_dir": bin_dir, "provider_auth": provider_auth,
        "provider": provider,
    }
    yield env, paths
    proxy.shutdown()
    provider.shutdown()
    confirmd.shutdown()


def _run_injector(env):
    return subprocess.run(
        ["bash", INJECTOR],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
        env=env,
    )


def _registry(registry_file):
    with open(registry_file, encoding="utf-8") as f:
        return json.load(f)


def _seed_real_key(paths):
    """The operator's grant-writer path, as the test harness sees it: the
    real tenant key in the store, bound to the provider host with
    bearer_header placement."""
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": [PROVIDER_HOST],
        }
    }))


def _report(proc):
    # Stdout carries exactly one JSON document (the inject report); all
    # progress and refusal diagnostics go to stderr.
    return json.loads(proc.stdout.decode())


def test_happy_path_no_fixture(stack):
    # Canonical golden-image path: the image-build gate tore the fixture
    # down completely pre-publish; the operator installed the real key.
    env, paths = stack
    _seed_real_key(paths)
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    report = _report(proc)
    assert report["image_version"] == IMAGE_SHA
    assert report["steps"]["manifest"] == "ok"
    assert report["steps"]["fixture_teardown"] == "ok"
    assert report["fixture_teardown_detail"] == "absent"
    assert report["steps"]["inference_key"] == "ok"
    assert report["steps"]["swapd_ca"] == "ok"
    assert report["steps"]["probe"] == "ok"
    # H9/H10 mechanics have not landed: deferred, loudly, never silent.
    assert report["steps"]["identity"] == "deferred (H9)"
    assert report["steps"]["confirmd_attribution"] == "deferred (H10)"
    assert report["deferred"] == [
        "identity (H9: tenant identity mechanics)",
        "confirmd_attribution (H10: per-tenant approvals URL wiring)",
    ]
    # End-to-end: the provider saw the swapped real key, never the
    # placeholder.
    assert paths["provider_auth"], "no request reached the provider"
    assert all(a == "Bearer " + REAL_KEY for a in paths["provider_auth"])
    assert not any(PLACEHOLDER in (a or "") for a in paths["provider_auth"])
    # The injector never touched the real key: byte-identical.
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_teardown_stale_fixture_binding(stack):
    # A real tenant key landed on a box whose echo binding was never
    # torn down (the exact case install-gate-fixture.sh refuses on).
    # The injector owns this teardown: unbind, then proceed.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": [ECHO_HOST, PROVIDER_HOST],
        }
    }))
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    report = _report(proc)
    assert report["steps"]["fixture_teardown"] == "ok"
    assert report["fixture_teardown_detail"] == "removed"
    reg = _registry(paths["registry_file"])
    assert reg[KEY_NAME]["allowed_hosts"] == [PROVIDER_HOST]
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_teardown_fixture_only_binding(stack):
    # Fixture binding present, stored value still the dummy, allowlists
    # clean: the binding is removed, then the run refuses at the key
    # assertion -- with the binding gone there is no usable credential,
    # and the injector must never probe with the dummy.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(INSTALLER_DUMMY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": [ECHO_HOST],
        }
    }))
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"no usable real inference credential" in proc.stderr
    # The teardown still happened (binding gone); the dummy is untouched.
    reg = _registry(paths["registry_file"])
    assert ECHO_HOST not in reg[KEY_NAME]["allowed_hosts"]
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == INSTALLER_DUMMY


def test_refuses_allowlist_residue(stack):
    # The binding is removed through the narrow writer, but the echo
    # host survives in inference-hosts.allow. The injector has no narrow
    # path to remove allowlist lines (production sudoers is append-only
    # by design), so it fails closed -- naming the image-build gate as
    # the teardown owner -- rather than letting a real key coexist with
    # a gate echo exemption.
    env, paths = stack
    _seed_real_key(paths)
    reg = _registry(paths["registry_file"])
    reg[KEY_NAME]["allowed_hosts"] = [ECHO_HOST, PROVIDER_HOST]
    paths["registry_file"].write_text(json.dumps(reg))
    paths["allow_file"].write_text(ECHO_HOST + "\n")
    proc = _run_injector(env)
    assert proc.returncode == 1
    # The refusal names the ACTUAL residue, not some other alias: the
    # inverted-grep mutation refuses on '::1' here and must not pass.
    assert b"echo host '127.0.0.1' still present" in proc.stderr
    assert b"image-build gate" in proc.stderr
    # The binding teardown still happened (defense in depth); the key
    # is byte-identical; nothing was appended anywhere.
    reg = _registry(paths["registry_file"])
    assert ECHO_HOST not in reg[KEY_NAME]["allowed_hosts"]
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY
    assert paths["ssrf_allow_file"].exists() is False


def test_refuses_ssrf_allowlist_residue(stack):
    # Same fail-closed contract for the inference proxy's OWN ssrf
    # exemption file (finding 29's egress guard).
    env, paths = stack
    _seed_real_key(paths)
    paths["ssrf_allow_file"].write_text(ECHO_HOST + "\n")
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"echo host '127.0.0.1' still present" in proc.stderr
    assert b"image-build gate" in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_refuses_loopback_alias_residue(stack):
    # A `localhost` entry is the same echo exemption under another name.
    env, paths = stack
    _seed_real_key(paths)
    paths["allow_file"].write_text("localhost\n")
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"echo host 'localhost' still present" in proc.stderr


def test_refuses_dummy_still_installed(stack):
    # Registry binds llm-api to the real provider, but the stored value
    # is still the public dummy: no real tenant key has landed.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(INSTALLER_DUMMY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": [PROVIDER_HOST],
        }
    }))
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"still the public fixture dummy" in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == INSTALLER_DUMMY


def test_refuses_missing_credential(stack):
    # The registry binds llm-api, but the store holds nothing: the
    # blind compare's exit-2 path.
    env, paths = stack
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": [PROVIDER_HOST],
        }
    }))
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"no llm-api credential in the store" in proc.stderr


def test_refuses_wrong_placement(stack):
    env, paths = stack
    _seed_real_key(paths)
    reg = _registry(paths["registry_file"])
    reg[KEY_NAME]["access_token"] = {"placement": "url_path_segment"}
    paths["registry_file"].write_text(json.dumps(reg))
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"no usable real inference credential" in proc.stderr


def test_refuses_manifest_drift(stack):
    # The box is not the pinned image: refuse before touching anything.
    env, paths = stack
    _seed_real_key(paths)
    env = dict(env)
    env["INJECT_IMAGE_VERSION"] = "f" * 64
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"manifest preflight failed" in proc.stderr
    # Nothing was touched: the key and registry are exactly as seeded.
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY
    assert _registry(paths["registry_file"])[KEY_NAME]["allowed_hosts"] == \
        [PROVIDER_HOST]


def test_refuses_missing_ca(stack):
    env, paths = stack
    _seed_real_key(paths)
    (paths["ca_dir"] / "mitmproxy-ca.pem").unlink()
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"fresh swapd CA absent" in proc.stderr


def test_identity_install(stack):
    # H9's future input contract: an authorized_keys file installs as
    # the agent user's ~/.ssh/authorized_keys, 0700/0600, byte-identical.
    env, paths = stack
    _seed_real_key(paths)
    identity_dir = paths["secrets_dir"] / "identity"
    identity_dir.mkdir()
    pubkey = ("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItestkeymaterial "
              "tenant@muse\n")
    (identity_dir / "authorized_keys").write_text(pubkey)
    env = dict(env)
    env["INJECT_IDENTITY_DIR"] = str(identity_dir)
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    report = _report(proc)
    assert report["steps"]["identity"] == "ok"
    installed = paths["agent_home"] / ".ssh" / "authorized_keys"
    assert installed.read_text() == pubkey
    assert (installed.stat().st_mode & 0o777) == 0o600
    assert ((paths["agent_home"] / ".ssh").stat().st_mode & 0o777) == 0o700


def test_identity_refuses_private_key(stack):
    # Private-key material in the identity dir is a credential
    # mishandling, not a no-op: refuse, fail-closed, install nothing.
    env, paths = stack
    _seed_real_key(paths)
    identity_dir = paths["secrets_dir"] / "identity"
    identity_dir.mkdir()
    (identity_dir / "authorized_keys").write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA\n"
        "-----END OPENSSH PRIVATE KEY-----\n")
    env = dict(env)
    env["INJECT_IDENTITY_DIR"] = str(identity_dir)
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert b"private-key material" in proc.stderr
    assert not (paths["agent_home"] / ".ssh").exists()


def test_identity_refuses_bad_shape(stack):
    env, paths = stack
    _seed_real_key(paths)
    identity_dir = paths["secrets_dir"] / "identity"
    identity_dir.mkdir()
    (identity_dir / "authorized_keys").write_text("not-a-key\n")
    env = dict(env)
    env["INJECT_IDENTITY_DIR"] = str(identity_dir)
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert b"not a recognized public-key shape" in proc.stderr


@pytest.mark.parametrize("keytype", [
    "ssh-rsa",
    "ssh-dss",
    "ssh-ed25519",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
    "cert-authority",
])
def test_identity_accepts_each_key_shape(stack, keytype):
    # Every alternative in the injector's public-key shape regex must be
    # accepted: a committed regex that silently rejected a legitimate
    # tenant key type would ship uncaught otherwise (the display layer
    # redacts sk-*-looking tokens in tool output, so assert behavior,
    # not bytes).
    env, paths = stack
    _seed_real_key(paths)
    identity_dir = paths["secrets_dir"] / "identity"
    identity_dir.mkdir()
    (identity_dir / "authorized_keys").write_text(
        "%s AAAAC3NzaC1lZDI1NTE5AAAAItestkeymaterial tenant@muse\n"
        % keytype)
    env = dict(env)
    env["INJECT_IDENTITY_DIR"] = str(identity_dir)
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert _report(proc)["steps"]["identity"] == "ok"


def test_tenant_record(stack):
    # H10's future input contract: a validated tenant id produces the
    # attribution record the per-tenant approvals slice will consume.
    env, paths = stack
    _seed_real_key(paths)
    env = dict(env)
    env["INJECT_TENANT_ID"] = "tenant-42"
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    report = _report(proc)
    assert report["steps"]["confirmd_attribution"] == "ok"
    assert report["deferred"] == ["identity (H9: tenant identity mechanics)"]
    record = json.loads(paths["tenant_record"].read_text())
    assert record["tenant_id"] == "tenant-42"
    assert record["image_version"] == IMAGE_SHA
    assert record["injector"] == "harness/inject-provision-state.sh"


def test_identity_refuses_symlinked_ssh_dir(stack):
    # A planted ~/.ssh symlink would redirect validated tenant keys
    # into an attacker-chosen directory (e.g. /root/.ssh): refuse,
    # fail-closed, install nothing.
    env, paths = stack
    _seed_real_key(paths)
    identity_dir = paths["secrets_dir"] / "identity"
    identity_dir.mkdir()
    (identity_dir / "authorized_keys").write_text(
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItestkeymaterial tenant@muse\n")
    (paths["agent_home"] / ".ssh").symlink_to("/tmp/evil-target")
    env = dict(env)
    env["INJECT_IDENTITY_DIR"] = str(identity_dir)
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"is a symlink" in proc.stderr
    assert not os.path.exists("/tmp/evil-target")


def test_identity_refuses_symlinked_authorized_keys(stack):
    env, paths = stack
    _seed_real_key(paths)
    identity_dir = paths["secrets_dir"] / "identity"
    identity_dir.mkdir()
    (identity_dir / "authorized_keys").write_text(
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItestkeymaterial tenant@muse\n")
    ssh_dir = paths["agent_home"] / ".ssh"
    ssh_dir.mkdir()
    (ssh_dir / "authorized_keys").symlink_to("/tmp/evil-keys")
    env = dict(env)
    env["INJECT_IDENTITY_DIR"] = str(identity_dir)
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"is a symlink" in proc.stderr
    assert not os.path.lexists("/tmp/evil-keys")


def test_tenant_record_refuses_symlink(stack):
    env, paths = stack
    _seed_real_key(paths)
    paths["tenant_record"].symlink_to("/tmp/evil-record")
    env = dict(env)
    env["INJECT_TENANT_ID"] = "tenant-42"
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"is a symlink" in proc.stderr
    assert not os.path.lexists("/tmp/evil-record")


def test_tenant_id_validation(stack):
    env, paths = stack
    _seed_real_key(paths)
    env = dict(env)
    env["INJECT_TENANT_ID"] = "../evil"
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert b"INJECT_TENANT_ID must match" in proc.stderr
    assert not paths["tenant_record"].exists()


def test_tenant_id_rejects_embedded_newline(stack):
    # grep is line-oriented: "ok\nEVIL" would pass a naive -x match.
    env, paths = stack
    _seed_real_key(paths)
    env = dict(env)
    env["INJECT_TENANT_ID"] = "tenant-42\ninjected-line"
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert b"INJECT_TENANT_ID must match" in proc.stderr
    assert not paths["tenant_record"].exists()


def test_probe_failure_propagates(stack):
    # The provider rejects the swapped credential: the injector maps it
    # to provisioning-failed and the key is byte-identical (the failure
    # is the credential or the proxy, never a half-written store).
    env, paths = stack
    _seed_real_key(paths)
    paths["provider"].RequestHandlerClass.status = 401
    try:
        proc = _run_injector(env)
    finally:
        paths["provider"].RequestHandlerClass.status = 200
    assert proc.returncode == 1
    assert b"provisioning-failed" in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_idempotent(stack):
    env, paths = stack
    _seed_real_key(paths)
    assert _run_injector(env).returncode == 0
    reg_before = _registry(paths["registry_file"])
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert _registry(paths["registry_file"]) == reg_before
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_privilege_prefix(stack):
    # Exercises the REAL production default SUDO_PREFIX ("sudo -u
    # swapd") end to end through the fake sudo, which asserts the -u
    # swapd argv AND denies everything outside the injector's narrow
    # surface (writers + cat on the registry). Popping SUDO_PREFIX --
    # not setting it -- reaches the script's `${SUDO_PREFIX-sudo -u
    # swapd}` default branch. The SUDO_CALL_LOG proves the default was
    # USED, not bypassed: a regressed empty default would leave it empty.
    # Notably the log must show NO tee/ls: the injector never appends to
    # an allowlist and never lists the secrets dir.
    env, paths = stack
    # Seed a stale fixture binding so the remove-host teardown is
    # exercised through the privilege path too (the happy path with no
    # binding never calls the registry writer).
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": [ECHO_HOST, PROVIDER_HOST],
        }
    }))
    env = dict(env)
    env.pop("SUDO_PREFIX", None)
    call_log = paths["bin_dir"] / "sudo-calls.log"
    env["SUDO_CALL_LOG"] = str(call_log)
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    calls = call_log.read_text() if call_log.exists() else ""
    assert calls, "no privileged calls logged: the injector bypassed sudo"
    assert env["CRED_STORE_VERIFY_INFERENCE"] in calls
    assert env["CRED_REGISTRY_SET_INFERENCE"] in calls
    assert "cat" in calls
    assert "tee" not in calls
    assert " ls " not in calls


def test_missing_image_version(stack):
    env, paths = stack
    env = dict(env)
    env.pop("INJECT_IMAGE_VERSION", None)
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert b"INJECT_IMAGE_VERSION is required" in proc.stderr


@pytest.mark.parametrize("var", ["CRED_STORE_VERIFY_INFERENCE",
                                 "CRED_REGISTRY_SET_INFERENCE",
                                 "INJECT_MANIFEST_CHECK",
                                 "HARNESS_PROBE_BIN"])
def test_missing_binary_fails(stack, var):
    # The -x prechecks fail closed with the env-var name in the message.
    env, paths = stack
    env = dict(env)
    env[var] = "/nonexistent/binary"
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert var.encode() in proc.stderr


def test_never_writes_through_privilege(stack):
    # Structural proof the injector cannot write a credential value:
    # the fake bin dir contains NO store writer at all, and the fake
    # sudo denies every command outside the writer+cat surface (exit
    # 98). Any regressed store-write attempt -- privileged or not --
    # fails loudly instead of landing in the secrets dir.
    env, paths = stack
    _seed_real_key(paths)
    assert not (paths["bin_dir"] / "fake-store-writer").exists()
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert b"fake-sudo: denied" not in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY
