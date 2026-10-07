#!/usr/bin/env bash
# build-image.sh — build the spark-vm golden image (#1087, F-P1).
#
# D-P1 (docs/PROVISIONING_METERING_CONVERGENCE_2026-10-06.md): pins forward,
# never silently. The driver:
#   1. refuses a dirty checkout (the manifest generator refuses dirty trees
#      too — a dirty tree baked under a clean SHA would lie to the
#      provision-time injector preflight);
#   2. computes SPARKVM_SHA=HEAD and SPARKVM_VERSION=VERSION from the tree
#      itself and passes them as build args — the tree is the pin; there is
#      no override flag, so a build can never silently bake a different
#      commit than the one the manifest names;
#   3. generates the image manifest into the build context (the recipe COPYs
#      it in — it cannot be generated in-image because the build context
#      excludes .git and the generator needs git metadata), removed by a
#      trap so the tree stays clean;
#   4. builds the image from that tree;
#   5. runs the baked-secrets scan INSIDE the built image (the gate
#      procedure's Step 0b — exit 1 is a build failure, not a warning);
#   6. preflights the baked manifest (gate Step 0);
#   7. emits the gate-record skeleton (automated steps filled, the
#      interactive round-trip steps left pending — the operator runs
#      docs/GOLDEN_IMAGE_GATE_PROCEDURE.md before publish).
#
# The driver NEVER pushes: registry credentials are operator-owned. It
# prints the exact publish command for the operator to run after the gate.
#
# Usage: deploy/golden-image/build-image.sh [--preflight-only]
#        [--gate-record-out <path>] [--tag <name>]
#        [--record-pushed-digest <gate-record.json> <image-ref> [--force]]
#   --preflight-only   run only the tree/version/sha checks (used by tests)
#   --gate-record-out  run the preflights and emit the gate-record skeleton
#                      to <path> without docker (scan section is marked
#                      "not-run"; used by tests and by CI's static job)
#   --tag              override the local image tag (default
#                      sparkvm-golden:<version>+<sha12>)
#   --record-pushed-digest
#                      publish-step mode (#1111): after the operator pushes
#                      the gated image, resolve the push-produced digest of
#                      <image-ref> via the local docker daemon (RepoDigests —
#                      the digest comes from the registry through docker,
#                      never from an operator paste) and stamp it into the
#                      gate record's build.image_digest. Write-once: a
#                      record that already names a different digest refuses
#                      (the re-push case needs --force); the same digest is
#                      idempotent. The gate record's image_version must
#                      match this tree's HEAD — the tree is the pin, and a
#                      digest stamped onto the wrong record would lie to the
#                      pin cross-check.
#   --force            allow --record-pushed-digest to overwrite an already
#                      recorded digest (the re-push case only; same-digest
#                      re-runs never need it)
#
# Env: REPO_OVERRIDE — build from a different tree (tests point it at a
# scratch git repo). Production never sets it.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${REPO_OVERRIDE:-$(cd "$HERE/../.." && pwd)}"
PREFLIGHT_ONLY=0
GATE_RECORD_OUT=""
TAG=""
RECORD_PUSHED_DIGEST=""
RECORD_IMAGE_REF=""
FORCE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --preflight-only) PREFLIGHT_ONLY=1; shift ;;
        --gate-record-out) GATE_RECORD_OUT="${2:?--gate-record-out needs a path}"; shift 2 ;;
        --tag) TAG="${2:?--tag needs a name}"; shift 2 ;;
        --record-pushed-digest)
            RECORD_PUSHED_DIGEST="${2:?--record-pushed-digest needs a gate-record path}"
            RECORD_IMAGE_REF="${3:?--record-pushed-digest needs an image ref}"
            shift 3 ;;
        --force) FORCE=1; shift ;;
        --help|-h) sed -n '2,/^$/p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "ERROR: unknown argument: $1 (try --help)" >&2; exit 1 ;;
    esac
done

die() { echo "build-image: ERROR: $*" >&2; exit 1; }

# The record mode is standalone: combining it with the build/preflight
# modes would silently drop the stamp request (their early exits fire
# first), and --force is meaningless outside the record mode.
if [ -n "$RECORD_PUSHED_DIGEST" ] && { [ "$PREFLIGHT_ONLY" = "1" ] || [ -n "$GATE_RECORD_OUT" ]; }; then
    die "--record-pushed-digest cannot be combined with --preflight-only or --gate-record-out"
fi
if [ "$FORCE" = "1" ] && [ -z "$RECORD_PUSHED_DIGEST" ]; then
    die "--force only applies to --record-pushed-digest"
fi

