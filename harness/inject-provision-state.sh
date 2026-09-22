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
#   2. Gate-fixture teardown: unbinds every llm-api -> echo-host registry
#      binding through the narrow registry writer (idempotent per entry),
#      then VERIFIES no effective echo binding remains AND that no echo
#      exemption survives in inference-hosts.allow or the inference
#      proxy's own inference-ssrf.allow. "Effective" uses the inference
#      proxy's own matching semantics via harness/proxy_match.py -- the
#      single shared mirror of proxy/swap_addon.py::_host_in_list and
#      _parse_ssrf_allow, pinned against the real functions by
#      harness/test_proxy_match.py's drift tripwire (case-insensitive,
#      whitespace-stripped, trailing dots stripped, CIDR-aware) -- a
#      check narrower than the enforcement point would let a real key
#      coexist with a live exemption. Fail-closed: the injector has no
#      narrow path to remove allowlist lines (production sudoers is
#      append-only by design), so a surviving echo entry is REFUSED --
#      loudly, naming the image-build gate (which runs as root on the
#      build box, pre-publish) as the owner of allowlist teardown. The
#      binding removal alone is what stops a swap toward the echo host; the refusal is what keeps a
#      half-torn-down fixture from ever coexisting with a real key.
#   3. Real-key assertion: the tenant's inference credential is installed
#      by the OPERATOR through the existing human-only grant-writer path
#      (SETUP.md "Inference-model recipe") BEFORE this runs. The injector
#      asserts, never handles: the registry must bind llm-api (with
#      bearer_header placement) to at least one host that is not one of
#      the fixture echo aliases (127.0.0.1, ::1, localhost -- the provision
#      probe backstops this: a wrong-host binding means no swap match for
#      the real provider host, so the probe fails closed), and a
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
# (then named in deferred[]). Note: a narrow writer crashing under
# `set -e` exits with the writer's code rather than 1/2 -- still
# fail-closed, but the H4 driver must treat ANY non-zero exit as
# provisioning-failed, not just 1.
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
#                          the image by the image-build gate; until that
#                          slice lands the H4 driver must pass
#                          INJECT_MANIFEST explicitly)
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
# Loopback aliases the teardown treats as the echo host. The fixture only
# ever used 127.0.0.1; the aliases close the obvious bypass where a later
# fixture variant binds `localhost` instead. Matching is done with the
# proxy's own semantics (see echo_bound_hosts / allowlist_echo_entries),
# not exact string comparison.
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
HERE="$(cd "$(dirname "$0")" && pwd)"  # canonical: a bare-PATH invocation must still find proxy_match.py
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

# require_proxy_match: the three matcher call sites depend on
# harness/proxy_match.py; a missing helper must refuse with a named error,
# not a misleading "cannot read the registry" diagnostic.
require_proxy_match() {
    if [ ! -f "$HERE/proxy_match.py" ]; then
        echo "inject-provision-state: refusing: $HERE/proxy_match.py is missing -- the shared proxy-match mirror must ship next to this script" >&2
        exit 1
    fi
}

# echo_bound_hosts: print the llm-api allowed_hosts entries that are
# effective echo exemptions, one per line, under the inference proxy's
# own matching semantics. Implemented in harness/proxy_match.py -- the
# single shared mirror of proxy/swap_addon.py::_host_in_list (pinned by
# harness/test_proxy_match.py's drift tripwire). Exits 2 when the
# registry cannot be read -- an unverifiable teardown is not a clean
# teardown (fail-closed).
echo_bound_hosts() {
    require_proxy_match
    run_priv cat "$REGISTRY_FILE" 2>/dev/null \
        | KEY_NAME="$KEY_NAME" ECHO_ALIASES="$ECHO_ALIASES" \
            python3 "$HERE/proxy_match.py" echo-bound-hosts
}

# allowlist_echo_entries <kind> <file>: print the file's effective echo
# exemptions, one per line. Implemented in harness/proxy_match.py (mirror
# of _host_in_list for "hosts", of _parse_ssrf_allow for "ssrf" -- the
# ssrf file additionally honors CIDR literals and promotes bare IPs to
# /32 or /128 nets, which are exemptions when they cover 127.0.0.0/8 or
# ::1/128). The proxy_match module is the single mirror; the tripwire
# test pins it against the real proxy functions.
allowlist_echo_entries() {
    require_proxy_match
    python3 "$HERE/proxy_match.py" allowlist-echo-entries "$1" "$2"
}

