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


# --- refusals ---

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
