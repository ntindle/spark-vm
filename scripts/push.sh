#!/bin/bash
# Push box-side changes in ~/spark-vm back to the ntindle/spark-vm repo.
# Usage: ~/spark-vm/scripts/push.sh [commit message]
# Auth: GH_TOKEN from `cred get github` (see setup below).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

# --- auth: github token from the credential store ---
if ! GH_TOKEN="$(cred get github 2>/tmp/push-cred-err)"; then
    if [ -s /tmp/push-cred-err ]; then
        cat /tmp/push-cred-err >&2
    fi
    echo "GitHub token not set. Create a fine-grained PAT with contents:write on ntindle/spark-vm, then run:" >&2
    echo "  echo '<token>' | cred set github" >&2
    exit 1
fi
rm -f /tmp/push-cred-err

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

# --- push with the token in an HTTP header (never in the remote URL, never echoed) ---
git -c http.extraHeader="Authorization: Bearer ${GH_TOKEN}" push origin HEAD
echo "Pushed."