# --- Step 1: manifest preflight -------------------------------------------
echo "inject-provision-state: preflighting image manifest against pinned $IMAGE_VERSION" >&2
if ! "$MANIFEST_CHECK" "$MANIFEST" --expect-version "$IMAGE_VERSION" >&2; then
    echo "inject-provision-state: refusing: manifest preflight failed (image drift -- the box is not the pinned image)" >&2
    exit 1
fi

# --- Step 2: gate-fixture teardown -----------------------------------------
# Remove every llm-api echo-host binding through the narrow writer
# (idempotent per entry), then verify no effective echo binding remains
# AND no echo exemption survives in either allow file. The injector
# cannot remove allowlist lines through any narrow path (production
# sudoers is append-only by design); a surviving echo entry fails closed
# here, naming the image-build gate -- which runs as root on the build
# box pre-publish -- as the teardown owner. Every match below uses the
# inference proxy's own semantics via harness/proxy_match.py (the single
# shared mirror, pinned by the drift tripwire): a check narrower than
# the enforcement point would let a real key coexist with a live
# exemption.
TEARDOWN="absent"
if ! bound="$(echo_bound_hosts)"; then
    echo "inject-provision-state: refusing: cannot read the inference registry -- will not verify the echo-host teardown blindly" >&2
    exit 1
fi
if [ -n "$bound" ]; then
    echo "inject-provision-state: unbinding $KEY_NAME from echo host(s): $(printf '%s' "$bound" | tr '\n' ' ')" >&2
    while IFS= read -r h; do
        [ -n "$h" ] || continue
        # The real writer prints "unbound ..." to stdout on success;
        # keep it on the log stream so stdout carries exactly the JSON
        # report. Note the writer lowercases its host argument and only
        # removes exact (lowercased) matches: a variant it cannot remove
        # is caught by the re-verification below, fail-closed.
        run_priv "$REGISTRY_WRITER" remove-host "$KEY_NAME" "$h" >&2
    done <<< "$bound"
    TEARDOWN="removed"
fi
if ! bound="$(echo_bound_hosts)"; then
    echo "inject-provision-state: refusing: cannot re-read the inference registry after teardown" >&2
    exit 1
fi
if [ -n "$bound" ]; then
    echo "inject-provision-state: refusing: $KEY_NAME is still bound to echo host(s) after remove-host: $(printf '%s' "$bound" | tr '\n' ' ') -- the narrow registry writer cannot remove this variant (exact lowercase matches only); the image is pathological, rebuild it" >&2
    exit 1
fi
for spec in "hosts:$ALLOW_FILE" "ssrf:$SSRF_ALLOW_FILE"; do
    kind="${spec%%:*}"; f="${spec#*:}"
    if ! allowlist_readable "$f"; then
        echo "inject-provision-state: refusing: cannot read $f as the invoking user -- will not verify the echo-host teardown blindly" >&2
        exit 1
    fi
    if [ -f "$f" ]; then
        if ! bad="$(allowlist_echo_entries "$kind" "$f")"; then
            echo "inject-provision-state: refusing: cannot parse $f -- will not verify the echo-host teardown blindly" >&2
            exit 1
        fi
        if [ -n "$bad" ]; then
            echo "inject-provision-state: refusing: echo exemption(s) still present in $f: $(printf '%s' "$bad" | tr '\n' ' ') -- the injector has no narrow path to remove allowlist lines (production sudoers is append-only by design); the image-build gate owns allowlist teardown pre-publish -- a box holding a real key must never keep a gate echo exemption" >&2
            exit 1
        fi
    fi
done
echo "inject-provision-state: fixture teardown $TEARDOWN (no echo binding, no echo allowlist entries)" >&2

