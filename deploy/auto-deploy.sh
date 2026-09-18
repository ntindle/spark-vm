#!/bin/bash
# deploy/auto-deploy.sh — unattended updater for spark-vm's deployed components.
#
# Watches origin/main for new merged commits, detects which deployable
# components changed (components.conf), runs pre-deploy gates, installs
# only the changed components, restarts only their services, health-checks,
# and rolls back on failure. Every run is appended to an audit log.
#
# Trust model (read deploy/README.md before enabling):
#   - THE TIMER RUNS THE INSTALLED COPY at $UPDATER_STATE_DIR/bin/, NOT the
#     repo checkout. `init` copies the script + components.conf there from the
#     checkout; re-running `init` refreshes them. A checkout-only writer
#     therefore cannot rewire the updater's own code or config — but CAN still
#     influence cred-ui at restart time, because cred-ui executes from the
#     working checkout (its subtree is synced from the mirror at deploy).
#     Treat `init` (reinstall) as a privileged step: review the diff first.
#   - The updater deploys whatever is merged to main. Anyone who can merge to
#     main can therefore execute code on the box — the same trust deploy.sh
#     already assumes. Enabling the timer automates an existing trust, it does
#     not widen it.
#   - It fetches from a PINNED upstream URL and aborts if `origin` was rewired.
#   - Gates run BEFORE any file is installed; a rollback snapshot is taken
#     before install; health checks run after restart; failure rolls back and
#     marks the commit blocked so the next tick does not retry-loop it.
#
# Usage:
#   auto-deploy.sh init      # one-time: create mirror repo + install updater copy
#   auto-deploy.sh check     # fetch + report what a deploy would do (read-only)
#   auto-deploy.sh deploy    # fetch, gate, install, restart, health-check
#   auto-deploy.sh rollback  # restore the most recent snapshot + restart
#   auto-deploy.sh status    # watermark, last run, timer state
#   auto-deploy.sh map FROM TO  # print components changed between two commits
#
# State lives in UPDATER_STATE_DIR (default /home/ntindle/.sparkvm-deploy),
# OUTSIDE the repo checkout. The systemd unit's ExecStart points at the
# installed copy there.
#
# Env overrides (for tests): UPDATER_STATE_DIR, UPDATER_REPO, SWAPD_HOME,
# BIN_DIR, SYSTEMD_DIR, WORKING_CHECKOUT, UPDATER_COMPONENTS_CONF,
# SKIP_SYSTEMCTL=1 (skip systemctl calls), SKIP_SUDO=1 (run file ops without
# sudo), PINNED_UPSTREAM.

set -euo pipefail
set -o pipefail
# Security-relevant state (watermark, audit log, snapshots of root-deployed
# files) must not be world-readable.
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# --- configurable paths (env-overridable for tests) -------------------------
: "${UPDATER_STATE_DIR:=/home/ntindle/.sparkvm-deploy}"
: "${UPDATER_REPO:=$UPDATER_STATE_DIR/repo}"
: "${UPDATER_COMPONENTS_CONF:=$SCRIPT_DIR/components.conf}"
: "${SWAPD_HOME:=/home/swapd}"
: "${BIN_DIR:=/usr/local/bin}"
: "${SYSTEMD_DIR:=/etc/systemd/system}"
: "${WORKING_CHECKOUT:=/home/ntindle/spark-vm}"
: "${PINNED_UPSTREAM:=https://github.com/ntindle/spark-vm}"
: "${SKIP_SYSTEMCTL:=0}"
: "${SKIP_SUDO:=0}"

WATERMARK="$UPDATER_STATE_DIR/deployed-commit"
BLOCKED_COMMIT="$UPDATER_STATE_DIR/blocked-commit"
AUDIT_LOG="$UPDATER_STATE_DIR/audit.log"
LOCK_FILE="$UPDATER_STATE_DIR/auto-deploy.lock"
SNAPSHOT_DIR="$UPDATER_STATE_DIR/snapshots"
LAST_FAILURE="$UPDATER_STATE_DIR/last-failure"
INSTALLED_BIN="$UPDATER_STATE_DIR/bin"

# components.conf must be sourced AFTER the *_HOME vars exist, because its
# install_paths reference them.
# shellcheck source=components.conf
source "$UPDATER_COMPONENTS_CONF"

# --- helpers -----------------------------------------------------------------

log() { echo "[auto-deploy] $*" >&2; }

# bash var prefix for a component name: cred-ui -> cred_ui
vpre() { local c="$1"; echo "${c//-/_}"; }

