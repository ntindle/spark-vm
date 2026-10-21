#!/usr/bin/env bash
# preflight-upstream-assets.sh — fail fast when the golden-image recipe's
# pinned upstream release assets don't exist.
#
# The recipe (deploy/golden-image/Dockerfile, cua-driver layer) fetches the
# pinned cua-driver release from upstream GitHub at BUILD time. The v0.9.0
# release's golden-image gate failed TWO MINUTES into the docker build on a
# 404 for .../cua-driver-rs-v0.28.2/checksums.txt — the asset name was wrong
# at the release tree (#1689 fixed the name and pinned cross-producer
# agreement), but nothing verifies the pinned upstream release EXISTS before
# the build burns minutes. This preflight HEAD-checks the exact first URL
# the recipe fetches (checksums.txt — the v0.9.0 failure point); a non-200
# refuses the build in seconds with the URL, the pinned version, and the
# bump hint, instead of a mid-build gate failure. Scope note: only
# checksums.txt is checked — a yanked tarball with a live checksums.txt
# still fails mid-build; the recipe's own sha256sum -c remains the
# integrity gate, this is the existence gate.
#
# The version is resolved from the recipe's ARG CUA_DRIVER_VERSION default —
# the same pin the recipe consumes (build args can override it at build
# time, but the default is the tree's deliberate pin per D-P1). Exactly one
# defaulted ARG may exist: two would make the effective default ambiguous.
#
# Usage: preflight-upstream-assets.sh [DOCKERFILE]
#   DOCKERFILE defaults to the golden-image recipe in this checkout.
#
# Env: REPO_OVERRIDE (testing hook — repo root override, same as
#      build-image.sh), CUA_DRIVER_RELEASES_BASE (testing hook — release
#      download base; default https://github.com/trycua/cua/releases/download).
#
# Exit 0 when the checksums URL answers 200; nonzero with a loud diagnostic
# otherwise. Never touches docker, never mutates anything.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${REPO_OVERRIDE:-$(cd "$HERE/../.." && pwd)}"
DOCKERFILE="${1:-$REPO/deploy/golden-image/Dockerfile}"
BASE="${CUA_DRIVER_RELEASES_BASE:-https://github.com/trycua/cua/releases/download}"

die() { echo "upstream-assets-preflight: ERROR: $*" >&2; exit 1; }

[ -f "$DOCKERFILE" ] || die "recipe not found: $DOCKERFILE"
# grep -c exits 1 on zero matches; the || true keeps set -e from firing
# before the loud ambiguity check below can name the problem.
DEFAULT_COUNT="$(sed -n 's/^ARG CUA_DRIVER_VERSION=//p' "$DOCKERFILE" | grep -c . || true)"
[ "$DEFAULT_COUNT" -eq 1 ] \
    || die "expected exactly one ARG CUA_DRIVER_VERSION default in the recipe, found $DEFAULT_COUNT"
CUA_DRIVER_VERSION="$(sed -n 's/^ARG CUA_DRIVER_VERSION=//p' "$DOCKERFILE" | head -1)"
[ -n "$CUA_DRIVER_VERSION" ] || die "ARG CUA_DRIVER_VERSION default is empty"

# Tag form mirrors the recipe's cua-driver layer:
#   tag="cua-driver-rs-v${CUA_DRIVER_VERSION}"
# (deploy/golden-image/test_golden_image.py asserts they agree.)
TAG="cua-driver-rs-v${CUA_DRIVER_VERSION}"
URL="${BASE}/${TAG}/checksums.txt"

HTTP_CODE="$(curl -sSIL -o /dev/null -w '%{http_code}' \
    --max-time 30 --retry 2 "$URL")" \
    || die "request failed for $URL (network error?) — cannot verify the pinned cua-driver assets exist"

[ "$HTTP_CODE" = "200" ] \
    || die "$URL returned HTTP $HTTP_CODE — the pinned CUA_DRIVER_VERSION=$CUA_DRIVER_VERSION has no published checksums.txt upstream (bump the recipe pin deliberately with a changelog note, D-P1)"

echo "upstream-assets-preflight: OK — $URL -> 200 (cua-driver $CUA_DRIVER_VERSION)"
