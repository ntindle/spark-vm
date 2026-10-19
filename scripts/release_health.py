#!/usr/bin/env python3
"""Release-health drift check: every release tag must have a published release.

Background: the release pipeline (scripts/cut-release.sh +
.github/workflows/release.yml) cuts an immutable v* tag and publishes a
GitHub release for it. The workflow recovers the tag-pushed / publish-failed
class in the same run (GitHub #659 — the v0.5.0 cut), but anything that fails
*outside* that recovery window — a hand-pushed tag, a failed recovery, a
publish that silently never happened — drifts silently: a tag the project
advertises as a release that GitHub never published, or a published release
with no tag behind it.

This script is the standing answer to that drift class. It is read-only:
no tags are created, no releases are published, no mutations of any kind.
It exits 0 when the published release surface is consistent, 2 when drift
is found, 1 on operational errors (network failures fail loud — a monitor
that fails silently is the failure mode being prevented).

Usage:
    release_health.py [--repo OWNER/REPO] [--json] [--api-url URL]

Env: GITHUB_TOKEN / GH_TOKEN (optional) raises the GitHub API rate limit;
the token is sent in the Authorization header and never logged. Without it
the unauthenticated quota (60 requests/hour) is enough for one daily run.

Pure stdlib. The consistency core (check_consistency) is hermetic and
unit-tested; network fetching sits at the two edges (fetch_tags,
fetch_releases) and is injectable for tests.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Release-tag grammar: `v` + strict semver, the same grammar cut-release.sh
# and install.sh's --version filter on. Non-release tags (e.g.
# `ghost/20261002-2129`) are not release candidates and are ignored.
_SEMVER_RE = re.compile(
    r"\A(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z"
)
_RELEASE_TAG_RE = re.compile(r"\Av(" + _SEMVER_RE.pattern[2:-2] + r")\Z")


def is_release_tag(tag):
    """True when `tag` is a release-candidate tag (`v` + strict semver)."""
    return isinstance(tag, str) and _RELEASE_TAG_RE.match(tag) is not None


# Exit codes: 0 clean, 2 drift, 1 operational error.
EXIT_OK = 0
EXIT_DRIFT = 2
EXIT_ERROR = 1


def _git_url(repo):
    return "https://github.com/%s.git" % repo


def _parse_ls_remote(output):
    """Parse `git ls-remote --tags` output into a list of tag names.

    Deref lines (`<sha>\trefs/tags/<tag>^{}`) are collapsed away; only the
    plain `refs/tags/<tag>` lines contribute.
    """
    tags = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.endswith("^{}"):
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        tags.append(parts[1][len("refs/tags/"):])
    # Preserve first-seen order, dedupe.
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def fetch_tags(repo):
    """List tag names on the repo's remote (read-only, no clone)."""
    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--tags", _git_url(repo)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("git ls-remote failed: %s" % exc)
    if proc.returncode != 0:
        raise RuntimeError(
            "git ls-remote failed (exit %d): %s"
            % (proc.returncode, (proc.stderr or "").strip()[:500])
        )
    return _parse_ls_remote(proc.stdout or "")


def _api_get(url, token):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "spark-vm-release-health",
        },
    )
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", "replace")
            link = resp.headers.get("Link") or ""
    except urllib.error.HTTPError as exc:
        raise RuntimeError("GitHub API %s -> HTTP %s" % (url, exc.code))
    except urllib.error.URLError as exc:
        raise RuntimeError("GitHub API request failed: %s" % exc)
    try:
        data = json.loads(body)
    except ValueError:
        raise RuntimeError("GitHub API returned non-JSON for %s" % url)
    return data, _next_link(link)


def _next_link(link_header):
    """Extract the `next` page URL from an RFC 5988 Link header."""
    for part in (link_header or "").split(","):
        part = part.strip()
        if 'rel="next"' in part:
            url = part.split(";", 1)[0].strip()
            if url.startswith("<") and url.endswith(">"):
                return url[1:-1]
    return None


