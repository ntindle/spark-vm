#!/bin/bash
# jail/build.sh — reproducibly build the agent jail on spark-vm.
#
# The jail is a persistent systemd-nspawn container ("jail") where the
# agent's SSH login lands. Properties (owner decision 2, 2026-09-15):
#   - rootful inside, guest root is NOT host root (PrivateUsers=yes)
#   - its own rootfs at /var/lib/machines/jail, package installs free
#   - veth whose ONLY egress is the swap proxy on the host
#     (10.99.0.1:18080/18081 via DNAT to the host's 127.0.0.1 listener)
#   - no host secrets, swapd state, bdrive state, or audit log inside
#   - agent SSH: jail sshd, reached via tailnet :2222 -> DNAT -> jail :22
#   - swapd CA trusted system-wide INSIDE the jail only
#   - no DNS in the jail (name resolution happens in the host proxy);
#     direct-IP/UDP/ping/git-over-SSH do not work by design
#
# Run on the host as the agent user (passwordless sudo). Re-running is safe:
# the rootfs step is skipped when present (pass --rebuild-rootfs to
# force), everything else is re-applied idempotently.
set -euo pipefail

MACHINE=jail
JAIL_USER=muse
ROOTFS=/var/lib/machines/$MACHINE
HOST_VETH_IP=10.99.0.1
GUEST_IP=10.99.0.2
CIDR=30
JAIL_SSH_PORT=2222          # on the tailnet interface only
REBUILD_ROOTFS=0
for a in "$@"; do [ "$a" = "--rebuild-rootfs" ] && REBUILD_ROOTFS=1; done

SUDO="sudo"
say() { echo "==> $*"; }

# ---------------------------------------------------------------- host packages
say "host packages"
$SUDO apt-get install -y -q systemd-container debootstrap >/dev/null

# ---------------------------------------------------------------- rootfs
if [ "$REBUILD_ROOTFS" = 1 ]; then
    say "removing existing rootfs (--rebuild-rootfs)"
    $SUDO rm -rf "$ROOTFS"
fi
# NOTE: the test must run under sudo — the rootfs is root-owned and not
# traversable by the invoking user, so an unprivileged -x test always
# fails and would re-bootstrap over a good tree.
if ! $SUDO test -x "$ROOTFS/bin/bash"; then
    say "debootstrap noble -> $ROOTFS (a few minutes)"
    $SUDO mkdir -p /var/lib/machines
    $SUDO debootstrap noble "$ROOTFS" http://archive.ubuntu.com/ubuntu/
else
    say "rootfs present, skipping debootstrap"
fi
# Fresh machine-id: debootstrap stamps one; never boot two machines
# with the same id. First boot regenerates it.
$SUDO rm -f "$ROOTFS/etc/machine-id"

# Guest network file, written from the host BEFORE first boot so
# networkd has it when the guest starts. (nspawn's ownership shift
# fixes the host-0 ownership on first boot.) Written again via
# run_guest in the guest-config phase for idempotent re-runs.
$SUDO mkdir -p "$ROOTFS/etc/systemd/network"
$SUDO tee "$ROOTFS/etc/systemd/network/80-container-host0.network" >/dev/null <<EOF
[Match]
Name=host0
[Network]
# Default route via the host veth address: REQUIRED so the guest can
# reply to DNAT'd tailnet SSH (return traffic). Egress is enforced by
# nftables (forward chain drops all iifname ve-jail except established
# and the proxy DNAT), not by the route table.
Address=$GUEST_IP/$CIDR
Gateway=$HOST_VETH_IP
LinkLocalAddressing=no
EOF
$SUDO chmod 644 "$ROOTFS/etc/systemd/network/80-container-host0.network"

# ---------------------------------------------------------------- .nspawn config
say ".nspawn config"
$SUDO mkdir -p /etc/systemd/nspawn
$SUDO tee /etc/systemd/nspawn/$MACHINE.nspawn >/dev/null <<EOF
[Exec]
# User namespacing: guest root is NOT host root. The range is EXPLICIT
# (not "yes"/"pick"): container uid 0 maps to host uid 2000000.
# NOTE: PrivateUsers=yes would read the range from the root dir's owner;
# on a fresh debootstrap that is host uid 0, which yields an IDENTITY map
# (no isolation). An explicit range cannot silently degrade like that.
# Verify with: cat /proc/$(machinectl show jail -p Leader --value)/uid_map
PrivateUsers=2000000:65536
# The guest's hostname (nspawn would otherwise copy the host's).
Hostname=jail
# No DNS in the jail: the host proxy resolves. (Build script also
# empties /etc/resolv.conf inside the guest; this stops nspawn from
# copying the host's in.)
ResolvConf=off
Boot=yes

