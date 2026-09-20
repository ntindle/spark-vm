#!/usr/bin/env bash
# generate-image-manifest.sh — emit the golden-image manifest for the current
# checkout (R2, docs/PRE_SEEDED_HARNESS_RESEARCH.md §4).
#
# The manifest records the repo SHA the image was built from plus the
# registry paths, unit names, and baked-component list the provision-time
# injector expects. The injector preflights with check-image-manifest.sh and
# fails closed on any drift before box-live.
#
# Usage: harness/generate-image-manifest.sh [--out path]
#   Writes JSON to stdout (or to path with --out).
#
# Fails closed (exit 2) when the checkout has uncommitted changes: image_version
# must name exactly what was baked, and a dirty tree under a clean SHA would lie
# to the injector preflight (and to anyone auditing the image later).
set -euo pipefail

OUT=""
if [[ "${1:-}" == "--out" ]]; then OUT="${2:?--out needs a path}"; shift 2; fi
if [[ $# -gt 0 ]]; then echo "usage: $0 [--out path]" >&2; exit 2; fi

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
SHA="$(git -C "$REPO" rev-parse HEAD)"
if [ -n "$(git -C "$REPO" -c status.showUntrackedFiles=normal status --porcelain)" ]; then
  echo "generate-image-manifest: refusing — the checkout has uncommitted changes; commit or stash before baking an image" >&2
  exit 2
fi
VERSION="$(cat "$REPO/VERSION")"
SCHEMA="sparkvm/golden-image-manifest@1"

json() { python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"; }

{
echo "{"
echo "  \"schema\": $(json "$SCHEMA"),"
echo "  \"image_version\": $(json "$SHA"),"
echo "  \"built_from_version\": $(json "$VERSION"),"
echo "  \"baked\": ["
echo "    \"os, agent user, sshd config (key-only)\","
echo "    \"swap proxy + swap-inference proxy units, grant writers, ssrf allow/deny lists\","
echo "    \"swapd CA bundle-build step (CA generated per tenant at first boot; private key never baked)\","
echo "    \"muse CLI + muse-job plugin installed and approved\","
echo "    \"CUA desktop stack (Xvfb :98, XFCE, cua-driver, bridge), autostarted at boot\","
echo "    \"confirmd + cred-ui services\","
echo "    \"empty credential stores with fixed registry paths\","
echo "    \"gate fixture: public dummy inference credential + echo host (non-secret)\","
echo "    \"smoke-test credential dummy (R1 FIRST_TEN_MINUTES_SPEC.md section 3a)\","
echo "    \"skeleton home (/etc/skel) + first-boot unit instantiating per-agent-user services\""
echo "  ],"
echo "  \"registry_paths\": {"
echo "    \"inference_registry\": \"/home/swapd/inference-registry.json\","
echo "    \"inference_hosts\": \"/home/swapd/inference-hosts.allow\","
echo "    \"inference_secrets\": \"/home/swapd/inference-secrets\","
echo "    \"main_registry\": \"/home/swapd/credentials.json\","
echo "    \"grants\": \"/home/swapd/grants.json\""
echo "  },"
echo "  \"units\": ["
echo "    \"swap-proxy.service\","
echo "    \"swap-inference.service\","
echo "    \"confirmd.service\","
echo "    \"cred-ui.service\""
echo "  ],"
echo "  \"injector_expect\": {"
echo "    \"manifest_schema\": $(json "$SCHEMA"),"
echo "    \"probe_path\": \"harness/harness-auth-probe\","
echo "    \"probe_modes\": [\"gate\", \"provision\"],"
echo "    \"key_placeholder_format\": \"hsurr:<name>\","
echo "    \"gate_fixture_credential\": \"gate-dummy\","
echo "    \"provision_credential\": \"llm-api\""
echo "  }"
echo "}"
} > "${OUT:-/dev/stdout}"
