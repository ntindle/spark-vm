#!/bin/bash
# inject-provision-state.sh -- the provision-time injector (R2, slice 3).
#
# Implements docs/PRE_SEEDED_HARNESS_RESEARCH.md section 4's inject list.
# Runs ONCE per tenant box at provision time, after the H4 provider driver
# has created the box and BEFORE box-live flips. Driven by the control
# plane over the H4 dial() stream (harness/provider_iface.py); runs as
# root on the tenant box, like proxy/deploy.sh.
#
# Steps, in order:
#   1. Manifest preflight: harness/check-image-manifest.sh against the
#      control plane's pinned image SHA (INJECT_IMAGE_VERSION, required).
#      Fails closed on any drift -- the injector never provisions onto an
#      image it was not pinned to.
#   2. Gate-fixture teardown: unbinds the llm-api -> echo-host (127.0.0.1)
#      registry binding through the narrow registry writer (idempotent),
#      then VERIFIES the binding is gone AND that the echo host is absent
#      from inference-hosts.allow and the inference proxy's own
#      inference-ssrf.allow. Fail-closed: the injector has no narrow path
#      to remove allowlist lines (production sudoers is append-only by
#      design), so a surviving echo entry is REFUSED -- loudly, naming the
#      image-build gate (which runs as root on the build box, pre-publish)
#      as the owner of allowlist teardown. The binding removal alone is
#      what stops a swap toward the echo host; the refusal is what keeps a
#      half-torn-down fixture from ever coexisting with a real key.
#   3. Real-key assertion: the tenant's inference credential is installed
#      by the OPERATOR through the existing human-only grant-writer path
#      (SETUP.md "Inference-model recipe") BEFORE this runs. The injector
#      asserts, never handles: the registry must bind llm-api (with
#      bearer_header placement) to at least one non-loopback host, and a
#      BLIND compare (proxy/cred-store-verify-inference) must confirm the
#      stored value is NOT the public fixture dummy. The real value is
#      never read, logged, or persisted by this script -- only the
#      one-bit "is / is-not the dummy" answer leaves the store.
#   4. swapd CA presence: the fresh per-tenant CA
#      (/home/swapd/.mitmproxy/mitmproxy-ca.pem) must exist. Generation +
#      trust-bundle install belong to the first-boot unit (mitmdump's
#      private key is never baked into the image); the injector gates on
#      presence and fails closed when the unit has not run. The key
#      material is never read.
#   5. Tenant identity (H9 interface): when INJECT_IDENTITY_DIR holds an
#      authorized_keys file, each line is validated (public-key shapes
#      only -- any "PRIVATE KEY" line refuses, fail-closed) and installed
#      as the agent user's ~/.ssh/authorized_keys (0700/0600, verified
#      byte-identical). When absent, the step is DEFERRED -- recorded in
#      the report as pending on H9, never silently skipped.
#   6. confirmd tenant attribution (H10 interface): when INJECT_TENANT_ID
#      is set (validated ^[A-Za-z0-9_-]{1,64}$), a tenant record
#      {tenant_id, image_version, injected_at} is written for the future
#      confirmd tenant slice to consume. When absent: DEFERRED on H10.
#   7. Provision-mode probe: harness/harness-auth-probe proves the
#      injected key is accepted by the provider through the inference
#      proxy, then confirmd liveness. A probe failure maps to R1's
#      provisioning-failed -- box-live must not flip.
#
# Exit codes: 0 ok (report on stdout) - 1 a step failed (provisioning-
# failed; the control plane must not flip box-live) - 2 usage/config
# error (fail-closed prechecks). On success the script prints ONE JSON
# report on stdout; the `deferred` list names the interface points still
# owned by unlanded mechanics (H9/H10). Box-live gating: the control
# plane requires the manifest, fixture_teardown, inference_key,
# swapd_ca, and probe steps to read "ok"; identity and
# confirmd_attribution may read "ok" or "deferred (H9)"/"deferred (H10)"
# (then named in deferred[]).
#
# The injector never writes a credential value: the only store writer it
# touches is the blind compare. A test asserting the real key file is
# byte-identical after a run is the standing proof (see
# harness/test_inject_provision_state.py).
#
# Env overrides (tests / nonstandard layouts):
#   INJECT_IMAGE_VERSION   REQUIRED: the control plane's pinned image SHA.
#   INJECT_MANIFEST        image manifest path (default
#                          /etc/sparkvm/image-manifest.json -- baked into
#                          the image by the image-build gate)
#   INJECT_MANIFEST_CHECK  manifest preflight script (default alongside
#                          this script)
#   CRED_STORE_VERIFY_INFERENCE
#                          inference store blind-compare writer (default
#                          /usr/local/bin/cred-store-verify-inference;
#                          never reveals the stored value)
#   CRED_REGISTRY_SET_INFERENCE
#                          inference registry writer (default
#                          /usr/local/bin/cred-registry-set-inference)
#   INFERENCE_HOSTS_ALLOW  hosts.allow path (default
#                          /home/swapd/inference-hosts.allow)
#   INFERENCE_SSRF_ALLOW   inference ssrf.allow path (default
#                          /home/swapd/inference-ssrf.allow)
#   INFERENCE_SECRETS_DIR  inference secrets dir (default
#                          /home/swapd/inference-secrets)
#   INFERENCE_REGISTRY_FILE
#                          inference registry path (default
#                          /home/swapd/inference-registry.json)
#   SUDO_PREFIX            privilege prefix, e.g. "sudo -u swapd"
#                          (default "sudo -u swapd"; empty runs directly)
#   SWAPD_CA_DIR           swapd CA dir (default /home/swapd/.mitmproxy)
#   INJECT_IDENTITY_DIR    optional dir holding `authorized_keys`
#                          (tenant SSH public keys; H9 fills this in)
#   INJECT_AGENT_USER      tenant agent user (default agent -- the image
#                          bakes this user; its absence is image drift)
#   INJECT_AGENT_HOME      tenant agent home (default /home/agent)
#   INJECT_TENANT_ID       optional tenant id (H10 fills this in)
#   INJECT_TENANT_RECORD   tenant record path (default
#                          /etc/sparkvm/tenant.json)
#   HARNESS_PROBE_BIN      probe path (default alongside this script)
# The probe reads its own env (PROBE_MODE=provision is forced here;
# PROBE_PROXY, PROBE_MUSE_BIN, PROBE_BASE_URL, PROBE_CONFIRMD_URL come
# from the caller) directly.
set -euo pipefail
umask 022

