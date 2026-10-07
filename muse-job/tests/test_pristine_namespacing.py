"""Pristine clone namespacing (issue #10).

The pristine clone dir used to be keyed on the last URL segment alone, so
`org1/foo` and `org2/foo` shared one clone: the second spawn `git fetch`ed
the wrong repo's objects into it and cut worktrees from the wrong base.
The fix keys the dir on host + full path
(`~/repos/github.com/ntindle/spark-vm`); local paths and `file://` URLs
namespace under `~/repos/_local/<path...>`; a bare name keeps the old
flat shape.

These tests pin the derivation. They are written anti-vacuous: every
positive case asserts the exact derived path, and the collision case
asserts the two colliding URLs produce *different* dirs (the pre-fix code
produced the same one for both).
"""
import importlib.machinery
import importlib.util
import os
import sys

import pytest

CLI_PATH = os.path.join(os.path.dirname(__file__), "..", "bin", "muse-job")


def load_script(name, path):
    sys.modules.pop(name, None)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    loader.exec_module(mod)
    return mod


@pytest.fixture()
def cli(monkeypatch, tmp_path):
    """Import bin/muse-job with HOME pointed at an isolated tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_pristine", CLI_PATH)


def derive(cli, url):
    return os.path.join(cli.REPOS_DIR, cli.pristine_name_from_url(url))


def test_collision_urls_get_distinct_pristines(cli):
    # The bug: all of these derived ~/repos/foo.
    a = derive(cli, "https://github.com/org1/foo.git")
    b = derive(cli, "https://github.com/org2/foo.git")
    c = derive(cli, "https://gitlab.com/org1/foo.git")
    assert len({a, b, c}) == 3
    assert a == os.path.join(cli.REPOS_DIR, "github.com", "org1", "foo")
    assert b == os.path.join(cli.REPOS_DIR, "github.com", "org2", "foo")
    assert c == os.path.join(cli.REPOS_DIR, "gitlab.com", "org1", "foo")


def test_same_upstream_normalizes_to_one_dir(cli):
    # Equivalent URL spellings for one upstream share one pristine dir.
    expected = derive(cli, "https://github.com/ntindle/spark-vm.git")
    assert derive(cli, "https://github.com/ntindle/spark-vm") == expected
    assert derive(cli, "git@github.com:ntindle/spark-vm.git") == expected
    assert derive(cli, "ssh://git@github.com/ntindle/spark-vm") == expected
    assert expected == os.path.join(
        cli.REPOS_DIR, "github.com", "ntindle", "spark-vm")


def test_explicit_port_is_part_of_the_key(cli):
    # Different ports on one host can serve different repos: the port
    # stays in the key. An explicit default port diverges from the
    # port-less spelling -- fail-safe duplication, never wrong code.
    a = derive(cli, "ssh://git@github.com:22/ntindle/spark-vm")
    b = derive(cli, "ssh://git@github.com:2222/ntindle/spark-vm")
    c = derive(cli, "ssh://git@github.com/ntindle/spark-vm")
    assert len({a, b, c}) == 3
    assert a == os.path.join(
        cli.REPOS_DIR, "github.com:22", "ntindle", "spark-vm")


@pytest.mark.parametrize("url,expected", [
    # Standard https.
    ("https://github.com/ntindle/spark-vm.git",
     ("github.com", "ntindle", "spark-vm")),
    ("https://github.com/ntindle/spark-vm/",
     ("github.com", "ntindle", "spark-vm")),
    # Uppercase path segments are preserved (deliberately not slug_ok()),
    # but the host is case-folded (DNS is case-insensitive).
    ("https://EXAMPLE.com/SomeOrg/SomeRepo.git",
     ("example.com", "SomeOrg", "SomeRepo")),
    # scp-like SSH syntax.
    ("git@github.com:ntindle/spark-vm.git",
     ("github.com", "ntindle", "spark-vm")),
    # ssh:// with userinfo + port (the port stays in the key).
    ("ssh://git@github.com:22/ntindle/spark-vm",
     ("github.com:22", "ntindle", "spark-vm")),
    # GitLab subgroups: the full path is kept, not just the last two
    # segments, so sibling subgroups stay distinct.
    ("https://gitlab.com/a/sub/repo", ("gitlab.com", "a", "sub", "repo")),
    # file:// URL: no meaningful host, namespaced under _local.
    ("file:///srv/git/myrepo.git", ("_local", "srv", "git", "myrepo")),
    # Local path: namespaced under _local.
    ("/srv/git/myrepo", ("_local", "srv", "git", "myrepo")),
    # Deep local path keeps the full path (no truncation).
    ("/opt/git/myrepo", ("_local", "opt", "git", "myrepo")),
    # A real local path literally named `_local` must not collapse onto
    # the namespace root or the empty-input fallback.
    ("_local", ("_local", "_local")),
])
def test_host_path_namespacing(cli, url, expected):
    assert cli.pristine_name_from_url(url) == os.path.join(*expected)


def test_bare_name_keeps_flat_shape(cli):
    # A bare name has no upstream identity to namespace: same shape as the
    # pre-#10 layout.
    assert cli.pristine_name_from_url("foo") == "foo"


@pytest.mark.parametrize("url", [
    "https://example.com/../foo",
    "https://example.com/org/..",
    "https://example.com/./foo",
    "https://example.com/org/.",
    "https://example.com/..",
    "git@github.com:../foo.git",
    "..",
    # A local path containing ':' is not scp-like: the pre-':' part must
    # not become a multi-segment host that escapes REPOS_DIR (issue #793).
    "../x:y",
    "/srv/git:myrepo",
    # `_local` is reserved for the local-path namespace; a network host
    # with that name would collide with local paths (issue #10).
    "https://_local/srv/git/myrepo",
    "git@_local:srv/git/myrepo",
    # Empty-path URLs would collapse onto a bare-name dir (issue #10).
    "https://foo",
    "git@foo:",
    "file://",
    # `a/b:x` is a local path to git, not scp-like: refusing keeps the
    # derivation and git agreeing on the upstream (issue #10).
    "foo/bar:o/r",
])
def test_dotdot_dot_segments_refused(cli, url):
    # Issue #793's fail-fast gate, extended to the org segment: no
    # containment escape, no silent munging.
    with pytest.raises(RuntimeError, match="bad repo name from url"):
        cli.pristine_name_from_url(url)


def test_empty_url_falls_back_to_repo(cli):
    assert cli.pristine_name_from_url("") == "repo"


def test_spawn_creates_namespaced_pristine(cli, monkeypatch, tmp_path):
    """End to end at the _spawn_prepare level: the clone lands in the
    namespaced dir, with the org dir created (faked git, real makedirs)."""
    import argparse
    import subprocess

    calls = []

    def fake_run(*argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            args=list(argv), returncode=0, stdout=b"deadbeef\n", stderr=b"")

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: False)
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda slug, timeout=20: False)
    monkeypatch.setattr(cli, "find_session", lambda work, started: "fake-uuid")
    prompt = tmp_path / "p.md"
    prompt.write_text("a perfectly innocent prompt with no secrets in it")
    args = argparse.Namespace(
        slug="nsjob", repo="https://example.com/SomeOrg/SomeRepo.git",
        prompt_file=str(prompt), base=None, budget_hours=8,
        allow_secrets=False)
    cli._spawn(args.slug, args)  # returns None on success; would raise first
    clones = [c for c in calls if list(c)[:2] == ["git", "clone"]]
    assert len(clones) == 1
    assert clones[0][-1] == os.path.join(
        str(tmp_path), "repos", "example.com", "SomeOrg", "SomeRepo")