# --- Step 3: real-key assertion --------------------------------------------
# The operator installs the real tenant key through the human-only
# grant-writer path BEFORE this runs. Assert, never handle: the registry
# must bind llm-api (bearer_header) to at least one host outside the
# fixture echo aliases (127.0.0.1, ::1, localhost),
# and the blind compare must prove the stored value is NOT the public
# fixture dummy. The real value is never read. The assertion lives in
# harness/proxy_match.py (assert-key-binding) -- the same shared mirror
# as the teardown checks, pinned by the drift tripwire.
if ! run_priv cat "$REGISTRY_FILE" 2>/dev/null \
    | { require_proxy_match; KEY_NAME="$KEY_NAME" ECHO_ALIASES="$ECHO_ALIASES" \
        python3 "$HERE/proxy_match.py" assert-key-binding; } >&2; then
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
    # Symlink guard: cp/chmod follow links, so a planted $ssh_dir (or
    # authorized_keys) symlink would redirect validated tenant keys
    # into an attacker-chosen directory (e.g. /root/.ssh). A symlinked
    # .ssh in a fresh agent home is a box-integrity failure: refuse,
    # fail-closed, never install through it.
    if [ -L "$ssh_dir" ] || [ -L "$ssh_dir/authorized_keys" ]; then
        echo "inject-provision-state: refusing: $ssh_dir or $ssh_dir/authorized_keys is a symlink -- refusing to install tenant identity through a link" >&2
        exit 1
    fi
    mkdir -p "$ssh_dir"
    chmod 0700 "$ssh_dir"
    # Issue #258 (TOCTOU): the [ -L ] guard above and this install are
    # separated by mkdir/chmod, so a concurrent privileged process could
    # still swap $ssh_dir/authorized_keys for a symlink (or FIFO) between
    # the check and the use -- install(1)/cp/chmod all resolve by path.
    # This block pins both ends by file descriptor instead: the source is
    # opened O_NOFOLLOW and re-validated (same shape regex as the
    # pre-check above -- the validated bytes are exactly the installed
    # bytes), the destination directory is opened O_DIRECTORY|O_NOFOLLOW
    # and the target is created through it with O_NOFOLLOW|O_CREAT|O_TRUNC
    # plus an S_ISREG re-check (a planted FIFO would otherwise hang the
    # open). Modes are set by fchmod/fchown on the open fds, and the
    # byte-identity check reads back through the same fd -- no path is
    # resolved twice, so there is no check/use window left.
    if ! SSH_DIR="$ssh_dir" IDENTITY_SRC="$IDENTITY_SRC" \
         AGENT_USER="$AGENT_USER" python3 -c '
import fcntl, os, pwd, re, stat, sys

def refuse(msg, code=1):
    print("inject-provision-state: refusing: %s" % msg, file=sys.stderr)
    sys.exit(code)

def read_all(fd):
    chunks = []
    while True:
        b = os.read(fd, 65536)
        if not b:
            break
        chunks.append(b)
    return b"".join(chunks)

def unblock(fd):
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)

agent_uid = pwd.getpwnam(os.environ["AGENT_USER"]).pw_uid