# Public, non-secret, on purpose. The blind compare asserts the stored
# value is NOT this dummy -- i.e. a real tenant key landed. Keep in sync
# with FIXTURE_DUMMY in harness/install-gate-fixture.sh and
# INSTALLER_DUMMY in harness/test_install_gate_fixture.py.
FIXTURE_DUMMY="GATE-FIXTURE-DUMMY-NOT-A-SECRET"
# The inference proxy holds exactly one credential and the store writer
# hardcodes its filename (finding 31). Keep in sync with KEY_NAME in
# harness/install-gate-fixture.sh.
KEY_NAME="llm-api"
# The gate fixture's echo host. The teardown removes the llm-api binding
# to exactly this host; any loopback alias still present in the allow
# files fails closed (step 2).
ECHO_HOST="127.0.0.1"
# Loopback aliases the teardown treats as the echo host for the fail-
# closed allowlist check. The fixture only ever used 127.0.0.1; the
# aliases close the obvious bypass where a later fixture variant binds
# `localhost` instead.
ECHO_ALIASES="127.0.0.1 localhost ::1"

if [ -z "${INJECT_IMAGE_VERSION:-}" ]; then
    echo "inject-provision-state: refusing: INJECT_IMAGE_VERSION is required (the control plane's pinned image SHA)" >&2
    exit 2
fi
IMAGE_VERSION="$INJECT_IMAGE_VERSION"

