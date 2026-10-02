#!/usr/bin/env bash
# sign-image-manifest.sh — sign a golden-image manifest with an operator-held
# Ed25519 key (closes #155).
#
# The manifest (harness/generate-image-manifest.sh) is read FROM THE IMAGE by
# the provision-time injector, and check-image-manifest.sh used to compare only
# its self-asserted image_version against the injector's pinned SHA — a
# compromised build host or a confused-deputy image registry could serve a
# lying manifest naming the pinned SHA while baking anything. Signing binds
# the manifest BYTES to an operator-held key: with --pubkey, the injector's
# preflight verifies the Ed25519 signature over the exact bytes before any
# JSON parse, and fails closed on a missing, malformed, or mismatched
# signature.
#
# Trust contract (say it plainly):
#   - The SIGNING key never enters the repo and never ships in the image.
#   - The VERIFICATION key ships with the injector (operator config, e.g.
#     passed as INJECT_MANIFEST_PUBKEY), never in the image.
#   - A signature proves the manifest bytes were authorized by whoever held
#     the signing key at build time. It does NOT prove the image is good —
#     the drift check (image_version vs pinned SHA) still binds the bytes to
#     the code you reviewed.
#   - Without --pubkey on the check side, the old self-attestation behavior
#     remains (needed while existing unsigned images are in service). An
#     unsigned preflight is a weaker claim — say so in the gate record.
#
# Requires python3 + the `cryptography` package (already pinned in
# requirements-test.txt for confirm/push.py's Web Push tests).
#
# Usage:
#   harness/sign-image-manifest.sh --gen-key <key-prefix>
#       Write <key-prefix>.priv.pem (mode 0600; refuses if it already
#       exists) and <key-prefix>.pub.pem, and print the pubkey's
#       SHA256 fingerprint — compare it out-of-band when configuring the
#       provisioner (trust-on-first-use). Hand the .pub.pem to whoever
#       configures the injector; keep the .priv.pem off every image.
#   harness/sign-image-manifest.sh <manifest.json> --key <priv.pem>
#       [--out <sig-path>]
#       Sign the manifest's exact bytes; write the base64 signature to
#       <manifest.json>.sig (default) or --out. Fails closed (exit 1) on a
#       non-regular manifest, a symlink manifest, or a private key readable
#       by group/other. Exit 2 is an invocation error.
set -euo pipefail

USAGE="usage: $0 --gen-key <key-prefix> | $0 <manifest.json> --key <priv.pem> [--out <sig-path>]"
need_arg() { # $1 = flag name; $2 = the value (maybe empty)
  if [[ -z "${2:-}" ]]; then echo "sign-image-manifest: $1 needs a value" >&2; echo "$USAGE" >&2; exit 2; fi
  printf '%s' "$2"
}

usage() { echo "$USAGE" >&2; exit 2; }

MODE=""
if [[ "${1:-}" == "--gen-key" ]]; then
  MODE="gen"; PREFIX="$(need_arg --gen-key "${2:-}")"; shift 2
elif [[ $# -ge 1 && "${1:-}" != "-h" && "${1:-}" != "--help" ]]; then
  MODE="sign"; MANIFEST="$1"; shift
else
  usage
fi
KEY=""; OUT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --key) KEY="$(need_arg --key "${2:-}")"; shift 2 ;;
    --out) OUT="$(need_arg --out "${2:-}")"; shift 2 ;;
    *) usage ;;
  esac
done
if [[ "$MODE" == "sign" && -z "$KEY" ]]; then usage; fi
if [[ -n "$OUT" && "$MODE" != "sign" ]]; then usage; fi
if [[ "$MODE" == "gen" && -n "$KEY" ]]; then usage; fi

NEED_CRYPTO_MSG="sign-image-manifest: the 'cryptography' package is required (pinned in requirements-test.txt); refusing to proceed"
export NEED_CRYPTO_MSG

if [[ "$MODE" == "gen" ]]; then
  PRIV="${PREFIX}.priv.pem"; PUB="${PREFIX}.pub.pem"
  if [[ -e "$PRIV" || -e "$PUB" ]]; then
    echo "sign-image-manifest: refusing to overwrite existing key file(s): $PRIV / $PUB" >&2
    exit 1
  fi
  PRIV_PATH="$PRIV" PUB_PATH="$PUB" python3 - <<'EOF'
import base64, hashlib, os, stat, sys
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
except ImportError:
    print(os.environ["NEED_CRYPTO_MSG"], file=sys.stderr)
    sys.exit(2)

