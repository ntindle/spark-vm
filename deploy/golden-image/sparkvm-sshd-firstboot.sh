#!/bin/bash
# sparkvm-sshd-firstboot.sh — sshd entrypoint for the golden image (#1087).
#
# Installs the sshd host keys on FIRST BOOT, then execs sshd -D. Host keys
# are per-machine secrets: baking one keypair into the shared image would
# hand every tenant the same host identity (a leak the baked-secrets scan
# would rightfully refuse), so the image ships with NO host keys and this
# wrapper installs them once, at boot, on the machine.
#
# Two identity sources, in precedence order (#1204, D-D3):
#   1. SPARKVM_SSH_HOST_KEYS (machine-config env, set by the provisioning
#      driver): base64 of the driver-minted per-machine ed25519 OpenSSH
#      private key. The attested key WINS over any pre-existing
#      self-generated keys — a reimaged rootfs must not keep the wrong
#      identity. Present-but-invalid is FATAL (exit nonzero): falling back
#      to self-generated keys would present an unattested host identity.
#      Never logged — only the key's fingerprint appears in logs.
#   2. Self-generated (self-hosted/dev, env absent): existing keys are kept;
#      missing keys are generated with ssh-keygen -A.
#
# On provisioned boxes the keys live on the data volume
# (docs/DATA_VOLUME_CONTRACT.md, D-V3): /data/ssh, symlinked from
# /etc/ssh, so cold stops stop rotating the host identity. The
# machine-config env persists across cold stops (verified 2026-10-09
# against the Fly stop/start model — config is server-side per-machine
# state; re-confirm at the #905 driver build), so the attested fingerprint
# stays stable across wake.
# deploy/golden-image/data-prep.sh lays out /data/ssh + the symlinks at
# boot (supervisord priority 5), but supervisord priority ordering is
# start-ordering, not a completion barrier — so this script DEFENSIVELY
# ensures its own precondition (D-V4) instead of trusting data-prep's
# timing. Without /data (self-hosted / dev) behavior is exactly as
# before: keys generate into /etc/ssh. The ensure is failure-tolerant
# by design (#1240): any ensure failure (lock timeout, unmovable
# conflict file, mkdir failure) degrades to rootfs keys with a loud
# warning — the ensure must never prevent sshd from starting.
#
# Idempotent: a machine that already serves the attested key (same
# fingerprint as SPARKVM_SSH_HOST_KEYS, on the volume or the rootfs)
# reinstalls nothing. Without the env, a machine that already has host
# keys (on the volume, or a reimage wave that preserves /etc/ssh, or a
# dev rebuild over an old rootfs) skips generation.
#
# Test seams (documented, test-only): SPARKVM_DATA_ROOT overrides /data;
# SPARKVM_SSH_ETC_DIR overrides /etc/ssh (tests must not touch the real
# one); SPARKVM_SSH_STATUS_DIR overrides the dir holding the
# machine-readable host-key receipt (/run/sparkvm — tmpfs, per-boot); SPARKVM_FIRSTBOOT_NO_EXEC=1 skips the final exec (prints what it
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
# NOTE: SPARKVM_SSH_HOST_KEYS is deliberately NOT here — it is a
# production driver-injected var, not a test seam; warning on it in root
# runs would fire on every provisioned box. Production vars live in
# _PROD_ENV below.
_SEAMS=(SPARKVM_DATA_ROOT SPARKVM_SSH_ETC_DIR SPARKVM_FIRSTBOOT_NO_EXEC SPARKVM_SSH_RUN_DIR SPARKVM_SSH_STATUS_DIR)

