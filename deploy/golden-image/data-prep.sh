#!/bin/bash
# data-prep.sh — first-boot /data layout for provisioned boxes (#1205).
#
# The Fly driver mounts an empty volume at /data (research F3); several
# box daemons cannot create their own state parents (confirmd never
# makedirs the audit log's parent; the relay journal fails loud on a
# missing parent by contract), and the ephemeral rootfs must never hold
# durable state. This script lays out the pinned subdirs from
# docs/DATA_VOLUME_CONTRACT.md, then points sshd's host-key paths at
# /data/ssh so cold stops stop rotating the host identity (#1204).
#
# Runs as root under supervisord (priority 5, one-shot, autorestart=false).
# Idempotent: safe to re-run on every boot. Writers that can create their
# own dirs still do — this script only covers parents the writers cannot
# make, plus the sshd key indirection.
#
# /data ABSENT (self-hosted / dev boots) is not an error: exit 0 with a
# loud log line, change nothing. Every in-image default keeps working.
#
# /data PRESENT BUT NOT A MOUNT is FATAL (Security B1): a misconfigured
# mount would silently lay "durable" state on the ephemeral rootfs —
# exactly the failure this script exists to prevent. supervisord's FATAL
# is the visible signal; the box must not boot half-durable.
#
# Test seams (documented, test-only): SPARKVM_DATA_ROOT overrides the
# volume root; SPARKVM_SSH_ETC_DIR overrides /etc/ssh (the link side of
# the host-key indirection — tests must not touch the real /etc/ssh);
# SPARKVM_DATA_PREP_SKIP_CHOWN=1 skips the chown calls (the swapd user
# does not exist on test machines). A seam set in a root run logs a loud
# WARNING — production must never set these (see the trust-boundary note
# below). Without the seam, a chown failure is loud and nonzero, never
# silently skipped.
#
# Trust boundary: machine-config env is root-equivalent in this codebase
# (cf. identity-seed-hook.sh's SPARKVM_PAIR_CLIENT override) — these
# seams do not widen it. They exist so the contract tests can exercise
# this script unprivileged and against fake roots.
set -euo pipefail

# Canonical list of test seams (see header). The WARNING loop below is
# the single consumer: a seam listed here gets a loud warning in a root
# run; a seam consumed below but not listed here cannot warn.
_SEAMS=(SPARKVM_DATA_ROOT SPARKVM_SSH_ETC_DIR SPARKVM_DATA_PREP_SKIP_CHOWN)

# Loud warning when a test seam is active in a root run: production must
# never set these. (Deliberate divergence from "ignore seams as root":
# the contract tests run as root in the loop's own environment, so
# ignoring them would make the suite untestable where it is actually
# verified. The warning makes any production use visible.)
if [ "${EUID:-$(id -u)}" -eq 0 ]; then
    for _seam in "${_SEAMS[@]}"; do
        if [ -n "${!_seam:-}" ]; then
            echo "data-prep: WARNING: test seam $_seam is set in a root run" >&2
        fi
    done
    unset _seam
fi

DATA_ROOT="${SPARKVM_DATA_ROOT:-/data}"
SSH_ETC="${SPARKVM_SSH_ETC_DIR:-/etc/ssh}"

if [ ! -d "$DATA_ROOT" ]; then
    echo "data-prep: no $DATA_ROOT — not a provisioned box, nothing to do" >&2
    exit 0
fi

# Security B1: a directory that is not a mount is the ephemeral rootfs
# wearing a /data costume. Refuse loudly instead of building "durable"
# state on it.
if ! mountpoint -q "$DATA_ROOT"; then
    echo "data-prep: FATAL: $DATA_ROOT exists but is not a mountpoint — refusing to lay out durable state on the ephemeral rootfs" >&2
    exit 1
fi

# subdir -> owner, per docs/DATA_VOLUME_CONTRACT.md inventory.
# pairing/ stays root-owned: the pairing-state ownership decision is
# #1220's (Options A/B); the contract pins the path, not the owner.
# NOTE: the every-boot chown root:root on pairing/ will silently revert a
# future #1220 ownership relaxation — keep this in lockstep with #1220.
mkpair() { # dir owner
    local dir="$DATA_ROOT/$1" owner="$2"
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        echo "data-prep: created $dir" >&2
    fi
    chmod 0700 "$dir"
    if [ "${SPARKVM_DATA_PREP_SKIP_CHOWN:-0}" = "1" ]; then
        echo "data-prep: (test seam) skipping chown $owner $dir" >&2
    else
        chown "$owner:$owner" "$dir"
    fi
}