# get_arr <component> <field>  -> prints array elements, one per line
get_arr() {
    local p var
    p="$(vpre "$1")"; var="${p}_$2"
    if ! declare -p "$var" >/dev/null 2>&1; then
        echo "ERROR: unknown component/field: $1/$2" >&2; return 1
    fi
    local -n arr="$var"
    printf '%s\n' "${arr[@]}"
}

# get_str <component> <field>
get_str() {
    local p var
    p="$(vpre "$1")"; var="${p}_$2"
    if ! declare -p "$var" >/dev/null 2>&1; then
        echo "ERROR: unknown component/field: $1/$2" >&2; return 1
    fi
    printf '%s' "${!var:-}"
}

audit() {
    # audit <event> <json-fields...>
    # Appends one JSON line: {"ts":..., "event":..., ...}. Best-effort: never
    # fails the run. Callers MUST expand variables before passing fields —
    # single-quoted '$old' would log literally (regression-tested).
    local event="$1"; shift
    mkdir -p "$(dirname "$AUDIT_LOG")" 2>/dev/null || true
    local ts; ts="$(date -u +%FT%TZ)"
    # Subshell so a redirection failure (e.g. unwritable state dir) is silent
    # rather than noisy.
    ( printf '{"ts":"%s","event":"%s"%s}\n' "$ts" "$event" "$*" >>"$AUDIT_LOG" ) 2>/dev/null || true
    # Bound the log: keep the newest 10k lines once it passes 12k.
    local n; n="$(wc -l <"$AUDIT_LOG" 2>/dev/null || echo 0)"
    if [ "$n" -gt 12000 ] 2>/dev/null; then
        tail -n 10000 "$AUDIT_LOG" >"$AUDIT_LOG.tmp" 2>/dev/null \
            && mv -f "$AUDIT_LOG.tmp" "$AUDIT_LOG" 2>/dev/null || true
    fi
}

alert() {
    # alert <reason> — persistent, visible failure record. The timer unit's
    # failure also lands in the journal; this file is the human-readable one.
    log "ALERT: $*"
    mkdir -p "$(dirname "$LAST_FAILURE")"
    # || true: a failed alert redirect must never kill the run before the
    # audit line that always follows.
    printf '%s deploy failed: %s\n' "$(date -u +%FT%TZ)" "$*" >"$LAST_FAILURE" || true
}

sctl() {
    # sctl <args...> — systemctl unless SKIP_SYSTEMCTL=1 (tests).
    if [ "$SKIP_SYSTEMCTL" = "1" ]; then log "(skip systemctl $*)"; return 0; fi
    systemctl "$@"
}

sudo_run() {
    if [ "$SKIP_SUDO" = "1" ]; then "$@"; else sudo "$@"; fi
}

tcp_ok() {
    # tcp_ok host port — true if something accepts a TCP connection.
    local host="$1" port="$2"
    (exec 3<>/dev/tcp/"$host"/"$port") 2>/dev/null
}

write_watermark() {
    # Atomic watermark update: a torn write must never strand the updater.
    printf '%s\n' "$1" >"$WATERMARK.tmp" && mv -f "$WATERMARK.tmp" "$WATERMARK"
}

newest_snapshot() {
    # Prints the newest snapshot dir, or nothing.
    find "$SNAPSHOT_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null \
        | sort -rn | head -1 | cut -d' ' -f2-
}

prune_snapshots() {
    # Keep the newest 5 snapshots.
    find "$SNAPSHOT_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2>/dev/null \
        | sort -rn | tail -n +6 | cut -d' ' -f2- | xargs -r rm -rf
}

# --- change detection ----------------------------------------------------------

fetch_main() {
    log "fetching $PINNED_UPSTREAM ..."
    # All fetch chatter goes to stderr: pending_range's stdout is machine-
    # readable ("old new"), and callers capture it.
    git -C "$UPDATER_REPO" fetch origin main 2>&1 | tail -2 >&2
}

check_upstream_pinned() {
    # Refuse to deploy if origin was rewired away from the pinned upstream.
    local url
    url="$(git -C "$UPDATER_REPO" remote get-url origin 2>/dev/null || true)"
    if [ "$url" != "$PINNED_UPSTREAM" ] && [ "$url" != "${PINNED_UPSTREAM}.git" ]; then
        log "ERROR: origin is '$url', expected pinned '$PINNED_UPSTREAM' — refusing to deploy"
        return 1
    fi
}

