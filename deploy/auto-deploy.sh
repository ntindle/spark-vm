#!/bin/bash
# deploy/auto-deploy.sh — unattended updater for spark-vm's deployed components.
#
# Watches origin/main for new merged commits, detects which deployable
# components changed (deploy/components.conf), runs pre-deploy gates, installs
# only the changed components, restarts only their services, health-checks,
# and rolls back on failure. Every run is appended to an audit log.
#
# Trust model (read deploy/README.md before enabling):
#   - The updater deploys whatever is merged to main. Anyone who can merge to
#     main can therefore execute code on the box — the same trust deploy.sh
#     already assumes. Enabling the timer automates an existing trust, it does
#     not widen it.
#   - It fetches from a PINNED upstream URL and aborts if `origin` was rewired.
#   - Gates run BEFORE any file is installed; a rollback snapshot is taken
#     before install; health checks run after restart; failure rolls back.
#
# Usage:
#   auto-deploy.sh init      # one-time: create the updater mirror repo
#   auto-deploy.sh check     # fetch + report what a deploy would do (read-only)
#   auto-deploy.sh deploy    # fetch, gate, install, restart, health-check
#   auto-deploy.sh rollback  # restore the most recent snapshot + restart
#   auto-deploy.sh status    # watermark, last run, timer state
#   auto-deploy.sh map FROM TO  # print components changed between two commits
#
# Intended to run from deploy/auto-deploy.timer (systemd, as the same user who
# runs proxy/deploy.sh manually). State lives in UPDATER_STATE_DIR
# (default /home/ntindle/.sparkvm-deploy), OUTSIDE the repo checkout, so an
# agent with checkout write access cannot rewire the updater's watermark,
# snapshots, or config without also holding the box shell.
#
# Env overrides (for tests): UPDATER_STATE_DIR, UPDATER_REPO, SWAPD_HOME,
# BIN_DIR, SYSTEMD_DIR, SKIP_SYSTEMCTL=1 (skip systemctl/restart calls),
# SKIP_SUDO=1 (run install steps without sudo), PINNED_UPSTREAM.

set -euo pipefail
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# --- configurable paths (env-overridable for tests) -------------------------
: "${UPDATER_STATE_DIR:=/home/ntindle/.sparkvm-deploy}"
: "${UPDATER_REPO:=$UPDATER_STATE_DIR/repo}"
: "${SWAPD_HOME:=/home/swapd}"
: "${BIN_DIR:=/usr/local/bin}"
: "${SYSTEMD_DIR:=/etc/systemd/system}"
: "${PINNED_UPSTREAM:=https://github.com/ntindle/spark-vm}"
: "${SKIP_SYSTEMCTL:=0}"
: "${SKIP_SUDO:=0}"

WATERMARK="$UPDATER_STATE_DIR/deployed-commit"
AUDIT_LOG="$UPDATER_STATE_DIR/audit.log"
LOCK_FILE="$UPDATER_STATE_DIR/auto-deploy.lock"
SNAPSHOT_DIR="$UPDATER_STATE_DIR/snapshots"
LAST_FAILURE="$UPDATER_STATE_DIR/last-failure"

# components.conf must be sourced AFTER the *_HOME vars exist, because its
# install_paths reference them.
# shellcheck source=components.conf
source "$SCRIPT_DIR/components.conf"

# --- helpers -----------------------------------------------------------------

log() { echo "[auto-deploy] $*" >&2; }

# bash var prefix for a component name: cred-ui -> cred_ui
vpre() { local c="$1"; echo "${c//-/_}"; }

# get_arr <component> <field>  -> prints array elements, one per line
get_arr() {
    local p; p="$(vpre "$1")"
    local -n arr="${p}_$2" 2>/dev/null || { echo "ERROR: unknown component/field: $1/$2" >&2; return 1; }
    printf '%s\n' "${arr[@]}"
}

# get_str <component> <field>
get_str() {
    local p; p="$(vpre "$1")"
    local var="${p}_$2"
    printf '%s' "${!var:-}"
}

audit() {
    # audit <event> <json-fields...>
    # Appends one JSON line: {"ts":..., "event":..., ...}. Never fails the run.
    local event="$1"; shift
    mkdir -p "$(dirname "$AUDIT_LOG")" 2>/dev/null || true
    local ts; ts="$(date -u +%FT%TZ)"
    # Subshell so a redirection failure (e.g. unwritable state dir) is silent
    # rather than noisy; the deploy flow treats audit as best-effort.
    ( printf '{"ts":"%s","event":"%s"%s}\n' "$ts" "$event" "$*" >>"$AUDIT_LOG" ) 2>/dev/null || true
}

