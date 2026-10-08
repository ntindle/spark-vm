"""Tests for scripts/cut-release.sh.

Run from the repo root:  python3 -m pytest scripts/test_cut_release.py -q

The tests build throwaway git repos (a bare "origin" + a work clone) and run
the real script against them via the CUT_RELEASE_DIR testing hook, so no
test ever touches the real repo or the network. A fake `gh` on PATH records
release-publish calls instead of hitting the GitHub API.
"""

import os
import shutil
import stat
import subprocess

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO, "scripts", "cut-release.sh")


def git(*args, cwd):
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd), capture_output=True, text=True, check=True, timeout=60,
    )


def write_changelog(work, version, section=True):
    body = "# Changelog\n\n## [Unreleased]\n\n"
    if section:
        body += ("## [%s] - 2026-09-19\n\n### Added\n"
                 "- Demo release bullet for %s\n\n" % (version, version))
    body += "## [0.1.0] - 2026-09-18\n\n### Added\n- First version\n"
    (work / "CHANGELOG.md").write_text(body)


@pytest.fixture
def workrepo(tmp_path):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)],
                   check=True, capture_output=True, timeout=60)
    work = tmp_path / "work"
    work.mkdir()
    git("init", "-b", "main", cwd=work)
    git("remote", "add", "origin", str(origin), cwd=work)
    scripts = work / "scripts"
    scripts.mkdir()
    shutil.copy(os.path.join(REPO, "scripts", "sparkvm_version.py"),
                scripts / "sparkvm_version.py")
    (work / "VERSION").write_text("0.2.0\n")
    write_changelog(work, "0.2.0")
    git("add", "-A", cwd=work)
    git("commit", "-m", "release: bump VERSION to 0.2.0", cwd=work)
    git("push", "-u", "origin", "main", cwd=work)
    return work


FAKE_GH = """#!/bin/sh
{
echo "ARGS: $*"
prev=""
for a in "$@"; do
  if [ "$prev" = "--notes-file" ]; then
    echo "NOTES-FILE: $a"
    cat "$a"
  fi
  prev="$a"
done
} >> "$GH_LOG"
exit 0
"""


@pytest.fixture
def fake_gh(tmp_path):
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(FAKE_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    log = tmp_path / "gh.log"
    return bindir, log


def run_script(work, *args, env=None):
    e = dict(os.environ)
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(k, None)
    e["CUT_RELEASE_DIR"] = str(work)
    # The script itself runs git (tag/push): give it an identity without
    # touching the operator's global gitconfig.
    e.setdefault("GIT_AUTHOR_NAME", "cut-release-test")
    e.setdefault("GIT_AUTHOR_EMAIL", "t@t")
    e.setdefault("GIT_COMMITTER_NAME", "cut-release-test")
    e.setdefault("GIT_COMMITTER_EMAIL", "t@t")
    if env:
        e.update(env)
    return subprocess.run(
        ["bash", SCRIPT, *args], cwd=str(work), env=e,
        capture_output=True, text=True, timeout=120,
    )


def run_with_gh(work, fake_gh, *args, env=None):
    bindir, log = fake_gh
    e = {"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
         "GH_LOG": str(log)}
    if env:
        e.update(env)
    r = run_script(work, *args, env=e)
    recorded = log.read_text() if log.exists() else ""
    return r, recorded


def bare_tags(work):
    # The bare origin lives next to the work dir in these fixtures.
    origin = work.parent / "origin.git"
    r = subprocess.run(["git", "--git-dir", str(origin), "tag", "--list"],
                       capture_output=True, text=True, check=True, timeout=60)
    return r.stdout.split()


# --- dry-run: plans, changes nothing ---

def test_dry_run_plans_release_and_changes_nothing(workrepo):
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "VERSION=0.2.0 tag=v0.2.0" in r.stdout
    assert "Demo release bullet for 0.2.0" in r.stdout  # changelog section used
    assert "dry run" in r.stdout
    assert bare_tags(workrepo) == []
    assert subprocess.run(["git", "tag", "--list"], cwd=str(workrepo),
                           capture_output=True, text=True,
                           timeout=60).stdout.strip() == ""


def test_dry_run_warns_without_changelog_section(workrepo):
    write_changelog(workrepo, "0.2.0", section=False)
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "docs: drop section", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "No curated CHANGELOG.md section" in r.stdout
    assert "WARNING: no CHANGELOG.md section" in r.stderr


def test_dry_run_lists_merged_prs_since_previous_tag(workrepo):
    (workrepo / "feat.txt").write_text("x\n")
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "feat: widget (#34)", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "## Merged (first release)" in r.stdout
    assert "- #34 — feat: widget" in r.stdout


def test_dry_run_ranges_pr_list_from_previous_tag(workrepo):
    first = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"],
                           cwd=str(workrepo), capture_output=True, text=True,
                           check=True, timeout=60).stdout.strip()
    git("tag", "v0.1.0", first, cwd=workrepo)
    git("push", "origin", "v0.1.0", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "## Merged since v0.1.0" in r.stdout


def test_dry_run_without_changelog(workrepo):
    (workrepo / "CHANGELOG.md").unlink()
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "docs: drop changelog", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "No curated CHANGELOG.md section" in r.stdout


def test_changelog_section_with_build_metadata(workrepo):
    (workrepo / "VERSION").write_text("1.2.0+build\n")
    changelog = workrepo / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [Unreleased]\n\n"
        "## [1.2.000build] - 2026-09-19\n\n### Added\n- DECOY SECTION\n\n"
        "## [1.2.0+build] - 2026-09-19\n\n### Added\n- Real bullet for build metadata\n\n"
    )
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "release: bump VERSION to 1.2.0+build", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "Real bullet for build metadata" in r.stdout
    assert "DECOY SECTION" not in r.stdout


def test_ci_superseded_bump_fails_sync_by_design(workrepo, tmp_path, fake_gh):
    other = tmp_path / "other"
    subprocess.run(["git", "clone", str(workrepo.parent / "origin.git"),
                    str(other)], check=True, capture_output=True, timeout=60)
    (other / "VERSION").write_text("0.2.0\n")
    (other / "extra.txt").write_text("y\n")
    git("add", "-A", cwd=other)
    git("commit", "-m", "release: bump VERSION to 0.2.1", cwd=other)
    git("push", "origin", "main", cwd=other)
    git("checkout", "--detach", "HEAD", cwd=workrepo)  # the superseded bump
    r, _ = run_with_gh(workrepo, fake_gh, "--ci",
                       env={"GITHUB_REF": "refs/heads/main"})
    assert r.returncode != 0
    assert "is not" in r.stderr and "origin/main" in r.stderr
    assert bare_tags(workrepo) == []  # no release cut for the superseded bump


