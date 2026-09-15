#!/bin/bash
# Deploy bdrive v1 (round 8) on the spark-vm host.
# Reviewed by Nick; run by Nick:  sudo ./browser-driver/deploy.sh
# (from the repo root). Installs the daemon, CLI, service user,
# socket dir, approvals dirs (finding 50 setgid group), the jail
# bind-mount + ordering, and the nftables egress rule (finding 10).
set -euo pipefail
cd "$(dirname "$0")/.."

say() { echo "[bdrive-deploy] $*"; }

# --- 1. users and groups -------------------------------------------
if ! id bdrive >/dev/null 2>&1; then
    say "creating user bdrive"
    sudo useradd -r -m -s /usr/sbin/nologin bdrive
fi
if ! getent group bdrive-clients >/dev/null; then
    say "creating group bdrive-clients"
    sudo groupadd -r bdrive-clients
fi
# The jail's agent reaches the host as a userns-mapped uid: with
# PrivateUsers=2000000:65536, guest uid G appears on the host as
# 2000000+G. The agent logs in as the jail's "muse" user, so read its
# guest uid from the jail rootfs and derive the real peer uid.
# (A host user with that numeric uid would NOT help: the connecting
# process is the mapped jail process, and host group membership can
# never apply to it — SO_PEERCRED on the numeric uid is the gate.)
JAIL_ROOTFS="/var/lib/machines/jail"
if [ ! -f "${JAIL_ROOTFS}/etc/passwd" ]; then
    say "ERROR: jail rootfs not found at ${JAIL_ROOTFS};"
    say "build the jail (jail/build.sh) before deploying bdrive."
    exit 1
fi
GUEST_UID="$(awk -F: '/^muse:/ {print $3}' "${JAIL_ROOTFS}/etc/passwd")"
if [ -z "${GUEST_UID}" ]; then
    say "ERROR: no 'muse' user in ${JAIL_ROOTFS}/etc/passwd."
    exit 1
fi
PEER_UID="$((2000000 + GUEST_UID))"
say "jail agent: guest uid ${GUEST_UID} -> host uid ${PEER_UID}"
# The daemon files approvals into 2770 swapd:bdrive dirs, so it needs
# the bdrive group (its primary group is bdrive-clients, set by the
# unit). swapd needs it too, to read/move what bdrive files.
sudo usermod -aG bdrive bdrive
sudo usermod -aG bdrive swapd

# --- 2. profile and shots dirs --------------------------------------
sudo install -d -o bdrive -g bdrive -m 0700 /home/bdrive/profile
sudo install -d -o bdrive -g bdrive -m 0750 /home/bdrive/shots

# --- 3. approvals dirs: setgid group (finding 50) -------------------
# bdrive (the daemon) files purchase approvals here; confirmd derives
# the requester from the FILE OWNER, so the writer must be the bdrive
# uid. The setgid bit forces the group to bdrive so swapd/confirmd
# (member of bdrive) can read and move them. obox can never file here.
for d in /home/swapd/approvals /home/swapd/approvals/pending \
         /home/swapd/approvals/answered /home/swapd/approvals/consumed; do
    sudo install -d -o swapd -g bdrive -m 2770 "$d"
done

# --- 4. install the daemon and CLI ----------------------------------
sudo install -o root -g root -m 0755 browser-driver/bdrived.py \
    /usr/local/bin/bdrived
sudo install -o root -g root -m 0644 browser-driver/driver.py \
    /usr/local/bin/driver.py
sudo install -o root -g root -m 0755 browser-driver/bdrive \
    /usr/local/bin/bdrive
sudo install -o root -g root -m 0644 browser-driver/bdrive.service \
    /etc/systemd/system/bdrive.service
# Peer uid override: the unit's default (2000000) is a placeholder.
# The drop-in carries the real mapped agent uid computed above.
sudo mkdir -p /etc/systemd/system/bdrive.service.d
sudo tee /etc/systemd/system/bdrive.service.d/peer.conf >/dev/null \
    <<EOF
[Service]
Environment=BDRIVE_PEER_UIDS=${PEER_UID}
EOF
say "peer uid drop-in written: BDRIVE_PEER_UIDS=${PEER_UID}"

# --- 5. Playwright + Chromium (pinned, reproducible) -----------------
# The daemon runs headless Chromium from a venv owned by bdrive.
PLAYWRIGHT_VERSION="1.62.0"
BROWSERS_PATH="/home/bdrive/.cache/ms-playwright"
say "installing python3-venv (for the bdrive venv)"
sudo apt-get install -y -q python3-venv >/dev/null
if [ ! -x /home/bdrive/venv/bin/python ]; then
    say "creating /home/bdrive/venv"
    sudo python3 -m venv /home/bdrive/venv
    sudo chown -R bdrive:bdrive /home/bdrive/venv
fi
say "installing playwright ${PLAYWRIGHT_VERSION} into the venv"
sudo -u bdrive /home/bdrive/venv/bin/pip install -q \
    "playwright==${PLAYWRIGHT_VERSION}"
# OS-level browser deps need root; the browser itself is downloaded as
# bdrive into its own cache (matching PLAYWRIGHT_BROWSERS_PATH in the
# unit). Split install-deps/install keeps the download out of /root.
say "installing Chromium OS dependencies (apt)"
sudo /home/bdrive/venv/bin/playwright install-deps chromium
sudo install -d -o bdrive -g bdrive -m 0755 \
    /home/bdrive/.cache /home/bdrive/.cache/ms-playwright
say "downloading Chromium as bdrive"
sudo -u bdrive env PLAYWRIGHT_BROWSERS_PATH="${BROWSERS_PATH}" \
    /home/bdrive/venv/bin/playwright install chromium

# --- 6. jail: bind-mount the socket dir, order after bdrive ---------
sudo mkdir -p /etc/systemd/system/systemd-nspawn@jail.service.d
sudo tee /etc/systemd/system/systemd-nspawn@jail.service.d/bdrive.conf \
    >/dev/null <<'EOF'
[Unit]
Wants=bdrive.service
After=bdrive.service
EOF
say "NOTE: jail/build.sh adds Bind=/run/bdrive to the .nspawn config;"

# --- 7. nftables: bdrive's egress is the proxy, nothing else --------
# (finding 10 — a network rule, not a Chromium flag)
if [ -f browser-driver/nftables-bdrive.nft ]; then
    BDRIVE_UID="$(id -u bdrive)"
    sudo sed "s/__BDRIVE_UID__/${BDRIVE_UID}/g" \
        browser-driver/nftables-bdrive.nft \
        > /tmp/nftables-bdrive.nft
    sudo nft -f /tmp/nftables-bdrive.nft
    rm /tmp/nftables-bdrive.nft
    say "nftables bdrive_egress table applied"
fi

sudo systemctl daemon-reload
sudo systemctl enable --now bdrive.service
say "bdrive.service enabled and started; socket: /run/bdrive/bdrive.sock"
say "verify from the jail as the agent: bdrive ping"
say "(only host uid ${PEER_UID} — the mapped jail agent — is accepted;"
say " SO_PEERCRED is the gate, not group membership; obox joins the"
say " peer list in round 9)"
