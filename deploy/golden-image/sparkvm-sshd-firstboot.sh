#!/bin/bash
# sparkvm-sshd-firstboot.sh — sshd entrypoint for the golden image (#1087).
#
# Generates the sshd host keys on FIRST BOOT when they are missing, then
# execs sshd -D. Host keys are per-machine secrets: baking one keypair into
# the shared image would hand every tenant the same host identity (a leak
# the baked-secrets scan would rightfully refuse), so the image ships with
# NO host keys and this wrapper creates them once, at boot, on the machine.
#
# On provisioned boxes the keys live on the data volume
# (docs/DATA_VOLUME_CONTRACT.md, D-V3): /data/ssh, symlinked from
# /etc/ssh, so cold stops stop rotating the host identity (#1204).
# deploy/golden-image/data-prep.sh lays out /data/ssh + the symlinks at
# boot (supervisord priority 5), but supervisord priority ordering is
# start-ordering, not a completion barrier — so this script DEFENSIVELY
# ensures its own precondition (D-V4) instead of trusting data-prep's
# timing. Without /data (self-hosted / dev) behavior is exactly as
# before: keys generate into /etc/ssh.
#
# Idempotent: a machine that already has host keys (on the volume, or a
# reimage wave that preserves /etc/ssh, or a dev rebuild over an old
# rootfs) skips generation.
#
# Test seams (documented, test-only): SPARKVM_DATA_ROOT overrides /data;
# SPARKVM_SSH_ETC_DIR overrides /etc/ssh (tests must not touch the real
# one); SPARKVM_FIRSTBOOT_NO_EXEC=1 skips the final exec (prints what it
# would exec instead); SPARKVM_SSH_RUN_DIR overrides the dir this script
# creates for sshd's privilege separation (/run/sshd — not writable
# outside root, so the contract tests point it at a tmp dir on CI's
# non-root runner). The canonical seam list is _SEAMS (defined just
# below; the WARNING loop iterates it, so the header doc and the loop
# cannot drift). A seam set in a root run logs a loud WARNING —
# production must never set these (see the trust-boundary note in
# data-prep.sh).
set -euo pipefail

# Canonical list of test seams (see header). The WARNING loop below is
# the single consumer: a seam listed here gets a loud warning in a root
# run; a seam consumed below but not listed here cannot warn.
_SEAMS=(SPARKVM_DATA_ROOT SPARKVM_SSH_ETC_DIR SPARKVM_FIRSTBOOT_NO_EXEC SPARKVM_SSH_RUN_DIR)

# Loud warning when a test seam is active in a root run (see data-prep.sh
# for the rationale: the contract tests run as root where they are
# verified, so the seams stay functional and any production use is
# visible instead of silently ignored).
if [ "${EUID:-$(id -u)}" -eq 0 ]; then
    for _seam in "${_SEAMS[@]}"; do
        if [ -n "${!_seam:-}" ]; then
            echo "sparkvm-sshd-firstboot: WARNING: test seam $_seam is set in a root run" >&2
        fi
    done
    unset _seam
fi

DATA_ROOT="${SPARKVM_DATA_ROOT:-/data}"
SSH_ETC="${SPARKVM_SSH_ETC_DIR:-/etc/ssh}"
KEYTYPES=(rsa ecdsa ed25519)

