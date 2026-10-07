"""Input validation on the operator boundary (issue #7).

Two gaps, both cheap to exploit by accident and both cheap to fix:

1. Slug path traversal: only `spawn` validated the slug. Every other
   subcommand fed the raw argv slug into job_dir() path joins, so
   `muse-job close ..` resolved the job directory to ~. The fix is a
   central gate in main(): any slug-bearing subcommand refuses a bad slug
   before dispatch.

2. `git clone` option injection via --repo: no `--` separator and no
   leading-dash rejection, so `--repo '--upload-pack=<cmd>'` would make git
   execute <cmd> as the operator. The fix rejects leading-dash URLs at
   spawn time and passes `--` at the clone call site.

Tests pin the gate (bad slugs refused at main() for every slug-bearing
subcommand, home untouched by `close ..`), the repo-URL refusal (leading
dash and empty), and the `--` separator on the actual clone invocation.

Issue #793 (security, hardening residuals of the #7 review) adds three
more pins here: `ext::`/`fd::` remote-helper transports are refused as repo
URLs, a `..`/`.` last URL segment is refused before the pristine path is
derived, and a leading-dash `--base` is refused before it reaches
`rev-parse` in option position (rev-parse does not honor `--` before the
revision, so validation is the gate, not the separator).
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
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
    monkeypatch.setenv("HOME", str(tmp_path))
    return load_script("muse_job_cli_inputval", CLI_PATH)


BAD_SLUGS = [
    "..", "../..", "../../etc", "a/b", "A", "a b", "",
    "a" * 81, ".", "x..y/../z",
]
# "-x" is slug_ok-rejected too, but argparse intercepts a leading-dash
# positional before main()'s gate ever sees it (unrecognized option ->
# SystemExit(2)); it gets its own test below with the `--` separator.
DASH_SLUGS = ["-x"]
GOOD_SLUGS = ["a", "job-1", "x.y_z-9", "a" * 80]


def test_slug_ok_unit(cli):
    for bad in BAD_SLUGS + DASH_SLUGS:
        assert not cli.slug_ok(bad), bad
    for good in GOOD_SLUGS:
        assert cli.slug_ok(good), good


@pytest.mark.parametrize("cmd", ["status", "steer", "log", "kill", "resume", "close"])
@pytest.mark.parametrize("slug", BAD_SLUGS)
def test_main_gate_rejects_bad_slug_every_subcommand(cli, monkeypatch, capsys, cmd, slug):
    argv = ["muse-job", cmd, slug]
    if cmd == "steer":
        argv.append("hello")
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == 1
    err = capsys.readouterr().err
    assert "bad slug" in err, err
    assert slug in err


def test_dash_slug_via_separator_reaches_gate(cli, monkeypatch, capsys):
    # `muse-job status -x`: argparse rejects the leading-dash positional
    # itself (SystemExit 2, unrecognized option) -- safe, but our gate never
    # sees it. With `--`, the slug reaches the gate and is refused there.
    monkeypatch.setattr(sys, "argv", ["muse-job", "status", "--", "-x"])
    assert cli.main() == 1
    assert "bad slug" in capsys.readouterr().err


def test_dash_slug_without_separator_dies_in_argparse(cli, monkeypatch):
    # Documents the boundary: argparse never lets a leading-dash positional
    # become args.slug, so it cannot reach job_dir() unvalidated.
    monkeypatch.setattr(sys, "argv", ["muse-job", "status", "-x"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2


def test_spawn_bad_slug_rejected(cli, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [
        "muse-job", "spawn", "..",
        "--repo", "https://example.com/r.git",
        "--prompt-file", "p.md",
    ])
    assert cli.main() == 1
    assert "bad slug" in capsys.readouterr().err


def test_close_dotdot_leaves_home_untouched(cli, monkeypatch, tmp_path, capsys):
    # Pre-fix, `close ..` resolved job_dir("..") to ~ and the close path
    # acted on it (rmtree ~/tmp, gzip ~/*.log, save ~/job.json). A job.json
    # in ~ (operator accident or plant) is all it took to get past load_job.
    (tmp_path / "job.json").write_text(json.dumps(
        {"state": "active", "pristine": str(tmp_path / "repos" / "r")}))
    victim = tmp_path / "tmp"
    victim.mkdir()
    (victim / "sentinel").write_text("x")
    (tmp_path / "notes.log").write_text("keep me")
    monkeypatch.setattr(sys, "argv", ["muse-job", "close", ".."])
    assert cli.main() == 1
    assert "bad slug" in capsys.readouterr().err
    assert (victim / "sentinel").read_text() == "x"
    assert (tmp_path / "notes.log").exists()


def test_valid_slug_still_reaches_unknown_job(cli, monkeypatch, tmp_path, capsys):
    # The gate must not false-positive: a well-formed slug for a job that
    # does not exist fails at load_job, not at the gate.
    monkeypatch.setattr(sys, "argv", ["muse-job", "status", "nosuchjob"])
    assert cli.main() == 1
    err = capsys.readouterr().err
    assert "unknown job" in err
    assert "bad slug" not in err


def test_list_has_no_slug_and_still_works(cli, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["muse-job", "list", "--json"])
    assert cli.main() == 0
    assert json.loads(capsys.readouterr().out) == []


def test_repo_url_ok_unit(cli):
    assert not cli.repo_url_ok("--upload-pack=id")
    assert not cli.repo_url_ok("-x")
    assert not cli.repo_url_ok("")
    assert not cli.repo_url_ok(None)
    assert not cli.repo_url_ok(123)
    # Issue #793: remote-helper transports are rejected (spawning an
    # external command as the operator); case-insensitive.
    assert not cli.repo_url_ok("ext::sh -c id")
    assert not cli.repo_url_ok("EXT::sh -c id")
    assert not cli.repo_url_ok("fd::0")
    assert not cli.repo_url_ok("FD::0")
    assert cli.repo_url_ok("https://example.com/r.git")
    assert cli.repo_url_ok("git@github.com:ntindle/spark-vm.git")
    assert cli.repo_url_ok("file:///home/ntindle/repos/r")
    assert cli.repo_url_ok("/home/ntindle/repos/r")


@pytest.mark.parametrize("repo", ["--upload-pack=id", "--config=protocol.ext.allow=always", "-x"])
def test_spawn_rejects_leading_dash_repo(cli, monkeypatch, tmp_path, capsys, repo):
    # Equals-form: the only argv shape that delivers a leading-dash value
    # into args.repo (a separate token is refused by argparse itself -- see
    # next test). The spawn gate must refuse it before any filesystem work.
    prompt = tmp_path / "p.md"
    prompt.write_text("do the thing")
    monkeypatch.setattr(sys, "argv", [
        "muse-job", "spawn", "goodslug",
        f"--repo={repo}",
        "--prompt-file", str(prompt),
    ])
    assert cli.main() == 1
    assert "bad repo url" in capsys.readouterr().err
    # Refused before the lock, the clone, any filesystem work.
    assert not (tmp_path / "repos").exists()
    assert not (tmp_path / "muse-jobs").exists()


def test_spawn_dash_repo_separate_token_dies_in_argparse(cli, monkeypatch, tmp_path):
    # Documents the boundary: argparse will not consume an option-looking
    # token as --repo's value, so `--repo --upload-pack=id` never reaches
    # the clone call site through real argv.
    prompt = tmp_path / "p.md"
    prompt.write_text("do the thing")
    monkeypatch.setattr(sys, "argv", [
        "muse-job", "spawn", "goodslug",
        "--repo", "--upload-pack=id",
        "--prompt-file", str(prompt),
    ])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2


def test_spawn_rejects_empty_repo(cli, monkeypatch, tmp_path, capsys):
    prompt = tmp_path / "p.md"
    prompt.write_text("do the thing")
    monkeypatch.setattr(sys, "argv", [
        "muse-job", "spawn", "goodslug",
        "--repo", "",
        "--prompt-file", str(prompt),
    ])
    assert cli.main() == 1
    assert "bad repo url" in capsys.readouterr().err


@pytest.mark.parametrize("repo", ["ext::sh -c id", "EXT::sh -c id", "fd::0"])
def test_spawn_rejects_remote_helper_transports(cli, monkeypatch, tmp_path, capsys, repo):
    # Issue #793: ext::/fd:: reach `git clone` as remote-helper transports --
    # a spawned external command as the operator. Refused at the same gate
    # as the leading dash, before the lock, clone, or any filesystem work.
    prompt = tmp_path / "p.md"
    prompt.write_text("do the thing")
    monkeypatch.setattr(sys, "argv", [
        "muse-job", "spawn", "goodslug",
        f"--repo={repo}",
        "--prompt-file", str(prompt),
    ])
    assert cli.main() == 1
    assert "bad repo url" in capsys.readouterr().err
    assert not (tmp_path / "repos").exists()
    assert not (tmp_path / "muse-jobs").exists()


@pytest.mark.parametrize("repo,name", [
    ("https://example.com/..", ".."),
    ("https://example.com/.", "."),
    ("..", ".."),
])
def test_spawn_rejects_dotdot_repo_name(cli, monkeypatch, tmp_path, capsys, repo, name):
    # Issue #793: the derived pristine path is REPOS_DIR/<host>/<path...>
    # (issue #10 namespacing). `..` escapes to $HOME itself (where the
    # clone would fail into ~) and `.` collapses to REPOS_DIR. Both fail
    # fast with no clone and no job dir; nothing is written outside the
    # containment root.
    prompt = tmp_path / "p.md"
    prompt.write_text("do the thing")
    monkeypatch.setattr(sys, "argv", [
        "muse-job", "spawn", "dotjob",
        f"--repo={repo}",
        "--prompt-file", str(prompt),
    ])
    assert cli.main() == 1
    err = capsys.readouterr().err
    assert "bad repo name from url" in err
    assert name in err
    assert not (tmp_path / "muse-jobs" / "dotjob").exists()
    assert not list((tmp_path / "repos").iterdir()) if (tmp_path / "repos").exists() else True


def test_spawn_legit_repo_names_still_work(cli, monkeypatch, tmp_path, capsys):
    # The dotdot guard must not false-positive: uppercase and long-but-safe
    # repo names (slug_ok() would reject these) derive contained paths and
    # reach the clone call site.
    calls = []

    def fake_run(*argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            args=list(argv), returncode=0, stdout=b"deadbeef\n", stderr=b"")

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: False)
    # Issue #791: _spawn now answers the workspace-trust gate post-launch.
    # The faked run above returns junk pane text, so the real answerer would
    # poll its 20s timeout here -- pin it off; the answering contract is
    # covered in test_tui_banner.py.
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda slug, timeout=20: False)
    # Skip the 90s session-uuid discovery poll: the uuid path is not what
    # this test pins.
    monkeypatch.setattr(cli, "find_session", lambda work, started: "fake-uuid")
    prompt = tmp_path / "p.md"
    prompt.write_text("a perfectly innocent prompt with no secrets in it")
    args = cli.argparse.Namespace(
        slug="casejob", repo="https://example.com/SomeOrg/SomeRepo.git",
        prompt_file=str(prompt), base=None, budget_hours=8, allow_secrets=False)
    cli._spawn(args.slug, args)  # returns None on success; would raise first
    clones = [c for c in calls if list(c)[:2] == ["git", "clone"]]
    assert len(clones) == 1
    # Issue #10: the pristine dir is namespaced host/path, not the bare
    # repo name.
    assert clones[0][-1].endswith(
        os.path.join("repos", "example.com", "SomeOrg", "SomeRepo"))


@pytest.mark.parametrize("base", ["--verify", "--symbolic-full-name", "-x"])
def test_spawn_rejects_dash_base_ref(cli, monkeypatch, tmp_path, capsys, base):
    # Issue #793: --base reaches `rev-parse` in option position. rev-parse
    # has no command-execution options, but the gate is cheap: refuse the
    # leading dash before any clone or filesystem work.
    prompt = tmp_path / "p.md"
    prompt.write_text("do the thing")
    monkeypatch.setattr(sys, "argv", [
        "muse-job", "spawn", "basejob",
        "--repo", "https://example.com/r.git",
        f"--base={base}",
        "--prompt-file", str(prompt),
    ])
    assert cli.main() == 1
    err = capsys.readouterr().err
    assert "bad base ref" in err
    assert not (tmp_path / "muse-jobs" / "basejob").exists()
    # Issue #10: the namespaced dir is repos/<host>/<repo>.
    assert not (tmp_path / "repos" / "example.com" / "r").exists()


def test_rev_parse_gets_base_without_option_separator(cli, monkeypatch, tmp_path):
    # Pins the deliberate choice: rev-parse does NOT honor `--` before the
    # revision (post-`--` args echo verbatim, never resolve), so the base is
    # passed bare as the final arg. A future "add `--`" would silently
    # resolve every base to its literal string -- this test fails first.
    calls = []

    def fake_run(*argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            args=list(argv), returncode=0, stdout=b"deadbeef\n", stderr=b"")

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: False)
    # Issue #791: _spawn now answers the workspace-trust gate post-launch;
    # the faked run returns junk pane text, so pin the answerer off here
    # (its contract is covered in test_tui_banner.py).
    monkeypatch.setattr(cli, "_answer_trust_prompt",
                        lambda slug, timeout=20: False)
    # Skip the 90s session-uuid discovery poll: the uuid path is not what
    # this test pins.
    monkeypatch.setattr(cli, "find_session", lambda work, started: "fake-uuid")
    prompt = tmp_path / "p.md"
    prompt.write_text("a perfectly innocent prompt with no secrets in it")
    args = cli.argparse.Namespace(
        slug="revjob", repo="https://example.com/r.git",
        prompt_file=str(prompt), base="v1.2.3",
        budget_hours=8, allow_secrets=False)
    cli._spawn(args.slug, args)
    # Issue #10: the namespaced dir is repos/<host>/<repo>.
    revs = [c for c in calls if list(c)[:3] == ["git", "-C", os.path.join(
        str(tmp_path), "repos", "example.com", "r")] and "rev-parse" in list(c)]
    assert len(revs) == 1
    assert list(revs[0][-2:]) == ["rev-parse", "v1.2.3"]


def test_clone_passes_option_separator(cli, monkeypatch, tmp_path):
    # Drive _spawn with a stubbed run(): prove the URL reaches git after `--`
    # so it can never be parsed as flags, even if a future caller bypasses
    # repo_url_ok(). The URL is attacker-influenced (copied from issues/chat).
    calls = []

    def fake_run(*argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(
            args=list(argv), returncode=0, stdout=b"deadbeef\n", stderr=b"")

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli, "tmux_alive", lambda slug: False)
    repo = "https://example.com/some/repo.git"
    prompt = tmp_path / "p.md"
    prompt.write_text("a perfectly innocent prompt with no secrets in it")
    args = cli.argparse.Namespace(
        slug="sepjob", repo=repo, prompt_file=str(prompt),
        base=None, budget_hours=8, allow_secrets=False)
    cli._spawn(args.slug, args)
    clones = [c for c in calls if list(c)[:2] == ["git", "clone"]]
    assert len(clones) == 1
    assert list(clones[0]) == [
        "git", "clone", "--", repo,
        # Issue #10: pristine is namespaced host/path, not the bare name.
        os.path.join(str(tmp_path), "repos", "example.com", "some", "repo"),
    ]