components_for_files() {
    # stdin: changed repo paths, one per line. stdout: component names, unique.
    local f c pfx
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        for c in "${COMPONENTS[@]}"; do
            while IFS= read -r pfx; do
                if [[ "$f" == "$pfx"* ]]; then echo "$c"; break; fi
            done < <(get_arr "$c" paths)
        done
    done | sort -u
}

expand_install_unit() {
    # expand_install_unit <array-name> — components sharing an install_unit
    # deploy as one unit (e.g. proxy+confirm share deploy.sh, which installs
    # both unconditionally — snapshotting only one of them would leave the
    # other unrestorable).
    local -n _eu_arr="$1"
    local -a _eu_seed
    mapfile -t _eu_seed < <(printf '%s\n' "${_eu_arr[@]}")
    local c d u x found
    for c in "${_eu_seed[@]}"; do
        u="$(get_str "$c" install_unit)"
        [ -n "$u" ] || continue
        for d in "${COMPONENTS[@]}"; do
            [ "$(get_str "$d" install_unit)" = "$u" ] || continue
            found=0
            for x in "${_eu_arr[@]}"; do [ "$x" = "$d" ] && found=1; done
            [ "$found" -eq 0 ] && _eu_arr+=("$d")
        done
    done
    # dedupe + sort
    mapfile -t _eu_arr < <(printf '%s\n' "${_eu_arr[@]}" | sort -u)
}

cmd_map() {
    # map FROM TO — print deployable components changed between two commits.
    local from="$1" to="$2"
    git -C "$UPDATER_REPO" diff --name-only "$from" "$to" | components_for_files
}

# --- gates ---------------------------------------------------------------------

run_gates() {
    # run_gates <component> — returns 0 iff all gates pass.
    local c="$1"
    local tests; tests="$(get_str "$c" tests)"
    if [ -z "$tests" ]; then log "  $c: no gate configured — FAIL CLOSED"; return 1; fi
    log "  $c gate: $tests"
    if ( cd "$UPDATER_REPO" && eval "$tests" ); then
        log "  $c gate: PASS"
        return 0
    fi
    log "  $c gate: FAIL"
    return 1
}

check_checkout_sync_ready() {
    # check_checkout_sync_ready <component> <subtree> <new> — fail closed if
    # the working-checkout subtree cannot be safely synced (gate phase: runs
    # BEFORE any mutation).
    local c="$1" sub="$2" new="$3"
    local dest="$WORKING_CHECKOUT/$sub"
    if [ ! -d "$WORKING_CHECKOUT/.git" ]; then
        log "  $c: WORKING_CHECKOUT $WORKING_CHECKOUT is not a git checkout — FAIL CLOSED"
        return 1
    fi
    if [ -e "$dest" ] && [ -n "$(git -C "$WORKING_CHECKOUT" status --porcelain -- "$sub")" ]; then
        log "  $c: uncommitted changes in $dest — refusing to overwrite (commit or stash first)"
        return 1
    fi
    if ! git -C "$UPDATER_REPO" cat-file -e "$new:$sub" 2>/dev/null; then
        log "  $c: subtree $sub not present at $new — FAIL CLOSED"
        return 1
    fi
    return 0
}

# --- snapshot / rollback -------------------------------------------------------

snapshot_component() {
    # snapshot_component <component> <snapdir> — copy currently-installed
    # files and checkout-synced subtrees.
    local c="$1" snapdir="$2"
    local p rel sub dest
    while IFS= read -r p; do
        [ -n "$p" ] || continue
        # store under snapdir + absolute path, e.g. <snapdir>/home/swapd/swap_addon.py
        rel="$snapdir$p"
        if [ -e "$p" ]; then
            mkdir -p "$(dirname "$rel")" || {
                log "ERROR: cannot create snapshot dir for $p"; return 1; }
            sudo_run cp -a "$p" "$rel" || {
                log "ERROR: snapshot copy of $p failed"; return 1; }
            echo "$p" >>"$snapdir/MANIFEST"
        else
            echo "ABSENT $p" >>"$snapdir/MANIFEST"
        fi
    done < <(get_arr "$c" install_paths)
    sub="$(get_str "$c" checkout_sync)"
    if [ -n "$sub" ]; then
        dest="$WORKING_CHECKOUT/$sub"
        if [ -e "$dest" ]; then
            mkdir -p "$snapdir/checkout-$(vpre "$c")" || {
                log "ERROR: cannot create checkout snapshot dir for $c"; return 1; }
            cp -a "$dest" "$snapdir/checkout-$(vpre "$c")/" || {
                log "ERROR: checkout snapshot of $dest failed"; return 1; }
            echo "CHECKOUT $c $sub" >>"$snapdir/MANIFEST"
        else
            echo "CHECKOUT-ABSENT $c $sub" >>"$snapdir/MANIFEST"
        fi
    fi
    return 0
}