# ensure_link is the race-safe twin of data-prep.sh's ensure_link —
# identical semantics (Security B2 conflict quarantine, B3
# mispointed-symlink repair, QA B1 flock-serialized critical section);
# only the log tag differs. See data-prep.sh for the full rationale.
ensure_link() { # link target mode tag
    local link="$1" target="$2" mode="$3" tag="$4"
    if [ -e "$link" ] && [ ! -L "$link" ]; then
        if [ -e "$target" ]; then
            local q="${target}.rootfs-conflict-$(date +%s).$$"
            echo "$tag: CONFLICT: $link is a real file but $target already exists on the volume — quarantining the rootfs file at $q, volume wins" >&2
            if mv "$link" "$q.tmp" 2>/dev/null; then
                mv "$q.tmp" "$q" 2>/dev/null || true
                chmod 0600 "$q" 2>/dev/null || true
                if [ "$mode" = "0600" ] && [ -e "${link}.pub" ] && [ ! -L "${link}.pub" ]; then
                    mv "${link}.pub" "$q.pub.tmp" 2>/dev/null && mv "$q.pub.tmp" "$q.pub" 2>/dev/null || true
                fi
            fi
        else
            echo "$tag: moving pre-existing $link onto the volume" >&2
            if mv "$link" "$target" 2>/dev/null; then
                chmod "$mode" "$target" 2>/dev/null || true
            fi
        fi
    fi
    if [ -e "$link" ] && [ ! -L "$link" ]; then
        echo "$tag: $link is a real file and could not be moved onto the volume" >&2
        return 1
    fi
    if [ -L "$link" ]; then
        local cur
        cur="$(readlink "$link")"
        if [ "$cur" != "$target" ]; then
            echo "$tag: WARNING: repairing mispointed symlink $link ($cur -> $target)" >&2
            ln -sfn "$target" "$link"
        fi
    else
        ln -sfn "$target" "$link"
        echo "$tag: linked $link -> $target" >&2
    fi
}

ensure_volume_keys() {
    # D-V4 defensive ensure: /data/ssh exists and the /etc/ssh symlinks
    # point at it. Idempotent — a no-op when data-prep.sh already ran.
    [ -d "$DATA_ROOT" ] || return 0
    # Security B1: not a mount, not durable. Loud warning and fall back
    # to today's rootfs key behavior so sshd still starts — unlike
    # data-prep (which FATALs), this script must never prevent sshd from
    # starting: losing SSH is worse than rotating keys.
    if ! mountpoint -q "$DATA_ROOT"; then
        echo "sparkvm-sshd-firstboot: WARNING: $DATA_ROOT exists but is not a mountpoint — keeping host keys on the rootfs (cold stops will rotate them)" >&2
        return 0
    fi
    if [ ! -d "$DATA_ROOT/ssh" ]; then
        mkdir -p "$DATA_ROOT/ssh"
        chmod 0700 "$DATA_ROOT/ssh"
        echo "sparkvm-sshd-firstboot: created $DATA_ROOT/ssh" >&2
    fi
    # Serialize against data-prep.sh's identical loop (QA B1 / D-V4).
    exec 9>"/tmp/sparkvm-sshkey-ensure.lock"
    flock -w 120 9
    for t in "${KEYTYPES[@]}"; do
        link="$SSH_ETC/ssh_host_${t}_key"
        target="$DATA_ROOT/ssh/ssh_host_${t}_key"
        ensure_link "$link" "$target" 0600 "sparkvm-sshd-firstboot"
        ensure_link "${link}.pub" "${target}.pub" 0644 "sparkvm-sshd-firstboot"
    done
    flock -u 9
    exec 9>&-
}

ensure_volume_keys

missing=0
for t in "${KEYTYPES[@]}"; do
    if [ ! -f "$SSH_ETC/ssh_host_${t}_key" ]; then
        missing=1
    fi
done

if [ "$missing" = "1" ]; then
    echo "sparkvm-sshd-firstboot: generating missing sshd host keys (first boot)" >&2
    ssh-keygen -A
fi

# /run is a fresh tmpfs on most runtimes — the build-time /run/sshd may not
# survive. sshd refuses to start without it, and the box would lose SSH.
# SPARKVM_SSH_RUN_DIR is the test seam (see header); production keeps the
# pinned /run/sshd default.
SSH_RUN_DIR="${SPARKVM_SSH_RUN_DIR:-/run/sshd}"
mkdir -p "$SSH_RUN_DIR"

if [ "${SPARKVM_FIRSTBOOT_NO_EXEC:-0}" = "1" ]; then
    echo "sparkvm-sshd-firstboot: (test seam) would exec /usr/sbin/sshd -D -e" >&2
    exit 0
fi
exec /usr/sbin/sshd -D -e