[Network]
VirtualEthernet=yes

[Files]
# Shift the (host-0-owned) debootstrap tree into the range above on
# first boot; reuse idmapped mounts where the fs supports it.
# NOTE: this key lives in [Files], not [Exec] — nspawn ignores it in
# [Exec] ("Unknown key name"), silently skipping the ownership shift
# and leaving the tree host-root-owned (container root could then
# write host-0-owned files).
PrivateUsersOwnership=auto
# Deliberately no bind mounts: no host files inside the jail.
EOF

# Host-side veth address, assigned each time the container starts.
say "host veth address drop-in"
$SUDO mkdir -p /etc/systemd/system/systemd-nspawn@$MACHINE.service.d
$SUDO tee /etc/systemd/system/systemd-nspawn@$MACHINE.service.d/veth-ip.conf >/dev/null <<EOF
[Service]
ExecStartPost=-/usr/sbin/ip addr add $HOST_VETH_IP/$CIDR dev ve-$MACHINE
ExecStartPost=-/usr/sbin/ip link set ve-$MACHINE up
# Finding 51: route_localnet is needed only on ve-jail (the proxy
# DNATs jail traffic to 127.0.0.1). Setting it on `all` would let any
# same-L2 peer address loopback services; leave all/default at 0.
ExecStartPost=-/usr/sbin/sysctl -w net.ipv4.conf.ve-$MACHINE.route_localnet=1
EOF
$SUDO systemctl daemon-reload

# ---------------------------------------------------------------- firewall
say "jail firewall"
# (route_localnet is set per-interface on ve-jail from the veth
# drop-in above, not globally.)
$SUDO tee /etc/nftables-jail.conf >/dev/null <<'EOF'
# Proxy-only egress for the jail's veth (ve-jail). Evaluated before the
# base filter chains (priority -10 < filter 0), so nothing later can
# re-allow what this drops. Lives in its own table; Docker/Tailscale
# tables are untouched.
table inet jail {
    chain prerouting {
        type nat hook prerouting priority dstnat; policy accept;
        # Jail -> proxy. mitmdump listens on 127.0.0.1:18080/18081 on the
        # host; DNAT the jail's gateway address there so the proxy's own
        # config never changes and is never exposed on a real interface.
        iifname "ve-jail" ip daddr 10.99.0.1 tcp dport { 18080, 18081 } dnat to 127.0.0.1
        # Tailnet -> jail sshd (the agent login). Tailnet interface only.
        # (dnat ip: inet-family tables need the address family explicit.)
        iifname "tailscale0" tcp dport 2222 dnat ip to 10.99.0.2:22
    }
    chain input {
        type filter hook input priority -10; policy accept;
        # DNATed proxy traffic from the jail.
        iifname "ve-jail" tcp dport { 18080, 18081 } accept
        iifname "ve-jail" ct state established,related accept
        # The jail may not touch any other host service (host sshd, ...).
        iifname "ve-jail" log prefix "jail-input-drop: " drop
    }
    chain forward {
        type filter hook forward priority -10; policy accept;
        # Tailnet -> jail sshd, after DNAT.
        iifname "tailscale0" oifname "ve-jail" ip daddr 10.99.0.2 tcp dport 22 ct state new,established accept
        iifname "ve-jail" ct state established,related accept
        oifname "ve-jail" ct state established,related accept
        # No other egress for the jail: no direct internet, no tailnet,
        # no lan. (Runs before ts-forward, so the tailnet accept there
        # cannot re-allow jail traffic.)
        iifname "ve-jail" log prefix "jail-fwd-drop: " drop
        # Nothing may route INTO the jail either, except the sshd DNAT
        # above (and its return traffic).
        oifname "ve-jail" log prefix "jail-fwd-indrop: " drop
    }
}
EOF
$SUDO tee /etc/systemd/system/jail-firewall.service >/dev/null <<'EOF'
[Unit]
Description=Jail egress firewall (proxy-only veth)
Before=systemd-nspawn@jail.service
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=-/usr/sbin/nft destroy table inet jail
ExecStart=/usr/sbin/nft -f /etc/nftables-jail.conf