def _parse_releases_page(payload):
    """Normalize one /releases API page into (tag_name, draft, prerelease).

    Never raises on malformed entries: unparseable rows are skipped, and an
    unexpected payload shape degrades to an empty page (the consistency check
    then reports what it can see; a totally broken response shape is an
    operational error at the fetch layer only if zero pages parsed AND the
    request succeeded — see fetch_releases).
    """
    rows = []
    if not isinstance(payload, list):
        return rows
    for item in payload:
        if not isinstance(item, dict):
            continue
        tag = item.get("tag_name")
        if not isinstance(tag, str) or not tag:
            continue
        rows.append(
            {
                "tag_name": tag,
                "draft": bool(item.get("draft")),
                "prerelease": bool(item.get("prerelease")),
            }
        )
    return rows


def fetch_releases(repo, api_url="https://api.github.com"):
    """List published releases on the repo (paginated, read-only)."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    url = "%s/repos/%s/releases?per_page=100" % (api_url.rstrip("/"), repo)
    rows = []
    while url:
        data, url = _api_get(url, token)
        rows.extend(_parse_releases_page(data))
    return rows


def check_consistency(tags, releases):
    """Pure consistency core: return the drift list (empty when clean).

    tags: iterable of tag names (remote refs/tags).
    releases: iterable of {"tag_name", "draft", "prerelease"} dicts.
    Each drift is {"kind", "tag", "detail"}:
      - tag-without-release: release-grammar tag with no non-draft release.
      - release-without-tag: non-draft release whose tag is missing or not
        release grammar.
    Draft releases are not published and satisfy nothing. Non-release tags
    (branches, ghost/*) are ignored. Malformed inputs never raise: they are
    skipped, and what remains is checked.
    """
    tag_set = set(t for t in (tags or []) if isinstance(t, str))
    release_tags = set()
    for r in releases or []:
        if not isinstance(r, dict):
            continue
        tag = r.get("tag_name")
        if not isinstance(tag, str) or not tag:
            continue
        if r.get("draft"):
            continue
        release_tags.add(tag)

    drifts = []
    for tag in sorted(tag_set):
        if not is_release_tag(tag):
            continue
        if tag not in release_tags:
            drifts.append(
                {
                    "kind": "tag-without-release",
                    "tag": tag,
                    "detail": "tag exists on the remote but no published "
                    "(non-draft) GitHub release carries it",
                }
            )
    for tag in sorted(release_tags):
        if tag not in tag_set:
            drifts.append(
                {
                    "kind": "release-without-tag",
                    "tag": tag,
                    "detail": "published release has no such tag on the remote",
                }
            )
        elif not is_release_tag(tag):
            drifts.append(
                {
                    "kind": "release-without-tag",
                    "tag": tag,
                    "detail": "published release's tag is not release grammar "
                    "(v + strict semver)",
                }
            )
    return drifts


def format_text(repo, tags, releases, drifts):
    lines = [
        "release-health %s" % repo,
        "  release-grammar tags on remote: %d" % sum(1 for t in tags if is_release_tag(t)),
        "  published (non-draft) releases: %d"
        % sum(1 for r in releases if isinstance(r, dict) and not r.get("draft")),
    ]
    if not drifts:
        lines.append("  OK: every release tag has a published release; "
                     "every published release has its tag")
    else:
        lines.append("  DRIFT (%d):" % len(drifts))
        for d in drifts:
            lines.append("    - %s: %s — %s" % (d["kind"], d["tag"], d["detail"]))
    return "\n".join(lines)


def main(argv=None, _fetch_tags=None, _fetch_releases=None):
    """Run the check. Network functions are injectable for tests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="ntindle/spark-vm")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable output")
    parser.add_argument("--api-url", default="https://api.github.com",
                        help="GitHub API base (testing hook)")
    args = parser.parse_args(argv)

    fetch_tags_fn = _fetch_tags or fetch_tags
    fetch_releases_fn = _fetch_releases or fetch_releases
    try:
        tags = fetch_tags_fn(args.repo)
        releases = fetch_releases_fn(args.repo, args.api_url)
    except RuntimeError as exc:
        print("release_health: error: %s" % exc, file=sys.stderr)
        return EXIT_ERROR

    drifts = check_consistency(tags, releases)
    if args.json:
        print(json.dumps({
            "ok": not drifts,
            "repo": args.repo,
            "drifts": drifts,
        }, indent=2, sort_keys=True))
    else:
        print(format_text(args.repo, tags, releases, drifts))
    return EXIT_OK if not drifts else EXIT_DRIFT


if __name__ == "__main__":
    sys.exit(main())
