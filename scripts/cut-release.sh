#!/bin/bash
# cut-release.sh -- cut a GitHub release for the current VERSION on main.
#
# This is the operator half of GitHub #53 ("Automate GitHub releases from
# VERSION"). The release workflow (.github/workflows/release.yml) calls this
# script in --ci mode when VERSION changes on main; an operator can run it by
# hand for a manual release.
#
# What it does:
#   1. Preflights: on main (or GITHUB_REF=refs/heads/main in --ci), clean
#      tree, VERSION is strict semver, HEAD is in sync with the remote's
#      main, and tag v<VERSION> does not exist locally or on the remote.
#   2. Assembles release notes: the curated CHANGELOG.md section for this
#      version when it exists, plus the merged-PR list since the previous
#      tag. Notes are printed (and optionally written) in --dry-run.
#   3. In --execute: creates an annotated, immutable tag v<VERSION>, pushes
#      it, and publishes a GitHub release (via `gh`, or the API with
#      $GITHUB_TOKEN when `gh` is unavailable).
#   4. In --publish-only: recovers from a tag-pushed/publish-failed state
#      (the tag exists on the remote but no release does) by regenerating
#      the notes and publishing the release for the existing tag.
#
# Usage: cut-release.sh [--dry-run] [--execute [--yes]] [--publish-only]
#                        [--ci] [--notes-file PATH] [--remote NAME]
#                        [-h|--help]
#
#   --dry-run      (default) validate everything, print the plan and the
#                  release-notes draft, change nothing.
#   --execute      actually cut the release. Requires --yes (except in
#                  --ci, where the workflow dispatch is the confirmation).
#   --yes          confirm the --execute run (no prompt).
#   --ci           workflow mode: verify GITHUB_REF is refs/heads/main
#                  instead of checking the local branch (CI checks out
#                  detached), then execute.
#   --notes-file   write the generated release notes to PATH as well.
#   --remote       git remote to use (default: origin; env CUT_RELEASE_REMOTE).
#
# Env: CUT_RELEASE_REMOTE (default origin), CUT_RELEASE_REPO (default
#      ntindle/spark-vm), CUT_RELEASE_DIR (repo root override; testing hook),
#      CUT_RELEASE_NO_GH (set to force the API fallback even when `gh`
#      exists; testing hook), GITHUB_TOKEN (API fallback when `gh` is
#      unavailable; never logged).
#
# Never commits secrets: the token is read from the environment only.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: cut-release.sh [--dry-run] [--execute [--yes]] [--publish-only]
                      [--ci] [--notes-file PATH] [--remote NAME] [-h|--help]

Cut a GitHub release for the current VERSION on main: preflight checks,
release-notes assembly (CHANGELOG.md section + merged PRs since the
previous tag), annotated tag v<VERSION>, and a published GitHub release.

  --dry-run      validate + print the plan and notes draft, change nothing
                 (default)
  --execute      cut the release for real; requires --yes (implied by --ci)
  --yes          confirm an --execute run
  --publish-only publish the release for the already-pushed tag v<VERSION>
                 (recovery: --execute pushed the tag but publishing failed)
  --ci           workflow mode: check GITHUB_REF is refs/heads/main instead
                 of the local branch, then execute without --yes
  --notes-file PATH  also write the generated notes to PATH
  --remote NAME  git remote to use (default: origin)
  -h, --help     show this help

Environment: CUT_RELEASE_REMOTE, CUT_RELEASE_REPO (default
ntindle/spark-vm), CUT_RELEASE_DIR (repo-root override, testing hook),
CUT_RELEASE_NO_GH (force the API fallback; testing hook),
GITHUB_TOKEN (API fallback when `gh` is unavailable).
EOF
}

die() { echo "cut-release.sh: $*" >&2; exit 1; }

