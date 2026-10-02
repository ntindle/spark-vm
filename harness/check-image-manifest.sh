#!/usr/bin/env bash
# check-image-manifest.sh — injector preflight for the golden-image manifest
# (R2, docs/PRE_SEEDED_HARNESS_RESEARCH.md §4: "the injector preflights: it
# asserts the image's manifest version matches its own expectations and fails
# closed before box-live on any drift").
#
# Usage: harness/check-image-manifest.sh <manifest.json> [--expect-version <sha>]
#        [--pubkey <key-spec> [--sig <sig-path>]]
#   --expect-version defaults to the current checkout's HEAD (right for the
#   image-build gate: "was this manifest built from the repo I'm building?").
#   The provision-time injector passes its own pinned SHA instead.
#   --pubkey enables the #155 signed path. <key-spec> is a rotation window
#   mirroring the fleet's SPARKVM_GATE_KEYS convention:
#       "key_id=/path/to/key.pub.pem[,key_id2=/path2 ...]"
#   (repeatable: multiple --pubkey flags join into one window). The
#   manifest's Ed25519 signature (written by harness/sign-image-manifest.sh,
#   default <manifest.json>.sig) is verified over the manifest's EXACT BYTES
#   before any JSON is parsed; the signature verifies if ANY window key
#   matches, and the check logs which key_id verified. Fail closed (exit 1)
#   on a missing, malformed, or mismatched signature, or on any unreadable
#   key (a misconfigured window must not silently degrade).
#   Without --pubkey the old self-attestation check runs — the manifest's
#   own bytes are the only witness, so an unsigned preflight is a weaker
#   claim; the final line says which mode ran (manifest-trust=signed vs
#   manifest-trust=self-attested) so the provision record can name it.
# Exit 0 iff the manifest is well-formed, carries the expected schema, has
# all required fields, image_version matches the expectation, and (when
# --pubkey is given) the signature verifies.
set -euo pipefail

USAGE="usage: $0 <manifest.json> [--expect-version <sha>] [--pubkey <key-spec> [--sig <sig-path>]]"
need_arg() { # $1 = flag name; $2 = the value (maybe empty)
  if [[ -z "${2:-}" ]]; then echo "check-image-manifest: $1 needs a value" >&2; echo "$USAGE" >&2; exit 2; fi
  printf '%s' "$2"
}

if [[ $# -lt 1 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  echo "$USAGE" >&2; exit 2
fi
MANIFEST="$1"; shift
EXPECT=""; PUBKEY_SPEC=""; SIG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --expect-version) EXPECT="$(need_arg --expect-version "${2:-}")"; shift 2 ;;
    --pubkey)
      v="$(need_arg --pubkey "${2:-}")"
      PUBKEY_SPEC="${PUBKEY_SPEC:+$PUBKEY_SPEC,}$v"
      shift 2 ;;
    --sig) SIG="$(need_arg --sig "${2:-}")"; shift 2 ;;
    *) echo "$USAGE" >&2; exit 2 ;;
  esac
done
if [[ -n "$SIG" && -z "$PUBKEY_SPEC" ]]; then
  echo "check-image-manifest: --sig is meaningless without --pubkey" >&2; exit 2
fi
if [[ -z "$SIG" && -n "$PUBKEY_SPEC" ]]; then SIG="${MANIFEST}.sig"; fi

if [[ -z "$EXPECT" ]]; then
  HERE="$(cd "$(dirname "$0")" && pwd)"
  EXPECT="$(git -C "$HERE/.." rev-parse HEAD)"
fi

MANIFEST_PATH="$MANIFEST" EXPECT_SHA="$EXPECT" PUBKEY_SPEC="$PUBKEY_SPEC" SIG_PATH="$SIG" python3 - <<'EOF'
import base64, json, os, stat, sys

manifest_path, expect = os.environ["MANIFEST_PATH"], os.environ["EXPECT_SHA"]
pubkey_spec, sig_path = os.environ["PUBKEY_SPEC"], os.environ["SIG_PATH"]

def fail(msg):
    print(f"check-image-manifest: {msg}; failing closed", file=sys.stderr)
    sys.exit(1)

# Read the manifest bytes once, with no symlink following: every later step
# (signature verify AND JSON parse) consumes these exact bytes, so a
# between-steps swap cannot present different bytes to the parser.
try:
    mfd = os.open(manifest_path, os.O_RDONLY | os.O_NOFOLLOW)
except OSError as e:
    fail(f"manifest unreadable (symlinks refused): {e}")
try:
    if not stat.S_ISREG(os.fstat(mfd).st_mode):
        fail("manifest is not a regular file")
    raw = os.read(mfd, 1 << 26)
    if os.read(mfd, 1):
        fail("manifest over 64 MiB")
