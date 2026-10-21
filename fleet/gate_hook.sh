#!/usr/bin/env bash
# fleet/gate_hook.sh — S1b hook-loop tick for the G18 release-gating channel.
#
# The latency optimizer + local-status writer of
# docs/RELEASE_GATE_CHANNEL_DESIGN.md §3: runs `gate_query.py state` and
# writes the box's self-evaluated answer to the local gate status file, so
# a frozen or gate-stale fleet is *visible* degraded operation — never
# silent drift. G15 §5's "gate-answer age/source" is the status file's
# generated_at + source fields; readers derive staleness as now -
# generated_at ("last good answer T ago").
#
# NOT the enforcement point: the update tick's own re-query enforces (§3).
# A frozen fleet is a *signal*, not a hook failure — the hook exits 0
# whenever the status file was written, and non-zero only when the write
# itself failed (then the timer goes red and the journal says why).
#
# Identity/keys/gate resolve exactly like gate_query.py: flags
# --box-id/--box-id-file/--keys/--gate or SPARKVM_BOX_ID(/_FILE)/
# SPARKVM_GATE_KEYS/SPARKVM_GATE_JSON env. Extra hook-only inputs:
# --status-file PATH or SPARKVM_GATE_STATUS (default
# /var/lib/sparkvm/gate/status.json). All other arguments pass through to
# gate_query.py untouched.
#
# Trust: runs as root from the INSTALLED copy
# (/home/ntindle/.sparkvm-deploy/bin/gate_hook.sh — installed by
# `deploy/auto-deploy.sh init`, same discipline as gate_query.py: re-run
# init to refresh). Never prints key material — gate_query.py never does,
# and the status file carries only the evaluated answer. The journal
# summary line is control-character scrubbed (the S1a log-channel rule:
# client/operator-controlled strings never reach a terminal raw).
set -euo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUERY="$HOOK_DIR/gate_query.py"

DEFAULT_STATUS_FILE="/var/lib/sparkvm/gate/status.json"
STATUS_FILE="${SPARKVM_GATE_STATUS:-$DEFAULT_STATUS_FILE}"

usage() {
    cat <<'EOF'
Usage: gate_hook.sh [--status-file PATH] [gate_query.py args...]

Runs `gate_query.py state` and atomically writes the self-evaluated answer
to the box's local gate status file (default
/var/lib/sparkvm/gate/status.json, override with --status-file or
SPARKVM_GATE_STATUS). All other arguments pass through to gate_query.py
(--box-id, --keys, --gate, ...). Exit 0 when the status file was written
(even when the answer is frozen); non-zero only when the write failed.
EOF
}

QUERY_ARGS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --status-file)
            [ $# -ge 2 ] || { echo "gate_hook: --status-file needs a path" >&2; exit 1; }
            STATUS_FILE="$2"; shift 2 ;;
        --status-file=*)
            STATUS_FILE="${1#*=}"; shift ;;
        -h|--help)
            usage; exit 0 ;;
        --)
            shift
            while [ $# -gt 0 ]; do QUERY_ARGS+=("$1"); shift; done ;;
        *)
            QUERY_ARGS+=("$1"); shift ;;
    esac
done

answer_tmp="$(mktemp "${TMPDIR:-/tmp}/gate_hook.answer.XXXXXX")"
err_tmp="$(mktemp "${TMPDIR:-/tmp}/gate_hook.err.XXXXXX")"
trap 'rm -f "$answer_tmp" "$err_tmp"' EXIT

# --- #1649 S2 (slice 3): the gate-answer journal producer -------------------
# The hook appends one standard-shape `kind: gate-answer` row to a
# box-local `update-events.jsonl` on each answer TRANSITION (plus an anchor
# row on the first tick) — the G18 freeze-propagation proof's observable
# stream (UPDATE_EVENT_REPORTING.md §G18). Per-tick rows would flood the
# 12k-bound journal (~960/day); transitions are the events the fleet
# consumes, matching the S1 noise discipline (noop stays local-only).
#
# Sink layout: the installed copy is flat ($INSTALLED_BIN/event-journal.sh
# next to this script — installed by `auto-deploy.sh init`); the checkout
# keeps the sink at deploy/event-journal.sh. Try both so repo tests
# exercise the same code the timer runs.
_JOURNAL_LIB=""
for _cand in "$HOOK_DIR/event-journal.sh" "$HOOK_DIR/../deploy/event-journal.sh"; do
    if [ -f "$_cand" ]; then _JOURNAL_LIB="$_cand"; break; fi