STORE_VERIFY_WRITER="${CRED_STORE_VERIFY_INFERENCE:-/usr/local/bin/cred-store-verify-inference}"
REGISTRY_WRITER="${CRED_REGISTRY_SET_INFERENCE:-/usr/local/bin/cred-registry-set-inference}"
ALLOW_FILE="${INFERENCE_HOSTS_ALLOW:-/home/swapd/inference-hosts.allow}"
SSRF_ALLOW_FILE="${INFERENCE_SSRF_ALLOW:-/home/swapd/inference-ssrf.allow}"
REGISTRY_FILE="${INFERENCE_REGISTRY_FILE:-/home/swapd/inference-registry.json}"
# A bare `-` (not `:-`) preserves an explicitly empty SUDO_PREFIX --
# the test seam; unset keeps the production default.
SUDO_PREFIX="${SUDO_PREFIX-sudo -u swapd}"
HERE="$(dirname "$0")"
MANIFEST_CHECK="${INJECT_MANIFEST_CHECK:-$HERE/check-image-manifest.sh}"
MANIFEST="${INJECT_MANIFEST:-/etc/sparkvm/image-manifest.json}"
HARNESS_PROBE_BIN="${HARNESS_PROBE_BIN:-$HERE/harness-auth-probe}"
SWAPD_CA_DIR="${SWAPD_CA_DIR:-/home/swapd/.mitmproxy}"
TENANT_RECORD="${INJECT_TENANT_RECORD:-/etc/sparkvm/tenant.json}"
AGENT_USER="${INJECT_AGENT_USER:-agent}"
AGENT_HOME="${INJECT_AGENT_HOME:-/home/agent}"

if [ ! -x "$STORE_VERIFY_WRITER" ]; then
    echo "inject-provision-state: store verify writer not executable: $STORE_VERIFY_WRITER (CRED_STORE_VERIFY_INFERENCE)" >&2
    exit 2
fi
if [ ! -x "$REGISTRY_WRITER" ]; then
    echo "inject-provision-state: registry writer not executable: $REGISTRY_WRITER (CRED_REGISTRY_SET_INFERENCE)" >&2
    exit 2
fi
if [ ! -x "$MANIFEST_CHECK" ]; then
    echo "inject-provision-state: manifest check not executable: $MANIFEST_CHECK (INJECT_MANIFEST_CHECK)" >&2
    exit 2
fi
if [ ! -x "$HARNESS_PROBE_BIN" ]; then
    echo "inject-provision-state: probe not executable: $HARNESS_PROBE_BIN (HARNESS_PROBE_BIN)" >&2
    exit 2
fi

# shellcheck disable=SC2086  # SUDO_PREFIX is intentionally word-split
run_priv() { $SUDO_PREFIX "$@"; }

# allowlist_readable <file>: fail-closed readability check, same contract
# as harness/install-gate-fixture.sh -- the reads run as the invoking
# user (production sudoers grants only `tee -a` on the allow files), and
# a masked EACCES must never read as "entry absent".
allowlist_readable() {
    python3 - "$1" <<'EOF'
import os, sys
p = sys.argv[1]
try:
    os.stat(p)
except FileNotFoundError:
    sys.exit(0)
except OSError:
    sys.exit(1)
sys.exit(0 if os.access(p, os.R_OK) else 1)
EOF
}

# registry_bound_to_echo: exit 0 iff the inference registry currently
# binds llm-api to the echo host. Reads through the sudoers-allowed cat;
# a missing/unreadable registry means "no binding" (the key assertion in
# step 3 fails closed on that case separately).
registry_bound_to_echo() {
    run_priv cat "$REGISTRY_FILE" 2>/dev/null | KEY_NAME="$KEY_NAME" ECHO_HOST="$ECHO_HOST" python3 -c '
import json, os, sys
try:
    reg = json.load(sys.stdin)
except Exception:
    sys.exit(1)
entry = reg.get(os.environ["KEY_NAME"])
hosts = entry.get("allowed_hosts") if isinstance(entry, dict) else None
sys.exit(0 if isinstance(hosts, list) and os.environ["ECHO_HOST"] in hosts else 1)
'
}

# --- Step 1: manifest preflight -------------------------------------------
echo "inject-provision-state: preflighting image manifest against pinned $IMAGE_VERSION" >&2
if ! "$MANIFEST_CHECK" "$MANIFEST" --expect-version "$IMAGE_VERSION" >&2; then
    echo "inject-provision-state: refusing: manifest preflight failed (image drift -- the box is not the pinned image)" >&2
    exit 1
