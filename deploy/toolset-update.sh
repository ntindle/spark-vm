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
#     when agent jobs are active, unless --force. The gate is uid-aware:
#     for every user in $TOOLSET_AGENT_USERS (default: ntindle) it checks
#     that user's own tmux server for live `mjob-*` sessions AND scans
#     their muse-job registry (~/muse-jobs/*/job.json) for non-terminal
#     job records — the registry half survives the muse-job v2 cutover
#     (#228), which moves jobs off tmux. Both probes are read-only. An
#     identity-switch failure defers loudly (fail-closed); a tmux probe
#     that fails for other reasons (missing binary, broken server) reads
#     as no-sessions for that half, with the registry probe as the
#     independent backstop.
#     The apt layer may trigger maintainer-script service restarts (e.g.
#     dockerd); the idle gate plus the weekly quiet-hours window bound
#     that surface (see docs/TOOLSET_UPDATE.md).
#   - Fail-closed: unknown/missing state is reported, never silently skipped.
#   - Idempotent: safe to run on an already-current box (no-op).
#   - --dry-run changes nothing. --now is informational-only in v0: the
#     timer owns the weekly schedule; the flag only logs that the operator
#     asked for an immediate run (the idle gate still applies unless
#     --force).
#   - Opt-out: /etc/sparkvm/toolset-update.optout (or $TOOLSET_UPDATE_OPTOUT=1)
#     makes `update` a no-op.
#   - Failure freeze (#532 Recovery): update runs that FAIL (any layer
#     returns nonzero) increment a consecutive-failure counter in
#     $TOOLSET_STATE_DIR/freeze.state. After 3 consecutive failures
#     (env: TOOLSET_FREEZE_AFTER) the box freezes: `update` refuses to run
#     (exit 1, loud log + audit line) until an operator runs `unfreeze`.
#     Deferrals (idle gate, lock held), --dry-run runs, and opt-outs never
#     touch the counter; a successful run resets it to 0. `update
#     --dry-run` is still permitted while frozen as a diagnostic (it
#     changes nothing and never touches the counter). The freeze state is
#     machine-readable: `status` prints a `freeze` row, so the health
#     report surfaces the single "box needs attention" state instead of
#     churning through failing updates. (Post-update health checks, when
#     they land, feed the same counter.)
#
# Usage:
#   toolset-update.sh status  # machine-readable TSV inventory report
#   toolset-update.sh update [--dry-run] [--now] [--force]
#   toolset-update.sh unfreeze  # clear the failure-freeze state
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
#   playwright   — converge Playwright onto the pins.conf pin (issue #532):
#                  the `playwright` pip package inside the managed venv
#                  ($PLAYWRIGHT_VENV) is held on the exact pin
#                  (`playwright==<pin>`, never a floating upgrade); the
#                  Chromium browser builds (`playwright install chromium`)
#                  and the system libraries converge on every run
#                  (idempotent — `install` skips present builds, the deps
#                  step no-ops when nothing is missing). Venv and browser
#                  work runs as $PLAYWRIGHT_USER so the venv and browser
#                  cache stay user-owned. The system-library step never
#                  executes venv code as root: the missing-package list is
#                  computed as the user (`install-deps --dry-run`,
#                  read-only), each name is validated against the Debian
#                  package-name pattern, and root installs the validated
#                  names with apt-get itself. Fail-closed: missing/unsafe
#                  pin, missing venv, unparseable installed version,
#                  missing browser CLI, or any unexpected --dry-run output
#                  shape all refuse loudly. The pip install and the browser
#                  download are TLS-only without hash pinning (follow-up:
#                  hash-pinned wheel + browser archives).
#
# Env overrides (for tests): TOOLSET_STATE_DIR, APT_CONF_DIR, SYSTEMD_DIR,
# OPTOUT_FILE, SKIP_SYSTEMCTL=1 (skip systemctl calls), SKIP_SUDO=1 (run
# file ops without sudo), TMUX_BIN (tmux binary for the idle-gate probe),
# TOOLSET_AGENT_USERS (space-separated agent uids whose activity blocks
# updates; default ntindle), TOOLSET_UPDATE_NO_MAIN=1 (source functions
# only, for tests), TOOLSET_INSTALL_OWNER/GROUP (owner for installed
# files; default root — tests run non-root, e.g. CI, set these to the
# current uid/gid since `install -o root` requires privilege),
# APT_DOCKER_PKGS / APT_NODE_PKGS / APT_GH_PKGS (space-separated candidate
# package names per tool; tests override to fixture packages).
# TOOLSET_FREEZE_AFTER (consecutive failed update runs before the box
# freezes; default 3).
# PINS_FILE (pin file; default $TOOLSET_STATE_DIR/self_update_pins.conf —
# refreshed only by the privileged `install` step, never read from the live
# checkout), CUA_DRIVER_BIN (default /home/ntindle/cua/bin/cua-driver),
# CUA_DRIVER_OWNER/GROUP (default ntindle — the daemon runs as ntindle, not
# root), CUA_RELEASE_BASE (release download base; tests point it at a local
# dir), PLAYWRIGHT_VENV (managed Playwright venv; default
# /home/ntindle/.venvs/pw), PLAYWRIGHT_USER (owner of that venv and of the
# browser cache; default ntindle).
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
#     playwright layer's `pip install playwright==<pin>` (exact pin, never a
#     floating upgrade, run as the venv-owning user) plus `playwright install
#     chromium` (browser binaries from the Playwright CDN, run as the user)
#     are TLS-only without hash pinning — the documented residual for a
#     follow-up slice; the version the layer may install is bounded by the
#     operator-owned pins file. The system-library step does NOT execute
#     venv code as root: `install-deps --dry-run` (a read-only simulation)
#     runs as the user, root validates each reported package name against
#     the Debian package-name pattern, and root installs the validated
#     names itself from the box's configured, signature-verified apt
#     sources — the same pipeline as the `apt` layer. The version probe
#     (`_playwright_current`) also runs as the user, never as root. The
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
# Agent users whose live jobs block `update` (space-separated). The updater
# runs as root; agent jobs run as these users, on their own tmux servers
# and with their own muse-job registries. Default ntindle when unset; an
# explicitly empty value means "no users" — the gate stays open but says
# so loudly in the run log (operator's explicit choice, not a default).
: "${TOOLSET_AGENT_USERS-ntindle}"
: "${TOOLSET_INSTALL_OWNER:=root}"
: "${TOOLSET_INSTALL_GROUP:=root}"
# Resolve the probe tmux to an absolute path once: the per-user probe
# executes it as another uid, where a PATH-relative name would invite PATH
# hijacking. Falls back to the name itself when unresolvable (the probe
# then degrades to the registry half, documented below).
TMUX_RESOLVED="$(command -v "$TMUX_BIN" 2>/dev/null || printf '%s' "$TMUX_BIN")"
# Pin file: read from the installed/backfilled copy refreshed only by the
# privileged `install` step — never from the live repo checkout (see
# docs/SELF_UPDATE.md "Two planes" contract).
: "${PINS_FILE:=$TOOLSET_STATE_DIR/self_update_pins.conf}"
: "${CUA_DRIVER_BIN:=/home/ntindle/cua/bin/cua-driver}"
: "${CUA_DRIVER_OWNER:=ntindle}"
: "${CUA_DRIVER_GROUP:=ntindle}"
: "${CUA_RELEASE_BASE:=https://github.com/trycua/cua/releases/download}"
# Playwright: the managed venv holding the playwright package, and the user
# that owns it (pip installs and browser installs run as this user, never as
# root — the timer runs as root, and a root-owned venv or browser cache
# would break the agent's own Playwright use).
: "${PLAYWRIGHT_VENV:=/home/ntindle/.venvs/pw}"
: "${PLAYWRIGHT_USER:=ntindle}"

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

