#!/bin/bash
# install-gate-fixture.sh -- install the PUBLIC gate fixture for
# harness/harness-auth-probe (R2 section 5.4, "gate mode"; the probe
# contract is docs/PRE_SEEDED_HARNESS_RESEARCH.md section 5).
#
# Installs, through the existing narrow writers only:
#   1. the public dummy inference credential `gate-dummy` (NOT a secret --
#      the value is baked into this repo on purpose; it proves the swap
#      path end to end without ever touching a real credential),
#   2. its `bearer_header` placement in the inference registry,
#   3. the loopback echo host in inference-hosts.allow,
# then starts the loopback echo fixture (harness/echo-fixture.py) and
# runs the probe in gate mode to prove the fixture works.
#
# Idempotent: safe to re-run. The inference proxy hot-reloads the
# registry and hosts files per request, so no restart is needed.
#
# NEVER install a real credential with this script. The fixture dummy is
# public by design; a real key here would be baked into image layers and
# echo-server logs. Real tenant credentials travel the human-only
# grant-writer path (SETUP.md "Inference-model recipe"), never this one.
#
# FIXTURE LIFECYCLE (read before building on this): the fixture binds
# `gate-dummy` to the echo host and allowlists that host. That binding
# must NEVER coexist with a real credential -- after the gate passes, the
# echo host MUST be removed from inference-hosts.allow and the
# gate-dummy->echo-host binding MUST be unbound (by the image-build gate
# before publish, or by the provision-time injector when the real key
# lands). Otherwise any request to the echo host carrying the placeholder
# would swap in the REAL tenant key and ship it to the echo server. The
# gate is only safe because the fixture is public; the teardown is what
# keeps it safe once a real key exists. See harness/README.md
# "Fixture lifecycle".
#
# Env overrides (tests / nonstandard layouts):
#   CRED_STORE_SET_INFERENCE inference secret writer (default
#                            /usr/local/bin/cred-store-set-inference)
#   CRED_REGISTRY_SET_INFERENCE
#                            inference registry writer (default
#                            /usr/local/bin/cred-registry-set-inference)
#   INFERENCE_HOSTS_ALLOW    hosts.allow path (default
#                            /home/swapd/inference-hosts.allow)
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
# design -- keep in sync with FIXTURE_DUMMY in
# harness/test_install_gate_fixture.py (same value, documented there).
FIXTURE_DUMMY="GATE-FIXTURE-DUMMY-NOT-A-SECRET"
KEY_NAME="gate-dummy"
ECHO_HOST="127.0.0.1"

STORE_WRITER="${CRED_STORE_SET_INFERENCE:-/usr/local/bin/cred-store-set-inference}"
REGISTRY_WRITER="${CRED_REGISTRY_SET_INFERENCE:-/usr/local/bin/cred-registry-set-inference}"
ALLOW_FILE="${INFERENCE_HOSTS_ALLOW:-/home/swapd/inference-hosts.allow}"
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

echo "install-gate-fixture: installing public dummy credential '$KEY_NAME'"
printf '%s' "$FIXTURE_DUMMY" | run_priv "$STORE_WRITER"

echo "install-gate-fixture: registering bearer_header placement"
run_priv "$REGISTRY_WRITER" set "$KEY_NAME" access_token '"bearer_header"'

echo "install-gate-fixture: binding $KEY_NAME to echo host $ECHO_HOST"
run_priv "$REGISTRY_WRITER" add-host "$KEY_NAME" "$ECHO_HOST"

if run_priv grep -qxF "$ECHO_HOST" "$ALLOW_FILE" 2>/dev/null; then
    echo "install-gate-fixture: $ECHO_HOST already in $(basename "$ALLOW_FILE")"
else
    echo "install-gate-fixture: adding $ECHO_HOST to $(basename "$ALLOW_FILE")"
    # If a pre-existing file lacks its trailing newline, a bare append
    # would merge lines -- terminate it first.
    if run_priv test -s "$ALLOW_FILE" && [ -n "$(run_priv tail -c 1 "$ALLOW_FILE")" ]; then
        printf '\n' | run_priv tee -a "$ALLOW_FILE" >/dev/null
    fi
    printf '%s\n' "$ECHO_HOST" | run_priv tee -a "$ALLOW_FILE" >/dev/null
fi

# Truncate the echo log so the probe reads only this run's records
# (the canonical probe ignores records predating its getsize call, but a
# fresh log makes the gate's own evidence unambiguous).
: > "$ECHO_LOG"

# Start the echo fixture; its "PORT=<n>" stdout line is the readiness
# signal. Killed on exit (trap) -- the fixture is gate-scratch, never a
# service.
port_file="$(mktemp)"
ECHO_FIXTURE_LOG="$ECHO_LOG" ECHO_FIXTURE_PORT="$ECHO_PORT" \
    "$ECHO_FIXTURE" >"$port_file" 2>/dev/null &
echo_pid=$!
trap 'kill "$echo_pid" 2>/dev/null || true; rm -f "$port_file"' EXIT

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
    exit 3
fi
echo "install-gate-fixture: echo fixture on 127.0.0.1:$port, log $ECHO_LOG"

echo "install-gate-fixture: verifying with the probe (gate mode)"
PROBE_MODE=gate \
PROBE_BASE_URL="http://127.0.0.1:${port}" \
PROBE_ECHO_LOG="$ECHO_LOG" \
PROBE_EXPECTED_SWAPPED="$FIXTURE_DUMMY" \
PROBE_KEY_NAME="$KEY_NAME" \
    timeout 10 "$HARNESS_PROBE_BIN" </dev/null