# --- 1. tree preflight -------------------------------------------------------
[ -d "$REPO/.git" ] || die "not a git checkout: $REPO"
if [ -n "$(git -C "$REPO" -c status.showUntrackedFiles=normal status --porcelain)" ]; then
    die "refusing — the checkout has uncommitted changes; commit or stash before baking an image (a dirty tree under a clean SHA would lie to the injector preflight)"
fi
SHA="$(git -C "$REPO" rev-parse HEAD)" || die "cannot resolve HEAD"
VERSION="$(cat "$REPO/VERSION")" || die "cannot read VERSION"
# VERSION must be real semver — a non-semver VERSION becomes "unknown"
# downstream (proxy/deploy.sh preflight), so fail here, loudly.
(cd "$REPO" && python3 scripts/sparkvm_version.py --check >/dev/null) \
    || die "VERSION '$VERSION' is not valid semver"
# The recipe's own ARG default must agree with the tree: a recipe that
# defaults to a different version than the tree being baked is a silent
# pin — refuse (the Dockerfile RUN check is the second line of defense).
# Exactly one defaulted ARG may exist: two would make the effective default
# ambiguous (the first wins silently).
RECIPE_DEFAULT_COUNT="$(sed -n 's/^ARG SPARKVM_VERSION=//p' "$REPO/deploy/golden-image/Dockerfile" | grep -c .)"
[ "$RECIPE_DEFAULT_COUNT" -eq 1 ] \
    || die "expected exactly one ARG SPARKVM_VERSION default in the recipe, found $RECIPE_DEFAULT_COUNT"
RECIPE_DEFAULT="$(sed -n 's/^ARG SPARKVM_VERSION=//p' "$REPO/deploy/golden-image/Dockerfile" | head -1)"
[ "$RECIPE_DEFAULT" = "$VERSION" ] \
    || die "recipe ARG default '$RECIPE_DEFAULT' != tree VERSION '$VERSION' — bump the Dockerfile deliberately (D-P1), never silently"
[ -z "$TAG" ] && TAG="sparkvm-golden:${VERSION}+${SHA:0:12}"

echo "build-image: tree clean at $SHA (v$VERSION); tag $TAG"

if [ "$PREFLIGHT_ONLY" = "1" ]; then
    echo "build-image: preflight-only — OK"
    exit 0
fi

# --- gate-record skeleton ------------------------------------------------------
# Emitted both by the full build and by --gate-record-out (CI static job);
# the full build fills the docker/scan sections afterwards.
emit_gate_record() {
    # args: out_path manifest_status base_digest scan_exit scan_target scan_hits docker_note
    local out="$1" manifest_status="$2" base_digest="$3" scan_exit="$4" scan_target="$5" scan_hits="$6" docker_note="$7"
    python3 - "$out" "$manifest_status" "$base_digest" "$scan_exit" "$scan_target" "$scan_hits" "$docker_note" "$TAG" <<EOF
import json, sys, datetime
out, manifest_status, base_digest, scan_exit, scan_target, scan_hits, docker_note, tag = sys.argv[1:9]
record = {
    "schema": "sparkvm/golden-image-gate-record@1",
    "image_version": "$SHA",
    "built_from_version": "$VERSION",
    "manifest_schema": "sparkvm/golden-image-manifest@1",
    "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "build": {
        # TAG is operator input — it travels via argv, never interpolated
        # into the heredoc, so a quote/backslash in --tag cannot break the JSON.
        "tag": tag,
        "docker_built": docker_note != "not-built",
        "base_digest": base_digest or None,
        # The push-produced image digest, stamped at publish time by
        # --record-pushed-digest (#1111). Null here is honest: the skeleton
        # is emitted before the image is pushed, and an unpushed image has
        # no RepoDigests (same not-pushed-means-empty discipline as the
        # base-digest note in the full build below). A later pin_image.py
        # slice cross-checks --image-ref against this value.
        "image_digest": None,
        "note": docker_note,
    },
    "automated_gate_steps": {
        # Gate procedure Step 0: manifest names exactly what was baked.
        "step0_manifest_preflight": manifest_status,
        # Gate procedure Step 0b: no baked secret material in the image.
        "step0b_baked_secrets_scan": {
            "exit": int(scan_exit),
            "target": scan_target,
            "hits": int(scan_hits),
        },
    },
    # The interactive round-trip (steps 1-5) needs the operator + confirmd.
    # This record is the skeleton the operator completes per
    # docs/GOLDEN_IMAGE_GATE_PROCEDURE.md step 6; an image without a
    # completed gate record does not publish.
    "interactive_gate": {
        "status": "pending",
        "canonical_task": None,
        "round_trip": None,
        "filing_count": None,
        "teardown_attestation": None,
        "verdict": "not-run",
    },
    "interface_gaps": [
        "round trip exercised through confirmd directly; pending-signal interface not yet shipped (gate procedure scope note)",
        "muse CLI + muse-job plugin install is provision-time (operator/account bound), not baked — the gate validates the claim",
    ],
}
with open(out, "w", encoding="utf-8") as f:
    json.dump(record, f, indent=2)
    f.write("\n")
