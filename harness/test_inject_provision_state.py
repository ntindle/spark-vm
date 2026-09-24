"""Hermetic tests for harness/inject-provision-state.sh (R2 slice 3).

The injector ships test seams for exactly this purpose
(CRED_STORE_VERIFY_INFERENCE, CRED_REGISTRY_SET_INFERENCE,
CRED_STORE_SET_WRITER, MAIN_HOSTS_ALLOW, SMOKE_SUDOERS_PATH, VISUDO_BIN,
INFERENCE_HOSTS_ALLOW, INFERENCE_SSRF_ALLOW, INFERENCE_SECRETS_DIR,
INFERENCE_REGISTRY_FILE, SUDO_PREFIX, INJECT_MANIFEST,
INJECT_MANIFEST_CHECK, INJECT_IMAGE_VERSION, SWAPD_CA_DIR,
INJECT_IDENTITY_DIR, INJECT_AGENT_USER, INJECT_AGENT_HOME,
INJECT_TENANT_ID, INJECT_TENANT_RECORD, INJECT_SMOKE_HOST,
HARNESS_PROBE_BIN).

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
  enforces the injector's sudoers surface -- the two narrow writers,
  the main-store set writer (smoke step only), and ``cat`` on the
  inference registry ONLY. The injector never appends to an allowlist
  and never lists the secrets dir, so ``tee`` and ``ls`` are denied
  here (exit 98): a regressed injector that reached for them would
  fail loudly instead of being masked by a permissive fake.
  Notably the fake bin dir holds exactly ONE value-writing store
  writer -- the smoke dummy's -- and the fake sudo allows it only for
  the fixed smoke credential name; any attempt to write any other
  credential value has no binary to call and is denied anyway.
  ``test_only_writes_smoke_dummy`` is the structural proof.
- Fake main-store set writer: mirrors proxy/cred-store-set's contract
  for the smoke step only -- name arg validated like the real one
  (``[A-Za-z0-9_-]+``), stdin stored verbatim under the name. Writes
  to a fake secrets dir, never the live store.
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
- Stub confirmd: answers confirmd's own 403 deny shape (the probe's
  misbinding check, GitHub #160) -- in lockstep with
  confirm/confirmd.py _auth/_deny.

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
import ipaddress
import json
import os
import re
import subprocess
import sys
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
SMOKE_HOST = "smoke.example.com"  # the operator's §3a echo host (G6)
SMOKE_CRED = "smoke-test"  # §3a smoke credential name (public dummy)
SMOKE_DUMMY = "smoke-ok"  # §3a pass phrase -- public by design, never a secret

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
  "$CRED_STORE_SET_WRITER")
    # The smoke step's one sanctioned write: the fixed public dummy
    # name only. Any other name is denied (exit 98) -- a regressed
    # injector must not write any other credential value.
    [ "$2" = "smoke-test" ] || \
      { echo "fake-sudo: denied store-set for $2" >&2; exit 98; } ;;
  "$CRED_REGISTRY_SET_WRITER")
    # The §3a registry binding: exactly `add-host smoke-test
    # <smoke-host>` -- nothing else may touch the main registry.
    [ "$2" = "add-host" ] && [ "$3" = "smoke-test" ] || \
      { echo "fake-sudo: denied registry-set for $2 $3" >&2; exit 98; } ;;
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

# Fake main-store set writer: mirrors proxy/cred-store-set's narrow
# contract for the smoke step only -- the name argument is validated
# like the real writer's ([A-Za-z0-9_-]+, non-empty), stdin is stored
# verbatim (no newline chomping) under the name. The smoke step is the
# injector's one sanctioned value-writing step; this fake exists so
# that step is exercised, and the fake sudo gates it to the fixed
# "smoke-test" name.
FAKE_STORE_SET = """#!/bin/sh
case "$1" in
  ''|*[!a-zA-Z0-9_-]*) echo "fake-store-set: invalid name" >&2; exit 2 ;;
esac
tmp="$(mktemp "$FAKE_SMOKE_SECRETS_DIR/.tmp.XXXXXX")"
cat > "$tmp"
if [ ! -s "$tmp" ]; then rm -f "$tmp"; echo "fake-store-set: empty value" >&2; exit 2; fi
mv -f "$tmp" "$FAKE_SMOKE_SECRETS_DIR/$1"
"""
# and semantics for the verbs the injector uses. Like the real writer,
# the host argument is validated by check_host (the canonical #150
# contract: shape + 253/63 length caps) then lowercased on add-host,
# while remove-host uses check_host_legacy (shape only) so over-long
# legacy bindings stay removable. Remove-host only removes exact
# (lowercased) matches -- so a non-lowercase variant in the registry
# (only reachable by hand-editing the JSON as root, since add-host
# lowercases) survives remove-host and must fail the injector closed,
# while a trailing-dot variant makes the writer itself fail.
# Remove-host is idempotent like the real one.
FAKE_REGISTRY_WRITER = """#!/usr/bin/env python3
import json, os, re, sys
reg_path = os.environ["FAKE_REGISTRY_FILE"]
reg = {}
if os.path.exists(reg_path):
    with open(reg_path, encoding="utf-8") as f:
        reg = json.load(f)
def check_host(h):
    # Mirror of proxy/cred-registry-set::check_host (canonical #150
    # contract: dotted-hostname shape, total length <= 253, each
    # dot-separated label <= 63 chars). Used by add-host: new bindings
    # must be canonical.
    lowered = (h or "").lower()
    if (len(lowered) > 253
            or not re.match(r"^\\.?[A-Za-z0-9-]+(\\.[A-Za-z0-9-]+)*$", lowered)
            or any(len(label) > 63
                   for label in lowered.lstrip(".").split("."))):
        sys.stderr.write("invalid host %r\\n" % (h,))
        sys.exit(1)
    return lowered
