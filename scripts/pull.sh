#!/bin/bash
# Pull remote changes into the box-side ~/spark-vm repo.
# Usage: ~/spark-vm/scripts/pull.sh
# Auth mirrors push.sh: the placeholder hsurr:github in the Authorization header
# is swapped for the real token by the credential-swapping proxy
# (with-proxy), for allowlisted hosts only. The token itself never appears
# in this script, in the environment, or in any log.
set -euo pipefail
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
# --- pull through the swapping proxy; hsurr:github becomes the real token ---
# GitHub's git HTTPS endpoint accepts Basic auth only (not Bearer) for
# PATs. The base64 below is computed over the *placeholder*
# (x-access-token:hsurr:github) — not a secret; the proxy base64-decodes,
# swaps in the real token, and re-encodes at egress for allowlisted hosts.
GIT_AUTH="Basic $(printf '%s' 'x-access-token:hsurr:github' | base64 -w0)"
if ! with-proxy git -c http.extraHeader="Authorization: $GIT_AUTH" -c http.proxy=http://127.0.0.1:18080 pull --ff-only origin "$(git rev-parse --abbrev-ref HEAD)"; then
    echo "Pull failed. If this is an auth (401/403) error, install a GitHub token:" >&2
    echo "  Create a fine-grained PAT with contents:read on ntindle/spark-vm, then run:" >&2
    echo "  cred set github   # paste the token at the prompt (your own SSH session)" >&2
    exit 1
fi
echo "Pulled."
