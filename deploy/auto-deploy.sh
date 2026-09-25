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
#   auto-deploy.sh rollback [--no-block]  # restore the newest snapshot + restart;
#                                        # marks the rolled-back commit blocked
#                                        # unless --no-block
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
VERSION_STATE="$UPDATER_STATE_DIR/deployed-version"
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

sudo_stat_path() {
    # sudo_stat_path <path> — privileged existence check, tri-state:
    #   0  path exists (file/dir/symlink; dangling symlinks included)
    #   1  path is absent
    #   2  the check itself errored (broken sudo / check infrastructure) — NOT "absent"
    #
    # The 1-vs-2 distinction is the rollback-safety fix (issue #107):
    # a broken sudo in production makes every check fail, and recording
    # such a path ABSENT (snapshot) or silently skipping its removal
    # (restore) corrupts the snapshot/rollback contract — callers must
    # fail loud on rc=2. Distinguishing signal: `test` prints nothing and
    # never exits >1 on a well-formed call, so stderr content or rc>1
    # means the check infrastructure errored, not "absent". Scoped
    # honestly: a silent-EACCES path (unprivileged box, e.g. literal
    # /etc/sudoers.d/swapd) still reads as absent — that is the existing
    # unprivileged-box contract (same privilege the copy/removal uses),
    # not a new gap. stderr on a *succeeding* check is ignored (noisy-but-
    # working sudo can't false-positive). Note for future callers: only
    # wrap commands whose stderr cannot carry secret material here —
    # sudo's own diagnostics ("a password is required") carry none.
    # (Narrow caveat: a sudo lecture printed to stderr on a failing check
    # reads as "errored" — fail-closed, the safe side here.)
    local p="$1" out rc
    if out="$(sudo_run test -e "$p" 2>&1)"; then
        return 0
    else
        rc=$?
        if [ -n "$out" ] || [ "$rc" -gt 1 ]; then
            log "ERROR: existence check for $p errored (rc=$rc): $out"
            return 2
        fi
    fi
    if out="$(sudo_run test -L "$p" 2>&1)"; then
        return 0
    else
        rc=$?
        if [ -n "$out" ] || [ "$rc" -gt 1 ]; then
            log "ERROR: symlink check for $p errored (rc=$rc): $out"
            return 2
        fi
    fi
    return 1
}

tcp_ok() {
    # tcp_ok host port — true if something accepts a TCP connection.
    local host="$1" port="$2"
    (exec 3<>/dev/tcp/"$host"/"$port") 2>/dev/null
}

resolve_health_host() {
    # resolve_health_host <host> — the literal host, except the TAILNET token
    # which resolves to this box's current tailnet IPv4 at check time. A
    # pinned tailnet IP goes stale on rekey and turns every later deploy
    # into a false health failure (rollback of a good deploy + blocked
    # commit); resolving at check time keeps the health check honest.
    # Prints the host, or nothing when TAILNET cannot be resolved.
    local host="$1"
    if [ "$host" = "TAILNET" ]; then
        # The || true matters: auto-deploy.sh runs under set -e with
        # pipefail, so a failing tailscale must yield empty here (the
        # caller fails the health check closed), not abort the script.
        tailscale ip -4 2>/dev/null | head -1 | tr -d '[:space:]' || true
        return 0
    fi
    printf '%s' "$host"
}

write_watermark() {
    # Atomic watermark update: a torn write must never strand the updater.
    printf '%s\n' "$1" >"$WATERMARK.tmp" && mv -f "$WATERMARK.tmp" "$WATERMARK"
}

write_version() {
    # Atomic deployed-version update (docs/VERSIONING.md): same torn-write
    # reasoning as the watermark — a half-written version file would lie
    # about which release is actually deployed.
    printf '%s\n' "$1" >"$VERSION_STATE.tmp" && mv -f "$VERSION_STATE.tmp" "$VERSION_STATE"
}

# Strict semver (mirrors scripts/sparkvm_version.py). VERSION is
# attacker-influenced — merged PRs feed new_version(), the deployed
# standalone copy at $SWAPD_HOME/VERSION is swapd-writable and feeds the
# rollback paths — and the result is interpolated raw into audit JSON.
# Never let unvalidated bytes near an audit line.
_semver_re='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-([0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*))?(\+([0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*))?$'
clean_version() {
    # clean_version <candidate>: print it iff strict semver, else "unknown".
    local v="${1%%$'\n'*}"
    if [[ "$v" =~ $_semver_re ]]; then printf '%s' "$v"; else printf 'unknown'; fi
}