mkpair pairing root
mkpair approvals swapd
mkpair confirmd swapd
mkpair ssh root

# sshd host-key indirection (D-V3): sshd keeps reading /etc/ssh; the
# symlinks move the bytes onto the volume. ssh-keygen -A and the
# firstboot script's "missing" check both follow symlinks, so this is
# transparent to sparkvm-sshd-firstboot.sh.
#
# RACE NOTE (QA B1): sparkvm-sshd-firstboot.sh runs the same ensure
# concurrently (D-V4 — supervisord priority is start-ordering, not a
# completion barrier). The per-keytype loop below holds an flock around
# its critical section, so the twin's check-then-act cannot interleave
# with ours; the section is milliseconds and contention is one twin
# one-shot at boot. ensure_link is additionally safe without the lock:
# the mv is best-effort, a still-real file fails loud instead of being
# unlinked, and `ln -sfn` only ever replaces a symlink — never a real
# file.
ensure_link() { # link target mode tag
    local link="$1" target="$2" mode="$3" tag="$4"
    if [ -e "$link" ] && [ ! -L "$link" ]; then
        if [ -e "$target" ]; then
            # CONFLICT (Security B2): the volume already holds this file —
            # the volume's attested identity wins. Quarantine the rootfs
            # file loudly; never silently overwrite the pinned identity.
            # The quarantine name is PID-unique so a racing twin cannot
            # collide with it. A .pub next to a quarantined private key
            # belongs to that key — quarantine it together (mode 0600
            # marks the private-key call) so the volume never ends up
            # with a mismatched .pub.
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
            # A real file here (not a symlink): pre-existing rootfs keys —
            # move the bytes onto the volume rather than abandoning the
            # identity. May lose a race with the twin script; the loser
            # carries on (the check below is the authority, not the mv).
            # A moved private key is forced 0600: a 0644 rootfs key would
            # otherwise make sshd refuse to load it (loud SSH outage).
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
    # Security B3: a pre-existing symlink is verified, not trusted. A
    # stale/mispointed symlink (operator error, partial prior run) would
    # otherwise send ssh-keygen's long-lived private key to the wrong
    # place — silent rotation (breaking the #1204 pin) or a
    # world-readable path (key exfiltration). Repair loudly.
    if [ -L "$link" ]; then
        local cur
        cur="$(readlink "$link")"
        if [ "$cur" != "$target" ]; then
            echo "$tag: WARNING: repairing mispointed symlink $link ($cur -> $target)" >&2
            ln -sfn "$target" "$link"
        fi
    else
        # -f can only fire on a symlink the twin created with the
        # identical target (real files are moved/quarantined above) —
        # never on a real key file.
        ln -sfn "$target" "$link"
        echo "$tag: linked $link -> $target" >&2
    fi
}

# Serialize the host-key ensure against the twin script's identical loop
# (QA B1 / D-V4): without this the two one-shots' check-then-act
# interleaves. The critical section is milliseconds; contention is one
# twin one-shot at boot. A wedged holder fails the wait loudly (set -e)
# instead of hanging the boot forever.
exec 9>"/tmp/sparkvm-sshkey-ensure.lock"
flock -w 120 9
for t in rsa ecdsa ed25519; do
    link="$SSH_ETC/ssh_host_${t}_key"
    target="$DATA_ROOT/ssh/ssh_host_${t}_key"
    ensure_link "$link" "$target" 0600 "data-prep"
    # The .pub symlink is created alongside even when the key does
    # not exist yet: ssh-keygen -A derives the .pub path from the
    # /etc/ssh key path (not by resolving the private-key symlink),
    # so without this the public key would land on the ephemeral
    # rootfs. Writing through the dangling symlink creates the
    # target on the volume.
    ensure_link "${link}.pub" "${target}.pub" 0644 "data-prep"
done
flock -u 9
exec 9>&-

echo "data-prep: /data layout ready" >&2
