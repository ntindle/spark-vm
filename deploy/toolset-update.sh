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
#     when agent jobs are active, unless --force. The apt layer may trigger
#     maintainer-script service restarts (e.g. dockerd); the idle gate plus
#     the weekly quiet-hours window bound that surface (see
#     docs/TOOLSET_UPDATE.md).
#   - Fail-closed: unknown/missing state is reported, never silently skipped.
#   - Idempotent: safe to run on an already-current box (no-op).
#   - --dry-run changes nothing. --now is informational-only in v0: the
#     timer owns the weekly schedule; the flag only logs that the operator
#     asked for an immediate run (the idle gate still applies unless
#     --force).
#   - Opt-out: /etc/sparkvm/toolset-update.optout (or $TOOLSET_UPDATE_OPTOUT=1)
#     makes `update` a no-op.
#
# Usage:
#   toolset-update.sh status  # machine-readable TSV inventory report
#   toolset-update.sh update [--dry-run] [--now] [--force]
#   toolset-update.sh install  # backfill onto an existing box
#   toolset-update.sh uninstall
#   toolset-update.sh optout | optin
#   toolset-update.sh version
#
# Update layers (run in order by `update`):
#   os-security  — unattended-upgrades presence + 20auto-upgrades config (v0)
#   cua-driver   — hold the cua-driver binary on the pins.conf pin: compare
#                  `cua-driver --version` against the pin and reinstall the
#                  pinned binary from the upstream release when drifted or
#                  absent. The tarball is SHA256-verified against the
#                  release's checksums.txt before install. Never restarts the
#                  CUA daemon — the new binary takes effect at the next
#                  daemon restart, which the updater does not perform.
#   apt          — converge the toolset's apt packages (docker, node, gh): the
#                  installed packages among the APT_*_PKGS candidate lists
#                  are upgraded with `apt-get install --only-upgrade` (-y,
#                  noninteractive, conffile keep-local). Never a bare
#                  `apt upgrade` — only the allowlisted names are passed, so
#                  unrelated and held packages are untouched. `--only-upgrade`
#                  never installs a missing package, so an absent tool stays
#                  absent. List freshness comes from the os-security layer's
#                  daily refresh — this layer never runs `apt-get update`
#                  itself. Maintainer-script service restarts (e.g.
#                  docker-ce's dockerd restart) can occur, so the layer runs
#                  only behind the idle gate in the weekly quiet-hours window.
#
# Env overrides (for tests): TOOLSET_STATE_DIR, APT_CONF_DIR, SYSTEMD_DIR,
# OPTOUT_FILE, SKIP_SYSTEMCTL=1 (skip systemctl calls), SKIP_SUDO=1 (run
# file ops without sudo), TMUX_BIN (idle-gate probe), TOOLSET_UPDATE_NO_MAIN=1
# (source functions only, for tests), TOOLSET_INSTALL_OWNER/GROUP (owner for
# installed files; default root — tests run non-root, e.g. CI, set these to
# the current uid/gid since `install -o root` requires privilege),
# APT_DOCKER_PKGS / APT_NODE_PKGS / APT_GH_PKGS (space-separated candidate
# package names per tool; tests override to fixture packages).
# PINS_FILE (pin file; default $TOOLSET_STATE_DIR/self_update_pins.conf —
# refreshed only by the privileged `install` step, never read from the live
# checkout), CUA_DRIVER_BIN (default /home/ntindle/cua/bin/cua-driver),
# CUA_DRIVER_OWNER/GROUP (default ntindle — the daemon runs as ntindle, not
# root), CUA_RELEASE_BASE (release download base; tests point it at a local
# dir).
#
# Trust model (read docs/TOOLSET_UPDATE.md before enabling):
#   - THE TIMER RUNS THE INSTALLED COPY at $TOOLSET_STATE_DIR/bin/, NOT the
#     repo checkout. `install` copies this script there; re-running `install`
#     refreshes it. Treat `install` (reinstall) as a privileged step: review
#     the checkout diff first. The timer automates the operator's existing
#     root maintenance — it does not grant new privilege to anyone.
#   - The script runs apt-get itself ONLY in the `apt` layer (`install
#     --only-upgrade` on the allowlisted, already-installed packages, from
#     the box's configured, signature-verified apt sources). All other
#     package installation remains the unattended-upgrades pipeline the
#     os-security layer arms.
#   - The script executes no code fetched over the network and has no bespoke
#     update channel to poison — EXCEPT the cua-driver layer, which downloads
#     the pinned release tarball from github.com/trycua/cua and SHA256-verifies
#     it against the release's checksums.txt before installing (the version it
#     may install is bounded by the operator-owned pins file; the tarball is
#     never executed and never extracted wholesale — only a single member
#     named `cua-driver` is extracted, after the member list is screened for
#     unsafe entries (symlinks/hardlinks/devices, `..`, absolute paths)). The
#     one-time `apt-get install -y
#     unattended-upgrades` bootstrap uses the box's configured,
#     signature-verified apt sources.

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
: "${TOOLSET_INSTALL_OWNER:=root}"
: "${TOOLSET_INSTALL_GROUP:=root}"
# Pin file: read from the installed/backfilled copy refreshed only by the
# privileged `install` step — never from the live repo checkout (see
# docs/SELF_UPDATE.md "Two planes" contract).
: "${PINS_FILE:=$TOOLSET_STATE_DIR/self_update_pins.conf}"
: "${CUA_DRIVER_BIN:=/home/ntindle/cua/bin/cua-driver}"
: "${CUA_DRIVER_OWNER:=ntindle}"
: "${CUA_DRIVER_GROUP:=ntindle}"
: "${CUA_RELEASE_BASE:=https://github.com/trycua/cua/releases/download}"

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
    # Prints one of: ok | repair-needed — never fails the caller.
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
    local tmp newf
    tmp="$(mktemp)"
    newf="$APT_CONF_DIR/.20auto-upgrades.new.$$"
    printf '%s\n%s\n' "$WANT_UPDATE_LIST" "$WANT_UNATTENDED" >"$tmp"
    # Atomic publish: stage with correct ownership/mode, then rename so
    # readers never see a half-written 20auto-upgrades.
    _sudo install -o "$TOOLSET_INSTALL_OWNER" -g "$TOOLSET_INSTALL_GROUP" -m 0644 "$tmp" "$newf" \
        || { rm -f "$tmp" "$newf"; log "os-security: config stage failed"; return 1; }
    rm -f "$tmp"
    _sudo mv -f "$newf" "$UNATTENDED_CONF" \
        || { _sudo rm -f "$newf"; log "os-security: config publish failed"; return 1; }
    log "os-security: config repaired"
    return 0
}

