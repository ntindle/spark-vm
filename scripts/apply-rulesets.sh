#!/usr/bin/env bash
# apply-rulesets.sh — declare GitHub repository rulesets from JSON, or diff
# the live repo state against them.
#
# Applying repo settings is an OWNER DECISION (see deploy/rulesets/README.md
# and issue #174). This script exists so the decision, once made, is one
# command and fully auditable — it is not run by any automation.
#
# Usage:
#   scripts/apply-rulesets.sh --file deploy/rulesets/tag-protection-vstar.json
#       --check                      # compare live rulesets vs the file (no changes)
#   scripts/apply-rulesets.sh --file <f> --execute --yes [--owner O] [--repo R]
#       # create the ruleset, or update it in place (matched by name)
#
# Default (no flags): dry-run — prints what would happen, touches nothing.
#
# The token travels only in a trap-cleaned 0600 curl config file; it is never
# printed. Like scripts/cut-release.sh, it is read from $GITHUB_TOKEN only.
set -euo pipefail

API=https://api.github.com
OWNER=ntindle
REPO=spark-vm
FILE=""
MODE=dry-run

usage() {
    sed -n '1,20p' "$0"
    echo
    echo "Flags: --file PATH  --check | --execute --yes  [--owner O] [--repo R]  [-h|--help]"
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --file)  FILE="${2:?--file needs a path}"; shift 2 ;;
        --check) MODE=check; shift ;;
        --execute) MODE=execute; shift ;;
        --yes) shift ;;  # acknowledgement flag, like cut-release.sh
        --owner) OWNER="${2:?--owner needs a value}"; shift 2 ;;
        --repo)  REPO="${2:?--repo needs a value}"; shift 2 ;;
        -h|--help) usage 0 ;;
        *) echo "apply-rulesets.sh: unknown flag $1" >&2; usage 1 ;;
    esac
done

[[ -n "$FILE" ]] || { echo "apply-rulesets.sh: --file is required" >&2; usage 1; }
[[ -f "$FILE" ]] || { echo "apply-rulesets.sh: file not found: $FILE" >&2; exit 1; }
# jq validates the JSON and compacts it for transport in one pass.
PAYLOAD="$(jq -c . "$FILE" 2>/dev/null)" \
    || { echo "apply-rulesets.sh: $FILE is not valid JSON" >&2; exit 1; }
NAME="$(printf '%s' "$PAYLOAD" | jq -r '.name')"

api() { # api METHOD PATH [BODY] — prints response body; never logs the token
    local method="$1" path="$2" body="${3:-}"
    local cfg; cfg="$(mktemp)"
    trap 'rm -f "$cfg"' RETURN
    printf 'header = "Authorization: Bearer %s"\n' "$GITHUB_TOKEN" > "$cfg"
    chmod 600 "$cfg"
    if [[ -n "$body" ]]; then
        curl -sS --fail-with-body -K "$cfg" -X "$method" \
            -H 'Accept: application/vnd.github+json' \
            -H 'Content-Type: application/json' \
            --data-binary "$body" "$API$path"
    else
        curl -sS --fail-with-body -K "$cfg" -X "$method" \
            -H 'Accept: application/vnd.github+json' "$API$path"
    fi
}

require_token() {
    [[ -n "${GITHUB_TOKEN:-}" ]] \
        || { echo "apply-rulesets.sh: GITHUB_TOKEN is unset; refusing to talk to the API" >&2; exit 1; }
}

# normalize FILE-body and live-body to the semantic fields, sorted for compare
normalize() {
    jq -c '{name, target, enforcement,
            bypass_actors: (.bypass_actors // []),
            conditions,
            rules: [.rules[] | {type, parameters: (.parameters // {})}] | sort_by(.type)}'
}

live_rulesets() {
    api GET "/repos/$OWNER/$REPO/rulesets"
}

live_match() { # prints the live ruleset id whose name == $NAME, or nothing
    live_rulesets | jq -r --arg n "$NAME" '.[] | select(.name == $n) | .id' | head -1
}

case "$MODE" in
    dry-run)
        echo "dry-run: would reconcile ruleset '$NAME' from $FILE against $OWNER/$REPO"
        echo "target:      $(printf '%s' "$PAYLOAD" | jq -r '.target')"
        echo "enforcement: $(printf '%s' "$PAYLOAD" | jq -r '.enforcement')"
        echo "refs:        $(printf '%s' "$PAYLOAD" | jq -r '.conditions.ref_name.include | join(", ")')"
        echo "rules:       $(printf '%s' "$PAYLOAD" | jq -r '[.rules[].type] | join(", ")')"
        echo "Re-run with --check to diff against live state, or --execute --yes to apply."
        ;;
    check)
        require_token
        id="$(live_match)"
        if [[ -z "$id" ]]; then
            echo "check: no live ruleset named '$NAME' on $OWNER/$REPO — would CREATE it"
            exit 2
        fi
        want="$(printf '%s' "$PAYLOAD" | normalize)"
        got="$(api GET "/repos/$OWNER/$REPO/rulesets/$id" | normalize)"
        if [[ "$want" == "$got" ]]; then
            echo "check: live ruleset '$NAME' (id $id) matches $FILE"
            exit 0
        fi
        echo "check: DRIFT — live ruleset '$NAME' (id $id) differs from $FILE"
        diff <(printf '%s\n' "$want" | jq .) <(printf '%s\n' "$got" | jq .) || true
        exit 2
        ;;
    execute)
        require_token
        id="$(live_match)"
        if [[ -z "$id" ]]; then
            resp="$(api POST "/repos/$OWNER/$REPO/rulesets" "$PAYLOAD")"
            new_id="$(printf '%s' "$resp" | jq -r '.id')"
            echo "created ruleset '$NAME' (id $new_id) on $OWNER/$REPO — enforcement: $(printf '%s' "$resp" | jq -r '.enforcement')"
        else
            resp="$(api PUT "/repos/$OWNER/$REPO/rulesets/$id" "$PAYLOAD")"
            echo "updated ruleset '$NAME' (id $id) on $OWNER/$REPO — enforcement: $(printf '%s' "$resp" | jq -r '.enforcement')"
        fi
        ;;
esac
