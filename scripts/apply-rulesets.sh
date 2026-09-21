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
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'EOF'
Usage: apply-rulesets.sh --file PATH [--check | --execute --yes] [--owner O] [--repo R]

  (no flags)       dry-run: print the reconciliation plan, touch nothing
  --check          compare live repo rulesets against the file (exit 2 on drift)
  --execute --yes  create the ruleset, or update it in place (matched by name)

Applying repo settings is an OWNER DECISION (issue #174). Not run by automation.
EOF
    exit "${1:-0}"
}

need_value() { # need_value FLAG COUNT — die unless the flag has a following value
    [[ "$2" -ge 2 ]] || { echo "apply-rulesets.sh: $1 needs a value" >&2; usage 1; }
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --file)  need_value --file $#; FILE="$2"; shift 2 ;;
        --check) MODE=check; shift ;;
        --execute) MODE=execute; shift ;;
        --yes) CONFIRM=1; shift ;;  # acknowledgement flag, like cut-release.sh
        --owner) need_value --owner $#; OWNER="$2"; shift 2 ;;
        --repo)  need_value --repo $#; REPO="$2"; shift 2 ;;
        -h|--help) usage 0 ;;
        *) echo "apply-rulesets.sh: unknown flag $1" >&2; usage 1 ;;
    esac
done

[[ -n "$FILE" ]] || { echo "apply-rulesets.sh: --file is required" >&2; usage 1; }
if [[ "$MODE" == "execute" && "${CONFIRM:-}" != "1" ]]; then
    echo "apply-rulesets.sh: --execute needs --yes (re-run with --yes to confirm)" >&2
    exit 1
fi
[[ -f "$FILE" ]] || { echo "apply-rulesets.sh: file not found: $FILE" >&2; exit 1; }
# jq validates the JSON and compacts it for transport in one pass.
PAYLOAD="$(jq -c . "$FILE" 2>/dev/null)" \
    || { echo "apply-rulesets.sh: $FILE is not valid JSON" >&2; exit 1; }
NAME="$(printf '%s' "$PAYLOAD" | jq -r '.name')"
# A ruleset document needs a name — without it, create/update can't match.
[[ "$NAME" != "null" && -n "$NAME" ]] \
    || { echo "apply-rulesets.sh: $FILE has no .name — not a ruleset document" >&2; exit 1; }

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

# normalize JSON-doc to the canonical semantic form (see ruleset-normalize.jq)
normalize() {
    jq -c -f "$SCRIPT_DIR/ruleset-normalize.jq"
}

live_rulesets() {
    api GET "/repos/$OWNER/$REPO/rulesets?per_page=100"
}

live_match() { # prints the live ruleset id whose name == $NAME, or nothing
    live_rulesets | jq -r --arg n "$NAME" '[.[] | select(.name == $n) | .id] | first // empty'
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
