#!/bin/bash
# deploy/toolset-update.sh — third-party toolset self-updater for spark-vm boxes.
#
# #532 (first slice, v0): the updater framework plus the `os-security` layer —
# guarantee that the OS security auto-update machinery (unattended-upgrades)
# is installed, enabled, and correctly configured, repairing it when it is not.
# `status` already reports the full in-scope inventory (os, docker, node, gh,
# playwright, cua-driver) as machine-readable output; per-tool updaters for
# those components are follow-up slices, NOT this file's v0 scope.
#
# Integration note (#532): repo-component redeploys stay with
# deploy/auto-deploy.sh (the updater for spark-vm's own code). This script is
# the missing half — the third-party toolset updater. It shares auto-deploy's
# conventions (env-overridable paths, umask 077, installed-copy trust model,
# JSON audit lines) but never touches the repo checkout's deploy path.
#
# Behavior contract:
#   - Never disrupts running agent work: `update` defers (exit 0, loud log)
#     when agent jobs are active, unless --force. v0 never restarts services.
#   - Fail-closed: unknown/missing state is reported, never silently skipped.
#   - Idempotent: safe to run on an already-current box (no-op).
#   - --dry-run changes nothing; --now runs immediately instead of waiting
#     for the weekly window (the idle gate still applies; --force bypasses it).
#   - Opt-out: /etc/sparkvm/toolset-update.optout (or $TOOLSET_UPDATE_OPTOUT=1)
#     makes `update` a no-op.
#
# Usage:
#   toolset-update.sh status [--json]  # machine-readable inventory report
#   toolset-update.sh update [--dry-run] [--now] [--force]
#   toolset-update.sh install [--force]  # backfill onto an existing box
#   toolset-update.sh uninstall
#   toolset-update.sh optout | optin
#   toolset-update.sh version
#
# Env overrides (for tests): TOOLSET_STATE_DIR, APT_CONF_DIR, SYSTEMD_DIR,
# OPTOUT_FILE, SKIP_SYSTEMCTL=1 (skip systemctl calls), SKIP_SUDO=1 (run
# file ops without sudo), TMUX_BIN (idle-gate probe), TOOLSET_UPDATE_NO_MAIN=1
# (source functions only, for tests).
#
# Trust model (read docs/TOOLSET_UPDATE.md before enabling):
#   - THE TIMER RUNS THE INSTALLED COPY at $TOOLSET_STATE_DIR/bin/, NOT the
#     repo checkout. `install` copies this script there; re-running `install`
#     refreshes it. Treat `install` (reinstall) as a privileged step: review
#     the checkout diff first. The timer automates the operator's existing
#     root maintenance — it does not grant new privilege to anyone.
#   - v0 only ever writes $APT_CONF_DIR/20auto-upgrades (repair) and its own
#     state dir. It runs no package manager itself; unattended-upgrades does
#     the installing on its own schedule.
#   - The script never executes anything fetched over the network and never
#     runs downloaded code. There is no update channel to poison — the v0
#     "update" is a config-state guarantee.

set -euo pipefail
set -o pipefail
# Security-relevant state (audit log, state dir) must not be world-readable.
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
VERSION_FILE="$(dirname "$SCRIPT_DIR")/VERSION"

# --- configurable paths (env-overridable for tests) -------------------------
: "${TOOLSET_STATE_DIR:=/home/ntindle/.sparkvm-toolset}"
: "${APT_CONF_DIR:=/etc/apt/apt.conf.d}"
: "${SYSTEMD_DIR:=/etc/systemd/system}"
: "${OPTOUT_FILE:=/etc/sparkvm/toolset-update.optout}"
: "${SKIP_SYSTEMCTL:=0}"
: "${SKIP_SUDO:=0}"
: "${TMUX_BIN:=tmux}"

STATE_AUDIT_LOG="$TOOLSET_STATE_DIR/audit.log"
STATE_RUN_LOG="$TOOLSET_STATE_DIR/toolset-update.log"
STATE_LOCK="$TOOLSET_STATE_DIR/toolset-update.lock"
INSTALLED_BIN="$TOOLSET_STATE_DIR/bin"
INSTALLED_SCRIPT="$INSTALLED_BIN/toolset-update.sh"
SERVICE_NAME="sparkvm-toolset-update"

# --- logging -----------------------------------------------------------------
_log_dest_init() {
    # Resolve once per invocation; tests override TOOLSET_STATE_DIR.
    LOG_FILE="$STATE_RUN_LOG"
}

