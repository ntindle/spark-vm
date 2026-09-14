#!/bin/bash
# Push box-side changes in ~/spark-vm back to the ntindle/spark-vm repo.
# Usage: ~/spark-vm/scripts/push.sh [commit message]
# Auth: the placeholder hsurr:github in the Authorization header is swapped
# for the real token by the credential-swapping proxy (with-proxy), for
# allowlisted hosts only. The token itself never appears in this script,
# in the environment, or in any log.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# --- never commit secrets: scan staged changes for secret-shaped values ---
git add -A
STAGED="$(git diff --cached --name-only)"
if [ -n "$STAGED" ]; then
    LEAK="$(echo "$STAGED" | xargs grep -nEi '(sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|xox[bap]-)' 2>/dev/null || true)"
    if [ -n "$LEAK" ]; then
        echo "Refusing to push: secret-shaped values found in staged changes:" >&2
        echo "$LEAK" | sed 's/=.*/=<redacted>/' >&2
        exit 1
    fi
fi

# --- commit (no-op if nothing changed) ---
MSG="${1:-update from spark-vm $(date -u +%Y-%m-%dT%H:%M:%SZ)}"
if git diff --cached --quiet; then
    echo "Nothing to commit."
else
    git commit -m "$MSG"
fi

# --- push through the swapping proxy; hsurr:github becomes the real token ---
if ! with-proxy git -c http.extraHeader="Authorization: Bearer hsurr:github" -c http.proxy=http://127.0.0.1:18080 push origin HEAD; then
    echo "Push failed. If this is an auth (401/403) error, install a GitHub token:" >&2
    echo "  Create a fine-grained PAT with contents:write on ntindle/spark-vm, then run:" >&2
    echo "  cred set github   # paste the token at the prompt (your own SSH session)" >&2
    exit 1
fi
echo "Pushed."
