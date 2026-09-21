#!/bin/bash
# proxy/deploy.sh — deploy the swap proxy, inference proxy, and confirmd
# from the repo. Nick runs this as himself (not from the jail).
#
# Finding 66: runs `systemctl daemon-reload` before restarting, so unit
# file changes take effect. Finding 19: this script is the rebuild
# documentation — the repo is the only source.
#
# Usage: ./proxy/deploy.sh [--no-restart] [--help]
# Must be run from the repo root.
#
#   --no-restart  install everything but do not restart services (used by
#                 deploy/auto-deploy.sh, which restarts only the services
#                 belonging to changed components).

set -euo pipefail

NO_RESTART=0
for arg in "$@"; do
    case "$arg" in
        --no-restart) NO_RESTART=1 ;;
        --help|-h)
            echo "Usage: ./proxy/deploy.sh [--no-restart]"
            echo "Deploys swap proxy, inference proxy, and confirmd from the repo."
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $arg (try --help)" >&2
            exit 1
            ;;
    esac
done

# --- single-flight with the auto-deploy timer ---------------------------------
# A manual deploy.sh racing the 10-minute unattended updater would interleave
# installs and restarts (and the updater's rollback snapshot could capture a
# half-installed manual state). Take the same lock the updater holds; the
# updater sets AUTO_DEPLOY_HOLDS_LOCK when it invokes this script itself.
# Run this script as the box owner (ntindle), not root, so the lock path matches.
UPDATER_STATE_DIR="${UPDATER_STATE_DIR:-/home/ntindle/.sparkvm-deploy}"
if [ "${AUTO_DEPLOY_HOLDS_LOCK:-0}" != "1" ]; then
    mkdir -p "$UPDATER_STATE_DIR"
    exec 9>"$UPDATER_STATE_DIR/auto-deploy.lock"
    if ! flock -n 9; then
        echo "ERROR: auto-deploy holds the lock (unattended deploy in progress) — try again in a minute" >&2
        exit 1
    fi
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

echo "=== spark-vm deploy from $REPO ==="

# --- 0. preflight: validate everything BEFORE touching the box --------
echo "[0/7] Preflight (no mutations yet)..."
for f in proxy/swap_addon.py proxy/grant-writer proxy/cred-grant-revoke \
         proxy/cred-registry-set proxy/cred-registry-set-inference \
         proxy/cred-store-set proxy/cred-store-set-inference \
         proxy/cred-store-verify-inference \
         proxy/cred-store-get proxy/cred-store-delete \
         proxy/with-proxy proxy/ssrf.deny proxy/sudoers-swapd \
         proxy/safe_install.py \
         proxy/swap-proxy.service proxy/swap-inference.service \
         confirm/confirmd.py confirm/confirm-request confirm/confirmd.service \
         confirm/push-worker.service \
         VERSION scripts/sparkvm_version.py; do
    if [ ! -f "$f" ]; then
        echo "ERROR: required repo file missing: $f — aborting before any mutation"
        exit 1
    fi
done
python3 -m py_compile proxy/swap_addon.py confirm/confirmd.py \
    proxy/safe_install.py scripts/sparkvm_version.py \
    || { echo "ERROR: python syntax check failed — aborting"; exit 1; }
# VERSION feeds audit JSON via the updater: a non-semver VERSION must fail
# the deploy here, loudly, rather than become "unknown" downstream.
python3 scripts/sparkvm_version.py --check >/dev/null \
    || { echo "ERROR: VERSION is not valid semver — aborting"; exit 1; }