restore_snapshot() {
    # restore_snapshot <snapdir> — copy snapshot files back to their paths.
    # Returns nonzero on any failure (caller must NOT report success).
    local snapdir="$1"
    local line rc=0
    [ -f "$snapdir/MANIFEST" ] || { log "ERROR: no MANIFEST in $snapdir"; return 1; }
    while IFS= read -r line; do
        case "$line" in
            ABSENT\ *)
                local p="${line#ABSENT }"
                log "  removing $p (was absent at snapshot)"
                sudo_run rm -f "$p" || rc=1
                ;;
            CHECKOUT\ *)
                local c="${line#CHECKOUT }"; c="${c%% *}"
                local sub="${line#CHECKOUT * }"
                sub="${sub#* }"
                local dest="$WORKING_CHECKOUT/$sub"
                log "  restoring checkout subtree $dest"
                rm -rf "$dest" || rc=1
                cp -a "$snapdir/checkout-$(vpre "$c")/$sub" "$dest" || rc=1
                ;;
            CHECKOUT-ABSENT\ *)
                local rest="${line#CHECKOUT-ABSENT }"
                local sub2="${rest#* }"
                log "  removing $WORKING_CHECKOUT/$sub2 (was absent at snapshot)"
                rm -rf "$WORKING_CHECKOUT/$sub2" || rc=1
                ;;
            *)
                log "  restoring $line"
                sudo_run cp -a "$snapdir$line" "$line" || rc=1
                ;;
        esac
    done <"$snapdir/MANIFEST"
    return "$rc"
}

# --- install / restart / health --------------------------------------------------

install_component() {
    # install_component <component> <new-sha> — run the component's install
    # step (from the updater mirror) and/or sync its checkout subtree.
    local c="$1" new="$2"
    local inst; inst="$(get_str "$c" install)"
    if [ -n "$inst" ]; then
        log "  $c install: $inst"
        # The install command owns its own privilege (e.g. deploy.sh uses
        # sudo internally). The child deploy.sh must not fight us for the
        # single-flight lock — we hold it.
        if ! ( export AUTO_DEPLOY_HOLDS_LOCK=1; cd "$UPDATER_REPO" && eval "$inst" ); then
            log "  $c install FAILED"
            return 1
        fi
    fi
    local sub; sub="$(get_str "$c" checkout_sync)"
    if [ -n "$sub" ]; then
        log "  $c: syncing subtree $sub from mirror@$new into $WORKING_CHECKOUT"
        rm -rf "$WORKING_CHECKOUT/$sub" || return 1
        if ! git -C "$UPDATER_REPO" archive "$new" "$sub" | tar -x -C "$WORKING_CHECKOUT"; then
            log "  $c: subtree sync FAILED"
            return 1
        fi
    fi
    return 0
}

restart_component_services() {
    # restart_component_services <component> — restart system + user units.
    local c="$1"
    local svc
    while IFS= read -r svc; do
        [ -n "$svc" ] || continue
        log "  restarting $svc"
        sctl restart "$svc" || { log "  restart of $svc failed"; return 1; }
    done < <(get_arr "$c" services)
    while IFS= read -r svc; do
        [ -n "$svc" ] || continue
        log "  restarting user service $svc"
        sctl --user restart "$svc" || { log "  user restart of $svc failed"; return 1; }
    done < <(get_arr "$c" user_services)
    return 0
}

reload_and_enable() {
    # reload_and_enable <components...> — daemon-reload after unit installs
    # (a restart without reload runs the STALE in-memory unit definition),
    # and enable units so a PR that adds a service doesn't install-but-never-enable.
    local c svc any_sys=0 any_user=0
    for c in "$@"; do
        while IFS= read -r svc; do
            [ -n "$svc" ] || continue
            any_sys=1
            sctl enable "$svc" >/dev/null 2>&1 || log "  warning: enable $svc failed"
        done < <(get_arr "$c" services)
        while IFS= read -r svc; do
            [ -n "$svc" ] || continue
            any_user=1
            sctl --user enable "$svc" >/dev/null 2>&1 || log "  warning: user enable $svc failed"
        done < <(get_arr "$c" user_services)
    done
    [ "$any_sys" -eq 1 ] && sctl daemon-reload
    [ "$any_user" -eq 1 ] && sctl --user daemon-reload
    return 0
}

