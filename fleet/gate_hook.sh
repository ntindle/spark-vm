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