done
# shellcheck source=event-journal.sh
[ -n "$_JOURNAL_LIB" ] && source "$_JOURNAL_LIB"
unset _cand _JOURNAL_LIB
# The hook's journal lives next to the gate status file (the root-owned
# gate lane — same trust as the status file itself), NOT the updater's
# state-dir journal: the hook runs as root, and a root-performed 12k-bound
# rotation would re-own the updater's file and silently break its appends.
# Overridable (tests, unusual layouts). Note: `:=` assigns the default when
# EVENT_JOURNAL is unset OR empty, so the sink is always armed at this
# point — the sink's "unset = silent no-op" contract applies to direct
# sink sourcing, not to this script.
: "${EVENT_JOURNAL:=$(dirname "$STATUS_FILE")/update-events.jsonl}"

# Journal-channel scrub (the S1a log-channel rule): operator-controlled
# strings never reach the journal raw. Unicode-aware (python, not tr) so
# multibyte UTF-8 survives intact.
_scrub() {
    python3 -c 'import sys
s = sys.stdin.read()
print("".join(c for c in s if not (ord(c) < 0x20 or 0x7F <= ord(c) <= 0x9F)), end="")'
}

[ -n "$STATUS_FILE" ] || { echo "gate_hook: empty status file path" >&2; exit 1; }
[ -f "$QUERY" ] || {
    echo "gate_hook: gate_query.py not found next to the hook: $(printf '%s' "$QUERY" | _scrub)" >&2
    exit 1
}
[ -r "$QUERY" ] || {
    echo "gate_hook: gate_query.py not readable: $(printf '%s' "$QUERY" | _scrub)" >&2
    exit 1
}

# gate_query's top-level flags (--box-id/--keys/--gate) must precede the
# `state` subcommand (argparse subparsers); the hook therefore emits the
# passthrough args first. Anything gate_query does not recognize fails
# loudly here — fail closed, never silently misconfigured.
if ! python3 "$QUERY" "${QUERY_ARGS[@]}" state >"$answer_tmp" 2>"$err_tmp"; then
    # Truncation happens inside python (character-based, no pipe): under
    # `set -o pipefail` a `| head -c` here could SIGPIPE-abort with 141
    # instead of this clean exit-1 message when stderr is long.
    err="$(python3 -c 'import sys
s = sys.stdin.read()
clean = "".join(c for c in s if not (ord(c) < 0x20 or 0x7F <= ord(c) <= 0x9F))
print(clean[:500], end="")' <"$err_tmp")"
    echo "gate_hook: gate_query.py failed to run ($err) — status file NOT updated: $(printf '%s' "$STATUS_FILE" | _scrub)" >&2
    exit 1
fi
[ -s "$answer_tmp" ] || {
    echo "gate_hook: gate_query.py printed no answer — status file NOT updated: $(printf '%s' "$STATUS_FILE" | _scrub)" >&2
    exit 1
}

# --- gate-answer transition gate (#1649 S2 slice 3) ---
# Read the PREVIOUS answer's (state, reason) from the status file BEFORE
# the writer below overwrites it. Best-effort: missing/corrupt/undecodable
# reads as "no previous answer" (prints 1), which emits the anchor row —
# a box whose hook history is unknown re-announces its answer once, and a
# corrupt status file is operator-visible via the anchor's arrival. (The
# `|| echo 0` fallback — python itself failed — prints 0: no emit, since
# the transition is unknowable.)
# The comparison is on (state, reason-class), NOT the raw reason string:
# no-signal reasons embed a tick-growing age counter ("gate document
# expired 93s past ttl=300s" — gate_query.py), so a raw comparison would
# fire every tick under a sustained no-signal (~960 rows/day) and break
# the slice's own noise discipline precisely in the fleet-wide outage the
# G18 freeze proof is about. The full age-bearing reason still lands in
# the emitted row's fragment — only the transition key is normalized.
_gate_transition="$(python3 - "$STATUS_FILE" "$answer_tmp" <<'PYEOF' 2>/dev/null || echo 0
import json
import re
import sys

def _transition_key(reason):
    # Collapse tick-varying counters so a sustained no-signal is one
    # transition, not one per tick. Semantic changes (operator freeze vs
    # no-signal, different failure classes) survive the collapse.
    return re.sub(r"\d+", "#", reason or "")

def _prev(path):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        ans = doc.get("answer") or {}
        state, reason = ans.get("state"), ans.get("reason")
        if isinstance(state, str) and isinstance(reason, str):
            return (state, _transition_key(reason))
    except Exception:
        pass
    return None

