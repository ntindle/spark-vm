#!/bin/bash
# install-gate-fixture.sh -- install the PUBLIC gate fixture for
# provision/harness-auth-probe (R2 section 5.4, "gate mode").
#
# Installs, through the existing narrow writers only:
#   1. the public dummy inference credential `llm-api` (NOT a secret --
#      the value is baked into this repo on purpose; it proves the swap
#      path end to end without ever touching a real credential),
#   2. its `bearer_header` placement in the inference registry,
#   3. the echo host in inference-hosts.allow,
# then runs the probe in gate mode to prove the fixture works.
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
# `llm-api` to the public echo host and allowlists that host. That binding
# must NEVER coexist with a real credential -- after the gate passes, the
# echo host MUST be removed from inference-hosts.allow and the
# llm-api->echo-host binding MUST be unbound (by the image-build gate
# before publish, or by the provision-time injector when it installs the
# real key). Otherwise any request to the echo host carrying the
# placeholder would swap in the REAL tenant key and ship it to a public
# echo server. See provision/README.md "Fixture lifecycle".
#
# Env overrides (tests / nonstandard layouts):
#   HARNESS_GATE_ECHO_HOST   echo host (default httpbin.org)
#   CRED_STORE_SET_INFERENCE inference secret writer (default
#                            /usr/local/bin/cred-store-set-inference)
#   CRED_REGISTRY_SET_INFERENCE
#                            inference registry writer (default
#                            /usr/local/bin/cred-registry-set-inference)
#   INFERENCE_HOSTS_ALLOW    hosts.allow path (default
#                            /home/swapd/inference-hosts.allow)
#   SUDO_PREFIX              privilege prefix, e.g. "sudo -u swapd"
#                            (default "sudo -u swapd"; empty runs directly)
set -euo pipefail

ECHO_HOST="${HARNESS_GATE_ECHO_HOST:-httpbin.org}"
# Public, non-secret, on purpose. Keep it obviously-not-a-key.
# The public dummy credential installed by the gate fixture. Public by
# design -- keep in sync with FIXTURE_DUMMY in
# provision/test_harness_auth_probe.py (same value, documented there).
FIXTURE_DUMMY="GATE-FIXTURE-DUMMY-NOT-A-SECRET"

STORE_WRITER="${CRED_STORE_SET_INFERENCE:-/usr/local/bin/cred-store-set-inference}"
REGISTRY_WRITER="${CRED_REGISTRY_SET_INFERENCE:-/usr/local/bin/cred-registry-set-inference}"
ALLOW_FILE="${INFERENCE_HOSTS_ALLOW:-/home/swapd/inference-hosts.allow}"
# Empty SUDO_PREFIX means "run directly, no privilege change" (the test
# seam); a bare `-` (not `:-`) preserves that.
SUDO_PREFIX="${SUDO_PREFIX-sudo -u swapd}"
PROBE="$(dirname "$0")/harness-auth-probe"

if [ ! -x "$STORE_WRITER" ]; then
    echo "install-gate-fixture: store writer not executable: $STORE_WRITER (CRED_STORE_SET_INFERENCE)" >&2
    exit 2
fi
if [ ! -x "$REGISTRY_WRITER" ]; then
    echo "install-gate-fixture: registry writer not executable: $REGISTRY_WRITER (CRED_REGISTRY_SET_INFERENCE)" >&2
    exit 2
fi
if [ ! -x "$PROBE" ]; then
    echo "install-gate-fixture: probe not executable: $PROBE" >&2
    exit 2
fi

# shellcheck disable=SC2086  # SUDO_PREFIX is intentionally word-split
run_priv() { $SUDO_PREFIX "$@"; }

echo "install-gate-fixture: installing public dummy credential 'llm-api'"
printf '%s' "$FIXTURE_DUMMY" | run_priv "$STORE_WRITER"

echo "install-gate-fixture: registering bearer_header placement"
run_priv "$REGISTRY_WRITER" set llm-api access_token '"bearer_header"'

echo "install-gate-fixture: binding llm-api to echo host $ECHO_HOST"
run_priv "$REGISTRY_WRITER" add-host llm-api "$ECHO_HOST"

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

echo "install-gate-fixture: verifying with the probe (gate mode)"
HARNESS_PROBE_UPSTREAM="http://${ECHO_HOST}" \
HARNESS_PROBE_PATH="/headers" \
HARNESS_PROBE_EXPECT="echo" \
    timeout 10 "$PROBE" </dev/null
