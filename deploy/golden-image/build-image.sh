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
#   3. builds the image from that tree;
#   4. runs the baked-secrets scan INSIDE the built image (the gate
#      procedure's Step 0b — exit 1 is a build failure, not a warning);
#   5. generates + preflights the image manifest (gate Step 0);
#   6. emits the gate-record skeleton (automated steps filled, the
#      interactive round-trip steps left pending — the operator runs
#      docs/GOLDEN_IMAGE_GATE_PROCEDURE.md before publish).
#
# The driver NEVER pushes: registry credentials are operator-owned. It
# prints the exact publish command for the operator to run after the gate.
#
# Usage: deploy/golden-image/build-image.sh [--preflight-only]
#        [--gate-record-out <path>] [--tag <name>]
#   --preflight-only   run only the tree/version/sha checks (used by tests)
#   --gate-record-out  run the preflights and emit the gate-record skeleton
#                      to <path> without docker (scan section is marked
#                      "not-run"; used by tests and by CI's static job)
#   --tag              override the local image tag (default
#                      sparkvm-golden:<version>+<sha12>)
#
# Env: REPO_OVERRIDE — build from a different tree (tests point it at a
# scratch git repo). Production never sets it.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${REPO_OVERRIDE:-$(cd "$HERE/../.." && pwd)}"
PREFLIGHT_ONLY=0
GATE_RECORD_OUT=""
TAG=""

while [ $# -gt 0 ]; do
    case "$1" in
        --preflight-only) PREFLIGHT_ONLY=1; shift ;;
        --gate-record-out) GATE_RECORD_OUT="${2:?--gate-record-out needs a path}"; shift 2 ;;
        --tag) TAG="${2:?--tag needs a name}"; shift 2 ;;
        --help|-h) sed -n '2,/^$/p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "ERROR: unknown argument: $1 (try --help)" >&2; exit 1 ;;
    esac
done

die() { echo "build-image: ERROR: $*" >&2; exit 1; }

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

command -v docker >/dev/null 2>&1 || die "docker not found — the image builds on the operator's build host or in CI"

# --- 3. build ------------------------------------------------------------------
echo "build-image: docker build $TAG"
docker build -f "$REPO/deploy/golden-image/Dockerfile" \
    --build-arg "SPARKVM_VERSION=$VERSION" \
    --build-arg "SPARKVM_SHA=$SHA" \
    -t "$TAG" "$REPO"

BASE_DIGEST="$(docker inspect --format='{{index .RepoDigests 0}}' "$TAG" 2>/dev/null || true)"
echo "build-image: base digest: ${BASE_DIGEST:-(not recorded — image built without a digest pull)}"

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

# --- 5. manifest generate + preflight (gate Step 0) ------------------------------
MANIFEST="image-manifest-${SHA:0:12}.json"
"$REPO/harness/generate-image-manifest.sh" --out "$MANIFEST"
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