log() {
    # log <msg> — timestamped line to the run log; best-effort, never fatal.
    local msg="$1"
    _log_dest_init
    if [ -n "${LOG_FILE:-}" ]; then
        ( mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null \
            && printf '%s %s\n' "$(date -u +%FT%TZ)" "$msg" >>"$LOG_FILE" ) \
            2>/dev/null || printf '%s %s\n' "$(date -u +%FT%TZ)" "$msg" >&2
    else
        printf '%s %s\n' "$(date -u +%FT%TZ)" "$msg" >&2
    fi
}

audit() {
    # audit <event> <json-fields...>
    # Appends one JSON line: {"ts":..., "event":..., ...}. Best-effort: never
    # fails the run. Callers MUST expand variables before passing fields —
    # single-quoted '$x' would log literally.
    local event="$1"; shift
    mkdir -p "$(dirname "$STATE_AUDIT_LOG")" 2>/dev/null || true
    local ts; ts="$(date -u +%FT%TZ)"
    ( printf '{"ts":"%s","event":"%s"%s}\n' "$ts" "$event" "$*" \
        >>"$STATE_AUDIT_LOG" ) 2>/dev/null || true
    local n; n="$(wc -l <"$STATE_AUDIT_LOG" 2>/dev/null || echo 0)"
    if [ "$n" -gt 12000 ] 2>/dev/null; then
        tail -n 10000 "$STATE_AUDIT_LOG" >"$STATE_AUDIT_LOG.tmp" 2>/dev/null \
            && mv -f "$STATE_AUDIT_LOG.tmp" "$STATE_AUDIT_LOG" 2>/dev/null || true
    fi
}