_sanitize_log_line() {
    # Strip terminal-injection bytes from a log line: ASCII C0 controls
    # (except tab) and DEL. CR and LF become spaces so one call is one
    # line — a CR would otherwise let a crafted slug overwrite the visible
    # head of the line in a terminal viewer (log forgery). The gate
    # interpolates user-influenced data (user names, job slugs, job states
    # from ~/muse-jobs records) into log lines that land in the journal
    # and the run log; raw ESC/CSI bytes would let a lower-privilege
    # writer inject terminal sequences into a privileged operator's
    # viewer. Pure bash (no external commands): log() must work on minimal
    # PATHs — a missing helper here must never kill the run before the
    # loud audit line.
    # Residual (documented): C1 controls (0x80-0x9F) are NOT stripped —
    # they are UTF-8 continuation bytes too, and telling a lone 0x9B from
    # a valid multibyte sequence needs a decoder, which the pure-bash
    # design rules out. The universal ESC vector is dead; only
    # xterm-in-UTF-8-mode interprets C1, and every other mainstream
    # terminal ignores them.
    local s="$1"
    s="${s//$'\n'/ }"
    s="${s//$'\r'/ }"
    s="${s//[$'\001'-$'\010'$'\013'$'\014'$'\016'-$'\037'$'\177']/}"
    printf '%s' "$s"
}