priv_path, pub_path = os.environ["PRIV_PATH"], os.environ["PUB_PATH"]
priv = ed25519.Ed25519PrivateKey.generate()
priv_pem = priv.private_bytes(serialization.Encoding.PEM,
                              serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption())
pub_pem = priv.public_key().public_bytes(serialization.Encoding.PEM,
                                         serialization.PublicFormat.SubjectPublicKeyInfo)
for path, blob in ((priv_path, priv_pem), (pub_path, pub_pem)):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, blob)
    finally:
        os.close(fd)
# Belt and braces: the umask could only have narrowed 0600, but verify it.
if stat.S_IMODE(os.stat(priv_path).st_mode) != 0o600:
    os.unlink(priv_path); os.unlink(pub_path)
    print("sign-image-manifest: key file did not land 0600; removed both files", file=sys.stderr)
    sys.exit(1)
print(f"sign-image-manifest: wrote {priv_path} (0600) + {pub_path}", file=sys.stderr)
# Trust-on-first-use anchor: the operator compares this fingerprint
# out-of-band when configuring the provisioner's INJECT_MANIFEST_PUBKEY,
# so a swapped .pub.pem is caught before it matters.
fp = base64.b64encode(hashlib.sha256(pub_pem).digest()).decode().rstrip("=")
print(f"sign-image-manifest: pubkey fingerprint SHA256:{fp}", file=sys.stderr)
EOF
  exit 0
fi

# sign mode
if [[ -z "$OUT" ]]; then OUT="${MANIFEST}.sig"; fi
MANIFEST_PATH="$MANIFEST" KEY_PATH="$KEY" OUT_PATH="$OUT" python3 - <<'EOF'
import base64, os, stat, sys
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519
except ImportError:
    print(os.environ["NEED_CRYPTO_MSG"], file=sys.stderr)
    sys.exit(2)

mpath, kpath, opath = (os.environ["MANIFEST_PATH"], os.environ["KEY_PATH"],
                       os.environ["OUT_PATH"])
# Read the manifest bytes with no symlink following: signing through a
# symlink would bind the signature to bytes the caller didn't name.
try:
    mfd = os.open(mpath, os.O_RDONLY | os.O_NOFOLLOW)
except OSError as e:
    print(f"sign-image-manifest: cannot open manifest (symlinks refused): {e}",
          file=sys.stderr)
    sys.exit(1)
try:
    if not stat.S_ISREG(os.fstat(mfd).st_mode):
        print("sign-image-manifest: refusing to sign a non-regular manifest",
              file=sys.stderr)
        sys.exit(1)
    data = os.read(mfd, 1 << 26)  # manifests are small; 64 MiB hard cap
    if os.read(mfd, 1):
        print("sign-image-manifest: manifest over 64 MiB; refusing", file=sys.stderr)
        sys.exit(1)
finally:
    os.close(mfd)
# The signing key is a capability: refuse it when anyone but the owner
# can read it (same discipline as fleet/gate_query.py's 0600 key refusal).
try:
    kfd = os.open(kpath, os.O_RDONLY | os.O_NOFOLLOW)
except OSError as e:
    print(f"sign-image-manifest: cannot open key (symlinks refused): {e}",
          file=sys.stderr)
    sys.exit(1)
try:
    if not stat.S_ISREG(os.fstat(kfd).st_mode):
        print("sign-image-manifest: key is not a regular file; refusing",
              file=sys.stderr)
        sys.exit(1)
    if os.fstat(kfd).st_mode & 0o077:
        print("sign-image-manifest: private key is group/other readable; "
              "chmod 600 it first — refusing to sign", file=sys.stderr)
        sys.exit(1)
    key_pem = os.read(kfd, 1 << 20)
finally:
    os.close(kfd)
try:
    priv = serialization.load_pem_private_key(key_pem, password=None)
except (ValueError, TypeError) as e:
    print(f"sign-image-manifest: not a usable PEM private key: {e}", file=sys.stderr)
    sys.exit(1)
if not isinstance(priv, ed25519.Ed25519PrivateKey):
    print("sign-image-manifest: key is not Ed25519; refusing", file=sys.stderr)
    sys.exit(1)
sig = priv.sign(data)
tmp = opath + ".tmp"
with open(tmp, "wb") as f:
    f.write(base64.b64encode(sig) + b"\n")
    f.flush(); os.fsync(f.fileno())
os.replace(tmp, opath)
print(f"sign-image-manifest: signed {len(data)} bytes -> {opath}", file=sys.stderr)
EOF