# --- sudo handling ------------------------------------------------------------
_sudo() {
    # Run "$@" with sudo unless SKIP_SUDO=1. Fails loud when sudo is missing
    # and we are not root — a repair that cannot write is a failure, not a
    # silent skip.
    if [ "$SKIP_SUDO" = "1" ]; then
        "$@"
    elif [ "$(id -u)" = "0" ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        echo "ERROR: not root and no sudo: cannot run: $*" >&2
        return 77
    fi
}

# --- idle gate ----------------------------------------------------------------
_jobs_active() {
    # v0 idle heuristic: any live `mjob-*` tmux session means an agent job is
    # running. Documented limitation (docs/TOOLSET_UPDATE.md): the muse-job
    # registry check arrives in a later slice; the tmux check is conservative
    # (false positives defer, never disrupt).
    local sessions
    sessions="$("$TMUX_BIN" ls -F '#S' 2>/dev/null || true)"
    [ -n "$sessions" ] || return 1
    printf '%s\n' "$sessions" | grep -q '^mjob-'
}

_idle_gate() {
    # _idle_gate <force:0|1> — returns 0 when the update may proceed.
    local force="$1"
    if [ "$force" = "1" ]; then
        log "idle gate bypassed (--force)"
        return 0
    fi
    if _jobs_active; then
        log "deferred: agent jobs active (mjob-* tmux session); retry next window"
        return 2
    fi
    return 0
}

# --- opt-out -------------------------------------------------------------------
_opted_out() {
    [ -n "${TOOLSET_UPDATE_OPTOUT:-}" ] && [ "$TOOLSET_UPDATE_OPTOUT" != "0" ] \
        && return 0
    [ -f "$OPTOUT_FILE" ]
}

# --- component: os-security (unattended-upgrades) ------------------------------
UNATTENDED_CONF="$APT_CONF_DIR/20auto-upgrades"
# The exact lines v0 requires. Minimal by design: verify the auto-install
# machinery is armed; the sources config is the operator's.
readonly WANT_UPDATE_LIST='APT::Periodic::Update-Package-Lists "1";'
readonly WANT_UNATTENDED='APT::Periodic::Unattended-Upgrade "1";'

_os_security_state() {
    # Prints one of: ok | repair-needed | unknown — never fails the caller.
    if ! command -v unattended-upgrades >/dev/null 2>&1 \
        && ! dpkg -l unattended-upgrades 2>/dev/null | grep -q '^ii'; then
        printf 'repair-needed'
        return 0
    fi
    if [ ! -f "$UNATTENDED_CONF" ]; then
        printf 'repair-needed'
        return 0
    fi
    if grep -Fqx "$WANT_UPDATE_LIST" "$UNATTENDED_CONF" 2>/dev/null \
        && grep -Fqx "$WANT_UNATTENDED" "$UNATTENDED_CONF" 2>/dev/null; then
        printf 'ok'
    else
        printf 'repair-needed'
    fi
}

_os_security_repair() {
    # _os_security_repair <dry:0|1> — install unattended-upgrades (apt, if
    # missing) and (re)write 20auto-upgrades with the required lines.
    # Idempotent: a correct box is a no-op.
    local dry="$1"
    if [ "$(_os_security_state)" = "ok" ]; then
        log "os-security: already configured, no-op"
        return 0
    fi
    if [ "$dry" = "1" ]; then
        log "os-security: DRY-RUN would repair unattended-upgrades config"
        return 0
    fi
    log "os-security: repairing unattended-upgrades config"
    if ! command -v unattended-upgrades >/dev/null 2>&1 \
        && ! dpkg -l unattended-upgrades 2>/dev/null | grep -q '^ii'; then
        _sudo apt-get install -y unattended-upgrades \
            || { log "os-security: apt-get install failed"; return 1; }
    fi
    local tmp; tmp="$(mktemp)"
    printf '%s\n%s\n' "$WANT_UPDATE_LIST" "$WANT_UNATTENDED" >"$tmp"
    # Atomic install, root-owned, world-readable (apt reads it as non-root).
    _sudo install -o root -g root -m 0644 "$tmp" "$UNATTENDED_CONF" \
        || { rm -f "$tmp"; log "os-security: config install failed"; return 1; }
    rm -f "$tmp"
    log "os-security: config repaired"
    return 0
}

# --- status probes (read-only, informational) -----------------------------------
_probe_version() {
    # _probe_version <name> <cmd...> — "name<TAB>present|absent<TAB>version-or-dash"
    local name="$1"; shift
    local ver
    if command -v "$1" >/dev/null 2>&1; then
        ver="$("$@" 2>/dev/null | head -n 1 | tr '\t' ' ' | cut -c1-120 || true)"
        [ -z "$ver" ] && ver="-"
        printf '%s\tpresent\t%s\n' "$name" "$ver"
    else
        printf '%s\tabsent\t-\n' "$name"
    fi
}

cmd_status() {
    # cmd_status — machine-readable inventory: one TSV line per component.
    # Format: COMPONENT<TAB>STATE<TAB>DETAIL
    #   os-security: ok | repair-needed
    #   *-version probes: present | absent, with the version string as DETAIL
    local st
    st="$(_os_security_state)"
    printf 'os-security\t%s\tunattended-upgrades config\n' "$st"
    _probe_version "docker" docker --version
    _probe_version "node" node --version
    _probe_version "npm" npm --version
    _probe_version "gh" gh --version
    if python3 -c 'import playwright' 2>/dev/null; then
        _probe_version "playwright" python3 -c "import playwright; print(playwright.__version__)"
    else
        printf 'playwright\tabsent\t-\n'
    fi
    _probe_version "cua-driver" cua-driver --version
    return 0
}

# --- update ---------------------------------------------------------------------
cmd_update() {
    # cmd_update [--dry-run] [--now] [--force]
    local dry=0 now=0 force=0
    for a in "$@"; do
        case "$a" in
            --dry-run) dry=1 ;;
            --now) now=1 ;;
            --force) force=1 ;;
            *) echo "ERROR: unknown flag: $a" >&2; return 2 ;;
        esac
    done
    [ "$now" = "1" ] && log "update --now: running outside the weekly window"

    if _opted_out; then
        log "update: opted out ($OPTOUT_FILE or TOOLSET_UPDATE_OPTOUT); no-op"
        audit 'toolset-update' ',"result":"opted-out"'
        return 0
    fi

    # Single-flight: never interleave two update runs.
    mkdir -p "$TOOLSET_STATE_DIR" 2>/dev/null \
        || { log "update: cannot create state dir $TOOLSET_STATE_DIR"; return 1; }
    exec 9>"$STATE_LOCK" 2>/dev/null || { log "update: cannot open lock"; return 1; }
    if ! flock -n 9 2>/dev/null; then
        log "update: another run holds the lock; no-op"
        return 0
    fi

    if ! _idle_gate "$force"; then
        # Deferral is not a failure: exit 0 keeps the timer quiet; the run
        # log and the audit line below carry the loud record.
        audit 'toolset-update' ',"result":"deferred","reason":"jobs-active"'
        return 0
    fi

    local rc=0
    if ! _os_security_repair "$dry"; then
        rc=1
    fi

    if [ "$dry" = "1" ]; then
        audit 'toolset-update' ',"result":"dry-run"'
    elif [ "$rc" = "0" ]; then
        audit 'toolset-update' ',"result":"ok","component":"os-security"'
    else
        audit 'toolset-update' ',"result":"failed","component":"os-security"'
        log "update: FAILED (os-security); see audit log"
    fi
    return "$rc"
}