# --- component: cua-driver (pinned binary reinstall) ---------------------------
# Holds the cua-driver binary on the pins.conf pin (#532): compare the
# MANAGED binary's `$CUA_DRIVER_BIN --version` against the pin (PATH is
# never consulted — the timer runs as root, and the layer converges
# $CUA_DRIVER_BIN, so only the managed binary is a meaningful probe);
# reinstall the pinned release when drifted or absent. Never restarts the CUA
# daemon — the new binary takes effect at the next daemon restart, which the
# updater does not perform.
_read_pin() {
    # _read_pin <tool> — print the pinned version from the pins file, or
    # nothing. Format: one `tool = version` per line; `#` comments and blank
    # lines ignored. First matching tool wins; fail-closed (empty) on a
    # missing/unreadable pins file.
    local tool="$1"
    local pins="${PINS_FILE:-}"
    [ -n "$pins" ] && [ -f "$pins" ] || return 0
    local line name ver
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in \#*|'') continue ;; esac
        case "$line" in *"="*) ;; *) continue ;; esac
        name="$(printf '%s' "$line" | cut -d= -f1 | tr -d ' \t')"
        ver="$(printf '%s' "$line" | cut -d= -f2- | tr -d ' \t')"
        if [ "$name" = "$tool" ] && [ -n "$ver" ]; then
            printf '%s' "$ver"
            return 0
        fi
    done <"$pins"
    return 0
}

_pin_ok() {
    # _pin_ok <pin> — the pin is interpolated into a release URL and a
    # filename, so it must be URL/filename-safe: no separators, no leading
    # dot or dash (blocks .. and absolute paths; / is excluded by the class).
    case "$1" in
        ''|*[!A-Za-z0-9._-]*|-*|.*) return 1 ;;
    esac
    return 0
}

