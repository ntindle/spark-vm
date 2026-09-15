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
# Run on the host as ntindle (passwordless sudo). Re-running is safe:
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
if [ ! -x "$ROOTFS/bin/bash" ]; then
    say "debootstrap noble -> $ROOTFS (a few minutes)"
    $SUDO mkdir -p /var/lib/machines
    $SUDO debootstrap noble "$ROOTFS" http://archive.ubuntu.com/ubuntu/
else
    say "rootfs present, skipping debootstrap"
fi

# ---------------------------------------------------------------- .nspawn config
say ".nspawn config"
$SUDO mkdir -p /etc/systemd/nspawn
$SUDO tee /etc/systemd/nspawn/$MACHINE.nspawn >/dev/null <<EOF
[Exec]
# Guest root is not host root: user namespacing on, tree chowned to the
# mapped range on first boot.
PrivateUsers=yes
PrivateUsersOwnership=auto
# No DNS in the jail: the host proxy resolves. (Build script also
# empties /etc/resolv.conf inside the guest; this stops nspawn from
# copying the host's in.)
ResolvConf=off
Boot=yes

[Network]
VirtualEthernet=yes

[Files]
# Deliberately empty: no host bind mounts. The jail sees no host files.
EOF

# Host-side veth address, assigned each time the container starts.
say "host veth address drop-in"
$SUDO mkdir -p /etc/systemd/system/systemd-nspawn@$MACHINE.service.d
$SUDO tee /etc/systemd/system/systemd-nspawn@$MACHINE.service.d/veth-ip.conf >/dev/null <<EOF
[Service]
ExecStartPost=-/usr/sbin/ip addr add $HOST_VETH_IP/$CIDR dev ve-$MACHINE
ExecStartPost=-/usr/sbin/ip link set ve-$MACHINE up
EOF
$SUDO systemctl daemon-reload

# ---------------------------------------------------------------- firewall
say "jail firewall"
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
        iifname "tailscale0" tcp dport 2222 dnat to 10.99.0.2:22
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
        # No other egress for the jail: no direct internet, no tailnet,
        # no lan. (Runs before ts-forward, so the tailnet accept there
        # cannot re-allow jail traffic.)
        iifname "ve-jail" log prefix "jail-fwd-drop: " drop
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
ExecStart=-/usr/sbin/nft delete table inet jail
ExecStart=/usr/sbin/nft -f /etc/nftables-jail.conf

[Install]
WantedBy=multi-user.target
EOF
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now jail-firewall.service
say "firewall active:"
$SUDO nft list table inet jail | head -8

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
run_guest /bin/bash -c 'cat > /etc/systemd/network/host0.network <<EOF
[Match]
Name=host0
[Network]
Address='"$GUEST_IP/$CIDR"'
Gateway='"$HOST_VETH_IP"'
EOF
systemctl enable systemd-networkd'
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

# ---------------------------------------------------------------- swapd CA inside the jail only
say "swapd CA -> jail trust store"
$SUDO cp /home/swapd/.mitmproxy/mitmproxy-ca-cert.pem /tmp/swapd-mitmproxy.crt
$SUDO chmod 644 /tmp/swapd-mitmproxy.crt
$SUDO cp /tmp/swapd-mitmproxy.crt "$ROOTFS/usr/local/share/ca-certificates/swapd-mitmproxy.crt"
run_guest /usr/sbin/update-ca-certificates >/dev/null
rm -f /tmp/swapd-mitmproxy.crt

# ---------------------------------------------------------------- agent user
say "agent user $JAIL_USER"
PUBKEY="$(cat "$HOME/.ssh/id_ed25519.pub")"
run_guest /bin/bash -c 'id -u '"$JAIL_USER"' >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo '"$JAIL_USER"
echo "'"$JAIL_USER"' ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/'"$JAIL_USER"'
chmod 440 /etc/sudoers.d/'"$JAIL_USER"'
mkdir -p /home/'"$JAIL_USER"'/.ssh
echo "'"$PUBKEY"'" > /home/'"$JAIL_USER"'/.ssh/authorized_keys
chmod 700 /home/'"$JAIL_USER"'/.ssh
chmod 600 /home/'"$JAIL_USER"'/.ssh/authorized_keys
chown -R '"$JAIL_USER:$JAIL_USER"' /home/'"$JAIL_USER"'/.ssh'
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
