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
#   token. `request` classifies its failure: transient plane failures
#   (transport/DNS/TLS/timeout, HTTP 5xx/429) retry in-process with bounded
#   exponential backoff (5 attempts, 1s/2s/4s/8s) so a boot-time plane outage
#   does not wedge the box permanently (#1221); permanent failures (403
#   consumed-token replay, other 4xx, malformed attested response) exit 1
#   immediately. Redeem completion is #907's box-side half — the hook logs
#   the exact command and stops; it never polls for approval inside the
#   boot sequence.
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
# The token must be base64url (enforced at the env gate): the retry path's
# client-output scrub is a ${var//pattern/} substitution, exact only for a
# glob-free token.
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
# The plane-push signal file (#1268): root-owned, world-readable, consumed
# by the swapd push worker (confirm/push.py _image_plane_signal), which
# cannot read the pairing record itself. Written here when the box is
# already enrolled; override the path via SPARKVM_PLANE_PUSH_FILE (the
# same variable the worker consults). A whitespace-only override is as
# good as unset (mirrors the attestation-token gate below).
_signal_file_raw="${SPARKVM_PLANE_PUSH_FILE:-/run/sparkvm/plane-push}"
_signal_file_raw="${_signal_file_raw//[[:space:]]/}"
SIGNAL_FILE="${_signal_file_raw:-/run/sparkvm/plane-push}"
unset _signal_file_raw

log() { echo "$HOOK: $*" >&2; }

# Clear a stale plane-push signal (#1268): the signal is only valid while
# the box is enrolled — any non-enrolled branch must not leave a
# stand-down behind, or a de-enrolled box keeps its box-local paging
# channel stood down with no plane lane to replace it.
clear_plane_signal() {
    if [ -e "$SIGNAL_FILE" ]; then
        rm -f "$SIGNAL_FILE"
        log "cleared stale plane-push signal ($SIGNAL_FILE)"
    fi
}

# --- env gate: fail closed on enrollment, not on boot ------------------------
# A whitespace-only token is as good as absent (base64url has no meaningful
# whitespace; the client strips anyway). Two-step: ${VAR//…/} on an unset
# variable trips `set -u`, so default first, then strip.
_token_stripped="${SPARKVM_ATTESTATION_TOKEN:-}"
_token_stripped="${_token_stripped//[[:space:]]/}"
if [ -z "${SPARKVM_BOX_ID:-}" ] || [ -z "${SPARKVM_PLANE_URL:-}" ] \
    || [ -z "$_token_stripped" ]; then
    log "identity env incomplete (need SPARKVM_BOX_ID, SPARKVM_PLANE_URL, SPARKVM_ATTESTATION_TOKEN) — not enrolling; normal for non-provisioned images"
    # No identity env means this box is not a provisioned plane box — a
    # stale signal must not outlive the enrollment it described.
    clear_plane_signal
    exit 0
fi

# Charset gate: the retry path below scrubs the token out of captured client
# output with a ${var//pattern/} substitution, which is only exact when the
# token holds no glob characters. The token is base64url per #1108 — enforce
# it here and fail closed (loud, nonzero) rather than letting an off-spec
# token silently defeat the scrub and leak to the persisted hook log.
if [[ ! "$SPARKVM_ATTESTATION_TOKEN" =~ ^[A-Za-z0-9_-]+$ ]]; then
    log "attestation token is not base64url — refusing to present or echo it; not enrolled"
    # Not enrolled (the token never gets presented) — no stale stand-down.
    clear_plane_signal
    exit 1
fi

# --- idempotency: the token is single-use; present it at most once -----------
if [ -f "$STATE_DIR/enrollment.json" ]; then
    log "enrollment state present — already enrolled, skipping (token never re-presented)"
    # Plane-push signal (#1268): propagate the #1135 handoff to the image's
    # push worker env. The worker runs as swapd and can never read this
    # root-owned record, so auto-detect always fails open to box-local on
    # the image. Mirror proxy/deploy.sh §5b's systemd drop-in semantics
    # with a root-owned, world-readable boolean the worker reads fresh on
    # every pass (confirm/push.py _image_plane_signal). Re-written at every
    # boot; /run is tmpfs so a stale value cannot survive a reboot. A
    # corrupt record writes nothing — fail-open to box-local, never a
    # planted kill of the box-local channel.
    if "$PYTHON" -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