deployed_version() {
    # The VERSION the updater last deployed ("unknown" when nothing has
    # recorded one yet, or the recorded bytes are not valid semver).
    clean_version "$(cat "$VERSION_STATE" 2>/dev/null || echo unknown)"
}

new_version() {
    # The VERSION stamped in the mirror at the commit being deployed.
    clean_version "$(cat "$UPDATER_REPO/VERSION" 2>/dev/null || echo unknown)"
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
    # A path entry ending in "/" is a directory prefix; a bare entry (e.g.
    # "VERSION") matches that exact file only — so docs/VERSIONING.md and any
    # other top-level VERSION* path do not trigger on the VERSION entry.
    local f c pfx
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        for c in "${COMPONENTS[@]}"; do
            while IFS= read -r pfx; do
                if [[ "$pfx" == */ ]]; then
                    if [[ "$f" == "$pfx"* ]]; then echo "$c"; break; fi
                elif [[ "$f" == "$pfx" ]]; then
                    echo "$c"; break
                fi
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
    # Version stamping (docs/VERSIONING.md): the root VERSION file travels
    # with every checkout sync, so it gets the same fail-closed treatment.
    if [ -e "$WORKING_CHECKOUT/VERSION" ] && [ -n "$(git -C "$WORKING_CHECKOUT" status --porcelain -- VERSION)" ]; then
        log "  $c: uncommitted changes in $WORKING_CHECKOUT/VERSION — refusing to overwrite (commit or stash first)"
        return 1
    fi
    if ! git -C "$UPDATER_REPO" cat-file -e "$new:$sub" 2>/dev/null; then
        log "  $c: subtree $sub not present at $new — FAIL CLOSED"
        return 1
    fi
    if ! git -C "$UPDATER_REPO" cat-file -e "$new:VERSION" 2>/dev/null; then
        log "  $c: VERSION not present at $new — FAIL CLOSED"
        return 1
    fi
    return 0
}

# --- snapshot / rollback -------------------------------------------------------

snapshot_component() {
    # snapshot_component <component> <snapdir> — copy currently-installed
    # files and checkout-synced subtrees.
    local c="$1" snapdir="$2"
    local p rel sub dest st
    while IFS= read -r p; do
        [ -n "$p" ] || continue
        # store under snapdir + absolute path, e.g. <snapdir>/home/swapd/swap_addon.py
        rel="$snapdir$p"
        # Existence goes through sudo_stat_path (same privilege the copy
        # would use): on an unprivileged box a literal system path (e.g.
        # /etc/sudoers.d/swapd) may not even be stat-able, and must be
        # recorded ABSENT rather than failing the snapshot. The `test -L`
        # disjunct keeps dangling symlinks snapshot-covered (`test -e` is
        # false for them; `cp -a` preserves the link itself). rc=2 (the
        # privilege check itself errored — e.g. broken sudo) fails the
        # snapshot LOUD (#107): recording such a path ABSENT would
        # silently drop a live file from the rollback manifest.
        if sudo_stat_path "$p"; then st=0; else st=$?; fi
        if [ "$st" -eq 2 ]; then
            log "ERROR: cannot snapshot $p — privilege check errored"
            return 1
        elif [ "$st" -eq 0 ]; then
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
        # Version stamping (docs/VERSIONING.md): the root VERSION file is
        # synced alongside the subtree (see install_component) — snapshot it
        # too, or a rollback leaves the new VERSION under the old code.
        vdest="$WORKING_CHECKOUT/VERSION"
        if [ -e "$vdest" ]; then
            mkdir -p "$snapdir/checkout-$(vpre "$c")" || {
                log "ERROR: cannot create checkout snapshot dir for $c"; return 1; }
            cp -a "$vdest" "$snapdir/checkout-$(vpre "$c")/" || {
                log "ERROR: checkout VERSION snapshot of $vdest failed"; return 1; }
            echo "CHECKOUT $c VERSION" >>"$snapdir/MANIFEST"
        else
            echo "CHECKOUT-ABSENT $c VERSION" >>"$snapdir/MANIFEST"
        fi
    fi
    return 0
}

