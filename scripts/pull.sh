#!/bin/bash
# Pull remote changes into the box-side ~/spark-vm repo.
# Usage: ~/spark-vm/scripts/pull.sh [--dry-run]
# Auth mirrors push.sh: the placeholder hsurr:github in the Authorization header
# is swapped for the real token by the credential-swapping proxy
# (with-proxy), for allowlisted hosts only. The token itself never appears
# in this script, in the environment, or in any log.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: pull.sh [--dry-run]

Fast-forward pulls the current branch from origin through the
credential-swapping proxy.

  --dry-run   fetch only, show what pull would bring in, do not merge
  -h, --help  show this help
EOF
}

die() { echo "pull.sh: $*" >&2; exit 1; }

DRY_RUN=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; break ;;
        -*) die "unknown flag: $1 (see --help)" ;;
        *) die "unexpected argument: $1 (see --help)" ;;
    esac
done

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# --- preflight ---
command -v with-proxy >/dev/null || die "with-proxy not found in PATH"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree"
git remote get-url origin >/dev/null 2>&1 || die "no 'origin' remote configured"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[[ "$BRANCH" != "HEAD" ]] || die "detached HEAD — check out a branch first"
if [ -n "$(git status --porcelain)" ]; then
    echo "warning: working tree has uncommitted changes; pull --ff-only may refuse to merge." >&2
fi

# --- fetch through the swapping proxy; hsurr:github becomes the real token ---
# GitHub's git HTTPS endpoint accepts Basic auth only (not Bearer) for
# PATs. The base64 below is computed over the *placeholder*
# (x-access-token:hsurr:github) — not a secret; the proxy base64-decodes,
# swaps in the real token, and re-encodes at egress for allowlisted hosts.
GIT_AUTH="Basic $(printf '%s' 'x-access-token:hsurr:github' | base64 -w0)"
PROXY_GIT=(with-proxy git -c http.extraHeader="Authorization: $GIT_AUTH" -c http.proxy=http://127.0.0.1:18080)

# --- dry run: fetch (remote-tracking refs only), show what would merge ---
if (( DRY_RUN )); then
    "${PROXY_GIT[@]}" fetch origin "$BRANCH" || die "fetch failed"
    if git merge-base --is-ancestor HEAD "origin/$BRANCH" 2>/dev/null; then
        INCOMING="$(git rev-list --count "HEAD..origin/$BRANCH")"
        if (( INCOMING == 0 )); then
            echo "dry-run: already up to date with origin/$BRANCH."
        else
            echo "dry-run: pull would fast-forward $INCOMING commit(s):"
            git log --oneline --no-merges "HEAD..origin/$BRANCH" | sed 's/^/  /'
        fi
    else
        echo "dry-run: WARNING — HEAD is not an ancestor of origin/$BRANCH;" >&2
        echo "dry-run: a real pull --ff-only would refuse to merge (diverged)." >&2
        exit 1
    fi
    echo "dry-run: no changes made."
    exit 0
fi

# --- real run ---
if ! "${PROXY_GIT[@]}" pull --ff-only origin "$BRANCH"; then
    echo "Pull failed. If this is an auth (401/403) error, install a GitHub token:" >&2
    echo "  Create a fine-grained PAT with contents:read on ntindle/spark-vm, then run:" >&2
    echo "  cred set github   # paste the token at the prompt (your own SSH session)" >&2
    exit 1
fi
echo "Pulled."
