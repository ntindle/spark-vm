#!/usr/bin/env python3
"""Release-health drift check: every release tag must have a published release,
and every published release must have a passing golden-image build gate.

Background: the release pipeline (scripts/cut-release.sh +
.github/workflows/release.yml) cuts an immutable v* tag and publishes a
GitHub release for it. The workflow recovers the tag-pushed / publish-failed
class in the same run (GitHub #659 — the v0.5.0 cut), but anything that fails
*outside* that recovery window — a hand-pushed tag, a failed recovery, a
publish that silently never happened — drifts silently: a tag the project
advertises as a release that GitHub never published, or a published release
with no tag behind it.

The second drift class is the golden-image gate: release.yml calls
.github/workflows/golden-image.yml (the automatable half of
docs/GOLDEN_IMAGE_GATE_PROCEDURE.md) after publishing. A published release
whose gate never passed — the release job succeeded but the gate job failed,
or no release run is on record for the tag's commit — leaves the release
shippable in name only: no gate record, no publishable image. The v0.9.0 cut
shipped exactly this way (release success, gate "Build the recipe" failure,
fixed later by #1736 with no re-verification on record). This script fails
loud on both classes.

This script is the standing answer to that drift class. It is read-only:
no tags are created, no releases are published, no workflows are dispatched,
no mutations of any kind. It exits 0 when the published release surface is
consistent, 2 when drift is found, 1 on operational errors (network failures
fail loud — a monitor that fails silently is the failure mode being
prevented).

Usage:
    release_health.py [--repo OWNER/REPO] [--json] [--api-url URL]

Env: GITHUB_TOKEN / GH_TOKEN (optional) raises the GitHub API rate limit;
the token is sent in the Authorization header and never logged. Without it
the unauthenticated quota (60 requests/hour) is enough for one daily run.
The gate check reads workflow runs via the Actions API, which needs a token
with `actions: read` (the scheduled workflow grants it); without one the
gate check degrades to operational error, never to a silent pass.

Pure stdlib. The consistency core (check_consistency, check_gate_coverage)
is hermetic and unit-tested; network fetching sits at the edges
(fetch_tags, fetch_releases, fetch_gate_verdicts) and is injectable for
tests.
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

# Release-tag grammar: `v` + strict semver — the same grammar cut-release.sh's
# preflight enforces (and sparkvm_version.py parses). Non-release tags (e.g.
# `ghost/20261002-2129`) are not release candidates and are ignored.
_SEMVER_CORE = (
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
)
_SEMVER_RE = re.compile(r"\A" + _SEMVER_CORE + r"\Z")
_RELEASE_TAG_RE = re.compile(r"\Av" + _SEMVER_CORE + r"\Z")


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


def _parse_ls_remote_deref(output):
    """Parse `git ls-remote --tags` into {tag: commit-sha} for deref lines.

    Annotated tags appear twice: `refs/tags/<tag>` names the tag object and
    `refs/tags/<tag>^{}` names the commit it points at. The gate check needs
    the *commit* sha (the release workflow runs on the tag's commit), so the
    deref line wins. Lightweight tags have no deref line; the plain line's
    sha is the commit itself and is used as the fallback.
    """
    deref = {}
    plain = {}
    for line in (output or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2 or not parts[1].startswith("refs/tags/"):
            continue
        sha, ref = parts
        name = ref[len("refs/tags/"):]
        if name.endswith("^{}"):
            deref[name[: -len("^{}")]] = sha
        else:
            plain[name] = sha
    out = dict(plain)
    out.update(deref)
    return out


def fetch_tag_shas(repo):
    """Map tag name -> commit sha on the repo's remote (read-only, no clone)."""
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
    return _parse_ls_remote_deref(proc.stdout or "")


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

    Never raises on malformed entries: unparseable rows are skipped, and a
    non-list payload degrades to an empty page.
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


# The golden-image gate job inside a release.yml run. When the gate runs via
# workflow_call its job name carries the caller prefix
# ("golden-image build gate / ..."); a direct dispatch names it bare. Match
# the stable suffix either way.
_GATE_JOB_SUFFIX = "build recipe + baked-secrets scan + manifest preflight"
_RELEASE_WORKFLOW_FILE = "release.yml"


def _default_api_get(url, token):
    return _api_get(url, token)


def fetch_gate_verdict_for_sha(repo, sha, api_url="https://api.github.com",
                               _api_get=None):
    """Read the golden-image gate verdict for one commit sha (read-only).

    Finds the release.yml workflow run on that head_sha and returns
    (verdict, run_id):
      - "success": the gate job concluded success.
      - "failure": the gate job concluded anything other than success
        (failure, cancelled, timed_out, action_required, stale).
      - "pending": a release.yml run exists for the sha but none has
        completed yet (gate verdict not yet knowable — not a pass).
      - "missing": no release.yml run exists for the sha at all.
      - "not-applicable": a release.yml run completed for the sha but it
        carries no gate job (releases cut before the gate was wired in).
    run_id is the workflow run the verdict came from, or None when missing.
    _api_get is the injectable network edge for tests.
    """
    api_get = _api_get or _default_api_get
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    url = ("%s/repos/%s/actions/workflows/%s/runs"
           "?head_sha=%s&per_page=5&exclude_pull_requests=true"
           % (api_url.rstrip("/"), repo, _RELEASE_WORKFLOW_FILE, sha))
    data, _ = api_get(url, token)
    runs = data.get("workflow_runs") if isinstance(data, dict) else None
    if not runs:
        return "missing", None
    completed = [r for r in runs
                 if isinstance(r, dict) and r.get("status") == "completed"]
    if not completed:
        first = runs[0] if isinstance(runs[0], dict) else {}
        return "pending", first.get("id")
    run = max(completed, key=lambda r: r.get("updated_at") or "")
    run_id = run.get("id")
    jobs_url = ("%s/repos/%s/actions/runs/%s/jobs?per_page=30"
                % (api_url.rstrip("/"), repo, run_id))
    jobs_data, _ = api_get(jobs_url, token)
    jobs = jobs_data.get("jobs") if isinstance(jobs_data, dict) else None
    gate = None
    for job in jobs or []:
        if isinstance(job, dict) and str(job.get("name", "")).endswith(
                _GATE_JOB_SUFFIX):
            gate = job
            break
    if gate is None:
        return "not-applicable", run_id
    if gate.get("conclusion") == "success":
        return "success", run_id
    return "failure", run_id


def fetch_gate_verdicts(repo, tag_shas, api_url="https://api.github.com"):
    """Map commit sha -> (verdict, run_id) for the golden-image gate.

    tag_shas: {tag: commit-sha}. One release.yml run lookup + one jobs
    lookup per sha — bounded by the release count, which grows slowly.
    Read-only; a 403 here (token without `actions: read`) is an operational
    error, never a silent pass.
    """
    verdicts = {}
    for _tag, sha in sorted((tag_shas or {}).items()):
        if not isinstance(sha, str) or not sha:
            continue
        if sha in verdicts:
            continue
        verdicts[sha] = fetch_gate_verdict_for_sha(repo, sha, api_url)
    return verdicts


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


def check_gate_coverage(published_tags, tag_shas, gate_verdicts):
    """Pure gate core: return the gate drift list (empty when clean).

    published_tags: release-grammar tags with a published (non-draft)
    release behind them — the set the gate owes a verdict to.
    tag_shas: {tag: commit-sha} from the remote.
    gate_verdicts: {sha: (verdict, run_id)} from fetch_gate_verdicts.
    Each drift is {"kind", "tag", "detail"}:
      - gate-failed: the gate job for the tag's commit did not conclude
        success (run id cited so the failure is one click away).
      - gate-unverified: no verdict exists yet — no release.yml run for the
        tag's commit ("missing"), or the run has not completed ("pending").
        A pending gate is not a pass.
    "not-applicable" (release.yml run completed but predates the gate) is
    skipped, not drift — the gate cannot owe a verdict to a release cut
    before it existed. Malformed inputs never raise: they are skipped.
    """
    drifts = []
    clean_tags = sorted(t for t in (published_tags or [])
                        if isinstance(t, str) and t)
    for tag in clean_tags:
        sha = (tag_shas or {}).get(tag)
        if not isinstance(sha, str) or not sha:
            drifts.append({
                "kind": "gate-unverified",
                "tag": tag,
                "detail": "tag's commit sha is unknown, so no gate verdict "
                "can be looked up",
            })
            continue
        verdict, run_id = (gate_verdicts or {}).get(sha, ("missing", None))
        if verdict == "success" or verdict == "not-applicable":
            continue
        if verdict == "failure":
            drifts.append({
                "kind": "gate-failed",
                "tag": tag,
                "detail": "golden-image gate did not pass for this release "
                "(release.yml run %s)" % run_id,
            })
        elif verdict == "pending":
            drifts.append({
                "kind": "gate-unverified",
                "tag": tag,
                "detail": "release.yml run %s has not completed yet — no "
                "gate verdict on record" % run_id,
            })
        else:  # "missing" or anything unrecognized: fail loud, never silent
            drifts.append({
                "kind": "gate-unverified",
                "tag": tag,
                "detail": "no release.yml run found for the tag's commit; "
                "dispatch golden-image.yml on the tag to verify",
            })
    return drifts


def format_text(repo, tags, releases, drifts, gate_drifts=()):
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
    if gate_drifts is None:
        lines.append("  gate check skipped (--skip-gate): no verdict on the "
                     "golden-image gate")
    elif not gate_drifts:
        lines.append("  OK: golden-image gate passed for every published release")
    else:
        lines.append("  GATE DRIFT (%d):" % len(gate_drifts))
        for d in gate_drifts:
            lines.append("    - %s: %s — %s" % (d["kind"], d["tag"], d["detail"]))
    return "\n".join(lines)


def main(argv=None, _fetch_tags=None, _fetch_releases=None,
         _fetch_tag_shas=None, _fetch_gate_verdicts=None):
    """Run the check. Network functions are injectable for tests."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="ntindle/spark-vm")
    parser.add_argument("--json", action="store_true",
                        help="machine-readable output")
    parser.add_argument("--api-url", default="https://api.github.com",
                        help="GitHub API base (testing hook)")
    parser.add_argument("--skip-gate", action="store_true",
                        help="skip the golden-image gate check (e.g. when the "
                        "token lacks actions:read)")
    args = parser.parse_args(argv)

    fetch_tags_fn = _fetch_tags or fetch_tags
    fetch_releases_fn = _fetch_releases or fetch_releases
    fetch_tag_shas_fn = _fetch_tag_shas or fetch_tag_shas
    fetch_gate_verdicts_fn = _fetch_gate_verdicts or fetch_gate_verdicts
    try:
        tags = fetch_tags_fn(args.repo)
        releases = fetch_releases_fn(args.repo, args.api_url)
    except RuntimeError as exc:
        print("release_health: error: %s" % exc, file=sys.stderr)
        return EXIT_ERROR

    drifts = check_consistency(tags, releases)

    # The gate owes a verdict to every published release: release-grammar
    # tags with a non-draft release behind them, present on the remote.
    tag_set = set(t for t in (tags or []) if isinstance(t, str))
    published_tags = set()
    for r in releases or []:
        if not isinstance(r, dict):
            continue
        tag = r.get("tag_name")
        if (isinstance(tag, str) and tag and not r.get("draft")
                and tag in tag_set and is_release_tag(tag)):
            published_tags.add(tag)

    gate_drifts = None  # None = skipped; [] = checked and clean
    if not args.skip_gate:
        try:
            tag_shas = fetch_tag_shas_fn(args.repo)
            gate_verdicts = fetch_gate_verdicts_fn(
                args.repo,
                {t: tag_shas.get(t) for t in published_tags},
                args.api_url)
        except RuntimeError as exc:
            print("release_health: error: %s" % exc, file=sys.stderr)
            return EXIT_ERROR
        gate_drifts = check_gate_coverage(published_tags, tag_shas,
                                          gate_verdicts)

    if args.json:
        print(json.dumps({
            "ok": not drifts and not gate_drifts,
            "repo": args.repo,
            "drifts": drifts,
            "gate_drifts": gate_drifts,
        }, indent=2, sort_keys=True))
    else:
        print(format_text(args.repo, tags, releases, drifts, gate_drifts))
    return EXIT_OK if not drifts and not gate_drifts else EXIT_DRIFT


if __name__ == "__main__":
    sys.exit(main())
