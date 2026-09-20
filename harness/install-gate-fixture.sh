#!/bin/bash
# install-gate-fixture.sh -- install the PUBLIC gate fixture for
# harness/harness-auth-probe (R2 section 5.4, "gate mode"; the probe
# contract is docs/PRE_SEEDED_HARNESS_RESEARCH.md section 5).
#
# Installs, through the existing narrow writers only:
#   1. the public dummy inference credential under the inference
#      proxy's single fixed credential name `llm-api` (NOT a secret --
#      the value is baked into this repo on purpose; it proves the swap
#      path end to end without ever touching a real credential). The
#      name is fixed because the inference store writer
#      (proxy/cred-store-set-inference) hardcodes it -- the inference
#      proxy holds exactly one credential (finding 31) -- so the
#      fixture MUST use `llm-api`; any other name resolves to
#      unknown-credential at swap time and the gate can never pass.
#   2. its `bearer_header` placement in the inference registry,
#   3. the loopback echo host in inference-hosts.allow (swap scope),
#   4. the loopback echo host in the inference proxy's OWN ssrf.allow
#      (/home/swapd/inference-ssrf.allow). The inference proxy's
#      finding-29 egress guard refuses loopback by default, and the
#      gate must prove the swap through the REAL proxy -- so the gate
#      needs the exemption. It lives in the inference instance's own
#      file, never the main proxy's shared one, so the main proxy's
#      egress guard is untouched.
# then starts the loopback echo fixture (harness/echo-fixture.py) and
# runs the probe in gate mode to prove the fixture works.
#
# Idempotent: safe to re-run. The inference proxy hot-reloads the
# registry, hosts, and ssrf files per request, so no restart is needed.
#
# Fail-closed: if the inference secrets dir already holds `llm-api` and
# the registry does NOT show this fixture's signature (`llm-api` bound
# to the loopback echo host), the installer refuses to run -- that is a
# real tenant credential, and overwriting it would destroy the box's
# only inference key. A previous fixture run (dummy + fixture binding)
# is detected and safely reinstalled, keeping the idempotency promise.
#
# NEVER install a real credential with this script. The fixture dummy is
# public by design; a real key here would be baked into image layers and
# echo-server logs. Real tenant credentials travel the human-only
# grant-writer path (SETUP.md "Inference-model recipe"), never this one.
#
# FIXTURE LIFECYCLE (read before building on this): the fixture binds
# `llm-api` to the echo host, allowlists that host for swapping, and
# exempts it from the inference proxy's SSRF guard. That binding must
# NEVER coexist with a real credential -- after the gate passes, the echo
# host MUST be removed from inference-hosts.allow AND from
# inference-ssrf.allow, and the llm-api->echo-host binding MUST be
# unbound -- by the image-build gate before the image is published, or by
# the provision-time injector BEFORE it installs the real tenant key.
# Otherwise any request to the echo host carrying the placeholder would
# swap in the REAL tenant key and ship it to the echo server. The gate is
# only safe because the fixture is public; the teardown is what keeps it
# safe once a real key exists. See harness/README.md "Fixture lifecycle".
#
# Env overrides (tests / nonstandard layouts):
#   CRED_STORE_SET_INFERENCE inference secret writer (default
#                            /usr/local/bin/cred-store-set-inference)
#   CRED_REGISTRY_SET_INFERENCE
#                            inference registry writer (default
#                            /usr/local/bin/cred-registry-set-inference)
#   INFERENCE_HOSTS_ALLOW    hosts.allow path (default
#                            /home/swapd/inference-hosts.allow)
#   INFERENCE_SSRF_ALLOW     inference ssrf.allow path (default
#                            /home/swapd/inference-ssrf.allow)
#   INFERENCE_SECRETS_DIR    inference secrets dir (default
#                            /home/swapd/inference-secrets); the
#                            fail-closed guard lists llm-api here
#   INFERENCE_REGISTRY_FILE  inference registry path (default
#                            /home/swapd/inference-registry.json); the
#                            guard reads it via the sudoers-allowed cat
#   SUDO_PREFIX              privilege prefix, e.g. "sudo -u swapd"
#                            (default "sudo -u swapd"; empty runs directly)
#   ECHO_FIXTURE             echo-fixture.py path (default alongside this script)
#   HARNESS_PROBE_BIN        probe path (default alongside this script)
#   HARNESS_GATE_ECHO_LOG    echo log path (default /tmp/harness-gate-echo.log)
#   HARNESS_GATE_ECHO_PORT   echo fixture port (default 0 = ephemeral)
# The probe reads its own env (PROBE_PROXY, PROBE_MUSE_BIN,
# PROBE_CONFIRMD_URL) directly; export those around this script to
# override them.
set -euo pipefail