fi

# --- Step 2: gate-fixture teardown -----------------------------------------
# Remove the llm-api -> echo-host binding through the narrow writer
# (idempotent), then verify the binding is gone AND the echo host is
# absent from both allow files. The injector cannot remove allowlist
# lines through any narrow path (production sudoers is append-only by
# design); a surviving echo entry fails closed here, naming the
# image-build gate -- which runs as root on the build box pre-publish --
# as the teardown owner.
TEARDOWN="absent"
if registry_bound_to_echo; then
    echo "inject-provision-state: unbinding $KEY_NAME from echo host $ECHO_HOST" >&2
    run_priv "$REGISTRY_WRITER" remove-host "$KEY_NAME" "$ECHO_HOST"
    TEARDOWN="removed"
fi
if registry_bound_to_echo; then
    echo "inject-provision-state: refusing: $KEY_NAME is still bound to $ECHO_HOST after remove-host -- the registry writer did not apply the teardown" >&2
    exit 1
fi
for f in "$ALLOW_FILE" "$SSRF_ALLOW_FILE"; do
    if ! allowlist_readable "$f"; then
        echo "inject-provision-state: refusing: cannot read $f as the invoking user -- will not verify the echo-host teardown blindly" >&2
        exit 1
    fi
    # shellcheck disable=SC2086  # ECHO_ALIASES is intentionally word-split
    for alias in $ECHO_ALIASES; do
        if [ -f "$f" ] && grep -qxF "$alias" "$f" 2>/dev/null; then
            echo "inject-provision-state: refusing: echo host '$alias' still present in $f -- the injector has no narrow path to remove allowlist lines (production sudoers is append-only by design); the image-build gate owns allowlist teardown pre-publish -- a box holding a real key must never keep a gate echo exemption" >&2
            exit 1
        fi
    done
done
echo "inject-provision-state: fixture teardown $TEARDOWN (no echo binding, no echo allowlist entries)" >&2

# --- Step 3: real-key assertion --------------------------------------------
# The operator installs the real tenant key through the human-only
# grant-writer path BEFORE this runs. Assert, never handle: the registry
# must bind llm-api (bearer_header) to at least one non-loopback host,
# and the blind compare must prove the stored value is NOT the public
# fixture dummy. The real value is never read.
if ! run_priv cat "$REGISTRY_FILE" 2>/dev/null | KEY_NAME="$KEY_NAME" ECHO_ALIASES="$ECHO_ALIASES" python3 -c '
import json, os, sys
try:
    reg = json.load(sys.stdin)
except Exception:
    print("registry unreadable or invalid JSON", file=sys.stderr)
    sys.exit(1)
entry = reg.get(os.environ["KEY_NAME"])
if not isinstance(entry, dict):
    print("llm-api has no registry entry", file=sys.stderr)
    sys.exit(1)
if entry.get("access_token", {}).get("placement") != "bearer_header":
    print("llm-api placement is not bearer_header", file=sys.stderr)
    sys.exit(1)
hosts = entry.get("allowed_hosts")
if not isinstance(hosts, list) or not hosts:
    print("llm-api is bound to no hosts", file=sys.stderr)
    sys.exit(1)
echo_aliases = set(os.environ["ECHO_ALIASES"].split())
bad = [h for h in hosts if h in echo_aliases]
if bad:
    print("llm-api still bound to echo host(s): %s" % ",".join(bad), file=sys.stderr)
    sys.exit(1)
sys.exit(0)
' >&2; then
    echo "inject-provision-state: refusing: no usable real inference credential in the registry (see above)" >&2
    exit 1
fi
# Blind compare: 0 = still the public dummy, 1 = something else (the
# real key -- never read), 2 = missing. Only the one-bit answer leaves
# the store.
set +e
printf '%s' "$FIXTURE_DUMMY" | run_priv "$STORE_VERIFY_WRITER" >/dev/null 2>&1
verify_rc=$?
set -e
if [ "$verify_rc" -eq 0 ]; then
    echo "inject-provision-state: refusing: the stored $KEY_NAME is still the public fixture dummy -- no real tenant key installed (install it through the grant-writer path, then re-run)" >&2
    exit 1