restore_snapshot() {
    # restore_snapshot <snapdir> — copy snapshot files back to their paths.
    # Returns nonzero on any failure (caller must NOT report success).
    local snapdir="$1"
    local line rc=0 st
    [ -f "$snapdir/MANIFEST" ] || { log "ERROR: no MANIFEST in $snapdir"; return 1; }
    while IFS= read -r line; do
        case "$line" in
            ABSENT\ *)
                local p="${line#ABSENT }"
                # #103: an empty path is a corrupt manifest line — the
                # snapshot writer skips empties, so only a hand-edited or
                # damaged MANIFEST produces one. Fail loud, mirroring the
                # CHECKOUT-ABSENT guard: the old code silently skipped with
                # rc=0 since both tests fail on "".
                if [ -z "$p" ]; then
                    log "  corrupt MANIFEST ABSENT line (empty path): $line"
                    rc=1
                    continue
                fi
                # Existence is checked through sudo_stat_path (same privilege
                # the removal would use): on an unprivileged box the manifest
                # can carry literal system paths (e.g. /etc/sudoers.d/swapd)
                # whose parent dir is not even stat-able — `rm -f` then dies
                # with Permission denied on a file that was never there,
                # failing the whole rollback. In production the timer runs
                # privileged, so the check sees exactly what the removal
                # would touch: no behavior change there. #107: rc=2 means the
                # privilege check itself errored (e.g. broken sudo) —
                # silently skipping removal could strand a deploy-installed
                # file, so mark the rollback failed and keep restoring.
                # The helper's `test -L` disjunct covers dangling symlinks
                # (`test -e` is false for them): a deploy-created dangling
                # symlink at an ABSENT path must still be unlinked on
                # rollback, exactly as the old unconditional `rm -f` did.
                # `rm -f` unlinks only the symlink, never its target.
                if sudo_stat_path "$p"; then st=0; else st=$?; fi
                if [ "$st" -eq 0 ]; then
                    log "  removing $p (was absent at snapshot)"
                    sudo_run rm -f "$p" || rc=1
                elif [ "$st" -eq 2 ]; then
                    log "  ERROR: cannot verify $p — refusing to skip removal silently"
                    rc=1
                else
                    log "  $p still absent (or not visible) — nothing to remove"
                fi
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
                if [ -z "$sub2" ]; then
                    log "  corrupt MANIFEST CHECKOUT-ABSENT line (empty subtree): $line"
                    rc=1
                    continue
                fi
                log "  removing $WORKING_CHECKOUT/$sub2 (was absent at snapshot)"
                rm -rf "${WORKING_CHECKOUT:?}/${sub2:?}" || rc=1
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
    # Return contract: 0 = installed; 1 = install failed (caller rolls back);
    # 2 = the pre-destruction checkout re-check failed (issue #324). The
    # caller must fail closed WITHOUT marking the commit blocked (the commit
    # is not bad; the checkout is dirty) — but anything already installed in
    # this run, including this component's own install step (which runs
    # before the re-check below), must still be rolled back; the caller owns
    # that (see cmd_deploy's no_block rollback).
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
        # Issue #324: re-run the checkout-sync preconditions at the moment of
        # destruction, not just at gate time. The single-flight lock
        # serializes auto-deploy runs against each other, not against
        # operators: a manual edit (or another agent job) to the working
        # checkout in the gate→install window (snapshots run between them)
        # would otherwise be silently clobbered by the rm -rf below — or land
        # mid-tar and leave a half-synced subtree under a health-checked
        # service. The check is two `git status --porcelain` calls plus two
        # `cat-file -e` lookups — cheap enough to close the window without a
        # lock protocol operators would also have to learn and take.
        # Distinct return code 2 (see the docstring contract): the subtree
        # sync itself has not run, but this component's install step (above)
        # may already have mutated the box — the caller rolls back on 2.
        check_checkout_sync_ready "$c" "$sub" "$new" || return 2
        rm -rf "${WORKING_CHECKOUT:?}/${sub:?}" || return 1
        if ! git -C "$UPDATER_REPO" archive "$new" "$sub" | tar -x -C "$WORKING_CHECKOUT"; then
            log "  $c: subtree sync FAILED"
            return 1
        fi
        # Version stamping (docs/VERSIONING.md): the component resolves the
        # repo VERSION by walking up from the working checkout, so the root
        # VERSION file must travel with the sync — a version-only deploy
        # otherwise leaves it reporting the old release.
        log "  $c: syncing VERSION from mirror@$new into $WORKING_CHECKOUT"
        if ! git -C "$UPDATER_REPO" archive "$new" VERSION | tar -x -C "$WORKING_CHECKOUT"; then
            log "  $c: VERSION sync FAILED"
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
        # #323: parse port as the trailing :digits field; host is everything
        # between tcp: and that field. The naive middle/last-colon split
        # silently accepted non-numeric "ports" into tcp_ok (e.g.
        # tcp:host:abc — bash /dev/tcp resolves service names, so a
        # typo'd "port" could dial an unintended service) and let
        # missing-port entries (tcp:host) through unparsed. Malformed
        # entries now fail closed instead of probing garbage endpoints.
        if [[ "$h" =~ ^tcp:(.*):([0-9]+)$ ]]; then
            host="${BASH_REMATCH[1]}"; port="${BASH_REMATCH[2]}"
        else
            log "  health: malformed tcp check '$h' — expected tcp:HOST:PORT"
            return 1
        fi
        # #323: an empty host (tcp::8080) passes the regex but is not a
        # real endpoint — reject it at parse time rather than letting it
        # masquerade as a tailnet resolution failure below.
        if [ -z "$host" ]; then
            log "  health: malformed tcp check '$h' — empty host"
            return 1
        fi
        host="$(resolve_health_host "$host")"
        if [ -z "$host" ]; then
            log "  health: could not resolve tailnet IP for $h"
            return 1
        fi
        log "  health: tcp $host:$port ..."
        local attempt ok=0
        for attempt in $(seq 1 20); do
            if tcp_ok "$host" "$port"; then ok=1; break; fi
            sleep 0.5
        done
        if [ "$ok" != "1" ]; then
            log "  health: tcp $host:$port FAILED after $attempt tries"
            return 1
        fi
    done < <(get_arr "$c" health)
    log "  health: $c OK"
    return 0
}