# --- 1. Python addons and scripts ---------------------------------------
echo "[1/7] Installing proxy files to /home/swapd..."
sudo install -o swapd -g swapd -m 0644 proxy/swap_addon.py /home/swapd/swap_addon.py
sudo install -o swapd -g swapd -m 0755 proxy/grant-writer /home/swapd/grant-writer
# Version stamping (docs/VERSIONING.md): the deployed standalone files resolve
# the repo VERSION by walking up from their own directory, so install the
# VERSION file and the reader next to them.
sudo install -o swapd -g swapd -m 0644 VERSION /home/swapd/VERSION
sudo install -o swapd -g swapd -m 0644 scripts/sparkvm_version.py /home/swapd/sparkvm_version.py
sudo install -o root -g root -m 0755 proxy/cred-grant-revoke /usr/local/bin/cred-grant-revoke
sudo install -o root -g root -m 0755 proxy/cred-registry-set /usr/local/bin/cred-registry-set
sudo install -o root -g root -m 0755 proxy/cred-registry-set-inference /usr/local/bin/cred-registry-set-inference
sudo install -o root -g root -m 0755 proxy/cred-store-set /usr/local/bin/cred-store-set
sudo install -o root -g root -m 0755 proxy/cred-store-set-inference /usr/local/bin/cred-store-set-inference
sudo install -o root -g root -m 0755 proxy/cred-store-verify-inference /usr/local/bin/cred-store-verify-inference
sudo install -o root -g root -m 0755 proxy/cred-store-get /usr/local/bin/cred-store-get
sudo install -o root -g root -m 0755 proxy/cred-store-delete /usr/local/bin/cred-store-delete
# Verify the security-critical writers landed root-owned 0755. Any
# install failure above aborts via set -e; this guards against silent
# drift (a stale or tampered /usr/local/bin).
for f in cred-registry-set cred-registry-set-inference cred-store-set \
         cred-store-set-inference cred-store-verify-inference cred-store-get \
         cred-store-delete \
         cred-grant-revoke; do
    got="$(stat -c '%U:%a' "/usr/local/bin/$f")"
    if [ "$got" != "root:755" ]; then
        echo "ERROR: /usr/local/bin/$f has owner:mode $got, expected root:755 — aborting before any service restart"
        exit 1
    fi
done

# --- 2. confirmd ---------------------------------------------------------
echo "[2/7] Installing confirmd..."
sudo install -o swapd -g swapd -m 0644 confirm/confirmd.py /home/swapd/confirmd.py
# H2: VAPID push sender, installed next to confirmd.py and swap_addon.py
# (both import it from their own directory).
sudo install -o swapd -g swapd -m 0644 confirm/push.py /home/swapd/push.py
sudo install -o root -g root -m 0755 confirm/confirm-request /usr/local/bin/confirm-request

# --- 3. ssrf.deny (finding 61) -------------------------------------------
echo "[3/7] Installing ssrf.deny..."
# Build the full denylist (repo file + this box's tailscale IPs, deduped,
# order-preserving) and write it with the symlink-safe helper: cp/tee/chown/
# chmod all FOLLOW symlinks, so a swapd-planted /home/swapd/ssrf.deny ->
# /etc/... would get this (unattended, root) deploy to write through it --
# and chown would hand the target to swapd (same class as #91/#128; GNU
# `install` in steps 1/2 replaces symlinks instead, so those are safe).
# The file is rebuilt declaratively each deploy (repo + current tailscale
# IPs); box-local manual additions are not preserved -- the repo is the
# only source (finding 19).
tmp_deny="$(sudo mktemp /tmp/ssrf-deny.XXXXXX)"
{
    cat proxy/ssrf.deny
    if command -v tailscale >/dev/null 2>&1; then
        # Start from the repo file (has the ts.net name), then the host's
        # current tailscale IPs (box-specific, finding 47).
        tailscale ip 2>/dev/null || true
    else
        echo "WARNING: tailscale not found; ssrf.deny has only the ts.net name" >&2
    fi
} | awk 'NF && !seen[$0]++' | sudo tee "$tmp_deny" >/dev/null
sudo python3 proxy/safe_install.py --src "$tmp_deny" \
    --owner swapd --group swapd --mode 0644 /home/swapd/ssrf.deny
sudo rm -f "$tmp_deny"

# --- 4. grants.json (finding 60) ------------------------------------------
echo "[4/7] Ensuring grants.json exists..."
# The existence check AND the create must run under the same privilege:
# the old `[ -f ]` ran as the deploy user, so when /home/swapd was not
# traversable the guard always took the create branch -- and the old
# `sudo tee` (truncate, not append) then wiped grants.json on EVERY deploy.
# --create-only does check-and-create atomically as root (O_EXCL), and the
# owner/mode are enforced on the fd, never through a symlink (#128 class).
printf '{"grants": []}\n' | sudo python3 proxy/safe_install.py --stdin \
    --create-only --owner swapd --group swapd --mode 0600 \
    /home/swapd/grants.json