elif [ "$verify_rc" -eq 2 ]; then
    echo "inject-provision-state: refusing: no $KEY_NAME credential in the store at all" >&2
    exit 1
elif [ "$verify_rc" -ne 1 ]; then
    echo "inject-provision-state: refusing: store verify writer exited $verify_rc (expected 0/1/2)" >&2
    exit 1
fi
echo "inject-provision-state: real inference credential asserted (registry binding + blind not-dummy compare; value never read)" >&2

# --- Step 4: swapd CA presence ---------------------------------------------
# The first-boot unit generates the fresh per-tenant CA; the injector
# gates on presence. The key material is never read.
if [ ! -s "$SWAPD_CA_DIR/mitmproxy-ca.pem" ]; then
    echo "inject-provision-state: refusing: fresh swapd CA absent at $SWAPD_CA_DIR/mitmproxy-ca.pem -- the first-boot unit must generate the per-tenant CA (never baked into the image) before the injector runs" >&2
    exit 1
fi
echo "inject-provision-state: swapd CA present" >&2

# --- Step 5: tenant identity (H9 interface) ----------------------------------
IDENTITY="deferred (H9)"
IDENTITY_SRC="${INJECT_IDENTITY_DIR:-}/authorized_keys"
if [ -n "${INJECT_IDENTITY_DIR:-}" ] && [ -f "$IDENTITY_SRC" ]; then
    # Validate: public-key shapes only. Any private-key line refuses,
    # fail-closed -- installing private material as authorized_keys
    # would be a credential mishandling, not just a no-op.
    if ! IDENTITY_SRC="$IDENTITY_SRC" python3 -c '
