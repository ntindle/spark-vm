#!/bin/bash
# sparkvm-sshd-firstboot.sh — sshd entrypoint for the golden image (#1087).
#
# Generates the sshd host keys on FIRST BOOT when they are missing, then
# execs sshd -D. Host keys are per-machine secrets: baking one keypair into
# the shared image would hand every tenant the same host identity (a leak
# the baked-secrets scan would rightfully refuse), so the image ships with
# NO host keys and this wrapper creates them once, at boot, on the machine's
# own (ephemeral) rootfs.
#
# Idempotent: a machine that already has host keys (e.g. a reimage wave that
# preserves /etc/ssh, or a dev rebuild over an old rootfs) skips generation.
set -euo pipefail

KEYTYPES=(rsa ecdsa ed25519)
missing=0
for t in "${KEYTYPES[@]}"; do
    if [ ! -f "/etc/ssh/ssh_host_${t}_key" ]; then
        missing=1
    fi
done

if [ "$missing" = "1" ]; then
    echo "sparkvm-sshd-firstboot: generating missing sshd host keys (first boot)" >&2
    ssh-keygen -A
fi

# /run is a fresh tmpfs on most runtimes — the build-time /run/sshd may not
# survive. sshd refuses to start without it, and the box would lose SSH.
mkdir -p /run/sshd

exec /usr/sbin/sshd -D -e
