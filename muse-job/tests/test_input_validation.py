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
        os.path.join(str(tmp_path), "repos", "repo"),
    ]