health_check() {
    # health_check <component> — is-active + tcp checks, with retries.
    local c="$1"
    local svc h host port
    while IFS= read -r svc; do
        [ -n "$svc" ] || continue
        if [ "$SKIP_SYSTEMCTL" = "1" ]; then continue; fi
        if ! systemctl is-active --quiet "$svc"; then
            log "  health: $svc is NOT active"
            return 1
        fi
    done < <(get_arr "$c" services)
    while IFS= read -r svc; do
        [ -n "$svc" ] || continue
        if [ "$SKIP_SYSTEMCTL" = "1" ]; then continue; fi
        if ! systemctl --user is-active --quiet "$svc"; then
            log "  health: user $svc is NOT active"
            return 1
        fi
    done < <(get_arr "$c" user_services)

    while IFS= read -r h; do
        [ -n "$h" ] || continue
        host="${h#tcp:}"; host="${host%:*}"; port="${h##*:}"
        log "  health: tcp $host:$port ..."
        local i ok=0
        for i in $(seq 1 20); do
            if tcp_ok "$host" "$port"; then ok=1; break; fi
            sleep 0.5
        done
        if [ "$ok" != "1" ]; then
            log "  health: tcp $host:$port FAILED"
            return 1
        fi
    done < <(get_arr "$c" health)
    log "  health: $c OK"
    return 0
}

# --- rollback driver -------------------------------------------------------------

do_rollback() {
    # do_rollback <snapdir> <old> <new> <failed-component> <phase>
    # Restore the snapshot, restart + health-check, mark the commit blocked
    # so the next tick does not retry-loop it. Always returns 1 (deploy failed).
    local snapdir="$1" old="$2" new="$3" failed_c="$4" phase="$5"
    local c
    alert "deploy $phase failed for component $failed_c ($old -> $new) — rolling back"
    audit 'deploy' ',"result":"deploy-fail","from":"'"$old"'","to":"'"$new"'","component":"'"$failed_c"'","phase":"'"$phase"'"'
    if ! restore_snapshot "$snapdir"; then
        alert "ROLLBACK FAILED for $new — box may be half-deployed, operator intervention required"
        audit 'deploy' ',"result":"rollback-failed","from":"'"$old"'","to":"'"$new"'"'
        printf '%s\n' "$new" >"$BLOCKED_COMMIT.tmp" && mv -f "$BLOCKED_COMMIT.tmp" "$BLOCKED_COMMIT"
        return 1
    fi
    # A failed daemon-reload here must not abort the rollback: the blocked
    # write + audit below must always run or the timer retry-loops forever.
    reload_and_enable "${ROLLBACK_COMPS[@]}" \
        || log "warning: daemon-reload/enable failed during rollback — continuing restore"
    for c in "${ROLLBACK_COMPS[@]}"; do
        restart_component_services "$c" || true
    done
    local unhealthy=0
    for c in "${ROLLBACK_COMPS[@]}"; do
        health_check "$c" || unhealthy=1
    done
    if [ "$unhealthy" -eq 1 ]; then
        alert "rolled back to $old but a component is unhealthy — operator intervention required"
    fi
    printf '%s\n' "$new" >"$BLOCKED_COMMIT.tmp" && mv -f "$BLOCKED_COMMIT.tmp" "$BLOCKED_COMMIT"
    audit 'deploy' ',"result":"rolled-back","from":"'"$old"'","to":"'"$new"'"'
    return 1
}

# --- subcommands ---------------------------------------------------------------

cmd_init() {
    # Operator setup (privileged step — review the checkout diff before
    # re-running): create the mirror repo and install the updater's own code
    # + config into $UPDATER_STATE_DIR/bin, which is what the timer runs.
    mkdir -p "$UPDATER_STATE_DIR" "$INSTALLED_BIN"
    if [ -d "$UPDATER_REPO/.git" ]; then
        log "updater repo already exists at $UPDATER_REPO"
    else
        log "cloning $PINNED_UPSTREAM into $UPDATER_REPO"
        git clone "$PINNED_UPSTREAM" "$UPDATER_REPO"
    fi
    install -m 0755 "$SCRIPT_DIR/auto-deploy.sh" "$INSTALLED_BIN/auto-deploy.sh"
    install -m 0644 "$UPDATER_COMPONENTS_CONF" "$INSTALLED_BIN/components.conf"
    log "installed updater to $INSTALLED_BIN (timer ExecStart must point here)"
    log "init done. Next: install the systemd unit + timer (see README.md)."
}