def check_name(s):
    # Mirror of proxy/cred-registry-set::check (canonical #150 name
    # contract: [A-Za-z0-9_-], 1-64 chars). add-host on an ABSENT name is
    # creation, so it enforces the canonical contract like the real writer.
    if not re.match(r"^[A-Za-z0-9_-]{1,64}$", s or ""):
        sys.stderr.write("invalid name %r\\n" % (s,))
        sys.exit(1)
    return s
def check_host_legacy(h):
    # Mirror of proxy/cred-registry-set::check_host_legacy: shape only.
    # Used by remove-host so over-long legacy bindings stay removable.
    lowered = (h or "").lower()
    if not re.match(r"^\\.?[A-Za-z0-9-]+(\\.[A-Za-z0-9-]+)*$", lowered):
        sys.stderr.write("invalid host %r\\n" % (h,))
        sys.exit(1)
    return lowered
args = sys.argv[1:]
if args[0] == "set":
    _, name, entry, pjson = args
    placement = json.loads(pjson)
    reg.setdefault(name, {})[entry] = {"placement": placement}
elif args[0] == "add-host":
    _, name, host = args
    host = check_host(host)
    # Mirror of the real writer's creation gate: add-host on an absent
    # name is creation, so the canonical name contract applies.
    entry = reg.get(name)
    if entry is None:
        check_name(name)
        entry = reg.setdefault(name, {})
    hosts = entry.setdefault("allowed_hosts", [])
    if host not in hosts:
        hosts.append(host)
elif args[0] == "remove-host":
    _, name, host = args
    host = check_host_legacy(host)
    entry = reg.get(name)
    if entry is None:
        # Mirror the real writer's creation gate: remove-host on an
        # absent name enforces the canonical contract (absent legacy
        # names fail closed); absent canonical names are a no-op.
        check_name(name)
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