def test_publish_only_refuses_when_nothing_to_publish(workrepo, fake_gh):
    r, _ = run_with_gh(workrepo, fake_gh, "--publish-only", "--yes")
    assert r.returncode != 0
    assert "does not exist locally" in r.stderr


def test_publish_only_refuses_already_published(workrepo, fake_gh):
    git("tag", "-a", "v0.2.0", "-m", "release v0.2.0", cwd=workrepo)
    git("push", "origin", "v0.2.0", cwd=workrepo)
    # The fake gh exits 0 for everything, so `gh release view` succeeds.
    r, _ = run_with_gh(workrepo, fake_gh, "--publish-only", "--yes")
    assert r.returncode != 0
    assert "already published" in r.stderr


def test_publish_only_recovers_after_failed_publish(workrepo, tmp_path):
    badbin = tmp_path / "badcurl"
    badbin.mkdir()
    bad = badbin / "curl"
    bad.write_text("#!/bin/sh\nexit 1\n")
    bad.chmod(bad.stat().st_mode | stat.S_IXUSR)
    no_gh_env = {"PATH": str(badbin) + os.pathsep + os.environ.get("PATH", ""),
                 "CUT_RELEASE_NO_GH": "1", "GITHUB_TOKEN": "fake",
                 # The poll would otherwise make 10 real HTTPS requests
                 # here (the suite's "no network" contract); the wait is
                 # not what this test exercises.
                 "CUT_RELEASE_POLL_ATTEMPTS": "0"}
    r = run_script(workrepo, "--execute", "--yes", env=no_gh_env)
    assert r.returncode != 0
    assert bare_tags(workrepo) == ["v0.2.0"]  # tag pushed, publish failed

    goodbin = tmp_path / "goodcurl"
    goodbin.mkdir()
    good = goodbin / "curl"
    good.write_text(FAKE_CURL)
    good.chmod(good.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    curl_log = tmp_path / "curl2.log"
    r2 = run_script(workrepo, "--publish-only", "--yes",
                    env={"PATH": str(goodbin) + os.pathsep + os.environ.get("PATH", ""),
                         "CUT_RELEASE_NO_GH": "1", "GITHUB_TOKEN": "sekrit",
                         "CURL_LOG": str(curl_log)})
    assert r2.returncode == 0, r2.stderr + r2.stdout
    assert "published release v0.2.0" in r2.stdout
    log = curl_log.read_text()
    assert "sekrit" not in log


def test_refuses_when_tag_moved_on_remote(workrepo):
    # A tag that exists locally but points elsewhere than the remote's tag
    # must fail closed: the non-forced tag fetch refuses to clobber it.
    (workrepo / "second.txt").write_text("s\n")
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "second commit", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    git("tag", "v0.2.0", cwd=workrepo)
    git("push", "origin", "v0.2.0", cwd=workrepo)
    git("tag", "-d", "v0.2.0", cwd=workrepo)
    git("tag", "v0.2.0", "HEAD~1", cwd=workrepo)  # stale local tag
    r = run_script(workrepo, "--dry-run")
    assert r.returncode != 0
    assert "could not fetch" in r.stderr


def test_pr_reference_anchored_to_end_of_subject(workrepo):
    (workrepo / "feat2.txt").write_text("x\n")
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "fix (#1) thing (#22)", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "- #22 — fix (#1) thing" in r.stdout


FAKE_GH_POLL_RETRY = """#!/bin/sh
# Fails the first two `gh api ... git/ref/tags/...` visibility polls, then
# succeeds — exercises the replication-wait retry path. GH_COUNT names a
# counter file.
{
echo "ARGS: $*"
} >> "$GH_LOG"
case "$*" in
  *"git/ref/tags/"*)
    n=0
    [ -f "${GH_COUNT:-/nonexistent}" ] && n=$(cat "$GH_COUNT")
    n=$((n + 1)); echo "$n" > "$GH_COUNT"
    [ "$n" -le 2 ] && exit 1
    exit 0 ;;
esac
prev=""
for a in "$@"; do
  if [ "$prev" = "--notes-file" ]; then
    echo "NOTES-FILE: $a"
    cat "$a"
  fi
  prev="$a"
done
exit 0
"""


FAKE_GH_POLL_FAIL = """#!/bin/sh
# Fails every `gh api ... git/ref/tags/...` visibility poll — exercises the
# poll-timeout warning path (publish must still be attempted).
{
echo "ARGS: $*"
} >> "$GH_LOG"
case "$*" in *"git/ref/tags/"*) exit 1 ;; esac
prev=""
for a in "$@"; do
  if [ "$prev" = "--notes-file" ]; then
    echo "NOTES-FILE: $a"
    cat "$a"
  fi
  prev="$a"
done
exit 0
"""


def fake_gh_with(bindir_src, text, tmp_path):
    bindir = tmp_path / bindir_src
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(text)
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def test_execute_announces_publish_path_and_outcome_via_gh(workrepo, fake_gh):
    # GitHub #659 follow-up: the failing publish step gave no
    # operator-visible signal beyond the red run — the path used and the
    # outcome must be announced.
    r, recorded = run_with_gh(workrepo, fake_gh, "--execute", "--yes")
    assert r.returncode == 0, r.stderr + r.stdout
    assert "publishing release v0.2.0 via gh" in r.stdout
    assert "published release v0.2.0" in r.stdout
    assert "ARGS: release create v0.2.0" in recorded


def test_execute_polls_tag_visibility_before_publish(workrepo, fake_gh):
    r, recorded = run_with_gh(workrepo, fake_gh, "--execute", "--yes")
    assert r.returncode == 0, r.stderr + r.stdout
    lines = recorded.splitlines()
    poll_idx = next(i for i, l in enumerate(lines)
                    if "git/ref/tags/v0.2.0" in l)
    create_idx = next(i for i, l in enumerate(lines)
                      if l.startswith("ARGS: release create v0.2.0"))
    assert poll_idx < create_idx
    assert "tag v0.2.0 visible to the GitHub API" in r.stdout


def test_tag_poll_retries_then_publishes(workrepo, tmp_path):
    bindir = fake_gh_with("retrybin", FAKE_GH_POLL_RETRY, tmp_path)
    log = tmp_path / "gh.log"
    count = tmp_path / "count"
    e = {"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
         "GH_LOG": str(log), "GH_COUNT": str(count),
         "CUT_RELEASE_POLL_SLEEP": "0"}
    r = run_script(workrepo, "--execute", "--yes", env=e)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "poll 3/10" in r.stdout
    assert "ARGS: release create v0.2.0" in log.read_text()


def test_tag_poll_timeout_warns_but_publishes_anyway(workrepo, tmp_path):
    bindir = fake_gh_with("failbin", FAKE_GH_POLL_FAIL, tmp_path)
    log = tmp_path / "gh.log"
    e = {"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
         "GH_LOG": str(log),
         "CUT_RELEASE_POLL_ATTEMPTS": "2", "CUT_RELEASE_POLL_SLEEP": "0"}
    r = run_script(workrepo, "--execute", "--yes", env=e)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "WARNING: tag v0.2.0 not visible to the GitHub API after 2 polls" in r.stderr
    assert "attempting publish anyway" in r.stderr
    assert "ARGS: release create v0.2.0" in log.read_text()


FAKE_CURL_REF_OK = """#!/bin/sh
# API-fallback curl fake: git-ref visibility polls get a real-looking ref
# body on stdout; the publish POST writes the release JSON to its -o target.
{
echo "CURL_ARGV: $*"
} >> "$CURL_LOG"
for a in "$@"; do
  case "$a" in
    *git/ref/tags/*) printf '{"ref":"refs/tags/v0.2.0","object":{"sha":"abc"}}' ;;
  esac
done
prev=""
for a in "$@"; do
  if [ "$prev" = "-o" ]; then
    printf '{"html_url":"https://example.invalid/r/v0.2.0"}' > "$a"
  fi
  prev="$a"
done
exit 0
"""


def test_api_fallback_polls_and_announces_path(workrepo, tmp_path):
    bindir = tmp_path / "curlbin2"
    bindir.mkdir()
    curl = bindir / "curl"
    curl.write_text(FAKE_CURL_REF_OK)
    curl.chmod(curl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    curl_log = tmp_path / "curl3.log"
    r = run_script(workrepo, "--execute", "--yes",
                   env={"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                        "CUT_RELEASE_NO_GH": "1",
                        "GITHUB_TOKEN": "sekrit",
                        "CURL_LOG": str(curl_log),
                        "CUT_RELEASE_POLL_SLEEP": "0"})
    assert r.returncode == 0, r.stderr + r.stdout
    assert "publishing release v0.2.0 via GitHub API fallback" in r.stdout
    assert "tag v0.2.0 visible to the GitHub API" in r.stdout
    assert "release URL: https://example.invalid/r/v0.2.0" in r.stdout
    log = curl_log.read_text()
    assert "sekrit" not in log  # token stayed in the 0600 config file


FAKE_GH_VIEW_FAIL = """#!/bin/sh
# `gh release view` fails (release not yet published) while everything else
# succeeds — models the workflow recovery step's view of the world.
{
echo "ARGS: $*"
} >> "$GH_LOG"
case "$*" in
  "release view"*) exit 1 ;;
esac
prev=""
for a in "$@"; do
  if [ "$prev" = "--notes-file" ]; then
    echo "NOTES-FILE: $a"
    cat "$a"
  fi
  prev="$a"
done
exit 0
"""


def test_publish_only_recovers_from_detached_head_ci(workrepo, tmp_path):
    # The workflow's recovery step runs `cut-release.sh --publish-only
    # --yes --ci` on actions/checkout's detached HEAD: the --ci flag must
    # apply the GITHUB_REF check (not clobber the mode to execute) so the
    # recovery actually publishes instead of dying on the ref preflight.
    bindir = fake_gh_with("viewfailbin", FAKE_GH_VIEW_FAIL, tmp_path)
    log = tmp_path / "gh.log"
    git("tag", "-a", "v0.2.0", "-m", "release v0.2.0", cwd=workrepo)
    git("push", "origin", "v0.2.0", cwd=workrepo)
    git("checkout", "--detach", "HEAD", cwd=workrepo)
    e = {"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
         "GH_LOG": str(log)}
    r = run_script(workrepo, "--publish-only", "--yes", "--ci",
                   env=dict(e, GITHUB_REF="refs/heads/main"))
    assert r.returncode == 0, r.stderr + r.stdout
    assert "publishing release v0.2.0 via gh" in r.stdout
    assert "published release v0.2.0" in r.stdout
    assert "ARGS: release create v0.2.0" in log.read_text()


def test_publish_only_ci_still_rejects_wrong_ref(workrepo, tmp_path):
    # --ci keeps the ref guard: a detached checkout NOT on main's ref must
    # not publish, even in publish-only mode.
    bindir = fake_gh_with("viewfailbin2", FAKE_GH_VIEW_FAIL, tmp_path)
    log = tmp_path / "gh.log"
    git("tag", "-a", "v0.2.0", "-m", "release v0.2.0", cwd=workrepo)
    git("push", "origin", "v0.2.0", cwd=workrepo)
    git("checkout", "--detach", "HEAD", cwd=workrepo)
    e = {"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
         "GH_LOG": str(log)}
    r = run_script(workrepo, "--publish-only", "--yes", "--ci",
                   env=dict(e, GITHUB_REF="refs/heads/feature"))
    assert r.returncode != 0
    assert "GITHUB_REF" in r.stderr
    # gh was never invoked (the ref guard fires before any network I/O).
    assert not log.exists()


FAKE_CURL_POLL_RETRY = """#!/bin/sh
# Fails the first two git-ref visibility polls (exit 22, like curl --fail
# on a 404), then returns a ref body — exercises the token path's retry
# integration. CURL_COUNT names a counter file.
{
echo "CURL_ARGV: $*"
} >> "$CURL_LOG"
for a in "$@"; do
  case "$a" in
    *git/ref/tags/*)
      n=0
      [ -f "${CURL_COUNT:-/nonexistent}" ] && n=$(cat "$CURL_COUNT")
      n=$((n + 1)); echo "$n" > "$CURL_COUNT"
      if [ "$n" -le 2 ]; then exit 22; fi
      printf '{"ref":"refs/tags/v0.2.0","object":{"sha":"abc"}}' ;;
  esac
done
prev=""
for a in "$@"; do
  if [ "$prev" = "-o" ]; then
    printf '{"html_url":"https://example.invalid/r/v0.2.0"}' > "$a"
  fi
  prev="$a"
done
exit 0
"""


def test_api_fallback_poll_retries_then_publishes(workrepo, tmp_path):
    bindir = tmp_path / "curlbin3"
    bindir.mkdir()
    curl = bindir / "curl"
    curl.write_text(FAKE_CURL_POLL_RETRY)
    curl.chmod(curl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    curl_log = tmp_path / "curl4.log"
    count = tmp_path / "curlcount"
    r = run_script(workrepo, "--execute", "--yes",
                   env={"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                        "CUT_RELEASE_NO_GH": "1",
                        "GITHUB_TOKEN": "sekrit",
                        "CURL_LOG": str(curl_log),
                        "CURL_COUNT": str(count),
                        "CUT_RELEASE_POLL_SLEEP": "0"})
    assert r.returncode == 0, r.stderr + r.stdout
    assert "poll 3/10" in r.stdout
    assert "release URL: https://example.invalid/r/v0.2.0" in r.stdout
    assert "sekrit" not in curl_log.read_text()


def test_poll_attempts_zero_disables_wait(workrepo, fake_gh):
    r, recorded = run_with_gh(workrepo, fake_gh, "--execute", "--yes",
                              env={"CUT_RELEASE_POLL_ATTEMPTS": "0"})
    assert r.returncode == 0, r.stderr + r.stdout
    assert "tag replication wait disabled" in r.stdout
    assert "WARNING" not in r.stderr
    assert "ARGS: release create v0.2.0" in recorded


def test_poll_rejects_non_numeric_hooks(workrepo, fake_gh):
    r, _ = run_with_gh(workrepo, fake_gh, "--execute", "--yes",
                       env={"CUT_RELEASE_POLL_ATTEMPTS": "abc"})
    assert r.returncode != 0
    assert "CUT_RELEASE_POLL_ATTEMPTS" in r.stderr


def test_release_workflow_calls_golden_image_gate():
    # #1176: the release workflow pushes the v* tag with GITHUB_TOKEN,
    # which never triggers workflow runs, so golden-image.yml's own
    # `push: tags` trigger could never fire the F-P1 gate on a real
    # release. release.yml must call the gate as a reusable workflow in
    # the same run. This pins the caller wiring structurally — a typo in
    # `uses:`, a dropped `needs:`, or a widened permission would otherwise
    # pass CI and detonate only on the next real release, the one path CI
    # can never exercise.
    wf = os.path.join(REPO, ".github", "workflows", "release.yml")
    text = open(wf, encoding="utf-8").read()
    assert "uses: ./.github/workflows/golden-image.yml" in text
    assert "needs: release" in text
    # The caller narrows to contents:read for the gate job (the workflow's
    # own top-level permission is contents:write for the tag+release).
    assert "contents: read" in text
    # The gate builds the exact release tree, not main's tip: the tag is
    # passed explicitly from the release job's own per-run checkout.
    assert "needs.release.outputs.tag" in text
    assert "steps.tag.outputs.tag" in text


def test_release_workflow_has_publish_only_recovery_step():
    # GitHub #659: the workflow must recover a tag-pushed/publish-failed
    # state on its own instead of leaving a manual recovery to the operator.
    wf = os.path.join(REPO, ".github", "workflows", "release.yml")
    text = open(wf, encoding="utf-8").read()
    # The recovery step runs the exact command the detached-HEAD test
    # exercises: publish-only with the --ci ref check for the detached
    # checkout.
    assert "cut-release.sh --publish-only --yes --ci" in text
    assert "if: failure()" in text
    # The recovery step lives in the same job, after the cut step, so it
    # reuses the checkout (the local tag) and the runner's gh.
    assert text.index("cut-release.sh --ci") < text.index("--publish-only --yes --ci")


def test_release_workflow_pins_checkout_and_sets_identity():
    wf = os.path.join(REPO, ".github", "workflows", "release.yml")
    text = open(wf, encoding="utf-8").read()
    # No floating action tag: checkout is SHA-pinned...
    assert "actions/checkout@" in text
    assert "actions/checkout@v" not in text.replace(
        "actions/checkout@11d5960a326750d5838078e36cf38b85af677262", "")
    # ...and the job configures a git identity, because `git tag -a`
    # embeds a tagger identity that actions/checkout does not set.
    assert "github-actions[bot]" in text


# --- refusals ---

def test_runs_from_linked_worktree(workrepo, tmp_path):
    """Issue #349: in a git linked worktree, `.git` is a file (a `gitdir:`
    pointer), not a directory — the repo gate must use `git rev-parse
    --git-dir` so a worktree run gets past it instead of aborting with
    "not a git repo". (The worktree sits on a helper branch — `git worktree
    add <path>` without -b names it after the path basename ("worktree") —
    so the next preflight, the main-branch check, is the expected stop.)"""
    wt = tmp_path / "worktree"
    git("worktree", "add", str(wt), cwd=workrepo)
    r = run_script(wt, "--dry-run")
    assert "not a git repo" not in r.stderr
    assert "must run on main" in r.stderr


def test_refuses_dirty_tree(workrepo):
    (workrepo / "VERSION").write_text("0.2.1\n")
    r = run_script(workrepo, "--dry-run")
    assert r.returncode != 0
    assert "not clean" in r.stderr


def test_refuses_non_main_branch(workrepo):
    git("checkout", "-b", "feature", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode != 0
    assert "must run on main" in r.stderr


def test_refuses_bad_version(workrepo):
    (workrepo / "VERSION").write_text("bogus\n")
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "bad version", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode != 0
    assert "strict semver" in r.stderr


def test_refuses_existing_local_tag(workrepo):
    git("tag", "-a", "v0.2.0", "-m", "old", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode != 0
    assert "already exists locally" in r.stderr


def test_refuses_when_behind_remote(workrepo, tmp_path):
    other = tmp_path / "other"
    subprocess.run(["git", "clone", str(workrepo.parent / "origin.git"),
                    str(other)], check=True, capture_output=True, timeout=60)
    (other / "VERSION").write_text("0.2.0\n")
    (other / "extra.txt").write_text("y\n")
    git("add", "-A", cwd=other)
    git("commit", "-m", "other commit", cwd=other)
    git("push", "origin", "main", cwd=other)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode != 0
    assert "not" in r.stderr and "origin/main" in r.stderr


def test_refuses_version_not_newer_than_latest_tag(workrepo):
    git("tag", "v0.5.0", cwd=workrepo)
    git("push", "origin", "v0.5.0", cwd=workrepo)
    git("tag", "-d", "v0.5.0", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode != 0
    assert "not newer than latest release v0.5.0" in r.stderr


def _retarget_version(work, version):
    (work / "VERSION").write_text(version + "\n")
    write_changelog(work, version)
    git("add", "-A", cwd=work)
    git("commit", "-m", "release: bump VERSION to %s" % version, cwd=work)
    git("push", "origin", "main", cwd=work)


def test_rc_to_final_promotion_passes(workrepo):
    # sort -V orders v0.2.0 before v0.2.0-rc.1 and would refuse this;
    # semver §11 says the prerelease has LOWER precedence, so the
    # promotion must pass.
    git("tag", "v0.2.0-rc.1", cwd=workrepo)
    git("push", "origin", "v0.2.0-rc.1", cwd=workrepo)
    git("tag", "-d", "v0.2.0-rc.1", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "VERSION=0.2.0 tag=v0.2.0" in r.stdout


def test_rc_to_rc2_promotion_passes(workrepo):
    _retarget_version(workrepo, "0.2.0-rc.2")
    git("tag", "v0.2.0-rc.1", cwd=workrepo)
    git("push", "origin", "v0.2.0-rc.1", cwd=workrepo)
    git("tag", "-d", "v0.2.0-rc.1", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "VERSION=0.2.0-rc.2 tag=v0.2.0-rc.2" in r.stdout


def test_final_to_rc_is_refused(workrepo):
    _retarget_version(workrepo, "0.2.0-rc.1")
    git("tag", "v0.2.0", cwd=workrepo)
    git("push", "origin", "v0.2.0", cwd=workrepo)
    git("tag", "-d", "v0.2.0", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode != 0
    assert "not newer than latest release v0.2.0" in r.stderr


def test_subject_control_characters_stripped(workrepo):
    evil = "fix: handle evil \x1b[2J\x1b[31mRED\x1b[0m subject"
    git("commit", "--allow-empty", "-m", evil, cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "\x1b" not in r.stdout
    assert "fix: handle evil [2J[31mRED[0m subject" in r.stdout


def test_changelog_section_control_characters_stripped(workrepo):
    # Same class as subjects: changelog entries are contributor-controlled
    # and the notes draft is printed to the operator's terminal.
    body = ("# Changelog\n\n## [Unreleased]\n\n"
            "## [0.2.0] - 2026-09-19\n\n### Added\n"
            "- poisoned \x1b[2J\x1b[31mRED\x1b[0m entry\n")
    (workrepo / "CHANGELOG.md").write_text(body)
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "docs: poison changelog", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r = run_script(workrepo, "--dry-run")
    assert r.returncode == 0, r.stderr
    assert "\x1b" not in r.stdout
    assert "poisoned [2J[31mRED[0m entry" in r.stdout


def test_execute_removes_local_tag_when_push_fails(workrepo, fake_gh):
    hook = workrepo.parent / "origin.git" / "hooks" / "update"
    hook.write_text("#!/bin/sh\necho 'tag push blocked' >&2\nexit 1\n")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    r, recorded = run_with_gh(workrepo, fake_gh, "--execute", "--yes")
    assert r.returncode != 0
    assert "local tag removed" in r.stderr
    local_tags = subprocess.run(
        ["git", "tag", "--list"], cwd=str(workrepo),
        capture_output=True, text=True, timeout=60).stdout.strip()
    assert local_tags == ""
    assert recorded == ""  # publish was never attempted


FAKE_CURL = """#!/bin/sh
{
echo "CURL_ARGV: $*"
prev=""
for a in "$@"; do
  if [ "$prev" = "-K" ]; then
    echo "CONFIG: $a"
    grep -q 'Authorization' "$a" && echo "CONFIG_HAS_AUTH_HEADER"
  fi
  if [ "$prev" = "-o" ]; then
    printf '{"html_url":"https://example.invalid/r/v0.2.0"}' > "$a"
  fi
  prev="$a"
done
} >> "$CURL_LOG"
exit 0
"""


def test_api_fallback_keeps_token_off_argv(workrepo, tmp_path):
    bindir = tmp_path / "curlbin"
    bindir.mkdir()
    curl = bindir / "curl"
    curl.write_text(FAKE_CURL)
    curl.chmod(curl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    curl_log = tmp_path / "curl.log"
    r = run_script(workrepo, "--execute", "--yes",
                   env={"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                        "CUT_RELEASE_NO_GH": "1",
                        "GITHUB_TOKEN": "sekrit-token-123",
                        "CURL_LOG": str(curl_log)})
    assert r.returncode == 0, r.stderr + r.stdout
    assert "release URL: https://example.invalid/r/v0.2.0" in r.stdout
    log = curl_log.read_text()
    assert "CONFIG_HAS_AUTH_HEADER" in log  # header went via the config file
    assert "sekrit-token-123" not in log  # ...and never on the command line


# --- execute ---

def test_execute_requires_yes(workrepo, fake_gh):
    r, recorded = run_with_gh(workrepo, fake_gh, "--execute")
    assert r.returncode != 0
    assert "--yes" in r.stderr
    assert bare_tags(workrepo) == []
    assert recorded == ""


def test_execute_pushes_tag_and_publishes_release(workrepo, fake_gh):
    (workrepo / "feat.txt").write_text("x\n")
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "feat: widget (#34)", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r, recorded = run_with_gh(workrepo, fake_gh, "--execute", "--yes")
    assert r.returncode == 0, r.stderr + r.stdout
    assert bare_tags(workrepo) == ["v0.2.0"]
    assert "ARGS: release create v0.2.0 --title v0.2.0" in recorded
    assert "--target main" in recorded
    assert "--prerelease" not in recorded
    assert "Demo release bullet for 0.2.0" in recorded  # changelog in notes
    assert "- #34 — feat: widget" in recorded  # merged PRs in notes


def test_execute_marks_prerelease_versions(workrepo, fake_gh):
    (workrepo / "VERSION").write_text("0.3.0-rc.1\n")
    write_changelog(workrepo, "0.3.0-rc.1")
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "release: bump VERSION to 0.3.0-rc.1", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r, recorded = run_with_gh(workrepo, fake_gh, "--execute", "--yes")
    assert r.returncode == 0, r.stderr + r.stdout
    assert "v0.3.0-rc.1" in bare_tags(workrepo)
    assert "--prerelease" in recorded


def test_ci_mode_requires_main_ref(workrepo, fake_gh):
    r, _ = run_with_gh(workrepo, fake_gh, "--ci",
                       env={"GITHUB_REF": "refs/heads/feature"})
    assert r.returncode != 0
    assert "GITHUB_REF" in r.stderr


def test_ci_dry_run_never_executes(workrepo, fake_gh):
    # --ci must not discard an explicit --dry-run: an operator probing the
    # CI path with the safety flag must get the plan, never a release.
    git("checkout", "--detach", "HEAD", cwd=workrepo)
    r, recorded = run_with_gh(workrepo, fake_gh, "--ci", "--dry-run",
                              env={"GITHUB_REF": "refs/heads/main"})
    assert r.returncode == 0, r.stderr + r.stdout
    assert "dry run" in r.stdout
    assert bare_tags(workrepo) == []
    assert recorded == ""  # gh never invoked: no tag, no publish


def test_ci_mode_executes_on_main_ref_detached(workrepo, fake_gh):
    git("checkout", "--detach", "HEAD", cwd=workrepo)
    r, recorded = run_with_gh(workrepo, fake_gh, "--ci",
                              env={"GITHUB_REF": "refs/heads/main"})
    assert r.returncode == 0, r.stderr + r.stdout
    assert bare_tags(workrepo) == ["v0.2.0"]
    assert "ARGS: release create v0.2.0" in recorded


def test_execute_fails_without_gh_or_token(workrepo, tmp_path):
    bindir = tmp_path / "emptybin"
    bindir.mkdir()
    r = run_script(workrepo, "--execute", "--yes",
                   env={"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                        "CUT_RELEASE_NO_GH": "1", "GITHUB_TOKEN": ""})
    assert r.returncode != 0
    assert "GITHUB_TOKEN" in r.stderr
    # The tag was still pushed before the publish step failed.
    assert bare_tags(workrepo) == ["v0.2.0"]


def test_publish_only_waits_for_tag_replication_before_publishing(workrepo, tmp_path):
    # #687 item 3: the replication wait moved into publish_release
    # (auth-gated), so --publish-only self-heals on #659 lag instead of
    # re-failing loudly seconds after the first publish attempt. Pin the
    # order: the tag-visibility GET happens before the publish POST.
    badbin = tmp_path / "badcurl-po"
    badbin.mkdir()
    bad = badbin / "curl"
    bad.write_text("#!/bin/sh\nexit 1\n")
    bad.chmod(bad.stat().st_mode | stat.S_IXUSR)
    r = run_script(workrepo, "--execute", "--yes",
                   env={"PATH": str(badbin) + os.pathsep + os.environ.get("PATH", ""),
                        "CUT_RELEASE_NO_GH": "1", "GITHUB_TOKEN": "fake",
                        "CUT_RELEASE_POLL_ATTEMPTS": "0"})
    assert r.returncode != 0
    assert bare_tags(workrepo) == ["v0.2.0"]  # tag pushed, publish failed

    goodbin = tmp_path / "goodcurl-po"
    goodbin.mkdir()
    good = goodbin / "curl"
    good.write_text(FAKE_CURL)
    good.chmod(good.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    curl_log = tmp_path / "curl-po.log"
    r2 = run_script(workrepo, "--publish-only", "--yes",
                    env={"PATH": str(goodbin) + os.pathsep + os.environ.get("PATH", ""),
                         "CUT_RELEASE_NO_GH": "1", "GITHUB_TOKEN": "sekrit",
                         "CURL_LOG": str(curl_log),
                         "CUT_RELEASE_POLL_SLEEP": "0"})
    assert r2.returncode == 0, r2.stderr + r2.stdout
    assert "visible to the GitHub API (poll 1/10)" in r2.stdout
    lines = curl_log.read_text().splitlines()
    polls = [i for i, l in enumerate(lines) if "git/ref/tags/v0.2.0" in l]
    posts = [i for i, l in enumerate(lines) if "/releases" in l and "-X" in l]
    assert polls and posts and min(polls) < min(posts)


def test_api_fallback_accepts_gh_token_alias(workrepo, tmp_path):
    # #687 item 4: the release workflow exports GH_TOKEN (gh's
    # conventional name); the API fallback accepts it as an alias so the
    # fallback is live in CI instead of fail-closing dead.
    bindir = tmp_path / "curlbin-gh"
    bindir.mkdir()
    curl = bindir / "curl"
    curl.write_text(FAKE_CURL)
    curl.chmod(curl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    curl_log = tmp_path / "curl-gh.log"
    r = run_script(workrepo, "--execute", "--yes",
                   env={"PATH": str(bindir) + os.pathsep + os.environ.get("PATH", ""),
                        "CUT_RELEASE_NO_GH": "1",
                        "GITHUB_TOKEN": "",  # unset-by-value: only the alias carries
                        "GH_TOKEN": "gh-alias-sekrit",
                        "CURL_LOG": str(curl_log),
                        "CUT_RELEASE_POLL_ATTEMPTS": "0"})
    assert r.returncode == 0, r.stderr + r.stdout
    assert "published release v0.2.0" in r.stdout
    log = curl_log.read_text()
    assert "CONFIG_HAS_AUTH_HEADER" in log  # the alias carried the token
    assert "gh-alias-sekrit" not in log  # ...and never on the command line


# --- release-notes body cap (GitHub #1086) ---

TRIM_MARKER = "release-body limit"


def write_section_changelog(work, version, section_md):
    body = ("# Changelog\n\n## [Unreleased]\n\n"
            "## [%s] - 2026-09-19\n\n%s\n" % (version, section_md))
    (work / "CHANGELOG.md").write_text(body)


def commit_changelog(work, msg="docs: update changelog"):
    git("add", "-A", cwd=work)
    git("commit", "-m", msg, cwd=work)
    git("push", "origin", "main", cwd=work)


def dry_run_notes(work, tmp_path, name, env=None):
    notes = tmp_path / name
    r = run_script(work, "--dry-run", "--notes-file", str(notes), env=env)
    assert r.returncode == 0, r.stderr + r.stdout
    return notes.read_text(), r


def highlights_region(body):
    """The assembled Highlights section, between its header and the PR list."""
    start = body.index("## Highlights")
    end = body.index("## Merged")
    return body[start:end]


def test_oversized_highlights_trimmed_with_default_cap(workrepo, tmp_path):
    # The production default (125,000 characters): a curated section over
    # the cap is trimmed at whole-bullet boundaries; the PR list and the
    # footer survive untouched.
    bullets = ["- bullet %04d %s" % (i, "x" * 80) for i in range(1400)]
    bullet_set = set(bullets)
    section = "### Added\n" + "\n".join(bullets) + "\n"
    assert len(section) > 125000  # the trim must engage (non-vacuous)
    write_section_changelog(workrepo, "0.2.0", section)
    commit_changelog(workrepo)
    body, r = dry_run_notes(workrepo, tmp_path, "notes.md")
    assert len(body) <= 125000
    assert "trimmed to fit the 125,000-character " + TRIM_MARKER in body
    assert "CHANGELOG.md on this tag" in body
    region = highlights_region(body)
    kept_lines = [l for l in region.splitlines() if l.startswith("- ")]
    assert kept_lines  # some bullets survive
    assert len(kept_lines) < len(bullets)  # ...but not all
    for line in kept_lines:
        assert line in bullet_set  # whole bullets only: never split mid-line
    # The merged-PR list and the footer are never trimmed.
    assert "- release: bump VERSION to 0.2.0" in body
    assert "\n---\n" in body
    assert "Release tag `v0.2.0`" in body
    assert any(l.startswith("Full commit `") for l in body.splitlines())
    assert "no trim needed" not in r.stderr


def test_cap_never_splits_a_single_long_bullet(workrepo, tmp_path):
    # A bullet longer than the remaining budget is dropped entire — its
    # prefix must not leak into the notes.
    giant = "- GIANT-" + "x" * 5000 + "-END"
    section = "### Added\n- short one\n%s\n- short two\n" % giant
    write_section_changelog(workrepo, "0.2.0", section)
    commit_changelog(workrepo)
    body, _ = dry_run_notes(workrepo, tmp_path, "notes.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": "3000"})
    assert len(body) <= 3000
    assert "GIANT-" not in body  # absent entire, not truncated
    assert "- short one" in body
    assert "- short two" in body  # later bullets that fit are still kept


def test_dangling_subsection_header_dropped(workrepo, tmp_path):
    # A "### " header whose bullets were all trimmed must not dangle at
    # the end of the trimmed section.
    giant = "- " + "y" * 2000
    section = "### Added\n- keeper bullet\n### Fixed\n%s\n" % giant
    write_section_changelog(workrepo, "0.2.0", section)
    commit_changelog(workrepo)
    body, _ = dry_run_notes(workrepo, tmp_path, "notes.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": "900"})
    assert len(body) <= 900
    region = highlights_region(body)
    content_lines = [l for l in region.splitlines()[2:]
                     if l.strip() and not l.startswith("_The Highlights")]
    assert content_lines
    assert not content_lines[-1].startswith("### ")
    assert "### Fixed" not in region
    assert "- keeper bullet" in body


def test_body_untouched_when_under_cap(workrepo, tmp_path):
    body, r = dry_run_notes(workrepo, tmp_path, "notes.md")
    assert TRIM_MARKER not in body
    assert "trimmed to fit" not in body
    assert "- Demo release bullet for 0.2.0" in body
    assert "no trim needed" in r.stderr


def test_cap_boundary_exact(workrepo, tmp_path):
    # Pin the boundary: a body of exactly `cap` characters passes through
    # untouched; one character more engages the trim.
    bullets = ["- bullet %04d %s" % (i, "z" * 60) for i in range(20)]
    write_section_changelog(workrepo, "0.2.0",
                            "### Added\n" + "\n".join(bullets) + "\n")
    commit_changelog(workrepo)
    full, _ = dry_run_notes(workrepo, tmp_path, "full.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": "1000000000"})
    assert TRIM_MARKER not in full
    size = len(full)
    exact, _ = dry_run_notes(workrepo, tmp_path, "exact.md",
                             env={"CUT_RELEASE_MAX_BODY_CHARS": str(size)})
    assert exact == full  # exactly at the cap: untouched
    over, _ = dry_run_notes(workrepo, tmp_path, "over.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": str(size - 1)})
    assert len(over) <= size - 1
    assert "trimmed to fit" in over


def test_dies_when_pr_list_alone_exceeds_cap(workrepo, tmp_path):
    # The merged-PR list is never trimmed; when it plus the footer exceed
    # the cap even with Highlights fully trimmed, the script must fail
    # loudly (operator diagnostic) instead of publishing a 422.
    r = run_script(workrepo, "--dry-run",
                   env={"CUT_RELEASE_MAX_BODY_CHARS": "200"})
    assert r.returncode != 0
    assert "still exceed" in r.stderr
    assert "merged-PR list alone" in r.stderr
    assert "notes-file" in r.stderr  # the diagnostic names the manual path
    assert "--prerelease" not in r.stderr  # E1: not a prerelease, no flag
    assert "<tag>" not in r.stderr  # the real tag, never a placeholder


def test_trim_die_recovery_names_prerelease_flag(workrepo):
    # E1: the trim-die's manual recovery command must carry --prerelease
    # for prerelease versions — an operator following the diagnostic
    # verbatim on an rc would otherwise publish a full release.
    (workrepo / "VERSION").write_text("0.3.0-rc.1\n")
    git("add", "-A", cwd=workrepo)
    git("commit", "-m", "release: bump VERSION to 0.3.0-rc.1", cwd=workrepo)
    git("push", "origin", "main", cwd=workrepo)
    r = run_script(workrepo, "--dry-run",
                   env={"CUT_RELEASE_MAX_BODY_CHARS": "200"})
    assert r.returncode != 0
    assert "still exceed" in r.stderr
    assert "--prerelease" in r.stderr
    assert "v0.3.0-rc.1" in r.stderr  # the real tag, not a <tag> placeholder
    assert "<tag>" not in r.stderr


def test_trim_die_recovery_recreates_tag_in_dry_run(workrepo):
    # Q4: in --dry-run (and --execute) no tag exists yet — the die fires on
    # the shared assembly path before tagging — so the recovery must
    # recreate the tag at the release commit. gh release create alone would
    # tag whatever main happens to point at by then.
    r = run_script(workrepo, "--dry-run",
                   env={"CUT_RELEASE_MAX_BODY_CHARS": "200"})
    assert r.returncode != 0
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(workrepo),
                         capture_output=True, text=True, check=True,
                         timeout=60).stdout.strip()
    assert ("git tag -a v0.2.0 -m 'spark-vm v0.2.0' %s" % sha) in r.stderr
    assert "git push origin v0.2.0" in r.stderr
    assert "already on the remote" not in r.stderr


def test_trim_die_recovery_targets_existing_tag_in_publish_only(workrepo):
    # Q4: in --publish-only the tag is already on the remote, so the
    # recovery publishes onto it directly — no tag recreation.
    git("tag", "v0.2.0", cwd=workrepo)
    git("push", "origin", "v0.2.0", cwd=workrepo)
    r = run_script(workrepo, "--publish-only", "--yes",
                   env={"CUT_RELEASE_MAX_BODY_CHARS": "200"})
    assert r.returncode != 0
    assert "still exceed" in r.stderr
    assert "already on the remote" in r.stderr
    assert "gh release create v0.2.0 --title v0.2.0" in r.stderr
    assert "git tag -a" not in r.stderr


def test_trim_report_counts_dangling_headers_separately(workrepo, tmp_path):
    # E2: popped "### " headers must not inflate the dropped-lines count.
    giant = "- " + "y" * 2000
    section = "### Added\n- keeper bullet\n### Fixed\n%s\n" % giant
    write_section_changelog(workrepo, "0.2.0", section)
    commit_changelog(workrepo)
    body, r = dry_run_notes(workrepo, tmp_path, "notes.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": "900"})
    assert len(body) <= 900
    assert "1 Highlights line(s) dropped" in r.stderr
    assert "(1 dangling '### ' header(s) pruned)" in r.stderr


def test_trim_note_framed_by_blank_lines(workrepo, tmp_path):
    # E3: the trim note must render as its own paragraph — a blank line
    # before and after it.
    bullets = ["- bullet %04d %s" % (i, "x" * 80) for i in range(1400)]
    section = "### Added\n" + "\n".join(bullets) + "\n"
    write_section_changelog(workrepo, "0.2.0", section)
    commit_changelog(workrepo)
    body, _ = dry_run_notes(workrepo, tmp_path, "notes.md")
    assert len(body) <= 125000
    assert "\n\n_The Highlights section was trimmed" in body
    assert "on this tag._\n\n## Merged" in body


def test_default_cap_boundary_exact_at_125000(workrepo, tmp_path):
    # Q1: pin the production default — a body of exactly 125,000 characters
    # passes the real default cap untouched; one more engages the trim.
    bullets = ["- bullet %04d %s" % (i, "z" * 60) for i in range(20)]
    write_section_changelog(workrepo, "0.2.0",
                            "### Added\n" + "\n".join(bullets) + "\n")
    commit_changelog(workrepo)
    full, _ = dry_run_notes(workrepo, tmp_path, "full.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": "1000000000"})
    assert TRIM_MARKER not in full
    pad = 125000 - len(full)
    assert pad > 4  # non-vacuous: the filler actually engages the boundary
    filler = "- " + "q" * (pad - 3)  # +1 newline == exactly `pad` new chars
    write_section_changelog(workrepo, "0.2.0",
                            "### Added\n" + "\n".join(bullets)
                            + "\n" + filler + "\n")
    commit_changelog(workrepo)
    # The commit above grew the merged-PR list by one line; measure the
    # padded body, then correct the filler with --amend (no new PR line)
    # so the final body lands exactly on the boundary.
    padded, _ = dry_run_notes(workrepo, tmp_path, "padded.md",
                              env={"CUT_RELEASE_MAX_BODY_CHARS": "1000000000"})
    delta = 125000 - len(padded)
    assert abs(delta) < 1000  # only the one PR-line growth to correct
    filler2 = "- " + "q" * (pad - 3 + delta)
    assert len(filler2) > 4
    write_section_changelog(workrepo, "0.2.0",
                            "### Added\n" + "\n".join(bullets)
                            + "\n" + filler2 + "\n")
    git("add", "-A", cwd=workrepo)
    git("commit", "--amend", "--no-edit", cwd=workrepo)
    git("push", "--force", "origin", "main", cwd=workrepo)
    body, r = dry_run_notes(workrepo, tmp_path, "exact.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": "125000"})
    assert len(body) == 125000
    assert TRIM_MARKER not in body
    assert "no trim needed" in r.stderr
    over, _ = dry_run_notes(workrepo, tmp_path, "over.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": "124999"})
    assert "trimmed to fit" in over


def test_unicode_counted_in_code_points_not_bytes(workrepo, tmp_path):
    # Q2: lengths are Unicode code points, not UTF-8 bytes. A body whose
    # character count fits the cap but whose byte count exceeds it must
    # pass untouched — a byte-counting implementation would trim.
    fire = "🔥" * 200  # 200 code points, 800 UTF-8 bytes
    section = "### Added\n- %s\n" % fire
    write_section_changelog(workrepo, "0.2.0", section)
    commit_changelog(workrepo)
    full, _ = dry_run_notes(workrepo, tmp_path, "full.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": "1000000000"})
    assert TRIM_MARKER not in full
    size = len(full)
    assert len(full.encode("utf-8")) > size  # the divergence is real
    body, r = dry_run_notes(workrepo, tmp_path, "uni.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": str(size)})
    assert body == full  # exactly at the cap in code points: untouched
    assert TRIM_MARKER not in body
    assert "no trim needed" in r.stderr
    assert len(body.encode("utf-8")) > size  # ...despite exceeding it in bytes


def test_placeholder_path_never_trims(workrepo, tmp_path):
    # Q3: the trim note claims "the full section is in CHANGELOG.md" —
    # misleading when there is no curated section. Structurally the note
    # (~150 chars) is longer than the placeholder (~78) it would replace,
    # so the placeholder path can never trim: an over-cap body always dies
    # loudly instead. Pin that no trim note is ever emitted on this path —
    # if a future edit shortens the note below the placeholder length,
    # this fails and forces the question.
    write_changelog(workrepo, "0.2.0", section=False)
    commit_changelog(workrepo)
    full, _ = dry_run_notes(workrepo, tmp_path, "full.md",
                            env={"CUT_RELEASE_MAX_BODY_CHARS": "1000000000"})
    assert TRIM_MARKER not in full
    assert "_No curated CHANGELOG.md section" in full
    for cap in (len(full) - 1, len(full) // 2, 200):
        r = run_script(workrepo, "--dry-run",
                       env={"CUT_RELEASE_MAX_BODY_CHARS": str(cap)})
        assert r.returncode != 0, cap  # always dies, never trims
        assert "still exceed" in r.stderr
        assert "the full section is in CHANGELOG.md" not in r.stderr


def test_rejects_non_numeric_max_body_chars(workrepo):
    r = run_script(workrepo, "--dry-run",
                   env={"CUT_RELEASE_MAX_BODY_CHARS": "abc"})
    assert r.returncode != 0
    assert "CUT_RELEASE_MAX_BODY_CHARS" in r.stderr


def test_rejects_zero_max_body_chars(workrepo):
    # A zero cap would die on every release; reject it up front.
    r = run_script(workrepo, "--dry-run",
                   env={"CUT_RELEASE_MAX_BODY_CHARS": "0"})
    assert r.returncode != 0
    assert "CUT_RELEASE_MAX_BODY_CHARS" in r.stderr