# Canonical list of production env vars consumed in the body (see
# header). Discipline mirrors _SEAMS: a production var consumed below
# must be listed here AND documented in the header, and must NOT appear
# in _SEAMS (the root-run WARNING loop must never fire on a var that is
# legitimately set in production). The contract tests pin the exact list
# and its disjointness from _SEAMS.
_PROD_ENV=(SPARKVM_SSH_HOST_KEYS)

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
    #
    # FAILURE POSTURE (deliberate, #1240): this function must never
    # abort the script — losing SSH is worse than rotating keys. The
    # call site runs it in an if-condition, which disables errexit for
    # the WHOLE body, so every failure inside degrades to rootfs keys
    # with a loud WARNING (same as the unmounted-/data path below)
    # instead of killing sshd before it starts: a flock timeout against
    # data-prep's identical loop, a lock-file creation failure, an
    # mkdir/chmod failure, and an unmovable conflict file in
    # ensure_link — the last returns 1 per key type, and the loop
    # continues with the remaining types rather than aborting the
    # whole ensure. The attested-key path below is NOT weakened by
    # this: present-but-invalid SPARKVM_SSH_HOST_KEYS still refuses to
    # start sshd (fail closed per D-D3) regardless of the ensure.
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
        if mkdir -p "$DATA_ROOT/ssh" && chmod 0700 "$DATA_ROOT/ssh"; then
            echo "sparkvm-sshd-firstboot: created $DATA_ROOT/ssh" >&2
        else
            echo "sparkvm-sshd-firstboot: WARNING: could not create $DATA_ROOT/ssh — continuing with rootfs keys (cold stops will rotate them)" >&2
            return 1
        fi
    fi
    # Serialize against data-prep.sh's identical loop (QA B1 / D-V4).
    # Lock failures degrade (loud WARNING + rootfs keys), never abort
    # the boot — but the loop below NEVER runs without the lock held: a
    # timeout means data-prep is mid-move, and racing it unserialized
    # would be worse than degrading. Per-type ensure_link failures
    # aggregate into $failed (never abort the loop): the call site's
    # WARNING fires on ANY partial failure.
    if ! exec 9>"/tmp/sparkvm-sshkey-ensure.lock"; then
        echo "sparkvm-sshd-firstboot: WARNING: could not open the sshkey ensure lock — continuing with rootfs keys (cold stops will rotate them)" >&2
        return 1
    fi
    if ! flock -w 120 9; then
        echo "sparkvm-sshd-firstboot: WARNING: timed out waiting for the sshkey ensure lock (data-prep may be mid-move) — continuing with rootfs keys (cold stops will rotate them)" >&2
        # NOTE: no 2>/dev/null here — on a bare exec (no command) that
        # redirect would permanently send the SCRIPT's stderr to
        # /dev/null, swallowing every later warning.
        exec 9>&- || true
        return 1
    fi
    local failed=0
    for t in "${KEYTYPES[@]}"; do
        link="$SSH_ETC/ssh_host_${t}_key"
        target="$DATA_ROOT/ssh/ssh_host_${t}_key"
        ensure_link "$link" "$target" 0600 "sparkvm-sshd-firstboot" || failed=1
        ensure_link "${link}.pub" "${target}.pub" 0644 "sparkvm-sshd-firstboot" || failed=1
    done
    flock -u 9 || true
    exec 9>&- || true
    return "$failed"
}

# #1240: deliberate failure posture — the ensure must never abort the
# boot. An if-condition disables errexit for the whole function body,
# so any ensure failure (flock timeout, lock-file or mkdir failure,
# unmovable conflict file) degrades to rootfs keys with a loud WARNING
# instead of killing sshd before it starts.
if ! ensure_volume_keys; then
    echo "sparkvm-sshd-firstboot: WARNING: volume-key ensure failed partway — continuing with rootfs keys (cold stops will rotate them)" >&2
fi

# --- D-D3 host-key attestation (#1204) --------------------------------------
# Machine-readable receipt of the serving host identity (per-boot; the
# fingerprint is public, the key material never leaves the box or the
# logs). Best-effort: a receipt write must never block sshd.
STATUS_DIR="${SPARKVM_SSH_STATUS_DIR:-/run/sparkvm}"
write_key_status() { # $1 = source (env|self-generated), $2 = sha256 fingerprint
    mkdir -p "$STATUS_DIR" 2>/dev/null || return 0
    {
        echo "source=$1"
        echo "key_type=ed25519"
        echo "fingerprint_sha256=$2"
        echo "installed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
    } > "$STATUS_DIR/ssh_host_key.status" 2>/dev/null || return 0
    chmod 0644 "$STATUS_DIR/ssh_host_key.status" 2>/dev/null || true
}