[Install]
WantedBy=multi-user.target
EOF
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now jail-firewall.service
say "firewall active:"
# (|| true: head closes the pipe early; pipefail would SIGPIPE the script.)
$SUDO nft list table inet jail | head -8 || true

# ---------------------------------------------------------------- start the machine
say "enable + start $MACHINE"
$SUDO machinectl enable $MACHINE >/dev/null 2>&1 || true
if ! $SUDO machinectl show $MACHINE >/dev/null 2>&1; then
    $SUDO machinectl start $MACHINE
fi
# Wait for the guest's systemd to settle.
for i in $(seq 1 30); do
    if $SUDO systemd-run --machine=$MACHINE --wait --pipe /bin/true 2>/dev/null; then
        break
    fi
    sleep 4
done

run_guest() { $SUDO systemd-run --machine=$MACHINE --wait --pipe "$@" ; }

# ---------------------------------------------------------------- guest base config
say "guest base config"
run_guest /bin/bash -c 'echo jail > /etc/hostname'
# Static veth address; no DNS (the host proxy resolves).
# Written as 80-container-host0.network so it SHADOWS systemd's default
# /usr/lib/.../80-container-host0.network by name: same-name files in
# /etc win; a differently-named file would LOSE to it (lexicographic
# order beats directory priority for different names).
run_guest /bin/bash -c 'cat > /etc/systemd/network/80-container-host0.network <<EOF
[Match]
Name=host0
[Network]
# Default route via the host veth: REQUIRED for SSH return traffic
# (DNAT from tailnet); egress is enforced by nftables, not the route table.
Address='"$GUEST_IP/$CIDR"'
Gateway='"$HOST_VETH_IP"'
LinkLocalAddressing=no
EOF
systemctl enable --now systemd-networkd
# networkd may already be running with an older config; restart so the
# file above is actually applied, then wait for the address.
systemctl restart systemd-networkd'
say "waiting for guest address $GUEST_IP"
for i in $(seq 1 30); do
    if run_guest /bin/bash -c 'ip -4 addr show host0 | grep -q '"$GUEST_IP"'' 2>/dev/null; then
        break
    fi
    sleep 2
done
run_guest /bin/bash -c 'ip -4 addr show host0 | grep -q '"$GUEST_IP"'' || {
    echo "guest did not get $GUEST_IP" >&2; exit 1
}
# No DNS by design: empty resolv.conf fails fast instead of hanging.
run_guest /bin/bash -c 'rm -f /etc/resolv.conf; : > /etc/resolv.conf; grep -q 127.0.0.1 /etc/hosts || echo "127.0.0.1 localhost" >> /etc/hosts'

# Proxy env for everything in the jail (the veth gateway DNATs to the
# host proxy). Apt gets its own config below.
run_guest /bin/bash -c 'cat > /etc/profile.d/00-jail-proxy.sh <<EOF
export http_proxy=http://'"$HOST_VETH_IP"':18080
export https_proxy=http://'"$HOST_VETH_IP"':18080
export HTTP_PROXY=http://'"$HOST_VETH_IP"':18080
export HTTPS_PROXY=http://'"$HOST_VETH_IP"':18080
export no_proxy=localhost,127.0.0.1
export NO_PROXY=localhost,127.0.0.1
EOF'
run_guest /bin/bash -c 'cat > /etc/apt/apt.conf.d/00proxy <<EOF
Acquire::http::Proxy "http://'"$HOST_VETH_IP"':18080";
Acquire::https::Proxy "http://'"$HOST_VETH_IP"':18080";
EOF'

# Packages. (http_proxy is exported inline: the jail has no DNS and the
# profile.d script is not loaded by systemd-run.)
say "guest packages (openssh-server, sudo, ca-certificates, curl, git, python3)"
run_guest /usr/bin/env http_proxy=http://$HOST_VETH_IP:18080 https_proxy=http://$HOST_VETH_IP:18080 \
    /usr/bin/apt-get update -qq
run_guest /usr/bin/env http_proxy=http://$HOST_VETH_IP:18080 https_proxy=http://$HOST_VETH_IP:18080 \
    DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get install -y -q \
    openssh-server sudo ca-certificates curl git python3 iproute2 >/dev/null