finally:
    os.close(mfd)

trust = "self-attested"
# The signature check runs BEFORE the JSON parse: the issue (#155) is a
# lying manifest, so trust must be established on bytes, not on a parse of
# attacker-shaped text.
if pubkey_spec:
    try:
        from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError:
        fail("--pubkey needs the 'cryptography' package "
             "(pip install cryptography; pinned in requirements-test.txt)")
    # Rotation window, fleet SPARKVM_GATE_KEYS convention: key_id=/path
    # pairs, comma-separated. Strict: a bare path is a config error, not a
    # guess — every entry names its key_id so the verify log is auditable.
    keys = []
    for item in pubkey_spec.split(","):
        item = item.strip()
        if "=" not in item:
            fail(f"bad --pubkey entry (want key_id=/path): {item!r}")
        key_id, path = item.split("=", 1)
        key_id, path = key_id.strip(), path.strip()
        if not key_id or not path or "/" in key_id:
            fail(f"bad --pubkey entry (want key_id=/path): {item!r}")
        if any(k == key_id for k, _ in keys):
            fail(f"duplicate key_id in --pubkey: {key_id!r}")
        keys.append((key_id, path))
    if not keys:
        fail("empty --pubkey spec")
    try:
        sfd = os.open(sig_path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        fail(f"SIGNATURE MISSING — {sig_path} not readable")
    try:
        if not stat.S_ISREG(os.fstat(sfd).st_mode):
            fail("signature file is not a regular file")
        sig_b64 = os.read(sfd, 4096)
        if os.read(sfd, 1) or not sig_b64.strip():
            fail("signature file malformed (empty/oversize)")
    finally:
        os.close(sfd)
    try:
        sig = base64.b64decode(sig_b64.strip(), validate=True)
    except (base64.binascii.Error, ValueError):
        fail("signature file is not valid base64")
    if len(sig) != 64:
        fail("signature is not 64 bytes (Ed25519)")
    pubs = []
    for key_id, path in keys:
        try:
            kfd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as e:
            fail(f"pubkey {key_id} unreadable (symlinks refused): {e}")
        try:
            if not stat.S_ISREG(os.fstat(kfd).st_mode):
                fail(f"pubkey {key_id} is not a regular file")
            pub_pem = os.read(kfd, 1 << 20)
        finally:
            os.close(kfd)
        try:
            pub = serialization.load_pem_public_key(pub_pem)
        except (ValueError, TypeError, UnsupportedAlgorithm) as e:
            fail(f"pubkey {key_id} is not a usable PEM public key: {e}")
        if not isinstance(pub, ed25519.Ed25519PublicKey):
            fail(f"pubkey {key_id} is not Ed25519")
        pubs.append((key_id, pub))
    verified_id = None
    for key_id, pub in pubs:
        try:
            pub.verify(sig, raw)
        except InvalidSignature:
            continue
        verified_id = key_id
        break
    if verified_id is None:
        fail("SIGNATURE MISMATCH — the manifest bytes were not signed by "
             "any key in the window")
    trust = "signed"
    print(f"check-image-manifest: signature OK (key_id {verified_id})",
          file=sys.stderr)

try:
    m = json.loads(raw)
except ValueError as e:
    fail(f"manifest unreadable/invalid JSON: {e}")
if not isinstance(m, dict):
    fail("manifest JSON is not an object")

schema = "sparkvm/golden-image-manifest@1"
if m.get("schema") != schema:
    fail(f"schema {m.get('schema')!r} != {schema!r}")

required = ("image_version", "built_from_version", "baked", "registry_paths",
            "units", "injector_expect")
missing = [k for k in required if k not in m]
if missing:
    fail(f"missing keys: {', '.join(missing)}")

if not isinstance(m["image_version"], str) or not m["image_version"]:
    fail("image_version must be a non-empty string")

if m["image_version"] != expect:
    fail(f"DRIFT — manifest image_version {str(m['image_version'])[:12]} "
         f"!= expected {expect[:12]}")

for sub, keys in (("registry_paths", ("inference_registry", "inference_hosts",
                                      "inference_secrets", "main_registry", "grants")),
                  ("injector_expect", ("manifest_schema", "probe_path", "probe_modes",
                                       "key_placeholder_format"))):
    submissing = [k for k in keys if k not in m[sub]]
    if submissing:
        fail(f"{sub} missing keys: {', '.join(submissing)}")

print(f"check-image-manifest: OK (image_version {m['image_version'][:12]}, "
      f"schema {schema}, manifest-trust={trust})", file=sys.stderr)
EOF
