#!/usr/bin/env bash
# deploy/event-journal.sh — box-side fleet event journal sink.
#
# Implements the S2 journal sink from docs/UPDATE_EVENT_REPORTING.md §S2
# (issue #1649): the repo updater appends event rows directly in the
# standard event shape (§2) to a box-local `update-events.jsonl` — the
# journal the collector will read once the read switch lands (see §S2).
# Wired into both updaters: deploy/auto-deploy.sh (#1649 slice 1) and
# deploy/toolset-update.sh (#1649 slice 2).
# audit.log keeps the raw box-side record; the journal is the fleet-facing
# translation.
#
# Sourcing contract (same as deploy/arc_probe.sh): functions only, no main
# dispatcher. The caller points EVENT_JOURNAL at its own state dir BEFORE
# sourcing:
#     : "${EVENT_JOURNAL:=$UPDATER_STATE_DIR/update-events.jsonl}"
#     source "$SCRIPT_DIR/event-journal.sh"
#
# If EVENT_JOURNAL is unset, event_emit is a silent no-op — the sink is
# unconfigured, not broken.
#
# event_emit <source> <component> <kind> <outcome> [json-fields...]
#   Appends one JSON line in the standard shape (UPDATE_EVENT_REPORTING.md
#   §2). Fixed fields: event_id (UUIDv7, time-ordered), box_id (from
#   SPARKVM_BOX_ID when the operator's install set it, else null — the
#   collector also stamps identity from its pull context, per §2),
#   session_epoch (null until provisioner box records exist, OQ3),
#   emitted_at (box clock, ISO-8601 UTC), received_at (null — the collector
#   stamps its own clock; box clocks are never trusted for ordering),
#   rollout (null until G15 S2 assigns waves), trigger (defaults to
#   "scheduled", the §3 legacy-line default — pass ,"trigger":"manual" etc.
#   in the fields fragment to override), attested (false — S1/S2; S3's
#   attested channel is a separate producer lane).
#   Extra fields are appended verbatim as a pre-formatted JSON fragment
#   (same rule as audit(): callers MUST expand variables before passing —
#   single-quoted '$x' logs literally).
#
#   Producer vocabulary (closed enums, fail-LOUD on violation):
#     source: the box-side producer — auto-deploy (repo updater),
#       toolset-update (toolset updater), manual (operator-run rows),
#       controller (plane/controller rows, e.g. freeze-hold publishes),
#       gate-hook (the G18 gate-hook tick, kind gate-answer — #1649 S2
#       slice 3).
#     component: the updatable component the row is about — repo,
#       toolset-cua-driver, image; gate (the gate channel's own rows —
#       fleet-scoped gate answers, not a deployable component).
#
# Discipline:
#   - Closed enum vocabulary (fail-LOUD, not fail-silent): an invalid
#     source/component/kind/outcome prints a loud [event-journal] line to
#     stderr and writes NOTHING. The journal feeds G15's gates, and a
#     silently-emitted garbage row would poison them. But event_emit always
#     returns 0 — under `set -euo pipefail` a bad row must never kill the
#     updater; the systemd journal carries the complaint for the operator.
#   - Bounded journal: once past 12000 lines, keep the newest 10000 — the
#     same discipline as audit().
#   - Best-effort I/O: unwritable dirs, full disks, and every other
#     environmental failure are silent no-ops (never fail the run), like
#     audit(). Callers never need `|| true`.

_event_journal_json_escape() {
    # Escape a string value for embedding in a JSON double-quoted string.
    # C0 control characters are mapped to JSON escapes (\n \t \r \b \f,
    # \u00XX for the rest) so the row stays valid JSONL — a newline in an
    # operator-set value must not split the line. The value round-trips
    # exactly (json.loads recovers the original string).
    local s="$1"
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.argv[1])[1:-1])' \
            "$s" 2>/dev/null && return 0
        # Fall through to the pure-shell path if python3 misbehaves.
    fi
    # Pure-shell fallback (no python3): strip C0 controls, escape " and \.
    # Degraded but safe — the row stays valid JSONL.
    s="$(printf '%s' "$s" | tr -d '[:cntrl:]' 2>/dev/null || printf '%s' "$s")"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    printf '%s' "$s"
}