new = {}
try:
    with open(sys.argv[2], encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line and "=" in line:
                key, value = line.split("=", 1)
                new[key] = value
except OSError:
    pass

prev = _prev(sys.argv[1])
new_key = (new.get("state"), _transition_key(new.get("reason")))
print("1" if (prev is None or prev != new_key) else "0")
PYEOF
)"
# Assemble + atomically write the status document. The python step also
# prints the scrubbed one-line journal summary; its exit code is the
# hook's (0 = status file written).
python3 - "$answer_tmp" "$STATUS_FILE" <<'PYEOF'
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

answer_path, status_path = sys.argv[1], sys.argv[2]

def scrub(s):
    # The log-channel rule (fleet/api.py _clean_log_line, pairing
    # _plane_text): control characters never reach the journal raw.
    return "".join(ch for ch in s
                   if not (ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F))

answer = {}
with open(answer_path, encoding="utf-8") as fh:
    for line in fh:
        line = line.rstrip("\n")
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        answer[key] = value

payload = {
    "schema_version": 1,
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source": "gate_hook",
    "answer": answer,
}

status_dir = os.path.dirname(os.path.abspath(status_path))
try:
    os.makedirs(status_dir, exist_ok=True)
    # Unique temp name in the target dir (mkstemp, O_EXCL, 0600): two
    # overlapping ticks can never share — or clobber — a temp file.
    fd, tmp_path = tempfile.mkstemp(dir=status_dir, prefix=".gate-status-",
                                    suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, status_path)
    except BaseException:
        # Never leave a torn temp file behind for the next tick to trip on.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
except OSError as exc:
    print(f"gate_hook: FAILED to write status file {scrub(status_path)}: {exc}",
          file=sys.stderr)
    sys.exit(1)

state = scrub(answer.get("state", "?"))
reason = scrub(answer.get("reason", "?"))
print(f"gate_hook: state={state} reason={reason} status={scrub(status_path)}",
      file=sys.stderr)
PYEOF

# --- gate-answer emit (#1649 S2 slice 3) ---
# Reached only when the status file was written (the writer above exits
# non-zero on failure, and `set -e` ends the hook there) — the row always
# reflects a recorded answer, never a phantom.
if [ "${_gate_transition:-0}" = "1" ] && command -v event_emit >/dev/null 2>&1; then
    _ga_state=""; _ga_reason=""; _ga_repo_max=""; _ga_toolset_max=""; _ga_image_max=""
    # Parse the key=value answer lines with the same semantics as the python
    # `split("=", 1)` the transition gate and the status writer use:
    # split on the FIRST `=` only, keep everything after it (a trailing `=`
    # in a value is data, not syntax — `IFS='=' read` would strip it).
    while IFS= read -r _line; do
        case "$_line" in
            *=*) _k="${_line%%=*}"; _v="${_line#*=}" ;;
            *) continue ;;
        esac
        case "$_k" in
            state) _ga_state="$_v" ;;
            reason) _ga_reason="$_v" ;;
            repo_max) _ga_repo_max="$_v" ;;
            toolset_max) _ga_toolset_max="$_v" ;;
            image_max) _ga_image_max="$_v" ;;
        esac
    done <"$answer_tmp"
    # The outcome vocabulary stretches here (UPDATE_EVENT_REPORTING.md
    # §G18): `succeeded` reads as "permitted", not "deployed".
    _ga_outcome="skipped-frozen"
    [ "$_ga_state" = "live" ] && _ga_outcome="succeeded"
    # `trigger=gate`: the freeze/gate triggers are reserved for S2 emitters
    # (§2). Reason + per-component permitted commits ride in the fragment
    # ("permitted commit X"); maxes are absent on no-signal answers (only
    # the freeze/live evaluations carry {comp}_max).
    _ga_frag=",\"trigger\":\"gate\",\"reason\":\"$(_event_journal_json_escape "$_ga_reason")\""
    [ -n "$_ga_repo_max" ] && _ga_frag="$_ga_frag,\"repo_max\":\"$(_event_journal_json_escape "$_ga_repo_max")\""
    [ -n "$_ga_toolset_max" ] && _ga_frag="$_ga_frag,\"toolset_max\":\"$(_event_journal_json_escape "$_ga_toolset_max")\""
    [ -n "$_ga_image_max" ] && _ga_frag="$_ga_frag,\"image_max\":\"$(_event_journal_json_escape "$_ga_image_max")\""
    event_emit "gate-hook" "gate" "gate-answer" "$_ga_outcome" "$_ga_frag"
fi
unset _gate_transition _ga_state _ga_reason _ga_repo_max _ga_toolset_max _ga_image_max _ga_outcome _ga_frag _line _k _v