print(f"build-image: gate record skeleton -> {out}")
EOF
}

if [ -n "$GATE_RECORD_OUT" ]; then
    # Static path: no docker — the manifest still generates from the clean
    # tree, the scan section is honestly marked not-run.
    "$REPO/harness/generate-image-manifest.sh" --out "${GATE_RECORD_OUT%.json}.manifest.json"
    "$REPO/harness/check-image-manifest.sh" "${GATE_RECORD_OUT%.json}.manifest.json" \
        --expect-version "$SHA" >/dev/null
    emit_gate_record "$GATE_RECORD_OUT" "pass" "" "-1" "not-run" "0" "not-built"
    exit 0
fi

# --- publish-step: record the push-produced digest --------------------------------
# #1111: stamps build.image_digest into an already-emitted gate record.
# The digest is resolved from the registry through the local docker daemon
# (RepoDigests of the pushed ref) — never from an operator paste: the
# record half of the advisory-D fix (the pin-side cross-check is a later
# slice). A later pin_image.py slice cross-checks --image-ref against the
# recorded digest.
cmd_record_pushed_digest() {
    local record="$1" image_ref="$2"
    command -v docker >/dev/null 2>&1 \
        || die "docker not found — the digest is resolved from the registry through the local daemon"
    local repo_digest
    repo_digest="$(docker inspect --format='{{index .RepoDigests 0}}' "$image_ref" 2>/dev/null || true)"
    [ -n "$repo_digest" ] \
        || die "the ref '$image_ref' has no RepoDigests on this host — push it (or pull it) here first; a ref the daemon never resolved cannot have a digest recorded"
    # RepoDigests entries look like <repo>@sha256:<hex>; the digest is the
    # part after the last @ (a value with no @ fails the strict grammar
    # below instead of silently recording garbage).
    local digest="${repo_digest##*@}"
    python3 - "$record" "$digest" "$SHA" "$FORCE" <<'EOF'
import json, os, re, sys
record_path, digest, tree_sha, force = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
fail = lambda msg: sys.exit(f"build-image: ERROR: {msg}")
# Exact-match grammar (not ^...$): a trailing newline or suffix must not
# slip a malformed digest into the trust record.
if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
    fail(f"digest resolved from RepoDigests is not a strict sha256 digest: {digest!r}")
try:
    with open(record_path, encoding="utf-8") as f:
        record = json.load(f)
except (OSError, ValueError) as e:
    fail(f"cannot read gate record {record_path}: {e}")
if not isinstance(record, dict) or record.get("schema") != "sparkvm/golden-image-gate-record@1":
    fail(f"{record_path} is not a sparkvm/golden-image-gate-record@1 record — refusing to stamp")
# The tree is the pin: a digest stamped onto another build's record would
# lie to the pin cross-check.
if record.get("image_version") != tree_sha:
    fail(f"gate record image_version {record.get('image_version')!r} != this tree's HEAD {tree_sha!r} — refusing to stamp the wrong record")
build = record.get("build")
if not isinstance(build, dict):
    fail(f"gate record {record_path} has no build section — refusing to stamp")
# Publish presumes a completed gate: a digest on a skeleton (or a refused
# gate) is meaningless to the cross-check and would look authoritative.
# The completed-pass vocabulary is shared with harness/pin_image.py's
# _check_gate_record (status == "complete", verdict == "pass") — the two
# predicates must agree, or no record can travel the publish → pin
# pipeline (a drift test in test_golden_image.py pins the agreement).
interactive = record.get("interactive_gate")
if not isinstance(interactive, dict) or interactive.get("status") != "complete" \
        or interactive.get("verdict") != "pass":
    fail(f"gate record {record_path} is not a completed gate pass "
         f"(interactive_gate.status={interactive.get('status') if isinstance(interactive, dict) else interactive!r}, "
         f"verdict={(interactive.get('verdict') if isinstance(interactive, dict) else None)!r}) — "
         f"the image does not publish before the gate")
current = build.get("image_digest")
if current == digest:
    print(f"build-image: image_digest {digest} already recorded — idempotent, nothing changed")
    sys.exit(0)
if current is not None and force != "1":
    fail(f"gate record already names image_digest {current!r} — refusing to overwrite with {digest!r} (the re-push case needs --force)")
build["image_digest"] = digest
tmp = record_path + ".tmp"
try:
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
        f.write("\n")
    os.replace(tmp, record_path)  # atomic: no torn record on a mid-write crash
except OSError as e:
    fail(f"cannot write gate record {record_path}: {e}")
print(f"build-image: image_digest {digest} recorded in {record_path}")
EOF
}