_cua_driver_current() {
    # Print the installed version, or: absent | version-unknown.
    # Probe the MANAGED binary only — never PATH. The timer runs as root,
    # and executing a PATH-resolved binary as root invites PATH hijacking;
    # and the layer converges $CUA_DRIVER_BIN, so probing anything else lets
    # a stray PATH copy mask drift of the managed binary (or substitute for
    # it when the managed binary is absent). Operators point the layer at a
    # different location with CUA_DRIVER_BIN itself.
    local out ver
    [ -n "${CUA_DRIVER_BIN:-}" ] && [ -x "$CUA_DRIVER_BIN" ] \
        || { printf 'absent'; return 0; }
    out="$("$CUA_DRIVER_BIN" --version 2>/dev/null | head -n 1 || true)"
    ver="$(printf '%s' "$out" | grep -oE '[0-9][A-Za-z0-9._-]*' | head -n 1 || true)"
    # A bare number is not a version — demand at least one dot so a stray
    # counter can never compare equal to a real pin.
    case "$ver" in
        *.*) printf '%s' "$ver" ;;
        *) printf 'version-unknown' ;;
    esac
}

_cua_driver_arch() {
    # Map the host to the release asset's platform tag.
    case "$(uname -m)" in
        x86_64) printf 'linux-x86_64' ;;
        aarch64|arm64) printf 'linux-arm64' ;;
        *) return 1 ;;
    esac
}