_event_journal_uuid7() {
    # UUIDv7 (RFC 9562): 48-bit unix-ms + ver 7 + 74 random bits, variant 10.
    # Time-ordered, so rows sort in emission order even across processes.
    if command -v python3 >/dev/null 2>&1; then
        python3 -c 'import random, time
ms = int(time.time() * 1000)
r = random.randbytes(10)
b = (ms.to_bytes(6, "big")
     + bytes([0x70 | (r[0] & 0x0F)])
     + r[1:2]
     + bytes([0x80 | (r[2] & 0x3F)])
     + r[3:])
h = b.hex()
print(f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}")' 2>/dev/null \
            && return 0
    fi
    if command -v uuidgen >/dev/null 2>&1; then
        # Not time-ordered (v4), but unique — a fallback, not the contract.
        uuidgen 2>/dev/null && return 0
    fi
    # Last resort: millisecond timestamp + 64 bits of urandom. Unique in
    # practice on a single box; never fails the emit path.
    local ms hex
    ms="$(date +%s%3N 2>/dev/null || date +%s)000"
    hex="$(od -A n -t x1 -N 8 /dev/urandom 2>/dev/null | tr -d ' \n')"
    printf '%s-%s\n' "${ms:0:13}" "${hex:0:16}" && return 0
    return 1
}

event_emit() {
    # event_emit <source> <component> <kind> <outcome> [json-fields...]
    local source="${1:-}" component="${2:-}" kind="${3:-}" outcome="${4:-}"
    shift 4 2>/dev/null || shift "$#"

    local bad=""
    case " $source " in
        " auto-deploy "|" toolset-update "|" manual "|" controller "|" gate-hook ") ;;
        *) bad="source='$source'" ;;
    esac
    case " $component " in
        " repo "|" toolset-cua-driver "|" image "|" gate ") ;;
        *) bad="${bad:+$bad, }component='$component'" ;;
    esac
    case " $kind " in
        " check "|" deploy "|" rollback "|" gate-answer "|" freeze-hold ") ;;
        *) bad="${bad:+$bad, }kind='$kind'" ;;
    esac
    case " $outcome " in
        " started "|" noop "|" precheck-fail "|" deferred-arc "|" skipped-frozen "|" succeeded "|" failed "|" rolled-back "|" rollback-failed "|" superseded ") ;;
        *) bad="${bad:+$bad, }outcome='$outcome'" ;;
    esac
    if [ -n "$bad" ]; then
        # Fail LOUD (stderr, operator-visible) but never fail the run:
        # nothing is written, and we still return 0 under set -e.
        echo "[event-journal] INVALID event row — not written: $bad (source=$source component=$component kind=$kind outcome=$outcome)" >&2
        return 0
    fi

    local journal="${EVENT_JOURNAL:-}"
    [ -n "$journal" ] || return 0

    local event_id ts box_id_json trigger
    event_id="$(_event_journal_uuid7 2>/dev/null)" || return 0
    ts="$(date -u +%FT%TZ 2>/dev/null)" || return 0
    if [ -n "${SPARKVM_BOX_ID:-}" ]; then
        box_id_json="\"$(_event_journal_json_escape "$SPARKVM_BOX_ID")\""
    else
        box_id_json="null"
    fi
    # The §3 legacy-line default: audit lines without a trigger canonicalize
    # to "scheduled". A caller-supplied ,"trigger":"..." in the fields
    # fragment overrides the default (dedupe by omission, not overwrite).
    trigger='"scheduled"'
    case "$*" in
        *'"trigger":'*) trigger='' ;;
    esac

    local row
    row="$(printf '{"event_id":"%s","box_id":%s,"session_epoch":null,"emitted_at":"%s","received_at":null,"source":"%s","component":"%s","kind":"%s","outcome":"%s","rollout":null%s,"attested":false%s}' \
        "$(_event_journal_json_escape "$event_id")" \
        "$box_id_json" \
        "$ts" \
        "$source" \
        "$component" \
        "$kind" \
        "$outcome" \
        "${trigger:+,\"trigger\":$trigger}" \
        "$*")"
    # Best-effort write: a redirection failure (unwritable state dir) is
    # silent rather than noisy, and never fails the run.
    mkdir -p "$(dirname "$journal")" 2>/dev/null || true
    ( printf '%s\n' "$row" >>"$journal" ) 2>/dev/null || return 0
    # The state dir must not be world-readable (the updater's contract);
    # enforce 0600 on every append (#1858), not only when the sink itself
    # created the file — a pre-existing loose-perm journal (operator error,
    # restored backup, shared image) must not stay readable after the sink
    # touches it. Best-effort, like the rest of the sink.
    chmod 600 "$journal" 2>/dev/null || true
    # Bound the journal: keep the newest 10k lines once it passes 12k —
    # the same discipline as audit().
    local n
    n="$(wc -l <"$journal" 2>/dev/null || echo 0)"
    if [ "$n" -gt 12000 ] 2>/dev/null; then
        tail -n 10000 "$journal" >"$journal.tmp" 2>/dev/null \
            && mv -f "$journal.tmp" "$journal" 2>/dev/null || true
        chmod 600 "$journal" 2>/dev/null || true
    fi
    return 0
}
