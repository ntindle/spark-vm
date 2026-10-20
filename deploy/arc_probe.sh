#!/bin/bash
# deploy/arc_probe.sh — shared active-arc (agent-session) probes.
#
# Read-only detection of live agent work on this box: (1) live `mjob-*`
# tmux sessions on each agent user's own server, (2) non-terminal muse-job
# registry records. First shipped for the toolset updater's idle gate
# (issue #532); the box-side rollout path (deploy/auto-deploy.sh,
# never-interrupt-an-arc, G15 §6 / issue #1808) consumes the same
# primitives so "an active arc" means the same thing in both lanes.
#
# Sourcing contract: functions only, no side effects at source time beyond
# the TMUX_RESOLVED assignment. These probes never log — they return
# status and print data lines; the caller logs. They never execute user
# code: tmux is asked only for session names (fixed argv, absolute binary
# path) and registry records are parsed as data, never executed.
#
# Env: TMUX_BIN (tmux binary override; default `tmux`).

# Resolve the probe tmux to an absolute path once: the per-user probe
# executes it as another uid, where a PATH-relative name would invite PATH
# hijacking. Falls back to the name itself when unresolvable (the probe
# then degrades to the registry half, documented below).
TMUX_RESOLVED="$(command -v "${TMUX_BIN:-tmux}" 2>/dev/null || printf '%s' "${TMUX_BIN:-tmux}")"

# Probe primitives (verbatim from deploy/toolset-update.sh's idle gate,
# issue #532 — kept byte-identical here so the two lanes stay one
# implementation). A tmux probe that fails for reasons other than the
# identity switch reads as no-sessions for that half, with the registry
# probe as the independent backstop.
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
    # `--`: a dash-prefixed user must not inject an id option (same
    # fail-open class as the cua-driver probe boundary, issue #1252).
    target="$(id -u -- "$user" 2>/dev/null || true)"
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
    # record. Issue #11: records moved out of the job dir to
    # ~/.local/share/muse-job/jobs/<slug>.json; the scan covers BOTH the
    # metadata dir (derived from <jobsdir>'s parent) and the legacy
    # <jobsdir>/*/job.json location (pre-#11 jobs the manager has not
    # touched yet). The metadata record wins a slug present in both.
    # Returns 0 when at least one record is non-terminal, 1 when the estate
    # is idle, 2 when the scan itself failed (fail-closed upstream).
    # Non-terminal: active, blocked.
    # Terminal: killed, closed, done. Anything else — missing state,
    # unparseable value, an unrecognized future state — is busy
    # (fail-closed). Read-only: records are parsed as data, never executed.
    # The scan runs as the invoking uid (root under the timer) — the parse
    # is data-only, so no user content executes with privilege; the only
    # output is the busy/idle bit plus slug:state lines in the (sanitized)
    # run log.
    local jobsdir="$1"
    local metadir
    metadir="$(dirname "$jobsdir")/.local/share/muse-job/jobs"
    [ -d "$jobsdir" ] || [ -d "$metadir" ] || return 1
    if command -v python3 >/dev/null 2>&1; then
        local out rc=0
        out="$(python3 -c '
import json, os, sys
jobsdir, metadir = sys.argv[1], sys.argv[2]
seen = set()
candidates = []
def scan(dirpath, legacy):
    try:
        names = sorted(os.listdir(dirpath))
    except OSError:
        # A present-but-unlistable dir is a scan failure (fail-closed),
        # mirroring the pre-#11 behavior; a missing dir is just absent.
        if os.path.isdir(dirpath):
            sys.exit(2)
        return
    for name in names:
        if legacy:
            slug, p = name, os.path.join(dirpath, name, "job.json")
        else:
            if not name.endswith(".json") or len(name) <= 5:
                continue
            slug, p = name[:-5], os.path.join(dirpath, name)
        if slug in seen or not os.path.isfile(p):
            continue
        seen.add(slug)
        candidates.append((slug, p))
scan(metadir, False)   # issue #11 location first: wins a slug present in both
scan(jobsdir, True)    # legacy in-tree location
for slug, p in candidates:
    try:
        with open(p) as fh:
            d = json.load(fh)
    except OSError:
        # Vanished between listdir and open (the tmp+rename write pattern
        # means readers never see a torn file) — not evidence of a live job.
        continue
    except ValueError:
        # Unparseable record: fail closed — a corrupt record for a live
        # job must never read as idle.
        print("%s:unparseable" % slug)
        continue
    state = d.get("state") if isinstance(d, dict) else None
    if state not in ("killed", "closed", "done"):
        print("%s:%s" % (slug, state))
' "$jobsdir" "$metadir" 2>/dev/null)" || rc=$?
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
    local d slug states rest first busy=0 f seen
    seen=""
    # Per-record scan shared by both locations below.
    _scan_one() { # <slug> <file>
        local s="$1" f2="$2" states rest first
        states="$(grep -o '"state"[[:space:]]*:[[:space:]]*"[^"]*"' \
            "$f2" 2>/dev/null | cut -d'"' -f4 || true)"
        # No parseable state at all: fail closed (a corrupt record must
        # never read as idle). NB: command substitution strips trailing
        # newlines, so an empty $states would otherwise vanish here.
        if [ -z "$states" ]; then
            printf '%s:unparseable\n' "$s"
            busy=1
            return
        fi
        # Strip the terminal states; whatever survives — a non-terminal
        # value — is busy. (A nested "done" can never mask a live
        # top-level state: ANY non-terminal value defers.)
        rest="$(printf '%s\n' "$states" | grep -Ev '^(killed|closed|done)$' || true)"
        if [ -n "$rest" ]; then
            first="$(printf '%s' "$rest" | grep -v '^$' | head -n 1 || true)"
            printf '%s:%s\n' "$s" "${first:-unparseable}"
            busy=1
        fi
    }
    # Issue #11 location first: a slug present in both locations is
    # decided by the metadata record (mirrors the python path's dedup).
    for f in "$metadir"/*.json; do
        [ -f "$f" ] || continue
        slug="$(basename "$f" .json)"
        seen="${seen}${slug}
"
        _scan_one "$slug" "$f"
    done
    # Legacy location (pre-#11): <jobsdir>/*/job.json
    for d in "$jobsdir"/*/; do
        [ -d "$d" ] || continue
        [ -f "${d}job.json" ] || continue
        slug="$(basename "$d")"
        # Skip when the metadata dir already decided this slug (fixed-string
        # whole-line match: a slug is one line of the seen list).
        if printf '%s' "$seen" | grep -Fxq "$slug"; then
            continue
        fi
        _scan_one "$slug" "${d}job.json"
    done
    [ "$busy" = "1" ] && return 0
    return 1
}