# --- rollback driver -------------------------------------------------------------

sync_version_from_deployed() {
    # sync_version_from_deployed — re-derive the updater's deployed-version
    # from the installed standalone VERSION file. Used after rollbacks, which
    # restore the old installed files: the updater state must agree with
    # what is actually on disk (docs/VERSIONING.md). Prints the new value.
    # Sanitized: the deployed copy is swapd-writable and attacker-influenced.
    local v; v="$(clean_version "$(cat "$SWAPD_HOME/VERSION" 2>/dev/null || echo unknown)")"
    write_version "$v"
    printf '%s' "$v"
}

do_rollback() {
    # do_rollback <snapdir> <old> <new> <failed-component> <phase> [no_block]
    # Restore the snapshot, restart + health-check. Unless no_block is set,
    # mark the commit blocked so the next tick does not retry-loop it.
    # no_block is for aborts where the commit itself is fine (issue #324's
    # checkout-dirty abort): the audit entries still fire, but BLOCKED_COMMIT
    # is never written — not even if the rollback itself fails (the alert
    # already screams for operator intervention; a good commit must not be
    # blocked). Always returns 1 (deploy failed).
    local snapdir="$1" old="$2" new="$3" failed_c="$4" phase="$5" no_block="${6:-}"
    local c
    if [ -n "$no_block" ]; then
        alert "checkout-dirty abort for component $failed_c ($old -> $new) — rolling back already-installed components (commit or stash first)"
    else
        alert "deploy $phase failed for component $failed_c ($old -> $new) — rolling back"
    fi
    audit 'deploy' ',"result":"deploy-fail","from":"'"$old"'","to":"'"$new"'","component":"'"$failed_c"'","phase":"'"$phase"'"'
    if ! restore_snapshot "$snapdir"; then
        alert "ROLLBACK FAILED for $new — box may be half-deployed, operator intervention required"
        audit 'deploy' ',"result":"rollback-failed","from":"'"$old"'","to":"'"$new"'"'
        if [ -z "$no_block" ]; then
            printf '%s\n' "$new" >"$BLOCKED_COMMIT.tmp" && mv -f "$BLOCKED_COMMIT.tmp" "$BLOCKED_COMMIT"
        fi
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
    if [ -z "$no_block" ]; then
        printf '%s\n' "$new" >"$BLOCKED_COMMIT.tmp" && mv -f "$BLOCKED_COMMIT.tmp" "$BLOCKED_COMMIT"
    fi
    # The restored snapshot reverted the deployed standalone files, so the
    # deployed version is whatever the restored VERSION file says.
    local rbv; rbv="$(sync_version_from_deployed)"
    audit 'deploy' ',"result":"rolled-back","from":"'"$old"'","to":"'"$new"'","to_version":"'"$rbv"'"'
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
    record_updater_source
    log "installed updater to $INSTALLED_BIN (timer ExecStart must point here)"
    log "init done. Next: install the systemd unit + timer (see README.md)."
}