# Fake MAIN registry writer: mirrors proxy/cred-registry-set's add-host
# contract only -- the one verb the injector's §3a step uses. Maintains
# MAIN_REGISTRY_FILE as a JSON object; add-host is idempotent and
# creates the entry when absent, enforcing the canonical name/host
# contract like the real writer.
FAKE_MAIN_REGISTRY_WRITER = """#!/usr/bin/env python3
import json, os, re, sys
reg_path = os.environ["MAIN_REGISTRY_FILE"]
reg = {}
if os.path.exists(reg_path):
    with open(reg_path, encoding="utf-8") as f:
        reg = json.load(f)
args = sys.argv[1:]
if len(args) != 3 or args[0] != "add-host":
    sys.stderr.write("fake-main-registry-writer: only add-host <name> <host>\\n")
    sys.exit(2)
_, name, host = args
if not re.match(r"^[A-Za-z0-9_-]{1,64}$", name or ""):
    sys.stderr.write("invalid name %r\\n" % (name,))
    sys.exit(1)
lowered = (host or "").lower()
if (len(lowered) > 253
        or not re.match(r"^\\.?[A-Za-z0-9-]+(\\.[A-Za-z0-9-]+)*$", lowered)
        or any(len(label) > 63
               for label in lowered.lstrip(".").split("."))):
    sys.stderr.write("invalid host %r\\n" % (host,))
    sys.exit(1)
entry = reg.setdefault(name, {})
hosts = entry.setdefault("allowed_hosts", [])
if lowered not in hosts:
    hosts.append(lowered)
with open(reg_path, "w", encoding="utf-8") as f:
    json.dump(reg, f, indent=2, sort_keys=True)
    f.write("\\n")
print("bound '%s' to host '%s'" % (name, lowered))
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
    """Mimics confirmd's own _deny contract (confirm/confirmd.py): the probe
    always connects from the box itself, which confirmd's auth gate refuses,
    so the expected answer is HTTP 403 + "forbidden: self-peer" body +
    "confirmd/1" Server header (GitHub #160 -- misbinding detection, not
    identity)."""
    server_version = "confirmd/1"

    def do_GET(self):
        body = b"forbidden: self-peer\n"
        self.send_response(403)
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
    smoke_secrets_dir = tmp_path / "smoke-secrets"
    smoke_secrets_dir.mkdir()
    registry_file = tmp_path / "inference-registry.json"
    allow_file = tmp_path / "inference-hosts.allow"
    ssrf_allow_file = tmp_path / "inference-ssrf.allow"
    main_allow_file = tmp_path / "hosts.allow"
    smoke_hosts_file = tmp_path / "smoke-hosts"
    sudoers_file = tmp_path / "swapd-smoke"
    main_registry_file = tmp_path / "main-registry.json"
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
    (bin_dir / "fake-main-registry-writer").write_text(
        FAKE_MAIN_REGISTRY_WRITER)
    (bin_dir / "fake-store-set").write_text(FAKE_STORE_SET)
    (bin_dir / "fake-muse").write_text(FAKE_MUSE)
    (bin_dir / "sudo").write_text(FAKE_SUDO)
    for f in ("fake-store-verify", "fake-registry-writer",
              "fake-main-registry-writer", "fake-store-set",
              "fake-muse", "sudo"):
        os.chmod(bin_dir / f, 0o755)

    proxy = _serve(_SwapProxyHandler, secrets_dir=str(secrets_dir))
    provider = _serve(_ProviderHandler, auth_seen=provider_auth, status=200)
    confirmd = _serve(_ConfirmdHandler)

    env = dict(os.environ)
    env.update({
        "CRED_STORE_VERIFY_INFERENCE": str(bin_dir / "fake-store-verify"),
        "CRED_REGISTRY_SET_INFERENCE": str(bin_dir / "fake-registry-writer"),
        "CRED_STORE_SET_WRITER": str(bin_dir / "fake-store-set"),
        "CRED_REGISTRY_SET_WRITER": str(bin_dir / "fake-main-registry-writer"),
        "MAIN_REGISTRY_FILE": str(main_registry_file),
        "FAKE_SMOKE_SECRETS_DIR": str(smoke_secrets_dir),
        "MAIN_HOSTS_ALLOW": str(main_allow_file),
        "SMOKE_HOSTS_PATH": str(smoke_hosts_file),
        "SMOKE_SUDOERS_PATH": str(sudoers_file),
        "VISUDO_BIN": "/usr/sbin/visudo",
        "INJECT_SMOKE_HOST": SMOKE_HOST,
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
        "main_allow_file": main_allow_file, "sudoers_file": sudoers_file,
        "smoke_hosts_file": smoke_hosts_file,
        "main_registry_file": main_registry_file,
        "smoke_secrets_dir": smoke_secrets_dir,
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
    assert b"echo exemption(s) still present in" in proc.stderr
    assert b"127.0.0.1" in proc.stderr
    assert b"image-build gate" in proc.stderr
    # The binding teardown still happened (defense in depth); the key
    # is byte-identical; nothing was appended anywhere.
    reg = _registry(paths["registry_file"])
    assert ECHO_HOST not in reg[KEY_NAME]["allowed_hosts"]
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY
    assert paths["ssrf_allow_file"].exists() is False


@pytest.mark.parametrize("residue", [
    "  127.0.0.1  \n",   # leading/trailing whitespace
    "LOCALHOST\n",       # case variant
    "127.0.0.1.\n",      # trailing dot
    "::1\n",             # IPv6 loopback literal (matched as a normalized
                         # address since issue #257; still an echo alias)
    "  ::1  \n",         # padded IPv6 loopback literal
    # NOTE (issue #257): ".0.0.1" used to be refused here via the old
    # string-suffix accident ("127.0.0.1".endswith(".0.0.1")). IP
    # literals no longer take the leading-dot subdomain rule, so that
    # entry matches nothing at enforcement -- it is dead config, not an
    # echo exemption. test_ignores_dead_leading_dot_partial_ip pins it.
])
def test_refuses_allowlist_format_variants(stack, residue):
    # The proxy parses allowlist entries case-insensitively,
    # whitespace-stripped, trailing-dot-stripped, with leading-dot
    # subdomain matching for hostnames (proxy/swap_addon.py::_host_in_list;
    # IP literals compare as addresses since issue #257). The injector
    # must enforce the proxy's semantics, not exact lines -- each of
    # these is a live echo exemption the old grep -qxF missed.
    env, paths = stack
    _seed_real_key(paths)
    paths["allow_file"].write_text(residue)
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"echo exemption(s) still present in" in proc.stderr
    assert residue.strip().encode() in proc.stderr
    assert b"image-build gate" in proc.stderr


def test_ignores_dead_leading_dot_partial_ip(stack):
    # Issue #257: a leading-dot entry holding a partial IP (".0.0.1")
    # matches nothing under the fixed matcher -- the leading-dot rule is
    # a hostname rule and IP literals compare as addresses. It is dead
    # config, not an echo exemption, so the injector must not refuse
    # on it (over-refusal would be a divergence from proxy semantics,
    # the exact failure mode harness/test_proxy_match.py guards).
    env, paths = stack
    _seed_real_key(paths)
    paths["allow_file"].write_text(".0.0.1\n")
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert _report(proc)["steps"]["fixture_teardown"] == "ok"


@pytest.mark.parametrize("residue", [
    "127.0.0.0/8\n",     # CIDR covering loopback
    "127.0.0.1/32\n",    # bare IP promoted to /32
    "LOCALHOST\n",       # hostname, case variant
    "  ::1  \n",         # IPv6 loopback, padded
])
def test_refuses_ssrf_format_variants(stack, residue):
    # Mirror of proxy/swap_addon.py::_parse_ssrf_allow: CIDR literals
    # are honored, bare IPs become /32 (/128 for v6) nets, hostnames are
    # lowercased. Each of these exempts the echo host from the proxy's
    # SSRF guard.
    env, paths = stack
    _seed_real_key(paths)
    paths["ssrf_allow_file"].write_text(residue)
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"echo exemption(s) still present in" in proc.stderr
    assert residue.strip().encode() in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_allowlist_ignores_comments_and_blanks(stack):
    # No false positives: comments, blanks, and non-echo entries pass.
    env, paths = stack
    _seed_real_key(paths)
    paths["allow_file"].write_text(
        "# 127.0.0.1 -- this is a comment\n\napi.provider.example\n")
    paths["ssrf_allow_file"].write_text("10.0.0.0/8\n")
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert _report(proc)["steps"]["fixture_teardown"] == "ok"


def test_refuses_registry_case_variant(stack):
    # "LOCALHOST" in allowed_hosts is honored by the proxy
    # (_host_in_list lowercases) but the narrow writer lowercases its
    # argument and only removes exact matches, so it cannot remove this
    # variant: the injector must fail closed, not silently proceed.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": ["LOCALHOST", PROVIDER_HOST],
        }
    }))
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"still bound to echo host(s)" in proc.stderr
    assert b"LOCALHOST" in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_refuses_registry_trailing_dot_variant(stack):
    # "127.0.0.1." is stripped to the echo host by the proxy's matcher.
    # The real writer's check_host rejects the trailing-dot form, so
    # remove-host fails and the run fails closed (non-zero) either way.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": ["127.0.0.1.", PROVIDER_HOST],
        }
    }))
    proc = _run_injector(env)
    assert proc.returncode != 0
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_refuses_unreadable_registry(stack):
    # The registry cannot be read at all (absent file): the step-2
    # teardown verification (pre- AND post-teardown reads, both through
    # echo_bound_hosts) must fail closed, not verify blindly.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    # registry_file intentionally never created
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"cannot read the inference registry" in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_refuses_corrupt_registry(stack):
    # Invalid JSON in the registry: the teardown is unverifiable, so
    # the run fails closed instead of provisioning onto an unknown
    # binding state.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    paths["registry_file"].write_text("{not valid json")
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"cannot read the inference registry" in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_refuses_unparseable_allowlist(stack):
    # A non-UTF-8 allow file cannot be parsed for echo exemptions:
    # fail closed rather than verifying the teardown blindly.
    env, paths = stack
    _seed_real_key(paths)
    paths["allow_file"].write_bytes(b"\xff\xfe not utf-8 \x80\n")
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"cannot parse" in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_refuses_registry_ipv6_loopback_literal(stack):
    # "::1" in allowed_hosts: since issue #257 the proxy's _host_in_list
    # matches the "::1" literal as a normalized address, and the
    # injector's echo detection agrees through the shared matcher (the
    # old fail-closed literal special-case is gone); the narrow writer's
    # check_host rejects the ":" form, so remove-host fails and the run
    # must fail closed either way.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": ["::1", PROVIDER_HOST],
        }
    }))
    proc = _run_injector(env)
    assert proc.returncode != 0
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_proxy_match_single_mirror_invariant():
    # ARCHITECTURE INVARIANT: the injector must not hand-mirror the
    # proxy's matching semantics inline. All three echo-detection call
    # sites (registry teardown, allowlist scan, key assertion) shell out
    # to harness/proxy_match.py -- the single shared mirror of
    # proxy/swap_addon.py::_host_in_list and _parse_ssrf_allow. The
    # behavioral agreement with the real proxy functions is pinned by
    # harness/test_proxy_match.py's drift tripwire; this test pins the
    # delegation itself, so a future edit cannot silently reintroduce a
    # second copy.
    src = open(INJECTOR, encoding="utf-8").read()
    assert "def host_in_list(" not in src, \
        "injector reintroduced an inline _host_in_list mirror"
    assert "def _parse_ssrf_allow(" not in src, \
        "injector reintroduced an inline _parse_ssrf_allow mirror"
    helper = os.path.join(HERE, "proxy_match.py")
    assert os.path.exists(helper), "harness/proxy_match.py missing"
    for subcommand in ("echo-bound-hosts",
                       "allowlist-echo-entries",
                       "assert-key-binding"):
        assert ("proxy_match.py\" " + subcommand) in src or \
               ("proxy_match.py' " + subcommand) in src or \
               ("proxy_match.py " + subcommand) in src, \
            "injector no longer delegates to proxy_match.py %s" % subcommand


def test_refuses_ssrf_allowlist_residue(stack):
    # Same fail-closed contract for the inference proxy's OWN ssrf
    # exemption file (finding 29's egress guard).
    env, paths = stack
    _seed_real_key(paths)
    paths["ssrf_allow_file"].write_text(ECHO_HOST + "\n")
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"echo exemption(s) still present in" in proc.stderr
    assert b"127.0.0.1" in proc.stderr
    assert b"image-build gate" in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY


def test_refuses_loopback_alias_residue(stack):
    # A `localhost` entry is the same echo exemption under another name.
    env, paths = stack
    _seed_real_key(paths)
    paths["allow_file"].write_text("localhost\n")
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"echo exemption(s) still present in" in proc.stderr
    assert b"localhost" in proc.stderr


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


def test_tenant_record_preserves_existing_mode(stack):
    # Security B1: the atomic write must preserve the old open("w")
    # semantics -- truncating an EXISTING file leaves its mode alone.
    # A pre-hardened 0600 tenant record must not be widened to 0644.
    import os
    import stat
    env, paths = stack
    _seed_real_key(paths)
    tenant_record = paths["tenant_record"]
    tenant_record.write_text("{}\n")
    os.chmod(tenant_record, 0o600)
    env = dict(env)
    env["INJECT_TENANT_ID"] = "tenant-42"
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    record = json.loads(tenant_record.read_text())
    assert record["tenant_id"] == "tenant-42"
    assert stat.S_IMODE(os.stat(tenant_record).st_mode) == 0o600


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


def test_identity_install_is_no_follow_regular_file(stack):
    # Issue #258: the install pins the destination directory by fd and
    # creates authorized_keys O_NOFOLLOW through it. The installed file
    # must be a regular file (lstat, not stat -- a symlink would pass
    # a stat-based check), 0600, byte-identical.
    import stat as statmod
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
    installed = paths["agent_home"] / ".ssh" / "authorized_keys"
    assert statmod.S_ISREG(os.lstat(installed).st_mode)
    assert not os.path.islink(installed)
    assert (installed.stat().st_mode & 0o777) == 0o600
    assert installed.read_text() == pubkey


def test_identity_refuses_fifo_destination(stack):
    # Issue #258: a FIFO planted at the destination must refuse
    # fail-closed, not hang the install open. The no-follow open uses
    # O_NONBLOCK plus an S_ISREG re-check, so the run exits 1 quickly.
    env, paths = stack
    _seed_real_key(paths)
    identity_dir = paths["secrets_dir"] / "identity"
    identity_dir.mkdir()
    (identity_dir / "authorized_keys").write_text(
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAItestkeymaterial tenant@muse\n")
    ssh_dir = paths["agent_home"] / ".ssh"
    ssh_dir.mkdir()
    os.mkfifo(ssh_dir / "authorized_keys")
    env = dict(env)
    env["INJECT_IDENTITY_DIR"] = str(identity_dir)
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"not a regular file" in proc.stderr


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
    # an allowlist through a privilege surface and never lists the
    # secrets dir.
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
    # The smoke step's store write goes through the real production
    # prefix (sudo -u swapd) too, so the fake sudo sees it.
    assert env["CRED_STORE_SET_WRITER"] in calls


def test_missing_image_version(stack):
    env, paths = stack
    env = dict(env)
    env.pop("INJECT_IMAGE_VERSION", None)
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert b"INJECT_IMAGE_VERSION is required" in proc.stderr


@pytest.mark.parametrize("var", ["CRED_STORE_VERIFY_INFERENCE",
                                 "CRED_REGISTRY_SET_INFERENCE",
                                 "CRED_STORE_SET_WRITER",
                                 "CRED_REGISTRY_SET_WRITER",
                                 "VISUDO_BIN",
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


def test_only_writes_smoke_dummy(stack):
    # Structural proof the injector writes exactly one credential
    # value: the §3a smoke-test dummy (public by design). The fake bin
    # dir holds no OTHER store writer, the fake sudo denies the smoke
    # writer for any other name (exit 98), and the real tenant key file
    # must be byte-identical after a run.
    env, paths = stack
    _seed_real_key(paths)
    assert not (paths["bin_dir"] / "fake-store-writer").exists()
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert b"fake-sudo: denied" not in proc.stderr
    assert (paths["secrets_dir"] / KEY_NAME).read_text() == REAL_KEY
    assert (paths["smoke_secrets_dir"] / SMOKE_CRED).read_bytes() == \
        SMOKE_DUMMY.encode()


def test_teardown_subdomain_echo_binding(stack):
    # The leading-dot gap: a ".localhost" binding matches *.localhost
    # (loopback) at enforcement, so it is a live echo exemption -- but
    # the old inline logic only matched bare aliases and would have let
    # it survive teardown as "clean". The shared mirror flags it, the
    # narrow writer removes it, the run proceeds.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": [".localhost", PROVIDER_HOST],
        }
    }))
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    report = _report(proc)
    assert report["fixture_teardown_detail"] == "removed"
    reg = _registry(paths["registry_file"])
    assert reg[KEY_NAME]["allowed_hosts"] == [PROVIDER_HOST]


def test_refuses_allowlist_subdomain_residue(stack):
    # Same gap on the allowlist side: ".localhost" in
    # inference-hosts.allow is a live exemption the injector cannot
    # remove through any narrow path -- fail closed, name the
    # image-build gate.
    env, paths = stack
    _seed_real_key(paths)
    paths["allow_file"].write_text(".localhost\n")
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"echo exemption(s) still present in" in proc.stderr
    assert b".localhost" in proc.stderr
    assert b"image-build gate" in proc.stderr


def test_teardown_deep_subdomain_echo_binding(stack):
    # The blocker's regression test at suite level: ".sub.localhost"
    # matches x.sub.localhost at enforcement and bare "sub.localhost"
    # matches that exact (loopback) name -- both are live echo
    # exemptions the first version of the shared mirror still missed.
    env, paths = stack
    (paths["secrets_dir"] / KEY_NAME).write_text(REAL_KEY)
    paths["registry_file"].write_text(json.dumps({
        KEY_NAME: {
            "access_token": {"placement": "bearer_header"},
            "allowed_hosts": [".sub.localhost", "sub.localhost",
                              PROVIDER_HOST],
        }
    }))
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    report = _report(proc)
    assert report["fixture_teardown_detail"] == "removed"
    reg = _registry(paths["registry_file"])
    assert reg[KEY_NAME]["allowed_hosts"] == [PROVIDER_HOST]


def test_proxy_match_helper_is_load_bearing(stack):
    # Mutation probe: the injector must actually USE
    # harness/proxy_match.py. With the helper moved aside, the happy
    # path must fail (refuse), never silently pass with the checks
    # skipped. Restored in `finally` so the suite stays green.
    helper = os.path.join(HERE, "proxy_match.py")
    parked = helper + ".parked-by-test"
    os.rename(helper, parked)
    try:
        env, paths = stack
        _seed_real_key(paths)
        proc = _run_injector(env)
        assert proc.returncode != 0, \
            "injector passed with proxy_match.py missing"
        assert b"proxy_match.py" in proc.stderr or \
            b"No such file" in proc.stderr, proc.stderr.decode()
    finally:
        os.rename(parked, helper)


def test_tenant_record_atomic_no_temp_litter(stack):
    # The record write is atomic (temp file + fsync + os.replace): a
    # successful run leaves the complete record and no temp litter.
    env, paths = stack
    _seed_real_key(paths)
    env = dict(env)
    env["INJECT_TENANT_ID"] = "tenant-42"
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    record = json.loads(paths["tenant_record"].read_text())
    assert record["tenant_id"] == "tenant-42"
    litter = [p for p in paths["tenant_record"].parent.iterdir()
              if p.name.startswith(".tenant.json.")]
    assert litter == [], litter


def test_tenant_record_write_failure_leaves_no_torn_record(stack):
    # Forcing the rename to fail (record path is a directory) proves
    # the atomic-write contract from the outside: the run refuses, the
    # pre-existing content at the path is untouched, no partial record
    # is left behind, and the temp file is cleaned up.
    env, paths = stack
    _seed_real_key(paths)
    record_dir = paths["tenant_record"]
    record_dir.mkdir()
    (record_dir / "sentinel").write_text("pre-existing\n")
    env = dict(env)
    env["INJECT_TENANT_ID"] = "tenant-42"
    proc = _run_injector(env)
    assert proc.returncode != 0
    assert record_dir.is_dir()
    assert (record_dir / "sentinel").read_text() == "pre-existing\n"
    litter = [p for p in record_dir.parent.iterdir()
              if p.name.startswith(".tenant.json.")]
    assert litter == [], litter


def test_tenant_record_reports_digest_lifecycle(stack):
    # Issue #258: the fd-pinned write verifies by reading the record
    # back through the pinned dir and reports the digest lifecycle on
    # stderr: "initialized" on first write, "updated" (old -> new) on a
    # rewrite. A changed tenant id guarantees a changed payload, so the
    # updated branch is deterministic (injected_at alone could collide
    # within one second).
    env, paths = stack
    _seed_real_key(paths)
    env = dict(env)
    env["INJECT_TENANT_ID"] = "tenant-42"
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert b"tenant record initialized (sha256 " in proc.stderr
    env["INJECT_TENANT_ID"] = "tenant-43"
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert b"tenant record updated (sha256 " in proc.stderr
    assert b" -> " in proc.stderr
    record = json.loads(paths["tenant_record"].read_text())
    assert record["tenant_id"] == "tenant-43"

# ---------------------------------------------------------------------------
# §3a smoke assets (G6)
# ---------------------------------------------------------------------------

def _smoke_sudoers_lines(paths):
    return paths["sudoers_file"].read_text().splitlines()


def test_smoke_assets_happy_path(stack):
    # The §3a provision assets land together: the public dummy
    # credential (exact public bytes, no newline), the operator's echo
    # host in the MAIN hosts.allow AND in the proxy's smoke-only
    # scoping list, and a visudo-valid scoped sudoers fragment for the
    # tenant agent user whose granted argv is pinned to the smoke-test
    # dummy install. The report's smoke_assets step reads "ok".
    env, paths = stack
    _seed_real_key(paths)
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()

    assert (paths["smoke_secrets_dir"] / SMOKE_CRED).read_bytes() == \
        SMOKE_DUMMY.encode()
    allow_lines = paths["main_allow_file"].read_text().splitlines()
    assert SMOKE_HOST in allow_lines
    # The proxy's smoke-only list holds the same host: enforcement
    # swaps only the smoke-test credential for it (never a real
    # secret), so the echo endpoint cannot become a read oracle.
    assert paths["smoke_hosts_file"].read_text().splitlines() == \
        [SMOKE_HOST]

    lines = _smoke_sudoers_lines(paths)
    agent_user = env["INJECT_AGENT_USER"]
    # S1: the granted argv is pinned -- the tenant agent user may run
    # exactly `cred-store-set smoke-test`, never any other name.
    expected = ("%s ALL=(swapd) NOPASSWD: "
                "/usr/local/bin/cred-store-set smoke-test") % agent_user
    assert expected in lines
    assert not any(ln == ("%s ALL=(swapd) NOPASSWD: "
                          "/usr/local/bin/cred-store-set") % agent_user
                   for ln in lines), \
        "the smoke fragment must pin the smoke-test argv, not the bare writer"
    assert not any("*" in ln for ln in lines), \
        "the smoke fragment must carry no wildcards"
    # The installed fragment re-validates under the REAL visudo (the
    # injector already validated pre-install; this proves the file on
    # disk is good, not just the temp copy).
    vis = subprocess.run(["/usr/sbin/visudo", "-c", "-f",
                          str(paths["sudoers_file"])],
                         capture_output=True, timeout=30)
    assert vis.returncode == 0, vis.stderr.decode()

    report = _report(proc)
    assert report["steps"]["smoke_assets"] == "ok"
    assert "smoke_assets" not in report["deferred"]


def test_smoke_registry_binding(stack):
    # 8d: the proxy's grant scoping refuses unbound credentials, so
    # the §3a swap needs smoke-test bound to the echo host in the MAIN
    # registry -- otherwise the placeholder would pass through
    # unchanged and the check could never pass.
    env, paths = stack
    _seed_real_key(paths)
    assert _run_injector(env).returncode == 0
    reg = json.loads(paths["main_registry_file"].read_text())
    assert SMOKE_HOST in reg[SMOKE_CRED]["allowed_hosts"]
    # Idempotent: a second run adds no duplicate binding.
    assert _run_injector(env).returncode == 0
    reg = json.loads(paths["main_registry_file"].read_text())
    assert reg[SMOKE_CRED]["allowed_hosts"].count(SMOKE_HOST) == 1


def test_smoke_registry_binding_failure_fails_closed(stack):
    # A failing registry writer fails the provision (exit 1) -- the
    # §3a assets are all-or-nothing for box-live gating.
    env, paths = stack
    _seed_real_key(paths)
    env = dict(env)
    env["CRED_REGISTRY_SET_WRITER"] = "/bin/false"
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"smoke registry binding failed" in proc.stderr


def test_smoke_credential_install_failure_fails_closed(stack):
    # The 8a store-set failure is the highest-sensitivity new branch:
    # the injector's ONE sanctioned credential-value write must fail
    # the provision (exit 1), never half-install the §3a assets.
    env, paths = stack
    _seed_real_key(paths)
    env = dict(env)
    env["CRED_STORE_SET_WRITER"] = "/bin/false"
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"smoke credential install failed" in proc.stderr


def test_single_sanctioned_value_write_invariant():
    # ARCHITECTURE INVARIANT: the injector's never-write-a-credential-
    # value rule has exactly ONE sanctioned exception -- the §3a
    # smoke-test dummy. This tripwire pins it mechanically: the narrow
    # store writer may be invoked exactly once, and its credential-name
    # argument must be the SMOKE_CRED_NAME constant. A future step that
    # widens the exception fails CI loudly instead of sliding through
    # review. The name literal must also agree with the proxy's
    # hardcoded smoke-test knowledge (swap_addon.py's _resolve gate and
    # the response-scrub exemption), so a rename breaks loudly too.
    src = open(INJECTOR, encoding="utf-8").read()
    invocations = [
        (i, line) for i, line in enumerate(src.splitlines(), 1)
        if not line.strip().startswith("#")
        and "$STORE_SET_WRITER" in line and "run_priv" in line
    ]
    assert len(invocations) == 1, \
        "expected exactly one sanctioned store-set invocation, found: %r" \
        % (invocations,)
    i, line = invocations[0]
    assert re.search(r'run_priv[ \t]+"\$STORE_SET_WRITER"'
                     r'[ \t]+"\$SMOKE_CRED_NAME"', line), \
        "line %d: store-set invocation not pinned to SMOKE_CRED_NAME: %r" \
        % (i, line)
    name_m = re.search(r'^SMOKE_CRED_NAME="([^"]+)"', src, re.M)
    assert name_m, "SMOKE_CRED_NAME constant missing from injector"
    addon = open(os.path.join(HERE, "..", "proxy", "swap_addon.py"),
                 encoding="utf-8").read()
    assert '"%s"' % name_m.group(1) in addon, \
        "proxy no longer hardcodes the smoke credential name %r " \
        "(literal agreement broken)" % name_m.group(1)


def test_smoke_assets_idempotent(stack):
    # A second run changes nothing: no duplicate allowlist line, the
    # sudoers fragment is byte-identical, the dummy is unchanged, and
    # the smoke-only list is untouched.
    env, paths = stack
    _seed_real_key(paths)
    assert _run_injector(env).returncode == 0
    allow_before = paths["main_allow_file"].read_bytes()
    sudoers_before = paths["sudoers_file"].read_bytes()
    smoke_hosts_before = paths["smoke_hosts_file"].read_bytes()
    assert _run_injector(env).returncode == 0
    assert paths["main_allow_file"].read_bytes() == allow_before
    assert paths["main_allow_file"].read_text().splitlines().count(
        SMOKE_HOST) == 1
    assert paths["sudoers_file"].read_bytes() == sudoers_before
    assert paths["smoke_hosts_file"].read_bytes() == smoke_hosts_before


def test_smoke_host_missing_refuses(stack):
    env, paths = stack
    env = dict(env)
    env.pop("INJECT_SMOKE_HOST", None)
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert b"INJECT_SMOKE_HOST is required" in proc.stderr


@pytest.mark.parametrize("bad", [
    "smoke host",            # whitespace
    "smoke..example.com",    # empty label
    ".smoke.example.com",    # leading dot
    "smoke.example.com.",    # trailing dot (canonical form has none)
    "-smoke.example.com",    # leading hyphen
    "localhost",             # bare name -- no dot, matches nothing useful
    "smoke_example.com",     # underscore is not a hostname char
    "x" * 64 + ".example.com",  # over-long label
    "x" * 63 + "." + "x" * 63 + "." + "x" * 63 + "." + "x" * 62,
    # 254 chars overall: every label is legal, only the total is over
    "smoke.EXAMPLE.com\nevil",  # embedded newline
])
def test_smoke_host_invalid_refuses(stack, bad):
    env, paths = stack
    env = dict(env)
    env["INJECT_SMOKE_HOST"] = bad
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert b"invalid host shape" in proc.stderr


def test_smoke_host_uppercase_normalized(stack):
    # The proxy's host matching is case-insensitive; the injector
    # stores the canonical lowercase form.
    env, paths = stack
    env = dict(env)
    env["INJECT_SMOKE_HOST"] = "Smoke.Example.COM"
    _seed_real_key(paths)
    proc = _run_injector(env)
    assert proc.returncode == 0, proc.stderr.decode()
    assert paths["main_allow_file"].read_text().splitlines() == \
        [SMOKE_HOST]


@pytest.mark.parametrize("hostile", [
    "agent; rm -rf /",          # shell metacharacters
    "agent\nALL ALL=(ALL) NOPASSWD: ALL",  # embedded newline: grep is
    # line-oriented, so the second line would pass a naive anchored
    # match and smuggle a sudoers rule past the check.
])
def test_smoke_agent_user_unsafe_refuses(stack, hostile):
    # The agent user is interpolated into a sudoers line -- a hostile
    # value must refuse before any fragment is written.
    env, paths = stack
    env = dict(env)
    env["INJECT_AGENT_USER"] = hostile
    _seed_real_key(paths)
    proc = _run_injector(env)
    assert proc.returncode == 2
    assert b"not a safe sudoers username" in proc.stderr
    assert not paths["sudoers_file"].exists()


def test_smoke_fragment_mode(stack):
    # The fragment installs mode 0440 like deploy.sh's sudoers install.
    env, paths = stack
    _seed_real_key(paths)
    assert _run_injector(env).returncode == 0
    import stat
    mode = stat.S_IMODE(os.stat(paths["sudoers_file"]).st_mode)
    assert mode == 0o440, oct(mode)


def test_smoke_allow_append_no_trailing_newline(stack):
    # E1: the allow file is image-built, not injector-owned -- it may
    # not end in a newline. A blind append would glue the smoke host
    # onto the last line, corrupting that entry AND failing to add
    # ours, while still reporting ok. Run twice: lines must be exactly
    # [old, SMOKE_HOST] both times.
    env, paths = stack
    _seed_real_key(paths)
    paths["main_allow_file"].write_bytes(b"github.example.com")
    assert _run_injector(env).returncode == 0
    assert paths["main_allow_file"].read_text().splitlines() == \
        ["github.example.com", SMOKE_HOST]
    assert _run_injector(env).returncode == 0
    assert paths["main_allow_file"].read_text().splitlines() == \
        ["github.example.com", SMOKE_HOST]


def test_smoke_allow_append_trailing_newline(stack):
    # The mirror of the no-trailing-newline case: a well-formed allow
    # file already ending in a newline takes the direct-append branch
    # (no gluing, no separator correction needed).
    env, paths = stack
    _seed_real_key(paths)
    paths["main_allow_file"].write_bytes(b"github.example.com\n")
    assert _run_injector(env).returncode == 0
    assert paths["main_allow_file"].read_bytes() == \
        b"github.example.com\n" + SMOKE_HOST.encode() + b"\n"


def test_smoke_hosts_union_preserves_prior_entries(stack):
    # UNION, never replace: a re-provision with a new echo host keeps
    # the previous entry. hosts.allow is append-only, so the rotated-
    # out host lingers there; dropping it from this durable list
    # (e.g. across a proxy restart) would silently un-restrict it and
    # reopen the echo read oracle. Comments and blank lines are not
    # carried over; duplicates collapse to one entry.
    env, paths = stack
    _seed_real_key(paths)
    paths["smoke_hosts_file"].write_text(
        "# stale comment\n\nold.example.com\n", encoding="utf-8")
    assert _run_injector(env).returncode == 0
    assert paths["smoke_hosts_file"].read_text().splitlines() == \
        ["old.example.com", SMOKE_HOST]
    # Idempotent: a second run with the same host changes nothing.
    assert _run_injector(env).returncode == 0
    assert paths["smoke_hosts_file"].read_text().splitlines() == \
        ["old.example.com", SMOKE_HOST]


def test_smoke_fragment_differing_preexisting_replaced(stack):
    # The un-owned fragment path: a pre-existing fragment with DIFFERENT
    # content is replaced by the pinned expected fragment (per-step
    # drift repair), not merged or left in place.
    env, paths = stack
    _seed_real_key(paths)
    paths["sudoers_file"].write_text(
        "swapd ALL=(ALL) NOPASSWD: ALL\n", encoding="utf-8")
    assert _run_injector(env).returncode == 0
    lines = _smoke_sudoers_lines(paths)
    agent_user = env["INJECT_AGENT_USER"]
    expected = [
        "# spark-vm §3a smoke check (G6): the tenant agent user may",
        "# re-install ONLY the public smoke-test dummy credential via",
        "# the narrow writer, value on stdin. The argv is pinned: any",
        "# other credential name is refused by sudo itself.",
        "# Literal paths, no wildcards.",
        ("%s ALL=(swapd) NOPASSWD: "
         "/usr/local/bin/cred-store-set smoke-test") % agent_user,
    ]
    assert lines == expected, lines


def test_smoke_sudoers_path_is_directory(stack):
    # Q1: mv into a directory "succeeds" while installing nothing where
    # the gate looks -- the injector must fail closed instead of
    # reporting ok.
    env, paths = stack
    _seed_real_key(paths)
    paths["sudoers_file"].mkdir()
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"is a directory" in proc.stderr
    assert list(paths["sudoers_file"].iterdir()) == []


def test_smoke_hosts_path_is_directory(stack):
    # Same fail-closed shape for the smoke-only host list: a directory
    # at SMOKE_HOSTS_PATH must not silently mis-install.
    env, paths = stack
    _seed_real_key(paths)
    paths["smoke_hosts_file"].mkdir()
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"is a directory" in proc.stderr
    assert list(paths["smoke_hosts_file"].iterdir()) == []


def test_smoke_hosts_stale_entry_preserved(stack):
    # The smoke-only list is a UNION, not a replacement: a host from
    # an earlier run is preserved, because hosts.allow is append-only
    # and dropping it here would silently un-restrict the retired
    # host (e.g. across a proxy restart), reopening the echo read
    # oracle.
    env, paths = stack
    _seed_real_key(paths)
    paths["smoke_hosts_file"].write_text("old-smoke.example.com\n")
    assert _run_injector(env).returncode == 0
    assert paths["smoke_hosts_file"].read_text().splitlines() == \
        ["old-smoke.example.com", SMOKE_HOST]


def test_smoke_visudo_failure_fails_closed(stack):
    # A failing VISUDO_BIN must fail the provision with nothing
    # installed and the temp fragment cleaned up -- the pre-install
    # gate is real, not decorative.
    env, paths = stack
    _seed_real_key(paths)
    env = dict(env)
    env["VISUDO_BIN"] = "/bin/false"
    proc = _run_injector(env)
    assert proc.returncode == 1
    assert b"visudo validation" in proc.stderr
    assert not paths["sudoers_file"].exists()
    assert list(paths["sudoers_file"].parent.glob(".swapd-smoke.*")) == []