# Public, non-secret, on purpose. Keep it obviously-not-a-key.
# The public dummy credential installed by the gate fixture. Public by
# design -- keep in sync with INSTALLER_DUMMY in
# harness/test_install_gate_fixture.py (same value, documented there).
FIXTURE_DUMMY="GATE-FIXTURE-DUMMY-NOT-A-SECRET"
# The inference proxy holds exactly one credential and the store writer
# hardcodes its filename (proxy/cred-store-set-inference: "The name is
# fixed ... (finding 31)"), so the fixture MUST live under this name.
# Keep in sync with KEY_NAME in harness/test_install_gate_fixture.py.
KEY_NAME="llm-api"
ECHO_HOST="127.0.0.1"

STORE_WRITER="${CRED_STORE_SET_INFERENCE:-/usr/local/bin/cred-store-set-inference}"
REGISTRY_WRITER="${CRED_REGISTRY_SET_INFERENCE:-/usr/local/bin/cred-registry-set-inference}"
ALLOW_FILE="${INFERENCE_HOSTS_ALLOW:-/home/swapd/inference-hosts.allow}"
SSRF_ALLOW_FILE="${INFERENCE_SSRF_ALLOW:-/home/swapd/inference-ssrf.allow}"
SECRETS_DIR="${INFERENCE_SECRETS_DIR:-/home/swapd/inference-secrets}"
REGISTRY_FILE="${INFERENCE_REGISTRY_FILE:-/home/swapd/inference-registry.json}"
# A bare `-` (not `:-`) preserves an explicitly empty SUDO_PREFIX --
# the test seam; unset keeps the production default.
SUDO_PREFIX="${SUDO_PREFIX-sudo -u swapd}"
HERE="$(dirname "$0")"
ECHO_FIXTURE="${ECHO_FIXTURE:-$HERE/echo-fixture.py}"
HARNESS_PROBE_BIN="${HARNESS_PROBE_BIN:-$HERE/harness-auth-probe}"
ECHO_LOG="${HARNESS_GATE_ECHO_LOG:-/tmp/harness-gate-echo.log}"
ECHO_PORT="${HARNESS_GATE_ECHO_PORT:-0}"

if [ ! -x "$STORE_WRITER" ]; then
    echo "install-gate-fixture: store writer not executable: $STORE_WRITER (CRED_STORE_SET_INFERENCE)" >&2
    exit 2
fi
if [ ! -x "$REGISTRY_WRITER" ]; then
    echo "install-gate-fixture: registry writer not executable: $REGISTRY_WRITER (CRED_REGISTRY_SET_INFERENCE)" >&2
    exit 2
fi
if [ ! -x "$ECHO_FIXTURE" ]; then
    echo "install-gate-fixture: echo fixture not executable: $ECHO_FIXTURE (ECHO_FIXTURE)" >&2
    exit 2
fi
if [ ! -x "$HARNESS_PROBE_BIN" ]; then
    echo "install-gate-fixture: probe not executable: $HARNESS_PROBE_BIN (HARNESS_PROBE_BIN)" >&2
    exit 2
fi

# shellcheck disable=SC2086  # SUDO_PREFIX is intentionally word-split
run_priv() { $SUDO_PREFIX "$@"; }

# Fail-closed guard: never overwrite a real inference credential. The
# existence check uses the sudoers-allowed `ls` on the secrets dir (the
# secret VALUE is never read -- the agent must never see real secrets).
# If llm-api is already stored, proceed only when the registry shows
# this fixture's own signature (llm-api bound to the loopback echo
# host) -- i.e. a previous gate run's dummy, safe to reinstall.
# Anything else is a real tenant key: refuse.
if run_priv ls "$SECRETS_DIR" 2>/dev/null | grep -qx "$KEY_NAME"; then
    if ! run_priv cat "$REGISTRY_FILE" 2>/dev/null | KEY_NAME="$KEY_NAME" ECHO_HOST="$ECHO_HOST" python3 -c '
import json, os, sys
try:
    reg = json.load(sys.stdin)
except Exception:
    sys.exit(1)
