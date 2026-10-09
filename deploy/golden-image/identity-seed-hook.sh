#!/bin/bash
# identity-seed-hook.sh — first-boot identity-seeding hook for the golden image (#1203).
#
# Reads the provision-time identity from machine-config env (D-D6,
# docs/FLY_DRIVER_DESIGN_AHEAD.md):
#   SPARKVM_BOX_ID            the provisioned box identity (opaque to the driver)
#   SPARKVM_PLANE_URL         control-plane base URL
#   SPARKVM_ATTESTATION_TOKEN G51.3's single-use pairing attestation token
#                             (opaque to the box; 256-bit random, base64url,
#                             format per #1108)
#
# Contract (G51.4, docs/BOX_PROVISIONING_GAP_ANALYSIS.md):
# - Absent vars (any of the three missing/empty) -> no enroll, loud log,
#   exit 0. The same image serves self-hosted/dev use without these vars, so
#   fail-closed means "never enrolls, never invents an identity", not
#   "refuses to boot".
# - Idempotent: enrollment.json present -> skip, the token is never
#   re-presented. pairing.json present (a pairing is in flight from a
#   previous boot) -> skip as well: the token was already consumed
#   plane-side and re-presenting would 403 + audit (per #1108). Loud log
#   naming the manual `redeem` step in both cases.
# - On a true first enroll: run the pairing client `init` (keygen, skipped
#   when a keypair already exists) then `request` presenting the attestation
#   token. Redeem completion is #907's box-side half — the hook logs the
#   exact command and stops; it never polls for approval inside the boot
#   sequence.
#
# Cold-stop note (arch 2026-10-09, #1203): pairing state lives in
# SVM_PAIR_DIR (default ~/.config/spark-pair of the hook's user). On an
# ephemeral-rootfs machine without a persisted state dir (#1205's /data
# contract, still open), a cold stop wipes the state and the next boot
# presents the token again; the plane 403s the replay (consumed token, per
# #1108) and the hook logs loudly instead of retry-looping. Persisted state
# (#1205) is what makes cold stops skip cleanly — this hook does not invent
# that persistence.
#
# Security: the attestation token reaches the pairing client via the
# SPARKVM_ATTESTATION_TOKEN environment variable only — never on argv (argv
# is world-readable via ps; environ is owner-readable). The token is never
# echoed, logged, or included in diagnostics. No `set -x` anywhere near it.
#
# Trust boundary note: SPARKVM_PAIR_CLIENT / SPARKVM_PYTHON override which
# code runs as root at boot — but only to whoever can already set
# machine-config env, which is boot-time root-equivalent by itself. The
# trust boundary is inherited from the provision path, not widened here;
# do not "harden" this layer while leaving machine-config env writable.
set -euo pipefail

HOOK="identity-seed-hook"
PAIR_CLIENT="${SPARKVM_PAIR_CLIENT:-/opt/sparkvm/pairing/spark_pair.py}"
# Mirrors the pairing client's own default (~/.config/spark-pair); /root is
# the fallback because supervisord children are not guaranteed a HOME.
STATE_DIR="${SVM_PAIR_DIR:-${HOME:-/root}/.config/spark-pair}"
PYTHON="${SPARKVM_PYTHON:-/usr/bin/python3}"

log() { echo "$HOOK: $*" >&2; }

# --- env gate: fail closed on enrollment, not on boot ------------------------
# A whitespace-only token is as good as absent (base64url has no meaningful
# whitespace; the client strips anyway). Two-step: ${VAR//…/} on an unset
# variable trips `set -u`, so default first, then strip.
_token_stripped="${SPARKVM_ATTESTATION_TOKEN:-}"
_token_stripped="${_token_stripped//[[:space:]]/}"
if [ -z "${SPARKVM_BOX_ID:-}" ] || [ -z "${SPARKVM_PLANE_URL:-}" ] \
    || [ -z "$_token_stripped" ]; then
    log "identity env incomplete (need SPARKVM_BOX_ID, SPARKVM_PLANE_URL, SPARKVM_ATTESTATION_TOKEN) — not enrolling; normal for non-provisioned images"
    exit 0
fi

# --- idempotency: the token is single-use; present it at most once -----------
if [ -f "$STATE_DIR/enrollment.json" ]; then
    log "enrollment state present — already enrolled, skipping (token never re-presented)"
    exit 0
fi
if [ -f "$STATE_DIR/pairing.json" ]; then
    log "pairing already in flight (pairing.json present) — not re-presenting the attestation token; complete enrollment with: \"$PYTHON\" \"$PAIR_CLIENT\" redeem"
    exit 0
fi

# --- first enroll ------------------------------------------------------------
log "identity env present — enrolling box via attested pairing"

# A keypair is usable only when BOTH halves exist: a previous init that died
# between the two writes leaves an orphan box.key that request cannot use
# (and init would refuse to replace without --force). --force is safe here:
# a key without its pub can never have completed a pairing, so nothing was
# ever presented with it.
if [ ! -f "$STATE_DIR/box.key" ] || [ ! -f "$STATE_DIR/box.pub" ]; then
    # Least privilege: init has no use for the attestation token, so scope
    # it out of the child's environment (a future traceback or diagnostic
    # dumping environ must not see the single-use token).
    env -u SPARKVM_ATTESTATION_TOKEN \
        "$PYTHON" "$PAIR_CLIENT" --dir "$STATE_DIR" --control "$SPARKVM_PLANE_URL" init --force \
        || { log "pairing init failed — not enrolled"; exit 1; }
fi

# The token travels in the child's environment only — never on argv.
SPARKVM_ATTESTATION_TOKEN="$SPARKVM_ATTESTATION_TOKEN" \
"$PYTHON" "$PAIR_CLIENT" --dir "$STATE_DIR" --control "$SPARKVM_PLANE_URL" \
    request --name "$SPARKVM_BOX_ID" \
    || { log "pairing request failed — not enrolled"; exit 1; }

log "attestation token presented; complete enrollment with: python3 $PAIR_CLIENT redeem (unattended completion is #907's box-side half)"