# pending_range return codes: 0 = range ready on stdout; 1 = nothing to do
# (up-to-date, or head is blocked after a rollback); 2 = error, do not proceed.
pending_range() {
    # Prints "old new" commit shas on stdout.
    # Returns 0 = range ready; 1 = nothing to do; 2 = error, do not proceed.
    # NOTE: this often runs inside $( ) — it must not communicate via globals.
    [ -d "$UPDATER_REPO/.git" ] || { log "ERROR: updater repo missing — run '$0 init' first"; return 2; }
    check_upstream_pinned || return 2
    fetch_main || return 2
    local old new blocked=""
    old="$(cat "$WATERMARK" 2>/dev/null || echo "")"
    new="$(git -C "$UPDATER_REPO" rev-parse origin/main)"
    [ -f "$BLOCKED_COMMIT" ] && blocked="$(cat "$BLOCKED_COMMIT" 2>/dev/null || echo "")"
    if [ -n "$blocked" ]; then
        if [ "$new" = "$blocked" ]; then
            log "head $new was rolled back earlier; waiting for a newer commit (see last-failure)"
            return 1
        fi
        if git -C "$UPDATER_REPO" merge-base --is-ancestor "$blocked" "$new" 2>/dev/null; then
            log "newer commit $new supersedes rolled-back $blocked — clearing block"
            rm -f "$BLOCKED_COMMIT"
        else
            log "head $new does not contain rolled-back $blocked (history rewritten?) — staying blocked"
            return 1
        fi
    fi
    if [ -z "$old" ]; then
        log "no watermark yet — first run will deploy everything at $new"
        # deploy everything on first run: diff against the empty tree
        echo "4b825dc642cb6eb9a060e54bf8d69288fbee4904 $new"
        return 0
    fi
    if [ "$old" = "$new" ]; then
        log "up to date at $new"
        return 1
    fi
    # Fail LOUD if either end is not a commit: a garbage range must never
    # silently deploy the wrong thing (or nothing).
    local sha
    for sha in "$old" "$new"; do
        if ! [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || ! git -C "$UPDATER_REPO" cat-file -e "$sha" 2>/dev/null; then
            log "ERROR: not a valid commit in updater repo: $sha — refusing to deploy"
            return 2
        fi
    done
    echo "$old $new"
}

cmd_check() {
    local range rc old new
    # NOTE: plain `range="$(pending_range)"; rc=$?` is dead code under
    # set -e — a failing command substitution exits the shell before rc=$?
    # runs. The `if` condition suppresses errexit so rc is captured.
    if range="$(pending_range)"; then rc=0; else rc=$?; fi
    if [ "$rc" -eq 1 ]; then return 0; fi  # up-to-date or blocked; already logged
    if [ "$rc" -ne 0 ]; then return "$rc"; fi  # propagate precheck errors (no silent success)
    old="${range%% *}"; new="${range##* }"
    log "would deploy $old -> $new"
    local -a comps
    mapfile -t comps < <(git -C "$UPDATER_REPO" diff --name-only "$old" "$new" | components_for_files)
    if [ "${#comps[@]}" -eq 0 ]; then
        log "no deployable components changed (pull-only changes)"
    else
        log "changed components:"
        local c
        for c in "${comps[@]}"; do log "  - $c"; done
    fi
}

cmd_deploy() {
    mkdir -p "$UPDATER_STATE_DIR" "$SNAPSHOT_DIR"
    local range rc old new
    # Same set -e trap as in cmd_check: the `if` captures the return code.
    if range="$(pending_range)"; then rc=0; else rc=$?; fi
    if [ "$rc" -eq 1 ]; then
        # A blocked head stays quiet: the rollback already audited + alerted.
        # (pending_range runs in $( ), so the reason can't come back via a
        # global — the blocked file's presence is the signal.)
        if [ ! -f "$BLOCKED_COMMIT" ]; then
            audit 'check' ',"result":"noop"'
        fi
        return 0
    fi
    if [ "$rc" -ne 0 ]; then
        alert "pre-deploy check failed"
        audit 'check' ',"result":"precheck-fail"'
        return 1
    fi
    old="${range%% *}"; new="${range##* }"

    # Reset the mirror to the new commit (the mirror is never a working tree).
    git -C "$UPDATER_REPO" reset --hard -q "$new" || {
        alert "mirror reset to $new failed ($old -> $new)"
        audit 'deploy' ',"result":"precheck-fail","from":"'"$old"'","to":"'"$new"'"'
        return 1
    }

    local changed c
    changed="$(git -C "$UPDATER_REPO" diff --name-only "$old" "$new")"
    local -a COMPS
    mapfile -t COMPS < <(printf '%s\n' "$changed" | components_for_files)

    if [ "${#COMPS[@]}" -eq 0 ]; then
        log "no deployable components changed — advancing watermark only"
        write_watermark "$new"
        audit 'deploy' ',"result":"pull-only","from":"'"$old"'","to":"'"$new"'"'
        return 0
    fi
    # Components sharing an install unit deploy together (proxy+confirm share
    # deploy.sh, which installs both unconditionally).
    expand_install_unit COMPS
    log "deploying $old -> $new; components: ${COMPS[*]}"

    # 1. gates BEFORE any mutation (incl. checkout-sync preconditions)
    for c in "${COMPS[@]}"; do
        run_gates "$c" || {
            alert "pre-deploy gate failed for component $c ($old -> $new)"
            audit 'deploy' ',"result":"gate-fail","from":"'"$old"'","to":"'"$new"'","component":"'"$c"'"'
            return 1
        }
        local sub; sub="$(get_str "$c" checkout_sync)"
        if [ -n "$sub" ]; then
            check_checkout_sync_ready "$c" "$sub" "$new" || {
                alert "pre-deploy checkout-sync check failed for component $c ($old -> $new)"
                audit 'deploy' ',"result":"gate-fail","from":"'"$old"'","to":"'"$new"'","component":"'"$c"'"'
                return 1
            }
        fi
    done

    # 2. snapshot for rollback
    local snapdir="$SNAPSHOT_DIR/$new"
    rm -rf "$snapdir"; mkdir -p "$snapdir" || {
        alert "could not create snapshot dir $snapdir ($old -> $new)"
        audit 'deploy' ',"result":"snapshot-fail","from":"'"$old"'","to":"'"$new"'"'
        return 1
    }
    printf '%s\n' "$old" >"$snapdir/FROM_COMMIT" || {
        alert "could not write snapshot manifest ($old -> $new)"
        audit 'deploy' ',"result":"snapshot-fail","from":"'"$old"'","to":"'"$new"'"'
        return 1
    }
    printf '%s\n' "${COMPS[@]}" >"$snapdir/COMPONENTS" || {
        alert "could not write snapshot manifest ($old -> $new)"
        audit 'deploy' ',"result":"snapshot-fail","from":"'"$old"'","to":"'"$new"'"'
        return 1
    }
    local snapc
    for snapc in "${COMPS[@]}"; do
        snapshot_component "$snapc" "$snapdir" || {
            alert "snapshot of component $snapc failed ($old -> $new)"
            audit 'deploy' ',"result":"snapshot-fail","from":"'"$old"'","to":"'"$new"'","component":"'"$snapc"'"'
            return 1
        }
    done
    log "snapshot saved to $snapdir"

    # ROLLBACK_COMPS is read by do_rollback (global by necessity).
    ROLLBACK_COMPS=("${COMPS[@]}")

    # 3. install; on any failure roll everything back
    for c in "${COMPS[@]}"; do
        log "deploying component: $c"
        install_component "$c" "$new" || { do_rollback "$snapdir" "$old" "$new" "$c" "install"; return 1; }
    done

    # 4. daemon-reload + enable BEFORE restarting (else restarts use the stale
    #    in-memory unit definition), then restart only affected services.
    reload_and_enable "${COMPS[@]}" || {
        alert "daemon-reload/enable failed after install ($old -> $new) — rolling back"
        audit 'deploy' ',"result":"reload-fail","from":"'"$old"'","to":"'"$new"'"'
        do_rollback "$snapdir" "$old" "$new" "${COMPS[0]}" "reload"
        return 1
    }
    for c in "${COMPS[@]}"; do
        restart_component_services "$c" || { do_rollback "$snapdir" "$old" "$new" "$c" "restart"; return 1; }
    done

    # 5. health-check; failure rolls back.
    for c in "${COMPS[@]}"; do
        health_check "$c" || { do_rollback "$snapdir" "$old" "$new" "$c" "health"; return 1; }
    done

    # 6. success: advance watermark, clear any block, prune, audit
    write_watermark "$new"
    rm -f "$BLOCKED_COMMIT" "$LAST_FAILURE"
    prune_snapshots
    local complist; complist="$(printf '%s\n' "${COMPS[@]}" | tr '\n' ' ' | xargs)"
    audit 'deploy' ',"result":"ok","from":"'"$old"'","to":"'"$new"'","components":"'"$complist"'"'
    log "deployed $new — components: $complist"
}

cmd_rollback() {
    local snapdir
    snapdir="$(newest_snapshot)"
    [ -n "$snapdir" ] || { log "ERROR: no snapshots to roll back to"; return 1; }
    log "rolling back to snapshot $snapdir"
    if ! restore_snapshot "$snapdir"; then
        alert "manual ROLLBACK FAILED for $snapdir — operator intervention required"
        audit 'rollback' ',"result":"rollback-failed","snapshot":"'"$snapdir"'"'
        return 1
    fi
    local -a rcomps
    if [ -f "$snapdir/COMPONENTS" ]; then
        mapfile -t rcomps <"$snapdir/COMPONENTS"
    else
        rcomps=("${COMPONENTS[@]}")
    fi
    reload_and_enable "${rcomps[@]}"
    local c unhealthy=0
    for c in "${rcomps[@]}"; do
        restart_component_services "$c" || unhealthy=1
    done
    for c in "${rcomps[@]}"; do
        health_check "$c" || unhealthy=1
    done
    local from; from="$(cat "$snapdir/FROM_COMMIT" 2>/dev/null || true)"
    if [ -z "$from" ]; then
        alert "manual rollback failed: snapshot $snapdir has no FROM_COMMIT — refusing to rewrite watermark"
        audit 'rollback' ',"result":"rollback-failed","snapshot":"'"$snapdir"'"'
        return 1
    fi
    write_watermark "$from"
    if [ "$unhealthy" -eq 1 ]; then
        alert "manual rollback to $from completed but a component is unhealthy"
        audit 'rollback' ',"result":"rollback-unhealthy","to":"'"$from"'","snapshot":"'"$snapdir"'"'
        return 1
    fi
    audit 'rollback' ',"result":"manual-rollback","to":"'"$from"'","snapshot":"'"$snapdir"'"'
    log "rolled back; watermark now $from; services restarted + healthy"
}

cmd_status() {
    echo "state dir:  $UPDATER_STATE_DIR"
    echo "watermark:  $(cat "$WATERMARK" 2>/dev/null || echo '(none)')"
    echo "blocked:    $(cat "$BLOCKED_COMMIT" 2>/dev/null || echo '(none)')"
    echo "audit log:  $AUDIT_LOG ($(wc -l <"$AUDIT_LOG" 2>/dev/null || echo 0) lines)"
    echo "snapshots:  $(find "$SNAPSHOT_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)"
    if [ -f "$LAST_FAILURE" ]; then echo "LAST FAILURE:"; cat "$LAST_FAILURE"; fi
    if [ "$SKIP_SYSTEMCTL" = "1" ]; then
        echo "timer:      (systemctl skipped in this environment)"
    elif systemctl --quiet is-enabled auto-deploy.timer 2>/dev/null; then
        echo "timer:      enabled"
        systemctl list-timers auto-deploy.timer --no-pager 2>/dev/null | tail -3
    else
        echo "timer:      not enabled"
    fi
}

