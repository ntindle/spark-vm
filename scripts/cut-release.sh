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
#      tag. Notes are printed (and optionally written) in --dry-run. The
#      body is capped at GitHub's 125,000-character release-body limit
#      (the Releases API 422s longer bodies): an oversized Highlights
#      section is trimmed at whole-bullet boundaries with an explicit note
#      pointing at the full CHANGELOG.md section; the merged-PR list and
#      the footer are never trimmed. If the body still exceeds the cap
#      with Highlights fully trimmed, the script dies with an operator
#      diagnostic (GitHub #1086 — the v0.6.0 cut failed its publish step
#      AND its --publish-only recovery on the same unbounded body).
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
#                  detached); implies --execute unless an explicit mode is
#                  given (the release workflow's recovery step runs
#                  --publish-only --yes --ci on the same detached checkout).
#   --notes-file   write the generated release notes to PATH as well.
#   --remote       git remote to use (default: origin; env CUT_RELEASE_REMOTE).
#
# Env: CUT_RELEASE_REMOTE (default origin), CUT_RELEASE_REPO (default
#      ntindle/spark-vm), CUT_RELEASE_DIR (repo root override; testing hook),
#      CUT_RELEASE_NO_GH (set to force the API fallback even when `gh`
#      exists; testing hook), GITHUB_TOKEN (API fallback when `gh` is
#      unavailable; never logged; GH_TOKEN accepted as an alias),
#      CUT_RELEASE_POLL_ATTEMPTS (default 10;
#      0 disables the wait) and CUT_RELEASE_POLL_SLEEP (default 3) bound
#      the post-tag-push replication wait before publishing,
#      CUT_RELEASE_MAX_BODY_CHARS (default 125000; testing hook) caps the
#      release-notes body at GitHub's 125,000-character Releases API limit.
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
                 of the local branch, then execute without --yes (unless an
                 explicit mode is given — the workflow's recovery step runs
                 --publish-only --yes --ci)
  --notes-file PATH  also write the generated notes to PATH
  --remote NAME  git remote to use (default: origin)
  -h, --help     show this help

Environment: CUT_RELEASE_REMOTE, CUT_RELEASE_REPO (default
ntindle/spark-vm), CUT_RELEASE_DIR (repo-root override, testing hook),
CUT_RELEASE_NO_GH (force the API fallback; testing hook),
GITHUB_TOKEN (API fallback when `gh` is unavailable; GH_TOKEN is
accepted as an alias — the workflow exports GH_TOKEN).
EOF
}

die() { echo "cut-release.sh: $*" >&2; exit 1; }