_cua_driver_layer() {
    # _cua_driver_layer <dry:0|1> — converge cua-driver onto the pins.conf pin.
    # Idempotent: a box already on the pin is a no-op. Fail-closed: missing
    # pin, unsafe pin, unparseable installed version, missing arch asset,
    # download failure, or checksum mismatch all refuse loudly.
    local dry="$1"
    local pin cur arch
    pin="$(_read_pin cua-driver)"
    if [ -z "$pin" ]; then
        log "cua-driver: no pin for cua-driver in $PINS_FILE — refusing (fail-closed)"
        return 1
    fi
    if ! _pin_ok "$pin"; then
        log "cua-driver: pin '$pin' is not URL/filename-safe — refusing"
        return 1
    fi
    cur="$(_cua_driver_current)"
    case "$cur" in
        "$pin")
            log "cua-driver: already on pin $pin, no-op"
            return 0 ;;
        version-unknown)
            log "cua-driver: installed but version unparseable — refusing to guess (fail-closed)"
            return 1 ;;
        absent)
            log "cua-driver: absent — installing pin $pin" ;;
        *)
            log "cua-driver: drift $cur -> $pin" ;;
    esac
    if [ "$dry" = "1" ]; then
        log "cua-driver: DRY-RUN would install cua-driver $pin (current: $cur)"
        return 0
    fi
    arch="$(_cua_driver_arch)" \
        || { log "cua-driver: unsupported arch $(uname -m) — no release asset"; return 1; }
    if ! command -v curl >/dev/null 2>&1; then
        log "cua-driver: curl not found — cannot fetch the release tarball"
        return 1
    fi
    local tag asset base work
    tag="cua-driver-rs-v${pin}"
    asset="cua-driver-rs-${pin}-${arch}-binary.tar.gz"
    base="${CUA_RELEASE_BASE%/}"
    work="$(mktemp -d)" || { log "cua-driver: cannot create staging dir"; return 1; }
    # shellcheck disable=SC2064
    trap "rm -rf '$work'" RETURN
    log "cua-driver: fetching $tag/$asset"
    if ! curl -fsSL --max-time 300 -o "$work/checksums.txt" "$base/$tag/checksums.txt"; then
        log "cua-driver: could not fetch checksums.txt for $tag"
        return 1
    fi
    if ! curl -fsSL --max-time 600 -o "$work/$asset" "$base/$tag/$asset"; then
        log "cua-driver: could not fetch $asset"
        return 1
    fi
    # Exact-field match on the expected filename — a prefix/substring match
    # could let a lookalike asset pass against the wrong digest.
    local want
    want="$(awk -v a="$asset" '{ sub(/\r$/, "", $2); if ($2 == a) { print $1; exit } }' "$work/checksums.txt" 2>/dev/null || true)"
    if [ -z "$want" ]; then
        log "cua-driver: $asset not listed in checksums.txt — refusing"
        return 1
    fi
    ( cd "$work" && printf '%s  %s\n' "$want" "$asset" | sha256sum -c - >/dev/null 2>&1 ) \
        || { log "cua-driver: SHA256 mismatch for $asset — refusing"; return 1; }
    # The tarball is never executed, and never extracted wholesale: list its
    # members first and refuse archives with unsafe members. The checksum
    # gate is same-channel (it cannot rule out a tampered release), and a
    # whole-archive `tar -xzf` as root would let a crafted tarball write
    # outside the staging dir (symlink/hardlink/device members, `..` or
    # absolute paths). Only the single wanted member is extracted.
    local members member newbin verbose bad
    members="$(tar -tzf "$work/$asset" 2>/dev/null)" \
        || { log "cua-driver: tarball list failed"; return 1; }
    bad="$(printf '%s\n' "$members" | grep -E '(^|/)\.\.(/|$)|^/' || true)"
    if [ -n "$bad" ]; then
        log "cua-driver: tarball has absolute or dot-dot member paths — refusing"
        return 1
    fi
    # Capture the verbose listing BEFORE grepping it: `tar -tzvf | grep -q`
    # under `set -o pipefail` is racy — grep -q exits on the first match, tar
    # takes SIGPIPE (exit 141), the pipeline reports failure, and an unsafe
    # member would slip through (caught as an intermittent test failure).
    verbose="$(tar -tzvf "$work/$asset" 2>/dev/null)" \
        || { log "cua-driver: tarball list failed"; return 1; }
    bad="$(printf '%s\n' "$verbose" | grep -E '^[^d-]' || true)"
    if [ -n "$bad" ]; then
        log "cua-driver: tarball has non-regular members (symlink/hardlink/device/fifo) — refusing"
        return 1
    fi
    member="$(printf '%s\n' "$members" | grep -E '(^|/)cua-driver$' | head -n 1 || true)"
    if [ -z "$member" ]; then
        log "cua-driver: no cua-driver binary inside $asset — refusing"
        return 1
    fi
    if ! tar -xzf "$work/$asset" -C "$work" -- "$member" 2>/dev/null; then
        log "cua-driver: tarball extract failed"
        return 1
    fi
    newbin="$work/$member"
    if [ ! -f "$newbin" ] || [ -L "$newbin" ]; then
        log "cua-driver: extracted member is not a regular file — refusing"
        return 1
    fi
    # Atomic publish beside the target, preserving the daemon's ownership
    # (ntindle, not root). Unpredictable stage name (mktemp in the target
    # dir, not a $$ suffix) so the stage path can't be pre-planted.
    local stage
    _sudo mkdir -p "$(dirname "$CUA_DRIVER_BIN")" \
        || { log "cua-driver: cannot create $(dirname "$CUA_DRIVER_BIN")"; return 1; }
    stage="$(_sudo mktemp "$(dirname "$CUA_DRIVER_BIN")/cua-driver.new.XXXXXX")" \
        || { log "cua-driver: cannot create stage file"; return 1; }
    _sudo install -o "$CUA_DRIVER_OWNER" -g "$CUA_DRIVER_GROUP" -m 0755 "$newbin" "$stage" \
        || { _sudo rm -f "$stage"; log "cua-driver: stage failed"; return 1; }
    _sudo mv -f "$stage" "$CUA_DRIVER_BIN" \
        || { _sudo rm -f "$stage"; log "cua-driver: publish failed"; return 1; }
    log "cua-driver: installed $pin (was: $cur) — takes effect at next daemon restart"
    return 0
}

# --- component: apt (docker, node, gh) -------------------------------------
# Issue #532: the apt-based half of the default toolset — docker engine +
# compose (apt), node/npm (nodesource), gh (apt). Scope is the
# spark-vm-provisioned defaults only; a box that never provisioned one of
# these tools simply no-ops for it.
: "${APT_DOCKER_PKGS:=docker-ce docker-ce-cli containerd.io docker-compose-plugin docker.io}"
: "${APT_NODE_PKGS:=nodejs}"
: "${APT_GH_PKGS:=gh}"

