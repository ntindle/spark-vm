#!/bin/bash
# proxy/deploy.sh — deploy the swap proxy, inference proxy, confirmd, and
# push-worker from the repo. Nick runs this as himself (not from the jail).
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
#                 A manual --no-restart caller owns the §7 step instead:
#                 `systemctl daemon-reload` + restart swap-proxy.service,
#                 swap-inference.service, confirmd.service, and
#                 push-worker.service, plus `systemctl enable --now
#                 summons-sweep.timer`. Restart is not optional hygiene —
#                 §4e's approval-filers group change leaves the still-running
#                 proxy without the group (filings demote to a loud log +
#                 no filing, fail-closed, until restart) and §5b's
#                 SPARKVM_PLANE_PUSH drop-ins take effect only after
#                 daemon-reload + restart.

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
for f in proxy/swap_addon.py proxy/host_match.py proxy/grant-writer proxy/cred-grant-revoke \
         proxy/cred-registry-set proxy/cred-registry-set-inference \
         proxy/cred-store-set proxy/cred-store-set-inference \
         proxy/cred-store-verify-inference \
         proxy/cred-store-get proxy/cred-store-delete \
         proxy/cred-ui-token-set \
         proxy/with-proxy proxy/ssrf.deny proxy/sudoers-swapd \
         proxy/safe_install.py \
         proxy/build_ca_bundle.py \
         proxy/privileged_read.py \
         proxy/swap-proxy.service proxy/swap-inference.service \
         proxy/summons-sweep.service proxy/summons-sweep.timer \
         confirm/confirmd.py confirm/confirm-request confirm/confirmd.service \
         confirm/push-worker.service confirm/push.py \
         VERSION scripts/sparkvm_version.py scripts/bounded_http.py; do
    if [ ! -f "$f" ]; then
        echo "ERROR: required repo file missing: $f — aborting before any mutation"
        exit 1
    fi
done
python3 -m py_compile proxy/swap_addon.py proxy/host_match.py confirm/confirmd.py confirm/push.py \
    proxy/safe_install.py proxy/build_ca_bundle.py proxy/privileged_read.py \
    scripts/sparkvm_version.py scripts/bounded_http.py \
    || { echo "ERROR: python syntax check failed — aborting"; exit 1; }
# VERSION feeds audit JSON via the updater: a non-semver VERSION must fail
# the deploy here, loudly, rather than become "unknown" downstream.
python3 scripts/sparkvm_version.py --check >/dev/null \
    || { echo "ERROR: VERSION is not valid semver — aborting"; exit 1; }

# --- 1. Python addons and scripts ---------------------------------------
echo "[1/7] Installing proxy files to /home/swapd..."
sudo install -o swapd -g swapd -m 0644 proxy/swap_addon.py /home/swapd/swap_addon.py
# Issue #261: swap_addon.py imports the shared matcher from host_match.py
# (its own directory is on sys.path in the standalone deploy, exactly
# like the sparkvm_version.py helper below) -- the shared module must
# ship with it, or the proxy fails its import loudly at service start.
sudo install -o swapd -g swapd -m 0644 proxy/host_match.py /home/swapd/host_match.py
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
# Issue #964: narrow writer for cred-ui's per-install API token
# (/home/swapd/ui-token, 0600 swapd-owned).
sudo install -o root -g root -m 0755 proxy/cred-ui-token-set /usr/local/bin/cred-ui-token-set
# Issue #706: the shared validation contract ships next to the writers it
# serves (same install step, so the two update atomically). Root-owned
# 0644: it is imported, never executed.
sudo install -o root -g root -m 0644 credlib/credvalidate.py /usr/local/bin/credvalidate.py
# Verify the security-critical writers landed root-owned 0755. Any
# install failure above aborts via set -e; this guards against silent
# drift (a stale or tampered /usr/local/bin).
for f in cred-registry-set cred-registry-set-inference cred-store-set \
         cred-store-set-inference cred-store-verify-inference cred-store-get \
         cred-store-delete cred-ui-token-set \
         cred-grant-revoke; do
    got="$(stat -c '%U:%a' "/usr/local/bin/$f")"
    if [ "$got" != "root:755" ]; then
        echo "ERROR: /usr/local/bin/$f has owner:mode $got, expected root:755 — aborting before any service restart"
        exit 1
    fi
done
# The validation module must be root-owned 0644 next to the writers: a
# missing or tampered copy must fail the deploy here, not a writer
# invocation later.
got="$(stat -c '%U:%a' /usr/local/bin/credvalidate.py)"
if [ "$got" != "root:644" ]; then
    echo "ERROR: /usr/local/bin/credvalidate.py has owner:mode $got, expected root:644 — aborting before any service restart"
    exit 1
fi