# Pin the tenant material: no-follow, must be a regular file (a FIFO
# swapped in here would hang a plain open, hence O_NONBLOCK + re-check).
try:
    src_fd = os.open(os.environ["IDENTITY_SRC"],
                     os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
except OSError:
    refuse("tenant identity material cannot be opened without following links")
try:
    if not stat.S_ISREG(os.fstat(src_fd).st_mode):
        refuse("tenant identity material is not a regular file")
    unblock(src_fd)
    data = read_all(src_fd)
finally:
    os.close(src_fd)
try:
    text = data.decode("utf-8")
except UnicodeDecodeError:
    refuse("tenant identity material is not valid UTF-8", 2)
# Same shape rules as the pre-check above, applied to the exact bytes
# being installed (keep the two regexes in sync).
pub = re.compile(r"^(ssh-rsa|ssh-dss|ssh-ed25519|ecdsa-sha2-[a-z0-9-]+|sk-ssh-ed25519@openssh\.com|sk-ecdsa-sha2-nistp256@openssh\.com|cert-authority)( |$)")
for i, line in enumerate(text.splitlines(), 1):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    if "PRIVATE KEY" in line:
        refuse("line %d looks like private-key material" % i, 2)
    if not pub.match(line):
        refuse("line %d is not a recognized public-key shape" % i, 2)

# Pin the destination directory: no-follow, must be a directory owned
# by root or the agent user (a foreign-owned .ssh in a fresh agent
# home is the same box-integrity failure the symlink guard refuses).
try:
    ssh_fd = os.open(os.environ["SSH_DIR"],
                     os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
except OSError:
    refuse("ssh dir cannot be opened without following links")
try:
    st = os.fstat(ssh_fd)
    if not stat.S_ISDIR(st.st_mode):
        refuse("ssh dir is not a directory")
    if st.st_uid not in (0, agent_uid):
        refuse("ssh dir owned by uid %d, expected root or %s"
               % (st.st_uid, os.environ["AGENT_USER"]))
    try:
        dst_fd = os.open("authorized_keys",
                         os.O_RDWR | os.O_CREAT | os.O_TRUNC
                         | os.O_NOFOLLOW | os.O_NONBLOCK,
                         0o600, dir_fd=ssh_fd)
    except OSError:
        refuse("authorized_keys cannot be created without following links")
    try:
        if not stat.S_ISREG(os.fstat(dst_fd).st_mode):
            refuse("authorized_keys exists and is not a regular file")
        unblock(dst_fd)
        os.fchmod(dst_fd, 0o600)  # explicit: not masked by umask, no
        # transient world-readable window (the old install -m 0600 rule)
        if os.geteuid() != agent_uid:
            # chown only when crossing users (same rule as before)
            os.fchown(dst_fd, agent_uid, -1)
        n = 0
        while n < len(data):
            n += os.write(dst_fd, data[n:])
        os.fsync(dst_fd)
        os.lseek(dst_fd, 0, os.SEEK_SET)
        if read_all(dst_fd) != data:
            refuse("installed authorized_keys is not byte-identical "
                   "to the tenant material")
    finally:
        os.close(dst_fd)
    if os.geteuid() != agent_uid:
        os.fchown(ssh_fd, agent_uid, -1)
finally:
    os.close(ssh_fd)
' >&2; then
        echo "inject-provision-state: refusing: tenant identity install failed (see above)" >&2
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
    # grep is line-oriented: an embedded newline would let a second line
    # slip past -x, so reject newlines explicitly before matching.
    if [[ "$INJECT_TENANT_ID" == *$'\n'* ]] \
        || ! printf '%s' "$INJECT_TENANT_ID" | grep -qxE '^[A-Za-z0-9_-]{1,64}$'; then
        echo "inject-provision-state: refusing: INJECT_TENANT_ID must match ^[A-Za-z0-9_-]{1,64}\$ (single line)" >&2
        exit 2
    fi
    if [ -L "$TENANT_RECORD" ]; then
        echo "inject-provision-state: refusing: $TENANT_RECORD is a symlink -- refusing to write the tenant record through a link" >&2
        exit 1
    fi
    mkdir -p "$(dirname "$TENANT_RECORD")"
    # Issue #258 (TOCTOU): the [ -L ] guard above and the write below are
    # separated by arbitrary shell, so a concurrent privileged process
    # could swap the tenant record for a symlink (or another non-regular
    # file) between the check and the use. This block pins the parent
    # directory with O_DIRECTORY|O_NOFOLLOW and does everything through
    # that fd: the existing record is re-checked by lstat (symlink and
    # non-regular files refuse, fail-closed), the temp file is created
    # O_EXCL|O_NOFOLLOW inside the pinned dir, and the atomic rename is
    # renameat2-style via src/dst dirfds -- even a symlink swapped in
    # between the lstat and the rename would be *replaced*, never
    # followed, so the worst case is the attacker's link being unlinked.
    # The verify read-back also goes through the pinned dir.
    if ! INJECT_TENANT_ID="$INJECT_TENANT_ID" IMAGE_VERSION="$IMAGE_VERSION" \
         TENANT_RECORD="$TENANT_RECORD" python3 -c '
import fcntl, hashlib, json, os, stat, sys, time

def refuse(msg):
    print("inject-provision-state: refusing: %s" % msg, file=sys.stderr)
    sys.exit(1)

def read_all(fd):
    chunks = []
    while True:
        b = os.read(fd, 65536)
        if not b:
            break
        chunks.append(b)
    return b"".join(chunks)

path = os.environ["TENANT_RECORD"]
parent = os.path.dirname(path) or "."
name = os.path.basename(path)

# open(path, "w") mode semantics, preserved: a CREATED file gets 0666
# masked by the process umask (022 at first boot -> 0644, as before);
# truncating an EXISTING file leaves its mode untouched. The atomic
# rename always lands a fresh inode, so replicate both branches
# explicitly -- hardcoding 0644 would silently widen a pre-hardened
# (e.g. 0600) tenant record.
_umask = os.umask(0)
os.umask(_umask)

try:
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
except OSError:
    refuse("tenant record parent cannot be opened without following links")
try:
    if not stat.S_ISDIR(os.fstat(parent_fd).st_mode):
        refuse("tenant record parent is not a directory")
    try:
        st = os.lstat(name, dir_fd=parent_fd)
    except FileNotFoundError:
        st = None
    if st is not None:
        if stat.S_ISLNK(st.st_mode):
            refuse("tenant record is a symlink -- refusing to write the "
                   "tenant record through a link")
        if not stat.S_ISREG(st.st_mode):
            refuse("tenant record exists and is not a regular file")
        _mode = stat.S_IMODE(st.st_mode)  # existing file: keep mode
        old_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=parent_fd)
        try:
            if not stat.S_ISREG(os.fstat(old_fd).st_mode):
                refuse("tenant record changed under us -- not a regular file")
            flags = fcntl.fcntl(old_fd, fcntl.F_GETFL)
            fcntl.fcntl(old_fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
            old_digest = hashlib.sha256(read_all(old_fd)).hexdigest()
        finally:
            os.close(old_fd)
    else:
        _mode = 0o666 & ~_umask           # new file: 0666 & ~umask
        old_digest = None
    record = {
        "tenant_id": os.environ["INJECT_TENANT_ID"],
        "image_version": os.environ["IMAGE_VERSION"],
        "injected_at": int(time.time()),
        "injector": "harness/inject-provision-state.sh",
        "confirmd_attribution": "pending (H10: per-tenant approvals URL wiring consumes this record)",
    }
    payload = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")
    # Atomic write: a direct open("w") truncates in place, so a
    # concurrent reader (the future H10 confirmd wiring reads this
    # record) could see a torn file. Write to a temp file in the pinned
    # directory, fsync, and rename over via dirfds.
    tmp_name = ".tenant.json.%d.%d" % (os.getpid(), time.time_ns())
    try:
        tmp_fd = os.open(tmp_name,
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=parent_fd)
    except OSError:
        refuse("tenant record temp file cannot be created without following links")
    try:
        os.fchmod(tmp_fd, _mode)  # same effective mode as open("w")
        n = 0
        while n < len(payload):
            n += os.write(tmp_fd, payload[n:])
        os.fsync(tmp_fd)
    except BaseException:
        try:
            os.unlink(tmp_name, dir_fd=parent_fd)
        except OSError:
            pass
        raise
    else:
        os.close(tmp_fd)
    os.rename(tmp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
    # Verify: read the record back through the pinned dir and confirm
    # the tenant id survived the round trip.
    vfd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                  dir_fd=parent_fd)
    try:
        if not stat.S_ISREG(os.fstat(vfd).st_mode):
            refuse("tenant record did not verify (not a regular file)")
        flags = fcntl.fcntl(vfd, fcntl.F_GETFL)
        fcntl.fcntl(vfd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)
        back = read_all(vfd)
    finally:
        os.close(vfd)
    try:
        seen = json.loads(back.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        refuse("tenant record did not verify (unreadable)")
    if seen.get("tenant_id") != os.environ["INJECT_TENANT_ID"]:
        refuse("tenant record did not verify")
    new_digest = hashlib.sha256(back).hexdigest()
    if old_digest is None:
        print("inject-provision-state: tenant record initialized "
              "(sha256 %s)" % new_digest, file=sys.stderr)
    elif old_digest == new_digest:
        print("inject-provision-state: tenant record unchanged "
              "(sha256 %s)" % new_digest, file=sys.stderr)
    else:
        print("inject-provision-state: tenant record updated "
              "(sha256 %s -> %s)" % (old_digest, new_digest), file=sys.stderr)
finally:
    os.close(parent_fd)
' >&2; then
        echo "inject-provision-state: refusing: tenant record write failed (see above)" >&2
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
