#!/usr/bin/env bash
# check-image-manifest.sh — injector preflight for the golden-image manifest
# (R2, docs/PRE_SEEDED_HARNESS_RESEARCH.md §4: "the injector preflights: it
# asserts the image's manifest version matches its own expectations and fails
# closed before box-live on any drift").
#
# Usage: harness/check-image-manifest.sh <manifest.json> [--expect-version <sha>]
#   --expect-version defaults to the current checkout's HEAD (right for the
#   image-build gate: "was this manifest built from the repo I'm building?").
#   The provision-time injector passes its own pinned SHA instead.
# Exit 0 iff the manifest is well-formed, carries the expected schema, has
# all required fields, and image_version matches the expectation.
set -euo pipefail

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "usage: $0 <manifest.json> [--expect-version <sha>]" >&2; exit 2
fi
MANIFEST="$1"; shift
EXPECT=""
if [[ "${1:-}" == "--expect-version" ]]; then EXPECT="${2:?}"; shift 2; fi
if [[ $# -gt 0 ]]; then echo "usage: $0 <manifest.json> [--expect-version <sha>]" >&2; exit 2; fi

if [[ -z "$EXPECT" ]]; then
  HERE="$(cd "$(dirname "$0")" && pwd)"
  EXPECT="$(git -C "$HERE/.." rev-parse HEAD)"
fi

python3 - "$MANIFEST" "$EXPECT" <<'EOF'
import json, sys

manifest_path, expect = sys.argv[1], sys.argv[2]
try:
    with open(manifest_path) as f:
        m = json.load(f)
except (OSError, ValueError) as e:
    print(f"check-image-manifest: manifest unreadable/invalid JSON: {e}", file=sys.stderr)
    sys.exit(1)

schema = "sparkvm/golden-image-manifest@1"
if m.get("schema") != schema:
    print(f"check-image-manifest: schema {m.get('schema')!r} != {schema!r}", file=sys.stderr)
    sys.exit(1)

required = ("image_version", "built_from_version", "baked", "registry_paths",
            "units", "injector_expect")
missing = [k for k in required if k not in m]
if missing:
    print(f"check-image-manifest: missing keys: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

if not isinstance(m["image_version"], str) or not m["image_version"]:
    print("check-image-manifest: image_version must be a non-empty string",
          file=sys.stderr)
    sys.exit(1)

if m["image_version"] != expect:
    print(f"check-image-manifest: DRIFT — manifest image_version "
          f"{str(m['image_version'])[:12]} != expected {expect[:12]}; failing closed",
          file=sys.stderr)
    sys.exit(1)

for sub, keys in (("registry_paths", ("inference_registry", "inference_hosts",
                                      "inference_secrets", "main_registry", "grants")),
                  ("injector_expect", ("manifest_schema", "probe_path", "probe_modes",
                                       "key_placeholder_format"))):
    submissing = [k for k in keys if k not in m[sub]]
    if submissing:
        print(f"check-image-manifest: {sub} missing keys: {', '.join(submissing)}",
              file=sys.stderr)
        sys.exit(1)

print(f"check-image-manifest: OK (image_version {m['image_version'][:12]}, "
      f"schema {schema})", file=sys.stderr)
EOF