record_updater_source() {
    # Record which checkout commit the installed updater copy came from, so
    # status/check can warn when the timer runs stale code: merging a fix to
    # auto-deploy.sh or components.conf does NOT take effect until init is
    # re-run (README "known limitations"), and nothing used to say so.
    # Best-effort: "unknown" when the updater wasn't installed from a git
    # checkout (then drift checks stay quiet).
    local sha
    sha="$(git -C "$SCRIPT_DIR/.." rev-parse HEAD 2>/dev/null || echo unknown)"
    printf '%s\n' "$sha" >"$UPDATER_STATE_DIR/updater-source-commit" 2>/dev/null || true
}

check_updater_drift() {
    # Warn when origin/main contains deploy/ changes newer than the commit
    # the installed updater copy came from -- i.e. merged updater fixes that
    # are not live because nobody re-ran init. Quiet when the source commit
    # is unknown or the histories are unrelated (test fixtures).
    local src cur
    src="$(cat "$UPDATER_STATE_DIR/updater-source-commit" 2>/dev/null || echo unknown)"
    cur="$(git -C "$UPDATER_REPO" rev-parse origin/main 2>/dev/null || echo unknown)"
    [ "$src" != "unknown" ] && [ "$cur" != "unknown" ] && [ "$src" != "$cur" ] || return 0
    git -C "$UPDATER_REPO" merge-base --is-ancestor "$src" "$cur" 2>/dev/null || return 0
    git -C "$UPDATER_REPO" diff --quiet "$src" "$cur" -- deploy/ 2>/dev/null && return 0
    log "WARNING: updater code is stale: installed copy came from $src,"
    log "WARNING: origin/main $cur carries newer deploy/ changes that are NOT live."
    log "WARNING: re-run './deploy/auto-deploy.sh init' from an updated checkout."
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
    check_updater_drift
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
        # The timer only ever runs `deploy`, so this is where the stale-updater
        # warning surfaces on the automated path (`check`/`status` warn too;
        # the quiet up-to-date tick deliberately stays quiet).
        check_updater_drift
        write_watermark "$new"
        local pnv pov; pnv="$(new_version)"; pov="$(deployed_version)"
        write_version "$pnv"
        audit 'deploy' ',"result":"pull-only","from":"'"$old"'","to":"'"$new"'","to_version":"'"$pnv"'","from_version":"'"$pov"'"'
        return 0
    fi
    # Components sharing an install unit deploy together (proxy+confirm share
    # deploy.sh, which installs both unconditionally).
    expand_install_unit COMPS
    log "deploying $old -> $new; components: ${COMPS[*]}"
    # The drift check belongs here, not on the quiet noop tick: a pending
    # deploy is exactly when stale updater logic is most dangerous, and the
    # timer never runs `check` or `status`.
    check_updater_drift

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
    local irc installed_any=0
    for c in "${COMPS[@]}"; do
        log "deploying component: $c"
        # NOTE: plain `install_component ...; irc=$?` is dead code under
        # set -e — the shell exits before irc=$? runs (see cmd_check). The
        # `if` condition suppresses errexit so irc is captured.
        if install_component "$c" "$new"; then irc=0; else irc=$?; fi
        if [ "$irc" -eq 2 ]; then
            # Issue #324: the working checkout gained uncommitted changes (or
            # stopped being a usable git checkout) between the gate phase and
            # the install phase. The commit is not bad, so it is NEVER marked
            # blocked — the next tick retries once the operator commits or
            # stashes. But components already installed in this run (or this
            # component's own install step, which runs BEFORE the re-check
            # inside install_component) may have mutated the box, so roll
            # those back first — otherwise the box drifts half-deployed until
            # the next tick. do_rollback's no_block mode restores the snapshot
            # without writing BLOCKED_COMMIT; the watermark stays untouched.
            alert "checkout changed during deploy for component $c ($old -> $new) — refusing to overwrite (commit or stash first)"
            audit 'deploy' ',"result":"checkout-dirty","from":"'"$old"'","to":"'"$new"'","component":"'"$c"'"'
            if [ "$installed_any" -eq 1 ] || [ -n "$(get_str "$c" install)" ]; then
                do_rollback "$snapdir" "$old" "$new" "$c" "checkout-dirty" "no_block"
            fi
            return 1
        fi
        [ "$irc" -eq 0 ] || { do_rollback "$snapdir" "$old" "$new" "$c" "install"; return 1; }
        installed_any=1
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

    # 6. success: advance watermark, record deployed version, clear any
    # block, prune, audit
    write_watermark "$new"
    local nv ov; nv="$(new_version)"; ov="$(deployed_version)"
    write_version "$nv"
    rm -f "$BLOCKED_COMMIT" "$LAST_FAILURE"
    prune_snapshots
    local complist; complist="$(printf '%s\n' "${COMPS[@]}" | tr '\n' ' ' | xargs)"
    audit 'deploy' ',"result":"ok","from":"'"$old"'","to":"'"$new"'","components":"'"$complist"'","to_version":"'"$nv"'","from_version":"'"$ov"'"'
    log "deployed $new ($nv) — components: $complist"
}