log() {
    # log <msg> — timestamped line to the run log; best-effort, never fatal.
    local msg="$1"
    msg="$(_sanitize_log_line "$msg")"
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

# --- idle gate (uid-aware, #532) --------------------------------------------------
# The weekly `update` must not restart services (apt maintainer scripts,
# e.g. dockerd) while agent jobs are live. Two independent probes, both
# read-only, OR-ed together — idle only when both are clean for every
# agent user:
#   1. tmux: live `mjob-*` sessions on each agent user's OWN tmux server.
#      tmux sockets are per-uid — probing as root saw only root's server,
#      so the v0 gate never saw any agent jobs at all.
#   2. muse-job registry: ~/muse-jobs/<slug>/job.json records whose state
#      is non-terminal (active/blocked). This is the v2-proof half: when
#      the muse-job v2 cutover (#228) moves jobs off tmux, the registry
#      keeps the same state contract and the gate keeps working.
# The probes never execute user code: tmux is asked only for session names
# (`ls -F '#S'`, no pane content, fixed argv, absolute binary path), and
# job.json records are parsed as JSON data (stdlib parser, never
# executed). Unknown job states are busy — fail-closed against a future
# state the gate does not recognize. A user that does not exist has no
# jobs (skipped, logged). An identity-switch failure defers loudly
# (fail-closed); a tmux probe that fails for other reasons reads as
# no-sessions for that half, with the registry probe as the independent
# backstop.
_user_home() {
    # _user_home <user> — print the user's home dir, or nothing when the
    # user does not exist. The home comes from the system passwd DB
    # (getent), never from env.
    local user="$1" line
    line="$(getent passwd "$user" 2>/dev/null || true)"
    [ -n "$line" ] || return 0
    printf '%s' "$line" | cut -d: -f6
}

_as_user() {
    # _as_user <user> -- cmd... — run a command as <user> for read-only
    # probes. Returns 2 when the identity switch itself is impossible
    # (fail-closed upstream); otherwise the command's own status. Never
    # drops into the user's shell — the command is executed directly, no
    # shell involved. 2 is reserved for the switch-impossible path, so a
    # command that itself exits 2 is reported as 3 and the two are never
    # confused.
    local user="$1"; shift
    [ "${1:-}" = "--" ] && shift
    local me target rc=0
    me="$(id -u 2>/dev/null || true)"
    target="$(id -u "$user" 2>/dev/null || true)"
    if [ -n "$me" ] && [ -n "$target" ] && [ "$me" = "$target" ]; then
        "$@" || rc=$?
        [ "$rc" = "2" ] && rc=3
        return "$rc"
    fi
    if [ "${me:-}" != "0" ]; then
        return 2
    fi
    if command -v runuser >/dev/null 2>&1; then
        runuser -u "$user" -- "$@" || rc=$?
    elif command -v sudo >/dev/null 2>&1; then
        sudo -u "$user" -- "$@" || rc=$?
    else
        return 2
    fi
    [ "$rc" = "2" ] && rc=3
    return "$rc"
}

_tmux_sessions_for_user() {
    # Print the user's tmux session names (one per line), or nothing.
    # Returns 2 when the identity switch itself is impossible (fail-closed
    # upstream). Any other non-zero tmux exit (e.g. "no server running")
    # is the idle state for this probe — the registry probe is the
    # independent backstop for a broken tmux.
    local user="$1"
    local out rc=0
    out="$(_as_user "$user" -- "$TMUX_RESOLVED" ls -F '#S' 2>/dev/null)" || rc=$?
    if [ "$rc" = "2" ]; then
        return 2
    fi
    printf '%s\n' "$out"
    return 0
}

_registry_busy() {
    # _registry_busy <jobsdir> — print one `slug:state` line per live job
    # record in <jobsdir>/*/job.json. Returns 0 when at least one record
    # is non-terminal, 1 when the estate is idle, 2 when the scan itself
    # failed (fail-closed upstream). Non-terminal: active, blocked.
    # Terminal: killed, closed, done. Anything else — missing state,
    # unparseable value, an unrecognized future state — is busy
    # (fail-closed). Read-only: records are parsed as data, never executed.
    # The scan runs as the invoking uid (root under the timer) — the parse
    # is data-only, so no user content executes with privilege; the only
    # output is the busy/idle bit plus slug:state lines in the (sanitized)
    # run log.
    local jobsdir="$1"
    [ -d "$jobsdir" ] || return 1
    if command -v python3 >/dev/null 2>&1; then
        local out rc=0
        out="$(python3 -c '
import json, os, sys
jobsdir = sys.argv[1]
try:
    names = sorted(os.listdir(jobsdir))
except OSError:
    sys.exit(2)
for name in names:
    p = os.path.join(jobsdir, name, "job.json")
    if not os.path.isfile(p):
        continue
    try:
        with open(p) as fh:
            d = json.load(fh)
    except OSError:
        # Vanished between listdir and open (the tmp+rename write pattern
        # means readers never see a torn file) — not evidence of a live job.
        continue
    except ValueError:
        # Unparseable record: fail closed — a corrupt job.json for a live
        # job must never read as idle.
        print("%s:unparseable" % name)
        continue
    state = d.get("state") if isinstance(d, dict) else None
    if state not in ("killed", "closed", "done"):
        print("%s:%s" % (name, state))
' "$jobsdir" 2>/dev/null)" || rc=$?
        if [ "$rc" = "2" ]; then
            return 2
        fi
        if [ -n "$out" ]; then
            printf '%s\n' "$out"
            return 0
        fi
        return 1
    fi
    # No python3: grep fallback — extract every "state" value from each
    # job.json. Busy if ANY value is non-terminal (a nested/history "done"
    # must never mask a live top-level state); a file with no parseable
    # state at all is busy too (fail-closed, matching the python path).
    # Cruder than the JSON parse (first textual match per value) but still
    # read-only. Known residual, fail-OPEN direction: a record with NO
    # top-level state but a nested terminal one ({"a":{"state":"done"}})
    # reads idle here (the nested "done" is all grep can see) while the
    # python path reads busy on state=None — the fallback cannot see JSON
    # structure. The primary python path is fail-closed; this fallback
    # only runs when python3 is absent.
    local d slug states rest first busy=0
    for d in "$jobsdir"/*/; do
        [ -d "$d" ] || continue
        [ -f "${d}job.json" ] || continue
        slug="$(basename "$d")"
        states="$(grep -o '"state"[[:space:]]*:[[:space:]]*"[^"]*"' \
            "${d}job.json" 2>/dev/null | cut -d'"' -f4 || true)"
        # No parseable state at all: fail closed (a corrupt record must
        # never read as idle). NB: command substitution strips trailing
        # newlines, so an empty $states would otherwise vanish here.
        if [ -z "$states" ]; then
            printf '%s:unparseable\n' "$slug"
            busy=1
            continue
        fi
        # Strip the terminal states; whatever survives — a non-terminal
        # value — is busy. (A nested "done" can never mask a live
        # top-level state: ANY non-terminal value defers.)
        rest="$(printf '%s\n' "$states" | grep -Ev '^(killed|closed|done)$' || true)"
        if [ -n "$rest" ]; then
            first="$(printf '%s' "$rest" | grep -v '^$' | head -n 1 || true)"
            printf '%s:%s\n' "$slug" "${first:-unparseable}"
            busy=1
        fi
    done
    [ "$busy" = "1" ] && return 0
    return 1
}

_jobs_active() {
    # UID-aware idle probe (#532): for every user in TOOLSET_AGENT_USERS,
    # check (1) their tmux server for live mjob-* sessions and (2) their
    # muse-job registry for non-terminal job records. Returns 0 (busy)
    # when any user has either; 1 when the whole estate is idle.
    local user home probed=0
    # Split the user list on whitespace WITHOUT pathname expansion: a glob
    # token in the root-set list must fail the allowlist check literally,
    # never expand against the cwd (`read -ra` does not glob).
    local -a users
    IFS=$' \t\n' read -ra users <<< "${TOOLSET_AGENT_USERS:-}" || true
    for user in "${users[@]}"; do
        probed=1
        case "$user" in
            ''|-*|.*|*[!A-Za-z0-9_.-]*)
                log "idle gate: refusing unsafe agent user name: $user"
                return 0 ;;
        esac
        home="$(_user_home "$user")"
        if [ -z "$home" ]; then
            log "idle gate: no such user $user — skipping (no jobs possible)"
            continue
        fi
        # Probe 1: tmux sessions on the user's own server.
        local sessions rc=0
        sessions="$(_tmux_sessions_for_user "$user")" || rc=$?
        if [ "$rc" = "2" ]; then
            log "idle gate: cannot probe tmux as $user — deferring (fail-closed)"
            return 0
        fi
        if printf '%s\n' "$sessions" | grep -q '^mjob-'; then
            log "idle gate: live mjob-* tmux session for $user"
            return 0
        fi
        # Probe 2: muse-job registry (v2-proof: survives the #228 cutover).
        local reg rc2=0
        reg="$(_registry_busy "$home/muse-jobs")" || rc2=$?
        if [ "$rc2" = "2" ]; then
            log "idle gate: cannot scan muse-job registry for $user — deferring (fail-closed)"
            return 0
        fi
        if [ -n "$reg" ]; then
            log "idle gate: live job record(s) for $user: $(printf '%s' "$reg" | tr '\n' ' ')"
            return 0
        fi
    done
    if [ "$probed" = "0" ]; then
        log "idle gate: TOOLSET_AGENT_USERS is empty — no users probed, the gate is open"
    fi
    return 1
}

_idle_gate() {
    # _idle_gate <force:0|1> — returns 0 when the update may proceed.
    local force="$1"
    if [ "$force" = "1" ]; then
        log "idle gate bypassed (--force)"
        return 0
    fi
    if _jobs_active; then
        # _jobs_active already logged which probe saw the live job; this
        # line stays generic.
        log "deferred: agent jobs active; retry next window"
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

# --- component: playwright (pip + browsers + system libs) ---------------------
# Issue #532: converge Playwright onto the pins.conf pin. Three artifacts,
# all version-locked together by the playwright package version:
#   1. the `playwright` pip package inside the managed venv,
#   2. the Chromium browser builds (`playwright install chromium`),
#   3. the system libraries (apt packages).
# The pip package is held on the exact pin; the browsers and the system
# libraries converge on every run (both steps are idempotent — `install`
# skips present builds, and the deps step no-ops when nothing is missing),
# so an on-pin pip package with an emptied browser cache or missing system
# libs still heals.
# The venv and browser cache are owned by $PLAYWRIGHT_USER (the agent user),
# so the pip and browser installs run as that user, never as root: a
# root-installed venv or browser cache would break the agent's own Playwright
# smoke tests. The system-library step never executes venv code as root:
# the missing-package list is computed as the user
# (`install-deps --dry-run`, read-only), each name is validated against the
# Debian package-name pattern, and root installs the validated names with
# apt-get itself (signature-verified sources, same as the `apt` layer).
# Probe the MANAGED venv only — never PATH — for the same PATH-hijacking
# reason as the cua-driver layer (the timer runs as root).
_as_playwright_user() {
    # _as_playwright_user cmd... — run a command as $PLAYWRIGHT_USER.
    # Fail-closed when user-switching is impossible.
    local user="${PLAYWRIGHT_USER:-ntindle}"
    local me
    me="$(id -un 2>/dev/null || true)"
    if [ "$me" = "$user" ]; then
        "$@"
        return
    fi
    if [ "$me" != "root" ]; then
        log "playwright: not $user and not root — refusing (fail-closed)"
        return 1
    fi
    if command -v runuser >/dev/null 2>&1; then
        runuser -u "$user" -- "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo -u "$user" -- "$@"
    else
        log "playwright: cannot switch to $user (no runuser/sudo) — refusing"
        return 1
    fi
}

_playwright_current() {
    # Print the managed venv's installed playwright version, or:
    # absent | version-unknown. The probe runs as $PLAYWRIGHT_USER — the
    # layer never executes venv code as root.
    local py ver out
    py="${PLAYWRIGHT_VENV:-}/bin/python"
    [ -n "${PLAYWRIGHT_VENV:-}" ] && [ -x "$py" ] \
        || { printf 'absent'; return 0; }
    out="$(_as_playwright_user "$py" -c 'import playwright; print(playwright.__version__)' 2>/dev/null || true)"
    ver="$(printf '%s' "$out" | grep -oE '[0-9][A-Za-z0-9._-]*' | head -n 1 || true)"
    # A bare number is not a version — demand at least one dot, mirroring
    # _cua_driver_current.
    case "$ver" in
        *.*) printf '%s' "$ver" ;;
        *) printf 'version-unknown' ;;
    esac
}

_playwright_dep_names() {
    # _playwright_dep_names <cli> — print the missing Chromium system
    # dependencies, one per line, or nothing when all are installed.
    # The list is computed as $PLAYWRIGHT_USER (`install-deps --dry-run`
    # only simulates via `apt-get install -s` — it changes nothing); root
    # never executes the venv CLI. Fail-closed: any output that is not
    # exactly the dry-run's "all installed" message or its
    # "Missing system dependencies (N):" block refuses, and every name is
    # validated against the Debian package-name pattern
    # (^[a-z0-9][a-z0-9+.-]*$) before it is printed.
    local cli="$1"
    local out rc=0
    out="$(_as_playwright_user "$cli" install-deps --dry-run chromium 2>/dev/null)" || rc=$?
    if [ "$rc" = "0" ]; then
        case "$out" in
            *"All system dependencies are installed."*) return 0 ;;
        esac
        log "playwright: unexpected install-deps --dry-run output (exit 0) — refusing"
        return 1
    fi
    local want="" have=0 pkgs="" line pkg
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            'Missing system dependencies ('*'):')
                want="$(printf '%s\n' "$line" | grep -oE '[0-9]+' | head -n 1 || true)" ;;
            '  '*)
                pkg="${line#  }"
                # Debian package-name pattern: ^[a-z0-9][a-z0-9+.-]*$
                # (the trailing `-` in the bracket class is literal).
                case "$pkg" in
                    ''|*[!a-z0-9+.-]*)
                        log "playwright: refusing unsafe dep name from --dry-run: $pkg"
                        return 1 ;;
                esac
                case "$pkg" in
                    [a-z0-9]*) ;;
                    *)
                        log "playwright: refusing dep name with non-alnum start: $pkg"
                        return 1 ;;
                esac
                pkgs="${pkgs:+$pkgs }$pkg"
                have=$((have + 1)) ;;
            '') ;;
            *)
                log "playwright: unexpected install-deps --dry-run line: $line — refusing"
                return 1 ;;
        esac
    done < <(printf '%s\n' "$out")
    case "$want" in
        ''|0)
            log "playwright: no missing-deps header in --dry-run output — refusing"
            return 1 ;;
    esac
    if [ "$have" -ne "$want" ]; then
        log "playwright: --dry-run header said $want missing, parsed $have — refusing"
        return 1
    fi
    printf '%s\n' "$pkgs" | tr ' ' '\n'
    return 0
}

_playwright_install_deps() {
    # _playwright_install_deps <cli> — converge the Chromium system
    # libraries. Root installs only validated package names via apt-get
    # (non-interactive, conffile keep-local, no recommends — mirroring the
    # `apt` layer); the venv CLI is never executed as root. Idempotent:
    # no-op when the dry-run reports everything installed. List freshness
    # comes from the os-security layer's daily refresh, same as the `apt`
    # layer — this step never runs `apt-get update` itself.
    local cli="$1"
    local pkgs
    pkgs="$(_playwright_dep_names "$cli")" || return 1
    if [ -z "$pkgs" ]; then
        log "playwright: system deps already installed"
        return 0
    fi
    local count
    count="$(printf '%s\n' "$pkgs" | grep -c .)"
    log "playwright: installing $count missing system dep(s)"
    # One call site: validated names only, word-splitting intentional.
    # Non-interactive by construction, mirroring the `apt` layer.
    # shellcheck disable=SC2086
    DEBIAN_FRONTEND=noninteractive _sudo apt-get install -y --no-install-recommends \
            -o Dpkg::Options::="--force-confdef" \
            -o Dpkg::Options::="--force-confold" \
            $pkgs \
        || { log "playwright: system-deps install failed"; return 1; }
    log "playwright: installed $count system dep(s)"
    return 0
}

_playwright_layer() {
    # _playwright_layer <dry:0|1> — converge Playwright onto the pins.conf
    # pin. Idempotent: the pip install is skipped on-pin, but the browser
    # and system-library steps still run (both no-op when satisfied).
    # Fail-closed: missing/unsafe pin, missing venv, unparseable installed
    # version, missing browser CLI, or any deps-step refusal all fail the
    # layer loudly. The pip specifier is the exact pin
    # (`playwright==<pin>`), never a floating upgrade — the pins file is the
    # version authority, not PyPI's latest.
    local dry="$1"
    local pin cur py cli
    pin="$(_read_pin playwright)"
    if [ -z "$pin" ]; then
        log "playwright: no pin for playwright in $PINS_FILE — refusing (fail-closed)"
        return 1
    fi
    if ! _pin_ok "$pin"; then
        log "playwright: pin '$pin' is not version-safe — refusing"
        return 1
    fi
    py="$PLAYWRIGHT_VENV/bin/python"
    cli="$PLAYWRIGHT_VENV/bin/playwright"
    cur="$(_playwright_current)"
    local pip_needed=1
    case "$cur" in
        "$pin")
            if [ -x "$cli" ]; then
                log "playwright: pip package on pin $pin"
                pip_needed=0
            else
                log "playwright: on pin $pin but $cli missing — refusing (fail-closed)"
                return 1
            fi ;;
        version-unknown)
            log "playwright: installed but version unparseable — refusing to guess (fail-closed)"
            return 1 ;;
        absent)
            # The venv itself is provisioned by setup, not this layer — a
            # missing venv is a provisioning failure, not package drift, so
            # the layer refuses rather than trying to recreate the venv.
            log "playwright: venv python $py absent — refusing (fail-closed)"
            return 1 ;;
        *)
            log "playwright: drift $cur -> $pin" ;;
    esac
    if [ "$dry" = "1" ]; then
        log "playwright: DRY-RUN would converge playwright $pin (pip: $([ "$pip_needed" = "1" ] && echo install || echo skip); browsers + system deps)"
        return 0
    fi
    if [ "$pip_needed" = "1" ]; then
        if ! _as_playwright_user "$py" -m pip install "playwright==$pin"; then
            log "playwright: pip install playwright==$pin failed"
            return 1
        fi
        [ -x "$cli" ] \
            || { log "playwright: $cli missing after pip install — refusing"; return 1; }
    fi
    # Browsers as the user (they land in the user's ~/.cache/ms-playwright);
    # system libraries via the validated-names apt path (root, never the
    # venv CLI).
    if ! _as_playwright_user "$cli" install chromium; then
        log "playwright: browser install failed"
        return 1
    fi
    if ! _playwright_install_deps "$cli"; then
        return 1
    fi
    log "playwright: converged on pin $pin (was: $cur)"
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
    # Probe the MANAGED venv (PLAYWRIGHT_VENV), not system python: Playwright
    # is provisioned inside the venv (SETUP.md), so a system-python probe
    # reports absent on a healthy box. The probe runs as $PLAYWRIGHT_USER
    # (never as root): it executes the venv interpreter, which imports a
    # user-writable package tree. Read-only: runs the venv's python with
    # -c, installs nothing.
    local _pwpy="${PLAYWRIGHT_VENV:-/home/ntindle/.venvs/pw}/bin/python"
    local _pwver=""
    if [ -x "$_pwpy" ]; then
        _pwver="$(_as_playwright_user "$_pwpy" -c 'import playwright; print(playwright.__version__)' 2>/dev/null | head -n 1 || true)"
    fi
    if [ -n "$_pwver" ]; then
        printf 'playwright\tpresent\t%s\n' "$(printf '%s' "$_pwver" | tr '\t' ' ' | cut -c1-120)"
    else
        printf 'playwright\tabsent\t-\n'
    fi
    _probe_version "cua-driver" cua-driver --version
    # Failure-freeze state (#532 Recovery): the single machine-readable
    # "box needs attention" signal. STATE is `frozen` | `ok`; DETAIL is the
    # freeze since/reason, or the current consecutive-failure count when
    # not frozen. A missing/corrupt state file reads as ok/0 — the counter
    # is availability bookkeeping, never a trust boundary.
    _freeze_state_init
    if [ "$_fz_frozen" = "1" ]; then
        printf 'freeze\tfrozen\t%s\n' "$(printf '%s' "since=$_fz_at reason=$_fz_reason" | tr '\t' ' ' | cut -c1-160 || true)"
    else
        printf 'freeze\tok\tconsecutive_failures=%s\n' "$_fz_consec"
    fi
    return 0
}

# --- failure freeze (#532 Recovery) -----------------------------------------------
: "${TOOLSET_FREEZE_AFTER:=3}"
case "$TOOLSET_FREEZE_AFTER" in
    ''|*[!0-9]*|0)
        # A non-numeric threshold would silently defeat the freeze: the
        # `-ge` comparison below fails (set -e-exempt as a condition) and
        # the counter increments forever without ever freezing (fail-open).
        # `0` is rejected too: it would freeze on the very first failure,
        # while most operators writing `0` mean "disabled" — a footgun.
        # Validate once, loudly, and fall back to the default.
        log "freeze: invalid TOOLSET_FREEZE_AFTER='$TOOLSET_FREEZE_AFTER' — defaulting to 3"
        TOOLSET_FREEZE_AFTER=3
        ;;
esac
STATE_FREEZE="$TOOLSET_STATE_DIR/freeze.state"

_freeze_state_init() {
    # Load the freeze state into _fz_consec / _fz_frozen / _fz_at /
    # _fz_reason. A missing, unreadable, non-regular, or MALFORMED state
    # file reads as clean (consecutive=0, not frozen): freeze.state is
    # root-writable runtime bookkeeping, not a trust boundary, so a bad
    # file must neither freeze the box spuriously nor brick updates
    # permanently. Anything but a clean parse is logged loudly.
    _fz_consec=0
    _fz_frozen=0
    _fz_at=""
    _fz_reason=""
    if [ -f "$STATE_FREEZE" ] && [ -r "$STATE_FREEZE" ]; then
        local line key val ok=1
        while IFS= read -r line || [ -n "$line" ]; do
            case "$line" in
                \#*|"") continue ;;
            esac
            key="${line%%=*}"; val="${line#*=}"
            case "$key" in
                consecutive_failures)
                    case "$val" in
                        ''|*[!0-9]*) ok=0 ;;
                        *) _fz_consec="$val" ;;
                    esac ;;
                frozen)
                    case "$val" in
                        0|1) _fz_frozen="$val" ;;
                        *) ok=0 ;;
                    esac ;;
                frozen_at) _fz_at="$(printf '%s' "$val" | tr -dc '0-9T:Z-' || true)" ;;
                frozen_reason) _fz_reason="$(printf '%s' "$val" | tr '\t' ' ' | cut -c1-120 || true)" ;;
                *) ok=0 ;;
            esac
        done <"$STATE_FREEZE"
        if [ "$ok" != "1" ]; then
            log "freeze: state file $STATE_FREEZE is malformed — resetting to clean (loud, continuing)"
            _fz_consec=0; _fz_frozen=0; _fz_at=""; _fz_reason=""
        fi
    elif [ -e "$STATE_FREEZE" ]; then
        # Exists but is not a readable regular file (directory, socket,
        # unreadable, …): reads as clean, loudly — never bricks, never
        # freezes spuriously, and the operator sees the signal.
        log "freeze: $STATE_FREEZE exists but is not a readable regular file — treating as clean (loud, continuing)"
    fi
}

_freeze_write() {
    # Persist the freeze-state locals. Best-effort: a write failure is
    # logged loudly but never kills the run — the update already happened,
    # the counter is bookkeeping. Sets _fz_write_ok (1/0) so callers with
    # a truthfulness obligation (cmd_unfreeze) can report honestly; a bare
    # nonzero return here would kill update runs under set -e, violating
    # the best-effort design — hence the flag, not the exit status.
    _fz_write_ok=1
    # mv -fT: treat the destination as a normal file. If freeze.state is
    # a directory, a plain `mv -f` would "succeed" by moving the tmp file
    # *into* the directory and the counter would be dropped into the void
    # with zero signal — -T makes that a loud failure instead.
    if ! { printf '# managed by toolset-update.sh — do not hand-edit\nconsecutive_failures=%s\nfrozen=%s\nfrozen_at=%s\nfrozen_reason=%s\n' \
        "$_fz_consec" "$_fz_frozen" "$_fz_at" "$_fz_reason" >"$STATE_FREEZE.tmp" 2>/dev/null \
        && mv -fT "$STATE_FREEZE.tmp" "$STATE_FREEZE" 2>/dev/null; }; then
        log "freeze: cannot write $STATE_FREEZE — counter not persisted (continuing)"
        _fz_write_ok=0
    fi
}

_freeze_refuse_if_frozen() {
    # Returns 1 (refuse) when the box is frozen: log + audit loudly, no
    # layers run. Callers exit nonzero so the timer unit surfaces the
    # "box needs attention" state instead of churning.
    _freeze_state_init
    if [ "$_fz_frozen" = "1" ]; then
        log "update: FROZEN since $_fz_at (reason: $_fz_reason) — box needs attention; run 'toolset-update.sh unfreeze' after investigating (no update attempted)"
        audit 'toolset-update' ",\"result\":\"frozen\",\"since\":\"$_fz_at\",\"reason\":\"$_fz_reason\""
        return 1
    fi
    return 0
}

_freeze_record_result() {
    # _freeze_record_result <ok|failed> [failed-components] — update the
    # consecutive-failure counter after an update run. Deferrals (idle
    # gate, lock held), --dry-run runs, and opt-outs never reach here:
    # only real update attempts move the counter.
    local outcome="$1" comps="${2:-}"
    _freeze_state_init
    case "$outcome" in
        ok)
            if [ "$_fz_consec" != "0" ]; then
                _fz_consec=0
                _freeze_write
                log "freeze: update succeeded — consecutive-failure counter reset"
            fi
            ;;
        failed)
            _fz_consec=$((_fz_consec + 1))
            if [ "$_fz_frozen" = "1" ]; then
                # Defensive: a frozen box refuses updates before the layers
                # run, so this path should not occur. If it ever does, keep
                # the freeze and say so loudly.
                _freeze_write
                log "freeze: update failed again while frozen (consecutive=$_fz_consec) — box still needs attention; run 'toolset-update.sh unfreeze' after investigating"
            elif [ "$_fz_consec" -ge "${TOOLSET_FREEZE_AFTER:-3}" ]; then
                _fz_frozen=1
                _fz_at="$(date -u +%FT%TZ)"
                _fz_reason="$comps"
                _freeze_write
                log "freeze: ENGAGED after $_fz_consec consecutive failed update runs (failed: $comps) — updates halted; box needs attention; run 'toolset-update.sh unfreeze' after investigating"
                audit 'toolset-update-frozen' ",\"consecutive\":\"$_fz_consec\",\"failed\":\"$comps\""
            else
                _freeze_write
            fi
            ;;
    esac
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
        # This is a failed update attempt like any other — it feeds the
        # freeze counter (S1), so a broken box can't churn here either.
        log "update: flock not found; cannot take the single-flight lock"
        _freeze_record_result failed "infra"
        audit 'toolset-update' ',"result":"failed","reason":"flock-missing"'
        return 1
    fi
    exec 9>"$STATE_LOCK" 2>/dev/null || {
        log "update: cannot open lock"
        _freeze_record_result failed "infra"
        return 1
    }
    if ! flock -n 9 2>/dev/null; then
        log "update: another run holds the lock; no-op"
        audit 'toolset-update' ',"result":"deferred","reason":"lock-held"'
        return 0
    fi

    # Failure freeze (#532 Recovery): a frozen box surfaces "box needs
    # attention" instead of churning through doomed updates. --dry-run is
    # still permitted while frozen as a diagnostic — it changes nothing
    # and never touches the counter.
    if [ "$dry" != "1" ] && ! _freeze_refuse_if_frozen; then
        return 1
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
    if ! _playwright_layer "$dry"; then
        rc=1
        failed_comps="${failed_comps:+$failed_comps }playwright"
    fi

    if [ "$dry" = "1" ]; then
        audit 'toolset-update' ',"result":"dry-run"'
    elif [ "$rc" = "0" ]; then
        _freeze_record_result ok
        audit 'toolset-update' ',"result":"ok","components":"os-security cua-driver apt playwright"'
    else
        _freeze_record_result failed "$failed_comps"
        audit 'toolset-update' ',"result":"failed","failed":"'"$failed_comps"'"'
        log "update: FAILED ($failed_comps); see audit log"
    fi
    return "$rc"
}

cmd_unfreeze() {
    # Clear the failure-freeze state after the operator/agent has
    # investigated: the next update run starts with a clean
    # consecutive-failure counter. Never runs updates itself.
    # Truthfulness: unlike the update path (where the counter is
    # best-effort bookkeeping), unfreeze's whole job is the state change —
    # a write failure must fail loudly, not report success.
    for a in "$@"; do case "$a" in *) echo "ERROR: unknown flag: $a" >&2; return 2 ;; esac; done
    mkdir -p "$TOOLSET_STATE_DIR" 2>/dev/null || true
    _fz_consec=0; _fz_frozen=0; _fz_at=""; _fz_reason=""
    _freeze_write
    if [ "${_fz_write_ok:-1}" != "1" ]; then
        echo "ERROR: unfreeze failed: cannot write $STATE_FREEZE — box is still frozen" >&2
        return 1
    fi
    log "unfreeze: failure-freeze state cleared (counter reset)"
    audit 'toolset-update' ',"result":"unfrozen"'
    return 0
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
        unfreeze)  cmd_unfreeze "$@" ;;
        install)   cmd_install "$@" ;;
        uninstall) cmd_uninstall "$@" ;;
        optout)    cmd_optout "$@" ;;
        optin)     cmd_optin "$@" ;;
        version)   cmd_version "$@" ;;
        -h|--help|help) usage ;;
        *) usage ;;
    esac
fi