alert() {
    # alert <reason> — persistent, visible failure record. The timer unit's
    # failure also lands in the journal; this file is the human-readable one.
    log "ALERT: $*"
    mkdir -p "$(dirname "$LAST_FAILURE")"
    printf '%s deploy failed: %s\n' "$(date -u +%FT%TZ)" "$*" >"$LAST_FAILURE"
}

sysctl() {
    # sysctl <args...> — systemctl unless SKIP_SYSTEMCTL=1 (tests).
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

# --- snapshot / rollback -------------------------------------------------------

snapshot_component() {
    # snapshot_component <component> <snapdir> — copy currently-installed files.
    local c="$1" snapdir="$2"
    local p rel
    while IFS= read -r p; do
        [ -n "$p" ] || continue
        # store under snapdir + absolute path, e.g. <snapdir>/home/swapd/swap_addon.py
        rel="$snapdir$p"
        if [ -e "$p" ]; then
            mkdir -p "$(dirname "$rel")"
            sudo_run cp -a "$p" "$rel"
            echo "$p" >>"$snapdir/MANIFEST"
        else
            echo "ABSENT $p" >>"$snapdir/MANIFEST"
        fi
    done < <(get_arr "$c" install_paths)
}

restore_snapshot() {
    # restore_snapshot <snapdir> — copy snapshot files back to their paths.
    local snapdir="$1"
    local line
    [ -f "$snapdir/MANIFEST" ] || { log "ERROR: no MANIFEST in $snapdir"; return 1; }
    while IFS= read -r line; do
        case "$line" in
            ABSENT\ *)
                local p="${line#ABSENT }"
                log "  removing $p (was absent at snapshot)"
                sudo_run rm -f "$p"
                ;;
            *)
                log "  restoring $line"
                sudo_run cp -a "$snapdir$line" "$line"
                ;;
        esac
    done <"$snapdir/MANIFEST"
}

# --- deploy steps ----------------------------------------------------------------

deploy_component() {
    # deploy_component <component> — install files, restart services, health-check.
    # Returns 0 on success (healthy), 1 otherwise (caller rolls back).
    local c="$1"
    log "deploying component: $c"

    case "$c" in
        proxy|confirm)
            # The shared deploy.sh installs proxy + confirm atomically and is
            # idempotent; --no-restart leaves service control to us so only
            # affected services bounce.
            log "  running proxy/deploy.sh --no-restart"
            if ! sudo_run bash "$UPDATER_REPO/proxy/deploy.sh" --no-restart; then
                log "  deploy.sh failed"
                return 1
            fi
            ;;
        cred-ui)
            log "  cred-ui runs from the checkout; deploy = restart only"
            ;;
        *)
            log "ERROR: no deploy steps defined for component $c — failing closed"
            return 1
            ;;
    esac

    local svc
    while IFS= read -r svc; do
        [ -n "$svc" ] || continue
        log "  restarting $svc"
        sysctl restart "$svc" || { log "  restart of $svc failed"; return 1; }
    done < <(get_arr "$c" services)

    while IFS= read -r svc; do
        [ -n "$svc" ] || continue
        log "  restarting user service $svc"
        sysctl --user restart "$svc" || { log "  user restart of $svc failed"; return 1; }
    done < <(get_arr "$c" user_services)

    health_check "$c"
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

# --- subcommands ---------------------------------------------------------------

cmd_init() {
    # One-time operator setup: create the mirror repo (never the working checkout).
    mkdir -p "$UPDATER_STATE_DIR"
    if [ -d "$UPDATER_REPO/.git" ]; then
        log "updater repo already exists at $UPDATER_REPO"
    else
        log "cloning $PINNED_UPSTREAM into $UPDATER_REPO"
        git clone "$PINNED_UPSTREAM" "$UPDATER_REPO"
    fi
    log "init done. Next: enable deploy/auto-deploy.timer (see README.md)."
}