cmd_rollback() {
    # cmd_rollback [--no-block] — restore the newest snapshot.
    # Marks the rolled-back commit blocked so the next timer tick does not
    # retry-loop it (issue #325): the commit being rolled back FROM is the
    # pre-rollback watermark (the deployed head). --no-block skips the mark
    # for the investigate-not-condemn case — the same semantics as
    # do_rollback's no_block (issue #324: the commit itself is fine).
    # The block auto-clears in pending_range once a newer commit supersedes
    # the blocked one; `status` tells the operator how to clear it by hand
    # for the re-deploy-the-same-tree case.
    local no_block=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --no-block) no_block=1 ;;
            *) log "ERROR: unknown rollback flag '$1'"; return 1 ;;
        esac
        shift
    done
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
    # The commit being rolled back FROM is the pre-rollback watermark —
    # capture it before the watermark is rewound to `from`.
    local rolled_from; rolled_from="$(cat "$WATERMARK" 2>/dev/null || true)"
    write_watermark "$from"
    local rbv; rbv="$(sync_version_from_deployed)"
    # Issue #325: block the rolled-back commit so the next tick does not
    # redeploy it. An empty watermark, or one already sitting at `from`
    # (nothing was ever deployed past it), means there is no bad commit to
    # block — writing `from` there would pin the updater on its own
    # watermark head, so skip the mark instead of blocking blindly.
    # The mark lands even when the restored components are unhealthy: the
    # watermark was already rewound, so the retry-loop hazard is identical
    # (the alert below already screams for the operator).
    local blocked_wrote="none"
    if [ -z "$no_block" ] && [ -n "$rolled_from" ] && [ "$rolled_from" != "$from" ]; then
        printf '%s\n' "$rolled_from" >"$BLOCKED_COMMIT.tmp" && mv -f "$BLOCKED_COMMIT.tmp" "$BLOCKED_COMMIT"
        blocked_wrote="$rolled_from"
        log "marked rolled-back commit $rolled_from blocked (next tick will not retry it)"
    elif [ -z "$no_block" ]; then
        log "not marking a commit blocked: watermark was empty or already at $from"
    fi
    if [ "$unhealthy" -eq 1 ]; then
        alert "manual rollback to $from completed but a component is unhealthy"
        audit 'rollback' ',"result":"rollback-unhealthy","to":"'"$from"'","rolled_back_from":"'"$rolled_from"'","blocked":"'"$blocked_wrote"'","snapshot":"'"$snapdir"'"'
        return 1
    fi
    audit 'rollback' ',"result":"manual-rollback","to":"'"$from"'","rolled_back_from":"'"$rolled_from"'","blocked":"'"$blocked_wrote"'","snapshot":"'"$snapdir"'","to_version":"'"$rbv"'"'
    log "rolled back; watermark now $from; version now $rbv; services restarted + healthy"
}

cmd_status() {
    echo "state dir:  $UPDATER_STATE_DIR"
    echo "watermark:  $(cat "$WATERMARK" 2>/dev/null || echo '(none)')"
    echo "deployed version: $(deployed_version)"
    echo "blocked:    $(cat "$BLOCKED_COMMIT" 2>/dev/null || echo '(none)')"
    if [ -f "$BLOCKED_COMMIT" ]; then
        # Issue #325: the operator may need to re-deploy the blocked tree
        # after a manual fix — tell them exactly how to clear the mark.
        echo "  clear with: rm \"$BLOCKED_COMMIT\" (the mark auto-clears on the next newer commit)"
    fi
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
    check_updater_drift
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
            cmd_rollback "${@:2}"
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