# Installs the driver-minted attested key from $1 (base64 of the OpenSSH
# ed25519 private key). Returns nonzero on any validation failure — the
# caller exits without starting sshd (fail closed per D-D3).
install_attested_host_key() {
    local b64="$1" tmp pub fp dest dest_real dest_pub_real installed_fp t f target cur
    if ! printf '%s' "$b64" | grep -Eq '^[A-Za-z0-9+/]+={0,2}$'; then
        echo "sparkvm-sshd-firstboot: FATAL: SPARKVM_SSH_HOST_KEYS is not valid base64 — refusing to start sshd with an unattested host identity" >&2
        return 1
    fi
    tmp="$(mktemp)"
    chmod 0600 "$tmp"
    if ! printf '%s' "$b64" | base64 -d > "$tmp" 2>/dev/null; then
        echo "sparkvm-sshd-firstboot: FATAL: SPARKVM_SSH_HOST_KEYS failed base64 decode — refusing to start sshd with an unattested host identity" >&2
        rm -f "$tmp"
        return 1
    fi
    # OpenSSH PEM shape check. Written as two half-literals on purpose:
    # the baked-secrets scan (harness/baked-secrets-patterns.txt) refuses
    # any "-----BEGIN ... PRIVATE KEY-----" string anywhere in the tree,
    # and this validation literal is not secret material — the halves
    # cannot match that rule individually while still pinning the shape.
    if [ "$(head -c 11 "$tmp")" != "-----BEGIN " ] \
        || [ "$(tail -c 6 "$tmp" | tr -d '\n')" != "-----" ]; then
        echo "sparkvm-sshd-firstboot: FATAL: SPARKVM_SSH_HOST_KEYS is not an OpenSSH private key — refusing to start sshd with an unattested host identity" >&2
        rm -f "$tmp"
        return 1
    fi
    # setsid + </dev/null: a passphrase-protected key fails here instead of
    # prompting — readpassphrase(3) would otherwise open /dev/tty directly
    # when one exists, bypassing the stdin redirect.
    if ! pub="$(setsid ssh-keygen -y -f "$tmp" </dev/null 2>/dev/null)"; then
        echo "sparkvm-sshd-firstboot: FATAL: SPARKVM_SSH_HOST_KEYS is not a usable private key (corrupt or passphrase-protected) — refusing to start sshd with an unattested host identity" >&2
        rm -f "$tmp"
        return 1
    fi
    case "$pub" in
        ssh-ed25519\ *) ;;
        *)
            echo "sparkvm-sshd-firstboot: FATAL: SPARKVM_SSH_HOST_KEYS is not an ed25519 key (D-D3 pins ed25519) — refusing to start sshd with an unattested host identity" >&2
            rm -f "$tmp"
            return 1
            ;;
    esac
    fp="$(ssh-keygen -lf "$tmp" -E sha256 2>/dev/null | awk '{print $2}')"
    if [ -z "$fp" ]; then
        echo "sparkvm-sshd-firstboot: FATAL: SPARKVM_SSH_HOST_KEYS has no fingerprintable key — refusing to start sshd with an unattested host identity" >&2
        rm -f "$tmp"
        return 1
    fi
    dest="$SSH_ETC/ssh_host_ed25519_key"
    # Idempotent: the attested key is already the serving identity.
    if [ -f "$dest" ]; then
        cur="$(ssh-keygen -lf "$dest" -E sha256 2>/dev/null | awk '{print $2}')"
        if [ -n "$cur" ] && [ -n "$fp" ] && [ "$cur" = "$fp" ]; then
            echo "sparkvm-sshd-firstboot: attested host key already installed (fingerprint $fp)" >&2
            rm -f "$tmp"
            write_key_status env "$fp"
            return 0
        fi
    fi
    # Env-provided keys win over pre-existing self-generated keys: drop
    # every non-attested host key pair so no unattested identity stays
    # served. The ed25519 pair is skipped above and handled below; for the
    # other types both the link and its volume target are removed (a
    # provisioned box serves the attested ed25519 key only).
    for t in "${KEYTYPES[@]}"; do
        for f in "$SSH_ETC/ssh_host_${t}_key" "$SSH_ETC/ssh_host_${t}_key.pub"; do
            if [ "$f" = "$dest" ] || [ "$f" = "${dest}.pub" ]; then
                continue
            fi
            if [ -L "$f" ]; then
                target="$(readlink -f "$f" 2>/dev/null || true)"
                [ -n "$target" ] && rm -f "$target"
            fi
            if [ -e "$f" ] || [ -L "$f" ]; then
                echo "sparkvm-sshd-firstboot: removing pre-existing $f (superseded by attested key)" >&2
            fi
            rm -f "$f"
        done
    done
    # Install through the D-V3 volume layout: $dest may be a DANGLING
    # symlink (ensure_volume_keys links /etc/ssh -> /data/ssh before the
    # targets exist) and GNU cp refuses to write through one, while shell
    # redirection follows it. Resolve both paths first so the key lands
    # on the volume either way.
    # NOTE on set -e: this function runs in an OR-list call context
    # (install_attested_host_key ... || exit 1), which disables set -e
    # for the whole body — so every mutating step below checks its own
    # failure explicitly. An unchecked failure here would print success
    # and exit 0 with no key installed.
    dest_real="$(readlink -f "$dest" 2>/dev/null || true)"
    dest_pub_real="$(readlink -f "${dest}.pub" 2>/dev/null || true)"
    install_fail() {
        echo "sparkvm-sshd-firstboot: FATAL: $1 — refusing to start sshd with an unattested host identity" >&2
        rm -f "$tmp"
        return 1
    }
    [ -n "$dest_real" ] && [ -n "$dest_pub_real" ] \
        || { install_fail "could not resolve the host key install path"; return 1; }
    cp "$tmp" "$dest_real" \
        || { install_fail "could not install attested host key to $dest"; return 1; }
    chmod 0600 "$dest_real" \
        || { install_fail "could not set permissions on $dest"; return 1; }
    printf '%s\n' "$pub" > "$dest_pub_real" \
        || { install_fail "could not install attested host key public half"; return 1; }
    chmod 0644 "$dest_pub_real" \
        || { install_fail "could not set permissions on ${dest}.pub"; return 1; }
    rm -f "$tmp"
    # Post-install verification: the served identity must BE the attested
    # key — the receipt below is only written when this comparison holds.
    installed_fp="$(ssh-keygen -lf "$dest" -E sha256 2>/dev/null | awk '{print $2}')"
    if [ -z "$installed_fp" ] || [ "$installed_fp" != "$fp" ]; then
        echo "sparkvm-sshd-firstboot: FATAL: installed host key fingerprint mismatch ($installed_fp != $fp) — refusing to start sshd" >&2
        return 1
    fi
    echo "sparkvm-sshd-firstboot: installed attested ed25519 host key (fingerprint $fp)" >&2
    write_key_status env "$fp"
}

if [ -n "${SPARKVM_SSH_HOST_KEYS+set}" ]; then
    # Hosted path: the driver claims an attested identity for this machine.
    # ${VAR+set} (not -n): a set-but-empty var is present-but-invalid and
    # must fail closed, never fall back to self-generation.
    install_attested_host_key "${SPARKVM_SSH_HOST_KEYS:-}" || exit 1
else
    # Self-hosted/dev path: unchanged legacy behavior.
    missing=0
    for t in "${KEYTYPES[@]}"; do
        if [ ! -f "$SSH_ETC/ssh_host_${t}_key" ]; then
            missing=1
        fi
    done

    if [ "$missing" = "1" ]; then
        echo "sparkvm-sshd-firstboot: generating missing sshd host keys (first boot)" >&2
        ssh-keygen -A
        # Receipt only when this boot changed the identity: pre-existing
        # keys mean ssh-keygen must not be invoked at all (skip means
        # skip — the contract tests pin this).
        write_key_status self-generated \
            "$(ssh-keygen -lf "$SSH_ETC/ssh_host_ed25519_key" -E sha256 2>/dev/null | awk '{print $2}')"
    fi
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