pending_range() {
    # prints "old new" commit shas; returns 1 if nothing to do or not ready.
    [ -d "$UPDATER_REPO/.git" ] || { log "ERROR: updater repo missing — run '$0 init' first"; return 1; }
    check_upstream_pinned || return 1
    fetch_main || return 1
    local old new
    old="$(cat "$WATERMARK" 2>/dev/null || echo "")"
    new="$(git -C "$UPDATER_REPO" rev-parse origin/main)"
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
    for sha in "$old" "$new"; do
        if ! [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || ! git -C "$UPDATER_REPO" cat-file -e "$sha" 2>/dev/null; then
            log "ERROR: not a valid commit in updater repo: $sha — refusing to deploy"
            return 1
        fi
    done
    echo "$old $new"
}

cmd_check() {
    local range old new comps
    range="$(pending_range)" || return 0
    old="${range%% *}"; new="${range##* }"
    log "would deploy $old -> $new"
    comps="$(git -C "$UPDATER_REPO" diff --name-only "$old" "$new" | components_for_files)"
    if [ -z "$comps" ]; then
        log "no deployable components changed (pull-only changes)"
    else
        log "changed components:"
        echo "$comps" | while read -r c; do log "  - $c"; done
    fi
}

cmd_deploy() {
    mkdir -p "$UPDATER_STATE_DIR" "$SNAPSHOT_DIR"
    local range old new comps
    range="$(pending_range)" || { audit 'check' ',"result":"noop"'; return 0; }
    old="${range%% *}"; new="${range##* }"

    # Reset the mirror to the new commit (the mirror is never a working tree).
    git -C "$UPDATER_REPO" reset --hard -q "$new"

    local changed
    changed="$(git -C "$UPDATER_REPO" diff --name-only "$old" "$new")"
    comps="$(printf '%s\n' "$changed" | components_for_files)"

    if [ -z "$comps" ]; then
        log "no deployable components changed — advancing watermark only"
        echo "$new" >"$WATERMARK"
        audit 'deploy' ',"result":"pull-only","from":"$old","to":"$new"'
        return 0
    fi
    log "deploying $old -> $new; components: $(echo "$comps" | tr '\n' ' ')"

    # 1. gates BEFORE any mutation
    local c
    for c in $comps; do
        run_gates "$c" || {
            alert "pre-deploy gate failed for component $c ($old -> $new)"
            audit 'deploy' ',"result":"gate-fail","from":"$old","to":"$new","component":"$c"'
            return 1
        }
    done

    # 2. snapshot for rollback
    local snapdir="$SNAPSHOT_DIR/$new"
    rm -rf "$snapdir"; mkdir -p "$snapdir"
    echo "$old" >"$snapdir/FROM_COMMIT"
    for c in $comps; do snapshot_component "$c" "$snapdir"; done
    log "snapshot saved to $snapdir"

    # 3. deploy each component; on any failure roll everything back
    for c in $comps; do
        deploy_component "$c" || {
            alert "deploy failed for component $c ($old -> $new) — rolling back"
            audit 'deploy' ',"result":"deploy-fail","from":"$old","to":"$new","component":"$c"'
            restore_snapshot "$snapdir"
            for c2 in $comps; do
                local svc
                while IFS= read -r svc; do
                    [ -n "$svc" ] || continue
                    sysctl restart "$svc" || true
                done < <(get_arr "$c2" services)
                while IFS= read -r svc; do
                    [ -n "$svc" ] || continue
                    sysctl --user restart "$svc" || true
                done < <(get_arr "$c2" user_services)
            done
            audit 'deploy' ',"result":"rolled-back","from":"$old","to":"$new"'
            return 1
        }
    done

    # 4. success: advance watermark, prune old snapshots (keep 5), audit
    echo "$new" >"$WATERMARK"
    (cd "$SNAPSHOT_DIR" && ls -t | tail -n +6 | xargs -r rm -rf)
    rm -f "$LAST_FAILURE"
    audit 'deploy' ',"result":"ok","from":"'"$old"'","to":"'"$new"'","components":"'"$(echo "$comps" | tr '\n' ' ' | xargs)"'"'
    log "deployed $new — components: $(echo "$comps" | tr '\n' ' ')"
}

cmd_rollback() {
    local snapdir
    snapdir="$(ls -td "$SNAPSHOT_DIR"/*/ 2>/dev/null | head -1 || true)"
    [ -n "$snapdir" ] || { log "ERROR: no snapshots to roll back to"; return 1; }
    log "rolling back to snapshot $snapdir"
    restore_snapshot "$snapdir"
    local from; from="$(cat "$snapdir/FROM_COMMIT" 2>/dev/null || echo unknown)"
    echo "$from" >"$WATERMARK"
    audit 'rollback' ',"result":"manual-rollback","to":"$from","snapshot":"$snapdir"'
    log "rolled back; watermark now $from. Restart affected services manually if needed."
}

cmd_status() {
    echo "state dir:  $UPDATER_STATE_DIR"
    echo "watermark:  $(cat "$WATERMARK" 2>/dev/null || echo '(none)')"
    echo "audit log:  $AUDIT_LOG ($(wc -l <"$AUDIT_LOG" 2>/dev/null || echo 0) lines)"
    echo "snapshots:  $(ls "$SNAPSHOT_DIR" 2>/dev/null | wc -l)"
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
        rollback) cmd_rollback ;;
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