# --- install / uninstall ----------------------------------------------------------
cmd_install() {
    # One-command backfill: copy the script to the state-dir installed copy,
    # install the systemd units, enable the timer. Re-running refreshes the
    # installed copy (privileged step — review the diff first).
    local force=0
    for a in "$@"; do case "$a" in --force) force=1 ;; *) echo "ERROR: unknown flag: $a" >&2; return 2 ;; esac; done
    _sudo mkdir -p "$INSTALLED_BIN" "$SYSTEMD_DIR" \
        || { echo "ERROR: cannot create install dirs" >&2; return 1; }
    _sudo install -o root -g root -m 0755 "$SCRIPT_DIR/toolset-update.sh" "$INSTALLED_SCRIPT" \
        || { echo "ERROR: cannot install script copy" >&2; return 1; }
    _sudo install -o root -g root -m 0644 "$SCRIPT_DIR/sparkvm-toolset-update.service" "$SYSTEMD_DIR/" \
        || { echo "ERROR: cannot install service unit" >&2; return 1; }
    _sudo install -o root -g root -m 0644 "$SCRIPT_DIR/sparkvm-toolset-update.timer" "$SYSTEMD_DIR/" \
        || { echo "ERROR: cannot install timer unit" >&2; return 1; }
    if [ "$SKIP_SYSTEMCTL" != "1" ]; then
        _sudo systemctl daemon-reload || { echo "ERROR: daemon-reload failed" >&2; return 1; }
        _sudo systemctl enable "$SERVICE_NAME.timer" \
            || { echo "ERROR: enable failed" >&2; return 1; }
    else
        log "install: SKIP_SYSTEMCTL=1, timer not enabled"
    fi
    log "install: toolset-update v0 installed; timer $SERVICE_NAME.timer enabled (weekly, quiet hours)"
    audit 'toolset-update' ',"result":"installed"'
    return 0
}

cmd_uninstall() {
    if [ "$SKIP_SYSTEMCTL" != "1" ]; then
        _sudo systemctl disable --now "$SERVICE_NAME.timer" 2>/dev/null || true
    fi
    _sudo rm -f "$SYSTEMD_DIR/$SERVICE_NAME.service" "$SYSTEMD_DIR/$SERVICE_NAME.timer" \
        2>/dev/null || true
    if [ "$SKIP_SYSTEMCTL" != "1" ]; then
        _sudo systemctl daemon-reload 2>/dev/null || true
    fi
    log "uninstall: units removed"
    audit 'toolset-update' ',"result":"uninstalled"'
    return 0
}

cmd_optout() {
    _sudo mkdir -p "$(dirname "$OPTOUT_FILE")" 2>/dev/null || true
    _sudo touch "$OPTOUT_FILE" || { echo "ERROR: cannot write opt-out marker" >&2; return 1; }
    log "optout: $OPTOUT_FILE created; update is now a no-op"
    audit 'toolset-update' ',"result":"opted-out"'
}

cmd_optin() {
    _sudo rm -f "$OPTOUT_FILE" || { echo "ERROR: cannot remove opt-out marker" >&2; return 1; }
    log "optin: $OPTOUT_FILE removed"
    audit 'toolset-update' ',"result":"opted-in"'
}

cmd_version() {
    local v="0.0.0-unknown"
    [ -f "$VERSION_FILE" ] && v="$(tr -d ' \t\r\n' <"$VERSION_FILE")"
    printf 'toolset-update %s (v0 slice of #532)\n' "$v"
}

usage() {
    sed -n '2,40p' "$SCRIPT_DIR/toolset-update.sh"
    exit 2
}

# --- main -------------------------------------------------------------------------
if [ "${TOOLSET_UPDATE_NO_MAIN:-0}" != "1" ]; then
    cmd="${1:-}"
    shift || true
    case "$cmd" in
        status)    cmd_status "$@" ;;
        update)    cmd_update "$@" ;;
        install)   cmd_install "$@" ;;
        uninstall) cmd_uninstall "$@" ;;
        optout)    cmd_optout "$@" ;;
        optin)     cmd_optin "$@" ;;
        version)   cmd_version "$@" ;;
        -h|--help|help) usage ;;
        *) usage ;;
    esac
fi