# --- 2. confirmd ---------------------------------------------------------
echo "[2/7] Installing confirmd..."
sudo install -o swapd -g swapd -m 0644 confirm/confirmd.py /home/swapd/confirmd.py
# Issue #471: confirmd's shared bounded-HTTP helper must ship with it —
# the standalone deployment adds /home/swapd to sys.path, so a missing
# helper would fail the import loudly at service start.
sudo install -o swapd -g swapd -m 0644 scripts/bounded_http.py /home/swapd/bounded_http.py
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
# --create-only does check-and-create atomically as root (os.link: EEXIST on an
# existing dest gives the old O_EXCL atomicity), and the
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
# the swapd CA cert. Rebuilt on every proxy deploy — and since issue #302,
# a CA rotation itself forces a proxy redeploy, so a rotated CA is picked
# up without a concurrent code change.
# Issue #303: honor WITH_PROXY_CA_BUNDLE (components.conf advertises it as
# env-overridable for snapshot/rollback, but deploy.sh wrote a hardcoded
# literal). The default keeps the old path, so the install-paths coverage
# test's literal pin stays green.
ca_bundle_dest="${WITH_PROXY_CA_BUNDLE:-/usr/local/share/with-proxy-ca/ca-bundle.crt}"
sudo mkdir -p "$(dirname "$ca_bundle_dest")"
# The CA source is swapd-writable: build_ca_bundle.py refuses a planted
# symlink there (issue #144 — the old `cat` followed it and would leak a
# root-readable file into this world-readable bundle). A missing CA on a
# first deploy still skips LOUDLY inside the helper; the destination write
# goes through safe_install (no symlink write-through, root:root 0644).
sudo python3 proxy/build_ca_bundle.py \
    --dest "$ca_bundle_dest"
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

# --- 4e. confirmd pending/ setgid dir (issue #1167, Finding 50) ------------
echo "[4e/7] Ensuring confirmd pending/ is a setgid filing dir..."
# Finding 50's owner-identifies-requester invariant needs pending/ to be
# a setgid dir owned by the filing principals' shared group. mkdir(2)
# drops S_ISGID even for root, so no makedirs in confirm-request or
# confirmd can establish it — the deploy step must (the operator
# contract in confirm/README.md names this group explicitly now).
# Dedicated group `approval-filers`, not group swapd: bdrive must
# eventually file here too, and putting bdrive in group swapd would hand
# it far more than filing rights. swapd files today (the proxy refusal
# path); bdrive joins when its user lands (box hardening).
# Idempotent: groupadd/usermod are no-ops on repeat runs, and the helper
# repairs drift with a WARNING instead of failing.
# Rollback note: pending/ is deliberately NOT in proxy_install_paths —
# a rollback must never delete or restore live approval state.
# Deploy-window note: between this chmod and the §7 restart, the still-
# running proxy (started before the usermod) lacks the new group and
# gets EACCES when filing — the addon's except OSError demotes that to
# a loud log + no filing (the swap stays refused, fail-closed); the §7
# restart (or the auto-deploy component restart) picks up the group.
# Issue #108: CONFIRM_DIR is env-overridable so deploy tests can
# redirect it at tmp instead of touching the host.
pending_group="approval-filers"
if ! getent group "$pending_group" >/dev/null; then
    sudo groupadd -r "$pending_group"
fi
sudo usermod -aG "$pending_group" swapd
if id -u bdrive >/dev/null 2>&1; then
    sudo usermod -aG "$pending_group" bdrive
fi
approvals_dir="${CONFIRM_DIR:-/home/swapd/approvals}"
# The parent stays swapd-owned (confirmd makedirs answered//consumed as
# swapd); only the leaf is root-owned setgid.
sudo -u swapd mkdir -p "$approvals_dir"
sudo python3 proxy/enforce_pending_dir.py --create \
    --owner root --group "$pending_group" --mode 2770 \
    "$approvals_dir/pending"

# --- 5. systemd units (finding 66) -----------------------------------------
echo "[5/7] Installing systemd units..."
sudo install -o root -g root -m 0644 proxy/swap-proxy.service /etc/systemd/system/swap-proxy.service
sudo install -o root -g root -m 0644 proxy/swap-inference.service /etc/systemd/system/swap-inference.service
sudo install -o root -g root -m 0644 confirm/confirmd.service /etc/systemd/system/confirmd.service
sudo install -o root -g root -m 0644 confirm/push-worker.service /etc/systemd/system/push-worker.service
# G4 S1 (GitHub #428): summons outbox reconciliation sweep (one-shot +
# 5-minute timer).
sudo install -o root -g root -m 0644 proxy/summons-sweep.service /etc/systemd/system/summons-sweep.service
sudo install -o root -g root -m 0644 proxy/summons-sweep.timer /etc/systemd/system/summons-sweep.timer

# --- 5b. plane push handoff (GitHub #1135) -----------------------------------
# On a plane-enrolled box the plane push lane is the paging channel, so the
# box-local push queue stands down via SPARKVM_PLANE_PUSH=1 drop-ins on the
# two services that consult it (swap-proxy: the enqueue path in the swap
# addon; push-worker: the delivery worker). Detection runs here as root:
# the pairing record is 0600 in the operator's home, unreadable by swapd —
# which is exactly why the services cannot auto-detect and the deploy must
# decide. Not enrolled → any stale drop-ins are removed, so a re-deploy
# after un-enrollment restores the box-local queue. Self-hosted boxes are
# unaffected (no enrollment record → no drop-ins). To override manually,
# write/remove the drop-in and re-run the deploy (or daemon-reload).
echo "[5b/7] Checking plane enrollment for the push handoff..."
plane_enrolled=0
for _pair_home in /root ${SUDO_USER:+/home/$SUDO_USER}; do
    _enroll="$_pair_home/.config/spark-pair/enrollment.json"
    if [ -f "$_enroll" ] && python3 -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