usage() {
    sed -n '2,/^$/p' "$0" | sed 's/^# \?//'
    echo "commands: init | check | deploy | rollback | status | map FROM TO"
}

main() {
    local cmd="${1:-}"
    case "$cmd" in
        init)     cmd_init ;;
        check)    cmd_check ;;
        deploy)
            # Single-flight: the timer and a manual run must never overlap.
            mkdir -p "$UPDATER_STATE_DIR"
            exec 9>"$LOCK_FILE"
            flock -n 9 || { log "another auto-deploy run holds the lock — exiting"; exit 0; }
            cmd_deploy
            ;;
        rollback)
            # A manual rollback must not race an in-flight deploy either.
            mkdir -p "$UPDATER_STATE_DIR"
            exec 9>"$LOCK_FILE"
            flock -n 9 || { log "a deploy holds the lock — retry the rollback after it finishes"; exit 1; }
            cmd_rollback
            ;;
        status)   cmd_status ;;
        map)      cmd_map "${2:?map needs FROM}" "${3:?map needs TO}" ;;
        -h|--help|help) usage ;;
        *)        usage; exit 1 ;;
    esac
}

# Sourcing guard: tests source this file to exercise its functions.
if [ "${AUTO_DEPLOY_NO_MAIN:-0}" != "1" ]; then
    main "$@"
fi
