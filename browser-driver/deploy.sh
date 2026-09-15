#!/bin/bash
# Deploy bdrive v1 (round 8) on the spark-vm host.
# Reviewed by Nick; run by Nick:  sudo ./browser-driver/deploy.sh
# (from the repo root). Installs the daemon, CLI, service user,
# socket dir, approvals dirs (finding 50 setgid group), the jail
# bind-mount + ordering, the swapd CA for Chromium (finding 70), and
# the nftables egress rule (finding 10) via a boot-persistent
# oneshot service (finding 71).
set -euo pipefail
cd "$(dirname "$0")/.."

say() { echo "[bdrive-deploy] $*"; }

# --- 1. users and groups -------------------------------------------
if ! id bdrive >/dev/null 2>&1; then
    say "creating user bdrive"
    sudo useradd -r -m -s /usr/sbin/nologin bdrive
fi
# NOTE: there is no bdrive-clients group (review nit 78). The socket
# is 0777 by design and the peer gate is SO_PEERCRED in the daemon,
# so no group is needed: a userns-mapped jail peer can never carry a
# host group anyway.
# The jail's agent reaches the host as a userns-mapped uid: with
# PrivateUsers=<base>:65536 from the .nspawn file, guest uid G appears
# on the host as <base>+G. The agent logs in as the jail's "muse"
# user, so read the map base from the .nspawn file and the guest uid
# from the jail rootfs, then derive the real peer uid.
# (A host user with that numeric uid would NOT help: the connecting
# process is the mapped jail process, and host group membership can
# never apply to it — SO_PEERCRED on the numeric uid is the gate.)
JAIL_ROOTFS="/var/lib/machines/jail"
NSPAWN="/etc/systemd/nspawn/jail.nspawn"
if [ ! -f "${NSPAWN}" ]; then
    say "ERROR: ${NSPAWN} not found;"
    say "build the jail (jail/build.sh) before deploying bdrive."
    exit 1
fi
MAP_BASE="$(awk -F'[=:]' '/^PrivateUsers=/ {print $2}' "${NSPAWN}")"
if [ -z "${MAP_BASE}" ]; then
    say "ERROR: no PrivateUsers= line in ${NSPAWN}."
    exit 1
fi
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
PEER_UID="$((MAP_BASE + GUEST_UID))"
say "jail agent: map base ${MAP_BASE}, guest uid ${GUEST_UID} -> host uid ${PEER_UID}"
# The daemon files approvals into 2770 swapd:bdrive dirs, so it needs
# the bdrive group (its primary group is bdrive, the user's own).
# swapd needs it too, to read/move what bdrive files.
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
sudo install -o root -g root -m 0644 \
    browser-driver/bdrive-firewall.service \
    /etc/systemd/system/bdrive-firewall.service
# Peer uid override: the unit's default is EMPTY (finding 73 — accept
# nobody until configured). The drop-in carries the real mapped agent
# uid computed above.
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

# --- 5b. swapd CA into bdrive's NSS database (finding 70) -----------
# All browser traffic goes through the swap proxy, which MITMs TLS.
# Chromium ignores the system CA store, so the proxy's CA must be in
# the bdrive user's NSS database, or every HTTPS goto fails cert
# verification. Same recipe as SETUP.md's login section.
say "installing libnss3-tools (certutil)"
sudo apt-get install -y -q libnss3-tools >/dev/null
SWAPD_CA="/home/swapd/.mitmproxy/mitmproxy-ca-cert.pem"
NSSDB="sql:/home/bdrive/.pki/nssdb"
if [ ! -f "${SWAPD_CA}" ]; then
    say "ERROR: swap proxy CA not found at ${SWAPD_CA}."
    exit 1
fi
say "adding swapd CA to bdrive's NSS database"
sudo install -d -o bdrive -g bdrive -m 0700 /home/bdrive/.pki/nssdb
sudo -u bdrive certutil -d "${NSSDB}" -N --empty-password 2>/dev/null || true
sudo -u bdrive certutil -d "${NSSDB}" -D -n swapd-ca 2>/dev/null || true
sudo -u bdrive certutil -d "${NSSDB}" -A -t C -n swapd-ca \
    -i "${SWAPD_CA}"
# Deploy-time check: the CA must be listed, or HTTPS through the
# proxy will fail at runtime.
if ! sudo -u bdrive certutil -d "${NSSDB}" -L | grep -q "^swapd-ca "; then
    say "ERROR: swapd-ca not listed in bdrive's NSS database."
    exit 1
fi
say "swapd CA installed and verified in bdrive's NSS database"

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
# (finding 10 — a network rule, not a Chromium flag; finding 71 —
# boot-persistent via bdrive-firewall.service, which destroys the
# table before reloading so re-deploy never duplicates rules.)
if [ -f browser-driver/nftables-bdrive.nft ]; then
    BDRIVE_UID="$(id -u bdrive)"
    sudo sed "s/__BDRIVE_UID__/${BDRIVE_UID}/g" \
        browser-driver/nftables-bdrive.nft \
        > /etc/nftables-bdrive.conf
    say "nftables bdrive_egress rules installed to /etc/nftables-bdrive.conf"
fi

sudo systemctl daemon-reload
sudo systemctl enable --now bdrive-firewall.service
sudo systemctl enable --now bdrive.service
say "bdrive-firewall.service and bdrive.service enabled and started;"
say "socket: /run/bdrive/bdrive.sock"
say "verify from the jail as the agent: bdrive ping"
say "(only host uid ${PEER_UID} — the mapped jail agent — is accepted;"
say " SO_PEERCRED is the gate, not group membership; obox joins the"
say " peer list in round 9)"