# --- 4a. audit log (swap.log) ---------------------------------------------
echo "[4a/7] Tightening any pre-existing audit log..."
# The writers create swap.log 0600, but a log left 0644 by the old code
# stays that way (creation-only mode). Tighten it here every deploy --
# through the symlink-safe helper (chown/chmod follow symlinks, #91 class).
if sudo test -f /home/swapd/swap.log; then
    sudo python3 proxy/safe_install.py --owner swapd --group swapd \
        --mode 0600 /home/swapd/swap.log
fi
echo "[4a.2/7] Installing swap.log rotation policy (GitHub #198)..."
# The audit trail is bounded by rotation, not by hope: swap.log is
# append-only, and a full disk fails EVERY swap closed (the audit write
# is part of authorization) — a total outage of credentialed egress.
# The addon opens/appends/closes per write (no persistent fd), so
# logrotate's rename+create needs no postrotate signal and never drops a
# line across the rotate boundary. Not --create-only: a tightened policy
# must land on redeploy. Covers the inference proxy's audit log too.
sudo python3 proxy/safe_install.py --stdin \
    --owner root --group root --mode 0644 \
    /etc/logrotate.d/swap-proxy < proxy/swap-logrotate.conf

# --- 4b. with-proxy + its CA bundle (owner decision 13) ------------------
echo "[4b/7] Building the with-proxy CA bundle and installing with-proxy..."
# The swapd CA is not in the host store; with-proxy uses system CAs plus
# the swapd CA cert. Rebuilt on every deploy so a rotated CA is picked up.
sudo mkdir -p /usr/local/share/with-proxy-ca
if sudo test -f /home/swapd/.mitmproxy/mitmproxy-ca-cert.pem; then
    sudo sh -c 'cat /etc/ssl/certs/ca-certificates.crt /home/swapd/.mitmproxy/mitmproxy-ca-cert.pem > /usr/local/share/with-proxy-ca/ca-bundle.crt'
    sudo chmod 0644 /usr/local/share/with-proxy-ca/ca-bundle.crt
else
    # First-time deploy: the proxy has never run, so it has not generated
    # its CA yet. Skip the bundle LOUDLY rather than aborting mid-deploy;
    # the restart below starts the proxy, which generates the CA, and the
    # next deploy (or a manual re-run of this step) builds the bundle.
    # Until then with-proxy refuses to run (it checks for the bundle).
    echo "WARNING: /home/swapd/.mitmproxy/mitmproxy-ca-cert.pem missing (first deploy?)"
    echo "WARNING: skipping CA bundle; re-run deploy.sh after the proxy has started once"
fi
sudo install -o root -g root -m 0755 proxy/with-proxy /usr/local/bin/with-proxy

# --- 4c. secrets dirs (issue #91) -------------------------------------------
echo "[4c/7] Enforcing secrets dir ownership and mode..."
# SETUP.md documents the secrets dirs as 0700 swapd-only, but nothing
# created or enforced them: cred-store-set's mktemp fails closed when the
# dir is absent, and a dir left 0755 would expose credential NAMES to all
# local users (values stay 0600, and names are already listable via the
# sudoers `ls` entry — impact is minimal, but the doc must hold).
# Enforce it on every deploy, alongside grants.json (4) and swap.log (4a).
# The helper refuses symlinks outright: chown/chmod follow them, so a
# swapd-level attacker who planted a secrets-dir symlink at /etc would
# otherwise get the next (unattended) deploy to hand them a system dir.
# Enforcement is race-free (lstat + O_NOFOLLOW open + fchown/fchmod on
# the fd) and prints a WARNING whenever it actually repaired drift.
for d in /home/swapd/secrets /home/swapd/inference-secrets; do
    sudo mkdir -p "$d"
    sudo python3 proxy/enforce_secrets_dir.py "$d"
