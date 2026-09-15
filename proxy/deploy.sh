#!/bin/bash
# proxy/deploy.sh — deploy the swap proxy, inference proxy, and confirmd
# from the repo. Nick runs this as himself (not from the jail).
#
# Finding 66: runs `systemctl daemon-reload` before restarting, so unit
# file changes take effect. Finding 19: this script is the rebuild
# documentation — the repo is the only source.
#
# Usage: ./proxy/deploy.sh
# Must be run from the repo root.

set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

echo "=== spark-vm deploy from $REPO ==="

# --- 1. Python addons and scripts ---------------------------------------
echo "[1/7] Installing proxy files to /home/swapd..."
sudo install -o swapd -g swapd -m 0644 proxy/swap_addon.py /home/swapd/swap_addon.py
sudo install -o swapd -g swapd -m 0755 proxy/grant-writer /home/swapd/grant-writer
sudo install -o root -g root -m 0755 proxy/cred-grant-revoke /usr/local/bin/cred-grant-revoke
sudo install -o root -g root -m 0755 proxy/cred-registry-set /usr/local/bin/cred-registry-set 2>/dev/null || true
sudo install -o root -g root -m 0755 proxy/cred-registry-set-inference /usr/local/bin/cred-registry-set-inference 2>/dev/null || true

# --- 2. confirmd ---------------------------------------------------------
echo "[2/7] Installing confirmd..."
sudo install -o swapd -g swapd -m 0644 confirm/confirmd.py /home/swapd/confirmd.py
sudo install -o root -g root -m 0755 confirm/confirm-request /usr/local/bin/confirm-request

# --- 3. ssrf.deny (finding 61) -------------------------------------------
echo "[3/7] Installing ssrf.deny..."
# Start from the repo file (has the ts.net name), then append the host's
# current tailscale IPs (box-specific, finding 47).
sudo cp proxy/ssrf.deny /home/swapd/ssrf.deny
if command -v tailscale >/dev/null 2>&1; then
    tailscale ip 2>/dev/null | while read -r ip; do
        if [ -n "$ip" ]; then
            # Avoid duplicates.
            if ! sudo grep -qxF "$ip" /home/swapd/ssrf.deny 2>/dev/null; then
                echo "$ip" | sudo tee -a /home/swapd/ssrf.deny >/dev/null
            fi
        fi
    done
else
    echo "WARNING: tailscale not found; ssrf.deny has only the ts.net name"
fi
sudo chown swapd:swapd /home/swapd/ssrf.deny
sudo chmod 0644 /home/swapd/ssrf.deny

# --- 4. grants.json (finding 60) ------------------------------------------
echo "[4/7] Ensuring grants.json exists..."
if [ ! -f /home/swapd/grants.json ]; then
    echo '{"grants": []}' | sudo tee /home/swapd/grants.json >/dev/null
fi
sudo chown swapd:swapd /home/swapd/grants.json
sudo chmod 0600 /home/swapd/grants.json

# --- 5. systemd units (finding 66) -----------------------------------------
echo "[5/7] Installing systemd units..."
sudo install -o root -g root -m 0644 proxy/swap-proxy.service /etc/systemd/system/swap-proxy.service
sudo install -o root -g root -m 0644 proxy/swap-inference.service /etc/systemd/system/swap-inference.service
sudo install -o root -g root -m 0644 confirm/confirmd.service /etc/systemd/system/confirmd.service

# --- 6. sudoers -------------------------------------------------------------
echo "[6/7] Installing sudoers..."
sudo install -o root -g root -m 0440 proxy/sudoers-swapd /etc/sudoers.d/swapd
sudo visudo -c -f /etc/sudoers.d/swapd

# --- 7. daemon-reload and restart (finding 66) -------------------------------
echo "[7/7] Reloading systemd and restarting services..."
sudo systemctl daemon-reload
sudo systemctl restart swap-proxy.service
sudo systemctl restart swap-inference.service
sudo systemctl restart confirmd.service

echo ""
echo "=== verifying ==="
for svc in swap-proxy swap-inference confirmd; do
    if sudo systemctl is-active --quiet "$svc.service"; then
        echo "  $svc: active"
    else
        echo "  $svc: FAILED"
        sudo systemctl status "$svc.service" --no-pager | head -20
    fi
done

# Warn if ssrf.deny is missing (finding 61). swapd's home is 0700, so
# the check needs sudo; without it the test always fails and the warning
# is noise.
if ! sudo test -f /home/swapd/ssrf.deny; then
    echo "WARNING: /home/swapd/ssrf.deny missing (finding 61)"
fi

echo ""
echo "Deploy complete. The repo is the only source (finding 19)."
