#!/usr/bin/env bash
# check-image-manifest.sh — injector preflight for the golden-image manifest
# (R2, docs/PRE_SEEDED_HARNESS_RESEARCH.md §4: "the injector preflights: it
# asserts the image's manifest version matches its own expectations and fails
# closed before box-live on any drift").
#
# Usage: harness/check-image-manifest.sh <manifest.json> [--expect-version <sha>]
#        [--pubkey <pubkey.pem> [--sig <sig-path>]]
#   --expect-version defaults to the current checkout's HEAD (right for the
#   image-build gate: "was this manifest built from the repo I'm building?").
#   The provision-time injector passes its own pinned SHA instead.
#   --pubkey enables the #155 signed path: the manifest's Ed25519 signature
#   (written by harness/sign-image-manifest.sh, default <manifest.json>.sig)
#   is verified over the manifest's EXACT BYTES before any JSON is parsed,
#   and the preflight fails closed (exit 1) on a missing, malformed, or
#   mismatched signature. Without --pubkey the old self-attestation check
#   runs — the manifest's own bytes are the only witness, so an unsigned
#   preflight is a weaker claim; say so in the gate record.
# Exit 0 iff the manifest is well-formed, carries the expected schema, has
# all required fields, image_version matches the expectation, and (when
# --pubkey is given) the signature verifies.
set -euo pipefail

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "usage: $0 <manifest.json> [--expect-version <sha>] [--pubkey <pubkey.pem> [--sig <sig-path>]]" >&2; exit 2
fi
MANIFEST="$1"; shift
EXPECT=""; PUBKEY=""; SIG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --expect-version) EXPECT="${2:?--expect-version needs a SHA}"; shift 2 ;;
    --pubkey) PUBKEY="${2:?--pubkey needs a path}"; shift 2 ;;
    --sig) SIG="${2:?--sig needs a path}"; shift 2 ;;
    *) echo "usage: $0 <manifest.json> [--expect-version <sha>] [--pubkey <pubkey.pem> [--sig <sig-path>]]" >&2; exit 2 ;;
  esac
done
if [[ -n "$SIG" && -z "$PUBKEY" ]]; then
  echo "check-image-manifest: --sig is meaningless without --pubkey" >&2; exit 2
fi
if [[ -z "$SIG" && -n "$PUBKEY" ]]; then SIG="${MANIFEST}.sig"; fi

if [[ -z "$EXPECT" ]]; then
  HERE="$(cd "$(dirname "$0")" && pwd)"
  EXPECT="$(git -C "$HERE/.." rev-parse HEAD)"
fi

MANIFEST_PATH="$MANIFEST" EXPECT_SHA="$EXPECT" PUBKEY_PATH="$PUBKEY" SIG_PATH="$SIG" python3 - <<'EOF'
import base64, json, os, stat, sys

manifest_path, expect = os.environ["MANIFEST_PATH"], os.environ["EXPECT_SHA"]
pubkey_path, sig_path = os.environ["PUBKEY_PATH"], os.environ["SIG_PATH"]

# Read the manifest bytes once, with no symlink following: every later step
# (signature verify AND JSON parse) consumes these exact bytes, so a
# between-steps swap cannot present different bytes to the parser.
try:
    mfd = os.open(manifest_path, os.O_RDONLY | os.O_NOFOLLOW)
except OSError as e:
    print(f"check-image-manifest: manifest unreadable (symlinks refused): {e}",
          file=sys.stderr)
    sys.exit(1)
try:
    if not stat.S_ISREG(os.fstat(mfd).st_mode):
        print("check-image-manifest: manifest is not a regular file; failing closed",
              file=sys.stderr)
        sys.exit(1)
    raw = os.read(mfd, 1 << 26)
    if os.read(mfd, 1):
        print("check-image-manifest: manifest over 64 MiB; failing closed",
              file=sys.stderr)
        sys.exit(1)
finally:
    os.close(mfd)

# The signature check runs BEFORE the JSON parse: the issue (#155) is a
# lying manifest, so trust must be established on bytes, not on a parse of
# attacker-shaped text.
if pubkey_path:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError:
        print("check-image-manifest: --pubkey needs the 'cryptography' package "
              "(pinned in requirements-test.txt); failing closed", file=sys.stderr)
        sys.exit(1)
    try:
        sfd = os.open(sig_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        print(f"check-image-manifest: SIGNATURE MISSING — {sig_path} not readable; "
              "failing closed", file=sys.stderr)
        sys.exit(1)
    try:
        if not stat.S_ISREG(os.fstat(sfd).st_mode):
            print("check-image-manifest: signature file is not a regular file; "
                  "failing closed", file=sys.stderr)
            sys.exit(1)
        sig_b64 = os.read(sfd, 4096)
        if os.read(sfd, 1) or not sig_b64.strip():
            print("check-image-manifest: signature file malformed (empty/oversize); "
                  "failing closed", file=sys.stderr)
            sys.exit(1)
    finally:
        os.close(sfd)
    try:
        sig = base64.b64decode(sig_b64.strip(), validate=True)
    except (base64.binascii.Error, ValueError):
        print("check-image-manifest: signature file is not valid base64; "
              "failing closed", file=sys.stderr)
        sys.exit(1)
    if len(sig) != 64:
        print("check-image-manifest: signature is not 64 bytes (Ed25519); "
              "failing closed", file=sys.stderr)
        sys.exit(1)
    try:
        kfd = os.open(pubkey_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        print(f"check-image-manifest: pubkey unreadable (symlinks refused): {e}; "
              "failing closed", file=sys.stderr)
        sys.exit(1)
    try:
        if not stat.S_ISREG(os.fstat(kfd).st_mode):
            print("check-image-manifest: pubkey is not a regular file; failing closed",
                  file=sys.stderr)
            sys.exit(1)
        pub_pem = os.read(kfd, 1 << 20)
    finally:
        os.close(kfd)
    try:
        pub = serialization.load_pem_public_key(pub_pem)
    except (ValueError, TypeError) as e:
        print(f"check-image-manifest: pubkey is not a usable PEM public key: {e}; "
              "failing closed", file=sys.stderr)
        sys.exit(1)
    if not isinstance(pub, ed25519.Ed25519PublicKey):
        print("check-image-manifest: pubkey is not Ed25519; failing closed",
              file=sys.stderr)
        sys.exit(1)
    try:
        pub.verify(sig, raw)
    except InvalidSignature:
        print("check-image-manifest: SIGNATURE MISMATCH — the manifest bytes were "
              "not signed by this key; failing closed", file=sys.stderr)
        sys.exit(1)
    print("check-image-manifest: signature OK", file=sys.stderr)

try:
    m = json.loads(raw)
except ValueError as e:
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