done

# --- 4d. inference SSRF allow file (findings 29, 31) -----------------------
echo "[4d/7] Ensuring inference-ssrf.allow exists..."
# The inference proxy reads its SSRF exceptions from its OWN file, never
# the main proxy's shared /home/swapd/ssrf.allow (see
# proxy/swap-inference.service): the gate fixture's loopback exemption
# (harness/install-gate-fixture.sh) must never weaken the main proxy's
# egress guard. Ships empty (default deny); deploy.sh never adds entries
# -- the gate installer appends 127.0.0.1 and the provision-time injector
# removes it before the real credential lands.
if ! sudo test -e /home/swapd/inference-ssrf.allow; then
    sudo install -o swapd -g swapd -m 0644 /dev/null /home/swapd/inference-ssrf.allow
fi

# --- 5. systemd units (finding 66) -----------------------------------------
echo "[5/7] Installing systemd units..."
sudo install -o root -g root -m 0644 proxy/swap-proxy.service /etc/systemd/system/swap-proxy.service
sudo install -o root -g root -m 0644 proxy/swap-inference.service /etc/systemd/system/swap-inference.service
sudo install -o root -g root -m 0644 confirm/confirmd.service /etc/systemd/system/confirmd.service
sudo install -o root -g root -m 0644 confirm/push-worker.service /etc/systemd/system/push-worker.service

# --- 6. sudoers -------------------------------------------------------------
echo "[6/7] Installing sudoers..."
# Validate BEFORE installing: a bad sudoers file must never go live.
# Write to a temp root-owned file, visudo-check it, then move it over
# the real path atomically.
tmp_sudoers="$(sudo mktemp /etc/sudoers.d/.swapd.XXXXXX)"
sudo install -o root -g root -m 0440 proxy/sudoers-swapd "$tmp_sudoers"
if ! sudo visudo -c -f "$tmp_sudoers"; then
    echo "ERROR: sudoers validation failed — not installing"
    sudo rm -f "$tmp_sudoers"
    exit 1
fi
sudo mv -f "$tmp_sudoers" /etc/sudoers.d/swapd
# (rename(2) replaces a destination symlink instead of writing through it --
# verified empirically -- and /etc/sudoers.d is root-owned, so only root
# could plant one there anyway.)

# --- 7. daemon-reload and restart (finding 66) -------------------------------
if [ "$NO_RESTART" = "1" ]; then
    echo "[7/7] Skipping service restarts (--no-restart; caller restarts affected services)"
    echo ""
    echo "Deploy complete (no restart). The repo is the only source (finding 19)."
    exit 0
fi
echo "[7/7] Reloading systemd and restarting services..."
sudo systemctl daemon-reload
sudo systemctl enable swap-proxy.service swap-inference.service confirmd.service push-worker.service
sudo systemctl restart swap-proxy.service
sudo systemctl restart swap-inference.service
sudo systemctl restart confirmd.service
sudo systemctl restart push-worker.service

echo ""
echo "=== verifying ==="
# mitmdump takes a few seconds to listen after restart; a pull.sh run
# straight after deploy would otherwise fail with "Couldn't connect".
proxy_ready=0
for attempt in $(seq 1 20); do
    if (exec 3<>/dev/tcp/127.0.0.1/18080) 2>/dev/null; then proxy_ready=1; break; fi
    sleep 0.5
done
if [ "$proxy_ready" != "1" ]; then
    echo "  WARNING: proxy port 18080 not listening after $attempt tries"
fi
for svc in swap-proxy swap-inference confirmd; do
    if sudo systemctl is-active --quiet "$svc.service"; then
        echo "  $svc: active"
    else
        echo "  $svc: FAILED"
        sudo systemctl status "$svc.service" --no-pager | head -20
    fi
done

# Warn if ssrf.deny is missing (finding 61).
if ! sudo test -f /home/swapd/ssrf.deny; then  # 69(e): swapd home is 0700, test under sudo
    echo "WARNING: /home/swapd/ssrf.deny missing (finding 61)"
fi

echo ""
echo "Deploy complete. The repo is the only source (finding 19)."