sys.exit(0 if isinstance(d, dict) and d.get("token") else 1)
' "$STATE_DIR/enrollment.json" 2>/dev/null; then
        # Atomic write: mktemp + chmod + rename replaces a pre-planted
        # symlink/FIFO instead of following it, and closes the
        # create->chmod mode window. The dir mode is pinned (root umask
        # is not a promise).
        _signal_dir="$(dirname "$SIGNAL_FILE")"
        _signal_tmp=""
        if mkdir -p "$_signal_dir" && chmod 0755 "$_signal_dir" \
            && _signal_tmp="$(mktemp "$_signal_dir/.plane-push.XXXXXX")" \
            && printf '1\n' > "$_signal_tmp" \
            && chmod 0644 "$_signal_tmp" \
            && mv -f "$_signal_tmp" "$SIGNAL_FILE"; then
            log "plane-push signal written ($SIGNAL_FILE) — enrolled boxes stand down the box-local push queue"
        else
            [ -n "$_signal_tmp" ] && rm -f "$_signal_tmp"
            log "WARNING: could not write plane-push signal $SIGNAL_FILE — worker falls back to record auto-detect"
        fi
        unset _signal_dir _signal_tmp
    else
        log "enrollment record unreadable or tokenless — not writing plane-push signal; worker fails open to box-local"
        clear_plane_signal
    fi
    exit 0
fi
if [ -f "$STATE_DIR/pairing.json" ]; then
    log "pairing already in flight (pairing.json present) — not re-presenting the attestation token; complete enrollment with: \"$PYTHON\" \"$PAIR_CLIENT\" redeem, then re-run this hook as root to propagate the plane-push signal (#1268)"
    clear_plane_signal
    exit 0
fi

# --- first enroll ------------------------------------------------------------
# Invariant (#1268): past the idempotency block, enrollment.json is absent
# by construction — every exit from here leaves the box unenrolled, so any
# stale signal is cleared up front. The signal exists only when a run
# verified enrollment.json-with-token.
clear_plane_signal
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
# A transient plane failure at boot (transport/DNS/TLS/timeout, HTTP 5xx or
# 429) no longer wedges the box permanently (#1221): retry in-process with
# bounded exponential backoff (5 attempts, 1s/2s/4s/8s), one loud log line
# per attempt. A permanent failure (403 consumed-token replay, other 4xx,
# malformed attested response) exits 1 immediately — retrying a consumed
# single-use token is wrong and would only burn audit log. supervisord's
# autorestart=false still stands: in-process retries are the only retries.
#
# Classification keys on the pairing client's documented error vocabulary:
# _http synthesizes "transport: ..." for network/DNS/TLS failures, and
# cmd_request prefixes every failure line with "http={status}" (so a JSON
# error body can no longer hide a 5xx/429 behind the plane's own text),
# surfaced as "request failed: http={status}: ...". The "failed: 5xx"
# alternative below is retained for older client output shapes.
# Captured output is token-scrubbed before it reaches the log: the client
# never prints the token, but a hostile plane could reflect it inside its
# error payload, and supervisord persists hook stderr to disk. The token is
# base64url (no glob characters), so the // substitution is exact.
_request_attempt=0
_request_max_attempts=5
while :; do
    _request_attempt=$((_request_attempt + 1))
    if _request_out="$(SPARKVM_ATTESTATION_TOKEN="$SPARKVM_ATTESTATION_TOKEN" \
        "$PYTHON" "$PAIR_CLIENT" --dir "$STATE_DIR" --control "$SPARKVM_PLANE_URL" \
        request --name "$SPARKVM_BOX_ID" 2>&1)"; then
        break
    fi
    case "$_request_out" in
        *transport:*|*http=5[0-9][0-9]*|*http=429*|*"failed: 5"[0-9][0-9]*)
            _request_transient=1 ;;
        *)
            _request_transient=0 ;;
    esac
    _request_out_scrubbed="${_request_out//$SPARKVM_ATTESTATION_TOKEN/<redacted>}"
    if [ "$_request_transient" -eq 0 ] \
        || [ "$_request_attempt" -ge "$_request_max_attempts" ]; then
        if [ "$_request_transient" -eq 1 ]; then
            _request_kind="transient, attempts exhausted"
        else
            _request_kind="permanent"
        fi
        log "pairing request failed ($_request_kind, attempt $_request_attempt/$_request_max_attempts) — not enrolled; client said: $_request_out_scrubbed"
        exit 1
    fi
    _request_backoff=$((1 << (_request_attempt - 1)))
    log "pairing request attempt $_request_attempt/$_request_max_attempts failed (transient) — retrying in ${_request_backoff}s; client said: $_request_out_scrubbed"
    sleep "$_request_backoff"
done

log "attestation token presented; complete enrollment with: python3 $PAIR_CLIENT redeem (unattended completion is #907's box-side half)"
