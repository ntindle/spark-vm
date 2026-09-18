#!/bin/bash
# Push box-side changes in ~/spark-vm back to the ntindle/spark-vm repo.
# Usage: ~/spark-vm/scripts/push.sh [--dry-run] [commit message]
# Auth: the placeholder hsurr:github in the Authorization header is swapped
# for the real token by the credential-swapping proxy (with-proxy), for
# allowlisted hosts only. The token itself never appears in this script,
# in the environment, or in any log.
set -euo pipefail

usage() {
    cat <<'EOF'
Usage: push.sh [--dry-run] [--] [commit message]

Stages all changes, scans them for secret-shaped values, commits, and pushes
origin HEAD through the credential-swapping proxy.

  --dry-run   show what would be committed and pushed, change nothing
  --          end of flags (use if the commit message starts with -)
  -h, --help  show this help
EOF
}

die() { echo "push.sh: $*" >&2; exit 1; }

DRY_RUN=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        --) shift; break ;;
        -*) die "unknown flag: $1 (see --help)" ;;
        *) break ;;
    esac
done
(( $# <= 1 )) || die "too many arguments (see --help; use -- if the message starts with -)"

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# --- preflight ---
command -v with-proxy >/dev/null || die "with-proxy not found in PATH"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree"
git remote get-url origin >/dev/null 2>&1 || die "no 'origin' remote configured"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
[[ "$BRANCH" != "HEAD" ]] || die "detached HEAD — check out a branch first"

# --- never commit secrets: scan staged contents for secret-shaped values ---
# Scoped to files changed vs HEAD (like the old scan): a committed false
# positive must not block future pushes. git grep --cached reads the *staged*
# blobs (not the working tree), handles filenames with spaces, and
# --diff-filter=ACM skips deleted files.
SECRET_RE='(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|ghr_[A-Za-z0-9]{36}|glpat-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16}|LLM_[0-9]{3,}_[A-Za-z0-9-]{16,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|xox[bap]-)'
scan_secrets() {
    local -a paths=()
    while IFS= read -r -d '' p; do paths+=("$p"); done \
        < <(git diff --cached --name-only -z --diff-filter=ACM)
    ((${#paths[@]})) || return 0
    git grep -nEi -e "$SECRET_RE" --cached -- "${paths[@]}" 2>/dev/null || true
}

# Print file:line only — never the matched content (echoing even a
# "redacted" secret is still an exposure; git grep -n emits path:lineno:content).
report_leak() {
    echo "$1" | cut -d: -f1,2 | sed 's/^/  /'
}

MSG="${1:-update from spark-vm $(date -u +%Y-%m-%dT%H:%M:%SZ)}"

# --- dry run: stage into a throwaway index, report, change nothing ---
if (( DRY_RUN )); then
    # Race-free temp index: mktemp -d is atomic; the index file lives inside.
    TMPDIR_IDX="$(mktemp -d)"
    TMPIDX="$TMPDIR_IDX/index"
    trap 'rm -rf "$TMPDIR_IDX"' EXIT
    GIT_INDEX_FILE="$TMPIDX" git add -A
    STAGED="$(GIT_INDEX_FILE="$TMPIDX" git diff --cached --name-only --diff-filter=ACM)"
    if [ -z "$STAGED" ]; then
        echo "dry-run: nothing to commit."
    else
        echo "dry-run: would commit with message:"
        echo "  $MSG"
        echo "dry-run: would commit these files:"
        echo "$STAGED" | sed 's/^/  /'
        echo "dry-run: diff stat:"
        GIT_INDEX_FILE="$TMPIDX" git diff --cached --stat | sed 's/^/  /'
        LEAK="$(GIT_INDEX_FILE="$TMPIDX" scan_secrets)"
        if [ -n "$LEAK" ]; then
            echo "dry-run: REFUSED — secret-shaped values found (same as a real run):" >&2
            report_leak "$LEAK" >&2
            exit 1
        fi
        echo "dry-run: secret scan clean."
    fi
    if git ls-remote --exit-code origin "refs/heads/$BRANCH" >/dev/null 2>&1; then
        # Fetch so the ahead-count reads a fresh, local ref — a stale or
        # never-fetched origin/$BRANCH would miscount or die under set -e.
        git fetch -q origin "$BRANCH" 2>/dev/null || true
        AHEAD="$(git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo "?")"
        echo "dry-run: would push $AHEAD local commit(s) to origin $BRANCH."
    else
        echo "dry-run: would push and create remote branch $BRANCH."
    fi
    echo "dry-run: no changes made."
    exit 0
fi

# --- real run ---
git add -A
STAGED="$(git diff --cached --name-only)"
if [ -n "$STAGED" ]; then
    LEAK="$(scan_secrets)"
    if [ -n "$LEAK" ]; then
        echo "Refusing to push: secret-shaped values found in staged changes:" >&2
        report_leak "$LEAK" >&2
        exit 1
    fi
fi

# --- commit (no-op if nothing changed) ---
if git diff --cached --quiet; then
    echo "Nothing to commit."
else
    git commit -m "$MSG"
fi

# --- push through the swapping proxy; hsurr:github becomes the real token ---
# GitHub's git HTTPS endpoint accepts Basic auth only (not Bearer) for
# PATs. The base64 below is computed over the *placeholder*
# (x-access-token:hsurr:github) — not a secret; the proxy base64-decodes,
# swaps in the real token, and re-encodes at egress for allowlisted hosts.
GIT_AUTH="Basic $(printf '%s' 'x-access-token:hsurr:github' | base64 -w0)"
if ! with-proxy git -c http.extraHeader="Authorization: $GIT_AUTH" -c http.proxy=http://127.0.0.1:18080 push origin HEAD; then
    echo "Push failed. If this is an auth (401/403) error, install a GitHub token:" >&2
    echo "  Create a fine-grained PAT with contents:write on ntindle/spark-vm, then run:" >&2
    echo "  cred set github   # paste the token at the prompt (your own SSH session)" >&2
    echo "  (Pushing changes under .github/workflows/ additionally needs the" >&2
    echo "   workflow scope on the token.)" >&2
    exit 1
fi
echo "Pushed."