entry = reg.get(os.environ["KEY_NAME"])
hosts = entry.get("allowed_hosts") if isinstance(entry, dict) else None
sys.exit(0 if isinstance(hosts, list) and os.environ["ECHO_HOST"] in hosts else 1)
'; then
        echo "install-gate-fixture: refusing: $SECRETS_DIR/$KEY_NAME already holds a credential that is not this fixture ($KEY_NAME is not bound to the gate echo host) -- the gate fixture must never overwrite a real inference credential" >&2
        exit 2
    fi
    echo "install-gate-fixture: previous fixture run detected ($KEY_NAME bound to $ECHO_HOST); reinstalling the public dummy"
fi

# allowlist_add <file> <entry>: idempotent append. If a pre-existing
# file lacks its trailing newline, a bare append would merge lines --
# terminate it first. (The single backslash in '\n' is intentional:
# printf interprets it as a newline; '\\n' would append a literal
# backslash-n. Verified with od -c; do not "fix".)
allowlist_add() {
    local file="$1" entry="$2"
    if run_priv grep -qxF "$entry" "$file" 2>/dev/null; then
        echo "install-gate-fixture: $entry already in $(basename "$file")"
    else
        echo "install-gate-fixture: adding $entry to $(basename "$file")"
        if run_priv test -s "$file" && [ -n "$(run_priv tail -c 1 "$file")" ]; then
            printf '\n' | run_priv tee -a "$file" >/dev/null
        fi
        printf '%s\n' "$entry" | run_priv tee -a "$file" >/dev/null
    fi
}

echo "install-gate-fixture: installing public dummy credential '$KEY_NAME'"
printf '%s' "$FIXTURE_DUMMY" | run_priv "$STORE_WRITER"

echo "install-gate-fixture: registering bearer_header placement"
run_priv "$REGISTRY_WRITER" set "$KEY_NAME" access_token '"bearer_header"'

echo "install-gate-fixture: binding $KEY_NAME to echo host $ECHO_HOST"
run_priv "$REGISTRY_WRITER" add-host "$KEY_NAME" "$ECHO_HOST"

echo "install-gate-fixture: allowlisting $ECHO_HOST for swapping"
allowlist_add "$ALLOW_FILE" "$ECHO_HOST"

echo "install-gate-fixture: exempting $ECHO_HOST from the inference SSRF guard"
allowlist_add "$SSRF_ALLOW_FILE" "$ECHO_HOST"

# Truncate the echo log so the probe reads only this run's records
# (the canonical probe ignores records predating its getsize call, but a
# fresh log makes the gate's own evidence unambiguous).
: > "$ECHO_LOG"

# Start the echo fixture; its "PORT=<n>" stdout line is the readiness
# signal. Killed on exit (trap) -- the fixture is gate-scratch, never a
# service. Stderr is captured so a startup failure is diagnosable.
port_file="$(mktemp)"
err_file="$(mktemp)"
ECHO_FIXTURE_LOG="$ECHO_LOG" ECHO_FIXTURE_PORT="$ECHO_PORT" \
    "$ECHO_FIXTURE" >"$port_file" 2>"$err_file" &
echo_pid=$!
trap 'kill "$echo_pid" 2>/dev/null || true; rm -f "$port_file" "$err_file"' EXIT

port=""
deadline=$((SECONDS + 10))
while [ $SECONDS -lt "$deadline" ]; do
    if grep -q '^PORT=' "$port_file" 2>/dev/null; then
        port="$(grep '^PORT=' "$port_file" | head -1 | cut -d= -f2)"
        break
    fi
    sleep 0.1
done
if [ -z "$port" ]; then
    echo "install-gate-fixture: echo fixture failed to start (no PORT= line in 10s)" >&2
    echo "install-gate-fixture: echo fixture stderr:" >&2
    cat "$err_file" >&2
    exit 3
fi
echo "install-gate-fixture: echo fixture on 127.0.0.1:$port, log $ECHO_LOG"

echo "install-gate-fixture: verifying with the probe (gate mode)"
PROBE_MODE=gate \
PROBE_BASE_URL="http://127.0.0.1:${port}" \
PROBE_ECHO_LOG="$ECHO_LOG" \
PROBE_EXPECTED_SWAPPED="$FIXTURE_DUMMY" \
PROBE_KEY_NAME="$KEY_NAME" \
    timeout 15 "$HARNESS_PROBE_BIN" </dev/null