MODE="dry-run"
CONFIRM=0
CI=0
NOTES_FILE=""
REMOTE="${CUT_RELEASE_REMOTE:-origin}"
REPO="${CUT_RELEASE_REPO:-ntindle/spark-vm}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) MODE="dry-run"; shift ;;
        --execute) MODE="execute"; shift ;;
        --publish-only) MODE="publish-only"; shift ;;
        --yes) CONFIRM=1; shift ;;
        --ci) CI=1; MODE="execute"; shift ;;
        --notes-file) [[ $# -ge 2 ]] || die "--notes-file needs a path"; NOTES_FILE="$2"; shift 2 ;;
        --remote) [[ $# -ge 2 ]] || die "--remote needs a name"; REMOTE="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        -*) die "unknown flag: $1 (see --help)" ;;
        *) die "unexpected argument: $1 (see --help)" ;;
    esac
done

REPO_DIR="${CUT_RELEASE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO_DIR"
[[ -d .git ]] || die "not a git repo: $REPO_DIR"

# Fail fast on a missing confirmation, before any network I/O.
if [[ "$MODE" == "execute" && "$CI" != "1" && "$CONFIRM" != "1" ]]; then
    die "--execute needs --yes (re-run with --yes to confirm)"
fi
if [[ "$MODE" == "publish-only" && "$CONFIRM" != "1" ]]; then
    die "--publish-only needs --yes (re-run with --yes to confirm)"
fi

# --- preflight: right ref ---
if [[ "$CI" == "1" ]]; then
    [[ "${GITHUB_REF:-}" == "refs/heads/main" ]] \
        || die "--ci requires GITHUB_REF=refs/heads/main (got '${GITHUB_REF:-<unset>}')"
else
    BRANCH="$(git symbolic-ref --short -q HEAD || true)"
    [[ -n "$BRANCH" ]] || die "detached HEAD outside --ci; release only from main"
    [[ "$BRANCH" == "main" ]] || die "must run on main (on '$BRANCH')"
fi

# --- preflight: clean tree ---
[[ -z "$(git status --porcelain)" ]] || die "working tree not clean; commit or stash first"

# --- preflight: VERSION is strict semver ---
VERSION="$(python3 scripts/sparkvm_version.py --check 2>/dev/null)" \
    || die "VERSION is missing or not strict semver (scripts/sparkvm_version.py --check failed)"
TAG="v$VERSION"
echo "cut-release.sh: VERSION=$VERSION tag=$TAG"

# --- preflight: in sync with the remote ---
git fetch --quiet -- "$REMOTE" "refs/heads/main:refs/remotes/$REMOTE/main" \
    "refs/tags/*:refs/tags/*" \
    || die "could not fetch $REMOTE (network? remote name? --remote to override)"
HEAD_SHA="$(git rev-parse HEAD)"
# The fetch above already pulled remote tags into the local tag namespace,
# so the local existence check below fires first; the ls-remote is
# belt-and-braces for a tag created on the remote between the fetch and
# this check.
REMOTE_TAGS_ALL="$(git ls-remote --tags "$REMOTE" "$TAG")" \
    || die "could not list remote tags on $REMOTE"

if [[ "$MODE" == "publish-only" ]]; then
    # Recovery mode: a previous --execute pushed the tag but publishing
    # failed. The tag must already exist on both sides; the release must
    # not. No in-sync check: later commits may have merged since.
    git rev-parse -q --verify "refs/tags/$TAG" >/dev/null \
        || die "--publish-only: tag $TAG does not exist locally; run --execute first"
    [[ -n "$REMOTE_TAGS_ALL" ]] \
        || die "--publish-only: tag $TAG is not on $REMOTE; run --execute first"
    RELEASE_REF="$TAG"
    RELEASE_SHA="$(git rev-list -n 1 "$TAG")"
else
    REMOTE_SHA="$(git rev-parse "$REMOTE/main")"
    [[ "$HEAD_SHA" == "$REMOTE_SHA" ]] \
        || die "HEAD ($HEAD_SHA) is not $REMOTE/main ($REMOTE_SHA); pull/rebase first"
    # --- preflight: tag must not exist anywhere (tags are immutable) ---
    git rev-parse -q --verify "refs/tags/$TAG" >/dev/null \
        && die "tag $TAG already exists locally; releases are immutable, bump VERSION first"
    [[ -z "$REMOTE_TAGS_ALL" ]] \
        || die "tag $TAG already exists on $REMOTE; releases are immutable, bump VERSION first"
    # --- preflight: VERSION must be newer than every existing release tag ---
    # (merging to main is the release authorization, so a downgrade typo must
    # not silently publish a confusing release).
    # Real semver-§11 precedence, not `sort -V`: GNU sort -V orders v1.2.4
    # BEFORE v1.2.4-rc.1, which would wrongly refuse the legitimate rc ->
    # final promotion (a prerelease has LOWER precedence than its normal
    # version). The regex below is kept in sync with
    # scripts/sparkvm_version.py.
    SEMVER_MSG="$(python3 - "$TAG" <<'PYEOF' 2>&1
import re, subprocess, sys
_semver_re = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
def _key(tag):
    v = tag[1:] if tag.startswith("v") else tag
    m = _semver_re.match(v)
    if not m:
        return None
    major, minor, patch, pre, _build = m.groups()
    if pre is None:
        prekey = (1,)  # no prerelease: higher precedence than any prerelease
    else:
        ids = tuple((0, int(i)) if i.isdigit() else (1, i)
                    for i in pre.split("."))
        prekey = (0, ids)
    return (int(major), int(minor), int(patch), prekey)
new_tag = sys.argv[1]
new_key = _key(new_tag)
latest, latest_key = None, None
tags = subprocess.run(["git", "tag", "--list", "v*"],
                      capture_output=True, text=True, check=True).stdout.split()
for t in tags:
    if t == new_tag:
        continue
    k = _key(t)
    if k is None:
        continue  # not a semver tag; TAG itself passed the strict check above
    if latest_key is None or k > latest_key:
        latest, latest_key = t, k
if latest is not None and not new_key > latest_key:
    sys.stderr.write("VERSION %s is not newer than latest release %s\n"
                     % (new_tag[1:], latest))
    sys.exit(1)
PYEOF
)" || die "$SEMVER_MSG"
    RELEASE_REF="HEAD"
    RELEASE_SHA="$HEAD_SHA"
fi

# --- release-notes assembly ---
# PREV_TAG excludes the tag being (re-)released, so --publish-only ranges
# from the previous release to the tag's commit, not to HEAD.
PREV_TAG="$(git tag --list 'v*' --sort=-v:refname | grep -vxF "$TAG" | head -n 1 || true)"
NOTES_DIR="$(mktemp -d)"
NOTES="$NOTES_DIR/notes.md"
trap 'rm -rf "$NOTES_DIR"' EXIT

{
    echo "## Highlights"
    echo
    SECTION=""
    if [[ -f CHANGELOG.md ]]; then
        # Extract the Keep-a-Changelog section for this version. Literal
        # prefix comparison, never a regex: semver build metadata like the
        # + in 1.2.0+build must match exactly, never as a pattern.
        # The section is contributor-controlled (per-PR entries are
        # mandatory), so it goes through the same control-character filter
        # as commit subjects: the notes draft is printed to the operator's
        # terminal in every mode.
        SECTION="$(awk -v ver="$VERSION" '
            /^## / {
                h = "## [" ver "]"; hv = "## [v" ver "]";
                insec = (substr($0, 1, length(h)) == h) || \
                        (substr($0, 1, length(hv)) == hv);
                next
            }
            insec { print }
        ' CHANGELOG.md | LC_ALL=C tr -d '\000-\010\013-\037\177')"
    fi
    if [[ -n "${SECTION//[[:space:]]/}" ]]; then
        printf '%s\n' "$SECTION"
        echo "cut-release.sh: using CHANGELOG.md section for $VERSION" >&2
    else
        echo "_No curated CHANGELOG.md section for $VERSION — notes assembled from merged PRs._"
        echo "cut-release.sh: WARNING: no CHANGELOG.md section for $VERSION" >&2
    fi
    echo
    if [[ -n "$PREV_TAG" ]]; then
        RANGE="$PREV_TAG..$RELEASE_REF"
        echo "## Merged since $PREV_TAG"
    else
        RANGE="$RELEASE_REF"
        echo "## Merged (first release)"
    fi
    echo
    # Squash-merge subjects look like "subject (#123)"; plain subjects pass
    # through. The PR reference is anchored to the end of the subject so a
    # subject containing an earlier "(#N)" keeps its full title.
    # Control characters are stripped: a crafted subject must not be able to
    # smuggle terminal control sequences into the published notes (the
    # --dry-run draft is printed to the operator's terminal, and any
    # contributor's PR title becomes a notes line). All C0 controls and DEL
    # go; tab and newline are kept (newline separates the subjects).
    # LC_ALL=C keeps tr byte-oriented so the ranges match single bytes.
    git log --first-parent --format='%s' "$RANGE" | LC_ALL=C tr -d '\000-\010\013-\037\177' | while IFS= read -r subject; do
        if [[ "$subject" =~ ^(.*)\ \(#([0-9]+)\)$ ]]; then
            num="${BASH_REMATCH[2]}"
            title="${BASH_REMATCH[1]}"
            echo "- #$num — $title"
        else
            echo "- $subject"
        fi
    done
    echo
    echo "---"
    echo "Release tag \`$TAG\` (immutable — tags are never moved or re-cut)."
    echo "Full commit \`$RELEASE_SHA\`."
} > "$NOTES"

if [[ -n "$NOTES_FILE" ]]; then
    cp "$NOTES" "$NOTES_FILE"
    echo "cut-release.sh: notes written to $NOTES_FILE"
fi

echo "cut-release.sh: ---- release-notes draft ----"
cat "$NOTES"
echo "cut-release.sh: ---- end draft ----"

have_gh() { [[ -z "${CUT_RELEASE_NO_GH:-}" ]] && command -v gh >/dev/null 2>&1; }

publish_release() {
    # Publish the GitHub release for $TAG from $NOTES. In --publish-only
    # mode the release must not already exist (the API path fail-closes on
    # this anyway: a duplicate tag returns 422 with no html_url).
    if [[ "$MODE" == "publish-only" ]] && have_gh \
            && gh release view "$TAG" >/dev/null 2>&1; then
        die "release $TAG is already published"
    fi
    GH_ARGS=(release create "$TAG" --title "$TAG" --notes-file "$NOTES" --target main)
    if [[ "$VERSION" == *-* ]]; then
        GH_ARGS+=(--prerelease)
        echo "cut-release.sh: prerelease version detected; marking GitHub release as prerelease"
    fi
    if have_gh; then
        gh "${GH_ARGS[@]}" || die "gh release create failed"
    elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
        # API fallback for operators without `gh`. The token comes from the
        # environment only and is never printed, logged, or placed on a command
        # line: it travels in a 0600 curl config file under the trap-cleaned
        # temp dir, so it never appears in ps output.
        PAYLOAD="$NOTES_DIR/payload.json"
        CURL_CFG="$NOTES_DIR/curl.cfg"
        printf 'header = "Authorization: Bearer %s"\n' "$GITHUB_TOKEN" > "$CURL_CFG"
        chmod 600 "$CURL_CFG"
        TAG="$TAG" REPO="$REPO" VERSION="$VERSION" NOTES_PATH="$NOTES" \
            python3 - > "$PAYLOAD" <<'PYEOF' || die "release payload build failed"
import json, os
with open(os.environ["NOTES_PATH"], encoding="utf-8") as f:
    body = f.read()
print(json.dumps({
    "tag_name": os.environ["TAG"],
    "target_commitish": "main",
    "name": os.environ["TAG"],
    "body": body,
    "draft": False,
    "prerelease": "-" in os.environ["VERSION"],
}))
PYEOF
        curl -sS -X POST -K "$CURL_CFG" \
            -H "Accept: application/vnd.github+json" \
            "https://api.github.com/repos/$REPO/releases" \
            -d @"$PAYLOAD" -o "$NOTES_DIR/release.json" \
            || die "release API call failed"
        python3 - "$NOTES_DIR/release.json" <<'PYEOF' || die "release API returned an error"
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    d = json.load(f)
url = d.get("html_url")
if not url:
    sys.stderr.write("github API error: %s\n" % json.dumps(d)[:500])
    sys.exit(1)
print("release URL: %s" % url)
PYEOF
    else
        die "no 'gh' on PATH and GITHUB_TOKEN unset; cannot publish the release (tag $TAG is on the remote; re-run with --publish-only once publishing is possible)"
    fi
    echo "cut-release.sh: published release $TAG on $REPO"
}

if [[ "$MODE" == "dry-run" ]]; then
    echo "cut-release.sh: dry run — no tag created, no release published."
    echo "cut-release.sh: --execute --yes would run:"
    echo "  git tag -a $TAG -m <message> && git push $REMOTE $TAG"
    echo "  gh release create $TAG --title $TAG --notes-file <notes> --target main"
    exit 0
fi

if [[ "$MODE" == "publish-only" ]]; then
    publish_release
    exit 0
fi

# --- execute: confirmation was already gated up front ---

# --- execute: tag ---
TAG_MSG="spark-vm $TAG"
git tag -a "$TAG" -m "$TAG_MSG" \
    || die "git tag failed (is a tagger identity configured? user.name/user.email)"
echo "cut-release.sh: created tag $TAG on $HEAD_SHA"
git push "$REMOTE" "$TAG" \
    || { git tag -d "$TAG" >/dev/null 2>&1 || true
         die "git push of $TAG failed (local tag removed; fix and re-run)"; }
echo "cut-release.sh: pushed $TAG to $REMOTE"

publish_release