if [ -n "$RECORD_PUSHED_DIGEST" ]; then
    cmd_record_pushed_digest "$RECORD_PUSHED_DIGEST" "$RECORD_IMAGE_REF"
    exit 0
fi

command -v docker >/dev/null 2>&1 || die "docker not found — the image builds on the operator's build host or in CI"

# --- 2b. manifest into the build context -----------------------------------------
# The recipe COPYs the manifest in — it cannot generate it in-image (the
# build context excludes .git, and the generator needs git metadata to name
# the SHA). Generated here, after the dirty-tree preflight above, and removed
# by the trap below so the tree stays clean for the next run.
CONTEXT_MANIFEST="$REPO/deploy/golden-image/image-manifest.json"
cleanup_context_manifest() { rm -f "$CONTEXT_MANIFEST"; }
trap cleanup_context_manifest EXIT
"$REPO/harness/generate-image-manifest.sh" --out "$CONTEXT_MANIFEST"
echo "build-image: context manifest generated"

# --- 3. build ------------------------------------------------------------------
echo "build-image: docker build $TAG"
docker build -f "$REPO/deploy/golden-image/Dockerfile" \
    --build-arg "SPARKVM_VERSION=$VERSION" \
    --build-arg "SPARKVM_SHA=$SHA" \
    -t "$TAG" "$REPO"

# The gate record's base_digest must name the BASE image's resolved digest,
# not the built tag's (a locally built tag has no RepoDigests until it is
# pushed — inspecting $TAG would record an empty string and the "gate
# record makes base drift visible" claim would be false). Resolve the base
# ref from the recipe's FROM line so the two cannot diverge.
BASE_REF="$(sed -n 's/^FROM[[:space:]]\+\([^[:space:]]\+\).*/\1/p' "$REPO/deploy/golden-image/Dockerfile" | head -1)"
[ -n "$BASE_REF" ] || die "cannot resolve the base image ref from the Dockerfile FROM line"
BASE_DIGEST="$(docker inspect --format='{{index .RepoDigests 0}}' "$BASE_REF" 2>/dev/null || true)"
echo "build-image: base $BASE_REF digest: ${BASE_DIGEST:-(not recorded — pull the base by digest to pin it)}"

# --- 4. baked-secrets scan inside the built image (gate Step 0b) ---------------
echo "build-image: baked-secrets scan of the built image"
SCAN_OUT="$(mktemp)"
set +e
docker run --rm --entrypoint /bin/bash "$TAG" /opt/sparkvm/harness/scan-baked-secrets.sh / >"$SCAN_OUT" 2>&1
SCAN_EXIT=$?
set -e
HITS="$(grep -c 'baked-secrets-scan: HIT' "$SCAN_OUT" || true)"
cat "$SCAN_OUT"
rm -f "$SCAN_OUT"
if [ "$SCAN_EXIT" -eq 1 ]; then
    die "baked-secrets scan REFUSED the image ($HITS hits) — find how the material got baked and rebuild; the image does not publish"
elif [ "$SCAN_EXIT" -ne 0 ]; then
    die "baked-secrets scan failed with exit $SCAN_EXIT (invocation error) — fix the invocation and rebuild"
fi
echo "build-image: scan clean (exit 0)"

# --- 5. manifest preflight (gate Step 0) -------------------------------------------
# The context manifest (generated pre-build in step 2b) is the D-P1 artifact;
# preflight it here for the gate record (the recipe preflights the baked
# copy in-image too).
MANIFEST="image-manifest-${SHA:0:12}.json"
cp "$CONTEXT_MANIFEST" "$MANIFEST"
"$REPO/harness/check-image-manifest.sh" "$MANIFEST" --expect-version "$SHA" >/dev/null
echo "build-image: manifest $MANIFEST preflights (exit 0)"

# --- 6. gate-record skeleton ------------------------------------------------------
GATE_RECORD="gate-record-${SHA:0:12}.json"
emit_gate_record "$GATE_RECORD" "pass" "$BASE_DIGEST" "0" "/" "0" "built"

echo "build-image: DONE — image $TAG built, scan clean, manifest + gate record emitted"
echo "build-image: the image does NOT publish itself. After the interactive gate"
echo "  (docs/GOLDEN_IMAGE_GATE_PROCEDURE.md), the operator publishes with:"
echo "    docker tag $TAG <registry>/sparkvm-golden:${VERSION}+${SHA:0:12}"
echo "    docker push <registry>/sparkvm-golden:${VERSION}+${SHA:0:12}"
echo "  then records the push-produced digest into the gate record (#1111):"
echo "    $0 --record-pushed-digest $GATE_RECORD <registry>/sparkvm-golden:${VERSION}+${SHA:0:12}"