run_guest /bin/systemctl enable ssh
# sshd hardening: key-only, no root login, only the agent user.
run_guest /bin/bash -c 'cat > /etc/ssh/sshd_config.d/90-jail.conf <<EOF
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
X11Forwarding no
AllowUsers '"$JAIL_USER"'
# Let ~/.ssh/environment set session env (proxy vars for non-interactive
# ssh commands, which do not source /etc/profile.d).
PermitUserEnvironment yes
EOF
passwd -l root'

# ---------------------------------------------------------------- swapd CA inside the jail only
say "swapd CA -> jail trust store"
$SUDO cp /home/swapd/.mitmproxy/mitmproxy-ca-cert.pem /tmp/swapd-mitmproxy.crt
$SUDO chmod 644 /tmp/swapd-mitmproxy.crt
$SUDO cp /tmp/swapd-mitmproxy.crt "$ROOTFS/usr/local/share/ca-certificates/swapd-mitmproxy.crt"
run_guest /usr/sbin/update-ca-certificates >/dev/null
$SUDO rm -f /tmp/swapd-mitmproxy.crt

# ---------------------------------------------------------------- agent user
say "agent user $JAIL_USER"
# The agent's SSH public key. Copy the agent's id_ed25519.pub to this
# path on the host before running (override with PUBKEY_FILE=...).
PUBKEY_FILE="${PUBKEY_FILE:-$HOME/agent-jail.pub}"
PUBKEY="$(cat "$PUBKEY_FILE")"
# All guest-side setup runs inside run_guest (heredoc via stdin, quoted
# so nothing expands on the host; $1/$2 are passed as arguments).
run_guest /bin/bash -s "$JAIL_USER" "$PUBKEY" <<'GUEST_EOF'
set -e
U="$1"
KEY="$2"
id -u "$U" >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo "$U"
echo "$U ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$U"
chmod 440 "/etc/sudoers.d/$U"
mkdir -p "/home/$U/.ssh"
echo "$KEY" > "/home/$U/.ssh/authorized_keys"
chmod 700 "/home/$U/.ssh"
chmod 600 "/home/$U/.ssh/authorized_keys"
chown -R "$U:$U" "/home/$U/.ssh"
# ~/.ssh/environment: proxy vars for every SSH session, including
# non-interactive commands (which skip /etc/profile.d). Requires
# PermitUserEnvironment yes in sshd_config (set above).
cat > "/home/$U/.ssh/environment" <<EOF
https_proxy=http://10.99.0.1:18080
http_proxy=http://10.99.0.1:18080
HTTPS_PROXY=http://10.99.0.1:18080
HTTP_PROXY=http://10.99.0.1:18080
EOF
chmod 600 "/home/$U/.ssh/environment"
chown "$U:$U" "/home/$U/.ssh/environment"
GUEST_EOF
# Guest sshd host keys (generated once, live in the jail rootfs).
run_guest /usr/bin/ssh-keygen -A

# ---------------------------------------------------------------- with-proxy for the jail
say "with-proxy inside the jail"
run_guest /bin/bash -c 'cat > /usr/local/bin/with-proxy <<EOF
#!/bin/bash
# with-proxy — jail edition: route through the host swap proxy.
# Configs may contain hsurr:<name> placeholders; the proxy swaps them
# for real secrets, for allowlisted hosts only.
set -u
CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export http_proxy=http://'"$HOST_VETH_IP"':18080
export https_proxy=http://'"$HOST_VETH_IP"':18080
export HTTP_PROXY=http://'"$HOST_VETH_IP"':18080
export HTTPS_PROXY=http://'"$HOST_VETH_IP"':18080
export REQUESTS_CA="\$CA_BUNDLE"
export REQUESTS_CA_BUNDLE="\$CA_BUNDLE"
export CURL_CA_BUNDLE="\$CA_BUNDLE"
export SSL_CERT_FILE="\$CA_BUNDLE"
export NODE_EXTRA_CA_CERTS="\$CA_BUNDLE"
if [ "\$#" -eq 0 ]; then echo "usage: with-proxy <cmd> [args...]" >&2; exit 2; fi
exec "\$@"
EOF
chmod 755 /usr/local/bin/with-proxy'

say "done. Verify with:  ssh -p 2222 $JAIL_USER@<tailnet-ip>"
say "Then remove the swapd CA from the HOST trust store (see jail/README)."