import os, re, sys
pub = re.compile(r"^(ssh-rsa|ssh-dss|ssh-ed25519|ecdsa-sha2-[a-z0-9-]+|sk-ssh-ed25519@openssh\.com|sk-ecdsa-sha2-nistp256@openssh\.com|cert-authority)( |$)")
with open(os.environ["IDENTITY_SRC"], encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "PRIVATE KEY" in line:
            print("line %d looks like private-key material" % i, file=sys.stderr)
            sys.exit(1)
        if not pub.match(line):
            print("line %d is not a recognized public-key shape" % i, file=sys.stderr)
            sys.exit(1)
' >&2; then
        echo "inject-provision-state: refusing: tenant identity material failed validation (see above)" >&2
        exit 2
    fi
    if ! id -u "$AGENT_USER" >/dev/null 2>&1; then
        echo "inject-provision-state: refusing: agent user $AGENT_USER does not exist (the image bakes this user; its absence is image drift)" >&2
        exit 1
    fi
    ssh_dir="$AGENT_HOME/.ssh"
    mkdir -p "$ssh_dir"
    chmod 0700 "$ssh_dir"
    cp "$IDENTITY_SRC" "$ssh_dir/authorized_keys"
    chmod 0600 "$ssh_dir/authorized_keys"
    # chown only when crossing users: as root in production the agent
    # user differs; in tests the invoker IS the agent user and a chown
    # would need privilege for no reason.
    if [ "$(id -u)" != "$(id -u "$AGENT_USER")" ]; then
        chown -R "$AGENT_USER" "$ssh_dir"
    fi
    if ! cmp -s "$IDENTITY_SRC" "$ssh_dir/authorized_keys"; then
        echo "inject-provision-state: refusing: installed authorized_keys is not byte-identical to the tenant material" >&2
        exit 1
    fi
    IDENTITY="ok"
    echo "inject-provision-state: tenant identity installed for $AGENT_USER" >&2
else
    if [ -n "${INJECT_IDENTITY_DIR:-}" ]; then
        echo "inject-provision-state: tenant identity deferred (H9 -- INJECT_IDENTITY_DIR is set but $IDENTITY_SRC is not a file)" >&2
    else
        echo "inject-provision-state: tenant identity deferred (H9 -- no INJECT_IDENTITY_DIR provided)" >&2
    fi
fi

# --- Step 6: confirmd tenant attribution (H10 interface) ----------------------
ATTRIBUTION="deferred (H10)"
if [ -n "${INJECT_TENANT_ID:-}" ]; then
    if ! printf '%s' "$INJECT_TENANT_ID" | grep -qE '^[A-Za-z0-9_-]{1,64}$'; then
        echo "inject-provision-state: refusing: INJECT_TENANT_ID must match ^[A-Za-z0-9_-]{1,64}\$" >&2
        exit 2
    fi
    mkdir -p "$(dirname "$TENANT_RECORD")"
    INJECT_TENANT_ID="$INJECT_TENANT_ID" IMAGE_VERSION="$IMAGE_VERSION" TENANT_RECORD="$TENANT_RECORD" python3 -c '
import json, os, time
record = {
    "tenant_id": os.environ["INJECT_TENANT_ID"],
    "image_version": os.environ["IMAGE_VERSION"],
    "injected_at": int(time.time()),
    "injector": "harness/inject-provision-state.sh",
    "confirmd_attribution": "pending (H10: per-tenant approvals URL wiring consumes this record)",
}
with open(os.environ["TENANT_RECORD"], "w", encoding="utf-8") as f:
    json.dump(record, f, indent=2, sort_keys=True)
    f.write("\n")
'
    if ! INJECT_TENANT_ID="$INJECT_TENANT_ID" TENANT_RECORD="$TENANT_RECORD" python3 -c '
import json, os, sys
with open(os.environ["TENANT_RECORD"], encoding="utf-8") as f:
    record = json.load(f)
sys.exit(0 if record.get("tenant_id") == os.environ["INJECT_TENANT_ID"] else 1)
'; then
        echo "inject-provision-state: refusing: tenant record did not verify" >&2
        exit 1
    fi
    ATTRIBUTION="ok"
    echo "inject-provision-state: tenant attribution recorded for $INJECT_TENANT_ID" >&2
else
    echo "inject-provision-state: confirmd tenant attribution deferred (H10 -- no INJECT_TENANT_ID provided)" >&2
fi

# --- Step 7: provision-mode probe --------------------------------------------
echo "inject-provision-state: proving the injected key with the probe (provision mode)" >&2
# External cap is 15s -- deliberately looser than the probe docstring's
# 10s contract line: headroom for slow boxes (same rationale as
# install-gate-fixture.sh).
if ! PROBE_MODE=provision timeout 15 "$HARNESS_PROBE_BIN" </dev/null >&2; then
    echo "inject-provision-state: provisioning-failed: the provision-mode probe did not pass (the injected credential was not accepted, or confirmd is down) -- box-live must not flip" >&2
    exit 1
fi

# --- Report --------------------------------------------------------------------
# One JSON document on stdout, like the probe's contract. The
# fixture_teardown step reads "ok" with the absent/removed detail in
# fixture_teardown_detail, so the documented box-live gating rule (every
# gated step reads "ok") holds for the machine consumer; the `deferred`
# list names the interface points still owned by unlanded mechanics.
TEARDOWN="$TEARDOWN" IDENTITY="$IDENTITY" ATTRIBUTION="$ATTRIBUTION" \
IMAGE_VERSION="$IMAGE_VERSION" python3 -c '
import json, os
deferred = []
steps = {
    "manifest": "ok",
    "fixture_teardown": "ok",
    "inference_key": "ok",
    "swapd_ca": "ok",
    "identity": os.environ["IDENTITY"],
    "confirmd_attribution": os.environ["ATTRIBUTION"],
    "probe": "ok",
}
for step, owner in (("identity", "H9: tenant identity mechanics"),
                    ("confirmd_attribution", "H10: per-tenant approvals URL wiring")):
    if steps[step].startswith("deferred"):
        deferred.append("%s (%s)" % (step, owner))
print(json.dumps({
    "injector": "harness/inject-provision-state.sh",
    "image_version": os.environ["IMAGE_VERSION"],
    "steps": steps,
    "fixture_teardown_detail": os.environ["TEARDOWN"],
    "deferred": deferred,
}, indent=2, sort_keys=True))
'