_apt_toolset_packages() {
    # Print the managed apt packages that are actually installed (one per
    # line), or nothing. Detection is by installed-package presence via
    # `dpkg -l` (status line `ii`), never by probing PATH — the timer runs
    # as root, so executing a PATH-resolved binary to decide what to upgrade
    # would invite PATH hijacking, and the layer converges installed
    # packages, not executables. Candidate names per tool are overridable
    # (APT_DOCKER_PKGS / APT_NODE_PKGS / APT_GH_PKGS) so boxes provisioned
    # from different apt repos (docker.io from Ubuntu vs docker-ce from
    # docker's own repo) are both covered. Fail-closed when dpkg is missing:
    # with no dpkg we cannot know what is installed, so the layer refuses
    # instead of guessing.
    local tool cand p
    command -v dpkg >/dev/null 2>&1 \
        || { log "apt: dpkg not found — cannot inventory installed packages; refusing"; return 1; }
    for tool in docker node gh; do
        case "$tool" in
            docker) cand="${APT_DOCKER_PKGS:-}" ;;
            node)   cand="${APT_NODE_PKGS:-}" ;;
            gh)     cand="${APT_GH_PKGS:-}" ;;
        esac
        # shellcheck disable=SC2086
        for p in $cand; do
            if dpkg -l "$p" 2>/dev/null | grep -q '^ii'; then
                printf '%s\n' "$p"
            fi
        done
    done
    return 0
}

_apt_layer() {
    # _apt_layer <dry:0|1> — converge the toolset's apt packages: the
    # already-installed packages among the APT_*_PKGS candidates are upgraded
    # in place with `apt-get install --only-upgrade`. Idempotent: apt itself
    # no-ops when everything is current, and `--only-upgrade` never installs
    # a package that is not already there, so an absent tool stays absent
    # (scope: provisioned defaults, per #532). Never a bare `apt upgrade` —
    # only the allowlisted package names are passed, so unrelated packages
    # and held packages are untouched.
    #
    # Non-interactive by construction: -y, DEBIAN_FRONTEND=noninteractive,
    # conffile-confdef/confold (keep the box's existing config on conflicts —
    # this runs unattended). Maintainer-script service restarts (e.g.
    # docker-ce's dockerd restart) can occur: the layer runs only behind the
    # idle gate (defer while agent jobs are live) in the weekly quiet-hours
    # window, per the trust model.
    local dry="$1"
    if ! command -v apt-get >/dev/null 2>&1; then
        log "apt: apt-get not found — refusing (fail-closed)"
        return 1
    fi
    local pkgs
    pkgs="$(_apt_toolset_packages)" || return 1
    if [ -z "$pkgs" ]; then
        log "apt: no managed apt packages installed — no-op"
        return 0
    fi
    local count
    count="$(printf '%s\n' "$pkgs" | grep -c .)"
    log "apt: converging $count package(s): $(printf '%s' "$pkgs" | tr '\n' ' ')"
    # List freshness comes from the os-security layer's daily
    # unattended-upgrades refresh — this layer never runs `apt-get update`
    # itself.
    local mode="-y" why="install --only-upgrade"
    if [ "$dry" = "1" ]; then
        mode="-s"
        why="DRY-RUN simulate"
        log "apt: DRY-RUN — simulating the converge"
    fi
    # One call site for both modes, so the trust-model pin
    # (test_script_never_fetches_code) keeps counting exactly two apt-get
    # invocations in the whole script.
    # shellcheck disable=SC2086
    DEBIAN_FRONTEND=noninteractive _sudo apt-get "$mode" install \
        -o Dpkg::Options::="--force-confdef" \
        -o Dpkg::Options::="--force-confold" \
        --only-upgrade $pkgs \
        || { log "apt: $why failed"; return 1; }
    log "apt: converged $count package(s)"
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
    [ "$now" = "1" ] && log "update --now: informational only in v0 (the timer owns the schedule); running now"

    if _opted_out; then
        log "update: opted out ($OPTOUT_FILE or TOOLSET_UPDATE_OPTOUT); no-op"
        audit 'toolset-update' ',"result":"opted-out"'
        return 0
    fi

    # Single-flight: never interleave two update runs.
    mkdir -p "$TOOLSET_STATE_DIR" 2>/dev/null \
        || { log "update: cannot create state dir $TOOLSET_STATE_DIR"; return 1; }
    if ! command -v flock >/dev/null 2>&1; then
        # A missing flock must not degrade into a silent perpetual no-op:
        # fail loud so the timer's failure is visible in the audit log.
        log "update: flock not found; cannot take the single-flight lock"
        audit 'toolset-update' ',"result":"failed","reason":"flock-missing"'
        return 1
    fi
    exec 9>"$STATE_LOCK" 2>/dev/null || { log "update: cannot open lock"; return 1; }
    if ! flock -n 9 2>/dev/null; then
        log "update: another run holds the lock; no-op"
        audit 'toolset-update' ',"result":"deferred","reason":"lock-held"'
        return 0
    fi

    if ! _idle_gate "$force"; then
        # Deferral is not a failure: exit 0 keeps the timer quiet; the run
        # log and the audit line below carry the loud record.
        audit 'toolset-update' ',"result":"deferred","reason":"jobs-active"'
        return 0
    fi

    local rc=0 failed_comps=""
    if ! _os_security_repair "$dry"; then
        rc=1
        failed_comps="os-security"
    fi
    if ! _cua_driver_layer "$dry"; then
        rc=1
        failed_comps="${failed_comps:+$failed_comps }cua-driver"
    fi
    if ! _apt_layer "$dry"; then
        rc=1
        failed_comps="${failed_comps:+$failed_comps }apt"
    fi

    if [ "$dry" = "1" ]; then
        audit 'toolset-update' ',"result":"dry-run"'
    elif [ "$rc" = "0" ]; then
        audit 'toolset-update' ',"result":"ok","components":"os-security cua-driver apt"'
    else
        audit 'toolset-update' ',"result":"failed","failed":"'"$failed_comps"'"'
        log "update: FAILED ($failed_comps); see audit log"
    fi
    return "$rc"
}