sys.exit(0 if isinstance(d, dict) and d.get("token") else 1)
' "$_enroll" 2>/dev/null; then
        plane_enrolled=1
        break
    fi
done
for _svc in swap-proxy push-worker; do
    _dropdir="/etc/systemd/system/$_svc.service.d"
    if [ "$plane_enrolled" = "1" ]; then
        sudo install -o root -g root -m 0755 -d "$_dropdir"
        printf '[Service]\nEnvironment=SPARKVM_PLANE_PUSH=1\n' | \
            sudo tee "$_dropdir/10-plane-push.conf" > /dev/null
        echo "    $_svc: plane-enrolled -> SPARKVM_PLANE_PUSH=1 drop-in installed"
    else
        sudo rm -f "$_dropdir/10-plane-push.conf"
        echo "    $_svc: not plane-enrolled -> no push-handoff drop-in"
    fi
done
unset _pair_home _enroll _svc _dropdir plane_enrolled

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
    echo "[7/7] Skipping service restarts (--no-restart)"
    echo "      Caller owns the restart: systemctl daemon-reload, then restart"
    echo "      swap-proxy.service swap-inference.service confirmd.service push-worker.service"
    echo "      plus: systemctl enable --now summons-sweep.timer"
    echo "      (confirmd included). Until then: the still-running proxy lacks §4e's"
    echo "      approval-filers group (filings demote to a loud log + no filing,"
    echo "      fail-closed), and §5b's SPARKVM_PLANE_PUSH drop-ins have no effect."
    echo ""
    echo "Deploy complete (no restart). The repo is the only source (finding 19)."
    exit 0
fi
echo "[7/7] Reloading systemd and restarting services..."
sudo systemctl daemon-reload
sudo systemctl enable swap-proxy.service swap-inference.service confirmd.service push-worker.service
sudo systemctl enable --now summons-sweep.timer
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
for svc in swap-proxy swap-inference confirmd push-worker; do
    if sudo systemctl is-active --quiet "$svc.service"; then
        echo "  $svc: active"
    else
        echo "  $svc: FAILED"
        sudo systemctl status "$svc.service" --no-pager | head -20
    fi
done
# G4 S1: the summons sweep is a timer, not a long-running service —
# check the timer is armed, not the one-shot service.
if sudo systemctl is-active --quiet "summons-sweep.timer"; then
    echo "  summons-sweep.timer: active"
else
    echo "  summons-sweep.timer: FAILED"
    sudo systemctl status "summons-sweep.timer" --no-pager | head -20
fi

# Issue #261: swap_addon.py hard-imports the sibling host_match.py at
# module load. mitmproxy catches a script import failure, logs it, and
# keeps running WITHOUT the addon -- a dumb forwarder with no
# ssrf.deny/hosts.allow enforcement, while the port + is-active checks
# above stay green. The addon's __init__ logs "swap_addon: spark-vm
# version ..." on every successful load, so its presence in the journal
# since the service (re)started proves the addon is actually enforcing.
# (Positive signal, not an "error in script" grep: a renamed mitmproxy
# log line fails this check loudly instead of passing silently.)
# Retry briefly: journald delivery can lag the restart by a second or two.
for svc in swap-proxy.service swap-inference.service; do
    start_ts=$(sudo systemctl show "$svc" -p ExecMainStartTimestamp --value 2>/dev/null)
    if [ -z "$start_ts" ] || [ "$start_ts" = "n/a" ]; then
        echo "  ERROR: cannot determine start time of $svc -- addon load unverifiable, refusing"
        exit 1
    fi
    loaded=0
    for attempt in $(seq 1 5); do
        # Capture-then-grep (no pipe): `journalctl | grep -q` under
        # pipefail races SIGPIPE (141) when grep -q exits on first match,
        # false-reporting "not loaded" on a healthy box.
        journal_out=$(sudo journalctl -u "$svc" --since "$start_ts" --no-pager 2>/dev/null) || true
        if grep -q "swap_addon: spark-vm version" <<< "$journal_out"; then
            loaded=1; break
        fi
        sleep 1
    done
    if [ "$loaded" = "1" ]; then
        echo "  $svc: addon loaded (version line in journal since $start_ts)"
    else
        echo "  ERROR: $svc shows no swap_addon load signal since $start_ts -- the proxy may be running addon-less (no enforcement). Refusing."
        exit 1
    fi
done

# Warn if ssrf.deny is missing (finding 61).
if ! sudo test -f /home/swapd/ssrf.deny; then  # 69(e): swapd home is 0700, test under sudo
    echo "WARNING: /home/swapd/ssrf.deny missing (finding 61)"
fi

echo ""
echo "Deploy complete. The repo is the only source (finding 19)."