MODE="dry-run"
MODE_EXPLICIT=0  # set when --dry-run/--execute/--publish-only is given
CONFIRM=0
CI=0
NOTES_FILE=""
REMOTE="${CUT_RELEASE_REMOTE:-origin}"
REPO="${CUT_RELEASE_REPO:-ntindle/spark-vm}"
# GH_TOKEN is gh's conventional name (the release workflow exports it);
# accept it as a one-line alias so the API fallback is live in CI (#687 item 4).
GITHUB_TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) MODE="dry-run"; MODE_EXPLICIT=1; shift ;;
        --execute) MODE="execute"; MODE_EXPLICIT=1; shift ;;
        --publish-only) MODE="publish-only"; MODE_EXPLICIT=1; shift ;;
        --yes) CONFIRM=1; shift ;;
        --ci) CI=1; shift ;;
        --notes-file) [[ $# -ge 2 ]] || die "--notes-file needs a path"; NOTES_FILE="$2"; shift 2 ;;
        --remote) [[ $# -ge 2 ]] || die "--remote needs a name"; REMOTE="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        -*) die "unknown flag: $1 (see --help)" ;;
        *) die "unexpected argument: $1 (see --help)" ;;
    esac
done

# --ci without an explicit mode means execute (the workflow's cut step);
# an explicit --dry-run/--execute/--publish-only always wins, even with
# --ci (so --ci --dry-run stays a dry run).
if [[ "$CI" == "1" && "$MODE_EXPLICIT" == "0" ]]; then
    MODE="execute"
fi

# Fail fast on malformed poll hooks, before any remote mutation.
[[ "${CUT_RELEASE_POLL_ATTEMPTS:-10}" =~ ^[0-9]+$ ]] \
    || die "CUT_RELEASE_POLL_ATTEMPTS must be a non-negative integer (got '${CUT_RELEASE_POLL_ATTEMPTS:-10}')"
[[ "${CUT_RELEASE_POLL_SLEEP:-3}" =~ ^[0-9]+(\.[0-9]+)?$ ]] \
    || die "CUT_RELEASE_POLL_SLEEP must be a non-negative number (got '${CUT_RELEASE_POLL_SLEEP:-3}')"

# The release-body cap must be a positive integer: a zero/negative cap
# would make every release die in the trim step below.
[[ "${CUT_RELEASE_MAX_BODY_CHARS:-125000}" =~ ^[1-9][0-9]*$ ]] \
    || die "CUT_RELEASE_MAX_BODY_CHARS must be a positive integer (got '${CUT_RELEASE_MAX_BODY_CHARS:-125000}')"
MAX_BODY_CHARS="${CUT_RELEASE_MAX_BODY_CHARS:-125000}"


REPO_DIR="${CUT_RELEASE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO_DIR"
git rev-parse --git-dir >/dev/null 2>&1 || die "not a git repo: $REPO_DIR"

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

# --- release-notes body cap (GitHub #1086) ---
# GitHub's Releases API rejects bodies over 125,000 characters with HTTP
# 422 "body is too long". The v0.6.0 cut hit this in --execute AND in the
# --publish-only recovery (the recovery regenerates the same unbounded
# body), so the cap is enforced here, on the shared assembly path, before
# --notes-file is written and before any publish attempt. Only the curated
# Highlights section is trimmed — at whole-line (whole-bullet) boundaries,
# with an explicit note pointing at the full CHANGELOG.md section; the
# merged-PR list and the footer are never trimmed. If the body still
# exceeds the cap with Highlights fully trimmed, the script dies with an
# operator diagnostic. CUT_RELEASE_MAX_BODY_CHARS exists only so tests can
# exercise the trim; production always uses GitHub's real limit. Lengths
# are counted in Unicode code points, matching how the API measures the
# JSON body.
TRIM_MSG="$(MAX_BODY_CHARS="$MAX_BODY_CHARS" python3 - "$NOTES" <<'PYEOF' 2>&1
import os
import sys

notes_path = sys.argv[1]
cap = int(os.environ["MAX_BODY_CHARS"])
cap_fmt = f"{cap:,}"

with open(notes_path, encoding="utf-8") as f:
    text = f.read()

if len(text) <= cap:
    print("cut-release.sh: release notes %s characters (cap %s) - no trim needed"
          % (f"{len(text):,}", cap_fmt))
    sys.exit(0)

lines = text.split("\n")

def find(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    return -1

i_high = find(lambda l: l == "## Highlights")
i_merge = find(lambda l: l.startswith("## Merged"),
               i_high + 1 if i_high >= 0 else 0)
i_sep = -1
if i_merge >= 0:
    for i in range(i_merge + 1, len(lines) - 1):
        if lines[i] == "---" and lines[i + 1].startswith("Release tag "):
            i_sep = i
            break
if i_high < 0 or i_merge < 0 or i_sep < 0:
    sys.stderr.write("internal error: release-notes structure changed; "
                     "cannot apply the body cap\n")
    sys.exit(1)

HEADER_PREFIX = "## Highlights\n\n"
# The section content sits between the header's blank line and the blank
# line before "## Merged ...". (The awk that extracts the section stops at
# the next "## " heading, so the content itself never contains a "## "
# line that could confuse the marker search above.)
content = lines[i_high + 2:i_merge - 1]
pr_block = "\n".join(lines[i_merge:i_sep]) + "\n"
footer = "\n".join(lines[i_sep:]) + "\n"

trim_note = ("_The Highlights section was trimmed to fit the %s-character "
             "release-body limit; the full section is in CHANGELOG.md on "
             "this tag._\n" % cap_fmt)

# Even a fully trimmed Highlights section keeps its header, the trim note,
# the whole merged-PR list, and the footer.
floor_len = len(HEADER_PREFIX + trim_note + pr_block + footer)
if floor_len > cap:
    sys.stderr.write(
        "release notes are %s characters and still exceed the %s-character "
        "release-body limit with the Highlights section fully trimmed - "
        "the merged-PR list alone is too long to publish. Trim the PR list "
        "by hand: cut-release.sh --dry-run --notes-file notes.md, edit the "
        "file, then publish with: gh release create <tag> --title <tag> "
        "--notes-file notes.md --target main\n"
        % (f"{len(text):,}", cap_fmt))
    sys.exit(1)

kept = []
kept_len = floor_len
dropped = 0
for ln in content:
    # Whole lines only: a bullet is kept entire or dropped entire, never
    # split mid-line.
    if kept_len + len(ln) + 1 <= cap:
        kept.append(ln)
        kept_len += len(ln) + 1
    else:
        dropped += 1
# A subsection header ("### Added") with no surviving bullets underneath
# would dangle at the end of the trimmed section; drop it.
while kept and kept[-1].startswith("### "):
    kept_len -= len(kept.pop()) + 1
    dropped += 1

new_text = HEADER_PREFIX
if kept:
    new_text += "\n".join(kept) + "\n"
new_text += trim_note + pr_block + footer
# Invariant by construction: kept_len tracked every addition, and the
# header-pop only shrinks it; floor_len <= cap was checked above.
with open(notes_path, "w", encoding="utf-8") as f:
    f.write(new_text)
print("cut-release.sh: release notes trimmed to %s characters (cap %s); "
      "%d Highlights line(s) dropped" % (f"{len(new_text):,}", cap_fmt, dropped))
PYEOF
)" || die "$TRIM_MSG"
echo "$TRIM_MSG" >&2

if [[ -n "$NOTES_FILE" ]]; then
    cp "$NOTES" "$NOTES_FILE"
    echo "cut-release.sh: notes written to $NOTES_FILE"
fi

echo "cut-release.sh: ---- release-notes draft ----"
cat "$NOTES"
echo "cut-release.sh: ---- end draft ----"

have_gh() { [[ -z "${CUT_RELEASE_NO_GH:-}" ]] && command -v gh >/dev/null 2>&1; }

# Emit the body of GET /repos/$REPO/<endpoint> to stdout; nonzero exit on
# transport failure or an HTTP error status (gh's `api --silent` fails on
# 4xx/5xx; the token path uses curl --fail for the same semantics). The
# token path reuses the 0600-config-file pattern: the token never appears
# on a command line.
# Print the path of a 0600 curl config file carrying the GitHub token
# as an Authorization header (the token never appears on a command line).
# The file lives under $NOTES_DIR, so the EXIT trap cleans it on any
# abnormal-but-catchable exit too; callers either rm -f it on the normal
# path right after use (api_get) or leave it for the EXIT trap
# (publish_release — the config must survive the whole publish sequence).
# (mktemp creates 0600, so the token is never readable by other users
# even for an instant.)
token_curl_cfg() {
    local cfg; cfg="$(mktemp -p "$NOTES_DIR")"
    printf 'header = "Authorization: Bearer %s"\n' "$GITHUB_TOKEN" > "$cfg"
    printf '%s\n' "$cfg"
}

api_get() {
    local endpoint="$1"
    if have_gh; then
        gh api --silent "repos/$REPO/$endpoint"
    else
        local cfg; cfg="$(token_curl_cfg)"
        # Bounded per-attempt: a blackholed network must not hang one poll
        # far past the whole wait budget.
        curl -sS --fail --connect-timeout 10 --max-time 30 -K "$cfg" \
            -H "Accept: application/vnd.github+json" \
            "https://api.github.com/repos/$REPO/$endpoint"
        local rc=$?
        rm -f "$cfg"
        return $rc
    fi
}

# True when the GitHub API can see the just-pushed tag in its git-ref
# namespace — the same namespace the Releases API validates `tag_name`
# against, so visibility here is the publish precondition the v0.5.0 cut
# (#659) violated by racing. Exit-code based: both api_get paths fail on
# HTTP errors, so no body sniffing is needed.
tag_visible_to_api() {
    api_get "git/ref/tags/$TAG" >/dev/null 2>&1
}

# Bounded best-effort wait for the pushed tag to become visible to the
# GitHub API before publishing. Never fatal on timeout: it prints a
# WARNING and the publish attempt still runs — the workflow's publish-only
# recovery step covers a tag-pushed/publish-failed outcome (GitHub #659),
# and refusing to publish at all would guarantee exactly that state.
# CUT_RELEASE_POLL_ATTEMPTS=0 disables the wait explicitly (no warning).
wait_for_tag_replication() {
    local attempts="${CUT_RELEASE_POLL_ATTEMPTS:-10}"
    local sleep_s="${CUT_RELEASE_POLL_SLEEP:-3}"
    # (validated up front, before any remote mutation)
    if (( attempts == 0 )); then
        echo "cut-release.sh: tag replication wait disabled (CUT_RELEASE_POLL_ATTEMPTS=0)"
        return 0
    fi
    local i=1
    while (( i <= attempts )); do
        if tag_visible_to_api; then
            echo "cut-release.sh: tag $TAG visible to the GitHub API (poll $i/$attempts)"
            return 0
        fi
        sleep "$sleep_s"
        i=$((i + 1))
    done
    echo "cut-release.sh: WARNING: tag $TAG not visible to the GitHub API after $attempts polls; attempting publish anyway" >&2
    return 0
}

publish_release() {
    # Publish the GitHub release for $TAG from $NOTES. In --publish-only
    # mode the release must not already exist (the API path fail-closes on
    # this anyway: a duplicate tag returns 422 with no html_url).
    if [[ "$MODE" == "publish-only" ]] && have_gh \
            && gh release view "$TAG" >/dev/null 2>&1; then
        die "release $TAG is already published"
    fi
    # Auth-gated replication wait: the tag pushed seconds ago can be
    # invisible to the Releases API's tag_name validation (replication
    # lag — the tag-pushed/publish-failed state #659 documented). Waiting
    # here, rather than only on the --execute path, makes --publish-only
    # self-healing for its exact recovery purpose instead of re-failing
    # loudly seconds after the first publish attempt. Skipped when
    # publishing is impossible anyway (no gh, no token): publish_release
    # fail-closes immediately below with its own diagnostic.
    if have_gh || [[ -n "${GITHUB_TOKEN:-}" ]]; then
        wait_for_tag_replication
    fi
    GH_ARGS=(release create "$TAG" --title "$TAG" --notes-file "$NOTES" --target main)
    if [[ "$VERSION" == *-* ]]; then
        GH_ARGS+=(--prerelease)
        echo "cut-release.sh: prerelease version detected; marking GitHub release as prerelease"
    fi
    if have_gh; then
        echo "cut-release.sh: publishing release $TAG via gh"
        gh "${GH_ARGS[@]}" || die "gh release create failed for $TAG (gh's error is above)"
        # The release URL is the operator's handle on the published state.
        # Non-fatal: if the view lags the create, the publish already
        # succeeded — don't turn a diagnostics read into a failure.
        local RELEASE_URL=""
        RELEASE_URL="$(gh release view "$TAG" --json url -q .url 2>/dev/null || true)"
        [[ -n "$RELEASE_URL" ]] && echo "cut-release.sh: release URL: $RELEASE_URL"
    elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
        echo "cut-release.sh: publishing release $TAG via GitHub API fallback (no gh on PATH)"
        # API fallback for operators without `gh`. The token comes from the
        # environment only and is never printed, logged, or placed on a command
        # line: it travels in a 0600 curl config file under the trap-cleaned
        # temp dir, so it never appears in ps output.
        PAYLOAD="$NOTES_DIR/payload.json"
        CURL_CFG="$(token_curl_cfg)"
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
        curl -sS -X POST --connect-timeout 10 --max-time 30 -K "$CURL_CFG" \
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
print("cut-release.sh: release URL: %s" % url)
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

# Give the Releases API a moment to see the tag before publishing: a tag
# pushed seconds ago can be invisible to the API's tag_name validation
# (replication lag), and gh release create then fails even though the tag
# is on the remote — the tag-pushed/publish-failed state GitHub #659
# documented. Bounded and non-fatal by design (see the function).

publish_release