# --- install / uninstall ----------------------------------------------------------
cmd_install() {
    # One-command backfill: copy the script to the state-dir installed copy,
    # install the systemd units, enable the timer. Re-running refreshes the
    # installed copy (privileged step — review the diff first).
    # install takes no flags; re-running refreshes the installed copy
    # (privileged step — review the diff first).
    for a in "$@"; do case "$a" in *) echo "ERROR: unknown flag: $a" >&2; return 2 ;; esac; done
    _sudo mkdir -p "$INSTALLED_BIN" "$SYSTEMD_DIR" \
        || { echo "ERROR: cannot create install dirs" >&2; return 1; }
    _sudo install -o "$TOOLSET_INSTALL_OWNER" -g "$TOOLSET_INSTALL_GROUP" -m 0755 "$SCRIPT_DIR/toolset-update.sh" "$INSTALLED_SCRIPT" \
        || { echo "ERROR: cannot install script copy" >&2; return 1; }
    # The pins file is the operator-owned version authority for pinned
    # layers (cua-driver). It is installed/backfilled ONLY here — the update
    # plane never reads it from the live checkout, per the installed-copy
    # trust model (docs/SELF_UPDATE.md "Two planes" contract).
    _sudo install -o "$TOOLSET_INSTALL_OWNER" -g "$TOOLSET_INSTALL_GROUP" -m 0644 "$SCRIPT_DIR/../scripts/self_update_pins.conf" "$TOOLSET_STATE_DIR/self_update_pins.conf" \
        || { echo "ERROR: cannot install pins file" >&2; return 1; }
    _sudo install -o "$TOOLSET_INSTALL_OWNER" -g "$TOOLSET_INSTALL_GROUP" -m 0644 "$SCRIPT_DIR/sparkvm-toolset-update.service" "$SYSTEMD_DIR/" \
        || { echo "ERROR: cannot install service unit" >&2; return 1; }
    _sudo install -o "$TOOLSET_INSTALL_OWNER" -g "$TOOLSET_INSTALL_GROUP" -m 0644 "$SCRIPT_DIR/sparkvm-toolset-update.timer" "$SYSTEMD_DIR/" \
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
    # Print the full header comment (everything up to `set -euo pipefail`).
    sed -n '2,/^set -euo pipefail$/p' "$SCRIPT_DIR/toolset-update.sh" | sed '$d'
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
